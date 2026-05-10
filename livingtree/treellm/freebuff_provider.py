"""FreeBuff Provider — free LLM via OpenRouter, ad-supported CLI model.

Real architecture (from CodebuffAI/codebuff analysis):
  - Freebuff runs on OpenRouter, not a standalone API
  - Models: DeepSeek V4 Pro (default), Kimi K2.6, Gemini 3.1 Flash Lite
  - Ads shown in terminal CLI, NOT injected into prompts
  - No public REST API — it's an npm CLI tool

LivingTree adaptation:
  - Use OpenRouter's free-tier models as a fallback provider
  - Track "ad impressions" locally — one impression per request
  - Show sponsor acknowledgment in LivingTree chat UI (not prompt injection)
  - Registered as fallback tier in model election (below paid, above local)
"""

from __future__ import annotations

import time
from typing import Any, Optional

import aiohttp
from loguru import logger

from .providers import Provider, ProviderResult, RATE_LIMIT_MAX_RETRIES

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

FREEBUFF_MODELS = {
    "nemotron-super": "nvidia/nemotron-3-super-120b-a12b:free",
    "nemotron-nano": "nvidia/nemotron-3-nano-30b-a3b:free",
    "nemotron-9b": "nvidia/nemotron-nano-9b-v2:free",
    "nemotron-vl": "nvidia/nemotron-nano-12b-v2-vl:free",
    "cobuddy": "baidu/cobuddy:free",
}

FREEBUFF_DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"


class FreeBuffProvider(Provider):
    """Provider wrapping OpenRouter free-tier models.

    Each request tracks an "ad impression" locally. A sponsor
    acknowledgment is returned alongside the response text so
    the LivingTree UI can display it.
    """

    def __init__(
        self,
        name: str = "freebuff",
        api_key: str = "",
        default_model: str = "",
    ):
        super().__init__(
            name=name,
            base_url=OPENROUTER_BASE,
            api_key=api_key or "",
            default_model=default_model or FREEBUFF_DEFAULT_MODEL,
        )
        self._total_requests: int = 0
        self._total_success: int = 0
        self._total_failures: int = 0
        self._total_tokens: int = 0
        self._ad_impressions: int = 0
        self._sponsor_message: str = (
            "⚡ 由 Codebuff/Freebuff 开源社区提供免费算力支持"
        )

    # ═══ Core ═══

    async def chat(
        self,
        messages: list[dict],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> ProviderResult:
        t0 = time.time()
        self._total_requests += 1

        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        result = await self._request_with_retry(payload, timeout=timeout, t0=t0)
        result.latency_ms = (time.time() - t0) * 1000

        if result.error:
            self._total_failures += 1
        else:
            self._total_success += 1
            self._total_tokens += result.tokens
            self._ad_impressions += 1
            result.text = result.text.rstrip() + "\n\n" + self._sponsor_message

        return result

    # ═══ Override request for OpenRouter headers ═══

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers["HTTP-Referer"] = "https://livingtree.ai"
        headers["X-Title"] = "LivingTree AI Agent"
        return headers

    async def ping(self) -> tuple[bool, str]:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"{OPENROUTER_BASE}/models",
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return resp.status == 200, ""
        except Exception as e:
            return False, str(e)

    # ═══ Stats ═══

    @property
    def stats(self) -> dict:
        return {
            "provider": self.name,
            "backend": "openrouter",
            "model": self.default_model,
            "total_requests": self._total_requests,
            "success_rate": round(self._total_success / max(1, self._total_requests), 3),
            "total_tokens": self._total_tokens,
            "ad_impressions": self._ad_impressions,
            "is_free": True,
            "ad_supported": True,
            "sponsor": "Codebuff/Freebuff 开源社区",
            "available_models": list(FREEBUFF_MODELS.keys()),
        }

    def available_models(self) -> dict[str, str]:
        return dict(FREEBUFF_MODELS)


def create_freebuff_provider(
    api_key: str = "",
    model: str = "",
) -> FreeBuffProvider:
    return FreeBuffProvider(
        name="freebuff",
        api_key=api_key,
        default_model=model or FREEBUFF_DEFAULT_MODEL,
    )
