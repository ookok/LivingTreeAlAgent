"""
去中心化伪域名 - 内容服务层 (生命之树版本)
提供博客、论坛、文件等内容服务

功能:
- 博客文章管理
- 论坛帖子聚合
- 云盘文件服务
- 动态内容生成
"""

import asyncio
import time
import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field

from .models import DomainType, ContentSource, WebContent

logger = logging.getLogger(__name__)


@dataclass
class BlogPost:
    """博客文章"""
    post_id: str
    title: str
    content: str              # Markdown 或 HTML
    author: str
    author_node_id: str
    created_at: float
    updated_at: float
    tags: List[str] = field(default_factory=list)
    views: int = 0
    comments: int = 0
    likes: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.post_id,
            "title": self.title,
            "content": self.content,
            "author": self.author,
            "author_node_id": self.author_node_id,
            "date": time.strftime("%Y-%m-%d", time.localtime(self.created_at)),
            "tags": self.tags,
            "views": self.views,
            "comments": self.comments,
            "likes": self.likes,
            "excerpt": self.content[:200] + "..." if len(self.content) > 200 else self.content
        }


@dataclass
class ForumTopic:
    """论坛话题"""
    topic_id: str
    name: str
    description: str
    icon: str
    post_count: int
    member_count: int
    created_at: float


