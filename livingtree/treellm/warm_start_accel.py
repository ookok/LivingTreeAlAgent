"""WarmStartAccel — Pre-warms providers and caches on startup.

Eliminates cold-start latency by:
  1. Pinging top-N fastest providers in parallel
  2. Sending 1-token warmup requests to pre-establish HTTP keepalive
  3. Pre-caching ElectionBus scores so the first real request has zero wait

Integration:
    accel = get_warm_start_accel()
    await accel.warmup(llm, providers)  # called in hub._init_async()
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Optional

from loguru import logger


class WarmStartAccel:
    """Pre-warms providers and caches on startup to eliminate cold starts."""

    _instance: Optional["WarmStartAccel"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "WarmStartAccel":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = WarmStartAccel()
        return cls._instance

    def __init__(self):
        self._warmed = False
        self._warmup_time_ms = 0.0
        self._providers_warmed = 0

    async def warmup(self, llm: Any, providers: dict[str, Any],
                     free_models: list[str] = None, top_n: int = 5) -> int:
        """Pre-warm providers and cache election results.

        Returns number of providers successfully warmed.
        """
        if self._warmed:
            return self._providers_warmed

        t0 = time.monotonic()

        if not providers:
            logger.info("WarmStart: no providers to warm")
            return 0

        # Phase 1: Parallel ping top-N fastest providers
        sorted_providers = sorted(
            providers.keys(),
            key=lambda n: getattr(providers[n], 'avg_latency_ms', 999) or 999,
        )[:top_n]

        async def _ping(name):
            try:
                p = providers[name]
                ok, _ = await p.ping()
                return name, ok
            except Exception:
                return name, False

        ping_results = await asyncio.gather(*[_ping(n) for n in sorted_providers])
        alive = [name for name, ok in ping_results if ok]

        # Phase 2: Warm HTTP connections with 1-token requests
        warm_results = await asyncio.gather(*[
            llm.chat(
                [{"role": "user", "content": "ping"}],
                provider=name, max_tokens=1, timeout=5,
            )
            for name in alive[:3]
        ], return_exceptions=True)

        actual_warmed = sum(
            1 for r in warm_results
            if not isinstance(r, Exception) and getattr(r, 'text', None)
        )

        # Phase 3: Pre-cache election results
        try:
            from .election_bus import get_election_bus
            bus = get_election_bus()
            await bus.get_scores(providers, free_models or [], force=True)
        except Exception:
            pass

        self._warmed = True
        self._providers_warmed = actual_warmed
        self._warmup_time_ms = (time.monotonic() - t0) * 1000

        logger.info(
            f"WarmStart: {actual_warmed}/{len(alive)} providers warmed "
            f"in {self._warmup_time_ms:.0f}ms"
        )
        return actual_warmed

    @property
    def is_warmed(self) -> bool:
        return self._warmed

    def stats(self) -> dict:
        return {
            "warmed": self._warmed,
            "providers_warmed": self._providers_warmed,
            "warmup_time_ms": round(self._warmup_time_ms, 0),
        }


_accel: Optional[WarmStartAccel] = None
_accel_lock = threading.Lock()


def get_warm_start_accel() -> WarmStartAccel:
    global _accel
    if _accel is None:
        with _accel_lock:
            if _accel is None:
                _accel = WarmStartAccel()
    return _accel


__all__ = ["WarmStartAccel", "get_warm_start_accel"]
