"""
LivingTreeAI Protocol - 通信协议处理
=================================

消息类型定义和协议处理器

Author: Hermes Desktop Team
"""

import json
import struct
import hashlib
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime


class MessageType(Enum):
    """消息类型"""
    # 控制消息
    HEARTBEAT = 0x01
    NODE_REGISTER = 0x02
    NODE_UNREGISTER = 0x03

    # 任务消息
    TASK_REQUEST = 0x10
    TASK_RESPONSE = 0x11
    TASK_CANCEL = 0x12
    TASK_PROGRESS = 0x13

    # 知识消息
    KNOWLEDGE_PUSH = 0x20
    KNOWLEDGE_PULL = 0x21
    KNOWLEDGE_SYNC = 0x22

    # 联邦学习消息
    FL_ROUND_START = 0x30
    FL_MODEL_SEND = 0x31
    FL_GRADIENT_SEND = 0x32
    FL_AGGREGATE = 0x33

    # 网络消息
    PEER_DISCOVER = 0x40
    PEER_CONNECT = 0x41
    PEER_DISCONNECT = 0x42

    # 中继消息
    RELAY_REQUEST = 0x50
    RELAY_FORWARD = 0x51


@dataclass
class Message:
    """消息基类"""
    msg_type: MessageType
    sender_id: str
    timestamp: float = field(default_factory=time.time)
    message_id: str = ""
    ttl: int = 3          # 跳数限制

    # 加密和签名
    encrypted: bool = False
    signature: str = ""

    def __post_init__(self):
        if not self.message_id:
            self.message_id = hashlib.sha256(
                f"{self.sender_id}{self.timestamp}{self.msg_type}".encode()
            ).hexdigest()[:16]

    def to_dict(self) -> Dict:
        return {
            "msg_type": self.msg_type.value,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
            "ttl": self.ttl,
        }

    def to_bytes(self) -> bytes:
        """序列化为字节"""
        return json.dumps(self.to_dict()).encode('utf-8')

    @classmethod
    def from_bytes(cls, data: bytes) -> 'Message':
        """从字节反序列化"""
        d = json.loads(data.decode('utf-8'))
        return cls(
            msg_type=MessageType(d["msg_type"]),
            sender_id=d["sender_id"],
            timestamp=d["timestamp"],
            message_id=d["message_id"],
            ttl=d["ttl"],
        )


@dataclass
class TaskRequest(Message):
    """任务请求消息"""
    task_type: str = ""
    task_data: Any = None
    priority: int = 1
    required_capability: Optional[str] = None
    timeout: float = 300.0

    def __init__(self, sender_id: str, task_type: str, task_data: Any = None):
        super().__init__(MessageType.TASK_REQUEST, sender_id)
        self.task_type = task_type
        self.task_data = task_data

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update({
            "task_type": self.task_type,
            "task_data": str(self.task_data)[:1000],  # 截断
            "priority": self.priority,
            "required_capability": self.required_capability,
            "timeout": self.timeout,
        })
        return d


@dataclass
class TaskResponse(Message):
    """任务响应消息"""
    request_id: str = ""
    status: str = ""      # success, failed, cancelled
    result: Any = None
    error: str = ""
    progress: float = 1.0

    def __init__(self, sender_id: str, request_id: str, status: str = "success"):
        super().__init__(MessageType.TASK_RESPONSE, sender_id)
        self.request_id = request_id
        self.status = status

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update({
            "request_id": self.request_id,
            "status": self.status,
            "result": str(self.result)[:500] if self.result else None,
            "error": self.error,
            "progress": self.progress,
        })
        return d


@dataclass
class KnowledgeMessage(Message):
    """知识消息"""
    knowledge_type: str = ""
    title: str = ""
    content: Any = None
    tags: List[str] = field(default_factory=list)
    license: str = "open"
    source_node: str = ""

    def __init__(self, sender_id: str, title: str, content: Any, knowledge_type: str = "fact"):
        super().__init__(MessageType.KNOWLEDGE_PUSH, sender_id)
        self.title = title
        self.content = content
        self.knowledge_type = knowledge_type
        self.source_node = sender_id

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update({
            "knowledge_type": self.knowledge_type,
            "title": self.title,
            "content": str(self.content)[:500],
            "tags": self.tags,
            "license": self.license,
            "source_node": self.source_node,
        })
        return d


