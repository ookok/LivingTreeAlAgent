"""GC metrics — write amplification, space reclamation, and operational counters.

Tracks the key TCO metrics described in the DisCoGC paper:
  - Write amplification factor (WAF): total bytes written / application bytes written
  - Space reclaimed: bytes freed via discard + compaction
  - Discard efficiency: stale bytes reclaimed / total bytes freed
  - Trace window stats: I/O patterns over sliding time windows
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


@dataclass
class StorageStats:
    """Snapshot of a storage backend's current state."""
    backend_name: str = ""
    total_bytes: int = 0
    used_bytes: int = 0
    stale_bytes: int = 0
    live_bytes: int = 0
    segment_count: int = 0
    stale_segment_count: int = 0
    fragmentation_ratio: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def usage_ratio(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return self.used_bytes / self.total_bytes

    @property
    def stale_ratio(self) -> float:
        if self.used_bytes == 0:
            return 0.0
        return self.stale_bytes / max(self.used_bytes, 1)


@dataclass
class TraceWindow:
    """Sliding window of I/O trace statistics.

    Used by GCScheduler to decide between discard and compaction.
    """
    start_time: float = 0.0
    end_time: float = 0.0
    total_reads: int = 0
    total_writes: int = 0
    read_bytes: int = 0
    write_bytes: int = 0
    unique_read_segments: int = 0
    unique_write_segments: int = 0
    read_once_segments: int = 0   # segments read exactly once → good discard candidates
    hot_segments: int = 0         # segments with high read count → keep/compact

    def __post_init__(self):
        if self.end_time == 0.0:
            self.end_time = time.time()

    @property
    def read_write_ratio(self) -> float:
        if self.write_bytes == 0:
            return float('inf')
        return self.read_bytes / self.write_bytes

    @property
    def discard_friendly_ratio(self) -> float:
        """Fraction of segments that are discard-friendly (read once or never)."""
        total = self.unique_read_segments
        if total == 0:
            return 0.0
        return self.read_once_segments / total


class GCMetrics:
    """Thread-safe collector for DisCoGC operational metrics.

    Maps to the production cluster metrics described in the paper
    for TCO reduction tracking.
    """

    def __init__(self, backend_name: str = ""):
        self.backend_name = backend_name
        self._lock = threading.Lock()

        self.discard_rounds: int = 0
        self.compaction_rounds: int = 0
        self.hybrid_rounds: int = 0

        self.bytes_discarded: int = 0
        self.bytes_compacted: int = 0
        self.bytes_written_during_gc: int = 0
        self.app_bytes_written: int = 0

        self.last_gc_timestamp: float = 0.0
        self.total_gc_duration_seconds: float = 0.0

        self.discard_error_count: int = 0
        self.compaction_error_count: int = 0

    @property
    def total_bytes_reclaimed(self) -> int:
        return self.bytes_discarded + self.bytes_compacted

    @property
    def write_amplification(self) -> float:
        if self.app_bytes_written == 0:
            return 1.0
        return (self.app_bytes_written + self.bytes_written_during_gc) / self.app_bytes_written

    @property
    def discard_efficiency(self) -> float:
        """Fraction of total reclamation achieved via zero-copy discard."""
        total = self.total_bytes_reclaimed
        if total == 0:
            return 0.0
        return self.bytes_discarded / total

    @property
    def total_gc_rounds(self) -> int:
        return self.discard_rounds + self.compaction_rounds + self.hybrid_rounds

    def record_discard(self, bytes_freed: int, duration_seconds: float) -> None:
        with self._lock:
            self.discard_rounds += 1
            self.bytes_discarded += bytes_freed
            self.total_gc_duration_seconds += duration_seconds
            self.last_gc_timestamp = time.time()

    def record_compaction(self, bytes_freed: int, bytes_written: int, duration_seconds: float) -> None:
        with self._lock:
            self.compaction_rounds += 1
            self.bytes_compacted += bytes_freed
            self.bytes_written_during_gc += bytes_written
            self.total_gc_duration_seconds += duration_seconds
            self.last_gc_timestamp = time.time()

    def record_hybrid(self, bytes_discarded: int, bytes_compacted: int,
                      bytes_written: int, duration_seconds: float) -> None:
        with self._lock:
            self.hybrid_rounds += 1
            self.bytes_discarded += bytes_discarded
            self.bytes_compacted += bytes_compacted
            self.bytes_written_during_gc += bytes_written
            self.total_gc_duration_seconds += duration_seconds
            self.last_gc_timestamp = time.time()

    def record_app_write(self, bytes_written: int) -> None:
        with self._lock:
            self.app_bytes_written += bytes_written

    def record_discard_error(self) -> None:
        with self._lock:
            self.discard_error_count += 1

    def record_compaction_error(self) -> None:
        with self._lock:
            self.compaction_error_count += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "backend": self.backend_name,
                "discard_rounds": self.discard_rounds,
                "compaction_rounds": self.compaction_rounds,
                "hybrid_rounds": self.hybrid_rounds,
                "bytes_discarded": self.bytes_discarded,
                "bytes_compacted": self.bytes_compacted,
                "total_reclaimed": self.total_bytes_reclaimed,
                "bytes_written_gc": self.bytes_written_during_gc,
                "app_bytes_written": self.app_bytes_written,
                "write_amplification": round(self.write_amplification, 3),
                "discard_efficiency": round(self.discard_efficiency, 3),
                "total_gc_duration_s": round(self.total_gc_duration_seconds, 2),
                "discard_errors": self.discard_error_count,
                "compaction_errors": self.compaction_error_count,
            }

    def log_summary(self) -> None:
        s = self.snapshot()
        logger.info(
            "DisCoGC[%s] | rounds: d=%d c=%d h=%d | reclaimed: %.1fMB | WAF: %.2f | "
            "discard_eff: %.1f%% | gc_time: %.1fs",
            s["backend"],
            s["discard_rounds"], s["compaction_rounds"], s["hybrid_rounds"],
            s["total_reclaimed"] / (1024 * 1024),
            s["write_amplification"],
            s["discard_efficiency"] * 100,
            s["total_gc_duration_s"],
        )
