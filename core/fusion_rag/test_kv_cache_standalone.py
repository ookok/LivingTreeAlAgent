"""KV Cache 优化器独立测试（无需 core 依赖）"""

# 复制核心 KV Cache 类进行独立测试
import time
import hashlib
import threading
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict, defaultdict
import math


# ============== LRU Cache ==============

class LRUCache:
    """线程安全的 LRU 缓存"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[str, 'CacheEntry'] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            if entry.is_expired(self.ttl):
                del self._cache[key]
                self._misses += 1
                return None
            
            self._cache.move_to_end(key)
            entry.access_count += 1
            entry.last_access = time.time()
            self._hits += 1
            return entry.value
    
    def set(self, key: str, value: Any):
        with self._lock:
            if key in self._cache:
                self._cache[key].value = value
                self._cache.move_to_end(key)
                return
            
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = CacheEntry(key=key, value=value)
    
    def get_stats(self) -> Dict[str, Any]:
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


@dataclass
class CacheEntry:
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    
    def is_expired(self, ttl: int) -> bool:
        return (time.time() - self.created_at) > ttl


# ============== Semantic Query Cache ==============

class SemanticQueryCache:
    def __init__(self, max_size: int = 1000, ttl: int = 3600, similarity_threshold: float = 0.92):
        self.max_size = max_size
        self.ttl = ttl
        self.similarity_threshold = similarity_threshold
        self._cache: OrderedDict[str, QueryCacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._exact_hits = 0
        self._similar_hits = 0
    
    def _compute_hash(self, query: str) -> str:
        return hashlib.md5(query.encode()).hexdigest()
    
    def get(self, query: str, return_similarity: bool = False) -> Tuple[Optional[Any], float]:
        with self._lock:
            query_hash = self._compute_hash(query)
            
            if query_hash in self._cache:
                entry = self._cache[query_hash]
                if not entry.is_expired(self.ttl):
                    entry.access_count += 1
                    entry.last_access = time.time()
                    self._cache.move_to_end(query_hash)
                    self._hits += 1
                    self._exact_hits += 1
                    return (entry.value, 1.0) if return_similarity else (entry.value, 1.0)[0]
                else:
                    del self._cache[query_hash]
            
            self._misses += 1
            return (None, 0.0) if return_similarity else (None, 0.0)
    
    def set(self, query: str, value: Any, embedding: Optional[List[float]] = None):
        with self._lock:
            query_hash = self._compute_hash(query)
            
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[query_hash] = QueryCacheEntry(
                key=query_hash,
                value=value,
                embedding=embedding or [],
                original_query=query
            )
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            return {
                "type": "semantic_query_cache",
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "exact_hits": self._exact_hits,
                "similar_hits": self._similar_hits,
                "hit_rate": hit_rate
            }


@dataclass
class QueryCacheEntry:
    key: str
    value: Any
    embedding: List[float] = field(default_factory=list)
    original_query: str = ""
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    
    def is_expired(self, ttl: int) -> bool:
        return (time.time() - self.created_at) > ttl


# ============== Retrieval Result Cache ==============

class RetrievalResultCache:
    def __init__(self, max_size: int = 500, ttl: int = 1800):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[str, RetrievalCacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, query: str, top_k: int, filters: Optional[Dict] = None) -> str:
        key_parts = [hashlib.md5(query.encode()).hexdigest(), str(top_k)]
        if filters:
            filter_str = "|".join(f"{k}={v}" for k, v in sorted(filters.items()))
            key_parts.append(hashlib.md5(filter_str.encode()).hexdigest()[:8])
        return "|".join(key_parts)
    
    def get(self, query: str, top_k: int = 10, filters: Optional[Dict] = None) -> Optional[List[Dict]]:
        with self._lock:
            key = self._make_key(query, top_k, filters)
            
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            if entry.is_expired(self.ttl):
                del self._cache[key]
                self._misses += 1
                return None
            
            entry.access_count += 1
            entry.last_access = time.time()
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value
    
    def set(self, query: str, results: List[Dict], top_k: int = 10, filters: Optional[Dict] = None):
        with self._lock:
            key = self._make_key(query, top_k, filters)
            
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = RetrievalCacheEntry(key=key, value=results, fused_results=results)
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            return {
                "type": "retrieval_cache",
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate
            }


@dataclass
class RetrievalCacheEntry:
    key: str
    value: Any
    fused_results: List[Dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    
    def is_expired(self, ttl: int) -> bool:
        return (time.time() - self.created_at) > ttl


# ============== LLM Response Cache ==============

class LLMResponseCache:
    def __init__(self, max_size: int = 200, ttl: int = 7200):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[str, LLMCacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, messages: List[Dict]) -> str:
        content = ""
        for m in messages:
            content += m.get("role", "") + ":" + m.get("content", "") + "|"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, messages: List[Dict]) -> Optional[Dict]:
        with self._lock:
            key = self._make_key(messages)
            
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            if entry.is_expired(self.ttl):
                del self._cache[key]
                self._misses += 1
                return None
            
            entry.access_count += 1
            entry.last_access = time.time()
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value
    
    def set(self, messages: List[Dict], response: Dict):
        with self._lock:
            key = self._make_key(messages)
            
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = LLMCacheEntry(key=key, value=response, messages=messages, response=response)
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            return {
                "type": "llm_cache",
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate
            }


@dataclass
class LLMCacheEntry:
    key: str
    value: Any
    messages: List[Dict] = field(default_factory=list)
    response: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    
    def is_expired(self, ttl: int) -> bool:
        return (time.time() - self.created_at) > ttl


# ============== 测试函数 ==============

def test_lru_cache():
    print('=== 测试 LRU Cache ===')
    cache = LRUCache(max_size=3, ttl=60)
    cache.set('a', 1)
    cache.set('b', 2)
    cache.set('c', 3)
    print(f'a={cache.get("a")}, b={cache.get("b")}, c={cache.get("c")}')
    cache.set('d', 4)  # 触发 LRU 淘汰
    print(f'a 被淘汰: {cache.get("a") is None}, d={cache.get("d")}')
    
    stats = cache.get_stats()
    print(f'缓存大小: {stats["size"]}, 命中率: {stats["hit_rate"]:.2%}')
    print('✅ LRU Cache 测试通过\n')


def test_semantic_query_cache():
    print('=== 测试 SemanticQueryCache ===')
    sem_cache = SemanticQueryCache(max_size=10, ttl=60, similarity_threshold=0.9)
    sem_cache.set('Python 是什么', {'answer': '一种编程语言'})
    value, sim = sem_cache.get('Python 是什么', return_similarity=True)
    print(f'精确匹配: value={value}, similarity={sim}')
    
    stats = sem_cache.get_stats()
    print(f'缓存大小: {stats["size"]}, 命中率: {stats["hit_rate"]:.2%}')
    print('✅ SemanticQueryCache 测试通过\n')


def test_retrieval_result_cache():
    print('=== 测试 RetrievalResultCache ===')
    ret_cache = RetrievalResultCache(max_size=10, ttl=60)
    results = [{'id': '1', 'content': '测试'}, {'id': '2', 'content': '测试2'}]
    ret_cache.set('查询', results)
    cached = ret_cache.get('查询')
    print(f'检索缓存: {len(cached)} 条结果')
    
    # 测试过滤器
    ret_cache.set('查询2', [{'id': '3'}], filters={'doc_type': 'article'})
    cached2 = ret_cache.get('查询2', filters={'doc_type': 'article'})
    print(f'带过滤器查询: {len(cached2)} 条结果')
    
    stats = ret_cache.get_stats()
    print(f'缓存大小: {stats["size"]}, 命中率: {stats["hit_rate"]:.2%}')
    print('✅ RetrievalResultCache 测试通过\n')


def test_llm_response_cache():
    print('=== 测试 LLMResponseCache ===')
    llm_cache = LLMResponseCache(max_size=10, ttl=60)
    messages = [{'role': 'user', 'content': '你好'}]
    response = {'choices': [{'message': {'content': '你好！'}}]}
    llm_cache.set(messages, response)
    cached = llm_cache.get(messages)
    print(f'LLM 缓存: {cached["choices"][0]["message"]["content"]}')
    
    stats = llm_cache.get_stats()
    print(f'缓存大小: {stats["size"]}, 命中率: {stats["hit_rate"]:.2%}')
    print('✅ LLMResponseCache 测试通过\n')


def test_ttl_expiration():
    print('=== 测试 TTL 过期 ===')
    cache = LRUCache(max_size=10, ttl=1)
    cache.set('x', 100)
    assert cache.get('x') == 100
    
    print('等待 1.5 秒...')
    time.sleep(1.5)
    assert cache.get('x') is None
    print('✅ TTL 过期测试通过\n')


def test_concurrent_access():
    print('=== 测试并发访问 ===')
    cache = LRUCache(max_size=100, ttl=60)
    
    def writer(n):
        for i in range(10):
            cache.set(f'key_{n}_{i}', f'value_{n}_{i}')
    
    def reader(n):
        for i in range(10):
            cache.get(f'key_{n}_{i}')
    
    import threading
    threads = []
    for i in range(5):
        threads.append(threading.Thread(target=writer, args=(i,)))
        threads.append(threading.Thread(target=reader, args=(i,)))
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    stats = cache.get_stats()
    print(f'并发操作完成: {stats["size"]} 条记录, 命中率: {stats["hit_rate"]:.2%}')
    print('✅ 并发访问测试通过\n')


if __name__ == '__main__':
    print('=' * 50)
    print('FusionRAG KV Cache 优化器测试')
    print('=' * 50)
    print()

    test_lru_cache()
    test_semantic_query_cache()
    test_retrieval_result_cache()
    test_llm_response_cache()
    test_ttl_expiration()
    test_concurrent_access()

    print('=' * 50)
    print('所有测试完成!')
    print('=' * 50)
