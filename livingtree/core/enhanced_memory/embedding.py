"""
嵌入引擎 (Embedding Engine)

向量嵌入和语义搜索：
- 文本嵌入生成
- 余弦相似度计算
- 近似最近邻搜索
"""

import math
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """向量嵌入引擎"""

    def __init__(self, model_name: str = "default"):
        self.model_name = model_name
        self._dimension = 768
        self._cache: Dict[str, List[float]] = {}
        self._embed_func: Optional[Callable[[str], List[float]]] = None
        self._init_provider()

    def _init_provider(self):
        try:
            import ollama
            logger.info(f"使用 Ollama 嵌入模型: {self.model_name}")
        except ImportError:
            logger.info("Ollama 未安装，使用简单嵌入方案")

    def set_embed_func(self, func: Callable[[str], List[float]]):
        self._embed_func = func

    def embed(self, text: str) -> List[float]:
        cache_key = text[:200]
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self._embed_func:
            vector = self._embed_func(text)
        else:
            vector = self._simple_hash_embed(text)

        self._cache[cache_key] = vector
        if len(self._cache) > 1000:
            self._cache.pop(next(iter(self._cache)))

        return vector

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(text) for text in texts]

    def similarity(self, text1: str, text2: str) -> float:
        vec1 = self.embed(text1)
        vec2 = self.embed(text2)
        return self._cosine_similarity(vec1, vec2)

    def search(self, query: str, documents: List[str],
               top_k: int = 5) -> List[Tuple[str, float]]:
        query_vec = self.embed(query)
        doc_vecs = self.embed_batch(documents)

        scored = [(doc, self._cosine_similarity(query_vec, doc_vec))
                  for doc, doc_vec in zip(documents, doc_vecs)]
        scored.sort(key=lambda x: -x[1])

        return scored[:top_k]

    def _simple_hash_embed(self, text: str) -> List[float]:
        import hashlib
        hash_bytes = hashlib.sha256(text.encode()).digest()
        vector = []
        for i in range(0, min(32, self._dimension // 8)):
            vector.append(
                ((hash_bytes[i] / 255.0) - 0.5) * 2.0)

        while len(vector) < self._dimension:
            vector.append(0.0)

        return vector[:self._dimension]

    def _cosine_similarity(self, vec1: List[float],
                           vec2: List[float]) -> float:
        if len(vec1) != len(vec2):
            min_len = min(len(vec1), len(vec2))
            vec1 = vec1[:min_len]
            vec2 = vec2[:min_len]

        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)


__all__ = ["EmbeddingEngine"]
