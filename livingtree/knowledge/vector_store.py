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
        if _HAS_SENTENCE_TRANSFORMERS:
            try:
                self._model = SentenceTransformer(
                    "all-MiniLM-L6-v2"  # small and fast
                )  # type: ignore
            except Exception as e:  # pragma: no cover
                logger.warning("Local embedding model load failed: %s", e)
                self._model = None

    def _fallback_embed(self, texts: List[str]) -> List[List[float]]:
        # Deterministic, lightweight embedding using a tiny PRNG derived from content
        vecs: List[List[float]] = []
        for t in texts:
            import struct
            h = hashlib.sha256(t.encode("utf-8")).digest()
            seed = int.from_bytes(h[:4], "little", signed=False)
            a = seed if seed != 0 else 1
            rng = a
            out: List[float] = []
            for _ in range(128):
                rng = (1103515245 * rng + 12345) & 0x7fffffff
                out.append((rng % 1000) / 1000.0)
            vecs.append(out)
        return vecs

    def embed(self, texts: List[str]) -> List[List[float]]:
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

    def search_similar(self, query_vec: List[float], top_k: int = 5) -> List[str]:
        if not self._vectors:
            return []
        # Cosine similarity
        def _cos(a: List[float], b: List[float]) -> float:
            import math
            if len(a) != len(b) or len(a) == 0:
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a)) or 1.0
            nb = math.sqrt(sum(x * x for x in b)) or 1.0
            return dot / (na * nb)

        scores: List[Tuple[str, float]] = []
        for doc_id, vec in self._vectors.items():
            scores.append((doc_id, _cos(query_vec, vec)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, _ in scores[:top_k]]

    def delete_vector(self, doc_id: str) -> None:
        self._vectors.pop(doc_id, None)

    def create_collection(self, name: str) -> None:
        # Simple in-memory store supports only one collection by default
        self.collection = name
        self._vectors = {}


__all__ = ["VectorStore", "EmbeddingBackend"]
