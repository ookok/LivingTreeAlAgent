"""
Distributed Index - 分布式倒排索引
==================================

功能：
- 词项索引
- 板块索引
- 作者索引
- 分布式查询

Author: LivingTreeAI Community
"""

import hashlib
import re
import time
import json
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any, List, Dict, Set
from enum import Enum
from collections import defaultdict
import math


# 停用词列表
STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这",
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
}


@dataclass
class IndexEntry:
    """索引条目"""
    term: str
    content_id: str
    position: int  # 出现位置
    field: str = "body"  # 出现字段：title/body/tag
    weight: float = 1.0  # 权重


@dataclass
class SearchQuery:
    """搜索查询"""
    query: str
    filters: Dict = field(default_factory=dict)
    limit: int = 20
    offset: int = 0
    content_types: Optional[List[str]] = None
    boards: Optional[List[str]] = None
    authors: Optional[List[str]] = None
    time_range: Optional[tuple] = None  # (start_time, end_time)


@dataclass
class SearchResult:
    """搜索结果"""
    content_id: str
    score: float
    content: Optional[Any] = None
    highlights: List[str] = field(default_factory=list)
    rank: int = 0


class DistributedInvertedIndex:
    """
    分布式倒排索引

    功能：
    1. 本地索引维护
    2. 词项/板块/作者索引
    3. 分片策略
    4. 搜索结果排序
    """

    # 分片配置
    TOTAL_SHARDS = 256  # 总分片数

    def __init__(
        self,
        node_id: str,
        get_content_func: Optional[Callable[[str], Any]] = None,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
    ):
        self.node_id = node_id

        # 本地索引
        self.term_to_docs: Dict[str, Set[str]] = defaultdict(set)  # 词项→文档
        self.doc_to_terms: Dict[str, Set[str]] = defaultdict(set)  # 文档→词项
        self.board_index: Dict[str, Set[str]] = defaultdict(set)  # 板块→文档
        self.author_index: Dict[str, Set[str]] = defaultdict(set)  # 作者→文档
        self.type_index: Dict[str, Set[str]] = defaultdict(set)  # 类型→文档

        # 元数据
        self.doc_metadata: Dict[str, Dict] = {}  # 文档元数据
        self.doc_timestamps: Dict[str, float] = {}  # 文档时间

        # 索引分片
        self.assigned_shards: Set[int] = set()  # 本节点负责的分片

        # 网络函数
        self._get_content = get_content_func
        self._send_func = send_func

        # 配置
        self.config = {
            "min_term_length": 2,
            "max_terms_per_doc": 1000,
            "index_shards": True,
        }

    # ========== 分片策略 ==========

    def _get_term_shard(self, term: str) -> int:
        """获取词项所属分片（一致性哈希）"""
        term_hash = hashlib.sha256(term.encode()).hexdigest()
        shard_id = int(term_hash[:8], 16) % self.TOTAL_SHARDS
        return shard_id

    def _get_my_shards(self) -> Set[int]:
        """获取本节点负责的分片"""
        # 简化：基于节点ID确定分片范围
        node_hash = int(hashlib.sha256(self.node_id.encode()).hexdigest()[:8], 16)
        base = node_hash % self.TOTAL_SHARDS
        # 每个节点负责 TOTAL_SHARDS / 节点数 个分片
        # 这里简化处理，假设每个节点负责多个分片
        return {(base + i) % self.TOTAL_SHARDS for i in range(16)}

    def _is_my_shard(self, term: str) -> bool:
        """判断词项是否属于本节点"""
        if not self.config["index_shards"]:
            return True
        shard = self._get_term_shard(term)
        return shard in self._get_my_shards()

    # ========== 索引构建 ==========

    async def index_content(self, content: Any):
        """
        索引内容

        Args:
            content: Content 对象
        """
        if not content.content_id:
            content.content_id = content.compute_id()

        # 提取词项
        terms = self._extract_terms(content.title + " " + content.body)

        # 限制词项数量
        if len(terms) > self.config["max_terms_per_doc"]:
            terms = terms[:self.config["max_terms_per_doc"]]

        # 词项索引
        for i, term in enumerate(terms):
            # 确定负责分片
            if self._is_my_shard(term):
                self.term_to_docs[term].add(content.content_id)
                self.doc_to_terms[content.content_id].add(term)

        # 元数据索引
        if content.board:
            self.board_index[content.board].add(content.content_id)
        if content.author:
            self.author_index[content.author].add(content.content_id)
        self.type_index[content.type.value].add(content.content_id)

        # 元数据
        self.doc_metadata[content.content_id] = {
            "type": content.type.value,
            "author": content.author,
            "title": content.title,
            "board": content.board,
            "tags": content.tags,
            "timestamp": content.timestamp,
        }
        self.doc_timestamps[content.content_id] = content.timestamp

    def _extract_terms(self, text: str, is_query: bool = False) -> List[str]:
        """
        提取词项

        Args:
            text: 文本
            is_query: 是否为查询（查询时不使用停用词过滤）

        Returns:
            词项列表
        """
        if not text:
            return []

        # 分词（简单的中文按字符，英文按空格）
        # 实际应该使用jieba等分词库
        terms = []

        # 简单分词
        current_term = ""
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                # 中文字符
                if current_term:
                    terms.append(current_term.lower())
                    current_term = ""
                terms.append(char)
            elif char.isalnum():
                current_term += char
            else:
                if current_term:
                    terms.append(current_term.lower())
                    current_term = ""

        if current_term:
            terms.append(current_term.lower())

        # 停用词过滤
        if not is_query:
            terms = [t for t in terms if t not in STOP_WORDS and len(t) >= self.config["min_term_length"]]

        return terms

    def remove_content(self, content_id: str):
        """移除内容索引"""
        # 移除词项索引
        terms = self.doc_to_terms.pop(content_id, set())
        for term in terms:
            self.term_to_docs[term].discard(content_id)

        # 移除元数据索引
        metadata = self.doc_metadata.pop(content_id, {})
        if metadata.get("board"):
            self.board_index[metadata["board"]].discard(content_id)
        if metadata.get("author"):
            self.author_index[metadata["author"]].discard(content_id)
        if metadata.get("type"):
            self.type_index[metadata["type"]].discard(content_id)

        self.doc_timestamps.pop(content_id, None)

    # ========== 搜索 ==========

    async def search(self, query: SearchQuery) -> List[SearchResult]:
        """
        搜索内容

        Args:
            query: 搜索查询

        Returns:
            搜索结果列表
        """
        # 1. 解析查询词
        query_terms = self._extract_terms(query.query, is_query=True)
        if not query_terms:
            return []

        # 2. 确定需要查询的分片
        shards_to_query = set()
        for term in query_terms:
            shard = self._get_term_shard(term)
            shards_to_query.add(shard)

        # 3. 收集结果
        all_doc_scores: Dict[str, float] = defaultdict(float)

        for term in query_terms:
            shard = self._get_term_shard(term)

            if self._is_my_shard(term):
                # 本地查询
                docs = self.term_to_docs.get(term, set())
                for doc_id in docs:
                    # TF-IDF 风格评分
                    tf = len([t for t in self.doc_to_terms.get(doc_id, []) if t == term])
                    idf = math.log(self._get_total_docs() / (len(docs) + 1))
                    score = (1 + math.log(tf)) * idf if tf > 0 else 0
                    all_doc_scores[doc_id] += score
            else:
                # 远程查询
                remote_scores = await self._query_remote_shard(shard, term)
                for doc_id, score in remote_scores.items():
                    all_doc_scores[doc_id] += score

        # 4. 应用过滤
        filtered_scores = self._apply_filters(all_doc_scores, query)

        # 5. 排序
        sorted_docs = sorted(
            filtered_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # 6. 构建结果
        results = []
        for rank, (doc_id, score) in enumerate(sorted_docs[query.offset:query.offset + query.limit]):
            result = SearchResult(
                content_id=doc_id,
                score=score,
                rank=rank + 1,
            )

            # 获取内容（如果需要）
            if self._get_content:
                result.content = await self._get_content(doc_id)

            # 高亮
            result.highlights = self._generate_highlights(doc_id, query_terms)

            results.append(result)

        return results

    def _get_total_docs(self) -> int:
        """获取总文档数"""
        return len(self.doc_metadata)

    def _apply_filters(
        self,
        doc_scores: Dict[str, float],
        query: SearchQuery
    ) -> Dict[str, float]:
        """应用过滤条件"""
        filtered = {}

        for doc_id, score in doc_scores.items():
            metadata = self.doc_metadata.get(doc_id, {})
            if not metadata:
                continue

            # 内容类型过滤
            if query.content_types:
                if metadata.get("type") not in query.content_types:
                    continue

            # 板块过滤
            if query.boards:
                if metadata.get("board") not in query.boards:
                    continue

            # 作者过滤
            if query.authors:
                if metadata.get("author") not in query.authors:
                    continue

            # 时间范围过滤
            if query.time_range:
                start, end = query.time_range
                ts = self.doc_timestamps.get(doc_id, 0)
                if ts < start or ts > end:
                    continue

            filtered[doc_id] = score

        return filtered

    def _generate_highlights(self, doc_id: str, terms: List[str]) -> List[str]:
        """生成高亮片段"""
        metadata = self.doc_metadata.get(doc_id, {})
        title = metadata.get("title", "")

        highlights = []
        for term in terms:
            if term in title.lower():
                highlights.append(f"...{title}...")
                break

        return highlights[:2]

    async def _query_remote_shard(self, shard_id: int, term: str) -> Dict[str, float]:
        """查询远程分片"""
        if not self._send_func:
            return {}

        # 简化实现：实际需要发送到负责该分片的节点
        return {}

    # ========== 索引同步 ==========

    async def get_index_digest(self) -> dict:
        """获取索引摘要（用于同步）"""
        return {
            "term_count": len(self.term_to_docs),
            "doc_count": len(self.doc_metadata),
            "board_count": len(self.board_index),
            "author_count": len(self.author_index),
            "shards": list(self._get_my_shards()),
        }

    async def merge_remote_index(self, remote_digest: dict, term_docs: dict):
        """合并远程索引"""
        # 简化实现
        for term, doc_ids in term_docs.items():
            if self._is_my_shard(term):
                self.term_to_docs[term].update(doc_ids)

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取索引统计"""
        return {
            "total_terms": len(self.term_to_docs),
            "total_docs": len(self.doc_metadata),
            "boards": {
                board: len(docs)
                for board, docs in self.board_index.items()
            },
            "assigned_shards": list(self._get_my_shards()),
        }


# 全局单例
_index_instance: Optional[DistributedInvertedIndex] = None


def get_distributed_index(node_id: str = "local") -> DistributedInvertedIndex:
    """获取分布式索引单例"""
    global _index_instance
    if _index_instance is None:
        _index_instance = DistributedInvertedIndex(node_id)
    return _index_instance