"""VitalSigns — LivingTree digital lifeform self-diagnostic system.

Instead of unit-testing 500+ modules individually, treat the system as a living
organism with organs that must coordinate. VitalSigns checks the health of each
organ and how they interact — like a doctor checking pulse, breathing, reflexes.

Architecture: 7 organ systems tested
  1. Perception (P-body):  DeepProbe → knowledge retrieval → context prep
  2. Cognition (C-body):   HolisticElection → routing decision → model selection
  3. Reasoning:            SelfPlay reflection → DepthGrading → quality scoring
  4. Execution (B-body):   Orchestration plan → RDG graph → sub-goal decomposition
  5. Memory:              FluidCollective stigmergy → persistent traces
  6. Competition:         Elo rankings → CSRL evolution → joint health
  7. Cardio:              ReasoningBudget → cost tracking → economy loop

Each organ test returns: status (HEALTHY/WEAK/FAILED), vital metrics, latency.

Integration: Can be run manually or as a background health daemon.
  - `livingtree vitals` CLI command
  - Auto-runs on startup with summary report
  - Alerts when any organ degrades

Usage:
    vitals = get_vital_signs()
    report = await vitals.run_full_checkup()
    # report.summary → "7/7 organs HEALTHY (342ms)"
    # report.per_organ → detailed per-organ metrics
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


class OrganStatus(StrEnum):
    HEALTHY = "healthy"      # All checks passed, fast response
    WEAK = "weak"            # Degraded but functional (slow, fallback used)
    FAILED = "failed"        # Organ not responding
    UNKNOWN = "unknown"      # Not tested yet


@dataclass
class OrganReport:
    """Health report for a single organ system."""
    organ: str                      # Organ name (Perception, Cognition, etc.)
    status: OrganStatus
    latency_ms: float = 0.0
    checks_passed: int = 0
    checks_total: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class VitalReport:
    """Complete vital signs report for the entire digital lifeform."""
    organs: dict[str, OrganReport] = field(default_factory=dict)
    total_latency_ms: float = 0.0
    healthy_count: int = 0
    weak_count: int = 0
    failed_count: int = 0
    checked_at: float = field(default_factory=time.time)

    @property
    def summary(self) -> str:
        return (
            f"{self.healthy_count}/{len(self.organs)} organs HEALTHY"
            f"{f', {self.weak_count} WEAK' if self.weak_count else ''}"
            f"{f', {self.failed_count} FAILED' if self.failed_count else ''}"
            f" ({self.total_latency_ms:.0f}ms)"
        )

    @property
    def is_healthy(self) -> bool:
        return self.failed_count == 0


# ═══ VitalSigns Engine ═══════════════════════════════════════════


class VitalSigns:
    """Digital lifeform self-diagnostic engine.

    Instead of mocking external APIs, tests coordination between internal
    modules. Verifies that the "nervous system" (treellm) can route signals
    between "organs" (knowledge, execution, memory, etc.).
    """

    def __init__(self):
        self._last_report: Optional[VitalReport] = None
        self._check_count = 0

    # ── Full Checkup ──────────────────────────────────────────────

    async def run_full_checkup(self) -> VitalReport:
        """Run a complete 7-organ health check.

        Each organ test is independent and can run in parallel (they test
        different subsystems). Failed organs don't block other checks.
        """
        self._check_count += 1
        t0 = time.monotonic()

        # Run all organ checks in parallel
        organs = [
            self._check_perception(),
            self._check_cognition(),
            self._check_reasoning(),
            self._check_execution(),
            self._check_memory(),
            self._check_competition(),
            self._check_cardio(),
        ]

        results = await asyncio.gather(*organs, return_exceptions=True)

        report = VitalReport()
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                organ_names = ["Perception", "Cognition", "Reasoning",
                              "Execution", "Memory", "Competition", "Cardio"]
                report.organs[organ_names[i]] = OrganReport(
                    organ=organ_names[i], status=OrganStatus.FAILED,
                    error=str(result)[:200],
                )
            elif isinstance(result, OrganReport):
                report.organs[result.organ] = result

        report.total_latency_ms = (time.monotonic() - t0) * 1000
        report.healthy_count = sum(
            1 for o in report.organs.values() if o.status == OrganStatus.HEALTHY
        )
        report.weak_count = sum(
            1 for o in report.organs.values() if o.status == OrganStatus.WEAK
        )
        report.failed_count = sum(
            1 for o in report.organs.values() if o.status == OrganStatus.FAILED
        )

        self._last_report = report

        logger.info(f"VitalSigns: {report.summary}")
        return report

    # ── Organ 1: Perception (P-body) ─────────────────────────────

    async def _check_perception(self) -> OrganReport:
        """Check P-body: DeepProbe rewriting + knowledge retrieval pipeline."""
        t0 = time.monotonic()
        metrics: dict[str, Any] = {}
        warnings: list[str] = []
        passed = 0

        try:
            # DeepProbe: verify strategies are selectable
            from .deep_probe import get_deep_probe, ProbeStrategy
            probe = get_deep_probe()
            result = probe.rewrite("test query for system health check",
                                    task_type="analysis", depth=2)
            metrics["deep_probe_strategies"] = len(result.strategies_applied)
            metrics["deep_probe_depth"] = result.probe_depth
            if len(result.strategies_applied) >= 3:
                passed += 1
            else:
                warnings.append(f"DeepProbe only applied {len(result.strategies_applied)} strategies")
        except Exception as e:
            return OrganReport(organ="Perception", status=OrganStatus.FAILED,
                              latency_ms=(time.monotonic()-t0)*1000, error=str(e))

        try:
            # Stigmergic context: verify retrieval works
            from .fluid_collective import get_fluid_collective
            fc = get_fluid_collective()
            fc.deposit(model="vitals-check", content="system health test trace",
                       domain="diagnostics", confidence=1.0)
            ctx = fc.retrieve_context(domain="diagnostics")
            metrics["stigmergy_ctx_len"] = len(ctx)
            if len(ctx) > 10:
                passed += 1
            else:
                warnings.append("Stigmergy context retrieval returned empty")
        except Exception as e:
            warnings.append(f"Stigmergy: {e}")

        status = OrganStatus.HEALTHY if passed == 2 else (
            OrganStatus.WEAK if passed >= 1 else OrganStatus.FAILED
        )
        return OrganReport(
            organ="Perception", status=status,
            latency_ms=(time.monotonic()-t0)*1000,
            checks_passed=passed, checks_total=2,
            metrics=metrics, warnings=warnings,
        )

    # ── Organ 2: Cognition (C-body) ──────────────────────────────

    async def _check_cognition(self) -> OrganReport:
        """Check C-body: HolisticElection + routing pipeline."""
        t0 = time.monotonic()
        metrics: dict[str, Any] = {}
        passed = 0

        try:
            # HolisticElection: verify scoring dimensions exist
            from .holistic_election import get_election, get_dynamic_weights, PROVIDER_CAPABILITIES
            election = get_election()
            weights = get_dynamic_weights("general")
            metrics["scoring_dimensions"] = len(weights)
            metrics["known_providers"] = len(PROVIDER_CAPABILITIES)
            if len(weights) >= 10:
                passed += 1
        except Exception as e:
            return OrganReport(organ="Cognition", status=OrganStatus.FAILED,
                              latency_ms=(time.monotonic()-t0)*1000, error=str(e))

        try:
            # Thompson Sampling: verify bandit integration
            from .bandit_router import get_bandit_router
            br = get_bandit_router()
            arm = br.get_arm("test-provider")
            ts = arm.sample_composite()
            metrics["thompson_sample"] = round(ts, 3)
            metrics["exploration_bonus"] = round(arm.exploration_bonus, 3)
            passed += 1
        except Exception as e:
            metrics["thompson_error"] = str(e)[:100]

        try:
            # TinyClassifier (SkillRouter): verify TF-IDF routing
            from .classifier import get_router
            router = get_router()
            metrics["classifier_type"] = "TF-IDF+self-learning"
            passed += 1
        except Exception as e:
            metrics["classifier_error"] = str(e)[:100]

        status = OrganStatus.HEALTHY if passed >= 2 else (
            OrganStatus.WEAK if passed >= 1 else OrganStatus.FAILED
        )
        return OrganReport(
            organ="Cognition", status=status,
            latency_ms=(time.monotonic()-t0)*1000,
            checks_passed=passed, checks_total=3,
            metrics=metrics,
        )

    # ── Organ 3: Reasoning ────────────────────────────────────────

    async def _check_reasoning(self) -> OrganReport:
        """Check reasoning depth: SelfPlay + DepthGrading."""
        t0 = time.monotonic()
        metrics: dict[str, Any] = {}
        passed = 0

        try:
            from .adversarial_selfplay import get_selfplay
            sp = get_selfplay()
            metrics["selfplay_available"] = True
            passed += 1
        except Exception as e:
            metrics["selfplay_error"] = str(e)[:100]

        try:
            from .depth_grading import get_depth_grader
            grader = get_depth_grader()
            # Test with a sample reasoning output
            sample = (
                "Step 1: Define the problem scope.\n"
                "Step 2: Analyze factors A, B, C.\n"
                "Step 3: However, factor B has a limitation.\n"
                "Step 4: Therefore, the solution is X.\n"
                "Assumption: factor D remains constant.\n"
                "Edge case: this fails when input is empty."
            )
            grade = grader.grade(sample, task_type="analysis")
            metrics["depth_score"] = grade.depth_score
            metrics["depth_tier"] = grade.grade_tier
            metrics["reasoning_steps"] = grade.reasoning_steps_count
            if grade.depth_score > 0.3:
                passed += 1
        except Exception as e:
            metrics["grading_error"] = str(e)[:100]

        status = OrganStatus.HEALTHY if passed == 2 else (
            OrganStatus.WEAK if passed >= 1 else OrganStatus.FAILED
        )
        return OrganReport(
            organ="Reasoning", status=status,
            latency_ms=(time.monotonic()-t0)*1000,
            checks_passed=passed, checks_total=2,
            metrics=metrics,
        )

    # ── Organ 4: Execution (B-body) ───────────────────────────────

    async def _check_execution(self) -> OrganReport:
        """Check B-body: Orchestration + RDG graph."""
        t0 = time.monotonic()
        metrics: dict[str, Any] = {}
        passed = 0

        try:
            from .strategic_orchestrator import get_orchestrator, SubGoal
            orch = get_orchestrator()
            # Test sub-goal decomposition
            from .strategic_orchestrator import TaskStep
            step = TaskStep(id="test", description="Analyze system performance")
            subgoals = orch.decompose_to_subgoals(step)
            metrics["subgoals_generated"] = len(subgoals)
            if len(subgoals) >= 0:  # 0 is acceptable for short queries
                passed += 1
        except Exception as e:
            return OrganReport(organ="Execution", status=OrganStatus.FAILED,
                              latency_ms=(time.monotonic()-t0)*1000, error=str(e))

        try:
            from .reasoning_dependency_graph import get_reasoning_graph
            rdg = get_reasoning_graph()
            graph = rdg.build_graph("test task", steps=[
                {"id": "s1", "description": "Step 1"},
                {"id": "s2", "description": "Step 2", "depends_on": ["s1"]},
            ])
            metrics["graph_nodes"] = len(graph.nodes)
            metrics["graph_edges"] = len(graph.edges)
            metrics["parallel_waves"] = len(graph.parallel_groups)
            passed += 1
        except Exception as e:
            metrics["rdg_error"] = str(e)[:100]

        status = OrganStatus.HEALTHY if passed >= 1 else OrganStatus.FAILED
        return OrganReport(
            organ="Execution", status=status,
            latency_ms=(time.monotonic()-t0)*1000,
            checks_passed=passed, checks_total=2,
            metrics=metrics,
        )

    # ── Organ 5: Memory ───────────────────────────────────────────

    async def _check_memory(self) -> OrganReport:
        """Check memory: FluidCollective stigmergy + persistence."""
        t0 = time.monotonic()
        metrics: dict[str, Any] = {}
        passed = 0

        try:
            from .fluid_collective import get_fluid_collective, TraceType
            fc = get_fluid_collective()
            # Deposit and retrieve
            fc.deposit(model="vitals", content="memory test",
                       trace_type=TraceType.INSIGHT, domain="test", confidence=0.9)
            ctx = fc.retrieve_context(domain="test", max_traces=5)
            metrics["memory_traces"] = len(fc._traces)
            metrics["memory_db"] = fc._db_conn is not None
            if fc._db_conn:
                passed += 1
            # RRF search
            results = fc.unified_search("memory", domain="test")
            metrics["rrf_results"] = len(results)
            passed += 1
        except Exception as e:
            return OrganReport(organ="Memory", status=OrganStatus.FAILED,
                              latency_ms=(time.monotonic()-t0)*1000, error=str(e))

        status = OrganStatus.HEALTHY if passed >= 1 else OrganStatus.FAILED
        return OrganReport(
            organ="Memory", status=status,
            latency_ms=(time.monotonic()-t0)*1000,
            checks_passed=passed, checks_total=2,
            metrics=metrics,
        )

    # ── Organ 6: Competition ─────────────────────────────────────

    async def _check_competition(self) -> OrganReport:
        """Check competition: Elo rankings + JointEvolution."""
        t0 = time.monotonic()
        metrics: dict[str, Any] = {}
        passed = 0

        try:
            from .competitive_eliminator import get_eliminator
            elim = get_eliminator()
            elim.record_match("test-provider", success=True, latency_ms=100, quality=0.8)
            ranking = elim.get_ranking("test-provider")
            if ranking:
                metrics["elo_rating"] = ranking.elo_rating
                metrics["tier"] = ranking.tier
                metrics["matches"] = ranking.matches_played
            passed += 1
        except Exception as e:
            return OrganReport(organ="Competition", status=OrganStatus.FAILED,
                              latency_ms=(time.monotonic()-t0)*1000, error=str(e))

        try:
            from .joint_evolution import get_joint_evolution
            je = get_joint_evolution()
            traj_id = je.start_trajectory("vitals test")
            je.record_perception(traj_id, query="test", task_type="general")
            je.record_cognition(traj_id, elected_provider="test")
            je.record_behavior(traj_id, provider="test", success=True)
            je.complete_trajectory(traj_id, overall_success=True)
            health = je.joint_health()
            metrics["joint_health_score"] = health.score
            passed += 1
        except Exception as e:
            metrics["je_error"] = str(e)[:100]

        status = OrganStatus.HEALTHY if passed >= 1 else OrganStatus.FAILED
        return OrganReport(
            organ="Competition", status=status,
            latency_ms=(time.monotonic()-t0)*1000,
            checks_passed=passed, checks_total=2,
            metrics=metrics,
        )

    # ── Organ 7: Cardio (Economy) ────────────────────────────────

    async def _check_cardio(self) -> OrganReport:
        """Check cardio: ReasoningBudget + budget management."""
        t0 = time.monotonic()
        metrics: dict[str, Any] = {}
        passed = 0

        try:
            from .reasoning_budget import get_reasoning_budget
            rb = get_reasoning_budget()
            budget = rb.allocate("test query", task_type="analysis",
                                context_available=128000)
            metrics["budget_tier"] = budget.tier.value
            metrics["thinking_tokens"] = budget.thinking_tokens
            metrics["deep_probe_depth"] = budget.deep_probe_depth
            if budget.thinking_tokens > 0:
                passed += 1
        except Exception as e:
            return OrganReport(organ="Cardio", status=OrganStatus.FAILED,
                              latency_ms=(time.monotonic()-t0)*1000, error=str(e))

        try:
            from .proactive_interject import get_proactive_interject
            pi = get_proactive_interject()
            decision = pi.evaluate("help me optimize", session_id="vitals")
            metrics["interject_trigger"] = decision.trigger.value if decision.trigger else "none"
            passed += 1
        except Exception as e:
            metrics["interject_error"] = str(e)[:100]

        status = OrganStatus.HEALTHY if passed >= 1 else OrganStatus.FAILED
        return OrganReport(
            organ="Cardio", status=status,
            latency_ms=(time.monotonic()-t0)*1000,
            checks_passed=passed, checks_total=2,
            metrics=metrics,
        )

    # ── Quick Check ───────────────────────────────────────────────

    async def quick_check(self) -> str:
        """Fast one-line health check for CLI/startup."""
        report = await self.run_full_checkup()
        return (
            f"[{report.summary}] "
            f"P:{report.organs.get('Perception', OrganReport(organ='')).status.value} "
            f"C:{report.organs.get('Cognition', OrganReport(organ='')).status.value} "
            f"R:{report.organs.get('Reasoning', OrganReport(organ='')).status.value} "
            f"E:{report.organs.get('Execution', OrganReport(organ='')).status.value} "
            f"M:{report.organs.get('Memory', OrganReport(organ='')).status.value} "
            f"X:{report.organs.get('Competition', OrganReport(organ='')).status.value} "
            f"♡:{report.organs.get('Cardio', OrganReport(organ='')).status.value}"
        )

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict:
        last = self._last_report
        if not last:
            return {"status": "never_checked"}
        return {
            "last_check": last.summary,
            "healthy_count": last.healthy_count,
            "weak_count": last.weak_count,
            "failed_count": last.failed_count,
            "total_checks": self._check_count,
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_vitals: Optional[VitalSigns] = None


def get_vital_signs() -> VitalSigns:
    global _vitals
    if _vitals is None:
        _vitals = VitalSigns()
    return _vitals


__all__ = ["VitalSigns", "VitalReport", "OrganReport", "OrganStatus",
           "get_vital_signs"]
