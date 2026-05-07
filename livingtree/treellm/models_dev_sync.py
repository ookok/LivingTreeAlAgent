"""ModelsDevSync — Fetch, cache, and query the models.dev open model database.

models.dev (anomalyco/models.dev, 3.7k stars) is a community-maintained
database of AI model specifications, pricing, and capabilities. This module
syncs from https://models.dev/api.json, caches locally, and provides
structured queries for model routing and cost optimization.

Integration:
  - ModelRegistry:     populates model list from models.dev cache
  - EconomicPolicy:    select_model() uses capability filtering + real-time pricing
  - CostAware:         auto-syncs pricing tables
  - FitnessLandscape:  enriches cost dimension with provider-aware pricing

Cache: .livingtree/models_dev_cache.json (auto-refresh every 6 hours)
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

# ── Constants ──────────────────────────────────────────────────────

MODELS_DEV_API = "https://models.dev/api.json"
CACHE_DIR = Path(".livingtree/model_cache")
CACHE_FILE = CACHE_DIR / "models_dev.json"
REFRESH_INTERVAL = 21600  # 6 hours
FETCH_TIMEOUT = 30.0
USD_TO_CNY = 7.25


# ── Data Models ────────────────────────────────────────────────────

@dataclass
class ModelCost:
    input_per_1M: float = 0.0       # USD per 1M input tokens
    output_per_1M: float = 0.0      # USD per 1M output tokens
    reasoning_per_1M: float = 0.0   # USD per 1M reasoning tokens
    cache_read_per_1M: float = 0.0
    cache_write_per_1M: float = 0.0
    input_audio_per_1M: float = 0.0
    output_audio_per_1M: float = 0.0

    @property
    def input_cny(self) -> float:
        return round(self.input_per_1M * USD_TO_CNY, 2)

    @property
    def output_cny(self) -> float:
        return round(self.output_per_1M * USD_TO_CNY, 2)

    @property
    def avg_cny(self) -> float:
        return round((self.input_cny + self.output_cny) / 2, 2)

    @property
    def is_free(self) -> bool:
        return self.input_per_1M == 0.0 and self.output_per_1M == 0.0


@dataclass
class ModelLimit:
    context: int = 4096      # Max context window (tokens)
    max_input: int = 4096    # Max input tokens
    max_output: int = 4096   # Max output tokens


@dataclass
class Modalities:
    input: list[str] = field(default_factory=lambda: ["text"])
    output: list[str] = field(default_factory=lambda: ["text"])

    @property
    def supports_images(self) -> bool:
        return "image" in self.input

    @property
    def supports_audio(self) -> bool:
        return "audio" in self.input

    @property
    def supports_video(self) -> bool:
        return "video" in self.input

    @property
    def supports_pdf(self) -> bool:
        return "pdf" in self.input


@dataclass
class DevModel:
    """A single model entry from models.dev."""
    id: str                          # e.g. "openai/gpt-5"
    name: str = ""
    provider_id: str = ""            # e.g. "openai"
    provider_name: str = ""
    reasoning: bool = False
    tool_call: bool = False
    structured_output: bool = False
    temperature: bool = False
    attachment: bool = False
    open_weights: bool = False
    knowledge: str = ""              # "2024-04"
    release_date: str = ""
    cost: ModelCost = field(default_factory=ModelCost)
    limit: ModelLimit = field(default_factory=ModelLimit)
    modalities: Modalities = field(default_factory=Modalities)
    status: str = ""                 # alpha / beta / deprecated / ""

    @property
    def tier(self) -> str:
        """Classify model tier based on capabilities and name."""
        if self.reasoning and ("qwq" in self.id.lower() or "o1" in self.id.lower()
                               or "o3" in self.id.lower() or "r1" in self.id.lower()):
            return "reasoning"
        if "max" in self.id.lower() or "pro" in self.id.lower() or "opus" in self.id.lower():
            return "pro"
        if "flash" in self.id.lower() or "mini" in self.id.lower() or "nano" in self.id.lower():
            return "flash"
        if any(k in self.id.lower() for k in ["embed", "bge", "e5"]):
            return "embedding"
        if any(k in self.id.lower() for k in ["coder", "code"]):
            return "code"
        if self.modalities.supports_images or self.modalities.supports_video:
            return "multimodal"
        return "pro"  # Default unknown to pro

    def satisfies(self, requirements: dict) -> bool:
        """Check if this model satisfies capability requirements.

        Args:
            requirements: dict with optional keys:
                reasoning: bool
                tool_call: bool
                structured_output: bool
                attachment: bool
                open_weights: bool
                min_context: int
                max_input_cost_cny: float
                max_output_cost_cny: float
                modalities_input: list[str]
                status_exclude: list[str]  # exclude alpha/beta/deprecated
        """
        if requirements.get("reasoning") and not self.reasoning:
            return False
        if requirements.get("tool_call") and not self.tool_call:
            return False
        if requirements.get("structured_output") and not self.structured_output:
            return False
        if requirements.get("attachment") and not self.attachment:
            return False
        if requirements.get("open_weights") and not self.open_weights:
            return False

        min_ctx = requirements.get("min_context", 0)
        if self.limit.context < min_ctx:
            return False

        max_input_cost = requirements.get("max_input_cost_cny", float("inf"))
        if self.cost.input_cny > max_input_cost:
            return False

        max_output_cost = requirements.get("max_output_cost_cny", float("inf"))
        if self.cost.output_cny > max_output_cost:
            return False

        required_modalities = requirements.get("modalities_input", [])
        for mod in required_modalities:
            if mod not in self.modalities.input:
                return False

        exclude_status = requirements.get("status_exclude", [])
        if self.status in exclude_status:
            return False

        return True


# ── Sync Engine ────────────────────────────────────────────────────

class ModelsDevSync:
    """Sync engine for models.dev API data.

    Usage:
        sync = get_models_dev_sync()
        await sync.refresh()
        models = sync.query(reasoning=True, min_context=100000, max_input_cost_cny=5.0)
        best = sync.cheapest_for(requirements={"reasoning": True})
    """

    def __init__(self):
        self._providers: dict[str, dict] = {}
        self._models: dict[str, DevModel] = {}  # provider/model_id → DevModel
        self._last_refresh: float = 0.0
        self._etag: str = ""
        self._lock = threading.Lock()
        self._loaded = False
        self._load_cache()

    # ── Fetch ──────────────────────────────────────────────────────

    async def refresh(self, force: bool = False) -> int:
        """Fetch fresh data from models.dev API.

        Returns number of models loaded.
        """
        now = time.time()
        if not force and self._loaded and (now - self._last_refresh < REFRESH_INTERVAL):
            logger.debug("ModelsDevSync: cache still fresh")
            return len(self._models)

        try:
            headers = {"Accept": "application/json"}
            if self._etag:
                headers["If-None-Match"] = self._etag

            async with httpx.AsyncClient(timeout=FETCH_TIMEOUT) as client:
                resp = await client.get(MODELS_DEV_API, headers=headers)

                if resp.status_code == 304:
                    logger.info("ModelsDevSync: not modified (304)")
                    self._last_refresh = now
                    self._save_cache()
                    return len(self._models)

                if resp.status_code != 200:
                    logger.warning(f"ModelsDevSync: HTTP {resp.status_code}")
                    return len(self._models)

                # Check ETag
                etag = resp.headers.get("etag", "")
                if etag and etag == self._etag:
                    self._last_refresh = now
                    return len(self._models)
                self._etag = etag

                data = resp.json()
                count = self._parse(data)
                self._last_refresh = now
                self._loaded = True
                self._save_cache()
                logger.info(f"ModelsDevSync: loaded {count} models from {len(self._providers)} providers")
                return count

        except Exception as e:
            logger.warning(f"ModelsDevSync refresh: {e}")
            return len(self._models)

    def _parse(self, data: list[dict]) -> int:
        """Parse the models.dev API response into DevModel objects."""
        with self._lock:
            self._providers.clear()
            self._models.clear()
            count = 0

            for provider in data:
                pid = provider.get("id", "")
                pname = provider.get("name", "")
                if not pid:
                    continue

                self._providers[pid] = {
                    "name": pname,
                    "npm": provider.get("npm", ""),
                    "doc": provider.get("doc", ""),
                    "api": provider.get("api", ""),
                    "env": provider.get("env", []),
                }

                for model_data in provider.get("models", []):
                    mid = model_data.get("id", "")
                    if not mid:
                        continue

                    full_id = f"{pid}/{mid}"
                    cost_data = model_data.get("cost", {})
                    limit_data = model_data.get("limit", {})
                    mod_data = model_data.get("modalities", {})

                    model = DevModel(
                        id=full_id,
                        name=model_data.get("name", mid),
                        provider_id=pid,
                        provider_name=pname,
                        reasoning=model_data.get("reasoning", False),
                        tool_call=model_data.get("tool_call", False),
                        structured_output=model_data.get("structured_output", False),
                        temperature=model_data.get("temperature", False),
                        attachment=model_data.get("attachment", False),
                        open_weights=model_data.get("open_weights", False),
                        knowledge=model_data.get("knowledge", ""),
                        release_date=model_data.get("release_date", ""),
                        cost=ModelCost(
                            input_per_1M=cost_data.get("input", 0.0) or 0.0,
                            output_per_1M=cost_data.get("output", 0.0) or 0.0,
                            reasoning_per_1M=cost_data.get("reasoning", 0.0) or 0.0,
                            cache_read_per_1M=cost_data.get("cache_read", 0.0) or 0.0,
                            cache_write_per_1M=cost_data.get("cache_write", 0.0) or 0.0,
                            input_audio_per_1M=cost_data.get("input_audio", 0.0) or 0.0,
                            output_audio_per_1M=cost_data.get("output_audio", 0.0) or 0.0,
                        ),
                        limit=ModelLimit(
                            context=limit_data.get("context", 4096) or 4096,
                            max_input=limit_data.get("input", 4096) or 4096,
                            max_output=limit_data.get("output", 4096) or 4096,
                        ),
                        modalities=Modalities(
                            input=mod_data.get("input", ["text"]) or ["text"],
                            output=mod_data.get("output", ["text"]) or ["text"],
                        ),
                        status=model_data.get("status", ""),
                    )
                    self._models[full_id] = model
                    count += 1

            return count

    # ── Query ──────────────────────────────────────────────────────

    def query(self, **requirements) -> list[DevModel]:
        """Find models matching capability and cost requirements.

        Args:
            reasoning: bool
            tool_call: bool
            structured_output: bool
            attachment: bool
            open_weights: bool
            min_context: int
            max_input_cost_cny: float
            max_output_cost_cny: float
            modalities_input: list[str]
            status_exclude: list[str]
            provider: str | list[str]  # filter by provider ID
            tier: str
            sort_by: "cost" | "context" | "name"

        Returns:
            List of matching DevModel objects.
        """
        provider_filter = requirements.pop("provider", None)
        tier_filter = requirements.pop("tier", None)
        sort_by = requirements.pop("sort_by", "cost")

        # Build requirement dict
        req = {k: v for k, v in requirements.items() if v is not None}

        results = []
        for model in self._models.values():
            # Provider filter
            if provider_filter:
                if isinstance(provider_filter, str):
                    if model.provider_id != provider_filter:
                        continue
                elif model.provider_id not in provider_filter:
                    continue

            # Tier filter
            if tier_filter and model.tier != tier_filter:
                continue

            if model.satisfies(req):
                results.append(model)

        # Sort
        if sort_by == "cost":
            results.sort(key=lambda m: m.cost.avg_cny)
        elif sort_by == "context":
            results.sort(key=lambda m: -m.limit.context)
        elif sort_by == "name":
            results.sort(key=lambda m: m.name.lower())

        return results

    def cheapest_for(self, **requirements) -> DevModel | None:
        """Return the cheapest model satisfying the requirements."""
        results = self.query(**requirements, sort_by="cost")
        return results[0] if results else None

    def get_model(self, model_id: str) -> DevModel | None:
        """Get a specific model by its full ID (e.g. 'openai/gpt-5')."""
        return self._models.get(model_id)

    def get_provider_models(self, provider_id: str) -> list[DevModel]:
        """Get all models for a specific provider."""
        return [m for m in self._models.values() if m.provider_id == provider_id]

    def get_providers(self) -> list[str]:
        return list(self._providers.keys())

    def get_pricing_map(self) -> dict[str, tuple[float, float]]:
        """Return {model_id: (input_cny_per_1M, output_cny_per_1M)} for all models."""
        return {
            mid: (m.cost.input_cny, m.cost.output_cny)
            for mid, m in self._models.items()
            if not m.cost.is_free
        }

    def get_degradation_map(self) -> dict[str, str]:
        """Build degradation chain: pro→flash for each provider.

        Returns {expensive_model_id: cheaper_model_id}.
        """
        chain: dict[str, str] = {}
        for pid in self._providers:
            models = self.get_provider_models(pid)
            # Sort by cost
            models.sort(key=lambda m: m.cost.avg_cny)
            if len(models) >= 2:
                # Expensive → cheapest
                cheapest = models[0]
                for m in models[1:]:
                    chain[m.id] = cheapest.id
        return chain

    # ── Cache ──────────────────────────────────────────────────────

    def _save_cache(self):
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "last_refresh": self._last_refresh,
                "etag": self._etag,
                "providers": self._providers,
                "models": {
                    mid: {
                        "id": m.id,
                        "name": m.name,
                        "provider_id": m.provider_id,
                        "provider_name": m.provider_name,
                        "reasoning": m.reasoning,
                        "tool_call": m.tool_call,
                        "structured_output": m.structured_output,
                        "temperature": m.temperature,
                        "attachment": m.attachment,
                        "open_weights": m.open_weights,
                        "knowledge": m.knowledge,
                        "release_date": m.release_date,
                        "cost": {
                            "input": m.cost.input_per_1M,
                            "output": m.cost.output_per_1M,
                            "reasoning": m.cost.reasoning_per_1M,
                            "cache_read": m.cost.cache_read_per_1M,
                            "cache_write": m.cost.cache_write_per_1M,
                            "input_audio": m.cost.input_audio_per_1M,
                            "output_audio": m.cost.output_audio_per_1M,
                        },
                        "limit": {
                            "context": m.limit.context,
                            "input": m.limit.max_input,
                            "output": m.limit.max_output,
                        },
                        "modalities": {
                            "input": m.modalities.input,
                            "output": m.modalities.output,
                        },
                        "status": m.status,
                    }
                    for mid, m in self._models.items()
                },
            }
            CACHE_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception as e:
            logger.debug(f"ModelsDev cache save: {e}")

    def _load_cache(self):
        try:
            if not CACHE_FILE.exists():
                return
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            self._last_refresh = data.get("last_refresh", 0.0)
            self._etag = data.get("etag", "")
            self._providers = data.get("providers", {})

            models_data = data.get("models", {})
            for mid, md in models_data.items():
                cost = md.get("cost", {})
                limit = md.get("limit", {})
                mod = md.get("modalities", {})
                self._models[mid] = DevModel(
                    id=md.get("id", mid),
                    name=md.get("name", ""),
                    provider_id=md.get("provider_id", ""),
                    provider_name=md.get("provider_name", ""),
                    reasoning=md.get("reasoning", False),
                    tool_call=md.get("tool_call", False),
                    structured_output=md.get("structured_output", False),
                    temperature=md.get("temperature", False),
                    attachment=md.get("attachment", False),
                    open_weights=md.get("open_weights", False),
                    knowledge=md.get("knowledge", ""),
                    release_date=md.get("release_date", ""),
                    cost=ModelCost(
                        input_per_1M=cost.get("input", 0.0) or 0.0,
                        output_per_1M=cost.get("output", 0.0) or 0.0,
                        reasoning_per_1M=cost.get("reasoning", 0.0) or 0.0,
                        cache_read_per_1M=cost.get("cache_read", 0.0) or 0.0,
                        cache_write_per_1M=cost.get("cache_write", 0.0) or 0.0,
                        input_audio_per_1M=cost.get("input_audio", 0.0) or 0.0,
                        output_audio_per_1M=cost.get("output_audio", 0.0) or 0.0,
                    ),
                    limit=ModelLimit(
                        context=limit.get("context", 4096) or 4096,
                        max_input=limit.get("input", 4096) or 4096,
                        max_output=limit.get("output", 4096) or 4096,
                    ),
                    modalities=Modalities(
                        input=mod.get("input", ["text"]) or ["text"],
                        output=mod.get("output", ["text"]) or ["text"],
                    ),
                    status=md.get("status", ""),
                )

            self._loaded = True
            logger.info(
                f"ModelsDev cache loaded: {len(self._models)} models, "
                f"{len(self._providers)} providers")
        except Exception as e:
            logger.debug(f"ModelsDev cache load: {e}")

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        free_models = sum(1 for m in self._models.values() if m.cost.is_free)
        reasoning = sum(1 for m in self._models.values() if m.reasoning)
        vision = sum(1 for m in self._models.values() if m.modalities.supports_images)
        return {
            "providers": len(self._providers),
            "models": len(self._models),
            "free_models": free_models,
            "reasoning_models": reasoning,
            "vision_models": vision,
            "last_refresh": self._last_refresh,
            "cache_file": str(CACHE_FILE),
        }


# ── Singleton ──────────────────────────────────────────────────────

_models_dev_sync: ModelsDevSync | None = None


def get_models_dev_sync() -> ModelsDevSync:
    global _models_dev_sync
    if _models_dev_sync is None:
        _models_dev_sync = ModelsDevSync()
    return _models_dev_sync


def reset_models_dev_sync() -> None:
    global _models_dev_sync
    _models_dev_sync = None
