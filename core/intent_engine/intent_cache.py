"""
意图缓存 - 缓存意图解析和执行结果
"""

from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import hashlib
import time
from collections import OrderedDict


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    accessed_at: float
    access_count: int = 0
    ttl: Optional[float] = None  # Time to live in seconds
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl


class IntentCache:
    """
    意图缓存
    
    功能：
    1. LRU缓存策略
    2. TTL过期机制
    3. 缓存统计
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 3600):
        """
        初始化缓存
        
        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认TTL（秒）
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
        }
        
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，如果不存在或过期返回None
        """
        entry = self._cache.get(key)
        
        if entry is None:
            self._stats['misses'] += 1
            return None
            
        # 检查过期
        if entry.is_expired():
            self._remove(key)
            self._stats['misses'] += 1
            return None
            
        # 更新访问信息
        entry.accessed_at = time.time()
        entry.access_count += 1
        
        # 移到末尾（LRU）
        self._cache.move_to_end(key)
        
        self._stats['hits'] += 1
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
        """
        now = time.time()
        
        # 如果已存在，更新
        if key in self._cache:
            self._cache[key] = CacheEntry(
                key=key,
                value=value,
                created_at=self._cache[key].created_at,
                accessed_at=now,
                ttl=ttl or self.default_ttl,
            )
        else:
            # 新增
            self._cache[key] = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                accessed_at=now,
                ttl=ttl or self.default_ttl,
            )
            
            # LRU淘汰
            if len(self._cache) > self.max_size:
                self._evict_oldest()
                
        self._cache.move_to_end(key)
        
    def _evict_oldest(self):
        """淘汰最老的条目"""
        if self._cache:
            self._remove(next(iter(self._cache)))
            self._stats['evictions'] += 1
            
    def _remove(self, key: str):
        """移除缓存条目"""
        self._cache.pop(key, None)
        
    def invalidate(self, key: str):
        """使缓存失效"""
        self._remove(key)
        
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total if total > 0 else 0.0
        
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'evictions': self._stats['evictions'],
            'hit_rate': hit_rate,
        }
        
    @staticmethod
    def generate_key(intent_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """生成缓存键"""
        content = intent_text
        if context:
            content += str(sorted(context.items()))
        return hashlib.md5(content.encode()).hexdigest()
