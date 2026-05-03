"""
P2P网络消息模型

合并自 local_market/models.py NetworkMessage + MessageType
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import json

from .enums import MessageType


@dataclass
class NetworkMessage:
    """P2P网络消息"""
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    msg_type: MessageType = MessageType.CHAT

    # 收发
    sender_id: str = ""
    sender_name: str = ""
    receiver_id: Optional[str] = None          # None = 广播

    # 路由
    relay_nodes: List[str] = field(default_factory=list)
    ttl: int = 3
    hop_count: int = 0

    # 内容
    payload: Dict[str, Any] = field(default_factory=dict)

    # 安全
    encrypted: bool = False
    signature: str = ""

    # 时间
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    expires_at: Optional[float] = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now().timestamp() > self.expires_at

    @property
    def is_broadcast(self) -> bool:
        return self.receiver_id is None

    def to_bytes(self) -> bytes:
        data = {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "receiver_id": self.receiver_id,
            "relay_nodes": self.relay_nodes,
            "ttl": self.ttl,
            "hop_count": self.hop_count,
            "payload": self.payload,
            "encrypted": self.encrypted,
            "signature": self.signature,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
        }
        return json.dumps(data, ensure_ascii=False).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> NetworkMessage:
        obj = json.loads(data.decode("utf-8"))
        return cls(
            msg_id=obj.get("msg_id", ""),
            msg_type=MessageType(obj.get("msg_type", "chat")),
            sender_id=obj.get("sender_id", ""),
            sender_name=obj.get("sender_name", ""),
            receiver_id=obj.get("receiver_id"),
            relay_nodes=obj.get("relay_nodes", []),
            ttl=obj.get("ttl", 3),
            hop_count=obj.get("hop_count", 0),
            payload=obj.get("payload", {}),
            encrypted=obj.get("encrypted", False),
            signature=obj.get("signature", ""),
            timestamp=obj.get("timestamp", datetime.now().timestamp()),
            expires_at=obj.get("expires_at"),
        )

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "receiver_id": self.receiver_id,
            "relay_nodes": self.relay_nodes,
            "ttl": self.ttl,
            "hop_count": self.hop_count,
            "payload": self.payload,
            "encrypted": self.encrypted,
            "signature": self.signature,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NetworkMessage:
        return cls(
            msg_id=data.get("msg_id", ""),
            msg_type=MessageType(data.get("msg_type", "chat")),
            sender_id=data.get("sender_id", ""),
            sender_name=data.get("sender_name", ""),
            receiver_id=data.get("receiver_id"),
            relay_nodes=data.get("relay_nodes", []),
            ttl=data.get("ttl", 3),
            hop_count=data.get("hop_count", 0),
            payload=data.get("payload", {}),
            encrypted=data.get("encrypted", False),
            signature=data.get("signature", ""),
            timestamp=data.get("timestamp", datetime.now().timestamp()),
            expires_at=data.get("expires_at"),
        )
