"""
Broadcast Manager - 广播管理器
==============================

整合所有广播组件：
- 内容发布
- 订阅管理
- 索引搜索
- 反垃圾过滤

Author: LivingTreeAI Community
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any, List, Dict

from .content_types import Content, ContentType, ContentScope, create_email, create_post, create_website
from .subscription_broadcast import SubscriptionBroadcast, get_subscription_broadcast
from .distributed_index import DistributedInvertedIndex, SearchQuery, get_distributed_index
from .anti_spam import AntiSpamSystem, SpamScore, get_anti_spam
from .email_system import EmailSystem, get_email_system


class BroadcastConfig:
    """广播配置"""

    def __init__(self):
        # 启用状态
        self.enabled = True

        # 广播设置
        self.default_ttl = 7
        self.max_content_size = 1024 * 1024  # 1MB
        self.cache_size = 1000

        # 订阅设置
        self.default_boards = ["general"]
        self.auto_subscribe_boards = True

        # 反垃圾设置
        self.enable_anti_spam = True
        self.enable_rate_limit = True

        # 邮件设置
        self.default_email_priority = "normal"
        self.email_encrypt_default = True


@dataclass
class BroadcastStats:
    """广播统计"""
    published_content: int = 0
    received_content: int = 0
    searched_content: int = 0
    spam_filtered: int = 0
    rate_limited: int = 0
    emails_sent: int = 0
    emails_received: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    last_activity: float = field(default_factory=time.time)


class BroadcastManager:
    """
    广播管理器

    功能：
    1. 统一内容发布接口
    2. 订阅管理
    3. 搜索整合
    4. 反垃圾整合
    5. 统计追踪
    """

    def __init__(
        self,
        node_id: str,
        config: Optional[BroadcastConfig] = None,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
    ):
        self.node_id = node_id
        self.config = config or BroadcastConfig()
        self._send_func = send_func

        # 统计
        self.stats = BroadcastStats()

        # 子系统
        self.broadcast = get_subscription_broadcast(node_id)
        self.index = get_distributed_index(node_id)
        self.antispam = get_anti_spam(node_id)
        self.email_system = get_email_system(node_id)

        # 内容缓存
        self.content_cache: Dict[str, Content] = {}

        # 回调
        self._on_content_published: Optional[Callable] = None
        self._on_content_received: Optional[Callable] = None
        self._on_spam_filtered: Optional[Callable] = None

    # ========== 内容发布 ==========

    async def publish_content(
        self,
        content: Content,
        skip_anti_spam: bool = False,
    ) -> tuple[bool, str]:
        """
        发布内容

        Args:
            content: 内容对象
            skip_anti_spam: 是否跳过反垃圾检查

        Returns:
            (是否成功, 原因)
        """
        # 1. 验证内容
        if not content.is_valid():
            return False, "Invalid content"

        # 2. 反垃圾检查
        if self.config.enable_anti_spam and not skip_anti_spam:
            allowed, spam_score = self.antispam.filter_content(content)

            if not allowed:
                self.stats.spam_filtered += 1
                return False, f"Content filtered as spam ({spam_score.value})"

            # 检查速率限制
            if self.config.enable_rate_limit:
                action = f"publish_{content.type.value}"
                if not self.antispam.check_rate_limit(content.author, action):
                    self.stats.rate_limited += 1
                    return False, "Rate limit exceeded"

        # 3. 设置ID和签名
        if not content.content_id:
            content.content_id = content.compute_id()
        self.broadcast.sign_content(content)

        # 4. 发布
        success = await self.broadcast.publish(content)

        if success:
            # 5. 索引
            await self.index.index_content(content)

            # 6. 缓存
            self.content_cache[content.content_id] = content

            # 7. 统计
            self.stats.published_content += 1
            self.stats.last_activity = time.time()

            # 8. 回调
            if self._on_content_published:
                await self._on_content_published(content)

        return success, "Published successfully"

    async def publish_post(
        self,
        board: str,
        title: str,
        body: str,
        author: Optional[str] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> tuple[bool, str]:
        """发布帖子"""
        content = create_post(
            author=author or self.node_id,
            board=board,
            title=title,
            body=body,
            tags=tags,
            **kwargs
        )
        return await self.publish_content(content)

    async def publish_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        author: Optional[str] = None,
        cc: Optional[List[str]] = None,
        **kwargs
    ) -> tuple[bool, str]:
        """发送邮件"""
        # 邮件走专门的邮件系统
        email = await self.email_system.send_email(
            recipients=recipients,
            subject=subject,
            body=body,
            cc=cc,
            **kwargs
        )

        if email:
            self.stats.emails_sent += 1
            return True, "Email sent"

        return False, "Failed to send email"

    async def publish_website(
        self,
        url: str,
        title: str,
        body: str,
        author: Optional[str] = None,
        **kwargs
    ) -> tuple[bool, str]:
        """发布网站"""
        content = create_website(
            author=author or self.node_id,
            url=url,
            title=title,
            body=body,
            **kwargs
        )
        return await self.publish_content(content)

    # ========== 内容接收 ==========

    async def handle_incoming_content(self, content_data: dict):
        """处理收到的内容"""
        content = Content.from_dict(content_data)

        # 检查重复
        if content.content_id in self.content_cache:
            return

        # 反垃圾检查
        if self.config.enable_anti_spam:
            allowed, spam_score = self.antispam.filter_content(content)

            if not allowed:
                self.stats.spam_filtered += 1
                if self._on_spam_filtered:
                    await self._on_spam_filtered(content, spam_score)
                return

        # 索引
        await self.index.index_content(content)

        # 缓存
        self.content_cache[content.content_id] = content

        # 统计
        self.stats.received_content += 1
        self.stats.last_activity = time.time()

        # 更新反垃圾系统
        self.antispam.record_action(content.author, f"receive_{content.type.value}")

        # 回调
        if self._on_content_received:
            await self._on_content_received(content)

    # ========== 搜索 ==========

    async def search(
        self,
        query: str,
        content_types: Optional[List[str]] = None,
        boards: Optional[List[str]] = None,
        authors: Optional[List[str]] = None,
        limit: int = 20,
        **kwargs
    ) -> List[Any]:
        """
        搜索内容

        Args:
            query: 搜索词
            content_types: 内容类型过滤
            boards: 板块过滤
            authors: 作者过滤
            limit: 结果数量限制

        Returns:
            搜索结果列表
        """
        search_query = SearchQuery(
            query=query,
            content_types=content_types,
            boards=boards,
            authors=authors,
            limit=limit,
            **kwargs
        )

        results = await self.index.search(search_query)

        self.stats.searched_content += 1

        # 填充内容
        for result in results:
            if not result.content and result.content_id in self.content_cache:
                result.content = self.content_cache[result.content_id]

        return results

    # ========== 订阅管理 ==========

    def subscribe_board(self, board: str, node_id: Optional[str] = None):
        """订阅板块"""
        self.broadcast.subscribe_board(board, node_id)

    def unsubscribe_board(self, board: str, node_id: Optional[str] = None):
        """取消订阅板块"""
        self.broadcast.unsubscribe_board(board, node_id)

    def subscribe_author(self, author: str, node_id: Optional[str] = None):
        """关注作者"""
        self.broadcast.subscribe_author(author, node_id)

    def unsubscribe_author(self, author: str, node_id: Optional[str] = None):
        """取消关注作者"""
        self.broadcast.unsubscribe_author(author, node_id)

    def subscribe_keyword(self, keyword: str, node_id: Optional[str] = None):
        """订阅关键词"""
        self.broadcast.subscribe_keyword(keyword, node_id)

    def get_subscriptions(self) -> dict:
        """获取订阅列表"""
        return {
            "boards": list(self.broadcast.my_boards),
            "authors": list(self.broadcast.my_authors),
            "keywords": self.broadcast.my_keywords,
        }

    # ========== 内容获取 ==========

    def get_content(self, content_id: str) -> Optional[Content]:
        """获取内容"""
        return self.content_cache.get(content_id)

    def get_recent_content(
        self,
        content_type: Optional[ContentType] = None,
        board: Optional[str] = None,
        limit: int = 20,
    ) -> List[Content]:
        """获取最近内容"""
        results = []

        for content in self.content_cache.values():
            if content_type and content.type != content_type:
                continue
            if board and content.board != board:
                continue
            results.append(content)

        # 按时间排序
        results.sort(key=lambda c: c.timestamp, reverse=True)
        return results[:limit]

    # ========== 反垃圾 ==========

    def get_author_reputation(self, author: str) -> float:
        """获取作者信誉"""
        return self.antispam.reputation.get_reputation(author)

    def report_spam(self, content: Content):
        """举报垃圾内容"""
        self.antispam.record_negative_interaction(content.author, content.content_id)

    def report_false_positive(self, content: Content):
        """误报"""
        self.antispam.record_false_positive(content.author)

    def get_rate_limit_status(self, node_id: str, action: str) -> dict:
        """获取速率限制状态"""
        return self.antispam.get_rate_limit_status(node_id, action)

    # ========== 邮件 ==========

    def check_inbox(self):
        """检查收件箱"""
        asyncio.create_task(self.email_system.inbox.check_inbox(self.email_system.email))

    def get_inbox_emails(self, limit: int = 20) -> List[str]:
        """获取收件箱邮件ID列表"""
        return self.email_system.get_inbox(limit)

    def get_email(self, email_id: str) -> Optional[Content]:
        """获取邮件"""
        return self.email_system.email.get_received_email(email_id)

    # ========== 回调设置 ==========

    def set_content_published_callback(self, callback: Callable):
        """设置内容发布回调"""
        self._on_content_published = callback

    def set_content_received_callback(self, callback: Callable):
        """设置内容接收回调"""
        self._on_content_received = callback

    def set_spam_filtered_callback(self, callback: Callable):
        """设置垃圾过滤回调"""
        self._on_spam_filtered = callback

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "published": self.stats.published_content,
            "received": self.stats.received_content,
            "searched": self.stats.searched_content,
            "spam_filtered": self.stats.spam_filtered,
            "rate_limited": self.stats.rate_limited,
            "emails_sent": self.stats.emails_sent,
            "emails_received": self.stats.emails_received,
            "cached_content": len(self.content_cache),
            "last_activity": self.stats.last_activity,
            "subscriptions": self.get_subscriptions(),
            "antispam": self.antispam.get_stats(),
            "email": self.email_system.get_stats(),
        }


# 全局单例
_broadcast_manager_instance: Optional[BroadcastManager] = None


def get_broadcast_manager(node_id: str = "local") -> BroadcastManager:
    """获取广播管理器单例"""
    global _broadcast_manager_instance
    if _broadcast_manager_instance is None:
        _broadcast_manager_instance = BroadcastManager(node_id)
    return _broadcast_manager_instance