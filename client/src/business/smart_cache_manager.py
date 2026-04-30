"""
智能缓存管理器 - 多级缓存 + 预加载
"""

import asyncio
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional, List


class LRUCache:
    """本地LRU缓存"""
    
    def __init__(self, maxsize: int = 1000):
        self._cache = OrderedDict()
        self._maxsize = maxsize
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None
    
    def set(self, key: str, value: Any):
        """设置缓存"""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        
        # 超过容量限制时删除最老的
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)
    
    def delete(self, key: str):
        """删除缓存"""
        self._cache.pop(key, None)
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()


class RedisCache:
    """分布式Redis缓存（模拟实现）"""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key in self._expiry and time.time() > self._expiry[key]:
            del self._cache[key]
            del self._expiry[key]
            return None
        return self._cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: int = 300):
        """设置缓存"""
        self._cache[key] = value
        self._expiry[key] = time.time() + ttl
    
    async def delete(self, key: str):
        """删除缓存"""
        self._cache.pop(key, None)
        self._expiry.pop(key, None)


class PreloadStrategy:
    """预加载策略"""
    
    def predict_keys(self, context: Dict[str, Any]) -> List[str]:
        """根据上下文预测需要预加载的缓存键"""
        keys = []
        
        # 根据用户类型预测
        user_type = context.get("user_type", "general")
        if user_type == "developer":
            keys.extend(["code_templates", "api_docs", "best_practices"])
        elif user_type == "researcher":
            keys.extend(["search_providers", "document_templates"])
        
        # 根据使用模式预测
        usage_pattern = context.get("usage_pattern", {})
        if usage_pattern.get("code_execution", 0) > 0.5:
            keys.append("code_engine_config")
        if usage_pattern.get("web_search", 0) > 0.5:
            keys.append("search_config")
        
        return keys


class SmartCacheManager:
    """智能缓存管理器 - 多级缓存 + 预加载"""
    
    def __init__(self):
        self._local_cache = LRUCache(maxsize=1000)
        self._distributed_cache = RedisCache()
        self._preload_strategy = PreloadStrategy()
    
    async def get_or_compute(self, key: str, compute_func: Callable, ttl: int = 300) -> Any:
        """获取或计算缓存"""
        # 三级缓存查找
        result = self._local_cache.get(key)
        if result is not None:
            return result
        
        result = await self._distributed_cache.get(key)
        if result is not None:
            self._local_cache.set(key, result)
            return result
        
        # 计算并缓存
        result = await compute_func()
        self._local_cache.set(key, result)
        await self._distributed_cache.set(key, result, ttl)
        
        return result
    
    def warm_up(self, context: Dict[str, Any]):
        """基于上下文预加载缓存"""
        keys = self._preload_strategy.predict_keys(context)
        for key in keys:
            asyncio.create_task(self._schedule_preload(key))
    
    async def _schedule_preload(self, key: str):
        """调度预加载任务"""
        # 实际实现中会调用相应的初始化函数
        pass
    
    def invalidate(self, key: str):
        """使缓存失效"""
        self._local_cache.delete(key)
        asyncio.create_task(self._distributed_cache.delete(key))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "local_cache_size": len(self._local_cache._cache),
            "distributed_cache_size": len(self._distributed_cache._cache)
        }


def get_cache_manager() -> SmartCacheManager:
    """获取智能缓存管理器单例"""
    if not hasattr(get_cache_manager, '_instance'):
        get_cache_manager._instance = SmartCacheManager()
    return get_cache_manager._instance