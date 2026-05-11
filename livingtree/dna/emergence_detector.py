"""Emergence Detector — distinguish genuine emergence from linear extrapolation.

Based on Anderson (1972) "More is different" + Schaeffer et al. (2023):
  - True emergence: system behavior that cannot be predicted from component-level metrics
  - Spurious emergence (mirage): appears emergent due to measurement artifacts or scaling
  - Critical test: does the behavior survive under perturbation? If yes → genuine

Two complementary detectors:
  1. Statistical Detector: nonlinearity test (does metric M scale as Σ components or superlinearly?)
  2. Perturbation Detector: robustness test (does behavior persist under noise injection?)
  3. Phase Transition Detector: detect when system crosses a critical point

Integration:
    detector = EmergenceDetector()
    detector.record_metric("life_cycles", value)       # feed metrics
    report = detector.analyze()                          # periodic analysis
    if report.has_genuine_emergence:
        # System exhibits true emergent behavior — notify LifeEngine
"""

from __future__ import annotations

import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══ Data Types ═══


@dataclass
class EmergenceSignal:
    """A detected emergent behavior pattern."""
    name: str                          # Signal name (e.g. "success_rate_jump")
    description: str
    is_genuine: bool                   # True = nonlinear, persists under perturbation
    confidence: float                  # Statistical confidence (0-1)
    nonlinearity_score: float          # How much it deviates from linear expectation
    perturbation_score: float          # How robust under perturbation (0=fragile, 1=robust)
    phase_order: float                 # 0=gradual, 1=abrupt (first-order phase transition)
    metrics_involved: list[str]
    threshold_value: float
    observed_value: float
    detected_at: float


@dataclass
class EmergenceReport:
    """Periodic emergence analysis report."""
    timestamp: float
    signals: list[EmergenceSignal]
    has_genuine_emergence: bool = False
    has_phase_transition: bool = False
    spurious_signals: list[EmergenceSignal] = field(default_factory=list)
    component_count: int = 0
    summary: str = ""

    @property
    def genuine_count(self) -> int:
        return sum(1 for s in self.signals if s.is_genuine)

    @property
    def spurious_count(self) -> int:
        return sum(1 for s in self.signals if not s.is_genuine)


# ═══ Emergence Detector ═══


