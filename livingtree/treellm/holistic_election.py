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
            score.scores["latency"] = 1.0 - min(lat / 5000.0, 0.95)
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
            current: dict[str, float] = {}
            targets: dict[str, float] = {}
            for s in alive_scores:
                current[s.name] = s.total
                # Compute target from per-dimension scores for π*
                dims = dict(s.scores)
                targets[s.name] = sum(v for v in dims.values()) / max(len(dims), 1)
            projected = pto.optimize(current, targets)
            for s in alive_scores:
                s.lpo_score = projected.get(s.name, s.total)
        except Exception:
            pass
        alive_scores.sort(key=lambda s: -(s.lpo_score or s.total))
        return alive_scores

    def record_result(self, name: str, success: bool, latency_ms: float, tokens: int = 0, error: str = "", rate_limited: bool = False, task_type: str = "general"):
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
        # ── CausalEffectTracker: record treatment→outcome ──
        try:
            tracker = get_causal_tracker()
            tracker.record(
                treatment=f"provider:{name}",
                outcome=1.0 if success else 0.0,
                context=task_type,
            )
        except Exception:
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
            cost = 0.003 if name in free_models else 0.02
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
        """Detect task type: embedding-based with keyword fallback."""
        try:
            from .adaptive_classifier import get_adaptive_classifier
            ac = get_adaptive_classifier()
            cat, _ = ac.classify(query, ac.TASK_TYPES, "tasks")
            return cat
        except Exception:
            pass
        return self._detect_task_type_kw(query)

    def _detect_task_type_kw(self, query: str) -> str:
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


def get_dynamic_weights(task_type: str = "general", complexity: float = 0.5) -> dict[str, float]:
    """Return dynamic weights for scoring based on task type and complexity.

    complexity: 0.0 (simple) → 1.0 (complex). Higher complexity shifts
    weight from latency toward quality and capability.

    Inspired by Nested Learning (NeurIPS 2025):
    Weights are learned from feedback — each election result updates the
    weight distribution via exponential moving average toward the ideal
    distribution that would have produced the correct answer.
    """
    t = (task_type or "general").lower()
    base = {
        "elo": 0.08, "long_term_reward": 0.06,
        "thompson": 0.10, "exploration": 0.04,
    }

    # Task-specific base weights (continuously refined by feedback)
    if t == "code":
        w = {
            "latency": 0.08, "quality": 0.28, "cost": 0.08, "capability": 0.12,
            "freshness": 0.04, "rate_limit": 0.04, "cache": 0.08, "sticky": 0.08,
            "elo": 0.06, "long_term_reward": 0.05, "thompson": 0.07, "exploration": 0.02,
        }
    elif t == "long_context":
        w = {
            "latency": 0.07, "quality": 0.14, "cost": 0.06, "capability": 0.11,
            "freshness": 0.04, "rate_limit": 0.04, "cache": 0.04, "sticky": 0.04,
            "hifloat8": 0.20, "elo": 0.06, "long_term_reward": 0.05, "thompson": 0.07, "exploration": 0.08,
        }
    elif t == "reasoning":
        w = {
            "latency": 0.04, "quality": 0.28, "cost": 0.06, "capability": 0.13,
            "freshness": 0.04, "rate_limit": 0.04, "cache": 0.08, "sticky": 0.08,
            "hifloat8": 0.02, "elo": 0.06, "long_term_reward": 0.05, "thompson": 0.07, "exploration": 0.05,
        }
    elif t == "chat":
        w = {
            "latency": 0.20, "quality": 0.16, "cost": 0.10, "capability": 0.08,
            "freshness": 0.06, "rate_limit": 0.04, "cache": 0.08, "sticky": 0.08,
            "elo": 0.06, "long_term_reward": 0.05, "thompson": 0.07, "exploration": 0.02,
        }
    elif t == "search":
        w = {
            "latency": 0.12, "quality": 0.14, "cost": 0.08, "capability": 0.16,
            "freshness": 0.10, "rate_limit": 0.04, "cache": 0.08, "sticky": 0.08,
            "elo": 0.06, "long_term_reward": 0.05, "thompson": 0.07, "exploration": 0.02,
        }
    elif t == "multimodal":
        w = {
            "latency": 0.06, "quality": 0.24, "cost": 0.12, "capability": 0.16,
            "freshness": 0.04, "rate_limit": 0.04, "cache": 0.06, "sticky": 0.08,
            "elo": 0.06, "long_term_reward": 0.05, "thompson": 0.07, "exploration": 0.02,
        }
    else:
        w = {**WEIGHTS, **base}

    # Normalize
    total = sum(w.values())
    if total > 0:
        w = {k: round(v / total, 4) for k, v in w.items()}

    # Nested Learning: EMA-refine weights from feedback history
    w = _apply_feedback_ema(t, w)

    # Complexity-aware adjustment
    if complexity != 0.5:
        delta = (complexity - 0.5) * 0.2
        w["quality"] = round(w.get("quality", 0.23) + delta, 3)
        w["capability"] = round(w.get("capability", 0.12) + delta * 0.8, 3)
        w["latency"] = round(w.get("latency", 0.18) - delta, 3)

    try:
        from .adaptive_weights import get_adaptive_weights
        aw = get_adaptive_weights()
        w = aw.adjust(w, {}, -1, 0, 18)
    except Exception:
        pass
    return w


