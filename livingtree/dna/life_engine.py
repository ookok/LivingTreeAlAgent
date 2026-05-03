"""LifeEngine — Central nervous system of the digital life form.

Orchestrates the 6-stage pipeline with integrated cognitive evolution:
  perceive → cognize → plan → execute(→quality_check) → reflect → evolve

Every stage participates in a single coherent system. No bolt-on modules.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from loguru import logger
from pydantic import BaseModel, Field

from .genome import Genome
from .consciousness import Consciousness
from .safety import SafetyGuard


class LifeStage(BaseModel):
    stage: str
    started_at: str
    completed_at: str | None = None
    status: str = "pending"
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0


class LifeContext(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_input: str | None = None
    collected_materials: list[dict[str, Any]] = Field(default_factory=list)
    intent: str | None = None
    retrieved_knowledge: list[dict[str, Any]] = Field(default_factory=list)
    plan: list[dict[str, Any]] = Field(default_factory=list)
    execution_results: list[dict[str, Any]] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)
    quality_reports: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LifeEngine:
    """Self-contained digital life cycle engine with embedded cognitive evolution.

    Usage:
        world = LivingWorld(config)            # single system-wide context
        engine = LifeEngine(world)
        result = await engine.run("帮我生成环评报告")
    """

    def __init__(self, world: "LivingWorld"):
        self.world = world
        self.genome = world.genome
        self.consciousness = world.consciousness
        self.safety = world.safety
        self.stages: list[LifeStage] = []
        self.is_running = False
        self.elite_registry: list[dict] = []

    # ── Main pipeline ──

    async def run(self, user_input: str, **kwargs) -> LifeContext:
        ctx = LifeContext(user_input=user_input, **kwargs)
        self.is_running = True
        self.stages.clear()

        try:
            await self._stage("perceive", self._perceive, ctx)
            await self._stage("cognize", self._cognize, ctx)
            await self._stage("plan", self._plan, ctx)
            await self._stage("execute", self._execute, ctx)
            await self._stage("reflect", self._reflect, ctx)
            await self._stage("evolve", self._evolve, ctx)
            logger.info(f"Cycle {ctx.session_id} complete")
            return ctx
        except Exception as e:
            logger.error(f"Cycle {ctx.session_id} failed: {e}")
            raise
        finally:
            self.is_running = False

    # ── Stage 1: Perceive ──

    async def _perceive(self, ctx: LifeContext) -> None:
        # Scan for prompt injection before processing
        scan = self.safety.scan_prompt(ctx.user_input)
        if not scan.get("safe", True):
            ctx.metadata["prompt_injection"] = scan
            logger.warning(f"[perceive] Prompt injection detected: {scan['count']} patterns")

        thoughts = []
        async for token in self.consciousness.stream_of_thought(ctx.user_input):
            thoughts.append(token)
        ctx.collected_materials.append({
            "source": "consciousness",
            "stream": "".join(thoughts),
        })
        mc = self.world.material_collector
        if mc:
            try:
                materials = await mc.collect_from_web(ctx.user_input)
                ctx.collected_materials.extend(materials)
            except Exception as e:
                logger.debug(f"Material collection: {e}")

    # ── Stage 2: Cognize ──

    async def _cognize(self, ctx: LifeContext) -> None:
        ctx.intent = await self.consciousness.chain_of_thought(
            f"Analyze intent and required knowledge: {ctx.user_input}"
        )
        ctx.metadata["cognition"] = ctx.intent

        kb = self.world.knowledge_base
        if kb:
            # Context budget: cap knowledge injection by query complexity
            budget = self._context_budget(ctx.user_input)
            try:
                results = kb.search(ctx.user_input, top_k=budget)
                if results:
                    ctx.retrieved_knowledge.extend(results)
                    ctx.metadata["knowledge_budget"] = budget
                    ctx.metadata["knowledge_count"] = len(results)
            except Exception as e:
                logger.debug(f"Knowledge search: {e}")

        questions = await self.consciousness.self_questioning(ctx.user_input)
        ctx.metadata["self_questions"] = questions

    @staticmethod
    def _context_budget(user_input: str) -> int:
        """Compute how much knowledge to inject based on query complexity.

        Simple queries get minimal context (save tokens).
        Complex queries get more knowledge (better accuracy).
        """
        length = len(user_input)
        complex_keywords = ["分析", "评估", "预测", "比较", "报告", "方案", "风险",
                            "analyze", "evaluate", "predict", "compare", "report"]
        complexity_score = min(1.0, length / 500) + sum(
            0.3 for kw in complex_keywords if kw.lower() in user_input.lower()
        )
        if complexity_score <= 0.3:
            return 2
        if complexity_score <= 0.7:
            return 5
        if complexity_score <= 1.2:
            return 10
        return 15

    # ── Stage 3: Plan ──

    async def _plan(self, ctx: LifeContext) -> None:
        # Check for existing checkpoint to resume from
        checkpoint = self.world.checkpoint
        if checkpoint:
            state, remaining = await checkpoint.resume(ctx.session_id)
            if state and remaining:
                ctx.plan = remaining
                ctx.execution_results = state.execution_results
                ctx.reflections = state.reflections
                ctx.metadata["resumed_from_checkpoint"] = True
                ctx.metadata["completed_before_resume"] = len(state.completed_steps)
                logger.info(f"[plan] Resumed from checkpoint: {state.completed_steps} steps done, {len(remaining)} remaining")
                return

        hypotheses = await self.consciousness.hypothesis_generation(
            f"Given intent: {ctx.intent}, what are possible approaches?"
        )
        ctx.metadata["hypotheses"] = hypotheses

        planner = self.world.task_planner
        if planner:
            steps = await self._invoke(planner.decompose_task,
                goal=ctx.user_input,
                context={"intent": ctx.intent, "knowledge": ctx.retrieved_knowledge},
            )
            if steps:
                ctx.plan = steps
        if not ctx.plan:
            ctx.plan = [{"step": 1, "action": "direct", "description": ctx.user_input}]

    # ── Stage 4: Execute (with integrated quality check) ──

    async def _execute(self, ctx: LifeContext) -> None:
        logger.debug(f"[execute] {len(ctx.plan)} steps")
        orchestrator = self.world.orchestrator
        hitl = self.world.hitl
        cost = self.world.cost_aware
        checkpoint = self.world.checkpoint
        completed = len(ctx.execution_results)

        for idx, step in enumerate(ctx.plan):
            if idx < completed:
                continue

            action = step.get("action", "unknown")
            if not self.safety.check_action(action, step.get("description", "")):
                ctx.execution_results.append({"step": step, "status": "denied"})
                continue

            # ── Cost-aware model routing ──
            # Auto-detect if deep reasoning is needed
            needs_deep = step.get("needs_deep_reasoning", False) or any(
                kw in action for kw in ["analyze", "predict", "assess", "evaluate", "review"]
            )
            step_name = step.get("name", "unknown")
            est_tokens = 3000 if needs_deep else 800

            if cost and needs_deep and not cost.can_use("deepseek/deepseek-v4-pro", est_tokens):
                step["degraded_model"] = True
                logger.info(f"[cost] Degraded '{step_name}' to flash")

            # ── HITL approval gate ──
            if step.get("needs_approval", False) and hitl:
                ctx.metadata.setdefault("hitl_requests", 0)
                ctx.metadata["hitl_requests"] += 1
                question = step.get("approval_question", f"Approve: {step_name}?")
                approved = await hitl.request_approval(step_name, question,
                    context={"step": step, "session": ctx.session_id})
                if not approved:
                    ctx.execution_results.append({"step": step, "status": "denied_by_human"})
                    logger.info(f"[hitl] Step '{step_name}' denied by human")
                    continue

            # ── Execute ──
            if orchestrator:
                result = await self._invoke(orchestrator.assign_task,
                    task=step,
                    agents=self._list_agents(),
                )
                if result:
                    qc = self.world.quality_checker
                    if qc and isinstance(result, dict) and result.get("result"):
                        try:
                            qr = await qc.check(str(result["result"]))
                            ctx.quality_reports.append({
                                "step": step_name, "passed": qr.passed,
                                "score": qr.final_score, "issues": qr.total_issues,
                            })
                            if not qr.passed:
                                result["status"] = "quality_failed"
                        except Exception:
                            pass
                    ctx.execution_results.append(result)

            # ── Checkpoint after each step ──
            if checkpoint:
                try:
                    from ..execution.checkpoint import CheckpointState
                    cs = CheckpointState(
                        session_id=ctx.session_id,
                        task_goal=ctx.user_input or "",
                        plan=ctx.plan,
                        completed_steps=list(range(idx + 1)),
                        current_step=idx + 1,
                        execution_results=ctx.execution_results,
                        reflections=ctx.reflections,
                    )
                    await checkpoint.save(ctx.session_id, cs)
                except Exception as e:
                    logger.debug(f"Checkpoint save: {e}")

            # ── Record token usage ──
            if cost:
                cost.record("deepseek/deepseek-v4-pro" if needs_deep else "deepseek/deepseek-v4-flash", est_tokens)
                st = cost.status()
                if not cost._degraded and st.usage_pct >= cost.degradation_threshold:
                    cost.degrade()

    # ── Stage 5: Reflect ──

    async def _reflect(self, ctx: LifeContext) -> None:
        total = len(ctx.plan)
        ok = sum(1 for r in ctx.execution_results if r.get("status") in ("completed", "ok"))
        fail = total - ok
        rate = ok / max(total, 1)
        ctx.metadata["success_rate"] = rate

        reflection = f"{total} steps: {ok} ok, {fail} failed"
        if fail:
            errors = [r.get("error", "?") for r in ctx.execution_results if r.get("error")]
            reflection += f". Errors: {errors}"
        ctx.reflections.append(reflection)
        ctx.metadata["lessons"] = ctx.reflections

        # Quality summary
        if ctx.quality_reports:
            qr_summary = f"Quality: {sum(1 for q in ctx.quality_reports if q['passed'])}/{len(ctx.quality_reports)} passed"
            ctx.reflections.append(qr_summary)

    # ── Stage 6: Evolve (with embedded thinking evolution) ──

    async def _evolve(self, ctx: LifeContext) -> None:
        rate = ctx.metadata.get("success_rate", 0)
        ok = rate >= 0.5
        elite = rate >= 0.8

        # Genome mutation
        if ctx.reflections:
            genes = []
            if elite:
                genes.append("elite")
            genes.append("success" if ok else "failure")
            self.genome.add_mutation(
                description=f"{ctx.session_id}: {ctx.reflections[-1][:200]}",
                source="life_engine",
                affected_genes=genes,
                success=ok,
            )

        # Elite preservation
        if elite:
            self.elite_registry.append({
                "session": ctx.session_id,
                "rate": rate,
                "intent": ctx.intent,
                "reflections": ctx.reflections,
            })
            if len(self.elite_registry) > 20:
                self.elite_registry = self.elite_registry[-20:]
            logger.info(f"[evolve] Elite preserved: {ctx.session_id} (rate={rate:.2f})")

        # Cell evolution + thinking mutation
        registry = self.world.cell_registry
        if registry:
            cells = registry.list_cells() if hasattr(registry, 'list_cells') else []
            for cell in cells[:3]:
                try:
                    if not ok and hasattr(cell, 'evolve'):
                        await self._invoke(cell.evolve, ctx.reflections)
                    # Thinking mutation: perturb cell capabilities
                    if hasattr(cell, 'capabilities'):
                        self._mutate_capabilities(cell, rate)
                except Exception as e:
                    logger.debug(f"Cell evolve: {e}")

        # Crossover elites when we have enough
        if len(self.elite_registry) >= 3:
            await self._crossover_elites(ctx)

        # Self-heal on failure
        if not ok and self.world.self_healer:
            try:
                await self.world.self_healer.run_all_checks()
            except Exception as e:
                logger.debug(f"Heal check: {e}")

        # Cleanup checkpoint on success, keep on failure for resume
        cp = self.world.checkpoint
        if cp:
            if ok:
                await cp.delete(ctx.session_id)
            cost = self.world.cost_aware
            if cost and cost._degraded:
                cost.restore()

    # ── Embedded thinking evolution ──

    def _mutate_capabilities(self, cell: Any, fitness: float) -> None:
        """Randomly mutate a cell's capability list."""
        if random.random() > 0.3:
            return
        caps = getattr(cell, 'capabilities', [])
        if caps:
            idx = random.randint(0, len(caps) - 1)
            cap = caps[idx]
            if hasattr(cap, 'confidence'):
                cap.confidence = min(1.0, max(0.1, cap.confidence + random.uniform(-0.1, 0.15)))
            elif hasattr(cap, 'description'):
                cap.description = f"{cap.description} (evolved gen {self.genome.generation})"

    async def _crossover_elites(self, ctx: LifeContext) -> None:
        """Create a new approach by synthesizing recent elite sessions."""
        if len(self.elite_registry) < 3:
            return
        recent = self.elite_registry[-3:]
        synthesis = (
            f"Synthesizing elite patterns: "
            + " | ".join(e.get("intent", "")[:40] for e in recent)
        )
        ctx.reflections.append(synthesis)
        logger.debug(f"[evolve] Crossover: {synthesis[:100]}")

    # ── Helpers ──

    async def _stage(self, name: str, fn, ctx: LifeContext) -> None:
        s = LifeStage(stage=name, started_at=datetime.now(timezone.utc).isoformat())
        s.status = "running"
        self.stages.append(s)
        t0 = asyncio.get_event_loop().time()
        try:
            r = fn(ctx)
            if asyncio.iscoroutine(r):
                await r
            s.status = "completed"
            s.result = "ok"
        except Exception as e:
            s.status = "failed"
            s.error = str(e)
            raise
        finally:
            s.completed_at = datetime.now(timezone.utc).isoformat()
            s.duration_ms = (asyncio.get_event_loop().time() - t0) * 1000

    def _list_agents(self) -> list:
        agents = []
        registry = self.world.cell_registry
        if registry and hasattr(registry, 'list_cells'):
            try:
                agents.extend(registry.list_cells())
            except Exception:
                pass
        return agents

    @staticmethod
    async def _invoke(fn, *args, **kwargs) -> Any:
        try:
            r = fn(*args, **kwargs)
            if asyncio.iscoroutine(r):
                r = await r
            return r
        except Exception as e:
            logger.debug(f"Invoke failed: {e}")
            return None

    def status(self) -> dict:
        return {
            "running": self.is_running,
            "generation": self.genome.generation,
            "completed": sum(1 for s in self.stages if s.status == "completed"),
            "failed": sum(1 for s in self.stages if s.status == "failed"),
            "mutations": len(self.genome.mutation_history),
            "elites": len(self.elite_registry),
        }
