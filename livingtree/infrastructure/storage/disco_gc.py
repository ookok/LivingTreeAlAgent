"""DisCoGC — Discard-and-Compaction combined Garbage Collection orchestrator.

Main engine implementing the ByteDance/Tsinghua FAST'26 DisCoGC algorithm
for LivingTree's storage infrastructure.

Usage:
    from livingtree.infrastructure.storage import DisCoGC, get_disco_gc
    from livingtree.infrastructure.storage.backends import SQLiteStorageBackend

    backend = SQLiteStorageBackend(db_path="cache.db")
    disco = DisCoGC(backend)
    disco.register()
    bytes_freed = disco.run_gc()

Integration with background tasks:
    disco.start_background(interval_seconds=300)
    # ... application runs ...
    disco.stop_background()

Or manual triggering:
    disco = get_disco_gc(backend)
    disco.run_gc()
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from loguru import logger

from .storage_config import GCConfig, GCPolicy, get_default_gc_config
from .storage_layer import StorageBackend
from .gc_metrics import GCMetrics
from .trace_collector import TraceCollector, TraceRegistry
from .discard_executor import DiscardExecutor
from .compaction_executor import CompactionExecutor
from .gc_scheduler import GCScheduler, GCUrgency


class DisCoGC:
    """Discard-and-Compaction combined Garbage Collection orchestrator.

    Orchestrates the full DisCoGC pipeline:
      1. Query storage stats from backend
      2. Collect I/O trace window
      3. Scheduler evaluates and decides discard vs compact
      4. Execute discard (zero-copy) and/or compaction (data movement)
      5. Record metrics and log results

    Thread-safe: uses internal lock for GC execution to prevent
    concurrent rounds from interfering.
    """

    def __init__(
        self,
        backend: StorageBackend,
        config: Optional[GCConfig] = None,
        trace_collector: Optional[TraceCollector] = None,
    ):
        self._backend = backend
        self._config = config or get_default_gc_config()
        self._metrics = GCMetrics(backend_name=backend.name)
        self._trace_collector = trace_collector or TraceCollector(backend.name)

        self._scheduler = GCScheduler(self._config, self._metrics, self._trace_collector)
        self._discard_executor = DiscardExecutor(backend, self._config, self._metrics, self._trace_collector)
        self._compaction_executor = CompactionExecutor(backend, self._config, self._metrics)

        self._gc_lock = threading.Lock()
        self._background_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_gc_result: Optional[dict] = None

    def register(self) -> None:
        """Register the backend with trace registry for I/O tracking."""
        self._backend.mark_registered()

    def run_gc(self) -> int:
        """Execute one complete GC round. Returns total bytes reclaimed.

        The pipeline:
          1. Get storage stats
          2. Scheduler evaluates
          3. Execute discard if advised
          4. Execute compaction if advised
          5. Log metrics summary
        """
        with self._gc_lock:
            stats = self._backend.get_stats()
            decision = self._scheduler.evaluate(stats)

            if not decision.should_gc:
                logger.trace("DisCoGC[%s]: skipping GC — %s", self._backend.name, decision.reason)
                return 0

            logger.info(
                "DisCoGC[%s]: GC round starting — %s",
                self._backend.name, decision.reason,
            )

            total_freed = 0
            start_time = time.time()

            if decision.should_discard:
                discard_freed = self._discard_executor.execute()
                total_freed += discard_freed

            if decision.should_compact:
                compact_freed = self._compaction_executor.execute(
                    force_full=(decision.urgency == GCUrgency.CRITICAL),
                )
                total_freed += compact_freed

            self._scheduler.mark_gc_complete()

            duration = time.time() - start_time

            self._last_gc_result = {
                "backend": self._backend.name,
                "total_freed_bytes": total_freed,
                "duration_seconds": duration,
                "decision": decision,
                "metrics_snapshot": self._metrics.snapshot(),
            }

            self._metrics.log_summary()

            logger.info(
                "DisCoGC[%s]: GC round complete — freed %.1f MB in %.2fs",
                self._backend.name,
                total_freed / (1024 * 1024),
                duration,
            )

            return total_freed

    def record_app_write(self, bytes_written: int) -> None:
        """Record application-level write for WAF tracking."""
        self._metrics.record_app_write(bytes_written)

    def get_metrics(self) -> GCMetrics:
        return self._metrics

    def get_stats(self) -> dict:
        with self._gc_lock:
            return {
                "backend": self._backend.name,
                "storage": self._backend.get_stats(),
                "metrics": self._metrics.snapshot(),
                "trace_window": self._trace_collector.get_window(
                    duration_seconds=self._config.trace_window_seconds,
                ),
                "last_gc_result": self._last_gc_result,
            }

    def start_background(self, interval_seconds: int = 300) -> None:
        """Start background GC thread with periodic execution."""
        if self._background_thread and self._background_thread.is_alive():
            logger.warning("DisCoGC[%s]: background thread already running", self._backend.name)
            return

        self._stop_event.clear()
        self._background_thread = threading.Thread(
            target=self._background_loop,
            args=(interval_seconds,),
            daemon=True,
            name=f"discogc-{self._backend.name}",
        )
        self._background_thread.start()
        logger.info(
            "DisCoGC[%s]: background GC started (interval=%ds)",
            self._backend.name, interval_seconds,
        )

    def stop_background(self) -> None:
        """Stop background GC thread."""
        if self._background_thread and self._background_thread.is_alive():
            self._stop_event.set()
            self._background_thread.join(timeout=10.0)
            logger.info("DisCoGC[%s]: background GC stopped", self._backend.name)

    def _background_loop(self, interval_seconds: int) -> None:
        while not self._stop_event.wait(timeout=interval_seconds):
            try:
                self.run_gc()
            except Exception as e:
                logger.error("DisCoGC[%s]: background GC error: %s", self._backend.name, e)

    def close(self) -> None:
        self.stop_background()
        self._backend.close()
        TraceRegistry.get_instance().unregister(self._backend.name)


# ── Global registry ──

_instances: dict[str, DisCoGC] = {}
_instances_lock = threading.Lock()


def get_disco_gc(
    backend: StorageBackend,
    config: Optional[GCConfig] = None,
) -> DisCoGC:
    """Get or create a DisCoGC instance for a given backend."""
    with _instances_lock:
        if backend.name not in _instances:
            instance = DisCoGC(backend, config)
            instance.register()
            _instances[backend.name] = instance
        return _instances[backend.name]
