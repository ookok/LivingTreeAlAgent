"""SmartGC — Importance-weighted intelligent memory eviction.

Replaces naive FIFO eviction in struct_mem and vector_store with a combined
frequency × recency × depth scoring model. High-value memories persist longer;
low-value noise is evicted first.

Scoring formula: score = access_count × decay_factor × depth_quality
  - access_count: how many times this entry was retrieved
  - decay_factor: exp(-hours_since_last_access / halflife_hours)
  - depth_quality: 0.0-1.0, from DepthGrading if available

Integration: replaces plain dict in struct_mem._entries and vector_store._vectors.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class WeightedEntry:
    value: Any
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    depth_quality: float = 0.5  # 0.0-1.0 from DepthGrading


class SmartStore:
    """Importance-weighted key-value store with automatic eviction."""

    def __init__(self, max_size: int = 10000, halflife_hours: float = 24.0):
        self._data: dict[str, WeightedEntry] = {}
        self.max_size = max_size
        self.halflife_hours = halflife_hours

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def keys(self):
        return self._data.keys()

    def items(self):
        for k, e in self._data.items():
            yield k, e.value

    def values(self):
        for e in self._data.values():
            yield e.value

    def get(self, key: str, default=None) -> Any:
        entry = self._data.get(key)
        if entry is None:
            return default
        entry.access_count += 1
        entry.last_access = time.time()
        return entry.value

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def set(self, key: str, value: Any, depth_quality: float = 0.5) -> None:
        if key in self._data:
            entry = self._data[key]
            entry.value = value
            entry.access_count += 1
            entry.last_access = time.time()
            entry.depth_quality = max(entry.depth_quality, depth_quality)
        else:
            self._data[key] = WeightedEntry(value=value, depth_quality=depth_quality)
        self._evict_if_needed()

    def __setitem__(self, key: str, value: Any):
        self.set(key, value)

    def pop(self, key: str, default=None) -> Any:
        entry = self._data.pop(key, None)
        return entry.value if entry else default

    def _score(self, entry: WeightedEntry) -> float:
        now = time.time()
        hours = (now - entry.last_access) / 3600.0
        decay = math.exp(-hours / max(self.halflife_hours, 0.1))
        freq = min(math.log2(entry.access_count + 1), 5.0)  # cap at 32 accesses
        return freq * decay * entry.depth_quality

    def _evict_if_needed(self) -> None:
        if len(self._data) <= self.max_size:
            return
        excess = len(self._data) - self.max_size
        scored = [(k, self._score(e)) for k, e in self._data.items()]
        scored.sort(key=lambda x: x[1])  # lowest score first
        for k, _ in scored[:excess]:
            del self._data[k]

    def stats(self) -> dict:
        return {
            "size": len(self._data),
            "max_size": self.max_size,
            "avg_access": sum(e.access_count for e in self._data.values()) / max(len(self._data), 1),
        }


__all__ = ["SmartStore", "WeightedEntry"]
