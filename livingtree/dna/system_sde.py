"""System-Level Stochastic Differential Equation — multi-organ unified SDE modeling.

Bosso et al. (2025): "A machine learning framework for uncovering stochastic
nonlinear dynamics from noisy data." This module applies the framework at the
SYSTEM level — modeling the LivingTree's 12 organs as a coupled SDE system.

Core model:
    dX^{(i)}_t = f_i(X_t) dt + g_i(X_t) dW^{(i)}_t

where X_t = (X^{(1)}_t, ..., X^{(12)}_t) are the organ state vectors,
f_i is the deterministic dynamics of organ i, and g_i is its stochastic
diffusion. The key Bosso insight: if organs share noise structures
(g_i correlates with f_i), the system has INTRINSIC stochasticity —
the noise is part of the system's own dynamics, not external measurement error.

Usage:
    from livingtree.dna.system_sde import SystemSDE

    sde = SystemSDE()
    sde.record_organ("consciousness", value=0.7)
    sde.record_organ("knowledge_graph", value=0.5)
    state = sde.get_state()
    pred = sde.predict_horizon(steps=5)
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

# ═══════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OrganSDEState:
    """SDE state for a single organ."""
    organ_name: str
    current_value: float = 0.5
    drift_estimate: float = 0.0          # μ: deterministic tendency
    diffusion_estimate: float = 0.1      # σ: stochastic volatility
    noise_type: str = "additive"         # additive / multiplicative
    last_updated: float = 0.0


@dataclass
class SystemSDEState:
    """Complete system SDE state across all organs."""
    organs: dict[str, OrganSDEState] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    total_drift_magnitude: float = 0.0
    total_diffusion_magnitude: float = 0.0
    coupling_strength: float = 0.0       # Inter-organ coupling (0=decoupled, 1=strongly coupled)
    system_regime: str = "stable"        # stable / critical / chaotic


@dataclass
class SDEPrediction:
    """SDE-based prediction for future system state."""
    steps_ahead: int
    organ_predictions: dict[str, dict[str, float]]  # organ → {mean, lower, upper}
    confidence: float


# ═══════════════════════════════════════════════════════════════════
# System SDE Engine
# ═══════════════════════════════════════════════════════════════════

class SystemSDE:
    """Multi-organ unified SDE model for the LivingTree system.

    Tracks state trajectories for each of the 12 organs and fits
    simplified SDE models to detect coupling, predict phase transitions,
    and distinguish intrinsic vs extrinsic noise.

    Organs tracked:
        consciousness, knowledge_graph, reasoning, learning,
        memory, perception, action, emotion, creativity,
        social, ethical, self_reflection
    """

    #: Recognized organ names (12-organ architecture)
    RECOGNIZED_ORGANS = {
        "consciousness", "knowledge_graph", "reasoning", "learning",
        "memory", "perception", "action", "emotion", "creativity",
        "social", "ethical", "self_reflection",
    }

    def __init__(self, history_size: int = 200):
        self._history: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self._history_size = history_size
        self._states: dict[str, OrganSDEState] = {}
        self._last_coupling = 0.0

    # ── Data Recording ──

    def record_organ(self, organ_name: str, value: float) -> None:
        """Record a state measurement for one organ."""
        now = time.time()
        self._history[organ_name].append((now, value))
        # Prune history
        if len(self._history[organ_name]) > self._history_size:
            self._history[organ_name] = self._history[organ_name][-self._history_size:]

    def record_batch(self, measurements: dict[str, float]) -> None:
        """Record multiple organ measurements at once."""
        for name, value in measurements.items():
            self.record_organ(name, value)

    # ── State Estimation ──

    def get_state(self) -> SystemSDEState:
        """Estimate the current system SDE state from recorded history.

        For each organ, computes drift μ (mean trend) and diffusion σ
        (volatility) from the recent trajectory using Euler-Maruyama
        discretization.

        Returns:
            SystemSDEState with per-organ estimates and system-level aggregates.
        """
        organs: dict[str, OrganSDEState] = {}
        total_drift = 0.0
        total_diff = 0.0
        n_active = 0

        for organ_name, series in self._history.items():
            if len(series) < 10:
                continue

            values = [v for _, v in series[-50:]]
            n = len(values)
            if n < 5:
                continue

            # Compute increments
            incs = [values[i + 1] - values[i] for i in range(n - 1)]
            mu = sum(incs) / len(incs) if incs else 0.0
            var = sum((v - mu) ** 2 for v in incs) / len(incs) if incs else 0.0
            sigma = math.sqrt(max(0.0, var))

            # Noise type: constant σ → additive; σ ∝ value → multiplicative
            if n >= 5:
                mean_val = sum(values) / n
                # Correlation between σ and value level
                if sigma > 0.01 and mean_val > 0.01:
                    ratio = sigma / (abs(mean_val) + 0.01)
                    noise_type = "multiplicative" if ratio > 0.2 else "additive"
                else:
                    noise_type = "additive"
            else:
                noise_type = "additive"

            state = OrganSDEState(
                organ_name=organ_name,
                current_value=values[-1],
                drift_estimate=round(mu, 6),
                diffusion_estimate=round(sigma, 4),
                noise_type=noise_type,
                last_updated=series[-1][0],
            )
            organs[organ_name] = state
            self._states[organ_name] = state

            total_drift += abs(mu)
            total_diff += sigma
            n_active += 1

        # System-level aggregates
        n = max(n_active, 1)
        avg_drift = total_drift / n
        avg_diffusion = total_diff / n
        coupling = self._estimate_coupling()

        # System regime
        if avg_diffusion > 3 * max(avg_drift, 0.001):
            regime = "chaotic"
        elif avg_diffusion > avg_drift:
            regime = "critical"
        else:
            regime = "stable"

        return SystemSDEState(
            organs=organs,
            timestamp=time.time(),
            total_drift_magnitude=round(avg_drift, 6),
            total_diffusion_magnitude=round(avg_diffusion, 4),
            coupling_strength=round(coupling, 3),
            system_regime=regime,
        )

    # ── Coupling Estimation ──

    def _estimate_coupling(self) -> float:
        """Estimate inter-organ coupling via cross-correlation of recent trends.

        High coupling means organs move together → the system is "tight."
        Low coupling means organs operate independently → modular.

        Returns coupling strength in [0, 1].
        """
        active = list(self._states.keys())
        if len(active) < 2:
            return 0.0

        # Extract recent trends for each organ
        trends: dict[str, list[float]] = {}
        for name in active:
            series = self._history.get(name, [])
            if len(series) < 10:
                continue
            values = [v for _, v in series[-20:]]
            # Compute trend as increments
            trends[name] = [
                values[i + 1] - values[i] for i in range(len(values) - 1)
            ]

        if len(trends) < 2:
            return 0.0

        # Pairwise correlation of trends
        couplings: list[float] = []
        organ_names = list(trends.keys())
        for i in range(len(organ_names)):
            for j in range(i + 1, len(organ_names)):
                a_vals = trends[organ_names[i]]
                b_vals = trends[organ_names[j]]
                n = min(len(a_vals), len(b_vals))
                if n < 5:
                    continue
                a = a_vals[:n]
                b = b_vals[:n]

                mean_a = sum(a) / n
                mean_b = sum(b) / n
                std_a = math.sqrt(sum((v - mean_a) ** 2 for v in a) / n)
                std_b = math.sqrt(sum((v - mean_b) ** 2 for v in b) / n)

                if std_a < 1e-9 or std_b < 1e-9:
                    couplings.append(0.0)
                else:
                    cov = sum((ai - mean_a) * (bi - mean_b) for ai, bi in zip(a, b)) / n
                    corr = cov / (std_a * std_b)
                    couplings.append(abs(corr))

        if not couplings:
            return 0.0
        self._last_coupling = sum(couplings) / len(couplings)
        return self._last_coupling

    # ── Prediction ──

    def predict_horizon(self, steps: int = 5) -> SDEPrediction:
        """Predict system state N steps ahead using Euler-Maruyama.

        For each organ, propagates the current SDE forward:
            X_{t+1} = X_t + μ·dt + σ·√dt·Z

        Reports the mean path and 95% confidence intervals.
        """
        dt = 1.0
        predictions: dict[str, dict[str, float]] = {}

        for organ_name, state in self._states.items():
            x = state.current_value
            mu = state.drift_estimate
            sigma = state.diffusion_estimate

            # Forward propagation (mean path)
            mean_path = x
            for _ in range(steps):
                mean_path += mu * dt

            # 95% CI: ±1.96 × σ × √(steps·dt)
            half_width = 1.96 * sigma * math.sqrt(steps * dt)

            predictions[organ_name] = {
                "current": round(x, 4),
                "mean": round(mean_path, 4),
                "lower": round(mean_path - half_width, 4),
                "upper": round(mean_path + half_width, 4),
            }

        # Confidence: higher when coupling is stable and diffusion is low
        state = self.get_state()
        coupling_stability = 1.0 - abs(self._last_coupling - state.coupling_strength)
        diffusion_penalty = max(0.0, 1.0 - state.total_diffusion_magnitude)
        confidence = 0.5 * coupling_stability + 0.5 * diffusion_penalty

        return SDEPrediction(
            steps_ahead=steps,
            organ_predictions=predictions,
            confidence=round(confidence, 3),
        )

    # ── Structural Emergence Detection ──

    def intrinsic_noise_ratio(self) -> dict[str, Any]:
        """Compute the ratio of intrinsic to extrinsic noise across organs.

        Bosso et al. (2025) key metric: if g(x) structurally resembles f(x),
        noise is intrinsic (from system parameters). If g(x) is constant,
        noise is extrinsic (from measurement).

        Returns:
            dict with intrinsic_ratio (0-1), organ classifications, and
            system-level interpretation.
        """
        state = self.get_state()
        intrinsic = 0
        extrinsic = 0
        classifications: dict[str, str] = {}

        for organ_name, org_state in state.organs.items():
            if org_state.noise_type == "multiplicative":
                intrinsic += 1
                classifications[organ_name] = "intrinsic"
            else:
                extrinsic += 1
                classifications[organ_name] = "extrinsic"

        total = max(intrinsic + extrinsic, 1)
        ratio = intrinsic / total

        if ratio > 0.6:
            interpretation = (
                "System dominated by INTRINSIC stochasticity — noise sources "
                "are part of the system's own dynamics. The system has rich "
                "internal structure generating its own uncertainty. GENUINE emergence."
            )
        elif ratio > 0.3:
            interpretation = (
                "Mixed noise regime — some organs have intrinsic noise, "
                "others have extrinsic measurement noise. Consider filtering "
                "extrinsic organs before emergence classification."
            )
        else:
            interpretation = (
                "System dominated by EXTRINSIC noise — uncertainty likely "
                "from measurement limitations or external perturbations. "
                "Reduced confidence in emergence claims."
            )

        return {
            "intrinsic_ratio": round(ratio, 3),
            "intrinsic_count": intrinsic,
            "extrinsic_count": extrinsic,
            "organ_classifications": classifications,
            "interpretation": interpretation,
        }

    # ── OrthoReg Organ Coupling Heatmap (CVPR 2026) ──

    def organ_coupling_heatmap(self) -> dict[str, Any]:
        """Compute pairwise cosine similarity of organ SDE state trajectories.

        OrthoReg (CVPR 2026) mapping: the cosine heatmap of weight column
        vectors (WVO) maps to the cosine similarity of organ output
        trajectories. Organ pairs with high similarity may be functionally
        redundant or interfering — they are not weight-disentangled (WD).

        Returns a heatmap-ready matrix suitable for visualization, plus
        OrthoReg-style interference classification.

        Returns:
            dict with:
              - heatmap: {organ_i: {organ_j: cosine_similarity}} (symmetric)
              - high_coupling_pairs: pairs with |cos| > 0.7
              - coupling_strength: mean absolute cosine across all pairs
              - orthoreg_score: 1 - coupling_strength (0=fully coupled, 1=orthogonal)
              - interpretation: OrthoReg WVO status
        """
        import math

        state = self.get_state()
        organs = list(state.organs.keys())
        n = len(organs)
        if n < 2:
            return {
                "heatmap": {}, "high_coupling_pairs": [],
                "coupling_strength": 0.0, "orthoreg_score": 1.0,
                "interpretation": "insufficient organs for coupling analysis",
            }

        heatmap: dict[str, dict[str, float]] = {}
        high_pairs: list[dict] = []
        all_cos: list[float] = []
        threshold = 0.7  # |cos| > 0.7 = high coupling

        for i in range(n):
            a_name = organs[i]
            a_series = self._history.get(a_name, [])
            if len(a_series) < 5:
                continue
            heatmap[a_name] = {}

            for j in range(i + 1, n):
                b_name = organs[j]
                b_series = self._history.get(b_name, [])
                if len(b_series) < 5:
                    continue

                # Extract aligned value sequences
                m = min(len(a_series), len(b_series))
                a_vals = [v for _, v in a_series[-m:]]
                b_vals = [v for _, v in b_series[-m:]]

                # Cosine similarity
                dot = sum(a_vals[k] * b_vals[k] for k in range(m))
                norm_a = math.sqrt(sum(v * v for v in a_vals))
                norm_b = math.sqrt(sum(v * v for v in b_vals))
                cos_sim = (
                    dot / (norm_a * norm_b)
                    if norm_a > 1e-9 and norm_b > 1e-9
                    else 0.0
                )
                abs_cos = abs(cos_sim)

                heatmap[a_name][b_name] = round(cos_sim, 4)
                if b_name not in heatmap:
                    heatmap[b_name] = {}
                heatmap[b_name][a_name] = round(cos_sim, 4)
                all_cos.append(abs_cos)

                if abs_cos > threshold:
                    direction = "cooperative" if cos_sim > 0 else "competitive"
                    high_pairs.append({
                        "organ_a": a_name, "organ_b": b_name,
                        "cosine": round(cos_sim, 4),
                        "abs_cosine": round(abs_cos, 4),
                        "direction": direction,
                    })

        mean_coupling = (
            round(sum(all_cos) / len(all_cos), 4) if all_cos else 0.0
        )
        orthoreg_score = round(max(0.0, 1.0 - mean_coupling), 4)

        if orthoreg_score > 0.7:
            interp = (
                f"Strong OrthoReg condition: organs are well-orthogonalized "
                f"(score={orthoreg_score}). WVO maintained — minimal cross-organ "
                "interference. Weight Disentanglement (WD) hypothesis supported."
            )
        elif orthoreg_score > 0.4:
            interp = (
                f"Moderate OrthoReg condition (score={orthoreg_score}). "
                f"{len(high_pairs)} organ pairs show high coupling — "
                "potential functional redundancy or interference."
            )
        else:
            interp = (
                f"Weak OrthoReg condition: high organ coupling "
                f"(score={orthoreg_score}). {len(high_pairs)} pairs exceed "
                "threshold. Recommend OrthoReg-style disentanglement to "
                "restore organ modularity."
            )

        return {
            "heatmap": heatmap,
            "high_coupling_pairs": high_pairs,
            "coupling_strength": mean_coupling,
            "orthoreg_score": orthoreg_score,
            "interpretation": interp,
        }

    # ── Stats ──

    def stats(self) -> dict[str, Any]:
        state = self.get_state()
        intrinsic = self.intrinsic_noise_ratio()
        return {
            "organs_tracked": len(self._history),
            "active_organs": len(state.organs),
            "system_regime": state.system_regime,
            "total_drift": state.total_drift_magnitude,
            "total_diffusion": state.total_diffusion_magnitude,
            "coupling_strength": state.coupling_strength,
            "intrinsic_noise_ratio": intrinsic["intrinsic_ratio"],
            "interpretation": intrinsic["interpretation"],
        }


# ═══════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════

_system_sde: SystemSDE | None = None


def get_system_sde() -> SystemSDE:
    """Get or create the singleton SystemSDE instance."""
    global _system_sde
    if _system_sde is None:
        _system_sde = SystemSDE()
    return _system_sde


__all__ = [
    "SystemSDE",
    "OrganSDEState",
    "SystemSDEState",
    "SDEPrediction",
    "get_system_sde",
]
