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
from pathlib import Path
from typing import Any

from loguru import logger

STATS_FILE = Path(".livingtree/election_stats.json")

# Scoring weights (sum to 1.0)
WEIGHTS = {
    "latency": 0.20,    # Speed matters
    "quality": 0.25,     # Success matters most
    "cost": 0.16,        # Free preferred
    "capability": 0.13,  # Task match
    "freshness": 0.06,   # Prefer recently-used providers
    "rate_limit": 0.08,  # Penalize throttled providers
    "cache": 0.12,       # Prefer providers with high cache hit rates
}

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
}


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
    ) -> list[ProviderScore]:
        """Score all candidates holistically. Returns ranked list."""
        results = []

        # Phase 1: Ping all alive candidates
        alive_scores = []
        for name in candidates:
            p = providers.get(name)
            if not p:
                continue
            stats = self.get_stats(name)
            ok, latency = await p.ping()
            if not ok:
                continue

            score = ProviderScore(
                name=name,
                alive=True,
                is_free=name in free_models,
                latency_ms=latency,
                success_rate=stats.success_rate,
                last_used=stats.last_used,
            )

            # Score 1: Latency (normalized: faster = higher score)
            max_latency = max(max(100, stats.avg_latency_ms), latency)
            score.scores["latency"] = 1.0 - min(latency / max_latency, 0.95)

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

            # Weighted total
            score.total = sum(
                WEIGHTS[k] * score.scores.get(k, 0)
                for k in WEIGHTS
            )
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

    def record_result(self, name: str, success: bool, latency_ms: float, tokens: int = 0, error: str = "", rate_limited: bool = False):
        stats = self.get_stats(name)
        stats.record(success, latency_ms, tokens, error, rate_limited)
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


# ═══ Global ═══

_election: HolisticElection | None = None


def get_election() -> HolisticElection:
    global _election
    if _election is None:
        _election = HolisticElection()
    return _election
