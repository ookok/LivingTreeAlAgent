"""System Health Monitor — unified observability + autonomous self-optimization.

Integrates monitoring signals from ALL modules into a single health dashboard,
and runs background daemons for continuous self-optimization.

Cross-module signals monitored:
  SynapticPlasticity   → degradation_alert, silent_ratio, interference_ratio
  PredictabilityEngine → predictability_score per subsystem
  EmergenceDetector    → genuine vs spurious emergence
  GodelianSelf         → consciousness_gap, fixed_point detection
  EconomicOrchestrator → daily_spent, cumulative_roi
  FreeModelPool        → available/healthy/degraded ratios
  ThompsonRouter       → exploration/exploitation balance
  InquiryEngine        → high_yield_question effectiveness

Background daemons (run continuously):
  1. Homeostatic daemon      → periodic synaptic scaling
  2. Pruning daemon           → remove synapses below threshold
  3. Calibration daemon       → auto-tune two-tiered reward alpha
  4. Decay daemon             → decay unused provider beliefs
  5. Interference daemon      → detect + fix representation interference
  6. Consolidation daemon     → promote eligible active→mature synapses
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger


# ═══ Data Types ═══


class HealthLevel(str, Enum):
    OPTIMAL = "optimal"       # Everything working perfectly
    HEALTHY = "healthy"       # Normal operation
    DEGRADING = "degrading"   # Some subsystems need attention
    CRITICAL = "critical"     # Immediate intervention needed


@dataclass
class SubsystemHealth:
    """Health report for one subsystem."""
    name: str
    status: HealthLevel
    score: float                # 0-1, higher is better
    key_metrics: dict[str, Any]
    alerts: list[str]
    recommendations: list[str]


@dataclass
class SystemHealthReport:
    """Complete system health report across all subsystems."""
    timestamp: float
    overall_status: HealthLevel
    overall_score: float
    subsystems: list[SubsystemHealth]
    daemon_status: dict[str, bool]  # daemon_name → is_running
    action_items: list[str]         # Priority-ordered fixes needed
    summary: str = ""


# ═══ System Health Engine ═══


class SystemHealth:
    """Unified health monitoring + background daemon manager.

    Collects signals from all modules into a single dashboard,
    and manages background daemons for continuous self-optimization.
    """

    def __init__(self):
        self._history: deque[SystemHealthReport] = deque(maxlen=50)
        self._daemons: dict[str, asyncio.Task] = {}
        self._daemon_intervals: dict[str, float] = {}
        self._running = False
        self._cycle_count = 0
        self._last_actions: list[str] = []

    # ═══ Health Check ═══

    def check(self, module_refs: dict[str, Any] | None = None) -> SystemHealthReport:
        """Run a full system health check across all subsystems.

        Args:
            module_refs: Optional dict of module_name → module_instance.
                        If None, tries to import from singletons.

        Returns:
            SystemHealthReport with status, scores, and action items
        """
        refs = module_refs or self._gather_modules()
        now = time.time()

        subsystems: list[SubsystemHealth] = []

        # 1. Synaptic Plasticity
        subsystems.append(self._check_synaptic(refs.get("plasticity")))

        # 2. Predictability
        subsystems.append(self._check_predictability(refs.get("predictability")))

        # 3. Emergence Detection
        subsystems.append(self._check_emergence(refs.get("emergence")))

        # 4. Consciousness (Gödelian)
        subsystems.append(self._check_consciousness(refs.get("consciousness"),
                                                     refs.get("godelian")))

        # 5. Economic
        subsystems.append(self._check_economic(refs.get("economic")))

        # 6. Model Pool
        subsystems.append(self._check_pool(refs.get("pool")))

        # 7. Thompson Router
        subsystems.append(self._check_router(refs.get("router")))

        # 8. Pipeline Orchestrator
        subsystems.append(self._check_pipeline(refs.get("pipeline_orch")))

        # Composite score
        scores = [s.score for s in subsystems]
        overall = sum(scores) / max(len(scores), 1)

        if overall >= 0.85:
            status = HealthLevel.OPTIMAL
        elif overall >= 0.65:
            status = HealthLevel.HEALTHY
        elif overall >= 0.40:
            status = HealthLevel.DEGRADING
        else:
            status = HealthLevel.CRITICAL

        # Action items
        actions = []
        for s in subsystems:
            for rec in s.recommendations:
                if rec not in actions:
                    actions.append(rec)
        # Sort: critical subsystems first
        critical_actions = [a for a in actions if any(
            w in a.lower() for w in ["critical", "immediate", "degradation", "interference"])]
        other_actions = [a for a in actions if a not in critical_actions]
        action_items = critical_actions + other_actions

        daemon_status = {name: not t.done() for name, t in self._daemons.items()}

        report = SystemHealthReport(
            timestamp=now,
            overall_status=status,
            overall_score=round(overall, 3),
            subsystems=subsystems,
            daemon_status=daemon_status,
            action_items=action_items[:5],
            summary=self._build_summary(status, overall, subsystems, action_items),
        )
        self._history.append(report)
        self._cycle_count += 1
        self._last_actions = action_items

        # Auto-apply fixes for critical issues
        if status == HealthLevel.CRITICAL:
            self._auto_fix(report, refs)

        return report

    # ═══ Subsystem Checks ═══

    def _check_synaptic(self, sp) -> SubsystemHealth:
        if not sp:
            return SubsystemHealth(name="synaptic", status=HealthLevel.HEALTHY,
                                    score=0.7, key_metrics={}, alerts=[],
                                    recommendations=["Synaptic plasticity module not connected"])

        alert = sp.degradation_alert()
        ir = sp.interference_ratio()
        sr = sp.silent_ratio()
        mr = sp.maturity_ratio()
        stats = sp.stats()

        score = 1.0
        alerts = []
        recs = []

        if alert["severity"] == "critical":
            score -= 0.4
            alerts.append("CRITICAL: High synaptic interference detected")
            recs.append("Apply self-distillation regularization immediately")
        elif alert["severity"] == "warning":
            score -= 0.2
            alerts.append("WARNING: Elevated synaptic degradation")

        if sr < 0.15:
            score -= 0.15
            recs.append("Silent synapse reserve below 15% — reduce pruning rate")
        if sr > 0.45:
            score -= 0.1
            alerts.append("Silent ratio above 45% — too many unused connections")
            recs.append("Increase activation rate to utilize silent pool")

        if ir > 0.15:
            score -= 0.1
            recs.append("Increase mature protection level for degraded synapses")

        score = max(0.0, score)

        return SubsystemHealth(
            name="synaptic_plasticity",
            status=self._level_from_score(score),
            score=round(score, 3),
            key_metrics={"silent_ratio": sr, "mature_ratio": mr,
                         "interference": ir, "synapses": stats.get("total_synapses", 0)},
            alerts=alerts, recommendations=recs,
        )

    def _check_predictability(self, pe) -> SubsystemHealth:
        if not pe:
            return SubsystemHealth(name="predictability", status=HealthLevel.HEALTHY,
                                    score=0.7, key_metrics={}, alerts=[],
                                    recommendations=[])
        stats = pe.stats()
        avg_pred = stats.get("avg_predictability", 0.5)
        score = min(1.0, avg_pred + 0.2)
        recs = []
        if avg_pred < 0.4:
            recs.append("System predictability low — increase monitoring frequency")
        return SubsystemHealth(
            name="predictability", status=self._level_from_score(score),
            score=round(score, 3), key_metrics=stats, alerts=[], recommendations=recs)

    def _check_emergence(self, ed) -> SubsystemHealth:
        if not ed:
            return SubsystemHealth(name="emergence", status=HealthLevel.HEALTHY,
                                    score=0.7, key_metrics={}, alerts=[], recommendations=[])
        stats = ed.stats()
        latest = ed.latest_report()
        score = 0.7
        alerts = []
        recs = []
        if latest:
            if latest.spurious_count > latest.genuine_count:
                score -= 0.2
                alerts.append(f"More spurious ({latest.spurious_count}) than genuine "
                              f"({latest.genuine_count}) emergence signals")
        return SubsystemHealth(
            name="emergence", status=self._level_from_score(score),
            score=round(score, 3), key_metrics=stats, alerts=alerts, recommendations=recs)

    def _check_consciousness(self, pc, gs) -> SubsystemHealth:
        if not pc:
            return SubsystemHealth(name="consciousness", status=HealthLevel.HEALTHY,
                                    score=0.7, key_metrics={}, alerts=[], recommendations=[])
        stats = pc.stats()
        score = 0.7
        alerts = []
        recs = []
        if gs:
            gap = gs.compute_consciousness_gap()
            if gs.is_fixed_point:
                score -= 0.3
                alerts.append("Self-model reached fixed point — not evolving")
                recs.append("Inject novel experiences to restart self-evolution")
            if gap < 0.1:
                score -= 0.1
                alerts.append("Consciousness gap near zero — self-model may be over-complete")
        return SubsystemHealth(
            name="consciousness", status=self._level_from_score(score),
            score=round(score, 3), key_metrics=stats, alerts=alerts, recommendations=recs)

    def _check_economic(self, eco) -> SubsystemHealth:
        if not eco:
            return SubsystemHealth(name="economic", status=HealthLevel.HEALTHY,
                                    score=0.7, key_metrics={}, alerts=[], recommendations=[])
        stats = eco.stats()
        daily = stats.get("daily_spent_yuan", 0)
        roi = stats.get("cumulative_roi", 1)
        score = 0.7
        alerts = []
        recs = []
        if roi < 1.0:
            score -= 0.2
            alerts.append(f"Cumulative ROI below 1.0: {roi:.2f}")
            recs.append("Switch to ECONOMY policy temporarily")
        if daily > 30:
            score -= 0.1
            alerts.append(f"Daily spend high: ¥{daily:.1f}")
        return SubsystemHealth(
            name="economic", status=self._level_from_score(score),
            score=round(score, 3), key_metrics=stats, alerts=alerts, recommendations=recs)

    def _check_pool(self, pool) -> SubsystemHealth:
        if not pool:
            return SubsystemHealth(name="model_pool", status=HealthLevel.HEALTHY,
                                    score=0.7, key_metrics={}, alerts=[], recommendations=[])
        stats = pool.pool_stats()
        available = stats.get("available", 0)
        total = stats.get("total_models", 1)
        ratio = available / max(total, 1)
        score = min(1.0, ratio + 0.1)
        alerts = []
        recs = []
        if ratio < 0.3:
            alerts.append(f"Only {available}/{total} models available")
            recs.append("Reduce quarantine cooldown for degraded models")
        return SubsystemHealth(
            name="model_pool", status=self._level_from_score(score),
            score=round(score, 3), key_metrics=stats, alerts=alerts, recommendations=recs)

    def _check_router(self, router) -> SubsystemHealth:
        if not router:
            return SubsystemHealth(name="thompson_router", status=HealthLevel.HEALTHY,
                                    score=0.7, key_metrics={}, alerts=[], recommendations=[])
        stats = router.all_stats()
        score = 0.7
        recs = []
        if stats:
            uncertain = [s for s in stats if s.get("quality_uncertainty", 0) > 0.3]
            if len(uncertain) > len(stats) * 0.5:
                recs.append("Many providers have high uncertainty — run more exploration")
        return SubsystemHealth(
            name="thompson_router", status=self._level_from_score(score),
            score=round(score, 3),
            key_metrics={"providers_tracked": len(stats)}, alerts=[], recommendations=recs)

    def _check_pipeline(self, orch) -> SubsystemHealth:
        if not orch:
            return SubsystemHealth(name="pipeline", status=HealthLevel.HEALTHY,
                                    score=0.7, key_metrics={}, alerts=[], recommendations=[])
        stats = orch.stats()
        success = stats.get("success_rate", 0.7)
        score = min(1.0, success + 0.1)
        recs = []
        if success < 0.5:
            recs.append("Pipeline success rate low — review mode selection logic")
        return SubsystemHealth(
            name="pipeline_orchestrator", status=self._level_from_score(score),
            score=round(score, 3), key_metrics=stats, alerts=[], recommendations=recs)

    # ═══ Background Daemons ═══

    async def start_daemons(self, module_refs: dict[str, Any]) -> None:
        """Start all background optimization daemons."""
        if self._running:
            return
        self._running = True

        intervals = {
            "homeostatic": 300,      # Every 5 minutes
            "pruning": 600,          # Every 10 minutes
            "calibration": 900,      # Every 15 minutes
            "decay": 1200,           # Every 20 minutes
            "interference": 180,    # Every 3 minutes (frequent, cheap)
            "consolidation": 300,   # Every 5 minutes
        }
        self._daemon_intervals = intervals

        daemons = {
            "homeostatic": self._homeostatic_loop,
            "pruning": self._pruning_loop,
            "calibration": self._calibration_loop,
            "decay": self._decay_loop,
            "interference": self._interference_loop,
            "consolidation": self._consolidation_loop,
        }

        for name, loop_fn in daemons.items():
            self._daemons[name] = asyncio.create_task(
                loop_fn(intervals[name], refs))
        logger.info(f"SystemHealth: {len(daemons)} background daemons started")

    async def stop_daemons(self) -> None:
        """Stop all background daemons."""
        self._running = False
        for name, task in self._daemons.items():
            task.cancel()
        await asyncio.gather(*self._daemons.values(), return_exceptions=True)
        self._daemons.clear()
        logger.info("SystemHealth: all daemons stopped")

    async def _homeostatic_loop(self, interval: float, refs: dict) -> None:
        sp = refs.get("plasticity")
        while self._running:
            await asyncio.sleep(interval)
            if sp:
                sp.homeostatic_scale()
                logger.debug("Daemon: homeostatic scaling applied")

    async def _pruning_loop(self, interval: float, refs: dict) -> None:
        sp = refs.get("plasticity")
        while self._running:
            await asyncio.sleep(interval)
            if sp:
                pruned = sp.decay_all()
                if pruned:
                    logger.debug(f"Daemon: pruned {pruned} synapses")

    async def _calibration_loop(self, interval: float, refs: dict) -> None:
        ie = refs.get("inquiry_engine")
        while self._running:
            await asyncio.sleep(interval)
            if ie and hasattr(ie, '_reward'):
                ie._reward.calibrate(target_task_ratio=0.5)
                logger.debug(f"Daemon: reward α={ie._reward._alpha:.3f}")

    async def _decay_loop(self, interval: float, refs: dict) -> None:
        router = refs.get("router")
        while self._running:
            await asyncio.sleep(interval)
            if router and hasattr(router, '_decay_all'):
                router._decay_all()
                logger.debug("Daemon: ThompsonRouter decay applied")

    async def _interference_loop(self, interval: float, refs: dict) -> None:
        sp = refs.get("plasticity")
        while self._running:
            await asyncio.sleep(interval)
            if sp:
                alert = sp.degradation_alert()
                if alert["severity"] in ("warning", "critical"):
                    sp.regularize_distribution(strength=0.05)
                    logger.info(f"Daemon: self-distillation applied ({alert['severity']})")

    async def _consolidation_loop(self, interval: float, refs: dict) -> None:
        sp = refs.get("plasticity")
        while self._running:
            await asyncio.sleep(interval)
            if sp:
                promoted = sp.mature_all_eligible()
                if promoted:
                    logger.debug(f"Daemon: {promoted} synapses matured")

    # ═══ Auto-Fix ═══

    def _auto_fix(self, report: SystemHealthReport, refs: dict) -> None:
        """Automatically apply fixes for critical conditions."""
        for sub in report.subsystems:
            if sub.name == "synaptic_plasticity" and sub.status == HealthLevel.CRITICAL:
                sp = refs.get("plasticity")
                if sp:
                    sp.regularize_distribution(strength=0.15)
                    logger.warning("AUTO-FIX: emergency self-distillation applied")
            if sub.name == "model_pool" and sub.score < 0.3:
                pool = refs.get("pool")
                if pool:
                    for m in pool._models.values():
                        if m.status.value in ("quarantined",):
                            if time.time() - m.last_used > 60:
                                m.status = type(m.status).UNKNOWN
                                m.failure_streak = 0
                    logger.warning("AUTO-FIX: quarantined models released")

    # ═══ Helpers ═══

    @staticmethod
    def _gather_modules() -> dict[str, Any]:
        """Try to gather all module singletons."""
        refs = {}
        for mod_name, attr, key in [
            ("..core.synaptic_plasticity", "get_plasticity", "plasticity"),
            ("..dna.predictability_engine", "get_predictability", "predictability"),
            ("..dna.emergence_detector", "get_emergence_detector", "emergence"),
            ("..dna.phenomenal_consciousness", "get_consciousness", "consciousness"),
            ("..dna.godelian_self", "get_godelian_self", "godelian"),
            ("..economy.economic_engine", "get_economic_orchestrator", "economic"),
            ("..treellm.free_pool_manager", "get_free_pool", "pool"),
            ("..treellm.bandit_router", "get_bandit_router", "router"),
            ("..dna.inquiry_engine", "get_inquiry_engine", "inquiry_engine"),
            ("..execution.unified_pipeline", "get_pipeline_orchestrator", "pipeline_orch"),
        ]:
            try:
                mod = __import__(mod_name, fromlist=[attr])
                refs[key] = getattr(mod, attr)()
            except Exception:
                pass
        return refs

    @staticmethod
    def _level_from_score(score: float) -> HealthLevel:
        if score >= 0.85:
            return HealthLevel.OPTIMAL
        if score >= 0.65:
            return HealthLevel.HEALTHY
        if score >= 0.40:
            return HealthLevel.DEGRADING
        return HealthLevel.CRITICAL

    @staticmethod
    def _build_summary(status: HealthLevel, score: float,
                       subsystems: list[SubsystemHealth],
                       actions: list[str]) -> str:
        parts = [f"System: {status.value.upper()} ({score:.0%})"]
        by_status = {}
        for s in subsystems:
            by_status[s.status.value] = by_status.get(s.status.value, 0) + 1
        parts.append(f"Subsystems: " + ", ".join(
            f"{k}={v}" for k, v in sorted(by_status.items())))
        if actions:
            parts.append(f"Actions: {actions[0][:80]}")
        return " | ".join(parts)

    def stats(self) -> dict[str, Any]:
        goodput = {}
        try:
            from .decoupled_executor import get_decoupled_executor
            goodput = get_decoupled_executor().stats()
        except Exception:
            pass

        return {
            "cycles": self._cycle_count,
            "daemons_running": sum(1 for t in self._daemons.values() if not t.done()),
            "last_status": self._history[-1].overall_status.value if self._history else "unknown",
            "last_score": self._history[-1].overall_score if self._history else 0,
            "daemon_intervals": self._daemon_intervals,
            "goodput": {
                "pending_tasks": goodput.get("pending", 0),
                "completed": goodput.get("completed", 0),
                "failed": goodput.get("failed", 0),
                "goodput_ratio": goodput.get("goodput_ratio", 1.0),
                "diagnosis": "DiLoCo: effective_work / wall_time" if goodput else "not initialized",
                "isolation_saves": goodput.get("isolation_saves", 0),
            },
        }


# ═══ Singleton ═══

_health: SystemHealth | None = None


def get_system_health() -> SystemHealth:
    global _health
    if _health is None:
        _health = SystemHealth()
    return _health


async def start_autopilot(module_refs: dict[str, Any] | None = None) -> SystemHealth:
    """One-liner: start all background daemons and return the health monitor."""
    health = get_system_health()
    refs = module_refs or SystemHealth._gather_modules()
    await health.start_daemons(refs)
    logger.info("SystemHealth autopilot engaged — 6 background daemons running")
    return health


# ═══ TrustScorer — Per-agent reliability posture scoring ═══

TRUST_DIR = Path(".livingtree/trust")
TRUST_DB = TRUST_DIR / "trust_scores.json"


@dataclass
class TrustProfile:
    agent: str
    score: float = 100.0
    successes: int = 0
    failures: int = 0
    rate_limits: int = 0
    total_calls: int = 0
    last_success: float = 0.0
    last_failure: float = 0.0
    drift_score: float = 1.0
    component_score: float = 1.0
    active_profile: str = "standard"


class TrustScorer:
    """Multi-factor agent trust scoring."""

    WEIGHTS = {
        "success_rate": 0.40,
        "recency": 0.20,
        "drift": 0.15,
        "rate_limit": 0.10,
        "component": 0.15,
    }

    PROFILE_THRESHOLDS = {
        "minimal": 30,
        "standard": 60,
        "strict": 85,
    }

    def __init__(self):
        TRUST_DIR.mkdir(parents=True, exist_ok=True)
        self._profiles: dict[str, TrustProfile] = {}
        self._active_profile: str = "standard"
        self._load()

    def set_profile(self, profile: str):
        if profile in self.PROFILE_THRESHOLDS:
            self._active_profile = profile
            logger.info(f"Trust profile: {profile} (threshold: {self.PROFILE_THRESHOLDS[profile]})")

    def record(
        self,
        agent: str,
        success: bool,
        latency_ms: float = 0.0,
        rate_limited: bool = False,
    ):
        if agent not in self._profiles:
            self._profiles[agent] = TrustProfile(agent=agent)

        p = self._profiles[agent]
        p.total_calls += 1

        if success:
            p.successes += 1
            p.last_success = time.time()
        else:
            p.failures += 1
            p.last_failure = time.time()

        if rate_limited:
            p.rate_limits += 1

        try:
            from ..observability.agent_eval import get_eval
            cm = get_eval().component_report(agent)
            if cm:
                p.component_score = cm.success_rate
        except Exception:
            pass

        p.score = self._calculate(p)

        if p.total_calls % 20 == 0:
            self._save()

    def score(self, agent: str) -> float:
        profile = self._profiles.get(agent)
        if not profile:
            return 100.0
        return profile.score

    def can_auto_approve(self, agent: str) -> bool:
        threshold = self.PROFILE_THRESHOLDS.get(self._active_profile, 60)
        return self.score(agent) >= threshold

    def trust_level(self, agent: str) -> str:
        s = self.score(agent)
        if s >= 90:
            return "🟢 trusted"
        elif s >= 70:
            return "🟡 reliable"
        elif s >= 50:
            return "🟠 cautious"
        elif s >= 30:
            return "🔴 risky"
        return "⛔ untrusted"

    def all_profiles(self) -> dict[str, TrustProfile]:
        return dict(self._profiles)

    def summary(self) -> dict[str, Any]:
        profiles = self._profiles
        if not profiles:
            return {"agents": 0, "avg_score": 100, "lowest": None}

        scores = [p.score for p in profiles.values()]
        avg = sum(scores) / len(scores)
        lowest_agent = min(profiles.values(), key=lambda p: p.score)

        return {
            "agents": len(profiles),
            "avg_score": round(avg, 1),
            "lowest_agent": lowest_agent.agent,
            "lowest_score": round(lowest_agent.score, 1),
            "profile": self._active_profile,
            "threshold": self.PROFILE_THRESHOLDS[self._active_profile],
            "all": {
                name: {
                    "score": round(p.score, 1),
                    "level": self.trust_level(name),
                    "calls": p.total_calls,
                    "success_rate": round(p.successes / max(p.total_calls, 1) * 100, 1),
                    "rate_limits": p.rate_limits,
                }
                for name, p in profiles.items()
            },
        }

    def _calculate(self, p: TrustProfile) -> float:
        total = max(p.total_calls, 1)

        success_rate = p.successes / total * 100

        now = time.time()
        time_since_failure = now - p.last_failure if p.last_failure else 86400
        time_since_success = now - p.last_success if p.last_success else 86400
        recency_bonus = min(100, time_since_success / 3600 * 10)
        if p.last_failure > p.last_success:
            recency_bonus *= 0.3

        drift = p.drift_score * 100

        rl_rate = p.rate_limits / max(total, 1)
        rl_score = max(0, 100 - rl_rate * 200)

        comp_score = p.component_score * 100

        score = (
            self.WEIGHTS["success_rate"] * success_rate +
            self.WEIGHTS["recency"] * recency_bonus +
            self.WEIGHTS["drift"] * drift +
            self.WEIGHTS["rate_limit"] * rl_score +
            self.WEIGHTS["component"] * comp_score
        )

        return max(0.0, min(100.0, score))

    def _save(self):
        data = {}
        for name, p in self._profiles.items():
            data[name] = {
                "agent": p.agent, "score": p.score,
                "successes": p.successes, "failures": p.failures,
                "rate_limits": p.rate_limits, "total_calls": p.total_calls,
                "last_success": p.last_success, "last_failure": p.last_failure,
                "drift_score": p.drift_score, "component_score": p.component_score,
            }
        TRUST_DB.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        if not TRUST_DB.exists():
            return
        try:
            data = json.loads(TRUST_DB.read_text(encoding="utf-8"))
            for name, d in data.items():
                self._profiles[name] = TrustProfile(**{
                    k: d.get(k, 0) for k in TrustProfile.__dataclass_fields__
                })
        except Exception:
            pass


_ts_lock = __import__('threading').Lock()
_ts: TrustScorer | None = None


def get_trust_scorer() -> TrustScorer:
    global _ts
    if _ts is None:
        with _ts_lock:
            if _ts is None:
                _ts = TrustScorer()
    return _ts


__all__ = [
    "SystemHealth", "SystemHealthReport", "SubsystemHealth", "HealthLevel",
    "get_system_health", "start_autopilot",
    "TrustScorer", "TrustProfile", "get_trust_scorer",
]
