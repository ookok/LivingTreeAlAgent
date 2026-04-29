"""
L1 内存缓存模块
基于 LRU + 热度加权的内存缓存实现
"""

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from threading import RLock
import time
import hashlib
import json


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int = 1
    heat_weight: float = 1.0  # 热度加权值
    
    def update_access(self):
        """更新访问信息"""
        self.last_accessed = time.time()
        self.access_count += 1
        # 热度加权：频繁访问的项延长有效期
        if self.access_count > 5:
            self.heat_weight = min(2.0, 1.0 + (self.access_count - 5) * 0.1)
    
    def is_expired(self, ttl: int, current_time: float = None) -> bool:
        """检查是否过期"""
        if current_time is None:
            current_time = time.time()
        effective_ttl = ttl * self.heat_weight
        return (current_time - self.created_at) > effective_ttl


class MemoryCache:
    """
    L1 内存缓存
    - 容量：100-500条
    - 策略：LRU + 热度加权
    - 过期：15分钟TTL（可动态调整）
    """
    
    def __init__(self, max_items: int = 100, ttl_seconds: int = 900, heat_threshold: float = 3.0):
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds
        self.heat_threshold = heat_threshold
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = RLock()
        self._hits = 0
        self._misses = 0
    
    def _generate_key(self, query: str, context: str = None) -> str:
        """生成缓存键"""
        content = f"{query}|{context or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def get(self, query: str, context: str = None) -> Optional[Any]:
        """获取缓存"""
        with self._lock:
            key = self._generate_key(query, context)
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                return None
            
            # 检查过期
            if entry.is_expired(self.ttl_seconds):
                del self._cache[key]
                self._misses += 1
                return None
            
            # 更新访问信息并移到末尾（最近使用）
            entry.update_access()
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value
    
    def set(self, query: str, value: Any, context: str = None):
        """设置缓存"""
        with self._lock:
            key = self._generate_key(query, context)
            
            # 如果已存在，更新值
            if key in self._cache:
                entry = self._cache[key]
                entry.value = value
                entry.created_at = time.time()
                entry.last_accessed = time.time()
                self._cache.move_to_end(key)
                return
            
            # 如果达到容量，删除最旧的条目
            if len(self._cache) >= self.max_items:
                # 删除热度最低且最旧的
                self._evict_one()
            
            # 添加新条目
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                last_accessed=time.time()
            )
            self._cache[key] = entry
    
    def _evict_one(self):
        """驱逐一个条目（LRU + 热度加权）"""
        if not self._cache:
            return
        
        # 找出需要驱逐的条目：优先驱逐热度低且久未访问的
        items = list(self._cache.items())
        worst_score = float('inf')
        worst_key = None
        
        for key, entry in items:
            # 计算驱逐分数：越低越优先驱逐
            age = time.time() - entry.last_accessed
            score = entry.heat_weight / (1 + age / 60)  # 热度高但久未访问也会被驱逐
            if score < worst_score:
                worst_score = score
                worst_key = key
        
        if worst_key:
            del self._cache[worst_key]
    
    def invalidate(self, query: str, context: str = None):
        """使缓存失效"""
        with self._lock:
            key = self._generate_key(query, context)
            self._cache.pop(key, None)
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            
            return {
                "size": len(self._cache),
                "max_size": self.max_items,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "ttl_seconds": self.ttl_seconds
            }
    
    def update_ttl(self, new_ttl: int):
        """动态调整TTL"""
        self.ttl_seconds = new_ttl
    
    def warm_up(self, items: list):
        """预热缓存"""
        with self._lock:
            for query, value, context in items[:self.max_items]:
                self.set(query, value, context)
