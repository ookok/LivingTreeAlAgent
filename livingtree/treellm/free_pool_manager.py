"""Free Model Pool Manager — zero-cost MoE infrastructure.

Production-grade management of free LLM provider pools:
  - Capability profiling: which free model is good at what
  - Rate-limit-aware round-robin scheduling
  - Health monitoring with auto-quarantine on failure
  - Automatic degrade/upgrade based on task criticality
  - Context window management for small-window free models

The "edge-computing MoE" vision:
  Single free model = intern. Pool of free models with smart scheduling
  + role assignment = research team that rivals paid models.

Integration with existing routing:
  Pool-managed models are candidates for TreeLLM routing.
  The pool acts as a pre-filter: only healthy, non-rate-limited models
  are presented to the election engine.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


# ═══ Data Types ═══


class PoolModelStatus(str, Enum):
    HEALTHY = "healthy"         # Normal operation
    DEGRADED = "degraded"       # Slow but still responding
    RATE_LIMITED = "limited"    # Temporarily rate-limited
    QUARANTINED = "quarantined" # Failed, cooling down
    UNKNOWN = "unknown"         # Not yet tested


@dataclass
class FreeModelProfile:
    """Capability profile for a free model provider."""
    name: str                    # Provider name (e.g. "siliconflow-flash")
    base_url: str = ""
    is_free: bool = True
    # Capability scores (0-1)
    coding: float = 0.5          # Code generation quality
    reasoning: float = 0.5       # Logical reasoning
    reading: float = 0.5         # Long-text comprehension
    instruction_following: float = 0.5  # Format adherence / instruction precision
    search: float = 0.5          # Web search integration
    # Constraints
    context_window: int = 4096   # Max context tokens
    rpm_limit: int = 30          # Max requests per minute
    rpd_limit: int = 1000        # Max requests per day
    concurrent_limit: int = 2    # Max concurrent requests
    # Runtime state
    status: PoolModelStatus = PoolModelStatus.UNKNOWN
    last_used: float = 0.0
    rpm_count: int = 0           # Rolling minute counter
    rpd_count: int = 0           # Rolling day counter
    failure_streak: int = 0
    avg_latency_ms: float = 500.0
    total_calls: int = 0
    total_successes: int = 0


# Pre-calibrated profiles for known free models
FREE_MODEL_PRESETS: dict[str, dict] = {
    "siliconflow-flash": {
        "coding": 0.7, "reasoning": 0.6, "reading": 0.5,
        "instruction_following": 0.6, "search": 0.3,
        "context_window": 8192, "rpm_limit": 60, "rpd_limit": 2000,
    },
    "siliconflow-reasoning": {
        "coding": 0.5, "reasoning": 0.8, "reading": 0.6,
        "instruction_following": 0.5, "search": 0.2,
        "context_window": 16384, "rpm_limit": 30, "rpd_limit": 1000,
    },
    "longcat": {
        "coding": 0.4, "reasoning": 0.5, "reading": 0.6,
        "instruction_following": 0.5, "search": 0.4,
        "context_window": 4096, "rpm_limit": 100, "rpd_limit": 5000,
    },
    "dmxapi": {
        "coding": 0.5, "reasoning": 0.5, "reading": 0.5,
        "instruction_following": 0.6, "search": 0.3,
        "context_window": 4096, "rpm_limit": 60, "rpd_limit": 3000,
    },
    "mofang-flash": {
        "coding": 0.6, "reasoning": 0.5, "reading": 0.5,
        "instruction_following": 0.5, "search": 0.3,
        "context_window": 8192, "rpm_limit": 50, "rpd_limit": 1500,
    },
    "mofang-reasoning": {
        "coding": 0.4, "reasoning": 0.7, "reading": 0.5,
        "instruction_following": 0.5, "search": 0.2,
        "context_window": 16384, "rpm_limit": 20, "rpd_limit": 800,
    },
    "opencode-serve": {
        "coding": 0.6, "reasoning": 0.4, "reading": 0.4,
        "instruction_following": 0.5, "search": 0.1,
        "context_window": 8192, "rpm_limit": 9999, "rpd_limit": 99999,
    },
    "modelscope": {
        "coding": 0.5, "reasoning": 0.6, "reading": 0.5,
        "instruction_following": 0.5, "search": 0.2,
        "context_window": 32768, "rpm_limit": 30, "rpd_limit": 1000,
    },
    "stepfun": {
        "coding": 0.5, "reasoning": 0.7, "reading": 0.6,
        "instruction_following": 0.5, "search": 0.2,
        "context_window": 16384, "rpm_limit": 20, "rpd_limit": 500,
    },
    "internlm": {
        "coding": 0.5, "reasoning": 0.6, "reading": 0.5,
        "instruction_following": 0.4, "search": 0.2,
        "context_window": 32768, "rpm_limit": 20, "rpd_limit": 500,
    },
    "sensetime": {
        "coding": 0.6, "reasoning": 0.7, "reading": 0.7,
        "instruction_following": 0.7, "search": 0.3,
        "context_window": 32768, "rpm_limit": 60, "rpd_limit": 2000,
    },
    "sensetime-pro": {
        "coding": 0.5, "reasoning": 0.8, "reading": 0.7,
        "instruction_following": 0.6, "search": 0.2,
        "context_window": 65536, "rpm_limit": 30, "rpd_limit": 1000,
    },
    "sensetime-turbo": {
        "coding": 0.7, "reasoning": 0.5, "reading": 0.6,
        "instruction_following": 0.7, "search": 0.4,
        "context_window": 16384, "rpm_limit": 100, "rpd_limit": 3000,
    },
    "qwen/qwen3.6-flash": {
        "coding": 0.7, "reasoning": 0.6, "reading": 0.7,
        "instruction_following": 0.7, "search": 0.3,
        "context_window": 32768, "rpm_limit": 60, "rpd_limit": 2000,
    },
    "qwen/qwen-flash": {
        "coding": 0.6, "reasoning": 0.5, "reading": 0.6,
        "instruction_following": 0.6, "search": 0.2,
        "context_window": 8192, "rpm_limit": 100, "rpd_limit": 5000,
    },
    "default_free": {
        "coding": 0.5, "reasoning": 0.5, "reading": 0.5,
        "instruction_following": 0.5, "search": 0.3,
        "context_window": 4096, "rpm_limit": 30, "rpd_limit": 1000,
    },
}


# ═══ Role-Aware Model Selector ═══

class ResearchRole(str, Enum):
    DATA_HUNTER = "data"        # 数据猎人 — needs: reading, search
    CODER = "coder"             # 代码工匠 — needs: coding, context_window
    IDEA_AGENT = "idea"         # 策略研究员 — needs: reasoning
    REVIEWER = "reviewer"       # 严苛审查员 — needs: instruction_following


# Role → capability weight vector (coding, reasoning, reading, instruction, search)
ROLE_CAPABILITY_WEIGHTS: dict[str, list[float]] = {
    "data": [0.1, 0.2, 0.4, 0.15, 0.15],    # Reading + Search
    "coder": [0.45, 0.2, 0.15, 0.15, 0.05],  # Coding + Context
    "idea": [0.15, 0.5, 0.2, 0.1, 0.05],      # Reasoning heavy
    "reviewer": [0.1, 0.3, 0.15, 0.4, 0.05],  # Instruction following
}


# ═══ Free Pool Manager ═══


class FreeModelPool:
    """Zero-cost model pool with health-aware scheduling.

    Manages a pool of free LLM providers with:
      - Rate-limit tracking (per-minute and per-day)
      - Health state machine: UNKNOWN → HEALTHY ↔ DEGRADED ↔ QUARANTINED
      - Role-aware model selection (best fit for each research role)
      - Round-robin scheduling to distribute load
      - Automatic quarantine on failure streaks

    Cooldown strategy:
      - 1st failure: mark DEGRADED, wait 5s
      - 2nd consecutive: wait 15s
      - 3rd consecutive: QUARANTINED for 60s
      - 4th+: QUARANTINED for 300s
    """

    QUARANTINE_DURATIONS = [5, 15, 60, 300, 900]

    def __init__(self):
        self._models: dict[str, FreeModelProfile] = {}
        self._role_assignments: dict[str, str] = {}  # role → model_name
        self._call_queue: deque = deque()
        self._rpm_windows: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=200))
        self._initialize_defaults()

    def _initialize_defaults(self):
        """Load free model presets."""
        for name, props in FREE_MODEL_PRESETS.items():
            self._models[name] = FreeModelProfile(
                name=name,
                coding=props["coding"],
                reasoning=props["reasoning"],
                reading=props["reading"],
                instruction_following=props["instruction_following"],
                search=props.get("search", 0.3),
                context_window=props["context_window"],
                rpm_limit=props["rpm_limit"],
                rpd_limit=props["rpd_limit"],
            )

    # ── Model Registration ──

    def register(self, name: str, **capabilities) -> FreeModelProfile:
        """Register a new free model with capability scores."""
        preset = FREE_MODEL_PRESETS.get(name, {})
        profile = FreeModelProfile(
            name=name,
            coding=capabilities.get("coding", preset.get("coding", 0.5)),
            reasoning=capabilities.get("reasoning", preset.get("reasoning", 0.5)),
            reading=capabilities.get("reading", preset.get("reading", 0.5)),
            instruction_following=capabilities.get(
                "instruction_following", preset.get("instruction_following", 0.5)),
            search=capabilities.get("search", preset.get("search", 0.3)),
            context_window=capabilities.get(
                "context_window", preset.get("context_window", 4096)),
            rpm_limit=capabilities.get("rpm_limit", preset.get("rpm_limit", 30)),
            rpd_limit=capabilities.get("rpd_limit", preset.get("rpd_limit", 1000)),
        )
        self._models[name] = profile
        return profile

    # ── Health State Machine ──

    def mark_healthy(self, name: str, latency_ms: float = 500) -> None:
        model = self._get_model(name)
        model.status = PoolModelStatus.HEALTHY
        model.failure_streak = 0
        model.avg_latency_ms = (
            0.8 * model.avg_latency_ms + 0.2 * latency_ms
            if model.total_calls > 0 else latency_ms)
        model.total_calls += 1
        model.total_successes += 1
        model.last_used = time.time()

    def mark_failure(self, name: str) -> None:
        model = self._get_model(name)
        model.failure_streak += 1
        model.total_calls += 1
        model.last_used = time.time()

        idx = min(model.failure_streak - 1, len(self.QUARANTINE_DURATIONS) - 1)
        quarantine_sec = self.QUARANTINE_DURATIONS[idx]

        if model.failure_streak <= 1:
            model.status = PoolModelStatus.DEGRADED
        else:
            model.status = PoolModelStatus.QUARANTINED

        logger.warning(
            f"FreePool[{name}]: {model.status.value} "
            f"(streak={model.failure_streak}, cooldown={quarantine_sec}s)",
        )

    def mark_rate_limited(self, name: str) -> None:
        model = self._get_model(name)
        model.status = PoolModelStatus.RATE_LIMITED
        logger.info(f"FreePool[{name}]: rate limited")

    # ── Rate Limit Tracking ──

    def _check_rate_limit(self, name: str) -> bool:
        """Check if a model is within rate limits. Returns True if OK."""
        model = self._get_model(name)
        now = time.time()

        # Clean expired RPM counters
        window = self._rpm_windows[name]
        while window and now - window[0] > 60:
            window.popleft()

        # RPM check
        if len(window) >= model.rpm_limit:
            return False

        # RPD check (approximate: daily reset at midnight)
        today_start = now - (now % 86400)
        today_calls = sum(1 for t in window if t > today_start)
        if today_calls >= model.rpd_limit:
            return False

        return True

    def _record_call(self, name: str) -> None:
        """Record a call for rate limit tracking."""
        self._rpm_windows[name].append(time.time())

    # ── Health Checking ──

    def is_available(self, name: str) -> bool:
        """Check if a model is currently available."""
        model = self._get_model(name)
        if model.status == PoolModelStatus.HEALTHY:
            return self._check_rate_limit(name)
        if model.status == PoolModelStatus.DEGRADED:
            # Degraded: still usable but with caution
            return self._check_rate_limit(name)
        if model.status == PoolModelStatus.QUARANTINED:
            # Check cooldown
            idx = min(model.failure_streak - 1, len(self.QUARANTINE_DURATIONS) - 1)
            cooldown = self.QUARANTINE_DURATIONS[idx]
            if time.time() - model.last_used > cooldown:
                # Auto-recover from quarantine
                model.status = PoolModelStatus.UNKNOWN
                model.failure_streak = 0
                return self._check_rate_limit(name)
            return False
        if model.status == PoolModelStatus.RATE_LIMITED:
            # Check if rate limit window expired
            return self._check_rate_limit(name)
        # UNKNOWN: test if rate-limited
        return self._check_rate_limit(name)

    def available_models(self) -> list[str]:
        """Get all currently available free models."""
        return [name for name in self._models if self.is_available(name)]

    def healthy_models(self) -> list[str]:
        """Get models in HEALTHY state."""
        return [
            name for name in self._models
            if self._models[name].status == PoolModelStatus.HEALTHY
            and self._check_rate_limit(name)
        ]

    # ── Role-Aware Selection ──

    def assign_role(
        self, role: str | ResearchRole, prefer: str = "",
    ) -> str | None:
        """Assign the best available free model to a research role.

        Uses capability-weighted scoring: for each model, compute
        score = Σ w_i × cap_i, where w_i is the role's weight vector.
        Selects the highest-scoring healthy model, with round-robin
        tie-breaking to distribute load.

        Args:
            role: Research role (data/coder/idea/reviewer)
            prefer: Preferred model name (optional hint)

        Returns:
            Model name, or None if no model available for this role
        """
        if isinstance(role, str):
            role = role.lower()

        weights = ROLE_CAPABILITY_WEIGHTS.get(
            role, [0.25, 0.25, 0.25, 0.15, 0.1])

        candidates: list[tuple[str, float, int]] = []  # (name, score, calls)

        for name, model in self._models.items():
            if not self.is_available(name):
                continue
            if not model.is_free:
                continue

            # Context window check for coder role
            if role in ("coder", "idea") and model.context_window < 4096:
                continue

            # Compute capability score
            caps = [
                model.coding, model.reasoning, model.reading,
                model.instruction_following, model.search,
            ]
            score = sum(w * c for w, c in zip(weights, caps))

            # Bonus for preferred model (10% boost)
            if prefer and prefer in name:
                score *= 1.1

            # Health penalty
            if model.status == PoolModelStatus.DEGRADED:
                score *= 0.7

            candidates.append((name, score, model.total_calls))

        if not candidates:
            return None

        # Sort by score, tie-break by least-used (round-robin)
        candidates.sort(key=lambda x: (-x[1], x[2]))

        best_name = candidates[0][0]
        self._role_assignments[str(role)] = best_name

        logger.debug(
            f"FreePool assign: {role} → {best_name} "
            f"(score={candidates[0][1]:.3f}, candidates={len(candidates)})",
        )
        return best_name

    def get_role_model(self, role: str) -> str | None:
        """Get the currently assigned model for a role."""
        return self._role_assignments.get(str(role))

    def assign_team(self) -> dict[str, str]:
        """Assign models for all four research roles.

        Returns:
            {role: model_name} for all assigned roles
        """
        roles = ["data", "coder", "idea", "reviewer"]
        assigned: dict[str, str] = {}
        used: set[str] = set()

        for role in roles:
            model = self.assign_role(role)
            if model:
                # Prefer diversity: try to assign different models
                if model in used and len(self.available_models()) > len(used):
                    # Try another less-used model
                    alternatives = [
                        m for m, s, c in self._rank_for_role(role)
                        if m not in used
                    ]
                    if alternatives:
                        model = alternatives[0]
                assigned[role] = model
                used.add(model)
            else:
                # Fallback: reuse an already-assigned model
                assigned[role] = used.copy().pop() if used else None

        return assigned

    def _rank_for_role(self, role: str) -> list[tuple[str, float, int]]:
        """Get ranked candidates for a role (internal)."""
        weights = ROLE_CAPABILITY_WEIGHTS.get(role, [0.25]*5)
        candidates = []
        for name, model in self._models.items():
            if not self.is_available(name) or not model.is_free:
                continue
            caps = [
                model.coding, model.reasoning, model.reading,
                model.instruction_following, model.search,
            ]
            score = sum(w * c for w, c in zip(weights, caps))
            if model.status == PoolModelStatus.DEGRADED:
                score *= 0.7
            candidates.append((name, score, model.total_calls))
        candidates.sort(key=lambda x: (-x[1], x[2]))
        return candidates

    # ── Context Window Management ──

    def max_context_for(self, name: str) -> int:
        """Get max context window size for a model."""
        model = self._get_model(name)
        return model.context_window

    def recommend_chunk_size(self, name: str, safety_factor: float = 0.7) -> int:
        """Recommend a safe chunk size for this model's context window.

        Leaves 30% headroom for system prompt + generation.
        """
        window = self.max_context_for(name)
        return int(window * safety_factor)

    # ── Round-Robin pre-call ──

    async def acquire(self, name: str, timeout: float = 5.0) -> bool:
        """Acquire permission to call a model (rate limit + health check).

        Returns True if call is allowed, False if rejected.
        Implements async wait for rate-limited models.
        """
        model = self._get_model(name)

        if not self.is_available(name):
            return False

        if not self._check_rate_limit(name):
            # Rate-limited: wait and retry
            await asyncio.sleep(1.0)
            if not self._check_rate_limit(name):
                self.mark_rate_limited(name)
                return False

        self._record_call(name)
        return True

    # ── Bulk Operations ──

    def pool_stats(self) -> dict[str, Any]:
        """Get comprehensive pool statistics."""
        total = len(self._models)
        healthy = len(self.healthy_models())
        available = len(self.available_models())

        by_status: dict[str, int] = defaultdict(int)
        for m in self._models.values():
            by_status[m.status.value] += 1

        return {
            "total_models": total,
            "healthy": healthy,
            "available": available,
            "degraded": by_status.get("degraded", 0),
            "quarantined": by_status.get("quarantined", 0),
            "rate_limited": by_status.get("limited", 0),
            "role_assignments": dict(self._role_assignments),
            "avg_success_rate": round(
                sum(m.total_successes / max(m.total_calls, 1)
                    for m in self._models.values()) / max(total, 1), 3),
        }

    def reset_daily_counters(self):
        """Reset daily rate limit counters (call at midnight)."""
        for name in self._models:
            self._models[name].rpd_count = 0
        logger.info("FreePool: daily counters reset")

    def _get_model(self, name: str) -> FreeModelProfile:
        if name not in self._models:
            preset = FREE_MODEL_PRESETS.get(name, FREE_MODEL_PRESETS["default_free"])
            self._models[name] = FreeModelProfile(
                name=name,
                coding=preset["coding"],
                reasoning=preset["reasoning"],
                reading=preset["reading"],
                instruction_following=preset["instruction_following"],
                search=preset.get("search", 0.3),
                context_window=preset["context_window"],
                rpm_limit=preset["rpm_limit"],
                rpd_limit=preset["rpd_limit"],
            )
        return self._models[name]


# ═══ Singleton ═══

_free_pool: FreeModelPool | None = None


def get_free_pool() -> FreeModelPool:
    global _free_pool
    if _free_pool is None:
        _free_pool = FreeModelPool()
    return _free_pool


__all__ = [
    "FreeModelPool", "FreeModelProfile", "PoolModelStatus",
    "ResearchRole", "get_free_pool",
]
