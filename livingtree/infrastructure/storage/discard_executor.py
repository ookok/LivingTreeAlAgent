"""Discard executor — zero-copy stale data reclamation.

Core DisCoGC concept: reclaim space occupied by stale data WITHOUT
moving valid data. This is the key innovation over traditional compaction.

The executor:
  1. Queries storage backend segments
  2. Applies discard strategy (trace-based, age-based, size-based, hybrid)
  3. Submits discard commands for fully-stale segments
  4. Records metrics (bytes freed, duration, errors)

A segment is discardable when ALL data in it is stale (0% live).
"""

from __future__ import annotations

import time
from typing import List, Optional

from loguru import logger

from .storage_config import DiscardStrategy, GCConfig
from .storage_layer import StorageBackend, StorageSegment
from .gc_metrics import GCMetrics
from .trace_collector import TraceCollector


class DiscardExecutor:
    """Executes discard (zero-copy reclamation) on a storage backend.

    The executor selects fully-stale segments and reclaims them without
    any data movement. This is the primary TCO reduction path in DisCoGC.
    """

    def __init__(
        self,
        backend: StorageBackend,
        config: GCConfig,
        metrics: GCMetrics,
        trace_collector: Optional[TraceCollector] = None,
    ):
        self._backend = backend
        self._config = config
        self._metrics = metrics
        self._trace_collector = trace_collector

    def execute(self) -> int:
        """Run a discard round. Returns total bytes reclaimed."""
        start_time = time.time()
        segments = self._backend.list_segments()

        candidates = self._select_discard_candidates(segments)
        discountable = [s for s in candidates if s.is_discardable]

        if not discountable:
            logger.debug(
                "DiscardExecutor[%s]: no fully-stale segments found (%d candidates)",
                self._backend.name, len(candidates),
            )
            return 0

        segment_ids = [s.segment_id for s in discountable]
        estimated_bytes = sum(s.stale_bytes for s in discountable)

        logger.info(
            "DiscardExecutor[%s]: discarding %d segments (~%.1f MB)",
            self._backend.name, len(segment_ids), estimated_bytes / (1024 * 1024),
        )

        try:
            bytes_freed = self._backend.discard_segments(segment_ids)
        except Exception as e:
            logger.error("DiscardExecutor[%s]: discard failed: %s", self._backend.name, e)
            self._metrics.record_discard_error()
            return 0

        duration = time.time() - start_time
        self._metrics.record_discard(bytes_freed, duration)

        logger.info(
            "DiscardExecutor[%s]: freed %.1f MB in %.2fs (%.1f MB/s)",
            self._backend.name,
            bytes_freed / (1024 * 1024),
            duration,
            (bytes_freed / (1024 * 1024)) / max(duration, 0.001),
        )
        return bytes_freed

    def _select_discard_candidates(self, segments: List[StorageSegment]) -> List[StorageSegment]:
        """Select segments for discard based on configured strategy."""
        strategy = self._config.discard_strategy

        if strategy == DiscardStrategy.AGE_BASED:
            return self._select_by_age(segments)
        elif strategy == DiscardStrategy.SIZE_BASED:
            return self._select_by_size(segments)
        elif strategy == DiscardStrategy.TRACE_BASED:
            return self._select_by_trace(segments)
        elif strategy == DiscardStrategy.HYBRID:
            return self._select_hybrid(segments)
        return []

    def _select_by_age(self, segments: List[StorageSegment]) -> List[StorageSegment]:
        """Prefer oldest segments with high stale ratio."""
        candidates = [s for s in segments if s.stale_ratio >= self._config.stale_threshold]
        candidates.sort(key=lambda s: s.created_at)
        return candidates

    def _select_by_size(self, segments: List[StorageSegment]) -> List[StorageSegment]:
        """Prefer largest segments with high stale ratio."""
        candidates = [s for s in segments if s.stale_ratio >= self._config.stale_threshold]
        candidates.sort(key=lambda s: s.stale_bytes, reverse=True)
        return candidates

    def _select_by_trace(self, segments: List[StorageSegment]) -> List[StorageSegment]:
        """Use trace data to identify cold/read-once segments."""
        if self._trace_collector is None:
            return self._select_by_age(segments)

        cold_ids = set(self._trace_collector.get_cold_segments(
            duration_seconds=self._config.trace_window_seconds,
        ))

        candidates = [
            s for s in segments
            if s.segment_id in cold_ids and s.stale_ratio >= self._config.stale_threshold
        ]
        candidates.sort(key=lambda s: s.stale_bytes, reverse=True)
        return candidates

    def _select_hybrid(self, segments: List[StorageSegment]) -> List[StorageSegment]:
        """Score segments by weighted combination of age, size, and coldness."""
        if not segments:
            return []

        max_age = max(s.age_seconds for s in segments) or 1
        max_size = max(s.stale_bytes for s in segments) or 1

        cold_ids: set = set()
        if self._trace_collector:
            cold_ids = set(self._trace_collector.get_cold_segments(
                duration_seconds=self._config.trace_window_seconds,
            ))

        scored = []
        for s in segments:
            if s.stale_ratio < self._config.stale_threshold:
                continue
            age_score = s.age_seconds / max_age
            size_score = s.stale_bytes / max_size
            cold_score = 1.0 if s.segment_id in cold_ids else 0.3
            score = age_score * 0.3 + size_score * 0.4 + cold_score * 0.3
            scored.append((score, s))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored]
