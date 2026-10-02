"""
Web Gateway HTTP Server & REST API for Mobile Browser Access.
Enables any mobile phone or browser on the same Wi-Fi/LAN to access the chat network.
"""

import email
import email.policy
from email.parser import BytesParser
import http.server
import json
import mimetypes
import os
import socket
import threading
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from src.models.message import MessageType, Packet
from src.network.file_transfer import FileSender
from src.network.tcp_client import TCPClient
from src.utils.net_utils import get_local_ip


class WebGatewayHandler(http.server.BaseHTTPRequestHandler):
    """
    HTTP Request Handler serving the Mobile Single Page Application,
    REST APIs for peer directory, multi-channel messaging, and file streaming.
    """

    server: "WebGatewayServer"  # Type hint for custom server attribute

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP access logs to keep terminal clean."""
        pass

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Sends a JSON response with proper CORS headers."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _safe_append_message(
        self,
        ctx: Any,
        channel_id: Any,
        sender: str,
        message: str,
        category: str = "peer",
        sender_id: Optional[str] = None,
        msg_id: Optional[str] = None,
    ) -> None:
        """Invokes ctx._append_message gracefully supporting optional msg_id parameter."""
        try:
            ctx._append_message(
                channel_id,
                sender,
                message,
                category=category,
                sender_id=sender_id,
                msg_id=msg_id,
            )
        except TypeError:
            ctx._append_message(
                channel_id,
                sender,
                message,
                category=category,
                sender_id=sender_id,
            )

    def _send_file_content(self, filepath: Path) -> None:
        """Streams a static asset or download file with appropriate MIME type."""
        if not filepath.exists() or not filepath.is_file():
            self.send_error(404, "File not found")
            return

        mime_type, _ = mimetypes.guess_type(str(filepath))
        if not mime_type:
            mime_type = "application/octet-stream"

        try:
            filesize = filepath.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(filesize))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            with open(filepath, "rb") as f:
                while chunk := f.read(config.MAX_SOCKET_BUFFER):
                    self.wfile.write(chunk)
        except Exception:
            pass

    def do_HEAD(self) -> None:
        """Handle HTTP HEAD requests."""
        self.do_GET()

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        """Handles HTTP GET requests for static assets and REST data."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        static_dir = Path(__file__).parent / "static"

        # 1. Static Web Assets
        if path in ("/", "/index.html"):
            self._send_file_content(static_dir / "index.html")
            return
        elif path == "/style.css":
            self._send_file_content(static_dir / "style.css")
            return
        elif path == "/app.js":
            self._send_file_content(static_dir / "app.js")
            return

        # 2. File Download Route: /downloads/<filename>
        elif path.startswith("/downloads/"):
            filename = urllib.parse.unquote(path[len("/downloads/") :])
            download_dir = config.DEFAULT_DOWNLOAD_DIR
            target_path = (download_dir / filename).resolve()

            # Path traversal security guard
            if not str(target_path).startswith(str(download_dir.resolve())):
                self.send_error(403, "Access forbidden")
                return

            self._send_file_content(target_path)
            return

        # 3. API: Status & Peer Directory
        elif path == "/api/status":
            ctx = self.server.app_context
            client_id = query.get("client_id", [None])[0]
            client_name = query.get("username", ["Mobile User"])[0]

            if client_id:
                self.server.touch_client(client_id, client_name, self.client_address[0])

            peers_list = []

            # 1. The Host Desktop User (always first so mobile clients can DM the host)
            peers_list.append(
                {
                    "peer_id": ctx.peer_id,
                    "username": f"{ctx.username} (Host)",
                    "device_name": getattr(ctx, "device_name", "Host PC"),
                    "ip_address": ctx.local_ip,
                    "tcp_port": getattr(ctx, "actual_tcp_port", config.DEFAULT_TCP_PORT),
                    "status": "Online",
                    "is_host": True,
                    "is_web": False,
                }
            )

            # 2. Other Web / Mobile Clients connected to this gateway
            with self.server.clients_lock:
                for cid, cinfo in self.server.web_clients.items():
                    if cid != client_id:
                        peers_list.append(
                            {
                                "peer_id": cid,
                                "username": cinfo["username"],
                                "device_name": "Mobile / Web",
                                "ip_address": cinfo["ip_address"],
                                "tcp_port": 0,
                                "status": "Online",
                                "is_host": False,
                                "is_web": True,
                            }
                        )

            # 3. Regular LAN TCP peers discovered via UDP
            if hasattr(ctx, "discovery_engine") and hasattr(ctx.discovery_engine, "_peers_lock"):
                with ctx.discovery_engine._peers_lock:
                    peers_snapshot = list(ctx.peers.values())
            else:
                peers_snapshot = list(ctx.peers.values())

            for p in peers_snapshot:
                # Do not re-add web peers or the host
                if getattr(p, "is_web", False) or p.peer_id == ctx.peer_id:
                    continue
                peers_list.append(
                    {
                        "peer_id": p.peer_id,
                        "username": p.username,
                        "device_name": p.device_name,
                        "ip_address": p.ip_address,
                        "tcp_port": p.tcp_port,
                        "status": p.status,
                        "is_host": False,
                        "is_web": False,
                    }
                )

            # Calculate unread counts and pending notification events for this client
            unreads = {}
            notifications = []
            if client_id:
                read_times = self.server.client_read_times.get(client_id, {})

                # 1. Group Broadcast messages
                group_last_read = read_times.get(None, 0.0)
                group_msgs = ctx.chat_histories.get(None, [])
                new_group = [m for m in group_msgs if m.get("timestamp_epoch", 0) > group_last_read and m.get("sender_id") != client_id]
                unreads["group"] = len(new_group)
                for m in new_group[-5:]:
                    notifications.append({
                        "id": m.get("id") or f"{m.get('timestamp_epoch')}_{m.get('sender')}",
                        "channel": None,
                        "sender": m.get("sender", "Group Peer"),
                        "message": m.get("message", ""),
                        "timestamp": m.get("timestamp", ""),
                        "timestamp_epoch": m.get("timestamp_epoch", 0),
                        "is_dm": False,
                    })

                # 2. Private DMs from Desktop Host
                host_last_read = read_times.get(ctx.peer_id, 0.0)
                host_msgs = ctx.chat_histories.get(client_id, [])
                new_host = [m for m in host_msgs if m.get("timestamp_epoch", 0) > host_last_read and m.get("sender_id") != client_id]
                unreads[ctx.peer_id] = len(new_host)
                for m in new_host[-5:]:
                    notifications.append({
                        "id": m.get("id") or f"{m.get('timestamp_epoch')}_{m.get('sender')}",
                        "channel": ctx.peer_id,
                        "sender": f"{ctx.username} (Host)",
                        "message": m.get("message", ""),
                        "timestamp": m.get("timestamp", ""),
                        "timestamp_epoch": m.get("timestamp_epoch", 0),
                        "is_dm": True,
                    })

                # 3. Private DMs from other Web Clients
                for cid in self.server.web_clients:
                    if cid != client_id:
                        dm_k = f"dm_{min(client_id, cid)}_{max(client_id, cid)}"
                        cid_last_read = read_times.get(cid, 0.0)
                        cid_msgs = ctx.chat_histories.get(dm_k, [])
                        new_cid = [m for m in cid_msgs if m.get("timestamp_epoch", 0) > cid_last_read and m.get("sender_id") != client_id]
                        unreads[cid] = len(new_cid)
                        other_name = self.server.web_clients[cid].get("username", "Peer")
                        for m in new_cid[-5:]:
                            notifications.append({
                                "id": m.get("id") or f"{m.get('timestamp_epoch')}_{m.get('sender')}",
                                "channel": cid,
                                "sender": f"{other_name} 📱",
                                "message": m.get("message", ""),
                                "timestamp": m.get("timestamp", ""),
                                "timestamp_epoch": m.get("timestamp_epoch", 0),
                                "is_dm": True,
                            })

                # 4. Private DMs from remote LAN TCP desktop peers
                for pid, p in ctx.peers.items():
                    if getattr(p, "is_web", False) or pid == ctx.peer_id:
                        continue
                    p_last_read = read_times.get(pid, 0.0)
                    p_msgs = ctx.chat_histories.get(pid, [])
                    new_p = [m for m in p_msgs if m.get("timestamp_epoch", 0) > p_last_read and m.get("sender_id") != client_id]
                    if new_p:
                        unreads[pid] = len(new_p)
                        for m in new_p[-5:]:
                            notifications.append({
                                "id": m.get("id") or f"{m.get('timestamp_epoch')}_{m.get('sender')}",
                                "channel": pid,
                                "sender": p.username,
                                "message": m.get("message", ""),
                                "timestamp": m.get("timestamp", ""),
                                "timestamp_epoch": m.get("timestamp_epoch", 0),
                                "is_dm": True,
                            })

            self._send_json(
                {
                    "online": True,
                    "app_name": config.APP_NAME,
                    "version": config.APP_VERSION,
                    "host_user": ctx.username,
                    "username": ctx.username,
                    "host_ip": ctx.local_ip,
                    "local_ip": ctx.local_ip,
                    "host_port": ctx.actual_tcp_port,
                    "tcp_port": ctx.actual_tcp_port,
                    "peer_id": ctx.peer_id,
                    "active_peers": peers_list,
                    "peers": peers_list,
                    "unreads": unreads,
                    "notifications": notifications,
                }
            )
            return

        # 4. API: Messages for a specific channel
        elif path == "/api/messages":
            ctx = self.server.app_context
            raw_channel = query.get("channel", [None])[0]
            channel_id = None if raw_channel in (None, "", "null", "group") else raw_channel
            client_id = query.get("client_id", [None])[0]

            since_str = query.get("since", ["0"])[0]
            try:
                since = float(since_str)
            except ValueError:
                since = 0.0

            # Keep client activity alive and mark channel as read
            if client_id:
                client_name = query.get("username", ["Mobile User"])[0]
                self.server.touch_client(client_id, client_name, self.client_address[0])
                self.server.mark_read(client_id, channel_id)

            # Resolve history storage key:
            if channel_id is None:
                history_key = None
            elif channel_id == ctx.peer_id or channel_id == "host":
                # DM conversation with the Host is stored on desktop under this web client's ID
                history_key = client_id
            elif client_id and channel_id in self.server.web_clients:
                # DM conversation between two web clients
                history_key = f"dm_{min(client_id, channel_id)}_{max(client_id, channel_id)}"
            else:
                history_key = channel_id

            history = ctx.chat_histories.get(history_key, [])

            if since <= 0:
                raw_messages = list(history)
            else:
                raw_messages = [
                    msg for msg in history
                    if msg.get("timestamp_epoch", 0) > since
                ]

            formatted_messages = []
            for msg in raw_messages:
                m_copy = dict(msg)
                msg_sender_id = m_copy.get("sender_id")
                msg_cat = m_copy.get("category", "peer")

                if client_id and msg_sender_id == client_id:
                    # Message authored by this mobile client
                    m_copy["is_self"] = True
                    m_copy["category"] = "self"
                    m_copy["sender"] = f"{client_name} (You)" if "client_name" in locals() and client_name else "You"
                elif msg_sender_id == ctx.peer_id or msg_cat == "self" or "You" in str(m_copy.get("sender", "")):
                    # Message authored by the Desktop Host
                    m_copy["is_self"] = False
                    m_copy["category"] = "peer" if msg_cat != "file" else "file"
                    m_copy["sender"] = f"{ctx.username} (Host)"
                else:
                    m_copy["is_self"] = False
                formatted_messages.append(m_copy)

            self._send_json({
                "channel": channel_id,
                "history_key": history_key,
                "messages": formatted_messages,
                "server_time": time.time(),
            })
            return

        # 5. API: Ping Peer Latency Probe
        elif path == "/api/ping":
            ctx = self.server.app_context
            target_peer_id = query.get("peer_id", [None])[0]
            target_str = query.get("target", [None])[0]

            t0 = time.time()
            if target_peer_id in (ctx.peer_id, "host", None) and not target_str:
                self._send_json({"success": True, "rtt_ms": 1.0, "status": "Host Gateway Active"})
                return

            if target_peer_id and target_peer_id in self.server.web_clients:
                self._send_json({"success": True, "rtt_ms": 2.0, "status": "Web Peer Active via Gateway"})
                return

            ip = None
            port = config.DEFAULT_TCP_PORT
            if target_str:
                if ":" in target_str:
                    ip, p_str = target_str.split(":", 1)
                    try:
                        port = int(p_str)
                    except ValueError:
                        port = config.DEFAULT_TCP_PORT
                else:
                    ip = target_str
            elif target_peer_id and target_peer_id in ctx.peers:
                peer = ctx.peers[target_peer_id]
                ip = peer.ip_address
                port = peer.tcp_port

            if not ip:
                self._send_json({"success": False, "error": "Peer not found or unreachable"}, status=404)
                return

            try:
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.settimeout(2.0)
                test_sock.connect((ip, port))
                test_sock.close()
                rtt = round((time.time() - t0) * 1000, 1)
                self._send_json({"success": True, "rtt_ms": rtt, "ip": ip, "port": port})
            except Exception as e:
                self._send_json({"success": False, "error": str(e), "ip": ip, "port": port})
            return

        self.send_error(404, "Endpoint not found")

    def do_POST(self) -> None:
        """Handles HTTP POST requests for sending messages, typing events, and file uploads."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        ctx = self.server.app_context

        # Read JSON payload if applicable
        content_length = int(self.headers.get("Content-Length", 0))

        # 1. Send Message Route
        if path == "/api/send":
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            sender_name = data.get("sender", "Mobile User").strip() or "Mobile User"
            client_id = data.get("client_id") or f"mob_{ctx.peer_id[:4]}"
            raw_channel = data.get("channel")
            channel_id = None if raw_channel in (None, "", "null", "group") else raw_channel
            text = (data.get("text") or data.get("message") or "").strip()

            if not text:
                self._send_json({"success": False, "error": "Empty message"}, status=400)
                return

            self.server.touch_client(client_id, sender_name, self.client_address[0])

            now = time.time()
            timestamp_str = time.strftime("%H:%M:%S", time.localtime(now))

            # Case A: Group Broadcast
            if channel_id is None:
                packet = Packet(
                    type=MessageType.GROUP_CHAT,
                    sender_id=client_id,
                    sender_name=f"{sender_name} 📱",
                    payload={"text": text},
                )
                if hasattr(ctx, "seen_message_ids") and isinstance(ctx.seen_message_ids, set):
                    ctx.seen_message_ids.add(packet.msg_id)

                peers_info = [
                    (p.ip_address, p.tcp_port)
                    for p in ctx.peers.values()
                    if not getattr(p, "is_web", False)
                    and p.peer_id != ctx.peer_id
                    and not (
                        p.ip_address in (ctx.local_ip, "127.0.0.1", "localhost")
                        and p.tcp_port == getattr(ctx, "actual_tcp_port", config.DEFAULT_TCP_PORT)
                    )
                ]
                if peers_info:
                    threading.Thread(
                        target=TCPClient.broadcast_message,
                        args=(peers_info, packet.to_dict()),
                        daemon=True,
                    ).start()

                # Save into local desktop host history and notify UI with packet's unique msg_id
                self._safe_append_message(ctx, None, f"{sender_name} 📱 (Group)", text, category="peer", sender_id=client_id, msg_id=packet.msg_id)

            # Case B: Private Direct Message to the Host Desktop User
            elif channel_id == ctx.peer_id or channel_id == "host":
                # Stored under client_id so Host desktop sees it in conversation with this mobile user
                ctx._append_message(client_id, f"{sender_name} 📱", text, category="dm", sender_id=client_id)

            # Case C: Private Direct Message to another Mobile / Web User
            elif channel_id in self.server.web_clients:
                dm_key = f"dm_{min(client_id, channel_id)}_{max(client_id, channel_id)}"
                if dm_key not in ctx.chat_histories:
                    ctx.chat_histories[dm_key] = []
                entry = {
                    "id": f"{now}_{uuid.uuid4().hex[:6]}",
                    "timestamp": timestamp_str,
                    "timestamp_epoch": now,
                    "sender": f"{sender_name} 📱",
                    "sender_id": client_id,
                    "message": text,
                    "category": "dm",
                    "channel": channel_id,
                }
                ctx.chat_histories[dm_key].append(entry)

            # Case D: Private Direct Message to a remote LAN TCP desktop peer
            else:
                peer = ctx.peers.get(channel_id)
                packet = Packet(
                    type=MessageType.CHAT,
                    sender_id=client_id,
                    sender_name=f"{sender_name} 📱",
                    payload={"text": text},
                )
                if peer and not getattr(peer, "is_web", False):
                    threading.Thread(
                        target=TCPClient.send_message,
                        args=(peer.ip_address, peer.tcp_port, packet.to_dict()),
                        daemon=True,
                    ).start()

                ctx._append_message(channel_id, f"{sender_name} 📱", text, category="dm", sender_id=client_id)

            self._send_json({"success": True, "timestamp": timestamp_str, "server_time": now})
            return

        # 2. Typing Notification Route
        elif path == "/api/typing":
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            sender_name = data.get("sender", "Mobile User")
            client_id = data.get("client_id") or f"mob_{ctx.peer_id[:4]}"
            raw_channel = data.get("channel")
            channel_id = None if raw_channel in (None, "", "null", "group") else raw_channel

            self.server.touch_client(client_id, sender_name, self.client_address[0])

            packet = Packet(
                type=MessageType.TYPING,
                sender_id=client_id,
                sender_name=f"{sender_name} 📱",
                payload={"channel": channel_id},
            )

            if channel_id is None:
                peers_info = [
                    (p.ip_address, p.tcp_port)
                    for p in ctx.peers.values()
                    if not getattr(p, "is_web", False)
                    and p.tcp_port > 0
                    and p.peer_id != ctx.peer_id
                    and not (
                        p.ip_address in (ctx.local_ip, "127.0.0.1", "localhost")
                        and p.tcp_port == getattr(ctx, "actual_tcp_port", config.DEFAULT_TCP_PORT)
                    )
                ]
                if peers_info:
                    threading.Thread(
                        target=TCPClient.broadcast_message,
                        args=(peers_info, packet.to_dict()),
                        daemon=True,
                    ).start()
                ctx._handle_incoming_typing(packet)
            elif channel_id == ctx.peer_id or channel_id == "host":
                # Typing directed to the host
                packet.payload["channel"] = client_id
                ctx._handle_incoming_typing(packet)
            else:
                peer = ctx.peers.get(channel_id)
                if peer and not getattr(peer, "is_web", False) and peer.tcp_port > 0:
                    threading.Thread(
                        target=TCPClient.send_message,
                        args=(peer.ip_address, peer.tcp_port, packet.to_dict()),
                        daemon=True,
                    ).start()

            self._send_json({"success": True})
            return

        # 3. File Upload from Mobile Route
        elif path == "/api/upload":
            content_type = self.headers.get("Content-Type", "")
            if not content_type.startswith("multipart/form-data"):
                self._send_json({"success": False, "error": "Expected multipart/form-data"}, status=400)
                return

            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)

                msg_bytes = f"Content-Type: {content_type}\r\n\r\n".encode("utf-8") + body
                msg = BytesParser(policy=email.policy.default).parsebytes(msg_bytes)

                sender_name = "Mobile User"
                client_id = None
                channel_id = None
                file_bytes = None
                original_filename = None

                for part in msg.iter_parts():
                    name = part.get_param("name", header="content-disposition")
                    if name == "sender":
                        sender_name = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    elif name == "client_id":
                        client_id = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    elif name == "channel":
                        raw_ch = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        channel_id = None if raw_ch in (None, "", "null", "group") else raw_ch
                    elif name == "file":
                        original_filename = part.get_filename()
                        file_bytes = part.get_payload(decode=True)

                if not client_id:
                    client_id = f"mob_{ctx.peer_id[:4]}"

                self.server.touch_client(client_id, sender_name, self.client_address[0])

                if file_bytes is None or not original_filename:
                    self._send_json({"success": False, "error": "No file uploaded"}, status=400)
                    return

                original_filename = os.path.basename(original_filename)
                save_dir = config.DEFAULT_DOWNLOAD_DIR
                os.makedirs(save_dir, exist_ok=True)
                save_path = save_dir / original_filename

                with open(save_path, "wb") as f:
                    f.write(file_bytes)

                filesize = save_path.stat().st_size
                download_url = f"http://{ctx.local_ip}:{self.server.port}/downloads/{urllib.parse.quote(original_filename)}"

                notice_text = f"📎 Shared file: {original_filename} ({filesize} bytes)\nDownload / View: {download_url}"
                now = time.time()
                timestamp_str = time.strftime("%H:%M:%S", time.localtime(now))

                # Case A: Group Broadcast
                if channel_id is None:
                    packet = Packet(
                        type=MessageType.GROUP_CHAT,
                        sender_id=client_id,
                        sender_name=f"{sender_name} 📱",
                        payload={"text": notice_text},
                    )
                    if hasattr(ctx, "seen_message_ids") and isinstance(ctx.seen_message_ids, set):
                        ctx.seen_message_ids.add(packet.msg_id)

                    peers_info = [
                        (p.ip_address, p.tcp_port)
                        for p in ctx.peers.values()
                        if not getattr(p, "is_web", False)
                        and p.peer_id != ctx.peer_id
                        and not (
                            p.ip_address in (ctx.local_ip, "127.0.0.1", "localhost")
                            and p.tcp_port == getattr(ctx, "actual_tcp_port", config.DEFAULT_TCP_PORT)
                        )
                    ]
                    if peers_info:
                        threading.Thread(
                            target=TCPClient.broadcast_message,
                            args=(peers_info, packet.to_dict()),
                            daemon=True,
                        ).start()
                    self._safe_append_message(ctx, None, f"{sender_name} 📱 (Group)", notice_text, category="file", sender_id=client_id, msg_id=packet.msg_id)

                # Case B: Private file to Host Desktop User
                elif channel_id == ctx.peer_id or channel_id == "host":
                    ctx._append_message(client_id, f"{sender_name} 📱", notice_text, category="file", sender_id=client_id)

                # Case C: Private file to another Mobile / Web User
                elif channel_id in self.server.web_clients:
                    dm_key = f"dm_{min(client_id, channel_id)}_{max(client_id, channel_id)}"
                    if dm_key not in ctx.chat_histories:
                        ctx.chat_histories[dm_key] = []
                    entry = {
                        "id": f"{now}_{uuid.uuid4().hex[:6]}",
                        "timestamp": timestamp_str,
                        "timestamp_epoch": now,
                        "sender": f"{sender_name} 📱",
                        "sender_id": client_id,
                        "message": notice_text,
                        "category": "file",
                        "channel": channel_id,
                    }
                    ctx.chat_histories[dm_key].append(entry)

                # Case D: Private file to remote TCP desktop peer
                else:
                    peer = ctx.peers.get(channel_id)
                    packet = Packet(
                        type=MessageType.CHAT,
                        sender_id=client_id,
                        sender_name=f"{sender_name} 📱",
                        payload={"text": notice_text},
                    )
                    if peer and not getattr(peer, "is_web", False):
                        threading.Thread(
                            target=TCPClient.send_message,
                            args=(peer.ip_address, peer.tcp_port, packet.to_dict()),
                            daemon=True,
                        ).start()
                    ctx._append_message(channel_id, f"{sender_name} 📱", notice_text, category="file")

                self._send_json(
                    {
                        "success": True,
                        "filename": original_filename,
                        "filesize": filesize,
                        "download_url": download_url,
                        "server_time": now,
                    }
                )
                return

            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
                return

        # 4. Manual P2P Connect by IP:Port
        elif path == "/api/connect_peer":
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            target = data.get("target", "").strip()
            if not target:
                self._send_json({"success": False, "error": "Target IP:Port is required"}, status=400)
                return

            if hasattr(ctx, "manual_connect_peer"):
                success = ctx.manual_connect_peer(target)
                self._send_json({"success": success, "target": target})
            else:
                self._send_json({"success": False, "error": "Manual connect not supported"}, status=501)
            return

        self.send_error(404, "Endpoint not found")


class WebGatewayServer(http.server.ThreadingHTTPServer):
    """Threading HTTP server carrying a reference to LANChatApp context and active web clients."""
    allow_reuse_address = False

    def server_bind(self):
        # On Windows, enforce exclusive address use so port clashes raise OSError and trigger port increment
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except OSError:
                pass
        super().server_bind()

    def __init__(self, server_address, RequestHandlerClass, app_context, port):
        super().__init__(server_address, RequestHandlerClass)
        self.app_context = app_context
        self.port = port
        self.web_clients: Dict[str, dict] = {}
        self.clients_lock = threading.Lock()
        self.client_read_times: Dict[str, Dict[Any, float]] = {}

    def touch_client(self, client_id: str, username: str, ip_address: str) -> None:
        """Records or updates a web client's presence and notifies app context."""
        now = time.time()
        with self.clients_lock:
            if client_id not in self.client_read_times:
                self.client_read_times[client_id] = {None: now}
            self.web_clients[client_id] = {
                "client_id": client_id,
                "username": username,
                "device_name": "Mobile Browser",
                "ip_address": ip_address,
                "last_seen": now,
            }

        if hasattr(self.app_context, "register_web_peer"):
            self.app_context.register_web_peer(client_id, username, ip_address)

    def mark_read(self, client_id: str, channel_id: Any) -> None:
        """Marks a channel as read for this client."""
        now = time.time()
        with self.clients_lock:
            if client_id not in self.client_read_times:
                self.client_read_times[client_id] = {}
            self.client_read_times[client_id][channel_id] = now

    def prune_dead_clients(self) -> None:
        """Removes web clients that haven't sent a heartbeat/poll for > 15s."""
        now = time.time()
        dead = []
        with self.clients_lock:
            for cid, info in list(self.web_clients.items()):
                if now - info["last_seen"] > 15.0:
                    dead.append(cid)
                    del self.web_clients[cid]

        for cid in dead:
            if hasattr(self.app_context, "remove_web_peer"):
                self.app_context.remove_web_peer(cid)


