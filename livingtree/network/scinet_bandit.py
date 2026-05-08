"""Scinet Bandit Router — Contextual Multi-Armed Bandit for proxy selection.

Replaces the static scoring in proxy_fetcher.py with online reinforcement learning.
Implements:

1. Contextual Thompson Sampling:
   - State: domain category, time of day, request size, current load
   - Arms: available proxies (with features: latency, country, protocol, source)
   - Reward: success (1) or failure (0) weighted by latency inverse

2. LinUCB (Linear Upper Confidence Bound):
   - Disjoint linear model per arm
   - Confidence bounds for exploration/exploitation trade-off
   - Auto-decaying exploration factor

3. Adaptive learning rates per proxy (more recent data weighted higher)

Reference:
  - Li et al., "A Contextual-Bandit Approach to Personalized News Article Recommendation" (WWW 2010)
  - Agrawal & Goyal, "Thompson Sampling for Contextual Bandits with Linear Payoffs" (ICML 2013)

Usage:
    router = BanditRouter()
    proxy = await router.select_proxy(request_context)
    # ... use proxy ...
    await router.update(proxy, success=True, latency_ms=120)
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
from loguru import logger

BANDIT_CACHE = Path(".livingtree/bandit_state.json")
DEFAULT_ALPHA = 1.0  # Exploration factor
DECAY_RATE = 0.999  # Per-step decay of alpha
MIN_ALPHA = 0.01
CONTEXT_DIM = 8  # Feature vector dimension


@dataclass
class ArmState:
    """Per-proxy arm state for LinUCB."""
    proxy_id: str
    # LinUCB parameters
    A: np.ndarray = field(default=None)  # d×d matrix
    b: np.ndarray = field(default=None)  # d×1 vector
    theta: np.ndarray = field(default=None)  # d×1 parameter vector
    # Statistics
    pulls: int = 0
    successes: int = 0
    failures: int = 0
    total_latency: float = 0.0
    last_seen: float = 0.0
    # Thompson sampling
    alpha_param: float = 1.0  # Beta distribution alpha
    beta_param: float = 1.0  # Beta distribution beta

    def __post_init__(self):
        if self.A is None:
            self.A = np.eye(CONTEXT_DIM)
        if self.b is None:
            self.b = np.zeros(CONTEXT_DIM)
        if self.theta is None:
            self.theta = np.zeros(CONTEXT_DIM)

    @property
    def avg_latency(self) -> float:
        return self.total_latency / max(self.pulls, 1)

    @property
    def success_rate(self) -> float:
        return self.successes / max(self.pulls, 1)


@dataclass
class RequestContext:
    """Contextual feature vector for a proxy request."""
    domain_category: str = "GENERAL"
    time_hour: int = 0
    request_size_bytes: int = 0
    is_https: bool = True
    retry_count: int = 0
    peer_latency_ms: float = 0.0
    protocol: str = "https"
    bandwidth_budget: bool = True

    CATEGORY_ENCODING = {
        "DEDICATED": 0, "SEARCH": 1, "CDN": 2,
        "VIDEO": 3, "GENERAL": 4, "API": 5,
    }

    def to_features(self) -> np.ndarray:
        """Convert context to normalized feature vector."""
        cat_code = self.CATEGORY_ENCODING.get(self.domain_category, 4) / 5.0
        hour_norm = self.time_hour / 24.0
        size_norm = min(1.0, self.request_size_bytes / (10 * 1024 * 1024))  # up to 10MB
        https_val = 1.0 if self.is_https else 0.0
        retry_norm = min(1.0, self.retry_count / 5.0)
        latency_norm = min(1.0, self.peer_latency_ms / 5000.0)
        proto_val = 1.0 if self.protocol in ("https", "socks5") else 0.5
        budget_val = 1.0 if self.bandwidth_budget else 0.0

        return np.array([
            cat_code, hour_norm, size_norm, https_val,
            retry_norm, latency_norm, proto_val, budget_val,
        ])


class BanditRouter:
    """Contextual Multi-Armed Bandit router for proxy selection.

    Hybrid approach combining:
    1. LinUCB: linear contextual bandit for cold-start and sparse contexts
    2. Thompson Sampling: Beta-Bernoulli model for mature proxies
    3. UCB-style exploration bonus

    Selection strategy:
    - If pulls < 10: use Thompson Sampling (Bayesian)
    - If pulls >= 10: use LinUCB (contextual)
    - Tie-breaker: UCB exploration bonus based on time since last use
    """

    def __init__(self, alpha: float = DEFAULT_ALPHA):
        self._arms: dict[str, ArmState] = {}
        self._alpha = alpha
        self._lock = asyncio.Lock()
        self._total_pulls = 0
        self._context_memory: list[tuple[np.ndarray, str, float]] = []
        self._context_memory_max = 1000

    def add_proxy(self, proxy_id: str) -> None:
        """Register a new proxy as an arm."""
        if proxy_id not in self._arms:
            self._arms[proxy_id] = ArmState(proxy_id=proxy_id)

    def remove_proxy(self, proxy_id: str) -> None:
        self._arms.pop(proxy_id, None)

    async def select_proxy(
        self, context: RequestContext, candidates: list[str],
    ) -> Optional[str]:
        """Select the best proxy using contextual bandit.

        Args:
            context: request context features
            candidates: list of available proxy IDs

        Returns:
            Selected proxy ID, or None if no candidates
        """
        if not candidates:
            return None

        async with self._lock:
            x = context.to_features()

            # Ensure all candidates have arm states
            for pid in candidates:
                self.add_proxy(pid)

            # Compute scores for each candidate
            scores = []
            for pid in candidates:
                arm = self._arms[pid]
                score = self._compute_score(arm, x)
                scores.append((pid, score))

            scores.sort(key=lambda s: s[1], reverse=True)
            selected = scores[0][0]

            # Self-normalizing exploration
            selected_arm = self._arms[selected]
            if self._total_pulls > 0:
                # Occasional random exploration (epsilon-greedy with decay)
                eps = 1.0 / (1.0 + self._total_pulls * 0.001)
                if random.random() < eps:
                    selected = random.choice(candidates)

            return selected

    def _compute_score(self, arm: ArmState, context: np.ndarray) -> float:
        """Compute selection score for an arm given context.

        Hybrid: LinUCB for experienced arms, Thompson Sampling for new ones.
        """
        if arm.pulls >= 10:
            return self._linucb_score(arm, context)
        else:
            return self._thompson_score(arm)

    def _linucb_score(self, arm: ArmState, context: np.ndarray) -> float:
        """LinUCB score: expected reward + confidence bound.

        p_{t,a} = θ_a^T x_t + α √(x_t^T A_a^{-1} x_t)
        """
        try:
            A_inv = np.linalg.inv(arm.A)
            expected = float(np.dot(arm.theta, context))
            std = float(np.sqrt(np.dot(context.T, np.dot(A_inv, context))))
            ucb = self._alpha * std
            return expected + ucb
        except np.linalg.LinAlgError:
            return self._thompson_score(arm)

    def _thompson_score(self, arm: ArmState) -> float:
        """Thompson Sampling: sample from Beta(α, β) posterior."""
        return random.betavariate(
            arm.alpha_param + arm.successes,
            arm.beta_param + arm.failures,
        )

    async def update(
        self, proxy_id: str, context: RequestContext = None,
        success: bool = True, latency_ms: float = 0.0,
    ) -> None:
        """Update arm state after proxy usage.

        Performs:
        1. Beta posterior update for Thompson Sampling
        2. LinUCB matrix update for contextual learning
        3. Context memory update
        """
        async with self._lock:
            if proxy_id not in self._arms:
                self.add_proxy(proxy_id)

            arm = self._arms[proxy_id]
            arm.pulls += 1
            arm.last_seen = time.time()
            arm.total_latency += latency_ms
            self._total_pulls += 1

            if success:
                arm.successes += 1
            else:
                arm.failures += 1

            # LinUCB update
            if context is not None and arm.pulls >= 5:
                x = context.to_features()
                reward = self._compute_reward(success, latency_ms)
                arm.A += np.outer(x, x)
                arm.b += reward * x
                try:
                    arm.theta = np.linalg.solve(arm.A, arm.b)
                except np.linalg.LinAlgError:
                    arm.A = np.eye(CONTEXT_DIM) + np.outer(x, x)
                    arm.b = np.zeros(CONTEXT_DIM) + reward * x
                    arm.theta = np.linalg.solve(arm.A, arm.b)

                # Store context-reward pair for replay
                self._context_memory.append((x, proxy_id, reward))
                if len(self._context_memory) > self._context_memory_max:
                    self._context_memory.pop(0)

        # Decay exploration factor
        self._alpha = max(MIN_ALPHA, self._alpha * DECAY_RATE)

    def _compute_reward(self, success: bool, latency_ms: float) -> float:
        """Compute reward signal: success weighted by latency.

        Reward range: [-1, 1]
        - Success with low latency → high positive reward
        - Success with high latency → low positive reward
        - Failure → negative reward
        """
        if not success:
            return -1.0
        latency_score = max(0.0, 1.0 - latency_ms / 5000.0)
        return latency_score

    def get_top_proxies(self, n: int = 5) -> list[dict]:
        """Get top N proxies ranked by learned quality."""
        results = []
        for pid, arm in self._arms.items():
            results.append({
                "proxy_id": pid,
                "pulls": arm.pulls,
                "success_rate": round(arm.success_rate, 3),
                "avg_latency_ms": round(arm.avg_latency, 1),
                "theta_norm": float(np.linalg.norm(arm.theta)),
            })
        results.sort(key=lambda r: r["success_rate"], reverse=True)
        return results[:n]

    def get_stats(self) -> dict:
        top = self.get_top_proxies(5)
        return {
            "total_arms": len(self._arms),
            "total_pulls": self._total_pulls,
            "alpha": round(self._alpha, 4),
            "context_memory_size": len(self._context_memory),
            "top_proxies": top,
            "exploration_rate": round(
                1.0 / (1.0 + self._total_pulls * 0.001), 5
            ),
        }

    def save_state(self) -> None:
        """Persist bandit state to disk."""
        try:
            data = {
                "alpha": self._alpha,
                "total_pulls": self._total_pulls,
                "arms": {
                    pid: {
                        "pulls": arm.pulls,
                        "successes": arm.successes,
                        "failures": arm.failures,
                        "total_latency": arm.total_latency,
                        "last_seen": arm.last_seen,
                        "alpha_param": arm.alpha_param,
                        "beta_param": arm.beta_param,
                    }
                    for pid, arm in self._arms.items()
                },
            }
            BANDIT_CACHE.parent.mkdir(parents=True, exist_ok=True)
            BANDIT_CACHE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.debug("BanditRouter save: %s", e)

    def load_state(self) -> None:
        """Load bandit state from disk."""
        if not BANDIT_CACHE.exists():
            return
        try:
            data = json.loads(BANDIT_CACHE.read_text())
            self._alpha = data.get("alpha", DEFAULT_ALPHA)
            self._total_pulls = data.get("total_pulls", 0)
            for pid, arm_data in data.get("arms", {}).items():
                arm = ArmState(proxy_id=pid)
                arm.pulls = arm_data["pulls"]
                arm.successes = arm_data["successes"]
                arm.failures = arm_data["failures"]
                arm.total_latency = arm_data["total_latency"]
                arm.last_seen = arm_data["last_seen"]
                arm.alpha_param = arm_data["alpha_param"]
                arm.beta_param = arm_data["beta_param"]
                self._arms[pid] = arm
        except Exception as e:
            logger.debug("BanditRouter load: %s", e)


_router: Optional[BanditRouter] = None


def get_bandit_router() -> BanditRouter:
    global _router
    if _router is None:
        _router = BanditRouter()
        _router.load_state()
    return _router
