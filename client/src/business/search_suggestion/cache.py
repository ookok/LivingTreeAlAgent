# -*- coding: utf-8 -*-
"""
搜索建议缓存模块
LRU 缓存 + TTL 过期
"""

import time
from collections import OrderedDict
from typing import Dict, List, Optional, Any
from threading import Lock
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    timestamp: float
    ttl: float  # 生存时间（秒）
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() - self.timestamp > self.ttl


class LRUCache:
    """LRU 缓存实现"""
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 300):
        """
        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认过期时间（秒）
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            
            # 检查过期
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None
            
            # 移到末尾（最近使用）
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: float = None):
        """设置缓存值"""
        with self._lock:
            ttl = ttl if ttl is not None else self.default_ttl
            
            # 如果已存在，删除旧条目
            if key in self._cache:
                del self._cache[key]
            
            # 添加新条目
            self._cache[key] = CacheEntry(
                value=value,
                timestamp=time.time(),
                ttl=ttl
            )
            
            # 如果超过最大大小，删除最旧的条目
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)
    
    def delete(self, key: str):
        """删除缓存值"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def cleanup_expired(self):
        """清理过期条目"""
        with self._lock:
            expired_keys = [
                k for k, v in self._cache.items() 
                if v.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
    
    @property
    def hit_rate(self) -> float:
        """缓存命中率"""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
    
    def __len__(self) -> int:
        return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        with self._lock:
            return key in self._cache and not self._cache[key].is_expired()


class SuggestionCache:
    """搜索建议专用缓存"""
    
    # 缓存键前缀
    PREFIX_HISTORY = "history:"
    PREFIX_KB = "kb:"
    PREFIX_SUGGESTION = "suggestion:"
    
    def __init__(self, max_size: int = 5000, default_ttl: float = 300):
        self._history_cache = LRUCache(max_size // 2, default_ttl=3600 * 24)  # 历史缓存24小时
        self._kb_cache = LRUCache(max_size // 2, default_ttl=default_ttl)  # 知识库缓存5分钟
        self._suggestion_cache = LRUCache(max_size, default_ttl=60)  # 建议缓存1分钟
    
    def get_history(self, query: str) -> Optional[List[Dict]]:
        """获取历史建议"""
        key = f"{self.PREFIX_HISTORY}{query.lower()}"
        return self._history_cache.get(key)
    
    def set_history(self, query: str, suggestions: List[Dict]):
        """缓存历史建议"""
        key = f"{self.PREFIX_HISTORY}{query.lower()}"
        self._history_cache.set(key, suggestions)
    
    def get_knowledge(self, query: str) -> Optional[List[Dict]]:
        """获取知识库建议"""
        key = f"{self.PREFIX_KB}{query.lower()}"
        return self._kb_cache.get(key)
    
    def set_knowledge(self, query: str, suggestions: List[Dict]):
        """缓存知识库建议"""
        key = f"{self.PREFIX_KB}{query.lower()}"
        self._kb_cache.set(key, suggestions, ttl=300)
    
    def get_suggestions(self, query: str) -> Optional[List[Dict]]:
        """获取合并后的建议"""
        key = f"{self.PREFIX_SUGGESTION}{query.lower()}"
        return self._suggestion_cache.get(key)
    
    def set_suggestions(self, query: str, suggestions: List[Dict]):
        """缓存合并后的建议"""
        key = f"{self.PREFIX_SUGGESTION}{query.lower()}"
        self._suggestion_cache.set(key, suggestions, ttl=60)
    
    def add_to_history(self, query: str):
        """将搜索记录添加到历史缓存"""
        # 更新历史缓存，使最新搜索排在前面
        existing = self.get_history(query) or []
        
        # 添加新记录（时间戳）
        new_entry = {
            "text": query,
            "timestamp": time.time(),
            "count": 1
        }
        
        # 更新或添加
        found = False
        for item in existing:
            if item["text"] == query:
                item["timestamp"] = time.time()
                item["count"] += 1
                found = True
                break
        
        if not found:
            existing.insert(0, new_entry)
        
        # 限制大小
        existing = existing[:100]
        self.set_history(query, existing)
    
    def invalidate(self, query: str = None):
        """失效缓存"""
        if query:
            query_lower = query.lower()
            self._history_cache.delete(f"{self.PREFIX_HISTORY}{query_lower}")
            self._kb_cache.delete(f"{self.PREFIX_KB}{query_lower}")
            self._suggestion_cache.delete(f"{self.PREFIX_SUGGESTION}{query_lower}")
        else:
            self._history_cache.clear()
            self._kb_cache.clear()
            self._suggestion_cache.clear()
    
    def cleanup(self):
        """清理过期缓存"""
        self._history_cache.cleanup_expired()
        self._kb_cache.cleanup_expired()
        self._suggestion_cache.cleanup_expired()
    
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        return {
            "history_size": len(self._history_cache),
            "kb_size": len(self._kb_cache),
            "suggestion_size": len(self._suggestion_cache),
            "history_hit_rate": self._history_cache.hit_rate,
            "kb_hit_rate": self._kb_cache.hit_rate,
            "suggestion_hit_rate": self._suggestion_cache.hit_rate,
        }


# 全局实例
_cache = SuggestionCache()


def get_suggestion_cache() -> SuggestionCache:
    """获取全局建议缓存"""
    return _cache
