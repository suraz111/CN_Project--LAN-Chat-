"""
Binary File Transfer Module with Chunking and SHA-256 Checksum Verification.
"""

import hashlib
import os
import socket
from pathlib import Path
from typing import Callable, Optional, Tuple

import config


class FileSender:
    """
    Handles streaming binary file chunks to recipient TCP socket with SHA-256 verification.
    """

    @staticmethod
    def calculate_sha256(filepath: Path) -> str:
        """Computes SHA-256 checksum hash digest for a given file."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(config.MAX_SOCKET_BUFFER):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def send_file(
        target_ip: str,
        target_port: int,
        filepath: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """
        Sends raw file binary data to a listening recipient socket.
        """
        if not filepath.exists():
            print(f"[FileSender Error]: File {filepath} does not exist.")
            return False

        filesize = filepath.stat().st_size
        sent_bytes = 0

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15.0)

        try:
            sock.connect((target_ip, target_port))
            print(f"[FileSender] Connected to {target_ip}:{target_port}. Streaming '{filepath.name}' ({filesize} bytes)...")
            with open(filepath, "rb") as f:
                while chunk := f.read(config.MAX_SOCKET_BUFFER):
                    sock.sendall(chunk)
                    sent_bytes += len(chunk)

                    if progress_callback:
                        progress_callback(sent_bytes, filesize)

            print(f"[FileSender] Finished sending '{filepath.name}' ({sent_bytes}/{filesize} bytes).")
            return True

        except Exception as e:
            print(f"[FileSender Error sending to {target_ip}:{target_port}]: {e}")
            return False
        finally:
            try:
                sock.close()
            except Exception:
                pass


class FileReceiver:
    """
    Handles receiving raw binary file data and verifying SHA-256 digest on completion.
    """

    @staticmethod
    def create_listener(host: str = "0.0.0.0", port: int = 0) -> Tuple[socket.socket, int]:
        """
        Creates and binds a temporary listening socket on an OS-assigned port.
        Returns (server_socket, bound_port).
        """
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            try:
                server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except OSError:
                pass
        server_sock.bind((host, port))
        bound_port = server_sock.getsockname()[1]
        server_sock.listen(1)
        server_sock.settimeout(20.0)
        return server_sock, bound_port

    @staticmethod
    def receive_stream(
        server_sock: socket.socket,
        save_path: Path,
        filesize: int,
        expected_sha256: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """
        Accepts sender connection on pre-bound listener socket and streams file to disk.
        Closes server_sock upon completion.
        """
        received_bytes = 0
        sha256 = hashlib.sha256()

        os.makedirs(save_path.parent, exist_ok=True)

        try:
            conn, addr = server_sock.accept()
            conn.settimeout(15.0)
            print(f"[FileReceiver] Accepted connection from {addr[0]}. Receiving '{save_path.name}' ({filesize} bytes)...")

            with open(save_path, "wb") as f:
                while received_bytes < filesize:
                    chunk = conn.recv(min(config.MAX_SOCKET_BUFFER, filesize - received_bytes))
                    if not chunk:
                        break

                    f.write(chunk)
                    sha256.update(chunk)
                    received_bytes += len(chunk)

                    if progress_callback:
                        progress_callback(received_bytes, filesize)

            actual_sha256 = sha256.hexdigest()
            success = (received_bytes == filesize) and (actual_sha256 == expected_sha256)

            if success:
                print(f"[FileReceiver] Successfully received '{save_path.name}' ({received_bytes} bytes). Checksum verified.")
            else:
                print(
                    f"[FileReceiver Warning] Hash mismatch or incomplete transfer for '{save_path.name}'! "
                    f"Bytes: {received_bytes}/{filesize}. Expected: {expected_sha256}, Got: {actual_sha256}"
                )

            try:
                conn.close()
            except Exception:
                pass

            return success

        except Exception as e:
            print(f"[FileReceiver Error]: {e}")
            return False
        finally:
            try:
                server_sock.close()
            except Exception:
                pass

    @staticmethod
    def receive_file(
        save_path: Path,
        filesize: int,
        expected_sha256: str,
        host: str = "0.0.0.0",
        port: int = 0,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[bool, int]:
        """
        Listens on a temporary port to receive a binary file stream.
        Returns (success_boolean, bound_port).
        """
        server_sock, bound_port = FileReceiver.create_listener(host, port)
        success = FileReceiver.receive_stream(
            server_sock, save_path, filesize, expected_sha256, progress_callback
        )
        return success, bound_port
