"""TrustScoring — per-agent reliability posture scoring (0–100).

    Based on Mission Control's trust scoring system. Multi-factor:
    1. Success rate (40% weight) — recent + historical
    2. Recency (20%) — newer successes count more
    3. Drift (15%) — behavior stability vs baseline
    4. Rate limits (10%) — throttling frequency penalty
    5. Component health (15%) — tool reliability from AgentEval

    Hook profiles (minimal/standard/strict):
    - minimal: trust >= 30 to auto-approve
    - standard: trust >= 60 to auto-approve
    - strict: trust >= 85 + requires human review

    Usage:
        ts = get_trust_scorer()
        score = ts.score("nvidia-reasoning")
        ts.record("gaussian_plume", success=True, latency_ms=342)
        ts.set_profile("standard")
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

TRUST_DIR = Path(".livingtree/trust")
TRUST_DB = TRUST_DIR / "trust_scores.json"


@dataclass
class TrustProfile:
    agent: str
    score: float = 100.0  # 0–100
    successes: int = 0
    failures: int = 0
    rate_limits: int = 0
    total_calls: int = 0
    last_success: float = 0.0
    last_failure: float = 0.0
    drift_score: float = 1.0
    component_score: float = 1.0
    active_profile: str = "standard"  # minimal/standard/strict


class TrustScorer:
    """Multi-factor agent trust scoring."""

    WEIGHTS = {
        "success_rate": 0.40,
        "recency": 0.20,
        "drift": 0.15,
        "rate_limit": 0.10,
        "component": 0.15,
    }

    PROFILE_THRESHOLDS = {
        "minimal": 30,
        "standard": 60,
        "strict": 85,
    }

    def __init__(self):
        TRUST_DIR.mkdir(parents=True, exist_ok=True)
        self._profiles: dict[str, TrustProfile] = {}
        self._active_profile: str = "standard"
        self._load()

    def set_profile(self, profile: str):
        """Set active security profile: minimal/standard/strict."""
        if profile in self.PROFILE_THRESHOLDS:
            self._active_profile = profile
            logger.info(f"Trust profile: {profile} (threshold: {self.PROFILE_THRESHOLDS[profile]})")

    def record(
        self,
        agent: str,
        success: bool,
        latency_ms: float = 0.0,
        rate_limited: bool = False,
    ):
        """Record an agent action result. Auto-updates trust score.

        Called on every tool_call, provider election, etc.
        """
        if agent not in self._profiles:
            self._profiles[agent] = TrustProfile(agent=agent)

        p = self._profiles[agent]
        p.total_calls += 1

        if success:
            p.successes += 1
            p.last_success = time.time()
        else:
            p.failures += 1
            p.last_failure = time.time()

        if rate_limited:
            p.rate_limits += 1

        # Update component score from eval
        try:
            from .agent_eval import get_eval
            cm = get_eval().component_report(agent)
            if cm:
                p.component_score = cm.success_rate
        except Exception:
            pass

        # Recalculate
        p.score = self._calculate(p)

        if p.total_calls % 20 == 0:
            self._save()

    def score(self, agent: str) -> float:
        """Get current trust score for an agent."""
        profile = self._profiles.get(agent)
        if not profile:
            return 100.0  # new agents start at full trust
        return profile.score

    def can_auto_approve(self, agent: str) -> bool:
        """Check if agent meets current profile threshold for auto-approval."""
        threshold = self.PROFILE_THRESHOLDS.get(self._active_profile, 60)
        return self.score(agent) >= threshold

    def trust_level(self, agent: str) -> str:
        """Human-readable trust level."""
        s = self.score(agent)
        if s >= 90:
            return "🟢 trusted"
        elif s >= 70:
            return "🟡 reliable"
        elif s >= 50:
            return "🟠 cautious"
        elif s >= 30:
            return "🔴 risky"
        return "⛔ untrusted"

    def all_profiles(self) -> dict[str, TrustProfile]:
        return dict(self._profiles)

    def summary(self) -> dict[str, Any]:
        profiles = self._profiles
        if not profiles:
            return {"agents": 0, "avg_score": 100, "lowest": None}

        scores = [p.score for p in profiles.values()]
        avg = sum(scores) / len(scores)
        lowest_agent = min(profiles.values(), key=lambda p: p.score)

        return {
            "agents": len(profiles),
            "avg_score": round(avg, 1),
            "lowest_agent": lowest_agent.agent,
            "lowest_score": round(lowest_agent.score, 1),
            "profile": self._active_profile,
            "threshold": self.PROFILE_THRESHOLDS[self._active_profile],
            "all": {
                name: {
                    "score": round(p.score, 1),
                    "level": self.trust_level(name),
                    "calls": p.total_calls,
                    "success_rate": round(p.successes / max(p.total_calls, 1) * 100, 1),
                    "rate_limits": p.rate_limits,
                }
                for name, p in profiles.items()
            },
        }

    def _calculate(self, p: TrustProfile) -> float:
        """Multi-factor weighted trust score. 0–100."""
        total = max(p.total_calls, 1)

        # 1. Success rate (40%)
        success_rate = p.successes / total * 100

        # 2. Recency (20%) — decay score for old failures
        now = time.time()
        time_since_failure = now - p.last_failure if p.last_failure else 86400
        time_since_success = now - p.last_success if p.last_success else 86400
        recency_bonus = min(100, time_since_success / 3600 * 10)  # +10/hr since last success
        if p.last_failure > p.last_success:
            recency_bonus *= 0.3  # penalty if last action was failure

        # 3. Drift (15%) — component stability
        drift = p.drift_score * 100

        # 4. Rate limit penalty (10%)
        rl_rate = p.rate_limits / max(total, 1)
        rl_score = max(0, 100 - rl_rate * 200)  # each 1% rate-limit rate = -2 points

        # 5. Component health (15%)
        comp_score = p.component_score * 100

        score = (
            self.WEIGHTS["success_rate"] * success_rate +
            self.WEIGHTS["recency"] * recency_bonus +
            self.WEIGHTS["drift"] * drift +
            self.WEIGHTS["rate_limit"] * rl_score +
            self.WEIGHTS["component"] * comp_score
        )

        return max(0.0, min(100.0, score))

    def _save(self):
        data = {}
        for name, p in self._profiles.items():
            data[name] = {
                "agent": p.agent, "score": p.score,
                "successes": p.successes, "failures": p.failures,
                "rate_limits": p.rate_limits, "total_calls": p.total_calls,
                "last_success": p.last_success, "last_failure": p.last_failure,
                "drift_score": p.drift_score, "component_score": p.component_score,
            }
        TRUST_DB.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load(self):
        if not TRUST_DB.exists():
            return
        try:
            data = json.loads(TRUST_DB.read_text(encoding="utf-8"))
            for name, d in data.items():
                self._profiles[name] = TrustProfile(**{
                    k: d.get(k, 0) for k in TrustProfile.__dataclass_fields__
                })
        except Exception:
            pass


def get_trust_scorer() -> TrustScorer:
    global _ts
    if _ts is None:
        _ts = TrustScorer()
    return _ts


_ts: TrustScorer | None = None
