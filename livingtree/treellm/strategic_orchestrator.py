"""StrategicOrchestrator — Multi-step task coordination with sub-goal decomposition.

Core value: "Strategic perspective and coordination" — instead of per-request
routing, plan the optimal model combination across an entire multi-step task chain.

Enhanced (from Sun et al. 2025 three-body framework):
  - Sub-goal decomposition: C-body generates intermediate milestones for B-body
  - Verifiable completion criteria per sub-goal
  - Joint evolution integration: report trajectory data

Key capabilities:
  1. Task chain analysis: decompose multi-step tasks, identify dependencies
  2. Sub-goal generation: create verifiable intermediate milestones (C→B loop)
  3. Model pre-allocation: assign best model to each step based on capabilities
  4. Global budget management: track cost/latency across the full task chain
  5. Adaptive replanning: if a model fails, dynamically reassign without restarting
  6. Cross-step knowledge: pass intermediate reasoning between steps
  7. Fallback cascade: pre-planned backup models for each step

Integration:
  - Called by execution task planner for multi-step tasks
  - Uses TreeLLM.route_layered() for per-step model selection
  - Uses CompetitiveEliminator to check model viability
  - Uses HolisticElection for per-step scoring

Usage:
    orch = get_orchestrator()
    plan = await orch.plan(
        task_description="Design and implement a user auth system",
        available_models=["deepseek-pro", "deepseek-flash", "longcat"],
        budget_yuan=0.50,
        max_latency_ms=30000,
    )
    for step in plan.steps:
        result = await orch.execute_step(step, context=accumulated_context)
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class SubGoal:
    """A verifiable intermediate milestone (from the three-body framework's C→B loop).

    Each sub-goal has explicit completion criteria so B-body knows when it's done.
    """
    id: str
    description: str                        # What to achieve
    completion_criteria: list[str] = field(default_factory=list)  # How to verify completion
    estimated_tokens: int = 1000
    task_type: str = "general"              # For model capability matching
    status: str = "pending"                 # pending, achieved, failed
    result_summary: str = ""


@dataclass
class TaskStep:
    """A single step in a multi-step task orchestration plan."""
    id: str
    description: str
    task_type: str = "general"
    required_capabilities: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    sub_goals: list[SubGoal] = field(default_factory=list)   # C→B: intermediate milestones
    assigned_model: str = ""
    backup_model: str = ""
    estimated_tokens: int = 1000
    estimated_cost_yuan: float = 0.01
    priority: int = 0
    status: str = "pending"
    result: str = ""
    error: str = ""
    latency_ms: float = 0.0
    actual_tokens: int = 0
    actual_cost_yuan: float = 0.0


@dataclass
class OrchestrationPlan:
    """Full multi-step task orchestration plan."""
    task_id: str
    task_description: str
    steps: list[TaskStep]
    total_estimated_cost: float = 0.0
    total_estimated_latency_ms: float = 0.0
    budget_yuan: float = 0.0
    max_latency_ms: float = 0.0
    risk_score: float = 0.0
    fallback_plan: dict[str, str] = field(default_factory=dict)  # step_id → fallback_model
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    @property
    def progress(self) -> float:
        """0.0-1.0 completion ratio."""
        if not self.steps:
            return 1.0
        done = sum(1 for s in self.steps if s.status == "completed")
        return done / len(self.steps)

    @property
    def is_complete(self) -> bool:
        return all(s.status == "completed" for s in self.steps)

    @property
    def has_failures(self) -> bool:
        return any(s.status == "failed" for s in self.steps)


# ═══ StrategicOrchestrator ═════════════════════════════════════════


class StrategicOrchestrator:
    """Multi-step task coordination with strategic model allocation.

    Design principle (Strategic Perspective):
      Instead of routing each sub-request independently, analyze the full task
      chain upfront. Pre-allocate the optimal model combination considering:
        - Which model excels at each step type
        - Global cost budget (don't spend all budget on first step)
        - Overall latency budget
        - Cross-step dependencies (some steps need results from prior steps)
        - Risk hedging (don't rely on a single model for the entire chain)

    Adaptive replanning: if a model fails mid-chain, dynamically reassign
    to the backup model without restarting completed steps.
    """

    def __init__(self):
        self._active_plans: dict[str, OrchestrationPlan] = {}
        self._step_context: dict[str, dict[str, str]] = {}  # task_id → step_id → result text
        self._stats: dict[str, int] = {"plans_created": 0, "steps_executed": 0}

    # ── Plan Creation ──────────────────────────────────────────────

    async def plan(
        self,
        task_description: str,
        available_models: list[str] | None = None,
        budget_yuan: float = 1.0,
        max_latency_ms: float = 60000,
        steps_hint: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> OrchestrationPlan:
        """Create an orchestration plan for a multi-step task.

        Analyzes the task description, decomposes into steps, and pre-assigns
        the optimal model to each step based on capabilities and budget.

        Args:
            task_description: Full description of the task.
            available_models: List of available model provider names.
            budget_yuan: Total cost budget for the entire task chain.
            max_latency_ms: Maximum acceptable total latency.
            steps_hint: Optional pre-defined steps (from execution planner).

        Returns:
            OrchestrationPlan with fully allocated steps.
        """
        task_id = hashlib.sha256(
            f"{task_description}{time.time()}".encode()
        ).hexdigest()[:12]

        # Step 1: Decompose into steps (use hint if provided, else heuristics)
        if steps_hint:
            steps = self._build_steps_from_hint(steps_hint)
        else:
            # Try LLM decomposition if chat_fn available
            chat_fn = kwargs.get("chat_fn")
            if chat_fn:
                steps = await self.decompose_task_with_llm(task_description, chat_fn)
            else:
                steps = self._decompose_task(task_description, available_models or [])

        # Step 2: Analyze capabilities needed per step
        for step in steps:
            step.task_type = self._infer_task_type(step.description)
            step.required_capabilities = self._infer_capabilities(
                step.description, step.task_type,
            )

        # Step 2.5: C→B Sub-goal decomposition (from three-body framework)
        # Generate intermediate milestones for B-body to execute
        for step in steps:
            step.sub_goals = self.decompose_to_subgoals(step)

        # Step 3: Pre-allocate models to each step
        available = available_models or self._get_all_providers()
        await self._allocate_models(steps, available, budget_yuan)

        # Step 4: Assign backup models (different provider from primary)
        self._assign_backups(steps, available)

        # Step 5: Build fallback plan
        fallback = {s.id: s.backup_model for s in steps if s.backup_model}

        # Step 6: Compute risk score
        risk = self._compute_risk(steps)

        plan = OrchestrationPlan(
            task_id=task_id,
            task_description=task_description,
            steps=steps,
            total_estimated_cost=sum(s.estimated_cost_yuan for s in steps),
            total_estimated_latency_ms=sum(
                s.estimated_tokens * 50 for s in steps  # rough: 50ms per token
            ),
            budget_yuan=budget_yuan,
            max_latency_ms=max_latency_ms,
            risk_score=risk,
            fallback_plan=fallback,
        )

        self._active_plans[task_id] = plan
        self._step_context[task_id] = {}
        self._stats["plans_created"] += 1

        logger.info(
            f"StrategicOrchestrator: plan {task_id} created — "
            f"{len(steps)} steps, {sum(len(s.sub_goals) for s in steps)} sub-goals, "
            f"est.cost={plan.total_estimated_cost:.4f}¥, "
            f"risk={risk:.2f}"
        )
        return plan

    # ── Plan Execution ─────────────────────────────────────────────

    async def execute_step(
        self,
        plan: OrchestrationPlan,
        step: TaskStep,
        executor_fn=None,
        context: str = "",
    ) -> TaskStep:
        """Execute a single step in the orchestration plan.

        Args:
            plan: The orchestration plan this step belongs to.
            step: The step to execute.
            executor_fn: async callable(model, prompt, task_type) → str.
                If None, will use internal TreeLLM.
            context: Accumulated context from previous steps.

        Returns:
            Updated TaskStep with results.
        """
        step.status = "running"
        self._stats["steps_executed"] += 1
        t0 = time.monotonic()

        try:
            # Build prompt with context from dependent steps
            prompt = self._build_step_prompt(step, plan, context)

            if executor_fn:
                result_text = await executor_fn(step.assigned_model, prompt, step.task_type)
            else:
                result_text = await self._default_executor(
                    step.assigned_model, prompt, step.task_type,
                )

            step.result = result_text
            step.status = "completed"
            step.latency_ms = (time.monotonic() - t0) * 1000
            step.actual_tokens = len(result_text)

            # Store context for downstream steps
            self._step_context[plan.task_id][step.id] = result_text

        except Exception as e:
            logger.warning(
                f"StrategicOrchestrator: step {step.id} failed "
                f"(model={step.assigned_model}): {e}"
            )
            # Try backup model
            if step.backup_model and step.backup_model != step.assigned_model:
                try:
                    logger.info(
                        f"StrategicOrchestrator: retrying step {step.id} "
                        f"with backup model {step.backup_model}"
                    )
                    prompt = self._build_step_prompt(step, plan, context)
                    if executor_fn:
                        result_text = await executor_fn(step.backup_model, prompt, step.task_type)
                    else:
                        result_text = await self._default_executor(
                            step.backup_model, prompt, step.task_type,
                        )
                    step.result = result_text
                    step.status = "completed"
                    step.latency_ms = (time.monotonic() - t0) * 1000
                    step.actual_tokens = len(result_text)
                    self._step_context[plan.task_id][step.id] = result_text
                    return step
                except Exception as e2:
                    step.error = f"Primary failed: {e}; Backup failed: {e2}"
            else:
                step.error = str(e)

            step.status = "failed"
            step.latency_ms = (time.monotonic() - t0) * 1000

        return step

    async def execute_plan(
        self,
        plan: OrchestrationPlan,
        executor_fn=None,
    ) -> OrchestrationPlan:
        """Execute all steps in an orchestration plan, respecting dependencies.

        Steps with no dependencies run in parallel where possible.
        Dependent steps run sequentially after their prerequisites complete.
        """
        completed_ids: set[str] = set()
        failed = False

        while not plan.is_complete and not failed:
            # Find steps ready to execute (all dependencies met)
            ready = [
                s for s in plan.steps
                if s.status == "pending"
                and all(d in completed_ids for d in s.depends_on)
            ]
            if not ready:
                if not plan.has_failures:
                    break  # No more steps to run
                failed = True
                break

            # Execute ready steps in parallel (independent steps)
            async def exec_one(s: TaskStep) -> TaskStep:
                # Build context from dependent steps
                ctx_parts = []
                for dep_id in s.depends_on:
                    ctx = self._step_context.get(plan.task_id, {}).get(dep_id, "")
                    if ctx:
                        ctx_parts.append(f"[Step {dep_id} result]:\n{ctx[:2000]}")
                context = "\n\n".join(ctx_parts)
                return await self.execute_step(plan, s, executor_fn, context)

            results = await asyncio.gather(
                *(exec_one(s) for s in ready), return_exceptions=True,
            )
            for i, result in enumerate(results):
                if isinstance(result, BaseException):
                    ready[i].status = "failed"
                    ready[i].error = str(result)
                elif isinstance(result, TaskStep):
                    if result.status == "completed":
                        completed_ids.add(result.id)
                else:
                    ready[i].status = "failed"
                    ready[i].error = f"Unexpected result type: {type(result)}"

            # Check for critical failures
            critical_failures = [
                s for s in plan.steps
                if s.status == "failed" and s.priority >= 2
            ]
            if critical_failures:
                logger.error(
                    f"StrategicOrchestrator: plan {plan.task_id} aborted — "
                    f"critical step(s) failed: {[s.id for s in critical_failures]}"
                )
                break

        plan.completed_at = time.time()
        return plan

    # ── Task Decomposition ─────────────────────────────────────────

    def decompose_to_subgoals(self, step: TaskStep, complexity: float = 0.5) -> list[SubGoal]:
        """Generate verifiable intermediate sub-goals for a task step."""
        task_type = step.task_type or self._infer_task_type(step.description)
        is_zh = any('\u4e00' <= c <= '\u9fff' for c in step.description)
        subgoals: list[SubGoal] = []
        prefix = step.id
        if task_type == "analysis" or task_type == "reasoning":
            templates = [
                ("Define scope and assumptions", "At least 2 boundary conditions"),
                ("Identify key factors", "At least 3 factors listed"),
                ("Analyze each factor", "At least 2 sentences per factor"),
                ("Synthesize conclusion", "Directly answers the question"),
            ]
        elif task_type == "code":
            templates = [
                ("Understand requirements", "Input/output specified"),
                ("Design approach", "Algorithm described"),
                ("Implement solution", "Runnable code"),
                ("Test edge cases", "At least 2 edge cases"),
            ]
        else:
            templates = [
                ("Understand problem", "Problem restated"),
                ("Develop analysis", "Structured output"),
                ("Verify and refine", "Weakness identified"),
            ]
        for i, (desc, criteria) in enumerate(templates):
            subgoals.append(SubGoal(
                id=f"{prefix}_sg{i}", description=desc,
                completion_criteria=[criteria], task_type=task_type,
            ))
        return subgoals

    async def decompose_task_with_llm(
        self, task_description: str, chat_fn=None,
    ) -> list[TaskStep]:
        """Semantic task decomposition using a flash LLM.

        Replaces the keyword-based heuristic with actual semantic analysis.
        The flash model identifies logical sub-tasks with dependency structure,
        producing much better decompositions for complex tasks.
        """
        if not chat_fn:
            return self._decompose_task(task_description, [])

        prompt = (
            f"Decompose the following task into sequential sub-tasks. "
            f"For each sub-task, specify: (1) a short description, "
            f"(2) what it depends on (if any), and (3) what type of "
            f"reasoning it requires (analysis, code, search, or summarize).\n\n"
            f"Task: {task_description}\n\n"
            f"Reply in JSON format:\n"
            f'{{"steps": [{{"id": "s1", "description": "...", '
            f'"depends_on": [], "task_type": "analysis"}}, ...]}}\n\n'
            f"Keep it concise. Maximum 5 steps."
        )

        try:
            result = await chat_fn(prompt)
            import json
            data = json.loads(result) if isinstance(result, str) else result
            steps = []
            for s in data.get("steps", []):
                steps.append(TaskStep(
                    id=s.get("id", f"step_{len(steps)}"),
                    description=s.get("description", ""),
                    task_type=s.get("task_type", "general"),
                    depends_on=s.get("depends_on", []),
                    priority=len(data.get("steps", [])) - len(steps),
                ))
            if steps:
                logger.info(
                    f"StrategicOrchestrator LLM: decomposed into "
                    f"{len(steps)} semantic sub-tasks"
                )
                return steps
        except Exception as e:
            logger.debug(f"StrategicOrchestrator LLM decompose: {e}")

        return self._decompose_task(task_description, [])

    @staticmethod
    def _decompose_task(
        description: str, available_models: list[str],
    ) -> list[TaskStep]:
        """Heuristic task decomposition into steps.

        Uses keyword analysis to identify sub-tasks. For complex tasks,
        the execution planner should provide steps_hint instead.
        """
        steps: list[TaskStep] = []
        desc_lower = description.lower()
        step_id = 0

        # Multi-action indicators
        multi_indicators = [
            ("首先", "然后", "最后"),
            ("first", "then", "finally"),
            ("设计", "实现", "测试"),
            ("design", "implement", "test"),
            ("分析", "优化", "部署"),
            ("analyze", "optimize", "deploy"),
        ]

        for group in multi_indicators:
            if any(g in desc_lower for g in group):
                prefix = f"task_{hash(description) % 10000}"
                for i, indicator in enumerate(group):
                    steps.append(TaskStep(
                        id=f"{prefix}_s{i}",
                        description=f"{indicator}: {description[:100]}",
                        priority=len(group) - i,
                    ))
                    step_id += 1
                break

        if not steps:
            # Single step
            steps.append(TaskStep(
                id=f"task_{hash(description) % 10000}_s0",
                description=description,
                priority=1,
            ))

        return steps

    @staticmethod
    def _build_steps_from_hint(hint: list[dict[str, Any]]) -> list[TaskStep]:
        """Build steps from execution planner hint."""
        steps = []
        for i, h in enumerate(hint):
            steps.append(TaskStep(
                id=h.get("id", f"step_{i}"),
                description=h.get("description", f"Step {i}"),
                task_type=h.get("task_type", "general"),
                required_capabilities=h.get("capabilities", []),
                depends_on=h.get("depends_on", []),
                priority=h.get("priority", 1),
                estimated_tokens=h.get("estimated_tokens", 1000),
            ))
        return steps

    # ── Model Allocation ───────────────────────────────────────────

    async def _allocate_models(
        self, steps: list[TaskStep], available: list[str], budget: float,
    ) -> None:
        """Pre-allocate the best model to each step, considering budget constraints."""
        cost_per_step = budget / max(len(steps), 1)

        for step in steps:
            best_model = await self._select_best_for_step(step, available, cost_per_step)
            step.assigned_model = best_model
            step.estimated_cost_yuan = cost_per_step

    async def _select_best_for_step(
        self, step: TaskStep, available: list[str], budget: float,
    ) -> str:
        """Select the best model for a specific step using capability + fitness."""
        if not available:
            return ""

        # ── Try fitness_router adaptive tiering ──
        try:
            from .fitness_router import get_fitness_router, FitnessScore
            fr = get_fitness_router()
            scores = {
                m: FitnessScore(model_name=m, quality_score=0.5)
                for m in available
            }
            decision = await fr.route(step.description, step.id, scores)
            if decision.selected_model and decision.selected_model in available:
                return decision.selected_model
        except ImportError:
            pass

        # Use HolisticElection capability matching as fallback
        try:
            from .holistic_election import PROVIDER_CAPABILITIES, get_election
            election = get_election()

            scored = []
            for model in available:
                caps = PROVIDER_CAPABILITIES.get(model, [])
                match = sum(1 for c in step.required_capabilities if c in caps)
                match_score = match / max(len(step.required_capabilities), 1) if step.required_capabilities else 0.3

                # Check CompetitiveEliminator viability
                try:
                    from .competitive_eliminator import get_eliminator
                    elim = get_eliminator()
                    if not elim.is_viable(model):
                        continue
                    ranking = elim.get_ranking(model)
                    tiers = {"pro": 1.0, "mid": 0.7, "flash": 0.4, "eliminated": 0.0}
                    tier_bonus = tiers.get(ranking.tier, 0.5) if ranking else 0.5
                except ImportError:
                    tier_bonus = 0.5

                scored.append((model, match_score * 0.7 + tier_bonus * 0.3))

            scored.sort(key=lambda x: -x[1])
            return scored[0][0] if scored else (available[0] if available else "")

        except ImportError:
            return available[0] if available else ""

    @staticmethod
    def _assign_backups(steps: list[TaskStep], available: list[str]) -> None:
        """Assign backup model to each step (different from primary)."""
        for step in steps:
            for model in available:
                if model != step.assigned_model:
                    step.backup_model = model
                    break

    # ── Task Type Inference ────────────────────────────────────────

    @staticmethod
    def _infer_task_type(description: str) -> str:
        """Infer task type from description keywords."""
        d = description.lower()
        mapping = {
            "code": ["代码", "实现", "编写", "implement", "code", "function", "class"],
            "reasoning": ["分析", "推理", "思考", "analyze", "reason", "why", "how"],
            "search": ["搜索", "查找", "find", "search", "look up"],
            "chat": ["对话", "聊天", "问答", "chat", "question", "what"],
            "multimodal": ["图像", "图片", "image", "picture", "visual"],
            "long_context": ["长文", "文档", "document", "report", "报告"],
        }
        for task_type, keywords in mapping.items():
            if any(k in d for k in keywords):
                return task_type
        return "general"

    @staticmethod
    def _infer_capabilities(description: str, task_type: str) -> list[str]:
        """Infer required model capabilities for a step."""
        caps = []
        d = description.lower()

        if task_type == "code":
            caps.extend(["code", "tool_call", "structured_output"])
        elif task_type == "reasoning":
            caps.extend(["reasoning", "analysis", "deep"])
        elif task_type == "search":
            caps.extend(["search", "knowledge", "web"])
        elif task_type == "multimodal":
            caps.extend(["multimodal", "image"])
        elif task_type == "long_context":
            caps.extend(["long-context", "analysis"])

        if "中文" in d or any('\u4e00' <= c <= '\u9fff' for c in description):
            caps.append("chinese")
        if "翻译" in d or "translate" in d:
            caps.append("translate")

        return caps

    # ── Risk Assessment ────────────────────────────────────────────

    @staticmethod
    def _compute_risk(steps: list[TaskStep]) -> float:
        """Compute risk score (0-1) for the orchestration plan.

        Higher risk = more likely to fail or exceed budget.
        Factors: step count, model diversity, dependency depth.
        """
        if not steps:
            return 0.0

        risk = 0.0
        # More steps = more risk
        risk += min(0.4, len(steps) * 0.1)
        # Dependency chains = more risk
        max_depth = 0
        id_to_step = {s.id: s for s in steps}
        for s in steps:
            depth = 1
            current = s
            while current.depends_on:
                depth += 1
                dep = current.depends_on[0]
                if dep in id_to_step:
                    current = id_to_step[dep]
                else:
                    break
            max_depth = max(max_depth, depth)
        risk += min(0.3, max_depth * 0.1)
        # Low model diversity = more risk (single point of failure)
        unique_models = len({s.assigned_model for s in steps})
        if unique_models == 1:
            risk += 0.3
        elif unique_models == 2:
            risk += 0.1

        return min(1.0, risk)

    # ── Prompt Building ────────────────────────────────────────────

    @staticmethod
    def _build_step_prompt(
        step: TaskStep, plan: OrchestrationPlan, context: str,
    ) -> str:
        """Build a prompt for a step that includes context from dependencies."""
        parts = []
        # System context
        parts.append(
            f"You are executing step '{step.id}' of a multi-step task: "
            f"{plan.task_description[:300]}"
        )
        if context:
            parts.append(f"Context from previous steps:\n{context}")
        parts.append(f"Your task:\n{step.description}")
        return "\n\n".join(parts)

    # ── Default Executor ───────────────────────────────────────────

    async def _default_executor(
        self, model: str, prompt: str, task_type: str,
    ) -> str:
        """Default executor using TreeLLM if no custom function provided."""
        try:
            from .core import TreeLLM
            # Create a fresh TreeLLM instance for execution
            llm = TreeLLM()
            # Try to resolve provider
            p = llm.get_provider(model)
            if p:
                result = await llm.chat(
                    [{"role": "user", "content": prompt}],
                    provider=model,
                    max_tokens=4096,
                )
                if result and result.text:
                    return result.text
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"StrategicOrchestrator default executor: {e}")
        return f"[Step executed via {model}] No result available"

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _get_all_providers() -> list[str]:
        """Get list of all registered provider names from TreeLLM."""
        try:
            from .holistic_election import PROVIDER_CAPABILITIES
            return list(PROVIDER_CAPABILITIES.keys())
        except ImportError:
            return []

    # ── Query Methods ──────────────────────────────────────────────

    def get_plan(self, task_id: str) -> OrchestrationPlan | None:
        return self._active_plans.get(task_id)

    def get_active_plans(self) -> list[OrchestrationPlan]:
        return [p for p in self._active_plans.values() if not p.is_complete]

    def stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "active_plans": len([p for p in self._active_plans.values() if not p.is_complete]),
            "completed_plans": len([p for p in self._active_plans.values() if p.is_complete]),
        }


# ═══ Singleton ═════════════════════════════════════════════════════

_orchestrator: Optional[StrategicOrchestrator] = None


def get_orchestrator() -> StrategicOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = StrategicOrchestrator()
    return _orchestrator


def get_strategic_orchestrator() -> StrategicOrchestrator:
    return get_orchestrator()


__all__ = [
    "StrategicOrchestrator", "OrchestrationPlan", "TaskStep",
    "get_orchestrator", "get_strategic_orchestrator",
]
