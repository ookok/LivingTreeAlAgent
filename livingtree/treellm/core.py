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
import time
from loguru import logger
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from .classifier import TinyClassifier
from .providers import Provider, ProviderResult, create_deepseek_provider, create_longcat_provider
from .holistic_election import get_election, RouterStats



class TreeLLM:

    def __init__(self):
        self._providers: dict[str, Provider] = {}
        self._stats: dict[str, RouterStats] = {}
        self._elected: str = ""
        self._classifier = TinyClassifier()

    # ── Bootstrap from config ──

    @classmethod
    def from_config(cls) -> "TreeLLM":
        """Create a fully initialized TreeLLM from the system config.

        Autoregisters all providers with configured API keys from the vault.
        This is the canonical entry point — no manual provider registration needed.
        """
        llm = cls()
        try:
            from livingtree.config.settings import get_config
            config = get_config().model

            # Map provider name → (api_key_attr, create_fn, thinking_disabled_for_chat)
            provider_specs = [
                ("deepseek", "deepseek_api_key", create_deepseek_provider, False),
                ("longcat", "longcat_api_key", create_longcat_provider, True),
            ]

            for name, key_attr, create_fn, _no_think in provider_specs:
                api_key = getattr(config, key_attr, "")
                if api_key:
                    try:
                        provider = create_fn(api_key)
                        llm.add_provider(provider)
                    except Exception as e:
                        logger.debug(f"TreeLLM.from_config: {name} skipped ({e})")

            logger.info(
                f"TreeLLM.from_config: bootstrapped with "
                f"{len(llm._providers)} providers: {list(llm._providers.keys())}"
            )
        except Exception as e:
            logger.warning(f"TreeLLM.from_config: {e}")

        return llm

    # ── Provider management ──

    def add_provider(self, provider: Provider) -> None:
        self._providers[provider.name] = provider
        self._stats[provider.name] = RouterStats(provider=provider.name)

    def remove_provider(self, name: str) -> None:
        self._providers.pop(name, None)

    def get_provider(self, name: str) -> Provider | None:
        return self._providers.get(name)

    @property
    def provider_names(self) -> list[str]:
        return list(self._providers.keys())

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
        names = candidates or list(self._providers.keys())
        alive = []
        for name in names:
            p = self._providers.get(name)
            if p:
                ok, _ = await p.ping()
                if ok:
                    alive.append(name)

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
        max_layers: int = 3, early_stop_threshold: float = 0.85,
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
        try:
            from .fluid_collective import get_fluid_collective
            fc = get_fluid_collective()
            stigmergy_ctx = fc.retrieve_context(domain=task_type, max_traces=3)
            if stigmergy_ctx:
                query = stigmergy_ctx + "\n\n" + query
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
        except ImportError:
            pass

        # ── Fast path: preprocess only, no LLM ──
        if not model:
            return {
                "provider": "preprocess", "result": None, "mode": "preprocess",
                "layers_used": 0,
                "scores": {"final_decision": "preprocess_only"},
                "cost_saved": "Skipped LLM (~2min)",
                "deep_probe": probing_result,
                "micro_turn": micro_turn_state,
                "stigmergy": True if 'stigmergy_ctx' in dir() and stigmergy_ctx else False,
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

        # Layer 2: Election scoring
        layer2_candidates: list[str] = []
        election_score = 0.0
        try:
            election = get_election()
            scores = await election.score_providers(layer1_candidates_final, self._providers, [])
            if scores:
                layer2_scores = [(s.name, float(s.total)) for s in scores]
                layer2_scores.sort(key=lambda t: -t[1])
                top2 = layer2_scores[:top_k_per_layer]
                election_score = float(top2[0][1]) if top2 else 0.0
                layer2_candidates = [p for p, _ in top2]
        except Exception:
            layer2_candidates = layer1_candidates_final[:top_k_per_layer]

        # Layer 3: Inference + self-assessment
        final_provider = None
        final_result = None
        layers_used = 2 if layer2_candidates else 1
        self_assessment_score = 0.0
        if layer2_candidates:
            for candidate in layer2_candidates[:top_k_per_layer]:
                try:
                    res = await self.chat([{"role": "user", "content": query}], provider=candidate)  # query routed to provider
                    # Normalize to text
                    text = None
                    if isinstance(res, ProviderResult):
                        text = getattr(res, "text", None) or getattr(res, "content", None)
                    elif isinstance(res, dict):
                        text = res.get("text") or res.get("content") or res.get("output")
                    elif isinstance(res, str):
                        text = res
                    else:
                        text = str(res)

                    # Self-assessment
                    assessment = None
                    if 'election' in locals():
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
                        break
                except Exception as e:
                    logger.warning("{}: {}".format("TreeLLM core", e))
                    continue
        # Fallback if nothing stopped early: pick best by election score or first layer2 candidate
        if final_provider is None:
            if layer2_candidates:
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
        original_provider = final_provider
        original_result = final_result

        if final_provider is None or final_result is None:
            remaining = [p for p in list(self._providers.keys())
                         if p not in (layer2_candidates or []) and p not in (final_provider or "")]
            remaining = remaining[:top_k_per_layer]

            for candidate in remaining:
                try:
                    res = await self.chat([{"role": "user", "content": query}], provider=candidate)
                    if res and (getattr(res, "text", None) or getattr(res, "content", None)):
                        l4_provider = candidate
                        l4_result = res
                        layers_used = 4
                        break
                except Exception as e:
                    logger.warning("{}: {}".format("TreeLLM core", e))
                    continue

        if l4_provider is None and (final_provider is None or final_result is None):
            local_candidates = [
                n for n in self._providers.keys()
                if any(k in n.lower() for k in ("local", "offline", "ollama", "opencode", "serve", "llama"))
            ]
            for candidate in local_candidates:
                try:
                    res = await self.chat([{"role": "user", "content": query}], provider=candidate)
                    if res and (getattr(res, "text", None) or getattr(res, "content", None)):
                        l4_provider = candidate
                        l4_result = res
                        layers_used = 4
                        break
                except Exception as e:
                    logger.warning("{}: {}".format("TreeLLM core", e))
                    continue

        if l4_provider and l4_result:
            final_provider = l4_provider
            final_result = l4_result

        # ── SynapseAggregator: multi-model reasoning fusion ──
        synapse_result: dict[str, Any] | None = None
        if aggregate and final_result and final_provider:
            try:
                from .synapse_aggregator import get_synapse_aggregator, ModelOutput
                aggregator = get_synapse_aggregator()
                # Collect outputs from layer2_candidates that were actually invoked
                agg_outputs: list[ModelOutput] = []
                for candidate in (layer2_candidates or [])[:top_k_per_layer]:
                    if candidate == final_provider:
                        continue  # Already have this
                    try:
                        res = await self.chat(
                            [{"role": "user", "content": query}],
                            provider=candidate, max_tokens=4096,
                        )
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
                    except Exception:
                        pass

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
                "layer3": [original_provider] if original_provider else [],
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
                        "stigmergy": bool(stigmergy_ctx) if 'stigmergy_ctx' in dir() else False,
            }

    def route_layered_sync(self, query: str, **kwargs) -> dict[str, Any]:
        """Synchronous wrapper for route_layered."""
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.route_layered(query, **kwargs))



    # ── Chat ──

    async def chat(self, messages: list[dict], provider: str = "",
                   temperature: float = 0.7, max_tokens: int = 4096,
                   timeout: int = 120, model: str = "", **kwargs) -> ProviderResult:
        p = self._resolve_provider(provider)
        if not p:
            return ProviderResult.empty(f"No provider: {provider}")

        # ── Disable thinking for short queries (no budget for reasoning overhead) ──
        if max_tokens < 800 and hasattr(p, 'pro_thinking_enabled'):
            p.pro_thinking_enabled = False

        # ── Token optimization: apply CacheDirector for prefix caching ──
        provider_name = p.name if p else ""
        from .cache_director import get_cache_director
        director = get_cache_director()
        if director.supports_cache(provider_name):
            messages = director.prepare(messages, provider_name)

        # ── Session binding: inject transition context if model switched ──
        sid = kwargs.get("session_id", f"session_{id(self)}")
        from .session_binding import get_session_binding
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
                result.text = result.reasoning  # Use reasoning as response
            if result and result.text:
                self._record_success(p.name, result.tokens, (time.monotonic() - t0) * 1000)
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
                    from ..observability.trust_scoring import get_trust_scorer
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
        import re
        html_tag = re.compile(r'<[^>]+>')
        long_url = re.compile(r'https?://[^\s]{50,}')

        for msg in messages:
            content = str(msg.get("content", ""))
            if not content:
                continue
            # HTML → plain text
            if '<' in content and '>' in content:
                content = html_tag.sub(' ', content)
            # Long URLs → domain-only
            content = long_url.sub(
                lambda m: '[link:' + (re.search(r'https?://([^/]+)', m.group(0)).group(1)
                                        if re.search(r'https?://([^/]+)', m.group(0)) else 'url') + ']',
                content
            )
            msg["content"] = content

        try:
            from ..dna.cache_optimizer import CacheOptimizer
            if not hasattr(self, '_cache_optimizer'):
                self._cache_optimizer = CacheOptimizer(max_tokens=64000, cache_budget=0.85)
            return self._cache_optimizer.prepare(messages)
        except Exception as e:
            logger.warning("{}: {}".format("TreeLLM core", e))
            return messages

    # ── Private ──

    def _resolve_provider(self, name: str) -> Provider | None:
        if name and name in self._providers:
            return self._providers[name]
        if self._elected and self._elected in self._providers:
            return self._providers[self._elected]
        for p in self._providers.values():
            return p
        return None

    def _record_success(self, name: str, tokens: int, latency_ms: float) -> None:
        s = self._stats.get(name)
        if not s:
            return
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
        # ── Cost tracking ──
        try:
            from ..capability.industrial_doc_engine import get_cost_dash
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
        s.calls += 1; s.failures += 1
        if rate_limited:
            s.rate_limits += 1
        s.last_error = error
        s.recent_successes.append(False)
        if len(s.recent_successes) > 20:
            s.recent_successes = s.recent_successes[-20:]
        from .holistic_election import get_election
        get_election().record_result(name, False, 0, 0, error, rate_limited)
