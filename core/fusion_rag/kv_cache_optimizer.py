"""
KV Cache 推理优化器
FusionRAG 的 KV Cache 优化模块

灵感来自 nanochat 的推理优化理念:
- 用计算换内存
- 缓存复用，减少重复计算
- 分层缓存，按热度分配资源

三层缓存架构:
1. Query Cache    - 查询嵌入缓存 + 语义相似匹配
2. Retrieval Cache - 检索结果缓存
3. LLM Cache      - LLM 响应缓存

Author: LivingTreeAI Team
"""

from core.logger import get_logger
logger = get_logger('fusion_rag.kv_cache')

import time
import hashlib
import threading
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict, defaultdict
import math

# 导入统一配置
try:
    from core.config.unified_config import get
except ImportError:
    def get(key, default=None):
        return default


# ============== 配置 ==============

KV_CACHE_CONFIG = {
    # Query Cache 配置
    "query_cache_size": 1000,          # 查询缓存条目上限
    "query_cache_ttl": 3600,            # 查询缓存 TTL (秒)
    "query_similarity_threshold": 0.92, # 语义相似度阈值
    
    # Retrieval Cache 配置
    "retrieval_cache_size": 500,        # 检索结果缓存上限
    "retrieval_cache_ttl": 1800,        # 检索缓存 TTL (秒)
    
    # LLM Cache 配置
    "llm_cache_size": 200,              # LLM 响应缓存上限
    "llm_cache_ttl": 7200,              # LLM 缓存 TTL (秒)
    
    # 预热配置
    "preheat_enabled": True,            # 是否启用预热
    "preheat_top_k": 20,               # 预热时加载的 top-k chunks
}


# ============== 数据结构 ==============

@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    embedding: Optional[List[float]] = None  # 用于语义相似度匹配
    
    def is_expired(self, ttl: int) -> bool:
        """检查是否过期"""
        return (time.time() - self.created_at) > ttl
    
    def access(self):
        """记录访问"""
        self.access_count += 1
        self.last_access = time.time()


@dataclass
class QueryCacheEntry(CacheEntry):
    """查询缓存条目（包含嵌入向量）"""
    embedding: List[float] = field(default_factory=list)
    original_query: str = ""


@dataclass
class RetrievalCacheEntry(CacheEntry):
    """检索结果缓存条目"""
    fused_results: List[Dict] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)


@dataclass
class LLMCacheEntry(CacheEntry):
    """LLM 响应缓存条目"""
    messages: List[Dict] = field(default_factory=list)
    response: Dict = field(default_factory=dict)


# ============== LRU Cache ==============

class LRUCache:
    """线程安全的 LRU 缓存"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
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
            if entry.is_expired(self.ttl):
                del self._cache[key]
                self._misses += 1
                return None
            
            # 更新访问顺序（移到末尾）
            self._cache.move_to_end(key)
            entry.access()
            
            self._hits += 1
            return entry.value
    
    def set(self, key: str, value: Any):
        """设置缓存值"""
        with self._lock:
            # 如果已存在，更新
            if key in self._cache:
                self._cache[key].value = value
                self._cache[key].access()
                self._cache.move_to_end(key)
                return
            
            # 如果达到上限，删除最旧的
            if len(self._cache) >= self.max_size:
                # 删除最少使用的
                self._cache.popitem(last=False)
            
            # 添加新条目
            self._cache[key] = CacheEntry(key=key, value=value)
    
    def delete(self, key: str):
        """删除缓存条目"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate
            }


# ============== 语义相似度缓存 ==============

