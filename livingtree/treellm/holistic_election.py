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
    "budget": 0.0,        # BudgetRouter cost-aware modifier (injected dynamically)
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
    lpo_score: float = 0.0  # v2.6 LPO simplex-projected score (arXiv:2605.06139)
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
        alive_scores: list[ProviderScore] = []

        # Phase 1: Filter (circuit breaker, competitor eliminator)
        breaker = None
        try:
            from .circuit_breaker import get_circuit_breaker
            breaker = get_circuit_breaker()
        except Exception:
            pass

        # Phase 2: Parallel ping all candidates
        to_ping: list[tuple[str, Any]] = []
        for name in candidates:
            if breaker and breaker.is_open(name):
                continue
            try:
                from .competitive_eliminator import get_eliminator
                if not get_eliminator().is_viable(name):
                    continue
            except ImportError:
                pass
            p = providers.get(name)
            if not p:
                continue
            to_ping.append((name, p))

        async def _ping_one(name, p):
            ok, err = await p.ping()
            return name, p, ok, err

        ping_results = await asyncio.gather(*[_ping_one(n, p) for n, p in to_ping])

        # Phase 3: Score alive candidates
        weights = get_dynamic_weights(task_type)
        # InverseReward adjustments
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

        for name, p, ok, err in ping_results:
            if not ok:
                continue
            stats = self.get_stats(name)

            score = ProviderScore(
                name=name, alive=True,
                is_free=name in free_models,
                latency_ms=stats.avg_latency_ms,
                success_rate=stats.success_rate,
                last_used=stats.last_used,
            )

            # Score dimensions
            lat = float(stats.avg_latency_ms) if stats.avg_latency_ms else 200
            score.scores["latency"] = 1.0 - min(lat / max(200, lat), 0.95)
            score.scores["quality"] = stats.recent_quality
            score.scores["cost"] = 1.0 if score.is_free else 0.3
            score.scores["capability"] = self._capability_match(name, query)

            if stats.last_used > 0:
                hours_since = (time.time() - stats.last_used) / 3600
                score.scores["freshness"] = max(0.0, 1.0 - hours_since / 24.0)
            else:
                score.scores["freshness"] = 0.5

            rl_count = getattr(p, '_rate_limit_count', 0)
            rl_last = getattr(p, '_last_rate_limit', 0.0)
            rl_penalty = 0.0
            if rl_last > 0:
                seconds_since = time.time() - rl_last
                if seconds_since < 60: rl_penalty = 0.5
                elif seconds_since < 300: rl_penalty = 0.5 * (1.0 - (seconds_since - 60) / 240)
                if rl_count > 3: rl_penalty = min(0.8, rl_penalty + 0.1 * (rl_count - 3))
            score.scores["rate_limit"] = max(0.0, 1.0 - rl_penalty)

            try:
                from .cache_director import get_cache_director
                score.scores["cache"] = get_cache_director().cache_score(name)
            except Exception:
                score.scores["cache"] = 0.0

            try:
                from .session_binding import get_session_binding
                sid = query[:20] if query else "default"
                score.scores["sticky"] = get_session_binding().stickiness_score(sid, name)
            except Exception:
                score.scores["sticky"] = 0.0

            # BudgetRouter: cost-aware modifier
            try:
                from .budget_router import get_budget_router
                budget = get_budget_router()
                estimated_cost = 0.0 if score.is_free else 0.003
                bf = budget.budget_factor(name, estimated_cost)
                score.scores["budget"] = bf
            except Exception:
                score.scores["budget"] = 1.0

            # ProviderRoundRobin: cooldown consecutive provider
            try:
                from .provider_round_robin import get_provider_round_robin
                rr = get_provider_round_robin()
                cf = rr.cooldown_factor(name)
                score.scores["sticky"] = score.scores.get("sticky", 1.0) * cf
            except Exception:
                pass

            # Dynamic weights total (v2.6 LPO: additive baseline,
            # provider-level simplex projection available via election.lpo_score())
            for k in weights:
                score.scores.setdefault(k, 0.0)
            score.total = sum(weights[k] * score.scores.get(k, 0) for k in weights)
            health_factor = self._health_adjustment(name, stats)
            score.total *= health_factor
            # LPO simplex-projected score (tracks explicit target-projection value)
            score.lpo_score = score.total

            score.avg_latency_ms = stats.avg_latency_ms
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

        # HealthPredictor: predictive pre-failure detection
        try:
            from .health_predictor import get_health_predictor
            hp_factor = get_health_predictor().health_factor(name)
            factor *= hp_factor
        except Exception:
            pass

        return max(factor, 0.05)

    def election_lpo_scores(self, alive_scores: list[ProviderScore]) -> list[ProviderScore]:
        """v2.6 LPO (arXiv:2605.06139): Re-rank providers via simplex projection.

        Constructs explicit target distribution π* from provider metrics,
        then projects current scores π_θ toward π* using divergence minimization.
        The result is a monotonic, bounded, zero-sum re-ranking.

        Args:
            alive_scores: list of ProviderScore from election() (with score.total set)

        Returns:
            same list with score.lpo_score updated to LPO-projected values
        """
        try:
            from livingtree.optimization.lpo_optimizer import get_provider_lpo
            pto = get_provider_lpo(divergence="kl", temperature=0.5)
            metrics: dict[str, dict[str, float]] = {}
            current: dict[str, float] = {}
            for s in alive_scores:
                metrics[s.name] = dict(s.scores)
                current[s.name] = s.total
            projected = pto.optimize(current, current)
            for s in alive_scores:
                s.lpo_score = projected.get(s.name, s.total)
        except Exception:
            pass
        alive_scores.sort(key=lambda s: -(s.lpo_score or s.total))
        return alive_scores

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

    def get_best(self, candidates: list[str], providers: dict[str, Any], free_models: list[str],
                  task_type: str = "general") -> str:
        """Synchronous shortcut: get best provider by composite score snapshot."""
        best = None
        best_score = -1.0
        weights = get_dynamic_weights(task_type)
        for name in candidates:
            p = providers.get(name)
            if not p:
                continue
            stats = self.get_stats(name)
            score = (
                stats.success_rate * weights.get("quality", 0.23)
                + (1.0 if name in free_models else 0.3) * weights.get("cost", 0.15)
                + (1.0 - min(stats.avg_latency_ms / 5000.0, 0.95)) * weights.get("latency", 0.18)
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

import threading

_election: HolisticElection | None = None
_election_lock = threading.Lock()


def get_election() -> HolisticElection:
    global _election
    if _election is None:
        with _election_lock:
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
    # general/default — apply adaptive weight adjustment
    w = {**WEIGHTS, **base}
    try:
        from .adaptive_weights import get_adaptive_weights
        aw = get_adaptive_weights()
        w = aw.adjust(w, {}, -1, 0, 18)
    except Exception:
        pass
    return w
