"""Holistic Election Engine — multi-dimensional provider scoring.

Scores each provider on 5 dimensions:
  1. Alive (ping) — can we reach it?
  2. Latency — how fast does it respond? (lower is better)
  3. Quality — success rate over last N calls
  4. Cost — free > paid
  5. Capability — does this model match the task?

Weighted scoring produces a ranked list. Integrated into TreeLLM.elect().
"""
from __future__ import annotations

import asyncio
import json
import math
import time
from dataclasses import dataclass, field
import re
from pathlib import Path
from typing import Any

from loguru import logger

STATS_FILE = Path(".livingtree/election_stats.json")

# Scoring weights (sum to 1.0)
WEIGHTS = {
    "latency": 0.18,
    "quality": 0.23,
    "cost": 0.15,
    "capability": 0.12,
    "freshness": 0.05,
    "rate_limit": 0.07,
    "cache": 0.10,
    "sticky": 0.10,       # Session binding: prefer same model
    "hifloat8": 0.0,      # HiFloat8 cone-precision boost (weighted by task_type)
    "elo": 0.0,           # CompetitiveEliminator Elo rating (injected dynamically)
    "long_term_reward": 0.0,  # JointEvolution long-term reward (C→P loop)
    "thompson": 0.0,      # Thompson Sampling Bayesian prior
    "exploration": 0.0,   # Exploration bonus for under-tested providers
}

# NOTE: Pattern 5 dynamic weights will be used via get_dynamic_weights(task_type).

# Provider capability profiles: which tasks each model excels at
PROVIDER_CAPABILITIES: dict[str, list[str]] = {
    "siliconflow-reasoning": ["推理", "数学", "逻辑", "分析", "reasoning", "math", "logic"],
    "siliconflow-flash": ["对话", "翻译", "摘要", "chat", "translate", "summary"],
    "siliconflow-small": ["分类", "关键词", "简单", "classify"],
    "mofang-reasoning": ["推理", "分析", "reasoning"],
    "mofang-flash": ["对话", "文档", "chat", "document"],
    "mofang-small": ["分类", "简单", "classify"],
    "deepseek": ["代码", "推理", "分析", "code", "reasoning", "analysis"],
    "zhipu": ["中文", "理解", "chat", "chinese"],
    "longcat": ["对话", "快速", "chat", "fast"],
    "spark": ["搜索", "知识", "search", "knowledge"],
    "dmxapi": ["对话", "辅助", "chat"],
    "opencode-serve": ["本地", "离线", "local", "offline"],
    "xiaomi": ["多模态", "图像", "multimodal", "image"],
    "aliyun": ["企业", "分析", "enterprise", "analysis"],
    "nvidia-reasoning": ["推理", "深度思考", "数学", "逻辑", "reasoning", "deep", "math", "logic", "分析"],
    "nvidia-pro": ["推理", "代码", "综合", "reasoning", "code", "comprehensive"],
    "nvidia-flash": ["对话", "摘要", "翻译", "chat", "summary", "translate"],
    "nvidia-small": ["分类", "简单", "快速", "classify", "simple", "fast"],
    # Pattern 5: extra multiplier for multimodal capabilities (model scope)
    "modelscope": ["推理", "代码", "开源", "reasoning", "code", "open source"],
    "bailing": ["推理", "企业", "对话", "分析", "reasoning", "enterprise", "chat", "analysis"],
    "stepfun": ["推理", "深度", "长文本", "多模态", "reasoning", "deep", "long-context", "multimodal"],
    "internlm": ["推理", "中文", "学术", "代码", "reasoning", "chinese", "academic", "code"],
    "web2api": ["网页", "免费", "多平台", "web", "free", "multi-platform"],
    "sensetime": ["推理", "中文", "分析", "代码", "reasoning", "chinese", "analysis", "code"],
    "sensetime-pro": ["推理", "深度思考", "长文本", "reasoning", "deep", "long-context"],
    "sensetime-turbo": ["对话", "快速", "翻译", "chat", "fast", "translate"],
    "freebuff": ["对话", "代码", "免费", "广告赞助", "chat", "code", "fallback", "analysis"],
    "openrouter": ["对话", "代码", "推理", "分析", "chat", "code", "reasoning", "analysis", "多模型", "免费"],
    "hunyuan": ["对话", "中文", "企业", "分析", "chat", "chinese", "enterprise"],
    "baidu": ["对话", "中文", "知识", "企业", "chat", "chinese", "knowledge", "enterprise"],
}


