# update_notifier.py — 自动更新说明生成器
# ============================================================================
#
# 功能:
#   1. 自动生成客户端更新推送的更新说明
#   2. 标注更新来源（区域、用户、内部邮箱）
#   3. 同步到系统内置平台的博客和论坛
#   4. 博客详细说明更新内容
#   5. 论坛简要说明 + 博客地址链接
#
# 使用示例:
# ```python
# notifier = UpdateNotifier()
#
# # 生成更新说明
# notes = await notifier.generate_update_notes(
#     from_version="1.0.0",
#     to_version="1.2.0",
#     source_region="CN-North",
#     source_user="devteam@mogoo.com"
# )
#
# # 同步到博客和论坛
# result = await notifier.sync_to_blog_forum(notes)
# logger.info(f"博客: {result.blog_url}")
# logger.info(f"论坛: {result.forum_url}")
# ```
#
# ============================================================================

import json
import hashlib
import datetime
import asyncio
import aiohttp
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path
from enum import Enum

# ============================================================================
# 配置
# ============================================================================

BLOG_API_BASE = "https://blog.mogoo.com/api"
FORUM_API_BASE = "https://forum.mogoo.com/api"
INTERNAL_EMAIL_API = "https://internal.mogoo.com/api/notify"

# 默认内部邮箱列表
DEFAULT_INTERNAL_EMAILS = [
    "devteam@mogoo.com",
    "qa@mogoo.com",
    "ops@mogoo.com"
]

# ============================================================================
# 数据结构
# ============================================================================

class UpdateType(Enum):
    """更新类型"""
    STABLE = "stable"           # 稳定版
    BETA = "beta"                # 测试版
    DEV = "dev"                  # 开发版
    HOTFIX = "hotfix"            # 热修复
    SECURITY = "security"        # 安全更新