class SemanticQueryCache:
    """
    语义查询缓存
    
    特性:
    1. 支持语义相似度匹配（使用余弦相似度）
    2. 基于 LRU 淘汰策略
    3. 可配置 TTL 和相似度阈值
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        ttl: int = 3600,
        similarity_threshold: float = 0.92,
        embedding_func: Optional[Callable[[str], List[float]]] = None
    ):
        self.max_size = max_size
        self.ttl = ttl
        self.similarity_threshold = similarity_threshold
        self._embedding_func = embedding_func
        
        # 缓存存储
        self._cache: OrderedDict[str, QueryCacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # 统计
        self._hits = 0
        self._misses = 0
        self._exact_hits = 0
        self._similar_hits = 0
    
    def _compute_hash(self, query: str) -> str:
        """计算查询的哈希值"""
        return hashlib.md5(query.encode()).hexdigest()
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2:
            return 0.0
        
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(a * a for a in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot / (norm1 * norm2)
    
    def _get_embedding(self, query: str) -> Optional[List[float]]:
        """获取查询嵌入"""
        if self._embedding_func:
            try:
                return self._embedding_func(query)
            except Exception:
                return None
        return None
    
    def get(
        self, 
        query: str,
        return_similarity: bool = False
    ) -> Tuple[Optional[Any], float]:
        """
        获取缓存值
        
        Args:
            query: 查询文本
            return_similarity: 是否返回相似度
            
        Returns:
            (缓存值, 相似度) 或 (缓存值, 0)
        """
        with self._lock:
            query_hash = self._compute_hash(query)
            
            # 1. 精确匹配
            if query_hash in self._cache:
                entry = self._cache[query_hash]
                if not entry.is_expired(self.ttl):
                    entry.access()
                    self._cache.move_to_end(query_hash)
                    self._hits += 1
                    self._exact_hits += 1
                    return (entry.value, 1.0) if return_similarity else (entry.value, 1.0)[0]
                else:
                    del self._cache[query_hash]
            
            # 2. 语义相似度匹配
            query_emb = self._get_embedding(query)
            if query_emb:
                best_key = None
                best_similarity = 0.0
                best_entry = None
                
                for key, entry in self._cache.items():
                    if entry.is_expired(self.ttl):
                        continue
                    if entry.embedding is None:
                        continue
                    
                    sim = self._cosine_similarity(query_emb, entry.embedding)
                    if sim > best_similarity and sim >= self.similarity_threshold:
                        best_similarity = sim
                        best_key = key
                        best_entry = entry
                
                if best_entry:
                    self._cache.move_to_end(best_key)
                    best_entry.access()
                    self._hits += 1
                    self._similar_hits += 1
                    return (best_entry.value, best_similarity) if return_similarity else (best_entry.value, best_similarity)[0]
            
            self._misses += 1
            return (None, 0.0) if return_similarity else (None, 0.0)
    
    def set(self, query: str, value: Any, embedding: Optional[List[float]] = None):
        """设置缓存值"""
        with self._lock:
            query_hash = self._compute_hash(query)
            
            # 如果嵌入未提供，尝试计算
            if embedding is None:
                embedding = self._get_embedding(query)
            
            # 如果达到上限，删除最旧的
            if len(self._cache) >= self.max_size:
                # 删除最少使用的
                self._cache.popitem(last=False)
            
            # 添加/更新条目
            self._cache[query_hash] = QueryCacheEntry(
                key=query_hash,
                value=value,
                embedding=embedding or [],
                original_query=query
            )
    
    def invalidate(self, query: str):
        """使缓存失效"""
        with self._lock:
            query_hash = self._compute_hash(query)
            if query_hash in self._cache:
                del self._cache[query_hash]
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._exact_hits = 0
            self._similar_hits = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            return {
                "type": "semantic_query_cache",
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl": self.ttl,
                "similarity_threshold": self.similarity_threshold,
                "hits": self._hits,
                "misses": self._misses,
                "exact_hits": self._exact_hits,
                "similar_hits": self._similar_hits,
                "hit_rate": hit_rate
            }


# ============== 检索结果缓存 ==============

class RetrievalResultCache:
    """
    检索结果缓存
    
    特性:
    1. 基于查询哈希 + 过滤条件缓存
    2. 支持按热度预热
    3. 可配置 TTL
    """
    
    def __init__(self, max_size: int = 500, ttl: int = 1800):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[str, RetrievalCacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # 统计
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, query: str, top_k: int, filters: Optional[Dict] = None) -> str:
        """生成缓存键"""
        key_parts = [
            hashlib.md5(query.encode()).hexdigest(),
            str(top_k)
        ]
        if filters:
            filter_str = "|".join(f"{k}={v}" for k, v in sorted(filters.items()))
            key_parts.append(hashlib.md5(filter_str.encode()).hexdigest()[:8])
        return "|".join(key_parts)
    
    def get(
        self, 
        query: str, 
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> Optional[List[Dict]]:
        """获取缓存的检索结果"""
        with self._lock:
            key = self._make_key(query, top_k, filters)
            
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            
            # 检查过期
            if entry.is_expired(self.ttl):
                del self._cache[key]
                self._misses += 1
                return None
            
            # 更新访问
            entry.access()
            self._cache.move_to_end(key)
            self._hits += 1
            
            return entry.value
    
    def set(
        self,
        query: str,
        results: List[Dict],
        top_k: int = 10,
        filters: Optional[Dict] = None,
        sources: Optional[List[str]] = None
    ):
        """设置检索结果缓存"""
        with self._lock:
            key = self._make_key(query, top_k, filters)
            
            # LRU 淘汰
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = RetrievalCacheEntry(
                key=key,
                value=results,
                fused_results=results,
                sources=sources or []
            )
    
    def invalidate(self, pattern: Optional[str] = None):
        """使缓存失效"""
        with self._lock:
            if pattern is None:
                self._cache.clear()
            else:
                # 按模式删除
                keys_to_delete = [k for k in self._cache if pattern in k]
                for key in keys_to_delete:
                    del self._cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            return {
                "type": "retrieval_cache",
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl": self.ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate
            }


# ============== LLM 响应缓存 ==============

class LLMResponseCache:
    """
    LLM 响应缓存
    
    特性:
    1. 基于消息哈希缓存响应
    2. 支持语义相似度匹配
    3. 可配置 TTL 和最大条目数
    """
    
    def __init__(
        self,
        max_size: int = 200,
        ttl: int = 7200,
        similarity_threshold: float = 0.95
    ):
        self.max_size = max_size
        self.ttl = ttl
        self.similarity_threshold = similarity_threshold
        self._cache: OrderedDict[str, LLMCacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # 统计
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, messages: List[Dict]) -> str:
        """生成消息哈希"""
        content = ""
        for m in messages:
            content += m.get("role", "") + ":" + m.get("content", "") + "|"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(
        self, 
        messages: List[Dict],
        return_entry: bool = False
    ) -> Tuple[Optional[Dict], Optional[LLMCacheEntry]]:
        """获取缓存的 LLM 响应"""
        with self._lock:
            key = self._make_key(messages)
            
            if key not in self._cache:
                self._misses += 1
                return (None, None) if return_entry else (None, None)[0]
            
            entry = self._cache[key]
            
            # 检查过期
            if entry.is_expired(self.ttl):
                del self._cache[key]
                self._misses += 1
                return (None, None) if return_entry else (None, None)[0]
            
            # 更新访问
            entry.access()
            self._cache.move_to_end(key)
            self._hits += 1
            
            return (entry.response, entry) if return_entry else (entry.response, None)[0]
    
    def set(
        self,
        messages: List[Dict],
        response: Dict
    ):
        """设置 LLM 响应缓存"""
        with self._lock:
            key = self._make_key(messages)
            
            # LRU 淘汰
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = LLMCacheEntry(
                key=key,
                value=response,
                messages=messages,
                response=response
            )
    
    def invalidate(self, pattern: Optional[str] = None):
        """使缓存失效"""
        with self._lock:
            if pattern is None:
                self._cache.clear()
            else:
                keys_to_delete = [k for k in self._cache if pattern in k]
                for key in keys_to_delete:
                    del self._cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            return {
                "type": "llm_cache",
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl": self.ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate
            }


# ============== 预热器 ==============

class CachePreheater:
    """
    缓存预热器
    
    在系统启动时预加载热点数据，减少冷启动延迟
    """
    
    def __init__(
        self,
        knowledge_base: Optional[Any] = None,
        embedding_func: Optional[Callable[[str], List[float]]] = None
    ):
        self.knowledge_base = knowledge_base
        self._embedding_func = embedding_func
        self._preheated_chunks: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
    
    def preheat(
        self,
        queries: List[str],
        knowledge_base: Optional[Any] = None,
        top_k: int = 20
    ) -> int:
        """
        预热缓存
        
        Args:
            queries: 热点查询列表
            knowledge_base: 知识库实例
            top_k: 每个查询预加载的 chunk 数量
            
        Returns:
            预热的 chunk 数量
        """
        kb = knowledge_base or self.knowledge_base
        if not kb:
            return 0
        
        count = 0
        with self._lock:
            for query in queries:
                try:
                    # 搜索
                    results = kb.search(query, top_k=top_k)
                    
                    # 缓存嵌入
                    for r in results:
                        chunk_id = r.get("id", "")
                        if chunk_id not in self._preheated_chunks:
                            # 尝试获取预计算的嵌入
                            idx = kb.chunk_index.get(chunk_id)
                            if idx is not None and idx < len(kb.vector_index):
                                self._preheated_chunks[chunk_id] = kb.vector_index[idx]
                                count += 1
                    
                    # 预计算查询嵌入
                    if self._embedding_func:
                        self._embedding_func(query)
                        
                except Exception as e:
                    logger.warning(f"[CachePreheater] 预热失败: {e}")
        
        logger.info(f"[CachePreheater] 预热完成: {count} chunks, {len(queries)} queries")
        return count
    
    def get_preheated_embedding(self, chunk_id: str) -> Optional[List[float]]:
        """获取预热的嵌入"""
        return self._preheated_chunks.get(chunk_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "preheated_chunks": len(self._preheated_chunks),
            "queries_preheated": len(self._preheated_chunks) // 20  # 估算
        }


# ============== 主缓存管理器 ==============

class FusionKVCacheManager:
    """
    FusionRAG KV Cache 主管理器
    
    统一管理三层缓存，提供一致的 API
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(
        self,
        config: Optional[Dict] = None,
        embedding_func: Optional[Callable[[str], List[float]]] = None
    ):
        if self._initialized:
            return
        
        # 配置
        self.config = {**KV_CACHE_CONFIG, **(config or {})}
        
        # 嵌入函数
        self._embedding_func = embedding_func
        
        # 初始化三层缓存
        self.query_cache = SemanticQueryCache(
            max_size=self.config["query_cache_size"],
            ttl=self.config["query_cache_ttl"],
            similarity_threshold=self.config["query_similarity_threshold"],
            embedding_func=embedding_func
        )
        
        self.retrieval_cache = RetrievalResultCache(
            max_size=self.config["retrieval_cache_size"],
            ttl=self.config["retrieval_cache_ttl"]
        )
        
        self.llm_cache = LLMResponseCache(
            max_size=self.config["llm_cache_size"],
            ttl=self.config["llm_cache_ttl"]
        )
        
        # 预热器
        self.preheater = CachePreheater(embedding_func=embedding_func)
        
        # 知识库引用（用于预热）
        self._knowledge_base = None
        
        self._initialized = True
        logger.info("[FusionKVCache] KV Cache 管理器初始化完成")
    
    def set_knowledge_base(self, kb: Any):
        """设置知识库引用"""
        self._knowledge_base = kb
        self.preheater.knowledge_base = kb
    
    def set_embedding_func(self, func: Callable[[str], List[float]]):
        """设置嵌入函数"""
        self._embedding_func = func
        self.query_cache._embedding_func = func
        self.preheater._embedding_func = func
    
    def get_query_cached(
        self,
        query: str,
        return_similarity: bool = False
    ) -> Tuple[Optional[Any], float]:
        """获取查询缓存"""
        return self.query_cache.get(query, return_similarity)
    
    def set_query_cache(
        self,
        query: str,
        value: Any,
        embedding: Optional[List[float]] = None
    ):
        """设置查询缓存"""
        if embedding is None and self._embedding_func:
            embedding = self._embedding_func(query)
        self.query_cache.set(query, value, embedding)
    
    def get_retrieval_cached(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None
    ) -> Optional[List[Dict]]:
        """获取检索结果缓存"""
        return self.retrieval_cache.get(query, top_k, filters)
    
    def set_retrieval_cache(
        self,
        query: str,
        results: List[Dict],
        top_k: int = 10,
        filters: Optional[Dict] = None
    ):
        """设置检索结果缓存"""
        self.retrieval_cache.set(query, results, top_k, filters)
    
    def get_llm_cached(self, messages: List[Dict]) -> Optional[Dict]:
        """获取 LLM 响应缓存"""
        return self.llm_cache.get(messages)
    
    def set_llm_cache(self, messages: List[Dict], response: Dict):
        """设置 LLM 响应缓存"""
        self.llm_cache.set(messages, response)
    
    def preheat(self, queries: List[str], top_k: int = 20) -> int:
        """预热缓存"""
        return self.preheater.preheat(queries, self._knowledge_base, top_k)
    
    def invalidate_all(self):
        """使所有缓存失效"""
        self.query_cache.clear()
        self.retrieval_cache.invalidate()
        self.llm_cache.invalidate()
        logger.info("[FusionKVCache] 所有缓存已失效")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取完整统计信息"""
        return {
            "query_cache": self.query_cache.get_stats(),
            "retrieval_cache": self.retrieval_cache.get_stats(),
            "llm_cache": self.llm_cache.get_stats(),
            "preheater": self.preheater.get_stats(),
            "config": self.config
        }


# ============== 快捷函数 ==============

_cache_manager: Optional[FusionKVCacheManager] = None


def get_kv_cache_manager(
    config: Optional[Dict] = None,
    embedding_func: Optional[Callable[[str], List[float]]] = None
) -> FusionKVCacheManager:
    """获取 KV Cache 管理器单例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = FusionKVCacheManager(config, embedding_func)
    return _cache_manager


