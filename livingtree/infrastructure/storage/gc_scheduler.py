"""GC Scheduler — adaptive decision engine for discard vs compaction.

The scheduler analyzes storage stats + I/O trace windows to decide:
  - Should GC run at all?
  - If yes, should we use discard, compaction, or both?
  - What's the urgency level?

Decision logic (from DisCoGC paper insights):
  Low disk pressure  → discard-only (zero-cost reclamation)
  Moderate pressure  → hybrid (discard first, compact remainder)
  High fragmentation  → compaction (reorganize live data)
  Critical pressure  → aggressive compaction + discard
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from loguru import logger

from .storage_config import GCConfig, GCPolicy
from .gc_metrics import GCMetrics, StorageStats, TraceWindow
from .trace_collector import TraceCollector


class GCUrgency(str, Enum):
    """How urgently GC is needed."""
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class GCDecision:
    """The scheduler's decision for a GC round.

    urgency: whether GC is needed and how urgently
    policy: which GC policy to apply
    reason: human-readable explanation of the decision
    timestamp: when the decision was made
    """
    urgency: GCUrgency = GCUrgency.NONE
    policy: GCPolicy = GCPolicy.ADAPTIVE
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    @property
    def should_gc(self) -> bool:
        return self.urgency != GCUrgency.NONE

    @property
    def should_discard(self) -> bool:
        return self.policy in (GCPolicy.DISCARD_ONLY, GCPolicy.HYBRID, GCPolicy.ADAPTIVE)

    @property
    def should_compact(self) -> bool:
        return self.policy in (GCPolicy.COMPACT_ONLY, GCPolicy.HYBRID, GCPolicy.ADAPTIVE)


class GCScheduler:
    """Adaptive GC decision engine based on DisCoGC trace analysis.

    Evaluates storage state against configured thresholds and trace
    patterns to produce GCDecision instances consumed by DisCoGC.
    """

    def __init__(
        self,
        config: GCConfig,
        metrics: GCMetrics,
        trace_collector: Optional[TraceCollector] = None,
    ):
        self._config = config
        self._metrics = metrics
        self._trace_collector = trace_collector
        self._last_gc_time: float = 0.0

    def evaluate(self, stats: StorageStats) -> GCDecision:
        """Evaluate storage state and return a GC decision."""
        if not self._can_run():
            return GCDecision(
                urgency=GCUrgency.NONE,
                policy=GCPolicy.ADAPTIVE,
                reason=f"Cooldown active ({self._config.cooldown_seconds}s)",
            )

        urgency = self._assess_urgency(stats)

        if urgency == GCUrgency.NONE:
            return GCDecision(
                urgency=GCUrgency.NONE,
                policy=GCPolicy.ADAPTIVE,
                reason="Storage healthy, no GC needed",
            )

        if self._config.policy == GCPolicy.ADAPTIVE:
            policy = self._decide_adaptive(stats, urgency)
        else:
            policy = self._config.policy

        reason = self._build_reason(stats, urgency, policy)

        logger.debug(
            "GCScheduler: urgency=%s policy=%s usage=%.1f%% stale=%.1f%%",
            urgency.value, policy.value,
            stats.usage_ratio * 100, stats.stale_ratio * 100,
        )

        return GCDecision(urgency=urgency, policy=policy, reason=reason)

    def mark_gc_complete(self) -> None:
        self._last_gc_time = time.time()

    def _can_run(self) -> bool:
        if self._last_gc_time == 0.0:
            return True
        return (time.time() - self._last_gc_time) >= self._config.cooldown_seconds

    def _assess_urgency(self, stats: StorageStats) -> GCUrgency:
        usage = stats.usage_ratio
        stale = stats.stale_ratio

        if usage >= self._config.space_critical_threshold:
            return GCUrgency.CRITICAL
        if usage >= self._config.space_warning_threshold:
            if stale >= self._config.stale_threshold:
                return GCUrgency.HIGH
            return GCUrgency.MODERATE
        if stale >= self._config.stale_threshold:
            return GCUrgency.LOW
        return GCUrgency.NONE

    def _decide_adaptive(self, stats: StorageStats, urgency: GCUrgency) -> GCPolicy:
        """Adaptive policy: trace-based selection between discard and compaction."""
        window = self._get_trace_window()

        if urgency == GCUrgency.CRITICAL:
            return GCPolicy.HYBRID

        if urgency == GCUrgency.HIGH:
            if window and window.discard_friendly_ratio >= 0.5:
                return GCPolicy.HYBRID
            return GCPolicy.COMPACT_ONLY

        if urgency in (GCUrgency.MODERATE, GCUrgency.LOW):
            if window and window.discard_friendly_ratio >= 0.3:
                return GCPolicy.DISCARD_ONLY
            if self._metrics.write_amplification < self._config.max_write_amplification:
                return GCPolicy.COMPACT_ONLY
            return GCPolicy.DISCARD_ONLY

        return GCPolicy.ADAPTIVE

    def _build_reason(self, stats: StorageStats, urgency: GCUrgency, policy: GCPolicy) -> str:
        parts = [
            f"urgency={urgency.value}",
            f"policy={policy.value}",
            f"usage={stats.usage_ratio:.1%}",
            f"stale={stats.stale_ratio:.1%}",
            f"frag={stats.fragmentation_ratio:.1%}",
        ]
        if self._trace_collector:
            window = self._get_trace_window()
            if window:
                parts.append(f"discard_friendly={window.discard_friendly_ratio:.1%}")
        parts.append(f"WAF={self._metrics.write_amplification:.2f}")
        return " | ".join(parts)

    def _get_trace_window(self) -> Optional[TraceWindow]:
        if self._trace_collector is None:
            return None
        return self._trace_collector.get_window(
            duration_seconds=self._config.trace_window_seconds,
        )
