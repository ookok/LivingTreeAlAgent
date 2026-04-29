# discovery.py — DHT 版本发现层

"""
DHT 网络发现层
===============

实现 Kademlia 风格的分布式哈希表，用于：
1. 版本信息存储与查询
2. 节点发现与路由
3. 智能种子节点管理
4. 区域感知路由

基于 relay_chain/event_ext/p2p_network/ 的现有基础设施构建
"""

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
import random

from .models import (
    NodeInfo, NodeState, VersionInfo, UpdateManifest,
    generate_node_id, calculate_version_code
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# K-Bucket 管理
# ═══════════════════════════════════════════════════════════════════════════════


class KBucket:
    """K-Bucket 实现（Kademlia 路由表）"""

    def __init__(self, index: int, k: int = 20):
        self.index = index  # 距离范围索引
        self.k = k          # Bucket 大小
        self.nodes: Dict[str, NodeInfo] = {}  # node_id -> NodeInfo
        self.replacement_cache: List[NodeInfo] = []  # 替换缓存

    @property
    def distance_range(self) -> Tuple[int, int]:
        """距离范围 [2^index, 2^(index+1))"""
        return (2 ** self.index, 2 ** (self.index + 1))

    def add_node(self, node: NodeInfo) -> bool:
        """添加节点到 Bucket"""
        node_id = node.node_id

        if node_id in self.nodes:
            # 更新现有节点
            self.nodes[node_id] = node
            return True

        if len(self.nodes) < self.k:
            # Bucket 未满，直接添加
            self.nodes[node_id] = node
            return True

        # Bucket 已满，尝试替换不活跃节点
        for existing_id, existing in self.nodes.items():
            if existing.state == NodeState.OFFLINE:
                del self.nodes[existing_id]
                self.nodes[node_id] = node
                return True

        # 所有节点都活跃，添加到替换缓存
        if node not in self.replacement_cache:
            self.replacement_cache.append(node)
            if len(self.replacement_cache) > 10:
                self.replacement_cache.pop(0)

        return False

    def remove_node(self, node_id: str) -> bool:
        """从 Bucket 移除节点"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            # 从替换缓存提升节点
            if self.replacement_cache:
                replacement = self.replacement_cache.pop(0)
                self.nodes[replacement.node_id] = replacement
            return True
        return False

    def get_nodes(self) -> List[NodeInfo]:
        """获取所有活跃节点"""
        return [
            n for n in self.nodes.values()
            if n.state != NodeState.OFFLINE
        ]

    def get_closest_nodes(self, node_id: str, count: int = None) -> List[NodeInfo]:
        """获取距离最近的节点"""
        nodes = self.get_nodes()
        if count is None:
            return nodes

        # 按距离排序
        def distance(a: str, b: str) -> int:
            return int(hashlib.sha256(a.encode()).hexdigest(), 16) ^ \
                   int(hashlib.sha256(b.encode()).hexdigest(), 16)

        nodes.sort(key=lambda n: distance(n.node_id, node_id))
        return nodes[:count]


@dataclass
class DHTConfig:
    """DHT 配置"""
    k: int = 20                    # Bucket 大小
    alpha: int = 3                 # 并发查询数
    max_depth: int = 20            # 最大跳数
    bucket_count: int = 160       # Bucket 数量 (对应 160 位哈希)
    refresh_interval: int = 3600   # 刷新间隔 (秒)
    seed_nodes: List[str] = field(default_factory=list)  # 种子节点地址
    local_port: int = 0            # 本地端口 (0 = 自动)


# ═══════════════════════════════════════════════════════════════════════════════
# DHT 节点
# ═══════════════════════════════════════════════════════════════════════════════


class DHTNode:
    """
    DHT 节点实现

    功能：
    1. K-Bucket 路由表管理
    2. 节点发现与查询
    3. 版本信息存储与检索
    4. 区域感知路由优化
    """

    def __init__(self, node_id: str = None, config: DHTConfig = None):
        self.node_id = node_id or generate_node_id()
        self.config = config or DHTConfig()
        self.buckets: List[KBucket] = [
            KBucket(i, self.config.k) for i in range(self.config.bucket_count)
        ]
        self.local_version_cache: Dict[str, VersionInfo] = {}  # 本地缓存的版本信息
        self.local_manifest_cache: Dict[str, UpdateManifest] = {}  # 更新清单缓存
        self.pending_queries: Dict[str, asyncio.Future] = {}  # 待处理的查询
        self.last_refresh = time.time()
        self._running = False
        self._tasks: List[asyncio.Task] = []

        logger.info(f"DHT Node initialized: {self.node_id}")

    @property
    def routing_table_size(self) -> int:
        """路由表大小"""
        return sum(len(b.get_nodes()) for b in self.buckets)

    def _get_bucket_index(self, node_id: str) -> int:
        """获取节点 ID 对应的 Bucket 索引"""
        def distance(a: str, b: str) -> int:
            return int(hashlib.sha256(a.encode()).hexdigest(), 16) ^ \
                   int(hashlib.sha256(b.encode()).hexdigest(), 16)

        dist = distance(self.node_id, node_id)
        if dist == 0:
            return 0

        # 找到最高有效位
        index = dist.bit_length() - 1
        return min(index, self.config.bucket_count - 1)

    def add_node(self, node: NodeInfo) -> bool:
        """添加节点到路由表"""
        index = self._get_bucket_index(node.node_id)
        result = self.buckets[index].add_node(node)
        if result:
            logger.debug(f"Node {node.node_id[:8]} added to bucket {index}")
        return result

    def remove_node(self, node_id: str) -> bool:
        """从路由表移除节点"""
        for bucket in self.buckets:
            if bucket.remove_node(node_id):
                logger.debug(f"Node {node_id[:8]} removed")
                return True
        return False

    def get_closest_nodes(self, node_id: str, count: int = None) -> List[NodeInfo]:
        """获取距离最近的 K 个节点"""
        count = count or self.config.k
        all_nodes: List[NodeInfo] = []

        # 从最近的 Bucket 开始收集
        index = self._get_bucket_index(node_id)
        for offset in range(self.config.bucket_count):
            for i in [(index + offset) % self.config.bucket_count,
                      (index - offset) % self.config.bucket_count]:
                if i == index and offset > 0:
                    continue
                bucket_nodes = self.buckets[i].get_closest_nodes(node_id)
                all_nodes.extend(bucket_nodes)
                if len(all_nodes) >= count:
                    break
            if len(all_nodes) >= count:
                break

        # 去重并返回最近的 K 个
        seen = set()
        unique_nodes = []
        for n in all_nodes:
            if n.node_id not in seen:
                seen.add(n.node_id)
                unique_nodes.append(n)

        unique_nodes.sort(key=lambda x: self._xor_distance(x.node_id, node_id))
        return unique_nodes[:count]

    def _xor_distance(self, a: str, b: str) -> int:
        """XOR 距离"""
        return int(hashlib.sha256(a.encode()).hexdigest(), 16) ^ \
               int(hashlib.sha256(b.encode()).hexdigest(), 16)

    # ═══════════════════════════════════════════════════════════════════════════
    # 版本存储与查询
    # ═══════════════════════════════════════════════════════════════════════════

    def store_version(self, app_id: str, version: VersionInfo):
        """存储版本信息到本地"""
        key = f"{app_id}:{version.version}"
        self.local_version_cache[key] = version
        logger.info(f"Stored version {version.version} for {app_id}")

    def get_version(self, app_id: str, version: str) -> Optional[VersionInfo]:
        """获取指定版本信息"""
        key = f"{app_id}:{version}"
        return self.local_version_cache.get(key)

    def get_latest_version(self, app_id: str) -> Optional[VersionInfo]:
        """获取最新版本"""
        prefix = f"{app_id}:"
        versions = [
            v for k, v in self.local_version_cache.items()
            if k.startswith(prefix)
        ]
        if not versions:
            return None
        return max(versions, key=lambda x: x.version_code)

    def store_manifest(self, manifest: UpdateManifest):
        """存储更新清单"""
        self.local_manifest_cache[manifest.app_id] = manifest
        logger.info(f"Stored manifest for {manifest.app_id}")

    def get_manifest(self, app_id: str) -> Optional[UpdateManifest]:
        """获取更新清单"""
        return self.local_manifest_cache.get(app_id)

    # ═══════════════════════════════════════════════════════════════════════════
    # 节点发现协议
    # ═══════════════════════════════════════════════════════════════════════════

    async def find_node(self, target_id: str) -> List[NodeInfo]:
        """
        FIND_NODE 查询

        递归查找距离目标 ID 最近的节点
        """
        visited = set()
        candidates = self.get_closest_nodes(target_id, self.config.alpha)
        results: List[NodeInfo] = []

        while candidates and len(results) < self.config.k:
            # 并发查询 alpha 个节点
            queries = []
            for node in candidates[:self.config.alpha]:
                if node.node_id in visited:
                    continue
                visited.add(node.node_id)

                # 实际实现中这里会发送网络请求
                # 这里简化为直接返回路由表中的节点
                query = asyncio.create_task(self._simulate_find_node(node, target_id))
                queries.append((node, query))

            # 等待查询完成
            for node, query in queries:
                try:
                    closer = await asyncio.wait_for(query, timeout=5.0)
                    results.extend(closer)
                except asyncio.TimeoutError:
                    logger.warning(f"Find node timeout: {node.node_id[:8]}")
                except Exception as e:
                    logger.error(f"Find node error: {e}")

            # 更新候选列表
            candidates = self.get_closest_nodes(target_id, self.config.k)
            candidates = [n for n in candidates if n.node_id not in visited]

        # 去重并返回最近的 K 个
        seen = set()
        unique = []
        for n in results:
            if n.node_id not in seen:
                seen.add(n.node_id)
                unique.append(n)

        unique.sort(key=lambda x: self._xor_distance(x.node_id, target_id))
        return unique[:self.config.k]

    async def _simulate_find_node(self, node: NodeInfo, target_id: str) -> List[NodeInfo]:
        """模拟 FIND_NODE 响应"""
        # 实际实现中会通过网络获取远程节点的响应
        # 这里简化处理，返回本地最接近的节点
        return self.get_closest_nodes(target_id, self.config.alpha)

    async def find_value(self, app_id: str, version: str = None) -> Tuple[Optional[VersionInfo], List[NodeInfo]]:
        """
        FIND_VALUE 查询

        如果找到值返回版本信息，否则返回距离最近的节点
        """
        # 先查询本地缓存
        if version:
            local_version = self.get_version(app_id, version)
            if local_version:
                return local_version, []
        else:
            latest = self.get_latest_version(app_id)
            if latest:
                return latest, []

        # 本地未找到，查询网络
        key = f"{app_id}:{version or 'latest'}"
        target_id = hashlib.sha256(key.encode()).hexdigest()[:32]

        nodes = await self.find_node(target_id)
        return None, nodes

    # ═══════════════════════════════════════════════════════════════════════════
    # 版本查询协议
    # ═══════════════════════════════════════════════════════════════════════════

    async def query_latest_version(self, app_id: str, exclude_nodes: Set[str] = None) -> Optional[VersionInfo]:
        """
        查询最新版本

        递归查询网络中的最新版本信息
        """
        exclude_nodes = exclude_nodes or set()

        # 尝试本地获取
        latest = self.get_latest_version(app_id)
        if latest:
            return latest

        # 查询最近的 Alpha 个节点
        candidates = [
            n for n in self.get_closest_nodes(self.node_id, self.config.alpha)
            if n.node_id not in exclude_nodes
        ]

        for node in candidates:
            exclude_nodes.add(node.node_id)

        # 并发查询
        tasks = [
            self._query_node_version(node, app_id)
            for node in candidates
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集最新版本
        latest_version = None
        for result in results:
            if isinstance(result, VersionInfo):
                if latest_version is None or result.is_newer_than(latest_version):
                    latest_version = result

        return latest_version

    async def _query_node_version(self, node: NodeInfo, app_id: str) -> Optional[VersionInfo]:
        """查询单个节点的版本信息"""
        try:
            # 实际实现中会发送网络请求
            # 这里简化处理，尝试从本地缓存获取
            return self.get_latest_version(app_id)
        except Exception as e:
            logger.error(f"Query node {node.node_id[:8]} failed: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════════════
    # 生命周期管理
    # ═══════════════════════════════════════════════════════════════════════════

    async def start(self):
        """启动 DHT 节点"""
        if self._running:
            return

        self._running = True

        # 启动刷新任务
        self._tasks.append(asyncio.create_task(self._refresh_loop()))

        # 启动节点保活任务
        self._tasks.append(asyncio.create_task(self._keep_alive_loop()))

        logger.info(f"DHT Node {self.node_id[:8]} started")

    async def stop(self):
        """停止 DHT 节点"""
        self._running = False

        for task in self._tasks:
            task.cancel()

        self._tasks.clear()
        logger.info(f"DHT Node {self.node_id[:8]} stopped")

    async def _refresh_loop(self):
        """定期刷新路由表"""
        while self._running:
            try:
                await asyncio.sleep(self.config.refresh_interval)
                await self._refresh_routing_table()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Refresh loop error: {e}")

    async def _keep_alive_loop(self):
        """节点保活检测"""
        while self._running:
            try:
                await asyncio.sleep(60)  # 每分钟检测一次
                self._check_node_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Keep alive loop error: {e}")

    async def _refresh_routing_table(self):
        """刷新路由表"""
        logger.debug(f"Refreshing routing table, size: {self.routing_table_size}")

        # 随机选择一个 Bucket 进行刷新
        random_index = random.randint(0, self.config.bucket_count - 1)

        # 生成随机目标 ID
        random_id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:32]

        # 执行 FIND_NODE
        await self.find_node(random_id)

    def _check_node_health(self):
        """检查节点健康状态"""
        now = time.time()
        offline_threshold = 3600  # 1小时未活跃视为离线

        for bucket in self.buckets:
            for node_id, node in list(bucket.nodes.items()):
                if now - node.last_seen > offline_threshold:
                    node.state = NodeState.OFFLINE
                    logger.debug(f"Node {node_id[:8]} marked as offline")


# ═══════════════════════════════════════════════════════════════════════════════
# 智能种子节点管理器
# ═══════════════════════════════════════════════════════════════════════════════


class SeedNodeManager:
    """
    智能种子节点管理器

    功能：
    1. 种子节点注册与发现
    2. 健康状态追踪
    3. 区域感知选择
    4. 动态权重调度
    """

    def __init__(self):
        self.seed_nodes: Dict[str, NodeInfo] = {}
        self.heartbeat_tracker: Dict[str, float] = {}  # node_id -> last_heartbeat
        self.region_groups: Dict[str, List[str]] = defaultdict(list)  # region -> node_ids
        self._lock = asyncio.Lock()

    async def register_seed(self, node: NodeInfo):
        """注册种子节点"""
        async with self._lock:
            node.is_seed = True
            self.seed_nodes[node.node_id] = node
            self.heartbeat_tracker[node.node_id] = time.time()

            if node.region:
                self.region_groups[node.region].append(node.node_id)

            logger.info(f"Registered seed node: {node.node_id[:8]} ({node.region})")

    async def unregister_seed(self, node_id: str):
        """注销种子节点"""
        async with self._lock:
            if node_id in self.seed_nodes:
                node = self.seed_nodes.pop(node_id)
                self.heartbeat_tracker.pop(node_id, None)

                if node.region and node_id in self.region_groups[node.region]:
                    self.region_groups[node.region].remove(node_id)

                logger.info(f"Unregistered seed node: {node_id[:8]}")

    async def get_best_seeds(self, count: int = 5, region: str = None) -> List[NodeInfo]:
        """获取最优种子节点"""
        async with self._lock:
            candidates = self.seed_nodes.values()

            if region:
                region_ids = self.region_groups.get(region, [])
                candidates = [n for n in candidates if n.node_id in region_ids]

            # 按信誉分和带宽评分排序
            sorted_seeds = sorted(
                candidates,
                key=lambda n: (n.reputation_score * 0.6 + n.bandwidth_score * 0.4),
                reverse=True
            )

            return sorted_seeds[:count]

    async def update_heartbeat(self, node_id: str):
        """更新心跳"""
        async with self._lock:
            self.heartbeat_tracker[node_id] = time.time()

    async def get_unhealthy_seeds(self, threshold: float = 300) -> List[str]:
        """获取不健康种子节点列表"""
        async with self._lock:
            now = time.time()
            return [
                node_id for node_id, last_beat in self.heartbeat_tracker.items()
                if now - last_beat > threshold
            ]


# ═══════════════════════════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════════════════════════


_dht_node: Optional[DHTNode] = None
_seed_manager: Optional[SeedNodeManager] = None


def get_dht_node() -> DHTNode:
    """获取全局 DHT 节点实例"""
    global _dht_node
    if _dht_node is None:
        _dht_node = DHTNode()
    return _dht_node


def get_seed_manager() -> SeedNodeManager:
    """获取全局种子节点管理器"""
    global _seed_manager
    if _seed_manager is None:
        _seed_manager = SeedNodeManager()
    return _seed_manager
