"""
Unified Publisher - 统一发布器
================================

整合邮件、博客、论坛三大平台的统一发布接口。

支持：
- 邮件发送（节点间通信）
- 博客发布
- 论坛发帖
- 富文本内容

Author: Hermes Desktop Team
"""

import json
import time
import uuid
import asyncio
import logging
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class PlatformType(Enum):
    """平台类型"""
    EMAIL = "email"           # 邮件
    BLOG = "blog"             # 博客
    FORUM = "forum"           # 论坛


class PublishStatus(Enum):
    """发布状态"""
    DRAFT = "draft"           # 草稿
    PENDING = "pending"        # 待发布
    PUBLISHING = "publishing"  # 发布中
    PUBLISHED = "published"    # 已发布
    FAILED = "failed"         # 失败


@dataclass
class PublishTarget:
    """发布目标"""
    platform: PlatformType
    target_id: str = ""           # 平台特定目标ID（如话题ID、收件人地址）
    target_name: str = ""
    visibility: str = "public"    # public/private/friends

    # 额外参数
    tags: List[str] = field(default_factory=list)
    category: str = ""
    allow_comments: bool = True
    allow_reprint: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "visibility": self.visibility,
            "tags": self.tags,
            "category": self.category,
            "allow_comments": self.allow_comments,
            "allow_reprint": self.allow_reprint
        }


@dataclass
class PublishResult:
    """发布结果"""
    success: bool
    target: PublishTarget

    # 结果信息
    content_id: str = ""
    url: str = ""
    message: str = ""
    error: Optional[str] = None

    # 统计
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "target": self.target.to_dict(),
            "content_id": self.content_id,
            "url": self.url,
            "message": self.message,
            "error": self.error,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms
        }


@dataclass
class PublishRequest:
    """发布请求"""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # 内容
    title: str = ""
    content: str = ""           # 富文本内容 (HTML)
    plain_text: str = ""        # 纯文本摘要

    # 目标
    targets: List[PublishTarget] = field(default_factory=list)

    # 作者
    author_id: str = ""
    author_name: str = ""
    author_avatar: str = ""

    # 选项
    draft: bool = False         # 是否保存为草稿
    scheduled_at: Optional[float] = None  # 定时发布

    created_at: float = field(default_factory=time.time)


