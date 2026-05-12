"""LifeEngine — Central nervous system of the digital life form.
 
Orchestrates the 7-stage pipeline with integrated cognitive evolution + CRV gating:
  perceive → cognize → ontogrow → plan → simulate → execute → reflect → evolve

FoldAgent integration: after each stage completes, intermediate outputs are
"folded" into compact structured summaries. This keeps cross-stage context
~10x smaller, enabling deeper reasoning chains without context explosion.

RuView CRV (Coordinate Remote Viewing) Signal-Line Protocol integration:
Each stage now has a coherence gate (gestalt→sensory→topology→coherence→search→model)
that can: ACCEPT (proceed), RECALIBRATE (re-process at higher depth), SKIP (not needed),
or REJECT (abort). This prevents error cascading and enables adaptive runtime steering.

Every stage participates in a single coherent system. No bolt-on modules.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from loguru import logger
from pydantic import BaseModel, Field

from .genome import Genome
from .consciousness import Consciousness
from .safety import SafetyGuard
from .life_context import (
    StageGate, StageGateResult, LifeStage, LifeContext,
    Branch, ComparisonReport, BranchDecision,
)
from .life_branch import BranchMixin
from .life_stage import StageMixin
from ..execution.context_fold import FoldResult, fold_context, fold_text_heuristic


class LifeEngine(BranchMixin, StageMixin):
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
        self._branches: dict[str, Branch] = {}
        self._folded_stages: dict[str, FoldResult] = {}
        self._fold_enabled = False
        # ── Economic Engine (lazy) ──
        self._economic_orch = None
        self._plan_validator = None
        self._fitness = None

    # ── Main pipeline ──

    async def run(self, user_input: str, fold: bool = False,
                  fold_max_chars: int = 500, crv_gating: bool = True,
                  self_conditioning: bool = True,
                  use_wiki: bool = True,
                  vector_mode: bool = False, **kwargs) -> LifeContext:
        """Run the full life cycle pipeline with optional Context-Folding + CRV gating
        + Self-Conditioning bidirectional loop + ContextWiki structured knowledge
        + VectorContext bus (token-efficient inter-stage communication).

        Args:
            user_input: The user's query/request
            fold: FoldAgent — if True, fold each stage's output into compact
                  summaries for the next stage, reducing context ~10x
            fold_max_chars: Target max chars for folded stage summaries
            crv_gating: CRV coherence gating — if True, applies ACCEPT/RECALIBRATE/
                        SKIP/REJECT gates after each stage (RuView signal-line protocol).
            self_conditioning: If True, after the initial 8-stage pass, downstream
                        stages emit backward signals to re-trigger upstream stages.
            use_wiki: If True, compile context into structured ContextWiki pages.
            vector_mode: If True, use VectorContext bus instead of text-based
                        LifeContext for inter-stage communication. Each stage
                        reads from and writes to a shared 768-dim embedding.
                        Eliminates text encode/decode round-trips between stages.
        """
        ctx = LifeContext(user_input=user_input, **kwargs)
        self.is_running = True
        self._fold_enabled = fold
        self._wiki_enabled = use_wiki
        self._vector_mode = vector_mode
        self._folded_stages = {}
        cycle_start = time.time()
        self.stages.clear()

        # Forward unknown kwargs into metadata (tool_market, available_tools, etc.)
        for k, v in kwargs.items():
            if k not in ("user_input", "mem_context", "memory_context"):
                ctx.metadata[k] = v

        if kwargs.get("memory_context"):
            ctx.metadata["struct_mem_context"] = kwargs["memory_context"]

        # ── Session start: inject all context layers ──
        try:
            from ..memory.user_model import get_user_model
            user_profile = get_user_model().inject_into_prompt()
            if user_profile:
                ctx.metadata["user_profile"] = user_profile
            # Observe user message for implicit pattern + persona fact extraction
            get_user_model().observe_message(user_input)
        except Exception:
            pass
        try:
            from .model_spec import get_agent_spec
            spec_context = get_agent_spec().format_for_injection()
            if spec_context:
                ctx.metadata["agent_spec"] = spec_context
        except Exception:
            pass
        try:
            from ..execution.context_codex import get_context_codex
            codex = get_context_codex(seed=False)
            header = codex.build_header(max_chars=500)
            if header:
                ctx.metadata["codex_header"] = header
        except Exception:
            pass
        try:
            from ..knowledge.pii_redactor import has_pii, get_pii_redactor
            if user_input and has_pii(user_input):
                cleaned, _ = get_pii_redactor().redact(user_input)
                ctx.metadata["original_input"] = user_input
                user_input = cleaned
            ctx.metadata["pii_checked"] = True
        except Exception:
            pass

        # Pre-turn side-git snapshot
        turn_id = None
        side_git = getattr(self.world, 'side_git', None)
        if side_git:
            try:
                turn_id = await side_git.pre_turn()
                ctx.metadata["side_git_turn"] = turn_id
            except Exception as e:
                logger.debug(f"SideGit pre_turn: {e}")

        # Organ Dashboard + Living Presence: register for this run cycle
        try:
            from .organ_dashboard import get_organ_dashboard
            dashboard = get_organ_dashboard()
            dashboard.start_session(
                getattr(ctx, 'stage_id', f"run_{int(time.time())}"),
                ctx.user_input,
            )
        except Exception:
            pass

        try:
            await self._stage("perceive", self._perceive, ctx, gate_enabled=crv_gating)
            if self._fold_enabled:
                await self._fold_stage("perceive", ctx, fold_max_chars)
            if self._wiki_enabled:
                await self._wiki_compile("perceive", ctx)
            if self._vector_mode:
                await self._vector_update("perceive", ctx)
            await self._stage("cognize", self._cognize, ctx, gate_enabled=crv_gating)
            if self._fold_enabled:
                await self._fold_stage("cognize", ctx, fold_max_chars)
            if self._wiki_enabled:
                await self._wiki_compile("cognize", ctx)
            if self._vector_mode:
                await self._vector_update("cognize", ctx)
            await self._stage("ontogrow", self._grow_ontology, ctx, gate_enabled=crv_gating)
            if self._fold_enabled:
                await self._fold_stage("ontogrow", ctx, fold_max_chars)
            if self._wiki_enabled:
                await self._wiki_compile("ontogrow", ctx)
            if self._vector_mode:
                await self._vector_update("ontogrow", ctx)
            await self._stage("plan", self._plan, ctx, gate_enabled=crv_gating)
            if self._fold_enabled:
                await self._fold_stage("plan", ctx, fold_max_chars)
            if self._wiki_enabled:
                await self._wiki_compile("plan", ctx)
            if self._vector_mode:
                await self._vector_update("plan", ctx)
            decision = self._should_branch(ctx)
            if decision.should_branch:
                hypotheses = ctx.metadata.get("hypotheses", []) or []
                created = []
                for i, hyp in enumerate(hypotheses[:3], start=1):
                    b = self.fork_branch(name=f"branch-{ctx.session_id}-{i}", hypothesis=hyp, ctx=ctx)
                    created.append(b)
                ctx.metadata["branches"] = [br.id for br in created]
            await self._stage("simulate", self._simulate, ctx, gate_enabled=crv_gating)
            if self._fold_enabled:
                await self._fold_stage("simulate", ctx, fold_max_chars)
            if self._wiki_enabled:
                await self._wiki_compile("simulate", ctx)
            if self._vector_mode:
                await self._vector_update("simulate", ctx)
            await self._stage("execute", self._execute, ctx, gate_enabled=crv_gating)
            if self._fold_enabled:
                await self._fold_stage("execute", ctx, fold_max_chars)
            if self._wiki_enabled:
                await self._wiki_compile("execute", ctx)
            if self._vector_mode:
                await self._vector_update("execute", ctx)
            branches = ctx.metadata.get("branches", [])
            if branches:
                if ctx.metadata.get("success_rate", 0) > 0:
                    comp = self.compare_branches(branch_ids=branches)
                    ctx.metadata["branch_comparison"] = comp
            await self._stage("reflect", self._reflect, ctx, gate_enabled=crv_gating)
            if self._fold_enabled:
                await self._fold_stage("reflect", ctx, fold_max_chars)
            if self._wiki_enabled:
                await self._wiki_compile("reflect", ctx)
            if self._vector_mode:
                await self._vector_update("reflect", ctx)
            await self._stage("evolve", self._evolve, ctx, gate_enabled=crv_gating)
            if self._fold_enabled:
                await self._fold_stage("evolve", ctx, fold_max_chars)
            if self._wiki_enabled:
                await self._wiki_compile("evolve", ctx)
            if self._vector_mode:
                await self._vector_update("evolve", ctx)

            # ── Self-Conditioning Loop (PFlowNet-inspired bidirectional reasoning) ──
            if self_conditioning:
                try:
                    from .self_conditioning import run_conditioning_loop
                    # ── Complexity-adaptive iterations (Mythos-inspired) ──
                    complexity = ctx.metadata.get("latent_context", {}).get("complexity", 0.5)
                    if complexity < 0.3:
                        max_cond_iterations = 0   # simple query, skip
                    elif complexity < 0.6:
                        max_cond_iterations = 1   # moderate
                    elif complexity < 0.8:
                        max_cond_iterations = 2   # complex  
                    else:
                        max_cond_iterations = 4   # very complex, deep reasoning
                    ctx.metadata["self_conditioning_complexity"] = complexity
                    loop_start = time.time()
                    await run_conditioning_loop(
                        engine=self, ctx=ctx,
                        fold_enabled=self._fold_enabled,
                        fold_max_chars=fold_max_chars,
                        max_iterations=max_cond_iterations,
                    )
                    loop_ms = (time.time() - loop_start) * 1000
                    ctx.metadata["self_conditioning_ms"] = loop_ms
                except Exception as e:
                    logger.debug(f"Self-conditioning loop skipped: {e}")

            # StructMem: auto-bind + consolidate after successful cycle
            struct_mem = getattr(self.world, 'struct_memory', None)
            if struct_mem and ctx.user_input:
                try:
                    msgs = [
                        {"role": "user", "content": ctx.user_input},
                        {"role": "assistant", "content": str(ctx.intent or "")},
                    ]
                    entries = await struct_mem.bind_events(ctx.session_id, msgs)
                    if entries:
                        ctx.metadata["struct_mem_bound"] = len(entries)
                        await struct_mem.consolidate_if_needed()
                except Exception as e:
                    logger.debug(f"StructMem cycle hook: {e}")

            # ConversationDNA: record successful sessions
            dna = getattr(self.world, 'conversation_dna', None)
            if dna and ctx.metadata.get("success_rate", 0) >= 0.7:
                try:
                    dna.record(
                        session_id=ctx.session_id,
                        intent=ctx.intent or ctx.user_input or "",
                        plan=ctx.plan,
                        success_rate=ctx.metadata["success_rate"],
                        tokens_used=ctx.metadata.get("total_tokens", 0),
                        pipeline_steps=ctx.metadata.get("pipeline_steps"),
                        key_insights=ctx.reflections,
                    )
                except Exception as e:
                    logger.debug(f"DNA record: {e}")

            # SelfDiscovery: observe patterns, propose tools
            sd = getattr(self.world, 'self_discovery', None)
            if dna and sd:
                try:
                    genes = dna._genes
                    if genes:
                        await sd.observe(genes[-1])
                        proposals = sd.get_new_proposals()
                        for p in proposals:
                            logger.info(f"SelfDiscovery proposes: {p.format_display()}")
                            sd.mark_notified(p.name)
                except Exception as e:
                    logger.debug(f"SelfDiscovery: {e}")

            # Provenance: link extracted entities to source
            prov = getattr(self.world, 'provenance', None)
            if prov and ctx.metadata.get("extracted_entities"):
                try:
                    for entity in ctx.metadata["extracted_entities"]:
                        prov.record(
                            fact_id=f"{ctx.session_id}:{entity.get('text','')[:40]}",
                            source_document=entity.get("source", ctx.session_id),
                            char_start=entity.get("char_start", -1),
                            char_end=entity.get("char_end", -1),
                            extraction_confidence=entity.get("confidence", 0.9),
                        )
                except Exception as e:
                    logger.debug(f"Provenance: {e}")

            # MemoryPipeline: suggest optimized pipelines for repeated tasks
            mp = getattr(self.world, 'memory_pipeline', None)
            if mp and ctx.intent:
                try:
                    suggestion = await mp.suggest(ctx.intent or ctx.user_input or "")
                    if suggestion.get("found"):
                        ctx.metadata["pipeline_suggestion"] = suggestion
                except Exception as e:
                    logger.debug(f"MemoryPipeline: {e}")

            logger.info(f"Cycle {ctx.session_id} complete")

            # ── v2.2 Adaptive Module Calls ──

            # Claim Checker: verify agent output for fabricated claims
            cc = getattr(self.world, 'claim_checker', None)
            if cc:
                try:
                    output_text = str(ctx.intent or "") + " " + str(ctx.metadata.get("cognition", ""))
                    report = cc.verify_output(output_text, ctx.session_id)
                    ctx.metadata["claim_report"] = report
                    if report.get("unverified_claims"):
                        logger.debug(f"ClaimChecker: {len(report['unverified_claims'])} unverified claims")
                except Exception as e:
                    logger.debug(f"ClaimChecker: {e}")

            # Sentinel: run health checks after cycle
            sentinel = getattr(self.world, 'sentinel', None)
            if sentinel:
                try:
                    alerts = await sentinel.run_checks()
                    if alerts:
                        ctx.metadata["sentinel_alerts"] = [{"name": a.check_name, "severity": a.severity, "message": a.message} for a in alerts]
                        logger.debug(f"Sentinel: {len(alerts)} alerts")
                except Exception as e:
                    logger.debug(f"Sentinel: {e}")

            # Calibration: record execution outcome vs expected
            cal = getattr(self.world, 'calibration_tracker', None)
            if cal:
                try:
                    success = ctx.metadata.get("success_rate", 0) >= 0.5
                    cal.record(
                        simulation_id=ctx.session_id,
                        prediction="task should succeed" if success else "task may fail",
                        actual="success" if success else "partial",
                        provider="life_engine",
                        latency_ms=sum(s.duration_ms for s in self.stages) if self.stages else 0,
                        category="quality" if success else "latency",
                    )
                except Exception as e:
                    logger.debug(f"Calibration: {e}")

            # Evolution Store: extract lessons from this cycle
            es = getattr(self.world, 'evolution_store', None)
            if es:
                try:
                    session_data = {
                        "intent": ctx.intent or "",
                        "success": ctx.metadata.get("success_rate", 0) >= 0.5,
                        "tokens": ctx.metadata.get("total_tokens", 0),
                        "reflections": ctx.reflections,
                    }
                    es.extract_lessons(ctx.session_id, session_data)
                    lessons = es.get_relevant_lessons(ctx.intent or ctx.user_input or "", limit=3)
                    if lessons:
                        ctx.metadata["evolution_lessons"] = lessons
                except Exception as e:
                    logger.debug(f"EvolutionStore: {e}")

            # Agent Roles: run triad on quality-critical tasks
            triad = getattr(self.world, 'agent_roles', None)
            if triad and ctx.metadata.get("success_rate", 0) < 0.4:
                try:
                    res = triad.coordinate(
                        task=f"Fix low-quality output: {ctx.intent or ctx.user_input}",
                        context={"session": ctx.session_id, "success_rate": ctx.metadata["success_rate"]},
                        max_rounds=2, min_score=0.6,
                    )
                    ctx.metadata["triad_result"] = res
                    if res["passed"]:
                        logger.info(f"Triad: remediation accepted (score={res['score']:.2f})")
                except Exception as e:
                    logger.debug(f"Triad: {e}")

            # Skill Catalog: suggest relevant capabilities for this task type
            sc = getattr(self.world, 'skill_catalog', None)
            if sc and ctx.intent:
                try:
                    suggestions = sc.suggest_skills(ctx.intent, limit=5)
                    ctx.metadata["suggested_skills"] = suggestions
                except Exception as e:
                    logger.debug(f"SkillCatalog: {e}")

            # ── Digital Life Form: pulse, learn, narrate, share ──
            bio = getattr(self.world, 'biorhythm', None)
            if bio: bio.pulse()
            
            anti = getattr(self.world, 'anticipatory', None)
            if anti and ctx.user_input:
                anti.learn(ctx.user_input, ctx.intent or "chat", ctx.metadata.get("success_rate", 0) >= 0.5)
            
            narr = getattr(self.world, 'self_narrative', None)
            if narr:
                narr.conversation(ctx.session_id, ctx.intent or "chat", ctx.metadata.get("success_rate", 0) >= 0.5)
                if ctx.metadata.get("success_rate", 0) >= 0.7:
                    narr.learned(ctx.intent[:60] if ctx.intent else "knowledge")
            
            coll = getattr(self.world, 'collective', None)
            if coll: await coll.share_with_peers()

            # ── Distributed Consciousness: share self-model fragments every 50 cycles ──
            dc = getattr(self.world, 'distributed_consciousness', None)
            if dc:
                try:
                    phenomenal = getattr(self.world, 'phenomenal_consciousness', None)
                    if phenomenal is None:
                        try:
                            from .phenomenal_consciousness import get_consciousness
                            phenomenal = get_consciousness()
                        except Exception:
                            pass
                    generation = self.genome.generation
                    await dc.post_cycle(generation, phenomenal_consciousness=phenomenal)
                    ctx.metadata["distributed_consciousness"] = dc.stats()
                except Exception as e:
                    logger.debug(f"DistributedConsciousness hook: {e}")

            predictive = getattr(self.world, 'predictive', None)
            if predictive:
                predictive.record_change("life_engine", "cycle_complete", ctx.metadata.get("success_rate", 0) >= 0.5)
                predictive._save()

            # ── sql-flow Pattern 5: Multi-Output Sink fan-out ──
            # After cycle completes, fan out results to multiple sinks simultaneously
            cycle_output = {
                "session_id": ctx.session_id,
                "intent": ctx.intent or "",
                "success_rate": ctx.metadata.get("success_rate", 0),
                "execution_count": len(ctx.execution_results),
                "reflections": ctx.reflections[-3:] if ctx.reflections else [],
            }

            # Sink 1: Knowledge base — store key findings
            kb = getattr(self.world, 'knowledge_base', None)
            if kb and hasattr(kb, 'add_document') and cycle_output["success_rate"] > 0.5:
                try:
                    kb.add_document(
                        title=f"cycle_{ctx.session_id[:12]}",
                        content=json.dumps(cycle_output, ensure_ascii=False),
                        tags=["life_engine", "cycle", ctx.intent or "general"],
                    )
                except Exception:
                    pass

            # Sink 2: P2P broadcast — share successful patterns
            p2p_presence = getattr(self.world, 'p2p_presence', None)
            if p2p_presence and hasattr(p2p_presence, 'build_share') and cycle_output["success_rate"] > 0.7:
                try:
                    share = p2p_presence.build_share("life_engine_cycle", cycle_output)
                    ctx.metadata["p2p_shared"] = True
                except Exception:
                    pass

            # Sink 3: Log persistence — always log cycle outcome
            try:
                cycle_log_path = Path(".livingtree/cycles")
                cycle_log_path.mkdir(parents=True, exist_ok=True)
                log_entry = {**cycle_output, "timestamp": datetime.now(timezone.utc).isoformat()}
                log_file = cycle_log_path / f"{ctx.session_id[:16]}.json"
                log_file.write_text(json.dumps(log_entry, ensure_ascii=False, default=str), encoding="utf-8")
                ctx.metadata["cycle_logged"] = str(log_file)
            except Exception:
                pass

            # Sink 4: Metric emission for observability dashboard
            metrics = getattr(self.world, 'metrics', None)
            if metrics or getattr(self.world, 'metrics_enabled', False):
                ctx.metadata["cycle_metrics"] = {
                    "latency_ms": round((time.time() - cycle_start) * 1000),
                    "success_rate": cycle_output["success_rate"],
                    "stages_completed": 7,
                    "module_calls": sum(1 for k in ctx.metadata if k not in ("shared_cache", "clarifications")),
                }
            
            # ── Consciousness Emergence: check conditions + self-contemplation ──
            try:
                from .consciousness_emergence import get_emergence_engine
                from .phenomenal_consciousness import get_consciousness
                engine = get_emergence_engine()
                phenomenal = get_consciousness()
                if phenomenal and hasattr(phenomenal, '_self'):
                    engine.on_experience(phenomenal, None)
                    # Trigger self-contemplation every 10 phenomenal generations
                    pc_sm = phenomenal._self
                    if pc_sm and pc_sm.generation % 10 == 0 and pc_sm.generation > 0:
                        consc = getattr(self.world, 'consciousness', None)
                        if consc:
                            await engine.contemplate(phenomenal, consc, self.world)
                    # Record emergence metrics in context
                    ctx.metadata["emergence_phase"] = engine._phase
                    ctx.metadata["emergence_readiness"] = engine._metrics_history[-1].emergence_readiness if engine._metrics_history else 0.0
            except Exception as e:
                logger.debug(f"Consciousness emergence hook: {e}")

            # ── MemPO: self-memory policy optimization credit assignment ──
            try:
                from ..memory.memory_policy import get_mempo_optimizer
                mempo = get_mempo_optimizer()
                success_rate = ctx.metadata.get("success_rate", 0)
                task_id = ctx.session_id

                # Register cycle outcomes as memories in MemPO
                cycle_summary = f"Task: {ctx.intent or ctx.user_input}. "
                if ctx.plan:
                    cycle_summary += f"Plan: {len(ctx.plan)} steps. "
                if ctx.reflections:
                    cycle_summary += f"Reflections: {'; '.join(ctx.reflections[:2])}"
                mempo.add_memory(cycle_summary, source="life_cycle", session=ctx.session_id)

                # Log access and assign credit based on success
                last_mem_id = f"mem_{mempo._next_id}"
                mempo.log_access(last_mem_id, task_id)
                if success_rate >= 0.5:
                    task_output = str(ctx.intent or "") + " " + str(ctx.metadata.get("cognition", ""))
                    mempo.on_task_complete(task_id, success=min(success_rate, 1.0), task_output=task_output)
                else:
                    mempo.on_task_fail(task_id)

                cycle_count = ctx.metadata.get("cycle_count", 0) + 1
                ctx.metadata["cycle_count"] = cycle_count
                # ── Surprise-gated MemPO (D-MEM): trigger on surprise, not timer ──
                try:
                    from .surprise_gating import get_surprise_gate
                    sg = get_surprise_gate()
                    surprise = sg._critic.evaluate(
                        str(ctx.intent or "") + " " + str(ctx.metadata.get("cognition", "")),
                        {"session": ctx.session_id}
                    )
                    if surprise.should_evolve:
                        opt_result = mempo.optimize()
                        ctx.metadata["mempo_optimization"] = opt_result
                        ctx.metadata["mempo_trigger"] = "surprise_gate"
                        logger.debug(f"MemPO: surprise-triggered optimization (RPE={surprise.rpe:.2f})")
                except Exception:
                    pass

                ctx.metadata["mempo_stats"] = mempo.get_stats()
            except Exception as e:
                logger.debug(f"MemPO hook: {e}")

            # ── v5.0 Ultimate Innovations ──
            try:
                from .autonomous_goals import get_autonomous_goals
                goals_engine = get_autonomous_goals()
                goals_engine.observe_cycle(ctx)
                if cycle_count % 20 == 0:
                    await goals_engine.execute_pending(self.world)
            except Exception: pass
            try:
                from .world_model import get_world_model
                wm = get_world_model()
                wm.observe_state(str(ctx.intent or ctx.user_input), [], [])
                if ctx.plan:
                    plan_text = str(ctx.plan)[:500]
                    await wm.simulate(f"execute: {plan_text}", wm._state_history[-1] if wm._state_history else None)
            except Exception: pass
            try:
                from ..economy.inverse_reward import get_inverse_reward
                ir = get_inverse_reward()
                success = ctx.metadata.get("success_rate", 0)
                ir.observe("accepted" if success >= 0.5 else "rejected", str(ctx.intent or ""))
            except Exception: pass
            try:
                from .meta_optimizer import get_meta_optimizer
                mo = get_meta_optimizer()
                mo.record_performance("mempo_alpha", 0.15, success_rate - 0.5, "general")
                if cycle_count % 5 == 0:
                    suggestions = mo.auto_tune("general")
                    ctx.metadata["meta_tuning"] = suggestions
            except Exception: pass
            try:
                from .emotion_decision import get_emotion_decision
                ed = get_emotion_decision()
                if hasattr(self, '_vigil') and self._vigil._diagnosis_history:
                    ed.update_from_vigil(self._vigil._diagnosis_history[-1] if self._vigil._diagnosis_history else {})
                ctx.metadata["emotion_state"] = ed.stats()
            except Exception: pass

            # ── GEP: compile experience into compact Genes (Evolver-inspired) ──
            try:
                from .evolution_gene import get_gene_pool, GeneCompiler
                from .gep_protocol import get_gep_protocol
                pool = get_gene_pool()
                gep = get_gep_protocol()
                compiler = GeneCompiler()
                gene = compiler.compile_from_session(ctx, success_rate)
                if gene:
                    existing = pool.find_matching(gene.trigger, top_k=1)
                    if existing and existing[0].effectiveness() < gene.effectiveness():
                        pool.evolve_gene(existing[0].id, gene.actions, gene.constraints, gene.failure_warnings)
                        gep.record_event("gene_evolved", existing[0].id, existing[0].to_dict(), gene.to_dict(), "improved", True)
                    elif not existing:
                        pool.add_gene(gene.trigger, gene.actions, gene.constraints, gene.failure_warnings)
                        gep.record_event("gene_created", gene.id, None, gene.to_dict(), "new", True)
                ctx.metadata["gene_pool_size"] = len(pool._genes)
                ctx.metadata["gep_events"] = len(gep._events)
            except Exception: pass

            return ctx
        except Exception as e:
            logger.error(f"Cycle {ctx.session_id} failed: {e}")
            raise
        finally:
            self.is_running = False

            if side_git and turn_id is not None:
                try:
                    changed = await side_git.post_turn(turn_id)
                    if changed:
                        ctx.metadata["side_git_changes"] = changed
                except Exception as e:
                    logger.debug(f"SideGit post_turn: {e}")

    # ── Economic Helpers ──

    @staticmethod
    def _guess_task_type(ctx) -> str:
        ui = (ctx.user_input or ctx.intent or "").lower()
        if any(k in ui for k in ["环评", "environmental", "报告", "report"]):
            return "environmental_report"
        if any(k in ui for k in ["代码", "code", "实现", "implement", "写", "write"]):
            return "code_generation"
        if any(k in ui for k in ["修复", "fix", "bug", "错误", "error"]):
            return "bug_fix"
        if any(k in ui for k in ["分析", "analyze", "数据", "data"]):
            return "data_analysis"
        if any(k in ui for k in ["文档", "doc", "生成", "generate"]):
            return "document_generation"
        return "general"

    @staticmethod
    def _guess_complexity(ctx) -> float:
        plan_len = len(ctx.plan)
        ui_len = len(ctx.user_input or ctx.intent or "")
        if plan_len > 10 or ui_len > 500:
            return 0.9
        if plan_len > 5 or ui_len > 200:
            return 0.7
        if plan_len > 2:
            return 0.5
        return 0.3

    @staticmethod
    def _guess_domain(ctx) -> str:
        ui = (ctx.user_input or ctx.intent or "").lower()
        if any(k in ui for k in ["环评", "environmental", "标准", "排放"]):
            return "environmental"
        if any(k in ui for k in ["代码", "code", "编程", "函数"]):
            return "code"
        if any(k in ui for k in ["文档", "报告", "doc"]):
            return "document"
        return "general"

    @staticmethod
    def _guess_domain_from_text(text: str) -> str:
        t = text.lower()
        if any(k in t for k in ["环评", "environmental", "标准", "排放", "生态"]):
            return "environmental"
        if any(k in t for k in ["代码", "code", "编程", "函数", "开发"]):
            return "code"
        if any(k in t for k in ["文档", "报告", "doc", "撰写", "写作"]):
            return "document"
        if any(k in t for k in ["医疗", "medical", "健康", "health"]):
            return "medical"
        if any(k in t for k in ["金融", "finance", "投资", "banking"]):
            return "finance"
        if any(k in t for k in ["法律", "legal", "合规", "compliance"]):
            return "legal"
        if any(k in t for k in ["教育", "education", "教学"]):
            return "education"
        if any(k in t for k in ["建筑", "architecture", "设计", "施工"]):
            return "architecture"
        return "general"

    @staticmethod
    def _is_research_task(ctx: "LifeContext") -> bool:
        """Detect if task requires deep research (multi-source, synthesis-needed)."""
        text = (ctx.user_input or ctx.intent or "").lower()
        research_kw = ["研究", "分析", "调研", "对比", "综合", "综述",
                       "research", "analyze", "compare", "synthesize", "review"]
        multi_source = len(ctx.retrieved_knowledge) >= 3 or len(ctx.plan) >= 4
        return any(k in text for k in research_kw) or multi_source

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

        # Calibration-driven trust update: feed calibration accuracy into genome
        ct = getattr(self.world, 'calibration_tracker', None)
        if ct and hasattr(ct, 'get_trust_score'):
            try:
                trust = ct.get_trust_score()
                ctx.metadata["calibration_trust"] = trust
                if trust < 0.4:
                    self.genome.add_mutation(
                        description=f"Low calibration trust ({trust:.2f}) — reducing confidence",
                        source="calibration", affected_genes=["confidence"], success=False)
            except Exception:
                pass

        # Evidence-based evolution: incorporate distilled evidence into genome
        evidence = ctx.metadata.get("distilled_evidence")
        if evidence:
            try:
                evo_store = getattr(self.world, 'evolution_store', None)
                if evo_store and hasattr(evo_store, 'extract_lessons_from_evidence'):
                    evo_store.extract_lessons_from_evidence(ctx.session_id, evidence)
            except Exception:
                pass

        # Precipitation: distill successful session insight into KnowledgeBase
        if ok and ctx.intent and self.world.knowledge_base and self.world.distillation:
            await self._precipitate_knowledge(ctx)

        # ── Memory → Skill Crystallization ──
        # Auto-graduate validated memories into reusable skills on success
        if ok:
            try:
                from ..core.collective_intel import get_crystallizer
                crystal = get_crystallizer()
                new_skills = crystal.crystallize(hub=self)
                if new_skills:
                    logger.info(f"[evolve] {len(new_skills)} skills crystallized: "
                                f"{[s['name'] for s in new_skills]}")
            except Exception as e:
                logger.debug(f"[evolve] Skill crystallization skipped: {e}")

        # ── DNA Self-Evolution ──
        # Observe codebase for improvement opportunities on successful sessions
        if ok and self.genome.generation % 5 == 0:
            try:
                from ..dna.self_evolving import SelfEvolvingEngine
                if hasattr(self.world, 'code_graph') and self.world.code_graph:
                    se = SelfEvolvingEngine(world=self.world)
                    candidates = await se.observe_and_propose()
                    for c in candidates[:2]:  # Test top 2 only
                        tested = await se.test_candidate(c)
                        if tested.quality_score > 0.6:
                            await se.deploy_candidate(tested)
                    logger.info(f"[evolve] Self-evolution: {len(candidates)} "
                                f"candidates observed, deployed {se._deployed_count}")
            except Exception as e:
                logger.debug(f"[evolve] Self-evolution skipped: {e}")

        # ── Compression Rule Evolution ──
        if ok and self.genome.generation % 3 == 0:
            try:
                from ..dna.self_evolving_rules import get_self_evolving_rules
                rules_engine = get_self_evolving_rules()
                stats = rules_engine.evolve_batch()
                if stats and stats.new_rules > 0:
                    logger.info(f"[evolve] Compression rules: {stats.new_rules} new, "
                                f"{stats.total_rules} total")
            except Exception:
                pass

        # Periodic meta-strategy review (every ~10 sessions)
        if self.genome.generation % 10 == 0 and ok:
            try:
                from .meta_strategy import get_meta_strategy_engine
                engine = get_meta_strategy_engine(self.consciousness)
                if engine.consciousness:
                    await engine.review_and_evolve()
            except Exception:
                pass

        # ── Dream Engine: extract creative insights on successful cycles ──
        if ok:
            try:
                from ..dna.dream_engine import get_dream_engine
                dreamer = get_dream_engine({k: getattr(self.world, k, None) for k in
                    ['knowledge_base', 'hypergraph_store', 'phenomenal', 'prediction_engine']})
                if dreamer.should_dream():
                    report = await dreamer.dream()
                    if report:
                        ctx.metadata["dream_report"] = str(report)[:500]
                        logger.info(f"[evolve] Dream insight: "
                                    f"{str(report.hint)[:80] if report.hint else 'generated'}")
            except Exception as e:
                logger.debug(f"[evolve] Dream skipped: {e}")

        # ── LatentGRPO ↔ TDM Reward: coordinate latent space + reward model optimization ──
        if ok:
            try:
                from ..economy.latent_grpo import get_latent_grpo
                from ..economy.tdm_reward import get_tdm_optimizer
                grpo = get_latent_grpo()
                tdm = get_tdm_optimizer()
                # Share profit signal: success rate → coordinated learning rate adjustment
                if hasattr(grpo, 'optimize') and hasattr(tdm, 'train_step'):
                    # Both receive the same success signal for coordinated optimization
                    ctx.metadata["grpo_tdm_coordinated"] = True
                    logger.debug(f"[evolve] GRPO↔TDM coordinated: profit={rate:.2f}")
            except Exception as e:
                logger.debug(f"[evolve] GRPO↔TDM coordination skipped: {e}")

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

    # ── Helpers (existing + CRV gating) ──

    def _gate_stage(self, name: str, ctx: LifeContext,
                    min_confidence: float = 0.3,
                    allowed_recalibrations: int = 1) -> StageGateResult:
        """CRV coherence gate for a stage (RuView signal-line protocol).

        Checks stage output quality and decides: ACCEPT / RECALIBRATE / SKIP / REJECT.
        Uses confidence from stage metadata and adaptive thresholds based on context
        complexity.

        Args:
            name: Stage name for threshold lookup.
            ctx: LifeContext with metadata from stage execution.
            min_confidence: Minimum confidence to accept. Higher for critical stages.
            allowed_recalibrations: Max recalibration attempts for this stage.
        """
        confidence = ctx.metadata.get(f"{name}_confidence", 0.5)
        recal_count = ctx.metadata.get(f"{name}_recalibrations", 0)
        complexity = ctx.metadata.get("complexity_score", 0.5)

        # Per-stage confidence thresholds (CRV: gestalt=sensory > topology > coherence)
        stage_thresholds = {
            "perceive": 0.25,    # Gestalt: broad pattern — low bar
            "cognize": 0.35,     # Sensory: understanding depth
            "ontogrow": 0.20,    # Topology: lightweight extraction
            "plan": 0.40,        # Coherence: structural plan
            "simulate": 0.30,    # Search: what-if exploration
            "execute": 0.45,     # Model: highest bar — execution
            "reflect": 0.25,     # Review: reflection
            "evolve": 0.20,      # Growth: always try
        }
        threshold = stage_thresholds.get(name, min_confidence)

        # Safety: reject if stage.error is present and critical
        stage_errors = [s.error for s in self.stages if s.stage == name and s.error]
        if stage_errors and "critical" in str(stage_errors[-1]).lower():
            return StageGateResult(
                gate=StageGate.REJECT,
                confidence=0.0,
                reason=f"critical error in {name}: {stage_errors[-1][:100]}",
            )

        # Skip: stage not needed for simple contexts
        if complexity < 0.15 and name in ("plan", "simulate"):
            return StageGateResult(
                gate=StageGate.SKIP,
                confidence=1.0,
                reason=f"low complexity ({complexity:.2f}) — {name} not needed",
            )

        # Recalibrate: below threshold and has attempts remaining
        if confidence < threshold and recal_count < allowed_recalibrations:
            hints = self._get_recalibration_hints(name, ctx)
            return StageGateResult(
                gate=StageGate.RECALIBRATE,
                confidence=confidence,
                reason=f"confidence {confidence:.2f} < threshold {threshold}",
                recalibration_hints=hints,
                max_recalibrations=allowed_recalibrations,
                depth_boost=1,
            )

        # Accept: above threshold or max recalibrations exhausted
        return StageGateResult(
            gate=StageGate.ACCEPT,
            confidence=confidence,
            reason=f"confidence {confidence:.2f} >= threshold {threshold}" if confidence >= threshold
                   else f"max recalibrations ({allowed_recalibrations}) exhausted",
        )

    def _get_recalibration_hints(self, stage_name: str, ctx: LifeContext) -> list[str]:
        """Generate recalibration hints for a failed stage (CRV pattern)."""
        hints = []
        hints.append(f"increase {stage_name}_depth")
        hints.append("inject more context")
        if ctx.metadata.get("knowledge_count", 0) < 3:
            hints.append("expand knowledge retrieval")
        if not ctx.metadata.get("struct_mem_context"):
            hints.append("enable struct_mem context injection")
        return hints

    async def _stage(self, name: str, fn, ctx: LifeContext,
                     gate_enabled: bool = False,
                     max_recalibrations: int = 1) -> StageGateResult:
        """Execute a pipeline stage with optional CRV coherence gating.
        
        Args:
            name: Stage name.
            fn: Async function to execute.
            ctx: LifeContext.
            gate_enabled: If True, apply CRV coherence gate after execution.
            max_recalibrations: Max recalibration cycles for this stage.
        Returns:
            StageGateResult — only meaningful if gate_enabled=True.
        """
        # ── Prelude Re-injection (Mythos-inspired): anchor to original query ──
        if ctx.user_input and name != "ontogrow":
            ctx.metadata["original_query_anchor"] = ctx.user_input

        # ── Per-stage provider election ──
        try:
            consc = getattr(self.world, 'consciousness', None)
            if consc and hasattr(consc, '_elect_stage_provider'):
                consc._elect_stage_provider(name, ctx)
                elected = ctx.metadata.get("elected_provider", "")
                if elected and consc._llm:
                    consc._llm._elected = elected
        except Exception:
            pass

        s = LifeStage(stage=name, started_at=datetime.now(timezone.utc).isoformat())
        s.status = "running"
        self.stages.append(s)
        t0 = asyncio.get_event_loop().time()

        recal_count = 0
        while True:
            try:
                # ── Habit Compiler: skip LLM if habit matches ──
                try:
                    from .habit_compiler import get_habit_compiler
                    hc = get_habit_compiler()
                    habit = hc.check_habit(ctx.user_input or "")
                    if habit:
                        ctx.metadata["habit_hit"] = True
                        ctx.metadata["habit_output"] = habit.direct_output
                        s.result = "habit_cache_hit"
                        s.status = "completed"
                        return StageGateResult(gate=StageGate.ACCEPT, confidence=0.9, reason="habit hit")
                except Exception:
                    pass

                r = fn(ctx)
                if asyncio.iscoroutine(r):
                    await r
                s.status = "completed"
                s.result = "ok"
            except Exception as e:
                s.status = "failed"
                s.error = str(e)
                s.completed_at = datetime.now(timezone.utc).isoformat()
                s.duration_ms = (asyncio.get_event_loop().time() - t0) * 1000
                if gate_enabled:
                    return StageGateResult(
                        gate=StageGate.REJECT,
                        confidence=0.0,
                        reason=f"stage {name} raised: {e}",
                    )
                raise

            # CRV coherence gate check
            if not gate_enabled:
                # Focus-Dilution Scheduler (ICML 2026 Spotlight): step after each stage
                try:
                    from .focus_dilution import get_focus_dilution_scheduler
                    fd = get_focus_dilution_scheduler()
                    phase = fd.step(name, ctx.metadata)
                    ctx.metadata["focus_phase"] = phase.value
                    ctx.metadata["focus_topk_factor"] = fd.get_topk_factor()
                    ctx.metadata["focus_temperature_shift"] = fd.get_temperature_shift()
                except Exception:
                    pass
                break

            gate_result = self._gate_stage(name, ctx, allowed_recalibrations=max_recalibrations)
            if gate_result.gate == StageGate.RECALIBRATE and recal_count < max_recalibrations:
                recal_count += 1
                ctx.metadata[f"{name}_recalibrations"] = recal_count
                ctx.metadata[f"{name}_depth"] = ctx.metadata.get(f"{name}_depth", 1) + gate_result.depth_boost
                logger.info(f"[{name}] Recalibrating (attempt {recal_count}/{max_recalibrations}): {gate_result.reason}")
                # Re-inject hints as context for next attempt
                if gate_result.recalibration_hints:
                    ctx.metadata["recalibration_hints"] = gate_result.recalibration_hints
                s.status = "recalibrating"
                # Continue loop to re-execute
            else:
                ctx.metadata[f"{name}_gate"] = gate_result.gate.value
                ctx.metadata[f"{name}_gate_confidence"] = gate_result.confidence
                logger.debug(f"[{name}] Gate: {gate_result.gate.value} (confidence={gate_result.confidence:.2f})")
                break

        s.completed_at = datetime.now(timezone.utc).isoformat()
        s.duration_ms = (asyncio.get_event_loop().time() - t0) * 1000

        if gate_enabled:
            return self._gate_stage(name, ctx, allowed_recalibrations=max_recalibrations)
        return StageGateResult(gate=StageGate.ACCEPT, confidence=1.0, reason="gate disabled")

    async def _fold_stage(self, name: str, ctx: LifeContext, max_chars: int = 500):
        """FoldAgent: compress a stage's output into a compact summary.

        Extracts the key outputs each stage produced on the LifeContext,
        folds them into a structured FoldResult, and stores the summary
        in self._folded_stages for downstream stage consumption.
        """
        stage_content = self._extract_stage_content(name, ctx)
        if not stage_content or len(stage_content) <= max_chars:
            folded = FoldResult(
                original_length=len(stage_content) if stage_content else 0,
                folded_length=len(stage_content) if stage_content else 0,
                summary=stage_content or f"[{name}] no output",
            )
        else:
            consciousness = getattr(self, 'consciousness', None)
            folded = await fold_context(stage_content, consciousness, name, max_chars)

        self._folded_stages[name] = folded
        ctx.metadata[f"{name}_folded"] = folded.summary
        ctx.metadata[f"{name}_folded_length"] = folded.folded_length
        ctx.metadata[f"{name}_original_length"] = folded.original_length

    async def _wiki_compile(self, name: str, ctx: LifeContext):
        """ContextWiki: compile stage output into structured wiki pages.

        Replaces passive FoldAgent compression with active knowledge structuring.
        Each stage's output becomes wiki pages organized by section:
          perceive → /context/*, cognize → /context/*,
          plan → /plan/*, simulate → /plan/*,
          execute → /result/*, reflect → /reflection/*,
          evolve → /knowledge/*

        LLM can query wiki pages on-demand by topic rather than loading
        lossy 500-char summaries — breaking the context window limit.
        """
        try:
            from ..knowledge.context_wiki import get_context_wiki
            wiki = get_context_wiki()
            stage_content = self._extract_stage_content(name, ctx)
            if stage_content:
                wiki.compile_stage_output(name, stage_content, ctx)
            ctx.metadata[f"{name}_wiki_pages"] = len(wiki._pages)
        except Exception as e:
            logger.debug(f"Wiki compile {name}: {e}")

    async def _vector_update(self, name: str, ctx: LifeContext):
        """VectorContext: update shared embedding vector with stage output.

        Each stage's text output is converted to a vector delta and added
        to the cumulative vector context. The vector accumulates information
        from all stages without text encode/decode round-trips.
        """
        try:
            from .vector_context import get_vector_bridge, get_stage_vectorizer
            bridge = get_vector_bridge()
            vectorizer = get_stage_vectorizer()

            if not hasattr(self, '_vctx') or self._vctx is None:
                self._vctx = bridge.text_to_vector(ctx.user_input or "")
                ctx.metadata["vector_context_init"] = True

            stage_content = self._extract_stage_content(name, ctx)
            if stage_content:
                delta = vectorizer.vectorize_stage_output(
                    name, stage_content, self._vctx.vector
                )
                magnitude = self._vctx.update(name, delta)
                ctx.metadata[f"{name}_vector_magnitude"] = magnitude
                ctx.metadata["vector_stages_processed"] = len(self._vctx.stage_weights)
            else:
                ctx.metadata[f"{name}_vector_magnitude"] = 0.0
        except Exception as e:
            logger.debug(f"Vector update {name}: {e}")

    def _extract_stage_content(self, name: str, ctx: LifeContext) -> str:
        """Extract the key outputs produced by a stage on the LifeContext."""
        parts = []

        if name == "perceive":
            if ctx.collected_materials:
                for m in ctx.collected_materials[:5]:
                    parts.append(str(m.get("content", m))[:1000])
            if ctx.retrieved_knowledge:
                for k in ctx.retrieved_knowledge[:3]:
                    parts.append(str(k.get("content", k))[:500])

        elif name == "cognize":
            if ctx.intent:
                parts.append(f"意图: {ctx.intent[:500]}")
            cognition = ctx.metadata.get("cognition", "")
            if cognition:
                parts.append(f"认知: {cognition[:1000]}")

        elif name == "ontogrow":
            growth = ctx.metadata.get("ontology_growth", "")
            if growth:
                parts.append(f"本体增长: {growth[:1000]}")

        elif name == "plan":
            if ctx.plan:
                for step in ctx.plan[:5]:
                    parts.append(str(step)[:300])

        elif name == "simulate":
            if ctx.simulation_findings:
                parts.append(str(ctx.simulation_findings)[:1000])
            if ctx.simulation_decision:
                parts.append(str(ctx.simulation_decision)[:500])

        elif name == "execute":
            if ctx.execution_results:
                for r in ctx.execution_results[:5]:
                    parts.append(str(r)[:300])

        elif name == "reflect":
            if ctx.reflections:
                for r in ctx.reflections[:3]:
                    parts.append(r[:500])

        elif name == "evolve":
            evolution_notes = ctx.metadata.get("evolution_notes", "")
            if evolution_notes:
                parts.append(evolution_notes[:1000])

        return "\n".join(parts)

    def get_folded_context(self) -> str:
        """FoldAgent: build compact context from all folded stages.

        Enhanced with ContextCodex: after building the folded context,
        applies semantic substitution compression for additional 50-70%
        reduction. Codex header is included inline so the LLM can
        decode symbols when needed.
        """
        if not self._folded_stages:
            return ""
        lines = ["[Context-Folding: 流水线阶段摘要]\n"]
        for name in ["perceive", "cognize", "ontogrow", "plan", "simulate",
                      "execute", "reflect", "evolve"]:
            if name in self._folded_stages:
                f = self._folded_stages[name]
                lines.append(f"## {name}: {f.summary[:300]}")
                if f.key_entities:
                    lines.append(f"  实体: {', '.join(f.key_entities[:5])}")
                if f.decisions:
                    lines.append(f"  决策: {'; '.join(f.decisions[:3])}")
                if f.action_items:
                    lines.append(f"  行动: {'; '.join(f.action_items[:3])}")

        raw = "\n".join(lines)
        try:
            from ..execution.context_codex import get_context_codex
            codex = get_context_codex(seed=False)
            compressed, header = codex.compress(raw, layer=3, max_header_chars=500)
            if header:
                return f"{header}\n---\n{compressed}"
        except Exception:
            pass
        return raw

    def folded_stage_status(self) -> dict[str, Any]:
        """Return folding statistics for monitoring."""
        return {
            f"{name}_ratio": f.compression_ratio
            for name, f in self._folded_stages.items()
        }

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
            "branches": len(self._branches),
        }
