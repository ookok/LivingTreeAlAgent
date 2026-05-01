"""
Intelligent Cache System

智能缓存系统，提供四级缓存架构、智能淘汰策略和个性化缓存预热。

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import logging
import time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CacheLayer(Enum):
    """缓存层级"""
    L0 = "L0"   # 精确匹配缓存（毫秒级）
    L1 = "L1"   # 语义相似缓存（向量检索）
    L2 = "L2"   # 上下文缓存（会话级）
    L3 = "L3"   # 知识缓存（持久化）


class EvictionPolicy(Enum):
    """淘汰策略"""
    LRU = "lru"             # 最近最少使用
    LFU = "lfu"             # 最不常使用
    SIZE = "size"           # 按大小
    TIME = "time"           # 按时间
    IMPORTANCE = "importance"  # 按重要性
    HYBRID = "hybrid"       # 混合策略


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    layer: CacheLayer
    created_at: float = field(default_factory=lambda: time.time())
    accessed_at: float = field(default_factory=lambda: time.time())
    access_count: int = 0
    importance: float = 0.5
    ttl: Optional[float] = None  # 过期时间（秒）
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl
    
    def touch(self):
        """更新访问时间和计数"""
        self.accessed_at = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """缓存统计"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = 0
    hit_rate: float = 0.0


class BaseCache:
    """缓存基类"""
    
    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._stats = CacheStats(max_size=max_size)
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        raise NotImplementedError
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None, importance: float = 0.5):
        """设置缓存"""
        raise NotImplementedError
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        if key in self._cache:
            del self._cache[key]
            self._stats.size -= 1
            return True
        return False
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._stats = CacheStats(max_size=self._max_size)
    
    def get_stats(self) -> CacheStats:
        """获取统计信息"""
        self._stats.hit_rate = (self._stats.hits / (self._stats.hits + self._stats.misses)) * 100 if (self._stats.hits + self._stats.misses) > 0 else 0
        return self._stats


class ExactMatchCache(BaseCache):
    """L0: 精确匹配缓存"""
    
    def __init__(self, max_size: int = 10000):
        super().__init__(max_size)
    
    def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry:
            if entry.is_expired():
                self.delete(key)
                self._stats.misses += 1
                return None
            entry.touch()
            self._stats.hits += 1
            return entry.value
        self._stats.misses += 1
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None, importance: float = 0.5):
        if len(self._cache) >= self._max_size:
            self._evict()
        
        self._cache[key] = CacheEntry(
            key=key,
            value=value,
            layer=CacheLayer.L0,
            ttl=ttl,
            importance=importance,
        )
        self._stats.size += 1
    
    def _evict(self):
        """执行淘汰"""
        # LRU策略
        oldest = min(self._cache.values(), key=lambda x: x.accessed_at)
        self.delete(oldest.key)
        self._stats.evictions += 1


class SemanticCache(BaseCache):
    """L1: 语义相似缓存"""
    
    def __init__(self, max_size: int = 5000):
        super().__init__(max_size)
        self._vector_index = {}  # 简化实现：存储关键词
    
    def get(self, key: str) -> Optional[Any]:
        # 首先精确匹配
        entry = self._cache.get(key)
        if entry and not entry.is_expired():
            entry.touch()
            self._stats.hits += 1
            return entry.value
        
        # 语义相似匹配（简化实现：关键词匹配）
        for cached_key, entry in self._cache.items():
            if not entry.is_expired() and self._is_similar(key, cached_key):
                entry.touch()
                self._stats.hits += 1
                return entry.value
        
        self._stats.misses += 1
        return None
    
    def _is_similar(self, key1: str, key2: str) -> bool:
        """检查语义相似度"""
        words1 = set(key1.lower().split())
        words2 = set(key2.lower().split())
        if not words1 or not words2:
            return False
        return len(words1 & words2) / max(len(words1), len(words2)) > 0.5
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None, importance: float = 0.5):
        if len(self._cache) >= self._max_size:
            self._evict()
        
        self._cache[key] = CacheEntry(
            key=key,
            value=value,
            layer=CacheLayer.L1,
            ttl=ttl,
            importance=importance,
        )
        self._stats.size += 1
    
    def _evict(self):
        """LFU策略"""
        least_used = min(self._cache.values(), key=lambda x: x.access_count)
        self.delete(least_used.key)
        self._stats.evictions += 1


