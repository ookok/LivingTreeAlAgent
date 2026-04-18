"""
Relay Server Blog & Forum API
==============================

中继服务器端的博客和论坛功能：

1. 内容收集 - 收集节点在内置平台发布的内容
2. 内容发布 - 用户可以在中继服务器端发布
3. 增量同步 - 节点可以拉取增量信息
4. 自动回复 - 节点可以随机对内容进行思考回复

Author: Hermes Desktop Team
"""

import json
import time
import uuid
import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================

class ContentType(Enum):
    """内容类型"""
    BLOG_POST = "blog_post"
    FORUM_POST = "forum_post"
    FORUM_REPLY = "forum_reply"


class ContentStatus(Enum):
    """内容状态"""
    DRAFT = "draft"
    PUBLISHED = "published"
    DELETED = "deleted"
    HIDDEN = "hidden"


@dataclass
class Author:
    """作者信息"""
    node_id: str
    display_name: str
    avatar_url: str = ""
    reputation: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Author":
        return cls(**data) if data else None


@dataclass
class ContentItem:
    """内容项"""
    content_id: str
    content_type: ContentType

    # 基本信息
    title: str
    content: str  # HTML 富文本
    author: Author

    # 平台来源
    source_platform: str  # 原创平台
    source_url: str = ""  # 原文链接

    # 状态
    status: ContentStatus = ContentStatus.PUBLISHED

    # 互动数据
    upvotes: int = 0
    downvotes: int = 0
    reply_count: int = 0
    view_count: int = 0

    # AI 处理
    ai_thought: str = ""
    ai_reply: str = ""
    ai_processed: bool = False
    ai_reply_id: str = ""  # AI 回复的 ID

    # 元数据
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    published_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "content_id": self.content_id,
            "content_type": self.content_type.value,
            "title": self.title,
            "content": self.content,
            "author": self.author.to_dict() if self.author else None,
            "source_platform": self.source_platform,
            "source_url": self.source_url,
            "status": self.status.value,
            "upvotes": self.upvotes,
            "downvotes": self.downvotes,
            "reply_count": self.reply_count,
            "view_count": self.view_count,
            "ai_thought": self.ai_thought,
            "ai_reply": self.ai_reply,
            "ai_processed": self.ai_processed,
            "ai_reply_id": self.ai_reply_id,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "published_at": self.published_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContentItem":
        if not data:
            return None
        data = dict(data)
        data["content_type"] = ContentType(data.get("content_type", "forum_post"))
        data["status"] = ContentStatus(data.get("status", "published"))
        if data.get("author"):
            data["author"] = Author.from_dict(data["author"])
        return cls(**data)


@dataclass
class SyncCursor:
    """同步游标"""
    node_id: str
    platform: str
    last_sync_time: float
    last_content_id: str = ""
    synced_count: int = 0


# ============================================================
# 内容存储
# ============================================================

