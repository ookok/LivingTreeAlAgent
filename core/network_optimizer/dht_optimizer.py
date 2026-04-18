"""
DHT网络优化

基于Kademlia的分布式哈希表优化
- 动态K值
- 节点分级
- 缓存优化
- 并行查询
"""

import asyncio
import hashlib
from collections import defaultdict
from typing import Optional

from .models import NodeInfo, KBucket, NodeLevel


class DHTOptimizer:
    """
    DHT网络优化器
    
    Features:
    - Kademlia路由表优化
    - 动态K桶管理
    - 节点分级缓存
    - 并行查询
    """
    
    def __init__(self, node_id: str, alpha: int = 3, k: int = 20):
        self.node_id = node_id
        self.alpha = alpha  # 并行查询数
        self.k = k  # K桶大小
        
        # K桶路由表: {distance_prefix: KBucket}
        self.routing_table: dict[str, KBucket] = {}
        
        # 缓存查询结果
        self.query_cache: dict[str, tuple[list, float]] = {}
        self.cache_ttl = 60  # 缓存TTL: 秒
        
        # 节点信息
        self.nodes: dict[str, NodeInfo] = {}
        
        # 超级节点缓存
        self.super_node_cache: list[NodeInfo] = []
    
    def _xor_distance(self, id1: str, id2: str) -> int:
        """计算XOR距离"""
        h1 = int(hashlib.sha256(id1.encode()).hexdigest(), 16)
        h2 = int(hashlib.sha256(id2.encode()).hexdigest(), 16)
        return h1 ^ h2
    
    def _get_bucket_key(self, node_id: str) -> str:
        """获取节点所属的K桶键"""
        distance = self._xor_distance(self.node_id, node_id)
        # 根据距离分层
        if distance < 2**16:
            return "close"
        elif distance < 2**32:
            return "medium"
        else:
            return "far"
    
    def _get_bucket(self, node_id: str) -> KBucket:
        """获取或创建K桶"""
        key = self._get_bucket_key(node_id)
        if key not in self.routing_table:
            self.routing_table[key] = KBucket(node_id_prefix=key, max_size=self.k)
        return self.routing_table[key]
    
    def add_node(self, node: NodeInfo) -> bool:
        """
        添加节点到路由表
        
        Args:
            node: 节点信息
            
        Returns:
            bool: 是否添加成功
        """
        if node.node_id == self.node_id:
            return False
        
        self.nodes[node.node_id] = node
        
        # 超级节点特殊处理
        if node.level == NodeLevel.SUPER:
            if node not in self.super_node_cache:
                self.super_node_cache.append(node)
        
        bucket = self._get_bucket(node.node_id)
        return bucket.add_node(node)
    
    def remove_node(self, node_id: str):
        """从路由表移除节点"""
        if node_id in self.nodes:
            del self.nodes[node_id]
        
        for bucket in self.routing_table.values():
            for i, n in enumerate(bucket.nodes):
                if n.node_id == node_id:
                    bucket.nodes.pop(i)
                    break
    
    def get_closest_nodes(self, key: str, count: int = None) -> list[NodeInfo]:
        """
        获取最近的节点
        
        Args:
            key: 目标键
            count: 返回数量
            
        Returns:
            list[NodeInfo]: 最近的节点列表
        """
        count = count or self.alpha
        
        # 按距离排序
        sorted_nodes = sorted(
            self.nodes.values(),
            key=lambda n: self._xor_distance(self.node_id, key)
        )
        
        return sorted_nodes[:count]
    
    async def lookup(self, key: str, parallel: bool = True) -> list:
        """
        在DHT网络查找值
        
        Args:
            key: 要查找的键
            parallel: 是否并行查询
            
        Returns:
            list: 查找到的值列表
        """
        import time
        
        # 检查缓存
        now = time.time()
        if key in self.query_cache:
            cached_values, cache_time = self.query_cache[key]
            if now - cache_time < self.cache_ttl:
                return cached_values
        
        # 获取最近的节点
        closest = self.get_closest_nodes(key, self.alpha)
        
        if not closest:
            return []
        
        if parallel:
            # 并行查询
            tasks = [self._query_node(node, key) for node in closest]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            values = []
            for result in results:
                if isinstance(result, list):
                    values.extend(result)
        else:
            # 串行查询
            values = []
            for node in closest:
                try:
                    node_values = await self._query_node(node, key)
                    values.extend(node_values)
                    if values:
                        break
                except Exception:
                    continue
        
        # 缓存结果
        if values:
            self.query_cache[key] = (values, now)
        
        return values
    
    async def _query_node(self, node: NodeInfo, key: str) -> list:
        """查询单个节点"""
        return []
    
    async def store(self, key: str, value: bytes, peers: list[str]) -> bool:
        """
        存储值到DHT网络
        
        Args:
            key: 键
            value: 值
            peers: 存储到的节点ID列表
            
        Returns:
            bool: 是否存储成功
        """
        success_count = 0
        
        for peer_id in peers:
            node = self.nodes.get(peer_id)
            if not node:
                continue
            
            try:
                stored = await self._store_to_node(node, key, value)
                if stored:
                    success_count += 1
            except Exception:
                continue
        
        return success_count >= self.k // 2
    
    async def _store_to_node(self, node: NodeInfo, key: str, value: bytes) -> bool:
        """存储值到单个节点"""
        return True
    
    def refresh_bucket(self, bucket_key: str):
        """刷新K桶"""
        if bucket_key not in self.routing_table:
            return
        
        bucket = self.routing_table[bucket_key]
        import time
        bucket.last_refresh = time.time()
        
        # 移除长时间不活跃的节点
        now = time.time()
        bucket.nodes = [
            n for n in bucket.nodes
            if now - n.last_seen < 3600
        ]
    
    def get_stats(self) -> dict:
        """获取DHT统计"""
        total_nodes = len(self.nodes)
        super_nodes = sum(1 for n in self.nodes.values() if n.level == NodeLevel.SUPER)
        
        return {
            "total_nodes": total_nodes,
            "super_nodes": super_nodes,
            "buckets": len(self.routing_table),
            "cache_size": len(self.query_cache),
            "alpha": self.alpha,
            "k": self.k,
        }
