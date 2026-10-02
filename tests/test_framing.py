import os
import sys
import unittest

# Ensure project root is in sys.path when running script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.network.framing import FrameDecoder, encode_frame


class TestFraming(unittest.TestCase):

    def test_encode_decode_single_frame(self):
        payload = {"type": "CHAT", "sender": "Alice", "message": "Hello P2P!"}
        encoded = encode_frame(payload)

        decoder = FrameDecoder()
        decoded_frames = decoder.feed(encoded)

        self.assertEqual(len(decoded_frames), 1)
        self.assertEqual(decoded_frames[0], payload)

    def test_fragmented_stream_decoding(self):
        payload = {"type": "CHAT", "sender": "Bob", "message": "Fragmented Packet"}
        encoded = encode_frame(payload)

        decoder = FrameDecoder()

        # Feed in two partial chunks
        part1 = encoded[:5]
        part2 = encoded[5:]

        frames1 = decoder.feed(part1)
        self.assertEqual(len(frames1), 0)  # Not complete yet

        frames2 = decoder.feed(part2)
        self.assertEqual(len(frames2), 1)
        self.assertEqual(frames2[0], payload)

    def test_multiple_concatenated_frames(self):
        payload1 = {"type": "CHAT", "msg": "First"}
        payload2 = {"type": "CHAT", "msg": "Second"}

        encoded = encode_frame(payload1) + encode_frame(payload2)

        decoder = FrameDecoder()
        decoded = decoder.feed(encoded)

        self.assertEqual(len(decoded), 2)
        self.assertEqual(decoded[0], payload1)
        self.assertEqual(decoded[1], payload2)


if __name__ == "__main__":
    unittest.main()
