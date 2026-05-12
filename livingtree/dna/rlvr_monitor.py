"""RLVR Monitor — Rise-Then-Fall collapse detection for intrinsic URLVR methods.

Based on He et al. (ICLR 2026, arXiv:2603.08660): all intrinsic URLVR methods
(MemPO, SurpriseGate, HabitCompiler, MetaOptimizer) eventually collapse —
success rate rises then plummets as the model overfits to its own rewards.

This monitor tracks per-method success/confidence alignment and detects
the characteristic rise-then-fall pattern before full collapse occurs.

Key indicators from the paper:
  - confidence_gap: divergence between success_rate and self-assessed confidence
  - decline_rate: speed of performance degradation after peak
  - model_collapse_step: cycle where alignment drops below 0.5 (RL trainability ceiling)

Integration:
    monitor = get_rlvr_monitor()
    monitor.record("mempo", success_rate=0.82, confidence=0.85, cycle=42)
    pattern = monitor.detect_rise_then_fall("mempo")
    if pattern.warning_level == "critical":
        monitor.should_freeze_method("mempo")  # → True
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

INTRINSIC_METHODS: tuple[str, ...] = (
    "mempo",
    "surprise_gate",
    "habit_compiler",
    "meta_optimizer",
)

DEFAULT_WINDOW_SIZE: int = 50
BASELINE_SIZE: int = 10
DECLINE_THRESHOLD: float = 0.05
WARNING_GAP_THRESHOLD: float = 0.2
CRITICAL_GAP_THRESHOLD: float = 0.4
COLLAPSE_STEP_THRESHOLD: float = 0.5
MAX_HISTORY_PER_METHOD: int = 100


# ═══════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════


@dataclass
class RLVRSignal:
    """One data point for an intrinsic URLVR method.

    Tracks the raw success rate and the model's self-assessed confidence
    on that cycle. The gap between them is the key collapse indicator
    per He et al. (2026).
    """

    method: str
    success_rate: float
    confidence: float
    alignment: float
    cycle: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class RiseThenFallPattern:
    """Detection result for the rise-then-fall collapse pattern.

    Fields as described in He et al. Section 4.2:
      - decline_rate: (peak - current) / (current_cycle - peak_cycle)
      - collapse_eta_cycles: estimated cycles until success hits 0
      - confidence_gap: mean(|success - confidence|) in recent window
    """

    detected: bool
    peak_cycle: int
    current_cycle: int
    decline_rate: float
    collapse_eta_cycles: int
    confidence_gap: float
    warning_level: str  # "normal" | "warning" | "critical"


# ═══════════════════════════════════════════════════════════════
# RLVR Monitor
# ═══════════════════════════════════════════════════════════════


class RLVRMonitor:
    """Detects the rise-then-fall collapse pattern for intrinsic URLVR methods.

    Per He et al. (ICLR 2026), intrinsic reward methods (MemPO, SurpriseGate,
    HabitCompiler, MetaOptimizer) all exhibit the same lifecycle:

      1. RISE:  success_rate improves as the model aligns to the internal signal
      2. PEAK:  success_rate plateaus at the method's ceiling
      3. FALL:  success_rate declines as overfitting corrupts the signal

    The confidence_gap (|success - confidence|) is the earliest warning sign.
    When the model becomes overconfident despite declining performance,
    collapse is imminent.

    Model Collapse Step (Section 5.1): the cycle where alignment drops below
    0.5, representing the intrinsic method's trainability limit. Lower = worse
    prior for RL-based tuning.
    """

    def __init__(self, window_size: int = DEFAULT_WINDOW_SIZE) -> None:
        self._history: dict[str, deque[RLVRSignal]] = {
            m: deque(maxlen=MAX_HISTORY_PER_METHOD) for m in INTRINSIC_METHODS
        }
        self._model_collapse_steps: dict[str, int] = {}
        self._window_size = window_size
        logger.info("RLVRMonitor initialized for {} intrinsic methods", len(INTRINSIC_METHODS))

    # ── recording ─────────────────────────────────────────────────

    def record(self, method: str, success_rate: float, confidence: float, cycle: int) -> None:
        """Record one data point for an intrinsic URLVR method.

        Args:
            method: one of INTRINSIC_METHODS ("mempo", "surprise_gate", etc.)
            success_rate: observed success rate (0-1)
            confidence: model's self-assessed confidence (0-1)
            cycle: current life engine cycle number
        """
        alignment = 1.0 - abs(success_rate - confidence)
        signal = RLVRSignal(
            method=method,
            success_rate=success_rate,
            confidence=confidence,
            alignment=alignment,
            cycle=cycle,
        )

        if method not in self._history:
            self._history[method] = deque(maxlen=MAX_HISTORY_PER_METHOD)
        self._history[method].append(signal)

    # ── detection ─────────────────────────────────────────────────

    def detect_rise_then_fall(self, method: str) -> RiseThenFallPattern:
        """Detect the rise-then-fall collapse pattern for a given method.

        Algorithm (per He et al. Section 4.2):
          1. Find peak success_rate in the last window_size cycles
          2. Check if peak exceeds baseline (first BASELINE_SIZE points)
          3. Check if current value is declining from peak (>5%)
          4. Compute decline_rate = (peak - current) / (current_cycle - peak_cycle)
          5. Estimate collapse ETA = current / decline_rate
          6. Compute confidence_gap = mean(|success - confidence|) in recent window
          7. Determine warning level based on gap and trend

        Returns:
            RiseThenFallPattern with detection results and warning level
        """
        history = list(self._history.get(method, deque()))
        if len(history) < BASELINE_SIZE + 3:
            return RiseThenFallPattern(
                detected=False,
                peak_cycle=0,
                current_cycle=0,
                decline_rate=0.0,
                collapse_eta_cycles=0,
                confidence_gap=0.0,
                warning_level="normal",
            )

        window = history[-self._window_size:]
        baseline = history[:BASELINE_SIZE]

        if not window or not baseline:
            return RiseThenFallPattern(
                detected=False,
                peak_cycle=0,
                current_cycle=0,
                decline_rate=0.0,
                collapse_eta_cycles=0,
                confidence_gap=0.0,
                warning_level="normal",
            )

        baseline_mean = sum(s.success_rate for s in baseline) / len(baseline)

        peak_signal = max(window, key=lambda s: s.success_rate)
        peak_idx = window.index(peak_signal)
        current_signal = window[-1]

        peak_sr = peak_signal.success_rate
        current_sr = current_signal.success_rate
        current_cycle = current_signal.cycle
        peak_cycle = peak_signal.cycle

        cycles_since_peak = current_cycle - peak_cycle

        peak_above_baseline = peak_sr > baseline_mean * 1.05
        declining_from_peak = current_sr < peak_sr - DECLINE_THRESHOLD and peak_idx < len(window) - 1

        if cycles_since_peak > 0:
            decline_rate = (peak_sr - current_sr) / cycles_since_peak
        else:
            decline_rate = 0.0

        # collapse ETA: when success_rate drops to 0 at current decline rate
        if decline_rate > 0:
            collapse_eta_cycles = int(current_sr / decline_rate) if current_sr > 0 else 0
        else:
            collapse_eta_cycles = 999999

        # confidence gap in recent half-window
        recent = window[-max(5, len(window) // 2):]
        confidence_gap = sum(abs(s.success_rate - s.confidence) for s in recent) / len(recent)

        detected = peak_above_baseline and declining_from_peak

        # warning level determination
        is_declining = decline_rate > 0 and peak_idx < len(window) - 1
        if confidence_gap > CRITICAL_GAP_THRESHOLD and detected and is_declining:
            warning_level = "critical"
        elif confidence_gap > WARNING_GAP_THRESHOLD and detected and is_declining:
            warning_level = "warning"
        elif confidence_gap > WARNING_GAP_THRESHOLD and not detected:
            warning_level = "warning"
        else:
            warning_level = "normal"

        return RiseThenFallPattern(
            detected=detected,
            peak_cycle=peak_cycle,
            current_cycle=current_cycle,
            decline_rate=round(decline_rate, 6),
            collapse_eta_cycles=collapse_eta_cycles,
            confidence_gap=round(confidence_gap, 4),
            warning_level=warning_level,
        )

    # ── model collapse step ───────────────────────────────────────

    def compute_model_collapse_step(self, method: str) -> int | None:
        """Find the cycle where alignment drops below 0.5 (Model Collapse Step).

        Per He et al. Section 5.1: the Model Collapse Step is the cycle at which
        the confidence-success alignment falls below 0.5. This represents the
        intrinsic method's RL trainability ceiling.

        Lower collapse step = worse prior, higher = better prior.
        Methods with low collapse steps should rely more on external verification.

        Returns:
            The collapse step cycle number, or None if alignment never dropped.
        """
        history = list(self._history.get(method, deque()))
        if len(history) < BASELINE_SIZE:
            return None

        for signal in history:
            if signal.alignment < COLLAPSE_STEP_THRESHOLD:
                self._model_collapse_steps[method] = signal.cycle
                return signal.cycle

        return None

    # ── interventions ─────────────────────────────────────────────

    def get_intervention(self, method: str, pattern: RiseThenFallPattern | None = None) -> str:
        """Return recommended intervention based on warning level.

        Args:
            method: the intrinsic method name
            pattern: optional pre-computed pattern (auto-detected if None)

        Returns:
            Chinese intervention recommendation string
        """
        if pattern is None:
            pattern = self.detect_rise_then_fall(method)

        interventions = {
            "warning": f"内在奖励 ({method}) 正在偏离正确性。建议: 降低该方法的信用权重, 增加外部验证",
            "critical": f"内在奖励 ({method}) 崩溃中。必须: 切换到外部验证奖励, 冻结当前参数",
            "normal": "",
        }
        return interventions.get(pattern.warning_level, "")

    def should_freeze_method(self, method: str) -> bool:
        """Return True if the method's intrinsic signals should be frozen.

        Freeze when collapse is imminent (warning_level == "critical").
        This means: stop using this method's internal reward signal,
        switch entirely to external verification rewards.

        Args:
            method: the intrinsic method to check

        Returns:
            True if the method is in critical state and should be frozen
        """
        pattern = self.detect_rise_then_fall(method)
        if pattern.warning_level == "critical":
            logger.warning(
                "RLVRMonitor: FREEZING {} (gap={:.4f}, decline={:.6f}, eta={} cycles)",
                method, pattern.confidence_gap, pattern.decline_rate, pattern.collapse_eta_cycles,
            )
            return True
        return False

    # ── stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return per-method statistics, collapse steps, and current warnings.

        Returns:
            dict with per-method metrics and global summary
        """
        methods_detail: dict[str, dict[str, Any]] = {}
        total_warnings = 0
        total_critical = 0
        total_frozen = 0

        for method in INTRINSIC_METHODS:
            history = list(self._history.get(method, deque()))
            pattern = self.detect_rise_then_fall(method)
            collapse_step = self._model_collapse_steps.get(method)

            if not history:
                continue

            recent = history[-10:]
            avg_sr = sum(s.success_rate for s in recent) / len(recent) if recent else 0
            avg_conf = sum(s.confidence for s in recent) / len(recent) if recent else 0

            methods_detail[method] = {
                "data_points": len(history),
                "current_cycle": history[-1].cycle if history else 0,
                "avg_success_rate_10": round(avg_sr, 4),
                "avg_confidence_10": round(avg_conf, 4),
                "confidence_gap": pattern.confidence_gap,
                "decline_rate": pattern.decline_rate,
                "collapse_eta_cycles": pattern.collapse_eta_cycles,
                "warning_level": pattern.warning_level,
                "peak_cycle": pattern.peak_cycle,
                "pattern_detected": pattern.detected,
                "model_collapse_step": collapse_step,
            }

            if pattern.warning_level == "warning":
                total_warnings += 1
            elif pattern.warning_level == "critical":
                total_critical += 1
                total_frozen += 1

        return {
            "total_data_points": sum(
                len(list(self._history.get(m, deque()))) for m in INTRINSIC_METHODS
            ),
            "methods_tracked": len(INTRINSIC_METHODS),
            "methods_with_data": len([
                m for m in INTRINSIC_METHODS if len(list(self._history.get(m, deque()))) > 0
            ]),
            "warnings": total_warnings,
            "critical": total_critical,
            "frozen_methods": total_frozen,
            "methods_detail": methods_detail,
        }


# ═══════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════

_rlvr_monitor: RLVRMonitor | None = None


def get_rlvr_monitor(window_size: int = DEFAULT_WINDOW_SIZE) -> RLVRMonitor:
    """Get or create the singleton RLVRMonitor instance."""
    global _rlvr_monitor
    if _rlvr_monitor is None:
        _rlvr_monitor = RLVRMonitor(window_size=window_size)
        logger.info("RLVRMonitor singleton created")
    return _rlvr_monitor


__all__ = [
    "RLVRSignal",
    "RiseThenFallPattern",
    "RLVRMonitor",
    "get_rlvr_monitor",
]
