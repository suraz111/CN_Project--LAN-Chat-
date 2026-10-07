"""
Unit and integration tests for Personal Private Network creation, join,
and strict multi-tenant peer/room/message isolation.
"""

import json
import time
import unittest
import urllib.parse
import urllib.request

from pathlib import Path
from src.web.gateway import WebGateway


class DummyAppContext:
    def __init__(self):
        self.peer_id = "host_pc_peer_id"
        self.username = "HostPC"
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
        self.chat_histories[channel_id].append({
            "id": msg_id or f"{now}_test",
            "timestamp": "12:00:00",
            "timestamp_epoch": now,
            "sender": sender,
            "sender_id": sender_id,
            "message": message,
            "category": category,
        })

    def register_web_peer(self, client_id, username, ip_address):
        pass

    def remove_web_peer(self, client_id):
        pass


class TestPersonalNetworkIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = DummyAppContext()
        cls.gateway = WebGateway(app_context=cls.ctx, host="127.0.0.1", port=8998)
        cls.port = cls.gateway.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.gateway.stop()

    def test_personal_network_flow_and_isolation(self):
        client_a = f"alice_{time.time()}"
        client_b = f"bob_{time.time()}"
        client_c = f"charlie_{time.time()}"

        # 1. Alice creates her Personal Private Network
        create_payload = json.dumps({
            "client_id": client_a,
            "username": "Alice",
            "network_name": "Alice's Network",
        }).encode("utf-8")
        req_a = urllib.request.Request(
            f"{self.base_url}/api/network/create",
            data=create_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_a) as resp:
            self.assertEqual(resp.status, 200)
            res_a = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(res_a["success"])
            net_a_id = res_a["network_id"]
            self.assertTrue(net_a_id.startswith("NET-"))
            self.assertEqual(res_a["network_name"], "Alice's Network")
            self.assertEqual(res_a["rooms"], [])
            self.assertEqual(res_a["members_count"], 1)

        # 2. Alice queries status: Alice is the ONLY one in her private network!
        with urllib.request.urlopen(f"{self.base_url}/api/status?client_id={client_a}&network_id={net_a_id}&username=Alice") as resp:
            self.assertEqual(resp.status, 200)
            status_a = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(status_a["network_id"], net_a_id)
            self.assertEqual(status_a["rooms"], [])
            # Active peers (excluding self) must be completely EMPTY! 0 strangers!
            self.assertEqual(status_a["peers"], [], "Creator must be the only one in their private network initially")

        # 3. Bob independently creates his own personal private network
        create_b_payload = json.dumps({
            "client_id": client_b,
            "username": "Bob",
        }).encode("utf-8")
        req_b = urllib.request.Request(
            f"{self.base_url}/api/network/create",
            data=create_b_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_b) as resp:
            res_b = json.loads(resp.read().decode("utf-8"))
            net_b_id = res_b["network_id"]
            self.assertNotEqual(net_a_id, net_b_id)

        # 4. Bob queries status: Bob sees 0 strangers (does NOT see Alice)
        with urllib.request.urlopen(f"{self.base_url}/api/status?client_id={client_b}&network_id={net_b_id}&username=Bob") as resp:
            status_b = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(status_b["peers"], [])
            self.assertFalse(any(p["username"] == "Alice" for p in status_b["peers"]))

        # 5. Alice creates a room #alice-secret in her network
        room_payload = json.dumps({
            "client_id": client_a,
            "room": "#alice-secret",
            "network_id": net_a_id,
        }).encode("utf-8")
        req_room = urllib.request.Request(
            f"{self.base_url}/api/room/create",
            data=room_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_room) as resp:
            room_res = json.loads(resp.read().decode("utf-8"))
            self.assertIn("#alice-secret", room_res["rooms"])

        # Bob must NOT see #alice-secret!
        with urllib.request.urlopen(f"{self.base_url}/api/status?client_id={client_b}&network_id={net_b_id}&username=Bob") as resp:
            status_b = json.loads(resp.read().decode("utf-8"))
            self.assertNotIn("#alice-secret", status_b["rooms"])

        # 6. Charlie joins Alice's network using her network code
        join_payload = json.dumps({
            "client_id": client_c,
            "username": "Charlie",
            "network_id": net_a_id,
        }).encode("utf-8")
        req_join = urllib.request.Request(
            f"{self.base_url}/api/network/join",
            data=join_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_join) as resp:
            join_res = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(join_res["success"])
            self.assertIn("#alice-secret", join_res["rooms"])

        # Now Alice sees Charlie!
        with urllib.request.urlopen(f"{self.base_url}/api/status?client_id={client_a}&network_id={net_a_id}&username=Alice") as resp:
            status_a = json.loads(resp.read().decode("utf-8"))
            peer_names = [p["username"] for p in status_a["peers"]]
            self.assertIn("Charlie", peer_names)
            self.assertNotIn("Bob", peer_names)

        # Charlie sees Alice!
        with urllib.request.urlopen(f"{self.base_url}/api/status?client_id={client_c}&network_id={net_a_id}&username=Charlie") as resp:
            status_c = json.loads(resp.read().decode("utf-8"))
            peer_names = [p["username"] for p in status_c["peers"]]
            self.assertIn("Alice", peer_names)
            self.assertNotIn("Bob", peer_names)

        # 7. Message isolation: Alice sends a message in #alice-secret
        msg_payload = json.dumps({
            "client_id": client_a,
            "sender": "Alice",
            "channel": "#alice-secret",
            "text": "Confidential message for Alice's network",
            "network_id": net_a_id,
        }).encode("utf-8")
        req_send = urllib.request.Request(
            f"{self.base_url}/api/send",
            data=msg_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_send) as resp:
            send_res = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(send_res["success"])

        # Charlie receives it:
        ch_quoted = urllib.parse.quote("#alice-secret")
        with urllib.request.urlopen(f"{self.base_url}/api/messages?channel={ch_quoted}&client_id={client_c}&network_id={net_a_id}") as resp:
            msgs_c = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(any("Confidential message for Alice's network" in m["message"] for m in msgs_c["messages"]))

        # Bob (in other network) queries #alice-secret: gets empty!
        with urllib.request.urlopen(f"{self.base_url}/api/messages?channel={ch_quoted}&client_id={client_b}&network_id={net_b_id}") as resp:
            msgs_b = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(msgs_b["messages"], [])

    def test_frontend_personal_network_elements_and_js(self):
        root = Path(__file__).resolve().parent.parent
        html_file = root / "src" / "web" / "static" / "index.html"
        js_file = root / "src" / "web" / "static" / "app.js"
        css_file = root / "src" / "web" / "static" / "style.css"

        html_text = html_file.read_text(encoding="utf-8")
        js_text = js_file.read_text(encoding="utf-8")
        css_text = css_file.read_text(encoding="utf-8")

        # HTML elements
        self.assertIn("sidebar-network-card", html_text)
        self.assertIn('id="sidebar-network-name"', html_text)
        self.assertIn('id="sidebar-network-code"', html_text)
        self.assertIn('id="nav-network-pill"', html_text)
        self.assertIn('id="nav-network-id"', html_text)
        self.assertIn('id="join-network-modal"', html_text)
        self.assertIn('id="input-join-network-code"', html_text)
        self.assertIn('id="landing-invite-banner"', html_text)
        self.assertIn('id="btn-landing-primary"', html_text)

        # CSS styles
        self.assertIn(".sidebar-network-card", css_text)
        self.assertIn(".network-badge-chip", css_text)
        self.assertIn(".landing-invite-banner", css_text)

        # JS functions & bindings
        self.assertIn('localStorage.getItem("lanchat_network_id")', js_text)
        self.assertIn("function startPersonalNetworkFromLanding(", js_text)
        self.assertIn("function createPersonalNetwork(", js_text)
        self.assertIn("function joinNetwork(", js_text)
        self.assertIn("function updateNetworkUI(", js_text)
        self.assertIn("window.startPersonalNetworkFromLanding = startPersonalNetworkFromLanding", js_text)
        self.assertIn("window.createPersonalNetwork = createPersonalNetwork", js_text)
        self.assertIn("window.joinNetwork = joinNetwork", js_text)
        self.assertIn("personal-network-empty", js_text)
        self.assertIn("Only you are here", js_text)


if __name__ == "__main__":
    unittest.main()

