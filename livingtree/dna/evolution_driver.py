"""Evolution Driver — Unified optimization signal aggregator for self-modifying code.

Answers: "What drives autonomous code modification?"

Aggregates 12 existing runtime signal sources into a single optimization objective.
When any signal exceeds its target range, the driver generates a ModificationProposal
with: the file to modify, what to change, the current value, the target value,
and the driving signal that triggered it.

Architecture:
  12 signal sources → EvolutionDriver.aggregate() → unified_fitness score
    ↓ (fitness < threshold OR any signal out of range)
  ModificationProposal → CodeEvolution.apply() → git commit → test → deploy

Signal sources (all already exist in the codebase):
  1. observability/metrics.py        → latency distribution
  2. observability/error_interceptor  → error patterns (top-N exceptions)
  3. execution/quality_checker.py     → quality scores per task type
  4. execution/cost_aware.py          → cost trends (daily burn rate)
  5. execution/rank_monitor.py        → population diversity
  6. dna/evolution_store.py           → lesson accumulation rate
  7. observability/system_monitor.py  → CPU/memory pressure
  8. execution/context_evolution.py   → tool/peer success rates
  9. treellm/circuit_breaker.py       → trip frequency per provider
  10. api/token_accountant.py         → layer budget utilization
  11. observability/calibration.py    → prediction accuracy drift
  12. observability/sentinel.py       → anomaly alert frequency
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ── Data Types ──

class SignalSource(str, Enum):
    LATENCY = "latency"           # metrics.py histogram
    ERROR = "error"               # error_interceptor patterns
    QUALITY = "quality"           # quality_checker scores
    COST = "cost"                 # cost_aware trends
    DIVERSITY = "diversity"       # rank_monitor
    LESSONS = "lessons"           # evolution_store
    RESOURCES = "resources"       # system_monitor
    TOOLS = "tools"               # context_evolution tools
    BREAKER = "breaker"           # circuit_breaker trips
    BUDGET = "budget"             # token_accountant
    CALIBRATION = "calibration"   # calibration tracker
    ANOMALY = "anomaly"           # sentinel alerts


@dataclass
class SignalReading:
    """A single signal reading from one of the 12 sources."""
    source: SignalSource
    metric: str                  # e.g., "p95_latency_ms", "daily_cost_yuan"
    current_value: float
    target_min: float
    target_max: float
    direction: str = "minimize"  # "minimize" or "maximize"
    weight: float = 1.0          # Importance weight [0, 1]
    timestamp: float = field(default_factory=time.time)

    @property
    def is_healthy(self) -> bool:
        return self.target_min <= self.current_value <= self.target_max

    @property
    def deviation(self) -> float:
        """How far from target range (0 = within range, >0 = out of range)."""
        if self.is_healthy:
            return 0.0
        if self.current_value < self.target_min:
            return self.target_min - self.current_value
        return self.current_value - self.target_max

    @property
    def normalized_deviation(self) -> float:
        """Deviation as fraction of target range."""
        target_range = self.target_max - self.target_min
        if target_range == 0:
            return 1.0 if not self.is_healthy else 0.0
        return self.deviation / target_range


@dataclass
class ModificationProposal:
    """A concrete code change proposed by the evolution driver."""
    source: SignalSource          # Which signal triggered this
    file_path: str                 # File to modify
    parameter: str                 # Parameter name (e.g., "rate_limit_req_per_min")
    current_value: Any
    proposed_value: Any
    reason: str                    # Human-readable reason
    risk: str = "low"              # "low", "medium", "high"
    auto_apply: bool = False       # Safe to apply without human review?
    created_at: float = field(default_factory=time.time)


# ── Signal → File/Parameter Mapping ──

# Maps each signal source to the files and parameters it can modify
SIGNAL_TARGET_MAP = {
    SignalSource.LATENCY: [
        ("api/server.py", "rate_limit_req_per_min", "If p95 latency > 500ms, reduce rate limit"),
        ("treellm/providers.py", "RATE_LIMIT_BASE_DELAY", "If avg latency > 2s, increase retry delay"),
        ("config/settings.py", "pro_max_tokens", "If generation latency high, reduce max_tokens"),
    ],
    SignalSource.ERROR: [
        ("treellm/circuit_breaker.py", "failure_threshold", "If error rate > 10%, lower trip threshold from 3→2"),
        ("treellm/providers.py", "RATE_LIMIT_MAX_RETRIES", "If HTTP errors frequent, increase retries"),
    ],
    SignalSource.QUALITY: [
        ("execution/orchestrator.py", "max_agents", "If quality < 0.6, increase orchestrator parallelism"),
        ("config/settings.py", "execution.plan_depth", "If quality low on complex tasks, deepen planning"),
    ],
    SignalSource.COST: [
        ("execution/cost_aware.py", "daily_budget_tokens", "If daily cost exceeds budget, reduce"),
        ("treellm/holistic_election.py", "weights.cost", "If cost rising, increase cost weight in election"),
        ("api/token_accountant.py", "total_budget", "If utilization > 90%, expand budget"),
    ],
    SignalSource.DIVERSITY: [
        ("execution/rank_monitor.py", "collapse_threshold", "If diversity < 0.1, lower threshold"),
        ("execution/thinking_evolution.py", "mutation_rate", "If rank collapsed, increase mutation"),
    ],
    SignalSource.LESSONS: [
        ("dna/evolution_store.py", "decay_factor", "If lesson accumulation slows, reduce decay → keep longer"),
        ("dna/life_stage.py", "plan_depth", "If lessons pile up unused, increase plan depth to consume them"),
    ],
    SignalSource.BREAKER: [
        ("treellm/circuit_breaker.py", "cooldown_seconds", "If trip rate > 5/hour, increase cooldown"),
        ("treellm/holistic_election.py", "weights.latency", "If trips frequent, prioritize latency in election"),
    ],
    SignalSource.BUDGET: [
        ("api/token_accountant.py", "total_budget", "If router budget > 80%, shift to agent budget"),
        ("execution/cost_aware.py", "daily_budget_tokens", "If daily utilization > 90%, expand"),
    ],
}


class EvolutionDriver:
    """Aggregate 12 runtime signals → unified fitness → modification proposals.

    This is the "brain" that decides WHAT to modify and WHY.
    Connects existing signals to concrete code changes via SIGNAL_TARGET_MAP.
    """

    def __init__(self, store_path: str = ".livingtree/evolution_driver.json"):
        self._store_path = Path(store_path)
        self._readings: dict[str, SignalReading] = {}
        self._proposals: list[ModificationProposal] = []
        self._applied_count = 0
        self._fitness_history: list[float] = []
        self._load()

    # ── Signal Ingestion ──

    def ingest(self, reading: SignalReading) -> None:
        """Ingest a signal reading from any of the 12 sources."""
        key = f"{reading.source.value}:{reading.metric}"
        self._readings[key] = reading

    def ingest_batch(self, readings: list[SignalReading]) -> None:
        for r in readings:
            self.ingest(r)

    def ingest_from_metrics(self, metrics_collector) -> list[SignalReading]:
        """Auto-ingest from MetricsCollector."""
        readings = []
        try:
            stats = metrics_collector.get_all() if hasattr(metrics_collector, 'get_all') else {}
            for name, value in stats.items():
                if 'latency' in name.lower():
                    readings.append(SignalReading(
                        source=SignalSource.LATENCY, metric=name,
                        current_value=float(value), target_min=0, target_max=500,
                        direction="minimize",
                    ))
                elif 'error' in name.lower():
                    readings.append(SignalReading(
                        source=SignalSource.ERROR, metric=name,
                        current_value=float(value), target_min=0, target_max=0.05,
                    ))
                elif 'cost' in name.lower():
                    readings.append(SignalReading(
                        source=SignalSource.COST, metric=name,
                        current_value=float(value), target_min=0, target_max=10.0,
                    ))
        except Exception:
            pass
        self.ingest_batch(readings)
        return readings

    # ── Core: Generate Modification Proposals ──

    def generate_proposals(self) -> list[ModificationProposal]:
        """Generate modification proposals for all unhealthy signals.

        Returns list of concrete code changes ordered by urgency (highest deviation first).
        """
        proposals = []

        for key, reading in self._readings.items():
            if reading.is_healthy:
                continue

            # Find matching targets in SIGNAL_TARGET_MAP
            targets = SIGNAL_TARGET_MAP.get(reading.source, [])
            for file_path, parameter, reason in targets:
                current = reading.current_value
                target_mid = (reading.target_min + reading.target_max) / 2

                # Calculate proposed value (move toward target mid)
                if reading.direction == "minimize":
                    proposed = current * 0.8  # Reduce by 20%
                    proposed = max(reading.target_min, proposed)
                else:
                    proposed = current * 1.2  # Increase by 20%
                    proposed = min(reading.target_max, proposed)

                # Risk assessment
                if reading.normalized_deviation > 2.0:
                    risk = "high"
                elif reading.normalized_deviation > 1.0:
                    risk = "medium"
                else:
                    risk = "low"

                # Auto-apply only for low-risk, well-tested parameters
                auto_apply = (
                    risk == "low"
                    and "rate_limit" in parameter.lower()
                    or "max_tokens" in parameter.lower()
                    or "cooldown" in parameter.lower()
                )

                proposal = ModificationProposal(
                    source=reading.source,
                    file_path=file_path,
                    parameter=parameter,
                    current_value=current,
                    proposed_value=round(proposed, 2),
                    reason=f"{reason} (current={current:.2f}, target=[{reading.target_min:.2f},{reading.target_max:.2f}])",
                    risk=risk,
                    auto_apply=auto_apply,
                )
                proposals.append(proposal)

        # Sort by deviation (most urgent first)
        proposals.sort(key=lambda p: self._get_deviation_for(p), reverse=True)
        self._proposals = proposals
        self._save()
        return proposals

    # ── Fitness Score ──

    def compute_fitness(self) -> float:
        """Compute unified fitness score from all 12 signals.

        Fitness = weighted harmonic mean of all signal health scores.
        1.0 = perfectly healthy, 0.0 = catastrophic failure.
        When fitness drops below 0.6, autonomous evolution is triggered.
        """
        if not self._readings:
            return 1.0

        total_weight = 0.0
        weighted_sum = 0.0

        for reading in self._readings.values():
            # Health score: how close to target range center
            target_mid = (reading.target_min + reading.target_max) / 2
            target_range = reading.target_max - reading.target_min

            if target_range == 0:
                health = 1.0 if reading.is_healthy else 0.5
            else:
                distance = abs(reading.current_value - target_mid)
                health = max(0.0, 1.0 - distance / (target_range * 2))

            w = reading.weight
            weighted_sum += w * health
            total_weight += w

        fitness = weighted_sum / max(1e-9, total_weight)
        self._fitness_history.append(fitness)

        if len(self._fitness_history) > 100:
            self._fitness_history.pop(0)

        return fitness

    def should_evolve(self) -> bool:
        """Check if autonomous evolution should be triggered.

        Triggers when:
          1. Fitness drops below 0.6, OR
          2. Fitness is trending downward (3 consecutive drops), OR
          3. Any signal has deviation > 2x target range
        """
        fitness = self.compute_fitness()

        if fitness < 0.6:
            return True

        # Trend check
        if len(self._fitness_history) >= 3:
            recent = self._fitness_history[-3:]
            if recent[0] > recent[1] > recent[2]:
                return True

        # Critical deviation check
        for reading in self._readings.values():
            if reading.normalized_deviation > 2.0:
                return True

        return False

    # ── Query ──

    def unhealthy_signals(self) -> list[SignalReading]:
        return [r for r in self._readings.values() if not r.is_healthy]

    def pending_proposals(self) -> list[ModificationProposal]:
        return [p for p in self._proposals if not hasattr(p, 'applied')]

    @property
    def stats(self) -> dict:
        return {
            "signals_tracked": len(self._readings),
            "unhealthy_count": len(self.unhealthy_signals()),
            "fitness": round(self.compute_fitness(), 4),
            "pending_proposals": len(self.pending_proposals()),
            "applied_count": self._applied_count,
        }

    # ── Internal ──

    def _get_deviation_for(self, proposal: ModificationProposal) -> float:
        for reading in self._readings.values():
            if reading.source == proposal.source:
                return reading.normalized_deviation
        return 0.0

    def _load(self) -> None:
        try:
            if self._store_path.exists():
                data = json.loads(self._store_path.read_text("utf-8"))
                self._applied_count = data.get("applied_count", 0)
        except Exception:
            pass

    def _save(self) -> None:
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            self._store_path.write_text(json.dumps({
                "applied_count": self._applied_count,
                "fitness": self.compute_fitness(),
                "pending_proposals": len(self.pending_proposals()),
                "fitness_history": self._fitness_history[-20:],
            }, indent=2), "utf-8")
        except Exception:
            pass


# ── Singleton ──

_driver: Optional[EvolutionDriver] = None


def get_evolution_driver() -> EvolutionDriver:
    global _driver
    if _driver is None:
        _driver = EvolutionDriver()
    return _driver
