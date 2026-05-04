"""Vector store with pluggable embedding backends.

This module provides a light-weight, dependency-light vector store
that can be swapped with a local embedding model or an API-based API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
import math
import hashlib

from loguru import logger
from pydantic import BaseModel

try:
    # Optional dependency: heavy embedding model (not required for defaults)
    from sentence_transformers import SentenceTransformer  # type: ignore
    _HAS_SENTENCE_TRANSFORMERS = True
except Exception:  # pragma: no cover
    _HAS_SENTENCE_TRANSFORMERS = False
    SentenceTransformer = None  # type: ignore


class EmbeddingBackend(ABC):
    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        pass


class LocalEmbeddingBackend(EmbeddingBackend):
    """Attempt to use a local embedding model; fallback to a deterministic toy encoder."""

    def __init__(self) -> None:
        self._model = None
        self._model_loaded = False

    def _ensure_model(self) -> None:
        if self._model_loaded:
            return
        self._model_loaded = True
        if _HAS_SENTENCE_TRANSFORMERS:
            try:
                self._model = SentenceTransformer(
                    "all-MiniLM-L6-v2"
                )
            except Exception as e:
                logger.warning("Local embedding model load failed: %s", e)
                self._model = None

    def _fallback_embed(self, texts: List[str]) -> List[List[float]]:
        import hashlib
        vecs = []
        for t in texts:
            low = t.lower()
            vec = [0.0] * 128
            for i, ch in enumerate(low):
                if ch.isalpha():
                    idx = ord(ch) % 128
                    vec[idx] += 1.0 / max(len(low), 1)
            ngram = low + " " + low
            for i in range(len(ngram) - 2):
                h = ord(ngram[i]) * 256 + ord(ngram[i + 1])
                vec[h % 128] += 0.5 / max(len(ngram), 1)
            total = sum(abs(v) for v in vec) or 1.0
            vecs.append([v / total for v in vec])
        return vecs

    def embed(self, texts: List[str]) -> List[List[float]]:
        self._ensure_model()
        if self._model is not None:
            embeddings = self._model.encode(texts)  # type: ignore
            return embeddings.tolist()
        else:
            return self._fallback_embed(texts)


class APIEmbeddingBackend(EmbeddingBackend):
    """Placeholder for API-based embeddings (e.g., OpenAI)."""

    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.endpoint = endpoint
        self.api_key = api_key

    def embed(self, texts: List[str]) -> List[List[float]]:
        # In a real implementation, this would call an external service.
        # For safety, we raise a clear error to avoid silent failures.
        raise NotImplementedError("API-based embeddings are not configured in this environment.")


class VectorStore:
    """Simple in-memory vector store with embedding cache."""

    def __init__(self, embedding_backend=None, collection_name: str = "default"):
        self.collection = collection_name
        self.embedding_backend = embedding_backend or LocalEmbeddingBackend()
        self._vectors: dict[str, list[float]] = {}
        # Embedding cache to avoid re-computing
        try:
            from ..infrastructure.io_optimizer import _global_embed_cache
            self._cache = _global_embed_cache
        except Exception:
            self._cache = None
        logger.info(f"VectorStore init: {self.collection} / {type(self.embedding_backend).__name__}")

    def embed(self, text: str) -> list[float]:
        # Check cache first
        if self._cache:
            cached = self._cache.get(text)
            if cached:
                return cached
        vecs = self.embedding_backend.embed([text])
        result = vecs[0]
        if self._cache:
            self._cache.set(text, result)
        return result

    def add_vectors(self, items: List[Tuple[str, List[float]]]) -> None:
        for doc_id, vec in items:
            self._vectors[doc_id] = vec

    def search_similar(self, query_vec: list[float], top_k: int = 5) -> list[str]:
        if not self._vectors:
            return []
        try:
            import numpy as np
            ids = list(self._vectors.keys())
            matrix = np.array([self._vectors[k] for k in ids])
            query = np.array(query_vec)
            # Batch cosine: dot / (norm_a * norm_b)
            dots = np.dot(matrix, query)
            norms_a = np.linalg.norm(matrix, axis=1)
            norm_b = np.linalg.norm(query) or 1.0
            scores = dots / (norms_a * norm_b + 1e-10)
            top_indices = np.argsort(scores)[-top_k:][::-1]
            return [ids[i] for i in top_indices if scores[i] > 0]
        except ImportError:
            pass
        # Pure Python fallback
        def _cos(a, b):
            import math
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a)) or 1.0
            nb = math.sqrt(sum(x * x for x in b)) or 1.0
            return dot / (na * nb)
        scores = [(k, _cos(v, query_vec)) for k, v in self._vectors.items()]
        scores.sort(key=lambda x: x[1], reverse=True)
        return [k for k, _ in scores[:top_k]]

    def delete_vector(self, doc_id: str) -> None:
        self._vectors.pop(doc_id, None)

    def create_collection(self, name: str) -> None:
        # Simple in-memory store supports only one collection by default
        self.collection = name
        self._vectors = {}


__all__ = ["VectorStore", "EmbeddingBackend"]
