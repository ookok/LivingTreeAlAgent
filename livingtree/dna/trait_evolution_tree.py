"""Trait Evolution Tree — track and visualize SelfModel trait growth over time.

Snapshots the 7 core traits of PhenomenalConsciousness._self at each generation,
building a longitudinal record that reveals growth trajectories, regressions,
and stable periods. This provides a quantitative foundation for emergence
detection and self-narrative continuity.

Architecture:
    snapshot(phenomenal_consciousness) →
        ├─ Extract SelfModel.generation + traits dict
        ├─ Append to FIFO history (max 500)
        └─ Return snapshot dict

    get_growth_summary() →
        ├─ Compare earliest vs latest snapshot
        ├─ Compute deltas for each trait
        └─ Return human-readable growth narrative

    get_trait_timeline(name) →
        └─ Chronological list of trait values across all snapshots

Integration:
    tet = get_trait_evolution_tree()
    tet.snapshot(pc)  # call after each generation cycle
    summary = tet.get_growth_summary()
    curiosity_timeline = tet.get_trait_timeline("curiosity")
    stats = tet.stats()

Related modules:
    - phenomenal_consciousness.py — SelfModel with 7-core-trait structure
    - consciousness_emergence.py — emergence detection via trait drift
    - self_narrative.py — autobiographic continuity from trait history
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══ Data Types ═══


@dataclass
class TraitSnapshot:
    """A single point-in-time capture of the SelfModel traits."""
    generation: int
    traits: dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    identity_id: str = ""

    def summary(self) -> str:
        traits_str = ", ".join(
            f"{k}={v:.2f}" for k, v in sorted(self.traits.items())
        )
        return (
            f"TraitSnapshot(gen={self.generation}, "
            f"traits=[{traits_str}])"
        )

    def trait_vector(self) -> list[float]:
        """Return traits as an ordered vector (alphabetical by key)."""
        return [self.traits[k] for k in sorted(self.traits)]


@dataclass
class GrowthReport:
    """Analysis of trait evolution between two points in time."""
    first_gen: int
    last_gen: int
    span: int
    trait_deltas: dict[str, float] = field(default_factory=dict)
    trait_directions: dict[str, str] = field(default_factory=dict)
    significant_changes: list[str] = field(default_factory=list)
    stable_traits: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = []
        if self.significant_changes:
            parts.append(f"Growth: {', '.join(self.significant_changes[:5])}")
        if self.stable_traits:
            parts.append(f"Stable: {', '.join(self.stable_traits)}")
        return f"GrowthReport(gen {self.first_gen}→{self.last_gen}, span={self.span}) " + "; ".join(parts)


# ═══ Trait Evolution Tree ═══


class TraitEvolutionTree:
    """Longitudinal tracker for SelfModel trait evolution.

    Takes snapshots of the 7 core traits (curiosity, caution, creativity,
    persistence, openness, precision, empathy) at each generation cycle,
    enabling temporal analysis of personality growth and emergence.

    The name "tree" reflects the branching nature of trait evolution:
    each trait independently grows, stabilizes, or regresses, and the
    history forms a multi-dimensional trajectory through personality space.

    Usage:
        tet = get_trait_evolution_tree()
        tet.snapshot(phenomenal_consciousness)  # call each generation
        report = tet.analyze_growth()
        timeline = tet.get_trait_timeline("creativity")
        print(tet.get_growth_summary())
    """

    _MAX_HISTORY: int = 500
    _MIN_SPAN_FOR_ANALYSIS: int = 2
    _MIN_DELTA_SIGNIFICANT: float = 0.05
    _MAX_SUMMARY_TRAITS: int = 7

    def __init__(self) -> None:
        self._history: deque[TraitSnapshot] = deque(maxlen=self._MAX_HISTORY)
        self._first_snapshot_time: float = 0.0
        self._last_snapshot_time: float = 0.0
        self._total_snapshots: int = 0

    # ── Snapshot ───────────────────────────────────────────────────

    def snapshot(self, phenomenal_consciousness: Any) -> dict:
        """Capture the current state of the SelfModel traits.

        Args:
            phenomenal_consciousness: The PhenomenalConsciousness instance
                                      holding the SelfModel (_self).

        Returns:
            {
                "captured": bool,
                "generation": int,
                "traits": dict[str, float],
                "total_snapshots": int,
            }
        """
        if not phenomenal_consciousness:
            logger.debug("TraitEvolutionTree: no consciousness to snapshot")
            return {"captured": False, "generation": 0, "traits": {}, "total_snapshots": len(self._history)}

        sm = getattr(phenomenal_consciousness, "_self", None)
        if sm is None:
            logger.debug("TraitEvolutionTree: no self-model on consciousness")
            return {"captured": False, "generation": 0, "traits": {}, "total_snapshots": len(self._history)}

        traits = getattr(sm, "traits", {})
        if not traits:
            logger.debug("TraitEvolutionTree: self-model has no traits")
            return {"captured": False, "generation": sm.generation, "traits": {}, "total_snapshots": len(self._history)}

        identity_id = getattr(sm, "identity_id", "")
        generation = getattr(sm, "generation", 0)

        snap = TraitSnapshot(
            generation=generation,
            traits=dict(traits),
            identity_id=identity_id,
        )
        self._history.append(snap)
        t = time.time()
        self._last_snapshot_time = t
        if self._first_snapshot_time == 0.0:
            self._first_snapshot_time = t
        self._total_snapshots += 1

        logger.debug(
            f"TraitEvolutionTree: snapshot #{self._total_snapshots} — "
            f"gen={generation}, traits={len(traits)}"
        )

        return {
            "captured": True,
            "generation": generation,
            "traits": dict(traits),
            "total_snapshots": len(self._history),
        }

    # ── Growth analysis ────────────────────────────────────────────

    def get_growth_summary(self) -> str:
        """Generate a human-readable growth narrative.

        Compares the earliest and latest snapshots to describe how each
        of the 7 core traits has evolved.

        Returns:
            A natural-language summary like:
            "Growth from gen 0 to 42: curiosity: 0.7→0.9 (↑0.2);
             caution: 0.5→0.3 (↓0.2); openness: 0.8→0.9 (↑0.1)"
        """
        if len(self._history) < self._MIN_SPAN_FOR_ANALYSIS:
            return "No growth data yet — at least 2 snapshots needed."

        first = self._history[0]
        last = self._history[-1]

        if first.generation == last.generation:
            return f"Still at generation {first.generation} — no growth yet."

        changes: list[str] = []
        for trait, end_value in sorted(last.traits.items()):
            start_value = first.traits.get(trait, 0.5)
            delta = end_value - start_value
            if abs(delta) > self._MIN_DELTA_SIGNIFICANT:
                direction = "+" if delta > 0 else ""
                changes.append(
                    f"{trait}: {start_value:.2f}→{end_value:.2f} "
                    f"({direction}{delta:+.2f})"
                )

        if not changes:
            return (
                f"Growth from gen {first.generation} to {last.generation}: "
                f"all traits stable (Δ < {self._MIN_DELTA_SIGNIFICANT:.2f})"
            )

        trait_list = "; ".join(changes[:self._MAX_SUMMARY_TRAITS])
        return (
            f"Growth from gen {first.generation} to {last.generation}: "
            f"{trait_list}"
        )

    def analyze_growth(self) -> GrowthReport:
        """Statistical analysis of trait evolution.

        Returns a GrowthReport with per-trait deltas, directions,
        and lists of significantly changed vs. stable traits.
        """
        if len(self._history) < self._MIN_SPAN_FOR_ANALYSIS:
            return GrowthReport(
                first_gen=0,
                last_gen=0,
                span=0,
            )

        first = self._history[0]
        last = self._history[-1]

        deltas: dict[str, float] = {}
        directions: dict[str, str] = {}
        significant: list[str] = []
        stable: list[str] = []

        for trait, end_value in sorted(last.traits.items()):
            start_value = first.traits.get(trait, 0.5)
            delta = end_value - start_value
            deltas[trait] = delta

            if abs(delta) > self._MIN_DELTA_SIGNIFICANT:
                directions[trait] = "up" if delta > 0 else "down"
                direction_symbol = "+" if delta > 0 else ""
                significant.append(
                    f"{trait}: {direction_symbol}{delta:+.2f}"
                )
            else:
                directions[trait] = "stable"
                stable.append(trait)

        span = last.generation - first.generation

        return GrowthReport(
            first_gen=first.generation,
            last_gen=last.generation,
            span=span,
            trait_deltas=deltas,
            trait_directions=directions,
            significant_changes=significant,
            stable_traits=stable,
        )

    def get_trait_timeline(self, trait_name: str) -> list[float]:
        """Extract chronological values for a single trait across all snapshots.

        Args:
            trait_name: One of the 7 core trait names (e.g., "curiosity").

        Returns:
            List of float values in chronological order.
            Empty list if the trait has never been recorded.
        """
        values: list[float] = []
        for snap in self._history:
            val = snap.traits.get(trait_name)
            if val is not None:
                values.append(val)
        return values

    def get_all_trait_names(self) -> list[str]:
        """Return the list of trait names found in snapshots."""
        if not self._history:
            return []
        return sorted(self._history[-1].traits.keys())

    # ── Trend detection ────────────────────────────────────────────

    def get_trend(self, trait_name: str, window: int = 10) -> str:
        """Classify the recent trend for a trait.

        Uses simple linear regression on the last `window` snapshots
        to determine if the trait is rising, falling, or stable.

        Returns:
            "rising", "falling", "stable", or "insufficient_data"
        """
        timeline = self.get_trait_timeline(trait_name)
        if len(timeline) < 3:
            return "insufficient_data"

        recent = timeline[-window:] if len(timeline) >= window else timeline
        if len(recent) < 3:
            return "insufficient_data"

        # Simple linear regression slope
        n = len(recent)
        x_mean = (n - 1) / 2
        y_mean = sum(recent) / n
        numerator = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return "stable"

        slope = numerator / denominator

        if slope > 0.005:
            return "rising"
        elif slope < -0.005:
            return "falling"
        else:
            return "stable"

    def get_all_trends(self, window: int = 10) -> dict[str, str]:
        """Get trend classification for all tracked traits."""
        trends: dict[str, str] = {}
        for name in self.get_all_trait_names():
            trends[name] = self.get_trend(name, window)
        return trends

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return summary statistics for the trait evolution tree."""
        report = self.analyze_growth()
        return {
            "total_snapshots": self._total_snapshots,
            "history_size": len(self._history),
            "trait_names": self.get_all_trait_names(),
            "first_generation": report.first_gen,
            "last_generation": report.last_gen,
            "span": report.span,
            "first_snapshot_time": self._first_snapshot_time,
            "last_snapshot_time": self._last_snapshot_time,
            "growth_summary": self.get_growth_summary(),
            "trait_deltas": report.trait_deltas,
            "significant_changes": report.significant_changes,
            "stable_traits": report.stable_traits,
            "trends": self.get_all_trends(),
        }

    def history(self) -> list[TraitSnapshot]:
        """Return all stored snapshots in chronological order."""
        return list(self._history)


# ═══ Singleton ═══

_trait_evolution_tree: TraitEvolutionTree | None = None


def get_trait_evolution_tree() -> TraitEvolutionTree:
    """Get or create the global TraitEvolutionTree singleton."""
    global _trait_evolution_tree
    if _trait_evolution_tree is None:
        _trait_evolution_tree = TraitEvolutionTree()
        logger.info("TraitEvolutionTree singleton initialized")
    return _trait_evolution_tree


__all__ = [
    "TraitSnapshot",
    "GrowthReport",
    "TraitEvolutionTree",
    "get_trait_evolution_tree",
]
