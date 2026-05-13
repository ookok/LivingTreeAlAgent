"""EvalDashboard — unified evaluation metrics across all subsystems.

Consolidates metrics from every pipeline stage, safety module, emergence
detector, and quality guard into a single rolling window for real-time
dashboard visualization and trend analysis.

Architecture:
    LifeEngine.post-cycle  →  EvalDashboard.record_cycle()
    Admin Console /metrics →  EvalDashboard.get_summary()

Metrics tracked (rolling 200-cycle window):
    - success_rate: per-cycle success score (0.0–1.0)
    - hallucination_rate: detected fabrications per cycle
    - reasoning_depth: number of vector stages processed
    - safety_alert: aggregated safety severity level
    - emergence_phase: current consciousness emergence phase
    - tokens: total tokens consumed in cycle
    - latency_ms: cycle execution time
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

EVAL_DASHBOARD_STORE = Path(".livingtree/eval_dashboard.json")


@dataclass
class CycleMetric:
    """A single cycle's metrics snapshot."""
    success_rate: float = 0.0
    hallucination_rate: float = 0.0
    reasoning_depth: int = 0
    safety_alert: str = "normal"
    emergence_phase: str = "dormant"
    tokens: int = 0
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success_rate": self.success_rate,
            "hallucination_rate": self.hallucination_rate,
            "reasoning_depth": self.reasoning_depth,
            "safety_alert": self.safety_alert,
            "emergence_phase": self.emergence_phase,
            "tokens": self.tokens,
            "latency_ms": round(self.latency_ms, 1),
            "timestamp": self.timestamp,
        }


