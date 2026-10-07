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
from src.utils.net_utils import get_all_network_interfaces, get_local_ip


class WebGatewayHandler(http.server.BaseHTTPRequestHandler):
    """
    HTTP Request Handler serving the Mobile Single Page Application,
    REST APIs for peer directory, multi-channel messaging, and file streaming.
    """

    server: "WebGatewayServer"  # Type hint for custom server attribute

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP access logs to keep terminal clean."""
        pass

    def _get_client_ip(self) -> str:
        """Extracts real client IP handling reverse proxies (Render, Cloudflare, Nginx)."""
        xff = self.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        return self.client_address[0]

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
        """Streams a static asset or download file with appropriate MIME type and HTTP Range support."""
        if not filepath.exists() or not filepath.is_file():
            self.send_error(404, "File not found")
            return

        ext = filepath.suffix.lower()
        AUDIO_VIDEO_MIMES = {
            ".webm": "audio/webm",
            ".ogg": "audio/ogg",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".mp4": "video/mp4",
            ".aac": "audio/aac",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
        }

        if ext in AUDIO_VIDEO_MIMES:
            mime_type = AUDIO_VIDEO_MIMES[ext]
        else:
            mime_type, _ = mimetypes.guess_type(str(filepath))
            if not mime_type:
                mime_type = "application/octet-stream"

        try:
            filesize = filepath.stat().st_size
            range_header = self.headers.get("Range")

            if range_header and range_header.startswith("bytes="):
                # HTTP 206 Partial Content for audio / video streaming & seeking
                range_spec = range_header[len("bytes="):].strip()
                start_str, _, end_str = range_spec.partition("-")
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else filesize - 1
                if end >= filesize:
                    end = filesize - 1
                length = end - start + 1

                self.send_response(206)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Range", f"bytes {start}-{end}/{filesize}")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                with open(filepath, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk_size = min(config.MAX_SOCKET_BUFFER, remaining)
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            else:
                # Full content response
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(filesize))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
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

        # 2.5 API: Network Interfaces List
        elif path == "/api/interfaces":
            self._send_json({"interfaces": get_all_network_interfaces()})
            return

        # 2.6 API: Media Gallery
        elif path == "/api/media":
            media_list = []
            download_dir = config.DEFAULT_DOWNLOAD_DIR
            if download_dir.exists():
                for f in sorted(download_dir.iterdir(), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True):
                    if f.is_file():
                        st = f.stat()
                        ext = f.suffix.lower()
                        if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'):
                            m_type = 'image'
                        elif ext in ('.webm', '.ogg', '.mp3', '.wav', '.m4a'):
                            m_type = 'audio'
                        elif ext in ('.mp4', '.mov', '.avi', '.mkv'):
                            m_type = 'video'
                        else:
                            m_type = 'document'
                        media_list.append({
                            "filename": f.name,
                            "size": st.st_size,
                            "mtime": st.st_mtime,
                            "type": m_type,
                            "download_url": f"/downloads/{urllib.parse.quote(f.name)}",
                        })
            self._send_json({"media": media_list})
            return

        # 3. API: Status & Peer Directory
        elif path == "/api/status":
            ctx = self.server.app_context
            client_id = query.get("client_id", [None])[0]
            client_name = query.get("username", ["Mobile User"])[0]
            client_ip = self._get_client_ip()

            if client_id:
                self.server.touch_client(client_id, client_name, client_ip)

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
                connect_time = self.server.client_connect_times.get(client_id, 0.0)
                last_notified = self.server.client_last_notified.get(client_id, connect_time)
                notif_cutoff = max(connect_time, last_notified)

                # 1. Group Broadcast messages (exclude system messages)
                group_last_read = read_times.get(None, 0.0)
                group_msgs = ctx.chat_histories.get(None, [])
                new_group = [
                    m for m in group_msgs
                    if m.get("timestamp_epoch", 0) > group_last_read
                    and m.get("sender_id") != client_id
                    and m.get("category") != "system"
                ]
                unreads["group"] = len(new_group)
                notify_group = [m for m in new_group if m.get("timestamp_epoch", 0) > notif_cutoff]
                for m in notify_group[-5:]:
                    notifications.append({
                        "id": m.get("id") or f"{m.get('timestamp_epoch')}_{m.get('sender')}",
                        "channel": None,
                        "sender": m.get("sender", "Group Peer"),
                        "message": m.get("message", ""),
                        "timestamp": m.get("timestamp", ""),
                        "timestamp_epoch": m.get("timestamp_epoch", 0),
                        "category": m.get("category", "chat"),
                        "is_dm": False,
                    })

                # 2. Private DMs from Desktop Host
                host_last_read = read_times.get(ctx.peer_id, 0.0)
                host_msgs = ctx.chat_histories.get(client_id, [])
                new_host = [
                    m for m in host_msgs
                    if m.get("timestamp_epoch", 0) > host_last_read
                    and m.get("sender_id") != client_id
                    and m.get("category") != "system"
                ]
                unreads[ctx.peer_id] = len(new_host)
                notify_host = [m for m in new_host if m.get("timestamp_epoch", 0) > notif_cutoff]
                for m in notify_host[-5:]:
                    notifications.append({
                        "id": m.get("id") or f"{m.get('timestamp_epoch')}_{m.get('sender')}",
                        "channel": ctx.peer_id,
                        "sender": f"{ctx.username} (Host)",
                        "message": m.get("message", ""),
                        "timestamp": m.get("timestamp", ""),
                        "timestamp_epoch": m.get("timestamp_epoch", 0),
                        "category": m.get("category", "chat"),
                        "is_dm": True,
                    })

                # 3. Private DMs from other Web Clients
                for cid in list(self.server.web_clients.keys()):
                    if cid != client_id:
                        dm_k = f"dm_{min(client_id, cid)}_{max(client_id, cid)}"
                        cid_last_read = read_times.get(cid, 0.0)
                        cid_msgs = ctx.chat_histories.get(dm_k, [])
                        new_cid = [
                            m for m in cid_msgs
                            if m.get("timestamp_epoch", 0) > cid_last_read
                            and m.get("sender_id") != client_id
                            and m.get("category") != "system"
                        ]
                        unreads[cid] = len(new_cid)
                        other_info = self.server.web_clients.get(cid, {})
                        other_name = other_info.get("username", "Peer")
                        notify_cid = [m for m in new_cid if m.get("timestamp_epoch", 0) > notif_cutoff]
                        for m in notify_cid[-5:]:
                            notifications.append({
                                "id": m.get("id") or f"{m.get('timestamp_epoch')}_{m.get('sender')}",
                                "channel": cid,
                                "sender": f"{other_name} 📱",
                                "message": m.get("message", ""),
                                "timestamp": m.get("timestamp", ""),
                                "timestamp_epoch": m.get("timestamp_epoch", 0),
                                "category": m.get("category", "chat"),
                                "is_dm": True,
                            })

                # 4. Private DMs from remote LAN TCP desktop peers
                for pid, p in ctx.peers.items():
                    if getattr(p, "is_web", False) or pid == ctx.peer_id:
                        continue
                    p_last_read = read_times.get(pid, 0.0)
                    p_msgs = ctx.chat_histories.get(pid, [])
                    new_p = [
                        m for m in p_msgs
                        if m.get("timestamp_epoch", 0) > p_last_read
                        and m.get("sender_id") != client_id
                        and m.get("category") != "system"
                    ]
                    if new_p:
                        unreads[pid] = len(new_p)
                        notify_p = [m for m in new_p if m.get("timestamp_epoch", 0) > notif_cutoff]
                        for m in notify_p[-5:]:
                            notifications.append({
                                "id": m.get("id") or f"{m.get('timestamp_epoch')}_{m.get('sender')}",
                                "channel": pid,
                                "sender": p.username,
                                "message": m.get("message", ""),
                                "timestamp": m.get("timestamp", ""),
                                "timestamp_epoch": m.get("timestamp_epoch", 0),
                                "category": m.get("category", "chat"),
                                "is_dm": True,
                            })

                # 5. Topic Channel Rooms (exclude system messages)
                for r_name in getattr(ctx, "custom_rooms", ["#general", "#project", "#study"]):
                    r_last_read = read_times.get(r_name, 0.0)
                    r_msgs = ctx.chat_histories.get(r_name, [])
                    new_r = [
                        m for m in r_msgs
                        if m.get("timestamp_epoch", 0) > r_last_read
                        and m.get("sender_id") != client_id
                        and m.get("category") != "system"
                    ]
                    unreads[r_name] = len(new_r)
                    notify_r = [m for m in new_r if m.get("timestamp_epoch", 0) > notif_cutoff]
                    for m in notify_r[-5:]:
                        notifications.append({
                            "id": m.get("id") or f"{m.get('timestamp_epoch')}_{m.get('sender')}",
                            "channel": r_name,
                            "sender": f"{m.get('sender', 'Peer')} in {r_name}",
                            "message": m.get("message", ""),
                            "timestamp": m.get("timestamp", ""),
                            "timestamp_epoch": m.get("timestamp_epoch", 0),
                            "category": m.get("category", "chat"),
                            "is_dm": False,
                        })

                # Advance client_last_notified so these notifications are delivered only once
                if notifications:
                    max_notif_ts = max(n.get("timestamp_epoch", time.time()) for n in notifications)
                    self.server.client_last_notified[client_id] = max_notif_ts

            active_ip = get_local_ip()
            if not active_ip.startswith("127."):
                ctx.local_ip = active_ip

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
                    "rooms": sorted(list(getattr(ctx, "custom_rooms", ["#general", "#project", "#study"]))),
                    "unreads": unreads,
                    "notifications": notifications,
                    "interfaces": get_all_network_interfaces(),
                    "remembered_username": self.server.client_saved_names.get(client_id, "") if client_id else "",
                    "remembered_client_id": client_id or "",
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
                self.server.touch_client(client_id, client_name, self._get_client_ip())
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
                    m_copy["category"] = "peer" if msg_cat not in ("file", "audio", "image") else msg_cat
                    m_copy["sender"] = f"{ctx.username} (Host)"
                else:
                    m_copy["is_self"] = False
                m_copy.setdefault("reactions", {})
                m_copy.setdefault("pinned", False)
                formatted_messages.append(m_copy)

            pinned_msg = getattr(ctx, "pinned_messages", {}).get(channel_id)

            self._send_json({
                "channel": channel_id,
                "history_key": history_key,
                "messages": formatted_messages,
                "pinned_message": pinned_msg,
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

            self.server.touch_client(client_id, sender_name, self._get_client_ip())

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

            # Case B: Topic Channel Room (e.g. #general, #project, #study, etc.)
            elif str(channel_id).startswith("#") or channel_id in getattr(ctx, "custom_rooms", set()):
                if not hasattr(ctx, "custom_rooms"):
                    ctx.custom_rooms = set(["#general", "#project", "#study"])
                ctx.custom_rooms.add(str(channel_id))

                packet = Packet(
                    type=MessageType.ROOM_MESSAGE,
                    sender_id=client_id,
                    sender_name=f"{sender_name} 📱",
                    payload={"text": text, "room": str(channel_id)},
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

                # Save into local channel history
                self._safe_append_message(ctx, channel_id, f"{sender_name} 📱 ({channel_id})", text, category="peer", sender_id=client_id, msg_id=packet.msg_id)

            # Case C: Private Direct Message to the Host Desktop User
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

            self.server.touch_client(client_id, sender_name, self._get_client_ip())

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

                self.server.touch_client(client_id, sender_name, self._get_client_ip())

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
                relative_download_url = f"/downloads/{urllib.parse.quote(original_filename)}"
                download_url = relative_download_url

                ext = Path(original_filename).suffix.lower()
                is_voice = ext in (".webm", ".ogg", ".mp3", ".wav", ".m4a") or original_filename.startswith("voice_note_")
                is_image = ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")

                if is_voice:
                    file_category = "audio"
                    notice_text = f"🎙️ Voice Note: {original_filename} ({filesize} bytes)\nDownload / View: {download_url}"
                elif is_image:
                    file_category = "image"
                    notice_text = f"🖼️ Photo: {original_filename} ({filesize} bytes)\nDownload / View: {download_url}"
                else:
                    file_category = "file"
                    notice_text = f"📎 Shared file: {original_filename} ({filesize} bytes)\nDownload / View: {download_url}"

                now = time.time()
                timestamp_str = time.strftime("%H:%M:%S", time.localtime(now))

                # Case A: Group Broadcast
                if channel_id is None:
                    packet = Packet(
                        type=MessageType.GROUP_CHAT,
                        sender_id=client_id,
                        sender_name=f"{sender_name} 📱",
                        payload={"text": notice_text, "file_type": file_category},
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
                    self._safe_append_message(ctx, None, f"{sender_name} 📱 (Group)", notice_text, category=file_category, sender_id=client_id, msg_id=packet.msg_id)

                # Case B: Topic Channel Room File
                elif str(channel_id).startswith("#") or channel_id in getattr(ctx, "custom_rooms", set()):
                    if not hasattr(ctx, "custom_rooms"):
                        ctx.custom_rooms = set(["#general", "#project", "#study"])
                    ctx.custom_rooms.add(str(channel_id))

                    packet = Packet(
                        type=MessageType.ROOM_MESSAGE,
                        sender_id=client_id,
                        sender_name=f"{sender_name} 📱",
                        payload={"text": notice_text, "room": str(channel_id), "file_type": file_category},
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
                    self._safe_append_message(
                        ctx,
                        channel_id,
                        f"{sender_name} 📱 ({channel_id})",
                        notice_text,
                        category=file_category,
                        sender_id=client_id,
                        msg_id=packet.msg_id,
                    )

                # Case C: Private file to Host Desktop User
                elif channel_id == ctx.peer_id or channel_id == "host":
                    ctx._append_message(client_id, f"{sender_name} 📱", notice_text, category=file_category, sender_id=client_id)

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
                        "category": file_category,
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
                        payload={"text": notice_text, "file_type": file_category},
                    )
                    if peer and not getattr(peer, "is_web", False):
                        threading.Thread(
                            target=TCPClient.send_message,
                            args=(peer.ip_address, peer.tcp_port, packet.to_dict()),
                            daemon=True,
                        ).start()
                    ctx._append_message(channel_id, f"{sender_name} 📱", notice_text, category=file_category)

                self._send_json(
                    {
                        "success": True,
                        "filename": original_filename,
                        "filesize": filesize,
                        "download_url": download_url,
                        "file_type": file_category,
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

            if ":" not in target:
                target = f"{target}:{config.DEFAULT_TCP_PORT}"

            if hasattr(ctx, "manual_connect_peer"):
                success = ctx.manual_connect_peer(target)
                self._send_json({"success": success, "target": target})
            else:
                self._send_json({"success": False, "error": "Manual connect not supported"}, status=501)
            return

        # 5. Emoji Reaction Route: /api/react
        elif path == "/api/react":
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            msg_id = data.get("msg_id")
            emoji = (data.get("emoji") or "").strip()
            user = (data.get("user") or data.get("sender") or "User").strip()

            if not msg_id or not emoji:
                self._send_json({"success": False, "error": "msg_id and emoji are required"}, status=400)
                return

            found_reactions = {}
            for ch_history in ctx.chat_histories.values():
                for msg in ch_history:
                    if msg.get("id") == msg_id or msg.get("msg_id") == msg_id:
                        reactions = msg.setdefault("reactions", {})
                        users_for_emoji = reactions.setdefault(emoji, [])
                        if user in users_for_emoji:
                            users_for_emoji.remove(user)
                            if not users_for_emoji:
                                reactions.pop(emoji, None)
                        else:
                            users_for_emoji.append(user)
                        found_reactions = reactions
                        break

            self._send_json({"success": True, "msg_id": msg_id, "reactions": found_reactions})
            return

        # 6. Pin/Unpin Message Route: /api/pin
        elif path == "/api/pin":
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            msg_id = data.get("msg_id")
            raw_channel = data.get("channel")
            channel_id = None if raw_channel in (None, "", "null", "group") else raw_channel
            pin_action = data.get("pin", True)

            if not hasattr(ctx, "pinned_messages"):
                ctx.pinned_messages = {}

            found_msg = None
            for ch_id, ch_history in ctx.chat_histories.items():
                for msg in ch_history:
                    if msg.get("id") == msg_id or msg.get("msg_id") == msg_id:
                        msg["pinned"] = bool(pin_action)
                        if pin_action:
                            found_msg = msg
                        break

            if pin_action and found_msg:
                ctx.pinned_messages[channel_id] = found_msg
            elif not pin_action:
                ctx.pinned_messages.pop(channel_id, None)

            self._send_json({"success": True, "pinned": pin_action, "channel": channel_id})
            return

        # 7. Create Custom Room Route: /api/room/create
        elif path == "/api/room/create":
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            room_name = (data.get("room") or "").strip()
            if not room_name:
                self._send_json({"success": False, "error": "Room name is required"}, status=400)
                return

            if not room_name.startswith("#"):
                room_name = "#" + room_name

            if not hasattr(ctx, "custom_rooms"):
                ctx.custom_rooms = set(["#general", "#project", "#study"])
            ctx.custom_rooms.add(room_name)

            self._send_json({"success": True, "room": room_name, "rooms": sorted(list(ctx.custom_rooms))})
            return

        # 8. Delete Custom Room Route: /api/room/delete
        elif path == "/api/room/delete":
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            room_name = (data.get("room") or "").strip()
            if not room_name:
                self._send_json({"success": False, "error": "Room name is required"}, status=400)
                return

            if not room_name.startswith("#"):
                room_name = "#" + room_name

            if not hasattr(ctx, "custom_rooms"):
                ctx.custom_rooms = set(["#general", "#project", "#study"])

            ctx.custom_rooms.discard(room_name)

            self._send_json({"success": True, "room": room_name, "rooms": sorted(list(ctx.custom_rooms))})
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
        self.client_connect_times: Dict[str, float] = {}
        self.client_last_notified: Dict[str, float] = {}
        self.client_saved_names: Dict[str, str] = {}
        self.ip_saved_names: Dict[str, str] = {}
        self.ip_client_ids: Dict[str, str] = {}

    def touch_client(self, client_id: str, username: str, ip_address: str) -> None:
        """Records or updates a web client's presence by unique client_id without evicting peers sharing an IP/proxy."""
        if not client_id:
            return
        now = time.time()
        with self.clients_lock:
            # If user had a previously set custom name for this client_id, restore it if incoming is default
            if username in ("Mobile User", "Peer", "", None) and client_id in self.client_saved_names:
                username = self.client_saved_names[client_id]
            elif username and username not in ("Mobile User", "Peer"):
                self.client_saved_names[client_id] = username

            if client_id not in self.client_connect_times:
                self.client_connect_times[client_id] = now
                self.client_last_notified[client_id] = now

            if client_id not in self.client_read_times:
                self.client_read_times[client_id] = {}

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
        """Removes web clients that haven't sent a heartbeat/poll for > 30s."""
        now = time.time()
        dead = []
        with self.clients_lock:
            for cid, info in list(self.web_clients.items()):
                if now - info["last_seen"] > 30.0:
                    dead.append(cid)
                    del self.web_clients[cid]
                    self.client_read_times.pop(cid, None)
                    self.client_connect_times.pop(cid, None)
                    self.client_last_notified.pop(cid, None)

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
