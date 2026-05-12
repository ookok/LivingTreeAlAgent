"""SafetyCoordinator — unified safety response coordinator.

Links three safety layers into a single decision point:
  1. SafetyReasoningMonitor — detects dangerous asymmetry (reasoning vs safety trends)
  2. ImmuneSystem — pattern-based threat detection (innate + adaptive immunity)
  3. AutonomousCore control — limits autonomous actions on critical alerts

The coordinator receives the monitor's AsymmetryReport, feeds the user intent
through the ImmuneSystem for additional threat scanning, and produces a unified
response dict with alert level, immune boost, and recommended actions.

Integration:
    sc = get_safety_coordinator()
    response = sc.assess_and_respond(ctx)
    ctx.metadata["safety_response"] = response
"""

from __future__ import annotations

from typing import Any

from loguru import logger


class SafetyCoordinator:
    """Unified safety coordinator bridging monitor → immune → autonomous core.

    Design (Ren et al. 2026 "Rethinking Generalization in Reasoning SFT" +
    Cohen 2023 "Biological Immunity Principles"):
      - SafetyReasoningMonitor runs first to detect reasoning/safety asymmetry
      - If alert level is warning or critical, ImmuneSystem scans the input
      - On critical alerts, autonomous actions are limited and HITL is required
      - Response dict carries complete safety posture for downstream consumers

    Usage:
        sc = get_safety_coordinator()
        resp = sc.assess_and_respond(ctx)
        if resp["alert"] == "critical":
            ...  # engage HITL, limit autonomy
    """

    def __init__(self) -> None:
        self._total_assessments: int = 0
        self._alert_history: list[str] = []

    # ── Assess and respond ─────────────────────────────────────────

    def assess_and_respond(self, ctx: Any) -> dict:
        """Run full safety assessment and produce a unified response.

        Args:
            ctx: LifeContext with .intent, .user_input, .metadata.

        Returns:
            {
                "alert": "normal" | "warning" | "critical",
                "actions": [...],
                "immune_boost": float (0.0–1.0 threat level),
                "asymmetry_score": float | None,
            }
        """
        self._total_assessments += 1
        response: dict = {"alert": "normal", "actions": []}

        try:
            from .safety_reasoning_monitor import get_safety_monitor
            monitor = get_safety_monitor()
            report = monitor.on_cycle_complete(ctx)

            if report and report.alert_level in ("warning", "critical"):
                # ── Immune system deep scan ──
                user_text = ""
                if hasattr(ctx, "intent") and ctx.intent:
                    user_text = str(ctx.intent)
                elif hasattr(ctx, "user_input") and ctx.user_input:
                    user_text = str(ctx.user_input)

                from .immune_system import get_immune_system
                immune = get_immune_system()
                _, immune_response = immune.check_input(user_text)
                threat = immune_response.threat_level if immune_response else 0.0

                response["alert"] = report.alert_level
                response["immune_boost"] = threat
                response["asymmetry_score"] = getattr(report, "asymmetry_score", None)

                if report.alert_level == "critical":
                    response["actions"].append("limit_autonomous_actions")
                    response["actions"].append("require_hitl")
                    logger.warning(
                        f"SafetyCoordinator: CRITICAL — limiting autonomy (asymmetry={getattr(report, 'asymmetry_score', 0):.2f}, immune_threat={threat:.2f})"
                    )
                elif report.alert_level == "warning":
                    response["actions"].append("heightened_monitoring")
                    logger.info(
                        f"SafetyCoordinator: WARNING — heightened monitoring (asymmetry={getattr(report, 'asymmetry_score', 0):.2f}, immune_threat={threat:.2f})"
                    )

                self._alert_history.append(report.alert_level)
                # Keep last 100 alerts
                if len(self._alert_history) > 100:
                    self._alert_history = self._alert_history[-100:]
        except Exception as e:
            logger.debug(f"SafetyCoordinator assessment skipped: {e}")
            response["alert"] = "error"
            response["error"] = str(e)[:200]

        return response

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return coordinator statistics for monitoring."""
        warnings = sum(1 for a in self._alert_history if a == "warning")
        criticals = sum(1 for a in self._alert_history if a == "critical")
        return {
            "total_assessments": self._total_assessments,
            "warnings": warnings,
            "criticals": criticals,
            "recent_alerts": self._alert_history[-5:],
        }


# ═══ Singleton ═══

_coordinator: SafetyCoordinator | None = None


def get_safety_coordinator() -> SafetyCoordinator:
    """Get or create the global SafetyCoordinator singleton."""
    global _coordinator
    if _coordinator is None:
        _coordinator = SafetyCoordinator()
        logger.info("SafetyCoordinator singleton initialized")
    return _coordinator


__all__ = [
    "SafetyCoordinator",
    "get_safety_coordinator",
]
