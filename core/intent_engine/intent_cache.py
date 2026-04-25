#!/usr/bin/env python3
"""
意图缓存系统 - IntentCache
Phase 2 核心：缓存意图理解结果，加速重复任务

Author: LivingTreeAI Team
Version: 1.0.0
"""

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import threading


class CacheStrategy(Enum):
    """缓存策略"""
    LRU = "lru"           # 最近最少使用
    LFU = "lfu"           # 最不经常使用
    TTL = "ttl"           # 基于时间
    FIFO = "fifo"        # 先进先出


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: Optional[float] = None  # Time-to-live in seconds
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl
    
    def access(self) -> Any:
        """访问缓存，更新统计"""
        self.last_accessed = time.time()
        self.access_count += 1
        return self.value


@dataclass
class CacheStats:
    """缓存统计"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    
    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "hit_rate": f"{self.hit_rate:.2%}",
        }


class IntentCache:
    """
    意图缓存系统
    
    核心功能：
    - 多级缓存策略 (LRU/LFU/TTL/FIFO)
    - 自动过期管理
    - 缓存预热
    - 统计监控
    - 线程安全
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        strategy: CacheStrategy = CacheStrategy.LRU,
        default_ttl: Optional[float] = 3600.0,
        enable_stats: bool = True,
    ):
        """
        初始化缓存
        
        Args:
            max_size: 最大缓存条目数
            strategy: 缓存策略
            default_ttl: 默认过期时间(秒)
            enable_stats: 是否启用统计
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._strategy = strategy
        self._default_ttl = default_ttl
        self._enable_stats = enable_stats
        self._stats = CacheStats()
        self._lock = threading.RLock()
        self._listeners: List[Callable] = []
        
        # 频率计数器 (用于LFU策略)
        self._frequency: Dict[str, int] = {}
        
        # 过期检查间隔
        self._cleanup_interval = 300  # 5分钟
        self._last_cleanup = time.time()
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            default: 默认值
            
        Returns:
            缓存值或默认值
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.misses += 1
                return default
            
            # 检查过期
            if entry.is_expired():
                self._remove_entry(key)
                self._stats.misses += 1
                self._stats.expirations += 1
                self._notify_listeners("expired", key)
                return default
            
            # 更新访问
            value = entry.access()
            
            # 调整顺序 (LRU策略)
            if self._strategy == CacheStrategy.LRU:
                self._cache.move_to_end(key)
            
            self._stats.hits += 1
            self._notify_listeners("hit", key)
            
            return value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间(秒)
            metadata: 元数据
        """
        with self._lock:
            # 检查容量
            if key not in self._cache and len(self._cache) >= self._max_size:
                self._evict()
            
            # 创建条目
            entry = CacheEntry(
                key=key,
                value=value,
                ttl=ttl if ttl is not None else self._default_ttl,
                metadata=metadata or {},
            )
            
            self._cache[key] = entry
            self._frequency[key] = 0
            self._notify_listeners("set", key)
    
    def delete(self, key: str) -> bool:
        """
        删除缓存
        
        Args:
            key: 缓存键
            
        Returns:
            是否删除成功
        """
        with self._lock:
            if key in self._cache:
                self._remove_entry(key)
                return True
            return False
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._frequency.clear()
            self._stats = CacheStats()
            self._notify_listeners("clear", None)
    
    def has(self, key: str) -> bool:
        """检查键是否存在"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                self._remove_entry(key)
                return False
            return True
    
    def _remove_entry(self, key: str) -> None:
        """移除条目"""
        if key in self._cache:
            del self._cache[key]
        if key in self._frequency:
            del self._frequency[key]
    
    def _evict(self) -> None:
        """驱逐条目"""
        if not self._cache:
            return
        
        evicted_key = None
        
        if self._strategy == CacheStrategy.LRU:
            # 驱逐最旧的
            evicted_key, _ = self._cache.popitem(last=False)
        elif self._strategy == CacheStrategy.FIFO:
            # 驱逐最早的
            evicted_key, _ = self._cache.popitem(last=False)
        elif self._strategy == CacheStrategy.LFU:
            # 驱逐访问最少的
            if self._frequency:
                evicted_key = min(self._frequency, key=self._frequency.get)
                self._cache.pop(evicted_key, None)
        elif self._strategy == CacheStrategy.TTL:
            # 驱逐已过期的
            for key, entry in list(self._cache.items()):
                if entry.is_expired():
                    evicted_key = key
                    break
            if evicted_key:
                self._remove_entry(evicted_key)
                self._stats.evictions += 1
        
        if evicted_key:
            self._remove_entry(evicted_key)
            self._stats.evictions += 1
            self._notify_listeners("evict", evicted_key)
    
    def cleanup(self) -> int:
        """
        清理过期条目
        
        Returns:
            清理的条目数
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                self._remove_entry(key)
                self._stats.expirations += 1
            
            return len(expired_keys)
    
    def warm_up(self, data: Dict[str, Any], ttl: Optional[float] = None) -> None:
        """
        缓存预热
        
        Args:
            data: 预热数据
            ttl: 过期时间
        """
        with self._lock:
            for key, value in data.items():
                self.set(key, value, ttl=ttl)
            self._notify_listeners("warm_up", len(data))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self._lock:
            return {
                **self._stats.to_dict(),
                "size": len(self._cache),
                "max_size": self._max_size,
                "strategy": self._strategy.value,
            }
    
    def add_listener(self, listener: Callable) -> None:
        """添加监听器"""
        self._listeners.append(listener)
    
    def _notify_listeners(self, event: str, key: Optional[str]) -> None:
        """通知监听器"""
        if self._enable_stats:
            for listener in self._listeners:
                try:
                    listener(event, key)
                except Exception:
                    pass
    
    def keys(self) -> List[str]:
        """获取所有键"""
        with self._lock:
            return list(self._cache.keys())
    
    def __len__(self) -> int:
        """缓存大小"""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """检查键是否存在"""
        return self.has(key)


