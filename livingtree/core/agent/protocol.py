"""
LivingTree — Multi-Agent Communication Protocol
=================================================

Full migration from client/src/business/multi_agent/protocol.py

Agent-to-Agent communication format with:
- Request/Response/Broadcast/Notification/Heartbeat message types
- Priority-based message routing
- Conversation tracking
- Topic-based pub/sub subscriptions
- JSON serialization/deserialization
"""

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"


class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class AgentMessage:
    msg_id: str
    msg_type: MessageType
    sender: str
    receiver: str
    action: str
    payload: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=lambda: __import__('time').time())
    reply_to: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    conv_id: str
    participants: List[str]
    messages: List[AgentMessage] = field(default_factory=list)
    created_at: float = field(default_factory=lambda: __import__('time').time())
    updated_at: float = field(default_factory=lambda: __import__('time').time())


class AgentProtocol:
    """Agent communication protocol — message creation, routing, conversation management."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.conversations: Dict[str, Conversation] = {}
        self.outbox: List[AgentMessage] = []
        self.inbox: List[AgentMessage] = []
        self.subscriptions: Dict[str, List[str]] = {}

    def create_request(self, receiver: str, action: str,
                       payload: Dict[str, Any] = None) -> AgentMessage:
        msg = AgentMessage(
            msg_id=str(uuid.uuid4())[:12],
            msg_type=MessageType.REQUEST,
            sender=self.agent_id,
            receiver=receiver,
            action=action,
            payload=payload or {},
        )
        self.outbox.append(msg)
        return msg

    def create_response(self, original_msg: AgentMessage,
                        success: bool, result: Any = None,
                        error: str = None) -> AgentMessage:
        payload = {"success": success, "result": result}
        if error:
            payload["error"] = error

        msg = AgentMessage(
            msg_id=str(uuid.uuid4())[:12],
            msg_type=MessageType.RESPONSE,
            sender=self.agent_id,
            receiver=original_msg.sender,
            action=f"{original_msg.action}_response",
            payload=payload,
            reply_to=original_msg.msg_id,
        )
        self.outbox.append(msg)
        return msg

    def create_broadcast(self, action: str, payload: Dict[str, Any] = None,
                         topic: str = None) -> AgentMessage:
        msg = AgentMessage(
            msg_id=str(uuid.uuid4())[:12],
            msg_type=MessageType.BROADCAST,
            sender=self.agent_id,
            receiver="",
            action=action,
            payload=payload or {},
            metadata={"topic": topic} if topic else {},
        )
        self.outbox.append(msg)
        return msg

    def create_notification(self, receiver: str, action: str,
                            payload: Dict[str, Any] = None) -> AgentMessage:
        msg = AgentMessage(
            msg_id=str(uuid.uuid4())[:12],
            msg_type=MessageType.NOTIFICATION,
            sender=self.agent_id,
            receiver=receiver,
            action=action,
            payload=payload or {},
        )
        self.outbox.append(msg)
        return msg

    def create_heartbeat(self) -> AgentMessage:
        import time
        return self.create_broadcast("heartbeat", {
            "agent_id": self.agent_id,
            "timestamp": time.time(),
        }, topic="heartbeat")

    def send_message(self, msg: AgentMessage) -> bool:
        self.outbox.append(msg)
        return True

    def receive_message(self, msg: AgentMessage) -> None:
        self.inbox.append(msg)
        if msg.reply_to:
            for conv in self.conversations.values():
                for m in conv.messages:
                    if m.msg_id == msg.reply_to:
                        m.metadata["reply"] = msg

    def process_inbox(self) -> List[AgentMessage]:
        messages = self.inbox.copy()
        self.inbox.clear()
        return messages

    def get_outbox(self) -> List[AgentMessage]:
        outbox = self.outbox.copy()
        self.outbox.clear()
        return outbox

    def start_conversation(self, conv_id: str, participants: List[str]) -> Conversation:
        conv = Conversation(conv_id=conv_id, participants=participants)
        self.conversations[conv_id] = conv
        return conv

    def add_to_conversation(self, conv_id: str, msg: AgentMessage) -> bool:
        if conv_id not in self.conversations:
            return False
        conv = self.conversations[conv_id]
        conv.messages.append(msg)
        import time
        conv.updated_at = time.time()
        return True

    def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        return self.conversations.get(conv_id)

    def get_conversation_history(self, conv_id: str, limit: int = 50) -> List[AgentMessage]:
        conv = self.conversations.get(conv_id)
        if not conv:
            return []
        return conv.messages[-limit:]

    def subscribe(self, topic: str) -> None:
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        if self.agent_id not in self.subscriptions[topic]:
            self.subscriptions[topic].append(self.agent_id)

    def unsubscribe(self, topic: str) -> None:
        if topic in self.subscriptions and self.agent_id in self.subscriptions[topic]:
            self.subscriptions[topic].remove(self.agent_id)

    def get_subscribers(self, topic: str) -> List[str]:
        return self.subscriptions.get(topic, [])

    def serialize_message(self, msg: AgentMessage) -> str:
        return json.dumps({
            "msg_id": msg.msg_id,
            "msg_type": msg.msg_type.value,
            "sender": msg.sender,
            "receiver": msg.receiver,
            "action": msg.action,
            "payload": msg.payload,
            "priority": msg.priority.value,
            "timestamp": msg.timestamp,
            "reply_to": msg.reply_to,
            "metadata": msg.metadata,
        })

    @staticmethod
    def deserialize_message(data: str) -> AgentMessage:
        obj = json.loads(data)
        return AgentMessage(
            msg_id=obj["msg_id"],
            msg_type=MessageType(obj["msg_type"]),
            sender=obj["sender"],
            receiver=obj["receiver"],
            action=obj["action"],
            payload=obj["payload"],
            priority=MessagePriority(obj.get("priority", 1)),
            timestamp=obj.get("timestamp", __import__('time').time()),
            reply_to=obj.get("reply_to"),
            metadata=obj.get("metadata", {}),
        )


class ProtocolRegistry:
    """Global protocol registry — manages all agent protocol instances."""

    def __init__(self):
        self.protocols: Dict[str, AgentProtocol] = {}

    def register(self, agent_id: str) -> AgentProtocol:
        if agent_id not in self.protocols:
            self.protocols[agent_id] = AgentProtocol(agent_id)
        return self.protocols[agent_id]

    def get_protocol(self, agent_id: str) -> Optional[AgentProtocol]:
        return self.protocols.get(agent_id)

    def get_all_protocols(self) -> Dict[str, AgentProtocol]:
        return self.protocols.copy()

    def route_message(self, msg: AgentMessage) -> bool:
        if msg.msg_type == MessageType.BROADCAST:
            topic = msg.metadata.get("topic")
            if topic:
                subscribers = []
                for proto in self.protocols.values():
                    if topic in proto.subscriptions:
                        subscribers.extend(proto.subscriptions[topic])
                for subscriber_id in set(subscribers):
                    proto = self.protocols.get(subscriber_id)
                    if proto and subscriber_id != msg.sender:
                        proto.receive_message(msg)
            return True

        receiver_proto = self.protocols.get(msg.receiver)
        if receiver_proto:
            receiver_proto.receive_message(msg)
            return True
        return False


_protocol_registry: Optional[ProtocolRegistry] = None


def get_protocol_registry() -> ProtocolRegistry:
    global _protocol_registry
    if _protocol_registry is None:
        _protocol_registry = ProtocolRegistry()
    return _protocol_registry


__all__ = [
    "AgentProtocol",
    "AgentMessage",
    "Conversation",
    "MessageType",
    "MessagePriority",
    "ProtocolRegistry",
    "get_protocol_registry",
]
