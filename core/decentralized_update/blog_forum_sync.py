# blog_forum_sync.py — 博客论坛同步模块
# ============================================================================
#
# 功能:
#   1. 同步更新内容到内置博客平台
#   2. 同步简要说明到论坛
#   3. 管理博客和论坛的 URL 映射
#   4. 自动生成适合不同平台的内容格式
#
# ============================================================================

import json
import asyncio
import aiohttp
import hashlib
import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
from enum import Enum

# ============================================================================
# 配置
# ============================================================================

BLOG_API_BASE = "https://blog.mogoo.com/api"
FORUM_API_BASE = "https://forum.mogoo.com/api"

# ============================================================================
# 数据结构
# ============================================================================

class SyncStatus(Enum):
    """同步状态"""
    PENDING = "pending"
    SYNCING = "syncing"
    SUCCESS = "success"
    FAILED = "failed"

@dataclass
class BlogPost:
    """博客文章"""
    title: str
    content: str
    category: str = "product-update"
    tags: List[str] = field(default_factory=list)
    author: str = "system"
    url: str = ""
    post_id: str = ""
    published_at: str = ""

@dataclass
class ForumTopic:
    """论坛主题"""
    title: str
    content: str
    category: str = "update-announcements"
    tags: List[str] = field(default_factory=list)
    author: str = "system"
    url: str = ""
    topic_id: str = ""
    is_pinned: bool = False
    published_at: str = ""

@dataclass
class SyncRecord:
    """同步记录"""
    version: str
    blog_post: Optional[BlogPost] = None
    forum_topic: Optional[ForumTopic] = None
    sync_status: SyncStatus = SyncStatus.PENDING
    error_message: str = ""
    synced_at: str = ""

# ============================================================================
# 博客论坛同步器
# ============================================================================