class ContentStore:
    """
    内容存储

    内存存储 + 持久化（可扩展为 SQLite）
    """

    def __init__(self):
        # 内容存储
        self.contents: Dict[str, ContentItem] = {}

        # 索引
        self.by_platform: Dict[str, Set[str]] = defaultdict(set)  # platform -> content_ids
        self.by_author: Dict[str, Set[str]] = defaultdict(set)  # author_id -> content_ids
        self.by_type: Dict[ContentType, Set[str]] = defaultdict(set)

        # 同步游标
        self.sync_cursors: Dict[str, SyncCursor] = {}  # node_id:platform -> cursor

        # 订阅者（用于增量推送）
        self.subscribers: Dict[str, asyncio.Queue] = {}  # node_id -> queue

    def add(self, item: ContentItem) -> bool:
        """添加内容"""
        if item.content_id in self.contents:
            return False

        self.contents[item.content_id] = item
        self.by_platform[item.source_platform].add(item.content_id)
        if item.author:
            self.by_author[item.author.node_id].add(item.content_id)
        self.by_type[item.content_type].add(item.content_id)

        logger.info(f"Content added: {item.content_id} ({item.content_type.value})")
        return True

    def get(self, content_id: str) -> Optional[ContentItem]:
        """获取内容"""
        return self.contents.get(content_id)

    def delete(self, content_id: str) -> bool:
        """删除内容"""
        if content_id not in self.contents:
            return False

        item = self.contents[content_id]
        self.by_platform[item.source_platform].discard(content_id)
        if item.author:
            self.by_author[item.author.node_id].discard(content_id)
        self.by_type[item.content_type].discard(content_id)

        del self.contents[content_id]
        return True

    def list_by_platform(
        self,
        platform: str,
        status: ContentStatus = ContentStatus.PUBLISHED,
        limit: int = 50,
        offset: int = 0
    ) -> List[ContentItem]:
        """列出指定平台的内容"""
        content_ids = self.by_platform.get(platform, set())
        items = [
            self.contents[cid] for cid in content_ids
            if cid in self.contents and self.contents[cid].status == status
        ]
        items.sort(key=lambda x: x.published_at, reverse=True)
        return items[offset:offset + limit]

    def list_recent(
        self,
        limit: int = 50,
        content_types: List[ContentType] = None
    ) -> List[ContentItem]:
        """列出最近的内容"""
        items = list(self.contents.values())

        # 过滤类型
        if content_types:
            items = [i for i in items if i.content_type in content_types]

        # 过滤状态
        items = [i for i in items if i.status == ContentStatus.PUBLISHED]

        # 排序
        items.sort(key=lambda x: x.published_at, reverse=True)
        return items[:limit]

    def list_by_author(
        self,
        author_id: str,
        limit: int = 50
    ) -> List[ContentItem]:
        """列出指定作者的内容"""
        content_ids = self.by_author.get(author_id, set())
        items = [
            self.contents[cid] for cid in content_ids
            if cid in self.contents and self.contents[cid].status == ContentStatus.PUBLISHED
        ]
        items.sort(key=lambda x: x.published_at, reverse=True)
        return items[:limit]

    def search(
        self,
        query: str,
        limit: int = 50
    ) -> List[ContentItem]:
        """搜索内容"""
        query_lower = query.lower()
        results = []

        for item in self.contents.values():
            if item.status != ContentStatus.PUBLISHED:
                continue
            if (query_lower in item.title.lower() or
                query_lower in item.content.lower() or
                any(query_lower in tag.lower() for tag in item.tags)):
                results.append(item)

        results.sort(key=lambda x: x.published_at, reverse=True)
        return results[:limit]

    def get_incremental(
        self,
        node_id: str,
        platform: str,
        since: float
    ) -> List[ContentItem]:
        """获取增量内容"""
        items = []
        for item in self.contents.values():
            if (item.source_platform == platform and
                item.status == ContentStatus.PUBLISHED and
                item.published_at > since):
                items.append(item)

        items.sort(key=lambda x: x.published_at)
        return items

    def update_sync_cursor(self, cursor: SyncCursor):
        """更新同步游标"""
        key = f"{cursor.node_id}:{cursor.platform}"
        self.sync_cursors[key] = cursor

    def get_sync_cursor(self, node_id: str, platform: str) -> Optional[SyncCursor]:
        """获取同步游标"""
        key = f"{node_id}:{platform}"
        return self.sync_cursors.get(key)

    def vote(
        self,
        content_id: str,
        vote_type: str,  # "up" or "down"
        voter_id: str
    ) -> bool:
        """投票"""
        item = self.contents.get(content_id)
        if not item:
            return False

        if vote_type == "up":
            item.upvotes += 1
        elif vote_type == "down":
            item.downvotes += 1

        item.updated_at = time.time()
        return True

    def increment_reply_count(self, content_id: str):
        """增加回复数"""
        item = self.contents.get(content_id)
        if item:
            item.reply_count += 1
            item.updated_at = time.time()

    def set_ai_reply(
        self,
        content_id: str,
        ai_thought: str,
        ai_reply: str,
        ai_reply_id: str
    ):
        """设置 AI 回复"""
        item = self.contents.get(content_id)
        if item:
            item.ai_thought = ai_thought
            item.ai_reply = ai_reply
            item.ai_reply_id = ai_reply_id
            item.ai_processed = True
            item.updated_at = time.time()


# ============================================================
# Relay Blog & Forum Service
# ============================================================

