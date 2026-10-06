"""
Unit and integration tests for newly updated LAN Chat features:
- Network interfaces discovery endpoint (/api/interfaces)
- Media gallery index endpoint (/api/media)
- Message reactions (/api/react)
- Message pinning (/api/pin)
- Custom room creation (/api/room/create)
- Voice note audio upload categorization (/api/upload)
"""

import json
import time
import unittest
import urllib.request
from pathlib import Path

import config
from src.models.message import MessageType
from src.utils.net_utils import get_all_network_interfaces
from src.web.gateway import WebGateway


class DummyAppContext:
    def __init__(self):
        self.peer_id = "test_user_id"
        self.username = "TestHost"
        self.device_name = "HostPC"
        self.local_ip = "127.0.0.1"
        self.actual_tcp_port = 50001
        self.peers = {}
        self.chat_histories = {None: []}
        self.unread_counts = {}
        self.custom_rooms = set(["#general", "#project", "#study"])
        self.pinned_messages = {}

    def _append_message(self, channel_id, sender, message, category="peer", sender_id=None, msg_id=None, **kwargs):
        now = time.time()
        if channel_id not in self.chat_histories:
            self.chat_histories[channel_id] = []
        entry = {
            "id": msg_id or f"{now}_test",
            "timestamp": "12:00:00",
            "timestamp_epoch": now,
            "sender": sender,
            "sender_id": sender_id,
            "message": message,
            "category": category,
            "reactions": kwargs.get("reactions", {}),
            "pinned": kwargs.get("pinned", False),
        }
        self.chat_histories[channel_id].append(entry)

    def register_web_peer(self, client_id, username, ip_address):
        pass

    def remove_web_peer(self, client_id):
        pass

    def _handle_incoming_typing(self, packet):
        pass

    def manual_connect_peer(self, target):
        self.last_connected_target = target
        return True


class TestNewFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = DummyAppContext()
        cls.gateway = WebGateway(app_context=cls.ctx, host="127.0.0.1", port=8993)
        cls.port = cls.gateway.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.gateway.stop()

    def test_network_interfaces_utility(self):
        ifaces = get_all_network_interfaces()
        self.assertTrue(len(ifaces) >= 1)
        # Verify structure
        for iface in ifaces:
            self.assertIn("name", iface)
            self.assertIn("ip", iface)
            self.assertIn("is_primary", iface)

    def test_api_interfaces_endpoint(self):
        with urllib.request.urlopen(f"{self.base_url}/api/interfaces") as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("interfaces", data)
            self.assertTrue(len(data["interfaces"]) >= 1)

    def test_api_media_endpoint(self):
        with urllib.request.urlopen(f"{self.base_url}/api/media") as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("media", data)
            self.assertIsInstance(data["media"], list)

    def test_api_status_includes_rooms(self):
        with urllib.request.urlopen(f"{self.base_url}/api/status") as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("rooms", data)
            self.assertIn("#general", data["rooms"])

    def test_api_room_create(self):
        body = json.dumps({"room": "hackathon"}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/room/create",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("room"), "#hackathon")
            self.assertIn("#hackathon", data.get("rooms"))

    def test_api_reactions_toggle(self):
        # 1. Add a test message into chat history
        msg_id = "test_msg_react_123"
        self.ctx._append_message(None, "Alice", "Great demo!", msg_id=msg_id)

        # 2. Add reaction 👍 from Bob
        body = json.dumps({"msg_id": msg_id, "emoji": "👍", "user": "Bob"}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/react",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertIn("👍", data.get("reactions"))
            self.assertIn("Bob", data["reactions"]["👍"])

        # 3. Toggle off reaction 👍 from Bob
        with urllib.request.urlopen(req) as resp2:
            self.assertEqual(resp2.status, 200)
            data2 = json.loads(resp2.read().decode("utf-8"))
            self.assertTrue(data2.get("success"))
            self.assertNotIn("👍", data2.get("reactions"))

    def test_api_pin_message(self):
        # 1. Add a test message
        msg_id = "test_msg_pin_456"
        self.ctx._append_message(None, "Teacher", "Exam announcement", msg_id=msg_id)

        # 2. Pin message
        body = json.dumps({"channel": "group", "msg_id": msg_id, "pin": True}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/pin",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertTrue(data.get("pinned"))

        # 3. Fetch messages and check pinned_message
        with urllib.request.urlopen(f"{self.base_url}/api/messages?channel=group") as m_resp:
            self.assertEqual(m_resp.status, 200)
            m_data = json.loads(m_resp.read().decode("utf-8"))
            self.assertIsNotNone(m_data.get("pinned_message"))
            self.assertEqual(m_data["pinned_message"]["id"], msg_id)

    def test_voice_note_upload_categorization(self):
        boundary = "----TestVoiceBoundary123"
        content_type = f"multipart/form-data; boundary={boundary}"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="sender"\r\n\r\n'
            f"PhoneUser\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="channel"\r\n\r\n'
            f"group\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="voice_note_12345.webm"\r\n'
            f"Content-Type: audio/webm\r\n\r\n"
            f"DUMMY_AUDIO_BYTES_TEST\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/upload",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("file_type"), "audio")

    def test_custom_room_message_routing(self):
        body = json.dumps({
            "sender": "MobileTester",
            "client_id": "test_client_room_1",
            "channel": "#project",
            "text": "Hello in project room!",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/send",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))

        # Verify message stored in room history
        self.assertIn("#project", self.ctx.chat_histories)
        msgs = self.ctx.chat_histories["#project"]
        self.assertTrue(any("Hello in project room!" in m.get("message", "") for m in msgs))

    def test_custom_room_unreads_in_status(self):
        now = time.time()
        # Append message in #study from another user
        self.ctx._append_message(
            "#study",
            "StudyBuddy",
            "Let's review chapter 4",
            sender_id="other_study_client",
        )

        with urllib.request.urlopen(f"{self.base_url}/api/status?client_id=my_client_xyz") as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("unreads", data)
            self.assertIn("#study", data["unreads"])
            self.assertGreaterEqual(data["unreads"]["#study"], 1)

    def test_connect_peer_default_port(self):
        body = json.dumps({"target": "192.168.1.150"}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/connect_peer",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("target"), f"192.168.1.150:{config.DEFAULT_TCP_PORT}")


if __name__ == "__main__":
    unittest.main()
