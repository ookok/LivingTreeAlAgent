"""Unified multi-strategy provider router.

Merges 6 previously independent routing strategies into a single pluggable
entry point.  Strategies are selectable at runtime via `strategy=` kwarg.

Strategies:
  learned     — EMA cross-session learning (default, from route_learner)
  thompson    — Bayesian Thompson sampling with Beta beliefs (bandit_router)
  budget      — Cost-aware budget enforcement (budget_router)
  fitness     — Squeeze-Evolve adaptive fitness routing (fitness_router)
  predictive  — Historical pattern prediction (predictive_router)
  score_match — Diffusion-based score matching (score_matching_router)

Usage:
    from livingtree.treellm.router import (
        UnifiedRouter, get_router,
        RouteLearner, LearnedProfile, RoutingWeight,  # backward-compat
    )
    router = get_router()
    decision = router.select(task="code review", candidates=["p1","p2"])
    router.record(decision, success=True)
"""

from __future__ import annotations

import json
import math
import random
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

_STATE_DIR = Path(".livingtree/meta")
_STATE_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════
# Shared data types
# ═══════════════════════════════════════════════════════════════════


@dataclass
class RoutingCandidate:
    """Unified candidate representation for all strategies."""
    name: str
    quality_score: float = 0.5
    latency_score: float = 0.5
    cost_score: float = 0.5
    capability_score: float = 0.5
    is_free: bool = False
    cost_per_1k: float = 0.0
    avg_latency_ms: float = 500.0


@dataclass
class RoutingDecision:
    """Result from any routing strategy."""
    provider: str
    strategy: str = ""
    score: float = 0.5
    meta: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════
# Persistence helpers (shared by strategies)
# ═══════════════════════════════════════════════════════════════════


def _load_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return {}