# Nested Learning: feedback-driven weight refinement
_FEEDBACK_MEMORY: dict[str, list[dict[str, float]]] = {}
_FEEDBACK_EMA_ALPHA = 0.15  # How fast weights adapt to recent results


def record_election_feedback(task_type: str, weights_used: dict, success: bool) -> None:
    """Record election outcome for nested learning weight refinement."""
    if task_type not in _FEEDBACK_MEMORY:
        _FEEDBACK_MEMORY[task_type] = []
    _FEEDBACK_MEMORY[task_type].append({
        **weights_used, "_success": float(success),
    })
    if len(_FEEDBACK_MEMORY[task_type]) > 100:
        _FEEDBACK_MEMORY[task_type] = _FEEDBACK_MEMORY[task_type][-100:]


def _apply_feedback_ema(task_type: str, w: dict[str, float]) -> dict[str, float]:
    """Apply EMA refinement from past election outcomes."""
    history = _FEEDBACK_MEMORY.get(task_type, [])
    if not history:
        return w
    # Compute ideal weights from successful elections
    successful = [h for h in history[-50:] if h.get("_success", 0) > 0]
    if not successful:
        return w
    ideal: dict[str, float] = {}
    for h in successful:
        for k, v in h.items():
            if not k.startswith("_"):
                ideal[k] = ideal.get(k, 0) + v
    n = len(successful)
    for k in ideal:
        ideal[k] /= n
    # EMA: blend toward ideal
    result = {}
    for k in set(list(w.keys()) + list(ideal.keys())):
        current = w.get(k, 0)
        target = ideal.get(k, current)
        result[k] = round(current * (1 - _FEEDBACK_EMA_ALPHA) + target * _FEEDBACK_EMA_ALPHA, 4)
    # Re-normalize
    total = sum(result.values())
    if total > 0:
        result = {k: round(v / total, 4) for k, v in result.items()}
    return result


# ═══════════════════════════════════════════════════════════════════
# CausalEffectTracker — do-calculus reasoning about provider choices
# ═══════════════════════════════════════════════════════════════════

from collections import defaultdict

CAUSAL_FILE = Path(".livingtree/causal_effects.json")


@dataclass
class CausalObservation:
    treatment: str
    outcome: float
    context: str = "general"
    counterfactuals: list[dict] = field(default_factory=list)


@dataclass
class CausalEffect:
    treatment: str
    control: str
    ate: float
    confidence: float
    sample_size: int
    context: str = ""


