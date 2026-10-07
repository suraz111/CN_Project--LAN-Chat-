"""
Unit and integration tests for Private Room Isolation, Zero Default Rooms for New Users,
and Network-Scoped Notification Filtering.
"""

import json
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

from src.models.peer import Peer
from src.web.gateway import WebGateway


class DummyAppContext:
    def __init__(self):
        self.peer_id = "host_test_id"
        self.username = "TestHost"
        self.device_name = "HostPC"
        self.local_ip = "127.0.0.1"
        self.actual_tcp_port = 50001
        self.peers = {}
        self.chat_histories = {None: []}
        self.unread_counts = {}
        self.custom_rooms = set()
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


class TestRoomIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = DummyAppContext()
        cls.gateway = WebGateway(app_context=cls.ctx, host="127.0.0.1", port=8997)
        cls.port = cls.gateway.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.gateway.stop()

    def test_new_user_sees_no_default_rooms(self):
        # A brand new user with new client_id visits /api/status
        new_client_id = f"client_new_{time.time()}"
        with urllib.request.urlopen(f"{self.base_url}/api/status?client_id={new_client_id}&username=NewUser") as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            # Default rooms must be completely empty!
            self.assertEqual(data["rooms"], [], "New user must start with zero default rooms")
            self.assertNotIn("#general", data["rooms"])
            self.assertNotIn("#project", data["rooms"])
            self.assertNotIn("#study", data["rooms"])

    def test_room_isolation_between_clients(self):
        client_a = f"client_alice_{time.time()}"
        client_b = f"client_bob_{time.time()}"

        # Client A creates private room #alpha
        create_req = urllib.request.Request(
            f"{self.base_url}/api/room/create",
            data=json.dumps({"room": "#alpha", "client_id": client_a}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(create_req) as resp:
            self.assertEqual(resp.status, 200)
            a_data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("#alpha", a_data["rooms"])

        # Client A status returns #alpha
        with urllib.request.urlopen(f"{self.base_url}/api/status?client_id={client_a}") as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("#alpha", data["rooms"])

        # Client B is on a separate network/session and has NOT joined #alpha
        # Client B status must NOT contain #alpha
        with urllib.request.urlopen(f"{self.base_url}/api/status?client_id={client_b}") as resp:
            b_data = json.loads(resp.read().decode("utf-8"))
            self.assertNotIn("#alpha", b_data["rooms"], "Client B must NOT see Client A's private room")

        # Now send a message to #alpha
        self.ctx._append_message("#alpha", "Alice", "Secret message in Alpha", sender_id=client_a)

        # Client B polls /api/status -> must NOT get notification for #alpha
        with urllib.request.urlopen(f"{self.base_url}/api/status?client_id={client_b}") as resp:
            b_poll = json.loads(resp.read().decode("utf-8"))
            notif_channels = [n.get("channel") for n in b_poll.get("notifications", [])]
            self.assertNotIn("#alpha", notif_channels, "Client B must NOT receive notifications for rooms they did not join")

        # Now Client B joins #alpha via invite/code
        join_req = urllib.request.Request(
            f"{self.base_url}/api/room/create",
            data=json.dumps({"room": "#alpha", "client_id": client_b}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(join_req) as resp:
            self.assertEqual(resp.status, 200)
            b_joined = json.loads(resp.read().decode("utf-8"))
            self.assertIn("#alpha", b_joined["rooms"])

        # Now Client B status DOES include #alpha
        with urllib.request.urlopen(f"{self.base_url}/api/status?client_id={client_b}") as resp:
            b_final = json.loads(resp.read().decode("utf-8"))
            self.assertIn("#alpha", b_final["rooms"], "Client B should now see #alpha after joining")


if __name__ == "__main__":
    unittest.main()
