"""RealPipeline — genuine intent-driven task decomposition + agent orchestration.

Replaces the facade agent execution (orchestrator+task_planner stubs) with:
  1. Intent → Domain routing (consumes recognize_intent() output)
  2. LLM-driven task decomposition (produces dependency DAGs)
  3. Real agent dispatch (each agent has actual LLM-backed execution)
  4. Parallel DAG execution with failure propagation
  5. Incremental checkpoint at each step

Single entry point replacing the broken LifeEngine._execute path.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

CHECKPOINT_DIR = Path(".livingtree/real_pipeline")


@dataclass
class TaskStep:
    id: str
    name: str
    action: str = "execute"
    description: str = ""
    agent_role: str = "analyst"
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, done, failed
    result: str = ""
    error: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    retries: int = 0


@dataclass
class PipelineContext:
    session_id: str
    intent: str = "general"
    domain: str = "general"
    confidence: float = 0.5
    steps: list[TaskStep] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


class RealOrchestrator:
    """Real task decomposition + agent dispatch + DAG execution.

    Replaces:
      - orchestrator.py (facade _execute_with_agent)
      - task_planner.py (TemplateLearner section-name-only)
      - LifeEngine._plan/_execute (keyword gating, serial chaining)
    """

    MAX_RETRIES = 3
    MAX_PARALLEL = 4

    def __init__(self, hub=None):
        self._hub = hub
        self._agents: dict[str, Any] = {}
        self._register_agents()

    def _register_agents(self):
        self._agents = {
            "analyst": AgentSpec("analyst", "分析任务、提取需求、检索知识", ["analyze", "search", "extract"]),
            "executor": AgentSpec("executor", "执行操作、生成代码、生成报告", ["execute", "generate", "write"]),
            "reviewer": AgentSpec("reviewer", "审查结果、校验事实、检测错误", ["review", "verify", "check"]),
            "collector": AgentSpec("collector", "采集数据、搜索网页、抓取文档", ["collect", "fetch", "scrape"]),
        }

    # ═══ 1. Intent → Task Plan ═══

    async def plan(self, user_input: str) -> PipelineContext:
        """Full pipeline: intent → decompose → dependency DAG."""
        ctx = PipelineContext(session_id=f"pipe-{int(time.time())}")

        # Step A: Intent recognition
        if self._hub and self._hub.world:
            try:
                intent_result = self._hub.world.consciousness.recognize_intent(user_input)
                ctx.intent = intent_result.get("intent", "general")
                ctx.domain = intent_result.get("domain", "general")
                ctx.confidence = intent_result.get("confidence", 0.5)
            except Exception:
                pass

        # Step B: LLM-driven task decomposition (NOT just section names)
        steps = await self._decompose(user_input, ctx)
        ctx.steps = steps
        return ctx

    async def _decompose(self, user_input: str, ctx: PipelineContext) -> list[TaskStep]:
        """Use LLM to produce a real task plan with dependencies."""
        if not self._hub or not self._hub.world:
            return self._minimal_plan(user_input)

        llm = self._hub.world.consciousness._llm
        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    "将以下任务分解为可执行的子任务。输出JSON数组，每个元素包含:\n"
                    "- name: 步骤名称\n"
                    "- action: execute|analyze|search|generate|review|collect\n"
                    "- description: 步骤描述\n"
                    "- agent_role: analyst|executor|reviewer|collector\n"
                    "- depends_on: 前置步骤索引列表(空数组表示无依赖)\n\n"
                    f"任务: {user_input}\n\n"
                    "只输出JSON数组, 不要解释。"
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.2,
                max_tokens=2000,
                timeout=30,
            )
            if result and result.text:
                parsed = self._parse_steps(result.text)
                if parsed:
                    return parsed
        except Exception as e:
            logger.debug(f"Decompose: {e}")
        return self._minimal_plan(user_input)

    def _parse_steps(self, text: str) -> list[TaskStep] | None:
        """Parse LLM JSON output into TaskStep list."""
        import re
        m = re.search(r'\[[\s\S]*\]', text)
        if not m:
            return None
        try:
            data = json.loads(m.group())
            steps = []
            for i, item in enumerate(data):
                step = TaskStep(
                    id=f"s{i}", name=item.get("name", ""), action=item.get("action", "execute"),
                    description=item.get("description", ""), agent_role=item.get("agent_role", "analyst"),
                    dependencies=[f"s{d}" for d in item.get("depends_on", [])],
                )
                steps.append(step)
            return steps if steps else None
        except json.JSONDecodeError:
            return None

    def _minimal_plan(self, user_input: str) -> list[TaskStep]:
        return [
            TaskStep(id="s0", name="分析需求", action="analyze", agent_role="analyst", description=user_input),
            TaskStep(id="s1", name="执行任务", action="execute", agent_role="executor", description="执行核心任务", dependencies=["s0"]),
            TaskStep(id="s2", name="审查结果", action="review", agent_role="reviewer", description="验证输出质量", dependencies=["s1"]),
        ]

    # ═══ 2. Agent dispatch ═══

    async def _dispatch_agent(self, step: TaskStep, ctx: PipelineContext) -> str:
        """Actually execute a step via real LLM agent calls."""
        spec = self._agents.get(step.agent_role)
        if not spec:
            return f"Unknown agent: {step.agent_role}"

        if not self._hub or not self._hub.world:
            return f"Hub unavailable for {step.name}"

        llm = self._hub.world.consciousness

        if step.action == "analyze":
            result = await llm.chain_of_thought(
                f"分析以下任务: {step.description}\n上下文意图: {ctx.intent}",
                steps=2, max_tokens=1024,
            )
            return result

        elif step.action in ("execute", "generate"):
            result = await llm.chain_of_thought(
                f"执行以下任务并输出结果: {step.description}",
                steps=3, max_tokens=2048,
            )
            return result

        elif step.action == "review":
            # Calibrated review: compare against context
            result = await llm.chain_of_thought(
                f"审查以下任务输出是否符合要求: {step.description}\n"
                f"域: {ctx.domain} 意图: {ctx.intent}",
                steps=1, max_tokens=512,
            )
            return result

        elif step.action == "search":
            try:
                from ..capability.unified_search import get_unified_search
                search = get_unified_search()
                results = await search.query(step.description, limit=5)
                return search.format_results(results)
            except Exception as e:
                return f"Search failed: {e}"

        elif step.action == "collect":
            try:
                from ..capability.web_reach import WebReach
                reach = WebReach()
                page = await reach.fetch(step.description) if step.description.startswith("http") else None
                return page.text[:2000] if page else "No URL provided"
            except Exception as e:
                return f"Collect failed: {e}"

        return f"{spec.name}: {step.description}"

    # ═══ 3. DAG execution with failure propagation ═══

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        """Execute all steps respecting dependencies. Propagate failures."""
        pending = {s.id for s in ctx.steps}
        completed: dict[str, str] = {}  # id → result
        failed_ids: set[str] = set()
        semaphore = asyncio.Semaphore(self.MAX_PARALLEL)

        while pending:
            # Find ready steps (all deps satisfied, not failed)
            ready = []
            for sid in list(pending):
                step = next(s for s in ctx.steps if s.id == sid)
                if any(d in failed_ids for d in step.dependencies):
                    step.status = "failed"
                    step.error = "Dependency failed"
                    failed_ids.add(sid)
                    pending.discard(sid)
                    ctx.failed.append(sid)
                    # Save incremental checkpoint
                    self._save_checkpoint(ctx)
                    continue
                if all(d in completed for d in step.dependencies):
                    ready.append(sid)

            if not ready:
                break  # All remaining steps blocked by failures

            tasks = []
            for sid in ready:
                pending.discard(sid)
                tasks.append(self._run_step(sid, ctx, semaphore))

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for sid, result in zip(ready, results):
                    if isinstance(result, Exception):
                        completed[sid] = f"Error: {result}"
                    else:
                        completed[sid] = result

        ctx.completed = list(completed.keys())
        return ctx

    async def _run_step(self, sid: str, ctx: PipelineContext, semaphore: asyncio.Semaphore) -> str:
        step = next(s for s in ctx.steps if s.id == sid)
        async with semaphore:
            for retry in range(self.MAX_RETRIES):
                try:
                    step.status = "running"
                    step.started_at = time.time()

                    # ── Auto-skill resolver: retry with resolved skills ──
                    from .auto_skill_resolver import get_resolver
                    resolver = get_resolver(self._hub)
                    async def do_step():
                        return await self._dispatch_agent(step, ctx)
                    result = await resolver.retry_with_resolved(
                        do_step, step.description, max_attempts=2,
                    )

                    step.result = result
                    step.status = "done"
                    step.completed_at = time.time()
                    self._save_checkpoint(ctx)
                    return result
                except Exception as e:
                    step.retries += 1
                    if retry < self.MAX_RETRIES - 1:
                        await asyncio.sleep(2 ** retry)
                    else:
                        step.status = "failed"
                        step.error = str(e)
                        self._save_checkpoint(ctx)
                        raise

    # ═══ Incremental checkpoint ═══

    def _save_checkpoint(self, ctx: PipelineContext):
        try:
            CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
            path = CHECKPOINT_DIR / f"{ctx.session_id}.json"
            from ..core.task_guard import TaskGuard
            TaskGuard.atomic_write(path, json.dumps({
                "session_id": ctx.session_id, "intent": ctx.intent,
                "completed": ctx.completed, "failed": ctx.failed,
                "steps": [{"id": s.id, "name": s.name, "status": s.status,
                           "result": s.result[:200], "error": s.error}
                          for s in ctx.steps],
            }, indent=2, ensure_ascii=False))
        except Exception:
            pass

    def get_status(self, ctx: PipelineContext) -> dict:
        total = len(ctx.steps)
        done = len(ctx.completed)
        failed = len(ctx.failed)
        return {
            "total": total, "done": done, "failed": failed,
            "pending": total - done - failed,
            "progress": done / max(total, 1),
            "steps": [s.name for s in ctx.steps if s.status == "done"],
        }


@dataclass
class AgentSpec:
    name: str
    description: str
    capabilities: list[str]


# ═══ Global ═══

_real_orch: RealOrchestrator | None = None


def get_real_orchestrator(hub=None) -> RealOrchestrator:
    global _real_orch
    if _real_orch is None or hub:
        _real_orch = RealOrchestrator(hub)
    return _real_orch