class RelayBlogForumService:
    """
    中继服务器博客和论坛服务

    功能：
    1. 收集节点在内置平台发布的内容
    2. 用户可以在中继服务器端发布
    3. 节点可以拉取增量信息
    4. 节点可以随机对内容进行思考回复
    """

    _instance: Optional['RelayBlogForumService'] = None

    def __init__(self):
        self.store = ContentStore()
        self._running = False
        self._tasks: List[asyncio.Task] = []

    @classmethod
    def get_instance(cls) -> 'RelayBlogForumService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start(self):
        """启动服务"""
        self._running = True
        logger.info("RelayBlogForumService started")

    async def stop(self):
        """停止服务"""
        self._running = False
        for task in self._tasks:
            task.cancel()
        logger.info("RelayBlogForumService stopped")

    # ==================== 发布接口 ====================

    async def publish(
        self,
        title: str,
        content: str,
        content_type: ContentType,
        author_id: str,
        author_name: str,
        platform: str = "relay",
        tags: List[str] = None,
        author_avatar: str = ""
    ) -> ContentItem:
        """
        发布内容

        Args:
            title: 标题
            content: 内容 (HTML)
            content_type: 内容类型
            author_id: 作者ID
            author_name: 作者名称
            platform: 来源平台
            tags: 标签
            author_avatar: 头像 URL

        Returns:
            发布的内容项
        """
        author = Author(
            node_id=author_id,
            display_name=author_name,
            avatar_url=author_avatar
        )

        item = ContentItem(
            content_id=str(uuid.uuid4()),
            content_type=content_type,
            title=title,
            content=content,
            author=author,
            source_platform=platform,
            tags=tags or [],
            published_at=time.time()
        )

        self.store.add(item)

        # 通知订阅者
        await self._notify_subscribers(platform, item)

        return item

    async def publish_blog(
        self,
        title: str,
        content: str,
        author_id: str,
        author_name: str,
        tags: List[str] = None,
        **kwargs
    ) -> ContentItem:
        """发布博客"""
        return await self.publish(
            title=title,
            content=content,
            content_type=ContentType.BLOG_POST,
            author_id=author_id,
            author_name=author_name,
            platform=kwargs.get("platform", "relay"),
            tags=tags,
            **kwargs
        )

    async def publish_forum_post(
        self,
        title: str,
        content: str,
        author_id: str,
        author_name: str,
        tags: List[str] = None,
        **kwargs
    ) -> ContentItem:
        """发布论坛帖子"""
        return await self.publish(
            title=title,
            content=content,
            content_type=ContentType.FORUM_POST,
            author_id=author_id,
            author_name=author_name,
            platform=kwargs.get("platform", "relay"),
            tags=tags,
            **kwargs
        )

    async def publish_forum_reply(
        self,
        content_id: str,  # 被回复的帖子 ID
        content: str,
        author_id: str,
        author_name: str,
        **kwargs
    ) -> Optional[ContentItem]:
        """发布论坛回复"""
        parent = self.store.get(content_id)
        if not parent:
            logger.warning(f"Parent post not found: {content_id}")
            return None

        reply = await self.publish(
            title=f"Re: {parent.title[:50]}",
            content=content,
            content_type=ContentType.FORUM_REPLY,
            author_id=author_id,
            author_name=author_name,
            platform="relay",
            **kwargs
        )

        # 增加原帖回复数
        self.store.increment_reply_count(content_id)

        return reply

    # ==================== 查询接口 ====================

    async def get_content(self, content_id: str) -> Optional[ContentItem]:
        """获取内容"""
        return self.store.get(content_id)

    async def list_blogs(self, limit: int = 50, offset: int = 0) -> List[ContentItem]:
        """列出博客"""
        return self.store.list_by_platform("blog", limit=limit, offset=offset)

    async def list_forum_posts(self, limit: int = 50, offset: int = 0) -> List[ContentItem]:
        """列出论坛帖子"""
        return self.store.list_by_platform("forum", limit=limit, offset=offset)

    async def list_recent(self, limit: int = 50) -> List[ContentItem]:
        """列出最近内容"""
        return self.store.list_recent(limit=limit)

    async def list_by_author(self, author_id: str, limit: int = 50) -> List[ContentItem]:
        """列出作者的内容"""
        return self.store.list_by_author(author_id, limit=limit)

    async def search(self, query: str, limit: int = 50) -> List[ContentItem]:
        """搜索内容"""
        return self.store.search(query, limit=limit)

    # ==================== 增量同步 ====================

    async def sync_incremental(
        self,
        node_id: str,
        platform: str,
        since: float = 0
    ) -> Dict[str, Any]:
        """
        增量同步

        节点调用此接口获取增量内容

        Returns:
            {
                "items": [...],
                "cursor": {...},
                "has_more": bool
            }
        """
        items = self.store.get_incremental(node_id, platform, since)

        # 更新游标
        cursor = SyncCursor(
            node_id=node_id,
            platform=platform,
            last_sync_time=time.time(),
            synced_count=len(items)
        )
        if items:
            cursor.last_content_id = items[-1].content_id
        self.store.update_sync_cursor(cursor)

        return {
            "items": [item.to_dict() for item in items],
            "cursor": asdict(cursor),
            "has_more": len(items) >= 50  # 假设每页50条
        }

    async def get_for_poll(
        self,
        node_id: str,
        platforms: List[str] = None,
        limit: int = 10
    ) -> List[ContentItem]:
        """
        获取供节点轮询的内容

        节点定期调用此接口获取最新内容
        """
        platforms = platforms or ["blog", "forum", "relay"]
        all_items = []

        for platform in platforms:
            items = self.store.list_by_platform(platform, limit=limit)
            all_items.extend(items)

        # 按时间排序
        all_items.sort(key=lambda x: x.published_at, reverse=True)
        return all_items[:limit]

    # ==================== 投票和互动 ====================

    async def vote(
        self,
        content_id: str,
        vote_type: str,
        voter_id: str
    ) -> bool:
        """投票"""
        return self.store.vote(content_id, vote_type, voter_id)

    # ==================== AI 思考回复 ====================

    async def set_ai_reply(
        self,
        content_id: str,
        ai_thought: str,
        ai_reply: str,
        author_id: str = "ai_assistant",
        author_name: str = "AI Assistant"
    ) -> Optional[ContentItem]:
        """
        设置 AI 对内容的思考和回复

        节点可以调用此接口提交 AI 生成的内容
        """
        content = self.store.get(content_id)
        if not content:
            return None

        # 创建 AI 回复作为子内容
        ai_reply_item = await self.publish_forum_reply(
            content_id=content_id,
            content=f"<p>{ai_reply}</p>",
            author_id=author_id,
            author_name=author_name,
            platform="ai"
        )

        if ai_reply_item:
            self.store.set_ai_reply(
                content_id,
                ai_thought,
                ai_reply,
                ai_reply_item.content_id
            )

        return content

    async def get_random_unprocessed(
        self,
        platforms: List[str] = None,
        exclude_authors: List[str] = None
    ) -> Optional[ContentItem]:
        """
        获取随机一条未处理的内容

        节点可以调用此接口获取随机内容进行 AI 处理
        """
        platforms = platforms or ["blog", "forum", "relay"]
        candidates = []

        for platform in platforms:
            items = self.store.list_by_platform(platform)
            for item in items:
                if not item.ai_processed:
                    # 排除指定作者
                    if exclude_authors and item.author and item.author.node_id in exclude_authors:
                        continue
                    candidates.append(item)

        if not candidates:
            return None

        import random
        return random.choice(candidates)

    # ==================== 订阅机制 ====================

    async def subscribe(self, node_id: str) -> asyncio.Queue:
        """订阅内容更新"""
        queue = asyncio.Queue(maxsize=100)
        self.store.subscribers[node_id] = queue
        logger.info(f"Node {node_id} subscribed")
        return queue

    async def unsubscribe(self, node_id: str):
        """取消订阅"""
        if node_id in self.store.subscribers:
            del self.store.subscribers[node_id]
            logger.info(f"Node {node_id} unsubscribed")

    async def _notify_subscribers(self, platform: str, item: ContentItem):
        """通知订阅者"""
        for node_id, queue in self.store.subscribers.items():
            try:
                await queue.put({
                    "type": "new_content",
                    "platform": platform,
                    "content": item.to_dict()
                })
            except asyncio.QueueFull:
                pass

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self.store.contents)
        by_platform = {
            platform: len(ids)
            for platform, ids in self.store.by_platform.items()
        }
        by_type = {
            ct.value: len(ids)
            for ct, ids in self.store.by_type.items()
        }

        return {
            "total_contents": total,
            "by_platform": by_platform,
            "by_type": by_type,
            "published_count": len([
                c for c in self.store.contents.values()
                if c.status == ContentStatus.PUBLISHED
            ]),
            "ai_processed_count": len([
                c for c in self.store.contents.values()
                if c.ai_processed
            ])
        }


