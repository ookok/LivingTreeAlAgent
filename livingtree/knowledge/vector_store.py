"""Vector store with pluggable embedding backends.

This module provides a light-weight, dependency-light vector store
that can be swapped with a local embedding model or an API-based API.

Supports:
  - Hardware acceleration via HardwareAccelerator (GPU FAISS, CUDA embeddings)
  - Memory optimization via MemoryOptimizer (large memory caching)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

from loguru import logger
from pydantic import BaseModel

try:
    # Optional dependency: heavy embedding model (not required for defaults)
    from sentence_transformers import SentenceTransformer  # type: ignore
    _HAS_SENTENCE_TRANSFORMERS = True
except Exception:  # pragma: no cover
    _HAS_SENTENCE_TRANSFORMERS = False
    SentenceTransformer = None  # type: ignore

try:
    from livingtree.core.hardware_acceleration import get_accelerator
    _HAS_ACCELERATOR = True
except Exception:
    _HAS_ACCELERATOR = False
    get_accelerator = None

try:
    from livingtree.core.memory_optimizer import get_memory_optimizer
    _HAS_MEMORY_OPT = True
except Exception:
    _HAS_MEMORY_OPT = False
    get_memory_optimizer = None


class EmbeddingBackend(ABC):
    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        pass


class LocalEmbeddingBackend(EmbeddingBackend):
    """Attempt to use a local embedding model; fallback to a deterministic toy encoder.

    Automatically uses GPU via HardwareAccelerator when available.
    """

    def __init__(self) -> None:
        self._model = None
        self._model_loaded = False
        self._accelerator = None
        if _HAS_ACCELERATOR:
            try:
                self._accelerator = get_accelerator()
            except Exception:
                self._accelerator = None

    def _ensure_model(self) -> None:
        if self._model_loaded:
            return
        self._model_loaded = True
        if _HAS_SENTENCE_TRANSFORMERS:
            try:
                self._model = SentenceTransformer(
                    "all-MiniLM-L6-v2"
                )
                # Move to GPU if accelerator says so
                if self._accelerator:
                    self._accelerator.patch_sentence_transformer(self._model)
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
    """Simple in-memory vector store with embedding cache.

    Uses MemoryOptimizer for large memory caching when available.
    """

    def __init__(self, embedding_backend=None, collection_name: str = "default"):
        self.collection = collection_name
        self.embedding_backend = embedding_backend or LocalEmbeddingBackend()
        self._vectors: dict[str, list[float]] = {}
        self._matrix_cache: Any = None   # numpy array cache
        self._matrix_ids: list[str] = []  # keys corresponding to cached matrix
        self._matrix_dirty = True
        self._cache = None
        if _HAS_MEMORY_OPT:
            try:
                opt = get_memory_optimizer()
                self._cache = opt.get_embed_cache()
                logger.info("VectorStore: using MemoryOptimizer embed cache (size=%d)", self._cache.max_size)
            except Exception as e:
                logger.debug("MemoryOptimizer not available: %s", e)
        if self._cache is None:
            # Fallback to simple dict cache
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
        self._matrix_dirty = True
        # Cap at 50_000 vectors to prevent unbounded memory growth
        if len(self._vectors) > 50_000:
            excess = list(self._vectors.keys())[:len(self._vectors) - 50_000]
            for k in excess:
                self._vectors.pop(k, None)

    def search_similar(self, query_vec: list[float], top_k: int = 5) -> list[str]:
        if not self._vectors:
            return []
        # Use hardware accelerator for cosine similarity if available
        if _HAS_ACCELERATOR and self._accelerator and self._accelerator.has_gpu:
            try:
                ids = list(self._vectors.keys())
                matrix = [self._vectors[k] for k in ids]
                # Use accelerator's optimized cosine (CuPy → torch → NumPy)
                scores = []
                for i, vec in enumerate(matrix):
                    sim = self._accelerator.cosine_similarity(vec, query_vec)
                    scores.append((i, sim))
                scores.sort(key=lambda x: x[1], reverse=True)
                return [ids[i] for i, s in scores[:top_k] if s > 0]
            except Exception as e:
                logger.debug("Accelerator cosine failed: %s, falling back to NumPy", e)
        try:
            import numpy as np
            if self._matrix_dirty or self._matrix_cache is None:
                ids = list(self._vectors.keys())
                self._matrix_cache = np.array([self._vectors[k] for k in ids], dtype=np.float32)
                self._matrix_ids = ids
                self._matrix_dirty = False
            matrix = self._matrix_cache
            ids = self._matrix_ids
            query = np.array(query_vec, dtype=np.float32)
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


# ═══ LanceDB backend — disk-backed, zero-service vector store ═══


class LanceDBStore:
    """LanceDB-backed vector store for large-scale (100M+) vectors.

    Zero services — pip install lancedb, data lives in local files.
    Automatically falls back to in-memory VectorStore if lancedb unavailable.
    """

    def __init__(self, db_path: str = "", embedding_backend=None,
                 collection_name: str = "default"):
        self._path = db_path or str(Path(".livingtree/lancedb"))
        self._collection_name = collection_name
        self.embedding_backend = embedding_backend or LocalEmbeddingBackend()
        self._db = None
        self._table = None
        self._fallback = None

    def _ensure_db(self) -> bool:
        if self._db is not None:
            return True
        try:
            import lancedb
            Path(self._path).mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(self._path)
            try:
                self._table = self._db.open_table(self._collection_name)
            except Exception:
                pass
            logger.info(f"LanceDB initialized: {self._path}/{self._collection_name}")
            return True
        except ImportError:
            if self._fallback is None:
                self._fallback = VectorStore(self.embedding_backend, self._collection_name)
            return False

    def embed(self, text: str) -> list[float]:
        vecs = self.embedding_backend.embed([text])
        return vecs[0]

    def add_vectors(self, items: list[tuple[str, list[float]]]):
        if self._ensure_db() and self._db:
            import pyarrow as pa
            ids = [i[0] for i in items]
            vecs = [i[1] for i in items]
            data = pa.table({"id": ids, "vector": vecs})
            if self._table is None:
                self._table = self._db.create_table(self._collection_name, data)
            else:
                self._table.add(data)
        elif self._fallback:
            self._fallback.add_vectors(items)

    def search_similar(self, query_vec: list[float], top_k: int = 5) -> list[str]:
        if self._ensure_db() and self._table:
            results = self._table.search(query_vec).limit(top_k).to_list()
            return [r["id"] for r in results if r.get("id")]
        if self._fallback:
            return self._fallback.search_similar(query_vec, top_k)
        return []

    def create_collection(self, name: str):
        self._collection_name = name
        self._table = None
        if self._db:
            try:
                self._table = self._db.open_table(name)
            except Exception:
                self._table = self._db.create_table(name, pa.table(
                    {"id": [], "vector": []}))
        else:
            self._ensure_db()

    def count(self) -> int:
        if self._ensure_db() and self._table:
            return self._table.count_rows()
        return len(self._fallback._vectors) if self._fallback else 0
__all__ = ["VectorStore", "EmbeddingBackend"]
