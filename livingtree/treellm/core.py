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
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from .classifier import TinyClassifier
from .providers import Provider, ProviderResult, create_deepseek_provider, create_longcat_provider
from .holistic_election import get_election


@dataclass
class RouterStats:
    provider: str
    calls: int = 0
    successes: int = 0
    failures: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    last_latency_ms: float = 0.0
    last_error: str = ""

    @property
    def success_rate(self) -> float:
        return self.successes / max(self.calls, 1)

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / max(self.calls, 1)


class TreeLLM:

    def __init__(self):
        self._providers: dict[str, Provider] = {}
        self._stats: dict[str, RouterStats] = {}
        self._elected: str = ""
        self._classifier = TinyClassifier()

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
                f"latency={best.latency_ms:.0f}ms "
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
        except Exception:
            pass

        # Step 3: Fallback to best success rate
        best = max(alive, key=lambda n: self._stats.get(n, RouterStats(n)).success_rate)
        return best

    # ── Layered Dynamic Routing (Pattern 3) ──
    async def route_layered(
        self, query: str, candidates: list[str] | None = None,
        max_layers: int = 3, early_stop_threshold: float = 0.85,
        top_k_per_layer: int = 3, task_type: str = "general",
    ) -> dict[str, Any]:
        """Layered routing inspired by RouteMoA (Pattern 3) with Output Aggregation (Pattern 6).

        Returns a dict with provider, result, layer info, scores, and cost accounting.
        """
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
            scorer_mod = __import__(".embedding_scorer", globals(), locals(), ["get_embedding_scorer"], 0)
            get_embedding_scorer = getattr(scorer_mod, "get_embedding_scorer", None)
            if get_embedding_scorer:
                scorer = get_embedding_scorer()
                if scorer is not None and hasattr(scorer, "score_and_filter"):
                    scored = scorer.score_and_filter(query, layer1_candidates_final)
                    if isinstance(scored, list) and scored:
                        # Expect [(cand, score), ...] or [cand, ...]
                        if scored and isinstance(scored[0], tuple) and len(scored[0]) == 2:
                            scored_sorted = sorted(scored, key=lambda t: float(t[1]), reverse=True)
                            layer1_candidates_final = [p for p, s in scored_sorted[: max(1, min(len(scored_sorted), top_k_per_layer * 2))]]
                            embedding_score = float(scored_sorted[0][1]) if scored_sorted else 0.0
                        else:
                            layer1_candidates_final = list(scored[: max(0, min(len(scored), top_k_per_layer * 2))])
        except Exception:
            pass
        layer1_candidates_final = list(dict.fromkeys(layer1_candidates_final))

        # ── Layer 1.5: Foresight integration — lightweight probe (Pattern 4/5) ──
        foresight_insights: dict[str, Any] = {}
        if layer1_candidates_final and len(layer1_candidates_final) > 3:
            try:
                from .foresight_gate import get_foresight_gate
                gate = get_foresight_gate()
                decision = gate.assess(query, task_type, [], "normal")
                if getattr(decision, "should_simulate", False) and getattr(decision, "depth", 0) >= 2:
                    # Run lightweight probes on top-2 candidates using embedding scorer
                    try:
                        from .embedding_scorer import get_embedding_scorer
                        scorer = get_embedding_scorer()
                        probe_results = scorer.score_and_filter(query, getattr(scorer, "_profiles", {}), top_k=2)
                        foresight_insights = {
                            "simulated": True,
                            "top_probes": [(n, round(s, 3)) for n, s in probe_results],
                            "depth": getattr(decision, "depth", 0),
                            "reason": getattr(decision, "reason", ""),
                        }
                        try:
                            from loguru import logger as _logger
                            _logger.debug(f"Layer 1.5 probes: {foresight_insights['top_probes']}")
                        except Exception:
                            pass
                        # Boost layer1_candidates_final with probe-preferred names
                        probe_names = {n for n, _ in probe_results}
                        for name in probe_names:
                            if name not in layer1_candidates_final and len(layer1_candidates_final) < top_k_per_layer * 3:
                                layer1_candidates_final.append(name)
                    except ImportError:
                        pass
            except ImportError:
                pass
        # Layer 2: Election scoring + alive-ping
        layer2_candidates: list[str] = []
        election_score = 0.0
        try:
            layer2_provider_scores = []
            election = get_election()
            try:
                # Historical call style from elect(): score_providers(names, providers, free_models)
                scores = election.score_providers(layer1_candidates_final, self._providers, [])
                if scores:
                    if isinstance(scores, dict):
                        layer2_provider_scores = [(k, float(v)) for k, v in scores.items()]
                    else:
                        layer2_provider_scores = [(p, float(s)) for p, s in scores]
            except Exception:
                layer2_provider_scores = []
            if layer2_provider_scores:
                layer2_provider_scores.sort(key=lambda t: t[1], reverse=True)
                top2 = layer2_provider_scores[: max(1, min(len(layer2_provider_scores), top_k_per_layer))]
                # Ping each candidate to confirm alive
                for prov, sc in top2:
                    alive = True
                    try:
                        if hasattr(election, "ping"):
                            alive = election.ping(prov)
                    except Exception:
                        alive = False
                    if alive:
                        layer2_candidates.append(prov)
                layer2_candidates = list(dict.fromkeys(layer2_candidates))
                if top2:
                    election_score = float(top2[0][1])
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
                except Exception:
                    continue
        # Fallback if nothing stopped early: pick best by election score or first layer2 candidate
        if final_provider is None:
            if layer2_candidates:
                final_provider = layer2_candidates[0]
                final_result = await self.chat([{"role": "user", "content": query}], provider=final_provider)
                layers_used = 3
            elif layer1_candidates_final:
                final_provider = layer1_candidates_final[0]
                final_result = await self.chat([], provider=final_provider)
                layers_used = 1

        return {
            "provider": final_provider or "",
            "result": final_result,
            "layers_used": layers_used,
            "candidates_per_layer": {
                "layer1": layer1_candidates_final,
                "layer2": layer2_candidates,
                "layer3": [final_provider] if final_provider else [],
            },
            "scores": {
                "embedding_score": embedding_score,
                "election_score": election_score,
                "self_assessment": float(self_assessment_score),
                "final_decision": "early_stop" if final_result and self_assessment_score > early_stop_threshold else "fallback",
            },
            "cost_saved": "Used layering providers (embedded scoring + alive ping)",
            "foresight": foresight_insights,
        }

    def route_layered_sync(self, query: str, **kwargs) -> dict[str, Any]:
        """Synchronous wrapper for route_layered."""
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.route_layered(query, **kwargs))

    # ── Output Aggregation (Pattern 6) ──
    def aggregate_outputs(self, outputs: list[str], scores: list[float] | None = None,
                          method: str = "best") -> str:
        if not outputs:
            return ""
        if scores is None or len(scores) != len(outputs):
            scores = [0.0 for _ in outputs]

        if method == "longest":
            # Return the longest string
            return max(outputs, key=lambda s: len(s))
        if method == "consensus" and len(outputs) >= 2:
            # Find pairwise consensus with Jaccard similarity > 0.5
            from math import ceil
            best_candidate = outputs[0]
            best_score = scores[0]
            for i in range(len(outputs)):
                for j in range(i + 1, len(outputs)):
                    sim = self._jaccard_similarity(outputs[i], outputs[j])
                    if sim > 0.5 and scores[i] > best_score:
                        best_candidate = outputs[i]
                        best_score = scores[i]
                    if sim > 0.5 and scores[j] > best_score:
                        best_candidate = outputs[j]
                        best_score = scores[j]
            return best_candidate
        # Default: best by score, or first if scores unavailable
        if scores:
            idx = int(max(range(len(scores)), key=lambda i: scores[i]))
            return outputs[idx]
        return max(outputs, key=lambda s: len(s))

    @staticmethod
    def _jaccard_similarity(text_a: str, text_b: str) -> float:
        """Simple word-level Jaccard similarity."""
        if not text_a or not text_b:
            return 0.0
        set_a = set(text_a.lower().split())
        set_b = set(text_b.lower().split())
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    # ── Chat ──

    async def chat(self, messages: list[dict], provider: str = "",
                   temperature: float = 0.7, max_tokens: int = 4096,
                   timeout: int = 120, model: str = "", **kwargs) -> ProviderResult:
        p = self._resolve_provider(provider)
        if not p:
            return ProviderResult.empty(f"No provider: {provider}")

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
                except Exception:
                    pass
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
        """Apply token optimizations: prefix caching + system prompt trimming."""
        try:
            from ..dna.cache_optimizer import CacheOptimizer
            # Use a shared optimizer instance per TreeLLM
            if not hasattr(self, '_cache_optimizer'):
                self._cache_optimizer = CacheOptimizer(max_tokens=64000, cache_budget=0.85)
            return self._cache_optimizer.prepare(messages)
        except Exception:
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
            get_p2p_node().report_cost(name, tokens, tokens)
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
