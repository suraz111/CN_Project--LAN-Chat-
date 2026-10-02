"""
UDP Broadcast Discovery Module for Peer Presence Detection & Heartbeats.
"""

import json
import socket
import threading
import time
from typing import Callable, Dict, Optional

import config
from src.models.message import MessageType, Packet
from src.models.peer import Peer
from src.utils.net_utils import get_broadcast_address, get_local_ip


class DiscoveryEngine:
    """
    Manages sending UDP heartbeat broadcasts and listening for broadcasts from other peers on the local subnet.
    """

    def __init__(
        self,
        peer_id: str,
        username: str,
        device_name: str,
        tcp_port: int,
        udp_port: int = config.DEFAULT_UDP_PORT,
        on_peer_updated: Optional[Callable[[Peer], None]] = None,
        on_peer_removed: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.peer_id = peer_id
        self.username = username
        self.device_name = device_name
        self.tcp_port = tcp_port
        self.udp_port = udp_port

        self.on_peer_updated = on_peer_updated
        self.on_peer_removed = on_peer_removed

        self.peers: Dict[str, Peer] = {}
        self._peers_lock = threading.Lock()
        self._running = False

        self._send_thread: Optional[threading.Thread] = None
        self._listen_thread: Optional[threading.Thread] = None
        self._cleanup_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start UDP broadcast listener, sender, and peer cleanup background threads."""
        self._running = True

        self._listen_thread = threading.Thread(target=self._listen_worker, daemon=True)
        self._send_thread = threading.Thread(target=self._send_worker, daemon=True)
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)

        self._listen_thread.start()
        self._send_thread.start()
        self._cleanup_thread.start()

    def stop(self) -> None:
        """Send a GOODBYE broadcast and stop all background threads."""
        self._running = False
        self._send_goodbye()

    def update_username(self, new_name: str) -> None:
        """Update local username for future heartbeats."""
        self.username = new_name

    def _send_goodbye(self) -> None:
        """Emits a final goodbye message over UDP broadcast."""
        try:
            packet = Packet(
                type=MessageType.GOODBYE,
                sender_id=self.peer_id,
                sender_name=self.username,
                payload={"device_name": self.device_name},
            )
            self._broadcast_packet(packet)
        except Exception as e:
            print(f"[Discovery] Error sending goodbye: {e}")

    def _broadcast_packet(self, packet: Packet) -> None:
        """Broadcasts a packet datagram over UDP."""
        data = json.dumps(packet.to_dict()).encode("utf-8")
        targets = {config.BROADCAST_ADDRESS}
        local_ip = get_local_ip()
        if local_ip == "127.0.0.1":
            targets.add("127.255.255.255")

        for target in targets:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(2.0)
                sock.sendto(data, (target, self.udp_port))
            except Exception:
                pass
            finally:
                sock.close()

    def _send_worker(self) -> None:
        """Periodically broadcasts presence heartbeat."""
        while self._running:
            try:
                packet = Packet(
                    type=MessageType.HEARTBEAT,
                    sender_id=self.peer_id,
                    sender_name=self.username,
                    payload={
                        "device_name": self.device_name,
                        "tcp_port": self.tcp_port,
                        "ip_address": get_local_ip(),
                    },
                )
                self._broadcast_packet(packet)
            except Exception as e:
                print(f"[Discovery Sender Error]: {e}")

            time.sleep(config.HEARTBEAT_INTERVAL)

    def _listen_worker(self) -> None:
        """Listens for incoming UDP broadcast datagrams from peers on the local subnet."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", self.udp_port))
            sock.settimeout(1.0)

            while self._running:
                try:
                    data, addr = sock.recvfrom(4096)
                    self._process_datagram(data, addr[0])
                except socket.timeout:
                    continue
                except Exception as e:
                    if self._running:
                        print(f"[Discovery Listener Error]: {e}")
        finally:
            sock.close()

    def _process_datagram(self, data: bytes, sender_ip: str) -> None:
        """Processes raw UDP datagrams."""
        try:
            payload_dict = json.loads(data.decode("utf-8"))
            packet = Packet.from_dict(payload_dict)

            # Ignore own heartbeats / self
            if packet.sender_id == self.peer_id:
                return

            tcp_port = packet.payload.get("tcp_port", config.DEFAULT_TCP_PORT)
            local_ip = get_local_ip()
            if (sender_ip in (local_ip, "127.0.0.1") and tcp_port == self.tcp_port):
                return

            if packet.type == MessageType.HEARTBEAT:
                device_name = packet.payload.get("device_name", "Unknown")

                with self._peers_lock:
                    if packet.sender_id in self.peers:
                        peer = self.peers[packet.sender_id]
                        peer.update_heartbeat(username=packet.sender_name)
                        peer.ip_address = sender_ip
                        peer.tcp_port = tcp_port
                    else:
                        peer = Peer(
                            peer_id=packet.sender_id,
                            username=packet.sender_name,
                            device_name=device_name,
                            ip_address=sender_ip,
                            tcp_port=tcp_port,
                        )
                        self.peers[packet.sender_id] = peer
                        print(f"[Discovery] Discovered peer: {peer.username} ({peer.ip_address}:{peer.tcp_port})")

                if self.on_peer_updated:
                    self.on_peer_updated(self.peers[packet.sender_id])

            elif packet.type == MessageType.GOODBYE:
                removed_peer = None
                with self._peers_lock:
                    if packet.sender_id in self.peers:
                        removed_peer = self.peers.pop(packet.sender_id)

                if removed_peer:
                    print(f"[Discovery] Peer left: {removed_peer.username} ({removed_peer.ip_address})")

                if self.on_peer_removed:
                    self.on_peer_removed(packet.sender_id)

        except Exception as e:
            print(f"[Discovery Process Error]: {e}")

    def _cleanup_worker(self) -> None:
        """Monitors peer last_seen timestamp and cleans up inactive peers."""
        while self._running:
            expired_ids = []
            with self._peers_lock:
                for peer_id, peer in list(self.peers.items()):
                    if peer.is_expired(config.PEER_TIMEOUT):
                        expired_ids.append(peer_id)
                        del self.peers[peer_id]

            for peer_id in expired_ids:
                if self.on_peer_removed:
                    self.on_peer_removed(peer_id)

            time.sleep(2.0)
