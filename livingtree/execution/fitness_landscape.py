"""FitnessLandscape — Multi-objective Pareto frontier for execution trajectories.

Inspired by de novo protein design's fitness landscape concept:
just as protein designers navigate the sequence→structure→function landscape
to find Pareto-optimal designs (balancing stability, affinity, solubility),
this module navigates the tool_sequence→execution_outcome landscape to find
Pareto-optimal execution trajectories (balancing reliability, cost, speed, safety).

Key operations:
  - Pareto dominance: A dominates B if A ≥ B in all dimensions, > B in at least one
  - Front extraction: filter all trajectories to the non-dominated set
  - Navigation: given a proposed tool sequence, find similar successful paths

Usage:
    landscape = get_fitness_landscape()
    landscape.record(trajectory_id, tools, tokens, ms, success, violations, summary)
    best = landscape.find_best(weights={"reliability": 0.5, "speed": 0.3})
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class FitnessVector:
    """Multi-dimensional fitness score for an execution trajectory.

    All dimensions range 0-1, where higher = better.
    Cost and time are inverted/negated so "more is better".
    """
    reliability: float = 0.5     # 0-1, success rate
    cost_efficiency: float = 0.5  # 0-1, less cost = higher
    speed: float = 0.5           # 0-1, faster = higher
    safety: float = 0.5          # 0-1, fewer violations = higher

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.reliability, self.cost_efficiency, self.speed, self.safety)

    def dominates(self, other: FitnessVector) -> bool:
        """Check if self Pareto-dominates other.

        A dominates B if A ≥ B in ALL dimensions AND A > B in at least one.
        """
        a = self.as_tuple()
        b = other.as_tuple()
        all_ge = all(ai >= bi for ai, bi in zip(a, b))
        any_gt = any(ai > bi for ai, bi in zip(a, b))
        return all_ge and any_gt

    @staticmethod
    def from_raw(
        success: bool, total_tokens: int, total_ms: int,
        safety_violations: int,
    ) -> FitnessVector:
        """Compute FitnessVector from raw execution metrics."""
        # Reliability: binary (can be extended with partial success)
        reliability = 1.0 if success else 0.0

        # Cost efficiency: fewer tokens = higher score, cap at 1.0
        cost_efficiency = min(1.0, 10000.0 / max(total_tokens, 1))

        # Speed: faster = higher, normalize to 0-1 (cap at 120s = 0, 0s = 1)
        speed = max(0.0, 1.0 - total_ms / 120_000.0)
        # clamp
        speed = max(0.0, min(1.0, speed))

        # Safety: each violation deducts 0.2
        safety = max(0.0, 1.0 - safety_violations * 0.2)

        return FitnessVector(
            reliability=round(reliability, 3),
            cost_efficiency=round(cost_efficiency, 3),
            speed=round(speed, 3),
            safety=round(safety, 3),
        )

    def weighted_score(self, weights: dict[str, float] | None = None) -> float:
        """Compute weighted aggregate score."""
        if weights is None:
            weights = {"reliability": 0.4, "speed": 0.3, "safety": 0.2, "cost_efficiency": 0.1}
        total = 0.0
        total += self.reliability * weights.get("reliability", 0.0)
        total += self.cost_efficiency * weights.get("cost_efficiency", 0.0)
        total += self.speed * weights.get("speed", 0.0)
        total += self.safety * weights.get("safety", 0.0)
        return round(total, 4)

    def distance_to_utopia(self) -> float:
        """Euclidean distance to the ideal point (1, 1, 1, 1)."""
        return math.sqrt(
            (1.0 - self.reliability) ** 2 +
            (1.0 - self.cost_efficiency) ** 2 +
            (1.0 - self.speed) ** 2 +
            (1.0 - self.safety) ** 2
        )


@dataclass
class TrajectoryScore:
    """A scored execution trajectory."""
    trajectory_id: str
    fitness: FitnessVector = field(default_factory=FitnessVector)
    tool_sequence: list[str] = field(default_factory=list)
    summary: str = ""
    total_tokens: int = 0
    total_ms: int = 0

    @property
    def is_pareto_optimal(self) -> bool:
        """Whether this trajectory is on the Pareto front (set by landscape)."""
        return self._pareto_optimal

    _pareto_optimal: bool = field(default=False, repr=False)


class FitnessLandscape:
    """Multi-objective fitness landscape for execution trajectory optimization.

    Tracks all recorded trajectories and supports Pareto-front extraction
    and nearest-neighbor navigation for recommending optimal tool sequences.
    """

    def __init__(self):
        self._trajectories: dict[str, TrajectoryScore] = {}
        self._record_count = 0

    # ── Recording ─────────────────────────────────────────────────

    def record(
        self,
        trajectory_id: str,
        tool_sequence: list[str],
        total_tokens: int,
        total_ms: int,
        success: bool,
        safety_violations: int = 0,
        summary: str = "",
    ) -> TrajectoryScore:
        """Record an execution trajectory and compute its fitness.

        Args:
            trajectory_id: Unique identifier for this trajectory.
            tool_sequence: Ordered list of tools used.
            total_tokens: Total tokens consumed.
            total_ms: Total execution time in milliseconds.
            success: Whether the task completed successfully.
            safety_violations: Number of safety violations detected.
            summary: Human-readable summary of the outcome.
        """
        fitness = FitnessVector.from_raw(
            success, total_tokens, total_ms, safety_violations)
        score = TrajectoryScore(
            trajectory_id=trajectory_id,
            fitness=fitness,
            tool_sequence=tool_sequence,
            summary=summary,
            total_tokens=total_tokens,
            total_ms=total_ms,
        )
        self._trajectories[trajectory_id] = score
        self._record_count += 1
        logger.debug(
            f"FitnessLandscape: recorded '{trajectory_id}' "
            f"(reliability={fitness.reliability}, speed={fitness.speed:.2f})")
        return score

    # ── Pareto Front ──────────────────────────────────────────────

    def get_pareto_front(self) -> list[TrajectoryScore]:
        """Return all non-dominated trajectories (the Pareto frontier).

        O(n²) pairwise comparison. For large n, consider approximate front.
        """
        all_scores = list(self._trajectories.values())
        if not all_scores:
            return []

        front: list[TrajectoryScore] = []
        for score in all_scores:
            dominated = False
            for other in all_scores:
                if other.trajectory_id == score.trajectory_id:
                    continue
                if other.fitness.dominates(score.fitness):
                    dominated = True
                    break
            if not dominated:
                score._pareto_optimal = True
                front.append(score)

        logger.info(
            f"Pareto front: {len(front)}/{len(all_scores)} trajectories "
            f"({len(front) / max(len(all_scores), 1):.0%})")
        return front

    # ── Best Selection ────────────────────────────────────────────

    def find_best(
        self, weights: dict[str, float] | None = None,
        prefer_pareto: bool = True,
    ) -> TrajectoryScore | None:
        """Find the best trajectory by weighted score or utopia distance.

        Args:
            weights: Dimension weights for weighted_sum scoring.
                     Default: reliability=0.4, speed=0.3, safety=0.2, cost=0.1
            prefer_pareto: If True, only consider Pareto-front trajectories.

        Returns:
            Best TrajectoryScore or None if no trajectories recorded.
        """
        candidates = self.get_pareto_front() if prefer_pareto else list(
            self._trajectories.values())
        if not candidates:
            return None

        if weights:
            best = max(candidates, key=lambda s: s.fitness.weighted_score(weights))
        else:
            best = min(candidates, key=lambda s: s.fitness.distance_to_utopia())

        return best

    # ── Navigation ────────────────────────────────────────────────

    def recommend_for(
        self, tool_sequence: list[str], k: int = 3,
    ) -> list[TrajectoryScore]:
        """Find k most similar historical trajectories for a proposed sequence.

        Similarity = Jaccard coefficient on tool sets + prefix match bonus.
        """
        if not self._trajectories:
            return []

        query_set = set(tool_sequence)

        def similarity(ts: TrajectoryScore) -> float:
            hist_set = set(ts.tool_sequence)
            if not query_set or not hist_set:
                return 0.0

            # Jaccard
            jaccard = len(query_set & hist_set) / len(query_set | hist_set)

            # Prefix match bonus
            prefix_len = 0
            for qt, ht in zip(tool_sequence, ts.tool_sequence):
                if qt == ht:
                    prefix_len += 1
                else:
                    break
            prefix_bonus = prefix_len / max(len(tool_sequence), 1) * 0.3

            return jaccard + prefix_bonus

        ranked = sorted(
            self._trajectories.values(),
            key=lambda ts: similarity(ts),
            reverse=True,
        )
        return ranked[:k]

    def most_reliable_for_tools(
        self, tools: list[str], k: int = 3,
    ) -> list[TrajectoryScore]:
        """Find top trajectories that used these specific tools."""
        tool_set = set(tools)
        matching = [
            ts for ts in self._trajectories.values()
            if tool_set.issubset(set(ts.tool_sequence))
        ]
        matching.sort(key=lambda ts: ts.fitness.weighted_score(), reverse=True)
        return matching[:k]

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Aggregate statistics across all trajectories."""
        scores = list(self._trajectories.values())
        if not scores:
            return {"count": 0}

        avg_rel = sum(s.fitness.reliability for s in scores) / len(scores)
        avg_speed = sum(s.fitness.speed for s in scores) / len(scores)
        avg_safety = sum(s.fitness.safety for s in scores) / len(scores)
        avg_cost = sum(s.fitness.cost_efficiency for s in scores) / len(scores)

        best = max(scores, key=lambda s: s.fitness.weighted_score())
        worst = min(scores, key=lambda s: s.fitness.weighted_score())

        return {
            "count": len(scores),
            "record_count": self._record_count,
            "avg_reliability": round(avg_rel, 3),
            "avg_speed": round(avg_speed, 3),
            "avg_safety": round(avg_safety, 3),
            "avg_cost_efficiency": round(avg_cost, 3),
            "pareto_front_size": len(self.get_pareto_front()),
            "best_trajectory": best.trajectory_id if best else None,
            "worst_trajectory": worst.trajectory_id if worst else None,
            "best_score": best.fitness.weighted_score() if best else 0,
        }


# ── Singleton ────────────────────────────────────────────────────

_fitness_landscape: FitnessLandscape | None = None


def get_fitness_landscape() -> FitnessLandscape:
    """Get or create the singleton FitnessLandscape."""
    global _fitness_landscape
    if _fitness_landscape is None:
        _fitness_landscape = FitnessLandscape()
    return _fitness_landscape


def reset_fitness_landscape() -> None:
    """Test helper."""
    global _fitness_landscape
    _fitness_landscape = None
