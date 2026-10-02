"""
Unit tests verifying message deduplication in group broadcast and theme consistency.
"""

import time
import unittest
import tkinter as tk
from unittest.mock import MagicMock

from src.models.message import MessageType, Packet
from src.models.peer import Peer
from src.gui.app import LANChatApp, THEMES


class TestDeduplicationAndThemes(unittest.TestCase):
    def setUp(self):
        # Create LANChatApp in headless-friendly manner
        self.app = LANChatApp(peer_id="test_host_id", username="test_host", tcp_port=59990)
        self.app.withdraw()  # keep window hidden during tests

    def tearDown(self):
        try:
            if hasattr(self.app, "tcp_server") and self.app.tcp_server:
                self.app.tcp_server.stop()
            self.app.destroy()
        except Exception:
            pass

    def test_theme_consistency_no_black_bar(self):
        """Verifies that switching to light theme updates all header frames and text containers."""
        self.app._apply_theme("light")
        light_theme = THEMES["light"]

        # Ensure header subframes match the light theme background
        self.assertEqual(self.app.chat_header.cget("bg"), light_theme["bg_main"])
        self.assertEqual(self.app.header_left.cget("bg"), light_theme["bg_main"])
        self.assertEqual(self.app.header_actions.cget("bg"), light_theme["bg_main"])
        self.assertEqual(self.app.lbl_chat_title.cget("bg"), light_theme["bg_main"])
        self.assertEqual(self.app.lbl_chat_sub.cget("bg"), light_theme["bg_main"])
        self.assertEqual(self.app.txt_frame.cget("bg"), light_theme["chat_bg"])

        # Switch back to dark theme and verify
        self.app._apply_theme("dark")
        dark_theme = THEMES["dark"]
        self.assertEqual(self.app.chat_header.cget("bg"), dark_theme["bg_main"])
        self.assertEqual(self.app.header_left.cget("bg"), dark_theme["bg_main"])
        self.assertEqual(self.app.header_actions.cget("bg"), dark_theme["bg_main"])
        self.assertEqual(self.app.txt_frame.cget("bg"), dark_theme["chat_bg"])

    def test_message_deduplication_by_id(self):
        """Verifies that duplicate messages with same msg_id are ignored."""
        test_msg_id = "unique_msg_12345"

        # Append first time
        self.app._append_message(None, "Alice", "Hello World", category="peer", msg_id=test_msg_id)
        self.assertEqual(len(self.app.chat_histories[None]), 2)  # 1 initial welcome + 1 message

        # Append exact same message second time
        self.app._append_message(None, "Alice", "Hello World", category="peer", msg_id=test_msg_id)
        self.assertEqual(len(self.app.chat_histories[None]), 2)  # Count should NOT increase!

    def test_poll_ui_queue_ignores_self_packet(self):
        """Verifies that TCP_MSG originating from self.peer_id is dropped to prevent loopback duplicates."""
        initial_history_len = len(self.app.chat_histories[None])

        # Simulate TCP_MSG with packet where sender_id == self.peer_id
        packet = Packet(
            type=MessageType.GROUP_CHAT,
            sender_id=self.app.peer_id,
            sender_name=self.app.username,
            payload={"text": "Should not be added from loopback"},
        )
        self.app.ui_queue.put(("TCP_MSG", packet.to_dict(), "127.0.0.1"))
        self.app._poll_ui_queue()

        # History should remain unchanged
        self.assertEqual(len(self.app.chat_histories[None]), initial_history_len)

    def test_poll_ui_queue_ignores_seen_packet_ids(self):
        """Verifies that TCP_MSG with already seen msg_id is discarded."""
        initial_history_len = len(self.app.chat_histories[None])

        packet = Packet(
            type=MessageType.GROUP_CHAT,
            sender_id="remote_peer_1",
            sender_name="Remote Peer",
            payload={"text": "Broadcast message"},
        )
        # Mark as seen
        self.app.seen_message_ids.add(packet.msg_id)

        self.app.ui_queue.put(("TCP_MSG", packet.to_dict(), "192.168.1.100"))
        self.app._poll_ui_queue()

        # Should be dropped
        self.assertEqual(len(self.app.chat_histories[None]), initial_history_len)

    def test_peer_directory_rejects_self(self):
        """Verifies that self peer cannot be added to self.peers."""
        # 1. Via _on_peer_updated with self.peer_id
        self_peer_1 = Peer(
            peer_id=self.app.peer_id,
            username=self.app.username,
            device_name=self.app.device_name,
            ip_address="127.0.0.1",
            tcp_port=self.app.actual_tcp_port,
        )
        self.app._on_peer_updated(self_peer_1)
        self.app._poll_ui_queue()
        self.assertNotIn(self.app.peer_id, self.app.peers)

        # 2. Via _on_peer_updated with same IP and TCP port
        self_peer_2 = Peer(
            peer_id="other_id_same_endpoint",
            username="Clone",
            device_name="CloneDevice",
            ip_address=self.app.local_ip,
            tcp_port=self.app.actual_tcp_port,
        )
        self.app._on_peer_updated(self_peer_2)
        self.app._poll_ui_queue()
        self.assertNotIn("other_id_same_endpoint", self.app.peers)

        # 3. Via manual_connect_peer to own endpoint
        result = self.app.manual_connect_peer(f"{self.app.local_ip}:{self.app.actual_tcp_port}")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
