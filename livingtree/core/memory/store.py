"""
LivingTree 统一智能存储
======================

基于 unified_memory.py 的 IMemorySystem 接口，实现统一的 MemoryStore。
整合 VectorDB + GraphDB + SessionStore，支持多级记忆路由和自适应检索。

核心特性：
- 多级记忆路由：短期(最近) → 中期(频繁) → 长期(重要)
- 相关性评分：TF-IDF 启发式 + n-gram 匹配
- 重要性评分：recency / frequency / emotional-weight 三因子模型
- 上下文窗口优化：Token 感知截断 + 优先级排序
- TTL 过期机制：自动清理过期记忆
- 记忆合并：相似记忆的自动去重与合并
- 查询规划：根据意图分配不同记忆源权重
"""

import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple


class MemoryType(Enum):
    SHORT_TERM = "short_term"
    MID_TERM = "mid_term"
    LONG_TERM = "long_term"
    VECTOR = "vector"
    GRAPH = "graph"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryLevel(Enum):
    L0_CACHE = 0
    L1_SHORT = 1
    L2_MID = 2
    L3_LONG = 3
    L4_ARCHIVE = 4


@dataclass
class MemoryQuery:
    text: str = ""
    keywords: List[str] = field(default_factory=list)
    memory_types: List[MemoryType] = field(default_factory=list)
    limit: int = 10
    min_relevance: float = 0.3
    include_metadata: bool = False
    strategy: str = "auto"


@dataclass
class MemoryItem:
    id: str = ""
    content: str = ""
    memory_type: MemoryType = MemoryType.MID_TERM
    level: MemoryLevel = MemoryLevel.L2_MID
    source: str = ""
    relevance: float = 0.0
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    ttl_seconds: Optional[float] = None
    emotional_weight: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        if self.ttl_seconds is None:
            return False
        return (datetime.now() - self.created_at).total_seconds() > self.ttl_seconds

    @property
    def age_hours(self) -> float:
        return (datetime.now() - self.created_at).total_seconds() / 3600


@dataclass
class MemoryResult:
    items: List[MemoryItem] = field(default_factory=list)
    total_found: int = 0
    query_time_ms: float = 0.0
    sources: List[str] = field(default_factory=list)
    strategy_used: str = ""


class IMemorySystem:
    def store(self, item: MemoryItem) -> str: ...
    def search(self, query: MemoryQuery) -> MemoryResult: ...
    def delete(self, item_id: str) -> bool: ...
    def clear(self, memory_type: Optional[MemoryType] = None): ...
    def stats(self) -> Dict[str, Any]: ...


class RelevanceScorer:
    """相关性评分器 — TF-IDF 启发式 + n-gram + 语义标记."""

    def __init__(self):
        self._idf_cache: Dict[str, float] = {}
        self._doc_count: int = 0

    def score(self, query: str, document: str, metadata: Dict[str, Any] = None) -> float:
        if not query or not document:
            return 0.0

        query_lower = query.lower()
        doc_lower = document.lower()

        tf_score = self._compute_tf_score(query_lower, doc_lower)
        ngram_score = self._compute_ngram_score(query_lower, doc_lower)
        exact_bonus = 1.0 if query_lower in doc_lower else 0.0
        tag_score = self._compute_tag_score(query_lower, metadata)

        raw = tf_score * 0.4 + ngram_score * 0.3 + exact_bonus * 0.2 + tag_score * 0.1
        return min(1.0, raw)

    def _compute_tf_score(self, query_lower: str, doc_lower: str) -> float:
        query_terms = self._tokenize(query_lower)
        doc_terms = self._tokenize(doc_lower)
        if not query_terms:
            return 0.0

        doc_term_freq = Counter(doc_terms)
        score = 0.0
        for term in query_terms:
            tf = doc_term_freq.get(term, 0)
            if tf > 0:
                idf = self._idf_cache.get(term, 1.0)
                score += (1 + math.log(tf)) * idf
        return score / (len(query_terms) * 3.0)

    def _compute_ngram_score(self, query_lower: str, doc_lower: str) -> float:
        q_ngrams = set(self._char_ngrams(query_lower, 3))
        d_ngrams = set(self._char_ngrams(doc_lower, 3))
        if not q_ngrams:
            return 0.0
        intersection = q_ngrams & d_ngrams
        return len(intersection) / len(q_ngrams)

    def _compute_tag_score(self, query_lower: str,
                           metadata: Dict[str, Any] = None) -> float:
        if not metadata:
            return 0.0
        tags = metadata.get("tags", [])
        if not tags:
            return 0.0
        matches = sum(1 for t in tags if t.lower() in query_lower)
        return min(1.0, matches / max(1, len(tags)))

    def update_idf(self, all_documents: List[str]):
        self._doc_count = len(all_documents)
        df: Dict[str, int] = {}
        for doc in all_documents:
            for term in set(self._tokenize(doc.lower())):
                df[term] = df.get(term, 0) + 1
        for term, count in df.items():
            self._idf_cache[term] = math.log((self._doc_count + 1) / (count + 1)) + 1

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", text)
        return [t for t in tokens if len(t) >= 2]

    @staticmethod
    def _char_ngrams(text: str, n: int = 3) -> List[str]:
        return [text[i:i + n] for i in range(max(0, len(text) - n + 1))]


