"""
去中心化论坛 - 核心调度器
整合所有论坛模块的统一入口

功能:
- 帖子/回复管理
- 订阅与推送
- P2P 广播
- 智能写作集成
- 离线同步
"""

import time
import asyncio
import logging
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field

from .models import (
    ForumPost, ForumReply, Topic, Subscription, Vote,
    Author, PostContent, ContentType, PostStatus, ReplyStatus, VoteType,
    generate_post_id, generate_reply_id
)
from .forum_protocol import ForumProtocol, ForumProtocolHandler, ProtocolMessage, MessageType
from .forum_storage import ForumStorage
from .smart_integration import SmartWritingIntegration, DiscussionAnalysis, SmartDraft

logger = logging.getLogger(__name__)


@dataclass
class ForumHubConfig:
    """论坛配置"""
    node_id: str = ""           # 当前节点 ID
    display_name: str = "Anonymous"  # 显示名称
    enable_p2p: bool = True    # 启用 P2P 广播
    enable_sync: bool = True   # 启用离线同步
    max_posts_per_page: int = 20
    max_replies_per_page: int = 50


class ForumHub:
    """
    论坛核心调度器 (单例)

    整合:
    - ForumStorage: 本地存储
    - ForumProtocol: P2P 协议
    - SmartWritingIntegration: 智能写作
    """

    _instance: Optional['ForumHub'] = None
    _lock = asyncio.Lock()

    def __init__(self, config: ForumHubConfig = None):
        self.config = config or ForumHubConfig()

        # 存储
        self.storage = ForumStorage(node_id=self.config.node_id)

        # 协议
        self.protocol = ForumProtocol(self.config.node_id, self.config.display_name)
        self.protocol_handler = ForumProtocolHandler(self.protocol)

        # 智能写作
        self.smart_writer = SmartWritingIntegration()

        # UI 回调
        self._ui_callbacks: Dict[str, List[Callable]] = {
            "post_created": [],
            "post_updated": [],
            "post_deleted": [],
            "reply_created": [],
            "reply_updated": [],
            "vote_changed": [],
            "new_post_received": [],  # P2P 收到的新帖
            "new_reply_received": [],  # P2P 收到的新回复
            "topic_updated": [],
            "sync_completed": [],
        }

        # 统计
        self._stats = {
            "posts_published": 0,
            "replies_published": 0,
            "votes_cast": 0,
            "synced_posts": 0,
            "synced_replies": 0,
        }

        # 已初始化
        self._initialized = False

    async def _init_async(self):
        """异步初始化"""
        if self._initialized:
            return

        # 设置协议广播回调
        def broadcast_to_p2p(msg: ProtocolMessage):
            # 这里将消息发送到 P2P 网络
            # 实际实现需要集成 P2PConnector
            logger.debug(f"Broadcasting message: {msg.msg_type.value}")

        self.protocol.set_broadcast_callback(broadcast_to_p2p)

        # 设置协议消息处理
        self.protocol.register_callback("post:create", self._on_post_received)
        self.protocol.register_callback("reply:create", self._on_reply_received)
        self.protocol.register_callback("vote", self._on_vote_received)

        # 设置智能写作回调 (如果有系统大脑)
        try:
            from ..system_brain import get_system_brain
            sb = get_system_brain()
            if sb:
                self.smart_writer.set_generate_callback(sb.generate)
        except ImportError:
            logger.debug("System brain not available for forum")

        self._initialized = True

    def ensure_initialized(self):
        """确保已初始化"""
        if not self._initialized:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._init_async())
            except RuntimeError:
                pass

    @classmethod
    def get_forum_hub(cls) -> 'ForumHub':
        """获取 ForumHub 单例"""
        if cls._instance is None:
            cls._instance = ForumHub()
        return cls._instance

    @classmethod
    async def get_forum_hub_async(cls) -> 'ForumHub':
        """异步获取 ForumHub 单例"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = ForumHub()
            await cls._instance._init_async()
            return cls._instance

    # ==================== UI 回调 ====================

    def add_ui_callback(self, event: str, callback: Callable):
        """添加 UI 回调"""
        if event in self._ui_callbacks:
            self._ui_callbacks[event].append(callback)

    def remove_ui_callback(self, event: str, callback: Callable):
        """移除 UI 回调"""
        if event in self._ui_callbacks:
            if callback in self._ui_callbacks[event]:
                self._ui_callbacks[event].remove(callback)

    def _emit(self, event: str, *args, **kwargs):
        """触发回调"""
        for callback in self._ui_callbacks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(*args, **kwargs))
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"UI callback error for {event}: {e}")

    # ==================== 话题操作 ====================

    def create_topic(self, name: str, description: str = "", icon: str = "📋") -> Topic:
        """创建话题"""
        topic = self.storage.create_topic(
            name=name,
            description=description,
            icon=icon,
            creator_id=self.config.node_id
        )
        self._emit("topic_updated", topic)
        return topic

    def get_topic(self, topic_id: str) -> Optional[Topic]:
        """获取话题"""
        return self.storage.get_topic(topic_id)

    def get_all_topics(self) -> List[Topic]:
        """获取所有话题"""
        return self.storage.get_all_topics()

    # ==================== 帖子操作 ====================

    async def create_post(self, topic_id: str, title: str, content: str,
                         content_type: ContentType = ContentType.TEXT,
                         tags: List[str] = None) -> ForumPost:
        """创建帖子"""
        author = Author(
            node_id=self.config.node_id,
            display_name=self.config.display_name,
            reputation=0.0
        )

        post_content = PostContent(
            text=content,
            content_type=content_type,
            language="zh"
        )

        post = self.storage.create_post(
            topic_id=topic_id,
            author=author,
            title=title,
            content=post_content,
            tags=tags
        )

        self._stats["posts_published"] += 1

        # P2P 广播
        if self.config.enable_p2p:
            await self.protocol.broadcast_post(post, topic_id)

        self._emit("post_created", post)
        return post

    def get_post(self, post_id: str) -> Optional[ForumPost]:
        """获取帖子"""
        return self.storage.get_post(post_id)

    def get_posts(self, topic_id: str = None, offset: int = 0, limit: int = 20,
                  sort_by: str = "created") -> List[ForumPost]:
        """获取帖子列表"""
        if topic_id:
            return self.storage.get_posts_by_topic(topic_id, offset, limit, sort_by)
        else:
            return self.storage.get_all_posts(offset, limit, sort_by)

    def increment_post_views(self, post_id: str):
        """增加浏览数"""
        self.storage.increment_post_views(post_id)

    async def delete_post(self, post_id: str):
        """删除帖子"""
        self.storage.delete_post(post_id)
        self._emit("post_deleted", post_id)

    # ==================== 回复操作 ====================

    async def create_reply(self, post_id: str, content: str,
                          parent_reply_id: str = None) -> ForumReply:
        """创建回复"""
        author = Author(
            node_id=self.config.node_id,
            display_name=self.config.display_name,
            reputation=0.0
        )

        post_content = PostContent(
            text=content,
            content_type=ContentType.TEXT,
            language="zh"
        )

        reply = self.storage.create_reply(
            post_id=post_id,
            author=author,
            content=post_content,
            parent_reply_id=parent_reply_id
        )

        self._stats["replies_published"] += 1

        # P2P 广播
        if self.config.enable_p2p:
            await self.protocol.broadcast_reply(reply, post_id)

        self._emit("reply_created", reply)
        return reply

    def get_replies(self, post_id: str, nested: bool = False) -> List[ForumReply]:
        """获取回复列表"""
        if nested:
            result = self.storage.get_nested_replies(post_id)
            return result.get("root", [])
        else:
            return self.storage.get_replies_by_post(post_id)

    # ==================== 订阅操作 ====================

    def subscribe(self, topic_id: str) -> Subscription:
        """订阅话题"""
        sub = self.storage.subscribe(self.config.node_id, topic_id)

        # 广播订阅
        if self.config.enable_p2p:
            msg = self.protocol.build_topic_subscribe_message(topic_id)
            asyncio.create_task(self.protocol.handle_message(msg))

        return sub

    def unsubscribe(self, topic_id: str):
        """取消订阅"""
        self.storage.unsubscribe(self.config.node_id, topic_id)

    def get_subscriptions(self) -> List[str]:
        """获取订阅列表"""
        return self.storage.get_subscriptions(self.config.node_id)

    def is_subscribed(self, topic_id: str) -> bool:
        """检查是否订阅"""
        return self.storage.is_subscribed(self.config.node_id, topic_id)

    # ==================== 投票操作 ====================

    async def vote_post(self, post_id: str, is_upvote: bool):
        """投票帖子"""
        vote_type = VoteType.UP if is_upvote else VoteType.DOWN
        self.storage.vote(self.config.node_id, "post", post_id, vote_type)
        self._stats["votes_cast"] += 1

        if self.config.enable_p2p:
            await self.protocol.broadcast_vote(
                self.config.node_id, "post", post_id,
                "up" if is_upvote else "down"
            )

        self._emit("vote_changed", "post", post_id)

    async def vote_reply(self, reply_id: str, is_upvote: bool):
        """投票回复"""
        vote_type = VoteType.UP if is_upvote else VoteType.DOWN
        self.storage.vote(self.config.node_id, "reply", reply_id, vote_type)
        self._stats["votes_cast"] += 1

        if self.config.enable_p2p:
            await self.protocol.broadcast_vote(
                self.config.node_id, "reply", reply_id,
                "up" if is_upvote else "down"
            )

        self._emit("vote_changed", "reply", reply_id)

    def get_user_vote(self, target_type: str, target_id: str) -> Optional[VoteType]:
        """获取用户对某内容的投票"""
        return self.storage.get_user_vote(self.config.node_id, target_type, target_id)

    # ==================== 搜索 ====================

    def search_posts(self, query: str, limit: int = 20) -> List[ForumPost]:
        """搜索帖子"""
        return self.storage.search_posts(query, limit)

    def search_replies(self, query: str, limit: int = 20) -> List[ForumReply]:
        """搜索回复"""
        return self.storage.search_replies(query, limit)

    # ==================== 智能写作 ====================

    async def generate_draft(self, topic: str, perspective: str = "balanced") -> SmartDraft:
        """生成智能草稿"""
        return await self.smart_writer.generate_draft(topic, perspective)

    async def analyze_discussion(self, post: ForumPost) -> DiscussionAnalysis:
        """分析讨论质量"""
        replies = self.storage.get_replies_by_post(post.post_id, limit=100)
        return await self.smart_writer.analyze_discussion(post, replies)

    async def enhance_reply(self, draft: str, context: str = "") -> str:
        """增强回复"""
        return await self.smart_writer.enhance_reply(draft, context)

    # ==================== P2P 接收处理 ====================

    async def _on_post_received(self, msg: ProtocolMessage):
        """收到远程帖子"""
        post_data = msg.payload.get("post", {})
        post = ForumPost.from_dict(post_data)

        # 忽略自己发送的
        if post.author.node_id == self.config.node_id:
            return

        # 存储
        # (实际应该检查是否已存在)
        self._stats["synced_posts"] += 1

        self._emit("new_post_received", post, msg)

    async def _on_reply_received(self, msg: ProtocolMessage):
        """收到远程回复"""
        reply_data = msg.payload.get("reply", {})
        reply = ForumReply.from_dict(reply_data)

        if reply.author.node_id == self.config.node_id:
            return

        self._stats["synced_replies"] += 1

        self._emit("new_reply_received", reply, msg)

    async def _on_vote_received(self, msg: ProtocolMessage):
        """收到远程投票"""
        payload = msg.payload
        voter_id = payload.get("voter_id")
        target_type = payload.get("target_type")
        target_id = payload.get("target_id")
        vote_type_str = payload.get("vote_type")

        if voter_id == self.config.node_id:
            return

        vote_type = VoteType.UP if vote_type_str == "up" else VoteType.DOWN
        self.storage.vote(voter_id, target_type, target_id, vote_type)

        self._emit("vote_changed", target_type, target_id)

    # ==================== 同步 ====================

    async def request_sync(self, since_timestamp: float = 0):
        """请求同步"""
        if not self.config.enable_sync:
            return

        await self.protocol.request_sync(since_timestamp)

    def get_pending_messages(self) -> List[ProtocolMessage]:
        """获取待同步消息"""
        return self.protocol.get_pending_messages()

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self._stats.copy()

    def get_user_stats(self, node_id: str = None) -> Dict[str, int]:
        """获取用户统计"""
        return self.storage.get_user_stats(node_id or self.config.node_id)


# 全局访问函数
def get_forum_hub() -> ForumHub:
    """获取 ForumHub 单例 (同步)"""
    return ForumHub.get_forum_hub()


async def get_forum_hub_async() -> ForumHub:
    """获取 ForumHub 单例 (异步)"""
    return await ForumHub.get_forum_hub_async()
