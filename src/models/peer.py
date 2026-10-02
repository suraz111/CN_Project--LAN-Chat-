"""
Peer Data Model representing active LAN users.
"""

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Peer:
    peer_id: str
    username: str
    device_name: str
    ip_address: str
    tcp_port: int
    status: str = "Online"
    last_seen: float = field(default_factory=time.time)
    is_web: bool = False

    def is_expired(self, timeout_seconds: float = 10.0) -> bool:
        """Check if the peer hasn't emitted a heartbeat within the timeout window."""
        return (time.time() - self.last_seen) > timeout_seconds

    def update_heartbeat(self, username: Optional[str] = None, status: Optional[str] = None) -> None:
        """Update last seen timestamp and optional metadata."""
        self.last_seen = time.time()
        if username:
            self.username = username
        if status:
            self.status = status

    def to_dict(self) -> dict:
        return {
            "peer_id": self.peer_id,
            "username": self.username,
            "device_name": self.device_name,
            "ip_address": self.ip_address,
            "tcp_port": self.tcp_port,
            "status": self.status,
            "last_seen": self.last_seen,
            "is_web": self.is_web,
        }
