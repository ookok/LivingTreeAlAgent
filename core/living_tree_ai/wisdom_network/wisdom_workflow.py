"""
Wisdom Workflow - 去中心化智慧网络工作流
========================================

整合 Search Net + Cache Net + Credit Net 的完整工作流

Author: LivingTreeAI Community
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any
from enum import Enum

from .search_routing import (
    SearchRouter,
    SearchRequest,
    SearchResult,
    QueryContext,
    QueryCategory,
    get_search_router,
)

from .distributed_cache import (
    DistributedCache,
    CacheEntry,
    get_distributed_cache,
)

from .credit_network import (
    CreditNetwork,
    ContributionType,
    get_credit_network,
)


@dataclass
class NetworkStats:
    """网络统计"""
    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    contributions_recorded: int = 0
    avg_query_time: float = 0.0
    last_update: float = field(default_factory=time.time)

    @property
    def cache_hit_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return self.cache_hits / self.total_queries


class WisdomWorkflow:
    """
    去中心化智慧网络工作流

    整合三网：
    1. SearchNet - 处理搜索请求
    2. CacheNet - 缓存结果
    3. CreditNet - 记录贡献

    工作流程示例（节点A搜索"2025年排污许可新规"）：
    1. 节点A接收搜索请求
    2. 查询本地缓存 → 未命中
    3. SearchRouter工作：
       - 计算查询语义向量
       - 匹配到节点B（环境法规专长）
       - 匹配到节点C（最近缓存过类似查询）
    4. 向B、C并行发送搜索请求
    5. 节点B执行搜索，生成结果
    6. 节点B返回结果 + 贡献证明PoC_B
    7. 节点A：
       - 验证PoC_B有效性
       - 记录"欠节点B一次贡献"
       - 缓存结果到本地
       - 广播缓存通知
    8. 节点D收到缓存通知，存储索引
    """

    def __init__(
        self,
        node_id: str,
        search_router: Optional[SearchRouter] = None,
        distributed_cache: Optional[DistributedCache] = None,
        credit_network: Optional[CreditNetwork] = None,
    ):
        self.node_id = node_id

        # 初始化三网
        self.search_router = search_router or get_search_router(node_id)
        self.cache = distributed_cache or get_distributed_cache(node_id)
        self.credit = credit_network or get_credit_network(node_id)

        # 统计
        self.stats = NetworkStats()

        # 回调函数
        self._on_cache_hit: Optional[Callable] = None
        self._on_contribution: Optional[Callable] = None

    async def execute_search(
        self,
        query: str,
        context: Optional[QueryContext] = None,
        user_id: Optional[str] = None,
    ) -> SearchResult:
        """
        执行去中心化搜索

        流程：
        1. 查询分布式缓存
        2. 如未命中，执行搜索路由
        3. 缓存结果
        4. 记录贡献
        """
        start_time = time.time()
        self.stats.total_queries += 1

        if context is None:
            context = QueryContext(query=query, user_id=user_id)

        # 1. 尝试从分布式缓存获取
        cached_result = await self.cache.query_distributed_cache(query)

        if cached_result:
            # 缓存命中
            self.stats.cache_hits += 1
            execution_time = time.time() - start_time

            if self._on_cache_hit:
                await self._on_cache_hit(query, cached_result)

            return SearchResult(
                query=query,
                results=cached_result.get("results", []) if isinstance(cached_result, dict) else [cached_result],
                source_node="distributed_cache",
                execution_time=execution_time,
                from_cache=True,
                confidence=0.95,
            )

        self.stats.cache_misses += 1

        # 2. 执行搜索路由
        request = SearchRequest(
            query=query,
            context=context,
            limit=10,
            timeout=30.0,
        )

        result = await self.search_router.route_search(request)

        # 3. 缓存结果
        if result.is_valid():
            await self.cache.cache_search_result(
                query=query,
                result={"results": result.results},
                category=context.category.value,
                ttl=3600,
            )

        # 4. 记录贡献
        if result.source_node != "local_cache" and result.source_node != "none":
            await self.credit.record_contribution(
                event_type=ContributionType.SEARCH_EXECUTED,
                details={
                    "query": query,
                    "query_complexity": len(query) / 100,
                    "beneficiary": result.source_node,
                },
                broadcast=True,
            )
            self.stats.contributions_recorded += 1

        # 更新统计
        execution_time = time.time() - start_time
        if execution_time > 0:
            alpha = 0.1
            self.stats.avg_query_time = (
                self.stats.avg_query_time * (1 - alpha) + execution_time * alpha
            )
        self.stats.last_update = time.time()

        return result

    async def prefetch_trending(self, k: int = 5):
        """
        预取趋势查询

        系统自动识别热点查询，在低峰期预热缓存
        """
        trending = self.cache.heat_map.get_trending_queries(k)

        for query in trending:
            # 检查本地是否已有缓存
            if not await self.cache.query_distributed_cache(query):
                # 没有缓存，触发搜索
                await self.execute_search(query)

    def register_search_handler(
        self,
        category: QueryCategory,
        handler: Callable[[str, SearchRequest], Awaitable[SearchResult]],
    ):
        """注册搜索处理器"""
        self.search_router.register_search_handler(category, handler)

    def set_cache_hit_callback(self, callback: Callable):
        """设置缓存命中回调"""
        self._on_cache_hit = callback

    def set_contribution_callback(self, callback: Callable):
        """设置贡献记录回调"""
        self._on_contribution = callback

    def get_network_stats(self) -> dict:
        """获取网络统计"""
        return {
            "workflow_stats": {
                "total_queries": self.stats.total_queries,
                "cache_hits": self.stats.cache_hits,
                "cache_misses": self.stats.cache_misses,
                "cache_hit_rate": f"{self.stats.cache_hit_rate:.1%}",
                "avg_query_time_ms": f"{self.stats.avg_query_time * 1000:.1f}",
                "contributions_recorded": self.stats.contributions_recorded,
            },
            "search_router": self.search_router.get_network_stats(),
            "distributed_cache": self.cache.get_cache_stats(),
            "credit_network": self.credit.get_network_stats(),
        }


class WisdomNetwork:
    """
    去中心化智慧网络管理器

    简化接口，管理多个节点和工作流
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.workflow = WisdomWorkflow(node_id)
        self.peer_workflows: dict[str, WisdomWorkflow] = {}

    async def search(
        self,
        query: str,
        use_network: bool = True,
        **kwargs
    ) -> SearchResult:
        """执行搜索"""
        if use_network:
            return await self.workflow.execute_search(query, **kwargs)
        else:
            # 仅本地搜索
            cached = await self.workflow.cache.local_cache.get(query)
            if cached:
                return SearchResult(
                    query=query,
                    results=cached.result.get("results", []) if isinstance(cached.result, dict) else [cached.result],
                    source_node="local",
                    execution_time=0,
                    from_cache=True,
                )
            return SearchResult(
                query=query,
                results=[],
                source_node="none",
                execution_time=0,
                confidence=0,
            )

    def register_peer(self, peer_id: str, workflow: WisdomWorkflow):
        """注册对等节点工作流"""
        self.peer_workflows[peer_id] = workflow

    def unregister_peer(self, peer_id: str):
        """注销对等节点"""
        if peer_id in self.peer_workflows:
            del self.peer_workflows[peer_id]

    def get_all_stats(self) -> dict:
        """获取全网统计"""
        stats = {
            "self": self.workflow.get_network_stats(),
            "peers": {},
        }

        for peer_id, workflow in self.peer_workflows.items():
            stats["peers"][peer_id] = workflow.get_network_stats()

        return stats


# 全局单例
_wisdom_instance: Optional[WisdomNetwork] = None


def get_wisdom_network(node_id: str = "local") -> WisdomNetwork:
    """获取智慧网络单例"""
    global _wisdom_instance
    if _wisdom_instance is None:
        _wisdom_instance = WisdomNetwork(node_id)
    return _wisdom_instance