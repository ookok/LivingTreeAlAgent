"""In-memory storage backend — dict-based log-structured store.

Lightweight backend for testing, small caches, and non-persistent
storage scenarios. Each segment is a logical bucket of entries.

Integrates with existing LivingTree memory stores:
  - client/src/business/tier_model/memory_cache.py (L1 cache)
  - client/src/business/collective_intelligence/collective_memory.py
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, List, Dict, Optional, Tuple

from loguru import logger

from ..storage_layer import StorageBackend, StorageSegment
from ..gc_metrics import StorageStats


@dataclass
class _Entry:
    key: str
    value: Any
    created_at: float
    last_accessed: float
    size_bytes: int

    def is_stale(self, ttl_seconds: float, now: float = None) -> bool:
        if now is None:
            now = time.time()
        return (now - self.created_at) >= ttl_seconds


class InMemoryStorageBackend(StorageBackend):
    """DisCoGC-compatible in-memory storage adapter.

    Data is organized into logical segments (buckets). Each segment
    holds up to `segment_entries` entries. Stale entries are those
    past their TTL.

    Supports both discard (delete stale entries in-place) and
    compaction (move live entries to new segments).
    """

    def __init__(
        self,
        name: str = "",
        ttl_seconds: int = 900,
        segment_entries: int = 100,
        max_entries: int = 10000,
    ):
        super().__init__(name=name or "inmemory")
        self.ttl_seconds = ttl_seconds
        self.segment_entries = segment_entries
        self.max_entries = max_entries
        self._data: OrderedDict[str, _Entry] = OrderedDict()
        self._segments: Dict[str, List[str]] = {}  # segment_id → list of keys
        self._lock = threading.Lock()
        self._next_segment_idx = 0

    def get_stats(self) -> StorageStats:
        with self._lock:
            now = time.time()
            total = len(self._data)
            total_bytes = sum(e.size_bytes for e in self._data.values())
            stale_count = sum(1 for e in self._data.values() if e.is_stale(self.ttl_seconds, now))
            live_count = total - stale_count
            stale_bytes = sum(e.size_bytes for e in self._data.values() if e.is_stale(self.ttl_seconds, now))
            live_bytes = total_bytes - stale_bytes

            return StorageStats(
                backend_name=self.name,
                total_bytes=total_bytes,
                used_bytes=total_bytes,
                stale_bytes=stale_bytes,
                live_bytes=live_bytes,
                segment_count=len(self._segments),
                stale_segment_count=0,
                fragmentation_ratio=stale_count / max(total, 1),
            )

    def list_segments(self) -> List[StorageSegment]:
        with self._lock:
            now = time.time()
            segments = []
            for seg_id, keys in list(self._segments.items()):
                if not keys:
                    continue
                segment_total = sum(self._data[k].size_bytes for k in keys if k in self._data)
                segment_stale = sum(
                    self._data[k].size_bytes
                    for k in keys
                    if k in self._data and self._data[k].is_stale(self.ttl_seconds, now)
                )
                segment_live = segment_total - segment_stale

                segment = StorageSegment(
                    segment_id=seg_id,
                    total_bytes=segment_total,
                    live_bytes=segment_live,
                    stale_bytes=segment_stale,
                    created_at=min(
                        (self._data[k].created_at for k in keys if k in self._data),
                        default=now,
                    ),
                    last_read_at=max(
                        (self._data[k].last_accessed for k in keys if k in self._data),
                        default=0.0,
                    ),
                    write_count=len(keys),
                    metadata={"key_count": len(keys)},
                )
                segments.append(segment)
            return segments

    def discard_segments(self, segment_ids: List[str]) -> int:
        total_freed = 0
        with self._lock:
            now = time.time()
            for seg_id in segment_ids:
                if seg_id not in self._segments:
                    continue
                keys = list(self._segments[seg_id])
                stale_keys = [
                    k for k in keys
                    if k in self._data and self._data[k].is_stale(self.ttl_seconds, now)
                ]
                if len(stale_keys) != len(keys):
                    continue

                freed = 0
                for k in stale_keys:
                    if k in self._data:
                        freed += self._data[k].size_bytes
                        del self._data[k]
                del self._segments[seg_id]
                total_freed += freed

            return total_freed

    def compact_segments(self, segment_ids: List[str]) -> tuple[int, int]:
        total_freed = 0
        total_written = 0
        with self._lock:
            now = time.time()
            for seg_id in segment_ids:
                if seg_id not in self._segments:
                    continue
                keys = list(self._segments[seg_id])

                stale_keys = []
                live_keys = []
                for k in keys:
                    if k in self._data:
                        if self._data[k].is_stale(self.ttl_seconds, now):
                            stale_keys.append(k)
                        else:
                            live_keys.append(k)

                freed = 0
                for k in stale_keys:
                    if k in self._data:
                        freed += self._data[k].size_bytes
                        del self._data[k]

                written = 0
                if live_keys:
                    new_seg_id = f"segment_{self._next_segment_idx}"
                    self._next_segment_idx += 1
                    new_keys = []
                    for k in live_keys:
                        if k in self._data:
                            new_keys.append(k)
                            written += self._data[k].size_bytes
                    if new_keys:
                        self._segments[new_seg_id] = new_keys

                del self._segments[seg_id]
                total_freed += freed
                total_written += written

            return total_freed, total_written

    def put(self, key: str, value: Any, size_bytes: int = 0) -> str:
        """Insert or update an entry. Returns the segment_id it was placed in."""
        with self._lock:
            if len(self._data) >= self.max_entries:
                self._evict_one_lru()

            entry = _Entry(
                key=key,
                value=value,
                created_at=time.time(),
                last_accessed=time.time(),
                size_bytes=size_bytes or len(str(value)),
            )
            self._data[key] = entry

            current_seg = self._next_segment_idx - 1
            seg_id = f"segment_{max(0, current_seg)}"
            if seg_id not in self._segments:
                seg_id = f"segment_{self._next_segment_idx}"
                self._next_segment_idx += 1
                self._segments[seg_id] = []

            if len(self._segments[seg_id]) >= self.segment_entries:
                seg_id = f"segment_{self._next_segment_idx}"
                self._next_segment_idx += 1
                self._segments[seg_id] = []

            self._segments[seg_id].append(key)
            return seg_id

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry.is_stale(self.ttl_seconds):
                del self._data[key]
                return None
            entry.last_accessed = time.time()
            self._data.move_to_end(key)
            return entry.value

    def _evict_one_lru(self) -> None:
        if not self._data:
            return
        oldest_key, _ = next(iter(self._data.items()))
        del self._data[oldest_key]

    def record_app_write(self, bytes_written: int) -> None:
        pass

    def close(self) -> None:
        with self._lock:
            self._data.clear()
            self._segments.clear()
