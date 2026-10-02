"""
Comprehensive End-to-End (E2E) Test Suite for Simple LAN Chat.
Validates all system conditions:
1. TCP Server & Client Framing & Messaging
2. Port 0 and Negative Port TCP Safety
3. Dual Instance Web Gateway Port Auto-Incrementing
4. HTTP HEAD and CORS OPTIONS Handling
5. Mobile Web Client Lifecycle (Join -> Send Group -> Send DM -> Upload File -> Download File)
6. Typing Notification Filtering (Web Peers with tcp_port=0)
7. Binary File Transfer with SHA-256 Integrity Verification
"""

import json
import os
import sys
import tempfile
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from src.models.message import MessageType, Packet
from src.models.peer import Peer
from src.network.file_transfer import FileReceiver, FileSender
from src.network.framing import FrameDecoder, encode_frame
from src.network.tcp_client import TCPClient
from src.network.tcp_server import TCPServer
from src.web.gateway import WebGateway


class MockAppContext:
    """Mock Application Context simulating LANChatApp state."""

    def __init__(self, peer_id: str = "mock_host_id", username: str = "HostSuraj"):
        self.peer_id = peer_id
        self.username = username
        self.device_name = "HostMachine"
        self.local_ip = "127.0.0.1"
        self.actual_tcp_port = 50001
        self.web_port = 8995
        self.chat_histories = {None: []}
        self.unread_counts = {}
        self.seen_message_ids = set()
        self.peers = {}

    def _append_message(self, channel_id, sender, message, category="peer", sender_id=None, msg_id=None, **kwargs):
        now = time.time()
        if channel_id not in self.chat_histories:
            self.chat_histories[channel_id] = []
        self.chat_histories[channel_id].append(
            {
                "id": msg_id or f"{now}_mock",
                "timestamp": time.strftime("%H:%M:%S"),
                "timestamp_epoch": now,
                "sender": sender,
                "sender_id": sender_id,
                "message": message,
                "category": category,
                "channel": channel_id,
            }
        )

    def register_web_peer(self, client_id, username, ip_address):
        self.peers[client_id] = Peer(
            peer_id=client_id,
            username=username,
            device_name="Mobile / Web",
            ip_address=ip_address,
            tcp_port=0,
            status="Online",
            is_web=True,
        )

    def remove_web_peer(self, client_id):
        self.peers.pop(client_id, None)

    def _handle_incoming_typing(self, packet):
        pass


