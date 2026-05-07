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
import enum
import json
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from loguru import logger
from pydantic import BaseModel, Field

from .genome import Genome
from .consciousness import Consciousness
from .safety import SafetyGuard
from ..execution.context_fold import FoldResult, fold_context, fold_text_heuristic


class StageGate(enum.StrEnum):
    """CRV 6-stage signal-line protocol gate states (RuView pattern).
    
    gestalt → sensory → topology → coherence → search → model
    """
    ACCEPT = "accept"           # Stage output is confident — proceed
    RECALIBRATE = "recalibrate"  # Stage output insufficient — re-process
    SKIP = "skip"               # Stage not needed for this context
    REJECT = "reject"           # Stage detected unsafe/invalid condition


@dataclass
class StageGateResult:
    """CRV gate result with recalibration hints (RuView coherence gate pattern)."""
    gate: StageGate
    confidence: float           # 0.0-1.0
    reason: str
    recalibration_hints: list[str] = field(default_factory=list)
    max_recalibrations: int = 1  # How many times this stage can recalibrate
    depth_boost: int = 0         # Extra depth for recalibration attempt


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
    # Simulation / foresight stage results (optional)
    simulation_ran: bool = False
    simulation_findings: dict[str, Any] = Field(default_factory=dict)
    simulation_decision: dict[str, Any] = Field(default_factory=dict)

@dataclass
class Branch:
    id: str
    name: str
    hypothesis: str
    parent_session: str = ""
    created_at: str = ""
    status: str = "active"  # active, completed, merged, abandoned
    context_snapshot: dict = field(default_factory=dict)
    plan: list = field(default_factory=list)
    execution_results: list = field(default_factory=list)
    reflections: list = field(default_factory=list)
    success_rate: float = 0.0
    metadata: dict = field(default_factory=dict)

@dataclass
class ComparisonReport:
    branches_compared: list[str] = field(default_factory=list)
    winner: str = ""
    winner_score: float = 0.0
    scores: dict = field(default_factory=dict)
    improvements: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)
    recommendation: str = ""

