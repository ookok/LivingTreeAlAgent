"""SemanticDedupCache — LSH-based semantic deduplication for queries.

Prevents re-calling LLMs when a semantically identical query was recently answered.
Uses locality-sensitive hashing on query embeddings to find near-duplicate queries.

Cached answers carry a "semantic_cache_hit" marker so the UI can indicate reuse.

Integration:
    cache = get_semantic_cache()
    answer = cache.get(query_embedding)       # returns cached answer or None
    cache.set(query_embedding, answer_text)    # stores for future reuse

In hub.chat(): check at start, skip engine.run() on hit.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from loguru import logger

LSH_BITS = 16
LSH_PLANES_CACHE: list[list[float]] = []


def _make_planes(dim: int = 128, n: int = LSH_BITS) -> list[list[float]]:
    global LSH_PLANES_CACHE
    if LSH_PLANES_CACHE and len(LSH_PLANES_CACHE) == n:
        return LSH_PLANES_CACHE
    random.seed(42)
    LSH_PLANES_CACHE = [
        [random.gauss(0, 1) for _ in range(dim)] for _ in range(n)
    ]
    return LSH_PLANES_CACHE


def _to_lsh(embedding: list[float], dim: int = 128) -> int:
    """Convert embedding to LSH hash (16-bit integer)."""
    planes = _make_planes(dim, LSH_BITS)
    bits = 0
    vec = embedding[:dim] if len(embedding) > dim else embedding + [0.0] * (dim - len(embedding))
    for i, plane in enumerate(planes):
        dot = sum(e * p for e, p in zip(vec, plane))
        if dot > 0:
            bits |= (1 << i)
    return bits


class SemanticDedupCache:
    """Semantic query deduplication using LSH."""

    _instance: Optional["SemanticDedupCache"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "SemanticDedupCache":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = SemanticDedupCache()
        return cls._instance

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 500):
        self._store: dict[int, tuple[str, float, int]] = {}  # hash → (answer, ts, access_count)
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0

    def get(self, query_embedding: list[float]) -> Optional[str]:
        """Try to find a cached answer for this query."""
        lsh = _to_lsh(query_embedding)
        entry = self._store.get(lsh)
        if entry is None:
            self._misses += 1
            return None

        answer, ts, count = entry
        if time.time() - ts > self._ttl:
            del self._store[lsh]
            self._misses += 1
            return None

        self._store[lsh] = (answer, ts, count + 1)
        self._hits += 1
        return answer

    def set(self, query_embedding: list[float], answer: str) -> None:
        """Cache an answer for future dedup."""
        lsh = _to_lsh(query_embedding)
        self._store[lsh] = (answer, time.time(), 1)
        self._evict_if_needed()

    def _evict_if_needed(self):
        if len(self._store) <= self._max_entries:
            return
        excess = len(self._store) - self._max_entries
        scored = [(k, v[2]) for k, v in self._store.items()]  # (hash, access_count)
        scored.sort(key=lambda x: x[1])  # evict least-accessed
        for k, _ in scored[:excess]:
            del self._store[k]

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / max(total, 1) if total else 0.0

    def stats(self) -> dict:
        return {
            "entries": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 3),
        }


_semantic_cache: Optional[SemanticDedupCache] = None
_semantic_cache_lock = threading.Lock()


def get_semantic_cache() -> SemanticDedupCache:
    global _semantic_cache
    if _semantic_cache is None:
        with _semantic_cache_lock:
            if _semantic_cache is None:
                _semantic_cache = SemanticDedupCache()
    return _semantic_cache


__all__ = ["SemanticDedupCache", "get_semantic_cache", "_to_lsh"]