def _save_json(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.debug(f"Router save {path.name}: {e}")


# ═══════════════════════════════════════════════════════════════════
# Strategy 1: Learned (originally route_learner.py — ACTIVE)
# ═══════════════════════════════════════════════════════════════════


@dataclass
class LearnedProfile:
    """Distilled model capability profile."""
    model_id: str
    provider: str = ""
    context_length: int = 4096
    reasoning: bool = False
    tool_call: bool = False
    structured_output: bool = False
    supports_images: bool = False
    is_free: bool = False
    cost_score: float = 0.5
    capability_score: float = 0.5

    @property
    def composite_score(self) -> float:
        return round(
            self.capability_score * 0.4
            + (1.0 - self.cost_score) * 0.3
            + (self.context_length / 1_000_000) * 0.3, 4)


@dataclass
class RoutingWeight:
    """Per-task-type per-model routing weight."""
    model_id: str
    task_type: str
    weight: float = 1.0
    success_rate: float = 0.5
    avg_latency_ms: float = 0.0
    sample_count: int = 0
    last_used: float = 0.0
    last_updated: float = field(default_factory=time.time)


class RouteLearner:
    """EMA-based cross-session routing weight learner (active default)."""

    DOMAIN_CAPABILITY_BONUS: dict[str, dict[str, float]] = {
        "code_engineering": {"tool_call": 0.3, "structured_output": 0.2, "context_length": 0.2},
        "environmental_report": {"structured_output": 0.3, "context_length": 0.3},
        "data_analysis": {"tool_call": 0.2, "reasoning": 0.3},
        "question": {"cost_score": 0.4},
        "general": {},
    }

    def __init__(self):
        self._profiles: dict[str, LearnedProfile] = {}
        self._weights: dict[str, dict[str, RoutingWeight]] = defaultdict(dict)
        self._loaded = False
        self._load()

    # ── Selection ──

    def select(self, task: str, candidates: list[str],
               task_type: str = "general") -> RoutingDecision:
        """Select best provider via learned weights."""
        ranked = self.get_routing_weights(task_type)
        for mid, w, _ in ranked:
            for c in candidates:
                if c == mid or mid in c or c in mid:
                    return RoutingDecision(provider=c, strategy="learned",
                                           score=w, meta={"task_type": task_type})
        fallback = candidates[0] if candidates else ""
        return RoutingDecision(provider=fallback, strategy="learned",
                               score=0.5, meta={"fallback": True})

    def record(self, decision: RoutingDecision, success: bool,
               latency_ms: float = 0, model_id: str = "",
               task_type: str = "general") -> None:
        """Record outcome and update weights."""
        mid = model_id or decision.provider
        tt = task_type or decision.meta.get("task_type", "general")
        w = self._weights[tt].get(mid)
        if w is None:
            w = RoutingWeight(model_id=mid, task_type=tt)
            self._weights[tt][mid] = w
        sv = 1.0 if success else 0.0
        w.success_rate = round(0.8 * w.success_rate + 0.2 * sv, 3)
        w.avg_latency_ms = round(
            0.8 * w.avg_latency_ms + 0.2 * latency_ms, 1) if w.avg_latency_ms else latency_ms
        w.sample_count += 1
        w.last_used = time.time()
        w.last_updated = time.time()
        profile = self._profiles.get(mid)
        base = profile.composite_score if profile else 0.5
        recency = min(1.5, 1.0 + w.sample_count * 0.05)
        w.weight = round(base * w.success_rate * recency, 4)
        if w.sample_count % 20 == 0:
            self._save()

    def learn_from_fitness(self, trajectories: list[dict] | None = None) -> int:
        """Update weights from fitness landscape history."""
        if trajectories is None:
            try:
                from ..execution.fitness_landscape import get_fitness_landscape
                landscape = get_fitness_landscape()
                trajectories = [{
                    "model_id": ts.trajectory_id, "task_type": "general",
                    "success": ts.fitness.reliability > 0.5, "latency_ms": ts.total_ms,
                } for ts in landscape._trajectories.values()]
            except Exception:
                return 0
        updated = 0
        for t in trajectories:
            mid = t.get("model_id", "")
            tt = t.get("task_type", "general")
            if not mid:
                continue
            w = self._weights[tt].get(mid)
            if w is None:
                w = RoutingWeight(model_id=mid, task_type=tt)
                self._weights[tt][mid] = w
            sv = 1.0 if t.get("success") else 0.0
            w.success_rate = round(0.8 * w.success_rate + 0.2 * sv, 3)
            lat = t.get("latency_ms", 0)
            w.avg_latency_ms = round(
                0.8 * w.avg_latency_ms + 0.2 * lat, 1) if w.avg_latency_ms else lat
            w.sample_count += 1
            profile = self._profiles.get(mid)
            base = profile.composite_score if profile else 0.5
            w.weight = round(base * w.success_rate * min(1.5, 1.0 + w.sample_count * 0.05), 4)
            updated += 1
        if updated:
            self._save()
        return updated

    def get_routing_weights(self, task_type: str = "general", top_n: int = 10
                            ) -> list[tuple[str, float, LearnedProfile | None]]:
        merged: dict[str, float] = {}
        for mid, w in self._weights.get("general", {}).items():
            merged[mid] = w.weight
        for mid, w in self._weights.get(task_type, {}).items():
            merged[mid] = w.weight * 1.2
        bonuses = self.DOMAIN_CAPABILITY_BONUS.get(task_type, {})
        for mid in merged:
            profile = self._profiles.get(mid)
            if profile and bonuses:
                for cap, bonus in bonuses.items():
                    if getattr(profile, cap, False) or cap == "context_length":
                        if cap == "context_length":
                            merged[mid] += bonus * (profile.context_length / 1_000_000)
                        else:
                            merged[mid] += bonus
        ranked = sorted(merged.items(), key=lambda x: x[1], reverse=True)
        return [(mid, w, self._profiles.get(mid)) for mid, w in ranked[:top_n]]

    def best_model_for(self, task_type: str = "general") -> str | None:
        ranked = self.get_routing_weights(task_type, top_n=1)
        return ranked[0][0] if ranked else None

    def stats(self) -> dict[str, Any]:
        total_weights = sum(len(w) for w in self._weights.values())
        total_samples = sum(w.sample_count for tw in self._weights.values() for w in tw.values())
        return {
            "strategy": "learned", "profiles": len(self._profiles),
            "weights": total_weights, "task_types": len(self._weights),
            "total_samples": total_samples,
            "best_code": self.best_model_for("code_engineering"),
            "best_env": self.best_model_for("environmental_report"),
        }

    def _save(self):
        data = {
            "profiles": {mid: {
                "model_id": p.model_id, "provider": p.provider,
                "context_length": p.context_length, "reasoning": p.reasoning,
                "tool_call": p.tool_call, "capability_score": p.capability_score,
                "cost_score": p.cost_score,
            } for mid, p in self._profiles.items()},
            "weights": {tt: {mid: {
                "model_id": w.model_id, "task_type": w.task_type,
                "weight": w.weight, "success_rate": w.success_rate,
                "sample_count": w.sample_count, "last_updated": w.last_updated,
            } for mid, w in tw.items()} for tt, tw in self._weights.items()},
        }
        _save_json(_STATE_DIR / "route_weights.json", data)

    def _load(self):
        data = _load_json(_STATE_DIR / "route_weights.json")
        for mid, pd in data.get("profiles", {}).items():
            self._profiles[mid] = LearnedProfile(**pd)
        for tt, td in data.get("weights", {}).items():
            for mid, wd in td.items():
                self._weights[tt][mid] = RoutingWeight(**wd)
        if data:
            self._loaded = True


# ═══════════════════════════════════════════════════════════════════
# Strategy 2: Thompson (originally bandit_router.py)
# ═══════════════════════════════════════════════════════════════════


class BetaBelief:
    """Beta-distribution belief for a single metric dimension."""
    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        self.alpha = prior_alpha
        self.beta = prior_beta
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta

    @property
    def mean(self) -> float:
        d = self.alpha + self.beta
        return self.alpha / d if d > 0 else 0.5

    @property
    def uncertainty(self) -> float:
        d = (self.alpha + self.beta) ** 2 * (self.alpha + self.beta + 1)
        return math.sqrt(self.alpha * self.beta / d) if d > 0 else 0.5

    def observe(self, success: bool, weight: float = 1.0) -> None:
        if success:
            self.alpha += weight
        else:
            self.beta += weight

    def sample(self) -> float:
        return random.betavariate(self.alpha, self.beta)

    def decay(self, rate: float = 0.001) -> None:
        self.alpha = self.prior_alpha + (self.alpha - self.prior_alpha) * (1 - rate)
        self.beta = self.prior_beta + (self.beta - self.prior_beta) * (1 - rate)


class ThompsonStrategy:
    """Bayesian multi-armed bandit with Thompson sampling."""

    def __init__(self, kl_budget: float = 0.1, decay_rate: float = 0.0001):
        self._arms: dict[str, dict[str, BetaBelief]] = {}
        self._kl_budget = kl_budget
        self._decay_rate = decay_rate
        self._total_selections = 0

    def _get_arm(self, provider: str) -> dict[str, BetaBelief]:
        if provider not in self._arms:
            self._arms[provider] = {
                "quality": BetaBelief(), "latency": BetaBelief(2, 1), "cost": BetaBelief()}
        return self._arms[provider]

    def select(self, task: str, candidates: list[str],
               task_type: str = "general") -> RoutingDecision:
        """Thompson-sample the best provider."""
        self._total_selections += 1
        best_name, best_score = "", -1.0
        for name in candidates:
            arm = self._get_arm(name)
            q = arm["quality"].sample()
            l = arm["latency"].sample()
            c = arm["cost"].sample()
            score = q * 0.5 + l * 0.25 + c * 0.25
            total_c = max(1, self._total_selections)
            arm_calls = max(1, sum(1 for k in arm if hasattr(arm[k], 'alpha')))
            bonus = self._kl_budget * arm["quality"].uncertainty * math.sqrt(
                math.log(total_c) / arm_calls)
            score += bonus
            if score > best_score:
                best_score, best_name = score, name
            arm["quality"].decay(self._decay_rate)
        return RoutingDecision(provider=best_name or (candidates[0] if candidates else ""),
                               strategy="thompson", score=best_score)

    def record(self, decision: RoutingDecision, success: bool,
               latency_ms: float = 0, cost_yuan: float = 0, **kw) -> None:
        arm = self._get_arm(decision.provider)
        arm["quality"].observe(success)
        latency_ok = max(0.0, min(1.0, 1.0 - latency_ms / 10000.0))
        arm["latency"].observe(latency_ok > 0.5, weight=abs(latency_ok - 0.5) * 2)
        cost_ok = max(0.0, min(1.0, 1.0 - cost_yuan / 0.1))
        arm["cost"].observe(cost_ok > 0.5, weight=abs(cost_ok - 0.5) * 2)

    def stats(self) -> dict:
        return {"strategy": "thompson", "arms": len(self._arms),
                "selections": self._total_selections}


# ═══════════════════════════════════════════════════════════════════
# Strategy 3: Budget (originally budget_router.py)
# ═══════════════════════════════════════════════════════════════════


class BudgetStrategy:
    """Cost-aware routing with per-provider budget caps."""

    def __init__(self):
        self._budgets: dict[str, dict] = {}
        self._today = time.strftime("%Y-%m-%d")
        self._load()

    def _ensure_today(self):
        today = time.strftime("%Y-%m-%d")
        if today != self._today:
            for b in self._budgets.values():
                b["daily_spent"] = 0.0
            self._today = today

    def select(self, task: str, candidates: list[str],
               task_type: str = "general") -> RoutingDecision:
        """Return provider with best budget headroom."""
        self._ensure_today()
        best_name, best_factor = candidates[0] if candidates else "", 0.0
        for name in candidates:
            factor = self._budget_factor(name)
            if factor > best_factor:
                best_factor, best_name = factor, name
        return RoutingDecision(provider=best_name, strategy="budget",
                               score=best_factor, meta={"exhausted": best_factor == 0.0})

    def _budget_factor(self, name: str, estimated_cost: float = 0.001) -> float:
        if estimated_cost <= 0:
            return 1.0
        b = self._budgets.get(name, {})
        if not b or b.get("is_free"):
            return 1.0
        dl = b.get("daily_limit", 2.0)
        ml = b.get("monthly_limit", 10.0)
        ds = b.get("daily_spent", 0.0)
        ms = b.get("monthly_spent", 0.0)
        if ds + estimated_cost > dl or ms + estimated_cost > ml:
            return 0.0
        dp = ds / max(dl, 0.01)
        mp = ms / max(ml, 0.01)
        if dp > 0.9 or mp > 0.9:
            return 0.3
        if dp > 0.7 or mp > 0.7:
            return 0.5
        if dp > 0.5:
            return 0.7
        return 1.0

    def record(self, decision: RoutingDecision, success: bool,
               cost_yuan: float = 0, **kw) -> None:
        if cost_yuan <= 0:
            return
        self._ensure_today()
        name = decision.provider
        if name not in self._budgets:
            self._budgets[name] = {"daily_spent": 0, "monthly_spent": 0,
                                   "daily_limit": 2.0, "monthly_limit": 10.0, "is_free": False}
        self._budgets[name]["daily_spent"] += cost_yuan
        self._budgets[name]["monthly_spent"] += cost_yuan
        self._save()

    def stats(self) -> dict:
        self._ensure_today()
        return {"strategy": "budget", "providers": len(self._budgets),
                "budgets": {k: {"daily": round(v["daily_spent"], 4),
                                "monthly": round(v["monthly_spent"], 4)}
                            for k, v in self._budgets.items()}}

    def _save(self):
        _save_json(_STATE_DIR / "budget_state.json", self._budgets)

    def _load(self):
        self._budgets = _load_json(_STATE_DIR / "budget_state.json")


# ═══════════════════════════════════════════════════════════════════
# Strategy 4: Fitness (originally fitness_router.py)
# ═══════════════════════════════════════════════════════════════════


class FitnessStrategy:
    """Squeeze-Evolve adaptive fitness-based routing with percentile thresholds."""

    def __init__(self, window_size: int = 50):
        self._decisions: deque[RoutingDecision] = deque(maxlen=window_size)
        self._threshold_low = 0.30
        self._threshold_high = 0.70
        self._tier_stats = {"pro": {"d": 0, "s": 0}, "mid": {"d": 0, "s": 0},
                            "flash": {"d": 0, "s": 0}, "skip": {"d": 0, "s": 0}}
        self._decision_count = 0
        self._load()

    def select(self, task: str, candidates: list[str],
               task_type: str = "general") -> RoutingDecision:
        self._decision_count += 1
        if not candidates:
            return RoutingDecision(provider="", strategy="fitness", score=0.0)
        best = candidates[0]
        tier = "mid"
        if self._decision_count > 10:
            flash_rate = (self._tier_stats["flash"]["s"]
                          / max(self._tier_stats["flash"]["d"], 1))
            if flash_rate > 0.7 and self._threshold_high < 0.85:
                self._threshold_high += 0.02
        decision = RoutingDecision(
            provider=best, strategy="fitness", score=0.5,
            meta={"tier": tier, "threshold_low": self._threshold_low})
        self._decisions.append(decision)
        return decision

    def record(self, decision: RoutingDecision, success: bool, **kw) -> None:
        tier = decision.meta.get("tier", "mid")
        if tier in self._tier_stats:
            self._tier_stats[tier]["d"] += 1
            if success:
                self._tier_stats[tier]["s"] += 1

    def stats(self) -> dict:
        return {"strategy": "fitness", "decisions": self._decision_count,
                "threshold_low": round(self._threshold_low, 3),
                "threshold_high": round(self._threshold_high, 3)}

    def _save(self):
        _save_json(_STATE_DIR / "fitness_router.json", {
            "threshold_low": self._threshold_low,
            "threshold_high": self._threshold_high,
            "decision_count": self._decision_count, "tier_stats": self._tier_stats})

    def _load(self):
        d = _load_json(_STATE_DIR / "fitness_router.json")
        if d:
            self._threshold_low = d.get("threshold_low", 0.30)
            self._threshold_high = d.get("threshold_high", 0.70)
            self._decision_count = d.get("decision_count", 0)
            for tier, s in d.get("tier_stats", {}).items():
                if tier in self._tier_stats:
                    self._tier_stats[tier].update(s)


# ═══════════════════════════════════════════════════════════════════
# Strategy 5: Predictive (originally predictive_router.py)
# ═══════════════════════════════════════════════════════════════════


class PredictiveStrategy:
    """Predict provider availability from historical patterns."""

    def __init__(self):
        self._hourly: dict[str, dict[int, float]] = defaultdict(dict)
        self._daily: dict[str, dict[int, float]] = defaultdict(dict)
        self._latencies: dict[str, list[float]] = defaultdict(list)
        self._errors: dict[str, list[bool]] = defaultdict(list)
        self._hits = 0
        self._misses = 0
        self._load()

    def select(self, task: str, candidates: list[str],
               task_type: str = "general") -> RoutingDecision:
        hour = time.localtime().tm_hour
        wday = time.localtime().tm_wday
        scored = []
        for name in candidates:
            hp = self._hourly.get(name, {}).get(hour, 0.5)
            dp = self._daily.get(name, {}).get(wday, 0.5)
            lt = self._latency_trend(name)
            er = 1.0 - self._error_rate(name)
            scored.append((name, hp * 0.35 + dp * 0.25 + lt * 0.15 + er * 0.25))
        scored.sort(key=lambda x: -x[1])
        best = scored[0][0] if scored else (candidates[0] if candidates else "")
        return RoutingDecision(provider=best, strategy="predictive",
                               score=scored[0][1] if scored else 0.5)

    def record(self, decision: RoutingDecision, success: bool,
               latency_ms: float = 0, **kw) -> None:
        name = decision.provider
        hour = time.localtime().tm_hour
        wday = time.localtime().tm_wday
        old_h = self._hourly[name].get(hour, 0.5)
        self._hourly[name][hour] = old_h * 0.85 + (1.0 if success else 0.0) * 0.15
        old_d = self._daily[name].get(wday, 0.5)
        self._daily[name][wday] = old_d * 0.85 + (1.0 if success else 0.0) * 0.15
        self._latencies[name].append(latency_ms)
        if len(self._latencies[name]) > 50:
            self._latencies[name] = self._latencies[name][-50:]
        self._errors[name].append(not success)
        if len(self._errors[name]) > 50:
            self._errors[name] = self._errors[name][-50:]
        if success:
            self._hits += 1
        else:
            self._misses += 1
        if len(self._latencies[name]) % 20 == 0:
            self._save()

    def _latency_trend(self, name: str) -> float:
        recent = self._latencies.get(name, [])
        if len(recent) < 3:
            return 0.5
        first = sum(recent[:3]) / 3
        last = sum(recent[-3:]) / 3
        if last <= first * 1.05:
            return 1.0
        if last <= first * 1.3:
            return 0.7
        return 0.3

    def _error_rate(self, name: str) -> float:
        recent = self._errors.get(name, [])[-20:]
        return sum(recent) / len(recent) if recent else 0.0

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {"strategy": "predictive",
                "hit_rate": round(self._hits / max(total, 1), 3),
                "providers": len(self._hourly)}

    def _save(self):
        _save_json(_STATE_DIR / "predictive_history.json", {
            "hourly": {k: dict(v) for k, v in self._hourly.items()},
            "daily": {k: dict(v) for k, v in self._daily.items()},
            "latency": {k: v[-30:] for k, v in self._latencies.items()},
            "errors": {k: v[-30:] for k, v in self._errors.items()}})

    def _load(self):
        d = _load_json(_STATE_DIR / "predictive_history.json")
        for k, v in d.get("hourly", {}).items():
            self._hourly[k] = {int(h): float(s) for h, s in v.items()}
        for k, v in d.get("daily", {}).items():
            self._daily[k] = {int(dd): float(s) for dd, s in v.items()}
        for k, v in d.get("latency", {}).items():
            self._latencies[k] = v
        for k, v in d.get("errors", {}).items():
            self._errors[k] = v


# ═══════════════════════════════════════════════════════════════════
# Strategy 6: ScoreMatch (originally score_matching_router.py)
# ═══════════════════════════════════════════════════════════════════


class ScoreMatchStrategy:
    """Diffusion-style score matching router with Intentional TD."""

    def __init__(self, gamma: float = 0.3):
        self._gamma = gamma
        self._scores: dict[tuple[str, str], float] = defaultdict(lambda: 0.5)
        self._gradients: dict[str, list[float]] = defaultdict(list)

    def select(self, task: str, candidates: list[str],
               task_type: str = "general") -> RoutingDecision:
        if not candidates:
            return RoutingDecision(provider="", strategy="score_match", score=0.0)
        best_name, best_score = candidates[0], 0.0
        for name in candidates:
            sc = self._scores.get((name, task_type), 0.5)
            grad = self._provider_gradient(name)
            score = sc * 0.6 + 0.2 * 0.5 + 0.2 * grad
            if score > best_score:
                best_score, best_name = score, name
        return RoutingDecision(provider=best_name, strategy="score_match", score=best_score)

    def record(self, decision: RoutingDecision, success: bool,
               latency_ms: float = 0, cost_yuan: float = 0,
               task_type: str = "general", **kw) -> None:
        key = (decision.provider, task_type)
        current = self._scores[key]
        reward = 1.0 if success else -0.3
        latency_bonus = max(0, 1.0 - latency_ms / 10000) * 0.1
        cost_bonus = max(0, 1.0 - cost_yuan / 0.1) * 0.1
        target = (min(1.0, current + reward + latency_bonus + cost_bonus) if success
                  else max(0.01, current + reward))
        error = target - current
        new_score = (current + self._gamma * error if self._gamma > 0
                     else current + 0.05 * error)
        new_score = max(0.01, min(1.0, new_score))
        grad = new_score - current
        self._scores[key] = new_score
        self._gradients[decision.provider].append(grad)
        if len(self._gradients[decision.provider]) > 50:
            self._gradients[decision.provider] = self._gradients[decision.provider][-50:]

    def _provider_gradient(self, provider: str) -> float:
        grads = self._gradients.get(provider, [])
        if len(grads) < 3:
            return 0.5
        ema = grads[-1]
        for g in reversed(grads[:-1]):
            ema = 0.7 * ema + 0.3 * g
        return max(0.0, min(1.0, (ema + 1.0) / 2.0))

    def stats(self) -> dict:
        return {"strategy": "score_match", "score_entries": len(self._scores),
                "providers": len(self._gradients)}


# ═══════════════════════════════════════════════════════════════════
# Unified Router
# ═══════════════════════════════════════════════════════════════════


class UnifiedRouter:
    """Multi-strategy provider router — single entry, pluggable strategies.

    Usage:
        router = get_router()
        decision = router.select("code review", ["deepseek", "longcat"])
        router.record(decision, success=True, latency_ms=800)
        router.record(decision, success=False)  # negative feedback
        print(router.stats())
    """

    _instance: Optional[UnifiedRouter] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> UnifiedRouter:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = UnifiedRouter()
        return cls._instance

    def __init__(self):
        self._strategies: dict[str, Any] = {
            "learned": RouteLearner(),
            "thompson": ThompsonStrategy(),
            "budget": BudgetStrategy(),
            "fitness": FitnessStrategy(),
            "predictive": PredictiveStrategy(),
            "score_match": ScoreMatchStrategy(),
        }
        self._default = "learned"

    # ── Public API ──

    def select(self, task: str, candidates: list[str],
               task_type: str = "general", strategy: str = "") -> RoutingDecision:
        """Select the best provider using the chosen strategy."""
        st = strategy or self._default
        impl = self._strategies.get(st)
        if impl is None:
            impl = self._strategies[self._default]
        return impl.select(task, candidates, task_type=task_type)

    def record(self, decision: RoutingDecision, success: bool,
               **kwargs) -> None:
        """Record outcome — updates the strategy that made the decision."""
        st = decision.strategy or self._default
        impl = self._strategies.get(st)
        if impl:
            impl.record(decision, success, **kwargs)

    def stats(self, strategy: str = "") -> dict:
        """Get stats for one or all strategies."""
        if strategy:
            impl = self._strategies.get(strategy)
            return impl.stats() if impl else {}
        return {st: impl.stats() for st, impl in self._strategies.items()}

    def set_default(self, strategy: str) -> None:
        if strategy in self._strategies:
            self._default = strategy

    @property
    def strategies(self) -> list[str]:
        return list(self._strategies.keys())


# ═══════════════════════════════════════════════════════════════════
# Factory & backward-compat exports
# ═══════════════════════════════════════════════════════════════════


def get_router(strategy: str = "learned") -> UnifiedRouter:
    """Get the unified router singleton, optionally overriding default strategy."""
    router = UnifiedRouter.instance()
    if strategy != "learned":
        router.set_default(strategy)
    return router


# Backward-compat: keep route_learner's public API accessible
def get_route_learner() -> RouteLearner:
    return UnifiedRouter.instance()._strategies["learned"]


__all__ = [
    # Unified
    "UnifiedRouter", "get_router",
    "RoutingCandidate", "RoutingDecision",
    # Strategies
    "RouteLearner", "ThompsonStrategy", "BudgetStrategy",
    "FitnessStrategy", "PredictiveStrategy", "ScoreMatchStrategy",
    # Legacy compat (route_learner public API)
    "LearnedProfile", "RoutingWeight", "get_route_learner",
]