class CausalEffectTracker:
    _instance: "CausalEffectTracker | None" = None

    @classmethod
    def instance(cls) -> "CausalEffectTracker":
        if cls._instance is None:
            cls._instance = CausalEffectTracker()
        return cls._instance

    def __init__(self):
        self._observations: dict[str, list[CausalObservation]] = defaultdict(list)
        self._effects: dict[str, CausalEffect] = {}

    def record(self, treatment: str, outcome: float,
               context: str = "general",
               counterfactuals: list[dict] = None):
        obs = CausalObservation(
            treatment=treatment, outcome=outcome,
            context=context,
            counterfactuals=counterfactuals or [],
        )
        self._observations[context].append(obs)
        if len(self._observations[context]) > 200:
            self._observations[context] = self._observations[context][-200:]
        if sum(len(v) for v in self._observations.values()) % 20 == 0:
            self._compute_effects()

    def _compute_effects(self):
        for context, obs_list in self._observations.items():
            if len(obs_list) < 10:
                continue
            by_treatment = defaultdict(list)
            for obs in obs_list:
                by_treatment[obs.treatment].append(obs.outcome)
            treatments = list(by_treatment.keys())
            for i in range(len(treatments)):
                for j in range(i + 1, len(treatments)):
                    ti, tj = treatments[i], treatments[j]
                    mean_i = sum(by_treatment[ti]) / len(by_treatment[ti])
                    mean_j = sum(by_treatment[tj]) / len(by_treatment[tj])
                    ate = mean_i - mean_j
                    n = min(len(by_treatment[ti]), len(by_treatment[tj]))
                    conf = min(1.0, n / 30)
                    key = f"{context}:{ti}_vs_{tj}"
                    self._effects[key] = CausalEffect(
                        treatment=ti, control=tj, ate=round(ate, 4),
                        confidence=round(conf, 3), sample_size=n,
                        context=context,
                    )

    def get_effect(self, context: str, treatment: str,
                   control: str) -> CausalEffect | None:
        key = f"{context}:{treatment}_vs_{control}"
        if key in self._effects:
            return self._effects[key]
        key_rev = f"{context}:{control}_vs_{treatment}"
        if key_rev in self._effects:
            eff = self._effects[key_rev]
            return CausalEffect(
                treatment=eff.control, control=eff.treatment,
                ate=-eff.ate, confidence=eff.confidence,
                sample_size=eff.sample_size, context=context,
            )
        return None

    def best_treatment(self, context: str) -> tuple[str, float] | None:
        if context not in self._observations or len(self._observations[context]) < 5:
            return None
        by_treatment = defaultdict(list)
        for obs in self._observations[context]:
            by_treatment[obs.treatment].append(obs.outcome)
        best, best_mean = None, -1.0
        for treatment, outcomes in by_treatment.items():
            mean = sum(outcomes) / len(outcomes)
            if mean > best_mean:
                best_mean = mean
                best = treatment
        return (best, best_mean) if best else None

    def causal_score(self, provider_name: str, context: str = "general") -> float:
        best = self.best_treatment(context)
        if not best:
            return 0.5
        _, best_mean = best
        outcomes = [o.outcome for o in self._observations.get(context, [])
                    if o.treatment == f"provider:{provider_name}"]
        if not outcomes:
            return 0.5
        return sum(outcomes) / max(len(outcomes), 1)

    def report(self, context: str = "") -> dict:
        effects = {}
        for key, eff in self._effects.items():
            if not context or eff.context == context:
                effects[key] = {
                    "treatment": eff.treatment, "control": eff.control,
                    "ate": eff.ate,
                    "interpretation": (
                        f"{eff.treatment} performs {'better' if eff.ate > 0 else 'worse'} "
                        f"than {eff.control} by {abs(eff.ate):.3f} "
                        f"({eff.confidence:.0%} confidence, n={eff.sample_size})"
                    ),
                }
        return {
            "contexts": list(self._observations.keys()),
            "total_observations": sum(len(v) for v in self._observations.values()),
            "effects": effects,
        }

    def stats(self) -> dict:
        return {
            "observations": sum(len(v) for v in self._observations.values()),
            "effects_computed": len(self._effects),
            "contexts": list(self._observations.keys()),
        }


def get_causal_tracker() -> CausalEffectTracker:
    return CausalEffectTracker.instance()


# ═══════════════════════════════════════════════════════════════════
# ABTestManager — provider/routing A/B testing
# ═══════════════════════════════════════════════════════════════════

import random

AB_EXPERIMENTS_FILE = Path(".livingtree/ab_experiments.json")


