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

        # ── Clarification: detect missing info before planning ──
        from ..execution.clarifier import Clarifier
        clarifier = Clarifier(
            consciousness=self.consciousness,
            kb=self.world.knowledge_base,
            distillation=self.world.distillation,
            expert_config=self.world.expert_config,
        )
        clarifications = await clarifier.analyze(ctx.user_input)
        ctx.metadata.setdefault("clarifications", [])
        ctx.metadata.setdefault("clarified_answers", {})

        hitl = self.world.hitl
        for cq in clarifications[:3]:  # Max 3 questions per session
            if hitl:
                formatted = cq.format_for_display()
                approved = await hitl.request_approval(
                    task_name="clarification",
                    question=formatted,
                    context={"choices": cq.options, "mode": cq.mode},
                    timeout=120.0,
                )
                if approved:
                    cq.answer = "confirmed"
                    clarifier.record(cq)
                    ctx.metadata["clarified_answers"][cq.id] = cq.answer
                    ctx.metadata["clarifications"].append({
                        "question": cq.question, "answer": cq.answer, "mode": cq.mode,
                    })
            else:
                # No HITL: auto-fill first option if available
                if cq.options:
                    cq.answer = cq.options[0]
                else:
                    cq.answer = "generic"
                clarifier.record(cq)
                ctx.metadata["clarified_answers"][cq.id] = cq.answer

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

        # Shared cache for cross-step data transfer
        ctx.metadata.setdefault("shared_cache", {})

        # Use DAG executor for parallel execution
        from ..execution.dag_executor import DAGExecutor, add_dependencies
        plan_with_deps = add_dependencies(list(ctx.plan))
        executor = DAGExecutor(max_parallel=5)

        async def execute_one(step: dict, ctx_lc: Any) -> dict:
            step_name = step.get("name", "unknown")
            action = step.get("action", "unknown")

            if not self.safety.check_action(action, step.get("description", "")):
                return {"step": step, "status": "denied"}

            # Cost-aware routing
            needs_deep = step.get("needs_deep_reasoning", False) or any(
                kw in action for kw in ["analyze", "predict", "assess", "evaluate", "review"])
            est_tokens = 3000 if needs_deep else 800

            if cost and needs_deep and not cost.can_use("deepseek/deepseek-v4-pro", est_tokens):
                step["degraded_model"] = True

            # HITL approval gate
            if step.get("needs_approval", False) and hitl:
                question = step.get("approval_question", f"Approve: {step_name}?")
                approved = await hitl.request_approval(step_name, question,
                    context={"step": step, "session": ctx_lc.session_id})
                if not approved:
                    return {"step": step, "status": "denied_by_human"}

            # ── Strategy retry ──
            strategies = [
                lambda: self._invoke(orchestrator.assign_task, task=step, agents=self._list_agents()),
                lambda: self._retry_with_pro(step),
                lambda: self._retry_with_kb(step, ctx_lc),
            ]
            result = None
            last_error = ""
            for strat in strategies:
                try:
                    result = await strat()
                    if result and result.get("status") != "failed":
                        break
                except Exception as e:
                    last_error = str(e)
                    continue

            if not result:
                return {"step": step, "status": "failed", "error": last_error}

            # Quality check
            qc = self.world.quality_checker
            if qc and isinstance(result, dict) and result.get("result"):
                try:
                    qr = await qc.check(str(result["result"]))
                    ctx_lc.metadata.setdefault("quality_reports", []).append({
                        "step": step_name, "passed": qr.passed, "score": qr.final_score,
                    })
                except Exception:
                    pass

            # Share result to cache
            ctx_lc.metadata["shared_cache"][step_name] = result
            return result

        results = await executor.execute(plan_with_deps, execute_one, ctx)
        ctx.execution_results = results

        # Checkpoint after all steps
        if checkpoint and results:
            try:
                from ..execution.checkpoint import CheckpointState
                cs = CheckpointState(
                    session_id=ctx.session_id, task_goal=ctx.user_input or "",
                    plan=ctx.plan, completed_steps=list(range(len(ctx.plan))),
                    current_step=len(ctx.plan),
                    execution_results=ctx.execution_results, reflections=ctx.reflections,
                )
                await checkpoint.save(ctx.session_id, cs)
            except Exception:
                pass

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

        # Precipitation: distill successful session insight into KnowledgeBase
        if ok and ctx.intent and self.world.knowledge_base and self.world.distillation:
            await self._precipitate_knowledge(ctx)

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

    async def _retry_with_pro(self, step: dict) -> dict:
        """Retry failed step using pro model for deeper reasoning."""
        step["needs_deep_reasoning"] = True
        step["_retry_strategy"] = "pro_model"
        return await self._invoke(
            self.world.orchestrator.assign_task,
            task=step, agents=self._list_agents(),
        )

    async def _retry_with_kb(self, step: dict, ctx: LifeContext) -> dict:
        """Retry failed step by first querying knowledge base for relevant info."""
        kb = self.world.knowledge_base
        if kb:
            try:
                query = step.get("name", step.get("description", ""))
                results = kb.search(query, top_k=3)
                if results:
                    # Inject KB knowledge into the step context
                    step["kb_context"] = [r.content[:500] for r in results]
                    step["_retry_strategy"] = "kb_injection"
                    return await self._invoke(
                        self.world.orchestrator.assign_task,
                        task=step, agents=self._list_agents(),
                    )
            except Exception:
                pass
        return {"step": step, "status": "failed", "error": "all retries exhausted"}

    async def process_large_document(self, content: str, chunk_size: int = 8000) -> list[str]:
        """Chunk large documents and summarize each chunk via LLM."""
        chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
        if len(chunks) <= 1:
            return chunks

        logger.info(f"Processing large doc: {len(chunks)} chunks of {chunk_size} chars")
        summaries = []
        for i, chunk in enumerate(chunks[:10]):  # Max 10 chunks per pass
            try:
                summary = await self.consciousness.chain_of_thought(
                    f"Summarize this section in 3-5 key points (section {i+1}/{len(chunks)}):\n\n{chunk[:5000]}",
                    steps=2, max_tokens=1024,
                )
                summaries.append(summary)
            except Exception:
                summaries.append(chunk[:500])
        return summaries
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

    async def _precipitate_knowledge(self, ctx: LifeContext) -> None:
        """Distill successful session insight into KnowledgeBase for future recall."""
        try:
            prompt = (
                f"The following task was successfully completed. Extract the key insight (1-2 sentences) "
                f"that would help a future agent handle similar tasks better.\n\n"
                f"Task: {ctx.user_input}\nResult: {ctx.plan[-1] if ctx.plan else 'completed'}\n"
                f"Reflection: {ctx.reflections[-1] if ctx.reflections else 'ok'}"
            )
            insight = await self.world.distillation.query_expert(
                prompt, self.world.expert_config,
            )
            if insight and len(insight) > 20:
                from ..knowledge.knowledge_base import Document
                doc = Document(
                    title=f"insight:{ctx.session_id}",
                    content=insight,
                    domain="general",
                    source="precipitation",
                    metadata={"session": ctx.session_id, "success_rate": ctx.metadata.get("success_rate", 0)},
                )
                self.world.knowledge_base.add_knowledge(doc)
                logger.debug(f"[evolve] Knowledge precipitated: {insight[:80]}...")
        except Exception:
            pass

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
