"""LayerConfig — 3-layer provider election with frontend-configurable settings.

Architecture:
  L0 VECTOR     → embedding/intent classification (BAAI/bge-large-zh-v1.5)
  L1 FAST       → fast response (deepseek-v4-flash, default for 80% queries)
  L2 REASONING  → deep thinking (deepseek-v4-pro, code/analysis/creative)

Startup: load config from .livingtree/layer_config.json (or use defaults).
Admin panel: /admin/layers → configure provider, api_key, model per layer.

Flow:
  classify(query) → embedding → FAST or REASONING
  FAST fails → retry FAST → fails → fallback to REASONING
  REASONING fails → fallback to FAST
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

CONFIG_PATH = Path(".livingtree/layer_config.json")


@dataclass
class LayerConfig:
    """Configuration for one layer."""
    provider: str = ""
    model: str = ""
    api_key: str = ""      # empty = use vault, "vault" = auto-load
    degraded: bool = False
    failures: int = 0
    successes: int = 0
    last_error: str = ""


class LayerConfigManager:
    """3-layer provider configuration with frontend settings support."""

    LAYERS = {0: "vector", 1: "fast", 2: "reasoning"}
    DEFAULTS = {
        0: LayerConfig(provider="siliconflow", model="BAAI/bge-large-zh-v1.5"),
        1: LayerConfig(provider="deepseek", model="deepseek-v4-flash"),
        2: LayerConfig(provider="deepseek", model="deepseek-v4-pro"),
    }

    _instance: Optional["LayerConfigManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._configs: dict[int, LayerConfig] = {l: LayerConfig() for l in range(3)}
        self._load()

    @classmethod
    def instance(cls) -> "LayerConfigManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = LayerConfigManager()
        return cls._instance

    # ═══ Config Persistence ════════════════════════════════════════

    def _load(self):
        try:
            if CONFIG_PATH.exists():
                data = json.loads(CONFIG_PATH.read_text())
                for l in range(3):
                    key = str(l)
                    if key in data:
                        d = data[key]
                        self._configs[l] = LayerConfig(
                            provider=d.get("provider", self.DEFAULTS[l].provider),
                            model=d.get("model", self.DEFAULTS[l].model),
                            api_key=d.get("api_key", ""),
                        )
                logger.info(f"LayerConfig loaded from {CONFIG_PATH}")
                return
        except Exception:
            pass
        self._configs = {l: LayerConfig(**dc.__dict__) for l, dc in self.DEFAULTS.items()}

    def _save(self):
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                str(l): {"provider": c.provider, "model": c.model, "api_key": c.api_key}
                for l, c in self._configs.items()
            }
            CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"LayerConfig save: {e}")

    # ═══ Getters ═══════════════════════════════════════════════════

    def get_provider(self, layer: int) -> tuple[str, str]:
        """Get (provider_name, model) for a layer."""
        c = self._configs.get(layer, self.DEFAULTS[layer])
        return c.provider or self.DEFAULTS[layer].provider, c.model or self.DEFAULTS[layer].model

    def get_api_key(self, layer: int) -> str:
        """Get API key for a layer. Tries explicit key → vault → env."""
        c = self._configs.get(layer)
        if c and c.api_key and c.api_key != "vault":
            return c.api_key
        try:
            from livingtree.config.secrets import get_secret_vault
            vault = get_secret_vault()
            key_map = {0: "siliconflow_api_key", 1: "deepseek_api_key", 2: "deepseek_api_key"}
            return vault._cache.get(key_map.get(layer, ""), "")
        except Exception:
            pass
        return ""

    def get_all(self) -> dict:
        """Get all layer configs for frontend display."""
        return {
            self.LAYERS[l]: {
                "provider": c.provider, "model": c.model,
                "api_key_set": bool(c.api_key),
                "degraded": c.degraded, "failures": c.failures,
                "successes": c.successes, "last_error": c.last_error[:80],
            }
            for l, c in self._configs.items()
        }

    # ═══ Setters (for frontend API) ════════════════════════════════

    def set_layer(self, layer: int, provider: str = "", model: str = "", api_key: str = ""):
        """Update layer config from frontend and persist."""
        if layer not in self._configs:
            raise ValueError(f"Invalid layer: {layer}")
        c = self._configs[layer]
        if provider:
            c.provider = provider
        if model:
            c.model = model
        if api_key:
            c.api_key = api_key
        c.degraded = False
        c.failures = 0
        self._save()
        logger.info(f"LayerConfig L{layer} ({self.LAYERS[layer]}): {c.provider}/{c.model}")
        return self.get_all()

    # ═══ Health ════════════════════════════════════════════════════

    def mark_failure(self, layer: int, error: str = ""):
        c = self._configs.get(layer)
        if c:
            c.failures += 1
            c.last_error = error
            if c.failures >= 2:
                c.degraded = True

    def mark_success(self, layer: int):
        c = self._configs.get(layer)
        if c:
            c.successes += 1
            if c.failures > 0:
                c.failures = max(0, c.failures - 1)
            if c.failures < 2:
                c.degraded = False

    def is_degraded(self, layer: int) -> bool:
        c = self._configs.get(layer)
        return c.degraded if c else False

    # ═══ Intent Classification ════════════════════════════════════

    def classify(self, query: str) -> int:
        """Classify intent: returns 1 (FAST) or 2 (REASONING)."""
        # Embedding-based classification
        emb = self._get_embedding(query)
        if emb:
            fast_proto = self._get_embedding("general chat question answer help")
            reas_proto = self._get_embedding("code debug analyze reason implement fix write create generate")
            if fast_proto and reas_proto:
                sim_fast = self._cosine(emb, fast_proto)
                sim_reas = self._cosine(emb, reas_proto)
                return 2 if sim_reas > sim_fast else 1

        # Keyword fallback
        q = query.lower()
        reasoning_kw = ["fix", "debug", "implement", "analyze", "code", "refactor",
                       "修复", "调试", "实现", "分析", "优化", "代码", "重构", "排查"]
        for kw in reasoning_kw:
            if kw in q:
                return 2
        return 1

    # ═══ Embedding ═════════════════════════════════════════════════

    def _get_embedding(self, text: str) -> list[float] | None:
        """Tier 1: SiliconFlow API, Tier 2: hash-based fallback."""
        emb = self._embed_api(text)
        if emb:
            return emb
        return self._embed_hash(text)

    def _embed_api(self, text: str) -> list[float] | None:
        try:
            import httpx
            key = self.get_api_key(0)
            if not key:
                return None
            resp = httpx.post(
                "https://api.siliconflow.cn/v1/embeddings",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": "BAAI/bge-large-zh-v1.5", "input": text},
                timeout=10.0,
            )
            if resp.status_code == 200:
                return resp.json()["data"][0]["embedding"]
        except Exception:
            pass
        return None

    def _embed_hash(self, text: str) -> list[float]:
        try:
            from ..dna.task_vector_geometry import text_to_embedding
            return text_to_embedding(text)
        except Exception:
            return [0.0] * 128

    @staticmethod
    def _cosine(a, b) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = (sum(x * x for x in a) ** 0.5)
        nb = (sum(y * y for y in b) ** 0.5)
        return dot / (na * nb) if na and nb else 0.0


# ═══ Singleton ═══

def get_layer_config() -> LayerConfigManager:
    return LayerConfigManager.instance()