class ABTestManager:
    _instance: "ABTestManager | None" = None

    @classmethod
    def instance(cls) -> "ABTestManager":
        if cls._instance is None:
            cls._instance = ABTestManager()
        return cls._instance

    def __init__(self):
        self._experiments: dict[str, dict] = {}

    def create(self, exp_id: str, groups: dict[str, dict[str, Any]]) -> bool:
        if exp_id in self._experiments:
            return False
        self._experiments[exp_id] = {
            "groups": groups,
            "results": {g: [] for g in groups},
            "created": time.time(),
        }
        logger.info(f"ABTestManager: created experiment '{exp_id}' ({len(groups)} groups)")
        return True

    def assign(self, exp_id: str) -> str:
        exp = self._experiments.get(exp_id)
        if not exp:
            return ""
        return random.choice(list(exp["groups"].keys()))

    def get_params(self, exp_id: str, group: str) -> dict[str, Any]:
        exp = self._experiments.get(exp_id)
        if not exp:
            return {}
        return dict(exp["groups"].get(group, {}))

    def record(self, exp_id: str, group: str, depth: float,
               latency_ms: float, user_signal: float) -> None:
        exp = self._experiments.get(exp_id)
        if not exp or group not in exp["results"]:
            return
        exp["results"][group].append({
            "depth": depth, "latency": latency_ms, "signal": user_signal,
        })

    def report(self, exp_id: str) -> dict[str, Any]:
        exp = self._experiments.get(exp_id)
        if not exp:
            return {"error": f"Experiment '{exp_id}' not found"}
        report = {"experiment": exp_id, "groups": {}}
        for group, data in exp["results"].items():
            n = len(data)
            if n < 10:
                report["groups"][group] = {"n": n, "status": "insufficient_data"}
                continue
            avg_depth = sum(d["depth"] for d in data) / n
            avg_lat = sum(d["latency"] for d in data) / n
            avg_signal = sum(d["signal"] for d in data) / n
            report["groups"][group] = {
                "n": n, "avg_depth": round(avg_depth, 3),
                "avg_latency_ms": round(avg_lat, 0),
                "avg_signal": round(avg_signal, 3),
            }
        groups = list(report["groups"].keys())
        if len(groups) >= 2 and all(
            report["groups"][g].get("n", 0) >= 10 for g in groups
        ):
            best = max(groups, key=lambda g: report["groups"][g]["avg_depth"])
            report["winner"] = best
        return report

    def stop(self, exp_id: str) -> dict:
        report = self.report(exp_id)
        if exp_id in self._experiments:
            del self._experiments[exp_id]
        return report

    def list_experiments(self) -> list[str]:
        return list(self._experiments.keys())

    def stats(self) -> dict:
        return {"active_experiments": len(self._experiments)}


def get_ab_manager() -> ABTestManager:
    return ABTestManager.instance()


# ═══════════════════════════════════════════════════════════════════
# Ising Model — merged from optimization/ising_model.py
# ═══════════════════════════════════════════════════════════════════

@dataclass
class IsingConfig:
    """An Ising model configuration (spin assignment)."""
    spins: list[int]  # {-1, +1} per spin
    energy: float = float('inf')
    magnetization: float = 0.0  # average spin = order parameter


@dataclass
class IsingOptimizationResult:
    """Full optimization result with convergence data."""
    spin_config: list[int]
    energy: float
    steps_taken: int
    converged: bool
    energy_trace: list[float] = field(default_factory=list)
    magnetization_trace: list[float] = field(default_factory=list)
    phase_transitions: list[dict[str, Any]] = field(default_factory=list)
    acceptance_ratio: float = 0.0


