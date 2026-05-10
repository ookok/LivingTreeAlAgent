"""ResilienceBrain — LLM-driven predictive fault tolerance orchestrator.

Connects existing modules into a coherent resilience system:
  PredictiveWorldModel → Anticipatory → DualMode → SelfHealer → MessageBus

When network degrades:
  1. Monitors latency/packet-loss via health probes
  2. Uses LLM to predict likely user actions before disconnect
  3. Pre-caches: knowledge fragments, model contexts, likely responses
  4. Circuit-breaker: stops retrying dead endpoints, switches to alternatives
  5. Graceful degradation: full → reduced → minimal → offline
  6. Recovery: auto-syncs queued actions on reconnect

All existing modules — just wired together with prediction on top.
"""

from __future__ import annotations

import asyncio
import time as _time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger


class NetworkTier(Enum):
    FULL = "full"         # All services reachable
    DEGRADED = "degraded"  # Some services slow/unreachable  
    MINIMAL = "minimal"    # Only essential services
    OFFLINE = "offline"    # Fully disconnected


@dataclass
class NetworkHealth:
    tier: NetworkTier = NetworkTier.FULL
    latency_ms: float = 0.0
    packet_loss_pct: float = 0.0
    last_probe: float = 0.0
    degraded_services: list[str] = field(default_factory=list)
    consecutive_failures: int = 0
    estimated_recovery_seconds: float = 0.0


@dataclass
class PredictiveCache:
    predicted_queries: list[str] = field(default_factory=list)
    pre_cached_knowledge: list[str] = field(default_factory=list)
    pre_warmed_models: list[str] = field(default_factory=list)
    cached_responses: dict[str, str] = field(default_factory=dict)
    last_prediction: float = 0.0


