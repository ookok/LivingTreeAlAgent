"""BudgetRouter — Cost-aware provider routing to prevent budget explosion.

Adds a budget dimension to HolisticElection scoring. Each provider has daily/monthly
budget caps. When approaching limits, cost score is dynamically reduced and providers
may be excluded entirely.

Integration:
    router = get_budget_router()
    factor = router.budget_factor(provider_name, estimated_cost)  # 0.0-1.0
    router.record_spend(provider_name, actual_cost)

Injected into holistic_election.py score_providers() as budget cost modifier.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger

BUDGET_FILE = Path(".livingtree/budget_state.json")


@dataclass
class ProviderBudget:
    provider: str
    daily_spent: float = 0.0
    monthly_spent: float = 0.0
    daily_limit: float = 2.0
    monthly_limit: float = 10.0
    last_reset_day: str = ""
    is_free: bool = False


class BudgetRouter:
    """Cost-aware routing with per-provider budget enforcement."""

    _instance: Optional["BudgetRouter"] = None

    @classmethod
    def instance(cls) -> "BudgetRouter":
        if cls._instance is None:
            cls._instance = BudgetRouter()
        return cls._instance

    def __init__(self, daily_total: float = 10.0, monthly_total: float = 50.0):
        self._daily_total = daily_total
        self._monthly_total = monthly_total
        self._budgets: dict[str, ProviderBudget] = {}
        self._today = time.strftime("%Y-%m-%d")
        self._load()

    def _ensure_today(self):
        today = time.strftime("%Y-%m-%d")
        if today != self._today:
            for b in self._budgets.values():
                b.daily_spent = 0.0
            self._today = today

    def budget_factor(self, provider_name: str, estimated_cost: float = 0.0) -> float:
        """Return 0.0-1.0 multiplier for how budget-friendly this provider is.

        1.0 = no budget constraint, 0.0 = excluded (budget exhausted).
        """
        if estimated_cost <= 0:
            return 1.0  # Free call

        self._ensure_today()
        b = self._budgets.get(provider_name)
        if not b or b.is_free:
            return 1.0

        if b.daily_spent + estimated_cost > b.daily_limit:
            return 0.0   # Daily budget exhausted → exclude
        if b.monthly_spent + estimated_cost > b.monthly_limit:
            return 0.0   # Monthly budget exhausted → exclude

        daily_pct = b.daily_spent / max(b.daily_limit, 0.01)
        monthly_pct = b.monthly_spent / max(b.monthly_limit, 0.01)

        if daily_pct > 0.9 or monthly_pct > 0.9:
            return 0.3   # Near limit → heavy penalty
        if daily_pct > 0.7 or monthly_pct > 0.7:
            return 0.5   # Approaching limit → moderate penalty
        if daily_pct > 0.5:
            return 0.7   # Half spent → light penalty
        return 1.0

    def record_spend(self, provider_name: str, cost: float) -> None:
        """Record actual spend after a successful LLM call."""
        if cost <= 0:
            return
        self._ensure_today()
        b = self._budgets.get(provider_name)
        if not b:
            b = ProviderBudget(provider=provider_name)
            self._budgets[provider_name] = b
        b.daily_spent += cost
        b.monthly_spent += cost
        if int(b.daily_spent * 100) % 50 == 0:
            self._save()

    def register_provider(self, name: str, is_free: bool = False,
                          daily: float = 2.0, monthly: float = 10.0):
        if name not in self._budgets:
            self._budgets[name] = ProviderBudget(
                provider=name, is_free=is_free,
                daily_limit=daily, monthly_limit=monthly,
            )

    def status(self) -> dict:
        self._ensure_today()
        return {
            name: {
                "daily_spent": round(b.daily_spent, 4),
                "daily_limit": b.daily_limit,
                "monthly_spent": round(b.monthly_spent, 4),
                "monthly_limit": b.monthly_limit,
                "is_free": b.is_free,
            }
            for name, b in self._budgets.items()
        }

    def _save(self):
        try:
            BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                name: {
                    "daily_spent": b.daily_spent,
                    "monthly_spent": b.monthly_spent,
                    "daily_limit": b.daily_limit,
                    "monthly_limit": b.monthly_limit,
                    "is_free": b.is_free,
                    "last_reset_day": b.last_reset_day,
                }
                for name, b in self._budgets.items()
            }
            BUDGET_FILE.write_text(json.dumps(data))
        except Exception as e:
            logger.debug(f"BudgetRouter save: {e}")

    def _load(self):
        try:
            if BUDGET_FILE.exists():
                data = json.loads(BUDGET_FILE.read_text())
                for name, d in data.items():
                    self._budgets[name] = ProviderBudget(
                        provider=name, daily_spent=d.get("daily_spent", 0),
                        monthly_spent=d.get("monthly_spent", 0),
                        daily_limit=d.get("daily_limit", 2.0),
                        monthly_limit=d.get("monthly_limit", 10.0),
                        is_free=d.get("is_free", False),
                        last_reset_day=d.get("last_reset_day", ""),
                    )
        except Exception:
            pass


_budget_router: Optional[BudgetRouter] = None


def get_budget_router() -> BudgetRouter:
    global _budget_router
    if _budget_router is None:
        _budget_router = BudgetRouter()
    return _budget_router


__all__ = ["BudgetRouter", "ProviderBudget", "get_budget_router"]
