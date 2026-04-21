"""
Distributed Cache - 分布式缓存网络
=================================

功能：
- 本地LRU缓存
- 缓存路由表
- 缓存热度图
- 智能广播通知
- 选择性同步复制

Author: LivingTreeAI Community
"""

import asyncio
import hashlib
import time
import json
from dataclasses import dataclass, field
from typing import Optional, Any, Callable, Awaitable
from collections import OrderedDict, defaultdict
from enum import Enum


class CacheLevel(Enum):
    """缓存层级"""
    LOCAL = "local"          # 本地缓存
    NEARBY = "nearby"       # 邻近节点
    SPECIALTY = "specialty" # 专长节点
    FULL = "full"           # 全网同步


@dataclass
class CacheEntry:
    """缓存条目"""
    query_hash: str
    query: str
    result: Any
    result_hash: str
    size: int
    category: str
    hot_score: float = 1.0
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    source_node: Optional[str] = None
    ttl: int = 3600  # 默认1小时

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl

    def access(self):
        """记录访问"""
        self.last_accessed = time.time()
        self.access_count += 1

    def update_hot_score(self, delta: float):
        """更新热度分数"""
        # 指数衰减
        self.hot_score = self.hot_score * 0.95 + delta * 0.05


@dataclass
class CacheNotice:
    """缓存通知（不包含完整数据）"""
    type: str = "cache_notice"
    node_id: str = ""
    query_hash: str = ""
    query: str = ""
    result_hash: str = ""
    size: int = 0
    category: str = ""
    hot_score: float = 1.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "node_id": self.node_id,
            "query_hash": self.query_hash,
            "query": self.query,
            "result_hash": self.result_hash,
            "size": self.size,
            "category": self.category,
            "hot_score": self.hot_score,
            "timestamp": self.timestamp,
        }


class CacheRoutingTable:
    """缓存路由表 - 维护 query_hash -> 持有节点 的映射"""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._table: dict[str, list[str]] = defaultdict(list)  # query_hash -> [node_ids]
        self._reverse_table: dict[str, str] = {}  # result_hash -> query_hash

    def register_cache(self, query_hash: str, result_hash: str, node_ids: list[str]):
        """注册缓存到路由表"""
        self._table[query_hash] = list(set(self._table[query_hash] + node_ids))
        self._reverse_table[result_hash] = query_hash

    def unregister_cache(self, query_hash: str, node_id: str):
        """从路由表注销"""
        if query_hash in self._table:
            if node_id in self._table[query_hash]:
                self._table[query_hash].remove(node_id)
            if not self._table[query_hash]:
                del self._table[query_hash]

    def get_cache_nodes(self, query_hash: str) -> list[str]:
        """获取持有某缓存的节点列表"""
        return self._table.get(query_hash, [])

    def get_all_hashes(self) -> list[str]:
        """获取所有缓存哈希"""
        return list(self._table.keys())


