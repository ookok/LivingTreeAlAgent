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


__all__ = [
    "EmergenceDetector", "EmergenceSignal", "EmergenceReport",
    "get_emergence_detector",
]