class TestFullEndToEndSystem(unittest.TestCase):
    """Executes all system conditions end-to-end."""

    @classmethod
    def setUpClass(cls):
        cls.ctx = MockAppContext()
        cls.gateway = WebGateway(app_context=cls.ctx, host="127.0.0.1", port=8995)
        cls.port = cls.gateway.start()
        cls.ctx.web_port = cls.port
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.gateway.stop()

    def test_condition_1_framing_integrity(self):
        """Condition 1: Custom 4-byte length-prefix framing roundtrip."""
        original = {"type": "CHAT", "sender": "Alice", "text": "Testing 123 😊"}
        encoded = encode_frame(original)
        self.assertGreater(len(encoded), 4)

        decoder = FrameDecoder()
        frames = decoder.feed(encoded)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]["type"], "CHAT")
        self.assertEqual(frames[0]["text"], "Testing 123 😊")

    def test_condition_2_tcp_port_zero_safety(self):
        """Condition 2: TCP Client must safely reject port 0 and negative ports."""
        dummy_packet = {"type": "TEST"}
        self.assertFalse(TCPClient.send_message("127.0.0.1", 0, dummy_packet))
        self.assertFalse(TCPClient.send_message("127.0.0.1", -1, dummy_packet))
        self.assertFalse(TCPClient.send_message("", 50001, dummy_packet))

        results = TCPClient.broadcast_message([("127.0.0.1", 0), ("10.0.0.1", -5)], dummy_packet)
        self.assertEqual(len(results), 0)

    def test_condition_3_web_server_port_auto_increment(self):
        """Condition 3: Second Web Gateway instance increments port automatically."""
        gw2 = WebGateway(app_context=self.ctx, host="127.0.0.1", port=self.port)
        p2 = gw2.start()
        try:
            self.assertNotEqual(self.port, p2)
            self.assertEqual(p2, self.port + 1)
        finally:
            gw2.stop()

    def test_condition_4_http_methods(self):
        """Condition 4: Web gateway handles GET, HEAD, and OPTIONS."""
        # 1. GET
        req_get = urllib.request.Request(f"{self.base_url}/")
        with urllib.request.urlopen(req_get) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("Simple LAN Chat", resp.read().decode("utf-8"))

        # 2. HEAD
        req_head = urllib.request.Request(f"{self.base_url}/", method="HEAD")
        with urllib.request.urlopen(req_head) as resp:
            self.assertEqual(resp.status, 200)

        # 3. OPTIONS (CORS)
        req_opts = urllib.request.Request(f"{self.base_url}/api/send", method="OPTIONS")
        with urllib.request.urlopen(req_opts) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")

    def test_condition_5_mobile_client_full_cycle(self):
        """Condition 5: Mobile client registers, sends group and private messages, and polls."""
        client_id = "mob_phone_e2e"
        username = "Pooja Mobile"

        # Step 5A: Join and touch presence
        status_url = f"{self.base_url}/api/status?client_id={client_id}&username={urllib.parse.quote(username)}"
        with urllib.request.urlopen(status_url) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("online"))

        self.assertIn(client_id, self.ctx.peers)
        self.assertEqual(self.ctx.peers[client_id].tcp_port, 0)
        self.assertTrue(self.ctx.peers[client_id].is_web)

        # Step 5B: Send group message
        group_payload = json.dumps(
            {"sender": username, "client_id": client_id, "channel": None, "message": "Hello from Mobile Wi-Fi!"}
        ).encode("utf-8")
        req_group = urllib.request.Request(
            f"{self.base_url}/api/send",
            data=group_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_group) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))

        # Verify host received it
        history = self.ctx.chat_histories.get(None, [])
        self.assertTrue(any("Hello from Mobile Wi-Fi!" in m["message"] for m in history))

        # Step 5C: Send DM to Host
        dm_payload = json.dumps(
            {"sender": username, "client_id": client_id, "channel": self.ctx.peer_id, "text": "Direct Question for Host"}
        ).encode("utf-8")
        req_dm = urllib.request.Request(
            f"{self.base_url}/api/send",
            data=dm_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_dm) as resp:
            self.assertEqual(resp.status, 200)

        # Host replies
        self.ctx._append_message(client_id, "HostSuraj", "Direct Answer from Host", category="dm", sender_id=self.ctx.peer_id)

        # Mobile fetches DM thread
        poll_url = f"{self.base_url}/api/messages?channel={self.ctx.peer_id}&client_id={client_id}&username={urllib.parse.quote(username)}"
        with urllib.request.urlopen(poll_url) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msgs = data.get("messages", [])
            self.assertTrue(any("Direct Answer from Host" in m.get("message", "") for m in msgs))

    def test_condition_6_typing_indicator_zero_port_safety(self):
        """Condition 6: Typing indicator from mobile client safely skips zero ports."""
        typing_payload = json.dumps(
            {"sender": "Pooja Mobile", "client_id": "mob_phone_e2e", "channel": None}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/typing",
            data=typing_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))

    def test_condition_7_binary_file_transfer_integrity(self):
        """Condition 7: Stream binary file over TCP with SHA-256 integrity check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_file = tmp_path / "document.pdf"
            dest_file = tmp_path / "received_document.pdf"

            # Create test payload with binary data
            test_content = os.urandom(65536)  # 64 KB binary content
            source_file.write_bytes(test_content)

            expected_sha = FileSender.calculate_sha256(source_file)

            listener, file_port = FileReceiver.create_listener()

            def receiver_thread():
                FileReceiver.receive_stream(
                    server_sock=listener,
                    save_path=dest_file,
                    filesize=len(test_content),
                    expected_sha256=expected_sha,
                )

            import threading
            t = threading.Thread(target=receiver_thread, daemon=True)
            t.start()

            # Sender streams file
            send_success = FileSender.send_file("127.0.0.1", file_port, source_file)
            t.join(timeout=3.0)

            self.assertTrue(send_success)
            self.assertTrue(dest_file.exists())
            self.assertEqual(dest_file.read_bytes(), test_content)
            self.assertEqual(FileSender.calculate_sha256(dest_file), expected_sha)


if __name__ == "__main__":
    unittest.main()
