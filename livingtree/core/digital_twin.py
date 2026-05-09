"""Digital Twin Sandbox — pre-simulate future states to prevent degradation.

Runs a lightweight clone of the current system state forward in time,
predicting health trajectories and triggering pre-emptive repairs.

Architecture:
  1. SNAPSHOT — capture current module states (synapses, pool, economic)
  2. SIMULATE — fast-forward 24-72h with accelerated event replay + noise
  3. PREDICT — evaluate health trajectory using predictability engine
  4. PREVENT — if predicted health < threshold, apply pre-repairs to real system

This transforms the autonomic loop from REACTIVE (detect→fix) to
PREDICTIVE (predict→prevent), like an immune system's early warning.
"""

from __future__ import annotations

import copy
import math
import random
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class TwinSnapshot:
    """A lightweight snapshot of system state for simulation."""
    synapse_weights: dict[str, float]
    synapse_states: dict[str, str]
    pool_health: dict[str, str]
    economic_stats: dict[str, float]
    predictability_data: dict[str, list[float]]
    timestamp: float = field(default_factory=time.time)


@dataclass
class SimulationResult:
    """Result of a digital twin simulation."""
    hours_simulated: float
    initial_health: float
    predicted_health: float
    health_trajectory: list[float]     # Health score at each checkpoint
    critical_events: list[str]         # Degradations detected
    pre_repairs_needed: list[str]       # Actions to prevent degradation
    confidence: float                   # How reliable this simulation is


class DigitalTwin:
    """Lightweight digital twin for predictive system health."""

    def __init__(self, modules: dict[str, Any]):
        self._modules = modules
        self._history: list[SimulationResult] = []
        self._sim_count = 0

    def snapshot(self) -> TwinSnapshot:
        """Capture current system state."""
        sp = self._modules.get("synaptic_plasticity")
        pool = self._modules.get("free_pool")
        eco = self._modules.get("economic")
        pe = self._modules.get("predictability")

        synapse_weights = {}
        synapse_states = {}
        if sp:
            for sid, m in sp._synapses.items():
                synapse_weights[sid] = m.weight
                synapse_states[sid] = m.state.value

        pool_health = {}
        if pool:
            for name, m in pool._models.items():
                pool_health[name] = m.status.value

        economic_stats = {}
        if eco:
            s = eco.stats()
            economic_stats = {
                "daily_spent": s.get("daily_spent_yuan", 0),
                "cumulative_roi": s.get("cumulative_roi", 1),
                "go_rate": s.get("go_rate", 0.7),
            }

        predictability_data = {}
        if pe:
            for name, series in pe._series.items():
                predictability_data[name] = list(series)[-50:]

        return TwinSnapshot(
            synapse_weights=synapse_weights,
            synapse_states=synapse_states,
            pool_health=pool_health,
            economic_stats=economic_stats,
            predictability_data=predictability_data,
        )

    def simulate(self, hours: float = 24.0, checkpoints: int = 6) -> SimulationResult:
        """Run a digital twin simulation forward in time.

        Args:
            hours: How many hours to simulate (24-72 typical)
            checkpoints: Number of health checks along the simulation

        Returns:
            SimulationResult with predicted trajectory and pre-repair suggestions
        """
        snap = self.snapshot()
        self._sim_count += 1

        initial_health = self._compute_health(snap)
        trajectory = [initial_health]
        critical_events = []

        # Simulate forward with accelerated decay + noise
        step_hours = hours / checkpoints
        current_health = initial_health
        weights = dict(snap.synapse_weights)

        for step in range(checkpoints):
            # Apply accelerated decay
            for sid in weights:
                noise = random.gauss(0, 0.02)  # Random perturbation
                weights[sid] = max(0.0, min(1.0, weights[sid] - 0.005 * step_hours + noise))

            # Recalculate health
            current_health = self._compute_health_from_weights(
                weights, snap, step_hours * (step + 1))
            trajectory.append(round(current_health, 3))

            # Detect critical events
            if current_health < 0.5 and (len(trajectory) < 2 or trajectory[-2] >= 0.5):
                critical_events.append(
                    f"健康跌破0.5 @ {step_hours * (step + 1):.0f}h — 突触持续衰减")

        predicted_health = trajectory[-1]

        # Generate pre-repair suggestions
        repairs = self._generate_repairs(trajectory, snap, predicted_health)

        # Confidence: higher with more data points
        confidence = min(1.0, len(snap.synapse_weights) / 50.0)

        result = SimulationResult(
            hours_simulated=hours,
            initial_health=round(initial_health, 3),
            predicted_health=round(predicted_health, 3),
            health_trajectory=trajectory,
            critical_events=critical_events,
            pre_repairs_needed=repairs,
            confidence=round(confidence, 3),
        )
        self._history.append(result)
        return result

    def _compute_health(self, snap: TwinSnapshot) -> float:
        """Compute current health score from snapshot."""
        # Mature ratio
        mature = sum(1 for s in snap.synapse_states.values() if s == "mature")
        total = max(len(snap.synapse_states), 1)
        mature_score = mature / total

        # Pool health
        healthy_pool = sum(1 for s in snap.pool_health.values() if s == "healthy")
        pool_score = healthy_pool / max(len(snap.pool_health), 1)

        # Economic health
        roi = snap.economic_stats.get("cumulative_roi", 1)
        eco_score = min(1.0, max(0.0, roi / 2))

        return 0.4 * mature_score + 0.3 * pool_score + 0.3 * eco_score

    def _compute_health_from_weights(self, weights: dict, snap: TwinSnapshot,
                                     elapsed_h: float) -> float:
        mature = sum(1 for w in weights.values() if w > 0.8)
        total = max(len(weights), 1)
        decay = math.exp(-elapsed_h * 0.01)
        return (mature / total) * decay

    @staticmethod
    def _generate_repairs(trajectory: list[float], snap: TwinSnapshot,
                          predicted: float) -> list[str]:
        repairs = []
        if predicted < 0.4:
            repairs.append("紧急自蒸馏 — 突触分布漂移到危险水平")
            repairs.append("释放所有隔离模型 — 池健康崩溃风险")
        elif predicted < 0.6:
            repairs.append("轻度自蒸馏 — 预防性权重正则化")
            repairs.append("提升 LTP 速率 — 刺激突触生长")
        if len(trajectory) >= 4 and trajectory[-1] < trajectory[0] - 0.15:
            repairs.append("检测到持续退化趋势 — 建议缩短自主周期")
        return repairs

    def stats(self) -> dict[str, Any]:
        return {
            "simulations_run": self._sim_count,
            "last_predicted_health": (
                self._history[-1].predicted_health if self._history else None),
            "pre_repairs_issued": sum(
                len(r.pre_repairs_needed) for r in self._history),
        }


# ═══ Singleton ═══

_twin: DigitalTwin | None = None


def get_digital_twin(modules=None) -> DigitalTwin:
    global _twin
    if _twin is None:
        _twin = DigitalTwin(modules or {})
    return _twin


__all__ = ["DigitalTwin", "TwinSnapshot", "SimulationResult", "get_digital_twin"]
