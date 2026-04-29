"""
去中心化论坛协议层
实现帖子/回复的 P2P 广播、同步与订阅机制

参考: NNTP (新闻组) 轻量树状讨论 + ActivityPub 联邦协议
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import hashlib

from .models import (
    ForumPost, ForumReply, Topic, Subscription,
    PostNotification, generate_post_id, generate_reply_id, compute_hash_chain,
    Author, PostContent, ContentType, PostStatus, ReplyStatus
)

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """协议消息类型"""
    # 帖子操作
    POST_CREATE = "post:create"
    POST_UPDATE = "post:update"
    POST_DELETE = "post:delete"
    POST_GET = "post:get"

    # 回复操作
    REPLY_CREATE = "reply:create"
    REPLY_UPDATE = "reply:update"
    REPLY_DELETE = "reply:delete"

    # 话题操作
    TOPIC_CREATE = "topic:create"
    TOPIC_SUBSCRIBE = "topic:subscribe"
    TOPIC_UNSUBSCRIBE = "topic:unsubscribe"

    # 同步操作
    SYNC_REQUEST = "sync:request"
    SYNC_RESPONSE = "sync:response"
    SYNC_ACK = "sync:ack"

    # 通知
    NOTIFICATION = "notification"

    # 投票
    VOTE = "vote"


@dataclass
class ProtocolMessage:
    """协议消息"""
    msg_id: str           # 消息唯一 ID
    msg_type: str         # 消息类型
    sender_id: str        # 发送者节点 ID
    sender_name: str      # 发送者显示名
    timestamp: float      # 时间戳
    topic_id: Optional[str] = None  # 话题 ID (可选)
    payload: Dict[str, Any] = field(default_factory=dict)  # 负载
    ttl: int = 3          # 跳数/生存时间
    previous_hash: str = ""  # 前一个消息的哈希 (哈希链)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value if isinstance(self.msg_type, Enum) else self.msg_type,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "timestamp": self.timestamp,
            "topic_id": self.topic_id,
            "payload": self.payload,
            "ttl": self.ttl,
            "previous_hash": self.previous_hash
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ProtocolMessage':
        data = dict(data)
        data["msg_type"] = MessageType(data["msg_type"])
        return cls(**data)

    def compute_hash(self) -> str:
        """计算消息哈希"""
        content = f"{self.msg_id}{self.msg_type.value}{self.sender_id}{self.timestamp}{json.dumps(self.payload, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class SyncState:
    """同步状态"""
    last_sync_time: float = 0.0
    last_sync_hash: str = ""
    synced_post_ids: List[str] = field(default_factory=list)
    synced_reply_ids: List[str] = field(default_factory=list)


class ForumProtocol:
    """
    论坛协议处理器

    功能:
    - 帖子/回复的广播
    - 订阅与推送
    - 离线同步
    - 哈希链验证
    """

    def __init__(self, node_id: str, display_name: str):
        self.node_id = node_id
        self.display_name = display_name

        # 消息回调
        self._callbacks: Dict[str, List[Callable]] = {
            "post:create": [],
            "post:update": [],
            "post:delete": [],
            "reply:create": [],
            "reply:update": [],
            "reply:delete": [],
            "topic:create": [],
            "topic:subscribe": [],
            "topic:unsubscribe": [],
            "sync:request": [],
            "sync:response": [],
            "notification": [],
            "vote": [],
        }

        # 已处理的消息 ID (防止重复)
        self._processed_msgs: Dict[str, float] = {}  # msg_id -> timestamp
        self._previous_hash: str = ""  # 上一个消息的哈希

        # 同步状态
        self._sync_states: Dict[str, SyncState] = {}  # node_id -> SyncState

        # 待同步的消息队列 (离线期间收到)
        self._pending_messages: List[ProtocolMessage] = []

        # 发布者回调 (用于发送消息到网络)
        self._broadcast_callback: Optional[Callable] = None

        # 清理过期消息 (1小时前的)
        self._cleanup_interval = 3600

    def set_broadcast_callback(self, callback: Callable):
        """设置广播回调 (用于发送到 P2P 网络)"""
        self._broadcast_callback = callback

    def register_callback(self, msg_type: str, callback: Callable):
        """注册消息回调"""
        if msg_type in self._callbacks:
            self._callbacks[msg_type].append(callback)

    def unregister_callback(self, msg_type: str, callback: Callable):
        """取消注册回调"""
        if msg_type in self._callbacks:
            self._callbacks[msg_type].remove(callback)

    # ==================== 消息构建 ====================

    def build_post_create_message(self, post: ForumPost, topic_id: str) -> ProtocolMessage:
        """构建帖子创建消息"""
        msg_id = f"msg_{int(time.time() * 1000)}_{self.node_id}"
        msg = ProtocolMessage(
            msg_id=msg_id,
            msg_type=MessageType.POST_CREATE,
            sender_id=self.node_id,
            sender_name=self.display_name,
            timestamp=time.time(),
            topic_id=topic_id,
            payload={
                "post": post.to_dict(),
            },
            ttl=3,
            previous_hash=self._previous_hash
        )
        msg.hash = msg.compute_hash()
        self._previous_hash = msg.hash
        return msg

    def build_reply_create_message(self, reply: ForumReply, post_id: str) -> ProtocolMessage:
        """构建回复创建消息"""
        msg_id = f"msg_{int(time.time() * 1000)}_{self.node_id}"
        msg = ProtocolMessage(
            msg_id=msg_id,
            msg_type=MessageType.REPLY_CREATE,
            sender_id=self.node_id,
            sender_name=self.display_name,
            timestamp=time.time(),
            topic_id=reply.content.language,
            payload={
                "reply": reply.to_dict(),
                "post_id": post_id,
            },
            ttl=3,
            previous_hash=self._previous_hash
        )
        msg.hash = msg.compute_hash()
        self._previous_hash = msg.hash
        return msg

    def build_vote_message(self, voter_id: str, target_type: str, target_id: str, vote_type: str) -> ProtocolMessage:
        """构建投票消息"""
        msg_id = f"msg_{int(time.time() * 1000)}_{self.node_id}"
        msg = ProtocolMessage(
            msg_id=msg_id,
            msg_type=MessageType.VOTE,
            sender_id=self.node_id,
            sender_name=self.display_name,
            timestamp=time.time(),
            payload={
                "voter_id": voter_id,
                "target_type": target_type,
                "target_id": target_id,
                "vote_type": vote_type,
            },
            ttl=2,
            previous_hash=self._previous_hash
        )
        msg.hash = msg.compute_hash()
        self._previous_hash = msg.hash
        return msg

    def build_sync_request_message(self, since_timestamp: float = 0) -> ProtocolMessage:
        """构建同步请求消息"""
        msg_id = f"msg_{int(time.time() * 1000)}_{self.node_id}"
        msg = ProtocolMessage(
            msg_id=msg_id,
            msg_type=MessageType.SYNC_REQUEST,
            sender_id=self.node_id,
            sender_name=self.display_name,
            timestamp=time.time(),
            payload={
                "since_timestamp": since_timestamp,
            },
            ttl=1,
            previous_hash=self._previous_hash
        )
        msg.hash = msg.compute_hash()
        self._previous_hash = msg.hash
        return msg

    def build_topic_subscribe_message(self, topic_id: str) -> ProtocolMessage:
        """构建话题订阅消息"""
        msg_id = f"msg_{int(time.time() * 1000)}_{self.node_id}"
        msg = ProtocolMessage(
            msg_id=msg_id,
            msg_type=MessageType.TOPIC_SUBSCRIBE,
            sender_id=self.node_id,
            sender_name=self.display_name,
            timestamp=time.time(),
            topic_id=topic_id,
            payload={},
            ttl=2,
            previous_hash=self._previous_hash
        )
        msg.hash = msg.compute_hash()
        self._previous_hash = msg.hash
        return msg

    # ==================== 消息处理 ====================

    async def handle_message(self, msg: ProtocolMessage) -> bool:
        """
        处理接收到的协议消息
        返回: 是否处理成功
        """
        # 防重复检查
        if msg.msg_id in self._processed_msgs:
            logger.debug(f"Duplicate message ignored: {msg.msg_id}")
            return False

        # 验证哈希链
        if msg.previous_hash != self._previous_hash:
            logger.warning(f"Hash chain mismatch for message {msg.msg_id}, expected {self._previous_hash}, got {msg.previous_hash}")
            # 仍然处理，但不验证哈希链 (可能从其他分支同步)

        # 验证 TTL
        if msg.ttl <= 0:
            logger.debug(f"Message TTL expired: {msg.msg_id}")
            return False

        # 标记已处理
        self._processed_msgs[msg.msg_id] = time.time()

        # 更新哈希
        self._previous_hash = msg.hash

        # 调用回调
        msg_type_str = msg.msg_type.value if isinstance(msg.msg_type, Enum) else msg.msg_type
        callbacks = self._callbacks.get(msg_type_str, [])

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(msg)
                else:
                    callback(msg)
            except Exception as e:
                logger.error(f"Callback error for {msg_type_str}: {e}")

        # 广播给其他节点 (TTL > 1 时)
        if msg.ttl > 1 and self._broadcast_callback:
            msg.ttl -= 1
            try:
                self._broadcast_callback(msg)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

        return True

    async def broadcast_post(self, post: ForumPost, topic_id: str):
        """广播帖子创建"""
        msg = self.build_post_create_message(post, topic_id)
        await self.handle_message(msg)

    async def broadcast_reply(self, reply: ForumReply, post_id: str):
        """广播回复创建"""
        msg = self.build_reply_create_message(reply, post_id)
        await self.handle_message(msg)

    async def broadcast_vote(self, voter_id: str, target_type: str, target_id: str, vote_type: str):
        """广播投票"""
        msg = self.build_vote_message(voter_id, target_type, target_id, vote_type)
        await self.handle_message(msg)

    # ==================== 同步 ====================

    def get_pending_messages(self) -> List[ProtocolMessage]:
        """获取待同步消息"""
        return self._pending_messages.copy()

    def add_pending_message(self, msg: ProtocolMessage):
        """添加待同步消息"""
        self._pending_messages.append(msg)

    async def request_sync(self, since_timestamp: float = 0):
        """请求同步"""
        msg = self.build_sync_request_message(since_timestamp)
        if self._broadcast_callback:
            self._broadcast_callback(msg)

    def cleanup_old_messages(self):
        """清理过期的已处理消息"""
        now = time.time()
        expired = [msg_id for msg_id, ts in self._processed_msgs.items() if now - ts > self._cleanup_interval]
        for msg_id in expired:
            del self._processed_msgs[msg_id]


class ForumProtocolHandler:
    """
    论坛协议处理器 (便捷封装)

    提供高层 API，封装协议细节
    """

    def __init__(self, protocol: ForumProtocol):
        self.protocol = protocol

    async def publish_post(self, post: ForumPost, topic_id: str):
        """发布帖子"""
        await self.protocol.broadcast_post(post, topic_id)

    async def publish_reply(self, reply: ForumReply, post_id: str):
        """发布回复"""
        await self.protocol.broadcast_reply(reply, post_id)

    async def vote_post(self, voter_id: str, post_id: str, is_upvote: bool):
        """投票帖子"""
        vote_type = "up" if is_upvote else "down"
        await self.protocol.broadcast_vote(voter_id, "post", post_id, vote_type)

    async def vote_reply(self, voter_id: str, reply_id: str, is_upvote: bool):
        """投票回复"""
        vote_type = "up" if is_upvote else "down"
        await self.protocol.broadcast_vote(voter_id, "reply", reply_id, vote_type)

    async def subscribe_topic(self, topic_id: str):
        """订阅话题"""
        msg = self.protocol.build_topic_subscribe_message(topic_id)
        await self.protocol.handle_message(msg)

    def register_post_handler(self, handler: Callable):
        """注册帖子处理句柄"""
        self.protocol.register_callback("post:create", handler)

    def register_reply_handler(self, handler: Callable):
        """注册回复处理句柄"""
        self.protocol.register_callback("reply:create", handler)
