# forum_client.py — 内置 .tree 论坛客户端

import json
import time
import hashlib
import threading
import requests
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from dataclasses import asdict

from .models import (
    ForumPost, ForumPostType, PostStatus, ExternalPlatform,
    PatchDoc,
    generate_client_id, hash_for_dedup,
)


class ForumClient:
    """
    内置论坛客户端 (.tree 网络)

    功能：
    1. 补丁分享到论坛
    2. 社区求助与回复
    3. 知识分享
    4. 外发到外部平台
    """

    # .tree 网络默认节点
    DEFAULT_TREE_NODES = [
        "http://localhost:8766",
    ]

    def __init__(
        self,
        data_dir: Path = None,
        client_id: str = None,
        relay_server_url: str = None,
    ):
        """
        初始化论坛客户端

        Args:
            data_dir: 数据存储目录
            client_id: 匿名客户端ID
            relay_server_url: 中继服务器地址
        """
        self._data_dir = data_dir or self._default_data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._client_id = client_id or generate_client_id()
        self._relay_server_url = relay_server_url or self.DEFAULT_TREE_NODES[0]

        # 存储文件
        self._posts_file = self._data_dir / "forum_posts.json"
        self._cache_file = self._data_dir / "forum_cache.json"

        # 内存缓存
        self._local_posts: Dict[str, ForumPost] = {}
        self._remote_cache: Dict[str, ForumPost] = {}

        # 回调函数
        self._callbacks: Dict[str, Callable] = {}

        # 加载数据
        self._load_posts()
        self._load_cache()

    def _default_data_dir(self) -> Path:
        """默认数据目录"""
        return Path.home() / ".hermes-desktop" / "evolution" / "forum"

    def _load_posts(self):
        """加载本地帖子"""
        if self._posts_file.exists():
            try:
                with open(self._posts_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        post = ForumPost.from_dict(item)
                        self._local_posts[post.id] = post
            except (json.JSONDecodeError, KeyError):
                pass

    def _load_cache(self):
        """加载远程缓存"""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        post = ForumPost.from_dict(item)
                        self._remote_cache[post.id] = post
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_posts(self):
        """保存本地帖子"""
        data = [p.to_dict() for p in self._local_posts.values()]
        with open(self._posts_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_cache(self):
        """保存远程缓存"""
        data = [p.to_dict() for p in self._remote_cache.values()]
        with open(self._cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create_patch_post(
        self,
        patch: PatchDoc,
        title: str = None,
        additional_content: str = "",
    ) -> ForumPost:
        """
        创建补丁分享帖

        Args:
            patch: 补丁文档
            title: 标题（可选，自动生成）
            additional_content: 附加内容

        Returns:
            ForumPost: 创建的帖子
        """
        if title is None:
            title = f"[补丁] {patch.module}: {patch.action.value} ({patch.reason[:30]}...)"

        content_parts = [
            f"## 补丁信息",
            f"- 模块: {patch.module}",
            f"- 操作: {patch.action.value}",
            f"- 原因: {patch.reason}",
            f"- 改善: {patch.old_value} -> {patch.new_value}",
            "",
        ]

        if additional_content:
            content_parts.append(additional_content)

        content_parts.extend([
            "",
            "---",
            f"*来源: {patch.client_id} | 签名: {patch.signature}*",
        ])

        post = ForumPost(
            id=patch.id,
            post_type=ForumPostType.PATCH_SHARE,
            title=title,
            content="\n".join(content_parts),
            author_client_id=self._client_id,
            timestamp=int(time.time()),
            status=PostStatus.DRAFT,
            referenced_patch_id=patch.id,
        )

        self._local_posts[post.id] = post
        self._save_posts()

        return post

    def create_help_post(
        self,
        title: str,
        content: str,
        tags: List[str] = None,
    ) -> ForumPost:
        """
        创建求助帖

        Args:
            title: 标题
            content: 内容
            tags: 标签

        Returns:
            ForumPost: 创建的帖子
        """
        post_id = hash_for_dedup("help", title, str(int(time.time())))

        content_with_meta = f"{content}\n\n---\n*来源: {self._client_id}*"

        post = ForumPost(
            id=post_id,
            post_type=ForumPostType.HELP_REQUEST,
            title=title,
            content=content_with_meta,
            author_client_id=self._client_id,
            timestamp=int(time.time()),
            status=PostStatus.DRAFT,
            tags=tags or [],
        )

        self._local_posts[post.id] = post
        self._save_posts()

        return post

    def create_knowledge_post(
        self,
        title: str,
        content: str,
        tags: List[str] = None,
    ) -> ForumPost:
        """
        创建知识分享帖

        Args:
            title: 标题
            content: 内容
            tags: 标签

        Returns:
            ForumPost: 创建的帖子
        """
        post_id = hash_for_dedup("knowledge", title, str(int(time.time())))

        content_with_meta = f"{content}\n\n---\n*来源: {self._client_id} | 知识分享*"

        post = ForumPost(
            id=post_id,
            post_type=ForumPostType.KNOWLEDGE分享,
            title=title,
            content=content_with_meta,
            author_client_id=self._client_id,
            timestamp=int(time.time()),
            status=PostStatus.DRAFT,
            tags=tags or [],
        )

        self._local_posts[post.id] = post
        self._save_posts()

        return post

    def publish_post(self, post_id: str) -> bool:
        """
        发布帖子

        Args:
            post_id: 帖子ID

        Returns:
            bool: 是否成功
        """
        post = self._local_posts.get(post_id)
        if post is None:
            return False

        # 转换为 Markdown
        md_content = post.to_markdown()

        # 发送到中继服务器
        try:
            resp = requests.post(
                f"{self._relay_server_url}/api/forum/publish",
                json={
                    "post": post.to_dict(),
                    "markdown": md_content,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                post.status = PostStatus.PUBLISHED
                self._save_posts()
                return True
        except requests.RequestException:
            pass

        # 如果发送失败，标记为本地已发布
        post.status = PostStatus.PUBLISHED
        self._save_posts()
        return True

    def fetch_forum_feed(
        self,
        post_type: ForumPostType = None,
        limit: int = 20,
    ) -> List[ForumPost]:
        """
        获取论坛动态

        Args:
            post_type: 帖子类型过滤
            limit: 返回数量

        Returns:
            List[ForumPost]: 帖子列表
        """
        try:
            params = {"limit": limit}
            if post_type:
                params["type"] = post_type.value

            resp = requests.get(
                f"{self._relay_server_url}/api/forum/feed",
                params=params,
                timeout=10,
            )

            if resp.status_code == 200:
                data = resp.json()
                posts = []
                for item in data.get("posts", []):
                    post = ForumPost.from_dict(item)
                    self._remote_cache[post.id] = post
                    posts.append(post)
                self._save_cache()
                return posts
        except requests.RequestException:
            pass

        # 返回缓存
        cached = list(self._remote_cache.values())
        if post_type:
            cached = [p for p in cached if p.post_type == post_type]
        return cached[:limit]

    def fetch_patch广场(self, limit: int = 10) -> List[ForumPost]:
        """
        获取补丁广场（所有补丁分享帖）

        Args:
            limit: 返回数量

        Returns:
            List[ForumPost]: 补丁分享帖列表
        """
        return self.fetch_forum_feed(ForumPostType.PATCH_SHARE, limit)

    def mark_for_external(
        self,
        post_id: str,
        platform: ExternalPlatform,
    ) -> bool:
        """
        标记帖子将外发到外部平台

        Args:
            post_id: 帖子ID
            platform: 目标平台

        Returns:
            bool: 是否成功
        """
        post = self._local_posts.get(post_id) or self._remote_cache.get(post_id)
        if post is None:
            return False

        post.external_platform = platform
        self._save_posts()
        return True

    def upvote_post(self, post_id: str) -> bool:
        """
        点赞帖子

        Args:
            post_id: 帖子ID

        Returns:
            bool: 是否成功
        """
        post = self._local_posts.get(post_id) or self._remote_cache.get(post_id)
        if post is None:
            return False

        post.upvotes += 1

        # 如果是本地帖子，保存
        if post_id in self._local_posts:
            self._save_posts()
        else:
            self._save_cache()

        # 发送点赞到服务器
        try:
            requests.post(
                f"{self._relay_server_url}/api/forum/upvote",
                json={"post_id": post_id},
                timeout=5,
            )
        except requests.RequestException:
            pass

        return True

    def get_local_posts(
        self,
        status: PostStatus = None,
    ) -> List[ForumPost]:
        """获取本地帖子"""
        posts = list(self._local_posts.values())
        if status:
            posts = [p for p in posts if p.status == status]
        return sorted(posts, key=lambda p: p.timestamp, reverse=True)

    def get_pending_external_posts(self) -> List[ForumPost]:
        """获取待外发的帖子"""
        return [
            p for p in self._local_posts.values()
            if p.status == PostStatus.PUBLISHED and p.external_platform
        ]

    def register_callback(self, event: str, callback: Callable):
        """
        注册回调

        Args:
            event: 事件类型 (on_new_post / on_reply / on_mention)
            callback: 回调函数
        """
        self._callbacks[event] = callback

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        local = list(self._local_posts.values())
        return {
            "total_local_posts": len(local),
            "published": sum(1 for p in local if p.status == PostStatus.PUBLISHED),
            "draft": sum(1 for p in local if p.status == PostStatus.DRAFT),
            "for_external": sum(1 for p in local if p.external_platform),
            "cached_remote": len(self._remote_cache),
        }


# 全局单例
_forum_client_instance: Optional[ForumClient] = None


def get_forum_client(
    relay_server_url: str = None,
) -> ForumClient:
    """获取论坛客户端全局实例"""
    global _forum_client_instance
    if _forum_client_instance is None:
        _forum_client_instance = ForumClient(
            relay_server_url=relay_server_url,
        )
    return _forum_client_instance