def compute_intent_key(intent_text: str, context: Optional[Dict] = None) -> str:
    """
    计算意图缓存键
    
    Args:
        intent_text: 意图文本
        context: 上下文
        
    Returns:
        缓存键
    """
    data = {
        "intent": intent_text,
        "context": context or {},
    }
    json_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()[:32]


# 全局缓存实例
_global_cache: Optional[IntentCache] = None
_cache_lock = threading.Lock()


def get_intent_cache(
    max_size: int = 1000,
    strategy: CacheStrategy = CacheStrategy.LRU,
) -> IntentCache:
    """
    获取全局意图缓存实例
    
    Args:
        max_size: 最大缓存条目数
        strategy: 缓存策略
        
    Returns:
        意图缓存实例
    """
    global _global_cache
    
    with _cache_lock:
        if _global_cache is None:
            _global_cache = IntentCache(
                max_size=max_size,
                strategy=strategy,
            )
        return _global_cache


def cached_intent(ttl: Optional[float] = None):
    """
    意图缓存装饰器
    
    Args:
        ttl: 过期时间
        
    Returns:
        装饰器函数
    """
    cache = get_intent_cache()
    
    def decorator(func: Callable) -> Callable:
        def wrapper(intent_text: str, **kwargs) -> Any:
            # 计算缓存键
            context = kwargs.get("context", {})
            cache_key = compute_intent_key(intent_text, context)
            
            # 尝试从缓存获取
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # 执行函数
            result = func(intent_text, **kwargs)
            
            # 存入缓存
            cache.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    
    return decorator


# 便捷函数
def cache_intent(key: str, value: Any, ttl: Optional[float] = None) -> None:
    """缓存意图结果"""
    get_intent_cache().set(key, value, ttl=ttl)


def get_cached_intent(key: str, default: Any = None) -> Any:
    """获取缓存的意图结果"""
    return get_intent_cache().get(key, default)


def clear_intent_cache() -> None:
    """清空意图缓存"""
    get_intent_cache().clear()
