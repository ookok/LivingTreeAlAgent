"""
缓存层 (Cache Layer)

提供统一的缓存管理，支持多种缓存策略和过期机制。
"""

import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    expire_at: float  # 过期时间戳
    hit_count: int = 0  # 命中次数
    created_at: float = field(default_factory=lambda: time.time())


class CacheLayer:
    """
    缓存层
    
    功能：
    1. 基础缓存操作：get/set/invalidate
    2. TTL过期机制
    3. 缓存统计
    4. 多级缓存支持
    5. 缓存预热
    
    使用方式：
    cache = CacheLayer(default_ttl=3600)
    cache.set("user:1", user_data)
    user = cache.get("user:1")
    """
    
    def __init__(self, default_ttl: int = 3600, max_size: int = 10000):
        """
        初始化缓存层
        
        Args:
            default_ttl: 默认过期时间（秒）
            max_size: 最大缓存条目数
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = Lock()
        
        # 统计信息
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "invalidations": 0,
            "evictions": 0
        }
        
        print("[CacheLayer] 初始化完成")
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，如果不存在或已过期返回None
        """
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None
            
            entry = self._cache[key]
            
            # 检查是否过期
            if time.time() > entry.expire_at:
                del self._cache[key]
                self._stats["misses"] += 1
                return None
            
            # 更新命中次数
            entry.hit_count += 1
            self._stats["hits"] += 1
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），默认使用default_ttl
        """
        with self._lock:
            # 检查是否需要清理
            if len(self._cache) >= self._max_size:
                self._evict_old_entries()
            
            # 设置缓存
            expire_at = time.time() + (ttl or self._default_ttl)
            self._cache[key] = CacheEntry(
                value=value,
                expire_at=expire_at
            )
            
            self._stats["sets"] += 1
    
    def invalidate(self, key: str):
        """
        失效指定缓存
        
        Args:
            key: 缓存键
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats["invalidations"] += 1
    
    def invalidate_pattern(self, pattern: str):
        """
        按模式失效缓存
        
        Args:
            pattern: 匹配模式（支持*通配符）
        """
        with self._lock:
            keys_to_delete = []
            for key in self._cache:
                if self._match_pattern(key, pattern):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self._cache[key]
                self._stats["invalidations"] += 1
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """
        简单的模式匹配
        
        Args:
            key: 缓存键
            pattern: 模式（支持*通配符）
            
        Returns:
            是否匹配
        """
        # 将模式转换为简单的正则
        regex_pattern = pattern.replace('*', '.*')
        import re
        return bool(re.match(regex_pattern, key))
    
    def _evict_old_entries(self):
        """
        淘汰最老的缓存条目
        """
        # 按创建时间排序，淘汰最老的20%
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].created_at
        )
        
        # 淘汰数量
        evict_count = max(1, len(self._cache) // 5)
        
        for key, _ in sorted_entries[:evict_count]:
            del self._cache[key]
            self._stats["evictions"] += 1
    
    def clear(self):
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()
    
    def warm_up(self, data: Dict[str, Any]):
        """
        缓存预热
        
        Args:
            data: 预加载的数据
        """
        for key, value in data.items():
            self.set(key, value)
        
        print(f"[CacheLayer] 缓存预热完成，加载 {len(data)} 条数据")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        stats = dict(self._stats)
        stats["total_entries"] = len(self._cache)
        stats["hit_rate"] = (stats["hits"] / max(stats["hits"] + stats["misses"], 1)) * 100
        
        return stats
    
    def get_entry_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存条目的详细信息
        
        Args:
            key: 缓存键
            
        Returns:
            条目信息，如果不存在返回None
        """
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            
            return {
                "expire_at": entry.expire_at,
                "hit_count": entry.hit_count,
                "created_at": entry.created_at,
                "ttl_remaining": max(0, int(entry.expire_at - time.time()))
            }


class MultiLevelCache:
    """
    多级缓存
    
    支持多级缓存策略，如：
    - L1: 内存缓存（快速访问）
    - L2: 文件缓存（大容量）
    
    当前实现简化为单级内存缓存。
    """
    
    def __init__(self):
        self._l1_cache = CacheLayer(default_ttl=300)  # 5分钟
        self._l2_cache = CacheLayer(default_ttl=3600)  # 1小时
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值（先查L1，再查L2）"""
        # 先查L1
        value = self._l1_cache.get(key)
        if value is not None:
            return value
        
        # 再查L2
        value = self._l2_cache.get(key)
        if value is not None:
            # 提升到L1
            self._l1_cache.set(key, value)
            return value
        
        return None
    
    def set(self, key: str, value: Any, level: int = 1):
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            level: 缓存级别（1=L1, 2=L2）
        """
        if level == 1:
            self._l1_cache.set(key, value)
        else:
            self._l2_cache.set(key, value)
    
    def invalidate(self, key: str):
        """失效所有级别的缓存"""
        self._l1_cache.invalidate(key)
        self._l2_cache.invalidate(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "l1": self._l1_cache.get_stats(),
            "l2": self._l2_cache.get_stats()
        }


# 全局缓存实例
_global_cache = CacheLayer()


def get_cache() -> CacheLayer:
    """获取全局缓存实例"""
    return _global_cache


def cache_get(key: str) -> Optional[Any]:
    """从全局缓存获取值"""
    return _global_cache.get(key)


def cache_set(key: str, value: Any, ttl: Optional[int] = None):
    """设置全局缓存值"""
    _global_cache.set(key, value, ttl)


def cache_invalidate(key: str):
    """失效全局缓存"""
    _global_cache.invalidate(key)


__all__ = [
    "CacheLayer",
    "MultiLevelCache",
    "CacheEntry",
    "get_cache",
    "cache_get",
    "cache_set",
    "cache_invalidate"
]