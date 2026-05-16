"""SystemMonitor — resource-aware task scheduling.

Monitors CPU, memory, and disk usage. All autonomous tasks
(AutonomousLearner, CronScheduler, ModelRegistry refresh, etc.)
check resources before executing. If system is under pressure,
tasks are deferred to the next cycle.

Thresholds configurable via LIVINGTREE_RESOURCE_* env vars.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from loguru import logger

try:
    import psutil
except ImportError:
    psutil = None


@dataclass
class ResourceSnapshot:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    memory_available_mb: float = 0.0
    timestamp: float = 0.0

    @property
    def under_pressure(self) -> bool:
        return (
            self.cpu_percent > CPU_HIGH_THRESHOLD
            or self.memory_percent > MEM_HIGH_THRESHOLD
            or self.memory_available_mb < MEM_LOW_THRESHOLD_MB
        )

    @property
    def critical(self) -> bool:
        return (
            self.cpu_percent > 95
            or self.memory_percent > 95
            or self.memory_available_mb < 100
        )

    def summary(self) -> str:
        return (
            f"CPU:{self.cpu_percent:.0f}% "
            f"MEM:{self.memory_percent:.0f}% "
            f"Avail:{self.memory_available_mb:.0f}MB"
        )


# Thresholds configurable via env vars
CPU_HIGH_THRESHOLD = float(os.environ.get("LIVINGTREE_CPU_HIGH", "80"))
MEM_HIGH_THRESHOLD = float(os.environ.get("LIVINGTREE_MEM_HIGH", "85"))
MEM_LOW_THRESHOLD_MB = float(os.environ.get("LIVINGTREE_MEM_LOW_MB", "512"))
IDLE_CPU_THRESHOLD = float(os.environ.get("LIVINGTREE_CPU_IDLE", "30"))


class SystemMonitor:
    """Monitors system resources and gates autonomous tasks."""

    _instance: SystemMonitor | None = None

    @classmethod
    def instance(cls) -> SystemMonitor:
        if cls._instance is None:
            cls._instance = SystemMonitor()
        return cls._instance

    def __init__(self):
        self._last_snapshot: ResourceSnapshot | None = None
        self._deferred_count: int = 0
        self._consecutive_skips: int = 0
        self._cache_ttl = 5.0  # seconds: reuse snapshot within this window

    def snapshot(self) -> ResourceSnapshot:
        """Get current resource usage snapshot."""
        now = time.time()
        if self._last_snapshot and (now - self._last_snapshot.timestamp) < self._cache_ttl:
            return self._last_snapshot

        snap = ResourceSnapshot(timestamp=now)

        if psutil is not None:
            try:
                snap.cpu_percent = psutil.cpu_percent(interval=0.5)
                mem = psutil.virtual_memory()
                snap.memory_percent = mem.percent
                snap.memory_available_mb = mem.available / (1024 * 1024)
                disk = psutil.disk_usage(os.getcwd())
                snap.disk_percent = disk.percent
            except Exception:
                pass

        self._last_snapshot = snap
        return snap

    def can_run_task(self, task_name: str = "", heavy: bool = False) -> bool:
        """Check if a task can run without stressing the system.

        Args:
            task_name: Human-readable task name for logging.
            heavy: If True, requires lower CPU/memory (idle thresholds).
        """
        snap = self.snapshot()

        if snap.critical:
            self._deferred_count += 1
            self._consecutive_skips += 1
            logger.debug(f"⏸ {task_name} deferred (critical: {snap.summary()})")
            return False

        cpu_limit = IDLE_CPU_THRESHOLD if heavy else CPU_HIGH_THRESHOLD
        if snap.cpu_percent > cpu_limit:
            self._deferred_count += 1
            self._consecutive_skips += 1
            logger.debug(f"⏸ {task_name} deferred (CPU:{snap.cpu_percent:.0f}% > {cpu_limit:.0f}%)")
            return False

        if snap.memory_percent > MEM_HIGH_THRESHOLD:
            self._deferred_count += 1
            self._consecutive_skips += 1
            logger.debug(f"⏸ {task_name} deferred (MEM:{snap.memory_percent:.0f}% > {MEM_HIGH_THRESHOLD:.0f}%)")
            return False

        if snap.memory_available_mb < MEM_LOW_THRESHOLD_MB:
            self._deferred_count += 1
            self._consecutive_skips += 1
            logger.debug(f"⏸ {task_name} deferred (Avail:{snap.memory_available_mb:.0f}MB < {MEM_LOW_THRESHOLD_MB}MB)")
            return False

        self._consecutive_skips = 0
        return True

    def get_stats(self) -> dict:
        snap = self.snapshot()
        return {
            "snapshot": snap.summary(),
            "deferred": self._deferred_count,
            "consecutive_skips": self._consecutive_skips,
            "thresholds": {
                "cpu_high": CPU_HIGH_THRESHOLD,
                "mem_high": MEM_HIGH_THRESHOLD,
                "mem_low_mb": MEM_LOW_THRESHOLD_MB,
                "cpu_idle": IDLE_CPU_THRESHOLD,
            },
        }


def get_monitor() -> SystemMonitor:
    return SystemMonitor.instance()
