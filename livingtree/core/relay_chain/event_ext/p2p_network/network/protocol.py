"""
通信协议 - P2P Network Protocol

定义节点间的通信协议格式和处理器。

消息类型：
- DISCOVER: 节点发现（UDP多播）
- HELLO: 节点握手
- PEER_EXCHANGE: 节点列表交换
- ELECTION_*: 选举相关消息
- HEARTBEAT: 心跳保活
- TASK_*: 任务相关消息
- LOAD_REPORT: 负载上报
- ROUTING_UPDATE: 路由更新

消息格式：
{
    "type": "MESSAGE_TYPE",
    "from": "node_id",
    "to": "node_id",        # 可选，空表示广播
    "id": "msg_unique_id",
    "timestamp": 1234567890.123,
    "ttl": 3,               # 消息跳数限制
    "payload": {
        ...
    }
}
"""

import json
import time
import uuid
import struct
import logging
from enum import Enum
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from threading import RLock

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型枚举"""

    # 发现协议
    DISCOVER = "DISCOVER"
    HELLO = "HELLO"
    GOODBYE = "GOODBYE"
    PEER_EXCHANGE = "PEER_EXCHANGE"

    # 选举协议
    ELECTION = "ELECTION"
    ELECTION_OK = "ELECTION_OK"
    COORDINATOR = "COORDINATOR"
    HEARTBEAT = "HEARTBEAT"
    VOTE_REQUEST = "VOTE_REQUEST"
    VOTE_RESPONSE = "VOTE_RESPONSE"

    # 任务协议
    TASK_SUBMIT = "TASK_SUBMIT"
    TASK_DISPATCH = "TASK_DISPATCH"
    TASK_RESULT = "TASK_RESULT"
    TASK_STATUS = "TASK_STATUS"
    TASK_CANCEL = "TASK_CANCEL"

    # 负载协议
    LOAD_REPORT = "LOAD_REPORT"
    LOAD_QUERY = "LOAD_QUERY"

    # 路由协议
    ROUTING_UPDATE = "ROUTING_UPDATE"
    ROUTING_REQUEST = "ROUTING_REQUEST"

    # 系统
    PING = "PING"
    PONG = "PONG"
    ERROR = "ERROR"


@dataclass
class Message:
    """
    P2P 网络消息

    Attributes:
        type: 消息类型
        from_node: 发送节点ID
        to_node: 接收节点ID，空表示广播
        id: 消息唯一ID
        timestamp: 时间戳
        ttl: 跳数限制
        payload: 消息载荷
    """
    type: str
    from_node: str
    to_node: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)
    ttl: int = 3
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> bytes:
        """序列化为 JSON 字节"""
        return json.dumps({
            "type": self.type,
            "from": self.from_node,
            "to": self.to_node,
            "id": self.id,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
            "payload": self.payload,
        }, ensure_ascii=False).encode("utf-8")

    @classmethod
    def from_json(cls, data: bytes) -> "Message":
        """从 JSON 反序列化"""
        d = json.loads(data.decode("utf-8"))
        return cls(
            type=d["type"],
            from_node=d["from"],
            to_node=d.get("to", ""),
            id=d.get("id", uuid.uuid4().hex),
            timestamp=d.get("timestamp", time.time()),
            ttl=d.get("ttl", 3),
            payload=d.get("payload", {}),
        )

    def decrement_ttl(self) -> bool:
        """减少 TTL，返回是否还有效"""
        self.ttl -= 1
        return self.ttl > 0

    def is_broadcast(self) -> bool:
        """是否为广播消息"""
        return not self.to_node


@dataclass
class Protocol:
    """
    通信协议处理器

    负责：
    1. 消息的序列化和反序列化
    2. 消息的路由和转发
    3. 消息处理器注册

    使用示例：
    ```python
    protocol = Protocol(node_id="node-001")

    # 注册消息处理器
    protocol.register_handler(MessageType.TASK_DISPATCH, handle_task)

    # 发送消息
    protocol.send_message(node_id="node-002", msg_type=MessageType.PING)

    # 接收消息
    protocol.receive_message(data)
    ```
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._lock = RLock()

        # 消息处理器
        self._handlers: Dict[MessageType, Callable] = {}

        # 消息缓存（用于去重）
        self._seen_messages: Dict[str, float] = {}
        self._seen_expiry = 300.0  # 5分钟过期

        # 回调
        self.on_send: Optional[Callable[[str, bytes], None]] = None  # (to_node, data)
        self.on_broadcast: Optional[Callable[[bytes], None]] = None  # (data)
        self.on_message: Optional[Callable[[Message], None]] = None

    def register_handler(self, msg_type: MessageType, handler: Callable):
        """
        注册消息处理器

        Args:
            msg_type: 消息类型
            handler: 处理函数，签名为 handler(message: Message) -> None
        """
        with self._lock:
            self._handlers[msg_type] = handler
            logger.info(f"[{self.node_id}] 注册处理器: {msg_type.value}")

    def unregister_handler(self, msg_type: MessageType):
        """注销消息处理器"""
        with self._lock:
            if msg_type in self._handlers:
                del self._handlers[msg_type]

    def create_message(
        self,
        msg_type: MessageType,
        to_node: str = "",
        payload: Dict[str, Any] = None,
        ttl: int = 3,
    ) -> Message:
        """
        创建消息

        Args:
            msg_type: 消息类型
            to_node: 目标节点，空表示广播
            payload: 消息载荷
            ttl: 跳数限制

        Returns:
            Message 对象
        """
        return Message(
            type=msg_type.value,
            from_node=self.node_id,
            to_node=to_node,
            ttl=ttl,
            payload=payload or {},
        )

    def send_message(self, to_node: str, msg_type: MessageType, payload: Dict[str, Any] = None):
        """
        发送消息给指定节点

        Args:
            to_node: 目标节点ID
            msg_type: 消息类型
            payload: 消息载荷
        """
        msg = self.create_message(msg_type, to_node, payload)
        data = msg.to_json()

        logger.debug(f"[{self.node_id}] 发送消息 -> {to_node}: {msg_type.value}")

        if self.on_send:
            self.on_send(to_node, data)

    def broadcast(self, msg_type: MessageType, payload: Dict[str, Any] = None, ttl: int = 3):
        """
        广播消息

        Args:
            msg_type: 消息类型
            payload: 消息载荷
            ttl: 跳数限制
        """
        msg = self.create_message(msg_type, "", payload, ttl)
        data = msg.to_json()

        logger.debug(f"[{self.node_id}] 广播消息: {msg_type.value}")

        if self.on_broadcast:
            self.on_broadcast(data)

    def receive_message(self, data: bytes) -> Optional[Message]:
        """
        接收并处理消息

        Args:
            data: 原始消息数据

        Returns:
            如果消息有效且被处理，返回 Message 对象；否则返回 None
        """
        try:
            msg = Message.from_json(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"[{self.node_id}] 消息解析失败: {e}")
            return None

        # 忽略自己发的消息
        if msg.from_node == self.node_id:
            return None

        # 去重检查
        if not self._check_and_mark_seen(msg.id):
            logger.debug(f"[{self.node_id}] 忽略重复消息: {msg.id}")
            return None

        # TTL 检查
        if msg.ttl <= 0:
            logger.debug(f"[{self.node_id}] 忽略 TTL 耗尽的消息")
            return None

        # 路由消息
        self._route_message(msg)

        # 触发回调
        if self.on_message:
            self.on_message(msg)

        return msg

    def _check_and_mark_seen(self, msg_id: str) -> bool:
        """
        检查消息是否已见过，如果是则标记

        Args:
            msg_id: 消息ID

        Returns:
            True 如果是新消息，False 如果已见过
        """
        with self._lock:
            now = time.time()

            # 清理过期记录
            expired = [
                mid for mid, ts in self._seen_messages.items()
                if now - ts > self._seen_expiry
            ]
            for mid in expired:
                del self._seen_messages[mid]

            if msg_id in self._seen_messages:
                return False

            self._seen_messages[msg_id] = now
            return True

    def _route_message(self, msg: Message):
        """路由消息到处理器"""
        try:
            msg_type = MessageType(msg.type)
        except ValueError:
            logger.warning(f"[{self.node_id}] 未知消息类型: {msg.type}")
            return

        with self._lock:
            handler = self._handlers.get(msg_type)

        if handler:
            try:
                handler(msg)
            except Exception as e:
                logger.error(f"[{self.node_id}] 处理消息错误: {e}")
        else:
            logger.debug(f"[{self.node_id}] 无处理器: {msg_type.value}")

    def create_task_submit(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        requirements: Dict[str, Any] = None,
    ) -> Message:
        """创建任务提交消息"""
        return self.create_message(
            MessageType.TASK_SUBMIT,
            payload={
                "task_type": task_type,
                "task_data": task_data,
                "requirements": requirements or {},
                "submit_time": time.time(),
            }
        )

    def create_task_dispatch(
        self,
        task_id: str,
        executor: str,
        task_data: Dict[str, Any],
    ) -> Message:
        """创建任务分发消息"""
        return self.create_message(
            MessageType.TASK_DISPATCH,
            to_node=executor,
            payload={
                "task_id": task_id,
                "task_data": task_data,
                "dispatch_time": time.time(),
            }
        )

    def create_task_result(
        self,
        task_id: str,
        result: Any,
        success: bool = True,
        error: str = None,
    ) -> Message:
        """创建任务结果消息"""
        return self.create_message(
            MessageType.TASK_RESULT,
            payload={
                "task_id": task_id,
                "result": result,
                "success": success,
                "error": error,
                "complete_time": time.time(),
            }
        )

    def create_load_report(
        self,
        load: float,
        metrics: Dict[str, Any] = None,
    ) -> Message:
        """创建负载上报消息"""
        return self.create_message(
            MessageType.LOAD_REPORT,
            payload={
                "load": load,
                "metrics": metrics or {},
                "report_time": time.time(),
            }
        )

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        with self._lock:
            return {
                "node_id": self.node_id,
                "handlers": [t.value for t in self._handlers.keys()],
                "seen_messages": len(self._seen_messages),
            }
