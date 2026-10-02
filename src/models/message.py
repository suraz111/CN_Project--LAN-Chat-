"""
Message and Protocol Packet Data Models.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class MessageType(str, Enum):
    HEARTBEAT = "HEARTBEAT"
    CHAT = "CHAT"
    GROUP_CHAT = "GROUP_CHAT"
    TYPING = "TYPING"
    FILE_REQUEST = "FILE_REQUEST"
    FILE_ACCEPT = "FILE_ACCEPT"
    FILE_REJECT = "FILE_REJECT"
    FILE_CHUNK = "FILE_CHUNK"
    FILE_COMPLETE = "FILE_COMPLETE"
    GOODBYE = "GOODBYE"


@dataclass
class Packet:
    type: MessageType
    sender_id: str
    sender_name: str
    payload: Dict[str, Any]
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id,
            "type": self.type.value if isinstance(self.type, MessageType) else self.type,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Packet":
        return cls(
            msg_id=data.get("msg_id", str(uuid.uuid4())),
            type=MessageType(data["type"]),
            sender_id=data["sender_id"],
            sender_name=data["sender_name"],
            timestamp=data.get("timestamp", time.time()),
            payload=data.get("payload", {}),
        )
