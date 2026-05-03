"""Metrics collection and export for the digital life form."""
from __future__ import annotations

import time
import threading
from typing import Any

from loguru import logger


class MetricGauge:
    """A metric that holds a single numerical value that can go up and down."""

    def __init__(self, name: str, description: str = "", labels: dict[str, str] | None = None):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self._value: float = 0.0
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def get(self) -> float:
        with self._lock:
            return self._value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value -= amount


class MetricCounter:
    """A cumulative metric that only ever increases."""

    def __init__(self, name: str, description: str = "", labels: dict[str, str] | None = None):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self._value: int = 0
        self._lock = threading.Lock()

    def inc(self, amount: int = 1) -> None:
        with self._lock:
            self._value += amount

    def get(self) -> int:
        with self._lock:
            return self._value

    def reset(self) -> None:
        with self._lock:
            self._value = 0


class MetricHistogram:
    """A metric that records observations in buckets."""

    def __init__(self, name: str, description: str = "", buckets: list[float] | None = None,
                 labels: dict[str, str] | None = None):
        self.name = name
        self.description = description
        self.buckets = buckets or [0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 60.0, 300.0]
        self.labels = labels or {}
        self._observations: list[float] = []
        self._lock = threading.Lock()
        self._max_observations = 10000

    def observe(self, value: float) -> None:
        with self._lock:
            self._observations.append(value)
            if len(self._observations) > self._max_observations:
                self._observations = self._observations[-self._max_observations:]

    def get_statistics(self) -> dict[str, Any]:
        with self._lock:
            if not self._observations:
                return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
            obs = list(self._observations)
            return {
                "count": len(obs),
                "sum": sum(obs),
                "avg": sum(obs) / len(obs),
                "min": min(obs),
                "max": max(obs),
            }


class MetricsCollector:
    """Central metrics registry for the life form."""

    def __init__(self):
        self._gauges: dict[str, MetricGauge] = {}
        self._counters: dict[str, MetricCounter] = {}
        self._histograms: dict[str, MetricHistogram] = {}

        # Built-in metrics
        self.life_cycles: MetricCounter = self.register_counter(
            "livingtree_life_cycles_total", "Total life cycles executed"
        )
        self.cell_count: MetricGauge = self.register_gauge(
            "livingtree_cells_active", "Number of active AI cells"
        )
        self.task_duration: MetricHistogram = self.register_histogram(
            "livingtree_task_duration_seconds", "Task execution duration"
        )
        self.knowledge_docs: MetricGauge = self.register_gauge(
            "livingtree_knowledge_documents", "Number of documents in knowledge base"
        )
        self.tool_executions: MetricCounter = self.register_counter(
            "livingtree_tool_executions_total", "Total tool invocations"
        )
        self.errors_total: MetricCounter = self.register_counter(
            "livingtree_errors_total", "Total errors encountered"
        )
        self.peers_connected: MetricGauge = self.register_gauge(
            "livingtree_peers_connected", "Number of connected P2P peers"
        )

    def register_gauge(self, name: str, description: str = "",
                       labels: dict[str, str] | None = None) -> MetricGauge:
        g = MetricGauge(name, description, labels)
        self._gauges[name] = g
        return g

    def register_counter(self, name: str, description: str = "",
                         labels: dict[str, str] | None = None) -> MetricCounter:
        c = MetricCounter(name, description, labels)
        self._counters[name] = c
        return c

    def register_histogram(self, name: str, description: str = "",
                           buckets: list[float] | None = None,
                           labels: dict[str, str] | None = None) -> MetricHistogram:
        h = MetricHistogram(name, description, buckets, labels)
        self._histograms[name] = h
        return h

    def get_snapshot(self) -> dict[str, Any]:
        """Get a snapshot of all metrics for export."""
        snapshot = {}
        for name, gauge in self._gauges.items():
            snapshot[name] = {"type": "gauge", "value": gauge.get()}
        for name, counter in self._counters.items():
            snapshot[name] = {"type": "counter", "value": counter.get()}
        for name, histogram in self._histograms.items():
            snapshot[name] = {"type": "histogram", **histogram.get_statistics()}
        return snapshot

    def print_summary(self) -> None:
        """Print a human-readable metrics summary."""
        snapshot = self.get_snapshot()
        logger.info("=" * 50)
        logger.info("LivingTree Metrics Summary")
        logger.info("=" * 50)
        for name, data in sorted(snapshot.items()):
            logger.info(f"  {name}: {data}")
        logger.info("=" * 50)