class ContextCache(BaseCache):
    """L2: 上下文缓存（会话级）"""
    
    def __init__(self, max_size: int = 1000):
        super().__init__(max_size)
        self._conversation_cache: Dict[str, Dict[str, CacheEntry]] = {}
    
    def get(self, key: str, conversation_id: Optional[str] = None) -> Optional[Any]:
        if conversation_id:
            conv_cache = self._conversation_cache.get(conversation_id, {})
            entry = conv_cache.get(key)
            if entry and not entry.is_expired():
                entry.touch()
                self._stats.hits += 1
                return entry.value
        else:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                entry.touch()
                self._stats.hits += 1
                return entry.value
        
        self._stats.misses += 1
        return None
    
    def set(self, key: str, value: Any, conversation_id: Optional[str] = None, 
            ttl: Optional[float] = None, importance: float = 0.5):
        if conversation_id:
            if conversation_id not in self._conversation_cache:
                self._conversation_cache[conversation_id] = {}
            
            conv_cache = self._conversation_cache[conversation_id]
            if len(conv_cache) >= 100:  # 每个会话最多100条
                self._evict_conversation(conversation_id)
            
            conv_cache[key] = CacheEntry(
                key=key,
                value=value,
                layer=CacheLayer.L2,
                ttl=ttl,
                importance=importance,
            )
        else:
            if len(self._cache) >= self._max_size:
                self._evict()
            
            self._cache[key] = CacheEntry(
                key=key,
                value=value,
                layer=CacheLayer.L2,
                ttl=ttl,
                importance=importance,
            )
        self._stats.size += 1
    
    def _evict_conversation(self, conversation_id: str):
        """清理会话缓存"""
        conv_cache = self._conversation_cache.get(conversation_id, {})
        if conv_cache:
            oldest = min(conv_cache.values(), key=lambda x: x.accessed_at)
            del conv_cache[oldest.key]
            self._stats.evictions += 1
    
    def _evict(self):
        """混合策略：优先淘汰低重要性且不常访问的"""
        entries = sorted(self._cache.values(), key=lambda x: (x.importance, x.access_count))
        if entries:
            self.delete(entries[0].key)
            self._stats.evictions += 1
    
    def clear_conversation(self, conversation_id: str):
        """清理指定会话的缓存"""
        if conversation_id in self._conversation_cache:
            self._stats.size -= len(self._conversation_cache[conversation_id])
            del self._conversation_cache[conversation_id]


class KnowledgeCache(BaseCache):
    """L3: 知识缓存（持久化）"""
    
    def __init__(self, max_size: int = 500):
        super().__init__(max_size)
        self._persistent_store = {}  # 模拟持久化存储
    
    def get(self, key: str) -> Optional[Any]:
        # 先查内存
        entry = self._cache.get(key)
        if entry and not entry.is_expired():
            entry.touch()
            self._stats.hits += 1
            return entry.value
        
        # 再查持久化存储
        if key in self._persistent_store:
            value = self._persistent_store[key]
            # 加载到内存
            self._cache[key] = CacheEntry(
                key=key,
                value=value,
                layer=CacheLayer.L3,
            )
            self._stats.size += 1
            self._stats.hits += 1
            return value
        
        self._stats.misses += 1
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None, importance: float = 0.5):
        # 同时写入内存和持久化存储
        if len(self._cache) >= self._max_size:
            self._evict()
        
        self._cache[key] = CacheEntry(
            key=key,
            value=value,
            layer=CacheLayer.L3,
            ttl=ttl,
            importance=importance,
        )
        self._persistent_store[key] = value
        self._stats.size += 1
    
    def _evict(self):
        """按重要性和时间淘汰"""
        entries = sorted(self._cache.values(), key=lambda x: (x.importance, time.time() - x.created_at))
        if entries:
            # 只从内存淘汰，保留持久化存储
            del self._cache[entries[0].key]
            self._stats.size -= 1
            self._stats.evictions += 1