class ContentService:
    """
    内容服务 (生命之树版本)

    提供各类内容的服务接口
    """

    def __init__(self):
        # 博客存储 (本地 SQLite 回调)
        self._blog_storage_callback: Optional[Callable] = None

        # 论坛存储回调
        self._forum_storage_callback: Optional[Callable] = None

        # 云盘存储回调
        self._cloud_storage_callback: Optional[Callable] = None

        # AI 写作回调
        self._ai_writer_callback: Optional[Callable] = None

        # 本地博客文章 (内存, 演示用)
        self._local_posts: Dict[str, BlogPost] = {}
        self._init_demo_posts()

    def set_blog_storage_callback(self, callback: Callable):
        """设置博客存储回调"""
        self._blog_storage_callback = callback

    def set_forum_storage_callback(self, callback: Callable):
        """设置论坛存储回调"""
        self._forum_storage_callback = callback

    def set_cloud_storage_callback(self, callback: Callable):
        """设置云盘存储回调"""
        self._cloud_storage_callback = callback

    def set_ai_writer_callback(self, callback: Callable):
        """设置 AI 写作回调"""
        self._ai_writer_callback = callback

    def _init_demo_posts(self):
        """初始化演示文章"""
        demo_posts = [
            BlogPost(
                post_id="post_001",
                title="欢迎来到生命之树",
                content="""🌳 欢迎来到 Living Tree AI！

在这个系统中, 您可以:
- 🌿 使用 .tree 伪域名发布博客
- 🌲 创建去中心化论坛
- 🔒 端到端加密通信
- 🌱 无需服务器, 无需备案

所有内容都存储在节点网络中, 如同大树的根系互联, 抗审查, 抗封锁。

**根系相连，智慧生长。**
""",
                author="System",
                author_node_id="living",
                created_at=time.time() - 86400,
                updated_at=time.time() - 86400,
                tags=["welcome", "tree", "living"]
            ),
            BlogPost(
                post_id="post_002",
                title="生命之树命名系统",
                content="""🌳 什么是 .tree 伪域名？

## 核心理念

生命之树是一个去中心化的命名系统, 用自然的隐喻替代冷冰冰的技术术语.

## 顶级域名

| 后缀 | 含义 | 示例 |
|------|------|------|
| .tree | 个人主页/商店 | shop.8848993321.tree |
| .leaf | 轻量服务/邮箱 | @8848993321.leaf |
| .root | 核心系统/路由 | registry.living.root |
| .wood | 社区/论坛 | forum.8855.wood |

## 命名哲学

- 🌳 **.tree**: 生命之树的主干, 代表个人身份
- 🍃 **.leaf**: 轻量的叶子, 代表便捷的服务
- 🌱 **.root**: 深埋的根, 代表核心系统
- 🌲 **.wood**: 茂密的森林, 代表社区协作

**根系相连，智慧生长。**
""",
                author="Tech Writer",
                author_node_id="living",
                created_at=time.time() - 43200,
                updated_at=time.time() - 43200,
                tags=["tree", "naming", "philosophy"]
            ),
            BlogPost(
                post_id="post_003",
                title="智能写作助手使用指南",
                content="""🤖 我们的系统集成了强大的 AI 写作助手.

## 功能

### 自动草稿生成
输入主题, AI 为您生成论点、论据和参考资料.

### 内容优化
AI 分析您的文章, 提供优化建议.

### 讨论增强
在论坛中, AI 可以:
- 🌿 生成回复摘要
- 🌲 分析讨论质量
- 🍃 提供反驳建议

## 使用方法

1. 在创作面板中选择"智能写作"
2. 输入您的主题或草稿
3. AI 将为您生成建议

让我们一起构建更好的去中心化互联网!
""",
                author="AI Assistant",
                author_node_id="living",
                created_at=time.time() - 21600,
                updated_at=time.time() - 21600,
                tags=["ai", "writing", "guide"]
            )
        ]

        for post in demo_posts:
            self._local_posts[post.post_id] = post

    async def get_content(self, content_type: str, action: str, params: Dict[str, Any]) -> Any:
        """
        获取内容

        Args:
            content_type: 内容类型 (blog/forum/file)
            action: 操作 (list/get/create)
            params: 参数

        Returns:
            内容数据
        """
        if content_type == "blog":
            return await self._get_blog_content(action, params)
        elif content_type == "forum":
            return await self._get_forum_content(action, params)
        elif content_type == "file":
            return await self._get_file_content(action, params)
        else:
            return None

    async def _get_blog_content(self, action: str, params: Dict[str, Any]) -> Any:
        """获取博客内容"""
        node_id = params.get("node_id", "")

        if action == "list":
            # 获取文章列表
            posts = list(self._local_posts.values())
            posts.sort(key=lambda p: p.created_at, reverse=True)
            return [p.to_dict() for p in posts]

        elif action == "get":
            # 获取单篇文章
            post_id = params.get("post_id", "")
            post = self._local_posts.get(post_id)
            if post:
                post.views += 1
            return post.to_dict() if post else None

        elif action == "create":
            # 创建文章
            post = BlogPost(
                post_id=f"post_{int(time.time())}",
                title=params.get("title", "Untitled"),
                content=params.get("content", ""),
                author=params.get("author", "Anonymous"),
                author_node_id=node_id,
                created_at=time.time(),
                updated_at=time.time(),
                tags=params.get("tags", [])
            )
            self._local_posts[post.post_id] = post
            return post.to_dict()

        return None

    async def _get_forum_content(self, action: str, params: Dict[str, Any]) -> Any:
        """获取论坛内容"""
        if action == "list_topics":
            # 获取话题列表
            return [
                {
                    "id": "topic_general",
                    "name": "综合讨论",
                    "icon": "📋",
                    "description": "随便聊聊",
                    "posts": 42,
                    "members": 15
                },
                {
                    "id": "topic_tech",
                    "name": "技术交流",
                    "icon": "💻",
                    "description": "编程与技术",
                    "posts": 128,
                    "members": 28
                },
                {
                    "id": "topic_ai",
                    "name": "AI & 具身智能",
                    "icon": "🤖",
                    "description": "人工智能前沿",
                    "posts": 89,
                    "members": 34
                },
                {
                    "id": "topic_creative",
                    "name": "创意写作",
                    "icon": "✍️",
                    "description": "小说与创作",
                    "posts": 56,
                    "members": 21
                }
            ]

        elif action == "topic_posts":
            # 获取话题下的帖子
            topic_id = params.get("topic_id", "")
            # 模拟数据
            return [
                {
                    "id": f"post_{topic_id}_1",
                    "title": f"{topic_id} 主题下的第一个帖子",
                    "author": "User001",
                    "upvotes": 12,
                    "replies": 5,
                    "excerpt": "这是帖子的摘要内容..."
                },
                {
                    "id": f"post_{topic_id}_2",
                    "title": f"{topic_id} 主题下的第二个帖子",
                    "author": "User002",
                    "upvotes": 8,
                    "replies": 3,
                    "excerpt": "另一个帖子的内容..."
                }
            ]

        elif action == "get_post":
            # 获取单个帖子
            post_id = params.get("post_id", "")
            return {
                "id": post_id,
                "title": "帖子标题",
                "author": "Author",
                "content": "帖子完整内容...",
                "created_at": time.time()
            }

        return None

    async def _get_file_content(self, action: str, params: Dict[str, Any]) -> Any:
        """获取文件内容"""
        if action == "list":
            # 文件列表
            return [
                {"name": "documents", "type": "folder", "size": 0},
                {"name": "images", "type": "folder", "size": 0},
                {"name": "readme.md", "type": "file", "size": 1024}
            ]

        elif action == "get":
            # 获取文件
            file_path = params.get("path", "")
            return {
                "path": file_path,
                "content": "# File Content\n\nThis is a demo file.",
                "type": "markdown"
            }

        return None

    # ==================== AI 写作 ====================

    async def generate_blog_content(self, topic: str, style: str = "informative") -> str:
        """AI 生成博客内容"""
        if self._ai_writer_callback:
            try:
                prompt = f"请为以下主题写一篇博客文章 (风格: {style}):\n\n主题: {topic}\n\n要求:\n- 至少 500 字\n- 结构清晰, 有小标题\n- 包含实际案例或数据"
                result = await self._ai_writer_callback(prompt)
                return result
            except Exception as e:
                logger.error(f"AI writing error: {e}")

        # 回退
        return f"""# {topic}

这是一篇关于 {topic} 的文章。

## 概述

{topic} 是一个非常重要的话题...

## 详细内容

待补充...

---
*本文由 AI 辅助生成*
"""

    async def summarize_content(self, content: str, max_length: int = 200) -> str:
        """AI 摘要内容"""
        if len(content) <= max_length:
            return content

        if self._ai_writer_callback:
            try:
                prompt = f"请将以下内容摘要为 {max_length} 字:\n\n{content}"
                result = await self._ai_writer_callback(prompt)
                return result[:max_length] + "..." if len(result) > max_length else result
            except Exception as e:
                logger.error(f"AI summarization error: {e}")

        return content[:max_length] + "..."