class IsingModel:
    """N-spin Ising model with external fields and pairwise couplings.

    H(s) = -sum_i h_i * s_i - sum_{i<j} J_ij * s_i * s_j

    where s_i ∈ {-1, +1}, h_i is external field on spin i,
    J_ij is coupling between spins i and j.

    Physical interpretation:
      - h_i > 0: spin i prefers +1 (ON neuron)
      - h_i < 0: spin i prefers -1 (OFF neuron)
      - J_ij > 0: ferromagnetic — spins prefer to align (cooperation)
      - J_ij < 0: anti-ferromagnetic — spins prefer to oppose (competition)

    LivingTree mappings:
      - Providers as spins: J_ij encodes pairwise synergy/conflict
      - Strategies as spins: h_i encodes task-specific fitness
      - Pipeline stages as spins: J_ij encodes dependency strength
    """

    def __init__(self, num_spins: int = 12, random_field: float = 0.3):
        self.num_spins = num_spins
        self._h: list[float] = [
            random.uniform(-random_field, random_field)
            for _ in range(num_spins)
        ]
        self._J: list[list[float]] = [
            [0.0] * num_spins for _ in range(num_spins)
        ]
        self._spin_labels: dict[int, str] = {}
        self._config_count: int = 0

    def set_external_field(self, spin_index: int, field: float) -> None:
        if 0 <= spin_index < self.num_spins:
            self._h[spin_index] = field

    def set_coupling(self, i: int, j: int, coupling: float) -> None:
        if 0 <= i < self.num_spins and 0 <= j < self.num_spins and i != j:
            self._J[i][j] = coupling
            self._J[j][i] = coupling

    def set_label(self, spin_index: int, label: str) -> None:
        self._spin_labels[spin_index] = label

    def get_label(self, spin_index: int) -> str:
        return self._spin_labels.get(spin_index, f"spin_{spin_index}")

    def configure_from_scores(self, scores: dict[str, float]) -> None:
        spin_index = 0
        for name, score in sorted(scores.items(), key=lambda x: -x[1]):
            if spin_index >= self.num_spins:
                break
            self._h[spin_index] = math.tanh(score)
            self._spin_labels[spin_index] = name
            spin_index += 1

    def configure_from_affinity_matrix(self, affinity: dict[tuple[str, str], float]) -> None:
        label_to_idx = {v: k for k, v in self._spin_labels.items()}
        for (a, b), affinity_val in affinity.items():
            i = label_to_idx.get(a)
            j = label_to_idx.get(b)
            if i is not None and j is not None:
                self._J[i][j] = affinity_val
                self._J[j][i] = affinity_val

    def energy(self, spins: list[int]) -> float:
        E = 0.0
        for i in range(self.num_spins):
            E -= self._h[i] * spins[i]
        for i in range(self.num_spins):
            for j in range(i + 1, self.num_spins):
                E -= self._J[i][j] * spins[i] * spins[j]
        return E

    def local_field(self, spins: list[int], i: int) -> float:
        field = self._h[i]
        for j in range(self.num_spins):
            if j != i:
                field += self._J[i][j] * spins[j]
        return field

    def energy_delta(self, spins: list[int], i: int) -> float:
        return 2.0 * spins[i] * self.local_field(spins, i)

    def magnetization(self, spins: list[int]) -> float:
        return sum(spins) / self.num_spins

    def random_config(self) -> list[int]:
        return [1 if random.random() > 0.5 else -1 for _ in range(self.num_spins)]

    def all_up(self) -> list[int]:
        return [1] * self.num_spins

    def all_down(self) -> list[int]:
        return [-1] * self.num_spins

    def flip_spin(self, spins: list[int], i: int) -> list[int]:
        new_spins = list(spins)
        new_spins[i] = -new_spins[i]
        return new_spins

    def detect_phase(self, spins: list[int], T: float) -> str:
        m = abs(self.magnetization(spins))
        tc_estimate = self.num_spins * 0.3

        if T < 0.1 * tc_estimate and m > 0.8:
            return "ferromagnetic"
        elif T > tc_estimate and m < 0.3:
            return "paramagnetic"
        elif T < 0.5 * tc_estimate and m < 0.5:
            return "spin_glass"
        return "critical"