class EvalDashboard:
    """Unified evaluation metrics across all subsystems.

    Maintains a rolling window of the last 200 cycle metrics for
    real-time statistical analysis and trend detection.

    Usage:
        dashboard = get_eval_dashboard()
        dashboard.record_cycle(ctx)
        summary = dashboard.get_summary()
    """

    MAX_WINDOW = 200
    SUMMARY_WINDOW = 50
    DEGRADATION_THRESHOLD = -0.15  # 15% drop triggers warning
    HALLUCINATION_ALERT_THRESHOLD = 0.3
    PHASE_TRANSITION_WINDOW = 20

    def __init__(self) -> None:
        self._metrics: deque[CycleMetric] = deque(maxlen=self.MAX_WINDOW)
        self._record_count: int = 0
        self._last_phase_change: float = 0.0
        self._phase_history: list[tuple[str, float]] = []
        self._load()

    # ── Record ─────────────────────────────────────────────────────

    def record_cycle(self, ctx: Any) -> None:
        """Record metrics from a completed LifeCycle context.

        Extracts relevant fields from the LifeContext metadata dict
        and appends a CycleMetric to the rolling window.

        Args:
            ctx: LifeContext instance with metadata dict populated
        """
        meta = ctx.metadata if hasattr(ctx, "metadata") else ctx

        metric = CycleMetric(
            success_rate=float(meta.get("success_rate", 0)),
            hallucination_rate=float(meta.get("hallucination_rate", 0)),
            reasoning_depth=int(meta.get("vector_stages_processed", 0)),
            safety_alert=str(meta.get("safety_asymmetry", {}).get("alert", "normal")) if isinstance(meta.get("safety_asymmetry"), dict) else "normal",
            emergence_phase=str(meta.get("emergence_phase", "dormant")),
            tokens=int(meta.get("total_tokens", 0)),
            latency_ms=float(meta.get("latency_ms", 0)),
        )

        # Track phase transitions
        if metric.emergence_phase and (
            not self._phase_history
            or self._phase_history[-1][0] != metric.emergence_phase
        ):
            self._phase_history.append((metric.emergence_phase, time.time()))
            if len(self._phase_history) > 50:
                self._phase_history = self._phase_history[-50:]
            self._last_phase_change = time.time()

        self._metrics.append(metric)
        self._record_count += 1

        # Periodic save every 20 records
        if self._record_count % 20 == 0:
            self._save()

    # ── Summary ────────────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        """Compute statistical summary over the most recent cycles.

        Returns:
            dict with avg_success, avg_hallucination, avg_depth,
            safety_alerts count, current phase, and trend indicators.
        """
        if not self._metrics:
            return {
                "total_cycles": 0,
                "window_size": 0,
                "status": "no_data",
            }

        recent_all = list(self._metrics)
        recent = recent_all[-self.SUMMARY_WINDOW:]

        n = len(recent)
        avg_success = sum(m.success_rate for m in recent) / n
        avg_hallucination = sum(m.hallucination_rate for m in recent) / n
        avg_depth = sum(m.reasoning_depth for m in recent) / n
        avg_latency = sum(m.latency_ms for m in recent) / n
        total_tokens = sum(m.tokens for m in recent)

        # Safety alerts count
        safety_alerts = sum(1 for m in recent if m.safety_alert != "normal")
        critical_alerts = sum(1 for m in recent if m.safety_alert == "critical")

        # Phase distribution
        phase_counts: dict[str, int] = {}
        for m in recent:
            phase = m.emergence_phase
            phase_counts[phase] = phase_counts.get(phase, 0) + 1

        # Trend: compare first half vs second half of recent window
        midpoint = n // 2
        if midpoint > 0:
            first_half = recent[:midpoint]
            second_half = recent[midpoint:]
            first_avg = sum(m.success_rate for m in first_half) / len(first_half)
            second_avg = sum(m.success_rate for m in second_half) / len(second_half)
            trend = second_avg - first_avg
            trend_status = (
                "improving" if trend > 0.05
                else "degrading" if trend < self.DEGRADATION_THRESHOLD
                else "stable"
            )
        else:
            first_avg = avg_success
            second_avg = avg_success
            trend = 0.0
            trend_status = "stable"

        # Hallucination alert
        hallucination_alert = avg_hallucination > self.HALLUCINATION_ALERT_THRESHOLD

        # Recent phase transitions
        recent_phases = self._phase_history[-5:] if self._phase_history else []

        return {
            "total_cycles": len(recent_all),
            "window_size": n,
            "avg_success": round(avg_success, 4),
            "avg_hallucination": round(avg_hallucination, 4),
            "avg_depth": round(avg_depth, 2),
            "avg_latency_ms": round(avg_latency, 1),
            "total_tokens": total_tokens,
            "safety_alerts": safety_alerts,
            "critical_alerts": critical_alerts,
            "phase": recent[-1].emergence_phase,
            "phase_distribution": phase_counts,
            "success_trend": round(trend, 4),
            "trend_status": trend_status,
            "hallucination_alert": hallucination_alert,
            "first_half_avg": round(first_avg, 4),
            "second_half_avg": round(second_avg, 4),
            "recent_phase_transitions": [
                {"phase": p, "timestamp": t}
                for p, t in recent_phases
            ],
            "last_recorded_at": recent[-1].timestamp,
        }

    # ── Trend Detection ────────────────────────────────────────────

    def get_trend(self, metric: str = "success_rate", window: int = 50) -> dict[str, Any]:
        """Analyze trend for a specific metric over the given window.

        Args:
            metric: One of success_rate, hallucination_rate, reasoning_depth, tokens
            window: Number of recent cycles to analyze

        Returns:
            dict with trend direction, slope, and confidence
        """
        if not self._metrics:
            return {"trend": "no_data"}

        recent = list(self._metrics)[-window:]
        n = len(recent)
        if n < 5:
            return {"trend": "insufficient_data", "samples": n}

        values = [getattr(m, metric, 0) for m in recent]

        # Simple linear regression on index
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            slope = 0.0
        else:
            slope = numerator / denominator

        # Normalize slope relative to value range
        value_range = max(values) - min(values) if max(values) != min(values) else 1.0
        normalized_slope = slope / (value_range / n) if value_range > 0 else 0.0

        direction = (
            "rising" if slope > 0.01
            else "falling" if slope < -0.01
            else "flat"
        )

        # Confidence: r-squared approximation
        predicted = [y_mean + slope * (i - x_mean) for i in range(n)]
        ss_res = sum((values[i] - predicted[i]) ** 2 for i in range(n))
        ss_tot = sum((v - y_mean) ** 2 for v in values)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        return {
            "metric": metric,
            "direction": direction,
            "slope": round(slope, 6),
            "normalized_slope": round(normalized_slope, 4),
            "r_squared": round(r_squared, 4),
            "samples": n,
            "current": values[-1],
            "window_average": round(y_mean, 4),
        }

    # ── Alerts ─────────────────────────────────────────────────────

    def check_alerts(self) -> list[dict[str, Any]]:
        """Check for alert conditions across all tracked metrics.

        Returns:
            list of alert dicts with level, metric, and message
        """
        alerts: list[dict[str, Any]] = []
        summary = self.get_summary()

        if summary.get("total_cycles", 0) < 5:
            return alerts

        # Success rate degradation
        if summary.get("trend_status") == "degrading":
            alerts.append({
                "level": "warning",
                "metric": "success_rate",
                "message": f"Success rate degrading ({summary['success_trend']:+.4f})",
                "current": summary["avg_success"],
            })

        # Hallucination spike
        if summary.get("hallucination_alert"):
            alerts.append({
                "level": "critical",
                "metric": "hallucination_rate",
                "message": f"Hallucination rate elevated ({summary['avg_hallucination']:.2%})",
                "current": summary["avg_hallucination"],
            })

        # Safety critical
        if summary.get("critical_alerts", 0) > 0:
            alerts.append({
                "level": "critical",
                "metric": "safety",
                "message": f"{summary['critical_alerts']} critical safety alerts",
            })

        # Phase regression
        phases = summary.get("phase_distribution", {})
        if "regressing" in phases:
            alerts.append({
                "level": "warning",
                "metric": "emergence",
                "message": "Consciousness phase regression detected",
            })

        return alerts

    # ── Persistence ────────────────────────────────────────────────

    def _save(self) -> None:
        """Save dashboard state to disk for continuity across restarts."""
        try:
            EVAL_DASHBOARD_STORE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "record_count": self._record_count,
                "last_phase_change": self._last_phase_change,
                "phase_history": self._phase_history[-20:],
                "recent_metrics": [m.to_dict() for m in list(self._metrics)[-50:]],
                "saved_at": time.time(),
            }
            EVAL_DASHBOARD_STORE.write_text(
                __import__("json").dumps(data, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.debug(f"EvalDashboard save: {e}")

    def _load(self) -> None:
        """Load dashboard state from disk."""
        if not EVAL_DASHBOARD_STORE.exists():
            return
        try:
            import json as _json
            data = _json.loads(EVAL_DASHBOARD_STORE.read_text(encoding="utf-8"))
            self._record_count = data.get("record_count", 0)
            self._last_phase_change = data.get("last_phase_change", 0.0)
            self._phase_history = data.get("phase_history", [])
            for m_dict in data.get("recent_metrics", []):
                self._metrics.append(CycleMetric(
                    success_rate=m_dict.get("success_rate", 0),
                    hallucination_rate=m_dict.get("hallucination_rate", 0),
                    reasoning_depth=m_dict.get("reasoning_depth", 0),
                    safety_alert=m_dict.get("safety_alert", "normal"),
                    emergence_phase=m_dict.get("emergence_phase", "dormant"),
                    tokens=m_dict.get("tokens", 0),
                    latency_ms=m_dict.get("latency_ms", 0),
                    timestamp=m_dict.get("timestamp", time.time()),
                ))
            logger.info(f"EvalDashboard: loaded {len(self._metrics)} metrics from disk")
        except Exception as e:
            logger.debug(f"EvalDashboard load: {e}")

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return dashboard statistics."""
        return {
            "records": len(self._metrics),
            "total_recorded": self._record_count,
            "max_window": self.MAX_WINDOW,
            "current_phase": self._metrics[-1].emergence_phase if self._metrics else "none",
            "phase_changes": len(self._phase_history),
            "last_phase_change": self._last_phase_change,
        }


# ═══ Singleton ═══

_eval_dashboard: EvalDashboard | None = None


def get_eval_dashboard() -> EvalDashboard:
    """Get or create the global EvalDashboard singleton."""
    global _eval_dashboard
    if _eval_dashboard is None:
        _eval_dashboard = EvalDashboard()
        logger.info("EvalDashboard singleton created")
    return _eval_dashboard


__all__ = [
    "CycleMetric",
    "EvalDashboard",
    "get_eval_dashboard",
]
