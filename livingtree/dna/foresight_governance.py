"""Foresight Governance — world model usage calibration & quality metrics.

Based on Qian et al. (2026) "Current Agents Fail to Leverage World Model
as Tool for Foresight" (arXiv:2601.03905).

Key findings from the paper that drive this module:
  1. More simulation calls = worse outcomes (negative correlation, Fig 7)
  2. Agent tasks benefit more from foresight than VQA tasks (Fig 6)
  3. Forcing world model invocation degrades performance (Fig 8)
  4. The core bottleneck is governance: when to simulate, how to interpret,
     when to stop

This module tracks every simulation invocation and evaluates whether it
actually helped or hurt, building a governance quality score used by
AutonomousCore to self-calibrate its foresight strategy.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

GOVERNANCE_DIR = Path(".livingtree/meta")
GOVERNANCE_LOG = GOVERNANCE_DIR / "foresight_governance.json"


# ═══════════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════════

class ForesightDecision(str, Enum):
    """Governance decision for whether to simulate before acting.

    Qian et al. (2026): the agent's decision ct ∈ {E, W} where
    E = execute in real environment, W = simulate in world model.
    """
    ACT_DIRECTLY = "act_directly"        # Execute immediately, skip simulation
    SIMULATE_ONCE = "simulate_once"      # One simulation, then act
    SIMULATE_MULTIPLE = "simulate_multi" # Multi-simulation with stop criterion
    ASK_HUMAN = "ask_human"              # Too uncertain — escalate


class GovernanceDecisionReason(str, Enum):
    """Why the governance layer made a particular decision."""
    REVERSIBLE = "reversible"            # Action can be rolled back
    HIGH_CONFIDENCE = "high_confidence"  # Prediction interval is tight
    LOW_SNR = "low_snr"                  # Signal-to-noise too low, simulation harmful
    BUDGET_EXHAUSTED = "budget_exhausted" # Simulation budget used up
    DIMINISHING_RETURNS = "diminishing"  # Further simulation won't improve confidence
    HIGH_UNCERTAINTY = "high_uncertainty" # Wide prediction interval → need foresight
    IRREVERSIBLE = "irreversible"        # Action cannot be undone → simulate first


@dataclass
class SimulationRecord:
    """A single simulation invocation and its outcome."""
    timestamp: float = field(default_factory=time.time)
    work_description: str = ""
    decision: ForesightDecision = ForesightDecision.ACT_DIRECTLY
    reason: GovernanceDecisionReason = GovernanceDecisionReason.REVERSIBLE

    # Pre-simulation metrics
    pre_confidence: float = 0.5           # Confidence before simulation
    pre_prediction_interval_width: float = 0.0  # Relative width of prediction interval
    signal_to_noise: float = 0.0          # SNR from predictability engine

    # Simulation execution
    num_simulations_performed: int = 0    # Actually executed simulations
    stopped_early: bool = False           # Hit diminishing returns stop criterion

    # Post-simulation outcome
    post_confidence: float = 0.5          # Confidence after simulation
    confidence_gain: float = 0.0          # pre → post delta
    was_helpful: bool | None = None       # Did simulation improve the outcome?
    was_harmful: bool | None = None       # Did simulation degrade the outcome?


@dataclass
class ForesightGovernanceMetrics:
    """Aggregate governance quality metrics across all cycles.

    Qian et al. (2026) Fig 7: the key metric is whether simulations
    actually help or hurt. This tracks the "WM Helps" vs "WM Hurts"
    breakdown as evidence for self-calibration.
    """
    total_cycles: int = 0
    total_actions: int = 0
    total_simulations: int = 0
    total_simulation_calls: int = 0       # sum of num_simulations_performed

    helpful_simulations: int = 0          # WM Helps
    harmful_simulations: int = 0          # WM Hurts
    neutral_simulations: int = 0          # No measurable impact

    direct_actions: int = 0               # Skipped simulation entirely

    # Ratios (Qian et al. 2026 key metrics)
    @property
    def call_to_action_ratio(self) -> float:
        """Simulation calls per action. >0.5 warns of over-simulation."""
        return self.total_simulation_calls / max(self.total_actions, 1)

    @property
    def help_rate(self) -> float:
        """Fraction of simulations that actually helped."""
        total_rated = self.helpful_simulations + self.harmful_simulations + self.neutral_simulations
        return self.helpful_simulations / max(total_rated, 1)

    @property
    def harm_rate(self) -> float:
        """Fraction of simulations that hurt performance."""
        total_rated = self.helpful_simulations + self.harmful_simulations + self.neutral_simulations
        return self.harmful_simulations / max(total_rated, 1)

    @property
    def governance_score(self) -> float:
        """Composite governance quality score (0-1).

        High score = agent is making good decisions about when/how to simulate.
        Penalized by: high harm_rate, high call_to_action_ratio.
        Rewarded by: high help_rate, appropriate direct_actions.
        """
        if self.total_actions == 0:
            return 0.5

        # Base = help rate
        score = self.help_rate * 0.5

        # Penalty for harmful simulations
        score -= self.harm_rate * 0.4

        # Penalty for over-simulation (Fig 7: negative correlation)
        if self.call_to_action_ratio > 1.0:
            score -= 0.2
        elif self.call_to_action_ratio > 0.5:
            score -= 0.1

        # Bonus for strategic skipping (appropriate direct actions)
        if self.total_actions > 0:
            direct_ratio = self.direct_actions / self.total_actions
            if 0.3 < direct_ratio < 0.7:
                score += 0.1  # Balanced mix of simulation and direct action

        return max(0.0, min(1.0, score + 0.2))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cycles": self.total_cycles,
            "total_actions": self.total_actions,
            "total_simulations": self.total_simulations,
            "total_simulation_calls": self.total_simulation_calls,
            "helpful": self.helpful_simulations,
            "harmful": self.harmful_simulations,
            "neutral": self.neutral_simulations,
            "direct_actions": self.direct_actions,
            "call_to_action_ratio": round(self.call_to_action_ratio, 3),
            "help_rate": round(self.help_rate, 3),
            "harm_rate": round(self.harm_rate, 3),
            "governance_score": round(self.governance_score, 3),
        }


# ═══════════════════════════════════════════════════════════════════
# ForesightGovernance — record keeper
# ═══════════════════════════════════════════════════════════════════

class ForesightGovernance:
    """Tracks every simulation decision and evaluates governance quality.

    Lightweight record-keeper — does NOT make decisions (that's
    AutonomousCore's job). This is the evidence layer that feeds
    self-calibration.

    Usage:
        gov = ForesightGovernance()
        gov.record(SimulationRecord(decision=...))
        score = gov.metrics.governance_score
    """

    def __init__(self, max_records: int = 500):
        self._records: list[SimulationRecord] = []
        self._max_records = max_records
        self._metrics = ForesightGovernanceMetrics()

    def record(self, rec: SimulationRecord) -> None:
        """Log a foresight decision and update aggregate metrics."""
        self._records.append(rec)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]

        # Update metrics
        m = self._metrics
        m.total_actions += 1

        if rec.decision == ForesightDecision.ACT_DIRECTLY:
            m.direct_actions += 1
        else:
            m.total_simulations += 1
            m.total_simulation_calls += rec.num_simulations_performed

            if rec.was_helpful:
                m.helpful_simulations += 1
            elif rec.was_harmful:
                m.harmful_simulations += 1
            elif rec.num_simulations_performed > 0:
                m.neutral_simulations += 1

    def record_cycle(self, cycle_count: int) -> None:
        """Mark a cycle boundary."""
        self._metrics.total_cycles = cycle_count

    @property
    def metrics(self) -> ForesightGovernanceMetrics:
        return self._metrics

    def recent_confidence_history(self, n: int = 10) -> list[float]:
        """Get confidence gains from last N simulations (for stop criterion)."""
        sims = [r for r in self._records[-n:] if r.num_simulations_performed > 0]
        return [s.confidence_gain for s in sims]

    def is_over_simulating(self) -> bool:
        """Detect over-simulation pattern (Qian et al. 2026 Fig 7).

        Returns True if the agent is calling simulation too frequently
        with diminishing or negative returns.
        """
        m = self._metrics
        if m.total_actions < 10:
            return False
        return (
            m.call_to_action_ratio > 1.0
            or (m.harm_rate > m.help_rate and m.total_simulations > 5)
        )

    def stats(self) -> dict[str, Any]:
        return self._metrics.to_dict()

    def _save(self):
        """Persist governance metrics to disk."""
        try:
            GOVERNANCE_DIR.mkdir(parents=True, exist_ok=True)
            GOVERNANCE_LOG.write_text(json.dumps(
                self._metrics.to_dict(), indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"ForesightGovernance save: {e}")

    def _load(self):
        try:
            if GOVERNANCE_LOG.exists():
                data = json.loads(GOVERNANCE_LOG.read_text())
                # Restore countable metrics (not ratios, they're computed)
                self._metrics.total_cycles = data.get("total_cycles", 0)
                self._metrics.total_actions = data.get("total_actions", 0)
                self._metrics.total_simulations = data.get("total_simulations", 0)
                self._metrics.total_simulation_calls = data.get("total_simulation_calls", 0)
                self._metrics.helpful_simulations = data.get("helpful", 0)
                self._metrics.harmful_simulations = data.get("harmful", 0)
                self._metrics.neutral_simulations = data.get("neutral", 0)
                self._metrics.direct_actions = data.get("direct_actions", 0)
        except Exception:
            pass


# ── Singleton ──────────────────────────────────────────────────────

_governance: ForesightGovernance | None = None


def get_foresight_governance() -> ForesightGovernance:
    global _governance
    if _governance is None:
        _governance = ForesightGovernance()
        _governance._load()
    return _governance


__all__ = [
    "ForesightDecision",
    "GovernanceDecisionReason",
    "SimulationRecord",
    "ForesightGovernanceMetrics",
    "ForesightGovernance",
    "get_foresight_governance",
]
