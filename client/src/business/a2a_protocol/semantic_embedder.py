"""
语义嵌入生成器
==================
为 EigenFlux 信号生成语义嵌入向量，用于向量相似度匹配。

特性：
1. 使用 GlobalModelRouter 调用 LLM 生成嵌入
2. 缓存嵌入结果避免重复计算
3. 支持多种嵌入策略
4. 异步批量生成

Author: LivingTree AI Agent
Date: 2026-04-29
"""

import asyncio
import hashlib
import json
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import threading

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ==================== 配置 ====================

@dataclass
class EmbeddingConfig:
    """嵌入配置"""
    model: str = "embed"                    # 嵌入模型
    dimensions: int = 384                   # 向量维度
    batch_size: int = 32                    # 批处理大小
    cache_size: int = 10000                 # 缓存大小
    similarity_threshold: float = 0.7        # 相似度阈值
    ttl: int = 3600                         # 缓存 TTL（秒）
    
    # 嵌入策略
    include_keywords: bool = True           # 包含关键词
    include_domain: bool = True             # 包含领域
    include_payload: bool = True             # 包含载荷摘要
    include_tags: bool = True               # 包含标签


# ==================== 文本向量化工具 ====================

class TextVectorizer:
    """
    轻量级文本向量化工具
    ==================
    当没有外部嵌入模型时，使用基于词频的简单向量化
    """
    
    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions
        self._vocab: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        # 移除标点，转小写，按空格分词
        import re
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        tokens = text.split()
        # 过滤停用词
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                     'could', 'should', 'may', 'might', 'must', 'shall',
                     'i', 'you', 'he', 'she', 'it', 'we', 'they', 'this', 'that',
                     'and', 'or', 'but', 'if', 'then', 'not', 'no', 'so', 'in',
                     'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from'}
        return [t for t in tokens if len(t) > 2 and t not in stopwords]
    
    def _compute_idf(self, texts: List[str]):
        """计算 IDF"""
        df = defaultdict(int)
        for text in texts:
            tokens = set(self._tokenize(text))
            for token in tokens:
                df[token] += 1
        
        n = len(texts)
        for token, freq in df.items():
            self._idf[token] = max(0, 1 + (n - freq) / (freq + 1))
    
    def _get_vocab_index(self, token: str) -> int:
        """获取词在词汇表中的索引"""
        with self._lock:
            if token not in self._vocab:
                if len(self._vocab) < self.dimensions:
                    idx = len(self._vocab)
                    self._vocab[token] = idx
                else:
                    # 词汇表已满，返回哈希索引
                    return hash(token) % self.dimensions
            return self._vocab[token]
    
    def vectorize(self, text: str) -> List[float]:
        """将文本向量化"""
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.dimensions
        
        # TF-IDF 向量
        tf = defaultdict(float)
        for token in tokens:
            tf[token] += 1
        for token in tf:
            tf[token] /= len(tokens)  # 归一化 TF
        
        # 构建向量
        vector = [0.0] * self.dimensions
        for token, tf_val in tf.items():
            idx = self._get_vocab_index(token)
            idf_val = self._idf.get(token, 1.0)
            vector[idx] = tf_val * idf_val
        
        # L2 归一化
        if HAS_NUMPY:
            v = np.array(vector)
            norm = np.linalg.norm(v)
            if norm > 0:
                vector = (v / norm).tolist()
        else:
            norm = sum(x * x for x in vector) ** 0.5
            if norm > 0:
                vector = [x / norm for x in vector]
        
        return vector
    
    def batch_vectorize(self, texts: List[str]) -> List[List[float]]:
        """批量向量化"""
        self._compute_idf(texts)
        return [self.vectorize(t) for t in texts]
    
    def compute_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if not HAS_NUMPY:
            dot = sum(a * b for a, b in zip(vec1, vec2))
            norm1 = sum(a * a for a in vec1) ** 0.5
            norm2 = sum(b * b for b in vec2) ** 0.5
            return dot / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0
        
        v1, v2 = np.array(vec1), np.array(vec2)
        dot = np.dot(v1, v2)
        norm = np.linalg.norm(v1) * np.linalg.norm(v2)
        return dot / norm if norm > 0 else 0.0


# ==================== 语义嵌入生成器 ====================

