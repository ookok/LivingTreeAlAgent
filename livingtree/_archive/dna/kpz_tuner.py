"""KPZ Universality Tuner — dynamical tuning of evolution parameters.

Based on the KPZ (Kardar-Parisi-Zhang) universality class. The key insight:
  swarm learning, genetic evolution, and rule spreading are ALL instances
  of the same universal class — growth processes governed by KPZ dynamics.

KPZ Equation:  ∂h/∂t = ν∇²h + λ(∇h)² + η(x,t)
  h(x,t): "height" (quality score at position x, time t)
  ν: diffusion coefficient (knowledge spread rate)
  λ: nonlinear coupling (innovation amplification)
  η: noise (random exploration)

Universal scaling exponents (2D KPZ):
  Growth exponent β = 1/3
  Roughness exponent α = 1/2
  Dynamic exponent z = 3/2

These exponents are "mathematical fingerprints" — identical across
completely different physical systems. They tell us:
  - W(L,t) ~ t^β: how fast "roughness" (quality variance) grows
  - W_sat ~ L^α: saturation roughness depends on system size
  - t_sat ~ L^z: time to reach saturation

Applied to LivingTree:
  - W(t): variance of rule/proxy/trajectory quality over time
  - L: population size (number of genomes, peers, trajectories)
  - The KPZ exponents tell us WHEN to switch from exploration to exploitation

Usage:
    tuner = KPZTuner(population_size=50)
    strategy = tuner.get_strategy(generation=15, quality_variance=0.3)
    # → KEEP_EXPLORING (quality still growing, β ≈ 1/3 regime)
    # or → SHIFT_TO_EXPLOIT (quality saturated, reached L^α)
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

import numpy as np
import random

KPZ_CACHE = Path(".livingtree/kpz_state.json")


class KpzPhase(Enum):
    GROWING = auto()       # β ≈ 1/3: transient growth, high variance increase
    SATURATING = auto()     # Crossing to saturation
    STEADY = auto()         # L^α regime: system-size-limited roughness
    COLLAPSED = auto()      # Over-exploitation: diversity collapsed
    DIVERGENT = auto()      # Over-exploration: no convergence


class TuningStrategy(Enum):
    EXPLORE_MORE = auto()       # Increase exploration (mutation rate ↑)
    BALANCE = auto()             # Maintain current balance
    EXPLOIT_MORE = auto()        # Increase exploitation (selection pressure ↑)
    INJECT_DIVERSITY = auto()   # Inject random genomes (collapse recovery)
    SLOW_DOWN = auto()           # Reduce learning rate (divergence recovery)
    HOLD = auto()               # No change


@dataclass
class KpzState:
    """Current KPZ state of the evolving system."""
    phase: KpzPhase
    effective_beta: float      # Measured growth exponent
    effective_alpha: float     # Measured roughness exponent
    roughness_W: float         # Current quality variance (RMS)
    saturation_estimate: float # Predicted saturation roughness (L^α)
    time_to_saturation: float  # Estimated steps remaining (L^z)
    quality_trajectory: list[float] = field(default_factory=list)


@dataclass
class KpzTuning:
    """KPZ-guided tuning recommendation."""
    strategy: TuningStrategy
    recommended_mutation_rate: float
    recommended_selection_pressure: float
    recommended_exploration_bonus: float
    phase: KpzPhase
    confidence: float
    reason: str = ""


class KpzMetrics:
    """Compute KPZ universal exponents from quality trajectory data.

    Windowed estimation of growth exponent β, roughness exponent α,
    and dynamic exponent z from the quality time series.

    β: log(W) vs log(t) slope during transient growth
    α: log(W_sat) vs log(L) slope across population sizes  
    z: log(t_sat) vs log(L) slope → z = α/β
    """

    @classmethod
    def estimate_beta(
        cls, quality_history: list[float], window: int = 20,
    ) -> tuple[float, float]:
        """Estimate growth exponent β from recent quality variance.

        W²(t) ~ t^(2β) → log(W) = β·log(t) + const
        """
        if len(quality_history) < window:
            return 0.33, 0.5  # Default KPZ value

        recent = quality_history[-window:]
        # Compute running variance
        variances = []
        for i in range(2, len(recent) + 1):
            subset = recent[:i]
            variances.append(float(np.var(subset)))

        if len(variances) < 3:
            return 0.33, 0.5

        log_t = np.log(np.arange(1, len(variances) + 1))
        log_W = np.log(np.sqrt(np.maximum(variances, 1e-9)))

        # Linear fit: log(W) = β·log(t)
        if len(log_t) > 1:
            beta = float(np.polyfit(log_t, log_W, 1)[0])
            beta = max(0.0, min(1.0, beta))  # Clamp valid range
        else:
            beta = 0.33

        return beta, float(np.std(variances) / (np.mean(variances) + 1e-9))

    @classmethod
    def estimate_roughness(
        cls, population_size: int, quality_variance: float,
    ) -> float:
        """Estimate roughness exponent α: W_sat ~ L^α.

        For known population size L and current saturation W_sat,
        α = log(W_sat) / log(L).
        """
        if population_size < 2 or quality_variance <= 0:
            return 0.5  # Default 2D KPZ value
        return math.log(max(quality_variance, 1e-6)) / math.log(population_size)

    @classmethod
    def estimate_saturation(
        cls, population_size: int, alpha: float,
    ) -> float:
        """Predict saturation roughness: W_sat_pred = L^α."""
        return population_size ** alpha

    @classmethod
    def estimate_time_to_saturation(
        cls, population_size: int, z: float = 1.5,
    ) -> float:
        """Estimate time to saturation: t_sat ~ L^z."""
        return population_size ** z


class KPZTuner:
    """KPZ universality-guided dynamical parameter tuner.

    Uses the universal KPZ exponents to detect which phase the evolving
    system is in, and recommends exploration/exploitation adjustments.

    The key insight: different evolution phases have different KPZ signatures:
      - Growing (β ≈ 1/3): quality diversity increasing → keep exploring
      - Saturating: approaching system-size limit → balance exploration/exploitation
      - Steady (L^α): reached theoretical max → shift to exploitation
      - Collapsed: diversity below KPZ prediction → inject randomness
      - Divergent: roughness exceeds KPZ prediction → stabilize

    Usage:
        tuner = KPZTuner(population_size=50, target_quality=0.9)
        quality_var = compute_population_variance(genomes)
        tuning = tuner.tune(generation=15, quality_variance=quality_var)
        # Apply tuning to morph engine, swarm network, or bandit router
    """

    # Universal KPZ exponents (2D, theoretical ground truth)
    KPZ_BETA = 1.0 / 3.0    # Growth exponent
    KPZ_ALPHA = 1.0 / 2.0   # Roughness exponent
    KPZ_Z = 3.0 / 2.0       # Dynamic exponent

    def __init__(self, population_size: int = 50, target_quality: float = 0.9):
        self.population_size = population_size
        self.target_quality = target_quality

        # Theoretical predictions from KPZ
        self._predicted_saturation = KpzMetrics.estimate_saturation(
            population_size, self.KPZ_ALPHA,
        )
        self._predicted_saturation_steps = KpzMetrics.estimate_time_to_saturation(
            population_size, self.KPZ_Z,
        )

        # State tracking
        self._quality_history: deque[float] = deque(maxlen=200)
        self._current_state: KpzState | None = None
        self._generation = 0

        # Current parameter values
        self._mutation_rate = 0.15
        self._selection_pressure = 0.3
        self._exploration_bonus = 0.5

        self._stats = {"phases_seen": {}, "tunings_applied": 0}

    def record_generation(self, quality_variance: float, avg_quality: float = 0.0):
        """Record one generation's quality metrics for KPZ analysis."""
        self._quality_history.append(quality_variance)
        self._generation += 1

    def tune(
        self, generation: int, quality_variance: float,
        avg_quality: float = 0.0,
    ) -> KpzTuning:
        """KPZ-guided tuning recommendation for this generation.

        Returns optimal mutation rate, selection pressure, and exploration
        bonus based on detected KPZ phase.
        """
        self.record_generation(quality_variance, avg_quality)

        # Estimate KPZ exponents from history
        beta, beta_std = KpzMetrics.estimate_beta(
            list(self._quality_history),
        )
        alpha = KpzMetrics.estimate_roughness(
            self.population_size, quality_variance,
        )

        # Detect phase
        phase = self._detect_phase(beta, alpha, quality_variance, generation)
        self._current_state = KpzState(
            phase=phase,
            effective_beta=beta,
            effective_alpha=alpha,
            roughness_W=math.sqrt(max(quality_variance, 0)),
            saturation_estimate=self._predicted_saturation,
            time_to_saturation=max(0, self._predicted_saturation_steps - generation),
            quality_trajectory=list(self._quality_history),
        )

        # Determine tuning action
        tuning = self._compute_tuning(phase, beta, alpha, quality_variance, generation)

        # Apply tuning
        self._mutation_rate = tuning.recommended_mutation_rate
        self._selection_pressure = tuning.recommended_selection_pressure
        self._exploration_bonus = tuning.recommended_exploration_bonus
        self._stats["tunings_applied"] += 1
        self._stats["phases_seen"][phase.name] = (
            self._stats["phases_seen"].get(phase.name, 0) + 1
        )

        return tuning

    def _detect_phase(
        self, beta: float, alpha: float, variance: float, generation: int,
    ) -> KpzPhase:
        """Detect which KPZ phase the system is in.

        Decision tree based on KPZ exponent signatures:
        """
        # Collapse detection: diversity far below KPZ prediction
        if variance < self._predicted_saturation * 0.1 and generation > 10:
            return KpzPhase.COLLAPSED

        # Divergence detection: roughness far above KPZ prediction
        if variance > self._predicted_saturation * 3.0:
            return KpzPhase.DIVERGENT

        # Near saturation: quality variance approaching L^α
        if abs(variance - self._predicted_saturation) < self._predicted_saturation * 0.3:
            return KpzPhase.STEADY

        # Crossing to saturation
        if generation > self._predicted_saturation_steps * 0.7:
            return KpzPhase.SATURATING

        # Transient growth: β in KPZ range
        if abs(beta - self.KPZ_BETA) < 0.15:
            return KpzPhase.GROWING

        # Default: still growing
        return KpzPhase.GROWING

    def _compute_tuning(
        self, phase: KpzPhase, beta: float, alpha: float,
        variance: float, generation: int,
    ) -> KpzTuning:
        """Compute optimal parameter values for detected phase."""

        if phase == KpzPhase.GROWING:
            # KPZ β ≈ 1/3: system is in healthy growth → maintain exploration
            return KpzTuning(
                strategy=TuningStrategy.EXPLORE_MORE,
                recommended_mutation_rate=0.18,
                recommended_selection_pressure=0.25,
                recommended_exploration_bonus=0.6,
                phase=phase,
                confidence=min(1.0, 1.0 - abs(beta - self.KPZ_BETA) * 3),
                reason=f"Healthy KPZ growth (β={beta:.3f} ≈ 1/3). Variance still growing toward predicted L^α={self._predicted_saturation:.2f}.",
            )

        elif phase == KpzPhase.SATURATING:
            # Approaching t_sat ~ L^z → start shifting toward exploitation
            progress = generation / max(self._predicted_saturation_steps, 1)
            return KpzTuning(
                strategy=TuningStrategy.BALANCE,
                recommended_mutation_rate=0.15 - 0.05 * progress,
                recommended_selection_pressure=0.3 + 0.3 * progress,
                recommended_exploration_bonus=0.5 - 0.2 * progress,
                phase=phase,
                confidence=0.8,
                reason=f"Saturating toward steady state (gen {generation}/{self._predicted_saturation_steps:.0f}). Shifting from explore to exploit.",
            )

        elif phase == KpzPhase.STEADY:
            # Reached L^α → maximum diversity for this population size
            # Either: expand population (increase L) or exploit best genomes
            return KpzTuning(
                strategy=TuningStrategy.EXPLOIT_MORE,
                recommended_mutation_rate=0.05,
                recommended_selection_pressure=0.7,
                recommended_exploration_bonus=0.2,
                phase=phase,
                confidence=0.9,
                reason=f"Steady state reached. Roughness saturated at L^α={self._predicted_saturation:.2f}. Exploit best genomes or expand population.",
            )

        elif phase == KpzPhase.COLLAPSED:
            # Diversity collapsed → inject randomness (KPZ noise term η)
            return KpzTuning(
                strategy=TuningStrategy.INJECT_DIVERSITY,
                recommended_mutation_rate=0.40,  # High mutation to restore diversity
                recommended_selection_pressure=0.05,  # Low selection to let diverse survive
                recommended_exploration_bonus=1.0,
                phase=phase,
                confidence=0.95,
                reason=f"COLLAPSE detected (W={math.sqrt(variance):.3f} ≪ L^α={self._predicted_saturation:.2f}). Injecting KPZ noise η to restore surface roughness.",
            )

        elif phase == KpzPhase.DIVERGENT:
            # Too much exploration → reduce noise
            return KpzTuning(
                strategy=TuningStrategy.SLOW_DOWN,
                recommended_mutation_rate=0.03,
                recommended_selection_pressure=0.6,
                recommended_exploration_bonus=0.1,
                phase=phase,
                confidence=0.9,
                reason="DIVERGENCE: roughness exceeds KPZ bound. Reducing noise term η and increasing diffusion ν.",
            )

        # Default
        return KpzTuning(
            strategy=TuningStrategy.HOLD,
            recommended_mutation_rate=self._mutation_rate,
            recommended_selection_pressure=self._selection_pressure,
            recommended_exploration_bonus=self._exploration_bonus,
            phase=phase,
            confidence=0.5,
            reason="Holding current parameters.",
        )

    def get_state(self) -> KpzState | None:
        return self._current_state

    def get_prediction(self) -> dict:
        """KPZ theoretical predictions for this system size."""
        return {
            "population_size_L": self.population_size,
            "predicted_saturation_W": round(self._predicted_saturation, 3),
            "predicted_saturation_steps": round(self._predicted_saturation_steps, 0),
            "theoretical_beta": round(self.KPZ_BETA, 3),
            "theoretical_alpha": round(self.KPZ_ALPHA, 3),
            "theoretical_z": round(self.KPZ_Z, 3),
        }

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "current_parameters": {
                "mutation_rate": round(self._mutation_rate, 3),
                "selection_pressure": round(self._selection_pressure, 3),
                "exploration_bonus": round(self._exploration_bonus, 3),
            },
            "prediction": self.get_prediction(),
            "current_phase": self._current_state.phase.name if self._current_state else "unknown",
        }


_tuner: KPZTuner | None = None


def get_kpz_tuner(population_size: int = 50) -> KPZTuner:
    global _tuner
    if _tuner is None:
        _tuner = KPZTuner(population_size=population_size)
    return _tuner
