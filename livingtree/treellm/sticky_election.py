"""Sticky Layer Election — startup-elected providers, locked until failure.

Problem: Per-request provider election introduces latency variance and
cost unpredictability. Providers should be elected once at startup and
locked, with per-layer re-election only on failure.

Architecture:
  L0 (primary)    → fastest/cheapest provider for simple tasks
  L1 (fallback)   → balanced provider for routine tasks
  L2 (reasoning)  → best reasoning capability
  L3 (creative)   → highest quality generation
  L4 (emergency)  → last-resort provider when all above fail

Flow:
  Startup → elect all 5 layers → lock → no re-election
  Request → use L0; if fail → L1; if fail → ... L4
  Layer fail → mark degraded → re-elect ONLY that layer → relock

Integration:
  election = get_sticky_election()
  await election.elect_all()  # called once at startup
  provider = election.get_provider(layer=0)  # get cached L0
  election.mark_failure(layer=0)  # on error, triggers re-election
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class LayerBinding:
    """A locked provider binding for one election layer."""
    layer: int
    provider_name: str
    model: str = ""
    elected_at: float = 0.0
    failure_count: int = 0
    success_count: int = 0
    last_error: str = ""
    degraded: bool = False


class StickyElection:
    """Startup-elected provider layers, locked until failure."""

    LAYER_COUNT = 5
    LAYER_NAMES = {0: "primary", 1: "fallback", 2: "reasoning", 3: "creative", 4: "emergency"}

    _instance: Optional["StickyElection"] = None
    _lock = threading.Lock()

    def __init__(self, tree_llm=None):
        self._tree = tree_llm
        self._layers: dict[int, LayerBinding] = {}
        self._lock = threading.RLock()
        self._initialized = False

    @classmethod
    def instance(cls, tree_llm=None) -> "StickyElection":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = StickyElection(tree_llm)
        return cls._instance

    # ═══ Election ══════════════════════════════════════════════════

    async def elect_all(self) -> dict[int, LayerBinding]:
        """Run full L0-L4 election once at startup."""
        with self._lock:
            for layer in range(self.LAYER_COUNT):
                binding = await self._elect_layer(layer)
                self._layers[layer] = binding
                logger.info(f"StickyElection L{layer} ({self.LAYER_NAMES[layer]}): {binding.provider_name}/{binding.model}")
            self._initialized = True
            return dict(self._layers)

    async def reelect_layer(self, layer: int) -> LayerBinding:
        """Re-elect ONLY the specified layer (on failure)."""
        with self._lock:
            old = self._layers.get(layer)
            binding = await self._elect_layer(layer, exclude=old.provider_name if old else "")
            self._layers[layer] = binding
            if old:
                logger.warning(f"StickyElection L{layer} re-elected: {old.provider_name}→{binding.provider_name} (failures={old.failure_count})")
            return binding

    async def _elect_layer(self, layer: int, exclude: str = "") -> LayerBinding:
        """Elect the best provider for a specific layer.

        Layer-specific criteria:
          L0: cheapest + fastest
          L1: balanced
          L2: highest reasoning score
          L3: highest quality/creativity
          L4: most reliable (survivability)
        """
        candidates = self._get_candidates()
        if exclude:
            candidates = [c for c in candidates if c.get("name") != exclude]

        if not candidates:
            return LayerBinding(layer=layer, provider_name="unknown", model="unknown",
                               elected_at=time.time())

        if layer == 0:
            best = min(candidates, key=lambda c: (c.get("cost", 999), c.get("avg_latency_ms", 9999)))
        elif layer == 1:
            scored = [(c, c.get("success_rate", 0) * 0.6 + (1 - c.get("avg_latency_ms", 0) / 10000) * 0.4) for c in candidates]
            best = max(scored, key=lambda x: x[1])[0]
        elif layer == 2:
            best = max(candidates, key=lambda c: c.get("reasoning_score", 0) or c.get("capability_score", 0))
        elif layer == 3:
            best = max(candidates, key=lambda c: c.get("quality_score", 0) or c.get("success_rate", 0))
        else:  # L4 emergency
            best = max(candidates, key=lambda c: c.get("survivability", 0) or c.get("success_rate", 0))

        return LayerBinding(
            layer=layer,
            provider_name=best.get("name", "unknown"),
            model=best.get("model", best.get("default_model", "")),
            elected_at=time.time(),
        )

    # ═══ Provider Management ═══════════════════════════════════════

    def get_provider(self, layer: int = 0) -> LayerBinding | None:
        """Get the locked provider for a layer. Returns None if not elected yet."""
        return self._layers.get(layer)

    def mark_failure(self, layer: int, error: str = ""):
        """Mark layer provider as failed — triggers degradation."""
        with self._lock:
            if layer in self._layers:
                binding = self._layers[layer]
                binding.failure_count += 1
                binding.last_error = error
                if binding.failure_count >= 2:
                    binding.degraded = True
                    logger.warning(f"StickyElection L{layer} DEGRADED: {binding.provider_name} ({error[:80]})")

    def mark_success(self, layer: int):
        """Mark layer provider as successful."""
        with self._lock:
            if layer in self._layers:
                binding = self._layers[layer]
                binding.success_count += 1
                if binding.failure_count > 0:
                    binding.failure_count = max(0, binding.failure_count - 1)

    def is_degraded(self, layer: int) -> bool:
        binding = self._layers.get(layer)
        return binding.degraded if binding else False

    # ═══ Internal ═══════════════════════════════════════════════════

    def _get_candidates(self) -> list[dict]:
        """Get all available provider candidates with scores."""
        candidates = []
        try:
            if self._tree and hasattr(self._tree, '_providers'):
                for name, p in self._tree._providers.items():
                    candidates.append({
                        "name": name,
                        "model": getattr(p, 'default_model', ''),
                        "success_rate": getattr(p, 'success_rate', 0.5),
                        "avg_latency_ms": getattr(p, 'avg_latency_ms', 1000.0),
                        "cost": getattr(p, 'cost_per_1k', 0.0),
                        "reasoning_score": getattr(p, 'reasoning_score', 0.0),
                        "capability_score": getattr(p, 'capability_score', 0.0),
                        "quality_score": getattr(p, 'quality_score', 0.0),
                        "survivability": getattr(p, 'survivability', 0.5),
                    })
        except Exception as e:
            logger.debug(f"StickyElection candidates: {e}")

        if not candidates and self._tree:
            try:
                reg = getattr(self._tree, '_registry', None)
                if reg:
                    for name, info in reg.list_all().items():
                        candidates.append({"name": name, "model": info.get("default_model", "")})
            except Exception:
                pass

        return candidates

    # ═══ Stats ═════════════════════════════════════════════════════

    def stats(self) -> dict:
        return {
            "initialized": self._initialized,
            "layers": {
                str(l): {
                    "provider": b.provider_name,
                    "model": b.model,
                    "degraded": b.degraded,
                    "failures": b.failure_count,
                    "successes": b.success_count,
                    "last_error": b.last_error[:100],
                    "elected_at": b.elected_at,
                }
                for l, b in self._layers.items()
            },
        }


_sticky: Optional[StickyElection] = None


def get_sticky_election(tree_llm=None) -> StickyElection:
    global _sticky
    if _sticky is None or tree_llm:
        _sticky = StickyElection(tree_llm)
    return _sticky
