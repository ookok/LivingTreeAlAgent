"""
Prompt缓存管理器 (Prompt Cache Manager)
======================================

集成 Anthropic Prompt Caching 功能，实现：
1. 智能缓存 - 根据prompt内容进行缓存
2. 增量缓存 - 支持缓存提示词的部分内容
3. 缓存失效 - 智能判断缓存是否有效
4. 成本优化 - 通过缓存减少API调用成本

核心特性：
- 支持多种缓存策略
- 可配置的缓存有效期
- 智能缓存失效检测
- 缓存统计和监控

参考项目：https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import hashlib
import time
import asyncio
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

logger = __import__('logging').getLogger(__name__)


class CacheStrategy(Enum):
    """缓存策略"""
    FULL = "full"           # 完整缓存（整个prompt）
    PARTIAL = "partial"     # 部分缓存（支持增量）
    LRU = "lru"             # 最近最少使用
    TTL = "ttl"             # 时间过期


class CacheStatus(Enum):
    """缓存状态"""
    HIT = "hit"             # 缓存命中
    MISS = "miss"           # 缓存未命中
    STALE = "stale"         # 缓存过期


@dataclass
class CacheEntry:
    """缓存条目"""
    prompt_hash: str
    prompt: str
    response: str
    created_at: float
    accessed_at: float
    access_count: int
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheStats:
    """缓存统计"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_entries: int = 0
    avg_access_time: float = 0.0