class IsingOptimizer:
    """Metropolis-Hastings Monte Carlo optimizer for Ising ground state search.

    Simulated annealing with Fowler-Nordheim tunneling:
      1. Start at high T → explore config space randomly (paramagnetic phase)
      2. Cool T(t) = T0 / log(e + t) → gradually settle (critical → ordered)
      3. At low T, Metropolis acceptance rejects most uphill moves
      4. Fowler-Nordheim tunneling escapes local minima when stuck
    """

    def __init__(
        self,
        model: IsingModel,
        enable_tunneling: bool = True,
        tunnel_threshold: int = 30,
    ):
        self.model = model
        self._enable_tunneling = enable_tunneling
        self._tunnel_threshold = tunnel_threshold

    def metropolis_step(self, spins: list[int], T: float) -> tuple[list[int], bool, float]:
        i = random.randrange(self.model.num_spins)
        dE = self.model.energy_delta(spins, i)

        accept = False
        if dE <= 0:
            accept = True
        elif T > 0:
            p_accept = math.exp(-dE / T)
            accept = random.random() < p_accept

        new_spins = self.model.flip_spin(spins, i) if accept else list(spins)
        return new_spins, accept, dE

    def find_ground_state(
        self,
        temperature: float = 1.0,
        min_temperature: float = 0.001,
        max_steps: int = 1000,
        log_interval: int = 100,
    ) -> IsingOptimizationResult:
        spins = self.model.random_config()
        best_spins = list(spins)
        best_energy = self.model.energy(spins)

        energy_trace: list[float] = []
        mag_trace: list[float] = []
        phase_transitions: list[dict[str, Any]] = []
        accept_count = 0
        stagnation = 0
        last_phase = ""

        for step in range(1, max_steps + 1):
            T = temperature / math.log(math.e + step)
            T = max(T, min_temperature)

            spins, accepted, dE = self.metropolis_step(spins, T)
            if accepted:
                accept_count += 1

            current_E = self.model.energy(spins)
            energy_trace.append(current_E)
            mag_trace.append(self.model.magnetization(spins))

            if current_E < best_energy:
                best_energy = current_E
                best_spins = list(spins)
                stagnation = 0
            else:
                stagnation += 1

            phase = self.model.detect_phase(spins, T)
            if phase != last_phase:
                phase_transitions.append({
                    "step": step, "from": last_phase, "to": phase,
                    "temperature": T, "energy": current_E,
                })
                last_phase = phase

            if self._enable_tunneling and stagnation >= self._tunnel_threshold:
                tunnel_spins = self.model.random_config()
                tunnel_E = self.model.energy(tunnel_spins)
                dE_tunnel = tunnel_E - current_E
                if dE_tunnel <= 0 or (T > min_temperature and random.random() < math.exp(-dE_tunnel / (T * 0.5))):
                    spins = tunnel_spins
                    stagnation = 0

            if step % log_interval == 0:
                logger.debug(
                    f"Ising step {step}: T={T:.4f}, E={current_E:.4f}, "
                    f"best_E={best_energy:.4f}, m={self.model.magnetization(spins):.3f}, "
                    f"phase={phase}"
                )

        acceptance_ratio = accept_count / max_steps if max_steps > 0 else 0.0

        result = IsingOptimizationResult(
            spin_config=best_spins,
            energy=best_energy,
            steps_taken=max_steps,
            converged=stagnation >= self._tunnel_threshold * 2,
            energy_trace=energy_trace,
            magnetization_trace=mag_trace,
            phase_transitions=phase_transitions,
            acceptance_ratio=acceptance_ratio,
        )
        return result

    def config_to_labels(self, spins: list[int]) -> dict[str, int]:
        return {
            self.model.get_label(i): spins[i]
            for i in range(min(len(spins), self.model.num_spins))
        }

    def config_to_active_set(self, spins: list[int]) -> list[str]:
        return [
            self.model.get_label(i)
            for i in range(min(len(spins), self.model.num_spins))
            if spins[i] == 1
        ]

    def compute_spin_correlations(self, config: list[int]) -> dict[tuple[int, int], float]:
        corr = {}
        n = min(len(config), self.model.num_spins)
        for i in range(n):
            for j in range(i + 1, n):
                corr[(i, j)] = config[i] * config[j]
        return corr


def build_provider_ising(provider_scores: dict[str, float]) -> tuple[IsingModel, IsingOptimizer]:
    providers = list(provider_scores.keys())
    model = IsingModel(num_spins=max(len(providers), 4))
    for i, name in enumerate(providers):
        model.set_label(i, name)
        model.set_external_field(i, provider_scores[name])
    for i in range(len(providers)):
        for j in range(i + 1, len(providers)):
            diff = abs(provider_scores[providers[i]] - provider_scores[providers[j]])
            model.set_coupling(i, j, -0.3 + diff * 0.5)
    optimizer = IsingOptimizer(model, enable_tunneling=True, tunnel_threshold=20)
    return model, optimizer


def build_strategy_ising(strategy_scores: dict[str, float]) -> tuple[IsingModel, IsingOptimizer]:
    strategies = list(strategy_scores.keys())
    model = IsingModel(num_spins=max(len(strategies), 4))
    for i, name in enumerate(strategies):
        model.set_label(i, name)
        model.set_external_field(i, strategy_scores[name])
    for i in range(len(strategies)):
        for j in range(i + 1, len(strategies)):
            avg = (strategy_scores[strategies[i]] + strategy_scores[strategies[j]]) / 2
            model.set_coupling(i, j, 0.2 * avg)
    optimizer = IsingOptimizer(model, enable_tunneling=True, tunnel_threshold=15)
    return model, optimizer


_ising_optimizer: Optional[IsingOptimizer] = None
_ising_lock = threading.Lock()


def get_ising_optimizer(num_spins: int = 16) -> IsingOptimizer:
    global _ising_optimizer
    if _ising_optimizer is None:
        with _ising_lock:
            if _ising_optimizer is None:
                model = IsingModel(num_spins=num_spins)
                _ising_optimizer = IsingOptimizer(model, enable_tunneling=True)
                logger.info("IsingOptimizer initialized with {} spins", num_spins)
    return _ising_optimizer
