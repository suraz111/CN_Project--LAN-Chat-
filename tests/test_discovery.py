"""
Unit tests for UDP Discovery module using Python standard unittest library.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.message import MessageType, Packet
from src.models.peer import Peer
from src.network.discovery import DiscoveryEngine


class TestDiscoveryEngine(unittest.TestCase):

    def test_datagram_processing(self):
        engine = DiscoveryEngine(
            peer_id="local_id_123",
            username="LocalUser",
            device_name="LocalPC",
            tcp_port=50001,
        )

        heartbeat_packet = Packet(
            type=MessageType.HEARTBEAT,
            sender_id="remote_peer_999",
            sender_name="RemoteAlice",
            payload={"device_name": "AliceLaptop", "tcp_port": 50002},
        )

        encoded_data = str(heartbeat_packet.to_dict()).replace("'", '"').encode("utf-8")
        engine._process_datagram(encoded_data, "192.168.1.50")

        self.assertIn("remote_peer_999", engine.peers)
        peer = engine.peers["remote_peer_999"]
        self.assertEqual(peer.username, "RemoteAlice")
        self.assertEqual(peer.ip_address, "192.168.1.50")
        self.assertEqual(peer.tcp_port, 50002)

    def test_ignore_self_datagram(self):
        engine = DiscoveryEngine(
            peer_id="self_123",
            username="SelfUser",
            device_name="SelfPC",
            tcp_port=50001,
        )

        self_packet = Packet(
            type=MessageType.HEARTBEAT,
            sender_id="self_123",
            sender_name="SelfUser",
            payload={"device_name": "SelfPC", "tcp_port": 50001},
        )

        encoded_data = str(self_packet.to_dict()).replace("'", '"').encode("utf-8")
        engine._process_datagram(encoded_data, "127.0.0.1")

        # Self should not be added to active peer directory
        self.assertNotIn("self_123", engine.peers)


if __name__ == "__main__":
    unittest.main()