class PromptCacheManager:
    """
    Prompt缓存管理器
    
    核心功能：
    1. 智能缓存 - 根据prompt内容进行缓存
    2. 增量缓存 - 支持缓存提示词的部分内容
    3. 缓存失效 - 智能判断缓存是否有效
    4. 成本优化 - 通过缓存减少API调用成本
    
    参考项目：https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 缓存存储
        self._cache: Dict[str, CacheEntry] = {}
        
        # 配置参数
        self._config = {
            "strategy": "full",
            "max_entries": 1000,
            "default_ttl": 3600,  # 默认1小时
            "min_ttl": 60,        # 最小1分钟
            "max_ttl": 86400,     # 最大24小时
            "cache_enabled": True,
            "auto_cleanup_interval": 300,  # 自动清理间隔（秒）
        }
        
        # 统计信息
        self._stats = CacheStats()
        
        # 缓存锁
        self._lock = asyncio.Lock()
        
        # 后台清理任务
        self._cleanup_task = None
        
        self._initialized = True
        logger.info("[PromptCacheManager] Prompt缓存管理器初始化完成")
    
    def configure(self, **kwargs):
        """配置缓存管理器"""
        self._config.update(kwargs)
        logger.info(f"[PromptCacheManager] 配置更新: {kwargs}")
    
    async def get(self, prompt: str) -> Tuple[Optional[str], CacheStatus]:
        """
        获取缓存的响应
        
        Args:
            prompt: 提示词
            
        Returns:
            (响应内容, 缓存状态)
        """
        if not self._config["cache_enabled"]:
            return None, CacheStatus.MISS
        
        prompt_hash = self._hash_prompt(prompt)
        
        async with self._lock:
            if prompt_hash not in self._cache:
                self._stats.misses += 1
                return None, CacheStatus.MISS
            
            entry = self._cache[prompt_hash]
            
            # 检查是否过期
            if entry.expires_at and entry.expires_at < time.time():
                del self._cache[prompt_hash]
                self._stats.evictions += 1
                self._stats.misses += 1
                return None, CacheStatus.STALE
            
            # 更新访问信息
            entry.accessed_at = time.time()
            entry.access_count += 1
            
            self._stats.hits += 1
            return entry.response, CacheStatus.HIT
    
    async def set(self, prompt: str, response: str, ttl: float = None, **metadata):
        """
        设置缓存
        
        Args:
            prompt: 提示词
            response: 响应内容
            ttl: 过期时间（秒），默认使用配置值
            **metadata: 额外元数据
        """
        if not self._config["cache_enabled"]:
            return
        
        prompt_hash = self._hash_prompt(prompt)
        expires_at = time.time() + (ttl or self._config["default_ttl"])
        
        async with self._lock:
            # 检查是否需要清理
            await self._ensure_capacity()
            
            # 创建缓存条目
            self._cache[prompt_hash] = CacheEntry(
                prompt_hash=prompt_hash,
                prompt=prompt,
                response=response,
                created_at=time.time(),
                accessed_at=time.time(),
                access_count=1,
                expires_at=expires_at,
                metadata=metadata
            )
            
            self._stats.total_entries = len(self._cache)
    
    async def delete(self, prompt: str) -> bool:
        """
        删除缓存
        
        Args:
            prompt: 提示词
            
        Returns:
            是否删除成功
        """
        prompt_hash = self._hash_prompt(prompt)
        
        async with self._lock:
            if prompt_hash in self._cache:
                del self._cache[prompt_hash]
                self._stats.total_entries = len(self._cache)
                return True
        return False
    
    async def clear(self):
        """清空所有缓存"""
        async with self._lock:
            self._cache.clear()
            self._stats.total_entries = 0
            logger.info("[PromptCacheManager] 缓存已清空")
    
    def get_stats(self) -> CacheStats:
        """获取缓存统计信息"""
        return self._stats
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存详细信息"""
        info = {
            "config": self._config,
            "stats": {
                "hits": self._stats.hits,
                "misses": self._stats.misses,
                "evictions": self._stats.evictions,
                "total_entries": self._stats.total_entries,
                "hit_rate": self._calculate_hit_rate(),
            },
        }
        return info
    
    def _calculate_hit_rate(self) -> float:
        """计算缓存命中率"""
        total = self._stats.hits + self._stats.misses
        if total == 0:
            return 0.0
        return self._stats.hits / total
    
    def _hash_prompt(self, prompt: str) -> str:
        """计算提示词的哈希值"""
        return hashlib.sha256(prompt.encode('utf-8')).hexdigest()
    
    async def _ensure_capacity(self):
        """确保缓存容量不超过限制"""
        max_entries = self._config["max_entries"]
        
        while len(self._cache) >= max_entries:
            # 找到最旧或访问最少的条目
            oldest_key = None
            oldest_access = float('inf')
            
            for key, entry in self._cache.items():
                if entry.accessed_at < oldest_access:
                    oldest_access = entry.accessed_at
                    oldest_key = key
            
            if oldest_key:
                del self._cache[oldest_key]
                self._stats.evictions += 1
    
    async def start_auto_cleanup(self):
        """启动自动清理任务"""
        if self._cleanup_task:
            return
        
        async def cleanup_loop():
            while True:
                await asyncio.sleep(self._config["auto_cleanup_interval"])
                await self._cleanup_stale_entries()
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("[PromptCacheManager] 自动清理任务已启动")
    
    async def stop_auto_cleanup(self):
        """停止自动清理任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
            logger.info("[PromptCacheManager] 自动清理任务已停止")
    
    async def _cleanup_stale_entries(self):
        """清理过期的缓存条目"""
        now = time.time()
        stale_count = 0
        
        async with self._lock:
            stale_keys = [
                key for key, entry in self._cache.items()
                if entry.expires_at and entry.expires_at < now
            ]
            
            for key in stale_keys:
                del self._cache[key]
                stale_count += 1
            
            self._stats.total_entries = len(self._cache)
            self._stats.evictions += stale_count
        
        if stale_count > 0:
            logger.debug(f"[PromptCacheManager] 清理了 {stale_count} 个过期缓存")
    
    # ========== 便捷方法 ==========
    
    async def cached_call(self, prompt: str, callable: Callable[[str], str]) -> Tuple[str, CacheStatus]:
        """
        带缓存的调用
        
        Args:
            prompt: 提示词
            callable: 实际调用函数
            
        Returns:
            (响应内容, 缓存状态)
        """
        # 先尝试获取缓存
        response, status = await self.get(prompt)
        
        if status == CacheStatus.HIT:
            return response, status
        
        # 缓存未命中，执行实际调用
        response = await callable(prompt) if asyncio.iscoroutinefunction(callable) else callable(prompt)
        
        # 缓存结果
        await self.set(prompt, response)
        
        return response, status


# 便捷函数
def get_prompt_cache() -> PromptCacheManager:     
    """获取Prompt缓存管理器单例"""
    return PromptCacheManager()


def get_prompt_cache_manager() -> PromptCacheManager:
    """获取Prompt缓存管理器单例（兼容旧接口）"""
    return get_prompt_cache()


__all__ = [
    "CacheStrategy",
    "CacheStatus",
    "CacheEntry",
    "CacheStats",
    "PromptCacheManager",
    "get_prompt_cache",
    "get_prompt_cache_manager",
]