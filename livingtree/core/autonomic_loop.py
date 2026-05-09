"""Autonomic Self-Correction Loop — closed feedback across all modules.

The final architectural layer: closes the loop between detection, diagnosis,
repair, verification, and feedback — enabling fully autonomous self-optimization.

Five-phase cycle (runs continuously in background):
  DETECT   → SystemHealth.check() identifies degradation
  DIAGNOSE → ActionPrinciple pinpoints which module deviates from δS=0
  REPAIR   → Applies the specific fix derived from Euler-Lagrange
  VERIFY   → PredictabilityEngine checks if the fix improved the system
  FEEDBACK → Updates all models (plasticity, router, latent GRPO) with outcome

This is the biological autonomic nervous system analog:
  - Sympathetic (fight):  detect + diagnose + repair
  - Parasympathetic (rest): verify + feedback + consolidate

Integration: one line activates the entire self-correcting system:
  loop = await start_autonomic_loop(interval_sec=120)
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


# ═══ Data Types ═══


class Phase(str, Enum):
    DETECT = "detect"
    DIAGNOSE = "diagnose"
    REPAIR = "repair"
    VERIFY = "verify"
    FEEDBACK = "feedback"


class FixType(str, Enum):
    SELF_DISTILLATION = "self_distillation"    # Regularize synaptic distribution
    RECALIBRATE_REWARD = "recalibrate_reward"  # Adjust two-tiered reward alpha
    RELEASE_QUARANTINED = "release_quarantined" # Unblock isolated models
    EXPLORE_MORE = "explore_more"              # Increase Thompson exploration
    HOMEOSTATIC_SCALE = "homeostatic_scale"    # Global weight normalization
    DECAY_STALE = "decay_stale"                # Decay unused provider beliefs
    INJECT_NOVELTY = "inject_novelty"          # Break fixed-point self-model
    REDUCE_LTP = "reduce_ltp"                  # Slow learning to prevent interference
    PROMOTE_MATURE = "promote_mature"           # Consolidate active → mature


@dataclass
class FixAction:
    """A specific repair action derived from diagnosis."""
    fix_type: FixType
    target_module: str
    reason: str                    # Why this fix is needed
    params: dict[str, float]       # Fix parameters (from Euler-Lagrange)
    applied_at: float = 0.0
    success: bool | None = None    # Was it effective? (None = not yet verified)


@dataclass
class LoopCycle:
    """One complete autonomic self-correction cycle."""
    cycle_id: int
    # DETECT
    health_status: str
    health_score: float
    degraded_modules: list[str]
    # DIAGNOSE
    root_cause_module: str
    action_residual: float
    # REPAIR
    fixes_applied: list[FixAction]
    # VERIFY
    score_before: float
    score_after: float | None        # None if still pending
    improvement: float | None
    # FEEDBACK
    models_updated: list[str]
    # Timing
    total_ms: float
    timestamp: float = field(default_factory=time.time)

    @property
    def effective(self) -> bool:
        return self.improvement is not None and self.improvement > 0


# ═══ Autonomic Loop ═══


class AutonomicLoop:
    """Closed-loop autonomous self-correction across all subsystems.

    The biological analog:
      - Brainstem: monitors vital signs (health check)
      - Hypothalamus: diagnoses imbalance (action principle)
      - Autonomic NS: applies corrective action (fixes)
      - Cerebellum: verifies correction worked (predictability)
      - Hippocampus: consolidates learning (feedback)
    """

    def __init__(self, module_refs: dict[str, Any] | None = None):
        self._refs = module_refs or {}
        self._history: deque[LoopCycle] = deque(maxlen=50)
        self._running = False
        self._task: asyncio.Task | None = None
        self._cycle_count = 0
        self._total_improvements = 0.0

    # ═══ Start/Stop ═══

    async def start(self, interval_sec: float = 120.0) -> None:
        """Start the autonomic self-correction loop.

        Runs a full 5-phase cycle every interval_sec seconds.
        """
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

    # ═══ Five-Phase Cycle ═══

    async def _run_cycle(self) -> LoopCycle | None:
        t0 = time.time()
        self._cycle_count += 1
        cycle_id = self._cycle_count

        # ═══ PHASE 1: DETECT ═══
        health = self._refs.get("health")
        if not health:
            return None
        report = health.check(self._refs)
        score_before = report.overall_score
        degraded = [s.name for s in report.subsystems if s.status.value in ("degrading", "critical")]

        if not degraded and report.overall_status.value not in ("degrading", "critical"):
            logger.debug(f"Cycle {cycle_id}: OPTIMAL — no action needed (score={score_before:.3f})")
            return None

        # ═══ PHASE 2: DIAGNOSE ═══
        action_p = self._refs.get("action_principle")
        root_cause = "unknown"
        action_residual = 0.0
        if action_p:
            analysis = action_p.analyze()
            root_cause = action_p.most_deviant_module()
            action_residual = analysis.avg_el_residual
            logger.info(f"Cycle {cycle_id}: root cause = {root_cause} (EL residual={action_residual:.3f})")

        # ═══ PHASE 3: REPAIR ═══
        fixes = self._derive_fixes(report, root_cause, action_p)
        for fix in fixes:
            self._apply_fix(fix)

        # ═══ PHASE 4: VERIFY ═══
        # Brief wait for fixes to take effect
        await asyncio.sleep(2.0)
        report_after = health.check(self._refs)
        score_after = report_after.overall_score
        improvement = round(score_after - score_before, 4)

        for fix in fixes:
            fix.success = improvement > 0

        # ═══ PHASE 5: FEEDBACK ═══
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

    # ═══ Fix Derivation ═══

    def _derive_fixes(
        self, report: Any, root_cause: str, action_p,
    ) -> list[FixAction]:
        """Derive specific fixes from diagnosis.

        Maps: health alert + action principle deviation → concrete fix
        """
        fixes: list[FixAction] = []

        # Synaptic interference → self-distillation
        syn = next((s for s in report.subsystems if s.name == "synaptic_plasticity"), None)
        if syn and syn.status.value in ("degrading", "critical"):
            fixes.append(FixAction(
                fix_type=FixType.SELF_DISTILLATION,
                target_module="synaptic",
                reason=f"Interference ratio elevated, synaptic degradation detected",
                params={"strength": 0.1},
            ))

        # Model pool low availability → release quarantined
        pool = next((s for s in report.subsystems if s.name == "model_pool"), None)
        if pool and pool.score < 0.5:
            fixes.append(FixAction(
                fix_type=FixType.RELEASE_QUARANTINED,
                target_module="pool",
                reason=f"Model availability low ({pool.key_metrics.get('available', 0)} available)",
                params={},
            ))

        # Router uncertainty → explore more
        router = next((s for s in report.subsystems if s.name == "thompson_router"), None)
        if router and router.key_metrics.get("providers_tracked", 0) < 3:
            fixes.append(FixAction(
                fix_type=FixType.EXPLORE_MORE,
                target_module="router",
                reason="Insufficient provider exploration data",
                params={"exploration_weight": 0.25},
            ))

        # Self-model fixed point → inject novelty
        consc = next((s for s in report.subsystems if s.name == "consciousness"), None)
        if consc and any("fixed point" in a.lower() for a in consc.alerts):
            fixes.append(FixAction(
                fix_type=FixType.INJECT_NOVELTY,
                target_module="consciousness",
                reason="Self-model reached fixed point",
                params={"intensity": 0.8},
            ))

        # Economic ROI low → recalibrate
        eco = next((s for s in report.subsystems if s.name == "economic"), None)
        if eco and eco.score < 0.5:
            fixes.append(FixAction(
                fix_type=FixType.RECALIBRATE_REWARD,
                target_module="economic",
                reason=f"Low ROI or high daily spend",
                params={"target_ratio": 0.6},
            ))

        # Euler-Lagrange: high potential → homeostatic scaling
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

    # ═══ Fix Application ═══

    def _apply_fix(self, fix: FixAction) -> None:
        """Apply a fix to the target module."""
        fix.applied_at = time.time()
        sp = self._refs.get("plasticity")
        pool = self._refs.get("pool")
        router = self._refs.get("router")
        consc = self._refs.get("consciousness")
        ie = self._refs.get("inquiry_engine")

        try:
            if fix.fix_type == FixType.SELF_DISTILLATION:
                if sp:
                    sp.regularize_distribution(strength=fix.params.get("strength", 0.1))
                    logger.info(f"FIX: self-distillation (strength={fix.params['strength']})")
            elif fix.fix_type == FixType.RELEASE_QUARANTINED:
                if pool:
                    released = 0
                    for m in pool._models.values():
                        if m.status.value == "quarantined":
                            m.status = type(m.status).UNKNOWN
                            m.failure_streak = 0
                            released += 1
                    logger.info(f"FIX: released {released} quarantined models")
            elif fix.fix_type == FixType.EXPLORE_MORE:
                if router:
                    router._exploration_weight = fix.params.get("exploration_weight", 0.25)
                    logger.info(f"FIX: exploration weight → {router._exploration_weight}")
            elif fix.fix_type == FixType.INJECT_NOVELTY:
                if consc:
                    consc.experience(
                        event_type="insight",
                        content="My self-model has been perturbed to escape a fixed point. I am evolving again.",
                        causal_source="self",
                        intensity=fix.params.get("intensity", 0.8),
                    )
                    logger.info("FIX: novelty injected into self-model")
            elif fix.fix_type == FixType.RECALIBRATE_REWARD:
                if ie and hasattr(ie, '_reward'):
                    ie._reward.calibrate(target_task_ratio=fix.params.get("target_ratio", 0.5))
                    logger.info(f"FIX: reward α → {ie._reward._alpha:.3f}")
            elif fix.fix_type == FixType.REDUCE_LTP:
                if sp and sp.LTP_RATE > fix.params.get("ltp_rate", 0.08):
                    sp.LTP_RATE = fix.params["ltp_rate"]
                    logger.info(f"FIX: LTP rate → {sp.LTP_RATE:.4f}")
        except Exception as e:
            logger.error(f"Fix failed ({fix.fix_type.value}): {e}")
            fix.success = False

    # ═══ Feedback ═══

    def _feedback_cycle(self, fixes: list[FixAction], improvement: float) -> list[str]:
        """Close the feedback loop: update learning models with outcome."""
        updated = []
        sp = self._refs.get("plasticity")
        pe = self._refs.get("predictability")

        # Record fix effectiveness as an experience for future learning
        for fix in fixes:
            if fix.success is True and sp:
                sp.strengthen(f"fix:{fix.fix_type.value}", boost=improvement * 2)
                updated.append("synaptic")
            elif fix.success is False and sp:
                sp.weaken(f"fix:{fix.fix_type.value}", penalty=abs(improvement) * 2)

        # Feed predictability data
        if pe and improvement != 0:
            pe.feed("autonomic_improvement", improvement)
            updated.append("predictability")

        return updated

    # ═══ Stats ═══

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


# ═══ One-liner ═══

async def start_autonomic_loop(
    interval_sec: float = 120.0, module_refs: dict[str, Any] | None = None,
) -> AutonomicLoop:
    """Start the fully autonomous self-correcting system.

    This is the single entry point that activates all five phases:
      DETECT → DIAGNOSE → REPAIR → VERIFY → FEEDBACK

    Args:
        interval_sec: How often to run a full cycle (default: 2 min)
        module_refs: Pre-built module references (auto-detected if None)

    Returns:
        Running AutonomicLoop instance
    """
    if module_refs is None:
        from .system_health import SystemHealth
        refs = SystemHealth._gather_modules()
    else:
        refs = module_refs

    # Ensure health monitor is in refs
    if "health" not in refs:
        from .system_health import get_system_health
        refs["health"] = get_system_health()

    # Ensure action principle is in refs
    if "action_principle" not in refs:
        from .action_principle import get_action_principle
        refs["action_principle"] = get_action_principle()

    loop = AutonomicLoop(refs)
    await loop.start(interval_sec)
    logger.info(
        f"Autonomic loop engaged: {len(refs)} modules monitored, "
        f"{interval_sec}s cycle, 5-phase closed-loop correction"
    )
    return loop


__all__ = [
    "AutonomicLoop", "LoopCycle", "FixAction", "FixType", "Phase",
    "start_autonomic_loop",
]