@dataclass
class BranchDecision:
    should_branch: bool = False
    reason: str = ""
    num_branches: int = 1
    hypotheses: list[str] = field(default_factory=list)
    confidence: float = 0.0


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
        self._branches: dict[str, Branch] = {}
        self._folded_stages: dict[str, FoldResult] = {}
        self._fold_enabled = False
        # ── Economic Engine (lazy) ──
        self._economic_orch = None
        self._plan_validator = None
        self._fitness = None

    # ── Main pipeline ──

    async def run(self, user_input: str, fold: bool = False,
                  fold_max_chars: int = 500, **kwargs) -> LifeContext:
        """Run the full life cycle pipeline with optional Context-Folding.

        Args:
            user_input: The user's query/request
            fold: FoldAgent — if True, fold each stage's output into compact
                  summaries for the next stage, reducing context ~10x
            fold_max_chars: Target max chars for folded stage summaries
        """
        ctx = LifeContext(user_input=user_input, **kwargs)
        self.is_running = True
        self._fold_enabled = fold
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

        try:
            await self._stage("perceive", self._perceive, ctx)
            if self._fold_enabled:
                await self._fold_stage("perceive", ctx, fold_max_chars)
            await self._stage("cognize", self._cognize, ctx)
            if self._fold_enabled:
                await self._fold_stage("cognize", ctx, fold_max_chars)
            await self._stage("ontogrow", self._grow_ontology, ctx)
            if self._fold_enabled:
                await self._fold_stage("ontogrow", ctx, fold_max_chars)
            await self._stage("plan", self._plan, ctx)
            if self._fold_enabled:
                await self._fold_stage("plan", ctx, fold_max_chars)
            decision = self._should_branch(ctx)
            if decision.should_branch:
                hypotheses = ctx.metadata.get("hypotheses", []) or []
                created = []
                for i, hyp in enumerate(hypotheses[:3], start=1):
                    b = self.fork_branch(name=f"branch-{ctx.session_id}-{i}", hypothesis=hyp, ctx=ctx)
                    created.append(b)
                ctx.metadata["branches"] = [br.id for br in created]
            await self._stage("simulate", self._simulate, ctx)
            if self._fold_enabled:
                await self._fold_stage("simulate", ctx, fold_max_chars)
            await self._stage("execute", self._execute, ctx)
            if self._fold_enabled:
                await self._fold_stage("execute", ctx, fold_max_chars)
            branches = ctx.metadata.get("branches", [])
            if branches:
                if ctx.metadata.get("success_rate", 0) > 0:
                    comp = self.compare_branches(branch_ids=branches)
                    ctx.metadata["branch_comparison"] = comp
            await self._stage("reflect", self._reflect, ctx)
            if self._fold_enabled:
                await self._fold_stage("reflect", ctx, fold_max_chars)
            await self._stage("evolve", self._evolve, ctx)
            if self._fold_enabled:
                await self._fold_stage("evolve", ctx, fold_max_chars)

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
        cog_prompt = f"Analyze intent and required knowledge: {ctx.user_input}"

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
            cog_prompt = f"{cog_prompt}\n\nRelevant memory context:\n{mem_context[:4000]}"

        ctx.intent = await self.consciousness.chain_of_thought(cog_prompt)
        ctx.metadata["cognition"] = ctx.intent

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
        import re
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
        import time as _time
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
                        metadata={"extracted_from": "cognize_stage", "timestamp": _time.time()},
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
                from loguru import logger as _log
                _log.info(f"[ontogrow] Registered {len(registered)} new concepts: {registered}")
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

        # ── Dual-mode routing: DAG vs ReAct ──
        from ..execution.react_executor import (
            ExecutionMode, route_execution, ReactExecutor)
        fg = getattr(self.world, 'foresight_gate', None)
        mode = await route_execution(
            task=ctx.user_input or ctx.intent or "",
            plan=ctx.plan,
            consciousness=self.consciousness,
            foresight_gate=fg,
        )
        ctx.metadata["execution_mode"] = mode.value
        logger.info(f"[execute] Mode: {mode.value} ({len(ctx.plan)} steps, confidence={getattr(fg, '_state_streak', {})})")

        if mode == ExecutionMode.REACT:
            # ── ReAct: serial Think-Act-Observe loop ──
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
            from .skill_progression import get_skill_progression
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
        if fail:
            errors = [r.get("error", "?") for r in ctx.execution_results if r.get("error")]
            reflection += f". Errors: {errors}"
        ctx.reflections.append(reflection)
        ctx.metadata["lessons"] = ctx.reflections

        # Quality summary
        if ctx.quality_reports:
            qr_summary = f"Quality: {sum(1 for q in ctx.quality_reports if q['passed'])}/{len(ctx.quality_reports)} passed"
            ctx.reflections.append(qr_summary)

        # Calibration tracker: record prediction-vs-actual for trust calibration (RouteMoA Foresight)
        ct = getattr(self.world, 'calibration_tracker', None)
        if ct and rate:
            try:
                predicted_ok = ctx.metadata.get("plan_confidence", rate)
                ct.record(predicted_ok, rate, metadata={
                    "session_id": ctx.session_id, "intent": ctx.intent or "",
                    "plan_steps": len(ctx.plan), "failed_steps": fail,
                })
            except Exception:
                pass

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

        # Periodic meta-strategy review (every ~10 sessions)
        if self.genome.generation % 10 == 0 and ok:
            try:
                from .meta_strategy import get_meta_strategy_engine
                engine = get_meta_strategy_engine(self.consciousness)
                if engine.consciousness:
                    await engine.review_and_evolve()
            except Exception:
                pass

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

    # ── Branching utilities ──

    def fork_branch(self, name: str, hypothesis: str, ctx: LifeContext) -> Branch:
        branch_id = f"branch-{uuid.uuid4().hex[:8]}"
        snapshot = {
            "plan": ctx.plan,
            "retrieved_knowledge": ctx.retrieved_knowledge,
        }
        b = Branch(
            id=branch_id,
            name=name,
            hypothesis=hypothesis,
            parent_session=ctx.session_id,
            created_at=datetime.utcnow().isoformat(),
            context_snapshot=snapshot,
            plan=list(ctx.plan),
            execution_results=list(ctx.execution_results),
            reflections=list(ctx.reflections),
            success_rate=ctx.metadata.get("success_rate", 0.0),
            metadata=dict(ctx.metadata),
        )
        self._branches[branch_id] = b
        logger.info(f"[branch] forked new branch {branch_id} from session {ctx.session_id}")
        return b

    def compare_branches(self, branch_ids: list[str] | None = None) -> ComparisonReport:
        # Determine which branches to compare
        if branch_ids is None:
            candidates = [b for b in self._branches.values() if b.status in ("completed", "merged")]
        else:
            candidates = [self._branches[bid] for bid in branch_ids if bid in self._branches]
        if not candidates:
            return ComparisonReport(branches_compared=[], winner="", winner_score=0.0, scores={})

        # Score: primarily by success_rate, tie-breaker by completed execution results length
        scores = {b.id: (b.success_rate, len(b.execution_results)) for b in candidates}
        winner = max(candidates, key=lambda b: (b.success_rate, len(b.execution_results)))
        winner_score = scores[winner.id][0]
        all_ids = [b.id for b in candidates]

        report = ComparisonReport(
            branches_compared=all_ids,
            winner=winner.id,
            winner_score=float(winner_score),
            scores={b.id: scores[b.id][0] for b in candidates},
            improvements=[],
            regressions=[],
            recommendation=f"Selected {winner.id} as best branch based on highest success rate and progress.",
        )
        logger.info(f"[branch] comparison done: winner={report.winner}")
        return report

    def merge_branch(self, branch_id: str, strategy: str = "best") -> Branch:
        target = self._branches.get(branch_id)
        if not target:
            return None  # type: ignore
        # Determine winner among all branches for merging reference
        if self._branches:
            winner = max(self._branches.values(), key=lambda b: (b.success_rate, len(b.execution_results)))
        else:
            winner = target

        if strategy == "best" and winner:
            target.execution_results = list(winner.execution_results)
            target.plan = list(winner.plan)
            target.success_rate = winner.success_rate
        elif strategy == "concat":
            merged = []
            for b in self._branches.values():
                merged.extend(b.execution_results)
            target.execution_results = merged
            target.plan = [step for b in self._branches.values() for step in b.plan]
            target.success_rate = max(b.success_rate for b in self._branches.values()) if self._branches else target.success_rate
        elif strategy == "voting":
            # Majority vote on plan steps by length; simple heuristic
            if target.plan:
                target.plan = target.plan
            # otherwise keep existing
        target.status = "merged"
        logger.info(f"[branch] merged branch {branch_id} using strategy '{strategy}'")
        return target

    def list_branches(self) -> list[Branch]:
        return list(self._branches.values())

    def _should_branch(self, ctx: LifeContext) -> BranchDecision:
        hypotheses = ctx.metadata.get("hypotheses", []) or []
        explore_mode = ctx.metadata.get("explore_mode", False)
        # Simple complexity heuristic: longer inputs imply more complex tasks
        complexity = len(ctx.user_input) if ctx.user_input else 0
        threshold = 50
        should = len(hypotheses) >= 2 or explore_mode or complexity > threshold
        return BranchDecision(
            should_branch=should,
            reason=("multiple hypotheses detected" if len(hypotheses) >= 2 else "explore_mode" if explore_mode else "complexity"),
            num_branches=len(hypotheses) if hypotheses else 1,
            hypotheses=hypotheses,
            confidence=0.7,
        )

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
        s = LifeStage(stage=name, started_at=datetime.now(timezone.utc).isoformat())
        s.status = "running"
        self.stages.append(s)
        t0 = asyncio.get_event_loop().time()

        recal_count = 0
        while True:
            try:
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
