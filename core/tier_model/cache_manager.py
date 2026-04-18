"""
缓存管理器
统一管理三级缓存系统
"""

from typing import Optional, Any, Dict, List
from threading import Lock
import time

from .memory_cache import MemoryCache
from .local_cache import LocalCache
from .semantic_cache import SemanticCache, SemanticCacheResult
from .cache_config import CacheConfigManager, MemoryCacheConfig, LocalCacheConfig, SemanticCacheConfig


class CacheManager:
    """
    缓存管理器
    统一管理 L1 内存缓存、L2 本地缓存、L3 语义缓存
    实现写时更新和读时验证策略
    """
    
    def __init__(self, config_manager: CacheConfigManager = None):
        self.config_manager = config_manager or CacheConfigManager()
        
        # 初始化三级缓存
        mem_cfg = self.config_manager.get_memory_config()
        local_cfg = self.config_manager.get_local_config()
        sem_cfg = self.config_manager.get_semantic_config()
        
        self.l1_cache = MemoryCache(
            max_items=mem_cfg.max_items,
            ttl_seconds=mem_cfg.ttl_seconds,
            heat_threshold=mem_cfg.heat_threshold
        )
        
        self.l2_cache = LocalCache(
            db_path=local_cfg.db_path,
            max_items=local_cfg.max_items,
            ttl_seconds=local_cfg.ttl_seconds,
            index_type=local_cfg.index_type
        )
        
        self.l3_cache = SemanticCache(
            vector_dim=sem_cfg.vector_dim,
            similarity_threshold=sem_cfg.similarity_threshold,
            index_type=sem_cfg.index_type,
            persist_path=sem_cfg.persist_path,
            batch_size=sem_cfg.batch_size
        )
        
        self._lock = Lock()
        self._write_queue: List[tuple] = []
    
    def get(self, query: str, context: str = None) -> Optional[Dict[str, Any]]:
        """
        获取缓存（逐级查询）
        L1 → L2 → L3
        """
        # L1: 内存缓存（最快）
        result = self.l1_cache.get(query, context)
        if result is not None:
            return {
                "tier": "L1",
                "response": result,
                "latency_ms": 0
            }
        
        # L2: 本地缓存
        result = self.l2_cache.get(query, context)
        if result is not None:
            # 写回 L1
            self.l1_cache.set(query, result["response"], context)
            return {
                "tier": "L2",
                "response": result["response"],
                "model_id": result.get("model_id"),
                "latency_ms": 1
            }
        
        # L3: 语义缓存
        result = self.l3_cache.get(query)
        if result is not None:
            return {
                "tier": "L3",
                "response": result.response,
                "model_id": result.model_id,
                "similarity": result.similarity,
                "latency_ms": 5
            }
        
        return None
    
    def set(self, query: str, response: Any, context: str = None, model_id: str = None):
        """
        设置缓存（写入所有层级）
        异步更新语义索引
        """
        with self._lock:
            # L1: 立即写入
            self.l1_cache.set(query, response, context)
            
            # L2: 立即写入
            self.l2_cache.set(query, response, context, model_id)
            
            # L3: 异步更新（加入队列）
            self._write_queue.append((query, response, model_id))
            if len(self._write_queue) >= 10:  # 批量更新
                self._flush_semantic_cache()
    
    def _flush_semantic_cache(self):
        """刷新语义缓存队列"""
        for query, response, model_id in self._write_queue:
            self.l3_cache.set(query, response, model_id)
        self._write_queue.clear()
    
    def invalidate(self, query: str, context: str = None):
        """使缓存失效"""
        self.l1_cache.invalidate(query, context)
        # L2/L3 需要通过哈希查找后失效，这里简化处理
    
    def clear_all(self):
        """清空所有缓存"""
        self.l1_cache.clear()
        self.l2_cache.clear()
        self.l3_cache.clear()
    
    def get_combined_stats(self) -> Dict[str, Any]:
        """获取综合缓存统计"""
        l1_stats = self.l1_cache.get_stats()
        l2_stats = self.l2_cache.get_stats()
        l3_stats = self.l3_cache.get_stats()
        
        # 计算综合命中率
        total_hits = l1_stats["hits"] + l2_stats["hits"] + l3_stats["hits"]
        total_requests = total_hits + l1_stats["misses"] + l2_stats["misses"] + l3_stats["misses"]
        combined_hit_rate = total_hits / total_requests if total_requests > 0 else 0
        
        return {
            "combined_hit_rate": combined_hit_rate,
            "L1_memory": l1_stats,
            "L2_local": l2_stats,
            "L3_semantic": l3_stats,
            "pending_semantic_updates": len(self._write_queue)
        }
    
    def update_config(self, layer: str, params: Dict[str, Any]):
        """更新配置"""
        self.config_manager.update_config(layer, params)
        
        if layer == "memory_cache":
            if "ttl_seconds" in params:
                self.l1_cache.update_ttl(params["ttl_seconds"])
        elif layer == "semantic_cache":
            if "similarity_threshold" in params:
                self.l3_cache.update_similarity_threshold(params["similarity_threshold"])
    
    def warm_up(self, queries: List[tuple]):
        """预热缓存"""
        # 格式: [(query, response, context), ...]
        for query, response, context in queries[:100]:
            self.set(query, response, context)
        
        self._flush_semantic_cache()


class MultiQueryCache:
    """
    多查询缓存处理
    支持批量查询和并行缓存查找
    """
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
    
    def batch_get(self, queries: List[str]) -> List[Optional[Dict[str, Any]]]:
        """批量获取缓存"""
        results = []
        for query in queries:
            results.append(self.cache_manager.get(query))
        return results
    
    def parallel_get(self, queries: List[str]) -> List[Optional[Dict[str, Any]]]:
        """并行获取缓存（使用多线程）"""
        from concurrent.futures import ThreadPoolExecutor
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(self.cache_manager.get, queries))
        return results