class CacheHeatMap:
    """缓存热度图 - 追踪查询模式"""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._query_frequencies: dict[str, int] = defaultdict(int)
        self._category_frequencies: dict[str, int] = defaultdict(int)
        self._time_buckets: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._trending_queries: list[str] = []
        self._last_update: float = 0

    def record_query(self, query: str, category: str):
        """记录查询"""
        self._query_frequencies[query] += 1
        self._category_frequencies[category] += 1

        # 时间桶（按小时）
        hour_bucket = int(time.time() // 3600)
        self._time_buckets[hour_bucket][query] += 1

        # 更新趋势
        self._update_trending()

    def _update_trending(self):
        """更新趋势查询"""
        now = time.time()
        if now - self._last_update < 60:  # 最多每分钟更新一次
            return

        # 合并最近3小时的数据
        hour_bucket = int(now // 3600)
        query_scores = defaultdict(float)

        for delta in range(3):
            bucket = hour_bucket - delta
            weight = 1.0 / (delta + 1)  # 越近权重越高
            for query, count in self._time_buckets.get(bucket, {}).items():
                query_scores[query] += count * weight

        # 排序取前20
        sorted_queries = sorted(query_scores.items(), key=lambda x: x[1], reverse=True)
        self._trending_queries = [q for q, _ in sorted_queries[:20]]
        self._last_update = now

    def get_trending_queries(self, k: int = 10) -> list[str]:
        """获取趋势查询"""
        return self._trending_queries[:k]

    def get_category_distribution(self) -> dict[str, float]:
        """获取类别分布"""
        total = sum(self._category_frequencies.values())
        if total == 0:
            return {}
        return {
            cat: count / total
            for cat, count in self._category_frequencies.items()
        }


class LocalCache:
    """本地LRU缓存"""

    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        self.max_size = max_size
        self.max_memory = max_memory_mb * 1024 * 1024
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._current_memory: int = 0

    def get(self, query: str) -> Optional[CacheEntry]:
        """获取缓存"""
        query_hash = self._hash_query(query)
        entry = self._cache.get(query_hash)

        if entry is None:
            return None

        if entry.is_expired():
            self._remove_entry(query_hash)
            return None

        # LRU: 移动到末尾
        self._cache.move_to_end(query_hash)
        entry.access()
        return entry

    def set(self, query: str, result: Any, category: str = "general", ttl: int = 3600):
        """设置缓存"""
        query_hash = self._hash_query(query)
        result_hash = self._hash_result(result)
        size = self._calculate_size(result)

        # 如果已存在，先移除
        if query_hash in self._cache:
            self._remove_entry(query_hash)

        # 检查内存限制
        while self._current_memory + size > self.max_memory and self._cache:
            self._evict_oldest()

        # 如果超过条目数限制
        while len(self._cache) >= self.max_size and self._cache:
            self._evict_oldest()

        entry = CacheEntry(
            query_hash=query_hash,
            query=query,
            result=result,
            result_hash=result_hash,
            size=size,
            category=category,
            ttl=ttl,
        )

        self._cache[query_hash] = entry
        self._current_memory += size

    def _remove_entry(self, query_hash: str):
        """移除条目"""
        if query_hash in self._cache:
            entry = self._cache.pop(query_hash)
            self._current_memory -= entry.size

    def _evict_oldest(self):
        """驱逐最老条目"""
        if self._cache:
            oldest = next(iter(self._cache))
            self._remove_entry(oldest)

    def _hash_query(self, query: str) -> str:
        return hashlib.sha256(query.encode()).hexdigest()[:32]

    def _hash_result(self, result: Any) -> str:
        data = json.dumps(result, sort_keys=True, default=str).encode()
        return hashlib.sha256(data).hexdigest()[:32]

    def _calculate_size(self, result: Any) -> int:
        """计算结果大小"""
        try:
            data = json.dumps(result, default=str).encode()
            return len(data)
        except Exception:
            return 1024  # 默认1KB

    def get_stats(self) -> dict:
        """获取缓存统计"""
        return {
            "entries": len(self._cache),
            "memory_mb": self._current_memory / (1024 * 1024),
            "max_memory_mb": self.max_memory / (1024 * 1024),
        }


class DistributedCache:
    """
    分布式缓存网络

    功能：
    1. 本地LRU缓存
    2. 缓存路由表维护
    3. 热度追踪
    4. 智能广播通知
    5. 选择性复制
    """

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
        get_specialty_nodes_func: Optional[Callable[[str], list[str]]] = None,
        get_nearby_nodes_func: Optional[Callable[[], list[str]]] = None,
    ):
        self.node_id = node_id
        self.local_cache = LocalCache()

        # 路由表和热度图
        self.routing_table = CacheRoutingTable(node_id)
        self.heat_map = CacheHeatMap(node_id)

        # 网络函数（由外部注入）
        self._send_func = send_func
        self._get_specialty_nodes = get_specialty_nodes_func or (lambda cat: [])
        self._get_nearby_nodes = get_nearby_nodes_func or (lambda: [])

        # 缓存容量追踪
        self.cache_capacities: dict[str, float] = {}  # node_id -> 使用率

    async def cache_search_result(
        self,
        query: str,
        result: Any,
        category: str = "general",
        ttl: int = 3600,
        source_node: Optional[str] = None,
    ):
        """
        缓存搜索结果到网络

        流程：
        1. 本地缓存
        2. 生成缓存摘要
        3. 广播缓存通知
        4. 选择性复制到专长节点
        """
        # 1. 本地缓存
        self.local_cache.set(query, result, category, ttl)

        # 2. 生成缓存摘要
        entry = self.local_cache.get(query)
        if not entry:
            return

        cache_summary = CacheNotice(
            node_id=self.node_id,
            query_hash=entry.query_hash,
            query=entry.query,
            result_hash=entry.result_hash,
            size=entry.size,
            category=entry.category,
            hot_score=entry.hot_score,
        )

        # 3. 注册到本地路由表
        self.routing_table.register_cache(
            entry.query_hash,
            entry.result_hash,
            [self.node_id]
        )

        # 4. 广播缓存通知
        await self.broadcast_cache_notice(cache_summary)

        # 5. 记录热度
        self.heat_map.record_query(query, category)

        # 6. 热度高则选择性复制
        if entry.hot_score > 0.8:
            await self.replicate_to_specialty_nodes(cache_summary, result)

    async def broadcast_cache_notice(self, notice: CacheNotice):
        """广播缓存通知"""
        targets = self.select_cache_notice_targets(notice)

        for target in targets:
            try:
                await self._send_func(target, notice.to_dict())
            except Exception as e:
                # 广播失败不影响主流程
                pass

    def select_cache_notice_targets(self, notice: CacheNotice) -> list[str]:
        """
        选择缓存通知的目标节点

        策略：
        1. 同类别专长节点
        2. 同城/同ISP节点（低延迟）
        3. 缓存容量充足的节点
        """
        targets = set()

        # 1. 同类别专长节点
        specialty_nodes = self._get_specialty_nodes(notice.category)
        targets.update(specialty_nodes[:5])

        # 2. 邻近节点
        nearby_nodes = self._get_nearby_nodes()
        targets.update(nearby_nodes[:3])

        # 3. 缓存容量充足的节点
        for node_id, capacity in self.cache_capacities.items():
            if capacity < 0.7:  # 使用率低于70%
                targets.add(node_id)

        # 排除自己
        targets.discard(self.node_id)

        return list(targets)[:10]

    async def replicate_to_specialty_nodes(self, notice: CacheNotice, result: Any):
        """选择性复制到专长节点"""
        specialty_nodes = self._get_specialty_nodes(notice.category)

        for node_id in specialty_nodes[:3]:
            try:
                await self._send_func(node_id, {
                    "type": "cache_replicate",
                    "query_hash": notice.query_hash,
                    "result": result,
                    "ttl": 7200,
                })
            except Exception:
                pass

    async def query_distributed_cache(self, query: str) -> Optional[Any]:
        """
        查询分布式缓存

        流程：
        1. 检查本地缓存
        2. 查询路由表
        3. 向缓存节点请求
        """
        query_hash = self._hash_query(query)

        # 1. 检查本地缓存
        entry = self.local_cache.get(query)
        if entry:
            entry.update_hot_score(1.0)  # 本地命中增加热度
            return entry.result

        # 2. 查询路由表
        cache_nodes = self.routing_table.get_cache_nodes(query_hash)

        # 3. 向缓存节点请求
        for node_id in cache_nodes:
            try:
                result = await self._request_cache_from_node(node_id, query_hash)
                if result:
                    # 更新本地缓存
                    self.local_cache.set(query, result, "cached", ttl=3600)
                    return result
            except Exception:
                continue

        return None

    async def _request_cache_from_node(self, node_id: str, query_hash: str) -> Optional[Any]:
        """从节点请求缓存"""
        if not self._send_func:
            return None

        try:
            response = await self._send_func(node_id, {
                "type": "cache_request",
                "query_hash": query_hash,
            })
            return response.get("result")
        except Exception:
            return None

    def update_capacity(self, node_id: str, usage_ratio: float):
        """更新节点缓存容量信息"""
        self.cache_capacities[node_id] = usage_ratio

    def get_cache_stats(self) -> dict:
        """获取缓存统计"""
        return {
            "local_cache": self.local_cache.get_stats(),
            "routing_entries": len(self.routing_table.get_all_hashes()),
            "trending_queries": self.heat_map.get_trending_queries(5),
            "category_distribution": self.heat_map.get_category_distribution(),
        }

    def _hash_query(self, query: str) -> str:
        return hashlib.sha256(query.encode()).hexdigest()[:32]


# 全局单例
_cache_instance: Optional[DistributedCache] = None


def get_distributed_cache(node_id: str = "local") -> DistributedCache:
    """获取分布式缓存单例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DistributedCache(node_id)
    return _cache_instance