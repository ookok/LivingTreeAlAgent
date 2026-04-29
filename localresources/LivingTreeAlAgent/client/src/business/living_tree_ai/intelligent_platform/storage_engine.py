"""
存储引擎 (Storage Engine)
=======================

本地本体 + 分布式智能层的混合存储架构：

1. 本地存储（本体）：原始文件始终在你的硬盘里
2. 分布式存储（智能层）：
   - 边缘节点：高频访问预览缓存
   - 中心节点：全局搜索索引、用户关系图谱
   - 海外集群：知识图谱（关联推荐）
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .workspace import IntelligentWorkspace


class StorageType(Enum):
    """存储类型"""
    LOCAL = "local"                   # 本地存储
    EDGE = "edge"                    # 边缘节点
    CENTRAL = "central"              # 中心节点
    OVERSEAS = "overseas"            # 海外集群


@dataclass
class IndexEntry:
    """索引条目"""
    entry_id: str
    content_id: str                  # 关联的内容 ID
    index_type: str                  # keyword/full_text/knowledge_graph
    storage_type: StorageType
    data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: Optional[datetime] = None


@dataclass
class PreviewCache:
    """预览缓存"""
    cache_id: str
    content_id: str
    preview_type: str                # thumbnail/summary/480p/transcript
    cache_path: Optional[str]        # 本地缓存路径
    remote_path: Optional[str]       # 边缘节点路径
    size_bytes: int = 0
    generated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    access_count: int = 0


@dataclass
class DeduplicationRecord:
    """去重记录"""
    file_hash: str
    canonical_path: str              # 规范存储路径
    aliases: list[str] = field(default_factory=list)  # 引用此文件的其他路径
    size_bytes: int
    created_at: datetime = field(default_factory=datetime.now)
    last_referenced: datetime = field(default_factory=datetime.now)
    reference_count: int = 1


@dataclass
class SyncStatus:
    """同步状态"""
    content_id: str
    sync_type: StorageType
    status: str                      # pending/syncing/synced/error
    progress: float = 0.0            # 0.0 - 1.0
    last_sync: Optional[datetime] = None
    error_message: Optional[str] = None


class StorageEngine:
    """
    存储引擎

    架构：
    - 本地存储（本体）：原始文件
    - 边缘缓存：预览、转码
    - 中心索引：搜索、关系
    - 海外知识：图谱、推荐

    原则：
    - 数据不动，只动索引
    - AI 只处理"影子"（索引+预览）
    """

    def __init__(self, workspace: IntelligentWorkspace):
        self.workspace = workspace
        self.central_brain = workspace.central_brain

        # 本地路径
        self.local_storage = workspace.local_storage_path / "storage"
        self.local_storage.mkdir(parents=True, exist_ok=True)

        # 子目录
        self.content_dir = self.local_storage / "content"    # 原始内容
        self.attachment_dir = self.local_storage / "attachments"  # 附件
        self.preview_dir = self.local_storage / "previews"    # 预览缓存
        self.index_dir = self.local_storage / "indices"       # 索引

        for d in [self.content_dir, self.attachment_dir, self.preview_dir, self.index_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self.db_path = self.local_storage / "storage.db"
        self._init_database()

    def _init_database(self):
        """初始化存储数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 索引表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS indices (
                entry_id TEXT PRIMARY KEY,
                content_id TEXT NOT NULL,
                index_type TEXT NOT NULL,
                storage_type TEXT NOT NULL,
                data TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT
            )
        """)

        # 预览缓存表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preview_cache (
                cache_id TEXT PRIMARY KEY,
                content_id TEXT NOT NULL,
                preview_type TEXT NOT NULL,
                cache_path TEXT,
                remote_path TEXT,
                size_bytes INTEGER DEFAULT 0,
                generated_at TEXT NOT NULL,
                expires_at TEXT,
                access_count INTEGER DEFAULT 0
            )
        """)

        # 去重表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deduplication (
                file_hash TEXT PRIMARY KEY,
                canonical_path TEXT NOT NULL,
                aliases TEXT,
                size_bytes INTEGER,
                created_at TEXT NOT NULL,
                last_referenced TEXT NOT NULL,
                reference_count INTEGER DEFAULT 1
            )
        """)

        # 同步状态表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_status (
                content_id TEXT NOT NULL,
                sync_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                progress REAL DEFAULT 0.0,
                last_sync TEXT,
                error_message TEXT,
                PRIMARY KEY (content_id, sync_type)
            )
        """)

        conn.commit()
        conn.close()

    def generate_hash(self, content: str) -> str:
        """生成内容哈希"""
        return hashlib.sha256(content.encode()).hexdigest()

    async def store_content(
        self,
        content_id: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None
    ) -> str:
        """
        存储内容（本体）

        Args:
            content_id: 内容 ID
            content: 原始内容
            metadata: 元数据

        Returns:
            存储路径
        """
        storage_path = self.content_dir / f"{content_id}.json"

        data = {
            "content_id": content_id,
            "content": content,
            "metadata": metadata or {},
            "stored_at": datetime.now().isoformat()
        }

        with open(storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 建立索引
        await self._index_content(content_id, content)

        return str(storage_path)

    async def _index_content(self, content_id: str, content: str):
        """索引内容"""
        # 关键词索引
        words = content.split()
        keywords = [w for w in words if len(w) >= 4][:20]

        entry = IndexEntry(
            entry_id=self.generate_hash(f"{content_id}_keywords"),
            content_id=content_id,
            index_type="keyword",
            storage_type=StorageType.LOCAL,
            data={"keywords": keywords}
        )
        await self._save_index_entry(entry)

        # 同步到中心节点（异步）
        if self.central_brain:
            # 通知中心节点更新全局索引
            pass

    async def _save_index_entry(self, entry: IndexEntry):
        """保存索引条目"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO indices
            (entry_id, content_id, index_type, storage_type, data,
             created_at, updated_at, access_count, last_accessed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.entry_id,
            entry.content_id,
            entry.index_type,
            entry.storage_type.value,
            json.dumps(entry.data),
            entry.created_at.isoformat(),
            entry.updated_at.isoformat(),
            entry.access_count,
            entry.last_accessed.isoformat() if entry.last_accessed else None
        ))

        conn.commit()
        conn.close()

    async def generate_preview(
        self,
        content: Any,
        preview_types: Optional[list[str]] = None
    ) -> list[PreviewCache]:
        """
        生成预览

        Args:
            content: 智能内容对象
            preview_types: 预览类型列表

        Returns:
            预览缓存列表
        """
        preview_types = preview_types or ["summary", "thumbnail"]

        caches = []

        for ptype in preview_types:
            cache = PreviewCache(
                cache_id=self.generate_hash(f"{content.metadata.content_id}_{ptype}"),
                content_id=content.metadata.content_id,
                preview_type=ptype
            )

            if ptype == "summary":
                # 生成摘要预览
                cache.cache_path = str(self.preview_dir / f"{cache.cache_id}.txt")
                with open(cache.cache_path, "w", encoding="utf-8") as f:
                    f.write(content.summary)

            elif ptype == "thumbnail":
                # 生成缩略图（如果是图片内容）
                cache.cache_path = str(self.preview_dir / f"{cache.cache_id}.jpg")

            elif ptype == "480p":
                # 视频转码预览（480p）
                cache.cache_path = str(self.preview_dir / f"{cache.cache_id}.mp4")

            caches.append(cache)
            await self._save_preview_cache(cache)

        return caches

    async def _save_preview_cache(self, cache: PreviewCache):
        """保存预览缓存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO preview_cache
            (cache_id, content_id, preview_type, cache_path, remote_path,
             size_bytes, generated_at, expires_at, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cache.cache_id,
            cache.content_id,
            cache.preview_type,
            cache.cache_path,
            cache.remote_path,
            cache.size_bytes,
            cache.generated_at.isoformat(),
            cache.expires_at.isoformat() if cache.expires_at else None,
            cache.access_count
        ))

        conn.commit()
        conn.close()

    async def deduplicate_attachment(
        self,
        file_hash: str,
        file_path: str,
        file_size: int
    ) -> DeduplicationRecord:
        """
        附件去重

        Args:
            file_hash: 文件哈希
            file_path: 当前文件路径
            file_size: 文件大小

        Returns:
            去重记录
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 检查是否已存在
        cursor.execute("""
            SELECT file_hash, canonical_path, aliases, reference_count
            FROM deduplication WHERE file_hash = ?
        """, (file_hash,))

        row = cursor.fetchone()

        if row:
            # 已存在，更新引用
            canonical_path, aliases_str, reference_count = row[1], row[2], row[3]
            aliases = json.loads(aliases_str) if aliases_str else []

            if file_path not in aliases:
                aliases.append(file_path)

            record = DeduplicationRecord(
                file_hash=file_hash,
                canonical_path=canonical_path,
                aliases=aliases,
                size_bytes=file_size,
                reference_count=reference_count + 1,
                last_referenced=datetime.now()
            )

            cursor.execute("""
                UPDATE deduplication
                SET aliases = ?, reference_count = ?, last_referenced = ?
                WHERE file_hash = ?
            """, (json.dumps(aliases), record.reference_count, record.last_referenced.isoformat(), file_hash))
        else:
            # 新文件
            record = DeduplicationRecord(
                file_hash=file_hash,
                canonical_path=file_path,
                aliases=[],
                size_bytes=file_size,
                last_referenced=datetime.now()
            )

            cursor.execute("""
                INSERT INTO deduplication
                (file_hash, canonical_path, aliases, size_bytes, created_at, last_referenced, reference_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                record.file_hash,
                record.canonical_path,
                json.dumps(record.aliases),
                record.size_bytes,
                record.created_at.isoformat(),
                record.last_referenced.isoformat(),
                record.reference_count
            ))

        conn.commit()
        conn.close()

        return record

    async def sync_to_edge(
        self,
        content_id: str,
        preview_cache: PreviewCache
    ) -> SyncStatus:
        """
        同步预览到边缘节点

        Args:
            content_id: 内容 ID
            preview_cache: 预览缓存

        Returns:
            同步状态
        """
        status = SyncStatus(
            content_id=content_id,
            sync_type=StorageType.EDGE,
            status="pending"
        )

        # 模拟同步过程
        try:
            # 1. 上传到边缘节点
            # 实际实现中，这里会调用边缘节点的 API
            status.status = "syncing"
            status.progress = 0.5

            # 2. 更新远程路径
            preview_cache.remote_path = f"edge://previews/{preview_cache.cache_id}"

            # 3. 完成
            status.status = "synced"
            status.progress = 1.0
            status.last_sync = datetime.now()

        except Exception as e:
            status.status = "error"
            status.error_message = str(e)

        # 保存状态
        await self._save_sync_status(status)

        return status

    async def _save_sync_status(self, status: SyncStatus):
        """保存同步状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO sync_status
            (content_id, sync_type, status, progress, last_sync, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            status.content_id,
            status.sync_type.value,
            status.status,
            status.progress,
            status.last_sync.isoformat() if status.last_sync else None,
            status.error_message
        ))

        conn.commit()
        conn.close()

    async def search_indices(
        self,
        query: str,
        index_type: Optional[str] = None,
        limit: int = 20
    ) -> list[IndexEntry]:
        """
        搜索索引

        Args:
            query: 查询
            index_type: 索引类型
            limit: 返回数量

        Returns:
            匹配的索引条目
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if index_type:
            cursor.execute("""
                SELECT * FROM indices
                WHERE index_type = ?
                ORDER BY access_count DESC
                LIMIT ?
            """, (index_type, limit))
        else:
            cursor.execute("""
                SELECT * FROM indices
                ORDER BY access_count DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        entries = []
        for row in rows:
            entry = IndexEntry(
                entry_id=row[0],
                content_id=row[1],
                index_type=row[2],
                storage_type=StorageType(row[3]),
                data=json.loads(row[4]) if row[4] else {},
                created_at=datetime.fromisoformat(row[5]),
                updated_at=datetime.fromisoformat(row[6]),
                access_count=row[7],
                last_accessed=datetime.fromisoformat(row[8]) if row[8] else None
            )
            entries.append(entry)

        # 关键词匹配
        query_keywords = set(query.lower().split())
        matched = []

        for entry in entries:
            if entry.index_type == "keyword":
                keywords = entry.data.get("keywords", [])
                if any(kw in query.lower() for kw in keywords):
                    matched.append(entry)

        return matched[:limit]

    async def predict_and_prefetch(
        self,
        user_node_id: str,
        context: dict[str, Any]
    ) -> list[str]:
        """
        预测性预取

        AI 预测用户即将查看的内容，提前同步到边缘节点

        Args:
            user_node_id: 用户节点 ID
            context: 上下文（当前时间、位置、设备等）

        Returns:
            预取的内容 ID 列表
        """
        prefetch_ids = []

        # 基于上下文的预测
        hour = datetime.now().hour
        location = context.get("location", "unknown")
        device = context.get("device", "desktop")

        # 预测场景
        if 8 <= hour <= 10 and location == "home":
            # 早间：预取新闻、项目更新
            prefetch_ids = ["news_daily", "project_updates"]
        elif 12 <= hour <= 14 and location == "office":
            # 午间：预取邮件、工单
            prefetch_ids = ["unread_mails", "assigned_tickets"]
        elif 18 <= hour <= 20 and location == "transit":
            # 晚间通勤：预取娱乐、社交
            prefetch_ids = ["social_updates", "entertainment"]

        # 如果有中心大脑，进行更智能的预测
        if self.central_brain:
            prompt = f"""基于以下用户上下文，预测用户接下来可能查看的内容：

用户：{user_node_id}
当前时间：{hour}:00
位置：{location}
设备：{device}

请给出 3-5 个最可能的内容 ID 或内容类型。
"""
            result = await self.central_brain.think(prompt)
            if result:
                # 简化解析
                pass

        return prefetch_ids

    def get_storage_stats(self) -> dict[str, Any]:
        """获取存储统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # 索引数量
        cursor.execute("SELECT COUNT(*) FROM indices")
        stats["total_indices"] = cursor.fetchone()[0]

        # 预览缓存数量
        cursor.execute("SELECT COUNT(*) FROM preview_cache")
        stats["total_previews"] = cursor.fetchone()[0]

        # 预览缓存大小
        cursor.execute("SELECT SUM(size_bytes) FROM preview_cache")
        stats["preview_cache_size"] = cursor.fetchone()[0] or 0

        # 去重节省空间
        cursor.execute("SELECT SUM(size_bytes * (reference_count - 1)) FROM deduplication")
        saved_bytes = cursor.fetchone()[0] or 0
        stats["deduplication_saved_bytes"] = saved_bytes

        # 同步状态
        cursor.execute("""
            SELECT status, COUNT(*) FROM sync_status GROUP BY status
        """)
        stats["sync_by_status"] = dict(cursor.fetchall())

        conn.close()

        # 本地存储大小
        stats["local_content_size"] = sum(
            f.stat().st_size for f in self.content_dir.glob("*") if f.is_file()
        )
        stats["local_attachment_size"] = sum(
            f.stat().st_size for f in self.attachment_dir.glob("*") if f.is_file()
        )

        return stats


def create_storage_engine(workspace: IntelligentWorkspace) -> StorageEngine:
    """创建存储引擎"""
    return StorageEngine(workspace)