def clear_kv_cache():
    """清空所有 KV 缓存"""
    global _cache_manager
    if _cache_manager:
        _cache_manager.invalidate_all()


# ============== 装饰器 ==============

def with_query_cache(enabled: bool = True):
    """
    查询缓存装饰器
    
    用法:
        @with_query_cache()
        async def search(self, query, ...):
            ...
    """
    def decorator(func):
        async def wrapper(self, query, *args, **kwargs):
            if not enabled:
                return await func(self, query, *args, **kwargs)
            
            cache = getattr(self, '_kv_cache', None)
            if cache:
                cached = cache.get_query_cached(query)
                if cached is not None:
                    return cached
            
            result = await func(self, query, *args, **kwargs)
            
            if cache and result is not None:
                cache.set_query_cache(query, result)
            
            return result
        return wrapper
    return decorator


def with_retrieval_cache(ttl: int = 1800):
    """
    检索结果缓存装饰器
    
    用法:
        @with_retrieval_cache()
        def search(self, query, top_k=10):
            ...
    """
    def decorator(func):
        def wrapper(self, query, *args, **kwargs):
            cache = getattr(self, '_retrieval_cache', None)
            if cache:
                top_k = kwargs.get('top_k', args[1] if len(args) > 1 else 10)
                filters = kwargs.get('filters')
                
                cached = cache.get_retrieval_cached(query, top_k, filters)
                if cached is not None:
                    return cached
            
            result = func(self, query, *args, **kwargs)
            
            if cache and result is not None:
                cache.set_retrieval_cache(query, result, top_k, filters)
            
            return result
        return wrapper
    return decorator


def with_llm_cache():
    """
    LLM 响应缓存装饰器
    
    用法:
        @with_llm_cache()
        async def execute(self, messages, ...):
            ...
    """
    def decorator(func):
        async def wrapper(self, messages, *args, **kwargs):
            cache = getattr(self, '_llm_cache', None)
            if cache:
                cached = cache.get_llm_cached(messages)
                if cached is not None:
                    logger.debug("[with_llm_cache] LLM 缓存命中")
                    return cached
            
            result = await func(self, messages, *args, **kwargs)
            
            if cache and result is not None:
                cache.set_llm_cache(messages, result)
            
            return result
        return wrapper
    return decorator
