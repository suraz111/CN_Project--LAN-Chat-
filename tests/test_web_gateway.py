"""
Unit tests for the WebGateway HTTP Server & REST API endpoints.
"""

import json
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock

from src.models.peer import Peer
from src.web.gateway import WebGateway


class DummyAppContext:
    def __init__(self):
        self.peer_id = "test_user_id"
        self.username = "TestHost"
        self.device_name = "HostPC"
        self.local_ip = "127.0.0.1"
        self.actual_tcp_port = 50001
        self.peers = {
            "peer_bob": Peer(
                peer_id="peer_bob",
                username="Bob",
                device_name="BobLaptop",
                ip_address="127.0.0.1",
                tcp_port=50002,
                last_seen=time.time(),
            )
        }
        self.chat_histories = {None: []}
        self.unread_counts = {}

    def _append_message(self, channel_id, sender, message, category="peer", sender_id=None, msg_id=None, **kwargs):
        now = time.time()
        if channel_id not in self.chat_histories:
            self.chat_histories[channel_id] = []
        self.chat_histories[channel_id].append(
            {
                "id": msg_id or f"{now}_test",
                "timestamp": "12:00:00",
                "timestamp_epoch": now,
                "sender": sender,
                "sender_id": sender_id,
                "message": message,
                "category": category,
            }
        )

    def register_web_peer(self, client_id, username, ip_address):
        pass

    def remove_web_peer(self, client_id):
        pass

    def _handle_incoming_typing(self, packet):
        pass

    def manual_connect_peer(self, target_str: str) -> bool:
        return True if "127.0.0.1" in target_str else False


class TestWebGateway(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = DummyAppContext()
        cls.gateway = WebGateway(app_context=cls.ctx, host="127.0.0.1", port=8990)
        cls.port = cls.gateway.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.gateway.stop()

    def test_static_html(self):
        req = urllib.request.Request(f"{self.base_url}/")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("Simple LAN Chat", content)
            self.assertIn("app.js", content)

    def test_static_css_and_js(self):
        with urllib.request.urlopen(f"{self.base_url}/style.css") as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get_content_type(), "text/css")

        with urllib.request.urlopen(f"{self.base_url}/app.js") as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("selectChannel", content)

    def test_api_status(self):
        with urllib.request.urlopen(f"{self.base_url}/api/status") as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("online"))
            self.assertEqual(data.get("username"), "TestHost")
            peers = data.get("peers", [])
            host_peer = next((p for p in peers if p.get("is_host")), None)
            self.assertIsNotNone(host_peer)
            self.assertEqual(host_peer["username"], "TestHost (Host)")
            bob_peer = next((p for p in peers if p.get("username") == "Bob"), None)
            self.assertIsNotNone(bob_peer)

    def test_api_send_group_message(self):
        payload = json.dumps(
            {
                "sender": "MobilePhoneUser",
                "client_id": "mob_unit_test",
                "message": "Hello from my phone!",
                "channel": None,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))

        history = self.ctx.chat_histories.get(None, [])
        self.assertTrue(any("Hello from my phone!" in msg["message"] for msg in history))

    def test_api_upload_file(self):
        boundary = "----TestUploadBoundary123"
        content_type = f"multipart/form-data; boundary={boundary}"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="sender"\r\n\r\n'
            f"PhoneUser\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="channel"\r\n\r\n'
            f"group\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="test_web_file.txt"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
            f"Content from mobile phone test\r\n"
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
            self.assertEqual(data.get("filename"), "test_web_file.txt")
            download_url = data.get("download_url")

        # Now test downloading that file through /downloads/
        with urllib.request.urlopen(f"{self.base_url}/downloads/test_web_file.txt") as dl_resp:
            self.assertEqual(dl_resp.status, 200)
            dl_content = dl_resp.read().decode("utf-8")
            self.assertEqual(dl_content, "Content from mobile phone test")

    def test_api_private_dm_flow(self):
        client_id = "mob_phone_private"
        # 1. Send private DM from mobile phone to Host
        payload = json.dumps(
            {
                "sender": "MobilePhoneUser",
                "client_id": client_id,
                "channel": self.ctx.peer_id,
                "text": "Secret private message to Host",
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)

        # Host desktop appends a reply into this client's conversation
        self.ctx._append_message(
            client_id,
            f"You -> MobilePhoneUser",
            "Got your private message!",
            category="self",
            sender_id=self.ctx.peer_id,
        )

        # 2. Mobile phone fetches messages for channel = host's peer_id
        fetch_url = f"{self.base_url}/api/messages?channel={self.ctx.peer_id}&client_id={client_id}&username=MobilePhoneUser"
        with urllib.request.urlopen(fetch_url) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            msgs = data.get("messages", [])
            self.assertGreaterEqual(len(msgs), 2)
            # Check host reply is marked as coming from Host
            host_msg = next((m for m in msgs if "Got your private message!" in m.get("message", "")), None)
            self.assertIsNotNone(host_msg)
            self.assertIn("Host", host_msg.get("sender", ""))
            self.assertFalse(host_msg.get("is_self"))

    def test_api_ping(self):
        with urllib.request.urlopen(f"{self.base_url}/api/ping?peer_id={self.ctx.peer_id}") as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertIn("rtt_ms", data)

    def test_api_connect_peer(self):
        payload = json.dumps({"target": "127.0.0.1:50001"}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/connect_peer",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("target"), "127.0.0.1:50001")

    def test_api_notifications(self):
        status_url = f"{self.base_url}/api/status?client_id=test_notif_client&username=NotifUser"
        # 1. Connect client first to establish baseline read time
        with urllib.request.urlopen(status_url) as resp:
            self.assertEqual(resp.status, 200)

        time.sleep(0.05)
        # 2. New message arrives after connection
        self.ctx._append_message(None, "SomeoneElse", "Testing incoming notification", category="peer", sender_id="remote_peer_1")

        # 3. Next status poll receives the notification event
        with urllib.request.urlopen(status_url) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("notifications", data)
            notifs = data["notifications"]
            self.assertGreaterEqual(len(notifs), 1)
            matching = next((n for n in notifs if "Testing incoming notification" in n.get("message", "")), None)
            self.assertIsNotNone(matching)
            self.assertEqual(matching.get("sender"), "SomeoneElse")

    def test_http_head_method(self):
        """Verify that HTTP HEAD / works cleanly and returns 200 without error."""
        req = urllib.request.Request(f"{self.base_url}/", method="HEAD")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)

    def test_gateway_port_fallback_on_collision(self):
        """Verify that a second gateway starting on the same port automatically increments."""
        gateway2 = WebGateway(app_context=self.ctx, host="127.0.0.1", port=self.port)
        port2 = gateway2.start()
        try:
            self.assertNotEqual(self.port, port2, "Second gateway must increment port on collision!")
        finally:
            gateway2.stop()

    def test_typing_endpoint_safely_handles_web_peers(self):
        """Verify typing notification endpoint handles web peers with tcp_port=0 safely."""
        # Add a dummy web peer with tcp_port = 0
        self.ctx.peers["web_peer_mobile"] = Peer(
            peer_id="web_peer_mobile",
            username="MobileTester",
            device_name="Mobile / Web",
            ip_address="10.93.18.160",
            tcp_port=0,
            is_web=True,
        )

        payload = json.dumps(
            {
                "sender": "MobilePhoneUser",
                "client_id": "mob_test_typing",
                "channel": None,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/typing",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))


if __name__ == "__main__":
    unittest.main()