class ImportanceScorer:
    """重要性评分 — recency + frequency + emotional_weight 三因子模型."""

    def __init__(self, recency_weight: float = 0.3,
                 frequency_weight: float = 0.3,
                 emotional_weight: float = 0.2,
                 length_weight: float = 0.2):
        self.recency_weight = recency_weight
        self.frequency_weight = frequency_weight
        self.emotional_weight = emotional_weight
        self.length_weight = length_weight

    def score(self, item: MemoryItem) -> float:
        recency = self._recency_score(item)
        frequency = self._frequency_score(item)
        emotional = item.emotional_weight
        length = self._length_score(item)

        total = (recency * self.recency_weight +
                 frequency * self.frequency_weight +
                 emotional * self.emotional_weight +
                 length * self.length_weight)
        return round(min(1.0, total), 4)

    def _recency_score(self, item: MemoryItem) -> float:
        hours = item.age_hours
        if hours < 1:
            return 1.0
        elif hours < 24:
            return 0.8
        elif hours < 168:
            return 0.5
        elif hours < 720:
            return 0.2
        return 0.05

    def _frequency_score(self, item: MemoryItem) -> float:
        if item.access_count == 0:
            return 0.0
        return min(1.0, math.log(item.access_count + 1) / math.log(10))

    def _length_score(self, item: MemoryItem) -> float:
        length = len(item.content)
        if length < 100:
            return 0.1
        elif length < 500:
            return 0.4
        elif length < 2000:
            return 0.7
        return 1.0


class QueryPlanner:
    """查询规划器 — 根据意图和策略分配不同记忆源的权重."""

    STRATEGIES: Dict[str, Dict[str, float]] = {
        "auto": {"short_term": 1.0, "mid_term": 0.5, "long_term": 0.3, "vector": 0.5, "graph": 0.3},
        "recent": {"short_term": 1.0, "mid_term": 0.5, "vector": 0.3},
        "deep": {"short_term": 0.3, "mid_term": 0.8, "long_term": 1.0, "vector": 1.0, "graph": 0.8},
        "knowledge": {"long_term": 1.0, "graph": 1.0, "vector": 0.5},
        "fast": {"short_term": 1.0, "vector": 0.5},
    }

    def __init__(self, default_strategy: str = "auto"):
        self.default_strategy = default_strategy

    def plan(self, query: MemoryQuery) -> Dict[str, float]:
        strategy = query.strategy or self.default_strategy
        return self.STRATEGIES.get(strategy, self.STRATEGIES["auto"])


