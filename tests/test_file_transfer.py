"""
Unit tests for File Transfer engine & SHA-256 checksum verification.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.network.file_transfer import FileReceiver, FileSender


class TestFileTransfer(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.source_file = Path(self.temp_dir.name) / "test_image.bin"
        self.dest_file = Path(self.temp_dir.name) / "received_image.bin"

        # Generate 128 KB of dummy binary data
        self.dummy_data = os.urandom(128 * 1024)
        with open(self.source_file, "wb") as f:
            f.write(self.dummy_data)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sha256_checksum(self):
        digest = FileSender.calculate_sha256(self.source_file)
        self.assertIsInstance(digest, str)
        self.assertEqual(len(digest), 64)

    def test_file_transfer_end_to_end(self):
        filesize = len(self.dummy_data)
        checksum = FileSender.calculate_sha256(self.source_file)

        import threading

        transfer_result = [False]

        def receive_worker():
            success, _ = FileReceiver.receive_file(
                save_path=self.dest_file,
                filesize=filesize,
                expected_sha256=checksum,
                host="127.0.0.1",
                port=54321,
            )
            transfer_result[0] = success

        rec_thread = threading.Thread(target=receive_worker, daemon=True)
        rec_thread.start()

        # Give receiver time to bind socket
        import time

        time.sleep(0.2)

        # Send file from sender
        send_success = FileSender.send_file("127.0.0.1", 54321, self.source_file)
        self.assertTrue(send_success)

        rec_thread.join(timeout=2.0)
        self.assertTrue(transfer_result[0])
        self.assertTrue(self.dest_file.exists())
        self.assertEqual(self.dest_file.stat().st_size, filesize)


if __name__ == "__main__":
    unittest.main()
