"""
Search Routing - 智能搜索路由
=============================

功能：
- 语义向量匹配专长节点
- 缓存索引查询
- 节点性能统计
- 并行搜索 + 结果选择

Author: LivingTreeAI Community
"""

import asyncio
import hashlib
import time
import math
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable
from collections import defaultdict
from enum import Enum

# 尝试导入可选依赖
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class QueryCategory(Enum):
    """查询分类"""
    GENERAL = "general"
    TECHNICAL = "technical"
    LEGAL = "legal"
    FINANCIAL = "financial"
    MEDICAL = "medical"
    SCIENTIFIC = "scientific"
    NEWS = "news"
    ENTERTAINMENT = "entertainment"
    LIFESTYLE = "lifestyle"
    UNKNOWN = "unknown"


@dataclass
class QueryContext:
    """查询上下文"""
    query: str
    category: QueryCategory = QueryCategory.UNKNOWN
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    language: str = "zh"
    domain: Optional[str] = None  # 专业领域
    intent: Optional[str] = None  # 搜索/问答/导航


@dataclass
class SearchRequest:
    """搜索请求"""
    query: str
    context: QueryContext
    limit: int = 10
    timeout: float = 30.0
    redundancy: int = 2  # 冗余请求数


@dataclass
class SearchResult:
    """搜索结果"""
    query: str
    results: list
    source_node: str
    execution_time: float
    from_cache: bool = False
    cache_hit_rate: float = 0.0
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)

    def is_valid(self) -> bool:
        return self.results is not None and len(self.results) > 0


@dataclass
class SpecialtyNode:
    """专长节点"""
    node_id: str
    specialties: list[str]  # 专长领域列表
    vector: Optional[np.ndarray] = None  # 语义向量
    success_rate: float = 1.0
    avg_latency: float = 1000.0  # ms
    last_seen: float = field(default_factory=time.time)
    active_queries: int = 0


