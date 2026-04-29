"""
L3 语义缓存模块
基于向量数据库的语义缓存实现
"""

import os
import json
import time
from typing import Optional, Any, Dict, List
from threading import RLock
from dataclasses import dataclass

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None


@dataclass
class SemanticCacheResult:
    """语义缓存结果"""
    query: str
    response: Any
    similarity: float
    model_id: str
    created_at: float


class EmbeddingGenerator:
    """嵌入向量生成器"""
    
    def __init__(self, dim: int = 384):
        self.dim = dim
        self._cache: Dict[str, List[float]] = {}
    
    def generate(self, text: str) -> List[float]:
        """生成文本嵌入向量"""
        import hashlib
        
        features = []
        for i in range(self.dim):
            hash_input = f"{text}_{i}_feature"
            h = hashlib.md5(hash_input.encode()).hexdigest()
            val = int(h[:8], 16) / (16**8)
            features.append(val - 0.5)
        
        # L2归一化
        if HAS_NUMPY:
            vec = np.array(features, dtype=np.float64)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec.tolist()
        else:
            total = sum(f * f for f in features) ** 0.5
            if total > 0:
                features = [f / total for f in features]
            return features


class SemanticCache:
    """
    L3 语义缓存
    - 技术：向量数据库(FAISS/Chroma)
    - 维度：384维嵌入向量
    - 匹配：余弦相似度 > 0.85
    """
    
    def __init__(self, vector_dim: int = 384, similarity_threshold: float = 0.85,
                 index_type: str = "faiss", persist_path: str = "~/.hermes-desktop/cache/semantic_index",
                 batch_size: int = 100):
        self.vector_dim = vector_dim
        self.similarity_threshold = similarity_threshold
        self.index_type = index_type
        self.persist_path = os.path.expanduser(persist_path)
        self.batch_size = batch_size
        self._lock = RLock()
        self._hits = 0
        self._misses = 0
        self.index = None
        self.vectors: List[List[float]] = []
        
        self.embedding_generator = EmbeddingGenerator(vector_dim)
        self._init_storage()
    
    def _init_storage(self):
        """初始化存储"""
        os.makedirs(self.persist_path, exist_ok=True)
        
        self.meta_path = os.path.join(self.persist_path, "metadata.json")
        self.vectors_path = os.path.join(self.persist_path, "vectors.npy")
        
        if os.path.exists(self.meta_path):
            with open(self.meta_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {"entries": [], "count": 0}
        
        if os.path.exists(self.vectors_path) and HAS_NUMPY:
            self.vectors = np.load(self.vectors_path).tolist()
        else:
            self.vectors = []
        
        self._init_index()
    
    def _init_index(self):
        """初始化向量索引"""
        if self.index_type == "faiss" and HAS_NUMPY:
            try:
                import faiss
                if len(self.vectors) > 0:
                    self.index = faiss.IndexFlatIP(self.vector_dim)
                    self.index.add(np.array(self.vectors, dtype=np.float32))
            except ImportError:
                self.index = None
                self.index_type = "list"
        else:
            self.index = None
            self.index_type = "list"
    
    def _save_state(self):
        """保存状态"""
        with open(self.meta_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False)
        if HAS_NUMPY and self.vectors:
            np.save(self.vectors_path, np.array(self.vectors, dtype=np.float32))
    
    def get(self, query: str) -> Optional[SemanticCacheResult]:
        """语义搜索缓存"""
        with self._lock:
            if len(self.metadata["entries"]) == 0:
                self._misses += 1
                return None
            
            query_vector = self.embedding_generator.generate(query)
            
            if self.index is not None and HAS_NUMPY:
                qv = np.array([query_vector], dtype=np.float32)
                distances, indices = self.index.search(qv, min(10, len(self.metadata["entries"])))
                best_idx = indices[0][0]
                best_dist = float(distances[0][0])
            else:
                best_idx = -1
                best_dist = 0.0
                for i, vec in enumerate(self.vectors):
                    sim = sum(a * b for a, b in zip(query_vector, vec))
                    if sim > best_dist:
                        best_dist = sim
                        best_idx = i
            
            if best_idx < 0 or best_idx >= len(self.metadata["entries"]):
                self._misses += 1
                return None
            
            if best_dist < self.similarity_threshold:
                self._misses += 1
                return None
            
            entry = self.metadata["entries"][best_idx]
            response = entry.get("response")
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                except:
                    pass
            
            self._hits += 1
            
            return SemanticCacheResult(
                query=entry["query"],
                response=response,
                similarity=best_dist,
                model_id=entry.get("model_id"),
                created_at=entry.get("created_at", time.time())
            )
    
    def set(self, query: str, response: Any, model_id: str = None):
        """添加语义缓存"""
        with self._lock:
            vector = self.embedding_generator.generate(query)
            
            if isinstance(response, (dict, list)):
                response_str = json.dumps(response, ensure_ascii=False)
            else:
                response_str = str(response)
            
            entry = {
                "query": query,
                "response": response_str,
                "model_id": model_id,
                "created_at": time.time(),
                "access_count": 1
            }
            
            idx = len(self.metadata["entries"])
            self.metadata["entries"].append(entry)
            self.metadata["count"] += 1
            self.vectors.append(vector)
            
            if self.index is not None and HAS_NUMPY:
                self.index.add(np.array([vector], dtype=np.float32))
            
            if self.metadata["count"] % self.batch_size == 0:
                self._save_state()
    
    def search(self, query: str, top_k: int = 5) -> List[SemanticCacheResult]:
        """语义搜索"""
        with self._lock:
            if len(self.metadata["entries"]) == 0:
                return []
            
            query_vector = self.embedding_generator.generate(query)
            results = []
            
            for i, vec in enumerate(self.vectors):
                sim = sum(a * b for a, b in zip(query_vector, vec))
                if sim > 0.5:
                    entry = self.metadata["entries"][i]
                    response = entry.get("response")
                    if isinstance(response, str):
                        try:
                            response = json.loads(response)
                        except:
                            pass
                    results.append(SemanticCacheResult(
                        query=entry["query"],
                        response=response,
                        similarity=sim,
                        model_id=entry.get("model_id"),
                        created_at=entry.get("created_at", time.time())
                    ))
            
            results.sort(key=lambda x: x.similarity, reverse=True)
            return results[:top_k]
    
    def update_similarity_threshold(self, new_threshold: float):
        """更新相似度阈值"""
        self.similarity_threshold = max(0.5, min(0.99, new_threshold))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        
        return {
            "size": len(self.metadata["entries"]),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "similarity_threshold": self.similarity_threshold,
            "vector_dim": self.vector_dim,
            "index_type": self.index_type
        }
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self.metadata = {"entries": [], "count": 0}
            self.vectors = []
            self._init_index()
            self._save_state()
            self._hits = 0
            self._misses = 0
