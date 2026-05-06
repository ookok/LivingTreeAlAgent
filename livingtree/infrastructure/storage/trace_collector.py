"""I/O trace collection for DisCoGC decision engine.

Inspired by ByteDance's ByteDrive trace analysis approach:
  Record every read/write operation at the segment level, aggregate into
  sliding trace windows, and identify discard-friendly patterns
  (read-once segments, cold segments, write-hot-spots).

The trace collector is the data source for GCScheduler's
adaptive policy decisions.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from loguru import logger

from .gc_metrics import TraceWindow


@dataclass
class IOTrace:
    """A single I/O operation record at the segment level."""
    operation: str  # "read" or "write"
    backend_name: str
    segment_id: str
    bytes_count: int
    timestamp: float = field(default_factory=time.time)
    latency_us: int = 0


class TraceRegistry:
    """Registry of all trace collectors for multi-backend tracking."""

    _instance: Optional["TraceRegistry"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._collectors: Dict[str, "TraceCollector"] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "TraceRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, collector: "TraceCollector") -> None:
        with self._lock:
            self._collectors[collector.backend_name] = collector
            logger.debug("TraceRegistry: registered collector for '%s'", collector.backend_name)

    def unregister(self, backend_name: str) -> None:
        with self._lock:
            self._collectors.pop(backend_name, None)

    def get(self, backend_name: str) -> Optional["TraceCollector"]:
        with self._lock:
            return self._collectors.get(backend_name)

    def list_backends(self) -> List[str]:
        with self._lock:
            return list(self._collectors.keys())


class TraceCollector:
    """Per-backend I/O trace collector with sliding window aggregation.

    Usage:
        collector = TraceCollector("sqlite_cache")
        collector.record_read("seg_001", 4096)
        collector.record_write("seg_002", 8192)
        window = collector.get_window(duration_seconds=3600)
        print(f"discard-friendly ratio: {window.discard_friendly_ratio}")
    """

    def __init__(self, backend_name: str, max_traces: int = 100000):
        self.backend_name = backend_name
        self.max_traces = max_traces
        self._traces: List[IOTrace] = []
        self._lock = threading.Lock()

        self._segment_read_counts: Dict[str, int] = defaultdict(int)
        self._segment_write_counts: Dict[str, int] = defaultdict(int)
        self._segment_last_read: Dict[str, float] = {}
        self._segment_last_write: Dict[str, float] = {}

        self.total_reads: int = 0
        self.total_writes: int = 0
        self.total_read_bytes: int = 0
        self.total_write_bytes: int = 0

        TraceRegistry.get_instance().register(self)

    def record_read(self, segment_id: str, bytes_count: int, latency_us: int = 0) -> None:
        trace = IOTrace(
            operation="read",
            backend_name=self.backend_name,
            segment_id=segment_id,
            bytes_count=bytes_count,
            latency_us=latency_us,
        )
        with self._lock:
            self._traces.append(trace)
            self._trim()
            self._segment_read_counts[segment_id] += 1
            self._segment_last_read[segment_id] = trace.timestamp
            self.total_reads += 1
            self.total_read_bytes += bytes_count

    def record_write(self, segment_id: str, bytes_count: int, latency_us: int = 0) -> None:
        trace = IOTrace(
            operation="write",
            backend_name=self.backend_name,
            segment_id=segment_id,
            bytes_count=bytes_count,
            latency_us=latency_us,
        )
        with self._lock:
            self._traces.append(trace)
            self._trim()
            self._segment_write_counts[segment_id] += 1
            self._segment_last_write[segment_id] = trace.timestamp
            self.total_writes += 1
            self.total_write_bytes += bytes_count

    def get_window(self, duration_seconds: int = 3600) -> TraceWindow:
        """Aggregate traces over the last `duration_seconds` into a window."""
        cutoff = time.time() - duration_seconds
        with self._lock:
            window_traces = [t for t in self._traces if t.timestamp >= cutoff]

        if not window_traces:
            return TraceWindow(
                start_time=cutoff,
                end_time=time.time(),
            )

        read_segments: Set[str] = set()
        write_segments: Set[str] = set()
        segment_read_counts: Dict[str, int] = defaultdict(int)
        total_reads = 0
        total_writes = 0
        read_bytes = 0
        write_bytes = 0

        for t in window_traces:
            if t.operation == "read":
                read_segments.add(t.segment_id)
                segment_read_counts[t.segment_id] += 1
                total_reads += 1
                read_bytes += t.bytes_count
            else:
                write_segments.add(t.segment_id)
                total_writes += 1
                write_bytes += t.bytes_count

        read_once_count = sum(
            1 for sid, cnt in segment_read_counts.items()
            if cnt == 1
        )
        hot_count = sum(
            1 for sid, cnt in segment_read_counts.items()
            if cnt >= 10
        )

        return TraceWindow(
            start_time=window_traces[0].timestamp,
            end_time=window_traces[-1].timestamp,
            total_reads=total_reads,
            total_writes=total_writes,
            read_bytes=read_bytes,
            write_bytes=write_bytes,
            unique_read_segments=len(read_segments),
            unique_write_segments=len(write_segments),
            read_once_segments=read_once_count,
            hot_segments=hot_count,
        )

    def get_cold_segments(self, duration_seconds: int = 3600) -> List[str]:
        """Return segment IDs not read within the window (discard candidates)."""
        cutoff = time.time() - duration_seconds
        with self._lock:
            return [
                sid for sid, last_ts in self._segment_last_read.items()
                if last_ts < cutoff
            ]

    def _trim(self) -> None:
        if len(self._traces) > self.max_traces:
            self._traces = self._traces[-self.max_traces // 2:]

    def reset(self) -> None:
        with self._lock:
            self._traces.clear()
            self._segment_read_counts.clear()
            self._segment_write_counts.clear()
            self._segment_last_read.clear()
            self._segment_last_write.clear()
            self.total_reads = 0
            self.total_writes = 0
            self.total_read_bytes = 0
            self.total_write_bytes = 0