class BlogForumSync:
    """
    博客论坛同步器

    功能:
    1. 同步详细更新内容到博客
    2. 同步简要公告到论坛
    3. 管理同步记录和 URL 映射
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._records_dir = Path.home() / ".hermes-desktop" / "blog_forum_sync"
        self._records_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # 核心功能
    # --------------------------------------------------------------------------

    async def sync_update(
        self,
        version: str,
        changelog: List[Dict],
        blog_content: str,
        forum_content: str,
        tags: List[str] = None,
        author: str = "system"
    ) -> SyncRecord:
        """
        同步更新到博客和论坛

        Args:
            version: 版本号
            changelog: 变更日志列表
            blog_content: 博客完整内容
            forum_content: 论坛简要内容
            tags: 标签列表
            author: 作者

        Returns:
            SyncRecord: 同步记录
        """
        record = SyncRecord(version=version)
        tags = tags or ["hermes-desktop", f"v{version}"]

        try:
            record.sync_status = SyncStatus.SYNCING

            # 并行同步博客和论坛
            blog_task = self._sync_blog(
                title=f"Hermes Desktop v{version} 更新说明",
                content=blog_content,
                tags=tags,
                author=author
            )

            forum_task = self._sync_forum(
                title=f"Hermes Desktop v{version} 更新公告",
                content=forum_content,
                tags=tags,
                author=author
            )

            blog_result, forum_result = await asyncio.gather(
                blog_task, forum_task, return_exceptions=True
            )

            # 处理博客结果
            if isinstance(blog_result, Exception):
                record.error_message += f"博客: {blog_result}; "
            else:
                record.blog_post = blog_result

            # 处理论坛结果
            if isinstance(forum_result, Exception):
                record.error_message += f"论坛: {forum_result}; "
            else:
                record.forum_topic = forum_result

            record.sync_status = SyncStatus.SUCCESS if not record.error_message else SyncStatus.FAILED
            record.synced_at = datetime.datetime.now().isoformat()

        except Exception as e:
            record.sync_status = SyncStatus.FAILED
            record.error_message = str(e)

        # 保存同步记录
        await self._save_record(record)

        return record

    async def sync_blog_only(
        self,
        version: str,
        title: str,
        content: str,
        category: str = "product-update",
        tags: List[str] = None,
        author: str = "system"
    ) -> BlogPost:
        """
        仅同步到博客

        Args:
            version: 版本号
            title: 标题
            content: 内容
            category: 分类
            tags: 标签
            author: 作者

        Returns:
            BlogPost: 博客文章
        """
        tags = tags or ["hermes-desktop", f"v{version}"]

        post = await self._sync_blog(
            title=title,
            content=content,
            tags=tags,
            author=author,
            category=category
        )

        # 保存记录
        record = SyncRecord(
            version=version,
            blog_post=post,
            sync_status=SyncStatus.SUCCESS,
            synced_at=datetime.datetime.now().isoformat()
        )
        await self._save_record(record)

        return post

    async def sync_forum_only(
        self,
        version: str,
        title: str,
        content: str,
        category: str = "update-announcements",
        tags: List[str] = None,
        author: str = "system",
        is_pinned: bool = False
    ) -> ForumTopic:
        """
        仅同步到论坛

        Args:
            version: 版本号
            title: 标题
            content: 内容
            category: 分类
            tags: 标签
            author: 作者
            is_pinned: 是否置顶

        Returns:
            ForumTopic: 论坛主题
        """
        tags = tags or ["hermes-desktop", f"v{version}"]

        topic = await self._sync_forum(
            title=title,
            content=content,
            tags=tags,
            author=author,
            category=category,
            is_pinned=is_pinned
        )

        # 保存记录
        record = SyncRecord(
            version=version,
            forum_topic=topic,
            sync_status=SyncStatus.SUCCESS,
            synced_at=datetime.datetime.now().isoformat()
        )
        await self._save_record(record)

        return topic

    # --------------------------------------------------------------------------
    # 博客同步
    # --------------------------------------------------------------------------

    async def _sync_blog(
        self,
        title: str,
        content: str,
        tags: List[str],
        author: str,
        category: str = "product-update"
    ) -> BlogPost:
        """同步到博客"""
        payload = {
            "title": title,
            "content": content,
            "category": category,
            "tags": tags,
            "author": author,
            "published_at": datetime.datetime.now().isoformat()
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BLOG_API_BASE}/posts",
                json=payload,
                headers=self._get_headers()
            ) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    return BlogPost(
                        title=title,
                        content=content,
                        category=category,
                        tags=tags,
                        author=author,
                        url=result.get("url", ""),
                        post_id=result.get("id", ""),
                        published_at=datetime.datetime.now().isoformat()
                    )
                else:
                    text = await response.text()
                    raise Exception(f"博客 API 错误 {response.status}: {text}")

    # --------------------------------------------------------------------------
    # 论坛同步
    # --------------------------------------------------------------------------

    async def _sync_forum(
        self,
        title: str,
        content: str,
        tags: List[str],
        author: str,
        category: str = "update-announcements",
        is_pinned: bool = False
    ) -> ForumTopic:
        """同步到论坛"""
        payload = {
            "title": title,
            "content": content,
            "category": category,
            "tags": tags,
            "author": author,
            "published_at": datetime.datetime.now().isoformat(),
            "is_pinned": is_pinned
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{FORUM_API_BASE}/topics",
                json=payload,
                headers=self._get_headers()
            ) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    return ForumTopic(
                        title=title,
                        content=content,
                        category=category,
                        tags=tags,
                        author=author,
                        url=result.get("url", ""),
                        topic_id=result.get("id", ""),
                        is_pinned=is_pinned,
                        published_at=datetime.datetime.now().isoformat()
                    )
                else:
                    text = await response.text()
                    raise Exception(f"论坛 API 错误 {response.status}: {text}")

    # --------------------------------------------------------------------------
    # 辅助方法
    # --------------------------------------------------------------------------

    def _get_headers(self) -> Dict:
        """获取 API 请求头"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _save_record(self, record: SyncRecord):
        """保存同步记录"""
        record_file = self._records_dir / f"sync-{record.version}.json"

        data = {
            "version": record.version,
            "blog_post": record.blog_post.__dict__ if record.blog_post else None,
            "forum_topic": record.forum_topic.__dict__ if record.forum_topic else None,
            "sync_status": record.sync_status.value,
            "error_message": record.error_message,
            "synced_at": record.synced_at
        }

        with open(record_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def get_sync_record(self, version: str) -> Optional[SyncRecord]:
        """获取同步记录"""
        record_file = self._records_dir / f"sync-{version}.json"

        if not record_file.exists():
            return None

        with open(record_file, encoding="utf-8") as f:
            data = json.load(f)

        blog_post = None
        if data.get("blog_post"):
            blog_post = BlogPost(**data["blog_post"])

        forum_topic = None
        if data.get("forum_topic"):
            forum_topic = ForumTopic(**data["forum_topic"])

        return SyncRecord(
            version=data["version"],
            blog_post=blog_post,
            forum_topic=forum_topic,
            sync_status=SyncStatus(data["sync_status"]),
            error_message=data.get("error_message", ""),
            synced_at=data.get("synced_at", "")
        )

    async def list_sync_records(self) -> List[SyncRecord]:
        """列出所有同步记录"""
        records = []

        for record_file in self._records_dir.glob("sync-*.json"):
            try:
                with open(record_file, encoding="utf-8") as f:
                    data = json.load(f)

                blog_post = None
                if data.get("blog_post"):
                    blog_post = BlogPost(**data["blog_post"])

                forum_topic = None
                if data.get("forum_topic"):
                    forum_topic = ForumTopic(**data["forum_topic"])

                records.append(SyncRecord(
                    version=data["version"],
                    blog_post=blog_post,
                    forum_topic=forum_topic,
                    sync_status=SyncStatus(data["sync_status"]),
                    error_message=data.get("error_message", ""),
                    synced_at=data.get("synced_at", "")
                ))
            except Exception:
                continue

        return sorted(records, key=lambda r: r.synced_at, reverse=True)

    def get_blog_url(self, version: str) -> str:
        """获取博客 URL"""
        return f"https://blog.mogoo.com/hermes-update/{version}"

    def get_forum_url(self, version: str) -> str:
        """获取论坛 URL"""
        return f"https://forum.mogoo.com/topic/hermes-{version}"

# ============================================================================
# 全局访问器
# ============================================================================

_sync_instance: Optional[BlogForumSync] = None

def get_blog_forum_sync() -> BlogForumSync:
    """获取全局 BlogForumSync 实例"""
    global _sync_instance
    if _sync_instance is None:
        _sync_instance = BlogForumSync()
    return _sync_instance

# ============================================================================
# 内容生成工具
# ============================================================================

def generate_blog_content(
    version: str,
    from_version: str,
    changelog: List[Dict],
    source_info: Dict = None,
    breaking_changes: List[str] = None,
    known_issues: List[str] = None
) -> str:
    """
    生成博客详细内容

    Args:
        version: 版本号
        from_version: 原版本
        changelog: 变更日志
        source_info: 来源信息
        breaking_changes: Breaking Changes
        known_issues: 已知问题

    Returns:
        str: Markdown 格式的博客内容
    """
    lines = [
        f"# Hermes Desktop v{version} 更新说明",
        "",
        f"**发布版本:** {version}",
        f"**发布日期:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**更新类型:** {determine_update_type(version)}",
        "",
        "---",
        "",
        "## 📋 更新概要",
        "",
        generate_summary_table(changelog),
        "",
        "---",
        "",
        "## 📝 详细更新内容",
        ""
    ]

    # 按类别分组
    categorized = categorize_changelog(changelog)

    for category, entries in categorized.items():
        if entries:
            lines.append(f"### {category}")
            lines.append("")
            for entry in entries:
                icon = get_severity_icon(entry.get("severity", "normal"))
                lines.append(f"{icon} **{entry.get('title', '')}**")
                lines.append(f"> {entry.get('description', '')}")
                lines.append("")

    # Breaking Changes
    if breaking_changes:
        lines.extend([
            "---",
            "",
            "## ⚠️ Breaking Changes",
            ""
        ])
        for change in breaking_changes:
            lines.append(f"- {change}")
        lines.append("")

    # 已知问题
    if known_issues:
        lines.extend([
            "---",
            "",
            "## 🔍 已知问题",
            ""
        ])
        for issue in known_issues:
            lines.append(f"- {issue}")
        lines.append("")

    # 内部信息
    if source_info:
        lines.extend([
            "---",
            "",
            "## 🏢 内部信息",
            "",
            "| 项目 | 内容 |",
            "| ---- | ---- |",
            f"| 来源区域 | {source_info.get('region', '未知')} |",
            f"| 内部邮箱 | {source_info.get('internal_email', '未指定')} |",
            f"| 用户标识 | {source_info.get('user', '系统自动')} |",
            f"| 同步时间 | {datetime.datetime.now().isoformat()} |"
        ])

    return "\n".join(lines)

def generate_forum_content(
    version: str,
    changelog: List[Dict],
    blog_url: str = ""
) -> str:
    """
    生成论坛简要内容

    Args:
        version: 版本号
        changelog: 变更日志
        blog_url: 博客 URL

    Returns:
        str: Markdown 格式的论坛内容
    """
    categorized = categorize_changelog(changelog)

    lines = [
        f"# 🆕 Hermes Desktop v{version} 已发布",
        "",
        f"**版本:** {version} | **类型:** {determine_update_type(version)}",
        "",
        "---",
        "",
        "## 📊 更新统计",
        "",
        "| 类型 | 数量 |",
        "| ---- | ---- |"
    ]

    for category in ["新增", "优化", "修复", "其他"]:
        count = len(categorized.get(category, []))
        lines.append(f"| {category} | {count} |")

    lines.extend([
        "",
        "## 📝 简要说明",
        ""
    ])

    # 列出重要更新
    important = [e for e in changelog if e.get("severity") in ["critical", "major"]][:5]

    if important:
        for entry in important:
            lines.append(f"- **{entry.get('title', '')}**: {entry.get('description', '')}")
    else:
        lines.append("本次更新主要包含多项功能优化和问题修复。")

    lines.extend([
        "",
        "---",
        ""
    ])

    if blog_url:
        lines.append(f"📖 **详细更新说明:** [{blog_url}]({blog_url})")

    lines.extend([
        "",
        f"*发布于 {datetime.datetime.now().strftime('%Y-%m-%d')}*"
    ])

    return "\n".join(lines)

# ============================================================================
# 辅助函数
# ============================================================================

def determine_update_type(version: str) -> str:
    """确定更新类型"""
    if "-beta" in version:
        return "测试版"
    elif "-dev" in version:
        return "开发版"
    elif "hotfix" in version.lower():
        return "热修复"
    elif "security" in version.lower():
        return "安全更新"
    else:
        return "稳定版"

def categorize_changelog(changelog: List[Dict]) -> Dict[str, List[Dict]]:
    """将变更日志按类别分组"""
    categories = {"新增": [], "优化": [], "修复": [], "其他": []}

    for entry in changelog:
        category = entry.get("category", "其他")
        if category in categories:
            categories[category].append(entry)
        else:
            categories["其他"].append(entry)

    return categories

def get_severity_icon(severity: str) -> str:
    """获取严重程度图标"""
    icons = {
        "critical": "🔴",
        "major": "🟠",
        "normal": "🟡",
        "minor": "⚪"
    }
    return icons.get(severity, "⚪")

def generate_summary_table(changelog: List[Dict]) -> str:
    """生成更新概要表格"""
    categorized = categorize_changelog(changelog)

    lines = [
        "| 类别 | 数量 |",
        "| ---- | ---- |"
    ]

    for category in ["新增", "优化", "修复", "其他"]:
        count = len(categorized.get(category, []))
        lines.append(f"| {category} | {count} |")

    return "\n".join(lines)