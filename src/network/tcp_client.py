"""
TCP Client Module for Sending Direct P2P Messages & File Handshakes.
"""

import socket
from typing import Dict, List, Tuple

import config
from src.network.framing import encode_frame


class TCPClient:
    """
    Handles sending framed messages directly to peer TCP sockets.
    """

    @staticmethod
    def send_message(target_ip: str, target_port: int, payload: dict, timeout: float = 5.0) -> bool:
        """
        Connects to target peer, sends a framed message, and closes socket.
        """
        if not target_port or target_port <= 0 or not target_ip:
            return False

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        try:
            sock.connect((target_ip, target_port))
            framed_bytes = encode_frame(payload)
            sock.sendall(framed_bytes)
            print(f"[TCPClient] Sent {payload.get('type', 'MSG')} to {target_ip}:{target_port}")
            return True
        except Exception as e:
            print(f"[TCPClient Send Error to {target_ip}:{target_port}]: {e}")
            return False
        finally:
            try:
                sock.close()
            except Exception:
                pass

    @staticmethod
    def broadcast_message(peers_info: List[Tuple[str, int]], payload: dict) -> Dict[str, bool]:
        """
        Sends a payload to multiple target peers concurrently or sequentially.
        Returns a dictionary mapping peer_ip -> success boolean.
        """
        results = {}
        for target_ip, target_port in peers_info:
            if not target_port or target_port <= 0:
                continue
            success = TCPClient.send_message(target_ip, target_port, payload)
            results[target_ip] = success
        return results
