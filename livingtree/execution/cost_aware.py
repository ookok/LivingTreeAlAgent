"""CostAware — Budget tracking and automatic model degradation.

Pricing source: https://api-docs.deepseek.com/zh-cn/quick_start/pricing
Flash:   input ¥1/M   output ¥2/M
Pro:     input ¥3/M   output ¥6/M  (2.5折，优惠至 2026-05-31)

All prices in CNY (元).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from loguru import logger


@dataclass
class TokenUsage:
    timestamp: float = field(default_factory=time.time)
    model: str = ""
    tokens: int = 0
    cost_yuan: float = 0.0


@dataclass
class BudgetStatus:
    daily_limit: int
    used_today: int
    remaining: int
    usage_pct: float
    degraded: bool
    cost_yuan: float = 0.0
    degraded_since: Optional[str] = None


# DeepSeek official pricing: ¥/1M tokens
PRICE_YUAN_PER_1M_INPUT: dict[str, float] = {
    "deepseek/deepseek-v4-pro": 3.0,
    "deepseek/deepseek-v4-flash": 1.0,
    # ═══ Qwen (千问) via qwencloud.com — USD→CNY @7.25 ═══
    "qwen/qwen3.6-plus": 2.90,        # $0.40 → ¥2.90
    "qwen/qwen3.6-flash": 0.73,       # $0.10 → ¥0.73
    "qwen/qwen3.6-max-preview": 8.70, # $1.20 → ¥8.70
    "qwen/qwen3-max": 8.70,           # $1.20 → ¥8.70
    "qwen/qwen-plus": 2.90,           # $0.40 → ¥2.90
    "qwen/qwen-flash": 0.36,          # $0.05 → ¥0.36
    "qwen/qwen3.5-plus": 2.90,        # $0.40 → ¥2.90
    "qwen/qwen3.5-flash": 0.73,       # $0.10 → ¥0.73
    "qwen/qwq-plus": 5.80,            # $0.80 → ¥5.80
    "qwen/qvq-max": 8.70,             # $1.20 → ¥8.70
}
PRICE_YUAN_PER_1M_OUTPUT: dict[str, float] = {
    "deepseek/deepseek-v4-pro": 6.0,
    "deepseek/deepseek-v4-flash": 2.0,
    # ═══ Qwen (千问) — USD→CNY @7.25 ═══
    "qwen/qwen3.6-plus": 17.40,       # $2.40 → ¥17.40
    "qwen/qwen3.6-flash": 2.90,       # $0.40 → ¥2.90
    "qwen/qwen3.6-max-preview": 43.50,# $6.00 → ¥43.50
    "qwen/qwen3-max": 43.50,          # $6.00 → ¥43.50
    "qwen/qwen-plus": 8.70,           # $1.20 → ¥8.70
    "qwen/qwen-flash": 2.90,          # $0.40 → ¥2.90
    "qwen/qwen3.5-plus": 17.40,       # $2.40 → ¥17.40
    "qwen/qwen3.5-flash": 2.90,       # $0.40 → ¥2.90
    "qwen/qwq-plus": 17.40,           # $2.40 → ¥17.40
    "qwen/qvq-max": 43.50,            # $6.00 → ¥43.50
}

MODEL_DEGRADATION_CHAIN: dict[str, str] = {
    "deepseek/deepseek-v4-pro": "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-v4-flash": "deepseek/deepseek-v4-flash",
    # Qwen degradation: max/plus → flash
    "qwen/qwen3.6-plus": "qwen/qwen3.6-flash",
    "qwen/qwen3.6-max-preview": "qwen/qwen3.6-flash",
    "qwen/qwen3-max": "qwen/qwen3.6-flash",
    "qwen/qwen-plus": "qwen/qwen-flash",
    "qwen/qwen3.5-plus": "qwen/qwen3.5-flash",
    "qwen/qwq-plus": "qwen/qwen3.6-flash",
    "qwen/qvq-max": "qwen/qwen3.6-flash",
    "qwen/qwen3.6-flash": "qwen/qwen3.6-flash",
    "qwen/qwen3.5-flash": "qwen/qwen3.5-flash",
    "qwen/qwen-flash": "qwen/qwen-flash",
}


class CostAware:
    """Budget-aware model selector with automatic degradation.

    Tracks token usage. When daily usage exceeds threshold,
    auto-switches from pro to flash model.
    """

    def __init__(self, daily_budget_tokens: int = 1_000_000,
                 degradation_threshold: float = 0.85,
                 history_window_seconds: float = 86400.0):
        self.daily_budget = daily_budget_tokens
        self.degradation_threshold = degradation_threshold
        self.history_window = history_window_seconds
        self._usage: deque[TokenUsage] = deque()
        self._lock = threading.Lock()
        self._degraded = False
        self._degraded_at: Optional[str] = None
        self._session_budget: dict[str, int] = {}

    def record(self, model: str, tokens: int, speedup_ratio: float = 1.0) -> None:
        """Record token usage. Cost in CNY based on DeepSeek official pricing.

        Args:
            model: Provider model name.
            tokens: Raw token count.
            speedup_ratio: HiFloat8 or other acceleration ratio (1.0 = no speedup).
                           Effective tokens = raw / speedup_ratio.
        """
        effective_tokens = max(1, int(tokens / speedup_ratio))
        inp_yuan_per_1M = PRICE_YUAN_PER_1M_INPUT.get(model, 1.0)
        out_yuan_per_1M = PRICE_YUAN_PER_1M_OUTPUT.get(model, 2.0)
        avg_yuan_per_1M = (inp_yuan_per_1M + out_yuan_per_1M) / 2
        cost = effective_tokens / 1_000_000 * avg_yuan_per_1M
        usage = TokenUsage(model=model, tokens=effective_tokens, cost_yuan=cost)
        with self._lock:
            self._usage.append(usage)
            self._cleanup_old()

    def record_session(self, session_id: str, model: str, tokens: int) -> None:
        self._session_budget[session_id] = self._session_budget.get(session_id, 0) + tokens
        self.record(model, tokens)

    def can_use(self, model: str, estimated_tokens: int = 0) -> bool:
        """Check if model can be used within budget.

        Auto-degrades pro→flash when daily usage exceeds threshold.
        """
        with self._lock:
            self._cleanup_old()
            used = self._today_usage()

        if "pro" in model:
            if self._degraded:
                return False
            if used >= self.daily_budget * self.degradation_threshold:
                self.degrade()
                return False

        if estimated_tokens > 0:
            return (used + estimated_tokens) <= self.daily_budget
        return used <= self.daily_budget * self.degradation_threshold

    def degraded_model(self) -> str:
        """Return the degraded model for current provider."""
        if self._degraded:
            # Check which provider we're using
            return "qwen/qwen3.6-flash"  # Default degraded to cheapest flash
        return "deepseek/deepseek-v4-pro"

    def degraded_model_for(self, model: str) -> str:
        """Return the degraded fallback for a given model."""
        return MODEL_DEGRADATION_CHAIN.get(model, model)

    def degrade(self) -> None:
        if not self._degraded:
            self._degraded = True
            self._degraded_at = datetime.now(timezone.utc).isoformat()
            logger.warning(f"[CostAware] Degraded to flash (used {self._today_usage()}/{self.daily_budget})")

    def restore(self) -> None:
        if self._degraded:
            self._degraded = False
            self._degraded_at = None
            logger.info("[CostAware] Restored to pro")

    def status(self) -> BudgetStatus:
        with self._lock:
            self._cleanup_old()
            used = self._today_usage()
        total_cost = sum(u.cost_yuan for u in self._usage)
        return BudgetStatus(
            daily_limit=self.daily_budget,
            used_today=used,
            remaining=max(0, self.daily_budget - used),
            usage_pct=used / max(self.daily_budget, 1),
            degraded=self._degraded,
            cost_yuan=total_cost,
            degraded_since=self._degraded_at,
        )

    def session_cost(self, session_id: str) -> int:
        return self._session_budget.get(session_id, 0)

    # ── Models.dev auto-sync ──────────────────────────────────────

    def sync_pricing_from_models_dev(self) -> int:
        """DEPRECATED: models_dev_sync removed. Returns 0."""
        return 0

    def _today_usage(self) -> int:
        return sum(u.tokens for u in self._usage)

    def _cleanup_old(self) -> None:
        cutoff = time.time() - self.history_window
        while self._usage and self._usage[0].timestamp < cutoff:
            self._usage.popleft()