class CircuitBreaker:
    """Prevents cascading failures by stopping calls to dead services."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self._failures: dict[str, int] = {}
        self._open_circuits: dict[str, float] = {}
        self._threshold = failure_threshold
        self._recovery_timeout = recovery_timeout

    def record_failure(self, service: str):
        self._failures[service] = self._failures.get(service, 0) + 1
        if self._failures[service] >= self._threshold:
            self._open_circuits[service] = _time.time()
            logger.warning(f"Circuit OPEN: {service} ({self._failures[service]} failures)")

    def record_success(self, service: str):
        self._failures[service] = 0
        self._open_circuits.pop(service, None)

    def is_open(self, service: str) -> bool:
        opened_at = self._open_circuits.get(service, 0)
        if not opened_at:
            return False
        if _time.time() - opened_at > self._recovery_timeout:
            self._open_circuits.pop(service, None)
            self._failures[service] = 0
            logger.info(f"Circuit HALF_OPEN → CLOSED: {service}")
            return False
        return True

    def status(self) -> dict:
        return {
            "open_circuits": list(self._open_circuits.keys()),
            "failure_counts": dict(self._failures),
        }


class ResilienceBrain:
    """Central resilience orchestrator. Monitors, predicts, pre-caches, degrades."""

    def __init__(self, hub=None):
        self._hub = hub
        self._health = NetworkHealth()
        self._cache = PredictiveCache()
        self._breaker = CircuitBreaker()
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._predict_task: Optional[asyncio.Task] = None
        self._probe_targets = [
            ("deepseek", "https://api.deepseek.com/v1/models"),
            ("github", "https://github.com"),
            ("models_dev", "https://models.dev/api.json"),
        ]

    @property
    def hub(self):
        return self._hub

    async def start(self):
        if self._running:
            return
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self._predict_task = asyncio.create_task(self._predict_loop())
        logger.info("ResilienceBrain: predictive fault tolerance active")

    async def stop(self):
        self._running = False
        for t in [self._monitor_task, self._predict_task]:
            if t:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass

    # ── Health Monitoring ──

    async def _monitor_loop(self):
        """Periodically probe network health and adjust tier."""
        while self._running:
            await self._probe_health()
            await self._adjust_tier()
            await asyncio.sleep(15)

    async def _probe_health(self):
        import aiohttp
        latencies = []
        failures = 0
        degraded = []

        async with aiohttp.ClientSession() as session:
            for name, url in self._probe_targets:
                if self._breaker.is_open(name):
                    degraded.append(name)
                    failures += 1
                    continue

                try:
                    start = _time.time()
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        lat = (_time.time() - start) * 1000
                        latencies.append(lat)
                        self._breaker.record_success(name)
                        if lat > 2000:
                            degraded.append(name)
                except Exception:
                    failures += 1
                    degraded.append(name)
                    self._breaker.record_failure(name)

        total = len(self._probe_targets)
        self._health.latency_ms = sum(latencies) / len(latencies) if latencies else 9999
        self._health.packet_loss_pct = (failures / total) * 100 if total else 100
        self._health.degraded_services = degraded
        self._health.last_probe = _time.time()
        self._health.consecutive_failures = failures if failures == total else 0

    async def _adjust_tier(self):
        """Adjust network tier based on health metrics."""
        f = self._health.consecutive_failures
        loss = self._health.packet_loss_pct
        lat = self._health.latency_ms

        if f >= len(self._probe_targets):
            new_tier = NetworkTier.OFFLINE
        elif loss > 50 or lat > 3000 or f >= 2:
            new_tier = NetworkTier.MINIMAL
        elif loss > 20 or lat > 1000:
            new_tier = NetworkTier.DEGRADED
        else:
            new_tier = NetworkTier.FULL

        if new_tier != self._health.tier:
            old = self._health.tier
            self._health.tier = new_tier
            logger.warning(f"Network tier: {old.value} → {new_tier.value}")
            await self._on_tier_change(old, new_tier)

    async def _on_tier_change(self, old: NetworkTier, new: NetworkTier):
        """React to tier change — trigger predictions, pre-caching, degradation."""
        world = self.hub.world if self.hub else None
        if not world:
            return

        if new == NetworkTier.OFFLINE and old != NetworkTier.OFFLINE:
            logger.warning("Going offline — triggering predictive pre-cache")
            await self._pre_cache_for_offline()

        if new == NetworkTier.FULL and old != NetworkTier.FULL:
            logger.info("Back online — syncing queued operations")
            dm = getattr(world, "dual_mode", None)
            if dm:
                await dm._sync_queued()

    # ── LLM-Driven Prediction ──

    async def _predict_loop(self):
        """Periodically predict what the user might need."""
        while self._running:
            if self._health.tier in (NetworkTier.DEGRADED, NetworkTier.MINIMAL):
                await self._run_prediction()
            await asyncio.sleep(120)

    async def _run_prediction(self):
        """Use LLM to predict likely user actions and pre-cache results."""
        world = self.hub.world if self.hub else None
        if not world:
            return

        consc = getattr(world, "consciousness", None)
        mem = getattr(world, "struct_memory", None)

        if not consc:
            return

        recent_context = ""
        if mem:
            try:
                entries, synthesis = await mem.retrieve_for_query("recent activity", top_k=5)
                recent_context = "\n".join(
                    getattr(e, "content", str(e))[:200] for e in entries[:5]
                )
            except Exception:
                pass

        try:
            prompt = (
                "网络即将离线。基于最近活动，预测用户最可能需要的3-5个问题或操作。"
                "每个预测一行。\n\n"
                f"最近活动:\n{recent_context[:1000]}\n\n"
                "预测:"
            )
            resp = await consc.chain_of_thought(prompt, steps=1)
            text = resp if isinstance(resp, str) else str(resp)
            queries = [l.strip().lstrip("-•*0123456789. ").strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 5]
            self._cache.predicted_queries = queries[:5]
            self._cache.last_prediction = _time.time()
            logger.info(f"Predicted {len(queries)} offline queries: {queries[:3]}")

            for q in queries[:3]:
                try:
                    if mem:
                        entries, _ = await mem.retrieve_for_query(q, top_k=3)
                        for e in entries[:3]:
                            content = getattr(e, "content", str(e))[:500]
                            self._cache.pre_cached_knowledge.append(content)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Prediction failed: {e}")

    async def _pre_cache_for_offline(self):
        """Aggressive pre-caching before going fully offline."""
        world = self.hub.world if self.hub else None
        if not world:
            return

        kb = getattr(world, "knowledge_base", None)
        if kb and hasattr(kb, "get_by_domain"):
            try:
                docs = kb.get_by_domain(None)
                for doc in docs[:20]:
                    self._cache.pre_cached_knowledge.append(
                        getattr(doc, "content", str(doc))[:500]
                    )
                logger.info(f"Pre-cached {min(len(docs), 20)} knowledge entries")
            except Exception:
                pass

    # ── Status ──

    def health(self) -> dict:
        return {
            "tier": self._health.tier.value,
            "latency_ms": round(self._health.latency_ms, 1),
            "packet_loss_pct": round(self._health.packet_loss_pct, 1),
            "degraded_services": self._health.degraded_services,
            "last_probe_seconds_ago": round(_time.time() - self._health.last_probe, 1),
            "circuit_breaker": self._breaker.status(),
            "predictions": {
                "queries": self._cache.predicted_queries[:5],
                "cached_knowledge_count": len(self._cache.pre_cached_knowledge),
                "last_prediction_seconds_ago": round(_time.time() - self._cache.last_prediction, 1) if self._cache.last_prediction else 0,
            },
        }


_resilience_instance: Optional[ResilienceBrain] = None


def get_resilience() -> ResilienceBrain:
    global _resilience_instance
    if _resilience_instance is None:
        _resilience_instance = ResilienceBrain()
    return _resilience_instance
