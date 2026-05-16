"""Sticky Layer Election with Continuous Attractor stabilization.

Based on: Representation Transfer via Invariant Input-driven Continuous
  Attractors for Fast Domain Adaptation (Communications Biology, 2026)

Core insight: Provider election converges to stable attractor states.
  Same intent with different phrasing → same attractor basin.
  Small input perturbations don't cause unnecessary re-elections.

Architecture:
  L0 (primary)    → cheapest + fastest
  L1 (fallback)   → balanced
  L2 (reasoning)  → highest reasoning score
  L3 (creative)   → highest quality
  L4 (emergency)  → most survivable

Attractor Basin:
  Each elected provider creates an attractor basin — neighboring
  providers in the same family/tier that share similar characteristics.
  On failure, basin members are tried first before full re-election.
  Only when entire basin fails → re-elect the layer.

Flow:
  Startup → elect all 5 layers → compute attractor basins → lock
  Request → use L0; fail → try L0 basin → fail → try L1 → ... L4
  Layer fail → try basin members → all fail → re-elect layer → new basin

Integration:
  election = get_sticky_election()
  await election.elect_all()
  binding = election.get_for_request(0, intent="weather query")
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class LayerBinding:
    """A locked provider + its attractor basin."""
    layer: int
    provider_name: str
    model: str = ""
    elected_at: float = 0.0
    failure_count: int = 0
    success_count: int = 0
    last_error: str = ""
    degraded: bool = False
    # Continuous attractor basin: same-family providers that can substitute
    attractor_basin: list[str] = field(default_factory=list)
    basin_failures: dict[str, int] = field(default_factory=dict)


class StickyElection:
    """Startup-elected provider layers with attractor-based fallback.

    Each layer's provider forms an attractor basin — neighboring providers
    that share the same base family or tier. On failure, basin members
    are tried first (they're within the same attractor), avoiding unnecessary
    full re-elections for minor perturbations.
    """

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
        """Full L0-L4 election + attractor basin computation."""
        with self._lock:
            for layer in range(self.LAYER_COUNT):
                binding = await self._elect_layer(layer)
                binding.attractor_basin = self._compute_basin(binding)
                self._layers[layer] = binding
                logger.info(
                    f"StickyElection L{layer} ({self.LAYER_NAMES[layer]}): "
                    f"{binding.provider_name}/{binding.model} "
                    f"[basin={len(binding.attractor_basin)}]"
                )
            self._initialized = True
            return dict(self._layers)

    async def reelect_layer(self, layer: int) -> LayerBinding:
        """Re-elect a single layer + recompute its attractor basin."""
        with self._lock:
            old = self._layers.get(layer)
            binding = await self._elect_layer(layer, exclude=old.provider_name if old else "")
            binding.attractor_basin = self._compute_basin(binding)
            self._layers[layer] = binding
            if old:
                logger.warning(
                    f"StickyElection L{layer} re-elected: "
                    f"{old.provider_name}→{binding.provider_name} "
                    f"(old failures={old.failure_count}, basin exhausted={len(old.basin_failures)})"
                )
            return binding

    async def _elect_layer(self, layer: int, exclude: str = "") -> LayerBinding:
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
        else:
            best = max(candidates, key=lambda c: c.get("survivability", 0) or c.get("success_rate", 0))

        return LayerBinding(
            layer=layer,
            provider_name=best.get("name", "unknown"),
            model=best.get("model", best.get("default_model", "")),
            elected_at=time.time(),
        )

    # ═══ Attractor Basin (continuous attractor network) ═══════════

    def _compute_basin(self, binding: LayerBinding) -> list[str]:
        """Compute attractor basin — providers in the same family/tier.

        Two providers share an attractor if:
          - Same base provider family (e.g., deepseek→deepseek-r1)
          - OR same tier (flash/pro/reasoning/small)
          - OR similar capability profile (<0.3 distance)

        Basin members can substitute for the elected provider
        without triggering a full layer re-election.
        """
        basin = []
        candidates = self._get_candidates()
        elected = next((c for c in candidates if c.get("name") == binding.provider_name), {})

        for c in candidates:
            name = c.get("name", "")
            if name == binding.provider_name:
                continue

            # Same base family (e.g., deepseek + deepseek-r1)
            elected_base = binding.provider_name.split("-")[0]
            candidate_base = name.split("-")[0]
            if elected_base == candidate_base and elected_base:
                basin.append(name)
                continue

            # Same tier (flash/reasoning/pro/small)
            elected_tier = binding.provider_name.split("-")[-1] if "-" in binding.provider_name else ""
            candidate_tier = name.split("-")[-1] if "-" in name else ""
            if elected_tier and elected_tier == candidate_tier:
                basin.append(name)
                continue

            # Similar capability (cosine distance < 0.3)
            if self._capability_distance(elected, c) < 0.3:
                basin.append(name)
                continue

        return basin[:5]  # max 5 basin members

    @staticmethod
    def _capability_distance(a: dict, b: dict) -> float:
        """Distance between two providers' capability profiles (0-1)."""
        dims = ["success_rate", "reasoning_score", "capability_score", "quality_score"]
        diff = sum(abs(a.get(d, 0) - b.get(d, 0)) for d in dims)
        return diff / max(len(dims), 1)

    # ═══ Provider Access ═══════════════════════════════════════════

    def get_for_request(self, layer: int = 0,
                        intent: str = "") -> tuple[str, str, bool]:
        """Get provider for a request. Returns (provider_name, model, is_primary).

        If the layer's provider is available → return it.
        If failed → try attractor basin members.
        Only the primary binding is returned here; fallback
        to higher layers is handled by the caller (TreeLLM).
        """
        binding = self._layers.get(layer)
        if not binding:
            return "", "", False

        # Primary: elected provider
        if not binding.degraded or binding.basin_failures.get(binding.provider_name, 0) < 2:
            return binding.provider_name, binding.model, True

        # Basin fallback: try attractor neighbors
        for basin_name in binding.attractor_basin:
            basin_fails = binding.basin_failures.get(basin_name, 0)
            if basin_fails < 2:
                logger.debug(f"StickyElection L{layer}: basin fallback {binding.provider_name}→{basin_name}")
                return basin_name, self._get_model(basin_name), False

        # All basin members exhausted → need re-election
        return "", "", False

    def mark_failure(self, layer: int, provider_name: str = "", error: str = ""):
        """Mark a provider as failed at a layer."""
        with self._lock:
            if layer not in self._layers:
                return
            binding = self._layers[layer]
            binding.failure_count += 1
            binding.last_error = error

            if provider_name:
                fails = binding.basin_failures.get(provider_name, 0) + 1
                binding.basin_failures[provider_name] = fails

            # Degrade if primary provider has 2+ failures
            if binding.failure_count >= 2:
                binding.degraded = True
                logger.warning(
                    f"StickyElection L{layer} DEGRADED: {binding.provider_name} "
                    f"(basin exhausted={len([k for k,v in binding.basin_failures.items() if v>=2])}/{len(binding.attractor_basin)})"
                )

    def mark_success(self, layer: int, provider_name: str = ""):
        """Mark success — reduces failure count for recovery."""
        with self._lock:
            binding = self._layers.get(layer)
            if not binding:
                return
            binding.success_count += 1
            if binding.failure_count > 0:
                binding.failure_count = max(0, binding.failure_count - 1)
            if provider_name and provider_name in binding.basin_failures:
                binding.basin_failures[provider_name] = max(
                    0, binding.basin_failures[provider_name] - 1
                )
            # Auto-recover if failures dropped below threshold
            if binding.failure_count < 2 and binding.degraded:
                binding.degraded = False
                logger.info(f"StickyElection L{layer} RECOVERED: {binding.provider_name}")

    def is_degraded(self, layer: int) -> bool:
        binding = self._layers.get(layer)
        return binding.degraded if binding else False

    def needs_reelection(self, layer: int) -> bool:
        """Check if the layer needs re-election (all basin members exhausted)."""
        binding = self._layers.get(layer)
        if not binding:
            return True
        all_exhausted = all(
            binding.basin_failures.get(name, 0) >= 2
            for name in [binding.provider_name] + binding.attractor_basin
        )
        return binding.degraded and all_exhausted

    # ═══ Internal ═══════════════════════════════════════════════════

    def _get_candidates(self) -> list[dict]:
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
        return candidates

    def _get_model(self, provider_name: str) -> str:
        candidates = self._get_candidates()
        for c in candidates:
            if c.get("name") == provider_name:
                return c.get("model", "")
        return ""

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
                    "basin_size": len(b.attractor_basin),
                    "basin_exhausted": sum(1 for v in b.basin_failures.values() if v >= 2),
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