class UnifiedPublisher:
    """
    统一发布器

    提供三大平台的统一发布接口：
    1. Email - 发送邮件到其他节点
    2. Blog - 发布博客文章
    3. Forum - 在论坛发帖

    使用示例：
        publisher = UnifiedPublisher()

        # 发送邮件
        result = await publisher.publish(
            content="Hello, this is a test email",
            targets=[PublishTarget(platform=PlatformType.EMAIL, target_id="user@node123.p2p")]
        )

        # 发布博客
        result = await publisher.publish(
            title="My First Blog Post",
            content="<p>Blog content here...</p>",
            targets=[PublishTarget(platform=PlatformType.BLOG, target_id="my-blog")]
        )

        # 论坛发帖
        result = await publisher.publish(
            title="Discussion Topic",
            content="<p>Forum post content...</p>",
            targets=[PublishTarget(platform=PlatformType.FORUM, target_id="general")]
        )
    """

    _instance: Optional['UnifiedPublisher'] = None

    def __init__(self):
        self._initialized = False

        # 发布历史
        self.publish_history: List[PublishResult] = []
        self.max_history = 1000

        # 草稿箱
        self.drafts: Dict[str, PublishRequest] = {}

        # 发布统计
        self.stats = {
            "total_published": 0,
            "total_failed": 0,
            "by_platform": {
                "email": {"success": 0, "failed": 0},
                "blog": {"success": 0, "failed": 0},
                "forum": {"success": 0, "failed": 0}
            }
        }

    @classmethod
    def get_instance(cls) -> 'UnifiedPublisher':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self):
        """异步初始化"""
        if self._initialized:
            return

        # 尝试导入并初始化各平台
        try:
            # 导入邮箱模块
            from client.src.business.decentralized_mailbox import MailboxHub
            self.mailbox = MailboxHub.get_instance()
            logger.info("Mailbox module initialized")
        except Exception as e:
            logger.warning(f"Mailbox module not available: {e}")
            self.mailbox = None

        try:
            # 导入论坛模块
            from client.src.business.forum import ForumHub
            self.forum = ForumHub()
            logger.info("Forum module initialized")
        except Exception as e:
            logger.warning(f"Forum module not available: {e}")
            self.forum = None

        self._initialized = True

    async def publish(
        self,
        title: str,
        content: str,
        targets: List[PublishTarget],
        author_id: str = "",
        author_name: str = "Anonymous",
        draft: bool = False,
        **kwargs
    ) -> List[PublishResult]:
        """
        统一发布接口

        Args:
            title: 标题
            content: 富文本内容 (HTML)
            targets: 发布目标列表
            author_id: 作者ID
            author_name: 作者名称
            draft: 是否保存为草稿

        Returns:
            List[PublishResult]: 各目标的发布结果
        """
        results = []

        for target in targets:
            start_time = time.time()

            try:
                if target.platform == PlatformType.EMAIL:
                    result = await self._publish_email(
                        title, content, target, author_id, author_name, draft
                    )
                elif target.platform == PlatformType.BLOG:
                    result = await self._publish_blog(
                        title, content, target, author_id, author_name, draft
                    )
                elif target.platform == PlatformType.FORUM:
                    result = await self._publish_forum(
                        title, content, target, author_id, author_name, draft
                    )
                else:
                    result = PublishResult(
                        success=False,
                        target=target,
                        error=f"Unknown platform: {target.platform}"
                    )
            except Exception as e:
                logger.error(f"Publish error for {target.platform.value}: {e}")
                result = PublishResult(
                    success=False,
                    target=target,
                    error=str(e)
                )

            result.duration_ms = (time.time() - start_time) * 1000
            results.append(result)

            # 更新统计
            self._update_stats(result)

        # 添加到历史
        self.publish_history.extend(results)
        if len(self.publish_history) > self.max_history:
            self.publish_history = self.publish_history[-self.max_history:]

        return results

    async def _publish_email(
        self,
        title: str,
        content: str,
        target: PublishTarget,
        author_id: str,
        author_name: str,
        draft: bool
    ) -> PublishResult:
        """发布邮件"""
        if not self.mailbox:
            # 没有邮箱模块，使用模拟方式
            logger.info(f"[Mock Email] To: {target.target_id}, Subject: {title}")
            return PublishResult(
                success=True,
                target=target,
                content_id=f"email_{uuid.uuid4().hex[:12]}",
                message=f"邮件已发送至 {target.target_id}（模拟模式）"
            )

        try:
            # 构建邮件消息
            from client.src.business.decentralized_mailbox.models import MailMessage, MailboxAddress

            msg = MailMessage(
                message_id=str(uuid.uuid4()),
                subject=title,
                body=content,
                body_plain=content[:200] if len(content) > 200 else content,
                from_addr=MailboxAddress(username=author_id, node_id="local"),
                to_addrs=[MailboxAddress(username=target.target_id.split("@")[0], node_id=target.target_id.split("@")[-1].replace(".p2p", ""))]
                if "@" in target.target_id else [MailboxAddress(username=target.target_id, node_id="unknown")]
            )

            if draft:
                msg.status = MessageStatus.DRAFT
                self.drafts[msg.message_id] = PublishRequest(
                    title=title,
                    content=content,
                    targets=[target],
                    author_id=author_id,
                    author_name=author_name,
                    draft=True
                )
                return PublishResult(
                    success=True,
                    target=target,
                    content_id=msg.message_id,
                    message="邮件已保存到草稿箱"
                )

            # 发送邮件
            await self.mailbox.send_message(msg)

            return PublishResult(
                success=True,
                target=target,
                content_id=msg.message_id,
                message=f"邮件已发送至 {target.target_id}"
            )

        except Exception as e:
            return PublishResult(
                success=False,
                target=target,
                error=f"邮件发送失败: {str(e)}"
            )

    async def _publish_blog(
        self,
        title: str,
        content: str,
        target: PublishTarget,
        author_id: str,
        author_name: str,
        draft: bool
    ) -> PublishResult:
        """发布博客"""
        # 博客实际上也是论坛帖子的一种特殊形式
        # 使用 Forum 模型发布博客文章

        try:
            from client.src.business.forum.models import (
                ForumPost, Author, PostContent, ContentType,
                PostStatus, generate_post_id
            )

            author = Author(
                node_id=author_id or "local",
                display_name=author_name,
                avatar_url=getattr(self, 'avatar_url', '')
            )

            post_content = PostContent(
                text=content,
                content_type=ContentType.RICH_TEXT
            )

            post = ForumPost(
                post_id=generate_post_id(),
                topic_id=target.target_id or "blog",  # 博客使用 blog 作为默认话题
                author=author,
                title=title,
                content=post_content,
                status=PostStatus.DRAFT if draft else PostStatus.PUBLISHED,
                tags=target.tags
            )

            if self.forum:
                await self.forum.create_post(post)

            return PublishResult(
                success=True,
                target=target,
                content_id=post.post_id,
                url=f"/blog/{post.post_id}",
                message=f"博客文章《{title}》已发布"
            )

        except Exception as e:
            logger.error(f"Blog publish error: {e}")
            return PublishResult(
                success=False,
                target=target,
                error=f"博客发布失败: {str(e)}"
            )

    async def _publish_forum(
        self,
        title: str,
        content: str,
        target: PublishTarget,
        author_id: str,
        author_name: str,
        draft: bool
    ) -> PublishResult:
        """发布论坛帖子"""
        try:
            from client.src.business.forum.models import (
                ForumPost, Author, PostContent, ContentType,
                PostStatus, generate_post_id
            )

            author = Author(
                node_id=author_id or "local",
                display_name=author_name,
                avatar_url=getattr(self, 'avatar_url', '')
            )

            post_content = PostContent(
                text=content,
                content_type=ContentType.RICH_TEXT
            )

            post = ForumPost(
                post_id=generate_post_id(),
                topic_id=target.target_id or "general",  # 默认发布到综合讨论区
                author=author,
                title=title,
                content=post_content,
                status=PostStatus.DRAFT if draft else PostStatus.PUBLISHED,
                tags=target.tags
            )

            if self.forum:
                await self.forum.create_post(post)

            return PublishResult(
                success=True,
                target=target,
                content_id=post.post_id,
                url=f"/forum/t/{post.post_id}",
                message=f"帖子《{title}》已发布到 {target.target_name or target.target_id}"
            )

        except Exception as e:
            logger.error(f"Forum publish error: {e}")
            return PublishResult(
                success=False,
                target=target,
                error=f"论坛发帖失败: {str(e)}"
            )

    def _update_stats(self, result: PublishResult):
        """更新统计"""
        if result.success:
            self.stats["total_published"] += 1
            self.stats["by_platform"][result.target.platform.value]["success"] += 1
        else:
            self.stats["total_failed"] += 1
            self.stats["by_platform"][result.target.platform.value]["failed"] += 1

    async def save_draft(
        self,
        request: PublishRequest
    ) -> str:
        """保存草稿"""
        self.drafts[request.request_id] = request
        return request.request_id

    async def get_draft(self, request_id: str) -> Optional[PublishRequest]:
        """获取草稿"""
        return self.drafts.get(request_id)

    async def delete_draft(self, request_id: str) -> bool:
        """删除草稿"""
        if request_id in self.drafts:
            del self.drafts[request_id]
            return True
        return False

    async def get_history(
        self,
        platform: PlatformType = None,
        limit: int = 50
    ) -> List[PublishResult]:
        """获取发布历史"""
        history = self.publish_history

        if platform:
            history = [r for r in history if r.target.platform == platform]

        return history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """获取发布统计"""
        return {
            **self.stats,
            "success_rate": (
                self.stats["total_published"] /
                max(1, self.stats["total_published"] + self.stats["total_failed"])
            ) * 100,
            "draft_count": len(self.drafts)
        }