@dataclass
class JudgeResult:
    name: str
    self_score: float = 0.0
    cross_score: float = 0.0
    combined: float = 0.0


@dataclass
class ProviderScore:
    name: str
    alive: bool = False
    is_free: bool = False
    scores: dict[str, float] = field(default_factory=dict)
    total: float = 0.0
    latency_ms: float = 0.0
    success_rate: float = 0.0
    capability_match: float = 0.0
    last_used: float = 0.0
    # Pattern 5: dynamic per-1k-cost and latency tracking
    cost_yuan_per_1k: float = 0.0
    avg_latency_ms: float = 0.0


@dataclass
class RouterStats:
    provider: str
    calls: int = 0
    successes: int = 0
    failures: int = 0
    rate_limits: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    last_latency_ms: float = 0.0
    last_error: str = ""
    last_used: float = 0.0

    # Sliding window: track last 20 calls for recency-weighted stats
    recent_successes: list[bool] = field(default_factory=list)
    recent_latencies: list[float] = field(default_factory=list)
    WINDOW_SIZE: int = 20

    def record(self, success: bool, latency_ms: float, tokens: int = 0, error: str = "", rate_limited: bool = False):
        self.calls += 1
        if success:
            self.successes += 1
        else:
            self.failures += 1
        if rate_limited:
            self.rate_limits += 1
        self.total_tokens += tokens
        self.total_latency_ms += latency_ms
        self.last_latency_ms = latency_ms
        self.last_error = error
        self.last_used = time.time()

        self.recent_successes.append(success)
        self.recent_latencies.append(latency_ms)
        if len(self.recent_successes) > self.WINDOW_SIZE:
            self.recent_successes = self.recent_successes[-self.WINDOW_SIZE:]
            self.recent_latencies = self.recent_latencies[-self.WINDOW_SIZE:]

    @property
    def success_rate(self) -> float:
        if len(self.recent_successes) >= 3:
            return sum(self.recent_successes) / len(self.recent_successes)
        return self.successes / max(self.calls, 1)

    @property
    def avg_latency_ms(self) -> float:
        if self.recent_latencies:
            return sum(self.recent_latencies) / len(self.recent_latencies)
        return self.total_latency_ms / max(self.calls, 1)

    @property
    def recent_quality(self) -> float:
        """Recency-weighted quality: recent calls matter more."""
        if not self.recent_successes:
            return self.success_rate
        weighted = sum(
            (1.0 if s else 0.0) * (i + 1) / len(self.recent_successes)
            for i, s in enumerate(self.recent_successes)
        )
        return weighted / sum((i + 1) / len(self.recent_successes) for i in range(len(self.recent_successes)))

    def project_future(self, cost_per_1k: float = 0.0, task_complexity: float = 0.5) -> dict[str, Any]:
        """World model abstraction: project future state if this provider is chosen.
        
        Returns expected: latency, quality, cost_yuan, risk score.
        Used by foresight gate to preview outcomes before committing.
        """
        expected_latency = self.avg_latency_ms * (1.0 + task_complexity * 0.5)
        expected_quality = self.success_rate * (1.0 - task_complexity * 0.2)
        expected_cost = cost_per_1k * 4.0  # assume ~4k tokens per call

        risk = 0.0
        if self.success_rate < 0.5:
            risk += 0.3
        if expected_latency > 5000:
            risk += 0.2
        if self.failures > self.successes:
            risk += 0.3
        
        return {
            "provider": self.provider,
            "expected_latency_ms": round(expected_latency, 1),
            "expected_quality": round(expected_quality, 3),
            "estimated_cost_yuan": round(expected_cost, 4),
            "confidence": min(1.0, self.calls / 20.0),  # more calls = more confident
            "risk_score": min(1.0, risk),
            "recommendation": "strong" if expected_quality > 0.8 and risk < 0.3 else "cautious" if expected_quality > 0.5 else "avoid",
        }