class EmergenceDetector:
    """Multi-method emergence detection for the digital lifeform.

    Anderson (1972): "More is different" — aggregate behavior cannot be
    derived from microscopic laws alone. We detect when the system
    genuinely exhibits higher-level organization.

    Schaeffer et al. (2023): Emergent abilities may be a mirage caused by
    discontinuous metrics. We apply perturbation tests to distinguish
    genuine emergence from measurement artifacts.
    """

    def __init__(self, window_size: int = 100, analysis_interval: int = 50):
        self._window_size = window_size
        self._analysis_interval = analysis_interval

        # Time series storage: metric_name → [(timestamp, value)]
        self._series: dict[str, list[tuple[float, float]]] = defaultdict(list)
        # Component-level series (for nonlinearity test)
        self._component_series: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list))
        # Track the number of data points since last analysis
        self._points_since_analysis = 0
        # Historical emergence reports
        self._reports: list[EmergenceReport] = []

    # ── Data Recording ──

    def record(self, metric_name: str, value: float) -> None:
        """Record a system-level metric."""
        self._series[metric_name].append((time.time(), value))
        if len(self._series[metric_name]) > self._window_size * 3:
            self._series[metric_name] = self._series[metric_name][-self._window_size * 2:]
        self._points_since_analysis += 1

    def record_component(
        self, metric_name: str, component_id: str, value: float,
    ) -> None:
        """Record a component-level metric (for emergence = system ≠ Σ components)."""
        self._component_series[metric_name][component_id].append(value)
        if len(self._component_series[metric_name][component_id]) > self._window_size:
            self._component_series[metric_name][component_id] = (
                self._component_series[metric_name][component_id][-self._window_size:])

    # ── Analysis ──

    def analyze(self) -> EmergenceReport:
        """Run full emergence analysis across all tracked metrics.

        Returns:
            EmergenceReport with detected signals classified as genuine/spurious
        """
        signals: list[EmergenceSignal] = []
        spurious: list[EmergenceSignal] = []

        for metric_name in self._series:
            signal = self._detect_emergence(metric_name)
            if signal:
                if signal.is_genuine:
                    signals.append(signal)
                else:
                    spurious.append(signal)

        # Check for phase transitions
        has_phase = any(s.phase_order > 0.7 for s in signals)

        # Count active components
        comp_count = sum(
            len(comps) for comps in self._component_series.values())

        report = EmergenceReport(
            timestamp=time.time(),
            signals=signals,
            has_genuine_emergence=len(signals) > 0,
            has_phase_transition=has_phase,
            spurious_signals=spurious,
            component_count=comp_count,
            summary=self._build_summary(signals, spurious),
        )

        if signals:
            logger.info(f"Emergence: {len(signals)} genuine signals detected")

        self._reports.append(report)
        if len(self._reports) > 50:
            self._reports = self._reports[-50:]

        self._points_since_analysis = 0
        return report

    def should_analyze(self) -> bool:
        """Check if it's time for periodic analysis."""
        return self._points_since_analysis >= self._analysis_interval

    # ── Signal Detection ──

    def _detect_emergence(self, metric_name: str) -> EmergenceSignal | None:
        """Detect emergence in a single metric using all three methods."""
        data = self._series.get(metric_name, [])
        if len(data) < 20:
            return None

        values = [v for _, v in data[-self._window_size:]]
        if not values:
            return None

        # Method 1: Nonlinearity test
        nonlinearity = self._test_nonlinearity(metric_name, values)

        # Method 2: Perturbation robustness
        perturbation = self._test_perturbation(metric_name, values)

        # Method 3: Phase transition detection
        phase_order = self._detect_phase_transition(values)

        # Only report if at least one method detects something significant
        if nonlinearity < 0.2 and perturbation < 0.3 and phase_order < 0.5:
            return None

        # Genuineness: nonlinear + perturbation-robust
        is_genuine = nonlinearity > 0.3 and perturbation > 0.4

        mean_val = sum(values) / len(values)
        return EmergenceSignal(
            name=f"{metric_name}_emergence",
            description=(
                f"Metric '{metric_name}' shows emergence: "
                f"nonlinearity={nonlinearity:.2f}, robustness={perturbation:.2f}, "
                f"phase_order={phase_order:.2f}"
            ),
            is_genuine=is_genuine,
            confidence=min(1.0, (nonlinearity + perturbation) / 2),
            nonlinearity_score=round(nonlinearity, 3),
            perturbation_score=round(perturbation, 3),
            phase_order=round(phase_order, 3),
            metrics_involved=[metric_name],
            threshold_value=round(mean_val * 1.5, 3),
            observed_value=round(mean_val, 3),
            detected_at=time.time(),
        )

    def _test_nonlinearity(
        self, metric_name: str, system_values: list[float],
    ) -> float:
        """Test if system behavior deviates from linear component aggregation.

        Hypothesis H0: system = Σ components
        If R² of (components_sum → system) < 0.5, behavior is nonlinear.

        Returns: 0-1 where 1 = strongly nonlinear (emergent).
        """
        comps = self._component_series.get(metric_name, {})
        if not comps:
            # No component data → fall back to variance test
            if len(system_values) < 5:
                return 0.0
            mean = sum(system_values) / len(system_values)
            # Check for sudden deviations (jump > 3σ)
            std = math.sqrt(
                sum((v - mean) ** 2 for v in system_values) / len(system_values))
            if std < 0.0001:
                return 0.0
            recent = system_values[-10:] if len(system_values) >= 10 else system_values
            recent_mean = sum(recent) / len(recent)
            z_score = abs(recent_mean - mean) / std
            return min(1.0, z_score / 3.0)

        # Aggregate component sums
        n = min(len(system_values), min(len(v) for v in comps.values()))
        if n < 5:
            return 0.0

        comp_sums = []
        sys_vals = system_values[-n:]
        for i in range(n):
            total = sum(
                vals[i] if i < len(vals) else 0
                for vals in comps.values())
            comp_sums.append(total)

        # Linear regression: sys ≈ a × comps + b
        mean_c = sum(comp_sums) / n
        mean_s = sum(sys_vals) / n
        cov = sum((c - mean_c) * (s - mean_s) for c, s in zip(comp_sums, sys_vals))
        var_c = sum((c - mean_c) ** 2 for c in comp_sums)
        if var_c < 0.0001:
            return 0.0
        slope = cov / var_c
        intercept = mean_s - slope * mean_c

        # R²
        ss_res = sum(
            (s - (slope * c + intercept)) ** 2
            for c, s in zip(comp_sums, sys_vals))
        ss_tot = sum((s - mean_s) ** 2 for s in sys_vals)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        return max(0.0, min(1.0, 1.0 - r_squared))

    def _test_perturbation(
        self, metric_name: str, values: list[float],
        noise_level: float = 0.1,
    ) -> float:
        """Test robustness under perturbation (Schaeffer et al. 2023).

        Add Gaussian noise to recent values. If the statistical signature
        survives the noise, it's genuine emergence. If it disappears,
        it's a mirage caused by metric artifacts.

        Returns: 0-1 where 1 = highly robust (genuine emergence).
        """
        if len(values) < 10:
            return 0.0

        original_mean = sum(values) / len(values)
        original_std = math.sqrt(
            sum((v - original_mean) ** 2 for v in values) / len(values))
        if original_std < 0.0001:
            return 0.5

        # Add noise and recompute
        perturbed = []
        for v in values:
            noisy = v + random.gauss(0, original_std * noise_level)
            perturbed.append(noisy)

        perturbed_mean = sum(perturbed) / len(perturbed)
        perturbed_std = math.sqrt(
            sum((p - perturbed_mean) ** 2 for p in perturbed) / len(perturbed))

        # Compare distributions via KS-like metric
        drift = abs(original_mean - perturbed_mean) / (original_std + 0.0001)
        shape_preserved = 1.0 - abs(
            1.0 - perturbed_std / (original_std + 0.0001))

        robustness = (1.0 - min(1.0, drift)) * shape_preserved
        return max(0.0, min(1.0, robustness))

    def _detect_phase_transition(self, values: list[float]) -> float:
        """Detect phase transitions: abrupt qualitative changes.

        0 = smooth/gradual change, 1 = first-order phase transition.
        """
        if len(values) < 20:
            return 0.0

        # Split into two halves
        half = len(values) // 2
        first = values[:half]
        second = values[half:]

        mean1 = sum(first) / len(first)
        mean2 = sum(second) / len(second)

        std1 = math.sqrt(sum((v - mean1) ** 2 for v in first) / len(first))
        std2 = math.sqrt(sum((v - mean2) ** 2 for v in second) / len(second))

        # Phase transition: mean shift is large relative to combined std
        combined_std = math.sqrt((std1 ** 2 + std2 ** 2) / 2)
        if combined_std < 0.0001:
            return 0.0

        mean_shift = abs(mean2 - mean1) / combined_std

        # Abruptness: how much of the shift happens in a small window
        window = min(5, len(values) // 4)
        max_gradient = 0.0
        for i in range(len(values) - window):
            segment = values[i:i + window]
            grad = abs(segment[-1] - segment[0]) / window
            max_gradient = max(max_gradient, grad)

        gradient_norm = max_gradient / (combined_std + 0.0001)

        # Phase order: higher = more abrupt (first-order transition)
        phase_order = 0.5 * min(1.0, mean_shift / 3.0) + 0.5 * min(1.0, gradient_norm / 2.0)
        return max(0.0, min(1.0, phase_order))

    # ── SDE Structural Emergence (Bosso et al. 2025) ──

    def diffusion_structure_similarity(
        self,
        drift_values: list[float],
        diffusion_values: list[float],
        x_values: list[float] | None = None,
    ) -> dict[str, float | str | int]:
        r"""Measure how much the diffusion structure g(x) inherits from drift f(x).

        Bosso et al. (2025) key insight: if noise originates from system parameters,
        then the diffusion function g(x) structurally resembles the drift function f(x).
        This is a signature of INTRINSIC stochasticity (genuine emergence) rather
        than EXTRINSIC measurement noise.

        Matches the SDE: dX_t = f(X_t)dt + g(X_t)dW_t

        Three metrics:
          1. gradient_correlation: corr(∇f, ∇g) — how aligned are their local slopes?
             High → diffusion "knows" about the drift structure → intrinsic noise
          2. amplitude_consistency: 1 - |σ_g/σ_f - σ_g/σ_f median| — regularity of
             the ratio between diffusion and drift variations
          3. functional_form_overlap: if g(x) can be approximately written as
             h(f(x)) for some smooth h (tested via rank correlation of sorted values)

        Returns:
            dict with keys: similarity_score (0-1, composite), gradient_correlation,
            amplitude_consistency, functional_overlap, interpretation

        Interpretation:
            > 0.7: Diffusion structurally inherits from drift — intrinsic stochasticity,
                   genuine emergence. System has INTERNAL noise sources.
            0.4-0.7: Partial structural overlap — mixed intrinsic/extrinsic noise.
            < 0.4: Diffusion is unstructured relative to drift — measurement noise,
                   spurious emergence (Schaeffer mirage). System noise is EXTERNAL.
        """
        n = min(len(drift_values), len(diffusion_values))
        if n < 10:
            return {
                "similarity_score": 0.0,
                "gradient_correlation": 0.0,
                "amplitude_consistency": 0.0,
                "functional_overlap": 0.0,
                "interpretation": "insufficient data (need ≥10 points)",
            }

        f = drift_values[:n]
        g = diffusion_values[:n]

        # ── 1. Gradient Correlation ──
        # Compute local gradients (finite differences)
        grad_f = [f[i + 1] - f[i] for i in range(n - 1)]
        grad_g = [g[i + 1] - g[i] for i in range(n - 1)]

        if len(grad_f) < 3:
            grad_corr = 0.0
        else:
            # Pearson correlation of gradients
            mean_gf = sum(grad_f) / len(grad_f)
            mean_gg = sum(grad_g) / len(grad_g)
            std_gf = math.sqrt(sum((v - mean_gf) ** 2 for v in grad_f) / len(grad_f))
            std_gg = math.sqrt(sum((v - mean_gg) ** 2 for v in grad_g) / len(grad_g))

            if std_gf < 1e-9 or std_gg < 1e-9:
                grad_corr = 0.0
            else:
                cov = sum(
                    (gf - mean_gf) * (gg - mean_gg)
                    for gf, gg in zip(grad_f, grad_g)) / len(grad_f)
                grad_corr = max(-1.0, min(1.0, cov / (std_gf * std_gg)))
            grad_corr = abs(grad_corr)

        # ── 2. Amplitude Consistency ──
        # How consistent is the ratio σ_g / σ_f across the signal?
        if x_values and len(x_values) >= n:
            xs = x_values[:n]
        else:
            xs = list(range(n))

        # Sliding window ratio analysis
        window = max(3, n // 5)
        ratios = []
        for i in range(0, n - window, window // 2):
            seg_f = f[i:i + window]
            seg_g = g[i:i + window]
            std_f = math.sqrt(
                sum((v - sum(seg_f) / len(seg_f)) ** 2 for v in seg_f) / len(seg_f))
            std_g_val = math.sqrt(
                sum((v - sum(seg_g) / len(seg_g)) ** 2 for v in seg_g) / len(seg_g))
            if std_f > 1e-9:
                ratios.append(std_g_val / std_f)

        if len(ratios) < 2:
            amp_consistency = 0.0
        else:
            median_ratio = sorted(ratios)[len(ratios) // 2]
            deviations = [abs(r - median_ratio) / max(median_ratio, 1e-9) for r in ratios]
            amp_consistency = max(0.0, 1.0 - min(1.0, sum(deviations) / len(deviations)))

        # ── 3. Functional Form Overlap ──
        # Test if g(x) ≈ h(f(x)) via Spearman rank correlation of sorted values
        f_ranks = sorted(range(n), key=lambda i: f[i])
        g_ranks = sorted(range(n), key=lambda i: g[i])
        # Spearman: rank each value, compute Pearson on ranks
        rank_f = [0] * n
        rank_g = [0] * n
        for rank, idx in enumerate(f_ranks):
            rank_f[idx] = rank
        for rank, idx in enumerate(g_ranks):
            rank_g[idx] = rank

        mean_rf = (n - 1) / 2
        mean_rg = (n - 1) / 2
        cov_rank = sum(
            (rf - mean_rf) * (rg - mean_rg) for rf, rg in zip(rank_f, rank_g)) / n
        var_rank = sum((rf - mean_rf) ** 2 for rf in rank_f) / n
        if var_rank < 1e-9:
            functional_overlap = 0.0
        else:
            functional_overlap = max(-1.0, min(1.0, cov_rank / var_rank))
        functional_overlap = abs(functional_overlap)

        # ── Composite Score ──
        similarity = (0.4 * grad_corr + 0.3 * amp_consistency
                       + 0.3 * functional_overlap)

        # Interpretation
        if similarity > 0.7:
            interp = (
                "Intrinsic stochasticity: g(x) structurally inherits from f(x). "
                "Noise originates from system parameters — GENUINE emergence. "
                "The system has internal noise sources that respect its dynamics."
            )
        elif similarity > 0.4:
            interp = (
                "Mixed noise: partial structural overlap between drift and diffusion. "
                "Some noise is intrinsic, some extrinsic. Consider filtering "
                "measurement noise before emergence classification."
            )
        else:
            interp = (
                "Extrinsic noise: g(x) is unstructured relative to f(x). "
                "Noise likely from measurement artifacts — SPURIOUS emergence "
                "(Schaeffer mirage). Consider recalibrating metrics."
            )

        return {
            "similarity_score": round(similarity, 4),
            "gradient_correlation": round(grad_corr, 4),
            "amplitude_consistency": round(amp_consistency, 4),
            "functional_overlap": round(functional_overlap, 4),
            "interpretation": interp,
            "sample_size": n,
        }

    # ── OrthoReg Organ Interference (CVPR 2026) ──

    def organ_interference_matrix(
        self, organ_states: dict[str, list[float]],
    ) -> dict[str, Any]:
        """Compute orthogonality-based interference between organs.

        OrthoReg (CVPR 2026) insight: WVO (Weight Vector Orthogonality)
        prevents cross-task interference. Organs with high cosine similarity
        in their output trajectories may be interfering with each other —
        violating the modular design.

        Computes pairwise cosine similarity between all organs' recent
        activity vectors. Outputs a heatmap-ready matrix and flags pairs
        exceeding the interference threshold.

        Args:
            organ_states: dict mapping organ_name → list of recent values
                          (from SystemSDE.get_state().organs)

        Returns:
            dict with keys:
              - matrix: {organ_i: {organ_j: cosine_similarity}}
              - interference_pairs: [(organ_i, organ_j, cos_sim)] exceeding threshold
              - max_interference: highest pairwise cosine found
              - avg_interference: mean pairwise cosine (system-level coupling)
              - interpretation: string summary
        """
        organ_names = list(organ_states.keys())
        n = len(organ_names)
        if n < 2:
            return {
                "matrix": {}, "interference_pairs": [],
                "max_interference": 0.0, "avg_interference": 0.0,
                "interpretation": "insufficient organs for interference analysis",
            }

        threshold = 0.6  # cos_sim > 0.6 = significant overlap ≈ 53°

        matrix: dict[str, dict[str, float]] = {}
        pairs: list[tuple[str, str, float]] = []
        all_cos: list[float] = []

        for i in range(n):
            a_name = organ_names[i]
            a_vals = organ_states.get(a_name, [])
            if not a_vals:
                continue
            matrix[a_name] = {}

            for j in range(i + 1, n):
                b_name = organ_names[j]
                b_vals = organ_states.get(b_name, [])
                if not b_vals:
                    continue

                # Align to common length
                m = min(len(a_vals), len(b_vals))
                if m < 3:
                    cos_sim = 0.0
                else:
                    va = a_vals[:m]
                    vb = b_vals[:m]

                    dot = sum(va[k] * vb[k] for k in range(m))
                    norm_a = math.sqrt(sum(v * v for v in va))
                    norm_b = math.sqrt(sum(v * v for v in vb))
                    cos_sim = (
                        dot / (norm_a * norm_b)
                        if norm_a > 1e-9 and norm_b > 1e-9
                        else 0.0
                    )
                    cos_sim = abs(cos_sim)

                matrix[a_name][b_name] = round(cos_sim, 4)
                if b_name not in matrix:
                    matrix[b_name] = {}
                matrix[b_name][a_name] = round(cos_sim, 4)
                all_cos.append(cos_sim)

                if cos_sim > threshold:
                    pairs.append((a_name, b_name, round(cos_sim, 4)))

        max_interference = max(all_cos) if all_cos else 0.0
        avg_interference = round(sum(all_cos) / len(all_cos), 4) if all_cos else 0.0

        if len(pairs) > n // 2:
            interp = (
                f"High organ interference detected ({len(pairs)} pairs exceed "
                f"cos_sim={threshold}). Organ modularity is compromised — "
                "consider disentanglement (Weight Disentanglement per OrthoReg)."
            )
        elif pairs:
            interp = (
                f"Moderate organ interference: {len(pairs)} overlapping pairs. "
                f"Some task interference likely. Monitor for drift."
            )
        else:
            interp = (
                "Good organ modularity: no significant interference detected. "
                "Weight vectors maintain WVO — OrthoReg condition satisfied."
            )

        return {
            "matrix": matrix,
            "interference_pairs": [{"organ_a": a, "organ_b": b, "cosine": c}
                                   for a, b, c in pairs],
            "max_interference": round(max_interference, 4),
            "avg_interference": avg_interference,
            "interpretation": interp,
        }

    # ── Reporting ──

    def _build_summary(
        self, genuine: list[EmergenceSignal], spurious: list[EmergenceSignal],
    ) -> str:
        parts = []
        if genuine:
            parts.append(
                f"Genuine emergence: {', '.join(s.name for s in genuine)}")
        if spurious:
            parts.append(
                f"Spurious signals (measurement artifacts): "
                f"{', '.join(s.name for s in spurious)}")
        if not genuine and not spurious:
            parts.append("No emergence detected — system is in linear regime")
        return "; ".join(parts)

    def latest_report(self) -> EmergenceReport | None:
        return self._reports[-1] if self._reports else None

    def stats(self) -> dict[str, Any]:
        latest = self.latest_report()
        return {
            "metrics_tracked": len(self._series),
            "components_tracked": sum(
                len(c) for c in self._component_series.values()),
            "reports_generated": len(self._reports),
            "latest_genuine_signals": latest.genuine_count if latest else 0,
            "latest_spurious_signals": latest.spurious_count if latest else 0,
            "has_phase_transition": latest.has_phase_transition if latest else False,
        }


# ═══ Singleton ═══

_emergence_detector: EmergenceDetector | None = None


def get_emergence_detector() -> EmergenceDetector:
    global _emergence_detector
    if _emergence_detector is None:
        _emergence_detector = EmergenceDetector()
    return _emergence_detector


# ═══ Knowledge Phase Transition (Portsmouth paper inspired) ═══

@dataclass
class CriticalPoint:
    """A knowledge concept approaching critical threshold.

    Maps the Portsmouth paper's finding: language evolution follows
    phase-transition physics. When a concept's adoption crosses a
    critical point, it rapidly diffuses across the entire system —
    like "roly-poly" spreading from the US South to nationwide.

    Conceptually: knowledge equates to magnetic domains.
    Below critical point → local, isolated usage.
    Above critical point → global reorder, full system adoption.
    """
    concept: str
    current_mass: float           # e.g., reference count, mention frequency
    critical_threshold: float     # calculated from system topology
    distance_to_critical: float   # negative = below, 0 = at, positive = above
    isolation_index: float        # 0 = highly connected, 1 = isolated (like Newcastle)
    predicted_survival: float     # 0 = dying, 1 = resilient local variant
    domain: str = ""
    neighbors: list[str] = field(default_factory=list)
    time_to_critical: float = 0.0  # estimated cycles until threshold
    phase_order: float = 0.0       # 0 = gradual (second-order), 1 = abrupt (first-order)


class KnowledgePhaseDetector:
    """Detect when knowledge concepts approach phase-transition critical points.

    Maps statistical field theory to knowledge dynamics:
      - "Isolation" = low surrounding population density → concept survives (like "spelk")
      - "Critical mass" = adoption crosses threshold → rapid diffusion (like "roly-poly")
      - Global reorder trigger: N concepts simultaneously above critical → full KB reindex
    """

    def __init__(self):
        self._concepts: dict[str, CriticalPoint] = {}
        self._triggered: list[str] = []     # concepts that crossed threshold this cycle

    def feed_concept(self, name: str, mass: float, domain: str = "",
                     isolation: float = 0.0, neighbors: list[str] | None = None):
        """Update a concept's mass and check if it approaches critical."""
        cp = self._concepts.get(name)
        if cp is None:
            total_mass = sum(c.current_mass for c in self._concepts.values())
            n = max(1, len(self._concepts))
            avg = total_mass / n if total_mass > 0 else 1.0
            threshold = avg * (2.0 + isolation * 3.0)
            cp = CriticalPoint(
                concept=name, current_mass=mass,
                critical_threshold=threshold,
                distance_to_critical=0.0, isolation_index=isolation,
                predicted_survival=0.5, domain=domain,
                neighbors=neighbors or [],
            )
            self._concepts[name] = cp

        cp.current_mass = mass
        if cp.critical_threshold > 0:
            cp.distance_to_critical = mass / cp.critical_threshold - 1.0
        cp.isolation_index = isolation
        cp.neighbors = neighbors or cp.neighbors

        if cp.isolation_index > 0.7:
            cp.predicted_survival = min(0.95, 0.4 + isolation * 0.7)
            cp.critical_threshold *= (1.0 + isolation)

        if cp.distance_to_critical > 0 and name not in self._triggered:
            self._triggered.append(name)

    def get_critical_concepts(self, min_mass: float = 0.0) -> list[CriticalPoint]:
        """Get concepts approaching or past critical threshold."""
        result = []
        for c in self._concepts.values():
            if c.current_mass >= min_mass:
                ttc = 0.0
                if c.critical_threshold > 0 and c.current_mass < c.critical_threshold:
                    recent_growth = c.current_mass * 0.05
                    if recent_growth > 0:
                        ttc = (c.critical_threshold - c.current_mass) / recent_growth
                c.time_to_critical = ttc
                c.phase_order = min(1.0, abs(c.distance_to_critical) * 2)
                result.append(c)
        result.sort(key=lambda x: -x.distance_to_critical)
        return result

    def should_reorder_knowledge_graph(self) -> bool:
        """Return True if enough concepts crossed critical → trigger full KB reindex."""
        if len(self._triggered) >= max(3, len(self._concepts) * 0.15):
            self._triggered.clear()
            return True
        return False

    def stats(self) -> dict[str, int | float | bool | list[dict[str, str | int | float]]]:
        critical = self.get_critical_concepts()
        return {
            "total_concepts": len(self._concepts),
            "above_critical": sum(1 for c in critical if c.distance_to_critical > 0),
            "approaching": sum(1 for c in critical if -0.1 <= c.distance_to_critical <= 0),
            "recently_triggered": len(self._triggered),
            "top_concepts": [
                {"name": c.concept, "mass": round(c.current_mass, 2),
                 "threshold": round(c.critical_threshold, 2),
                 "survival": round(c.predicted_survival, 2),
                 "domain": c.domain}
                for c in critical[:8]
            ],
        }


_phase_detector: KnowledgePhaseDetector | None = None
_emergence_detector: EmergenceDetector | None = None


def get_emergence_detector(window_size: int = 100) -> EmergenceDetector:
    """Get or create the singleton EmergenceDetector instance."""
    global _emergence_detector
    if _emergence_detector is None:
        _emergence_detector = EmergenceDetector(window_size=window_size)
    return _emergence_detector


def get_phase_detector() -> KnowledgePhaseDetector:
    global _phase_detector
    if _phase_detector is None:
        _phase_detector = KnowledgePhaseDetector()
    return _phase_detector


__all__ = [
    "EmergenceDetector", "EmergenceSignal", "EmergenceReport",
    "get_emergence_detector",
]
