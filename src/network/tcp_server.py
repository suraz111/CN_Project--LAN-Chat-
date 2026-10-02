"""
TCP Server Module for Receiving P2P Messages & File Transfers.
"""

import socket
import threading
from typing import Callable, Dict, Optional

import config
from src.network.framing import FrameDecoder


class TCPServer:
    """
    TCP Master Server listening on a local port for incoming connections from network peers.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = config.DEFAULT_TCP_PORT,
        on_message_received: Optional[Callable[[dict, str], None]] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.on_message_received = on_message_received

        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._client_threads: Dict[str, threading.Thread] = {}

    def start(self) -> int:
        """
        Binds to TCP port and starts master listener thread.
        Returns the bound TCP port (useful if dynamic port 0 is used).
        """
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # On Windows, SO_EXCLUSIVEADDRUSE prevents port stealing and ensures OSError is raised
        # if the port is already in use, allowing fallback to dynamic port (0).
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            try:
                self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except OSError:
                pass
        else:
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self._server_socket.bind((self.host, self.port))
        except OSError:
            # Fallback to an available OS port if default TCP port (50001) is already in use
            self._server_socket.bind((self.host, 0))

        self.port = self._server_socket.getsockname()[1]
        self._server_socket.listen(10)
        self._server_socket.settimeout(1.0)

        self._running = True
        self._listener_thread = threading.Thread(target=self._listen_worker, daemon=True)
        self._listener_thread.start()

        print(f"[TCPServer] Bound and listening on TCP port {self.port}")
        return self.port

    def stop(self) -> None:
        """Stops the TCP server and closes listener socket."""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass

    def _listen_worker(self) -> None:
        """Worker thread accepting incoming peer socket connections."""
        while self._running:
            try:
                client_sock, addr = self._server_socket.accept()
                client_thread = threading.Thread(
                    target=self._handle_client, args=(client_sock, addr[0]), daemon=True
                )
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    print(f"[TCPServer Accept Error]: {e}")

    def _handle_client(self, client_sock: socket.socket, client_ip: str) -> None:
        """Handles framed socket communication for an accepted client socket."""
        decoder = FrameDecoder()
        client_sock.settimeout(5.0)

        try:
            while self._running:
                try:
                    chunk = client_sock.recv(config.MAX_SOCKET_BUFFER)
                    if not chunk:
                        # Client disconnected
                        break

                    frames = decoder.feed(chunk)
                    for frame in frames:
                        msg_type = frame.get("type", "UNKNOWN")
                        sender = frame.get("sender_name", client_ip)
                        print(f"[TCPServer] Received {msg_type} from {sender} ({client_ip})")
                        if self.on_message_received:
                            self.on_message_received(frame, client_ip)

                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[TCPServer Client Error from {client_ip}]: {e}")
                    break
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
