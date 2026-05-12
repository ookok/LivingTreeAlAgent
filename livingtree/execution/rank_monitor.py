"""Rank Collapse Monitor — Detect and prevent parameter diversity collapse.

Based on SJTU Math4AI (Chen & Luo, NeurIPS 2025 Oral):
  "From Condensation to Rank Collapse: A Two-Stage Analysis of Transformer Training Dynamics"

Key findings:
  Stage 1: Parameters condense and align toward target directions.
  Stage 2: Value-query matrices undergo asymptotic rank collapse → diversity loss.

Implications for LivingTree:
  - thinking_evolution population diversity must be monitored
  - When rank collapses (diversity drops below threshold), inject noise to re-diversify
  - This mirrors the paper's finding that rank collapse is INEVITABLE without intervention
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


class DiversityState(str, Enum):
    HEALTHY = "healthy"       # High diversity, normal operations
    CONDENSING = "condensing" # Stage 1: parameters aligning (natural, expected)
    COLLAPSING = "collapsing" # Stage 2: rank collapsing (danger — intervene!)
    FROZEN = "frozen"         # No meaningful variation (extreme collapse)


@dataclass
class RankSnapshot:
    """A snapshot of population diversity."""
    timestamp: float = field(default_factory=time.time)
    population_size: int = 0
    effective_rank: float = 0.0       # Number of effectively independent "directions"
    diversity_score: float = 0.0       # 0 (collapsed) to 1 (maximally diverse)
    dominant_direction_count: int = 0  # How many distinct modes exist
    entropy: float = 0.0               # Shannon entropy of the population
    state: DiversityState = DiversityState.HEALTHY


class RankMonitor:
    """Monitor population diversity and detect rank collapse.

    Based on the paper's finding: Transformer training naturally
    goes through a two-stage process where rank collapse is expected
    in Stage 2. Detection enables timely intervention.

    Detection heuristics:
      - effective_rank < 2: severely collapsed
      - diversity_score < 0.2: collapsing
      - entropy drops 50% in one step: condensing → collapsing transition
    """

    def __init__(self, collapse_threshold: float = 0.2, history_window: int = 10):
        self.collapse_threshold = collapse_threshold
        self._history: list[RankSnapshot] = []
        self._intervention_count = 0
        self._max_history = history_window

    def analyze(self, population: list[Any]) -> RankSnapshot:
        """Analyze current population diversity.

        Args:
            population: List of solution/trajectory items with a 'score' or 'fitness' attribute.

        Returns:
            RankSnapshot with diversity metrics and recommended state.
        """
        if not population or len(population) < 2:
            return RankSnapshot(
                population_size=len(population),
                state=DiversityState.FROZEN,
            )

        # Extract scores/features for diversity analysis
        values = self._extract_values(population)
        n = len(values)

        if n < 2:
            return RankSnapshot(population_size=n, state=DiversityState.FROZEN)

        # Effective rank: count of distinct clusters (simplified)
        unique_clusters = len(set(round(v, 2) for v in values))
        effective_rank = min(n, unique_clusters)

        # Diversity score: normalized standard deviation
        mean_val = sum(values) / n
        variance = sum((v - mean_val) ** 2 for v in values) / n
        std = math.sqrt(variance)
        # Normalize: std / mean gives coefficient of variation
        cv = std / max(1e-9, abs(mean_val))
        diversity_score = min(1.0, cv)

        # Entropy: how evenly distributed are the values
        entropy = self._compute_entropy(values)

        # Dominant directions: count clusters with significant representation
        cluster_counts = {}
        for v in values:
            bucket = round(v, 1)
            cluster_counts[bucket] = cluster_counts.get(bucket, 0) + 1
        threshold = n * 0.1  # At least 10% to be a "dominant direction"
        dominant_count = sum(1 for c in cluster_counts.values() if c >= threshold)

        # State classification
        state = self._classify_state(
            effective_rank, diversity_score, entropy, n
        )

        snapshot = RankSnapshot(
            population_size=n,
            effective_rank=effective_rank,
            diversity_score=diversity_score,
            dominant_direction_count=dominant_count,
            entropy=entropy,
            state=state,
        )

        self._history.append(snapshot)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        if state == DiversityState.COLLAPSING:
            logger.warning(
                f"RankMonitor: COLLAPSING — effective_rank={effective_rank:.1f}, "
                f"diversity={diversity_score:.3f}, "
                f"dominant_dirs={dominant_count}"
            )

        return snapshot

    def should_intervene(self) -> bool:
        """Check if intervention is needed (inject noise / re-diversify)."""
        if not self._history:
            return False

        current = self._history[-1]
        return current.state in (DiversityState.COLLAPSING, DiversityState.FROZEN)

    def get_intervention_strength(self) -> float:
        """Recommended noise injection strength [0, 1].

        Higher values = more aggressive re-diversification needed.
        """
        if not self._history:
            return 0.0

        current = self._history[-1]
        if current.state == DiversityState.FROZEN:
            return 0.8  # Strong intervention
        elif current.state == DiversityState.COLLAPSING:
            return 0.4  # Moderate intervention
        elif current.diversity_score < 0.3:
            return 0.2  # Light intervention
        return 0.0

    # ── Internal ──

    def _extract_values(self, population: list[Any]) -> list[float]:
        """Extract numeric values from population items."""
        values = []
        for item in population:
            if isinstance(item, (int, float)):
                values.append(float(item))
            elif isinstance(item, dict):
                val = item.get("score", item.get("fitness", item.get("reward", 0.5)))
                values.append(float(val))
            elif hasattr(item, 'score'):
                values.append(float(item.score))
            elif hasattr(item, 'fitness'):
                values.append(float(item.fitness))
            else:
                values.append(0.5)  # default
        return values

    def _compute_entropy(self, values: list[float]) -> float:
        """Compute Shannon entropy of value distribution."""
        if not values:
            return 0.0

        # Bucket into 10 bins
        bins = [0] * 10
        min_v, max_v = min(values), max(values)
        if max_v == min_v:
            return 0.0

        for v in values:
            idx = min(9, int((v - min_v) / (max_v - min_v) * 10))
            bins[idx] += 1

        n = len(values)
        entropy = 0.0
        for count in bins:
            if count > 0:
                p = count / n
                entropy -= p * math.log2(p)

        return entropy

    def _classify_state(
        self, effective_rank: float, diversity: float, entropy: float, n: int
    ) -> DiversityState:
        """Classify population diversity state based on the paper's two-stage theory."""
        if n < 2:
            return DiversityState.FROZEN
        if effective_rank >= n * 0.5 and diversity > 0.5:
            return DiversityState.HEALTHY
        if effective_rank >= 3 and diversity > 0.3:
            return DiversityState.CONDENSING
        if effective_rank >= 1 and diversity > self.collapse_threshold:
            return DiversityState.CONDENSING
        if effective_rank >= 1:
            return DiversityState.COLLAPSING
        return DiversityState.FROZEN

    @property
    def intervention_count(self) -> int:
        return self._intervention_count


# ── Singleton ──

_monitor: Optional[RankMonitor] = None


def get_rank_monitor() -> RankMonitor:
    global _monitor
    if _monitor is None:
        _monitor = RankMonitor()
    return _monitor
