import os
import sys
import unittest

# Ensure project root is in sys.path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.net_utils import get_broadcast_address, get_local_ip


class TestNetUtils(unittest.TestCase):

    def test_get_local_ip(self):
        ip = get_local_ip()
        self.assertIsInstance(ip, str)
        self.assertTrue(len(ip) >= 7)  # e.g., '127.0.0.1' or '192.168.x.x'

    def test_get_broadcast_address(self):
        bcast = get_broadcast_address()
        self.assertIsInstance(bcast, str)
        self.assertTrue(bcast.endswith(".255") or bcast == "255.255.255.255")


if __name__ == "__main__":
    unittest.main()
