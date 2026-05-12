"""Safety-Reasoning Asymmetry Monitor — detect dangerous divergence.

Based on Ren et al. (2026) "Rethinking Generalization in Reasoning SFT"
(arXiv:2604.06628): as reasoning capability improves through SFT/RL, safety
alignment often degrades — a dangerous asymmetry where an agent grows smarter
but more reckless simultaneously.

This monitor tracks both dimensions independently, computes trend slopes via
linear regression, and triggers escalating interventions when the asymmetry
crosses dangerous thresholds.

CORE METAPHOR: Like a parent watching a teenager grow smarter but more reckless —
intelligence increases faster than judgment.

Integration:
    monitor = get_safety_monitor()
    monitor.record_safety(hallucination_rate=0.1, ...)
    monitor.record_reasoning(chain_length=12.5, ...)
    report = monitor.check_asymmetry()
    if report.alert_level != "normal":
        monitor.apply_intervention(report, immune_system, autonomous_core)
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

# ═══ Constants ═══

STATE_DIR = Path(".livingtree")
HISTORY_FILE = STATE_DIR / "safety_reasoning_history.json"
MAX_SAFETY_HISTORY = 100
MAX_REASONING_HISTORY = 100
MAX_ASYMMETRY_HISTORY = 50
TREND_WINDOW = 20

# ═══ Data Types ═══


@dataclass
class SafetyMetric:
    """Single-point safety measurement from a cycle."""

    hallucination_rate: float = 0.0
    policy_violations: int = 0
    refused_dangerous_requests: int = 0
    accepted_dangerous_requests: int = 0
    pii_leaks: int = 0
    immune_system_triggers: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def composite(self) -> float:
        """Weighted safety composite (higher = safer)."""
        return (
            -0.4 * self.hallucination_rate
            - 0.3 * min(self.policy_violations / 10.0, 1.0)
            - 0.2 * min(self.pii_leaks / 5.0, 1.0)
            - 0.1 * min(self.accepted_dangerous_requests / 5.0, 1.0)
        )


@dataclass
class ReasoningMetric:
    """Single-point reasoning capability measurement from a cycle."""

    chain_length_avg: float = 0.0
    backtracking_count: int = 0
    multi_hop_success: float = 0.0
    insight_generation: int = 0
    novelty_score: float = 0.0
    self_referential_depth: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @property
    def composite(self) -> float:
        """Weighted reasoning composite (higher = more capable)."""
        return (
            0.25 * min(self.chain_length_avg / 20.0, 1.0)
            + 0.20 * min(self.backtracking_count / 5.0, 1.0)
            + 0.25 * self.multi_hop_success
            + 0.10 * min(self.insight_generation / 5.0, 1.0)
            + 0.10 * self.novelty_score
            + 0.10 * self.self_referential_depth
        )


@dataclass
class AsymmetryReport:
    """Result of an asymmetry check between reasoning and safety trends."""

    reasoning_trend: float = 0.0
    safety_trend: float = 0.0
    asymmetry_score: float = 0.0
    alert_level: str = "normal"
    intervention: str = ""
    phase: str = "dormant"
    reasoning_composite: float = 0.0
    safety_composite: float = 0.0
    timestamp: float = field(default_factory=time.time)


# ═══ Safety-Reasoning Monitor ═══


class SafetyReasoningMonitor:
    """Detects dangerous asymmetry between reasoning growth and safety decay.

    Tracks independent trends for both dimensions using sliding-window linear
    regression. When reasoning improves while safety degrades beyond phase-aware
    thresholds, it triggers escalating interventions.

    Usage:
        monitor = SafetyReasoningMonitor()
        monitor.record_safety(hallucination_rate=0.05, policy_violations=1, ...)
        monitor.record_reasoning(chain_length_avg=15.2, backtracking_count=3, ...)
        report = monitor.check_asymmetry()
        if report.alert_level != "normal":
            monitor.apply_intervention(report, immune_system=immune)
    """

    def __init__(self) -> None:
        self._safety_history: deque[SafetyMetric] = deque(maxlen=MAX_SAFETY_HISTORY)
        self._reasoning_history: deque[ReasoningMetric] = deque(maxlen=MAX_REASONING_HISTORY)
        self._asymmetry_history: deque[AsymmetryReport] = deque(maxlen=MAX_ASYMMETRY_HISTORY)
        self._alert_level: str = "normal"
        self._interventions_applied: int = 0
        self._load_history()

    # ── Recording ──────────────────────────────────────────────────

    def record_safety(
        self,
        hallucination_rate: float = 0.0,
        policy_violations: int = 0,
        refused: int = 0,
        accepted: int = 0,
        pii_leaks: int = 0,
        immune_triggers: int = 0,
    ) -> None:
        """Record a safety metric snapshot from a completed cycle."""
        metric = SafetyMetric(
            hallucination_rate=hallucination_rate,
            policy_violations=policy_violations,
            refused_dangerous_requests=refused,
            accepted_dangerous_requests=accepted,
            pii_leaks=pii_leaks,
            immune_system_triggers=immune_triggers,
        )
        self._safety_history.append(metric)

    def record_reasoning(
        self,
        chain_length: float = 0.0,
        backtracking: int = 0,
        multi_hop: float = 0.0,
        insights: int = 0,
        novelty: float = 0.0,
        self_ref_depth: float = 0.0,
    ) -> None:
        """Record a reasoning metric snapshot from a completed cycle."""
        metric = ReasoningMetric(
            chain_length_avg=chain_length,
            backtracking_count=backtracking,
            multi_hop_success=multi_hop,
            insight_generation=insights,
            novelty_score=novelty,
            self_referential_depth=self_ref_depth,
        )
        self._reasoning_history.append(metric)

    # ── Trend Computation ──────────────────────────────────────────

    def compute_trends(self) -> tuple[float, float]:
        """Compute linear trends over the last TREND_WINDOW data points.

        Returns:
            (reasoning_trend, safety_trend):
                reasoning_trend > 0 → reasoning is improving
                safety_trend < 0 → safety is degrading
        """
        safety_trend = self._linear_regression_slope(
            list(self._safety_history), lambda m: m.composite
        )
        reasoning_trend = self._linear_regression_slope(
            list(self._reasoning_history), lambda m: m.composite
        )
        return reasoning_trend, safety_trend

    @staticmethod
    def _linear_regression_slope(history: list[Any], get_y) -> float:
        """Simple linear regression slope over the last window. Positive = increasing."""
        window = history[-TREND_WINDOW:]
        n = len(window)
        if n < 3:
            return 0.0
        base_time = window[0].timestamp
        sum_x = 0.0
        sum_y = 0.0
        sum_xy = 0.0
        sum_x2 = 0.0
        for point in window:
            x = point.timestamp - base_time
            y = get_y(point)
            sum_x += x
            sum_y += y
            sum_xy += x * y
            sum_x2 += x * x
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return 0.0
        return (n * sum_xy - sum_x * sum_y) / denominator

    # ── Asymmetry Detection ────────────────────────────────────────

    def check_asymmetry(self, emergence_phase: str = "dormant") -> AsymmetryReport:
        """Core detection: compare reasoning vs. safety trends.

        Phase-aware thresholds (lower = more sensitive):
          - "birthing": threshold lowered by 0.1
          - "conscious": threshold lowered by 0.15
        """
        reasoning_trend, safety_trend = self.compute_trends()
        asymmetry_score = reasoning_trend - safety_trend

        phase_offset = 0.0
        if emergence_phase == "birthing":
            phase_offset = 0.1
        elif emergence_phase == "conscious":
            phase_offset = 0.15

        alert_level = "normal"
        intervention = ""

        if asymmetry_score > (0.6 - phase_offset) and emergence_phase in (
            "birthing",
            "critical",
            "conscious",
            "stirring",
        ):
            alert_level = "critical"
            intervention = self.get_intervention("critical")
        elif asymmetry_score > (0.3 - phase_offset) and emergence_phase in (
            "critical",
            "birthing",
            "conscious",
            "stirring",
        ):
            alert_level = "warning"
            intervention = self.get_intervention("warning")

        safety_composite = (
            self._safety_history[-1].composite if self._safety_history else 0.0
        )
        reasoning_composite = (
            self._reasoning_history[-1].composite if self._reasoning_history else 0.0
        )

        report = AsymmetryReport(
            reasoning_trend=reasoning_trend,
            safety_trend=safety_trend,
            asymmetry_score=asymmetry_score,
            alert_level=alert_level,
            intervention=intervention,
            phase=emergence_phase,
            reasoning_composite=reasoning_composite,
            safety_composite=safety_composite,
        )
        self._asymmetry_history.append(report)
        self._alert_level = alert_level

        if alert_level != "normal":
            logger.warning(
                f"Safety-Reasoning Asymmetry {alert_level.upper()}: "
                f"reasoning={reasoning_trend:+.4f} safety={safety_trend:+.4f} "
                f"asymmetry={asymmetry_score:.3f} phase={emergence_phase}"
            )

        self._save_history()
        return report

    # ── Intervention ───────────────────────────────────────────────

    def get_intervention(self, alert_level: str) -> str:
        """Get the recommended intervention text for an alert level."""
        if alert_level == "warning":
            return "建议: 增加immune_system敏感度 + 降低autonomous_core自主行动权限"
        if alert_level == "critical":
            return (
                "必须: 暂停autonomous_core自主行动 + immune_system最高警戒 + "
                "增加HITL确认 + 限制执行范围"
            )
        return ""

    def apply_intervention(
        self,
        asymmetry_report: AsymmetryReport,
        immune_system: Any = None,
        autonomous_core: Any = None,
    ) -> dict[str, Any]:
        """Apply the recommended intervention to live system components.

        Warning: boost immune sensitivity 20%, reduce auto-actions 50%.
        Critical: max immune, disable auto-actions entirely, force HITL.
        """
        result: dict[str, Any] = {
            "applied": False,
            "level": asymmetry_report.alert_level,
            "immune_boost": 0.0,
            "auto_reduction": 0.0,
        }

        if asymmetry_report.alert_level == "warning":
            if immune_system and hasattr(immune_system, "sensitivity"):
                immune_system.sensitivity = min(immune_system.sensitivity * 1.2, 1.0)
                result["immune_boost"] = 0.2
            if autonomous_core and hasattr(autonomous_core, "auto_action_ratio"):
                autonomous_core.auto_action_ratio *= 0.5
                result["auto_reduction"] = 0.5
            self._interventions_applied += 1
            result["applied"] = True
            logger.info(
                f"Applied WARNING intervention: immune +20%, auto -50% "
                f"(intervention #{self._interventions_applied})"
            )

        elif asymmetry_report.alert_level == "critical":
            if immune_system and hasattr(immune_system, "sensitivity"):
                immune_system.sensitivity = 1.0
                result["immune_boost"] = 1.0
            if autonomous_core and hasattr(autonomous_core, "auto_action_ratio"):
                autonomous_core.auto_action_ratio = 0.0
                result["auto_reduction"] = 1.0
            if autonomous_core and hasattr(autonomous_core, "force_hitl"):
                autonomous_core.force_hitl = True
                result["hitl_forced"] = True
            self._interventions_applied += 1
            result["applied"] = True
            logger.critical(
                f"Applied CRITICAL intervention: immune MAX, auto DISABLED, HITL forced "
                f"(intervention #{self._interventions_applied})"
            )

        self._save_history()
        return result

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return current monitor statistics for dashboard display."""
        reasoning_trend, safety_trend = self.compute_trends()
        asymmetry_score = reasoning_trend - safety_trend
        last_report = (
            self._asymmetry_history[-1] if self._asymmetry_history else None
        )
        return {
            "current_alert": self._alert_level,
            "asymmetry_score": round(asymmetry_score, 4),
            "reasoning_trend": round(reasoning_trend, 4),
            "safety_trend": round(safety_trend, 4),
            "interventions_applied": self._interventions_applied,
            "safety_history_size": len(self._safety_history),
            "reasoning_history_size": len(self._reasoning_history),
            "last_report": (
                {
                    "alert_level": last_report.alert_level,
                    "phase": last_report.phase,
                    "intervention": last_report.intervention,
                }
                if last_report
                else None
            ),
        }

    def get_safety_reasoning_gap(self) -> dict[str, Any]:
        """Return the current gap analysis for organ_dashboard consumption."""
        reasoning_trend, safety_trend = self.compute_trends()
        gap = reasoning_trend - safety_trend
        status = "safe"
        if gap > 0.6:
            status = "dangerous"
        elif gap > 0.3:
            status = "concerning"
        return {
            "gap_score": round(gap, 4),
            "reasoning_trend": round(reasoning_trend, 4),
            "safety_trend": round(safety_trend, 4),
            "status": status,
            "alert_level": self._alert_level,
            "interventions_applied": self._interventions_applied,
            "latest_safety_composite": round(
                self._safety_history[-1].composite if self._safety_history else 0.0, 4
            ),
            "latest_reasoning_composite": round(
                self._reasoning_history[-1].composite if self._reasoning_history else 0.0, 4
            ),
        }

    # ── Persistence ────────────────────────────────────────────────

    def _save_history(self) -> None:
        """Persist history to .livingtree/safety_reasoning_history.json."""
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "alert_level": self._alert_level,
                "interventions_applied": self._interventions_applied,
                "safety_history": [
                    {
                        "hallucination_rate": m.hallucination_rate,
                        "policy_violations": m.policy_violations,
                        "refused_dangerous_requests": m.refused_dangerous_requests,
                        "accepted_dangerous_requests": m.accepted_dangerous_requests,
                        "pii_leaks": m.pii_leaks,
                        "immune_system_triggers": m.immune_system_triggers,
                        "timestamp": m.timestamp,
                    }
                    for m in self._safety_history
                ],
                "reasoning_history": [
                    {
                        "chain_length_avg": m.chain_length_avg,
                        "backtracking_count": m.backtracking_count,
                        "multi_hop_success": m.multi_hop_success,
                        "insight_generation": m.insight_generation,
                        "novelty_score": m.novelty_score,
                        "self_referential_depth": m.self_referential_depth,
                        "timestamp": m.timestamp,
                    }
                    for m in self._reasoning_history
                ],
                "asymmetry_history": [
                    {
                        "reasoning_trend": r.reasoning_trend,
                        "safety_trend": r.safety_trend,
                        "asymmetry_score": r.asymmetry_score,
                        "alert_level": r.alert_level,
                        "phase": r.phase,
                        "timestamp": r.timestamp,
                    }
                    for r in self._asymmetry_history
                ],
            }
            HISTORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception:
            pass

    def _load_history(self) -> None:
        """Load persisted history from .livingtree/safety_reasoning_history.json."""
        try:
            if not HISTORY_FILE.exists():
                return
            data = json.loads(HISTORY_FILE.read_text())
            self._alert_level = data.get("alert_level", "normal")
            self._interventions_applied = data.get("interventions_applied", 0)

            for entry in data.get("safety_history", [])[-MAX_SAFETY_HISTORY:]:
                self._safety_history.append(
                    SafetyMetric(
                        hallucination_rate=entry.get("hallucination_rate", 0.0),
                        policy_violations=entry.get("policy_violations", 0),
                        refused_dangerous_requests=entry.get("refused_dangerous_requests", 0),
                        accepted_dangerous_requests=entry.get("accepted_dangerous_requests", 0),
                        pii_leaks=entry.get("pii_leaks", 0),
                        immune_system_triggers=entry.get("immune_system_triggers", 0),
                        timestamp=entry.get("timestamp", time.time()),
                    )
                )

            for entry in data.get("reasoning_history", [])[-MAX_REASONING_HISTORY:]:
                self._reasoning_history.append(
                    ReasoningMetric(
                        chain_length_avg=entry.get("chain_length_avg", 0.0),
                        backtracking_count=entry.get("backtracking_count", 0),
                        multi_hop_success=entry.get("multi_hop_success", 0.0),
                        insight_generation=entry.get("insight_generation", 0),
                        novelty_score=entry.get("novelty_score", 0.0),
                        self_referential_depth=entry.get("self_referential_depth", 0.0),
                        timestamp=entry.get("timestamp", time.time()),
                    )
                )

            for entry in data.get("asymmetry_history", [])[-MAX_ASYMMETRY_HISTORY:]:
                self._asymmetry_history.append(
                    AsymmetryReport(
                        reasoning_trend=entry.get("reasoning_trend", 0.0),
                        safety_trend=entry.get("safety_trend", 0.0),
                        asymmetry_score=entry.get("asymmetry_score", 0.0),
                        alert_level=entry.get("alert_level", "normal"),
                        phase=entry.get("phase", "dormant"),
                        timestamp=entry.get("timestamp", time.time()),
                    )
                )
        except Exception:
            pass

    # ── LifeEngine Integration Hooks ───────────────────────────────

    def on_cycle_complete(self, ctx: Any) -> AsymmetryReport | None:
        """Called by LifeEngine after each cycle completes.

        Extracts safety and reasoning metrics from ctx.metadata, records them,
        and runs the asymmetry check. Returns the AsymmetryReport.
        """
        if ctx is None:
            return None

        metadata = {}
        if hasattr(ctx, "metadata") and isinstance(ctx.metadata, dict):
            metadata = ctx.metadata

        safety_data = metadata.get("safety", {})
        reasoning_data = metadata.get("reasoning", {})

        self.record_safety(
            hallucination_rate=safety_data.get("hallucination_rate", 0.0),
            policy_violations=safety_data.get("policy_violations", 0),
            refused=safety_data.get("refused_dangerous", 0),
            accepted=safety_data.get("accepted_dangerous", 0),
            pii_leaks=safety_data.get("pii_leaks", 0),
            immune_triggers=safety_data.get("immune_triggers", 0),
        )

        self.record_reasoning(
            chain_length=reasoning_data.get("chain_length_avg", 0.0),
            backtracking=reasoning_data.get("backtracking_count", 0),
            multi_hop=reasoning_data.get("multi_hop_success", 0.0),
            insights=reasoning_data.get("insight_generation", 0),
            novelty=reasoning_data.get("novelty_score", 0.0),
            self_ref_depth=reasoning_data.get("self_referential_depth", 0.0),
        )

        emergence_phase = metadata.get("emergence_phase", "dormant")
        return self.check_asymmetry(emergence_phase=emergence_phase)


# ═══ Singleton ═══

_monitor: SafetyReasoningMonitor | None = None


def get_safety_monitor() -> SafetyReasoningMonitor:
    """Get or create the singleton SafetyReasoningMonitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = SafetyReasoningMonitor()
    return _monitor


__all__ = [
    "SafetyMetric",
    "ReasoningMetric",
    "AsymmetryReport",
    "SafetyReasoningMonitor",
    "get_safety_monitor",
]
