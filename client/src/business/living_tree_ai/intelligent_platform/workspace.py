"""
智能工作空间核心 (Intelligent Workspace Core)
=============================================

整合所有 AI 增强能力，提供统一的智能工作空间接口。
"""

import asyncio
import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# 分布式 AI 导入
from ..distributed_ai import CentralBrain
from ..internal_mail import MailAIEnhancer


class ContentType(Enum):
    """内容类型"""
    POST = "post"           # 论坛帖子
    ARTICLE = "article"     # 技术文章
    MAIL = "mail"           # 邮件
    DOCUMENT = "document"   # 文档
    COMMENT = "comment"     # 评论
    REPLY = "reply"         # 回复


class PublishStatus(Enum):
    """发布状态"""
    DRAFT = "draft"           # 草稿
    REVIEWING = "reviewing"  # 审核中
    PUBLISHED = "published"  # 已发布
    REJECTED = "rejected"     # 被拒绝
    ARCHIVED = "archived"     # 已归档


@dataclass
class ComplianceResult:
    """合规检查结果"""
    passed: bool
    score: float = 1.0       # 0.0 - 1.0
    warnings: list[str] = field(default_factory=list)
    blocked_items: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class ContentMetadata:
    """内容元数据"""
    content_id: str
    title: str
    content_type: ContentType
    author_node_id: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    tags: list[str] = field(default_factory=list)
    language: str = "zh-CN"
    word_count: int = 0
    reading_time_minutes: float = 0.0
    attachments: list[str] = field(default_factory=list)  # 文件 Hash 列表


@dataclass
class IntelligentContent:
    """智能增强后的内容"""
    metadata: ContentMetadata
    original_content: str
    ai_enhanced_content: str = ""
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    related_items: list[str] = field(default_factory=list)  # 关联的内容 ID
    sentiment: str = "neutral"
    compliance: Optional[ComplianceResult] = None
    preview_cache_path: Optional[str] = None


