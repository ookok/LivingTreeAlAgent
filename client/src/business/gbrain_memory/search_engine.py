"""
GBrain 记忆搜索引擎
支持混合搜索：关键词 + 语义相似度 + RRF 融合排序

灵感来源：GBrain 使用 Postgres + pgvector 实现混合搜索
本实现使用 SQLite FTS5 + 关键词匹配实现类似功能
"""

import json
import sqlite3
import threading
import time
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

from core.gbrain_memory.models import (
    BrainPage, MemoryCategory, MemoryQuery, MemorySearchResult
)


class SearchEngine:
    """
    记忆搜索引擎

    支持的搜索模式：
    1. 关键词搜索 (FTS5)
    2. 分类过滤
    3. 标签过滤
    4. 时间范围过滤
    5. RRF 融合排序

    RRF (Reciprocal Rank Fusion) 是一种多结果集融合算法：
    score = sum(1 / (k + rank))
    k 通常取 60
    """

    def __init__(self, brain_dir: str | Path = None):
        from core.config import get_config_dir

        if brain_dir is None:
            brain_dir = get_config_dir() / "gbrain"

        self.brain_dir = Path(brain_dir)
        self.db_path = self.brain_dir / "gbrain.db"
        self.pages_dir = self.brain_dir / "pages"

        # RRF 参数
        self.rrf_k = 60

    def search(
        self,
        query: MemoryQuery,
        hybrid: bool = True
    ) -> List[MemorySearchResult]:
        """
        执行搜索

        Args:
            query: 搜索查询
            hybrid: 是否使用混合搜索（多策略融合）

        Returns:
            排序后的搜索结果
        """
        if hybrid:
            return self._hybrid_search(query)
        else:
            return self._simple_search(query)

    def _simple_search(self, query: MemoryQuery) -> List[MemorySearchResult]:
        """简单搜索（单一策略）"""
        results = []

        # 获取页面
        if query.page_id:
            page = self._get_page_direct(query.page_id)
            if page:
                results.append(MemorySearchResult(
                    page=page,
                    relevance_score=1.0,
                    matched_on=["page_id"],
                    snippet=page.compiled_truth.summary[:100] if page.compiled_truth.summary else ""
                ))
        else:
            pages = self._fts_search(query)
            for page in pages:
                results.append(MemorySearchResult(
                    page=page,
                    relevance_score=0.8,
                    matched_on=["fts"],
                    snippet=self._get_snippet(page, query.keywords)
                ))

        return results

    def _hybrid_search(self, query: MemoryQuery) -> List[MemorySearchResult]:
        """
        混合搜索：多策略结果融合

        策略1: FTS5 全文搜索
        策略2: 关键词匹配（标题、标签）
        策略3: 分类过滤
        """
        # 各策略的候选结果
        fts_results = self._fts_search(query)
        keyword_results = self._keyword_search(query)
        category_results = self._category_search(query)

        # 构建排名字典 {page_id: {strategy: rank}}
        rankings: Dict[str, Dict[str, int]] = {}

        for results, strategy in [
            (fts_results, "fts"),
            (keyword_results, "keyword"),
            (category_results, "category")
        ]:
            for rank, result in enumerate(results):
                page_id = result.page.id
                if page_id not in rankings:
                    rankings[page_id] = {}
                rankings[page_id][strategy] = rank + 1

        # 计算 RRF 分数
        rrf_scores: Dict[str, float] = {}
        for page_id, strategy_ranks in rankings.items():
            score = sum(
                1.0 / (self.rrf_k + rank)
                for rank in strategy_ranks.values()
            )
            rrf_scores[page_id] = score

        # 排序
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        # 构建最终结果
        final_results = []
        page_cache = {}

        for page_id in sorted_ids[:query.limit]:
            # 获取页面
            if page_id not in page_cache:
                page = self._get_page_direct(page_id)
                if page:
                    page_cache[page_id] = page

            if page_id in page_cache:
                result = MemorySearchResult(
                    page=page_cache[page_id],
                    relevance_score=rrf_scores[page_id],
                    matched_on=list(rankings[page_id].keys()),
                    snippet=self._get_snippet(page_cache[page_id], query.keywords)
                )
                final_results.append(result)

        return final_results

    def _fts_search(self, query: MemoryQuery) -> List[MemorySearchResult]:
        """FTS5 全文搜索"""
        if not query.keywords:
            return []

        conn = sqlite3.connect(str(self.db_path))
        try:
            # 构建 FTS 查询
            fts_query = " OR ".join(f'"{kw}"' for kw in query.keywords)

            rows = conn.execute("""
                SELECT id, title, compiled_summary,
                       highlight(pages_fts, 0, '<mark>', '</mark>') as title_hl,
                       highlight(pages_fts, 2, '<mark>', '</mark>') as summary_hl
                FROM pages_fts
                WHERE pages_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (fts_query, query.limit)).fetchall()

            results = []
            for row in rows:
                page = self._get_page_direct(row[0])
                if page:
                    snippet = row[4] if row[4] else (row[2][:100] if row[2] else "")
                    results.append(MemorySearchResult(
                        page=page,
                        relevance_score=1.0,
                        matched_on=["fts"],
                        snippet=snippet
                    ))

            return results
        finally:
            conn.close()

    def _keyword_search(self, query: MemoryQuery) -> List[MemorySearchResult]:
        """关键词匹配搜索"""
        if not query.keywords:
            return []

        conn = sqlite3.connect(str(self.db_path))
        try:
            conditions = []
            params = []

            for kw in query.keywords:
                conditions.append("(title LIKE ? OR tags LIKE ? OR compiled_summary LIKE ?)")
                like_kw = f"%{kw}%"
                params.extend([like_kw, like_kw, like_kw])

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            rows = conn.execute(f"""
                SELECT id FROM pages
                WHERE {where_clause}
                ORDER BY last_modified DESC
                LIMIT ?
            """, (*params, query.limit)).fetchall()

            results = []
            for row in rows:
                page = self._get_page_direct(row[0])
                if page:
                    results.append(MemorySearchResult(
                        page=page,
                        relevance_score=0.7,
                        matched_on=["keyword"],
                        snippet=self._get_snippet(page, query.keywords)
                    ))

            return results
        finally:
            conn.close()

    def _category_search(self, query: MemoryQuery) -> List[MemorySearchResult]:
        """分类搜索"""
        if not query.category:
            return []

        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute("""
                SELECT id FROM pages
                WHERE category = ?
                ORDER BY last_modified DESC
                LIMIT ?
            """, (query.category.value, query.limit)).fetchall()

            results = []
            for row in rows:
                page = self._get_page_direct(row[0])
                if page:
                    results.append(MemorySearchResult(
                        page=page,
                        relevance_score=0.5,
                        matched_on=["category"],
                        snippet=self._get_snippet(page, query.keywords)
                    ))

            return results
        finally:
            conn.close()

    def _get_page_direct(self, page_id: str) -> Optional[BrainPage]:
        """直接获取页面（不经过缓存）"""
        page_path = self.pages_dir / f"{page_id}.md"
        if not page_path.exists():
            return None

        markdown = page_path.read_text(encoding="utf-8")
        return BrainPage.from_markdown(markdown, page_id)

    def _get_snippet(self, page: BrainPage, keywords: List[str]) -> str:
        """获取匹配片段"""
        text = page.compiled_truth.summary or ""

        if not keywords:
            return text[:100] if text else ""

        # 找到第一个匹配位置
        text_lower = text.lower()
        for kw in keywords:
            pos = text_lower.find(kw.lower())
            if pos >= 0:
                start = max(0, pos - 30)
                end = min(len(text), pos + len(kw) + 50)
                snippet = text[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(text):
                    snippet = snippet + "..."
                return snippet

        return text[:100] if text else ""

    # === 高级搜索功能 ===

    def search_by_entity(self, entity_name: str) -> List[MemorySearchResult]:
        """搜索与特定实体相关的记忆"""
        query = MemoryQuery(
            keywords=[entity_name],
            limit=20
        )
        return self.search(query)

    def search_conversations(
        self,
        start_time: float = None,
        end_time: float = None,
        limit: int = 20
    ) -> List[MemorySearchResult]:
        """搜索对话记录"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conditions = ["category = 'conversations'"]
            params = []

            if start_time:
                conditions.append("last_modified >= ?")
                params.append(start_time)
            if end_time:
                conditions.append("last_modified <= ?")
                params.append(end_time)

            where_clause = " AND ".join(conditions)
            rows = conn.execute(f"""
                SELECT id FROM pages
                WHERE {where_clause}
                ORDER BY last_modified DESC
                LIMIT ?
            """, (*params, limit)).fetchall()

            results = []
            for row in rows:
                page = self._get_page_direct(row[0])
                if page:
                    results.append(MemorySearchResult(
                        page=page,
                        relevance_score=1.0,
                        matched_on=["category", "time_range"],
                        snippet=self._get_snippet(page, [])
                    ))

            return results
        finally:
            conn.close()

    def get_related_pages(self, page_id: str, limit: int = 5) -> List[MemorySearchResult]:
        """获取相关页面（基于交叉引用和共同标签）"""
        page = self._get_page_direct(page_id)
        if not page:
            return []

        results = []

        # 1. 直接引用的页面
        for ref_id in page.cross_references[:limit]:
            ref_page = self._get_page_direct(ref_id)
            if ref_page:
                results.append(MemorySearchResult(
                    page=ref_page,
                    relevance_score=0.9,
                    matched_on=["cross_reference"],
                    snippet=""
                ))

        # 2. 有共同标签的页面
        if page.tags:
            conn = sqlite3.connect(str(self.db_path))
            try:
                for tag in page.tags[:3]:
                    rows = conn.execute("""
                        SELECT id FROM pages
                        WHERE tags LIKE ? AND id != ?
                        ORDER BY last_modified DESC
                        LIMIT ?
                    """, (f"%{tag}%", page_id, 3)).fetchall()

                    for row in rows:
                        if row[0] not in page.cross_references:
                            ref_page = self._get_page_direct(row[0])
                            if ref_page:
                                results.append(MemorySearchResult(
                                    page=ref_page,
                                    relevance_score=0.6,
                                    matched_on=["shared_tag"],
                                    snippet=""
                                ))
            finally:
                conn.close()

        # 去重
        seen_ids = set()
        unique_results = []
        for r in results:
            if r.page.id not in seen_ids:
                seen_ids.add(r.page.id)
                unique_results.append(r)

        return unique_results[:limit]

    def suggest_related(self, query_text: str, limit: int = 5) -> List[str]:
        """
        根据查询文本推荐相关页面 ID

        用于自动补全和相关性建议
        """
        # 提取关键词
        keywords = self._extract_keywords(query_text)

        conn = sqlite3.connect(str(self.db_path))
        try:
            conditions = []
            params = []

            for kw in keywords:
                conditions.append("(title LIKE ? OR tags LIKE ?)")
                like_kw = f"%{kw}%"
                params.extend([like_kw, like_kw])

            if not conditions:
                return []

            where_clause = " OR ".join(conditions)
            rows = conn.execute(f"""
                SELECT id, title FROM pages
                WHERE {where_clause}
                ORDER BY last_modified DESC
                LIMIT ?
            """, (*params, limit)).fetchall()

            return [row[0] for row in rows]
        finally:
            conn.close()

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单的中英文分词
        chinese = re.findall(r'[\u4e00-\u9fa5]+', text)
        english = re.findall(r'[a-zA-Z]+', text)
        return chinese + english

    # === 统计分析 ===

    def get_search_stats(self) -> Dict[str, Any]:
        """获取搜索统计信息"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            total_pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
            total_timeline = conn.execute("SELECT COUNT(*) FROM timeline").fetchone()[0]

            # 各分类数量
            category_counts = {}
            rows = conn.execute("""
                SELECT category, COUNT(*) FROM pages GROUP BY category
            """).fetchall()
            for cat, count in rows:
                category_counts[cat] = count

            # 最近更新
            recent = conn.execute("""
                SELECT id, title, last_modified FROM pages
                ORDER BY last_modified DESC LIMIT 5
            """).fetchall()

            return {
                "total_pages": total_pages,
                "total_timeline_entries": total_timeline,
                "category_distribution": category_counts,
                "recent_pages": [
                    {"id": r[0], "title": r[1], "last_modified": r[2]}
                    for r in recent
                ]
            }
        finally:
            conn.close()