class SemanticEmbedder:
    """
    语义嵌入生成器
    ==================
    为信号生成语义向量，用于相似度匹配
    """
    
    def __init__(self, config: EmbeddingConfig = None,
                 router: Any = None,
                 signal_bus: Any = None):
        self.config = config or EmbeddingConfig()
        self._router = router
        self._signal_bus = signal_bus
        self._vectorizer = TextVectorizer(self.config.dimensions)
        
        # 嵌入缓存
        self._embedding_cache: Dict[str, Tuple[List[float], float]] = {}
        self._cache_lock = threading.Lock()
        
        # 批量嵌入队列
        self._pending_embeddings: Dict[str, Dict] = {}
        self._batch_lock = threading.Lock()
        
        # 统计
        self._stats = {
            "embeddings_generated": 0,
            "embeddings_cached": 0,
            "embeddings_failed": 0,
        }
    
    def _generate_cache_key(self, text: str, context: Dict = None) -> str:
        """生成缓存键"""
        content = json.dumps({
            "text": text,
            "context": context or {},
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _is_cache_valid(self, timestamp: float) -> bool:
        """检查缓存是否有效"""
        return time.time() - timestamp < self.config.ttl
    
    def _extract_signal_text(self, signal: Any) -> str:
        """从信号提取可嵌入的文本"""
        parts = []
        
        # 关键词
        if self.config.include_keywords and signal.metadata.keywords:
            parts.extend(signal.metadata.keywords)
        
        # 领域
        if self.config.include_domain:
            domain = signal.payload.get("domain", "")
            if domain:
                parts.append(domain)
        
        # 载荷摘要
        if self.config.include_payload:
            payload_str = json.dumps(signal.payload, sort_keys=True)
            parts.append(payload_str)
        
        # 标签
        if self.config.include_tags and signal.metadata.tags:
            parts.extend(signal.metadata.tags)
        
        # 信号类型
        parts.append(signal.metadata.signal_type.value)
        
        return " ".join(str(p) for p in parts)
    
    async def _generate_embedding_llm(self, text: str) -> Optional[List[float]]:
        """使用 LLM 生成嵌入向量"""
        if not self._router:
            return None
        
        try:
            # 使用 LLM 生成语义摘要，然后向量化
            prompt = f"""分析以下文本，提取核心语义特征：

文本：{text[:500]}

请用 50 个关键词描述这段文本的核心语义，用逗号分隔。"""
            
            # 通过路由调用 LLM
            result = await self._router.acall(
                prompt,
                capability="summarize",
                max_tokens=200,
            )
            
            if result and hasattr(result, 'content'):
                summary = result.content
                # 使用摘要文本生成向量
                return self._vectorizer.vectorize(summary)
            
        except Exception as e:
            print(f"[SemanticEmbedder] LLM embedding failed: {e}")
        
        return None
    
    def _generate_embedding_local(self, text: str) -> List[float]:
        """使用本地向量器生成嵌入"""
        return self._vectorizer.vectorize(text)
    
    def get_embedding(self, text: str, context: Dict = None,
                       use_cache: bool = True) -> Optional[List[float]]:
        """
        获取文本嵌入向量
        
        参数：
            text: 要嵌入的文本
            context: 上下文信息
            use_cache: 是否使用缓存
        
        返回：嵌入向量或 None
        """
        cache_key = self._generate_cache_key(text, context)
        
        # 检查缓存
        if use_cache:
            with self._cache_lock:
                if cache_key in self._embedding_cache:
                    embedding, timestamp = self._embedding_cache[cache_key]
                    if self._is_cache_valid(timestamp):
                        self._stats["embeddings_cached"] += 1
                        return embedding
                    # 缓存过期，删除
                    del self._embedding_cache[cache_key]
        
        # 生成新嵌入
        embedding = self._generate_embedding_local(text)
        
        # 存入缓存
        with self._cache_lock:
            self._embedding_cache[cache_key] = (embedding, time.time())
            self._stats["embeddings_generated"] += 1
        
        return embedding
    
    async def get_embedding_async(self, text: str, 
                                   context: Dict = None) -> Optional[List[float]]:
        """异步获取嵌入向量"""
        cache_key = self._generate_cache_key(text, context)
        
        # 检查缓存
        with self._cache_lock:
            if cache_key in self._embedding_cache:
                embedding, timestamp = self._embedding_cache[cache_key]
                if self._is_cache_valid(timestamp):
                    self._stats["embeddings_cached"] += 1
                    return embedding
        
        # 尝试 LLM 嵌入
        embedding = await self._generate_embedding_llm(text)
        
        if embedding is None:
            # 回退到本地向量器
            embedding = self._generate_embedding_local(text)
        
        # 存入缓存
        with self._cache_lock:
            self._embedding_cache[cache_key] = (embedding, time.time())
            self._stats["embeddings_generated"] += 1
        
        return embedding
    
    def add_to_batch(self, signal_id: str, text: str, 
                     callback: Callable[[List[float]], None] = None):
        """添加嵌入任务到批队列"""
        with self._batch_lock:
            self._pending_embeddings[signal_id] = {
                "text": text,
                "callback": callback,
                "timestamp": time.time(),
            }
    
    async def process_batch(self) -> Dict[str, List[float]]:
        """处理批量嵌入"""
        with self._batch_lock:
            if not self._pending_embeddings:
                return {}
            
            items = self._pending_embeddings.copy()
            self._pending_embeddings.clear()
        
        results = {}
        
        # 批量文本
        texts = [item["text"] for item in items.values()]
        
        # 尝试 LLM 批量生成
        llm_results = None
        if self._router:
            try:
                # 批量调用
                for signal_id, item in items.items():
                    embedding = await self.get_embedding_async(item["text"])
                    results[signal_id] = embedding
            except Exception as e:
                print(f"[SemanticEmbedder] Batch LLM failed: {e}")
        
        # 回退到本地批量
        if not results or None in results.values():
            local_results = self._vectorizer.batch_vectorize(texts)
            for i, (signal_id, _) in enumerate(items.items()):
                if signal_id not in results or results[signal_id] is None:
                    results[signal_id] = local_results[i]
        
        # 触发回调
        for signal_id, embedding in results.items():
            if signal_id in items and items[signal_id]["callback"]:
                items[signal_id]["callback"](embedding)
        
        return results
    
    def compute_similarity(self, vec1: List[float], 
                           vec2: List[float]) -> float:
        """计算两个向量的相似度"""
        return self._vectorizer.compute_similarity(vec1, vec2)
    
    def find_similar(self, query: str, candidates: List[Dict],
                     top_k: int = 5, threshold: float = None) -> List[Tuple[Dict, float]]:
        """
        查找相似的候选项
        
        参数：
            query: 查询文本
            candidates: 候选项列表，每项包含 id, text, embedding
            top_k: 返回前 k 个
            threshold: 相似度阈值
        
        返回：(候选项, 相似度) 列表
        """
        threshold = threshold or self.config.similarity_threshold
        
        # 获取查询向量
        query_embedding = self.get_embedding(query)
        if not query_embedding:
            return []
        
        similarities = []
        
        for candidate in candidates:
            embedding = candidate.get("embedding")
            if not embedding:
                # 尝试从候选项文本生成
                text = candidate.get("text", "")
                embedding = self.get_embedding(text)
            
            if embedding:
                sim = self.compute_similarity(query_embedding, embedding)
                if sim >= threshold:
                    similarities.append((candidate, sim))
        
        # 排序并返回 top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._cache_lock:
            total = self._stats["embeddings_generated"] + self._stats["embeddings_cached"]
            cache_rate = (
                self._stats["embeddings_cached"] / total 
                if total > 0 else 0
            )
            
            return {
                **self._stats,
                "cache_size": len(self._embedding_cache),
                "cache_rate": round(cache_rate, 3),
                "pending_batch": len(self._pending_embeddings),
            }
    
    def clear_cache(self):
        """清除缓存"""
        with self._cache_lock:
            self._embedding_cache.clear()
    
    def preload_from_history(self, signals: List[Any]):
        """从信号历史预加载嵌入"""
        for signal in signals[-100:]:  # 最多预加载 100 个
            text = self._extract_signal_text(signal)
            self.get_embedding(text, context={"signal_id": signal.metadata.signal_id})


# ==================== 集成到 SignalBus ====================

class EmbeddingSignalBus:
    """
    带语义嵌入的信号总线
    ==================
    扩展 SignalBus，添加自动嵌入生成
    """
    
    def __init__(self, signal_bus: Any, embedder: SemanticEmbedder = None):
        self._bus = signal_bus
        self._embedder = embedder or SemanticEmbedder()
        
        # 自动注入嵌入
        self._auto_embed = True
    
    def broadcast(self, signal: Any, **kwargs) -> int:
        """广播信号，自动生成嵌入"""
        # 如果信号没有嵌入，自动生成
        if self._auto_embed and not signal.metadata.embedding:
            text = self._embedder._extract_signal_text(signal)
            embedding = self._embedder.get_embedding(text)
            if embedding:
                signal.metadata.embedding = embedding
        
        return self._bus.broadcast(signal, **kwargs)
    
    def __getattr__(self, name):
        """代理其他方法到原始信号总线"""
        return getattr(self._bus, name)