class HolisticElection:
    """Multi-dimensional scoring election engine."""

    def __init__(self):
        self._stats: dict[str, RouterStats] = {}
        self._load()

    def get_stats(self, name: str) -> RouterStats:
        if name not in self._stats:
            self._stats[name] = RouterStats(provider=name)
        return self._stats[name]

    async def score_providers(
        self,
        candidates: list[str],
        providers: dict[str, Any],
        free_models: list[str],
        query: str = "",
        task_type: str = "general",
    ) -> list[ProviderScore]:
        """Score all candidates holistically. Returns ranked list."""
        results = []

        # Phase 1: Ping all alive candidates (skip circuit-broken providers)
        breaker = None
        try:
            from .circuit_breaker import get_circuit_breaker
            breaker = get_circuit_breaker()
        except Exception:
            pass

        alive_scores = []
        ping_count = 0

        # Token Accountant: shared price vector for router layer
        try:
            from ..api.token_accountant import get_token_accountant, AllocationLayer
            accountant = get_token_accountant()
            prices = accountant.get_price_vector()
            max_pings = prices.max_ping_providers
        except Exception:
            accountant = None
            max_pings = len(candidates)

        for name in candidates:
            # Skip providers with open circuit breaker (Token中转站熔断)
            if breaker and breaker.is_open(name):
                continue

            # CompetitiveEliminator: skip eliminated providers
            try:
                from .competitive_eliminator import get_eliminator
                if not get_eliminator().is_viable(name):
                    continue
            except ImportError:
                pass

            # Token Accountant: limit pings to prevent over-routing
            if accountant and ping_count >= max_pings:
                break

            p = providers.get(name)
            if not p:
                continue
            stats = self.get_stats(name)
            ok, err = await p.ping()
            if not ok:
                continue

            ping_count += 1
            # Token Accountant: record router layer allocation
            if accountant:
                try:
                    accountant.record_allocation(
                        layer=AllocationLayer.ROUTER,
                        action="ping",
                        tokens_spent=50,
                        actual_benefit=1.0 if ok else 0.0,
                        latency_ms=stats.avg_latency_ms,
                    )
                except Exception:
                    pass

            score = ProviderScore(
                name=name,
                alive=True,
                is_free=name in free_models,
                latency_ms=stats.avg_latency_ms,
                success_rate=stats.success_rate,
                last_used=stats.last_used,
            )

            # Score 1: Latency (normalized: faster = higher score)
            avg_lat = float(stats.avg_latency_ms) if stats.avg_latency_ms else 200
            lat = float(stats.avg_latency_ms) if stats.avg_latency_ms else 200
            max_latency = max(max(100, avg_lat), lat)
            score.scores["latency"] = 1.0 - min(lat / max_latency, 0.95)

            # Score 2: Quality (recent success rate)
            score.scores["quality"] = stats.recent_quality

            # Score 3: Cost (free = 1.0, paid = 0.3)
            score.scores["cost"] = 1.0 if score.is_free else 0.3

            # Score 3.5: Rate-limit penalty (temp -0.5 if recently throttled)
            rl_count = getattr(p, '_rate_limit_count', 0)
            rl_last = getattr(p, '_last_rate_limit', 0.0)
            rl_penalty = 0.0
            if rl_last > 0:
                seconds_since = time.time() - rl_last
                if seconds_since < 60:  # within last minute: full penalty
                    rl_penalty = 0.5
                elif seconds_since < 300:  # within 5 min: decay
                    rl_penalty = 0.5 * (1.0 - (seconds_since - 60) / 240)
                # Accumulated rate limits also count
                if rl_count > 3:
                    rl_penalty = min(0.8, rl_penalty + 0.1 * (rl_count - 3))
            score.scores["rate_limit"] = max(0.0, 1.0 - rl_penalty)

            # Score 4: Capability match
            score.capability_match = self._capability_match(name, query)
            score.scores["capability"] = score.capability_match

            # Score 5: Freshness (recently used = higher)
            if stats.last_used > 0:
                hours_since = (time.time() - stats.last_used) / 3600
                score.scores["freshness"] = max(0.0, 1.0 - hours_since / 24.0)
            else:
                score.scores["freshness"] = 0.5  # neutral for never-used

            # Score 6: Cache benefit (how much can prefix-cache save?)
            try:
                from .cache_director import get_cache_director
                cd = get_cache_director()
                score.scores["cache"] = cd.cache_score(name)
            except Exception:
                score.scores["cache"] = 0.0

            # Score 7: Session stickiness (prefer same model across turns)
            try:
                from .session_binding import get_session_binding
                sb = get_session_binding()
                # Get session ID from query context (passed via kwargs or global)
                sid = query[:20] if query else "default"
                score.scores["sticky"] = sb.stickiness_score(sid, name)
            except Exception:
                score.scores["sticky"] = 0.0

            # Score 8: HiFloat8 cone-precision support (Ascend 950 acceleration)
            # Higher score for HiFloat8-wrapped providers, especially with long context
            try:
                hifloat8_enabled = getattr(p, 'hifloat8_supported', False)
                score.scores["hifloat8"] = 1.0 if hifloat8_enabled else 0.0
            except Exception:
                score.scores["hifloat8"] = 0.0

            # ── CompetitiveEliminator: apply tier-based modifiers ──
            try:
                from .competitive_eliminator import get_eliminator
                elim = get_eliminator()
                if not elim.is_viable(name):
                    continue  # Skip eliminated providers
                modifiers = elim.get_tier_modifier(name)
                for dim, mod in modifiers.items():
                    if dim in score.scores:
                        score.scores[dim] *= mod
                    else:
                        score.scores[dim] = mod
                # Apply Elo rating as bonus dimension
                ranking = elim.get_ranking(name)
                if ranking and ranking.is_established:
                    elo_norm = max(0.0, min(1.0, (ranking.elo_rating - 800) / 1200.0))
                    score.scores.setdefault("elo", 0.0)
                    score.scores["elo"] = elo_norm * 0.5  # 50% weight of Elo contribution
            except ImportError:
                pass

            # ── JointEvolution: apply long-term reward modifiers (C→P loop) ──
            try:
                from .joint_evolution import get_joint_evolution
                je = get_joint_evolution()
                lt_rewards = je.inject_rewards_to_election()
                if name in lt_rewards:
                    modifier = lt_rewards[name]
                    score.scores.setdefault("long_term_reward", 0.0)
                    score.scores["long_term_reward"] = max(0.0, 0.5 + modifier)  # 0.2-0.8 range
                    logger.debug(
                        f"JointEvolution C→P: {name} long_term_reward={modifier:.3f}"
                    )
            except ImportError:
                pass

            # ── Thompson Sampling boost (bandit_router Bayesian prior) ──
            try:
                from .bandit_router import get_bandit_router
                br = get_bandit_router()
                arm = br.get_arm(name)
                # Thompson sample: exploration bonus for uncertain providers
                ts_value = arm.sample_composite()
                score.scores.setdefault("thompson", 0.0)
                score.scores["thompson"] = ts_value
                # Boost for high-uncertainty providers (exploration)
                score.scores.setdefault("exploration", 0.0)
                score.scores["exploration"] = arm.exploration_bonus * 0.5
            except ImportError:
                pass

            # Apply dynamic weights based on task_type (Pattern 5)
            weights = get_dynamic_weights(task_type)
            # ── InverseReward → Provider election influence ──
            try:
                from ..economy.inverse_reward import get_inverse_reward
                ir = get_inverse_reward()
                prefs = ir.get_preference_profile()
                if prefs.get("prefers_speed", 0) > 0.5:
                    weights["latency"] = weights.get("latency", 0.18) * 1.3
                    weights["quality"] = weights.get("quality", 0.23) * 0.9
                if prefs.get("prefers_simplicity", 0) > 0.5:
                    weights["cost"] = weights.get("cost", 0.15) * 1.2
            except Exception:
                pass
            # ensure all keys exist in scores
            for k in weights:
                score.scores.setdefault(k, 0.0)
            # Weighted total using dynamic weights
            score.total = sum(
                weights[k] * score.scores.get(k, 0)
                for k in weights
            )
            # Real-time health adjustment (live feedback from RouterStats)
            health_factor = self._health_adjustment(name, stats)
            score.total *= health_factor
            # Pattern 5: expose latency and cost currencies for later analysis
            try:
                score.avg_latency_ms = stats.avg_latency_ms
            except Exception:
                score.avg_latency_ms = 0.0
            try:
                base_cost = 5.0
                scale = max(0.0, min(1.0, score.scores.get("cost", 0.0)))
                score.cost_yuan_per_1k = base_cost * (1.0 - scale)
            except Exception:
                score.cost_yuan_per_1k = 0.0
            alive_scores.append(score)

        alive_scores.sort(key=lambda s: -s.total)
        return alive_scores

    def _capability_match(self, provider_name: str, query: str) -> float:
        """How well does this provider's capabilities match the user's query?"""
        caps = PROVIDER_CAPABILITIES.get(provider_name, [])
        if not caps or not query:
            return 0.3  # neutral

        query_lower = query.lower()
        matches = sum(1 for c in caps if c in query_lower)
        if matches > 0:
            return min(1.0, 0.5 + matches * 0.15)
        return 0.1  # no match

    def _health_adjustment(self, name: str, stats: RouterStats) -> float:
        """Compute a health penalty factor (0.0-1.0) based on real-time provider stats.

        Returns a multiplier to apply to the total score:
          - 1.0 = no penalty (healthy)
          - 0.0 = severe penalty (provider should be avoided)

        Penalties:
          - Recent success rate < 0.4: -60%
          - Recent success rate < 0.7: -30%
          - Avg latency > 10s: -50%
          - Avg latency > 5s: -20%
          - Recent rate-limited: -30%
        """
        factor = 1.0
        if stats.calls < 3:
            return 1.0  # Not enough data — neutral

        # Quality penalty
        recent_qual = stats.recent_quality
        if recent_qual < 0.4:
            factor *= 0.4
        elif recent_qual < 0.7:
            factor *= 0.7

        # Latency penalty
        avg_lat = stats.avg_latency_ms
        if avg_lat > 10000:
            factor *= 0.5
        elif avg_lat > 5000:
            factor *= 0.8

        # Rate-limit penalty (if last error contains rate_limit)
        if "rate_limit" in (stats.last_error or "").lower():
            factor *= 0.7

        # Heavy failure penalty (failures > successes)
        if stats.failures > stats.successes and stats.calls > 5:
            factor *= 0.5

        return max(0.05, factor)

    def record_result(self, name: str, success: bool, latency_ms: float, tokens: int = 0, error: str = "", rate_limited: bool = False):
        stats = self.get_stats(name)
        stats.record(success, latency_ms, tokens, error, rate_limited)
        # ── CompetitiveEliminator: update Elo rankings ──
        try:
            from .competitive_eliminator import get_eliminator
            elim = get_eliminator()
            quality = 0.8 if success else 0.2
            elim.record_match(
                provider=name, success=success, latency_ms=latency_ms,
                cost_yuan=0.01, tokens=tokens, quality=quality,
                opponent_providers=list(self._stats.keys()),
            )
        except ImportError:
            pass
        if stats.calls % 50 == 0:
            self._save()

    def get_best(self, candidates: list[str], providers: dict[str, Any], free_models: list[str]) -> str:
        """Synchronous shortcut: get best provider by composite score snapshot."""
        best = None
        best_score = -1.0
        for name in candidates:
            p = providers.get(name)
            if not p:
                continue
            stats = self.get_stats(name)
            score = (
                stats.success_rate * WEIGHTS["quality"]
                + (1.0 if name in free_models else 0.3) * WEIGHTS["cost"]
                + (1.0 - min(stats.avg_latency_ms / 5000.0, 0.95)) * WEIGHTS["latency"]
            )
            if score > best_score:
                best_score = score
                best = name
        return best or ""

    def project_all(self, candidates: list[str], task_complexity: float = 0.5) -> dict[str, dict]:
        """World model: project future states for all candidates. Returns sorted by recommendation."""
        projections: dict[str, dict] = {}
        for name in candidates:
            stats = self.get_stats(name)
            # rough cost estimate: try to use a small default, allow override if internal list exists
            cost = 0.003 if getattr(self, "_free_set", None) and name in self._free_set else 0.02
            proj = stats.project_future(cost_per_1k=cost, task_complexity=task_complexity)
            projections[name] = proj
        # Sort by recommendation priority then by higher expected quality
        order = {"strong": 0, "cautious": 1, "avoid": 2}
        return dict(sorted(projections.items(), key=lambda x: (order.get(x[1]["recommendation"], 3), -x[1].get("expected_quality", 0))))

    def get_all_stats(self) -> dict:
        return {
            name: {
                "calls": s.calls, "successes": s.successes, "failures": s.failures,
                "success_rate": s.success_rate, "avg_latency_ms": s.avg_latency_ms,
                "recent_quality": s.recent_quality, "total_tokens": s.total_tokens,
                "last_used": s.last_used,
            }
            for name, s in self._stats.items()
        }

    def _save(self):
        from livingtree.core.async_disk import save_json
        data = {
            name: {"calls": s.calls, "successes": s.successes, "failures": s.failures,
                   "total_tokens": s.total_tokens, "total_latency_ms": s.total_latency_ms,
                   "last_used": s.last_used}
            for name, s in self._stats.items()
        }
        save_json(STATS_FILE, data)

    def _load(self):
        try:
            if STATS_FILE.exists():
                data = json.loads(STATS_FILE.read_text())
                for name, d in data.items():
                    s = RouterStats(provider=name, **d)
                    self._stats[name] = s
        except Exception:
            pass

    # ===== Pattern 2: Mixture of Judges (self and cross assessments) =====
    def detect_task_type(self, query: str) -> str:
        """Heuristic mapping from user query to task type.
        Returns one of: code, reasoning, search, multimodal, chat, general
        """
        if not query:
            return "general"
        q = query.lower()
        mapping = {
            ("代码", "代码片段", "实现", "写"): "code",
            ("推理", "分析", "reasoning", "分析"): "reasoning",
            ("搜索", "查找", "find", "search"): "search",
            ("图像", "图片", "image", "multimodal"): "multimodal",
            ("什么", "问", "问题", "问答"): "chat",
        }
        for keys, t in mapping.items():
            for k in keys:
                if k in q:
                    return t
        return "general"

    def self_assess(self, output_text: str, confidence_keywords: list[str] | None = None) -> float:
        """Self-assessment of output quality. Uses LLM judge if available, else heuristic."""
        return self._self_assess_heuristic(output_text, confidence_keywords)

    @staticmethod
    def _self_assess_heuristic(output_text: str, confidence_keywords: list[str] | None = None) -> float:
        """Heuristic self-assessment — fast keyword-based fallback."""
        if confidence_keywords is None:
            confidence_keywords = [
                "confident", "certain", "definitely", "clearly", "sure", "确定", "明确", "肯定"
            ]
        hedging = ["maybe", "possibly", "perhaps", "might", "可能", "也许", "大概"]
        uncertainty = ["I don't know", "I'm not sure", "我不知道", "不确定"]

        score = 0.0
        if output_text and len(output_text) > 20:
            score += 0.3
        low = output_text.lower()
        if any(k in low for k in confidence_keywords):
            score += 0.2
        if any(h in low for h in hedging):
            score -= 0.1
        if not any(u in output_text for u in uncertainty):
            score += 0.1
        return max(0.0, min(1.0, score))

    async def self_assess_llm(self, output_text: str, query: str = "",
                               chat_fn=None) -> float:
        """LLM-based self-assessment — flash model judges quality in ~100ms.

        Much more accurate than heuristic keyword counting. The flash model
        evaluates: completeness, logical flow, specificity, and honesty.
        """
        if not chat_fn or not output_text:
            return self._self_assess_heuristic(output_text)

        prompt = (
            f"Rate the quality of this AI response on a scale of 0.0 to 1.0.\n\n"
            f"Query: {query[:300] if query else 'N/A'}\n\n"
            f"Response to evaluate:\n{output_text[:2000]}\n\n"
            f"Evaluate on: (1) completeness — does it fully answer the query? "
            f"(2) logical flow — is reasoning clear? (3) specificity — are claims "
            f"concrete or vague? (4) honesty — does it acknowledge uncertainty?\n\n"
            f"Reply with ONLY a number between 0.0 and 1.0. No explanation."
        )
        try:
            result = await chat_fn(prompt)
            # Extract first number found
            import re
            match = re.search(r'(\d+\.?\d*)', str(result))
            if match:
                return max(0.0, min(1.0, float(match.group(1))))
        except Exception:
            pass
        return self._self_assess_heuristic(output_text)

    def cross_assess(self, evaluator_output: str, target_output: str) -> float:
        """Quick cross-assessment using Jaccard similarity on word sets (lowercased, >2 chars)."""
        def words(s: str) -> set[str]:
            if not s:
                return set()
            # extract words with length > 2
            toks = re.findall(r"\b[a-zA-Z0-9一-龟]+\b", s.lower())
            return {t for t in toks if len(t) > 2}

        s1 = words(evaluator_output or "")
        s2 = words(target_output or "")
        if not s1 and not s2:
            return 0.0
        inter = len(s1 & s2)
        union = len(s1 | s2)
        return inter / max(union, 1)

    def judge_scores(self, candidates: list[str], layer_outputs: dict[str, str]) -> dict[str, float]:
        """Compute judge scores for each candidate based on self and cross assessments.
        Returns mapping candidate -> combined score."""
        scores: dict[str, float] = {}
        # Top-level evaluator: pick best candidate by self-assessment
        top_candidate = None
        top_self = -1.0
        self_outputs = {c: layer_outputs.get(c, "") for c in candidates}
        for c, out in self_outputs.items():
            s = self.self_assess(out)
            if s > top_self:
                top_self = s
                top_candidate = c
        # Compute cross scores relative to top evaluator if available
        for cname in candidates:
            own_out = self_outputs.get(cname, "")
            self_score = self.self_assess(own_out)
            cross_scores = []
            for other in candidates:
                if other == cname:
                    continue
                cross_scores.append(self.cross_assess(self_outputs.get(other, ""), own_out))
            cross_avg = sum(cross_scores) / max(len(cross_scores), 1) if cross_scores else 0.0
            combined = (self_score + cross_avg) / 2.0
            scores[cname] = combined
        return scores

    def apply_judge_correction(self, provider_scores: list[ProviderScore], judge_scores: dict[str, float]) -> list[ProviderScore]:
        """Blend provider scores with judge scores (0.7:0.3) and return sorted list."""
        result: list[ProviderScore] = []
        for ps in provider_scores:
            j = judge_scores.get(ps.name, 0.0)
            blended = ps.total * 0.7 + j * 0.3
            ps.total = blended
            result.append(ps)
        result.sort(key=lambda s: -s.total)
        return result