class ContentServiceHub:
    """
    内容服务中枢

    整合多个内容服务, 提供统一接口
    """

    def __init__(self):
        self.content_service = ContentService()

        # 关联其他服务
        self._forum_hub_callback: Optional[Callable] = None
        self._cloud_storage_callback: Optional[Callable] = None

    def set_forum_hub_callback(self, callback: Callable):
        """设置论坛回调"""
        self._forum_hub_callback = callback
        self.content_service.set_forum_storage_callback(callback)

    def set_cloud_storage_callback(self, callback: Callable):
        """设置云盘回调"""
        self._cloud_storage_callback = callback
        self.content_service.set_cloud_storage_callback(callback)

    def set_ai_writer_callback(self, callback: Callable):
        """设置 AI 写作回调"""
        self.content_service.set_ai_writer_callback(callback)

    async def get_content(self, content_type: str, action: str, params: Dict[str, Any]) -> Any:
        """获取内容"""
        return await self.content_service.get_content(content_type, action, params)

    async def generate_content(self, content_type: str, topic: str, **kwargs) -> str:
        """生成内容"""
        if content_type == "blog":
            return await self.content_service.generate_blog_content(topic, **kwargs)
        return ""


def create_content_service() -> ContentService:
    """创建内容服务"""
    return ContentService()


def create_content_service_hub() -> ContentServiceHub:
    """创建内容服务中枢"""
    return ContentServiceHub()
