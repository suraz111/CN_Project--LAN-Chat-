"""
Unit tests for TCP Server and TCP Client communication.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.network.tcp_client import TCPClient
from src.network.tcp_server import TCPServer


class TestTCPCommunication(unittest.TestCase):

    def test_tcp_send_receive(self):
        received_messages = []

        def on_msg(payload: dict, client_ip: str):
            received_messages.append((payload, client_ip))

        # Start TCP server on dynamic port (0)
        server = TCPServer(host="127.0.0.1", port=0, on_message_received=on_msg)
        bound_port = server.start()

        try:
            test_payload = {"type": "CHAT", "sender_name": "TestSender", "text": "Hello World"}
            success = TCPClient.send_message("127.0.0.1", bound_port, test_payload)

            self.assertTrue(success)

            # Wait briefly for server worker to process packet
            time.sleep(0.2)

            self.assertEqual(len(received_messages), 1)
            payload, ip = received_messages[0]
            self.assertEqual(payload["type"], "CHAT")
            self.assertEqual(payload["text"], "Hello World")
            self.assertEqual(ip, "127.0.0.1")

        finally:
            server.stop()

    def test_port_fallback_on_collision(self):
        server1 = TCPServer(host="127.0.0.1", port=0)
        port1 = server1.start()

        # Try to bind another server to the same port1
        server2 = TCPServer(host="127.0.0.1", port=port1)
        port2 = server2.start()

        try:
            self.assertNotEqual(port1, port2, "Second server should fallback to dynamic port!")
        finally:
            server1.stop()
            server2.stop()

    def test_invalid_port_safety(self):
        """Verify that sending to port 0 or negative ports fails safely without crashing."""
        test_payload = {"type": "CHAT", "sender_name": "TestSender", "text": "Hello"}
        self.assertFalse(TCPClient.send_message("127.0.0.1", 0, test_payload))
        self.assertFalse(TCPClient.send_message("127.0.0.1", -5, test_payload))
        self.assertFalse(TCPClient.send_message("", 50001, test_payload))

    def test_broadcast_skips_invalid_ports(self):
        """Verify that broadcast_message skips invalid/zero ports cleanly."""
        test_payload = {"type": "CHAT", "sender_name": "TestSender", "text": "Hello"}
        peers = [
            ("127.0.0.1", 0),
            ("10.93.18.160", 0),
            ("10.93.18.200", -1),
        ]
        results = TCPClient.broadcast_message(peers, test_payload)
        # All invalid ports were skipped, so results dict contains no successful transmissions
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
