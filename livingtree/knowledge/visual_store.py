"""Visual Knowledge Store — Persist and retrieve visual world models.

Based on arXiv:2601.19834: visual world models as first-class knowledge objects.

Stores generated VisualWorldModel instances alongside their task descriptions,
enabling retrieval of visual representations for similar queries.

Two-tier storage:
  L1: In-memory LRU cache (recent visual models)
  L2: JSON file (persistent, queryable by task type + capability)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from loguru import logger


class VisualKnowledgeStore:
    """Store and retrieve visual world models across sessions.

    Key value: reusing visual representations avoids regenerating
    similar diagrams for similar queries (like prompt caching for text).
    """

    def __init__(self, store_path: str = ".livingtree/visual_store.json"):
        self._store_path = Path(store_path)
        self._cache: dict[str, dict] = {}
        self._stats = {"hits": 0, "misses": 0, "stored": 0}
        self._load()

    # ── Core API ──

    def store(
        self,
        query: str,
        representation: str,
        capability: str,
        format: str = "ascii",
        description: str = "",
        confidence: float = 0.7,
    ) -> str:
        """Store a generated visual world model.

        Returns the cache key for future retrieval.
        """
        entry = {
            "query": query[:500],
            "representation": representation,
            "capability": capability,
            "format": format,
            "description": description,
            "confidence": confidence,
            "stored_at": time.time(),
            "hit_count": 0,
        }

        key = self._hash(query, capability)
        self._cache[key] = entry
        self._stats["stored"] += 1
        self._save()
        return key

    def retrieve(self, query: str, capability: str = None) -> Optional[dict]:
        """Find the best matching visual world model for a query.

        Args:
            query: Current task description.
            capability: Optional capability filter (simulation/reconstruction).

        Returns:
            dict with representation + metadata, or None.
        """
        # Exact hash match
        key = self._hash(query, capability)
        if key in self._cache:
            entry = self._cache[key]
            entry["hit_count"] = entry.get("hit_count", 0) + 1
            self._stats["hits"] += 1
            return entry

        # Fuzzy match: find most similar query
        best_entry = None
        best_score = 0.0

        for cached_key, entry in self._cache.items():
            if capability and entry.get("capability") != capability:
                continue

            score = self._similarity(query, entry.get("query", ""))
            if score > best_score and score > 0.3:
                best_score = score
                best_entry = entry

        if best_entry:
            best_entry["hit_count"] = best_entry.get("hit_count", 0) + 1
            self._stats["hits"] += 1
            return best_entry

        self._stats["misses"] += 1
        return None

    def retrieve_similar(
        self, query: str, top_k: int = 3, capability: str = None
    ) -> list[dict]:
        """Retrieve top-K similar visual models."""
        scored = []
        for key, entry in self._cache.items():
            if capability and entry.get("capability") != capability:
                continue
            score = self._similarity(query, entry.get("query", ""))
            if score > 0.2:
                scored.append((score, entry))

        scored.sort(key=lambda x: -x[0])
        return [entry for _, entry in scored[:top_k]]

    # ── Query API ──

    @property
    def stats(self) -> dict:
        total = self._stats["hits"] + self._stats["misses"]
        return {
            **self._stats,
            "entries": len(self._cache),
            "hit_rate": self._stats["hits"] / max(1, total),
        }

    def flush(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        self._save()
        return count

    # ── Persistence ──

    def _load(self) -> None:
        try:
            if self._store_path.exists():
                data = json.loads(self._store_path.read_text("utf-8"))
                self._cache = data
                self._stats["stored"] = len(data)
        except Exception:
            logger.debug("VisualKnowledgeStore: no existing data")

    def _save(self) -> None:
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            self._store_path.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2),
                "utf-8",
            )
        except Exception:
            pass

    # ── Helpers ──

    @staticmethod
    def _hash(query: str, capability: str = None) -> str:
        import hashlib
        key = query.strip().lower()
        if capability:
            key += f":{capability}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Simple token overlap similarity."""
        if not a or not b:
            return 0.0
        tokens_a = set(a.lower().split())
        tokens_b = set(b.lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        return len(intersection) / min(len(tokens_a), len(tokens_b))


# ── Singleton ──

_store: Optional[VisualKnowledgeStore] = None


def get_visual_store() -> VisualKnowledgeStore:
    global _store
    if _store is None:
        _store = VisualKnowledgeStore()
    return _store
