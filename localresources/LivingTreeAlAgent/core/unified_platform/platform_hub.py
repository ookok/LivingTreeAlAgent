"""
Platform Hub - 统一平台调度中心
================================

整合邮件、博客、论坛三大平台，提供统一的调度接口。

功能：
- 三平台统一入口
- 消息路由
- 状态同步
- 事件分发

Author: Hermes Desktop Team
"""

import json
import time
import asyncio
import logging
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PlatformType(Enum):
    """平台类型"""
    EMAIL = "email"
    BLOG = "blog"
    FORUM = "forum"
    ALL = "all"


@dataclass
class PlatformStats:
    """平台统计"""
    platform: PlatformType
    total_posts: int = 0
    total_views: int = 0
    total_replies: int = 0
    last_activity: float = 0


@dataclass
class ActivityEvent:
    """活动事件"""
    event_id: str
    platform: PlatformType
    event_type: str  # new_post, new_reply, new_email, etc.
    actor_id: str
    actor_name: str
    target_id: str
    content_preview: str
    timestamp: float


class PlatformHub:
    """
    统一平台调度中心

    提供三大平台的统一调度和管理接口。

    使用示例：
        hub = PlatformHub()

        # 获取所有平台状态
        status = await hub.get_status()

        # 发布内容到多个平台
        results = await hub.publish_all(
            title="Hello World",
            content="<p>This is my first post!</p>",
            platforms=[PlatformType.FORUM, PlatformType.BLOG]
        )

        # 获取活动流
        activities = await hub.get_activities(limit=50)
    """

    _instance: Optional['PlatformHub'] = None

    def __init__(self):
        self._initialized = False

        # 组件
        self.publisher = None
        self.auto_publisher = None

        # 事件回调
        self._event_handlers: Dict[str, List[Callable]] = {
            "new_post": [],
            "new_email": [],
            "new_reply": [],
            "activity": []
        }

        # 活动流
        self.activities: List[ActivityEvent] = []
        self.max_activities = 500

        # 统计
        self.stats = {
            PlatformType.EMAIL: PlatformStats(platform=PlatformType.EMAIL),
            PlatformType.BLOG: PlatformStats(platform=PlatformType.BLOG),
            PlatformType.FORUM: PlatformStats(platform=PlatformType.FORUM)
        }

    @classmethod
    def get_instance(cls) -> 'PlatformHub':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self):
        """初始化"""
        if self._initialized:
            return

        # 初始化统一发布器
        from .unified_publisher import UnifiedPublisher
        self.publisher = UnifiedPublisher.get_instance()
        await self.publisher.initialize()

        # 初始化自动发布器
        from .auto_publisher import AutoPublisher
        self.auto_publisher = AutoPublisher()
        await self.auto_publisher.initialize()

        self._initialized = True
        logger.info("PlatformHub initialized")

    def register_handler(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        if event_type in self._event_handlers:
            self._event_handlers[event_type].append(handler)

    def unregister_handler(self, event_type: str, handler: Callable):
        """注销事件处理器"""
        if event_type in self._event_handlers:
            self._event_handlers[event_type].remove(handler)

    async def publish_all(
        self,
        title: str,
        content: str,
        platforms: List[PlatformType],
        author_id: str = "",
        author_name: str = "Anonymous",
        **kwargs
    ) -> Dict[PlatformType, Any]:
        """
        发布到多个平台

        Args:
            title: 标题
            content: 内容 (HTML)
            platforms: 目标平台列表
            author_id: 作者ID
            author_name: 作者名称

        Returns:
            各平台的发布结果
        """
        from .unified_publisher import PublishTarget, PlatformType as PubPlatform

        results = {}

        for platform in platforms:
            if platform == PlatformType.ALL:
                continue

            # 映射平台类型
            pub_platform = PubPlatform[platform.name]

            # 构建目标
            target = PublishTarget(
                platform=pub_platform,
                target_id=kwargs.get("target_id", ""),
                target_name=kwargs.get("target_name", ""),
                tags=kwargs.get("tags", [])
            )

            # 发布
            try:
                result = await self.publisher.publish(
                    title=title,
                    content=content,
                    targets=[target],
                    author_id=author_id,
                    author_name=author_name
                )

                results[platform] = result[0] if result else None

                # 更新统计
                self._update_stats(platform, success=result[0].success if result else False)

                # 触发事件
                await self._emit_event(
                    "new_post" if platform != PlatformType.EMAIL else "new_email",
                    platform=platform,
                    actor_id=author_id,
                    actor_name=author_name,
                    target_id=result[0].content_id if result else ""
                )

            except Exception as e:
                logger.error(f"Publish to {platform.value} failed: {e}")
                results[platform] = None

        return results

    def _update_stats(self, platform: PlatformType, success: bool = True):
        """更新统计"""
        stats = self.stats.get(platform)
        if stats:
            if success:
                stats.total_posts += 1
            stats.last_activity = time.time()

    async def get_activities(
        self,
        platform: PlatformType = PlatformType.ALL,
        limit: int = 50
    ) -> List[ActivityEvent]:
        """获取活动流"""
        activities = self.activities

        if platform != PlatformType.ALL:
            activities = [a for a in activities if a.platform == platform]

        return activities[-limit:]

    async def _emit_event(
        self,
        event_type: str,
        platform: PlatformType,
        actor_id: str,
        actor_name: str,
        target_id: str,
        content_preview: str = ""
    ):
        """触发事件"""
        event = ActivityEvent(
            event_id=str(time.time()),
            platform=platform,
            event_type=event_type,
            actor_id=actor_id,
            actor_name=actor_name,
            target_id=target_id,
            content_preview=content_preview,
            timestamp=time.time()
        )

        # 添加到活动流
        self.activities.append(event)
        if len(self.activities) > self.max_activities:
            self.activities = self.activities[-self.max_activities:]

        # 调用处理器
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    async def get_status(self) -> Dict[str, Any]:
        """获取平台状态"""
        return {
            "initialized": self._initialized,
            "platforms": {
                platform.value: {
                    "total_posts": stats.total_posts,
                    "total_views": stats.total_views,
                    "total_replies": stats.total_replies,
                    "last_activity": stats.last_activity,
                    "active": time.time() - stats.last_activity < 3600 if stats.last_activity else False
                }
                for platform, stats in self.stats.items()
            },
            "auto_publisher": self.auto_publisher.get_stats() if self.auto_publisher else None,
            "publisher": self.publisher.get_stats() if self.publisher else None
        }

    # ==================== 快捷方法 ====================

    async def send_email(
        self,
        to: str,
        subject: str,
        content: str,
        from_name: str = "Anonymous"
    ):
        """发送邮件"""
        from .unified_publisher import PublishTarget, PlatformType as PubPlatform
        target = PublishTarget(
            platform=PubPlatform.EMAIL,
            target_id=to
        )
        result = await self.publisher.publish(
            title=subject,
            content=content,
            targets=[target],
            author_name=from_name
        )
        return result

    async def post_blog(
        self,
        title: str,
        content: str,
        author_id: str = "",
        author_name: str = "Anonymous",
        tags: List[str] = None
    ):
        """发布博客"""
        return await self.publish_all(
            title=title,
            content=content,
            platforms=[PlatformType.BLOG],
            author_id=author_id,
            author_name=author_name,
            tags=tags or []
        )

    async def post_forum(
        self,
        title: str,
        content: str,
        topic_id: str = "general",
        author_id: str = "",
        author_name: str = "Anonymous",
        tags: List[str] = None
    ):
        """发布论坛帖子"""
        return await self.publish_all(
            title=title,
            content=content,
            platforms=[PlatformType.FORUM],
            author_id=author_id,
            author_name=author_name,
            target_id=topic_id,
            tags=tags or []
        )
