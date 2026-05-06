"""Storage backend abstraction — pluggable log-structured storage for LivingTree.

Defines the StorageBackend ABC and StorageSegment model that all
DisCoGC-compatible storage backends must implement.

Design rationale (from DisCoGC paper):
  Each backend exposes its storage as segments. The GC engine queries segment
  stats (live/stale bytes, last access timestamp) to decide discard vs compact.
  Discard operates on whole segments (no live data movement); compaction
  moves live data from fragmented segments into fresh ones.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from loguru import logger

from .gc_metrics import StorageStats


@dataclass
class StorageSegment:
    """A logical segment of a log-structured storage backend.

    Each segment tracks its own live/stale bytes and access patterns.
    All-zero-size segments represent freed (discarded) space.

    Maps to "extent" or "segment" in log-structured file system terminology.
    """
    segment_id: str
    total_bytes: int = 0
    live_bytes: int = 0
    stale_bytes: int = 0
    created_at: float = field(default_factory=time.time)
    last_read_at: float = 0.0
    last_write_at: float = 0.0
    read_count: int = 0
    write_count: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def is_discardable(self) -> bool:
        """A segment is discardable if it contains only stale data."""
        return self.stale_bytes == self.total_bytes and self.total_bytes > 0

    @property
    def is_empty(self) -> bool:
        return self.total_bytes == 0

    @property
    def stale_ratio(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return self.stale_bytes / self.total_bytes

    @property
    def live_ratio(self) -> float:
        return 1.0 - self.stale_ratio

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    def mark_read(self) -> None:
        self.last_read_at = time.time()
        self.read_count += 1

    def mark_write(self, live_bytes: int, stale_bytes: int) -> None:
        self.last_write_at = time.time()
        self.write_count += 1
        self.live_bytes = live_bytes
        self.stale_bytes = stale_bytes
        self.total_bytes = live_bytes + stale_bytes


class StorageBackend(ABC):
    """Abstract base for all DisCoGC-compatible storage backends.

    Subclasses implement:
      - get_stats(): current storage state snapshot
      - list_segments(): enumerate all segments with live/stale info
      - discard_segments(): zero-copy reclamation (DisCoGC discard path)
      - compact_segments(): move live data to new segments (DisCoGC compaction path)

    Lifecycle:
      1. register(): backends register with TraceRegistry for I/O tracing
      2. DisCoGC queries stats → decides → calls discard/compact
      3. Backend notifies DisCoGC of app writes via record_app_write()
    """

    def __init__(self, name: str = ""):
        self._name = name or self.__class__.__name__
        self._registered = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def registered(self) -> bool:
        return self._registered

    def mark_registered(self) -> None:
        self._registered = True

    @abstractmethod
    def get_stats(self) -> StorageStats:
        """Return a full snapshot of this backend's storage state."""

    @abstractmethod
    def list_segments(self) -> List[StorageSegment]:
        """Enumerate all storage segments with live/stale metadata."""

    @abstractmethod
    def discard_segments(self, segment_ids: List[str]) -> int:
        """Reclaim space by discarding fully-stale segments.

        Returns total bytes freed. Must NOT move any live data.
        This is the core of DisCoGC's zero-copy reclamation path.
        """

    @abstractmethod
    def compact_segments(self, segment_ids: List[str]) -> tuple[int, int]:
        """Compact fragmented segments by moving live data to new segments.

        Returns (bytes_freed, bytes_written_during_gc).
        This is the traditional compaction path — only used when discard
        cannot reclaim enough space.
        """

    def record_app_write(self, bytes_written: int) -> None:
        """Notify that the application wrote bytes (for WAF tracking)."""

    def close(self) -> None:
        """Clean up backend resources."""
