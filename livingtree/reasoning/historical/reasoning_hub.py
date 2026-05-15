"""Historical Logic — Reasoning Hub: Layering Tracker + Consensus Measure.
 (历史逻辑在 LivingTree 中的工程实现)

层累演进律: 层层积累、逐渐高级
民心向背律: 以实际效果检验成败

Modules merged into this hub:
  - layering_tracker: LayeringTracker 记录系统能力的层层积累，监控涌现现象
  - consensus_measure: ConsensusMeasure A/B 评估 + 用户反馈聚合
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


# ──────────────────────────────────────────
#  Layering Tracker (层累演进)
# ──────────────────────────────────────────

@dataclass
class Layer:
    name: str
    level: int
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    transcends: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    stability: float = 1.0
    usage_count: int = 0


@dataclass
class EmergentCapability:
    name: str
    description: str
    emerged_at_level: int
    required_layers: list[str]
    detected_at: float = field(default_factory=time.time)
    confidence: float = 0.0


class LayeringTracker:
    def __init__(self, name: str = "default"):
        self.name = name
        self._layers: dict[str, Layer] = {}
        self._emergents: list[EmergentCapability] = []
        self._lock = threading.RLock()

    def register_layer(
        self,
        name: str,
        level: int,
        capabilities: list[str],
        description: str = "",
        depends_on: list[str] = None,
        transcends: list[str] = None,
    ) -> Layer:
        with self._lock:
            layer = Layer(
                name=name,
                level=level,
                description=description,
                capabilities=capabilities,
                depends_on=depends_on or [],
                transcends=transcends or [],
            )
            self._layers[name] = layer
            logger.info(
                "Layering[%s]: Layer %d — '%s' (%d capabilities, depends on %s)",
                self.name, level, name, len(capabilities), layer.depends_on,
            )
            return layer

    def mark_usage(self, layer_name: str) -> None:
        with self._lock:
            layer = self._layers.get(layer_name)
            if layer:
                layer.usage_count += 1
                layer.stability = min(1.0, layer.stability + 0.001)

    def check_emergence(self) -> list[EmergentCapability]:
        with self._lock:
            new_emergents = []
            capability_to_layers: dict[str, list[str]] = {}

            for name, layer in self._layers.items():
                for cap in layer.capabilities:
                    if cap not in capability_to_layers:
                        capability_to_layers[cap] = []
                    capability_to_layers[cap].append(name)

            for cap, layer_names in capability_to_layers.items():
                if len(layer_names) >= 2:
                    layers = [self._layers[n] for n in layer_names if n in self._layers]
                    max_level = max(l.level for l in layers)
                    min_level = min(l.level for l in layers)

                    if max_level - min_level >= 2:
                        existing = [e for e in self._emergents if e.name == cap]
                        if not existing:
                            emergent = EmergentCapability(
                                name=cap,
                                description=f"Emergent ability spanning Layers {min_level}-{max_level}",
                                emerged_at_level=max_level,
                                required_layers=layer_names,
                                confidence=min(1.0, 0.5 + 0.1 * (max_level - min_level)),
                            )
                            self._emergents.append(emergent)
                            new_emergents.append(emergent)
                            logger.info(
                                "Layering[%s]: EMERGENCE detected — '%s' at Layer %d "
                                "(spans layers %d-%d)",
                                self.name, cap, max_level, min_level, max_level,
                            )

            return new_emergents

    def get_layer_stack(self) -> list[dict]:
        with self._lock:
            sorted_layers = sorted(self._layers.values(), key=lambda l: l.level)
            return [
                {
                    "level": l.level,
                    "name": l.name,
                    "capabilities": l.capabilities,
                    "depends_on": l.depends_on,
                    "transcends": l.transcends,
                    "stability": l.stability,
                    "usage_count": l.usage_count,
                    "age_hours": (time.time() - l.created_at) / 3600,
                }
                for l in sorted_layers
            ]

    def get_layers_between(self, from_level: int, to_level: int) -> list[Layer]:
        return [
            l for l in self._layers.values()
            if from_level <= l.level <= to_level
        ]

    def get_total_capabilities(self) -> int:
        with self._lock:
            all_caps = set()
            for layer in self._layers.values():
                all_caps.update(layer.capabilities)
            return len(all_caps)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "name": self.name,
                "layers": len(self._layers),
                "max_level": max((l.level for l in self._layers.values()), default=0),
                "total_capabilities": self.get_total_capabilities(),
                "emergents": len(self._emergents),
                "stable_layers": sum(1 for l in self._layers.values() if l.stability >= 0.9),
            }


# ──────────────────────────────────────────
#  Consensus Measure (民心向背律)
# ──────────────────────────────────────────

class DecisionOutcome(str, Enum):
    A_WINS = "A_wins"
    B_WINS = "B_wins"
    TIE = "tie"
    INSUFFICIENT_DATA = "insufficient"


@dataclass
class TrialResult:
    variant: str
    metric_name: str
    value: float
    user_id: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


@dataclass
class ABComparison:
    metric_name: str
    a_mean: float
    b_mean: float
    a_std: float
    b_std: float
    a_count: int
    b_count: int
    improvement: float
    p_value: float
    outcome: DecisionOutcome
    confidence_interval: tuple[float, float]
    recommendation: str = ""


class ConsensusMeasure:
    def __init__(self, name: str = "default", significance_level: float = 0.05):
        self.name = name
        self.significance_level = significance_level
        self._experiments: dict[str, dict[str, Any]] = {}
        self._results: dict[str, list[TrialResult]] = defaultdict(list)
        self._adopted: dict[str, str] = {}
        self._lock = threading.Lock()
        self._min_sample_size = 30

    def start_experiment(
        self, name: str, variant_a: str, variant_b: str, description: str = "",
    ) -> None:
        with self._lock:
            self._experiments[name] = {
                "variant_a": variant_a,
                "variant_b": variant_b,
                "description": description,
                "started_at": time.time(),
                "status": "running",
            }
            logger.info("Consensus[%s]: experiment '%s' started: %s vs %s",
                       self.name, name, variant_a, variant_b)

    def record(
        self, experiment: str, variant: str, metric: str, value: float,
        user_id: str = "", **metadata,
    ) -> None:
        with self._lock:
            result = TrialResult(
                variant=variant,
                metric_name=metric,
                value=value,
                user_id=user_id,
                metadata=metadata,
            )
            self._results[experiment].append(result)

    def evaluate(self, experiment: str, metric: str = None,
                 min_samples: int = None) -> ABComparison:
        min_n = min_samples or self._min_sample_size

        with self._lock:
            trials = self._results.get(experiment, [])

            if metric:
                trials = [t for t in trials if t.metric_name == metric]
            elif trials:
                metric = trials[0].metric_name

            a_trials = [t for t in trials if t.variant == "A"]
            b_trials = [t for t in trials if t.variant == "B"]

            if len(a_trials) < min_n or len(b_trials) < min_n:
                return ABComparison(
                    metric_name=metric or "",
                    a_mean=0.0, b_mean=0.0, a_std=0.0, b_std=0.0,
                    a_count=len(a_trials), b_count=len(b_trials),
                    improvement=0.0, p_value=1.0,
                    outcome=DecisionOutcome.INSUFFICIENT_DATA,
                    confidence_interval=(0.0, 0.0),
                    recommendation=f"Need {min_n} samples per variant",
                )

            a_vals = [t.value for t in a_trials]
            b_vals = [t.value for t in b_trials]

            a_mean = sum(a_vals) / len(a_vals)
            b_mean = sum(b_vals) / len(b_vals)

            a_std = self._std(a_vals)
            b_std = self._std(b_vals)

            improvement = (b_mean - a_mean) / max(abs(a_mean), 0.001)

            p_value = self._welch_ttest(a_vals, b_vals)

            outcome = DecisionOutcome.TIE
            recommendation = ""
            if p_value < self.significance_level:
                if improvement > 0:
                    outcome = DecisionOutcome.B_WINS
                    recommendation = f"B wins: +{improvement:.1%} (p={p_value:.4f})"
                elif improvement < 0:
                    outcome = DecisionOutcome.A_WINS
                    recommendation = f"A wins: {improvement:.1%} (p={p_value:.4f})"
                else:
                    outcome = DecisionOutcome.TIE
                    recommendation = "No practical difference"
            else:
                recommendation = f"Not significant (p={p_value:.4f}, n={len(a_trials)}+{len(b_trials)})"

            ci = self._confidence_interval(a_vals, b_vals)

            logger.info(
                "Consensus[%s]: '%s' %s | A=%.3f±%.3f(n=%d) B=%.3f±%.3f(n=%d) p=%.4f",
                self.name, experiment, outcome.value,
                a_mean, a_std, len(a_vals), b_mean, b_std, len(b_vals), p_value,
            )

            return ABComparison(
                metric_name=metric or "",
                a_mean=a_mean, b_mean=b_mean,
                a_std=a_std, b_std=b_std,
                a_count=len(a_vals), b_count=len(b_vals),
                improvement=improvement, p_value=p_value,
                outcome=outcome,
                confidence_interval=ci,
                recommendation=recommendation,
            )

    def adopt(self, experiment: str) -> str:
        result = self.evaluate(experiment)
        with self._lock:
            if result.outcome == DecisionOutcome.B_WINS:
                self._adopted[experiment] = "B"
                if experiment in self._experiments:
                    self._experiments[experiment]["status"] = "completed"
                    self._experiments[experiment]["adopted"] = "B"
                logger.info("Consensus[%s]: adopting B for '%s'", self.name, experiment)
                return "B"
            elif result.outcome == DecisionOutcome.A_WINS:
                self._adopted[experiment] = "A"
                if experiment in self._experiments:
                    self._experiments[experiment]["status"] = "completed"
                    self._experiments[experiment]["adopted"] = "A"
                logger.info("Consensus[%s]: adopting A for '%s'", self.name, experiment)
                return "A"
            return "tie"

    def get_adopted(self, experiment: str) -> Optional[str]:
        return self._adopted.get(experiment)

    def get_sample_size(self, experiment: str) -> tuple[int, int]:
        trials = self._results.get(experiment, [])
        return (
            sum(1 for t in trials if t.variant == "A"),
            sum(1 for t in trials if t.variant == "B"),
        )

    def all_experiments(self) -> dict[str, dict]:
        result = {}
        for name, exp in self._experiments.items():
            a_n, b_n = self.get_sample_size(name)
            ev = self.evaluate(name)
            result[name] = {
                **exp,
                "a_samples": a_n,
                "b_samples": b_n,
                "outcome": ev.outcome.value,
                "improvement": ev.improvement,
                "recommendation": ev.recommendation,
            }
        return result

    @staticmethod
    def _std(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return math.sqrt(variance)

    @staticmethod
    def _welch_ttest(a: list[float], b: list[float]) -> float:
        n_a, n_b = len(a), len(b)
        if n_a < 2 or n_b < 2:
            return 1.0

        mean_a = sum(a) / n_a
        mean_b = sum(b) / n_b

        var_a = sum((x - mean_a) ** 2 for x in a) / (n_a - 1)
        var_b = sum((x - mean_b) ** 2 for x in b) / (n_b - 1)

        se = math.sqrt(var_a / n_a + var_b / n_b)
        if se == 0:
            return 0.0 if abs(mean_a - mean_b) < 1e-9 else 1e-10

        t = abs(mean_a - mean_b) / se

        df_num = (var_a / n_a + var_b / n_b) ** 2
        df_den = ((var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1))
        df = df_num / max(df_den, 1e-10)

        x = df / (df + t * t)
        p = 1 - x

        return min(1.0, max(0.0, p * 2))

    @staticmethod
    def _confidence_interval(a: list[float], b: list[float]) -> tuple[float, float]:
        n_a, n_b = len(a), len(b)
        if n_a < 2 or n_b < 2:
            return (-float('inf'), float('inf'))

        mean_a = sum(a) / n_a
        mean_b = sum(b) / n_b
        diff = mean_b - mean_a

        var_a = sum((x - mean_a) ** 2 for x in a) / (n_a - 1)
        var_b = sum((x - mean_b) ** 2 for x in b) / (n_b - 1)
        se = math.sqrt(var_a / n_a + var_b / n_b)

        z = 1.96
        margin = z * se
        return (diff - margin, diff + margin)

    def get_stats(self) -> dict:
        with self._lock:
            running = sum(1 for e in self._experiments.values() if e["status"] == "running")
            completed = sum(1 for e in self._experiments.values() if e["status"] == "completed")
            return {
                "name": self.name,
                "experiments": len(self._experiments),
                "running": running,
                "completed": completed,
                "total_trials": sum(len(v) for v in self._results.values()),
                "adopted": dict(self._adopted),
            }


_layering_tracker_instance: Optional[LayeringTracker] = None
_layering_lock = threading.Lock()


def get_layering_tracker(name: str = "default") -> LayeringTracker:
    global _layering_tracker_instance
    if _layering_tracker_instance is None:
        with _layering_lock:
            if _layering_tracker_instance is None:
                _layering_tracker_instance = LayeringTracker(name=name)
    return _layering_tracker_instance


_consensus_measure_instance: Optional[ConsensusMeasure] = None
_consensus_lock = threading.Lock()


def get_consensus_measure(name: str = "default") -> ConsensusMeasure:
    global _consensus_measure_instance
    if _consensus_measure_instance is None:
        with _consensus_lock:
            if _consensus_measure_instance is None:
                _consensus_measure_instance = ConsensusMeasure(name=name)
    return _consensus_measure_instance