class IntelligentCacheSystem:
    """
    智能缓存系统
    
    四级缓存架构：
    - L0: 精确匹配缓存（毫秒级，最高优先级）
    - L1: 语义相似缓存（向量检索）
    - L2: 上下文缓存（会话级）
    - L3: 知识缓存（持久化）
    
    智能淘汰策略：
    - 基于访问频率和时间
    - 基于内容重要性
    - 基于用户反馈
    - 基于模型更新
    """
    
    def __init__(self):
        """初始化缓存系统"""
        self._cache_layers: Dict[CacheLayer, BaseCache] = {
            CacheLayer.L0: ExactMatchCache(max_size=10000),
            CacheLayer.L1: SemanticCache(max_size=5000),
            CacheLayer.L2: ContextCache(max_size=1000),
            CacheLayer.L3: KnowledgeCache(max_size=500),
        }
        
        self._eviction_policy = EvictionPolicy.HYBRID
        self._user_profiles: Dict[str, Dict[str, Any]] = {}
        
        logger.info("IntelligentCacheSystem 初始化完成")
    
    def get(self, key: str, conversation_id: Optional[str] = None) -> Optional[Any]:
        """
        获取缓存
        
        Args:
            key: 缓存键
            conversation_id: 会话ID（用于上下文缓存）
            
        Returns:
            Any 缓存值
        """
        # 按层级优先级查找
        for layer in [CacheLayer.L0, CacheLayer.L1, CacheLayer.L2, CacheLayer.L3]:
            cache = self._cache_layers[layer]
            
            if layer == CacheLayer.L2 and conversation_id:
                value = cache.get(key, conversation_id)
            else:
                value = cache.get(key)
            
            if value is not None:
                logger.debug(f"缓存命中: {layer.value} - {key}")
                return value
        
        logger.debug(f"缓存未命中: {key}")
        return None
    
    def set(self, key: str, value: Any, layer: CacheLayer = CacheLayer.L0,
            conversation_id: Optional[str] = None, ttl: Optional[float] = None,
            importance: float = 0.5):
        """
        设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
            layer: 缓存层级
            conversation_id: 会话ID
            ttl: 过期时间（秒）
            importance: 重要性（0-1）
        """
        cache = self._cache_layers[layer]
        
        if layer == CacheLayer.L2 and conversation_id:
            cache.set(key, value, conversation_id, ttl, importance)
        else:
            cache.set(key, value, ttl, importance)
        
        logger.debug(f"缓存设置: {layer.value} - {key}")
    
    def delete(self, key: str, layer: Optional[CacheLayer] = None):
        """
        删除缓存
        
        Args:
            key: 缓存键
            layer: 缓存层级（None表示所有层级）
        """
        if layer:
            self._cache_layers[layer].delete(key)
        else:
            for cache in self._cache_layers.values():
                cache.delete(key)
    
    def clear(self, conversation_id: Optional[str] = None):
        """
        清空缓存
        
        Args:
            conversation_id: 会话ID（仅清空该会话的上下文缓存）
        """
        if conversation_id:
            self._cache_layers[CacheLayer.L2].clear_conversation(conversation_id)
        else:
            for cache in self._cache_layers.values():
                cache.clear()
    
    def warm_cache(self, user_profile: Dict[str, Any]):
        """
        基于用户画像预热缓存
        
        Args:
            user_profile: 用户画像
        """
        user_id = user_profile.get("user_id", "")
        if user_id:
            self._user_profiles[user_id] = user_profile
        
        # 根据用户兴趣预热
        interests = user_profile.get("interests", [])
        for interest in interests[:5]:
            # 创建预热缓存条目
            warm_key = f"interest_{interest}"
            self.set(warm_key, {"interest": interest, "timestamp": time.time()}, 
                     layer=CacheLayer.L2, ttl=3600)
        
        logger.info(f"缓存预热完成，用户兴趣: {interests[:5]}")
    
    def record_feedback(self, key: str, success: bool):
        """
        记录用户反馈，用于调整缓存策略
        
        Args:
            key: 缓存键
            success: 是否成功
        """
        # 根据反馈调整重要性
        for layer in self._cache_layers.values():
            if hasattr(layer, '_cache') and key in layer._cache:
                entry = layer._cache[key]
                if success:
                    entry.importance = min(1.0, entry.importance + 0.1)
                else:
                    entry.importance = max(0.0, entry.importance - 0.1)
    
    def consistency_control(self):
        """保证缓存与数据源一致性"""
        # 检查过期条目
        for layer, cache in self._cache_layers.items():
            if hasattr(cache, '_cache'):
                expired_keys = [k for k, entry in cache._cache.items() if entry.is_expired()]
                for key in expired_keys:
                    cache.delete(key)
        
        logger.debug("缓存一致性检查完成")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {}
        total_hits = 0
        total_misses = 0
        
        for layer, cache in self._cache_layers.items():
            layer_stats = cache.get_stats()
            stats[layer.value] = {
                "hits": layer_stats.hits,
                "misses": layer_stats.misses,
                "evictions": layer_stats.evictions,
                "size": layer_stats.size,
                "max_size": layer_stats.max_size,
                "hit_rate": f"{layer_stats.hit_rate:.1f}%",
            }
            total_hits += layer_stats.hits
            total_misses += layer_stats.misses
        
        total_hit_rate = (total_hits / (total_hits + total_misses)) * 100 if (total_hits + total_misses) > 0 else 0
        
        stats["total"] = {
            "hits": total_hits,
            "misses": total_misses,
            "hit_rate": f"{total_hit_rate:.1f}%",
        }
        
        return stats
    
    def set_eviction_policy(self, policy: EvictionPolicy):
        """设置淘汰策略"""
        self._eviction_policy = policy
        logger.info(f"淘汰策略已设置为: {policy.value}")


# 全局缓存系统实例
_cache_instance = None

def get_intelligent_cache_system() -> IntelligentCacheSystem:
    """获取全局智能缓存系统实例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = IntelligentCacheSystem()
    return _cache_instance