@dataclass
class FLMessage(Message):
    """联邦学习消息"""
    round_number: int = 0
    node_count: int = 0
    model_data: Any = None
    gradients: Any = None

    def __init__(self, sender_id: str, msg_type: MessageType, round_number: int):
        super().__init__(msg_type, sender_id)
        self.round_number = round_number

    def to_dict(self) -> Dict:
        d = super().to_dict()
        d.update({
            "round_number": self.round_number,
            "node_count": self.node_count,
            "has_model": self.model_data is not None,
            "has_gradients": self.gradients is not None,
        })
        return d


class ProtocolHandler:
    """
    协议处理器

    功能：
    - 消息编解码
    - 消息路由
    - 处理器注册
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.handlers: Dict[MessageType, Callable] = {}

        # 消息统计
        self.stats = {
            "sent": 0,
            "received": 0,
            "forwarded": 0,
            "errors": 0,
        }

    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器"""
        self.handlers[msg_type] = handler

    async def handle_message(self, data: bytes) -> Optional[bytes]:
        """处理接收到的消息"""
        try:
            # 解析消息头
            msg_obj = self._parse_header(data)

            # TTL 递减
            msg_obj.ttl -= 1
            if msg_obj.ttl <= 0:
                return None  # 丢弃

            # 查找处理器
            handler = self.handlers.get(msg_obj.msg_type)
            if handler:
                result = await handler(msg_obj)
                self.stats["received"] += 1
                return result
            else:
                # 默认处理
                self.stats["received"] += 1
                return None

        except Exception as e:
            self.stats["errors"] += 1
            print(f"消息处理错误: {e}")
            return None

    def _parse_header(self, data: bytes) -> Message:
        """解析消息头"""
        d = json.loads(data.decode('utf-8'))
        return Message(
            msg_type=MessageType(d["msg_type"]),
            sender_id=d["sender_id"],
            timestamp=d["timestamp"],
            message_id=d["message_id"],
            ttl=d["ttl"],
        )

    def create_message(self, msg_type: MessageType, **kwargs) -> bytes:
        """创建消息"""
        msg = Message(msg_type=msg_type, sender_id=self.node_id, **kwargs)
        self.stats["sent"] += 1
        return msg.to_bytes()

    async def forward_message(self, data: bytes, target_id: str) -> bool:
        """转发消息"""
        try:
            msg_obj = self._parse_header(data)
            msg_obj.ttl -= 1

            self.stats["forwarded"] += 1
            return True

        except Exception as e:
            self.stats["errors"] += 1
            return False

    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self.stats,
            "handlers_registered": len(self.handlers),
        }


# ==================== 协议常量 ====================

# 包格式版本
PROTOCOL_VERSION = 1

# 默认端口
DEFAULT_UDP_DISCOVERY_PORT = 19888
DEFAULT_TCP_PORT = 19889
DEFAULT_RELAY_PORT = 19890

# 超时配置
DEFAULT_TIMEOUT = 30.0
HEARTBEAT_INTERVAL = 10.0
CONNECTION_TIMEOUT = 60.0

# 消息大小限制
MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
MAX_KNOWLEDGE_SIZE = 10 * 1024 * 1024  # 10MB


if __name__ == "__main__":
    # 测试协议
    handler = ProtocolHandler("test_node")

    # 注册处理器
    async def handle_task(msg):
        print(f"收到任务: {msg.sender_id}")
        return None

    handler.register_handler(MessageType.TASK_REQUEST, handle_task)

    # 创建并处理消息
    msg_data = handler.create_message(MessageType.TASK_REQUEST)

    print(f"创建消息: {len(msg_data)} bytes")

    import asyncio
    asyncio.run(handler.handle_message(msg_data))

    print(f"统计: {handler.get_stats()}")