class SimpleVectorDB:
    """向量数据库 — 使用 TF-IDF 启发式评分 + n-gram 匹配."""

    def __init__(self, dim: int = 768):
        self._items: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        self._scorer = RelevanceScorer()

    def add(self, item_id: str, text: str, metadata: Dict[str, Any] = None):
        with self._lock:
            self._items[item_id] = {
                "id": item_id,
                "text": text,
                "metadata": metadata or {},
                "created_at": datetime.now(),
            }
            if self._scorer:
                self._scorer.update_idf(
                    [item["text"] for item in self._items.values()])

    def search(self, query: str, limit: int = 10,
               min_relevance: float = 0.0) -> List[Dict[str, Any]]:
        if not self._scorer:
            return []
        results = []
        query_lower = query.lower()
        with self._lock:
            for item_id, item in self._items.items():
                relevance = self._scorer.score(
                    query, item["text"], item.get("metadata"))
                if relevance >= min_relevance:
                    item["relevance"] = relevance
                    results.append(item)
                elif any(kw in item["text"].lower() for kw in query_lower.split()):
                    fallback = 0.3
                    item["relevance"] = fallback
                    results.append(item)

        results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        return results[:limit]

    def search_by_keywords(self, keywords: List[str],
                           limit: int = 10) -> List[Dict[str, Any]]:
        results = []
        with self._lock:
            for item_id, item in self._items.items():
                text_lower = item["text"].lower()
                score = sum(1 for kw in keywords if kw.lower() in text_lower)
                if score > 0:
                    item["relevance"] = score / len(keywords)
                    results.append(item)
        results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        return results[:limit]

    def count(self) -> int:
        return len(self._items)

    def remove_expired(self, ttl_seconds: float):
        deadline = datetime.now() - timedelta(seconds=ttl_seconds)
        with self._lock:
            expired = [k for k, v in self._items.items()
                       if v.get("created_at", datetime.now()) < deadline]
            for k in expired:
                del self._items[k]


class SimpleGraphDB:
    """知识图谱 — 多深度查询 + 关系推理."""

    def __init__(self):
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Tuple[str, str, str]] = []
        self._lock = Lock()

    def add_node(self, node_id: str, label: str,
                 properties: Dict[str, Any] = None):
        with self._lock:
            self._nodes[node_id] = {
                "id": node_id, "label": label,
                "properties": properties or {},
            }

    def add_edge(self, from_id: str, to_id: str,
                 relation: str = "RELATED_TO"):
        with self._lock:
            self._edges.append((from_id, to_id, relation))

    def query_related(self, node_id: str, depth: int = 1) -> List[Dict[str, Any]]:
        results = []
        visited = {node_id}
        current_layer = {node_id}

        for _ in range(depth):
            next_layer = set()
            for from_id, to_id, relation in self._edges:
                if from_id in current_layer and to_id not in visited:
                    if to_id in self._nodes:
                        results.append({"node": self._nodes[to_id], "relation": relation})
                    next_layer.add(to_id)
                    visited.add(to_id)
                elif to_id in current_layer and from_id not in visited:
                    if from_id in self._nodes:
                        results.append({"node": self._nodes[from_id], "relation": relation})
                    next_layer.add(from_id)
                    visited.add(from_id)
            current_layer = next_layer
            if not current_layer:
                break

        return results

    def search_nodes(self, keyword: str) -> List[Dict[str, Any]]:
        results = []
        kw = keyword.lower()
        for node in self._nodes.values():
            label = node.get("label", "").lower()
            props = {k: str(v).lower() for k, v in
                     node.get("properties", {}).items()}
            if kw in label or kw in str(props):
                results.append(node)
        return results

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)


class SessionStore:
    """会话存储 — 支持多会话隔离和时间范围查询."""

    def __init__(self):
        self._sessions: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = Lock()

    def create_session(self, session_id: str) -> str:
        with self._lock:
            self._sessions[session_id] = []
        return session_id

    def add_message(self, session_id: str, role: str, content: str):
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = []
            self._sessions[session_id].append({
                "role": role, "content": content,
                "timestamp": datetime.now(),
            })

    def get_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        msgs = self._sessions.get(session_id, [])
        return msgs[-limit:]

    def get_recent(self, session_id: str,
                   minutes: int = 60) -> List[Dict[str, Any]]:
        msgs = self._sessions.get(session_id, [])
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return [m for m in msgs if m.get("timestamp", datetime.min) > cutoff]

    def delete_session(self, session_id: str):
        with self._lock:
            self._sessions.pop(session_id, None)

    def active_sessions(self) -> int:
        return len(self._sessions)


