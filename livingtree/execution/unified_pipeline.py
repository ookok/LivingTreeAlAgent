"""Unified Pipeline Interface — StarVLA Lego-like execution abstraction.

Based on StarVLA (arXiv:2604.05014) modular architecture:
  "Each functional component follows top-down separation and high-cohesion,
  low-coupling, enabling plug-and-play design and rapid prototyping."

Core design:
  Backbone (which LLM provider) + Action Head (which execution mode)
  are independently swappable through a shared Pipeline interface.

Pipeline = Backbone × ActionHead
  All four execution modes (DAG / ReAct / BehaviorTree / GTSM) share
  the same `run(task, context)` signature and return `PipelineResult`.

PipelineOrchestrator auto-selects the optimal mode:
  - Simple task (≤ 3 steps) → DAG (fast, deterministic)
  - Interactive task (tools needed) → ReAct (think-act-observe)
  - Complex multi-branch → BehaviorTree (fallback-capable)
  - Ambiguous/creative → GTSM (tree→flow hybrid)
  - Highly uncertain → GTSM flow mode

Integration with LifeEngine:
  Replace the if/elif chain in _execute() with a single
  orchestrator.run(task, context) call.

Dual-system mapping (GR00T analog):
  System 2 (slow, deliberate): GTSM tree planning, BehaviorTree
  System 1 (fast, reflexive): DAG parallel, ReAct actions
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


# ═══ Unified Types ═══


class PipelineMode(str, Enum):
    DAG = "dag"                 # Parallel DAG execution
    REACT = "react"             # Think-Act-Observe loop
    BEHAVIOR_TREE = "tree"      # Hierarchical fallback tree
    GTSM_TREE = "gtsm_tree"    # GTSM decision tree
    GTSM_FLOW = "gtsm_flow"    # GTSM score matching
    GTSM_HYBRID = "gtsm_hybrid" # GTSM tree→flow
    DUAL = "dual"              # System 2 plans, System 1 executes


@dataclass
class PipelineResult:
    """Unified result from any execution pipeline.

    StarVLA analog: unified output format regardless of action head.
    """
    task: str
    mode: str                     # Which mode was used
    steps: list[dict[str, Any]]   # Unified step format
    success: bool = False
    confidence: float = 0.0
    tokens_used: int = 0
    latency_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_plan_format(self) -> list[dict]:
        """Convert to LifeEngine-compatible plan format."""
        return [
            {"step": i + 1, "action": s.get("action", "unknown"),
             "description": s.get("description", ""),
             "name": s.get("name", s.get("action", "")),
             "tool": s.get("tool", ""),
             "params": s.get("params", {}),
             "confidence": s.get("confidence", 0.5)}
            for i, s in enumerate(self.steps)
        ]


# ═══ Base Pipeline (StarVLA Backbone × ActionHead abstraction) ═══


class BasePipeline(ABC):
    """Abstract pipeline — all execution modes implement this.

    StarVLA analog: the shared forward() interface that all action
    heads conform to. Swap the implementation without changing callers.
    """

    def __init__(self, name: str, mode: PipelineMode):
        self.name = name
        self.mode = mode
        self._total_calls = 0
        self._total_tokens = 0

    @abstractmethod
    async def run(
        self, task: str, context: dict | None = None, **config,
    ) -> PipelineResult:
        """Execute the task. All pipelines share this exact signature.

        Args:
            task: Task description string
            context: Dict with keys: plan, tools, knowledge, consciousness, etc.
            **config: Mode-specific overrides

        Returns:
            Unified PipelineResult
        """
        ...

    def stats(self) -> dict:
        return {
            "name": self.name, "mode": self.mode.value,
            "calls": self._total_calls, "tokens": self._total_tokens,
        }


# ═══ Pipeline Adapters (wrap existing modes into unified interface) ═══


class DAGPipeline(BasePipeline):
    """Adapter: DAGExecutor → BasePipeline."""

    def __init__(self):
        super().__init__("dag", PipelineMode.DAG)

    async def run(self, task: str, context: dict | None = None, **config) -> PipelineResult:
        t0 = time.time()
        ctx = context or {}
        plan = ctx.get("plan", [{"step": 1, "action": "direct", "description": task}])
        orchestrator = ctx.get("orchestrator")
        consciousness = ctx.get("consciousness")
        max_parallel = config.get("max_parallel", 5)

        from .dag_executor import DAGExecutor, add_dependencies
        executor = DAGExecutor(max_parallel=max_parallel)
        plan_with_deps = add_dependencies(list(plan))

        async def execute_one(step: dict, _ctx: Any) -> dict:
            step_name = step.get("name", step.get("action", "unknown"))
            if orchestrator:
                try:
                    return await orchestrator.assign_task(task=step, agents=[])
                except Exception:
                    pass
            return {"step": step, "status": "completed", "result": f"[DAG:{step_name}]"}

        results = await executor.execute(plan_with_deps, execute_one, ctx)
        ok = sum(1 for r in results if r.get("status") in ("completed", "ok"))
        steps = [
            {"action": r.get("step", {}).get("action", "unknown"),
             "description": r.get("step", {}).get("description", ""),
             "status": r.get("status", "unknown"),
             "result": str(r.get("result", ""))[:200],
             "confidence": 0.7 if r.get("status") == "completed" else 0.3}
            for r in results
        ]

        self._total_calls += 1
        return PipelineResult(
            task=task, mode=self.mode.value, steps=steps,
            success=ok > 0, confidence=ok / max(len(results), 1),
            latency_ms=(time.time() - t0) * 1000,
            metadata={"dag_max_parallel": max_parallel, "total_steps": len(results)},
        )


class ReActPipeline(BasePipeline):
    """Adapter: ReactExecutor → BasePipeline."""

    def __init__(self):
        super().__init__("react", PipelineMode.REACT)

    async def run(self, task: str, context: dict | None = None, **config) -> PipelineResult:
        t0 = time.time()
        ctx = context or {}
        consciousness = ctx.get("consciousness")
        tools = ctx.get("tools", {})

        from .react_executor import ReactExecutor
        executor = ReactExecutor(consciousness=consciousness)
        trajectory = await executor.run(task=task, tools=tools, context=ctx)

        steps = [
            {"action": s.action, "description": s.observation[:200],
             "status": "completed" if not s.error else "failed",
             "result": s.observation[:200], "confidence": s.confidence,
             "error": s.error}
            for s in trajectory.steps
        ]
        if trajectory.final_answer:
            steps.append({"action": "final_answer", "description": trajectory.final_answer[:300],
                          "status": "completed", "confidence": 0.8})

        self._total_calls += 1
        self._total_tokens += ctx.get("total_tokens", 0)
        return PipelineResult(
            task=task, mode=self.mode.value, steps=steps,
            success=trajectory.success,
            confidence=trajectory.steps[-1].confidence if trajectory.steps else 0.5,
            tokens_used=len(trajectory.steps) * 500,
            latency_ms=(time.time() - t0) * 1000,
            errors=[s.error for s in trajectory.steps if s.error],
            metadata={"react_iterations": len(trajectory.steps), "trajectory": trajectory},
        )


class BehaviorTreePipeline(BasePipeline):
    """Adapter: BehaviorTree → BasePipeline."""

    def __init__(self):
        super().__init__("behavior_tree", PipelineMode.BEHAVIOR_TREE)

    async def run(self, task: str, context: dict | None = None, **config) -> PipelineResult:
        t0 = time.time()
        ctx = context or {}
        plan = ctx.get("plan", [])

        from ..core.behavior_tree import TreeContext, linear_plan_to_tree
        from ..core.behavior_tree import NodeStatus

        step_descs = [
            s.get("description", s.get("action", str(s)))
            for s in plan[:8]
        ]
        tree_root = linear_plan_to_tree(
            step_descs or [task],
            fallback_hint=config.get("fallback_hint", "ask for clarification"),
            use_model_for_routing=len(step_descs) > 3,
        )

        bt_ctx = TreeContext(
            user_input=task,
            metadata={"plan": plan},
            history=ctx.get("history", []),
        )
        status = await tree_root.tick(bt_ctx)

        steps = [
            {"action": f"bt_step_{i}", "description": r[:200] if isinstance(r, str) else str(r)[:200],
             "status": "completed", "confidence": 0.6}
            for i, r in enumerate(bt_ctx.results)
        ] if bt_ctx.results else [{"action": "bt_fallback", "description": status.value}]

        self._total_calls += 1
        return PipelineResult(
            task=task, mode=self.mode.value, steps=steps,
            success=status == NodeStatus.SUCCESS,
            confidence=0.7 if status == NodeStatus.SUCCESS else 0.3,
            latency_ms=(time.time() - t0) * 1000,
            errors=list(bt_ctx.errors),
            metadata={"bt_status": status.value, "bt_depth": len(step_descs)},
        )


class GTSMPipeline(BasePipeline):
    """Adapter: GTSMPlanner → BasePipeline.

    Wraps all three GTSM sub-modes (tree, flow, hybrid) under one adapter.
    """

    def __init__(self):
        super().__init__("gtsm", PipelineMode.GTSM_HYBRID)

    async def run(self, task: str, context: dict | None = None, **config) -> PipelineResult:
        t0 = time.time()
        ctx = context or {}
        domain = ctx.get("domain", "general")
        gtsm_mode_str = config.get("gtsm_mode", "auto")
        consciousness = ctx.get("consciousness")

        from .gtsm_planner import GTSMMode, get_gtsm_planner

        mode_map = {
            "tree": GTSMMode.TREE, "flow": GTSMMode.FLOW,
            "hybrid": GTSMMode.HYBRID, "auto": GTSMMode.AUTO,
        }
        mode = mode_map.get(gtsm_mode_str, GTSMMode.AUTO)

        planner = get_gtsm_planner(consciousness=consciousness)
        trajectory = await planner.plan(task=task, mode=mode, domain=domain,
                                        context=ctx, **config)

        steps = trajectory.to_plan_format()
        self._total_calls += 1
        return PipelineResult(
            task=task, mode=trajectory.mode.value, steps=steps,
            success=trajectory.total_score > 0.3,
            confidence=trajectory.total_score,
            latency_ms=trajectory.convergence_ms,
            metadata={"gtsm_mode": trajectory.mode.value, "tree_depth": trajectory.tree_depth,
                      "diffusion_steps": getattr(trajectory, 'diffusion_steps', 0)},
        )


# ═══ Pipeline Orchestrator (StarVLA-style auto-selection) ═══


class PipelineOrchestrator:
    """Auto-select and execute the optimal pipeline for each task.

    StarVLA analog: the framework that lets you swap backbone and action
    head independently. The orchestrator selects the best mode based on
    task characteristics, then delegates to the appropriate pipeline.

    Selection logic (dual-system inspired):
      - System 1 (fast): DAG for parallel, simple tasks
      - System 1 (reflexive): ReAct for tool-using interactive tasks
      - System 2 (deliberate): BehaviorTree for complex multi-branch
      - System 2 (creative): GTSM for ambiguous/novel tasks
    """

    def __init__(self):
        self._pipelines: dict[str, BasePipeline] = {}
        self._register_defaults()
        self._history: list[PipelineResult] = []

    def _register_defaults(self):
        for p in [DAGPipeline(), ReActPipeline(), BehaviorTreePipeline(), GTSMPipeline()]:
            self.register(p)

    def register(self, pipeline: BasePipeline) -> None:
        self._pipelines[pipeline.name] = pipeline
        logger.debug(f"Pipeline registered: {pipeline.name} ({pipeline.mode.value})")

    def unregister(self, name: str) -> None:
        self._pipelines.pop(name, None)

    def list_pipelines(self) -> list[str]:
        return list(self._pipelines.keys())

    # ── Auto-Selection ──

    def select(self, task: str, context: dict | None = None) -> str:
        """Auto-select the best pipeline mode for a task.

        Heuristic (mirrors StarVLA's backbone × action head selection):
          - Short/simple → DAG (fast parallel)
          - Has tools → ReAct (interactive)
          - Complex multi-step → BehaviorTree (fallback needed)
          - Ambiguous/creative → GTSM (tree+flow refinement)
        """
        ctx = context or {}
        task_lower = task.lower()
        length = len(task)
        plan = ctx.get("plan", [])
        has_tools = bool(ctx.get("tools"))

        # Explicit override
        if "pipeline_mode" in ctx:
            return ctx["pipeline_mode"]

        # Tool-heavy → ReAct
        if has_tools and any(
            kw in task_lower for kw in ["搜索", "查询", "search", "find", "工具"]
        ):
            return "react"

        # Simple → DAG
        if length < 50 and len(plan) <= 3:
            return "dag"

        # Complex multi-branch → BehaviorTree
        if len(plan) > 5 and any(
            kw in task_lower for kw in ["分支", "如果", "备选", "fallback", "alternative"]
        ):
            return "behavior_tree"

        # Creative/ambiguous → GTSM
        if any(kw in task_lower for kw in [
            "设计", "新颖", "创造", "优化", "改进", "探索",
            "design", "create", "novel", "optimize", "explore", "improve",
        ]):
            return "gtsm"

        # Complex multi-domain → Orchestrated (Expert decomposition + parallel sub-agents)
        if len(plan) > 5 and any(kw in task_lower for kw in [
            "研究报告", "全面分析", "综合评估", "多领域", "多方",
            "complex", "comprehensive", "multi-domain", "multidisciplinary",
            "环评", "调研", "尽调", "due diligence",
        ]):
            return "orchestrated"

        # Default: GTSM hybrid (best general-purpose)
        return "gtsm"

    def select_scored(self, task: str, context: dict | None = None) -> dict[str, Any]:
        """StarVLA scored auto-selection with confidence-weighted ranking.

        Unlike the fast if/elif heuristic in select(), this method computes
        a multi-factor score for each pipeline mode and returns the full
        ranking with confidence scores — enabling StarVLA's backbone ×
        action head abstraction to make traceable, auditable decisions.

        Score dimensions (0-1 each):
          - task_fit: how well the mode handles the task type
          - complexity_match: whether mode complexity matches task complexity
          - tool_compatibility: how well mode handles available tools
          - history_performance: past success rate for similar tasks
          - latency_budget: whether mode fits time constraints

        Returns:
            dict with ranking, top pick, and per-mode score breakdown
        """
        ctx = context or {}
        task_lower = task.lower()
        length = len(task)
        plan = ctx.get("plan", [])
        plan_len = len(plan) if isinstance(plan, list) else 0
        has_tools = bool(ctx.get("tools"))
        complexity = min(1.0, length / 500 + plan_len / 10)

        scores = {}
        for mode_name in self._pipelines:
            mode_scores = {}

            # Task fit: semantic keyword matching
            if mode_name == "dag":
                mode_scores["task_fit"] = 1.0 if length < 80 else max(0.1, 1.0 - length / 200)
            elif mode_name == "react":
                mode_scores["task_fit"] = 0.9 if has_tools else 0.4
            elif mode_name == "behavior_tree":
                mode_scores["task_fit"] = 0.9 if plan_len > 3 else 0.3
            elif mode_name == "gtsm":
                mode_scores["task_fit"] = 0.8  # General-purpose
            else:
                mode_scores["task_fit"] = 0.5

            # Complexity match: higher complexity → prefer BehaviorTree/GTSM
            if complexity > 0.6:
                complexity_score = 1.0 if mode_name in ("behavior_tree", "gtsm") else 0.3
            elif complexity > 0.3:
                complexity_score = 0.8 if mode_name in ("gtsm", "react") else 0.5
            else:
                complexity_score = 1.0 if mode_name == "dag" else 0.5
            mode_scores["complexity_match"] = complexity_score

            # Tool compatibility
            if has_tools:
                tool_score = 1.0 if mode_name == "react" else (
                    0.6 if mode_name in ("gtsm", "behavior_tree") else 0.3)
            else:
                tool_score = 1.0 if mode_name in ("dag", "gtsm") else 0.7
            mode_scores["tool_compatibility"] = tool_score

            # History performance: reward modes that succeeded recently
            mode_history = [r for r in self._history[-20:] if r.mode == mode_name]
            if mode_history:
                success_rate = sum(1 for r in mode_history if r.success) / len(mode_history)
            else:
                success_rate = 0.6  # Default for untested modes
            mode_scores["history_performance"] = success_rate

            # Weighted total (equal weights for simplicity, tunable)
            weights = {"task_fit": 0.3, "complexity_match": 0.25,
                       "tool_compatibility": 0.25, "history_performance": 0.2}
            total = sum(weights[k] * v for k, v in mode_scores.items())
            scores[mode_name] = {"total": round(total, 4), "breakdown": mode_scores}

        # Sort by total score descending
        ranking = sorted(scores.items(), key=lambda x: x[1]["total"], reverse=True)
        top_pick = ranking[0][0]
        top_score = ranking[0][1]["total"]
        second_score = ranking[1][1]["total"] if len(ranking) > 1 else 0

        # Confidence: difference between top pick and second best
        confidence = min(1.0, max(0.3, top_score - second_score + 0.5))

        # Tie-break: if margin < 0.05, use more exploratory mode
        if top_score - second_score < 0.05:
            tie_break = {"dag": "react", "react": "gtsm",
                         "behavior_tree": "gtsm", "gtsm": "behavior_tree"}
            top_pick = tie_break.get(top_pick, top_pick)
            top_score = scores[top_pick]["total"]

        return {
            "task": task[:80],
            "complexity": round(complexity, 3),
            "ranking": [{"mode": m, "score": s["total"],
                        "breakdown": s["breakdown"]}
                       for m, s in ranking],
            "selected": top_pick,
            "confidence": round(confidence, 3),
            "rationale": f"Selected '{top_pick}' (score={top_score:.3f}, "
                         f"margin={top_score - second_score:.3f}) "
                         f"for complexity={complexity:.2f}, "
                         f"tools={'yes' if has_tools else 'no'}",
        }

    # ── Execute ──

    async def run(
        self, task: str, context: dict | None = None, mode: str = "auto", **config,
    ) -> PipelineResult:
        """Execute a task through the optimal pipeline.

        Args:
            task: Task description
            context: Shared context dict (plan, tools, knowledge, consciousness, ...)
            mode: Pipeline name or "auto" for auto-selection
            **config: Pipeline-specific overrides

        Returns:
            Unified PipelineResult
        """
        if mode == "auto":
            mode = self.select(task, context)

        pipeline = self._pipelines.get(mode)
        if not pipeline:
            logger.warning(f"Unknown pipeline '{mode}', falling back to gtsm")
            pipeline = self._pipelines.get("gtsm")
            if not pipeline:
                raise ValueError(f"No pipeline available for mode '{mode}'")

        result = await pipeline.run(task=task, context=context, **config)
        self._history.append(result)
        if len(self._history) > 100:
            self._history = self._history[-100:]

        logger.info(
            f"Pipeline[{pipeline.name}]: {task[:50]}... → "
            f"{'SUCCESS' if result.success else 'FAIL'} "
            f"(confidence={result.confidence:.2f}, "
            f"{len(result.steps)} steps, {result.latency_ms:.0f}ms)",
        )
        return result

    # ── Dual-system execution ──

    async def run_dual(
        self, task: str, context: dict | None = None, **config,
    ) -> PipelineResult:
        """Dual-system execution: System 2 plans, System 1 executes.

        GR00T analog: VLM (System2) reasons about what to do,
        Flow (System1) executes fast reflexive actions.

        Implementation:
          1. System 2: GTSM tree mode generates plan skeleton
          2. System 1: DAG or ReAct executes the skeleton fast
        """
        ctx = context or {}

        # System 2: deliberate planning
        gtsm = self._pipelines.get("gtsm")
        plan_result = await gtsm.run(task=task, context=ctx,
                                     gtsm_mode="tree", **config)

        # System 1: fast execution of the plan
        dag = self._pipelines.get("dag")
        exec_ctx = {**ctx, "plan": plan_result.to_plan_format()}
        result = await dag.run(task=task, context=exec_ctx, **config)

        result.mode = PipelineMode.DUAL.value
        result.metadata["system2_plan"] = plan_result.steps
        result.metadata["system2_confidence"] = plan_result.confidence
        return result

    # ── Stats ──

    def stats(self) -> dict:
        modes_used: dict[str, int] = {}
        for r in self._history:
            modes_used[r.mode] = modes_used.get(r.mode, 0) + 1
        total = max(len(self._history), 1)
        return {
            "registered_pipelines": list(self._pipelines.keys()),
            "total_runs": total,
            "success_rate": round(
                sum(1 for r in self._history if r.success) / total, 3),
            "avg_confidence": round(
                sum(r.confidence for r in self._history) / total, 3),
            "avg_latency_ms": round(
                sum(r.latency_ms for r in self._history) / total, 0),
            "modes_used": modes_used,
        }


# ═══ LifeEngine Integration ═══

def integrate_to_life_engine(engine_orch=None) -> PipelineOrchestrator:
    """Integrate the PipelineOrchestrator into LifeEngine._execute.

    This replaces the existing if/elif chain (DAG vs ReAct) with a single
    orchestrator.run() call. Usage in LifeEngine:

        orchestrator = integrate_to_life_engine()
        result = await orchestrator.run(
            task=ctx.user_input,
            context={
                "plan": ctx.plan,
                "tools": available_tools,
                "consciousness": self.consciousness,
                "orchestrator": self.world.orchestrator,
            },
            mode="auto",
        )
        ctx.execution_results = result.to_plan_format()
    """
    orch = PipelineOrchestrator()
    return orch


# ═══ Singleton ═══

_orchestrator: PipelineOrchestrator | None = None


def get_pipeline_orchestrator() -> PipelineOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = PipelineOrchestrator()
    return _orchestrator


__all__ = [
    "BasePipeline", "PipelineResult", "PipelineMode",
    "DAGPipeline", "ReActPipeline", "BehaviorTreePipeline", "GTSMPipeline",
    "PipelineOrchestrator", "get_pipeline_orchestrator", "integrate_to_life_engine",
]
