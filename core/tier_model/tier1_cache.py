"""
L1 即时缓存层
毫秒级响应，处理目标：命中率 > 40%
"""

import time
from typing import Optional, Any, Dict
from dataclasses import dataclass

from .memory_cache import MemoryCache


@dataclass
class CacheHit:
    """缓存命中结果"""
    tier: str = "L1"
    response: Any = None
    latency_ms: float = 0
    confidence: float = 1.0


class Tier1Cache:
    """
    L1 即时缓存层
    - 处理目标：毫秒级响应
    - 命中率目标：> 40%
    - 策略：精确匹配 + 模糊匹配 + 热度加权
    """
    
    def __init__(self, memory_cache: MemoryCache = None):
        self.cache = memory_cache or MemoryCache(max_items=100, ttl_seconds=900)
        self._total_requests = 0
        self._cache_hits = 0
    
    def get(self, query: str, context: str = None) -> Optional[CacheHit]:
        """获取缓存结果"""
        start = time.perf_counter()
        self._total_requests += 1
        
        result = self.cache.get(query, context)
        
        if result is not None:
            self._cache_hits += 1
            latency = (time.perf_counter() - start) * 1000
            return CacheHit(
                tier="L1",
                response=result,
                latency_ms=latency,
                confidence=1.0
            )
        
        return None
    
    def set(self, query: str, response: Any, context: str = None):
        """设置缓存"""
        self.cache.set(query, response, context)
    
    def get_hit_rate(self) -> float:
        """获取命中率"""
        if self._total_requests == 0:
            return 0.0
        return self._cache_hits / self._total_requests
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.cache.get_stats()
        stats["target_hit_rate"] = 0.40
        stats["meets_target"] = stats["hit_rate"] >= 0.40
        return stats
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self._total_requests = 0
        self._cache_hits = 0
