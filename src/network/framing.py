"""
Network Protocol Length-Prefixed Framing Module.

Encodes and decodes stream payloads using a 4-byte big-endian length prefix header.
Prevents TCP stream concatenation and fragmentation errors.
"""

import json
import struct
from typing import Generator, List, Tuple


def encode_frame(payload: dict) -> bytes:
    """
    Encodes a Python dictionary payload into a framed byte stream:
    [4-Byte Length Prefix (Big-Endian)] + [JSON Bytes]
    """
    json_bytes = json.dumps(payload).encode("utf-8")
    length_prefix = struct.pack("!I", len(json_bytes))
    return length_prefix + json_bytes


class FrameDecoder:
    """
    Stateful buffer for decoding length-prefixed stream data received from socket.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> List[dict]:
        """
        Feeds received socket bytes into buffer and extracts all complete JSON payloads.
        """
        self._buffer.extend(chunk)
        frames = []

        while len(self._buffer) >= 4:
            payload_len = struct.unpack("!I", self._buffer[:4])[0]
            total_frame_len = 4 + payload_len

            if len(self._buffer) < total_frame_len:
                # Incomplete frame, wait for more socket data
                break

            # Extract full payload
            frame_bytes = self._buffer[4:total_frame_len]
            self._buffer = self._buffer[total_frame_len:]

            try:
                payload_dict = json.loads(frame_bytes.decode("utf-8"))
                frames.append(payload_dict)
            except Exception as e:
                print(f"[FrameDecoder Error] Failed to decode JSON payload: {e}")

        return frames