class NotificationPriority(Enum):
    """通知优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

@dataclass
class UpdateSource:
    """更新来源信息"""
    region: str = "unknown"           # 区域 (如: CN-North, US-West)
    user: str = ""                    # 用户标识
    internal_email: str = ""          # 内部邮箱
    ip_address: str = ""              # IP 地址
    device_id: str = ""              # 设备 ID
    relay_node: str = ""             # 中继节点
    p2p_peer: str = ""               # P2P 对等节点

@dataclass
class ChangelogEntry:
    """更新条目"""
    category: str                    # 类别 (新增/优化/修复/其他)
    title: str                       # 标题
    description: str                 # 描述
    severity: str = "normal"         # 严重程度 (critical/major/minor)

@dataclass
class UpdateNotes:
    """完整更新说明"""
    version: str                     # 版本号
    release_date: str               # 发布日期
    from_version: str               # 原版本
    to_version: str                 # 目标版本
    update_type: UpdateType         # 更新类型
    changelog: List[ChangelogEntry] = field(default_factory=list)
    source: UpdateSource = field(default_factory=UpdateSource)
    size_bytes: int = 0             # 更新包大小
    download_urls: List[str] = field(default_factory=list)
    breaking_changes: List[str] = field(default_factory=list)
    known_issues: List[str] = field(default_factory=list)
    blog_url: str = ""              # 博客 URL
    forum_url: str = ""             # 论坛 URL

@dataclass
class SyncResult:
    """同步结果"""
    success: bool
    blog_url: str = ""
    forum_url: str = ""
    email_sent: bool = False
    error_message: str = ""

# ============================================================================
# 更新说明生成器
# ============================================================================

class UpdateNotifier:
    """
    自动更新说明生成器

    功能:
    1. 根据版本差异自动生成更新说明
    2. 标注更新来源（区域、用户、内部邮箱）
    3. 生成适合博客和论坛的不同格式
    4. 同步到内置平台
    """

    def __init__(
        self,
        api_key: str = "",
        internal_emails: List[str] = None,
        blog_category: str = "product-update"
    ):
        self.api_key = api_key
        self.internal_emails = internal_emails or DEFAULT_INTERNAL_EMAILS
        self.blog_category = blog_category
        self._cache_dir = Path.home() / ".hermes-desktop" / "update_notifier"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # 核心功能
    # --------------------------------------------------------------------------

    async def generate_update_notes(
        self,
        from_version: str,
        to_version: str,
        source: UpdateSource = None,
        changelog_data: List[Dict] = None,
        size_bytes: int = 0,
        download_urls: List[str] = None
    ) -> UpdateNotes:
        """
        生成完整的更新说明

        Args:
            from_version: 原版本
            to_version: 目标版本
            source: 更新来源信息
            changelog_data: 变更数据列表
            size_bytes: 更新包大小
            download_urls: 下载地址列表

        Returns:
            UpdateNotes: 完整的更新说明对象
        """
        source = source or UpdateSource()

        # 确定更新类型
        update_type = self._determine_update_type(from_version, to_version)

        # 获取变更日志
        changelog = await self._get_changelog(from_version, to_version, changelog_data)

        # 创建更新说明
        notes = UpdateNotes(
            version=to_version,
            release_date=datetime.datetime.now().isoformat(),
            from_version=from_version,
            to_version=to_version,
            update_type=update_type,
            changelog=changelog,
            source=source,
            size_bytes=size_bytes,
            download_urls=download_urls or []
        )

        # 缓存更新说明
        await self._cache_notes(notes)

        return notes

    async def sync_to_blog_forum(
        self,
        notes: UpdateNotes,
        sync_email: bool = True
    ) -> SyncResult:
        """
        同步更新说明到博客和论坛

        Args:
            notes: 更新说明对象
            sync_email: 是否同步发送内部邮件

        Returns:
            SyncResult: 同步结果
        """
        result = SyncResult(success=False)

        try:
            # 并行执行博客和论坛同步
            blog_task = self._sync_to_blog(notes)
            forum_task = self._sync_to_forum(notes)

            blog_response, forum_response = await asyncio.gather(
                blog_task, forum_task, return_exceptions=True
            )

            # 处理博客响应
            if isinstance(blog_response, Exception):
                result.error_message += f"博客同步失败: {blog_response}; "
            else:
                notes.blog_url = blog_response.get("url", "")
                result.blog_url = notes.blog_url

            # 处理论坛响应
            if isinstance(forum_response, Exception):
                result.error_message += f"论坛同步失败: {forum_response}; "
            else:
                notes.forum_url = forum_response.get("url", "")
                result.forum_url = notes.forum_url

            # 发送内部邮件
            if sync_email:
                email_task = self._send_internal_email(notes)
                try:
                    await email_task
                    result.email_sent = True
                except Exception as e:
                    result.error_message += f"邮件发送失败: {e}"

            result.success = not bool(result.error_message)

        except Exception as e:
            result.error_message = str(e)

        return result

    # --------------------------------------------------------------------------
    # 博客同步
    # --------------------------------------------------------------------------

    async def _sync_to_blog(self, notes: UpdateNotes) -> Dict:
        """
        同步到博客 (详细说明)

        博客内容包含:
        - 完整的版本信息和更新概要
        - 详细的更新内容 (分类型)
        - 更新来源和内部信息
        - 下载地址
        """
        blog_content = self._generate_blog_content(notes)

        payload = {
            "title": f"Hermes Desktop v{notes.version} 更新说明",
            "content": blog_content,
            "category": self.blog_category,
            "tags": self._generate_tags(notes),
            "author": notes.source.user or "system",
            "published_at": notes.release_date
        }

        # 发送到博客 API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BLOG_API_BASE}/posts",
                json=payload,
                headers=self._get_headers()
            ) as response:
                if response.status == 200 or response.status == 201:
                    result = await response.json()
                    return {"url": result.get("url", ""), "id": result.get("id")}
                else:
                    raise Exception(f"博客 API 返回错误: {response.status}")

    def _generate_blog_content(self, notes: UpdateNotes) -> str:
        """生成博客详细内容的 Markdown 格式"""
        lines = [
            f"# Hermes Desktop v{notes.version} 更新说明",
            "",
            f"**发布版本:** {notes.version}",
            f"**发布日期:** {notes.release_date}",
            f"**更新类型:** {notes.update_type.value}",
            "",
            "---",
            "",
            "## 📋 更新概要",
            "",
            self._generate_update_summary_table(notes),
            "",
            "---",
            "",
            "## 📝 详细更新内容",
            ""
        ]

        # 按类别分组
        categorized = self._categorize_changelog(notes.changelog)

        for category, entries in categorized.items():
            if entries:
                lines.append(f"### {category}")
                lines.append("")
                for entry in entries:
                    severity_icon = self._get_severity_icon(entry.severity)
                    lines.append(f"{severity_icon} **{entry.title}**")
                    lines.append(f"> {entry.description}")
                    lines.append("")

        # Breaking Changes
        if notes.breaking_changes:
            lines.extend([
                "---",
                "",
                "## ⚠️ Breaking Changes",
                "",
                "本次更新包含以下 Breaking Changes，升级前请注意:",
                ""
            ])
            for change in notes.breaking_changes:
                lines.append(f"- {change}")
            lines.append("")

        # 已知问题
        if notes.known_issues:
            lines.extend([
                "---",
                "",
                "## 🔍 已知问题",
                ""
            ])
            for issue in notes.known_issues:
                lines.append(f"- {issue}")
            lines.append("")

        # 下载信息
        lines.extend([
            "---",
            "",
            "## 📥 下载信息",
            "",
            f"| 项目 | 内容 |",
            "| ---- | ---- |",
            f"| 版本 | {notes.version} |",
            f"| 大小 | {self._format_size(notes.size_bytes)} |",
            f"| 原版本 | {notes.from_version} |",
            ""
        ])

        if notes.download_urls:
            lines.append("**下载地址:**")
            for i, url in enumerate(notes.download_urls, 1):
                lines.append(f"{i}. {url}")
            lines.append("")

        # 内部信息
        lines.extend([
            "---",
            "",
            "## 🏢 内部信息",
            "",
            self._generate_internal_info_table(notes),
            ""
        ])

        return "\n".join(lines)

    def _generate_update_summary_table(self, notes: UpdateNotes) -> str:
        """生成更新概要表格"""
        categorized = self._categorize_changelog(notes.changelog)

        lines = [
            "| 类别 | 数量 |",
            "| ---- | ---- |"
        ]

        for category in ["新增", "优化", "修复", "其他"]:
            count = len(categorized.get(category, []))
            lines.append(f"| {category} | {count} |")

        return "\n".join(lines)

    def _generate_internal_info_table(self, notes: UpdateNotes) -> str:
        """生成内部信息表格"""
        source = notes.source

        return "\n".join([
            "| 项目 | 内容 |",
            "| ---- | ---- |",
            f"| 来源区域 | {source.region} |",
            f"| 内部邮箱 | {source.internal_email or '未指定'} |",
            f"| 用户标识 | {source.user or '系统自动'} |",
            f"| 设备 ID | {source.device_id or '未知'} |",
            f"| 中继节点 | {source.relay_node or 'P2P 自动发现'} |",
            f"| 同步时间 | {datetime.datetime.now().isoformat()} |"
        ])

    # --------------------------------------------------------------------------
    # 论坛同步
    # --------------------------------------------------------------------------

    async def _sync_to_forum(self, notes: UpdateNotes) -> Dict:
        """
        同步到论坛 (简要说明 + 博客链接)

        论坛内容包含:
        - 版本号和简要说明
        - 主要更新类型统计
        - 指向博客的链接
        """
        forum_content = self._generate_forum_content(notes)

        payload = {
            "title": f"Hermes Desktop v{notes.version} 更新公告",
            "content": forum_content,
            "category": "update-announcements",
            "tags": self._generate_tags(notes),
            "author": notes.source.user or "system",
            "published_at": notes.release_date,
            "is_pinned": notes.update_type in [UpdateType.SECURITY, UpdateType.HOTFIX]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{FORUM_API_BASE}/topics",
                json=payload,
                headers=self._get_headers()
            ) as response:
                if response.status == 200 or response.status == 201:
                    result = await response.json()
                    return {"url": result.get("url", ""), "id": result.get("id")}
                else:
                    raise Exception(f"论坛 API 返回错误: {response.status}")

    def _generate_forum_content(self, notes: UpdateNotes) -> str:
        """生成论坛简要内容的 Markdown 格式"""
        categorized = self._categorize_changelog(notes.changelog)

        lines = [
            f"# 🆕 Hermes Desktop v{notes.version} 已发布",
            "",
            f"**版本:** {notes.version} | **类型:** {notes.update_type.value} | **大小:** {self._format_size(notes.size_bytes)}",
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

        # 列出最重要的 3-5 项更新
        important = [
            e for e in notes.changelog
            if e.severity in ["critical", "major"]
        ][:5]

        if important:
            for entry in important:
                lines.append(f"- **{entry.title}**: {entry.description}")
        else:
            lines.append("本次更新主要包含多项功能优化和问题修复。")

        lines.extend([
            "",
            "---",
            "",
            f"📖 **详细更新说明:** [{notes.blog_url}]({notes.blog_url})",
            "",
            f"💬 **欢迎到论坛讨论:** [点击这里]({notes.forum_url})",
            "",
            "---",
            f"*发布于 {notes.release_date}*"
        ])

        return "\n".join(lines)

    # --------------------------------------------------------------------------
    # 内部邮件
    # --------------------------------------------------------------------------

    async def _send_internal_email(self, notes: UpdateNotes) -> bool:
        """发送内部通知邮件"""
        source = notes.source

        # 构建邮件内容
        email_body = self._generate_email_body(notes)

        # 发送到所有内部邮箱
        tasks = []
        for email in self.internal_emails:
            payload = {
                "to": email,
                "subject": f"[Hermes Update] v{notes.version} 更新通知",
                "body": email_body,
                "is_html": True
            }

            task = self._send_email(payload)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return all(r is True for r in results)

    async def _send_email(self, payload: Dict) -> bool:
        """发送单封邮件"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                INTERNAL_EMAIL_API,
                json=payload,
                headers=self._get_headers()
            ) as response:
                return response.status in [200, 201, 204]

    def _generate_email_body(self, notes: UpdateNotes) -> str:
        """生成内部邮件 HTML 内容"""
        categorized = self._categorize_changelog(notes.changelog)

        lines = [
            "<html><body>",
            f"<h2>Hermes Desktop v{notes.version} 更新通知</h2>",
            "",
            "<table border='1' cellpadding='8' cellspacing='0'>",
            f"<tr><td><b>原版本</b></td><td>{notes.from_version}</td></tr>",
            f"<tr><td><b>新版本</b></td><td>{notes.version}</td></tr>",
            f"<tr><td><b>更新类型</b></td><td>{notes.update_type.value}</td></tr>",
            f"<tr><td><b>发布时间</b></td><td>{notes.release_date}</td></tr>",
            f"<tr><td><b>来源区域</b></td><td>{notes.source.region}</td></tr>",
            f"<tr><td><b>内部邮箱</b></td><td>{notes.source.internal_email or notes.source.user}</td></tr>",
            "</table>",
            "",
            "<h3>更新统计</h3>",
            "<ul>"
        ]

        for category in ["新增", "优化", "修复", "其他"]:
            count = len(categorized.get(category, []))
            lines.append(f"<li>{category}: {count}</li>")

        lines.extend([
            "</ul>",
            "",
            f"<p><a href='{notes.blog_url}'>查看详细更新说明</a></p>",
            "",
            f"<p><small>此邮件由系统自动生成 | 同步时间: {datetime.datetime.now().isoformat()}</small></p>",
            "</body></html>"
        ])

        return "\n".join(lines)

    # --------------------------------------------------------------------------
    # 辅助方法
    # --------------------------------------------------------------------------

    def _determine_update_type(self, from_version: str, to_version: str) -> UpdateType:
        """根据版本号确定更新类型"""
        from_v = self._parse_version(from_version)
        to_v = self._parse_version(to_version)

        # 检查是否是热修复
        if to_v[2] > from_v[2]:
            return UpdateType.STABLE
        elif to_v[1] > from_v[1]:
            return UpdateType.STABLE
        elif "-beta" in to_version:
            return UpdateType.BETA
        elif "-dev" in to_version:
            return UpdateType.DEV
        elif "hotfix" in to_version.lower():
            return UpdateType.HOTFIX
        elif "security" in to_version.lower():
            return UpdateType.SECURITY
        else:
            return UpdateType.STABLE

    def _parse_version(self, version: str) -> tuple:
        """解析版本号为元组"""
        import re
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
        if match:
            return tuple(int(x) for x in match.groups())
        return (0, 0, 0)

    async def _get_changelog(
        self,
        from_version: str,
        to_version: str,
        changelog_data: List[Dict] = None
    ) -> List[ChangelogEntry]:
        """获取变更日志"""
        if changelog_data:
            return [
                ChangelogEntry(
                    category=item.get("category", "其他"),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    severity=item.get("severity", "normal")
                )
                for item in changelog_data
            ]

        # 从远程获取或生成默认
        return [
            ChangelogEntry(
                category="新增",
                title="功能更新",
                description="包含多项功能改进和优化",
                severity="normal"
            )
        ]

    def _categorize_changelog(
        self,
        changelog: List[ChangelogEntry]
    ) -> Dict[str, List[ChangelogEntry]]:
        """将变更日志按类别分组"""
        categories = {"新增": [], "优化": [], "修复": [], "其他": []}
        for entry in changelog:
            if entry.category in categories:
                categories[entry.category].append(entry)
            else:
                categories["其他"].append(entry)
        return categories

    def _generate_tags(self, notes: UpdateNotes) -> List[str]:
        """生成标签列表"""
        tags = [
            "hermes-desktop",
            f"v{notes.version}",
            notes.update_type.value
        ]

        if notes.source.region:
            tags.append(notes.source.region)

        return tags

    def _get_severity_icon(self, severity: str) -> str:
        """获取严重程度图标"""
        icons = {
            "critical": "🔴",
            "major": "🟠",
            "normal": "🟡",
            "minor": "⚪"
        }
        return icons.get(severity, "⚪")

    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def _get_headers(self) -> Dict:
        """获取 API 请求头"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _cache_notes(self, notes: UpdateNotes):
        """缓存更新说明"""
        cache_file = self._cache_dir / f"notes-{notes.version}.json"

        data = {
            "notes": asdict(notes),
            "cached_at": datetime.datetime.now().isoformat()
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def get_cached_notes(self, version: str) -> Optional[UpdateNotes]:
        """获取缓存的更新说明"""
        cache_file = self._cache_dir / f"notes-{version}.json"

        if not cache_file.exists():
            return None

        with open(cache_file, encoding="utf-8") as f:
            data = json.load(f)

        notes_data = data["notes"]
        notes_data["update_type"] = UpdateType(notes_data["update_type"])
        notes_data["source"] = UpdateSource(**notes_data["source"])

        return UpdateNotes(**notes_data)

# ============================================================================
# 全局访问器
# ============================================================================

_notifier_instance: Optional[UpdateNotifier] = None

def get_update_notifier() -> UpdateNotifier:
    """获取全局 UpdateNotifier 实例"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = UpdateNotifier()
    return _notifier_instance

