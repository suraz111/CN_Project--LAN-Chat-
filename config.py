"""
Global Configuration Constants for Simple LAN Chat
"""

import os
from pathlib import Path

# Application Meta
APP_NAME = "Simple LAN Chat"
APP_VERSION = "1.0.0"

# Networking Configuration
DEFAULT_UDP_PORT = 50000          # Port for discovery broadcast heartbeats
DEFAULT_TCP_PORT = 50001          # Port for P2P messaging & file transfers
BROADCAST_ADDRESS = "255.255.255.255"

# Heartbeat & Presense Settings
HEARTBEAT_INTERVAL = 3.0           # Broadcast presence every 3 seconds
PEER_TIMEOUT = 10.0                # Mark peer offline after 10s of silence

# Socket Buffer & Framing Settings
MAX_SOCKET_BUFFER = 65536          # 64 KB chunk size for socket operations
LENGTH_PREFIX_SIZE = 4             # 4-byte big-endian integer length prefix

# File Transfer Settings
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "LANChat_Received"

# Ensure download directory exists
os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
