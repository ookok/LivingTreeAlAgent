"""
私有法规库 FusionRAG 集成模块
Private Regulation RAG Integration

将私有法规库集成到 FusionRAG 四层混合检索架构中

融合策略:
1. 精确缓存层 → 法规精确匹配缓存
2. 会话缓存层 → 法规查询上下文
3. 知识库层 → 法规向量检索 (Chroma/Milvus)
4. 数据库层 → 法规元数据查询

Author: Hermes Desktop Team
"""

import time
import threading
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib


class RegulationRAGMode(Enum):
    """法规检索模式"""
    SEMANTIC_ONLY = "semantic_only"      # 仅语义检索
    KEYWORD_ONLY = "keyword_only"        # 仅关键词检索
    HYBRID = "hybrid"                    # 混合检索
    SEMANTIC_FIRST = "semantic_first"    # 语义优先，关键词补充


@dataclass
class RegulationRAGConfig:
    """法规 RAG 配置"""
    # 检索模式
    retrieval_mode: RegulationRAGMode = RegulationRAGMode.HYBRID

    # 向量检索配置
    use_vector_db: bool = True
    vector_db_type: str = "chroma"  # chroma / milvus / memory
    embedding_model: str = "all-MiniLM-L6-v2"
    top_k_vector: int = 10

    # BM25 配置
    use_bm25: bool = True
    top_k_bm25: int = 20
    bm25_k1: float = 1.5
    bm25_b: float = 0.75

    # 融合配置
    fusion_alpha: float = 0.7  # 向量权重
    fusion_beta: float = 0.3   # BM25权重

    # 过滤配置
    default_category: str = ""
    default_department: str = ""
    default_status: str = "有效"

    # 缓存配置
    enable_cache: bool = True
    cache_ttl: int = 3600  # 秒


@dataclass
class RegulationQuery:
    """法规查询"""
    query_id: str
    query_text: str
    category: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = "有效"
    mode: RegulationRAGMode = RegulationRAGMode.HYBRID
    timestamp: float = field(default_factory=time.time)

    @classmethod
    def create(cls, text: str, **kwargs) -> "RegulationQuery":
        query_id = hashlib.md5(f"{text}_{time.time()}".encode()).hexdigest()[:12]
        return cls(query_id=query_id, query_text=text, **kwargs)


@dataclass
class RegulationChunk:
    """法规分块"""
    chunk_id: str
    law_id: str
    title: str
    content: str
    category: str = ""
    department: str = ""
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "chunk_id": self.chunk_id,
            "law_id": self.law_id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "department": self.department,
            "keywords": self.keywords,
            "metadata": self.metadata
        }


class RegulationCache:
    """法规检索缓存"""

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def _make_key(self, query: RegulationQuery) -> str:
        """生成缓存键"""
        parts = [
            query.query_text,
            query.category or "",
            query.department or "",
            query.status or "",
            query.mode.value
        ]
        return hashlib.md5("|".join(parts).encode()).hexdigest()

    def get(self, query: RegulationQuery) -> Optional[List]:
        """获取缓存"""
        key = self._make_key(query)
        with self._lock:
            if key in self._cache:
                result, timestamp = self._cache[key]
                if time.time() - timestamp < self.ttl:
                    return result
                else:
                    del self._cache[key]
        return None

    def set(self, query: RegulationQuery, results: List) -> None:
        """设置缓存"""
        key = self._make_key(query)
        with self._lock:
            if len(self._cache) >= self.max_size:
                # LRU 淘汰
                oldest = min(self._cache.items(), key=lambda x: x[1][1])
                del self._cache[oldest[0]]
            self._cache[key] = (results, time.time())

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """获取缓存大小"""
        return len(self._cache)