# ============================================================
# FastAPI 路由
# ============================================================

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/blogforum", tags=["Blog & Forum"])

service = RelayBlogForumService.get_instance()


class PublishRequest(BaseModel):
    title: str
    content: str
    author_id: str
    author_name: str
    platform: str = "relay"
    tags: List[str] = []
    author_avatar: str = ""


class ReplyRequest(BaseModel):
    content_id: str
    content: str
    author_id: str
    author_name: str


class VoteRequest(BaseModel):
    content_id: str
    vote_type: str  # "up" or "down"
    voter_id: str


class AiReplyRequest(BaseModel):
    content_id: str
    ai_thought: str
    ai_reply: str
    author_id: str = "ai_assistant"
    author_name: str = "AI Assistant"


# ---- 发布接口 ----

@router.post("/publish/blog")
async def publish_blog(req: PublishRequest) -> dict:
    """发布博客"""
    item = await service.publish_blog(
        title=req.title,
        content=req.content,
        author_id=req.author_id,
        author_name=req.author_name,
        tags=req.tags,
        platform=req.platform,
        author_avatar=req.author_avatar
    )
    return {"success": True, "content": item.to_dict()}


@router.post("/publish/forum")
async def publish_forum(req: PublishRequest) -> dict:
    """发布论坛帖子"""
    item = await service.publish_forum_post(
        title=req.title,
        content=req.content,
        author_id=req.author_id,
        author_name=req.author_name,
        tags=req.tags,
        platform=req.platform,
        author_avatar=req.author_avatar
    )
    return {"success": True, "content": item.to_dict()}


