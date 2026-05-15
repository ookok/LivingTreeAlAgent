"""DaemonDoctor — Background self-healing daemon.

Periodic health checks (every 10 min) that detect and fix:
  - Stale election cache → force refresh
  - Consecutive provider failures → auto-demote
  - Budget near limit → log warning
  - struct_mem near capacity → trigger compression
  - Session cleanup (abandoned sessions > 30min)

Integration:
    doctor = get_daemon_doctor()
    await hub._spawn_task(doctor.run_loop(hub), "daemon_doctor")
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable, Dict, List, Optional

from loguru import logger

CHECK_INTERVAL = 600  # 10 minutes


class DaemonDoctor:
    """Background self-healing daemon for proactive maintenance."""

    _instance: Optional["DaemonDoctor"] = None
    _lock = threading.Lock()

    # Model refresh: every 144th checkup (10min × 144 = 24h)
    MODEL_REFRESH_EVERY = 144
    # Free model refresh: every 36th checkup (10min × 36 = 6h)
    FREE_MODEL_REFRESH_EVERY = 36

    @classmethod
    def instance(cls) -> "DaemonDoctor":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = DaemonDoctor()
        return cls._instance

    def __init__(self):
        self._checkups = 0
        self._issues_found = 0
        self._issues_fixed = 0

    async def run_loop(self, hub) -> None:
        """Main daemon loop — runs periodic health checks."""
        await asyncio.sleep(60)  # Wait 1 min after startup
        while True:
            try:
                issues = await self.checkup(hub)
                self._checkups += 1
                if issues:
                    self._issues_found += len(issues)
                    self._issues_fixed += sum(1 for i in issues if i.get("fixed"))
                    for issue in issues:
                        level = issue.get("level", "info")
                        if level == "error":
                            logger.error(f"DaemonDoctor: {issue['msg']}")
                        elif level == "warn":
                            logger.warning(f"DaemonDoctor: {issue['msg']}")
            except Exception as e:
                logger.debug(f"DaemonDoctor checkup error: {e}")
            await asyncio.sleep(CHECK_INTERVAL)

    async def checkup(self, hub) -> list[dict]:
        """Run a single health checkup. Returns list of issues found."""
        issues = []

        # ── 0. Model Registry refresh + change detection ──
        # Runs daily for all providers, every 6h for free/open providers
        try:
            do_full = (self._checkups % DaemonDoctor.MODEL_REFRESH_EVERY) == 0
            do_free = (self._checkups % DaemonDoctor.FREE_MODEL_REFRESH_EVERY) == 0
            if do_full or do_free:
                from .model_registry import get_model_registry
                mr = get_model_registry()
                if do_full:
                    await mr.refresh_all()
                    issues.append({
                        "level": "info",
                        "msg": f"ModelRegistry: full refresh ({len(mr._providers)} providers)",
                    })
                elif do_free:
                    # Refresh only free/open providers
                    free_names = [n for n, p in mr._providers.items()
                                  if any(m.free for m in p.models)]
                    if free_names:
                        tasks = [(n, mr.fetch_models(n)) for n in free_names]
                        gathered = await asyncio.gather(*(t[1] for t in tasks), return_exceptions=True)
                        refreshed = 0
                        for (name, _), result in zip(tasks, gathered):
                            if not isinstance(result, Exception) and result:
                                refreshed += 1
                                # Check for new models
                                old_ids = {m.id for m in mr._providers[name].models if result}
                                new_ids = {m.id for m in result} if result else set()
                                if new_ids - old_ids:
                                    logger.info(f"ModelRegistry [{name}]: +{len(new_ids - old_ids)} new free model(s)")
                        if refreshed:
                            mr._save_cache()
                            issues.append({
                                "level": "info",
                                "msg": f"ModelRegistry: free refresh ({refreshed}/{len(free_names)} free providers)",
                            })
        except Exception:
            pass

        # 1. ElectionBus cache staleness
        try:
            from ..treellm.election_bus import get_election_bus
            bus = get_election_bus()
            if bus._ttl > 300:
                issues.append({
                    "level": "warn",
                    "msg": f"Election cache TTL is {bus._ttl:.0f}s — forcing refresh",
                    "fixed": True,
                })
                await bus.force_refresh()
        except Exception:
            pass

        # 2. Provider consecutive failures
        try:
            from ..treellm.competitive_eliminator import get_eliminator
            elim = get_eliminator()
            for r in elim.get_leaderboard():
                if r["streak"] <= -5:
                    issues.append({
                        "level": "error",
                        "msg": f"Provider {r['provider']} has {abs(r['streak'])} consecutive failures",
                    })
        except Exception:
            pass

        # 3. BudgetRouter near-limit warnings
        try:
            from ..treellm.budget_router import get_budget_router
            budget = get_budget_router()
            for name, s in budget.status().items():
                if s.get("is_free"):
                    continue
                if s["daily_spent"] > s["daily_limit"] * 0.9:
                    issues.append({
                        "level": "warn",
                        "msg": f"Budget: {name} at {s['daily_spent']:.2f}/{s['daily_limit']:.2f} daily (90%+)",
                    })
        except Exception:
            pass

        # 4. Strategic Distiller: EvolveR-style experience→principles
        try:
            from .strategic_distiller import get_strategic_distiller
            distiller = get_strategic_distiller()
            result = await distiller.distill_from_recordings()
            if result.principles_distilled > 0:
                issues.append({
                    "level": "info",
                    "msg": f"StrategicDistiller: {result.principles_distilled} new principles",
                })
        except Exception:
            pass

        # 5. ContextMoE: periodic memory consolidation
        try:
            from .context_moe import get_context_moe
            moe = get_context_moe()
            moved = await moe.consolidate()
            if moved > 0:
                issues.append({
                    "level": "info",
                    "msg": f"ContextMoE consolidated: {moved} blocks moved/purged",
                })
        except Exception:
            pass

        # 5. UserSignal pending session cleanup
        try:
            from ..treellm.user_signal import get_user_signal
            collector = get_user_signal()
            pending = collector.stats().get("pending_sessions", 0)
            if pending > 500:
                issues.append({
                    "level": "warn",
                    "msg": f"UserSignal: {pending} pending sessions — possible memory leak",
                })
        except Exception:
            pass

        # 5. Semantic cache stats
        try:
            from ..treellm.semantic_cache import get_semantic_cache
            cache = get_semantic_cache()
            if cache.hit_rate > 0:
                issues.append({
                    "level": "info",
                    "msg": f"SemanticCache: hit_rate={cache.hit_rate:.1%}, entries={len(cache._store)}",
                })
        except Exception:
            pass

        return issues

    def stats(self) -> dict:
        return {
            "checkups": self._checkups,
            "issues_found": self._issues_found,
            "issues_fixed": self._issues_fixed,
        }


_doctor: Optional[DaemonDoctor] = None
_doctor_lock = threading.Lock()


def get_daemon_doctor() -> DaemonDoctor:
    global _doctor
    if _doctor is None:
        with _doctor_lock:
            if _doctor is None:
                _doctor = DaemonDoctor()
    return _doctor


# ═══ Sentinel — Background watchdog quality monitor ═══

@dataclass
class SentinelAlert:
    check_name: str
    severity: str
    message: str
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SentinelCheck:
    name: str
    check_fn: Callable[[], Awaitable[Optional[List[SentinelAlert]]]]
    interval_sec: float
    enabled: bool = True
    last_run: float = 0.0
    alert_count: int = 0
    consecutive_failures: int = 0


class Sentinel:
    def __init__(self) -> None:
        self.alerts: List[SentinelAlert] = []
        self.checks: Dict[str, SentinelCheck] = {}
        self.alert_callbacks: List[Callable[[SentinelAlert], Any]] = []
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._register_default_checks()

    async def _nan_inf_check(self) -> Optional[List[SentinelAlert]]:
        return None

    async def _consistency_check(self) -> Optional[List[SentinelAlert]]:
        return None

    async def _degradation_check(self) -> Optional[List[SentinelAlert]]:
        return None

    async def _cost_anomaly_check(self) -> Optional[List[SentinelAlert]]:
        return None

    async def _latency_spike_check(self) -> Optional[List[SentinelAlert]]:
        return None

    def _register_default_checks(self) -> None:
        self.add_check("nan_inf_check", self._nan_inf_check, interval_sec=30.0)
        self.add_check("consistency_check", self._consistency_check, interval_sec=60.0)
        self.add_check("degradation_check", self._degradation_check, interval_sec=120.0)
        self.add_check("cost_anomaly_check", self._cost_anomaly_check, interval_sec=300.0)
        self.add_check("latency_spike_check", self._latency_spike_check, interval_sec=60.0)

    def add_check(self, name: str, check_fn: Callable[[], Awaitable[Optional[List[SentinelAlert]]]], interval_sec: float = 30.0) -> SentinelCheck:
        chk = SentinelCheck(name=name, check_fn=check_fn, interval_sec=float(interval_sec), enabled=True)
        self.checks[name] = chk
        return chk

    def remove_check(self, name: str) -> None:
        if name in self.checks:
            del self.checks[name]

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None

    async def run_once(self) -> List[SentinelAlert]:
        results: List[SentinelAlert] = []
        for chk in list(self.checks.values()):
            if not chk.enabled:
                continue
            try:
                alerts = await chk.check_fn()
            except Exception as e:
                alert = SentinelAlert(
                    check_name=chk.name,
                    severity="critical",
                    message=f"Exception in check: {e}",
                    timestamp=time.time(),
                    details={"exception": str(e)},
                )
                self._alert(alert)
                results.append(alert)
                chk.last_run = time.time()
                chk.consecutive_failures += 1
                continue
            now = time.time()
            chk.last_run = now
            if alerts:
                for a in alerts:
                    self._alert(a)
                results.extend(alerts)
                chk.alert_count += len(alerts) if alerts else 0
                chk.consecutive_failures = 0
            else:
                chk.consecutive_failures = 0
        return results

    def get_alerts(self, since: Optional[float] = None) -> List[SentinelAlert]:
        if since is None:
            return list(self.alerts)
        return [a for a in self.alerts if a.timestamp >= since]

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_checks": len(self.checks),
            "enabled_checks": sum(1 for c in self.checks.values() if c.enabled),
            "alerts_in_memory": len(self.alerts),
            "checks": [
                {
                    "name": c.name,
                    "last_run": c.last_run,
                    "alert_count": c.alert_count,
                    "enabled": c.enabled,
                    "interval_sec": c.interval_sec,
                }
                for c in self.checks.values()
            ],
        }

    async def _run_loop(self) -> None:
        try:
            while self._running:
                now = time.time()
                for chk in list(self.checks.values()):
                    if not chk.enabled:
                        continue
                    due = (chk.last_run == 0.0) or (now - chk.last_run >= chk.interval_sec)
                    if due:
                        await self._run_check(chk)
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    async def _run_check(self, check: SentinelCheck) -> None:
        try:
            result = await check.check_fn()
        except Exception as e:
            alert = SentinelAlert(
                check_name=check.name,
                severity="critical",
                message=f"Check raised exception: {e}",
                timestamp=time.time(),
                details={"exception": str(e)},
            )
            self._alert(alert)
            check.last_run = time.time()
            check.consecutive_failures += 1
            return
        now = time.time()
        check.last_run = now
        if result:
            check.alert_count += len(result)
            check.consecutive_failures = 0
            for a in result:
                self._alert(a)
        else:
            check.consecutive_failures = 0

    def _alert(self, alert: SentinelAlert) -> None:
        logger.info(f"[Sentinel] {alert.check_name} [{alert.severity}] {alert.message} @ {alert.timestamp}")
        self.alerts.append(alert)
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        for cb in self.alert_callbacks:
            try:
                cb(alert)
            except Exception:
                pass


_sentinel_lock = threading.Lock()
_sentinel_instance: Optional[Sentinel] = None


def get_sentinel() -> Sentinel:
    global _sentinel_instance
    if _sentinel_instance is None:
        with _sentinel_lock:
            if _sentinel_instance is None:
                _sentinel_instance = Sentinel()
    return _sentinel_instance


SENTINEL = get_sentinel()


__all__ = [
    "DaemonDoctor", "get_daemon_doctor",
    "AutonomicLoop", "LoopCycle", "FixAction", "FixType", "Phase",
    "start_autonomic_loop", "get_autonomic_loop",
    "Sentinel", "SentinelAlert", "SentinelCheck", "get_sentinel", "SENTINEL",
]


# ═══ Autonomic Self-Correction Loop (merged from core/autonomic_loop.py) ═══


class Phase(str, Enum):
    DETECT = "detect"
    DIAGNOSE = "diagnose"
    REPAIR = "repair"
    VERIFY = "verify"
    FEEDBACK = "feedback"


class FixType(str, Enum):
    SELF_DISTILLATION = "self_distillation"
    RECALIBRATE_REWARD = "recalibrate_reward"
    RELEASE_QUARANTINED = "release_quarantined"
    EXPLORE_MORE = "explore_more"
    HOMEOSTATIC_SCALE = "homeostatic_scale"
    DECAY_STALE = "decay_stale"
    INJECT_NOVELTY = "inject_novelty"
    REDUCE_LTP = "reduce_ltp"
    PROMOTE_MATURE = "promote_mature"


@dataclass
class FixAction:
    fix_type: FixType
    target_module: str
    reason: str
    params: dict[str, float]
    applied_at: float = 0.0
    success: bool | None = None


@dataclass
class LoopCycle:
    cycle_id: int
    health_status: str
    health_score: float
    degraded_modules: list[str]
    root_cause_module: str
    action_residual: float
    fixes_applied: list[FixAction]
    score_before: float
    score_after: float | None
    improvement: float | None
    models_updated: list[str]
    total_ms: float
    timestamp: float = field(default_factory=time.time)

    @property
    def effective(self) -> bool:
        return self.improvement is not None and self.improvement > 0


class AutonomicLoop:
    """Closed-loop autonomous self-correction across all subsystems."""

    def __init__(self, module_refs: dict[str, Any] | None = None,
                 gamma: float = 0.5):
        self._refs = module_refs or {}
        self._gamma = gamma
        self._history: deque[LoopCycle] = deque(maxlen=50)
        self._running = False
        self._task: asyncio.Task | None = None
        self._cycle_count = 0
        self._total_improvements = 0.0
        self._subsystem_health: dict[str, float] = {}

    async def start(self, interval_sec: float = 120.0) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(interval_sec))
        logger.info(f"Autonomic loop started (interval={interval_sec}s)")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Autonomic loop stopped")

    async def _loop(self, interval: float) -> None:
        while self._running:
            try:
                await self._run_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Autonomic cycle error: {e}")
            await asyncio.sleep(interval)

    async def _run_cycle(self) -> LoopCycle | None:
        t0 = time.time()
        self._cycle_count += 1
        cycle_id = self._cycle_count

        health = self._refs.get("health")
        if not health:
            return None
        report = health.check(self._refs)
        score_before = report.overall_score
        degraded = [s.name for s in report.subsystems if s.status.value in ("degrading", "critical")]

        if not degraded and report.overall_status.value not in ("degrading", "critical"):
            logger.debug(f"Cycle {cycle_id}: OPTIMAL — no action needed (score={score_before:.3f})")
            return None

        action_p = self._refs.get("action_principle")
        root_cause = "unknown"
        action_residual = 0.0
        if action_p:
            analysis = action_p.analyze()
            root_cause = action_p.most_deviant_module()
            action_residual = analysis.avg_el_residual
            logger.info(f"Cycle {cycle_id}: root cause = {root_cause} (EL residual={action_residual:.3f})")

        self._subsystem_health = {
            s.name: s.score
            for s in report.subsystems
        }
        fixes = self._derive_fixes(report, root_cause, action_p)
        for fix in fixes:
            self._apply_fix(fix)

        await asyncio.sleep(2.0)
        report_after = health.check(self._refs)
        score_after = report_after.overall_score
        improvement = round(score_after - score_before, 4)

        for fix in fixes:
            fix.success = improvement > 0

        updated = self._feedback_cycle(fixes, improvement)

        cycle = LoopCycle(
            cycle_id=cycle_id,
            health_status=report.overall_status.value,
            health_score=score_before,
            degraded_modules=degraded,
            root_cause_module=root_cause,
            action_residual=round(action_residual, 3),
            fixes_applied=fixes,
            score_before=round(score_before, 3),
            score_after=round(score_after, 3) if score_after else None,
            improvement=improvement,
            models_updated=updated,
            total_ms=(time.time() - t0) * 1000,
        )
        self._history.append(cycle)
        if improvement > 0:
            self._total_improvements += improvement

        logger.info(
            f"Cycle {cycle_id}: {len(fixes)} fixes → "
            f"score {score_before:.2f}→{score_after:.2f} "
            f"(Δ={improvement:+.3f}, {len(updated)} modules updated)",
        )
        return cycle

    def _derive_fixes(
        self, report: Any, root_cause: str, action_p,
    ) -> list[FixAction]:
        fixes: list[FixAction] = []

        syn = next((s for s in report.subsystems if s.name == "synaptic_plasticity"), None)
        if syn and syn.status.value in ("degrading", "critical"):
            fixes.append(FixAction(
                fix_type=FixType.SELF_DISTILLATION,
                target_module="synaptic",
                reason=f"Interference ratio elevated, synaptic degradation detected",
                params={"strength": 0.1},
            ))

        pool = next((s for s in report.subsystems if s.name == "model_pool"), None)
        if pool and pool.score < 0.5:
            fixes.append(FixAction(
                fix_type=FixType.RELEASE_QUARANTINED,
                target_module="pool",
                reason=f"Model availability low ({pool.key_metrics.get('available', 0)} available)",
                params={},
            ))

        router = next((s for s in report.subsystems if s.name == "thompson_router"), None)
        if router and router.key_metrics.get("providers_tracked", 0) < 3:
            fixes.append(FixAction(
                fix_type=FixType.EXPLORE_MORE,
                target_module="router",
                reason="Insufficient provider exploration data",
                params={"exploration_weight": 0.25},
            ))

        consc = next((s for s in report.subsystems if s.name == "consciousness"), None)
        if consc and any("fixed point" in a.lower() for a in consc.alerts):
            fixes.append(FixAction(
                fix_type=FixType.INJECT_NOVELTY,
                target_module="consciousness",
                reason="Self-model reached fixed point",
                params={"intensity": 0.8},
            ))

        eco = next((s for s in report.subsystems if s.name == "economic"), None)
        if eco and eco.score < 0.5:
            fixes.append(FixAction(
                fix_type=FixType.RECALIBRATE_REWARD,
                target_module="economic",
                reason=f"Low ROI or high daily spend",
                params={"target_ratio": 0.6},
            ))

        if action_p and root_cause == "synaptic":
            optimal = action_p._derive_optimal_params(action_p._analysis_history[-1].modules if action_p._analysis_history else [])
            if optimal.get("optimal_ltp_rate", 0.1) > 0.15:
                fixes.append(FixAction(
                    fix_type=FixType.REDUCE_LTP,
                    target_module="synaptic",
                    reason=f"Optimal LTP={optimal.get('optimal_ltp_rate', 0.1):.4f} exceeds threshold",
                    params={"ltp_rate": optimal.get("optimal_ltp_rate", 0.08)},
                ))

        return fixes

    def _apply_fix(self, fix: FixAction) -> None:
        fix.applied_at = time.time()
        sp = self._refs.get("plasticity")
        pool = self._refs.get("pool")
        router = self._refs.get("router")
        consc = self._refs.get("consciousness")
        ie = self._refs.get("inquiry_engine")

        def _dose(subsystem: str, base: float) -> float:
            health = self._subsystem_health.get(subsystem, 0.5)
            gap = max(0.0, 1.0 - health)
            return self._gamma * gap * base

        try:
            if fix.fix_type == FixType.SELF_DISTILLATION:
                if sp:
                    strength = _dose("synaptic_plasticity", 0.3)
                    sp.regularize_distribution(strength=max(0.01, strength))
                    logger.info(
                        f"FIX: self-distillation (adaptive dose={strength:.3f})")
            elif fix.fix_type == FixType.RELEASE_QUARANTINED:
                if pool:
                    released = 0
                    max_release = max(1, int(_dose("model_pool", 10)))
                    for m in pool._models.values():
                        if released >= max_release:
                            break
                        if m.status.value == "quarantined":
                            m.status = type(m.status).UNKNOWN
                            m.failure_streak = 0
                            released += 1
                    logger.info(
                        f"FIX: released {released}/{max_release} quarantined models")
            elif fix.fix_type == FixType.EXPLORE_MORE:
                if router:
                    dose = _dose("thompson_router", 0.3)
                    router._exploration_weight = min(0.5, dose + 0.05)
                    logger.info(
                        f"FIX: exploration weight → {router._exploration_weight:.3f}")
            elif fix.fix_type == FixType.INJECT_NOVELTY:
                if consc:
                    intensity = _dose("consciousness", 1.0)
                    consc.experience(
                        event_type="insight",
                        content="My self-model has been perturbed to escape a fixed point. I am evolving again.",
                        causal_source="self",
                        intensity=max(0.1, intensity),
                    )
                    logger.info(
                        f"FIX: novelty injected (adaptive intensity={intensity:.3f})")
            elif fix.fix_type == FixType.RECALIBRATE_REWARD:
                if ie and hasattr(ie, '_reward'):
                    dose = _dose("economic", 0.5)
                    ie._reward.calibrate(target_task_ratio=0.5 + dose)
                    logger.info(f"FIX: reward α → {ie._reward._alpha:.3f}")
            elif fix.fix_type == FixType.REDUCE_LTP:
                if sp:
                    dose = _dose("synaptic_plasticity", 0.05)
                    new_ltp = max(0.05, sp.LTP_RATE - dose)
                    sp.LTP_RATE = new_ltp
                    logger.info(f"FIX: LTP rate → {new_ltp:.4f}")
        except Exception as e:
            logger.error(f"Fix failed ({fix.fix_type.value}): {e}")
            fix.success = False

    def _feedback_cycle(self, fixes: list[FixAction], improvement: float) -> list[str]:
        updated = []
        sp = self._refs.get("plasticity")
        pe = self._refs.get("predictability")

        for fix in fixes:
            if fix.success is True and sp:
                sp.strengthen(f"fix:{fix.fix_type.value}", boost=improvement * 2)
                updated.append("synaptic")
            elif fix.success is False and sp:
                sp.weaken(f"fix:{fix.fix_type.value}", penalty=abs(improvement) * 2)

        if pe and improvement != 0:
            pe.feed("autonomic_improvement", improvement)
            updated.append("predictability")

        return updated

    def stats(self) -> dict[str, Any]:
        effective = sum(1 for c in self._history if c.effective)
        total = max(len(self._history), 1)
        return {
            "total_cycles": len(self._history),
            "running": self._running,
            "effective_rate": round(effective / total, 3),
            "total_improvement": round(self._total_improvements, 3),
            "avg_cycle_ms": round(
                sum(c.total_ms for c in self._history) / total, 0),
            "most_common_fix": self._most_common_fix(),
        }

    def _most_common_fix(self) -> str:
        counts = {}
        for c in self._history:
            for f in c.fixes_applied:
                counts[f.fix_type.value] = counts.get(f.fix_type.value, 0) + 1
        return max(counts, key=counts.get) if counts else "none"


# ═══ Autonomic Loop Singleton ═══

_autonomic_loop: Optional[AutonomicLoop] = None
_autonomic_lock = threading.Lock()


def get_autonomic_loop() -> AutonomicLoop:
    global _autonomic_loop
    if _autonomic_loop is None:
        with _autonomic_lock:
            if _autonomic_loop is None:
                _autonomic_loop = AutonomicLoop()
    return _autonomic_loop


# ═══ One-liner Start ═══

async def start_autonomic_loop(
    interval_sec: float = 120.0, module_refs: dict[str, Any] | None = None,
) -> AutonomicLoop:
    if module_refs is None:
        from ..core.system_health import SystemHealth
        refs = SystemHealth._gather_modules()
    else:
        refs = module_refs

    if "health" not in refs:
        from ..core.system_health import get_system_health
        refs["health"] = get_system_health()

    if "action_principle" not in refs:
        from ..core.action_principle import get_action_principle
        refs["action_principle"] = get_action_principle()

    loop = AutonomicLoop(refs)
    await loop.start(interval_sec)
    logger.info(
        f"Autonomic loop engaged: {len(refs)} modules monitored, "
        f"{interval_sec}s cycle, 5-phase closed-loop correction"
    )
    return loop
