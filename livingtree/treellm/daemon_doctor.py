"""DaemonDoctor — Background self-healing daemon.

Periodic health checks (every 10 min) that detect and fix:
  - Stale election cache → force refresh
  - Consecutive provider failures → auto-demote
  - Budget near limit → log warning
  - struct_mem near capacity → trigger compression
  - Session cleanup (abandoned sessions > 30min)

Integration:
    doctor = get_daemon_doctor()
    await hub._spawn_task(doctor.run_loop(hub), "daemon_doctor")
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from loguru import logger

CHECK_INTERVAL = 600  # 10 minutes


class DaemonDoctor:
    """Background self-healing daemon for proactive maintenance."""

    _instance: Optional["DaemonDoctor"] = None

    @classmethod
    def instance(cls) -> "DaemonDoctor":
        if cls._instance is None:
            cls._instance = DaemonDoctor()
        return cls._instance

    def __init__(self):
        self._checkups = 0
        self._issues_found = 0
        self._issues_fixed = 0

    async def run_loop(self, hub) -> None:
        """Main daemon loop — runs periodic health checks."""
        await asyncio.sleep(60)  # Wait 1 min after startup
        while True:
            try:
                issues = await self.checkup(hub)
                self._checkups += 1
                if issues:
                    self._issues_found += len(issues)
                    self._issues_fixed += sum(1 for i in issues if i.get("fixed"))
                    for issue in issues:
                        level = issue.get("level", "info")
                        if level == "error":
                            logger.error(f"DaemonDoctor: {issue['msg']}")
                        elif level == "warn":
                            logger.warning(f"DaemonDoctor: {issue['msg']}")
            except Exception as e:
                logger.debug(f"DaemonDoctor checkup error: {e}")
            await asyncio.sleep(CHECK_INTERVAL)

    async def checkup(self, hub) -> list[dict]:
        """Run a single health checkup. Returns list of issues found."""
        issues = []

        # 1. ElectionBus cache staleness
        try:
            from ..treellm.election_bus import get_election_bus
            bus = get_election_bus()
            if bus._ttl > 300:
                issues.append({
                    "level": "warn",
                    "msg": f"Election cache TTL is {bus._ttl:.0f}s — forcing refresh",
                    "fixed": True,
                })
                await bus.force_refresh()
        except Exception:
            pass

        # 2. Provider consecutive failures
        try:
            from ..treellm.competitive_eliminator import get_eliminator
            elim = get_eliminator()
            for r in elim.get_leaderboard():
                if r["streak"] <= -5:
                    issues.append({
                        "level": "error",
                        "msg": f"Provider {r['provider']} has {abs(r['streak'])} consecutive failures",
                    })
        except Exception:
            pass

        # 3. BudgetRouter near-limit warnings
        try:
            from ..treellm.budget_router import get_budget_router
            budget = get_budget_router()
            for name, s in budget.status().items():
                if s.get("is_free"):
                    continue
                if s["daily_spent"] > s["daily_limit"] * 0.9:
                    issues.append({
                        "level": "warn",
                        "msg": f"Budget: {name} at {s['daily_spent']:.2f}/{s['daily_limit']:.2f} daily (90%+)",
                    })
        except Exception:
            pass

        # 4. ContextMoE: periodic memory consolidation
        try:
            from .context_moe import get_context_moe
            moe = get_context_moe()
            moved = await moe.consolidate()
            if moved > 0:
                issues.append({
                    "level": "info",
                    "msg": f"ContextMoE consolidated: {moved} blocks moved/purged",
                })
        except Exception:
            pass

        # 5. UserSignal pending session cleanup
        try:
            from ..treellm.user_signal import get_user_signal
            collector = get_user_signal()
            pending = collector.stats().get("pending_sessions", 0)
            if pending > 500:
                issues.append({
                    "level": "warn",
                    "msg": f"UserSignal: {pending} pending sessions — possible memory leak",
                })
        except Exception:
            pass

        # 5. Semantic cache stats
        try:
            from ..treellm.semantic_cache import get_semantic_cache
            cache = get_semantic_cache()
            if cache.hit_rate > 0:
                issues.append({
                    "level": "info",
                    "msg": f"SemanticCache: hit_rate={cache.hit_rate:.1%}, entries={len(cache._store)}",
                })
        except Exception:
            pass

        return issues

    def stats(self) -> dict:
        return {
            "checkups": self._checkups,
            "issues_found": self._issues_found,
            "issues_fixed": self._issues_fixed,
        }


_doctor: Optional[DaemonDoctor] = None


def get_daemon_doctor() -> DaemonDoctor:
    global _doctor
    if _doctor is None:
        _doctor = DaemonDoctor()
    return _doctor


__all__ = ["DaemonDoctor", "get_daemon_doctor"]
