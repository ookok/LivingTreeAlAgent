"""
缓存管理器

负责管理本地缓存，实现缓存策略和数据淘汰
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional, List, Tuple

from .models import CDNData, DataMetadata, CacheStatus

logger = logging.getLogger(__name__)


class CacheStrategy:
    """
    缓存策略枚举
    """
    LRU = "lru"  # 最近最少使用
    LFU = "lfu"  # 最不经常使用
    FIFO = "fifo"  # 先进先出


class CacheItem:
    """
    缓存项
    """
    
    def __init__(self, data: CDNData):
        self.data = data
        self.access_time = time.time()
        self.access_count = 1
        self.status = CacheStatus.CACHED


class CacheManager:
    """
    缓存管理器
    负责管理本地缓存，实现缓存策略和数据淘汰
    """
    
    def __init__(self, storage, max_cache_size: int):
        self.storage = storage
        self.max_cache_size = max_cache_size
        self.cache: Dict[str, CacheItem] = {}
        self.current_cache_size = 0
        self.strategy = CacheStrategy.LRU
    
    async def init(self):
        """初始化缓存管理器"""
        logger.info("Initializing cache manager...")
        # 可以在这里加载持久化的缓存数据
    
    async def cache_data(self, data: CDNData) -> bool:
        """缓存数据"""
        data_id = data.data_id
        data_size = len(str(data.data))
        
        # 检查缓存是否已满
        while self.current_cache_size + data_size > self.max_cache_size:
            # 淘汰数据
            evicted = await self._evict_data()
            if not evicted:
                logger.warning("Cache is full and cannot evict any data")
                return False
        
        # 检查数据是否已在缓存中
        if data_id in self.cache:
            # 更新缓存项
            self.cache[data_id].data = data
            self.cache[data_id].access_time = time.time()
            self.cache[data_id].access_count += 1
            self.cache[data_id].status = CacheStatus.CACHED
        else:
            # 添加新缓存项
            self.cache[data_id] = CacheItem(data)
            self.current_cache_size += data_size
        
        logger.debug(f"Cached data {data_id}, current cache size: {self.current_cache_size}/{self.max_cache_size}")
        return True
    
    async def get_data(self, data_id: str) -> Optional[CDNData]:
        """获取缓存数据"""
        if data_id in self.cache:
            # 更新访问时间和次数
            item = self.cache[data_id]
            item.access_time = time.time()
            item.access_count += 1
            logger.debug(f"Cache hit for data {data_id}")
            return item.data
        
        logger.debug(f"Cache miss for data {data_id}")
        return None
    
    async def remove_data(self, data_id: str) -> bool:
        """从缓存中移除数据"""
        if data_id in self.cache:
            item = self.cache[data_id]
            self.current_cache_size -= len(str(item.data.data))
            del self.cache[data_id]
            logger.debug(f"Removed data {data_id} from cache")
            return True
        
        return False
    
    async def _evict_data(self) -> bool:
        """淘汰数据"""
        if not self.cache:
            return False
        
        # 根据策略选择要淘汰的数据
        if self.strategy == CacheStrategy.LRU:
            # 选择最近最少使用的数据
            evict_key = min(self.cache.items(), key=lambda x: x[1].access_time)[0]
        elif self.strategy == CacheStrategy.LFU:
            # 选择最不经常使用的数据
            evict_key = min(self.cache.items(), key=lambda x: x[1].access_count)[0]
        elif self.strategy == CacheStrategy.FIFO:
            # 选择最早加入的数据
            evict_key = min(self.cache.items(), key=lambda x: x[1].data.created_at)[0]
        else:
            # 默认使用 LRU
            evict_key = min(self.cache.items(), key=lambda x: x[1].access_time)[0]
        
        # 淘汰数据
        await self.remove_data(evict_key)
        logger.debug(f"Evicted data {evict_key} using {self.strategy} strategy")
        return True
    
    async def cleanup_expired(self):
        """清理过期数据"""
        # 这里可以添加过期数据清理逻辑
        # 例如，根据数据的 TTL 或其他过期策略
        pass
    
    async def get_hot_data(self, threshold: int) -> Dict[str, DataMetadata]:
        """获取热门数据"""
        hot_data = {}
        for data_id, item in self.cache.items():
            if item.access_count >= threshold:
                # 创建元数据
                metadata = DataMetadata(
                    data_id=data_id,
                    data_type=item.data.data_type,
                    size=len(str(item.data.data)),
                    created_at=item.data.created_at,
                    access_count=item.access_count,
                    last_access=item.access_time,
                    replicas={},  # 这里需要从外部获取副本信息
                    version=item.data.version
                )
                hot_data[data_id] = metadata
        
        return hot_data
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "cache_size": self.current_cache_size,
            "max_cache_size": self.max_cache_size,
            "item_count": len(self.cache),
            "strategy": self.strategy,
            "hit_rate": self._calculate_hit_rate()
        }
    
    def _calculate_hit_rate(self) -> float:
        """计算命中率"""
        # 这里需要实现命中率计算逻辑
        # 可以通过记录缓存命中和未命中的次数来计算
        return 0.0