class RegulationRAG:
    """私有法规库 RAG 引擎

    将私有法规库融合到 FusionRAG 架构中，提供：
    1. 混合检索（向量 + BM25）
    2. 多级过滤（类别/部门/状态）
    3. 语义相似度排序
    4. 查询缓存加速
    5. 上下文感知
    """

    def __init__(
        self,
        regulation_db=None,  # PrivateRegulationDB 实例
        config: RegulationRAGConfig = None
    ):
        """
        初始化法规 RAG 引擎

        Args:
            regulation_db: 私有法规库实例
            config: 配置
        """
        self.config = config or RegulationRAGConfig()
        self.regulation_db = regulation_db

        # 缓存
        self.cache = RegulationCache(
            max_size=1000,
            ttl=self.config.cache_ttl
        ) if self.config.enable_cache else None

        # 统计
        self.stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "vector_searches": 0,
            "bm25_searches": 0,
            "avg_latency_ms": 0
        }
        self._lock = threading.Lock()

    def search(
        self,
        query_text: str,
        category: Optional[str] = None,
        department: Optional[str] = None,
        status: Optional[str] = None,
        top_k: int = 10,
        mode: Optional[RegulationRAGMode] = None
    ) -> List[Dict]:
        """
        检索法规

        Args:
            query_text: 查询文本
            category: 法规类别过滤
            department: 发布部门过滤
            status: 法规状态过滤
            top_k: 返回数量
            mode: 检索模式

        Returns:
            检索结果列表
        """
        # 构建查询对象
        query = RegulationQuery.create(
            text=query_text,
            category=category or self.config.default_category or None,
            department=department or self.config.default_department or None,
            status=status or self.config.default_status,
            mode=mode or self.config.retrieval_mode
        )

        # 检查缓存
        if self.cache:
            cached = self.cache.get(query)
            if cached:
                with self._lock:
                    self.stats["cache_hits"] += 1
                return cached

        start_time = time.time()
        results = []

        try:
            # 根据模式执行检索
            if query.mode == RegulationRAGMode.SEMANTIC_ONLY:
                results = self._semantic_search(query, top_k)
            elif query.mode == RegulationRAGMode.KEYWORD_ONLY:
                results = self._bm25_search(query, top_k)
            elif query.mode == RegulationRAGMode.HYBRID:
                results = self._hybrid_search(query, top_k)
            elif query.mode == RegulationRAGMode.SEMANTIC_FIRST:
                results = self._semantic_first_search(query, top_k)
            else:
                results = self._semantic_search(query, top_k)

        except Exception as e:
            print(f"[RegulationRAG] 检索失败: {e}")
            results = []

        # 更新统计
        latency = (time.time() - start_time) * 1000
        with self._lock:
            self.stats["total_queries"] += 1
            total = self.stats["total_queries"]
            current_avg = self.stats["avg_latency_ms"]
            self.stats["avg_latency_ms"] = (current_avg * (total - 1) + latency) / total

        # 写入缓存
        if self.cache and results:
            self.cache.set(query, results)

        return results

    def _semantic_search(self, query: RegulationQuery, top_k: int) -> List[Dict]:
        """语义向量检索"""
        if not self.regulation_db:
            return []

        with self._lock:
            self.stats["vector_searches"] += 1

        results = self.regulation_db.search(
            query=query.query_text,
            top_k=top_k,
            category=query.category,
            department=query.department,
            status=query.status
        )

        return [
            {
                "law_id": r.law.law_id,
                "title": r.law.title,
                "content": r.law.content,
                "category": r.law.category,
                "department": r.law.department,
                "score": r.score,
                "highlight": r.highlight,
                "source": "vector"
            }
            for r in results
        ]

    def _bm25_search(self, query: RegulationQuery, top_k: int) -> List[Dict]:
        """BM25 关键词检索（简化实现）"""
        if not self.regulation_db:
            return []

        with self._lock:
            self.stats["bm25_searches"] += 1

        # 获取所有法规进行 BM25 评分
        query_words = query.query_text.lower().split()
        scored_results = []

        # 遍历内存索引中的法规
        for law_id, law in self.regulation_db._law_index.items():
            # 过滤
            if query.category and law.category != query.category:
                continue
            if query.department and law.department != query.department:
                continue
            if query.status and law.status != query.status:
                continue

            # 计算 BM25 分数
            content_words = law.content.lower().split()
            word_freq = {}
            for word in content_words:
                word_freq[word] = word_freq.get(word, 0) + 1

            score = 0.0
            for qword in query_words:
                if qword in word_freq:
                    tf = word_freq[qword]
                    # 简化 IDF
                    idf = 1.0
                    score += idf * (tf * (self.config.bm25_k1 + 1)) / (
                        tf + self.config.bm25_k1 * (1 - self.config.bm25_b +
                        self.config.bm25_b * len(content_words) / 100)
                    )

            if score > 0:
                scored_results.append({
                    "law_id": law.law_id,
                    "title": law.title,
                    "content": law.content[:200],
                    "category": law.category,
                    "department": law.department,
                    "score": score,
                    "highlight": law.content[:100],
                    "source": "bm25"
                })

        # 排序
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]

    def _hybrid_search(self, query: RegulationQuery, top_k: int) -> List[Dict]:
        """混合检索（向量 + BM25）"""
        # 并行执行两种检索
        vector_results = self._semantic_search(query, self.config.top_k_vector)
        bm25_results = self._bm25_search(query, self.config.top_k_bm25)

        # 分数归一化与融合
        if not vector_results and not bm25_results:
            return []

        # 构建归一化分数
        all_law_ids = set()
        for r in vector_results:
            all_law_ids.add(r["law_id"])
        for r in bm25_results:
            all_law_ids.add(r["law_id"])

        # 分数融合
        fused_scores = {}
        for law_id in all_law_ids:
            vec_score = 0.0
            bm_score = 0.0

            for r in vector_results:
                if r["law_id"] == law_id:
                    vec_score = r["score"]
                    break

            for r in bm25_results:
                if r["law_id"] == law_id:
                    bm_score = r["score"]
                    break

            # 归一化并融合
            max_vec = max((r["score"] for r in vector_results), default=1.0)
            max_bm = max((r["score"] for r in bm25_results), default=1.0)

            normalized_vec = vec_score / max_vec if max_vec > 0 else 0.0
            normalized_bm = bm_score / max_bm if max_bm > 0 else 0.0

            fused_scores[law_id] = (
                self.config.fusion_alpha * normalized_vec +
                self.config.fusion_beta * normalized_bm
            )

        # 合并结果
        result_map = {}
        for r in vector_results:
            result_map[r["law_id"]] = r
        for r in bm25_results:
            if r["law_id"] not in result_map:
                result_map[r["law_id"]] = r

        # 排序
        fused_results = []
        for law_id, score in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]:
            r = result_map[law_id]
            r["score"] = score
            r["source"] = "hybrid"
            fused_results.append(r)

        return fused_results

    def _semantic_first_search(self, query: RegulationQuery, top_k: int) -> List[Dict]:
        """语义优先搜索"""
        # 先语义检索
        vector_results = self._semantic_search(query, top_k * 2)

        if not vector_results:
            return self._bm25_search(query, top_k)

        # 如果语义结果足够好，直接返回
        if vector_results[0]["score"] > 0.8:
            return vector_results[:top_k]

        # 否则用 BM25 补充
        bm25_results = self._bm25_search(query, top_k)

        # 合并去重
        seen = set()
        merged = []
        for r in vector_results:
            if r["law_id"] not in seen:
                seen.add(r["law_id"])
                merged.append(r)
        for r in bm25_results:
            if r["law_id"] not in seen:
                seen.add(r["law_id"])
                merged.append(r)

        return merged[:top_k]

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            stats = self.stats.copy()
        if self.cache:
            stats["cache_size"] = self.cache.size()
        if self.regulation_db:
            db_stats = self.regulation_db.get_statistics()
            stats.update(db_stats)
        return stats

    def reset_statistics(self) -> None:
        """重置统计"""
        with self._lock:
            self.stats = {
                "total_queries": 0,
                "cache_hits": 0,
                "vector_searches": 0,
                "bm25_searches": 0,
                "avg_latency_ms": 0
            }
        if self.cache:
            self.cache.clear()


