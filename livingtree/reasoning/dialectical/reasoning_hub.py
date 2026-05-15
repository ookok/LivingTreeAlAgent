"""Dialectical Logic — Reasoning Hub: Contradiction Tracking + Phase Transition.
 (黑格尔/马克思辩证逻辑的工程实现)

对立统一律: 任何事物内部都包含矛盾双方，矛盾推动发展
量变质变律: 量的积累达到临界点触发质的飞跃
否定之否定律: 发展呈现螺旋上升（正→反→合）

Modules merged into this hub:
  - contradiction_tracker: ContradictionTracker 追踪系统中的核心矛盾
  - phase_transition: PhaseTransitionMonitor 量变质变监控
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from loguru import logger


# ──────────────────────────────────────────
#  Contradiction Tracker (矛盾追踪)
# ──────────────────────────────────────────

class ContradictionState(str, Enum):
    UNITY = "unity"
    STRUGGLE = "struggle"
    RESOLUTION = "resolution"
    NEGATION = "negation"


@dataclass
class ContradictionPole:
    name: str
    value: float = 0.5
    trend: list[float] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def record(self) -> None:
        self.trend.append(self.value)
        if len(self.trend) > 100:
            self.trend = self.trend[-50:]

    @property
    def momentum(self) -> float:
        if len(self.trend) < 3:
            return 0.0
        recent = self.trend[-5:]
        if len(recent) < 2:
            return 0.0
        return sum(recent[i] - recent[i-1] for i in range(1, len(recent))) / (len(recent) - 1)


@dataclass
class Contradiction:
    name: str
    thesis: ContradictionPole
    antithesis: ContradictionPole
    state: ContradictionState = ContradictionState.UNITY
    resolution_count: int = 0

    @property
    def intensity(self) -> float:
        return self.thesis.value * self.antithesis.value

    @property
    def balance(self) -> float:
        return self.thesis.value - self.antithesis.value

    @property
    def is_escalating(self) -> bool:
        return self.thesis.momentum > 0 and self.antithesis.momentum > 0

    @property
    def is_resolving(self) -> bool:
        return self.thesis.momentum < 0 and self.antithesis.momentum < 0


class ContradictionTracker:
    def __init__(self, name: str = "default"):
        self.name = name
        self._contradictions: dict[str, Contradiction] = {}
        self._history: list[dict] = []
        self._lock = threading.Lock()

    def register(self, name: str, thesis_name: str, antithesis_name: str,
                 thesis_value: float = 0.5, antithesis_value: float = 0.5) -> Contradiction:
        with self._lock:
            c = Contradiction(
                name=name,
                thesis=ContradictionPole(name=thesis_name, value=thesis_value),
                antithesis=ContradictionPole(name=antithesis_name, value=antithesis_value),
            )
            c.thesis.record()
            c.antithesis.record()
            self._contradictions[name] = c
            logger.info("Contradiction[%s]: registered '%s' (%s ↔ %s)",
                       self.name, name, thesis_name, antithesis_name)
            return c

    def update(self, name: str, **poles: float) -> Contradiction:
        with self._lock:
            c = self._contradictions.get(name)
            if not c:
                raise KeyError(f"Unknown contradiction: {name}")

            if c.thesis.name in poles:
                c.thesis.value = max(0.0, min(1.0, poles[c.thesis.name]))
            if c.antithesis.name in poles:
                c.antithesis.value = max(0.0, min(1.0, poles[c.antithesis.name]))

            c.thesis.record()
            c.antithesis.record()

            self._history.append({
                "ts": time.time(),
                "name": name,
                c.thesis.name: c.thesis.value,
                c.antithesis.name: c.antithesis.value,
                "intensity": c.intensity,
                "balance": c.balance,
                "state": c.state.value,
            })

            if len(self._history) > 1000:
                self._history = self._history[-500:]

            return c

    def check_phase_transition(self, name: str, intensity_threshold: float = 0.8) -> Optional[str]:
        with self._lock:
            c = self._contradictions.get(name)
            if not c:
                return None

            if c.intensity >= intensity_threshold and c.is_escalating:
                old_state = c.state
                if old_state != ContradictionState.STRUGGLE:
                    c.resolution_count += 1
                c.state = ContradictionState.STRUGGLE
                desc = (
                    f"PHASE TRANSITION [{name}]: {c.thesis.name}({c.thesis.value:.2f}) "
                    f"↔ {c.antithesis.name}({c.antithesis.value:.2f}) | "
                    f"intensity={c.intensity:.2f}, "
                    f"old_state={old_state.value} → struggle, "
                    f"resolutions={c.resolution_count}"
                )
                logger.warning("Contradiction[%s]: %s", self.name, desc)
                return desc

            if c.state == ContradictionState.STRUGGLE and c.intensity < 0.3:
                c.state = ContradictionState.RESOLUTION
                desc = (
                    f"NEGATION OF NEGATION [{name}]: resolved at higher level, "
                    f"resolution #{c.resolution_count}"
                )
                logger.info("Contradiction[%s]: %s", self.name, desc)
                return desc

            return None

    def get_dominant_pole(self, name: str) -> tuple[str, float]:
        c = self._contradictions.get(name)
        if not c:
            return ("none", 0.0)
        if c.balance > 0:
            return (c.thesis.name, abs(c.balance))
        elif c.balance < 0:
            return (c.antithesis.name, abs(c.balance))
        return ("balanced", 0.0)

    def get_all_states(self) -> dict[str, dict]:
        with self._lock:
            return {
                name: {
                    "thesis": c.thesis.name,
                    "thesis_value": c.thesis.value,
                    "thesis_momentum": c.thesis.momentum,
                    "antithesis": c.antithesis.name,
                    "antithesis_value": c.antithesis.value,
                    "antithesis_momentum": c.antithesis.momentum,
                    "intensity": c.intensity,
                    "balance": c.balance,
                    "state": c.state.value,
                    "escalating": c.is_escalating,
                    "dominant": self.get_dominant_pole(name)[0],
                    "resolutions": c.resolution_count,
                }
                for name, c in self._contradictions.items()
            }

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "name": self.name,
                "contradictions": len(self._contradictions),
                "history_entries": len(self._history),
                "active_struggles": sum(
                    1 for c in self._contradictions.values()
                    if c.state == ContradictionState.STRUGGLE
                ),
                "total_resolutions": sum(
                    c.resolution_count for c in self._contradictions.values()
                ),
            }


_contradiction_tracker_instance: Optional[ContradictionTracker] = None
_contradiction_tracker_lock = threading.Lock()


def get_contradiction_tracker(name: str = "default") -> ContradictionTracker:
    global _contradiction_tracker_instance
    if _contradiction_tracker_instance is None:
        with _contradiction_tracker_lock:
            if _contradiction_tracker_instance is None:
                _contradiction_tracker_instance = ContradictionTracker(name=name)
    return _contradiction_tracker_instance


# ──────────────────────────────────────────
#  Phase Transition Monitor (量变质变监控)
# ──────────────────────────────────────────

class Phase(str, Enum):
    DORMANT = "dormant"
    ACCUMULATING = "accumulating"
    TRANSITIONING = "transitioning"
    LEAPING = "leaping"
    STABILIZING = "stabilizing"


@dataclass
class PhaseTransition:
    metric_name: str
    from_phase: Phase
    to_phase: Phase
    value_at_transition: float
    threshold: float
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class PhaseTransitionMonitor:
    def __init__(self, name: str = "default"):
        self.name = name
        self._metrics: dict[str, list[float]] = defaultdict(list)
        self._phases: dict[str, Phase] = {}
        self._thresholds: dict[str, dict[str, tuple[float, Phase]]] = {}
        self._transitions: list[PhaseTransition] = []
        self._lock = threading.Lock()
        self._on_transition: dict[str, list[Callable]] = defaultdict(list)

    def register_metric(
        self,
        name: str,
        thresholds: dict[str, tuple[float, Phase]] = None,
        initial_phase: Phase = Phase.DORMANT,
    ) -> None:
        with self._lock:
            self._phases[name] = initial_phase
            if thresholds:
                self._thresholds[name] = thresholds
            logger.debug("PhaseMonitor[%s]: registered metric '%s' (phase=%s)",
                        self.name, name, initial_phase.value)

    def record(self, metric_name: str, value: float) -> Optional[PhaseTransition]:
        with self._lock:
            self._metrics[metric_name].append(value)
            if len(self._metrics[metric_name]) > 200:
                self._metrics[metric_name] = self._metrics[metric_name][-100:]

            current_phase = self._phases.get(metric_name, Phase.DORMANT)
            thresholds = self._thresholds.get(metric_name, {})

            for thresh_desc, (threshold, target_phase) in sorted(
                thresholds.items(), key=lambda x: x[1][0],
            ):
                if value >= threshold and target_phase != current_phase:
                    transition = PhaseTransition(
                        metric_name=metric_name,
                        from_phase=current_phase,
                        to_phase=target_phase,
                        value_at_transition=value,
                        threshold=threshold,
                        metadata={"description": thresh_desc},
                    )
                    self._phases[metric_name] = target_phase
                    self._transitions.append(transition)

                    logger.info(
                        "PhaseMonitor[%s]: %s → %s @ %.3f (threshold: %s=%.3f)",
                        self.name, current_phase.value, target_phase.value,
                        value, thresh_desc, threshold,
                    )

                    for cb in self._on_transition.get(metric_name, []):
                        try:
                            cb(transition)
                        except Exception as e:
                            logger.error("PhaseMonitor callback error: %s", e)

                    return transition

            return None

    def get_phase(self, metric_name: str) -> Phase:
        return self._phases.get(metric_name, Phase.DORMANT)

    def get_trend(self, metric_name: str, window: int = 10) -> float:
        values = self._metrics.get(metric_name, [])
        if len(values) < 2:
            return 0.0
        recent = values[-min(window, len(values)):]
        if len(recent) < 2:
            return 0.0
        return sum(recent[i] - recent[i-1] for i in range(1, len(recent))) / (len(recent) - 1)

    def is_approaching_threshold(self, metric_name: str, margin: float = 0.1) -> bool:
        values = self._metrics.get(metric_name, [])
        if not values:
            return False
        current = values[-1]
        thresholds = self._thresholds.get(metric_name, {})

        for thresh_val, _ in thresholds.values():
            if abs(current - thresh_val) / max(thresh_val, 0.001) <= margin:
                return True
        return False

    def on_transition(self, metric_name: str, callback: Callable) -> None:
        self._on_transition[metric_name].append(callback)

    def get_transitions_since(self, timestamp: float) -> list[PhaseTransition]:
        return [t for t in self._transitions if t.timestamp >= timestamp]

    def get_summary(self) -> dict:
        with self._lock:
            return {
                metric: {
                    "current_phase": self._phases.get(metric, Phase.DORMANT).value,
                    "current_value": self._metrics[metric][-1] if self._metrics[metric] else None,
                    "trend": self.get_trend(metric),
                    "approaching_threshold": self.is_approaching_threshold(metric),
                }
                for metric in self._metrics
            }

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "name": self.name,
                "metrics": len(self._metrics),
                "transitions": len(self._transitions),
                "active_phases": {
                    metric: phase.value
                    for metric, phase in self._phases.items()
                },
            }


_phase_monitor_instance: Optional[PhaseTransitionMonitor] = None
_phase_monitor_lock = threading.Lock()


def get_phase_transition_monitor(name: str = "default") -> PhaseTransitionMonitor:
    global _phase_monitor_instance
    if _phase_monitor_instance is None:
        with _phase_monitor_lock:
            if _phase_monitor_instance is None:
                _phase_monitor_instance = PhaseTransitionMonitor(name=name)
    return _phase_monitor_instance
