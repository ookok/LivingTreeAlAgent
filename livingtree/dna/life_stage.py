"""Stage pipeline methods extracted from LifeEngine as a mixin.

Contains the 7-stage cognitive pipeline:
  Perceive → Cognize → Grow Ontology → Plan → Simulate → Execute → Reflect

Extracted from life_engine.py (previously ~2000 lines) to reduce God Object size.
"""

from __future__ import annotations

import re
import time
from typing import Any

from loguru import logger

from .life_context import LifeContext


class StageMixin:
    """LiteLLM pipeline 7-stage execution methods."""

    # ── Stage 1: Perceive ──

    async def _perceive(self, ctx: LifeContext) -> None:
        # Digital twin: observe user behavior
        twin = getattr(getattr(self.world, 'daemon', None), 'twin', None)
        if twin:
            twin.observe(ctx.user_input, auto_pro_triggered=(
                len(ctx.user_input) > 200 or any(kw in ctx.user_input for kw in
                ["分析","推理","预测","评估","优化","报告","方案","风险"])))

        # Scan for prompt injection before processing
        scan = self.safety.scan_prompt(ctx.user_input)
        if not scan.get("safe", True):
            ctx.metadata["prompt_injection"] = scan
            logger.warning(f"[perceive] Prompt injection detected: {scan['count']} patterns")

        thoughts = []
        async for token in self.consciousness.stream_of_thought(ctx.user_input):
            thoughts.append(token)
        thought_text = "".join(thoughts)

        # Thought harvesting — scavenge escaped tool calls from reasoning
        try:
            from .thought_harvest import ThoughtHarvester
            harvester = ThoughtHarvester()
            harvest = harvester.harvest(thought_text)
            if harvest.found:
                ctx.metadata["harvested_tool_calls"] = harvest.tool_calls
                logger.debug(f"[perceive] Harvested {len(harvest.tool_calls)} tool calls from thinking")
        except Exception:
            pass

        ctx.collected_materials.append({
            "source": "consciousness",
            "stream": thought_text,
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
        mem_context = ctx.metadata.get("struct_mem_context", "")

        # Latent Pre-Reasoning (arXiv:2604.02029):
        # Fast vector-space analysis before expensive explicit CoT
        try:
            from .latent_reasoner import get_latent_reasoner
            reasoner = get_latent_reasoner()
            latent_ctx = reasoner.pre_reason(ctx.user_input, ctx.metadata)
            ctx.metadata["latent_context"] = {
                "category": latent_ctx.task_category,
                "complexity": latent_ctx.estimated_complexity,
                "strategy": latent_ctx.recommended_strategy.value,
                "budget_factor": latent_ctx.budget_factor,
            }

            if reasoner.should_skip_cot(latent_ctx):
                ctx.intent = f"simple_{latent_ctx.task_category}"
                ctx.metadata["cognition"] = ctx.intent
                return
        except Exception:
            pass
        cog_prompt = f"Analyze intent and required knowledge: {ctx.user_input}"

        # Cache-Safe Prompt tracking: log KV cache hit likelihood
        try:
            from ..treellm.cache_safe_prompt import get_cache_safe_prompt
            csp = get_cache_safe_prompt()
            assembly = csp.build(
                system_prompt="Analyze user intent for cognitive processing",
                retrieved_context="",
                user_query=ctx.user_input,
            )
            ctx.metadata["cache_hit_likelihood"] = assembly.cache_hit_likelihood
            ctx.metadata["stable_prefix_tokens"] = assembly.stable_prefix_tokens
        except Exception:
            pass

        # Adaptively inject domain terminology from glossary (mattpocock/skills)
        glossary = getattr(self.world, 'context_glossary', None)
        if glossary and ctx.user_input:
            try:
                domain_context = glossary.get_context_for_task(ctx.user_input, max_terms=5)
                if domain_context and len(domain_context) > 20:
                    cog_prompt = f"{cog_prompt}\n\nRelevant domain context:\n{domain_context[:2000]}"
            except Exception:
                pass

        if mem_context:
            # Cone-Precision Prompt Assembly (#3): arrange content in cone layout
            try:
                from .cone_assembler import get_cone_assembler
                from ..treellm.hifloat8_provider import estimate_speedup
                ctx_len = len(ctx.user_input) // 2
                speedup = estimate_speedup(ctx_len)
                assembler = get_cone_assembler(max_tokens=8192)
                assembler.set_speedup(speedup)
                # Core = memory context, supporting = domain context
                assembled = assembler.assemble(
                    core=[{"text": mem_context, "source": "struct_mem"}],
                    supporting=[{"text": domain_context[:2000], "source": "glossary"}] if domain_context else [],
                )
                cog_prompt = f"Analyze intent: {ctx.user_input}\n\n{assembled}"
            except Exception:
                cog_prompt = f"{cog_prompt}\n\nRelevant memory context:\n{mem_context[:4000]}"

        ctx.intent = await self.consciousness.chain_of_thought(cog_prompt)
        ctx.metadata["cognition"] = ctx.intent

        # Interleaved Visual CoT (arXiv:2601.19834):
        # Insert visual world model step between verbal reasoning steps
        try:
            from .visual_world import (
                get_visual_router, get_visual_generator,
                WorldModelCapability, ModalityPreference,
            )
            router = get_visual_router()
            preference = router.classify(ctx.user_input, ctx.metadata)
            ctx.metadata["modality_preference"] = preference.value

            if preference in (ModalityPreference.VISUAL, ModalityPreference.INTERLEAVED):
                generator = get_visual_generator(self.consciousness)
                if router.needs_simulation(ctx.user_input):
                    vwm = await generator.generate(
                        ctx.user_input, WorldModelCapability.SIMULATION, ctx.metadata
                    )
                elif router.needs_reconstruction(ctx.user_input):
                    vwm = await generator.generate(
                        ctx.user_input, WorldModelCapability.RECONSTRUCTION, ctx.metadata
                    )
                else:
                    vwm = await generator.generate(
                        ctx.user_input, WorldModelCapability.SIMULATION, ctx.metadata
                    )

                if vwm:
                    ctx.metadata["visual_world_model"] = vwm.to_prompt_block()
                    # Inject visual model into cognition prompt for richer reasoning
                    cog_prompt = f"{cog_prompt}\n\n{vwm.to_prompt_block()}"
        except Exception:
            pass

        kb = self.world.knowledge_base
        if kb:
            # Context budget: cap knowledge injection by query complexity
            budget = self._context_budget(ctx.user_input)
            try:
                if hasattr(kb, 'multi_source_retrieve_sync'):
                    # Hindsight-style: multi-source RRF fusion retrieval
                    fusion_result = kb.multi_source_retrieve_sync(
                        ctx.user_input, top_k=budget)
                    results = [sr.document for sr in fusion_result.results if sr.document]
                    ctx.metadata["fusion_stats"] = fusion_result.fusion_stats
                    ctx.metadata["knowledge_source"] = "rrf_fusion"
                else:
                    results = kb.search(ctx.user_input, top_k=budget * 2)
                # Token-budget truncation: fit within ~6K chars
                results = self._token_budget_truncate(results, max_chars=6000)
                if results:
                    ctx.retrieved_knowledge.extend(results)
                    ctx.metadata["knowledge_budget"] = budget
                    ctx.metadata["knowledge_count"] = len(results)
            except Exception as e:
                logger.debug(f"Knowledge search: {e}")

        questions = await self.consciousness.self_questioning(ctx.user_input)
        ctx.metadata["self_questions"] = questions

    # ── Stage 2.5: Ontology Growth ──

    async def _grow_ontology(self, ctx: LifeContext) -> None:
        """Extract new concepts from cognition output and register in the
        unified entity registry + knowledge graph + glossary.

        Uses lightweight heuristics (keyword + pattern matching) to detect
        plausible new domain concepts, then checks for duplicates before
        submission. Avoids LLM re-invocation — operates on text already
        produced by the cognition stage.
        """
        text = (ctx.intent or "") + " " + (ctx.user_input or "")
        if not text.strip():
            return

        # Extract candidate noun phrases: capitalized words, quoted terms,
        # and technical-looking sequences.
        candidates: set[str] = set()
        # Capitalized multi-word phrases (likely proper nouns or concepts)
        for m in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text):
            candidates.add(m.group(1).strip())
        # Single capitalized words (but not sentence-starting ones)
        for m in re.finditer(r'(?<!\A\.\s)\b([A-Z][a-z]{3,})\b', text):
            candidates.add(m.group(1))
        # Chinese technical terms (2-6 char sequences with technical affixes)
        for m in re.finditer(r'[\u4e00-\u9fff]{2,6}(?:模型|引擎|系统|框架|算法|数据|网络|学习|优化|评估|检测|生成|分析|推理|分类|聚类|预测|识别)', text):
            candidates.add(m.group(0))

        if not candidates:
            return

        # Deduplicate against existing ontology layers.
        registry = None
        glossary = None
        kg = None
        try:
            from ..core.entity_registry import get_entity_registry
            registry = get_entity_registry()
        except Exception:
            pass
        try:
            from ..knowledge.context_glossary import GLOSSARY
            glossary = GLOSSARY
        except Exception:
            pass
        try:
            kg = self.world.knowledge_base
        except Exception:
            pass

        new_terms: list[str] = []
        for c in candidates:
            name_lower = c.lower()
            # Check if already registered
            if registry:
                found = False
                for eid in registry._entities:
                    e = registry._entities.get(eid)
                    if e and e.name.lower() == name_lower:
                        found = True
                        break
                if found:
                    continue
            if glossary:
                existing_terms = glossary.list_terms()
                if any(t.lower() == name_lower for t in existing_terms):
                    continue
            new_terms.append(c)

        if not new_terms:
            ctx.metadata["ontology_growth"] = "no new concepts"
            return

        # Register new terms across layers
        _t = time.time()
        registered: list[str] = []
        for term in new_terms[:5]:  # limit to 5 per cycle to avoid noise
            rc = None
            if registry:
                try:
                    eid = registry.register(
                        name=term,
                        namespace="general",
                        entity_type="concept",
                        source="llm_cognize",
                        metadata={"extracted_from": "cognize_stage", "timestamp": _t},
                    )
                    rc = eid
                except Exception:
                    pass
            if glossary:
                try:
                    glossary.register(
                        term=term,
                        category="ai_concept",
                        definition=f"Extracted from cognition: {term}",
                        priority=0.5,
                    )
                except Exception:
                    pass
            if kg and rc:
                try:
                    if hasattr(kg, 'add_document'):
                        kg.add_document(
                            title=term,
                            content=f"Cognized concept: {term}",
                            tags=["ontology_growth", "cognize"],
                        )
                except Exception:
                    pass
            registered.append(term)

        if registered:
            ctx.metadata["ontology_growth"] = f"registered {len(registered)} concepts: {', '.join(registered)}"
            try:
                logger.info(f"[ontogrow] Registered {len(registered)} new concepts: {registered}")
            except Exception:
                pass
        else:
            ctx.metadata["ontology_growth"] = "registration failed"

    @staticmethod
    def _context_budget(user_input: str) -> int:
        """Compute how much knowledge to inject based on query complexity.

        Simple queries get minimal context (save tokens).
        Complex queries get more knowledge (better accuracy).

        Hindsight-inspired: returns token-budget-aware count, not hard top-K.
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

    @staticmethod
    def _token_budget_truncate(docs: list, max_chars: int = 6000) -> list:
        """Hindsight-style token-budget truncation instead of hard top-K.

        Truncates document list to fit within max_chars, keeping documents
        with highest relevance first. Documents beyond budget are dropped.
        """
        if not docs:
            return docs
        result = []
        total_chars = 0
        for doc in docs:
            content = getattr(doc, 'content', '') if hasattr(doc, 'content') else str(doc)
            chunk = len(content) if isinstance(content, str) else 200
            if total_chars + chunk > max_chars and result:
                break
            result.append(doc)
            total_chars += chunk
        return result

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

        # Skill catalog: enrich planning context with relevant capabilities
        sc = getattr(self.world, 'skill_catalog', None)
        skill_hints = []
        if sc and ctx.intent:
            try:
                suggestions = sc.suggest_skills(ctx.intent, limit=5)
                skill_hints = [s.get("name", s) if isinstance(s, dict) else s for s in suggestions]
                ctx.metadata["plan_skill_hints"] = skill_hints
            except Exception:
                pass

        planner = self.world.task_planner
        if planner:
            planning_context = {"intent": ctx.intent, "knowledge": ctx.retrieved_knowledge}
            if skill_hints:
                planning_context["recommended_skills"] = skill_hints
            steps = await self._invoke(planner.decompose_task,
                goal=ctx.user_input,
                context=planning_context,
            )
            if steps:
                ctx.plan = steps
                # ── AgenticQwen-inspired behavior tree: enrich linear plan with fallback branches ──
                try:
                    from livingtree.core.behavior_tree import linear_plan_to_tree
                    step_descs = [s.get("description", s.get("action", str(s))) for s in steps[:8]]
                    fallback = "fallback: ask user for clarification or try alternative approach"
                    ctx.behavior_tree = linear_plan_to_tree(
                        step_descs,
                        fallback_hint=fallback,
                        use_model_for_routing=len(step_descs) > 3,  # Route complex plans
                    )
                    ctx.metadata["plan_mode"] = "behavior_tree"
                    logger.info(f"[plan] Behavior tree built: {len(step_descs)} primary steps + fallback")
                except Exception as e:
                    logger.debug(f"[plan] Behavior tree skipped: {e}")
        if not ctx.plan:
            ctx.plan = [{"step": 1, "action": "direct", "description": ctx.user_input}]

        # Harness registry: snapshot affected files before execution for rollback safety
        hr = getattr(self.world, 'harness_registry', None)
        if hr and ctx.plan:
            try:
                files_to_watch = set()
                for step in ctx.plan:
                    path = step.get("target_file") or step.get("file") or step.get("path")
                    if path:
                        files_to_watch.add(path)
                for f in files_to_watch:
                    hr.snapshot(f)
                if files_to_watch:
                    ctx.metadata["harness_snapshots"] = list(files_to_watch)
            except Exception:
                pass

    # ── Stage 4: Simulate (foresight) ──
    
    async def _simulate(self, ctx: LifeContext) -> None:
        """Foresight simulation stage — lightweight what-if before execution."""
        try:
            from ..treellm.foresight_gate import get_foresight_gate
            gate = get_foresight_gate()
            task_type = ctx.metadata.get("task_type", "general")
            risk = ctx.metadata.get("risk_level", "normal")
            history = ctx.metadata.get("past_queries", [])
            decision = gate.assess(ctx.user_input or "", task_type, history, risk)
            ctx.simulation_ran = decision.should_simulate
            ctx.simulation_decision = {
                "should_simulate": decision.should_simulate,
                "reason": decision.reason,
                "depth": decision.depth,
                "confidence": decision.confidence,
                "factors": decision.factors,
            }
            if decision.should_simulate:
                logger.info(f"Foresight: simulating at depth {decision.depth} — {decision.reason}")
                # Lightweight what-if: score top providers using embedding scorer
                try:
                    from ..treellm.embedding_scorer import get_embedding_scorer
                    scorer = get_embedding_scorer()
                    profiles = scorer._profiles[:8]  # top-8 for speed
                    what_if = scorer.score_and_filter(ctx.user_input or "", profiles, top_k=decision.depth + 1)
                    ctx.simulation_findings = {
                        "candidates": [(name, round(score, 3)) for name, score in what_if],
                        "top_pick": what_if[0][0] if what_if else "unknown",
                        "confidence_band": "high" if what_if and what_if[0][1] > 0.7 else "medium" if what_if and what_if[0][1] > 0.5 else "low",
                    }
                    ctx.metadata["simulation_insights"] = ctx.simulation_findings
                    logger.info(f"Foresight done: top pick={ctx.simulation_findings['top_pick']}, band={ctx.simulation_findings['confidence_band']}")
                except ImportError:
                    ctx.simulation_findings = {"error": "embedding_scorer unavailable"}
            else:
                logger.debug(f"Foresight skipped: {decision.reason}")
                ctx.simulation_findings = {"skipped": decision.reason}
        except ImportError:
            logger.debug("Foresight gate unavailable, skipping simulation")
            ctx.simulation_ran = False
        except Exception as e:
            logger.warning(f"Simulation stage error: {e}")
            ctx.simulation_ran = False

    # ── Stage 4: Execute (with integrated quality check) ──

    async def _execute(self, ctx: LifeContext) -> None:
        logger.debug(f"[execute] {len(ctx.plan)} steps")

        # Token Accountant: marginal benefit check before executing
        try:
            from ..api.token_accountant import get_token_accountant, AllocationLayer
            accountant = get_token_accountant()
            est_tokens = ctx.metadata.get("estimated_tokens", 5000)
            benefit = ctx.metadata.get("predicted_quality", 0.7)
            if not accountant.should_allocate(
                AllocationLayer.AGENT, "execute", est_tokens, benefit,
                session_id=getattr(ctx, 'stage_id', ''),
            ):
                logger.info(f"TokenAccountant: SKIP execution (benefit<cost)")
                ctx.execution_results = [{"status": "skipped", "reason": "marginal_benefit_insufficient"}]
                return
        except Exception:
            pass
        orchestrator = self.world.orchestrator
        hitl = self.world.hitl
        cost = self.world.cost_aware
        checkpoint = self.world.checkpoint
        completed = len(ctx.execution_results)

        # ── Economic Gate: 执行前经济审查 ──
        try:
            from ..economy.economic_engine import get_economic_orchestrator
            from ..execution.plan_validator import get_plan_validator, PlanStep
            eco = get_economic_orchestrator()
            task_id = getattr(ctx, 'stage_id', None) or f"task_{int(time.time())}"
            daily_cost = 0.0
            if cost:
                try:
                    s = cost.status()
                    daily_cost = s.cost_yuan
                except Exception:
                    pass
            decision = eco.evaluate(
                task_id=task_id,
                task_desc=ctx.user_input or ctx.intent or "",
                task_type=self._guess_task_type(ctx),
                estimated_tokens=ctx.metadata.get("estimated_tokens", 5000),
                complexity=self._guess_complexity(ctx),
                user_priority=ctx.metadata.get("user_priority", 0.5),
                predicted_quality=ctx.metadata.get("predicted_quality", 0.7),
                daily_spent_yuan=daily_cost,
            )
            if not decision.go:
                logger.warning(f"[execute] Economic gate rejected: {decision.suggestion}")
                ctx.execution_results.append({
                    "status": "rejected",
                    "reason": f"经济审查未通过: {decision.suggestion}",
                    "economic_decision": decision,
                })
                return
            ctx.metadata["economic_decision"] = decision
            ctx.metadata["selected_model"] = decision.selected_model

            # ── Record decision to ReasoningChain ──
            try:
                from .reasoning_chain import get_reasoning_chain
                rc = get_reasoning_chain()
                rc.decide(
                    domain="model_selection",
                    decision=decision.selected_model,
                    reasoning=f"Economic policy={decision.policy}, ROI={decision.roi.roi_estimate:.1f}x",
                    alternatives=["flash_model", "pro_model"],
                    confidence=decision.roi.roi_estimate / 10,
                    session_id=ctx.session_id or "",
                )
            except Exception:
                pass

            logger.info(f"[execute] Economic gate: GO | {decision.selected_model.split('/')[-1]} | ROI={decision.roi.roi_estimate:.1f}x")
        except Exception as e:
            logger.debug(f"[execute] Economic gate skipped: {e}")

        # ── Plan Validation: 执行前计划验证 ──
        try:
            validator = get_plan_validator(consciousness=self.consciousness)
            plan_id = getattr(ctx, 'stage_id', None) or f"plan_{int(time.time())}"
            vsteps = [
                PlanStep(
                    step_id=s.get("name", f"s{i}"),
                    tool=s.get("action", s.get("tool", "")),
                    description=s.get("description", ""),
                )
                for i, s in enumerate(ctx.plan[:20])]
            validation = await validator.validate(
                vsteps, domain=self._guess_domain(ctx), plan_id=plan_id)
            ctx.metadata["plan_validation"] = validation
            if validation.success_probability < 0.3:
                logger.warning(f"[execute] Plan validation low: {validation.success_probability:.0%}")
            else:
                logger.debug(f"[execute] Plan validation: {validation.success_probability:.0%}")
        except Exception as e:
            logger.debug(f"[execute] Plan validation skipped: {e}")

        # Shared cache for cross-step data transfer
        ctx.metadata.setdefault("shared_cache", {})

        # ── Unified Pipeline Routing (StarVLA Lego architecture) ──
        # Replaces old DAG vs ReAct dual-mode if/elif with auto-selection
        # across all 4+ execution modes via PipelineOrchestrator
        from ..execution.react_executor import (
            ExecutionMode, route_execution, ReactExecutor)
        from ..execution.unified_pipeline import get_pipeline_orchestrator

        fg = getattr(self.world, 'foresight_gate', None)
        task_str = ctx.user_input or ctx.intent or ""

        # Use unified orchestrator for mode selection (replaces old binary routing)
        pipeline_orch = get_pipeline_orchestrator()
        selected_mode = pipeline_orch.select(task_str, {
            "plan": ctx.plan, "tools": bool(self.world.orchestrator),
            "pipeline_mode": ctx.metadata.get("pipeline_mode"),
        })
        # Map unified mode to existing execution infrastructure
        if selected_mode in ("react",):
            mode_val = ExecutionMode.REACT
        elif selected_mode in ("orchestrated",):
            mode_val = ExecutionMode.DAG  # Fallback routing — orchestrated handled below
        else:
            mode_val = ExecutionMode.DAG
        ctx.metadata["execution_mode"] = selected_mode
        ctx.metadata["pipeline_available"] = pipeline_orch.list_pipelines()
        logger.info(f"[execute] Pipeline: {selected_mode} ({len(ctx.plan)} steps)")

        # ═══ Orchestrated Mode: Expert decomposition + parallel ReAct sub-agents ═══
        if selected_mode == "orchestrated":
            try:
                from ..dna.expert_role_manager import get_expert_role_manager
                from ..capability.sub_agent_dispatch import SubAgentDispatch

                erm = get_expert_role_manager()
                dispatch = SubAgentDispatch()

                # 1. Decompose into domain-specific sub-tasks
                sub_tasks = dispatch.decompose(ctx.user_input or task_str)
                logger.info(f"[orchestrated] Decomposed into {len(sub_tasks)} sub-tasks")

                # 2. For each sub-task, find matching expert and execute via ReAct
                all_results = []
                for st in sub_tasks:
                    st_desc = getattr(st, 'description', str(st))
                    # Infer domain from sub-task description
                    domain = self._guess_domain_from_text(st_desc)
                    experts = erm.filter(industry=domain, profession="")
                    expert_ctx = ""
                    if experts:
                        expert = experts[0]
                        expert_ctx = (
                            f"You are acting as {getattr(expert,'name','expert')} "
                            f"({getattr(expert,'profession','generalist')}). "
                            f"Context: {getattr(expert,'description','')[:200]}"
                        )

                    # Execute sub-task via ReAct
                    react = ReactExecutor(self.consciousness)
                    result = await react.run(
                        task=f"{expert_ctx}\nTask: {st_desc}",
                        context={"knowledge": ctx.retrieved_knowledge},
                    )
                    all_results.append({
                        "sub_task": st_desc[:200],
                        "success": result.success,
                        "steps": len(result.steps),
                        "answer": result.final_answer[:500] if result.final_answer else "",
                    })

                # 3. Synthesize results
                synth_task = (
                    f"Synthesize these {len(all_results)} sub-results into a unified answer. "
                    f"Original task: {ctx.user_input or task_str}\n\n"
                    + "\n".join(
                        f"[{i+1}] {r['sub_task']}\nResult: {r['answer']}"
                        for i, r in enumerate(all_results)
                    )
                )
                synth_react = ReactExecutor(self.consciousness)
                synth_result = await synth_react.run(task=synth_task)

                ctx.execution_results = [
                    {"step": {"name": f"orchestrated-{i}", "action": "react"},
                     "status": "completed" if r["success"] else "failed",
                     "result": r["answer"]}
                    for i, r in enumerate(all_results, 1)
                ]
                if synth_result.final_answer:
                    ctx.execution_results.append({
                        "step": {"name": "synthesis", "action": "synthesize"},
                        "status": "completed",
                        "result": synth_result.final_answer,
                    })
                ctx.metadata["orchestrated_sub_tasks"] = len(sub_tasks)
                ctx.metadata["react_success"] = synth_result.success
                return  # Orchestrated done
            except Exception as e:
                logger.warning(f"[orchestrated] Failed, falling back to ReAct: {e}")
                # Fall through to ReAct

        # ── Inquiry Engine routing: research-mode tasks → structured inquiry ──
        if self._is_research_task(ctx):
            try:
                from ..dna.inquiry_engine import get_inquiry_engine
                inquiry = get_inquiry_engine()
                task_desc = ctx.user_input or ctx.intent or ""
                domain = self._guess_domain(ctx)
                inquiry.start_inquiry(
                    task=task_desc, domain=domain, counterparty_role="analyst",
                )
                ctx.metadata["inquiry_routed"] = True
                logger.info(f"[execute] InquiryMode: {task_desc[:80]}")
            except Exception as e:
                logger.debug(f"[execute] Inquiry routing skipped: {e}")

        if mode_val == ExecutionMode.REACT:
            # ── ReAct: serial Think-Act-Observe loop ──
            # (preserved from original — now routed via PipelineOrchestrator)
            react = ReactExecutor(self.consciousness)

            # Build tool registry from available world capabilities
            tools: dict[str, Any] = {}
            if orchestrator:
                async def _assign(task_input: str) -> dict:
                    step = {"action": "execute", "description": task_input, "name": "react_step"}
                    return await self._invoke(orchestrator.assign_task, task=step, agents=self._list_agents())
                tools["execute"] = _assign

            kb = getattr(self.world, 'knowledge_base', None)
            if kb:
                async def _search_kb(query: str) -> list:
                    return kb.search(query) if hasattr(kb, 'search') else []
                tools["search_knowledge"] = _search_kb

            trajectory = await react.run(
                task=ctx.user_input or ctx.intent or "execute plan",
                tools=tools,
                context={"knowledge": ctx.retrieved_knowledge, "plan": ctx.plan},
            )

            # Convert ReAct trajectory to execution results format
            ctx.execution_results = [
                {"step": {"name": f"react-s{i}", "action": s.action},
                 "status": "completed" if not s.error else "failed",
                 "result": s.observation, "error": s.error,
                 "confidence": s.confidence}
                for i, s in enumerate(trajectory.steps, 1)
            ]
            if trajectory.final_answer:
                ctx.execution_results.append({
                    "step": {"name": "final_answer", "action": "final_answer"},
                    "status": "completed", "result": trajectory.final_answer,
                })
            ctx.metadata["react_trajectory"] = trajectory
            ctx.metadata["react_success"] = trajectory.success

            # ── Auto-memory writeback: persist ReAct experience ──
            try:
                from ..core.session_memory import AgentMemory
                mem = AgentMemory()
                summary = (
                    f"Task: {ctx.user_input or ctx.intent}\n"
                    f"Steps: {len(trajectory.steps)}, Success: {trajectory.success}\n"
                    f"Final: {trajectory.final_answer[:300] if trajectory.final_answer else 'N/A'}"
                )
                await mem.remember(content=summary)
                logger.debug(f"[execute] Memory writeback: {len(summary)} chars")
            except Exception as e:
                logger.debug(f"[execute] Memory writeback skipped: {e}")

            # ── Auto-bind to StructMemory for future recall ──
            struct_mem = getattr(self.world, 'struct_memory', None)
            if struct_mem and ctx.user_input:
                try:
                    assistant_msg = trajectory.final_answer or (
                        f"Executed {len(trajectory.steps)} steps, success={trajectory.success}")
                    msgs = [
                        {"role": "user", "content": ctx.user_input},
                        {"role": "assistant", "content": assistant_msg},
                    ]
                    await struct_mem.bind_events(ctx.session_id, msgs)
                    logger.debug(f"[execute] StructMemory bind: session={ctx.session_id}")
                except Exception as e:
                    logger.debug(f"[execute] StructMemory bind skipped: {e}")

            # Reflexion: extract lessons and inject into evolution
            if trajectory.success and getattr(self.world, 'evolution_store', None):
                try:
                    lessons = trajectory.extract_lessons()
                    if lessons:
                        self.world.evolution_store.extract_lessons(
                            ctx.session_id,
                            {"success": trajectory.success, "lessons": lessons,
                             "iterations": len(trajectory.steps)},
                        )
                except Exception:
                    pass

            return  # ReAct done — skip DAG path below

        # ── DAG: parallel batch execution (existing path) ──
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

            # ── Behavior tree fallback: if tree exists, add fallback branch as last resort ──
            bt = getattr(ctx_lc, 'behavior_tree', None)
            if bt:
                async def _bt_fallback():
                    from livingtree.core.behavior_tree import TreeContext
                    bt_ctx = TreeContext(
                        user_input=ctx_lc.user_input,
                        metadata={"plan": ctx_lc.plan, "step": step},
                        history=ctx_lc.metadata.get("clarifications", []),
                    )
                    status = await bt.tick(bt_ctx)
                    if status.value == "success":
                        return {"status": "completed", "result": bt_ctx.results, "bt_fallback": True}
                    return {"status": "failed", "error": bt_ctx.errors[-1] if bt_ctx.errors else "all branches failed"}
                strategies.append(_bt_fallback)

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

            # Change Manifest: record file edits as falsifiable contracts (AHE Pattern 1)
            cm = getattr(self.world, 'change_manifest', None)
            if cm and isinstance(result, dict) and result.get("status") in ("completed", "ok"):
                try:
                    file_path = step.get("target_file") or step.get("file") or result.get("file")
                    description = step.get("description", "") or result.get("result", "")
                    if file_path:
                        cm.record(file_path, description[:500], metadata={
                            "step": step_name, "session": ctx_lc.session_id, "intent": ctx_lc.intent,
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

        # ── Fitness Tracking: 记录执行轨迹到适应度景观 ──
        try:
            from ..execution.fitness_landscape import get_fitness_landscape
            fitness = get_fitness_landscape()
            tools_used = [
                r.get("action", r.get("tool", ""))
                for r in ctx.execution_results if r.get("status") in ("completed", "ok")]
            total_tokens = ctx.metadata.get("estimated_tokens", 0)
            total_ms = (time.time() - ctx.metadata.get("cycle_start", time.time())) * 1000
            fitness.record(
                trajectory_id=getattr(ctx, 'stage_id', None) or f"task_{int(time.time())}",
                tool_sequence=tools_used[:10],
                total_tokens=int(total_tokens),
                total_ms=int(total_ms),
                success=rate > 0.5,
                safety_violations=ctx.metadata.get("safety_violations", 0),
                summary=ctx.user_input or ctx.intent or "",
            )
        except Exception:
            pass

        # ── Skill Progression: 记录技能执行结果 ──
        try:
            from livingtree.dna.skill_progression import get_skill_progression
            prog = get_skill_progression()
            task_type = self._guess_task_type(ctx)
            skill_map = {
                "environmental_report": "regulatory_compliance",
                "code_generation": "code_engineering",
                "data_analysis": "data_analysis",
                "document_generation": "document_generation",
            }
            skill = skill_map.get(task_type, "reasoning_quality")
            prog.record_outcome(
                skill=skill, success=rate > 0.5,
                confidence=ctx.metadata.get("economic_decision",
                    type('',(),{'roi':type('',(),{'roi_estimate':0.5})()})()).roi.roi_estimate / 10 or 0.5,
                session=ctx.session_id or "",
                mistake_type="execution_failure" if fail > 0 else "",
            )
        except Exception:
            pass

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

        # Calibration tracker: record prediction-vs-actual for trust calibration
        ct = getattr(self.world, 'calibration_tracker', None)
        if ct and rate > 0:
            try:
                predicted_ok = ctx.metadata.get("plan_confidence", rate)
                ct.record(predicted_ok, rate, metadata={
                    "session_id": ctx.session_id, "intent": ctx.intent or "",
                    "plan_steps": len(ctx.plan), "failed_steps": fail,
                })
            except Exception:
                pass

        # ── Reflect→StructMemory: bind reflections for ReAct future context ──
        struct_mem = getattr(self.world, 'struct_memory', None)
        if struct_mem and ctx.reflections:
            try:
                reflection_text = "\n".join(ctx.reflections)
                msgs = [
                    {"role": "system", "content": f"Reflection on {ctx.intent or ctx.user_input}"},
                    {"role": "assistant", "content": reflection_text},
                ]
                await struct_mem.bind_events(f"reflect_{ctx.session_id}", msgs)
                logger.debug(f"[reflect] StructMemory bind: {len(reflection_text)} chars")
            except Exception as e:
                logger.debug(f"[reflect] StructMemory bind skipped: {e}")

        # Evidence distillation: generate layered evidence from execution trace (AHE Pattern 2)
        tracer = getattr(self.world, 'tracer', None)
        if tracer and hasattr(tracer, 'distill_evidence') and len(ctx.execution_results) > 0:
            try:
                evidence = tracer.distill_evidence(
                    session_id=ctx.session_id,
                    execution_results=ctx.execution_results,
                    success_rate=rate,
                )
                ctx.metadata["distilled_evidence"] = evidence
            except Exception:
                pass