# ============================================================
# 便捷工厂函数
# ============================================================

def create_regulation_rag(
    db_type: str = "chroma",
    embedding_model: str = "all-MiniLM-L6-v2",
    mode: str = "hybrid"
) -> RegulationRAG:
    """创建法规 RAG 引擎（便捷工厂函数）"""

    from business.regulation_vector_db import create_regulation_db

    # 创建法规库
    regulation_db = create_regulation_db(
        db_type=db_type,
        embedding_model=embedding_model,
        persist_directory="./data/regulations"
    )

    # 解析模式
    if mode == "semantic_only":
        rag_mode = RegulationRAGMode.SEMANTIC_ONLY
    elif mode == "keyword_only":
        rag_mode = RegulationRAGMode.KEYWORD_ONLY
    elif mode == "semantic_first":
        rag_mode = RegulationRAGMode.SEMANTIC_FIRST
    else:
        rag_mode = RegulationRAGMode.HYBRID

    # 创建 RAG 配置
    config = RegulationRAGConfig(
        retrieval_mode=rag_mode,
        vector_db_type=db_type,
        embedding_model=embedding_model
    )

    # 创建并返回
    return RegulationRAG(
        regulation_db=regulation_db,
        config=config
    )


# ============================================================
# 使用示例
# ============================================================

def example_usage():
    """使用示例"""

    print("=" * 60)
    print("创建法规 RAG 引擎...")

    rag = create_regulation_rag(
        db_type="chroma",
        embedding_model="all-MiniLM-L6-v2",
        mode="hybrid"
    )

    print("\n执行检索...")

    # 示例查询
    queries = [
        ("公司股东权益保护", {"status": "有效"}),
        ("劳动者合同权益", {"category": "法律法规"}),
        ("数据安全和个人信息", {}),
    ]

    for query_text, filters in queries:
        print(f"\n查询: '{query_text}'")
        print(f"过滤器: {filters}")

        results = rag.search(
            query_text=query_text,
            top_k=5,
            **filters
        )

        print(f"找到 {len(results)} 条结果:")
        for i, r in enumerate(results[:3], 1):
            print(f"  [{i}] {r['title']} (得分: {r['score']:.4f}, 来源: {r['source']})")

    print("\n统计信息:")
    stats = rag.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    example_usage()