@router.post("/publish/reply")
async def publish_reply(req: ReplyRequest) -> dict:
    """发布回复"""
    item = await service.publish_forum_reply(
        content_id=req.content_id,
        content=req.content,
        author_id=req.author_id,
        author_name=req.author_name
    )
    if not item:
        raise HTTPException(status_code=404, detail="Parent post not found")
    return {"success": True, "content": item.to_dict()}


# ---- 查询接口 ----

@router.get("/content/{content_id}")
async def get_content(content_id: str) -> dict:
    """获取内容"""
    item = await service.get_content(content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    return {"content": item.to_dict()}


@router.get("/blogs")
async def list_blogs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> dict:
    """列出博客"""
    items = await service.list_blogs(limit=limit, offset=offset)
    return {"contents": [i.to_dict() for i in items], "count": len(items)}


@router.get("/forum/posts")
async def list_forum_posts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> dict:
    """列出论坛帖子"""
    items = await service.list_forum_posts(limit=limit, offset=offset)
    return {"contents": [i.to_dict() for i in items], "count": len(items)}


@router.get("/recent")
async def list_recent(limit: int = Query(50, ge=1, le=100)) -> dict:
    """列出最近内容"""
    items = await service.list_recent(limit=limit)
    return {"contents": [i.to_dict() for i in items], "count": len(items)}


@router.get("/search")
async def search_content(q: str = Query(...), limit: int = Query(50, ge=1, le=100)) -> dict:
    """搜索内容"""
    items = await service.search(q, limit=limit)
    return {"contents": [i.to_dict() for i in items], "count": len(items), "query": q}


# ---- 增量同步 ----

@router.get("/sync/{node_id}")
async def sync_incremental(
    node_id: str,
    platform: str = Query(...),
    since: float = Query(0, ge=0)
) -> dict:
    """增量同步"""
    result = await service.sync_incremental(node_id, platform, since)
    return result


@router.get("/poll/{node_id}")
async def poll_for_updates(
    node_id: str,
    platforms: str = Query("blog,forum,relay"),
    limit: int = Query(10, ge=1, le=50)
) -> dict:
    """轮询获取更新"""
    platform_list = platforms.split(",")
    items = await service.get_for_poll(node_id, platform_list, limit)
    return {"contents": [i.to_dict() for i in items], "count": len(items)}


# ---- AI 处理 ----

@router.get("/unprocessed")
async def get_random_unprocessed(
    platforms: str = Query("blog,forum,relay"),
    exclude_authors: str = Query("")
) -> dict:
    """获取随机未处理内容"""
    platform_list = platforms.split(",")
    exclude_list = exclude_authors.split(",") if exclude_authors else []
    item = await service.get_random_unprocessed(platform_list, exclude_list)
    if not item:
        return {"content": None, "message": "No unprocessed content found"}
    return {"content": item.to_dict()}


@router.post("/ai/reply")
async def set_ai_reply(req: AiReplyRequest) -> dict:
    """提交 AI 回复"""
    content = await service.set_ai_reply(
        content_id=req.content_id,
        ai_thought=req.ai_thought,
        ai_reply=req.ai_reply,
        author_id=req.author_id,
        author_name=req.author_name
    )
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return {"success": True, "content": content.to_dict()}


# ---- 互动 ----

@router.post("/vote")
async def vote(req: VoteRequest) -> dict:
    """投票"""
    success = await service.vote(
        content_id=req.content_id,
        vote_type=req.vote_type,
        voter_id=req.voter_id
    )
    return {"success": success}


# ---- 统计 ----

@router.get("/stats")
async def get_stats() -> dict:
    """获取统计"""
    return service.get_stats()
