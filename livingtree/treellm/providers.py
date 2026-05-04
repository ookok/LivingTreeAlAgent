"""TreeLLM Providers — Direct HTTP implementations for each LLM backend.

No dependency on LiteLLM. Pure aiohttp + json. Each provider knows:
- Its endpoint URL
- How to format messages
- How to parse responses
- How to stream

Supports: DeepSeek, LongCat, OpenAI-compatible, opencode-serve.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import aiohttp


@dataclass
class ProviderResult:
    text: str = ""
    tokens: int = 0
    reasoning: str = ""
    model: str = ""
    latency_ms: float = 0.0
    error: str = ""

    @staticmethod
    def empty(error: str = "") -> "ProviderResult":
        return ProviderResult(error=error)


class Provider:
    """Base class for all LLM providers."""

    def __init__(self, name: str, base_url: str, api_key: str = "",
                 default_model: str = ""):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model

    async def ping(self) -> tuple[bool, str]:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{self.base_url}/chat/completions",
                    json={"model": self.default_model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return resp.status == 200, ""
        except Exception as e:
            return False, str(e)

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
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        return ProviderResult(error=f"HTTP {resp.status}: {body[:200]}",
                                              latency_ms=(time.monotonic() - t0) * 1000)
                    data = await resp.json()
                    choice = data["choices"][0]
                    msg = choice.get("message", {})
                    usage = data.get("usage", {})
                    return ProviderResult(
                        text=msg.get("content", ""),
                        reasoning=msg.get("reasoning_content", ""),
                        tokens=usage.get("total_tokens", 0),
                        model=data.get("model", model or self.default_model),
                        latency_ms=(time.monotonic() - t0) * 1000,
                    )
        except Exception as e:
            return ProviderResult(error=str(e), latency_ms=(time.monotonic() - t0) * 1000)

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


class OpenAILikeProvider(Provider):
    def __init__(self, name: str, base_url: str, api_key: str,
                 default_model: str = "gpt-4o-mini"):
        super().__init__(name=name, base_url=base_url, api_key=api_key,
                         default_model=default_model)


def create_deepseek_provider(api_key: str) -> DeepSeekProvider:
    return DeepSeekProvider(api_key=api_key)


def create_longcat_provider(api_key: str, model: str = "LongCat-Flash-Lite") -> LongCatProvider:
    return LongCatProvider(api_key=api_key, default_model=model)
