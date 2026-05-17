"""TreeLLM — Lightweight multi-provider LLM routing engine.

Replaces LiteLLM for LivingTree's specific needs. Features:
- Direct HTTP calls (no heavy dependency)
- Multi-provider tree with automatic failover
- Streaming support
- Cost/latency tracking
- Built-in tiny classifier for smart routing

Architecture:
    TreeLLM
    ├── providers (list of Provider)
    │   ├── DeepSeekProvider   (api.deepseek.com)
    │   ├── LongCatProvider    (api.longcat.chat)
    │   └── OpenCodeProvider   (localhost:4096)
    ├── router (RoutingStrategy)
    │   ├── ElectRouter       (ping all, pick first alive)
    │   ├── CostRouter        (cheapest first)
    │   ├── LatencyRouter     (fastest first)
    │   └── SmartRouter       (classifier-based)
    └── classifier (TinyClassifier)
        └── TF-IDF + Logistic Regression (pure numpy)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
import time
from loguru import logger
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from .classifier import TinyClassifier
from .providers import (
    Provider, ProviderResult, OpenAILikeProvider,
    create_deepseek_provider, create_longcat_provider,
    create_nvidia_provider, create_modelscope_provider,
    create_bailing_provider, create_stepfun_provider,
    create_internlm_provider, create_sensetime_provider,
    create_openrouter_provider,
)
from .holistic_election import get_election, RouterStats

# Lazy-imported modules (imported here once, not per-call)
from .capability_bus import get_capability_bus
from .session_compressor import get_session_compressor
from .segmented_kv_compressor import get_segmented_compressor
from .latency_oracle import get_latency_oracle
from .session_binding import get_session_binding
from .recording_engine import get_recording_engine, RecordLayer
from .synapse_aggregator import get_synapse_aggregator, ModelOutput
from .auto_prompt import get_auto_prompt

# Pre-compiled regex for hot paths
TOOL_CALL_RE = re.compile(r'<tool_call\s+name="(\w+)"\s*>(.*?)</tool_call>', re.DOTALL)
# JSON tool call: {"tool": "name", "params": {...}}
JSON_TOOL_RE = re.compile(r'\{\s*"tool"\s*:\s*"(\w+)"\s*,\s*"params"\s*:\s*(\{[^}]+\})\s*\}')
# OpenAI function calling: name + arguments JSON
OPENAI_TOOL_RE = re.compile(r'"name":\s*"(\w+)".*?"arguments":\s*"([^"]*)"', re.DOTALL)


def parse_tool_calls(text: str) -> list[tuple[str, str]]:
    """Unified tool call parser — handles XML, JSON, and OpenAI formats.

    Returns list of (tool_name, tool_args) tuples. Empty list if no tool calls.
    """
    calls = TOOL_CALL_RE.findall(text)
    if calls:
        return [(name, args.strip()) for name, args in calls]

    # JSON format: try balanced extraction first, then regex
    json_start = text.rfind('{"tool"')
    if json_start >= 0:
        depth = 0
        in_str = False
        esc = False
        for i in range(json_start, len(text)):
            ch = text[i]
            if esc: esc = False; continue
            if ch == '\\': esc = True; continue
            if ch == '"' and not esc: in_str = not in_str; continue
            if in_str: continue
            if ch == '{': depth += 1
            elif ch == '}': depth -= 1
            if depth == 0:
                json_block = text[json_start:i+1]
                try:
                    data = json.loads(json_block)
                    if "tool" in data and "params" in data:
                        return [(data["tool"], json.dumps(data["params"], ensure_ascii=False))]
                except json.JSONDecodeError:
                    pass
                break

    # OpenAI format
    openai_matches = list(OPENAI_TOOL_RE.finditer(text))
    if openai_matches:
        return [(m.group(1), m.group(2)) for m in openai_matches]

    return []



class TreeLLM:

    def __init__(self):
        self._providers: dict[str, Provider] = {}
        self._dead_providers: set[str] = set()
        self._stats: dict[str, RouterStats] = {}
        self._stats_lock = threading.Lock()
        self._elected: str = ""
        self._classifier = TinyClassifier()

    # ── Bootstrap from config ──

    @classmethod
    def from_config(cls) -> "TreeLLM":
        """Create a fully initialized TreeLLM from system config.

        Delegates to ProviderRegistry — the single source of truth.
        """
        llm = cls()
        try:
            from .provider_registry import register_all_providers
            register_all_providers(llm)

            logger.info(
                f"TreeLLM.from_config: {llm.provider_count} providers: "
                f"{list(llm._providers.keys())}"
            )

            # ── Model Registry: auto-discover latest model names ──
            try:
                from .model_registry import get_model_registry
                mr = get_model_registry()
                mr.load_cache()
                updated = 0
                for name, p in llm._providers.items():
                    pm = mr._providers.get(name)
                    if pm and pm.models:
                        flash = [m for m in pm.models if m.tier in ("flash", "small")]
                        candidates = flash or [m for m in pm.models if m.tier != "embedding"]
                        if candidates:
                            best = candidates[0]
                            # Set fallback models (all non-embedding)
                            p.fallback_models = [m.id for m in pm.models if m.tier != "embedding"]
                            if hasattr(p, 'default_model'):
                                old = p.default_model
                                p.default_model = best.id
                                if old != best.id:
                                    updated += 1
                                    logger.info(f"  {name}: model {old} → {best.id} ({best.tier})")
                if updated:
                    logger.info(f"ModelRegistry: updated {updated} provider models")
            except Exception as e:
                logger.debug(f"ModelRegistry: {e}")

            # ── LayerConfig: startup 3-layer provider loading ──
            try:
                from .sticky_election import get_layer_config
                self._layer_config = get_layer_config()
                asyncio.ensure_future(self._warm_embedding())
            except Exception as e:
                logger.debug(f"LayerConfig init: {e}")
            # Quick health check
            try:
                from .vital_signs import get_vital_signs
                vs = get_vital_signs()
                import asyncio as _a
                try:
                    _loop = _a.get_running_loop()
                except RuntimeError:
                    _loop = _a.new_event_loop()
                    report = _loop.run_until_complete(
                        _a.wait_for(vs.run_full_checkup(), timeout=10))
                    logger.info(f"VitalSigns: {report.summary}")
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"TreeLLM.from_config: {e}")

        return llm

    # ── Provider management ──

    def add_provider(self, provider: Provider) -> bool:
        """Add a provider. Returns True if new, False if name already exists (no-op)."""
        if provider.name in self._providers:
            return False
        self._providers[provider.name] = provider
        self._stats[provider.name] = RouterStats(provider=provider.name)
        return True

    @property
    def provider_count(self) -> int:
        return len(self._providers)

    def remove_provider(self, name: str) -> None:
        self._providers.pop(name, None)

    def get_provider(self, name: str) -> Provider | None:
        return self._providers.get(name)

    @property
    def provider_names(self) -> list[str]:
        """Return only layer-configured providers, not all 28."""
        try:
            from .sticky_election import get_layer_config
            cfg = get_layer_config()
            names = set()
            for i in range(3):
                p = cfg.get_provider(i)
                if p[0] and p[0] not in self._dead_providers:
                    names.add(p[0])
            if names:
                return list(names)
        except Exception:
            pass
        alive = [p for p in self._providers if p not in self._dead_providers]
        return alive[:3]

    # ── Routing ──

    async def elect(self, candidates: list[str] | None = None) -> str:
        """Elect best provider: holistic scoring (latency + quality + cost + capability)."""
        names = candidates or list(self._providers.keys())
        from .holistic_election import get_election
        election = get_election()

        # Holistic scoring
        free_models = []  # populated externally
        scored = await election.score_providers(names, self._providers, free_models)
        if scored:
            best = scored[0]
            self._elected = best.name
            logger.info(
                f"Elected {best.name}: "
                f"score={best.total:.2f} "
                f"latency={float(best.latency_ms or 0):.0f}ms "
                f"quality={best.scores.get('quality',0):.1%} "
                f"match={best.capability_match:.1%}"
            )
            return best.name

        self._elected = ""
        return ""

    async def smart_route(self, prompt: str, candidates: list[str] | None = None, task_type: str = "general") -> str:
        """Always route to layer-configured provider. No election."""
        from .sticky_election import get_layer_config
        from .three_model_intelligence import get_three_model_intelligence
        tmi = get_three_model_intelligence(self)
        triage = tmi.triage(prompt)
        cfg = get_layer_config()
        if triage.complexity >= 0.3:
            p = cfg.get_provider(2)
            return p[0] if p[0] else "deepseek"
        p = cfg.get_provider(1)
        return p[0] if p[0] else "deepseek"
        async def _ping_check(name):
            p = self._providers.get(name)
            if p:
                ok, _ = await p.ping()
                if ok:
                    return name
            return None
        results = await asyncio.gather(*[_ping_check(n) for n in names])
        alive = [r for r in results if r]

        if not alive:
            return ""

        if len(alive) == 1:
            return alive[0]

        # Step 1: TinyClassifier (fast, keyword-based)
        route = self._classifier.predict(prompt, alive, self._stats)
        if route and route in alive:
            score = self._classifier._last_score if hasattr(self._classifier, '_last_score') else 0.5
            if score > 0.3:  # High confidence → use classifier
                return route

        # Step 2: UnifiedSkillSystem (semantic, full-text based)
        try:
            from ..dna.unified_skill_system import get_skill_system
            router = get_skill_system()
            decision = router.route(prompt)
            for candidate in decision.providers:
                if candidate.name in alive:
                    return candidate.name
        except Exception as e:
            logger.warning("{}: {}".format("TreeLLM core", e))

        # Step 3: Fallback to best success rate
        best = max(alive, key=lambda n: self._stats.get(n, RouterStats(n)).success_rate)
        return best

    # ── Layered Dynamic Routing (Pattern 3) ──
    async def route_layered(
        self, query: str, candidates: list[str] | None = None,
        max_layers: int = 3, early_stop_threshold: float = 0.70,
        top_k_per_layer: int = 3, task_type: str = "general",
        aggregate: bool = False,
        deep_probe: bool = False,
        self_play: bool = False,
        model: bool = True,     # False = preprocess only (no LLM), for knowledge storage etc.
    ) -> dict[str, Any]:
        """Layered routing.

        When model=False: runs preprocessing only (stigmergy, DeepProbe, 
        MicroTurn, JointEvolution) without calling LLM — ~100ms for storage ops.
        """
        original_query = query

        # ── Fast-path: simple queries skip all preprocessing ──
        if self._is_simple_query(query):
            result = await self._fast_route(original_query, task_type)
            if result:
                return result

        # ── DeepProbe: cognitive forcing rewriter (reinstate original for display) ──
        probing_result: dict[str, Any] | None = None
        original_query = query

        # ── JointEvolution: start trajectory recording ──
        try:
            from .joint_evolution import get_joint_evolution
            je = get_joint_evolution()
            traj_id = je.start_trajectory(query=original_query, task_id=f"layered_{id(self)}",
                                          task_description=original_query[:200])
        except ImportError:
            je = None
            traj_id = ""

        # ── FluidCollective: inject stigmergic context ──
        stigmergy_ctx = ""
        try:
            from .fluid_collective import get_fluid_collective
            fc = get_fluid_collective()
            stigmergy_ctx = fc.retrieve_context(domain=task_type, max_traces=3)
            if stigmergy_ctx:
                query = stigmergy_ctx + "\n\n" + query
        except ImportError:
            pass

        # ── ProactiveInterject: check if we should interrupt instead of routing ──
        try:
            from .proactive_interject import get_proactive_interject
            pi = get_proactive_interject()
            decision = pi.evaluate(original_query, task_type=task_type)
            if decision.should_interject and decision.urgency > 0.5:
                return {
                    "provider": "interject", "result": decision.interjection_text,
                    "mode": "interject", "layers_used": 0,
                    "scores": {"final_decision": "interjected", "trigger": decision.trigger.value if decision.trigger else "unknown"},
                    "deep_probe": None, "micro_turn": None,
                    "stigmergy": False,
                }
        except ImportError:
            pass

        if deep_probe:
            try:
                from .deep_probe import get_deep_probe
                probe = get_deep_probe()
                # Chat queries: use depth=1 (light probe, don't over-structure)
                depth = 1 if task_type == "chat" else None
                result = probe.rewrite(query, task_type=task_type, depth=depth)
                query = result.rewritten
                probing_result = {
                    "original": result.original,
                    "strategies": [s.value for s in result.strategies_applied],
                    "probe_depth": result.probe_depth,
                    "expected_steps": result.expected_steps,
                    "anti_cache_seed": result.anti_cache_seed,
                }
                logger.info(
                    f"DeepProbe: [{task_type}] depth={result.probe_depth}, "
                    f"strategies={len(result.strategies_applied)}"
                )
            except Exception as e:
                logger.debug(f"DeepProbe skipped: {e}")

        # ── SurvivalMode: inject resource-aware routing hint ──
        try:
            from .survival_mode import get_survival_mode
            survival = get_survival_mode()
            hint = survival.routing_hint()
            if survival.current_level() > survival.FULL:
                top_k_per_layer = hint["top_k"]
                aggregate = hint["aggregate"]
                max_tokens_override = hint["max_tokens"]
                logger.debug(f"SurvivalMode: L{survival.current_level().name} → top_k={top_k_per_layer}")
        except Exception:
            pass

        # ── P→C→B Organ Health Modulation ──
        p_health = 1.0
        c_health = 1.0
        b_health = 1.0
        try:
            from .joint_evolution import get_joint_evolution
            jh = get_joint_evolution().get_health()
            p_health = jh.p_health
            c_health = jh.c_health
            b_health = jh.b_health
            # P体↓ (<0.4): 感知退步 → 用更多深度探测策略探索
            if p_health < 0.4:
                deep_probe = True
                probe_quality = "extra_deep"  # triggers more strategies
            # C体↓ (<0.4): 认知衰退 → 减少选举候选, 延长缓存TTL
            if c_health < 0.4:
                top_k_per_layer = max(1, top_k_per_layer - 1)
            # B体↓ (<0.4): 执行能力降级 → 跳过聚合, 直接用最佳结果
            if b_health < 0.4:
                aggregate = False
        except ImportError:
            pass

        # ── AdaptiveTopK: dynamically adjust candidates per query complexity ──
        if probing_result:
            complexity = probing_result.get("probe_depth", 2) / 3.0
        else:
            # Heuristic: query length + punctuation density as complexity proxy
            qlen = len(query)
            question_marks = query.count("?") + query.count("？")
            complexity = min(0.9, 0.3 + qlen / 800 + question_marks * 0.1)
        if complexity < 0.3:
            top_k_per_layer = 1
            aggregate = False
        elif complexity < 0.6:
            top_k_per_layer = 2
            aggregate = False
        elif complexity < 0.8:
            top_k_per_layer = 3
            aggregate = True
        else:
            top_k_per_layer = 4
            aggregate = True

        # ── MicroTurnAware: classify conversational state ──
        micro_turn_state: dict[str, Any] | None = None
        try:
            from .micro_turn_aware import get_micro_turn_aware
            mta = get_micro_turn_aware()
            ctx = mta.classify(original_query, time_since_last_input=0.5)
            micro_turn_state = {
                "state": ctx.current_state.value,
                "should_route_now": ctx.should_route_now,
                "should_probe_deep": ctx.should_probe_deep,
                "weave_opportunity": ctx.weave_opportunity,
                "conversation_rhythm": round(ctx.conversation_rhythm, 2),
                "optimal_response_delay_ms": ctx.optimal_response_delay_ms,
            }
            # If MicroTurnAware suggests deep probing, override
            if ctx.should_probe_deep and not deep_probe:
                deep_probe = True
            # If user is thinking (deliberative), enable aggregation for deeper answer
            if ctx.conversation_rhythm > 0.6 and not aggregate:
                aggregate = True
        except ImportError:
            pass

        # ── Fast path: preprocess only, no LLM ──
        if not model:
            # StrategicOrchestrator: decompose multi-step tasks
            try:
                from .strategic_orchestrator import get_orchestrator, TaskStep
                orch = get_orchestrator()
                step = TaskStep(id="routed", description=original_query)
                subgoals = orch.decompose_to_subgoals(step)
                if len(subgoals) >= 3:
                    return {
                        "provider": "orchestrator", "result": None, "mode": "decomposed",
                        "layers_used": 0,
                        "subgoals": [{"id": s.id, "desc": s.description, "criteria": s.completion_criteria} for s in subgoals],
                        "scores": {"final_decision": "decomposed_to_subgoals"},
                        "cost_saved": f"Task decomposed into {len(subgoals)} sub-goals",
                        "deep_probe": None, "micro_turn": None,
                        "stigmergy": bool(stigmergy_ctx),
                    }
            except ImportError:
                pass

            # Tool queries need LLM reasoning — force model=True if tools likely needed
            ql = query.lower()
            needs_tools = any(k in ql for k in ["搜索", "search", "查找", "计算", "文件", "画图"])
            if not needs_tools:
                return {
                "provider": "preprocess", "result": None, "mode": "preprocess",
                "layers_used": 0,
                "scores": {"final_decision": "preprocess_only"},
                "cost_saved": "Skipped LLM (~2min)",
                "deep_probe": probing_result,
                "micro_turn": micro_turn_state,
                "stigmergy": bool(stigmergy_ctx),
            }

        # ── Task Vector Geometry: ID vs OOD mode detection ──
        route_mode = "ood"  # default
        task_vector_id = None
        tv_similarity = 0.0
        tv_convex_dist = 0.0
        tv_cached_provider = None
        try:
            from ..dna.task_vector_geometry import get_task_geometry, text_to_embedding
            geo = get_task_geometry()
            q_embedding = text_to_embedding(query)
            decision = geo.classify(q_embedding, task_type)
            route_mode = decision.mode
            if route_mode == "id":
                task_vector_id = decision.nearest_vector_id
                tv_similarity = decision.similarity_score
                tv_convex_dist = decision.convex_hull_distance
                tv_cached_provider = decision.recommended_provider
                # If ID and we have a cached best provider, fast-path it
                if tv_cached_provider and tv_cached_provider in self._providers:
                    logger.debug(f"Task vector ID match: {tv_cached_provider} (similarity={tv_similarity:.2f})")
        except Exception as e:
            logger.debug(f"Task vector geometry skipped: {e}")

        # ── JointHealth: P→C→B organ-aware routing hints ──
        p_health = c_health = b_health = 0.5
        joint_score = 0.5
        try:
            from .joint_evolution import get_joint_evolution
            je = get_joint_evolution()
            h = je.joint_health()
            if h and h.total_trajectories > 0:
                p_health = max(h.p_health, 0.01)
                c_health = max(h.c_health, 0.01)
                b_health = max(h.b_health, 0.01)
                joint_score = h.score
        except Exception:
            pass

        # Prepare initial candidate list
        layer1_candidates = list(candidates) if candidates else list(self._providers.keys())
        if not layer1_candidates:
            return {
                "provider": "",
                "result": None,
                "layers_used": 0,
                "candidates_per_layer": {"layer1": [], "layer2": [], "layer3": []},
                "scores": {
                    "embedding_score": 0.0,
                    "election_score": 0.0,
                    "self_assessment": 0.0,
                    "final_decision": "fallback",
                },
                "cost_saved": "No providers available",
            }

        # Layer 1: Embedding pre-filter (optional)
        layer1_candidates_final = list(layer1_candidates)
        embedding_score = 0.0
        try:
            from .embedding_scorer import get_embedding_scorer
            scorer = get_embedding_scorer()
            if scorer and hasattr(scorer, "score_and_filter"):
                scored = scorer.score_and_filter(query, scorer._profiles)
                if isinstance(scored, list) and scored:
                    real_candidates = set(layer1_candidates)
                    valid_scores = [(n, s) for n, s in scored if n in real_candidates]
                    if valid_scores:
                        valid_scores.sort(key=lambda t: -t[1])
                        layer1_candidates_final = [n for n, _ in valid_scores[:top_k_per_layer]]
                        embedding_score = valid_scores[0][1] if valid_scores else 0.0
        except Exception:
            pass
        layer1_candidates_final = list(dict.fromkeys(layer1_candidates_final))

        # ── Foresight placeholder ──
        foresight_insights: dict[str, Any] = {}

        # Layer 2: Election scoring (via unified ElectionBus)
        layer2_candidates: list[str] = []
        election_score = 0.0
        election = None
        try:
            from .election_bus import get_election_bus
            bus = get_election_bus()
            scores = await bus.get_scores(self._providers, [], task_type=task_type)
            if scores:
                election = get_election()
                layer2_scores = [(s.name, float(s.total)) for s in scores]
                layer2_scores.sort(key=lambda t: -t[1])
                top2 = layer2_scores[:top_k_per_layer]
                election_score = float(top2[0][1]) if top2 else 0.0
                layer2_candidates = [p for p, _ in top2]
        except Exception:
            layer2_candidates = layer1_candidates_final[:top_k_per_layer]

        # ── Organ-aware adjustment ──
        if c_health < 0.3 and len(layer2_candidates) > 1:
            layer2_candidates = layer1_candidates_final[:max(1, len(layer2_candidates) - 1)]
        if p_health < 0.3 and len(layer1_candidates_final) > len(layer2_candidates):
            layer2_candidates = list(dict.fromkeys(layer2_candidates + [layer1_candidates_final[-1]]))
        skip_aggregation = b_health < 0.3

        # Layer 3: Inference + self-assessment (parallel candidates, early-stop)
        final_provider = None
        final_result = None
        layers_used = 2 if layer2_candidates else 1
        self_assessment_score = 0.0
        l3_results: dict[str, Any] = {}  # Store results for aggregation reuse
        if layer2_candidates:
            candidates_to_try = layer2_candidates[:top_k_per_layer]
            task_map: dict[asyncio.Task, str] = {}
            for c in candidates_to_try:
                task = asyncio.ensure_future(
                    self.chat([{"role": "user", "content": query}], provider=c)
                )
                task_map[task] = c
            task_set = set(task_map.keys())
            l3_early_stop = False
            while task_set and not l3_early_stop:
                done, task_set = await asyncio.wait(
                    task_set, timeout=None, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    candidate = task_map.get(task, "")
                    try:
                        res = task.result()
                        text = None
                        if isinstance(res, ProviderResult):
                            text = getattr(res, "text", None) or getattr(res, "content", None)
                        elif isinstance(res, dict):
                            text = res.get("text") or res.get("content") or res.get("output")
                        elif isinstance(res, str):
                            text = res
                        else:
                            text = str(res)

                        if text:
                            l3_results[candidate] = res  # Cache for aggregation reuse
                            assessment = None
                            if election is not None:
                                try:
                                    assessment = election.self_assess(text)
                                except Exception:
                                    assessment = None
                            if isinstance(assessment, (int, float)):
                                sa_score = float(assessment)
                            elif isinstance(assessment, dict) and 'score' in assessment:
                                try:
                                    sa_score = float(assessment.get('score', 0.0))
                                except Exception:
                                    sa_score = 0.0
                            else:
                                sa_score = 0.0
                            self_assessment_score = max(self_assessment_score, sa_score)
                            if sa_score > early_stop_threshold:
                                final_provider = candidate
                                final_result = res
                                layers_used = 3
                                l3_early_stop = True
                                for t in task_set:
                                    t.cancel()
                                break
                    except Exception as e:
                        logger.warning("{}: {}".format("TreeLLM core", e))

            if final_provider is None and layer2_candidates:
                final_provider = layer2_candidates[0]
                final_result = await self.chat([{"role": "user", "content": query}], provider=final_provider)
                layers_used = 3
            elif layer1_candidates_final:
                final_provider = layer1_candidates_final[0]
                final_result = await self.chat([{"role": "user", "content": query}], provider=final_provider)
                layers_used = 1
                # Run self-assessment on fallback result
                if final_result:
                    try:
                        from .holistic_election import get_election
                        election = get_election()
                        if hasattr(final_result, 'text') and final_result.text:
                            sa = election.self_assess(final_result.text)
                            self_assessment_score = float(sa)
                    except Exception:
                        pass

        # ── Layer 4: Smart fallback with local LLM guarantee ──
        l4_provider = None
        l4_result = None

        if final_provider is None or final_result is None:
            # Combine remaining providers + local candidates in single fast loop
            remaining = [p for p in self._providers.keys()
                         if p not in (layer2_candidates or [])]
            local_keywords = ("local", "offline", "ollama", "opencode", "serve", "llama")
            # Local-first: prioritize local models, then remaining
            fallback_order = sorted(
                remaining,
                key=lambda n: (0 if any(k in n.lower() for k in local_keywords) else 1, n),
            )[:5]  # Cap at 5 to avoid excessive retries

            for candidate in fallback_order:
                try:
                    res = await asyncio.wait_for(
                        self.chat([{"role": "user", "content": query}], provider=candidate),
                        timeout=15.0,  # Fast-fail per fallback
                    )
                    if res and (getattr(res, "text", None) or getattr(res, "content", None)):
                        l4_provider = candidate
                        l4_result = res
                        layers_used = 4
                        break
                except (asyncio.TimeoutError, Exception) as e:
                    logger.warning(f"TreeLLM L4: {candidate} fallback failed ({e})"[:120])
                    continue

        if l4_provider and l4_result:
            final_provider = l4_provider
            final_result = l4_result

        # ── SynapseAggregator: multi-model reasoning fusion ──
        synapse_result: dict[str, Any] | None = None
        if aggregate and final_result and final_provider and not skip_aggregation:
            try:
                aggregator = get_synapse_aggregator()
                agg_outputs: list[ModelOutput] = []
                # Reuse Layer 3 results to avoid duplicate LLM calls
                for candidate, res in l3_results.items():
                    if candidate == final_provider:
                        continue
                    text = ""
                    if isinstance(res, ProviderResult):
                        text = getattr(res, "text", "") or getattr(res, "content", "") or ""
                    elif isinstance(res, dict):
                        text = res.get("text") or res.get("content") or ""
                    elif isinstance(res, str):
                        text = res
                    if text:
                        agg_outputs.append(ModelOutput(
                            provider=candidate,
                            text=text,
                            tokens=getattr(res, "tokens", 0) if hasattr(res, "tokens") else len(text),
                            election_score=self._stats.get(candidate, RouterStats(candidate)).success_rate,
                        ))

                # Add the main result as primary output
                main_text = ""
                if isinstance(final_result, ProviderResult):
                    main_text = getattr(final_result, "text", "") or ""
                elif isinstance(final_result, dict):
                    main_text = final_result.get("text") or final_result.get("content") or ""
                elif isinstance(final_result, str):
                    main_text = final_result
                if main_text:
                    agg_outputs.insert(0, ModelOutput(
                        provider=final_provider,
                        text=main_text,
                        tokens=getattr(final_result, "tokens", 0) if hasattr(final_result, "tokens") else len(main_text),
                        election_score=self._stats.get(final_provider, RouterStats(final_provider)).success_rate,
                    ))

                if len(agg_outputs) >= 2:
                    agg_result = await aggregator.aggregate(
                        outputs=agg_outputs, query=query, task_type=task_type,
                    )
                    synapse_result = {
                        "aggregated_text": agg_result.aggregated_text,
                        "method": agg_result.method,
                        "consensus_level": agg_result.consensus_level,
                        "contributions": agg_result.contributions,
                        "grounded_in": agg_result.grounded_in,
                        "conflict_resolutions": agg_result.conflict_resolutions,
                    }
                    logger.info(
                        f"SynapseAggregator: fused {len(agg_outputs)} models "
                        f"via '{agg_result.method}' (consensus={agg_result.consensus_level:.2f})"
                    )
            except Exception as e:
                logger.warning(f"SynapseAggregator integration: {e}")

        return {
            "provider": final_provider or "",
            "result": final_result,
            "mode": route_mode,
            "layers_used": layers_used,
            "candidates_per_layer": {
                "layer1": layer1_candidates_final,
                "layer2": layer2_candidates,
                "layer3": [final_provider] if final_provider else [],
                "layer4": [l4_provider] if l4_provider else [],
            },
            "scores": {
                "embedding_score": embedding_score,
                "election_score": election_score,
                "self_assessment": float(self_assessment_score),
                "final_decision": "early_stop" if final_result and self_assessment_score > early_stop_threshold else "fallback",
            },
            "task_vector": {
                "mode": route_mode,
                "vector_id": task_vector_id,
                "similarity": tv_similarity,
                "convex_hull_distance": tv_convex_dist,
                "cached_provider": tv_cached_provider,
            },
            "cost_saved": "Used layering providers (embedded scoring + alive ping)",
            "foresight": foresight_insights,
            "synapse": synapse_result,
            "deep_probe": probing_result,
            "micro_turn": micro_turn_state,
            "stigmergy": bool(stigmergy_ctx),
        }

    def route_layered_sync(self, query: str, **kwargs) -> dict[str, Any]:
        """Synchronous wrapper for route_layered."""
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.route_layered(query, **kwargs))



    # ── Chat ──

    async def chat(self, messages: list[dict], provider: str = "",
                   temperature: float = 0.7, max_tokens: int = 4096,
                   timeout: int = 120, model: str = "", tools: bool = False,
                   accelerate: str = "", **kwargs) -> ProviderResult:
        p = self._resolve_provider(provider)

        # ── Acceleration fast-path (bypasses layered routing) ──
        if accelerate and not provider:
            try:
                from .acceleration import get_accelerator
                accel = get_accelerator(self)
                result = await accel.chat(messages, prefer=accelerate,
                                         temperature=temperature,
                                         max_tokens=max_tokens, tools=tools)
                if result and result.text:
                    return ProviderResult(text=result.text, provider=result.provider,
                                         success=True, elapsed_ms=result.elapsed_ms)
                
                # Speculative decoding fallback
                from .innovation import get_innovation_engine
                inn = get_innovation_engine(self)
                spec = await inn.speculative_chat(messages, draft_k=4)
                if spec and spec.text and spec.speedup > 1.2:
                    return ProviderResult(text=spec.text, provider=spec.verifier,
                                         success=True, elapsed_ms=spec.elapsed_ms)
            except Exception:
                pass

        if not p:
            return ProviderResult.empty(f"No provider: {provider}")

        # ── Cross-provider KV tail migration ──
        # When switching providers, carry minimal context (~500 tokens).
        # This avoids sending full conversation history to each provider.
        if kwargs.get("previous_provider") and kwargs.get("previous_provider") != provider:
            try:
                kvc = get_segmented_compressor()
                kv_state = kvc.extract_tail(kwargs.get("previous_messages", messages[:-1]))
                if kv_state.get("tail_text"):
                    kv_msg = {"role": "system",
                              "content": f"[context from {kwargs['previous_provider']}]\n{kv_state['tail_text']}"}
                    messages = [kv_msg] + messages[-3:]
            except Exception:
                pass

        # ── SegmentedKVCompressor: segment-level compression (TBPTT K=1) ──
        # Uses fixed-size KV tail instead of full-summary compression.
        # Falls back to legacy SessionCompressor if SegmentedKV not available.
        if len(messages) > 10:
            try:
                comp = get_segmented_compressor()
                messages = await comp.compress(messages, max_tokens=max_tokens,
                                               chat_fn=self.chat)
            except Exception:
                try:
                    comp = get_session_compressor()
                    messages = await comp.compress(messages, max_tokens=max_tokens,
                                                   chat_fn=self.chat)
                except Exception:
                    pass

        # ── Identity: inject 小树 persona + constitution as FIRST system message ──
        if not any(m.get("role") == "system" for m in messages):
            try:
                from ..dna.identity import get_identity_prompt
                messages = [{"role": "system", "content": get_identity_prompt()}] + messages
            except Exception:
                pass

        # ── Three-Model Triage: vector → L1 coach → L2 reasoning ──
        task_type = kwargs.get("task_type", "general")
        # Auto-detect code tasks from query content
        code_keywords = ["代码", "函数", "模块", "架构", "调用", "依赖",
                         "code", "def ", "class ", "import ", ".py", "重构",
                         "bug", "错误", "修复", "优化性能"]
        if any(kw in user_text.lower() for kw in code_keywords):
            task_type = "code"
        use_l2 = False
        triage = None
        try:
            from .three_model_intelligence import get_three_model_intelligence
            tmi = get_three_model_intelligence(self)
            user_text = messages[-1].get("content", "") if messages else ""
            if isinstance(user_text, list):
                user_text = " ".join(p.get("text", "") for p in user_text if isinstance(p, dict))
            triage = tmi.triage(user_text)
            emotion = tmi._detect_emotion(user_text)

            if triage.complexity >= 0.3:
                use_l2 = True
                from .sticky_election import get_layer_config
                l2 = get_layer_config().get_provider(2)
                provider = l2[0] if l2[0] else "deepseek"
                # L1 coach optimizes prompt for L2
                try:
                    from .prompt_coach import PromptCoach
                    coach = PromptCoach(self)
                    domain = "code" if task_type == "code" else (
                        "analysis" if triage.complexity > 0.6 else "general")
                    coaching = await coach.coach(user_text, domain=domain)
                    if coaching.get("meta_prompt") and coaching["meta_prompt"] != user_text:
                        messages[-1]["content"] = coaching["meta_prompt"]
                except Exception:
                    pass
                # Adjust for deep reasoning
                if not kwargs.get("max_tokens"):
                    kwargs["max_tokens"] = 4096
                if not kwargs.get("temperature"):
                    kwargs["temperature"] = 0.3
            else:
                from .sticky_election import get_layer_config
                l1 = get_layer_config().get_provider(1)
                provider = l1[0] if l1[0] else "deepseek"
                # Fast response params
                if not kwargs.get("max_tokens"):
                    kwargs["max_tokens"] = 1024
                if not kwargs.get("temperature"):
                    kwargs["temperature"] = 0.7
                # Emotion modulation for L1
                tone = emotion.tone_modifier()
                if tone:
                    sys_idx = next((i for i, m in enumerate(messages) if m.get("role") == "system"), 0)
                    if sys_idx < len(messages):
                        messages[sys_idx]["content"] = tone + "\n\n" + messages[sys_idx]["content"]
        except Exception:
            pass

        # ── OntoPromptBuilder: inject domain knowledge from ontology graph ──
        if use_l2:
            try:
                from .onto_prompt_builder import get_onto_prompt_builder
                onto = get_onto_prompt_builder()
                onto_result = onto.build_prompt(user_text if user_text else (
                    messages[-1].get("content", "") if messages else ""))
                if onto_result.get("concept_chain"):
                    chain_text = " | ".join(onto_result["concept_chain"][:10])
                    sys_idx = next((i for i, m in enumerate(messages) if m.get("role") == "system"), 0)
                    messages[sys_idx]["content"] += f"\n\n[Knowledge Domain: {chain_text}]"
            except Exception:
                pass

        # ── AutoPrompt + PromptEngine: inject optimized system prompt ──
        try:
            prompt_text, _ = get_auto_prompt().select(task_type)
            if prompt_text:
                sys_idx = next((i for i, m in enumerate(messages) if m.get("role") == "system"), None)
                if sys_idx is not None:
                    messages[sys_idx]["content"] += "\n\n" + prompt_text
                else:
                    messages = [{"role": "system", "content": prompt_text}] + messages
        except Exception:
            pass

        # ── CodeContext removed: LLM uses codegraph tools on demand ──
        # Codegraph tools (deps/callers/callees/impact) are available
        # via <tool_call> — LLM queries exactly what it needs, zero waste.

        # ── Disable thinking for short queries ──
        if max_tokens < 800 and hasattr(p, 'pro_thinking_enabled'):
            p.pro_thinking_enabled = False

        provider_name = p.name if p else ""

        # ── LatencyOracle: adaptive timeout per provider ──
        try:
            oracle = get_latency_oracle()
            complexity = kwargs.get("complexity", 0.5)
            predicted, viable = oracle.predict(provider_name, complexity)
            if not viable:
                logger.debug(f"LatencyOracle: skipping {provider_name} (pred={predicted}ms > timeout)")
                return ProviderResult.empty(f"LatencyOracle: {provider_name} predicted {predicted:.0f}ms > timeout")
            adaptive_timeout = oracle.smart_timeout(provider_name, complexity)
            if adaptive_timeout < timeout:
                timeout = adaptive_timeout
        except Exception:
            pass

        # ── Tool-calling: inject system instructions ──
        # Auto-enable tools when available_tools are provided
        if not tools and kwargs.get("available_tools"):
            tools = True
        if tools and messages:
            # Dynamic tool prompt from CapabilityBus + hardcoded essentials
            dynamic_tools = ""
            try:
                bus = get_capability_bus()
                dynamic_tools = bus.prompt_fragment_sync(["tool", "skill", "mcp"])
            except Exception:
                pass

            messages = [{
                "role": "system",
                "content": (
                    "## Output Format Specification\n\n"
                    "Structure your response using these markers. The frontend renders each marker as a specific UI component.\n\n"
                    "### Task Plan (multi-step checklist with progress)\n"
                    "When decomposing a task into multiple steps, output a plan:\n"
                    "<plan>\n<step id=\"1\" label=\"Scan codebase\"/>\n<step id=\"2\" label=\"Analyze hotspots\"/>\n<step id=\"3\" label=\"Generate report\"/>\n</plan>\n"
                    "The frontend shows: progress bar, step status (pending→running→done), auto-collapse on completion.\n"
                    "Update step status by emitting <step id=\"N\" status=\"done\"/> after each step completes.\n\n"
                    "### Thinking (collapsible reasoning)\n"
                    "Wrap chain-of-thought in tags. Collapsed by default in UI:\n"
                    "<thinking>\nyour step-by-step reasoning here\n</thinking>\n\n"
                    "### Tool Calls (expandable execution blocks)\n"
                    "Use XML format with explicit arguments:\n"
                    "<tool_call name=\"tool_name\">\narguments here\n</tool_call>\n"
                    "After each tool execution, the result appears in an expandable block.\n"
                    "The frontend shows: tool name, status (pending→running→done/error), execution time.\n\n"
                    "### Interactive Questions (user choice required)\n"
                    "When you need user input before continuing, use:\n"
                    "<ask type=\"confirm|select|input\" label=\"question text\">\n"
                    "  <option value=\"yes\" label=\"Yes\" selected/>\n"
                    "  <option value=\"no\" label=\"No\"/>\n"
                    "</ask>\n"
                    "For tab-style selection:\n"
                    "<ask type=\"tabs\" label=\"Choose action:\">\n"
                    "  <tab id=\"scan\" label=\"Scan Code\"/> <tab id=\"learn\" label=\"Learn\"/>\n"
                    "</ask>\n\n"
                    "### Visual Components (charts, diagrams, UI)\n"
                    "For data visualization or UI components, output A2UI JSON:\n"
                    '{"type":"tailwind","tailwind":{"component":"Card|Table|Alert|Badge|Button|Form|StatGrid","props":{...}}}\n'
                    '{"type":"chart","chart":{"type":"bar|line|pie|scatter","data":{...}}}\n'
                    '{"type":"diagram","diagram":{"engine":"mermaid","code":"graph LR\\n A-->B"}}\n\n'
                    "### Format Rules\n"
                    "1. Always separate thinking from final answer with </thinking>\n"
                    "2. Tool calls must be complete XML blocks on their own line\n"
                    "3. JSON blocks must be valid, balanced JSON on their own line\n"
                    "4. Text outside markers is rendered as normal markdown\n"
                    f"{dynamic_tools}\n"
                    "Core tools always available:\n"
                    "- web_search: search the internet. Args: query text.\n"
                    "- search_apis: find available APIs by category or keyword. Args: query category.\n"
                    "- call_api: call a specific web API. Args: api_name, then params as key=value pairs.\n"
                    "- kb_search: search internal knowledge base. Args: query text.\n"
                    "- bash: run a shell command. Args: command string.\n"
                    "- read_file: read a file via VFS. Supports paths: /disk/... /ram/... /cache/... /db/... /config/...\n"
                    "- write_file: write to a file via VFS. Args: file_path\\ncontent.\n"
                    "- codegraph_deps: query dependency graph. Args: module name. Returns dependencies.\n"
                    "- codegraph_callers: query call graph. Args: function name. Returns callers.\n"
                    "- codegraph_callees: query call graph. Args: function name. Returns callees.\n"
                    "- codegraph_update: re-index changed files (hash-based incremental). Use after code changes.\n"
                    "- codegraph_impact: query impact analysis. Args: file path. Returns blast radius.\n"
                    "- list_dir: list directory with file sizes. Args: path.",
                    "- grep_code: search codebase for pattern. Args: pattern [path] [glob].",
                    "- git_status: show working tree status.",
                    "- git_diff: show changes. Args: [file].",
                    "- git_commit: stage all and commit. Args: message.",
                    "- git_push: push to remote.",
                    "- git_branch: branch list|create|switch <name>.",
                    "- run_test: run pytest. Args: [test_path].",
                    "- browser_fetch: open URL in headless browser. Args: url [task].",
                    "- notify_slack: send Slack message. Args: message [channel].",
                    "- notify_feishu: send Feishu message. Args: message.",
                    "- notify_dingtalk: send DingTalk message. Args: message.\n"
                    "  For new files: output complete code with line structure.\n"
                    "  For modifications: output unified diff format with +/- markers.\n"
                    "VFS mounts: /ram(in-memory) /cache(LRU) /disk(local) /db(SQLite) /config(JSON)\n\n"
                    "When the user asks for a chart, diagram, or visualization, output in A2UI JSON format:\n"
                    '  Chart:  {"type":"chart","chart":{"type":"bar|line|pie|scatter","data":{"labels":[...],"datasets":[{"data":[...]}]}}}\n'
                    '  Diagram: {"type":"diagram","diagram":{"engine":"mermaid","code":"graph LR\\n  A-->B"}}\n'
                    '  SVG:    {"type":"svg","svg":"<svg>...</svg>"}\n'
                    '  Table:  {"type":"table","columns":["A","B"],"rows":[[1,2]]}\n'
                    '  UI:     {"type":"tailwind","tailwind":{"component":"Card|Table|Alert|Button|Form|Tabs|Page","props":{...}}}\n'
                    '  Card:   {"component":"Card","props":{"title":"标题","children":["<p>内容</p>"],"accent":"blue|green|red"}}\n'
                    '  Alert:  {"component":"Alert","props":{"message":"消息","level":"info|success|warning|error"}}\n'
                    '  Page:   {"component":"Page","props":{"title":"页面标题","children":["..."],"navbar":"..."}}\n'
                    "After tool results, continue your reasoning. You may call multiple tools.\n\n"
                    "## When to use which tool:\n"
                    "- web_search: general questions, news, facts, research topics → broad internet search\n"
                    "- search_apis: need structured data (weather, finance, maps, translation) → find specific APIs\n"
                    "- call_api: found the right API via search_apis → call it with specific params\n"
                    "- kb_search: internal documents, past reports, knowledge base → local search\n"
                    "- bash: file operations, code execution, system commands → terminal access\n"
                ),
            }] + messages
        from .cache_director import get_cache_director
        director = get_cache_director()
        if director.supports_cache(provider_name):
            messages = director.prepare(messages, provider_name)

        # ── Session binding: inject transition context if model switched ──
        sid = kwargs.get("session_id", f"session_{id(self)}")
        sb = get_session_binding()
        old_model = sb.get_session(sid).bound_model
        if old_model and old_model != provider_name:
            ctx = sb.transition_context(sid, old_model, provider_name)
            messages = [{"role": "system", "content": ctx}] + messages

        t0 = time.monotonic()
        result = None
        try:
            result = await p.chat(messages, temperature=temperature,
                                  max_tokens=max_tokens, timeout=timeout,
                                  model=model or kwargs.get("model_extra", ""))
            # Handle thinking mode: when text is empty but reasoning exists
            if result and not result.text and result.reasoning:
                result.text = result.reasoning

            # ── Multi-turn tool-calling loop (XML + JSON + OpenAI formats) ──
            MAX_TOOL_TURNS = 5
            tool_turn = 0
            while result and result.text and tool_turn < MAX_TOOL_TURNS:
                # Parse all three tool call formats with unified parser
                tool_calls = parse_tool_calls(result.text)
                if not tool_calls:
                    # Tool search instruction: LLM can search before calling
                    if tool_turn == 0 and any(k in result.text.lower() for k in ["搜索工具", "search_tool", "list_tools"]):
                        try:
                            bus = get_capability_bus()
                            caps = bus.prompt_fragment_sync(["tool"])
                            result.text = f"[Available tools]\n{caps}\n\nChoose a tool and call it."
                            tool_turn += 1
                            continue
                        except Exception:
                            pass
                    break
                tool_turn += 1
                tool_results = []
                for tool_name, tool_args in tool_calls[:3]:
                    tool_result_text = ""
                    try:
                        # Tier 1: Route through unified CapabilityBus (core tools)
                        bus = get_capability_bus()
                        cap_id = f"tool:{tool_name}"
                        result = await bus.invoke(cap_id, input=tool_args.strip())
                        if isinstance(result, dict) and "error" in result:
                            # Tier 2: Try MCP/local tools (LocalToolBus — zero overhead)
                            mcp_id = f"mcp:{tool_name}"
                            mcp_result = await bus.invoke(mcp_id, **self._unpack_tool_args(tool_name, tool_args))
                            if isinstance(mcp_result, dict) and "error" in mcp_result:
                                # Tier 3: Fallback to ReactExecutor legacy tools
                                from ..execution.react_executor import ReactExecutor
                                rex = ReactExecutor()
                                if tool_name == "web_search":
                                    tool_result_text = await rex._tool_web_search(tool_args.strip())
                                elif tool_name == "kb_search":
                                    tool_result_text = await rex._tool_kb_search(tool_args.strip())
                                elif tool_name in ("bash", "shell", "run_command", "execute"):
                                    tool_result_text = await rex._tool_run_command(tool_args.strip())
                                elif tool_name in ("read_file", "file_read"):
                                    tool_result_text = await self._tool_read_vfs(tool_args.strip())
                                elif tool_name in ("write_file", "file_write"):
                                    tool_result_text = await self._tool_write_vfs(tool_args.strip())
                                elif tool_name == "explore_domain":
                                    tool_result_text = await rex._tool_explore_domain(tool_args.strip())
                                elif tool_name == "get_world_knowledge":
                                    tool_result_text = await rex._tool_get_world_knowledge(tool_args.strip())
                                elif tool_name == "codegraph_update":
                                    from .codegraph_tools import codegraph_update
                                    tool_result_text = codegraph_update()
                                elif tool_name == "codegraph_deps":
                                    from .codegraph_tools import codegraph_deps
                                    tool_result_text = codegraph_deps(tool_args.strip())
                                elif tool_name == "codegraph_callers":
                                    from .codegraph_tools import codegraph_callers
                                    tool_result_text = codegraph_callers(tool_args.strip())
                                elif tool_name == "codegraph_callees":
                                    from .codegraph_tools import codegraph_callees
                                    tool_result_text = codegraph_callees(tool_args.strip())
                                elif tool_name == "codegraph_impact":
                                    from .codegraph_tools import codegraph_impact
                                    tool_result_text = codegraph_impact(tool_args.strip())
                                elif tool_name == "list_dir":
                                    from .developer_tools import list_dir
                                    tool_result_text = list_dir(tool_args.strip() or ".")
                                elif tool_name == "grep_code":
                                    from .developer_tools import grep_code
                                    parts = tool_args.strip().split(maxsplit=1)
                                    pattern = parts[0] if parts else ""
                                    rest = parts[1] if len(parts) > 1 else ""
                                    tool_result_text = grep_code(pattern, rest or ".", "*.py")
                                elif tool_name == "git_status":
                                    from .developer_tools import git_status
                                    tool_result_text = git_status()
                                elif tool_name == "git_diff":
                                    from .developer_tools import git_diff
                                    tool_result_text = git_diff(tool_args.strip())
                                elif tool_name == "git_commit":
                                    from .developer_tools import git_commit
                                    tool_result_text = git_commit(tool_args.strip())
                                elif tool_name == "git_push":
                                    from .developer_tools import git_push
                                    tool_result_text = git_push()
                                elif tool_name == "git_branch":
                                    from .developer_tools import git_branch
                                    parts = tool_args.strip().split(maxsplit=1)
                                    action = parts[0] if parts else "list"
                                    name = parts[1] if len(parts) > 1 else ""
                                    tool_result_text = git_branch(action, name)
                                elif tool_name == "run_test":
                                    from .developer_tools import run_test
                                    tool_result_text = run_test(tool_args.strip() or "tests/")
                                elif tool_name == "browser_fetch":
                                    from .developer_tools import browser_fetch
                                    parts = tool_args.strip().split(maxsplit=1)
                                    url = parts[0] if parts else ""
                                    task = parts[1] if len(parts) > 1 else "extract content"
                                    tool_result_text = await browser_fetch(url, task)
                                elif tool_name in ("notify_slack", "notify_feishu", "notify_dingtalk"):
                                    from .developer_tools import getattr as _dt_get
                                    fn = _dt_get(__import__("livingtree.treellm.developer_tools", fromlist=[tool_name]), tool_name)
                                    tool_result_text = fn(tool_args.strip())
                                else:
                                    tool_result_text = f"[tool:{tool_name}] not available"
                            else:
                                tool_result_text = json.dumps(mcp_result, default=str, ensure_ascii=False)[:5000]
                        else:
                            tool_result_text = str(result)[:5000]
                    except Exception as e:
                        tool_result_text = f"[tool:{tool_name} error: {e}]"
                    tool_results.append((tool_name, tool_result_text[:5000]))

                if not tool_results:
                    break

                # Build tool result messages for next LLM call
                tool_messages = []
                for tname, tresult in tool_results:
                    result.text = result.text.replace(
                        f'<tool_call name="{tname}">', '', 1
                    ).replace('</tool_call>', '', 1)
                    tool_messages.append({
                        "role": "tool",
                        "tool_name": tname,
                        "content": tresult,
                    })

                # Call LLM again with tool results
                messages_with_tools = list(messages) + [{"role": "assistant", "content": result.text}] + tool_messages
                result = await p.chat(messages_with_tools, temperature=temperature,
                                       max_tokens=max_tokens, timeout=timeout,
                                       model=model or kwargs.get("model_extra", ""))
                if result and result.text:
                    result.text = f"[tool_result: {tool_results[-1][0]}]\n{tool_results[-1][1]}\n\n{result.text}"
            if result and result.text:
                self._record_success(p.name, result.tokens, (time.monotonic() - t0) * 1000)
                # ── Gap Orchestrator: detect and fill knowledge/tool gaps ──
                try:
                    from .gap_orchestrator import GapOrchestrator
                    orchestrator = GapOrchestrator()
                    gap = await orchestrator.handle_gap(
                        str(messages[-1].get("content", ""))[:200],
                        result.text,
                    )
                    if gap.resolved and gap.enriched_query:
                        # Retry with enriched context
                        retry_messages = [{"role": "system",
                            "content": f"[Enriched context from {gap.resolution_method}]\n{gap.enriched_query[:2000]}"}] + messages
                        retry_result = await p.chat(retry_messages, temperature=temperature,
                            max_tokens=max_tokens, timeout=timeout, model=model or kwargs.get("model_extra", ""))
                        if retry_result and retry_result.text:
                            result = retry_result
                            logger.info(f"GapOrchestrator: retry succeeded via {gap.resolution_method}")
                except Exception:
                    pass
                # ── Recording capture: LLM response ──
                try:
                    get_recording_engine().capture(
                        RecordLayer.LLM, "llm_chat",
                        params={"messages": str(messages)[:500], "provider": p.name, "tokens": result.tokens},
                        result=result.text[:5000], render="stream",
                        duration_ms=(time.monotonic() - t0) * 1000,
                    )
                except Exception:
                    pass
                self._classifier.learn(prompt=str(messages[-1].get("content", ""))[:200],
                                        chosen=p.name, success=True)
                # ── Record session binding ──
                sb.bind(sid, p.name)
                # ── Record cache performance ──
                if result.prompt_tokens:
                    from .cache_director import get_cache_director
                    get_cache_director().record(
                        p.name, result.prompt_tokens,
                        result.cache_hit_tokens,
                    )
                # ── Activity feed + trust scoring ──
                try:
                    from ..observability.activity_feed import get_activity_feed
                    from ..core.system_health import get_trust_scorer
                    feed = get_activity_feed()
                    feed.election(p.name, 1.0, f"{result.tokens}t")
                    ts = get_trust_scorer()
                    ts.record(p.name, success=True, latency_ms=(time.monotonic() - t0) * 1000)
                except Exception as e:
                    logger.warning("{}: {}".format("TreeLLM core", e))
            elif result and (result.error or result.rate_limited):
                self._record_failure(p.name, result.error, rate_limited=result.rate_limited)
            return result or ProviderResult.empty("No result")
        except Exception as e:
            self._record_failure(p.name, str(e), rate_limited=getattr(result, 'rate_limited', False))
            return ProviderResult.empty(str(e))

    async def stream(self, messages: list[dict], provider: str = "",
                     temperature: float = 0.3, max_tokens: int = 4096,
                     timeout: int = 120) -> AsyncIterator[str]:
        p = self._resolve_provider(provider)
        if not p:
            yield f"[No provider: {provider}]"
            return

        # ── Token optimization ──
        messages = self._optimize_messages(messages)

        t0 = time.monotonic()
        tokens = 0
        try:
            async for token in p.stream(messages, temperature=temperature,
                                         max_tokens=max_tokens, timeout=timeout):
                tokens += 1
                yield token
            self._record_success(p.name, tokens, (time.monotonic() - t0) * 1000)
        except Exception as e:
            self._record_failure(p.name, str(e))
            yield f"\n[Error: {e}]"

    # ── Stats ──

    def get_stats(self) -> dict:
        return {
            name: {
                "calls": s.calls, "success_rate": s.success_rate,
                "avg_latency_ms": s.avg_latency_ms, "total_tokens": s.total_tokens,
                "last_error": s.last_error[:80] if s.last_error else "",
            }
            for name, s in self._stats.items()
        }

    def _optimize_messages(self, messages: list[dict]) -> list[dict]:
        """Apply token optimizations: HTML cleaning + URL shortening + prefix caching."""
        # Fast path: skip optimization for clean text content
        needs_html = any('<' in str(m.get("content", ""))
                         and '>' in str(m.get("content", "")) for m in messages)
        needs_url = any('http' in str(m.get("content", "")) for m in messages)
        if not needs_html and not needs_url:
            return messages

        if not hasattr(self, '_html_tag'):
            self._html_tag = re.compile(r'<[^>]+>')
            self._long_url = re.compile(r'https?://[^\s]{50,}')
            self._url_host = re.compile(r'https?://([^/]+)')
            self._optimize_cache: dict[str, list[dict]] = {}

        import hashlib, json
        cache_key = hashlib.sha256(
            json.dumps([m.get("content", "") for m in messages], sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        if cache_key in self._optimize_cache:
            return self._optimize_cache[cache_key]

        for msg in messages:
            content = str(msg.get("content", ""))
            if not content:
                continue
            if '<' in content and '>' in content:
                content = self._html_tag.sub(' ', content)
            content = self._long_url.sub(
                lambda m: '[link:' + (self._url_host.search(m.group(0)).group(1)
                                       if self._url_host.search(m.group(0)) else 'url') + ']',
                content
            )
            msg["content"] = content

        if len(self._optimize_cache) > 32:
            self._optimize_cache.clear()
        self._optimize_cache[cache_key] = messages

        try:
            from ..dna.cache_optimizer import CacheOptimizer
            if not hasattr(self, '_cache_optimizer'):
                self._cache_optimizer = CacheOptimizer(max_tokens=64000, cache_budget=0.85)
            return self._cache_optimizer.prepare(messages)
        except Exception as e:
            logger.warning("{}: {}".format("TreeLLM core", e))
            return messages

    # ── Private ──

    async def _warm_embedding(self):
        """Pre-load embedding model in background."""
        try:
            from .sticky_election import get_sticky_election
            get_sticky_election()._get_embedding("warmup")
        except Exception:
            pass

    @staticmethod
    def _is_simple_query(query: str) -> bool:
        q = query.lower()
        if len(query) > 80: return False
        for kw in ["fix","debug","implement","analyze","compare","evaluate",
                    "code","refactor","search","optimize","deploy",
                    "修复","调试","实现","分析","搜索","优化"]:
            if kw in q: return False
        return True

    async def _fast_route(self, query: str, task_type: str) -> dict | None:
        try:
            from .sticky_election import get_layer_config
            provider_name, model = get_layer_config().get_provider(1)
        except Exception:
            provider_name = "deepseek"
        p = self._providers.get(provider_name) or self._resolve_provider("")
        if not p: return None
        try:
            result = await p.chat(
                messages=[{"role": "user", "content": query}],
                temperature=0.7, max_tokens=1024, timeout=30,
            )
            if result and getattr(result, 'text', None):
                return {"provider": provider_name, "mode": "fast_path",
                        "result": result.text, "layers_used": 0}
        except Exception:
            pass
        return None

    def _resolve_provider(self, name: str) -> Provider | None:
        if name and name in self._providers:
            return self._providers[name]
        if self._elected and self._elected in self._providers:
            return self._providers[self._elected]
        return None

    def _record_success(self, name: str, tokens: int, latency_ms: float) -> None:
        s = self._stats.get(name)
        if not s:
            return
        with self._stats_lock:
            s.calls += 1; s.successes += 1
            s.total_tokens += tokens; s.total_latency_ms += latency_ms
            s.last_latency_ms = latency_ms
            s.recent_successes.append(True)
            s.recent_latencies.append(latency_ms)
            if len(s.recent_successes) > 20:
                s.recent_successes = s.recent_successes[-20:]
                s.recent_latencies = s.recent_latencies[-20:]
        from .holistic_election import get_election
        get_election().record_result(name, True, latency_ms, tokens)
        # Nested Learning: record election weights for EMA feedback
        try:
            from .holistic_election import record_election_feedback
            record_election_feedback(kwargs.get("task_type", "general"), {}, True)
        except Exception: pass
        # ── Cost tracking ──
        try:
            get_cost_dash().record(name, tokens, tokens)
        except Exception: pass
        # ── P2P cost report to relay ──
        try:
            from ..network.p2p_node import get_p2p_node
            import asyncio as _asyncio
            _asyncio.create_task(get_p2p_node().report_cost(name, tokens, tokens))
        except Exception: pass

    def _record_failure(self, name: str, error: str, rate_limited: bool = False) -> None:
        s = self._stats.get(name)
        if not s:
            return
        with self._stats_lock:
            s.calls += 1; s.failures += 1
            if rate_limited:
                s.rate_limits += 1
            s.last_error = error
        s.recent_successes.append(False)
        if len(s.recent_successes) > 20:
            s.recent_successes = s.recent_successes[-20:]
        from .holistic_election import get_election
        get_election().record_result(name, False, 0, 0, error, rate_limited)

    # ── Tool helpers (routed through VFS + MCP) ──

    @staticmethod
    def _unpack_tool_args(tool_name: str, tool_args: str) -> dict:
        """Convert flat tool arguments string to keyword dict for MCP tools.

        Supports formats:
          - key=value pairs: "cod=30 bod=6 do=5" → {"cod":30.0, "bod":6.0, "do":5.0}
          - JSON: '{"cod":30,"bod":6}' → {"cod":30, "bod":6}
          - Plain text: "some query text" → {"query":"some query text"}
        """
        import re as _re
        args = tool_args.strip()
        if not args:
            return {}
        # JSON format
        if args.startswith("{") and args.endswith("}"):
            try:
                import json as _json
                return _json.loads(args)
            except Exception:
                pass
        # key=value format
        if _re.search(r'\w+\s*=', args):
            result = {}
            for part in _re.split(r'\s+', args):
                if '=' in part:
                    k, _, v = part.partition("=")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    try:
                        v = float(v) if '.' in v or 'e' in v.lower() else int(v)
                    except ValueError:
                        pass
                    result[k] = v
            return result
        # Plain text → query parameter
        return {"query": args[:500]}

    @staticmethod
    async def _tool_read_vfs(path: str) -> str:
        """Read file through unified VFS. Supports all mounts: /ram, /disk, /cache, etc."""
        try:
            bus = get_capability_bus()
            result = await bus.invoke("vfs:read", path=path.strip())
            if isinstance(result, dict):
                return result.get("content", str(result)[:10000])
            return str(result)[:10000]
        except Exception as e:
            return f"[vfs:read error: {e}]"

    @staticmethod
    async def _tool_write_vfs(args: str) -> str:
        """Write file through unified VFS. Format: 'path\\ncontent'."""
        parts = args.split("\n", 1)
        path = parts[0].strip()
        content = parts[1] if len(parts) > 1 else ""
        try:
            bus = get_capability_bus()
            result = await bus.invoke("vfs:write", path=path, data=content)
            return str(result)
        except Exception as e:
            return f"[vfs:write error: {e}]"

    # ── Provider health check ──
    async def check_provider_health(self) -> dict[str, dict]:
        results = {}
        for name, p in self._providers.items():
            try:
                resp = await p.chat(
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=10, timeout=10,
                )
                healthy = bool(resp and hasattr(resp, 'text') and resp.text)
                error = "" if healthy else getattr(resp, 'error', 'empty')
                results[name] = {
                    "healthy": healthy,
                    "dead": name in self._dead_providers,
                    "error": str(error)[:200],
                    "latency_ms": getattr(resp, 'elapsed_ms', 0),
                }
                if healthy and name in self._dead_providers:
                    self._dead_providers.discard(name)
            except Exception as e:
                results[name] = {
                    "healthy": False,
                    "dead": name in self._dead_providers,
                    "error": str(e)[:200],
                }
        return results
