"""
GBrain 记忆页面管理器
负责记忆页面的 CRUD 操作、Timeline 追加、Compiled Truth 更新
"""

import json
import sqlite3
import threading
import time
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from business.gbrain_memory.models import (
    BrainPage, MemoryCategory, TimelineEntry, CompiledTruth,
    EvidenceSource, CATEGORY_STRUCTURE
)


class PageManager:
    """
    记忆页面管理器

    功能：
    1. 页面 CRUD 操作
    2. Timeline Append-only 管理
    3. Compiled Truth 自动更新
    4. 分类目录管理
    5. 别名和交叉引用管理
    """

    def __init__(self, brain_dir: str | Path = None):
        from business.config import get_config_dir

        if brain_dir is None:
            brain_dir = get_config_dir() / "gbrain"

        self.brain_dir = Path(brain_dir)
        self.brain_dir.mkdir(parents=True, exist_ok=True)

        # Markdown 存储目录
        self.pages_dir = self.brain_dir / "pages"
        self.pages_dir.mkdir(exist_ok=True)

        # 数据库（用于快速索引）
        self.db_path = self.brain_dir / "gbrain.db"

        self._lock = threading.Lock()
        self._init_database()

    def _init_database(self):
        """初始化索引数据库"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript("""
                -- 页面索引表
                CREATE TABLE IF NOT EXISTS pages (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT DEFAULT 'unclassified',
                    compiled_summary TEXT DEFAULT '',
                    key_points TEXT DEFAULT '[]',
                    tags TEXT DEFAULT '[]',
                    aliases TEXT DEFAULT '[]',
                    cross_refs TEXT DEFAULT '[]',
                    created_at REAL DEFAULT 0,
                    last_modified REAL DEFAULT 0,
                    timeline_count INTEGER DEFAULT 0
                );

                -- 全文搜索表 (FTS5)
                CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
                    id,
                    title,
                    compiled_summary,
                    key_points,
                    tags,
                    content='pages',
                    content_rowid='rowid'
                );

                -- 时间线索引
                CREATE TABLE IF NOT EXISTS timeline (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    source TEXT,
                    source_type TEXT,
                    content TEXT,
                    context TEXT,
                    FOREIGN KEY (page_id) REFERENCES pages(id)
                );

                -- 实体提及表
                CREATE TABLE IF NOT EXISTS entity_mentions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id TEXT NOT NULL,
                    entity_name TEXT NOT NULL,
                    context TEXT,
                    timestamp REAL DEFAULT 0,
                    FOREIGN KEY (page_id) REFERENCES pages(id)
                );

                -- 索引
                CREATE INDEX IF NOT EXISTS idx_pages_category ON pages(category);
                CREATE INDEX IF NOT EXISTS idx_pages_title ON pages(title);
                CREATE INDEX IF NOT EXISTS idx_timeline_page ON timeline(page_id);
                CREATE INDEX IF NOT EXISTS idx_timeline_time ON timeline(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_mentions_entity ON entity_mentions(entity_name);
            """)
            conn.commit()
        finally:
            conn.close()

    # === 核心 CRUD ===

    def create_page(
        self,
        title: str,
        category: MemoryCategory = MemoryCategory.UNCLASSIFIED,
        content: str = "",
        source: str = "system",
        source_type: EvidenceSource = EvidenceSource.MANUAL_ENTRY,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> BrainPage:
        """
        创建新记忆页面

        Args:
            title: 页面标题
            category: 记忆分类
            content: 初始内容（会作为第一条 Timeline）
            source: 来源描述
            source_type: 来源类型
            tags: 标签列表

        Returns:
            创建的 BrainPage 对象
        """
        with self._lock:
            page = BrainPage(
                title=title,
                category=category,
                tags=tags or [],
                metadata=metadata or {}
            )

            # 添加初始时间线条目
            if content:
                page.add_timeline_entry(
                    content=content,
                    source=source,
                    source_type=source_type
                )

            # 保存
            self._save_page(page)
            return page

    def get_page(self, page_id: str) -> Optional[BrainPage]:
        """获取记忆页面"""
        page_path = self.pages_dir / f"{page_id}.md"
        if not page_path.exists():
            return None

        markdown = page_path.read_text(encoding="utf-8")
        return BrainPage.from_markdown(markdown, page_id)

    def update_page(self, page: BrainPage, updated_by: str = "system") -> BrainPage:
        """
        更新记忆页面

        注意：只更新 Compiled Truth，不修改 Timeline
        """
        page.last_modified = time.time()
        self._save_page(page)
        return page

    def delete_page(self, page_id: str) -> bool:
        """删除记忆页面"""
        with self._lock:
            page_path = self.pages_dir / f"{page_id}.md"
            if page_path.exists():
                page_path.unlink()

            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("DELETE FROM pages WHERE id = ?", (page_id,))
                conn.execute("DELETE FROM timeline WHERE page_id = ?", (page_id,))
                conn.execute("DELETE FROM entity_mentions WHERE page_id = ?", (page_id,))
                conn.commit()
                return True
            finally:
                conn.close()

        return False

    def _save_page(self, page: BrainPage):
        """保存页面到磁盘和数据库"""
        with self._lock:
            # 1. 保存 Markdown 文件
            page_path = self.pages_dir / f"{page.id}.md"
            page_path.write_text(page.to_markdown(), encoding="utf-8")

            # 2. 更新索引数据库
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO pages
                    (id, title, category, compiled_summary, key_points, tags, aliases,
                     cross_refs, created_at, last_modified, timeline_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    page.id,
                    page.title,
                    page.category.value,
                    page.compiled_truth.summary,
                    json.dumps(page.compiled_truth.key_points),
                    json.dumps(page.tags),
                    json.dumps(page.aliases),
                    json.dumps(page.cross_references),
                    page.created_at,
                    page.last_modified,
                    len(page.timeline)
                ))
                conn.commit()

                # 3. 更新 FTS 索引
                self._update_fts_index(page)

            finally:
                conn.close()

    def _update_fts_index(self, page: BrainPage):
        """更新全文搜索索引"""
        # 删除旧索引
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("DELETE FROM pages_fts WHERE id = ?", (page.id,))

            # 插入新索引
            keywords = " ".join(page.compiled_truth.key_points)
            tags_str = " ".join(page.tags)
            conn.execute("""
                INSERT INTO pages_fts (id, title, compiled_summary, key_points, tags)
                VALUES (?, ?, ?, ?, ?)
            """, (
                page.id,
                page.title,
                page.compiled_truth.summary,
                keywords,
                tags_str
            ))
            conn.commit()
        finally:
            conn.close()

    # === Timeline 操作 ===

    def append_timeline(
        self,
        page_id: str,
        content: str,
        source: str,
        source_type: EvidenceSource = EvidenceSource.MANUAL_ENTRY,
        context: str = ""
    ) -> Optional[TimelineEntry]:
        """
        追加时间线条目（Append-only）

        Args:
            page_id: 页面 ID
            content: 内容
            source: 来源描述
            source_type: 来源类型
            context: 上下文

        Returns:
            新建的 TimelineEntry，如果页面不存在则返回 None
        """
        page = self.get_page(page_id)
        if not page:
            return None

        entry = page.add_timeline_entry(
            content=content,
            source=source,
            source_type=source_type,
            context=context
        )

        # 更新 Compiled Truth（重新编译）
        self._recompile_truth(page)

        # 保存
        self._save_page(page)

        # 更新 Timeline 索引
        self._index_timeline_entry(page_id, entry)

        return entry

    def _recompile_truth(self, page: BrainPage):
        """
        重新编译 Compiled Truth

        基于 Timeline 中的证据，生成新的 summary 和 key_points
        """
        # TODO: 将来可以用 LLM 来自动生成
        # 目前简化为：取最新的几条 Timeline 内容作为 summary

        if not page.timeline:
            return

        # 取最近 3 条的内容作为摘要
        recent = page.timeline[-3:]
        summaries = [e.content[:100] for e in recent]

        if not page.compiled_truth.summary:
            page.compiled_truth.summary = "; ".join(summaries)
        else:
            # 追加新信息
            page.compiled_truth.summary = page.compiled_truth.summary + "\n" + "; ".join(summaries)

        page.compiled_truth.last_updated = time.time()
        page.compiled_truth.updated_by = "system"

    def _index_timeline_entry(self, page_id: str, entry: TimelineEntry):
        """索引时间线条目"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                INSERT INTO timeline (page_id, timestamp, source, source_type, content, context)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                page_id,
                entry.timestamp,
                entry.source,
                entry.source_type.value,
                entry.content,
                entry.context
            ))
            conn.commit()
        finally:
            conn.close()

    # === 高级操作 ===

    def merge_pages(self, source_id: str, target_id: str, delete_source: bool = True) -> Optional[BrainPage]:
        """
        合并两个记忆页面

        将 source 的 Timeline 合并到 target，并更新 Compiled Truth
        """
        source = self.get_page(source_id)
        target = self.get_page(target_id)

        if not source or not target:
            return None

        # 合并 Timeline
        for entry in source.timeline:
            target.add_timeline_entry(
                content=f"[合并自 {source.title}] {entry.content}",
                source=f"{entry.source} (via merge)",
                source_type=EvidenceSource.MANUAL_ENTRY,
                context=entry.context
            )

        # 合并标签
        for tag in source.tags:
            if tag not in target.tags:
                target.tags.append(tag)

        # 重新编译
        self._recompile_truth(target)

        # 保存
        self._save_page(target)

        # 删除源页面
        if delete_source:
            self.delete_page(source_id)

        return target

    def link_pages(self, page_id1: str, page_id2: str) -> bool:
        """建立两个页面的交叉引用"""
        page1 = self.get_page(page_id1)
        page2 = self.get_page(page_id2)

        if not page1 or not page2:
            return False

        if page_id2 not in page1.cross_references:
            page1.cross_references.append(page_id2)
        if page_id1 not in page2.cross_references:
            page2.cross_references.append(page_id1)

        self._save_page(page1)
        self._save_page(page2)

        return True

    def unlink_pages(self, page_id1: str, page_id2: str) -> bool:
        """解除两个页面的交叉引用"""
        page1 = self.get_page(page_id1)
        page2 = self.get_page(page_id2)

        if not page1 or not page2:
            return False

        if page_id2 in page1.cross_references:
            page1.cross_references.remove(page_id2)
        if page_id1 in page2.cross_references:
            page2.cross_references.remove(page_id1)

        self._save_page(page1)
        self._save_page(page2)

        return True

    # === 分类和标签 ===

    def get_pages_by_category(self, category: MemoryCategory) -> List[BrainPage]:
        """获取指定分类的所有页面"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute("""
                SELECT id FROM pages WHERE category = ? ORDER BY last_modified DESC
            """, (category.value,)).fetchall()

            pages = []
            for row in rows:
                page = self.get_page(row[0])
                if page:
                    pages.append(page)

            return pages
        finally:
            conn.close()

    def get_pages_by_tag(self, tag: str) -> List[BrainPage]:
        """获取包含指定标签的所有页面"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute("""
                SELECT id FROM pages WHERE tags LIKE ? ORDER BY last_modified DESC
            """, (f"%{tag}%",)).fetchall()

            pages = []
            for row in rows:
                page = self.get_page(row[0])
                if page:
                    pages.append(page)

            return pages
        finally:
            conn.close()

    def add_tag(self, page_id: str, tag: str) -> bool:
        """为页面添加标签"""
        page = self.get_page(page_id)
        if not page:
            return False

        if tag not in page.tags:
            page.tags.append(tag)
            self._save_page(page)

        return True

    def remove_tag(self, page_id: str, tag: str) -> bool:
        """移除页面标签"""
        page = self.get_page(page_id)
        if not page:
            return False

        if tag in page.tags:
            page.tags.remove(tag)
            self._save_page(page)

        return True

    # === 别名管理 ===

    def add_alias(self, page_id: str, alias: str) -> bool:
        """为页面添加别名"""
        page = self.get_page(page_id)
        if not page:
            return False

        if alias not in page.aliases:
            page.aliases.append(alias)
            self._save_page(page)

        return True

    def find_page_by_alias(self, alias: str) -> Optional[BrainPage]:
        """通过别名查找页面"""
        page_path = self.pages_dir / f"{alias}.md"
        if page_path.exists():
            return self.get_page(alias)

        # 搜索数据库
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute("""
                SELECT id FROM pages WHERE aliases LIKE ?
            """, (f"%{alias}%",)).fetchone()

            if row:
                return self.get_page(row[0])
        finally:
            conn.close()

        return None

    # === 统计和查询 ===

    def get_all_pages(self, limit: int = 100, offset: int = 0) -> List[BrainPage]:
        """获取所有页面"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute("""
                SELECT id FROM pages ORDER BY last_modified DESC LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()

            pages = []
            for row in rows:
                page = self.get_page(row[0])
                if page:
                    pages.append(page)

            return pages
        finally:
            conn.close()

    def get_page_count(self) -> Dict[str, int]:
        """获取各分类的页面数量"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute("""
                SELECT category, COUNT(*) as count FROM pages GROUP BY category
            """).fetchall()

            result = {cat.value: 0 for cat in MemoryCategory}
            for category, count in rows:
                result[category] = count

            return result
        finally:
            conn.close()

    def get_recent_pages(self, limit: int = 10) -> List[BrainPage]:
        """获取最近修改的页面"""
        return self.get_all_pages(limit=limit, offset=0)

    def get_page_timeline(self, page_id: str, limit: int = 50) -> List[TimelineEntry]:
        """获取页面的 Timeline"""
        page = self.get_page(page_id)
        if not page:
            return []

        return page.timeline[-limit:]

    def search_pages(
        self,
        keywords: List[str],
        category: MemoryCategory = None,
        tags: List[str] = None
    ) -> List[BrainPage]:
        """搜索页面"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            query_parts = []
            params = []

            # FTS 搜索
            if keywords:
                fts_query = " OR ".join(f'"{kw}"' for kw in keywords)
                fts_results = conn.execute("""
                    SELECT id FROM pages_fts WHERE pages_fts MATCH ?
                """, (fts_query,)).fetchall()

                if fts_results:
                    ids = [r[0] for r in fts_results]
                    placeholders = ",".join("?" * len(ids))
                    query_parts.append(f"id IN ({placeholders})")
                    params.extend(ids)
                else:
                    return []

            # 分类过滤
            if category:
                query_parts.append("category = ?")
                params.append(category.value)

            # 标签过滤
            if tags:
                for tag in tags:
                    query_parts.append("tags LIKE ?")
                    params.append(f"%{tag}%")

            if not query_parts:
                return self.get_all_pages()

            query = "SELECT id FROM pages WHERE " + " AND ".join(query_parts)
            rows = conn.execute(query, params).fetchall()

            pages = []
            for row in rows:
                page = self.get_page(row[0])
                if page:
                    pages.append(page)

            return pages
        finally:
            conn.close()

    # === 导出和导入 ===

    def export_page(self, page_id: str, format: str = "markdown") -> str:
        """导出页面"""
        page = self.get_page(page_id)
        if not page:
            return ""

        if format == "markdown":
            return page.to_markdown()
        elif format == "json":
            return json.dumps(page.to_dict(), ensure_ascii=False, indent=2)

        return ""

    def import_page(self, content: str, format: str = "markdown") -> Optional[BrainPage]:
        """导入页面"""
        if format == "markdown":
            page = BrainPage.from_markdown(content)
        elif format == "json":
            data = json.loads(content)
            page = BrainPage.from_dict(data)
        else:
            return None

        # 检查是否已存在
        existing = self.get_page(page.id)
        if existing:
            # 合并
            return self.merge_pages(page.id, existing.id, delete_source=True)
        else:
            self._save_page(page)
            return page

    # === 健康检查 ===

    def check_health(self) -> Dict[str, Any]:
        """检查记忆系统健康状态"""
        issues = []

        # 1. 检查孤立页面（没有被引用的页面）
        conn = sqlite3.connect(str(self.db_path))
        try:
            orphaned = conn.execute("""
                SELECT COUNT(*) FROM pages p
                WHERE NOT EXISTS (
                    SELECT 1 FROM pages WHERE cross_refs LIKE '%' || p.id || '%'
                )
            """).fetchone()[0]

            if orphaned > 10:
                issues.append(f"有 {orphaned} 个孤立页面（未被引用）")
        finally:
            conn.close()

        # 2. 检查空页面（没有 Timeline）
        empty_pages = conn.execute("""
            SELECT COUNT(*) FROM pages WHERE timeline_count = 0
        """).fetchone()[0]

        if empty_pages > 5:
            issues.append(f"有 {empty_pages} 个空页面（没有 Timeline）")

        return {
            "total_pages": self.get_page_count(),
            "issues": issues,
            "healthy": len(issues) == 0
        }
