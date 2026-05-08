"""ModelRegistry — fetch, filter, cache free models from all LLM platforms.

Periodically queries {base_url}/models on each provider, classifies
models by tier (flash/reasoning/pro/small/embedding), caches results,
and supports user overrides + scheduled refresh.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

CACHE_DIR = Path(".livingtree/model_cache")
CACHE_FILE = CACHE_DIR / "model_registry.json"
REFRESH_INTERVAL = 86400  # 24 hours
FETCH_TIMEOUT = 15.0


@dataclass
class ModelInfo:
    id: str
    provider: str
    owned_by: str = ""
    created: int = 0
    context_length: int = 4096
    free: bool = True
    tier: str = "flash"
    enabled: bool = True
    pricing: str = "free"

    @property
    def short_name(self) -> str:
        return self.id.split("/")[-1] if "/" in self.id else self.id

    @property
    def pricing_label(self) -> str:
        if self.pricing == "free":
            return "🆓"
        if self.pricing == "token":
            return "💰"
        if self.pricing in ("paid", "subscription"):
            return "💳"
        return ""

    @property
    def source_label(self) -> str:
        return self.provider.upper()


@dataclass
class ProviderModels:
    name: str
    base_url: str
    api_key: str = ""
    models: list[ModelInfo] = field(default_factory=list)
    last_fetched: float = 0.0
    error: str = ""


class ModelRegistry:
    """Central registry of available models from all providers."""

    _instance: ModelRegistry | None = None

    @classmethod
    def instance(cls) -> ModelRegistry:
        if cls._instance is None:
            cls._instance = ModelRegistry()
        return cls._instance

    def __init__(self):
        self._providers: dict[str, ProviderModels] = {}
        self._refresh_task: asyncio.Task | None = None
        self._loaded = False

    def register_provider(self, name: str, base_url: str, api_key: str = ""):
        if name not in self._providers:
            self._providers[name] = ProviderModels(
                name=name, base_url=base_url.rstrip("/"), api_key=api_key
            )

    async def fetch_models(self, provider_name: str) -> list[ModelInfo]:
        """Fetch models from a provider's /models endpoint."""
        p = self._providers.get(provider_name)
        if not p or not p.base_url:
            return []

        try:
            headers = {"Authorization": f"Bearer {p.api_key}"} if p.api_key else {}
            async with httpx.AsyncClient(timeout=FETCH_TIMEOUT) as client:
                resp = await client.get(f"{p.base_url}/models", headers=headers)
                if resp.status_code != 200:
                    p.error = f"HTTP {resp.status_code}"
                    return []

                data = resp.json()
                model_list = data.get("data", data) if isinstance(data, dict) else data
                if not isinstance(model_list, list):
                    p.error = f"Unexpected response: {type(data)}"
                    return []

                models = []
                for item in model_list:
                    if not isinstance(item, dict):
                        continue
                    mid = item.get("id", "")
                    if not mid:
                        continue
                    free_flag = self._guess_free(mid, item)
                    info = ModelInfo(
                        id=mid,
                        provider=provider_name,
                        owned_by=item.get("owned_by", ""),
                        created=item.get("created", 0),
                        context_length=item.get("context_length", 4096),
                        free=free_flag,
                        tier=self._classify_tier(mid, item),
                        pricing=self._guess_pricing(mid, item, free_flag),
                    )
                    models.append(info)

                p.models = models
                p.last_fetched = time.time()
                p.error = ""
                logger.info(f"Fetched {len(models)} models from {provider_name}")
                return models

        except Exception as e:
            p.error = str(e)[:120]
            logger.warning(f"Model fetch {provider_name}: {e}")
            return []

    def _guess_free(self, model_id: str, data: dict) -> bool:
        """Heuristic: most models on shared platforms are free-tier accessible."""
        free_keywords = ["free", "instruct", "1.5b", "3b", "7b", "8b", "0.5b", "1.8b"]
        mid_lower = model_id.lower()
        if any(k in mid_lower for k in free_keywords):
            return True
        # Check pricing metadata
        pricing = data.get("pricing", data.get("price", {}))
        if pricing:
            return pricing.get("prompt", "1") == "0" or pricing.get("type") == "free"
        return True  # default to free for shared platforms

    def _guess_pricing(self, model_id: str, data: dict, is_free: bool) -> str:
        """Classify pricing mode: free / token / subscription / paid."""
        if is_free:
            return "free"
        pricing = data.get("pricing", data.get("price", {}))
        if isinstance(pricing, dict):
            ptype = pricing.get("type", "")
            if ptype == "token":
                return "token"
            if ptype == "subscription":
                return "subscription"
            prompt_price = pricing.get("prompt", "")
            if prompt_price and prompt_price != "0":
                return "token"
        mid_lower = model_id.lower()
        if any(k in mid_lower for k in ["pro", "max", "premium"]):
            return "subscription"
        return "paid"

    def _classify_tier(self, model_id: str, data: dict) -> str:
        """Classify model into a usage tier."""
        mid_lower = model_id.lower()

        # Embedding models
        if any(k in mid_lower for k in ["embed", "bge", "e5", "stella", "rerank"]):
            return "embedding"

        # Reasoning models — QwQ, QvQ, R1, o1/3
        if any(k in mid_lower for k in ["r1", "reasoning", "deepseek-r1",
                                          "qwq", "qvq", "o1", "o3"]):
            return "reasoning"

        # Pro/large models — Qwen Max/Plus, DeepSeek V3, large LLaMA
        if any(k in mid_lower for k in [
            "70b", "72b", "405b", "671b", "35b",
            "pro", "max", "v3", "opus",
            "qwen3.6-plus", "qwen3.5-plus", "qwen-plus",
            "qwen3-max", "qwen3.6-max",
        ]):
            return "pro"

        # Small models
        if any(k in mid_lower for k in [
            "0.5b", "1.5b", "1.8b", "3b", "tiny", "mini",
            "qwen3-0.6b", "qwen3-1.7b", "qwen3-4b", "qwen3-8b",
        ]):
            return "small"

        # Code models
        if any(k in mid_lower for k in ["coder", "code", "deepseek-coder"]):
            return "code"

        # Image/multimodal — VL, vision, omni, image generation
        if any(k in mid_lower for k in [
            "vl", "vision", "image", "flux", "sd-", "stable",
            "omni", "qvq",
        ]):
            return "multimodal"

        # Qwen flash models → flash tier
        if any(k in mid_lower for k in [
            "qwen-flash", "qwen3.6-flash", "qwen3.5-flash",
        ]):
            return "flash"

        return "flash"  # default: fast chat model

    def get_models(self, provider: str, tier: str | None = None, free_only: bool = True) -> list[ModelInfo]:
        """Get models for a provider, optionally filtered by tier."""
        p = self._providers.get(provider)
        if not p:
            return []
        models = p.models
        if free_only:
            models = [m for m in models if m.free]
        if tier:
            models = [m for m in models if m.tier == tier]
        return models

    def get_best_model(self, provider: str, tier: str = "flash") -> str | None:
        """Get the best enabled model for a provider+tier combination."""
        models = self.get_models(provider, tier=tier)
        enabled = [m for m in models if m.enabled]
        if not enabled:
            return None
        # Prefer instruct models, then largest context
        enabled.sort(key=lambda m: (
            "instruct" not in m.id.lower(),
            -m.context_length,
        ))
        return enabled[0].id

    def get_all_providers(self) -> list[str]:
        return list(self._providers.keys())

    def get_stats(self) -> dict[str, Any]:
        return {
            name: {
                "models": len(p.models),
                "free": sum(1 for m in p.models if m.free),
                "last_fetch": p.last_fetched,
                "error": p.error,
            }
            for name, p in self._providers.items()
        }

    # ═══ Periodic refresh ═══

    async def refresh_all(self) -> dict[str, list[ModelInfo]]:
        """Fetch models from all registered providers."""
        results = {}
        tasks = []
        for name in self._providers:
            tasks.append((name, self.fetch_models(name)))
        gathered = await asyncio.gather(
            *(t[1] for t in tasks), return_exceptions=True
        )
        for (name, _), result in zip(tasks, gathered):
            if isinstance(result, Exception):
                logger.warning(f"Refresh {name}: {result}")
                results[name] = []
            else:
                results[name] = result
        self._save_cache()
        return results

    async def start_periodic_refresh(self, interval: float = REFRESH_INTERVAL):
        """Start periodic background refresh."""
        async def _loop():
            while True:
                await asyncio.sleep(interval)
                try:
                    await self.refresh_all()
                except Exception as e:
                    logger.warning(f"Periodic refresh: {e}")

        self._refresh_task = asyncio.create_task(_loop())
        logger.info(f"Model registry refresh every {interval:.0f}s")

    async def stop_refresh(self):
        if self._refresh_task:
            self._refresh_task.cancel()

    # ═══ Cache persistence ═══

    def _save_cache(self):
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            data = {}
            for name, p in self._providers.items():
                data[name] = {
                    "base_url": p.base_url,
                    "last_fetched": p.last_fetched,
                    "models": [
                        {"id": m.id, "provider": m.provider, "owned_by": m.owned_by,
                         "tier": m.tier, "free": m.free, "enabled": m.enabled,
                         "context_length": m.context_length}
                        for m in p.models
                    ],
                }
            CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.debug(f"Model cache save: {e}")

    def load_cache(self) -> bool:
        """Load cached model data from disk. Returns True if cache was loaded."""
        try:
            if not CACHE_FILE.exists():
                return False
            data = json.loads(CACHE_FILE.read_text())
            for name, cached in data.items():
                if name not in self._providers:
                    continue
                p = self._providers[name]
                p.last_fetched = cached.get("last_fetched", 0)
                p.models = [
                    ModelInfo(**m) for m in cached.get("models", [])
                ]
            logger.info(f"Loaded model cache ({len(data)} providers)")
            return True
        except Exception as e:
            logger.debug(f"Model cache load: {e}")
            return False

    # ── Models.dev Integration ────────────────────────────────────

    async def sync_from_models_dev(self, force: bool = False) -> int:
        """Sync model data from models.dev open database.

        Uses ModelsDevSync to fetch/cache the community-maintained model
        database, then populates ModelRegistry providers with the data.

        Returns number of models synced.
        """
        from .models_dev_sync import get_models_dev_sync

        sync = get_models_dev_sync()
        count = await sync.refresh(force=force)

        if count == 0:
            return 0

        synced = 0
        for provider_id in sync.get_providers():
            dev_models = sync.get_provider_models(provider_id)
            if not dev_models:
                continue

            provider_name = sync._providers.get(provider_id, {}).get("name", provider_id)

            # Register provider if not exists
            self.register_provider(
                name=provider_id,
                base_url=sync._providers.get(provider_id, {}).get("api",
                    f"https://api.{provider_id}.com/v1"),
            )

            p = self._providers.get(provider_id)
            if not p:
                continue

            # Convert DevModel → ModelInfo
            model_infos = []
            for dm in dev_models:
                is_free = dm.cost.is_free or dm.open_weights
                info = ModelInfo(
                    id=dm.id,
                    provider=dm.provider_id,
                    owned_by=dm.provider_name,
                    context_length=dm.limit.context,
                    free=is_free,
                    tier=dm.tier,
                    pricing="free" if is_free else "token",
                    enabled=True,
                )
                model_infos.append(info)

            p.models = model_infos
            p.last_fetched = time.time()
            synced += len(model_infos)

        logger.info(f"Models.dev synced: {synced} models across {len(sync.get_providers())} providers")
        self._save_cache()
        return synced


# ── Global singleton ──
def get_model_registry() -> ModelRegistry:
    return ModelRegistry.instance()