class SpecialtyGraph:
    """节点专长图谱"""

    CATEGORY_KEYWORDS = {
        QueryCategory.TECHNICAL: ["编程", "代码", "算法", "软件", "系统", "技术", "开发", "IT"],
        QueryCategory.LEGAL: ["法律", "法规", "条例", "诉讼", "合同", "权利", "义务"],
        QueryCategory.FINANCIAL: ["金融", "投资", "股票", "基金", "债券", "理财", "财务"],
        QueryCategory.MEDICAL: ["医疗", "健康", "疾病", "药物", "治疗", "医生", "医院"],
        QueryCategory.SCIENTIFIC: ["科学", "研究", "实验", "论文", "学术", "发现"],
        QueryCategory.NEWS: ["新闻", "事件", "报道", "记者", "媒体"],
        QueryCategory.ENTERTAINMENT: ["娱乐", "明星", "电影", "音乐", "游戏", "综艺"],
        QueryCategory.LIFESTYLE: ["生活", "美食", "旅游", "购物", "时尚", "家居"],
    }

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.specialty_nodes: dict[str, SpecialtyNode] = {}
        self.category_index: dict[QueryCategory, list[str]] = defaultdict(list)

    def register_node(self, node: SpecialtyNode):
        """注册节点专长"""
        self.specialty_nodes[node.node_id] = node

        # 更新类别索引
        for category in QueryCategory:
            if category == QueryCategory.UNKNOWN:
                continue
            keywords = self.CATEGORY_KEYWORDS.get(category, [])
            for specialty in node.specialties:
                if any(kw in specialty for kw in keywords):
                    if node.node_id not in self.category_index[category]:
                        self.category_index[category].append(node.node_id)

    def unregister_node(self, node_id: str):
        """注销节点"""
        if node_id in self.specialty_nodes:
            del self.specialty_nodes[node_id]
            for category_list in self.category_index.values():
                if node_id in category_list:
                    category_list.remove(node_id)

    def get_nodes_by_category(self, category: QueryCategory) -> list[str]:
        """获取指定类别的节点"""
        return self.category_index.get(category, [])

    def calculate_similarity(self, query_vector: np.ndarray, node_vector: np.ndarray) -> float:
        """计算余弦相似度"""
        if not HAS_NUMPY:
            return 0.5  # 默认值
        norm_q = np.linalg.norm(query_vector)
        norm_n = np.linalg.norm(node_vector)
        if norm_q == 0 or norm_n == 0:
            return 0.0
        return float(np.dot(query_vector, node_vector) / (norm_q * norm_n))

    def match_query(self, query: str, query_vector: np.ndarray, top_k: int = 5) -> list[tuple[str, float]]:
        """匹配查询到最相关的专长节点"""
        scores = []

        # 检测查询类别
        detected_category = self._detect_category(query)

        # 策略1：专长匹配
        candidate_nodes = set()
        if detected_category != QueryCategory.UNKNOWN:
            candidate_nodes.update(self.category_index.get(detected_category, []))

        # 如果没有类别匹配，使用所有节点
        if not candidate_nodes:
            candidate_nodes.update(self.specialty_nodes.keys())

        # 计算相似度
        for node_id in candidate_nodes:
            node = self.specialty_nodes.get(node_id)
            if not node or node.vector is None:
                continue

            similarity = self.calculate_similarity(query_vector, node.vector)
            # 结合性能评分
            performance_factor = node.success_rate * (1.0 - min(node.avg_latency / 10000, 1.0))
            combined_score = similarity * 0.7 + performance_factor * 0.3
            scores.append((node_id, combined_score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def _detect_category(self, query: str) -> QueryCategory:
        """检测查询类别"""
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query:
                    return category
        return QueryCategory.UNKNOWN


@dataclass
class NodePerformanceStats:
    """节点性能统计"""
    node_id: str
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    total_latency: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    last_query_time: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_queries == 0:
            return 1.0
        return self.successful_queries / self.total_queries

    @property
    def avg_latency(self) -> float:
        if self.successful_queries == 0:
            return 1000.0
        return self.total_latency / self.successful_queries

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total

    def update_success(self, latency: float):
        self.total_queries += 1
        self.successful_queries += 1
        self.total_latency += latency
        self.last_query_time = time.time()

    def update_failure(self):
        self.total_queries += 1
        self.failed_queries += 1
        self.last_query_time = time.time()

    def update_cache(self, hit: bool):
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1


class SearchRouter:
    """
    智能搜索路由器

    功能：
    1. 本地缓存查询
    2. 语义向量计算
    3. 专长节点匹配
    4. 并行搜索执行
    5. 最优结果选择
    6. 结果缓存传播
    """

    def __init__(
        self,
        node_id: str,
        cache_backend: Optional[Callable] = None,
        embed_func: Optional[Callable[[str], Awaitable[np.ndarray]]] = None,
    ):
        self.node_id = node_id
        self.specialty_graph = SpecialtyGraph(node_id)
        self.performance_stats: dict[str, NodePerformanceStats] = {}
        self.cache_backend = cache_backend  # 外部缓存后端

        # 嵌入函数（需要外部提供）
        self._embed_func = embed_func

        # 搜索处理器注册
        self._search_handlers: dict[str, Callable] = {}

        # 统计
        self._local_stats = NodePerformanceStats(node_id)

    def register_search_handler(self, category: QueryCategory, handler: Callable):
        """注册搜索处理器"""
        self._search_handlers[category.value] = handler

    async def embed_query(self, query: str) -> np.ndarray:
        """将查询文本嵌入为向量"""
        if self._embed_func:
            return await self._embed_func(query)

        # 简单哈希向量（降级方案）
        if not HAS_NUMPY:
            return None

        hash_bytes = hashlib.sha256(query.encode()).digest()
        vector = np.frombuffer(hash_bytes, dtype=np.float32)
        # 归一化
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector

    async def route_search(self, request: SearchRequest) -> SearchResult:
        """
        路由搜索请求

        流程：
        1. 查询本地缓存
        2. 计算语义向量
        3. 选择执行节点
        4. 并行发送搜索
        5. 选择最佳结果
        6. 缓存结果
        """
        start_time = time.time()

        # 1. 查询本地缓存
        if cached := await self._check_local_cache(request.query):
            execution_time = time.time() - start_time
            self._local_stats.update_cache(True)
            return SearchResult(
                query=request.query,
                results=cached["results"],
                source_node="local_cache",
                execution_time=execution_time,
                from_cache=True,
                confidence=0.9,
            )

        self._local_stats.update_cache(False)

        # 2. 计算查询向量
        query_vector = await self.embed_query(request.query)

        # 3. 检测类别
        category = self._detect_category(request.query)
        request.context.category = category

        # 4. 选择执行节点
        target_nodes = await self._select_execution_nodes(
            request, query_vector, k=3
        )

        if not target_nodes:
            # 没有可用节点，返回空结果
            return SearchResult(
                query=request.query,
                results=[],
                source_node="none",
                execution_time=time.time() - start_time,
                confidence=0.0,
            )

        # 5. 并行发送搜索请求
        tasks = []
        for node_id in target_nodes:
            task = self._send_search_request(node_id, request)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 6. 选择最佳结果
        valid_results = [r for r in results if isinstance(r, SearchResult) and r.is_valid()]
        best_result = self._select_best_result(valid_results, request)

        if best_result:
            # 更新统计
            self._update_node_stats(best_result.source_node, best_result.execution_time, True)

            # 7. 缓存结果
            await self._cache_result(request.query, best_result)
        else:
            best_result = SearchResult(
                query=request.query,
                results=[],
                source_node="failed",
                execution_time=time.time() - start_time,
                confidence=0.0,
            )

        return best_result

    async def _check_local_cache(self, query: str) -> Optional[dict]:
        """检查本地缓存"""
        if not self.cache_backend:
            return None

        try:
            result = await self.cache_backend.get(query)
            return result
        except Exception:
            return None

    async def _cache_result(self, query: str, result: SearchResult):
        """缓存搜索结果"""
        if not self.cache_backend:
            return

        try:
            await self.cache_backend.set(query, {
                "results": result.results,
                "timestamp": time.time(),
                "source": result.source_node,
            }, ttl=3600)
        except Exception:
            pass

    async def _select_execution_nodes(
        self, request: SearchRequest, query_vector: np.ndarray, k: int = 3
    ) -> list[str]:
        """选择执行搜索的节点"""
        candidates = []

        # 策略1：专长匹配
        specialty_matches = self.specialty_graph.match_query(
            request.query, query_vector, top_k=k * 2
        )
        for node_id, score in specialty_matches:
            candidates.append((node_id, score * 0.6))

        # 策略2：性能优选
        for node_id, stats in self.performance_stats.items():
            if stats.success_rate > 0.8:
                candidates.append((node_id, stats.success_rate * 0.2))

        # 去重并排序
        score_map = {}
        for node_id, score in candidates:
            if node_id not in score_map:
                score_map[node_id] = 0
            score_map[node_id] = max(score_map[node_id], score)

        sorted_candidates = sorted(score_map.items(), key=lambda x: x[1], reverse=True)
        return [node_id for node_id, _ in sorted_candidates[:k]]

    async def _send_search_request(self, node_id: str, request: SearchRequest) -> SearchResult:
        """向节点发送搜索请求"""
        handler = self._search_handlers.get(request.context.category.value)
        if not handler:
            # 通用处理器
            handler = self._search_handlers.get("general")

        if handler:
            try:
                return await asyncio.wait_for(
                    handler(node_id, request),
                    timeout=request.timeout
                )
            except asyncio.TimeoutError:
                self._update_node_stats(node_id, request.timeout, False)
                raise
            except Exception:
                self._update_node_stats(node_id, 0, False)
                raise

        raise ValueError(f"No handler for category {request.context.category}")

    def _select_best_result(
        self, results: list[SearchResult], request: SearchRequest
    ) -> Optional[SearchResult]:
        """选择最佳搜索结果"""
        if not results:
            return None

        # 按置信度和执行时间加权评分
        scored_results = []
        for result in results:
            score = (
                result.confidence * 0.5 +
                (1.0 - min(result.execution_time / request.timeout, 1.0)) * 0.3 +
                (1.0 - min(len(results) / request.redundancy, 1.0)) * 0.2
            )
            scored_results.append((result, score))

        scored_results.sort(key=lambda x: x[1], reverse=True)
        return scored_results[0][0]

    def _update_node_stats(self, node_id: str, latency: float, success: bool):
        """更新节点统计"""
        if node_id not in self.performance_stats:
            self.performance_stats[node_id] = NodePerformanceStats(node_id)

        stats = self.performance_stats[node_id]
        if success:
            stats.update_success(latency)
        else:
            stats.update_failure()

    def _detect_category(self, query: str) -> QueryCategory:
        """检测查询类别"""
        return self.specialty_graph._detect_category(query)

    def get_network_stats(self) -> dict:
        """获取网络统计"""
        return {
            "total_nodes": len(self.specialty_graph.specialty_nodes),
            "active_nodes": sum(
                1 for n in self.specialty_graph.specialty_nodes.values()
                if time.time() - n.last_seen < 300
            ),
            "local_stats": {
                "success_rate": self._local_stats.success_rate,
                "cache_hit_rate": self._local_stats.cache_hit_rate,
                "avg_latency": self._local_stats.avg_latency,
            },
            "node_stats": {
                node_id: {
                    "success_rate": stats.success_rate,
                    "avg_latency": stats.avg_latency,
                }
                for node_id, stats in self.performance_stats.items()
            },
        }


# 全局单例
_router_instance: Optional[SearchRouter] = None


def get_search_router(node_id: str = "local") -> SearchRouter:
    """获取搜索路由器单例"""
    global _router_instance
    if _router_instance is None:
        _router_instance = SearchRouter(node_id)
    return _router_instance