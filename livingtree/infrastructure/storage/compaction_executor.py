"""Compaction executor — traditional data reorganization for fragmented storage.

The traditional GC path in DisCoGC: move live data from fragmented
segments into fresh segments, then free the old segments.

Used when discard alone cannot reclaim enough space, typically
when the stale ratio is below the discard threshold but fragmentation
is high enough to warrant compaction.

Compaction is more expensive than discard (write amplification),
so it's only invoked when necessary.
"""

from __future__ import annotations

import time
from typing import List, Optional

from loguru import logger

from .storage_config import CompactionStrategy, GCConfig
from .storage_layer import StorageBackend, StorageSegment
from .gc_metrics import GCMetrics


class CompactionExecutor:
    """Executes compaction (data-movement reclamation) on a storage backend.

    Selects fragmented segments (high stale but not 100% stale),
    moves their live data to fresh segments, then frees the originals.
    """

    def __init__(
        self,
        backend: StorageBackend,
        config: GCConfig,
        metrics: GCMetrics,
    ):
        self._backend = backend
        self._config = config
        self._metrics = metrics

    def execute(self, force_full: bool = False) -> int:
        """Run a compaction round. Returns total bytes reclaimed.

        Args:
            force_full: if True, use TRADITIONAL strategy regardless of config.
        """
        start_time = time.time()
        segments = self._backend.list_segments()

        candidates = self._select_compaction_candidates(segments, force_full)

        if not candidates:
            logger.debug(
                "CompactionExecutor[%s]: no compaction candidates",
                self._backend.name,
            )
            return 0

        segment_ids = [s.segment_id for s in candidates]
        estimated_bytes = sum(s.stale_bytes for s in candidates)
        estimated_live = sum(s.live_bytes for s in candidates)

        logger.info(
            "CompactionExecutor[%s]: compacting %d segments "
            "(~%.1f MB stale, ~%.1f MB live to move)",
            self._backend.name, len(segment_ids),
            estimated_bytes / (1024 * 1024),
            estimated_live / (1024 * 1024),
        )

        try:
            bytes_freed, bytes_written = self._backend.compact_segments(segment_ids)
        except Exception as e:
            logger.error("CompactionExecutor[%s]: compaction failed: %s", self._backend.name, e)
            self._metrics.record_compaction_error()
            return 0

        duration = time.time() - start_time
        self._metrics.record_compaction(bytes_freed, bytes_written, duration)

        write_amp = bytes_written / max(bytes_freed, 1)
        logger.info(
            "CompactionExecutor[%s]: freed %.1f MB, wrote %.1f MB (WAF %.2f) in %.2fs",
            self._backend.name,
            bytes_freed / (1024 * 1024),
            bytes_written / (1024 * 1024),
            write_amp,
            duration,
        )
        return bytes_freed

    def _select_compaction_candidates(
        self, segments: List[StorageSegment], force_full: bool = False
    ) -> List[StorageSegment]:
        strategy = self._config.compaction_strategy
        if force_full:
            strategy = CompactionStrategy.TRADITIONAL

        if strategy == CompactionStrategy.TRADITIONAL:
            return self._select_traditional(segments)
        elif strategy == CompactionStrategy.INCREMENTAL:
            return self._select_incremental(segments)
        elif strategy == CompactionStrategy.ADAPTIVE:
            return self._select_adaptive(segments)
        return []

    def _select_traditional(self, segments: List[StorageSegment]) -> List[StorageSegment]:
        """Select all segments with above-threshold stale ratio (not fully stale)."""
        candidates = [
            s for s in segments
            if 0 < s.stale_ratio < 1.0 and s.stale_ratio >= self._config.stale_threshold
        ]
        candidates.sort(key=lambda s: s.stale_ratio, reverse=True)
        return candidates

    def _select_incremental(self, segments: List[StorageSegment]) -> List[StorageSegment]:
        """Select only the most fragmented segments (top N by stale ratio)."""
        candidates = self._select_traditional(segments)
        return candidates[:max(1, len(candidates) // 3)]

    def _select_adaptive(self, segments: List[StorageSegment]) -> List[StorageSegment]:
        """Incremental under normal pressure, traditional when critical."""
        stats = self._backend.get_stats()
        if stats.usage_ratio >= self._config.space_critical_threshold:
            return self._select_traditional(segments)
        return self._select_incremental(segments)