class WebGateway:
    """
    Manages the background Web Gateway lifecycle.
    Binds to an available port (starting at 8080) and serves mobile clients.
    """

    def __init__(self, app_context: Any, host: str = "0.0.0.0", port: int = 8080) -> None:
        self.app_context = app_context
        self.host = host
        self.port = port
        self.server: Optional[WebGatewayServer] = None
        self._thread: Optional[threading.Thread] = None
        self._prune_thread: Optional[threading.Thread] = None
        self._running = False

    def _prune_loop(self) -> None:
        """Background thread pruning disconnected web clients every 5s."""
        while self._running:
            time.sleep(5)
            if self.server:
                try:
                    self.server.prune_dead_clients()
                except Exception:
                    pass

    def start(self) -> int:
        """Starts the Web Gateway HTTP server on the first available port."""
        current_port = self.port
        max_attempts = 10

        for attempt in range(max_attempts):
            try:
                self.server = WebGatewayServer(
                    (self.host, current_port), WebGatewayHandler, self.app_context, current_port
                )
                self.port = current_port
                break
            except OSError:
                current_port += 1

        if not self.server:
            print("[WebGateway Error] Failed to bind to any port in 8080-8090 range.")
            return 0

        self._running = True
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

        self._prune_thread = threading.Thread(target=self._prune_loop, daemon=True)
        self._prune_thread.start()

        local_ip = self.app_context.local_ip
        print(f"[WebGateway] Mobile Web Interface live at: http://{local_ip}:{self.port}")
        return self.port

    def stop(self) -> None:
        """Shuts down the HTTP server."""
        self._running = False
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