class IntelligentWorkspace:
    """
    智能工作空间

    提供统一的 AI 增强内容创作、发布、协作平台
    """

    def __init__(
        self,
        workspace_id: str,
        central_brain: Optional[CentralBrain] = None,
        local_storage_path: Optional[Path] = None
    ):
        self.workspace_id = workspace_id
        self.central_brain = central_brain
        self.local_storage_path = local_storage_path or Path.home() / ".hermes-desktop" / "workspace"

        # 创建本地存储目录
        self.local_storage_path.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self.db_path = self.local_storage_path / "workspace.db"
        self._init_database()

        # 初始化组件
        self._init_components()

    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 内容表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contents (
                content_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content_type TEXT NOT NULL,
                author_node_id TEXT NOT NULL,
                original_content TEXT,
                ai_enhanced_content TEXT,
                summary TEXT,
                tags TEXT,
                keywords TEXT,
                related_items TEXT,
                sentiment TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 附件索引表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                file_hash TEXT PRIMARY KEY,
                content_id TEXT,
                file_name TEXT,
                file_size INTEGER,
                file_type TEXT,
                threat_level TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (content_id) REFERENCES contents(content_id)
            )
        """)

        # 预览缓存表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preview_cache (
                content_id TEXT PRIMARY KEY,
                preview_type TEXT NOT NULL,
                cache_path TEXT,
                generated_at TEXT NOT NULL,
                FOREIGN KEY (content_id) REFERENCES contents(content_id)
            )
        """)

        conn.commit()
        conn.close()

    def _init_components(self):
        """初始化组件"""
        from .content_creator import ContentCreator, create_content_creator
        from .web_publisher import WebPublisher, create_web_publisher
        from .collaboration import CollaborationEngine, create_collaboration_engine
        from .security_guard import SecurityGuard, create_security_guard
        from .storage_engine import StorageEngine, create_storage_engine

        self.content_creator = create_content_creator(self)
        self.web_publisher = create_web_publisher(self)
        self.collaboration = create_collaboration_engine(self)
        self.security = create_security_guard(self)
        self.storage = create_storage_engine(self)

    def generate_content_id(self, title: str, author_node_id: str) -> str:
        """生成内容 ID"""
        raw = f"{author_node_id}:{title}:{datetime.now().isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def create_content(
        self,
        title: str,
        content: str,
        content_type: ContentType,
        author_node_id: str,
        tags: Optional[list[str]] = None
    ) -> IntelligentContent:
        """
        创建智能内容

        Args:
            title: 内容标题
            content: 原始内容
            content_type: 内容类型
            author_node_id: 作者节点 ID
            tags: 标签

        Returns:
            智能增强后的内容
        """
        # 生成元数据
        content_id = self.generate_content_id(title, author_node_id)
        metadata = ContentMetadata(
            content_id=content_id,
            title=title,
            content_type=content_type,
            author_node_id=author_node_id,
            tags=tags or [],
            word_count=len(content),
            reading_time_minutes=len(content) / 500  # 假设阅读速度 500 字/分钟
        )

        # 创建智能内容对象
        intelligent_content = IntelligentContent(
            metadata=metadata,
            original_content=content
        )

        # AI 增强处理
        intelligent_content = await self._enhance_content(intelligent_content)

        # 合规检查
        intelligent_content = await self._check_compliance(intelligent_content)

        # 存储
        await self._save_content(intelligent_content)

        return intelligent_content

    async def _enhance_content(self, content: IntelligentContent) -> IntelligentContent:
        """
        AI 增强内容

        流程：
        1. 语法检查（边缘节点）
        2. 内容优化（中心节点）
        3. 深度生成（海外集群）
        """
        # 1. 语法检查 - 边缘节点
        enhanced = await self.content_creator.enhance_writing(content.original_content)

        # 2. 摘要生成
        summary = await self.content_creator.generate_summary(content.original_content)

        # 3. 关键词提取
        keywords = await self.content_creator.extract_keywords(content.original_content)

        # 4. 关联分析 - 中心节点
        related = await self._find_related_content(content)

        content.ai_enhanced_content = enhanced
        content.summary = summary
        content.keywords = keywords
        content.related_items = related

        return content

    async def _find_related_content(self, content: IntelligentContent) -> list[str]:
        """查找关联内容"""
        if not self.central_brain:
            return []

        # 使用中心节点的知识图谱查找关联
        try:
            # 简化实现：基于关键词匹配
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            keywords_str = ",".join(f'"{k}"' for k in content.keywords[:5])
            if keywords_str:
                cursor.execute(f"""
                    SELECT content_id FROM contents
                    WHERE content_id != ?
                    AND (
                        keywords LIKE ({keywords_str})
                        OR tags IN ({keywords_str})
                    )
                    LIMIT 5
                """, (content.metadata.content_id,))
                related = [row[0] for row in cursor.fetchall()]
            else:
                related = []

            conn.close()
            return related
        except Exception:
            return []

    async def _check_compliance(self, content: IntelligentContent) -> IntelligentContent:
        """合规检查"""
        result = await self.security.scan_content(content.original_content)
        content.compliance = result
        return content

    async def _save_content(self, content: IntelligentContent):
        """保存内容到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO contents
            (content_id, title, content_type, author_node_id,
             original_content, ai_enhanced_content, summary, tags,
             keywords, related_items, sentiment, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            content.metadata.content_id,
            content.metadata.title,
            content.metadata.content_type.value,
            content.metadata.author_node_id,
            content.original_content,
            content.ai_enhanced_content,
            content.summary,
            ",".join(content.metadata.tags),
            ",".join(content.keywords),
            ",".join(content.related_items),
            content.sentiment,
            PublishStatus.DRAFT.value,
            content.metadata.created_at.isoformat(),
            content.metadata.updated_at.isoformat()
        ))

        conn.commit()
        conn.close()

    async def publish_content(self, content_id: str) -> ComplianceResult:
        """
        发布内容

        流程：
        1. 再次合规检查
        2. 生成预览
        3. 分发到相关节点
        """
        # 获取内容
        content = await self.get_content(content_id)
        if not content:
            raise ValueError(f"Content {content_id} not found")

        # 最终合规检查
        result = await self.security.scan_content(content.original_content)
        if not result.passed:
            return result

        # 生成预览
        await self.storage.generate_preview(content)

        # 更新状态
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE contents SET status = ?, updated_at = ?
            WHERE content_id = ?
        """, (PublishStatus.PUBLISHED.value, datetime.now().isoformat(), content_id))
        conn.commit()
        conn.close()

        return result

    async def get_content(self, content_id: str) -> Optional[IntelligentContent]:
        """获取内容"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM contents WHERE content_id = ?
        """, (content_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        content_id, title, content_type, author_node_id, original_content, \
            ai_enhanced_content, summary, tags, keywords, related_items, \
            sentiment, status, created_at, updated_at = row

        metadata = ContentMetadata(
            content_id=content_id,
            title=title,
            content_type=ContentType(content_type),
            author_node_id=author_node_id,
            tags=tags.split(",") if tags else [],
            created_at=datetime.fromisoformat(created_at),
            updated_at=datetime.fromisoformat(updated_at)
        )

        return IntelligentContent(
            metadata=metadata,
            original_content=original_content or "",
            ai_enhanced_content=ai_enhanced_content or "",
            summary=summary or "",
            keywords=keywords.split(",") if keywords else [],
            related_items=related_items.split(",") if related_items else [],
            sentiment=sentiment or "neutral"
        )

    async def list_contents(
        self,
        content_type: Optional[ContentType] = None,
        status: Optional[PublishStatus] = None,
        author_node_id: Optional[str] = None,
        limit: int = 20
    ) -> list[IntelligentContent]:
        """列出内容"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT content_id FROM contents WHERE 1=1"
        params = []

        if content_type:
            query += " AND content_type = ?"
            params.append(content_type.value)
        if status:
            query += " AND status = ?"
            params.append(status.value)
        if author_node_id:
            query += " AND author_node_id = ?"
            params.append(author_node_id)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        content_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        contents = []
        for cid in content_ids:
            content = await self.get_content(cid)
            if content:
                contents.append(content)

        return contents

    def get_workspace_stats(self) -> dict[str, Any]:
        """获取工作空间统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # 总内容数
        cursor.execute("SELECT COUNT(*) FROM contents")
        stats["total_contents"] = cursor.fetchone()[0]

        # 按状态统计
        cursor.execute("""
            SELECT status, COUNT(*) FROM contents GROUP BY status
        """)
        stats["by_status"] = dict(cursor.fetchall())

        # 按类型统计
        cursor.execute("""
            SELECT content_type, COUNT(*) FROM contents GROUP BY content_type
        """)
        stats["by_type"] = dict(cursor.fetchall())

        # 总字数
        cursor.execute("""
            SELECT SUM(LENGTH(original_content)) FROM contents
        """)
        stats["total_characters"] = cursor.fetchone()[0] or 0

        conn.close()
        return stats


def create_workspace(
    workspace_id: str,
    central_brain: Optional[CentralBrain] = None,
    local_storage_path: Optional[Path] = None
) -> IntelligentWorkspace:
    """
    创建智能工作空间

    Args:
        workspace_id: 工作空间 ID
        central_brain: 中心大脑实例
        local_storage_path: 本地存储路径

    Returns:
        智能工作空间实例
    """
    return IntelligentWorkspace(workspace_id, central_brain, local_storage_path)