# ============================================================================
# 便捷函数
# ============================================================================

async def generate_and_sync_update(
    from_version: str,
    to_version: str,
    source_region: str = "unknown",
    source_user: str = "",
    **kwargs
) -> SyncResult:
    """
    便捷函数: 生成并同步更新说明

    Args:
        from_version: 原版本
        to_version: 目标版本
        source_region: 来源区域
        source_user: 来源用户
        **kwargs: 其他参数传递给 generate_update_notes

    Returns:
        SyncResult: 同步结果
    """
    notifier = get_update_notifier()

    source = UpdateSource(
        region=source_region,
        user=source_user,
        internal_email=kwargs.get("internal_email", "")
    )

    notes = await notifier.generate_update_notes(
        from_version=from_version,
        to_version=to_version,
        source=source,
        **kwargs
    )

    result = await notifier.sync_to_blog_forum(notes)

    return result

# ============================================================================
# CLI 入口
# ============================================================================

if __name__ == "__main__":
    import argparse
from core.logger import get_logger
logger = get_logger('decentralized_update.update_notifier')


    parser = argparse.ArgumentParser(description="Hermes Desktop 更新说明生成器")
    parser.add_argument("--from", dest="from_version", required=True, help="原版本")
    parser.add_argument("--to", dest="to_version", required=True, help="目标版本")
    parser.add_argument("--region", default="unknown", help="来源区域")
    parser.add_argument("--user", default="", help="来源用户")
    parser.add_argument("--internal-email", default="", help="内部邮箱")
    parser.add_argument("--sync", action="store_true", help="同步到博客和论坛")

    args = parser.parse_args()

    async def main():
        source = UpdateSource(
            region=args.region,
            user=args.user,
            internal_email=args.internal_email
        )

        notifier = get_update_notifier()
        notes = await notifier.generate_update_notes(
            from_version=args.from_version,
            to_version=args.to_version,
            source=source
        )

        logger.info(f"更新说明已生成: v{notes.version}")
        logger.info(f"博客内容预览:\n{notes.blog_url or '未发布'}")

        if args.sync:
            result = await notifier.sync_to_blog_forum(notes)
            logger.info(f"\n同步结果:")
            logger.info(f"  博客: {result.blog_url}")
            logger.info(f"  论坛: {result.forum_url}")
            logger.info(f"  邮件: {'已发送' if result.email_sent else '未发送'}")
            if result.error_message:
                logger.info(f"  错误: {result.error_message}")

    asyncio.run(main())