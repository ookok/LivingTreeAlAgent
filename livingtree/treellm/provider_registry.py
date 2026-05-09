"""ProviderRegistry — plugin-based LLM provider registration.

Replaces the old 5-file modification pattern (providers.py, settings.py,
holistic_election.py, free_pool_manager.py, economic_engine.py) with a
single `ProviderRegistry.register()` call.

Usage:
    registry = ProviderRegistry()
    registry.register("sensetime", {
        "factory": create_sensetime_provider,
        "base_url": "https://api.sensetime.com/v1",
        "api_key": "sk-xxx",
        "capabilities": ["推理", "中文", "代码"],
        "pool_profile": {"coding": 0.6, "reasoning": 0.7, ...},
        "pricing": {"input": 0.0, "output": 0.0},
    })
    
    # All 5 integration points updated automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from loguru import logger


@dataclass
class ProviderSpec:
    """Complete specification for one LLM provider."""
    name: str
    display_name: str = ""
    base_url: str = ""
    api_key: str = ""
    default_model: str = ""
    is_free: bool = False
    # Election capabilities
    capabilities: list[str] = field(default_factory=list)
    # Free pool profile
    pool_profile: dict[str, Any] = field(default_factory=dict)
    # Pricing (CNY per 1M tokens)
    pricing_input: float = 0.0
    pricing_output: float = 0.0
    # Factory function
    factory: Callable | None = None


class ProviderRegistry:
    """Central registry for LLM provider plugins.

    One `register()` call updates all 5 integration points:
      1. providers.py → factory function
      2. settings.py → API key + base URL
      3. holistic_election.py → capabilities
      4. free_pool_manager.py → pool profile
      5. economic_engine.py → pricing
    """

    def __init__(self):
        self._providers: dict[str, ProviderSpec] = {}
        # Pre-loaded specs for known providers (backward compatible)
        self._load_builtins()

    def register(self, spec: ProviderSpec) -> None:
        """Register a provider and update all integration points."""
        self._providers[spec.name] = spec

        # 1. Register in free pool
        try:
            from ..treellm.free_pool_manager import get_free_pool, FREE_MODEL_PRESETS
            pool = get_free_pool()
            if spec.pool_profile:
                FREE_MODEL_PRESETS[spec.name] = spec.pool_profile
                pool.register(spec.name, **spec.pool_profile)
        except Exception as e:
            logger.debug(f"Registry: pool registration skipped for {spec.name}: {e}")

        # 2. Register capabilities
        try:
            from ..treellm.holistic_election import PROVIDER_CAPABILITIES
            if spec.capabilities:
                PROVIDER_CAPABILITIES[spec.name] = spec.capabilities
        except Exception as e:
            logger.debug(f"Registry: capability registration skipped: {e}")

        # 3. Register pricing
        try:
            from ..economy.economic_engine import ROIModel
            if spec.pricing_input >= 0:
                ROIModel.MODEL_PRICE_INPUT[f"{spec.name}/{spec.default_model}"] = spec.pricing_input
            if spec.pricing_output >= 0:
                ROIModel.MODEL_PRICE_OUTPUT[f"{spec.name}/{spec.default_model}"] = spec.pricing_output
        except Exception as e:
            logger.debug(f"Registry: pricing registration skipped: {e}")

        # 4. Store config for factory creation
        if spec.api_key or spec.base_url:
            try:
                from ..config.settings import get_config
                cfg = get_config()
                cfg.model.__dict__[f"{spec.name}_api_key"] = spec.api_key
                cfg.model.__dict__[f"{spec.name}_base_url"] = spec.base_url
            except Exception:
                pass

        logger.info(f"ProviderRegistry: {spec.name} registered ({len(spec.capabilities)} caps, "
                    f"pricing=¥{spec.pricing_input}/¥{spec.pricing_output})")

    def unregister(self, name: str) -> None:
        """Remove a provider from all integration points."""
        self._providers.pop(name, None)
        try:
            from ..treellm.free_pool_manager import FREE_MODEL_PRESETS
            FREE_MODEL_PRESETS.pop(name, None)
            from ..treellm.holistic_election import PROVIDER_CAPABILITIES
            PROVIDER_CAPABILITIES.pop(name, None)
        except Exception:
            pass
        logger.info(f"ProviderRegistry: {name} unregistered")

    def list(self) -> list[str]:
        return list(self._providers.keys())

    def get(self, name: str) -> ProviderSpec | None:
        return self._providers.get(name)

    def create_provider(self, name: str):
        """Create a provider instance from the registered spec."""
        spec = self._providers.get(name)
        if not spec or not spec.factory:
            return None
        return spec.factory(api_key=spec.api_key or "", model=spec.default_model)

    def _load_builtins(self):
        """Pre-load known providers from existing presets."""
        try:
            from ..treellm.free_pool_manager import FREE_MODEL_PRESETS
            from ..treellm.holistic_election import PROVIDER_CAPABILITIES

            for name, profile in FREE_MODEL_PRESETS.items():
                caps = PROVIDER_CAPABILITIES.get(name, [])
                self._providers[name] = ProviderSpec(
                    name=name, display_name=name,
                    capabilities=list(caps),
                    pool_profile=dict(profile),
                    is_free=True,
                )
        except Exception:
            pass

    def stats(self) -> dict[str, Any]:
        return {
            "registered": len(self._providers),
            "providers": sorted(self._providers.keys()),
            "free_count": sum(1 for p in self._providers.values() if p.is_free),
        }


# ═══ Singleton ═══

_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


__all__ = ["ProviderRegistry", "ProviderSpec", "get_provider_registry"]
