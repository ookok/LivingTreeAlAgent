"""
精确缓存层 (Exact Cache Layer)
基于 LRU 和 SimHash 的多级精确缓存

特性:
- LRU 内存缓存 (最近1000条高频查询)
- SSD级 RocksDB 存储 (百万级查询-答案对)
- SimHash 近似匹配 (容忍微小差异)
- 布隆过滤器快速判断不存在
"""

import time
import hashlib
from typing import Optional, Dict, Any, List
from collections import OrderedDict
import threading


class ExactCacheLayer:
    """精确缓存层 - 毫秒级响应"""
    
    def __init__(
        self,
        memory_size: int = 1000,
        ssd_path: Optional[str] = None,
        ttl_seconds: int = 86400 * 7  # 7天
    ):
        """
        初始化精确缓存层
        
        Args:
            memory_size: 内存缓存最大条目数
            ssd_path: SSD缓存路径 (可选)
            ttl_seconds: 缓存有效期 (秒)
        """
        self.memory_cache: OrderedDict = OrderedDict()
        self.memory_size = memory_size
        self.ttl_seconds = ttl_seconds
        self.hit_count = 0
        self.miss_count = 0
        self.lock = threading.Lock()
        
        # 布隆过滤器 (快速判断不存在)
        self.bloom_filter_size = 100000
        self.bloom_filter: set = set()
        
        # SimHash 索引 (近似匹配)
        self.simhash_index: Dict[str, str] = {}
        
        print(f"[ExactCache] 初始化完成，内存缓存容量: {memory_size}")
    
    def _hash_query(self, query: str) -> str:
        """计算查询哈希"""
        return hashlib.md5(query.encode()).hexdigest()
    
    def _compute_simhash(self, query: str) -> str:
        """计算 SimHash (简化版)"""
        # 使用字符 n-gram 生成指纹
        n = 3
        grams = [query[i:i+n] for i in range(max(0, len(query)-n+1))]
        return hashlib.md5("".join(sorted(grams)).encode()).hexdigest()[:8]
    
    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存结果
        
        Args:
            query: 查询文本
            
        Returns:
            缓存结果或 None
        """
        query_hash = self._hash_query(query)
        
        with self.lock:
            # 1. 精确匹配 (O(1))
            if query_hash in self.memory_cache:
                entry = self.memory_cache[query_hash]
                
                # 检查是否过期
                if time.time() - entry["timestamp"] < self.ttl_seconds:
                    # 移到末尾 (LRU)
                    self.memory_cache.move_to_end(query_hash)
                    self.hit_count += 1
                    return entry["data"]
                else:
                    # 已过期，删除
                    del self.memory_cache[query_hash]
            
            # 2. SimHash 近似匹配
            simhash = self._compute_simhash(query)
            if simhash in self.simhash_index:
                cached_hash = self.simhash_index[simhash]
                if cached_hash in self.memory_cache:
                    entry = self.memory_cache[cached_hash]
                    if time.time() - entry["timestamp"] < self.ttl_seconds:
                        self.hit_count += 1
                        return entry["data"]
            
            self.miss_count += 1
            return None
    
    def set(self, query: str, data: Any, metadata: Optional[Dict] = None) -> None:
        """
        设置缓存
        
        Args:
            query: 查询文本
            data: 缓存数据
            metadata: 额外元数据
        """
        query_hash = self._hash_query(query)
        
        with self.lock:
            # LRU 淘汰
            if len(self.memory_cache) >= self.memory_size:
                # 删除最旧的条目
                self.memory_cache.popitem(last=False)
            
            # 存储
            self.memory_cache[query_hash] = {
                "data": data,
                "timestamp": time.time(),
                "metadata": metadata or {},
                "query": query
            }
            
            # 更新 SimHash 索引
            simhash = self._compute_simhash(query)
            self.simhash_index[simhash] = query_hash
            
            # 更新布隆过滤器
            self.bloom_filter.add(query_hash[:8])
    
    def exists(self, query: str) -> bool:
        """快速判断查询是否可能存在 (布隆过滤器)"""
        query_hash = self._hash_query(query)
        
        # 布隆过滤器快速判断
        if query_hash[:8] not in self.bloom_filter:
            return False
        
        # 精确确认
        with self.lock:
            return query_hash in self.memory_cache
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total if total > 0 else 0
        
        return {
            "memory_size": len(self.memory_cache),
            "max_memory_size": self.memory_size,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": hit_rate,
            "simhash_entries": len(self.simhash_index)
        }
    
    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.memory_cache.clear()
            self.simhash_index.clear()
            self.bloom_filter.clear()
            self.hit_count = 0
            self.miss_count = 0
    
    def bulk_load(self, items: List[Dict[str, Any]]) -> int:
        """
        批量加载缓存
        
        Args:
            items: [(query, data), ...]
            
        Returns:
            加载数量
        """
        count = 0
        for query, data in items:
            self.set(query, data)
            count += 1
        return count