class MemoryStore(IMemorySystem):
    """统一记忆存储 — 多级记忆路由中枢.

    层级设计 (L0-L4):
    L0_CACHE  — 内存热缓存 (< 1h)
    L1_SHORT  — 短期工作记忆 (< 24h)
    L2_MID    — 中期频繁记忆 (< 7d)
    L3_LONG   — 长期知识 (> 7d)
    L4_ARCHIVE — 归档冷数据

    每级保留不同的分桶和过期策略.
    """

    DEFAULT_TTL: Dict[MemoryLevel, Optional[float]] = {
        MemoryLevel.L0_CACHE: 3600,
        MemoryLevel.L1_SHORT: 86400,
        MemoryLevel.L2_MID: 604800,
        MemoryLevel.L3_LONG: 2592000,
        MemoryLevel.L4_ARCHIVE: None,
    }

    LEVEL_CAPACITY: Dict[MemoryLevel, int] = {
        MemoryLevel.L0_CACHE: 50,
        MemoryLevel.L1_SHORT: 200,
        MemoryLevel.L2_MID: 500,
        MemoryLevel.L3_LONG: 2000,
        MemoryLevel.L4_ARCHIVE: 10000,
    }

    def __init__(self):
        self._items: Dict[str, MemoryItem] = {}
        self.vector_db = SimpleVectorDB()
        self.graph_db = SimpleGraphDB()
        self.sessions = SessionStore()
        self._lock = Lock()

        self._scorer = RelevanceScorer()
        self._importance_scorer = ImportanceScorer()
        self._planner = QueryPlanner()
        self._consolidation_threshold: float = 0.85

    def store(self, item: MemoryItem) -> str:
        if not item.id:
            item.id = f"mem_{len(self._items)}_{datetime.now().timestamp():.0f}"

        level = self._classify_level(item)
        item.level = level
        if item.ttl_seconds is None:
            item.ttl_seconds = self.DEFAULT_TTL.get(level)

        item.importance = self._importance_scorer.score(item)

        with self._lock:
            self._items[item.id] = item
            self.vector_db.add(item.id, item.content, {
                "tags": item.tags,
                "source": item.source,
                "importance": item.importance,
            })

        self._enforce_capacity(level)
        return item.id

    def store_many(self, items: List[MemoryItem]) -> List[str]:
        return [self.store(item) for item in items]

    def search(self, query: MemoryQuery) -> MemoryResult:
        start = time.time()
        weights = self._planner.plan(query)
        scored_items: List[Tuple[MemoryItem, float]] = []
        sources: List[str] = []

        if weights.get("short_term", 0) > 0:
            short_items = self._search_by_level(
                [MemoryLevel.L0_CACHE, MemoryLevel.L1_SHORT],
                query, weights["short_term"])
            scored_items.extend(short_items)
            if short_items:
                sources.append("short_term")

        if weights.get("mid_term", 0) > 0:
            mid_items = self._search_by_level(
                [MemoryLevel.L2_MID], query, weights["mid_term"])
            scored_items.extend(mid_items)
            if mid_items:
                sources.append("mid_term")

        if weights.get("long_term", 0) > 0:
            long_items = self._search_by_level(
                [MemoryLevel.L3_LONG, MemoryLevel.L4_ARCHIVE],
                query, weights["long_term"])
            scored_items.extend(long_items)
            if long_items:
                sources.append("long_term")

        if weights.get("vector", 0) > 0:
            vec_items = self._search_vector(query, weights["vector"])
            scored_items.extend(vec_items)
            if vec_items:
                sources.append("vector_db")

        if weights.get("graph", 0) > 0:
            graph_items = self._search_graph(query, weights["graph"])
            scored_items.extend(graph_items)
            if graph_items:
                sources.append("graph_db")

        if query.keywords:
            kw_items = self._search_by_keywords(query.keywords)
            scored_items.extend(kw_items)

        scored_items.sort(key=lambda x: -x[1])
        seen: set = set()
        unique: List[MemoryItem] = []
        for item, score in scored_items[:query.limit * 2]:
            if item.id not in seen:
                item.relevance = score
                unique.append(item)
                seen.add(item.id)

        return MemoryResult(
            items=unique[:query.limit],
            total_found=len(unique),
            query_time_ms=(time.time() - start) * 1000,
            sources=list(set(sources)),
            strategy_used=query.strategy or "auto",
        )

    def _search_by_level(self, levels: List[MemoryLevel],
                         query: MemoryQuery,
                         weight: float) -> List[Tuple[MemoryItem, float]]:
        results: List[Tuple[MemoryItem, float]] = []
        query_lower = query.text.lower()
        with self._lock:
            for item in self._items.values():
                if item.level not in levels:
                    continue
                if item.is_expired:
                    continue
                relevance = self._scorer.score(
                    query.text, item.content, item.metadata)
                combined = relevance * weight * item.importance
                if combined >= query.min_relevance * 0.5:
                    results.append((item, combined))
                    item.last_accessed = datetime.now()
                    item.access_count += 1
        return results

    def _search_vector(self, query: MemoryQuery,
                       weight: float) -> List[Tuple[MemoryItem, float]]:
        results: List[Tuple[MemoryItem, float]] = []
        vec_results = self.vector_db.search(
            query.text, query.limit, min_relevance=query.min_relevance * 0.5)
        with self._lock:
            for res in vec_results:
                item = self._items.get(res["id"])
                if item and not item.is_expired:
                    combined = res.get("relevance", 0) * weight * item.importance
                    results.append((item, combined))
        return results

    def _search_graph(self, query: MemoryQuery,
                      weight: float) -> List[Tuple[MemoryItem, float]]:
        results: List[Tuple[MemoryItem, float]] = []
        graph_results = self.graph_db.search_nodes(query.text)
        for node in graph_results[:query.limit]:
            mi = MemoryItem(
                id=node.get("id", ""), content=node.get("label", ""),
                memory_type=MemoryType.GRAPH, relevance=0.5,
                metadata=node.get("properties", {}),
            )
            results.append((mi, 0.5 * weight))
        return results

    def _search_by_keywords(self, keywords: List[str]) -> List[Tuple[MemoryItem, float]]:
        results: List[Tuple[MemoryItem, float]] = []
        with self._lock:
            for item in self._items.values():
                if item.is_expired:
                    continue
                content_lower = item.content.lower()
                score = sum(1 for kw in keywords if kw.lower() in content_lower)
                if score > 0:
                    results.append((item, score / len(keywords)))
        return results

    def context_window(self, query: str, max_tokens: int = 4000) -> str:
        """返回截至 max_tokens 的相关上下文文本."""
        mem_result = self.search(MemoryQuery(
            text=query, limit=20, min_relevance=0.2))
        parts: List[str] = []
        token_count = 0
        for item in mem_result.items:
            if item.is_expired:
                continue
            chunk = item.content[:800]
            est_tokens = len(chunk) // 3
            if token_count + est_tokens > max_tokens:
                break
            parts.append(chunk)
            token_count += est_tokens
        return "\n---\n".join(parts)

    def consolidate(self, similarity_threshold: float = 0.85):
        """合并相似记忆，减少冗余存储."""
        items_list = [i for i in self._items.values() if not i.is_expired]
        merged_count = 0

        for i in range(len(items_list)):
            if items_list[i].id not in self._items:
                continue
            for j in range(i + 1, len(items_list)):
                if items_list[j].id not in self._items:
                    continue
                a, b = items_list[i], items_list[j]
                sim = self._scorer.score(a.content, b.content)
                if sim >= similarity_threshold:
                    self._merge(a, b)
                    merged_count += 1

        if merged_count > 0:
            self.vector_db._scorer.update_idf(
                [item.content for item in self._items.values()])

    def _merge(self, keeper: MemoryItem, absorbed: MemoryItem):
        keeper.access_count += absorbed.access_count
        keeper.importance = max(keeper.importance, absorbed.importance)
        keeper.emotional_weight = max(keeper.emotional_weight,
                                       absorbed.emotional_weight)
        keeper.tags = list(set(keeper.tags + absorbed.tags))
        if keeper.metadata and absorbed.metadata:
            keeper.metadata.update(absorbed.metadata)
        self._items.pop(absorbed.id, None)

    def promote(self, item_id: str):
        """将记忆提升到更高的层级（更活跃）."""
        item = self._items.get(item_id)
        if not item:
            return
        current = item.level
        if current.value > MemoryLevel.L0_CACHE.value:
            new_level = MemoryLevel(current.value - 1)
            item.level = new_level
            item.ttl_seconds = self.DEFAULT_TTL.get(new_level)

    def demote(self, item_id: str):
        """将记忆降级到更低的层级（更冷）."""
        item = self._items.get(item_id)
        if not item:
            return
        current = item.level
        if current.value < MemoryLevel.L4_ARCHIVE.value:
            new_level = MemoryLevel(current.value + 1)
            item.level = new_level
            item.ttl_seconds = self.DEFAULT_TTL.get(new_level)

    def _classify_level(self, item: MemoryItem) -> MemoryLevel:
        if item.importance >= 0.8:
            return MemoryLevel.L3_LONG
        if item.importance >= 0.5:
            return MemoryLevel.L2_MID
        return MemoryLevel.L1_SHORT

    def _enforce_capacity(self, level: MemoryLevel):
        max_cap = self.LEVEL_CAPACITY.get(level, 500)
        level_items = [(kid, it) for kid, it in self._items.items()
                       if it.level == level]
        if len(level_items) <= max_cap:
            return
        level_items.sort(key=lambda x: x[1].importance)
        to_remove = level_items[:len(level_items) - max_cap]
        for kid, _ in to_remove:
            self._items.pop(kid, None)

    def cleanup_expired(self) -> int:
        """清理所有过期记忆，返回清理数量."""
        with self._lock:
            expired = [k for k, v in self._items.items() if v.is_expired]
            for k in expired:
                self._items.pop(k, None)
        self.vector_db.remove_expired(
            self.DEFAULT_TTL.get(MemoryLevel.L2_MID, 604800))
        return len(expired)

    def delete(self, item_id: str) -> bool:
        with self._lock:
            return self._items.pop(item_id, None) is not None

    def clear(self, memory_type: Optional[MemoryType] = None):
        with self._lock:
            if memory_type:
                self._items = {
                    k: v for k, v in self._items.items()
                    if v.memory_type != memory_type
                }
            else:
                self._items.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            level_counts = {}
            for item in self._items.values():
                lv = item.level.value
                level_counts[lv] = level_counts.get(lv, 0) + 1

        return {
            "total_items": len(self._items),
            "vector_count": self.vector_db.count(),
            "graph_nodes": self.graph_db.node_count,
            "graph_edges": self.graph_db.edge_count,
            "active_sessions": self.sessions.active_sessions(),
            "memory_types": {
                t.value: sum(1 for v in self._items.values()
                             if v.memory_type == t)
                for t in MemoryType
            },
            "level_distribution": level_counts,
            "expired_count": sum(1 for v in self._items.values() if v.is_expired),
            "avg_importance": (sum(v.importance for v in self._items.values()) /
                               max(1, len(self._items))),
        }

    def get_important_memories(self, top_k: int = 20) -> List[MemoryItem]:
        with self._lock:
            items = [i for i in self._items.values() if not i.is_expired]
            items.sort(key=lambda x: -x.importance)
            return items[:top_k]

    def auto_maintain(self):
        """自动维护：清理过期 + 合并相似记忆."""
        self.cleanup_expired()
        if len(self._items) > 100:
            self.consolidate(self._consolidation_threshold)


__all__ = [
    "MemoryStore",
    "IMemorySystem",
    "MemoryQuery",
    "MemoryItem",
    "MemoryResult",
    "MemoryType",
    "MemoryLevel",
    "SimpleVectorDB",
    "SimpleGraphDB",
    "SessionStore",
    "RelevanceScorer",
    "ImportanceScorer",
    "QueryPlanner",
]
