"""SurvivalMode — Unified cross-modal survival state machine.

Coordinates budget (TokenCircuitBreaker), rendering (LivingRenderer),
network (DualMode/offline_mode), and health (SystemHealth/VitalSigns)
into a single survival mode with ordered degradation priorities.

Survival levels:
  Level 0: FULL      — All 18 providers, VISUAL rendering, all features
  Level 1: CAUTIOUS  — Reduced providers (top_k-1), RICH rendering
  Level 2: THRIFTY   — Only free+local providers, STRUCT rendering
  Level 3: SURVIVAL  — Local only, PLAIN rendering, no aggregation
  Level 4: MINIMAL   — Cached responses only, TEXT rendering, background ops paused

Degradation triggers (priority ordered):
  1. Budget exhausted (>90%) → THRIFTY
  2. Network offline → SURVIVAL (auto-switch to local)
  3. CPU/GPU overloaded → CAUTIOUS
  4. High error rate (>30%) → CAUTIOUS
  5. Memory pressure (>85%) → THRIFTY

Integration:
  survival = get_survival_mode()
  level = survival.current_level()
  hint = survival.routing_hint()  # Adjusts top_k, aggregate, max_tokens
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional

from loguru import logger


class SurvivalLevel(IntEnum):
    FULL = 0
    CAUTIOUS = 1
    THRIFTY = 2
    SURVIVAL = 3
    MINIMAL = 4


@dataclass
class SystemVitals:
    budget_remaining_pct: float = 1.0
    network_online: bool = True
    cpu_percent: float = 0.0
    memory_pressure: float = 0.0
    error_rate: float = 0.0
    provider_count_alive: int = 18
    timestamp: float = field(default_factory=time.time)


class SurvivalMode:
    """Unified cross-modal survival state machine."""

    _instance: Optional["SurvivalMode"] = None

    @classmethod
    def instance(cls) -> "SurvivalMode":
        if cls._instance is None:
            cls._instance = SurvivalMode()
        return cls._instance

    def __init__(self):
        self._level: SurvivalLevel = SurvivalLevel.FULL
        self._transitions = 0
        self._history: list[tuple[SurvivalLevel, float]] = []

    # ── Level Assessment ───────────────────────────────────────────

    def assess(self, vitals: SystemVitals = None) -> SurvivalLevel:
        """Assess current survival level based on system vitals."""
        vitals = vitals or self._gather_vitals()
        old_level = self._level

        # Priority-ordered degradation checks
        if vitals.budget_remaining_pct < 0.03:
            self._level = SurvivalLevel.MINIMAL
        elif not vitals.network_online:
            self._level = SurvivalLevel.SURVIVAL
        elif vitals.budget_remaining_pct < 0.1:
            self._level = SurvivalLevel.SURVIVAL
        elif vitals.budget_remaining_pct < 0.3 or vitals.memory_pressure > 0.85:
            self._level = SurvivalLevel.THRIFTY
        elif vitals.error_rate > 0.3 or vitals.cpu_percent > 90:
            self._level = SurvivalLevel.CAUTIOUS
        elif vitals.budget_remaining_pct < 0.5 or vitals.memory_pressure > 0.7:
            self._level = SurvivalLevel.CAUTIOUS
        else:
            self._level = SurvivalLevel.FULL

        if self._level != old_level:
            self._transitions += 1
            direction = "↓" if self._level > old_level else "↑"
            logger.warning(
                f"SurvivalMode: {old_level.name}{direction}{self._level.name} "
                f"(budget={vitals.budget_remaining_pct:.0%}, "
                f"net={vitals.network_online}, errors={vitals.error_rate:.0%})"
            )

        self._history.append((self._level, time.time()))
        if len(self._history) > 100:
            self._history = self._history[-100:]

        return self._level

    def current_level(self) -> SurvivalLevel:
        return self._level

    # ── Routing Hints ──────────────────────────────────────────────

    def routing_hint(self) -> dict:
        """Return routing parameters adjusted for survival level."""
        hints = {
            SurvivalLevel.FULL:     {"top_k": 3, "aggregate": True,  "max_tokens": 4096, "render": "visual"},
            SurvivalLevel.CAUTIOUS:  {"top_k": 2, "aggregate": False, "max_tokens": 2048, "render": "rich"},
            SurvivalLevel.THRIFTY:   {"top_k": 1, "aggregate": False, "max_tokens": 1024, "render": "struct"},
            SurvivalLevel.SURVIVAL:  {"top_k": 1, "aggregate": False, "max_tokens": 512,  "render": "plain"},
            SurvivalLevel.MINIMAL:   {"top_k": 0, "aggregate": False, "max_tokens": 256,  "render": "plain"},
        }
        hint = dict(hints.get(self._level, hints[SurvivalLevel.FULL]))

        # Budget-aware token cap
        try:
            from .budget_router import get_budget_router
            budget = get_budget_router()
            status = budget.status()
            total_remaining = sum(
                s.get("daily_limit", 2) - s.get("daily_spent", 0)
                for s in status.values() if not s.get("is_free", True)
            )
            if total_remaining < 0.1:
                hint["max_tokens"] = min(hint["max_tokens"], 256)
        except Exception:
            pass

        return hint

    def should_pause_background(self) -> bool:
        """Return True if background operations should be paused."""
        return self._level >= SurvivalLevel.THRIFTY

    def render_level(self) -> str:
        """Return render level name for LivingRenderer."""
        mapping = {
            SurvivalLevel.FULL: "visual", SurvivalLevel.CAUTIOUS: "rich",
            SurvivalLevel.THRIFTY: "struct", SurvivalLevel.SURVIVAL: "plain",
            SurvivalLevel.MINIMAL: "plain",
        }
        return mapping.get(self._level, "rich")

    # ── Vital Gathering ────────────────────────────────────────────

    def _gather_vitals(self) -> SystemVitals:
        """Gather system vitals from multiple sources."""
        vitals = SystemVitals()

        # Budget
        try:
            from .budget_router import get_budget_router
            budget = get_budget_router()
            status = budget.status()
            total_limit = sum(s.get("daily_limit", 2) for s in status.values() if not s.get("is_free", True))
            total_spent = sum(s.get("daily_spent", 0) for s in status.values() if not s.get("is_free", True))
            vitals.budget_remaining_pct = max(0, (total_limit - total_spent) / max(total_limit, 0.01))
        except Exception:
            pass

        # Network
        try:
            from ..network.offline_mode import get_dual_mode
            dm = get_dual_mode()
            status = {"online": True}
            try:
                if hasattr(dm, 'check'):
                    status = dm.check() if not asyncio.iscoroutinefunction(dm.check) else {"online": True}
            except Exception:
                pass
            vitals.network_online = status.get("online", True)
        except Exception:
            pass

        # Provider health
        try:
            from .holistic_election import get_election
            election = get_election()
            alive = sum(1 for s in election._stats.values() if s.success_rate > 0)
            vitals.provider_count_alive = max(alive, 1)
            total = max(len(election._stats), 1)
            vitals.error_rate = (total - alive) / total
        except Exception:
            pass

        # Memory
        try:
            import psutil
            mem = psutil.virtual_memory()
            vitals.memory_pressure = mem.percent / 100.0
            vitals.cpu_percent = psutil.cpu_percent(interval=0.1)
        except ImportError:
            pass

        return vitals

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "level": self._level.name,
            "transitions": self._transitions,
            "hours_at_each_level": self._level_distribution(),
        }

    def _level_distribution(self) -> dict:
        if not self._history:
            return {}
        now = time.time()
        dist = defaultdict(float)
        for i, (level, ts) in enumerate(self._history):
            next_ts = self._history[i + 1][1] if i + 1 < len(self._history) else now
            dist[level.name] += (next_ts - ts) / 3600.0
        return {k: round(v, 2) for k, v in dist.items()}


# ═══ Singleton ════════════════════════════════════════════════════

_survival: Optional[SurvivalMode] = None


def get_survival_mode() -> SurvivalMode:
    global _survival
    if _survival is None:
        _survival = SurvivalMode()
    return _survival


__all__ = ["SurvivalMode", "SurvivalLevel", "SystemVitals", "get_survival_mode"]
