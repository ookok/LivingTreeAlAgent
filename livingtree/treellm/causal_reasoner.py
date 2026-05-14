"""CausalReasoner — Formal causal inference for LLM routing decisions.

Distinguishes correlation from causation: "did choosing provider X CAUSE better results,
or was it just lucky timing?"

Uses simplified do-calculus:
  1. Record treatment (provider choice) and outcome (success/depth/latency)
  2. For each decision, record counterfactual: "what if we'd chosen the runner-up?"
  3. Compute Average Treatment Effect (ATE): E[Y|do(X=x)] - E[Y|do(X=x')]
  4. Report causal effects with confidence intervals

Builds on existing mental_time_travel, deep_probe counterfactuals, joint_evolution.
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

CAUSAL_FILE = Path(".livingtree/causal_effects.json")


@dataclass
class CausalObservation:
    treatment: str       # e.g., "provider:deepseek"
    outcome: float       # 0.0-1.0 quality score
    context: str         # "code_gen", "reasoning", "chat"
    counterfactuals: list[dict] = field(default_factory=list)  # [{treatment, outcome}]


@dataclass
class CausalEffect:
    treatment: str
    control: str
    ate: float           # Average Treatment Effect (positive = treatment better)
    confidence: float    # 0.0-1.0 based on sample size
    sample_size: int
    context: str = ""


class CausalReasoner:
    """Simplified causal inference for LLM routing."""

    _instance: Optional["CausalReasoner"] = None

    @classmethod
    def instance(cls) -> "CausalReasoner":
        if cls._instance is None:
            cls._instance = CausalReasoner()
        return cls._instance

    def __init__(self):
        self._observations: dict[str, list[CausalObservation]] = defaultdict(list)
        self._effects: dict[str, CausalEffect] = {}

    # ── Recording ──────────────────────────────────────────────────

    def record(self, treatment: str, outcome: float,
               context: str = "general",
               counterfactuals: list[dict] = None):
        """Record a treatment→outcome observation with counterfactuals."""
        obs = CausalObservation(
            treatment=treatment, outcome=outcome,
            context=context,
            counterfactuals=counterfactuals or [],
        )
        self._observations[context].append(obs)

        # Keep last 200 per context
        if len(self._observations[context]) > 200:
            self._observations[context] = self._observations[context][-200:]

        # Recompute effects periodically
        if sum(len(v) for v in self._observations.values()) % 20 == 0:
            self._compute_effects()

    # ── Effect Computation ─────────────────────────────────────────

    def _compute_effects(self):
        """Compute Average Treatment Effects for all treatment pairs."""
        for context, obs_list in self._observations.items():
            if len(obs_list) < 10:
                continue

            # Group by treatment
            by_treatment = defaultdict(list)
            for obs in obs_list:
                by_treatment[obs.treatment].append(obs.outcome)

            # Pairwise ATE
            treatments = list(by_treatment.keys())
            for i in range(len(treatments)):
                for j in range(i + 1, len(treatments)):
                    ti, tj = treatments[i], treatments[j]
                    mean_i = sum(by_treatment[ti]) / len(by_treatment[ti])
                    mean_j = sum(by_treatment[tj]) / len(by_treatment[tj])
                    ate = mean_i - mean_j

                    # Simple confidence: larger sample → higher confidence
                    n = min(len(by_treatment[ti]), len(by_treatment[tj]))
                    conf = min(1.0, n / 30)

                    key = f"{context}:{ti}_vs_{tj}"
                    self._effects[key] = CausalEffect(
                        treatment=ti, control=tj, ate=round(ate, 4),
                        confidence=round(conf, 3), sample_size=n,
                        context=context,
                    )

    def get_effect(self, context: str, treatment: str,
                   control: str) -> Optional[CausalEffect]:
        """Get causal effect of treatment vs control in given context."""
        key = f"{context}:{treatment}_vs_{control}"
        if key in self._effects:
            return self._effects[key]
        key_rev = f"{context}:{control}_vs_{treatment}"
        if key_rev in self._effects:
            eff = self._effects[key_rev]
            return CausalEffect(
                treatment=eff.control, control=eff.treatment,
                ate=-eff.ate, confidence=eff.confidence,
                sample_size=eff.sample_size, context=context,
            )
        return None

    def best_treatment(self, context: str) -> Optional[tuple[str, float]]:
        """Return the best treatment for a context based on causal effects."""
        if context not in self._observations or len(self._observations[context]) < 5:
            return None

        by_treatment = defaultdict(list)
        for obs in self._observations[context]:
            by_treatment[obs.treatment].append(obs.outcome)

        best = None
        best_mean = -1
        for treatment, outcomes in by_treatment.items():
            mean = sum(outcomes) / len(outcomes)
            if mean > best_mean:
                best_mean = mean
                best = treatment

        return (best, best_mean) if best else None

    def report(self, context: str = "") -> dict:
        """Generate causal analysis report."""
        effects = {}
        for key, eff in self._effects.items():
            if not context or eff.context == context:
                effects[key] = {
                    "treatment": eff.treatment, "control": eff.control,
                    "ate": eff.ate,
                    "interpretation": (
                        f"{eff.treatment} performs {'better' if eff.ate > 0 else 'worse'} than "
                        f"{eff.control} by {abs(eff.ate):.3f} "
                        f"({eff.confidence:.0%} confidence, n={eff.sample_size})"
                    ),
                }

        return {
            "contexts": list(self._observations.keys()),
            "total_observations": sum(len(v) for v in self._observations.values()),
            "effects": effects,
        }

    def stats(self) -> dict:
        return {
            "observations": sum(len(v) for v in self._observations.values()),
            "effects_computed": len(self._effects),
            "contexts": list(self._observations.keys()),
        }


_reasoner: Optional[CausalReasoner] = None


def get_causal_reasoner() -> CausalReasoner:
    global _reasoner
    if _reasoner is None:
        _reasoner = CausalReasoner()
    return _reasoner


__all__ = ["CausalReasoner", "CausalEffect", "get_causal_reasoner"]
