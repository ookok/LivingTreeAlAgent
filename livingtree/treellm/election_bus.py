"""ElectionBus — Unified election result caching and broadcast bus.

Eliminates the dual-track election problem where _elect_tiers() and route_layered()
independently ping all 18 providers on every request (~800ms wasted).

Single source of truth: all consumers read from the same cached election results.
TTL-based refresh with forced-refresh capability for error recovery.

Integration:
    bus = get_election_bus()
    scores = await bus.get_scores(providers)          # cached read
    await bus.force_refresh()                          # on provider failure
    bus.on_refresh(lambda scores: ...)                 # subscribe to updates
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from loguru import logger


@dataclass
class ElectionSnapshot:
    """Cached election result for a set of providers."""
    scores: list[Any]
    timestamp: float
    candidates_hash: str


class ElectionBus:
    """Unified election result bus — single source of truth for provider rankings."""

    _instance: Optional["ElectionBus"] = None

    @classmethod
    def instance(cls) -> "ElectionBus":
        if cls._instance is None:
            cls._instance = ElectionBus()
        return cls._instance

    def __init__(self):
        self._snapshots: dict[str, ElectionSnapshot] = {}
        self._ttl: float = 30.0                # Cache TTL in seconds
        self._min_ttl: float = 5.0              # Minimum TTL for healthy providers
        self._max_ttl: float = 60.0             # Maximum TTL for stable providers
        self._refresh_lock = asyncio.Lock()
        self._subscribers: list[Callable] = []
        self._health_checks: dict[str, int] = {}  # provider → consecutive successes

    def _make_key(self, providers: dict[str, Any]) -> str:
        return ",".join(sorted(providers.keys()))

    async def get_scores(
        self, providers: dict[str, Any], free_models: list[str],
        force: bool = False, task_type: str = "general",
    ) -> list[Any]:
        """Get election scores, using cache if fresh or computing if stale/forced."""
        key = self._make_key(providers)
        snapshot = self._snapshots.get(key)

        if not force and snapshot and (time.time() - snapshot.timestamp) < self._ttl:
            return snapshot.scores

        async with self._refresh_lock:
            snapshot = self._snapshots.get(key)
            if not force and snapshot and (time.time() - snapshot.timestamp) < self._ttl:
                return snapshot.scores

            # ── PredictiveRouter: filter to top-K predicted providers ──
            candidate_names = list(providers.keys())
            try:
                from .predictive_router import get_predictive_router
                pred = get_predictive_router()
                top5 = pred.predict_top(providers, n=5)
                if top5 and len(top5) < len(candidate_names):
                    candidate_names = top5
            except Exception:
                pass

            from .holistic_election import get_election
            election = get_election()
            scores = await election.score_providers(
                candidate_names, providers, free_models, task_type=task_type,
            )

            self._snapshots[key] = ElectionSnapshot(
                scores=scores,
                timestamp=time.time(),
                candidates_hash=key,
            )

            # Adaptive TTL: extend when stable, shorten on errors
            healthy = sum(1 for s in scores if getattr(s, 'alive', False))
            total = max(len(scores), 1)
            health_ratio = healthy / total
            if health_ratio > 0.8:
                self._ttl = min(self._ttl * 1.2, self._max_ttl)
            elif health_ratio < 0.5:
                self._ttl = max(self._ttl * 0.5, self._min_ttl)

            # Notify subscribers
            for cb in self._subscribers:
                try:
                    cb(scores)
                except Exception:
                    pass

            return scores

    async def force_refresh(self) -> None:
        """Force next get_scores() call to re-elect."""
        async with self._refresh_lock:
            self._snapshots.clear()
            self._ttl = self._min_ttl

    def on_refresh(self, callback: Callable) -> None:
        """Subscribe to election refresh events."""
        self._subscribers.append(callback)

    def get_top(self, providers: dict[str, Any], free_models: list[str], n: int = 3) -> list[str]:
        """Synchronous: get top N provider names from cache."""
        key = self._make_key(providers)
        snapshot = self._snapshots.get(key)
        if not snapshot:
            return []
        alive = [s for s in snapshot.scores if getattr(s, 'alive', False)]
        return [s.name for s in alive[:n]]

    def stats(self) -> dict:
        return {
            "cached_snapshots": len(self._snapshots),
            "ttl": round(self._ttl, 1),
            "subscribers": len(self._subscribers),
        }


_election_bus: Optional[ElectionBus] = None


def get_election_bus() -> ElectionBus:
    global _election_bus
    if _election_bus is None:
        _election_bus = ElectionBus()
    return _election_bus


__all__ = ["ElectionBus", "ElectionSnapshot", "get_election_bus"]
