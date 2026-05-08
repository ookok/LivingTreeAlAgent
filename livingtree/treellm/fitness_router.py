"""Fitness-Based Model Router — Squeeze-Evolve inspired dynamic routing.

Based on "Squeeze Evolve: Unified Multi-Model Orchestration for Verifier-Free
Evolution" (Maheswaran et al., 2026). Replaces static weighted scoring with
adaptive fitness-based routing.

Core principle: allocate model capability where it has the highest marginal utility.
  - Low confidence tasks (hard) → expensive Pro model
  - High confidence tasks (easy) → cheap Flash model
  - Full consensus → non-LLM aggregation (skip model call)

Architecture:
  HolisticElection (8-dim scores)
       │
       ▼
  FitnessRouter (adaptive thresholding)
       │
       ├── fitness < 30th pctl  →  Pro model (high capability)
       ├── fitness 30-70th pctl →  Mid/Balanced model
       ├── fitness > 70th pctl →  Flash model (low cost)
       └── consensus detected  →  Skip (zero cost)
       │
       ▼
  EconomicOrchestrator (compliance + budget gate)

Population Evolution:
  Maintains sliding window of recent routing decisions.
  Adapts percentile thresholds based on success rates.
  Every N decisions: re-evaluate threshold optimality.

Integration with existing HolisticElection + EconomicOrchestrator:
  - Wraps existing systems, not replaces them
  - Uses HolisticElection scores as "fitness signal"
  - Uses EconomicOrchestrator for final compliance/budget checks

Usage:
    router = FitnessRouter()
    decision = await router.route(
        task_desc="generate EIA report",
        candidates=["deepseek-v4-pro", "deepseek-v4-flash"],
        holisitic_scores=...,  # from HolisticElection
    )
    # decision.selected_model = "deepseek-v4-flash" (if easy enough)
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
from loguru import logger

FITNESS_CACHE = Path(".livingtree/fitness_router.json")

# Percentile thresholds for 3-tier routing (from Squeeze-Evolve config)
LOW_FITNESS_PCT = 30.0    # Below this → Pro model (hardest)
HIGH_FITNESS_PCT = 70.0   # Above this → Flash model (easiest)
CONSENSUS_THRESHOLD = 0.95  # Above this → skip model call entirely

# Adaptive parameters
WINDOW_SIZE = 50           # Decisions window for threshold adaptation
ADAPT_INTERVAL = 20        # Re-evaluate thresholds every N decisions
LEARNING_RATE = 0.05       # How fast thresholds adapt


@dataclass
class FitnessScore:
    """Multi-dimensional fitness signal for a single routing candidate."""
    model_name: str
    # HolisticElection scores (0-1)
    quality_score: float = 0.5
    latency_score: float = 0.5
    cost_score: float = 0.5
    capability_score: float = 0.5
    cache_score: float = 0.0
    sticky_score: float = 0.0
    # Composite
    holistic_total: float = 0.5
    # Meta
    is_free: bool = False
    avg_latency_ms: float = 500.0
    cost_per_1k: float = 0.0


@dataclass
class FitnessDecision:
    """Squeeze-Evolve style routing decision."""
    task_id: str
    task_desc: str = ""
    selected_model: str = ""
    tier: str = "mid"  # pro, mid, flash, skip
    fitness: float = 0.5
    confidence: float = 0.5
    # Candidate rankings
    candidate_scores: dict[str, FitnessScore] = field(default_factory=dict)
    # Economic
    estimated_cost_yuan: float = 0.0
    estimated_tokens: int = 0
    # Adaptive state
    threshold_low: float = LOW_FITNESS_PCT / 100.0
    threshold_high: float = HIGH_FITNESS_PCT / 100.0
    # Metadata
    timestamp: float = field(default_factory=time.time)
    routing_reason: str = ""


class FitnessRouter:
    """Squeeze-Evolve style adaptive fitness-based model router.

    Key innovation over HolisticElection:
    - Not just "pick the highest score"
    - But "is this task hard enough to justify the expensive model?"
    - Adapts routing thresholds based on observed success rates

    Population evolution of routing decisions:
    - Sliding window of last WINDOW_SIZE decisions
    - Tracks per-tier success rates
    - Shifts thresholds to optimize cost-success Pareto frontier
    """

    def __init__(self, window_size: int = WINDOW_SIZE):
        self.window_size = window_size
        self._decisions: deque[FitnessDecision] = deque(maxlen=window_size)
        self._threshold_low = LOW_FITNESS_PCT / 100.0
        self._threshold_high = HIGH_FITNESS_PCT / 100.0
        self._decision_count = 0

        # Per-tier tracking
        self._tier_stats = {
            "pro":   {"decisions": 0, "successes": 0, "total_cost": 0.0, "total_tokens": 0},
            "mid":   {"decisions": 0, "successes": 0, "total_cost": 0.0, "total_tokens": 0},
            "flash": {"decisions": 0, "successes": 0, "total_cost": 0.0, "total_tokens": 0},
            "skip":  {"decisions": 0, "successes": 0, "total_cost": 0.0, "total_tokens": 0},
        }

        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return
        self._load_state()
        self._initialized = True
        logger.info(
            "FitnessRouter: adaptive thresholds (low=%.0fpct, high=%.0fpct), window=%d",
            self._threshold_low * 100, self._threshold_high * 100, self.window_size,
        )

    def compute_fitness(self, scores: dict[str, FitnessScore]) -> dict[str, float]:
        """Compute Squeeze-Evolve style fitness signal from HolisticElection scores.

        The fitness signal combines:
        - Quality score (primary — "how good is this likely to be?")
        - Confidence derived from score distribution (variance = uncertainty)
        - Cost adjusted by quality (marginal utility of expensive models)

        Returns {model_name: fitness} where higher = easier (use cheaper model).
        """
        if not scores:
            return {}

        fitness_map = {}
        for name, sc in scores.items():
            quality = sc.quality_score
            holistic = sc.holistic_total

            score_array = np.array([
                sc.quality_score, sc.latency_score, sc.cost_score,
                sc.capability_score, sc.cache_score, sc.sticky_score,
            ])
            score_variance = float(np.var(score_array))
            confidence = 1.0 / (1.0 + score_variance * 10)

            cost_penalty = 0.0 if sc.is_free else min(1.0, sc.cost_per_1k / 10.0)
            cost_adjusted = quality * (1.0 - cost_penalty * 0.3)

            # Wider spread: amplify differences between high and low quality
            fitness = (
                cost_adjusted * 0.5 +
                confidence * 0.3 +
                holistic * 0.2
            )
            # Sigmoid stretch for wider dynamic range
            fitness = 1.0 / (1.0 + math.exp(-(fitness - 0.5) * 8))
            fitness_map[name] = min(1.0, max(0.0, fitness))

        return fitness_map

    async def route(
        self, task_desc: str, task_id: str = "",
        candidate_scores: dict[str, FitnessScore] = None,
        task_complexity: float = 0.5,
    ) -> FitnessDecision:
        """Execute fitness-based routing decision.

        Pipeline:
        1. Compute fitness for each candidate
        2. Select best candidate (highest fitness)
        3. Classify into tier based on adaptive thresholds
        4. Route to appropriate model class
        """
        if task_id == "":
            task_id = f"task_{int(time.time())}_{hash(task_desc) % 10000}"

        scores = candidate_scores or {}

        # Step 1: Compute fitness
        fitness_map = self.compute_fitness(scores)

        if not fitness_map:
            # No candidates — use complexity heuristic
            best_model = "deepseek/deepseek-v4-pro" if task_complexity > 0.6 else "deepseek/deepseek-v4-flash"
            return FitnessDecision(
                task_id=task_id, task_desc=task_desc,
                selected_model=best_model, tier="pro" if task_complexity > 0.6 else "flash",
                fitness=0.5, routing_reason="no_candidates_fallback",
            )

        # Step 2: Select best candidate by fitness
        best_name = max(fitness_map, key=fitness_map.get)
        best_fitness = fitness_map[best_name]
        best_score = scores.get(best_name)

        # Step 3: Tier classification
        tier, reason = self._classify_tier(best_fitness, best_score)

        # Step 4: Map tier to model class
        model_mapping = self._map_tier_to_model(best_name, tier, scores)

        # Step 5: Economic estimation
        est_cost = (best_score.cost_per_1k / 1000) * 5000 if best_score else 0.01
        est_tokens = 5000

        decision = FitnessDecision(
            task_id=task_id, task_desc=task_desc,
            selected_model=model_mapping,
            tier=tier,
            fitness=best_fitness,
            confidence=best_score.quality_score if best_score else 0.5,
            candidate_scores=scores,
            estimated_cost_yuan=est_cost,
            estimated_tokens=est_tokens,
            threshold_low=self._threshold_low,
            threshold_high=self._threshold_high,
            routing_reason=reason,
        )

        # Track
        self._decisions.append(decision)
        self._decision_count += 1
        self._tier_stats[tier]["decisions"] += 1

        # Adaptive threshold update
        if self._decision_count % ADAPT_INTERVAL == 0:
            await self._adapt_thresholds()

        return decision

    def _classify_tier(self, fitness: float, score: Optional[FitnessScore]) -> tuple[str, str]:
        """Classify fitness into routing tier using adaptive thresholds.

        From Squeeze-Evolve:
        - Low fitness → hard task → pro model (high capability, high cost)
        - High fitness → easy task → flash model (low cost)
        - Consensus (very high fitness + high quality) → skip model call
        """
        # Consensus detection: all scores aligned → skip model call
        if score and score.quality_score > CONSENSUS_THRESHOLD and fitness > 0.85:
            return "skip", "consensus_detected_all_scores_aligned"

        # Tier routing based on adaptive thresholds
        if fitness < self._threshold_low:
            return "pro", f"fitness_{fitness:.2f}_below_low_{self._threshold_low:.2f}"
        elif fitness < self._threshold_high:
            return "mid", f"fitness_{fitness:.2f}_between_thresholds"
        else:
            return "flash", f"fitness_{fitness:.2f}_above_high_{self._threshold_high:.2f}"

    def _map_tier_to_model(
        self, best_name: str, tier: str, scores: dict[str, FitnessScore],
    ) -> str:
        """Map routing tier to specific model name.

        Strategy:
        - pro tier → return the best model as-is (highest quality)
        - mid tier → try to find a balanced alternative
        - flash tier → find the cheapest model with acceptable quality
        - skip tier → return the best model (but caller should skip inference)
        """
        if tier == "pro":
            return best_name

        if tier == "mid":
            # Find a model with good quality but lower cost
            candidates = sorted(
                scores.items(),
                key=lambda x: x[1].quality_score * 0.6 + x[1].cost_score * 0.4,
                reverse=True,
            )
            for name, sc in candidates:
                if sc.cost_per_1k < (scores[best_name].cost_per_1k if best_name in scores else 100):
                    return name
            return best_name

        if tier == "flash":
            # Find the cheapest model
            candidates = sorted(scores.items(), key=lambda x: x[1].cost_per_1k)
            for name, sc in candidates:
                if sc.quality_score > 0.3:  # Minimum quality threshold
                    return name
            # Fallback to free models
            for name, sc in candidates:
                if sc.is_free:
                    return name
            return candidates[0][0] if candidates else best_name

        if tier == "skip":
            # Return best model but mark as skippable
            free_candidates = [n for n, sc in scores.items() if sc.is_free]
            return free_candidates[0] if free_candidates else best_name

        return best_name

    async def record_outcome(
        self, task_id: str, success: bool, actual_cost: float = 0.0,
        actual_tokens: int = 0,
    ):
        """Record actual outcome — used for adaptive threshold tuning."""
        # Find the decision
        for d in self._decisions:
            if d.task_id == task_id:
                if success:
                    self._tier_stats[d.tier]["successes"] += 1
                self._tier_stats[d.tier]["total_cost"] += actual_cost
                self._tier_stats[d.tier]["total_tokens"] += actual_tokens
                break

    async def _adapt_thresholds(self):
        """Adapt percentile thresholds based on observed tier performance.

        Goal: maximize success rate while minimizing cost.
        - If pro tier has very high success → shift low threshold down (use pro less)
        - If flash tier has low success → shift high threshold up (use flash less)
        - Uses exponential moving average of success rates per tier
        """
        pro_stats = self._tier_stats["pro"]
        flash_stats = self._tier_stats["flash"]

        pro_success = (
            pro_stats["successes"] / max(pro_stats["decisions"], 1)
        )
        flash_success = (
            flash_stats["successes"] / max(flash_stats["decisions"], 1)
        )

        # If pro is very successful (can afford to use less)
        if pro_success > 0.95 and pro_stats["decisions"] > 10:
            self._threshold_low = max(0.1, self._threshold_low - LEARNING_RATE * 0.5)
            logger.debug("FitnessRouter: lowered pro threshold → %.2f (pro success=%.0f%%)",
                        self._threshold_low, pro_success * 100)

        # If flash is struggling (need to route more to pro)
        if flash_success < 0.7 and flash_stats["decisions"] > 10:
            self._threshold_high = min(0.9, self._threshold_high + LEARNING_RATE)
            logger.debug("FitnessRouter: raised flash threshold → %.2f (flash success=%.0f%%)",
                        self._threshold_high, flash_success * 100)

        # Normal bounds
        self._threshold_low = max(0.1, min(0.5, self._threshold_low))
        self._threshold_high = max(0.5, min(0.9, self._threshold_high))

    def get_cost_savings(self) -> dict:
        """Estimate cost savings vs uniform pro model usage."""
        total_cost = sum(s["total_cost"] for s in self._tier_stats.values())
        total_decisions = max(sum(s["decisions"] for s in self._tier_stats.values()), 1)
        hypothetical_pro_cost = total_decisions * 0.01  # Assume pro costs 0.01/task

        return {
            "actual_cost": round(total_cost, 4),
            "hypothetical_pro_cost": round(hypothetical_pro_cost, 4),
            "savings_ratio": round(1.0 - total_cost / max(hypothetical_pro_cost, 0.0001), 2),
            "tier_distribution": {
                tier: {
                    "decisions": s["decisions"],
                    "success_rate": round(s["successes"] / max(s["decisions"], 1), 2),
                    "avg_cost": round(s["total_cost"] / max(s["decisions"], 1), 4),
                }
                for tier, s in self._tier_stats.items()
                if s["decisions"] > 0
            },
        }

    def get_stats(self) -> dict:
        savings = self.get_cost_savings()
        return {
            "total_decisions": self._decision_count,
            "threshold_low": round(self._threshold_low, 3),
            "threshold_high": round(self._threshold_high, 3),
            "window_size": len(self._decisions),
            "cost_savings": savings,
            "recent_decisions": [
                {"task": d.task_desc[:40], "tier": d.tier, "model": d.selected_model.split("/")[-1][:20],
                 "fitness": round(d.fitness, 2), "reason": d.routing_reason[:40]}
                for d in list(self._decisions)[-5:]
            ],
        }

    def save_state(self):
        try:
            data = {
                "threshold_low": self._threshold_low,
                "threshold_high": self._threshold_high,
                "decision_count": self._decision_count,
                "tier_stats": self._tier_stats,
            }
            FITNESS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            FITNESS_CACHE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.debug("FitnessRouter save: %s", e)

    def _load_state(self):
        if not FITNESS_CACHE.exists():
            return
        try:
            data = json.loads(FITNESS_CACHE.read_text())
            self._threshold_low = data.get("threshold_low", LOW_FITNESS_PCT / 100.0)
            self._threshold_high = data.get("threshold_high", HIGH_FITNESS_PCT / 100.0)
            self._decision_count = data.get("decision_count", 0)
            for tier, stats in data.get("tier_stats", {}).items():
                if tier in self._tier_stats:
                    self._tier_stats[tier].update(stats)
        except Exception as e:
            logger.debug("FitnessRouter load: %s", e)


_fitness_router: Optional[FitnessRouter] = None


def get_fitness_router() -> FitnessRouter:
    global _fitness_router
    if _fitness_router is None:
        _fitness_router = FitnessRouter()
    return _fitness_router
