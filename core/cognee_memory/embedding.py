"""
向量嵌入模块

集成 sentence-transformers 实现真实向量嵌入
支持多种嵌入模型和向量存储
"""

from core.logger import get_logger
logger = get_logger('cognee_memory.embedding')

import numpy as np
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
import hashlib
import json


@dataclass
class EmbeddingConfig:
    """嵌入配置"""
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    dimension: int = 384
    batch_size: int = 32
    normalize: bool = True
    cache_dir: Optional[str] = None


class VectorStore:
    """向量存储"""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.vectors: List[np.ndarray] = []
        self.metadata: List[Dict[str, Any]] = []
        self._index: Optional[Any] = None

    def add(self, vector: np.ndarray, metadata: Dict[str, Any]):
        """添加向量"""
        if len(vector) != self.dimension:
            raise ValueError(f"向量维度必须为 {self.dimension}")

        self.vectors.append(vector)
        self.metadata.append(metadata)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5
    ) -> List[Tuple[int, float, Dict]]:
        """
        搜索最近邻

        Returns:
            List[(index, distance, metadata)]
        """
        if not self.vectors:
            return []

        query_vector = query_vector.reshape(1, -1)
        vectors = np.array(self.vectors)

        # 计算余弦相似度
        similarities = self._cosine_similarity(query_vector, vectors)[0]

        # 排序
        indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in indices:
            if similarities[idx] > 0:  # 过滤低相似度
                results.append((int(idx), float(similarities[idx]), self.metadata[idx]))

        return results

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """计算余弦相似度"""
        dot = np.dot(a, b.T)
        norm_a = np.linalg.norm(a, axis=1, keepdims=True)
        norm_b = np.linalg.norm(b, axis=1, keepdims=True)

        return dot / (norm_a * norm_b + 1e-8)

    def build_index(self, index_type: str = "flat"):
        """构建索引"""
        if index_type == "flat":
            # 已经是 flat，直接返回
            pass
        elif index_type == "ivf":
            # IVF 索引需要 faiss，暂时使用 flat
            pass

    def save(self, path: str):
        """保存向量存储"""
        data = {
            "dimension": self.dimension,
            "vectors": [v.tolist() for v in self.vectors],
            "metadata": self.metadata
        }
        with open(path, 'w') as f:
            json.dump(data, f)

    def load(self, path: str):
        """加载向量存储"""
        with open(path, 'r') as f:
            data = json.load(f)

        self.dimension = data["dimension"]
        self.vectors = [np.array(v) for v in data["vectors"]]
        self.metadata = data["metadata"]


class EmbeddingEngine:
    """嵌入引擎"""

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self.model = None
        self._load_model()

    def _load_model(self):
        """加载模型"""
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(self.config.model_name)
            self.config.dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"[EmbeddingEngine] 加载模型: {self.config.model_name}, 维度: {self.config.dimension}")
        except ImportError:
            logger.info("[EmbeddingEngine] sentence-transformers 未安装，使用模拟嵌入")
            self.model = None

    def encode(self, texts: List[str]) -> np.ndarray:
        """
        编码文本为向量

        Args:
            texts: 文本列表

        Returns:
            np.ndarray: 向量数组
        """
        if self.model is None:
            # 模拟嵌入
            return self._mock_encode(texts)

        vectors = self.model.encode(
            texts,
            batch_size=self.config.batch_size,
            normalize_embeddings=self.config.normalize,
            show_progress_bar=False
        )

        return vectors

    def _mock_encode(self, texts: List[str]) -> np.ndarray:
        """模拟嵌入（当 sentence-transformers 未安装时）"""
        vectors = []
        for text in texts:
            # 使用 hash 生成确定性随机向量
            hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
            np.random.seed(hash_val % (2**32))
            vec = np.random.randn(self.config.dimension)
            vec = vec / (np.linalg.norm(vec) + 1e-8)  # 归一化
            vectors.append(vec)

        return np.array(vectors)

    def encode_query(self, query: str) -> np.ndarray:
        """编码查询"""
        return self.encode([query])[0]


class SemanticSearch:
    """语义搜索"""

    def __init__(self, embedding_engine: Optional[EmbeddingEngine] = None):
        self.embedding_engine = embedding_engine or EmbeddingEngine()
        self.vector_store = VectorStore(dimension=self.embedding_engine.config.dimension)
        self.documents: Dict[str, str] = {}  # id -> content

    def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """添加文档"""
        # 编码
        vector = self.embedding_engine.encode_query(content)

        # 存储
        self.vector_store.add(vector, {
            "doc_id": doc_id,
            "content": content,
            "metadata": metadata or {}
        })

        self.documents[doc_id] = content

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        语义搜索

        Args:
            query: 查询文本
            top_k: 返回数量
            min_similarity: 最小相似度

        Returns:
            List[Dict]: 搜索结果
        """
        # 编码查询
        query_vector = self.embedding_engine.encode_query(query)

        # 搜索
        results = self.vector_store.search(query_vector, top_k=top_k * 2)  # 多取一些用于过滤

        # 格式化结果
        formatted = []
        for idx, similarity, metadata in results:
            if similarity < min_similarity:
                continue

            formatted.append({
                "doc_id": metadata["doc_id"],
                "content": metadata["content"],
                "similarity": similarity,
                "metadata": metadata.get("metadata", {})
            })

            if len(formatted) >= top_k:
                break

        return formatted

    def save(self, path: str):
        """保存"""
        self.vector_store.save(f"{path}.vectors")
        with open(f"{path}.docs.json", 'w') as f:
            json.dump(self.documents, f, ensure_ascii=False)

    def load(self, path: str):
        """加载"""
        self.vector_store.load(f"{path}.vectors")
        with open(f"{path}.docs.json", 'r') as f:
            self.documents = json.load(f)


# 全局实例
_global_engine: Optional[EmbeddingEngine] = None


def get_embedding_engine(config: Optional[EmbeddingConfig] = None) -> EmbeddingEngine:
    """获取嵌入引擎"""
    global _global_engine
    if _global_engine is None:
        _global_engine = EmbeddingEngine(config)
    return _global_engine


def get_semantic_search(embedding_engine: Optional[EmbeddingEngine] = None) -> SemanticSearch:
    """获取语义搜索"""
    engine = embedding_engine or get_embedding_engine()
    return SemanticSearch(engine)
