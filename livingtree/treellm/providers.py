"""TreeLLM Providers — Direct HTTP implementations for each LLM backend.

No dependency on LiteLLM. Pure aiohttp + json. Each provider knows:
- Its endpoint URL
- How to format messages
- How to parse responses
- How to stream

Supports: DeepSeek, LongCat, OpenAI-compatible, opencode-serve.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import aiohttp

# Rate-limit configuration
RATE_LIMIT_MAX_RETRIES = 3
RATE_LIMIT_BASE_DELAY = 2.0  # seconds
RATE_LIMIT_MAX_DELAY = 30.0  # seconds


@dataclass
class ProviderResult:
    text: str = ""
    tokens: int = 0
    prompt_tokens: int = 0
    cache_hit_tokens: int = 0
    reasoning: str = ""
    model: str = ""
    latency_ms: float = 0.0
    error: str = ""
    rate_limited: bool = False

    @staticmethod
    def empty(error: str = "") -> "ProviderResult":
        return ProviderResult(error=error)


class Provider:
    """Base class for all LLM providers with rate-limit resilience."""

    def __init__(self, name: str, base_url: str, api_key: str = "",
                 default_model: str = ""):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self._rate_limit_count = 0
        self._last_rate_limit = 0.0

    async def ping(self) -> tuple[bool, str]:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{self.base_url}/chat/completions",
                    json={"model": self.default_model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return True, ""  # Any HTTP response = server alive; errors caught by except
        except Exception as e:
            return False, str(e)

    async def _request_with_retry(
        self, payload: dict, timeout: int = 120, t0: float = 0.0
    ) -> ProviderResult:
        """HTTP request with exponential backoff on 429 rate limits.

        Circuit breaker: checks before call, reports success/failure after.
        """
        # Circuit breaker guard
        try:
            from .circuit_breaker import get_circuit_breaker
            breaker = get_circuit_breaker()
            if not breaker.before_call(self.name):
                return ProviderResult(
                    text="", error=f"Circuit breaker OPEN for {self.name}",
                    tokens=0, prompt_tokens=0,
                )
        except Exception:
            pass

        last_error = ""
        t_start = time.time()
        for attempt in range(RATE_LIMIT_MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=self._headers(),
                        timeout=aiohttp.ClientTimeout(total=timeout),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            choice = data["choices"][0]
                            msg = choice.get("message", {})
                            usage = data.get("usage", {})
                            return ProviderResult(
                                text=msg.get("content", ""),
                                reasoning=msg.get("reasoning_content", ""),
                                tokens=usage.get("total_tokens", 0),
                                prompt_tokens=usage.get("prompt_tokens", 0),
                                cache_hit_tokens=usage.get("prompt_cache_hit_tokens", 0)
                                    or usage.get("prompt_tokens_details", {}).get("cached_tokens", 0),
                                model=data.get("model", payload.get("model", self.default_model)),
                                latency_ms=(time.monotonic() - t0) * 1000,
                            )
                        elif resp.status == 429:
                            self._rate_limit_count += 1
                            self._last_rate_limit = time.time()
                            body = await resp.text()
                            last_error = f"HTTP 429 (rate limited): {body[:100]}"
                            if attempt < RATE_LIMIT_MAX_RETRIES - 1:
                                delay = min(RATE_LIMIT_BASE_DELAY * (2 ** attempt), RATE_LIMIT_MAX_DELAY)
                                await asyncio.sleep(delay)
                                continue
                            return ProviderResult(error=last_error, rate_limited=True,
                                                   latency_ms=(time.monotonic() - t0) * 1000)
                        else:
                            body = await resp.text()
                            return ProviderResult(error=f"HTTP {resp.status}: {body[:200]}",
                                                   latency_ms=(time.monotonic() - t0) * 1000)
            except Exception as e:
                last_error = str(e)
                if attempt < RATE_LIMIT_MAX_RETRIES - 1:
                    await asyncio.sleep(RATE_LIMIT_BASE_DELAY)
                    continue
        return ProviderResult(error=last_error, latency_ms=(time.monotonic() - t0) * 1000)

    async def chat(self, messages: list[dict], temperature: float = 0.7,
                   max_tokens: int = 4096, timeout: int = 120,
                   model: str = "", **kwargs) -> ProviderResult:
        t0 = time.monotonic()
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        result = await self._request_with_retry(payload, timeout, t0)
        # Circuit breaker: report success or failure
        try:
            from .circuit_breaker import get_circuit_breaker
            breaker = get_circuit_breaker()
            if result.error:
                breaker.on_failure(self.name, result.error)
            else:
                breaker.on_success(self.name, result.latency_ms)
        except Exception:
            pass
        # Token Accountant: record serving layer allocation (prefill + decode)
        try:
            from ..api.token_accountant import get_token_accountant, AllocationLayer
            accountant = get_token_accountant()
            accountant.record_allocation(
                layer=AllocationLayer.SERVING,
                action="prefill" if result.prompt_tokens > result.tokens / 2 else "decode",
                tokens_spent=result.tokens,
                actual_benefit=0.8 if not result.error else 0.0,
                latency_ms=result.latency_ms,
            )
        except Exception:
            pass
        return result

    async def stream(self, messages: list[dict], temperature: float = 0.3,
                     max_tokens: int = 4096, timeout: int = 120,
                     model: str = "", **kwargs) -> AsyncIterator[str]:
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs,
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status == 429:
                        yield f"\n[NVIDIA rate limited — backoff triggered]"
                        return
                    if resp.status != 200:
                        yield f"\n[HTTP {resp.status}]"
                        return
                    buf = b""
                    async for chunk in resp.content.iter_any():
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            t = line.decode(errors="replace").strip()
                            if not t.startswith("data: "):
                                continue
                            d = t[6:]
                            if d == "[DONE]":
                                return
                            try:
                                data = json.loads(d)
                                token = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if token:
                                    yield token
                            except Exception:
                                continue
        except Exception as e:
            yield f"\n[Stream error: {e}]"

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h


class DeepSeekProvider(Provider):
    def __init__(self, api_key: str):
        super().__init__(
            name="deepseek",
            base_url="https://api.deepseek.com/v1",
            api_key=api_key,
            default_model="deepseek-v4-flash",
        )

    async def chat_pro(self, messages: list[dict], temperature: float = 0.7,
                        max_tokens: int = 8192, timeout: int = 120) -> ProviderResult:
        return await self.chat(messages, temperature=temperature,
                               max_tokens=max_tokens, timeout=timeout,
                               model="deepseek-v4-pro")


class LongCatProvider(Provider):
    def __init__(self, api_key: str, default_model: str = "LongCat-Flash-Lite"):
        super().__init__(
            name="longcat",
            base_url="https://api.longcat.chat/openai/v1",
            api_key=api_key,
            default_model=default_model,
        )


class NvidiaProvider(Provider):
    """NVIDIA NIM — OpenAI-compatible API with NVAPI keys.

    Free tier models: deepseek-ai/deepseek-r1, nvidia/llama-3.1-nemotron-ultra-253b-v1,
    meta/llama-3.3-70b-instruct, qwen/qwen2.5-7b-instruct.
    """
    def __init__(self, api_key: str, default_model: str = "deepseek-ai/deepseek-r1"):
        super().__init__(
            name="nvidia",
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
            default_model=default_model,
        )


class OpenAILikeProvider(Provider):
    def __init__(self, name: str, base_url: str, api_key: str,
                 default_model: str = "gpt-4o-mini"):
        super().__init__(name=name, base_url=base_url, api_key=api_key,
                         default_model=default_model)


class KiroProvider(Provider):
    """Kiro AI — free Claude 4.5 + GLM-5 + MiniMax via OAuth.

    Token obtained via AWS Builder ID / Google / GitHub OAuth.
    """
    def __init__(self, api_key: str = "", default_model: str = "claude-sonnet-4.5"):
        super().__init__(
            name="kiro",
            base_url="https://api.kiro.ai/v1",
            api_key=api_key,
            default_model=default_model,
        )


class OpenCodeFreeProvider(Provider):
    """OpenCode Free — no-auth passthrough proxy.

    Models auto-fetched from opencode.ai/zen/v1/models.
    """
    def __init__(self, api_key: str = "", default_model: str = "claude-sonnet-4.5"):
        super().__init__(
            name="opencode-free",
            base_url="https://opencode.ai/zen/v1",
            api_key=api_key or "opencode-free",
            default_model=default_model,
        )


def create_deepseek_provider(api_key: str) -> DeepSeekProvider:
    return DeepSeekProvider(api_key=api_key)


def create_longcat_provider(api_key: str, model: str = "LongCat-Flash-Lite") -> LongCatProvider:
    return LongCatProvider(api_key=api_key, default_model=model)


def create_nvidia_provider(api_key: str, model: str = "deepseek-ai/deepseek-r1") -> NvidiaProvider:
    return NvidiaProvider(api_key=api_key, default_model=model)


def create_kiro_provider(api_key: str = "") -> KiroProvider:
    return KiroProvider(api_key=api_key)


def create_opencode_free_provider(api_key: str = "") -> OpenCodeFreeProvider:
    return OpenCodeFreeProvider(api_key=api_key)


def create_modelscope_provider(api_key: str, model: str = "Qwen/Qwen3-8B") -> OpenAILikeProvider:
    """Create a ModelScope provider — OpenAI-compatible API.

    ModelScope (modelscope.cn) provides free inference endpoints for open-source models
    including Qwen, DeepSeek, Llama, and more.

    Common models:
    - Qwen/Qwen3-8B (flash)
    - Qwen/Qwen2.5-72B-Instruct (chat)
    - deepseek-ai/DeepSeek-V3 (pro)
    - deepseek-ai/DeepSeek-R1 (reasoning)
    - Qwen/Qwen2.5-7B-Instruct (small)
    """
    return OpenAILikeProvider(
        name="modelscope",
        base_url="https://api-inference.modelscope.cn/v1",
        api_key=api_key,
        default_model=model,
    )


def create_bailing_provider(api_key: str, model: str = "Baichuan4-Turbo") -> OpenAILikeProvider:
    """Create an Ant Group BaiLing (百灵) provider — OpenAI-compatible API.

    Ant Group BaiLing (api.baichuan-ai.com) provides enterprise-grade LLM access
    including Baichuan4, Baichuan4-Turbo, Baichuan4-Air, and Baichuan3-Turbo.

    Common models:
    - Baichuan4-Turbo (flash — fast, lightweight)
    - Baichuan4 (chat/pro — flagship, balanced)
    - Baichuan4-Air (small — cheapest, simple tasks)
    """
    return OpenAILikeProvider(
        name="bailing",
        base_url="https://api.baichuan-ai.com/v1",
        api_key=api_key,
        default_model=model,
    )


def create_stepfun_provider(api_key: str, model: str = "step-1-flash") -> OpenAILikeProvider:
    """Create a StepFun (阶跃星辰) provider — OpenAI-compatible API.

    StepFun (stepfun.com) provides Step-1 and Step-2 series models with
    strong reasoning, long context (16K), and vision capabilities.

    Common models:
    - step-1-flash (flash — fast, lightweight)
    - step-1-8k (chat — balanced, 8K context)
    - step-2-16k (pro — powerful, 16K context)
    """
    return OpenAILikeProvider(
        name="stepfun",
        base_url="https://api.stepfun.com/v1",
        api_key=api_key,
        default_model=model,
    )


def create_internlm_provider(api_key: str, model: str = "internlm2.5-7b-chat") -> OpenAILikeProvider:
    """Create an InternLM (书生) provider — OpenAI-compatible API.

    Shanghai AI Lab's InternLM (intern-ai.org.cn) offers InternLM2.5/3 models
    with strong Chinese reasoning, long context, and tool-use capabilities.

    Common models:
    - internlm2.5-7b-chat (flash — fast, lightweight)
    - internlm2.5-20b-chat (chat — balanced)
    - internlm3-latest (pro — flagship, strongest reasoning)
    """
    return OpenAILikeProvider(
        name="internlm",
        base_url="https://api.intern-ai.org.cn/v1",
        api_key=api_key,
        default_model=model,
    )


def create_ollama_provider(base_url: str = "http://localhost:11434/v1", default_model: str = "qwen3.5:4b") -> OpenAILikeProvider:
    """Create an Ollama provider — OpenAI-compatible API.

    Ollama (ollama.com) is a local LLM server that manages GGUF models.
    It provides an OpenAI-compatible API at /v1 endpoint.

    Common models:
    - qwen3.5:0.8b (flash — fastest, lightweight)
    - qwen2.5:1.5b (small — balanced speed/quality)
    - qwen3.5:4b (chat — daily usage)
    - qwen3.5:9b (pro — complex tasks)
    - qwen3.6:35b-a3b (moe — strongest reasoning)
    """
    return OpenAILikeProvider(
        name="ollama",
        base_url=base_url,
        api_key="",
        default_model=default_model,
    )


def create_sensetime_provider(api_key: str, model: str = "SenseChat-Turbo") -> OpenAILikeProvider:
    """Create a SenseTime (商汤) provider — OpenAI-compatible API.

    SenseTime (sensetime.com) offers SenseChat series with strong
    Chinese language understanding and multimodal capabilities.
    Limited-time free access available.

    Common models:
    - SenseChat-Turbo (fast, general purpose)
    - SenseChat-Pro (advanced reasoning)
    """
    return OpenAILikeProvider(
        name="sensetime",
        base_url="https://api.sensetime.com/v1",
        api_key=api_key,
        default_model=model,
    )


def create_openrouter_provider(api_key: str, model: str = "") -> OpenAILikeProvider:
    """Create an OpenRouter provider — 300+ models via unified API.

    OpenRouter (openrouter.ai) provides a single OpenAI-compatible API
    to access 300+ models from all major providers (DeepSeek, Claude,
    GPT, Gemini, Qwen, Kimi, etc.) with automatic fallback and the
    ability to use free-tier models.

    Free models (no cost, rate-limited):
    - deepseek/deepseek-v4-flash:free
    - moonshotai/kimi-k2.6:free
    - google/gemini-2.5-flash-lite:free

    Key: sk-or-v1-...
    """
    return OpenAILikeProvider(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_model=model or "deepseek/deepseek-v4-flash:free",
    )
