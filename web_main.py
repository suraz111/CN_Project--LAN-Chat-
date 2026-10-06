"""
Standalone Headless Web Runner for Simple LAN Chat.
Runs the Discovery Engine, TCP Server, and Web Gateway without requiring a Tkinter GUI.
Access from any mobile phone, tablet, or browser on your LAN: http://<local_ip>:8080
"""

import argparse
import os
import signal
import socket
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import config
from src.models.message import MessageType, Packet
from src.models.peer import Peer
from src.network.discovery import DiscoveryEngine
from src.network.tcp_server import TCPServer
from src.utils.net_utils import get_local_ip
from src.web.gateway import WebGateway


class HeadlessAppContext:
    """
    Lightweight headless context fulfilling the interface expected by WebGateway.
    Maintains active peers, channel histories, and coordinates network discovery.
    """

    def __init__(self, username: str, tcp_port: int = config.DEFAULT_TCP_PORT) -> None:
        self.peer_id = uuid.uuid4().hex[:8]
        self.username = username
        self.device_name = f"{socket.gethostname()} (Web)"
        self.local_ip = get_local_ip()
        self.requested_tcp_port = tcp_port
        self.actual_tcp_port = 0
        self.web_port = 0

        # Peer directory & channel histories
        self.peers: Dict[str, Peer] = {}
        self.chat_histories: Dict[Optional[str], List[dict]] = {None: []}
        self.unread_counts: Dict[Optional[str], int] = {}
        self.seen_message_ids: set = set()
        self.custom_rooms: set = set(["#general", "#project", "#study"])
        self.pinned_messages: Dict[Optional[str], Optional[dict]] = {}

        # Network engines
        self.tcp_server: Optional[TCPServer] = None
        self.discovery_engine: Optional[DiscoveryEngine] = None
        self.web_gateway: Optional[WebGateway] = None

    def start(self, web_port: int = 8080) -> None:
        """Starts TCP Server, Discovery Engine, and Web Gateway."""
        # 1. Start TCP Server
        self.tcp_server = TCPServer(
            port=self.requested_tcp_port,
            on_message_received=self._on_tcp_message_received,
        )
        self.actual_tcp_port = self.tcp_server.start()

        # 2. Start Discovery Engine
        self.discovery_engine = DiscoveryEngine(
            peer_id=self.peer_id,
            username=self.username,
            device_name=self.device_name,
            tcp_port=self.actual_tcp_port,
            on_peer_updated=self._on_peer_updated,
            on_peer_removed=self._on_peer_removed,
        )
        self.discovery_engine.start()

        # 3. Start Web Gateway
        self.web_gateway = WebGateway(app_context=self, host="0.0.0.0", port=web_port)
        self.web_port = self.web_gateway.start()

        self._append_message(
            None,
            "System",
            f"Headless Web Gateway started on http://{self.local_ip}:{self.web_port}",
            category="system",
        )

    def stop(self) -> None:
        """Clean shutdown of all engines."""
        print("\n[Shutdown] Stopping Web Gateway and Network Engines...")
        if self.web_gateway:
            self.web_gateway.stop()
        if self.discovery_engine:
            self.discovery_engine.stop()
        if self.tcp_server:
            self.tcp_server.stop()
        print("[Shutdown] Completed.")

    def register_web_peer(self, client_id: str, username: str, ip_address: str) -> None:
        """Registers an active web/mobile client."""
        is_new = client_id not in self.peers
        peer = Peer(
            peer_id=client_id,
            username=username,
            device_name="Mobile Browser",
            ip_address=ip_address,
            tcp_port=0,
            status="Online",
            is_web=True,
        )
        self.peers[client_id] = peer
        if is_new:
            self._append_message(None, "System", f"Mobile/Web peer '{username}' ({ip_address}) connected.", category="system")

    def remove_web_peer(self, client_id: str) -> None:
        """Removes a disconnected web/mobile client."""
        if client_id in self.peers:
            removed = self.peers.pop(client_id)
            self._append_message(None, "System", f"Mobile/Web peer '{removed.username}' disconnected.", category="system")

    def manual_connect_peer(self, target_str: str) -> bool:
        """Manually connects to a peer by IP:Port over TCP and exchanges presence."""
        if not target_str:
            return False
        try:
            if ":" in target_str:
                ip, port_str = target_str.split(":", 1)
                port = int(port_str.strip())
            else:
                ip = target_str.strip()
                port = config.DEFAULT_TCP_PORT

            packet = Packet(
                type=MessageType.HEARTBEAT,
                sender_id=self.peer_id,
                sender_name=self.username,
                payload={
                    "device_name": self.device_name,
                    "tcp_port": self.actual_tcp_port,
                    "ip_address": self.local_ip,
                    "manual": True,
                },
            )
            return TCPClient.send_message(ip, port, packet.to_dict())
        except Exception:
            return False

    def _append_message(
        self,
        channel_id: Optional[str],
        sender: str,
        message: str,
        category: str = "peer",
        sender_id: Optional[str] = None,
        msg_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Appends a message to channel history and logs to console."""
        now = time.time()
        timestamp = time.strftime("%H:%M:%S", time.localtime(now))
        effective_sender_id = sender_id or (self.peer_id if (category in ("self", "file") and "You" in sender) else None)
        entry_id = msg_id or f"{now}_{uuid.uuid4().hex[:6]}"

        if channel_id not in self.chat_histories:
            self.chat_histories[channel_id] = []

        if any(e.get("id") == entry_id for e in self.chat_histories[channel_id]):
            return

        entry = {
            "id": entry_id,
            "timestamp": timestamp,
            "timestamp_epoch": now,
            "sender": sender,
            "sender_id": effective_sender_id,
            "message": message,
            "category": category,
            "channel": channel_id,
            "reactions": kwargs.get("reactions", {}),
            "pinned": kwargs.get("pinned", False),
        }

        self.chat_histories[channel_id].append(entry)

        target = "Group" if channel_id is None else f"DM:{channel_id[:6]}"
        print(f"[{timestamp}] [{target}] {sender}: {message}")

    def _handle_incoming_typing(self, packet: Packet) -> None:
        """Handles incoming typing packets."""
        pass

    def _on_peer_updated(self, peer: Peer) -> None:
        if peer.peer_id == self.peer_id:
            return
        if peer.ip_address in (self.local_ip, "127.0.0.1") and peer.tcp_port == self.actual_tcp_port:
            return
        is_new = peer.peer_id not in self.peers
        self.peers[peer.peer_id] = peer
        if is_new:
            self._append_message(
                None,
                "System",
                f"Peer '{peer.username}' ({peer.ip_address}:{peer.tcp_port}) discovered on LAN.",
                category="system",
            )

    def _on_peer_removed(self, peer_id: str) -> None:
        if peer_id in self.peers:
            removed = self.peers.pop(peer_id)
            self._append_message(
                None,
                "System",
                f"Peer '{removed.username}' went offline.",
                category="system",
            )

    def _on_tcp_message_received(self, payload: dict, client_ip: str) -> None:
        try:
            packet = Packet.from_dict(payload)
            if packet.sender_id == self.peer_id:
                return
            if hasattr(packet, "msg_id") and packet.msg_id:
                if packet.msg_id in self.seen_message_ids:
                    return
                self.seen_message_ids.add(packet.msg_id)

            if packet.type in (MessageType.GROUP_CHAT, MessageType.ROOM_MESSAGE):
                text = packet.payload.get("text", "")
                room = packet.payload.get("room")
                if room:
                    if not hasattr(self, "custom_rooms"):
                        self.custom_rooms = set(["#general", "#project", "#study"])
                    self.custom_rooms.add(room)
                    self._append_message(room, f"{packet.sender_name} ({room})", text, category="peer", sender_id=packet.sender_id, msg_id=packet.msg_id)
                else:
                    self._append_message(None, f"{packet.sender_name} (Group)", text, category="peer", sender_id=packet.sender_id, msg_id=packet.msg_id)
            elif packet.type == MessageType.CHAT:
                text = packet.payload.get("text", "")
                self._append_message(packet.sender_id, packet.sender_name, text, category="dm", sender_id=packet.sender_id, msg_id=packet.msg_id)
            elif packet.type == MessageType.TYPING:
                self._handle_incoming_typing(packet)
        except Exception as e:
            print(f"[Error] Failed handling packet from {client_ip}: {e}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    default_port = int(os.environ.get("PORT", 8080))
    parser = argparse.ArgumentParser(description="Simple LAN Chat — Standalone Web Gateway")
    parser.add_argument("--username", "-u", type=str, default=f"{socket.gethostname()}-Web", help="Display Name")
    parser.add_argument("--port", "-p", type=int, default=default_port, help="Web Interface HTTP Port (default: 8080 or $PORT)")
    parser.add_argument("--tcp-port", "-t", type=int, default=config.DEFAULT_TCP_PORT, help="LAN TCP Port")
    args = parser.parse_args()

    app = HeadlessAppContext(username=args.username, tcp_port=args.tcp_port)
    app.start(web_port=args.port)

    print("=" * 65)
    print("SIMPLE LAN CHAT — MOBILE WEB INTERFACE")
    print("=" * 65)
    print(f"* User / Host Name:  {app.username}")
    print(f"* Local LAN IP:      {app.local_ip}")
    print(f"* Peer TCP Port:     {app.actual_tcp_port}")
    print(f"* Web HTTP Port:     {app.web_port}")
    print("-" * 65)
    print(f">> OPEN ON YOUR PHONE: http://{app.local_ip}:{app.web_port}")
    print("   (Ensure your phone is connected to the same Wi-Fi network)")
    print("=" * 65)
    print("Press Ctrl+C to terminate the web server.\n")

    def sig_handler(sig, frame):
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        app.stop()


if __name__ == "__main__":
    main()