# ═══ Global ═══

_election: HolisticElection | None = None


def get_election() -> HolisticElection:
    global _election
    if _election is None:
        _election = HolisticElection()
    return _election


def get_dynamic_weights(task_type: str = "general") -> dict[str, float]:
    """Return dynamic weights for scoring based on task type (Pattern 5)."""
    t = (task_type or "general").lower()
    base = {
        "elo": 0.08,
        "long_term_reward": 0.06,
        "thompson": 0.10,  # Thompson Sampling — Bayesian prior weight
        "exploration": 0.04,  # Exploration bonus
    }
    if t == "code":
        w = {
            "latency": 0.10,
            "quality": 0.35,
            "cost": 0.10,
            "capability": 0.15,
            "freshness": 0.05,
            "rate_limit": 0.05,
            "cache": 0.10,
            "sticky": 0.10,
        }
        return {**base, **w}
    if t == "long_context":
        w = {
            "latency": 0.10,
            "quality": 0.20,
            "cost": 0.08,
            "capability": 0.15,
            "freshness": 0.05,
            "rate_limit": 0.05,
            "cache": 0.05,
            "sticky": 0.05,
            "hifloat8": 0.27,  # HiFloat8 gives 2.60x boost at 128K
        }
        return {**base, **w}
    if t == "reasoning":
        w = {
            "latency": 0.05,
            "quality": 0.38,
            "cost": 0.08,
            "capability": 0.17,
            "freshness": 0.05,
            "rate_limit": 0.05,
            "cache": 0.10,
            "sticky": 0.10,
            "hifloat8": 0.02,
        }
        return {**base, **w}
    if t == "chat":
        w = {
            "latency": 0.25,
            "quality": 0.20,
            "cost": 0.12,
            "capability": 0.10,
            "freshness": 0.08,
            "rate_limit": 0.05,
            "cache": 0.10,
            "sticky": 0.10,
        }
        return {**base, **w}
    if t == "search":
        w = {
            "latency": 0.15,
            "quality": 0.18,
            "cost": 0.10,
            "capability": 0.20,
            "freshness": 0.12,
            "rate_limit": 0.05,
            "cache": 0.10,
            "sticky": 0.10,
        }
        return {**base, **w}
    if t == "multimodal":
        w = {
            "latency": 0.08,
            "quality": 0.30,
            "cost": 0.15,
            "capability": 0.20,
            "freshness": 0.05,
            "rate_limit": 0.05,
            "cache": 0.07,
            "sticky": 0.10,
        }
        return {**base, **w}
    # general/default
    return {**WEIGHTS, **base}
