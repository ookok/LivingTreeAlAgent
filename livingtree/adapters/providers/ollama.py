"""
LivingTree Provider 适配器
==========================

Ollama / OpenAI / vLLM 等多模型后端适配。
"""

from typing import Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import json


class ProviderType(Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    VLLM = "vllm"
    CUSTOM = "custom"


@dataclass
class ChatCompletionRequest:
    model: str = ""
    messages: list = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.9
    stream: bool = False


@dataclass
class ChatCompletionResponse:
    content: str = ""
    model: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    finish_reason: str = "stop"
    success: bool = True
    error: str = ""


class ProviderBase:
    def __init__(self, base_url: str = "", api_key: str = ""):
        self.base_url = base_url
        self.api_key = api_key

    async def chat(self, req: ChatCompletionRequest) -> ChatCompletionResponse:
        raise NotImplementedError

    def chat_sync(self, req: ChatCompletionRequest) -> ChatCompletionResponse:
        raise NotImplementedError


class OllamaProvider(ProviderBase):
    def __init__(self, base_url: str = "http://localhost:11434"):
        super().__init__(base_url=base_url)

    def chat_sync(self, req: ChatCompletionRequest) -> ChatCompletionResponse:
        import requests
        url = f"{self.base_url}/api/chat"

        try:
            payload = {
                "model": req.model or "qwen2.5:7b",
                "messages": req.messages,
                "stream": False,
                "options": {
                    "temperature": req.temperature,
                    "num_predict": req.max_tokens,
                },
            }
            resp = requests.post(url, json=payload, timeout=120)
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return ChatCompletionResponse(
                content=content,
                model=req.model,
                tokens_input=data.get("prompt_eval_count", 0),
                tokens_output=data.get("eval_count", 0),
                success=True,
            )
        except Exception as e:
            return ChatCompletionResponse(
                success=False,
                error=str(e),
            )

    async def chat(self, req: ChatCompletionRequest) -> ChatCompletionResponse:
        import aiohttp
        url = f"{self.base_url}/api/chat"

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": req.model or "qwen2.5:7b",
                    "messages": req.messages,
                    "stream": False,
                    "options": {
                        "temperature": req.temperature,
                        "num_predict": req.max_tokens,
                    },
                }
                async with session.post(url, json=payload,
                                        timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    data = await resp.json()
                    content = data.get("message", {}).get("content", "")
                    return ChatCompletionResponse(
                        content=content,
                        model=req.model,
                        tokens_input=data.get("prompt_eval_count", 0),
                        tokens_output=data.get("eval_count", 0),
                        success=True,
                    )
        except Exception as e:
            return ChatCompletionResponse(success=False, error=str(e))

    async def stream_chat(self, req: ChatCompletionRequest) -> AsyncGenerator[str, None]:
        import aiohttp
        url = f"{self.base_url}/api/chat"

        async with aiohttp.ClientSession() as session:
            payload = {
                "model": req.model,
                "messages": req.messages,
                "stream": True,
                "options": {
                    "temperature": req.temperature,
                    "num_predict": req.max_tokens,
                },
            }
            async with session.post(url, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=120)) as resp:
                async for line in resp.content:
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except Exception:
                        continue


class OpenAICompatibleProvider(ProviderBase):
    """OpenAI API 兼容格式的 provider"""

    def chat_sync(self, req: ChatCompletionRequest) -> ChatCompletionResponse:
        import requests
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": req.model,
            "messages": req.messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "top_p": req.top_p,
        }

        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload, headers=headers, timeout=120
            )
            data = resp.json()
            choice = data.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})
            return ChatCompletionResponse(
                content=content,
                model=req.model,
                tokens_input=usage.get("prompt_tokens", 0),
                tokens_output=usage.get("completion_tokens", 0),
                success=True,
            )
        except Exception as e:
            return ChatCompletionResponse(success=False, error=str(e))


# ── Provider Registry ──────────────────────────────────────────────

class ProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, ProviderBase] = {}

    def register(self, name: str, provider: ProviderBase):
        self._providers[name] = provider

    def get(self, name: str) -> Optional[ProviderBase]:
        return self._providers.get(name)

    def get_ollama(self) -> Optional[OllamaProvider]:
        for provider in self._providers.values():
            if isinstance(provider, OllamaProvider):
                return provider
        return None


__all__ = [
    "ProviderBase",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "ProviderRegistry",
    "ProviderType",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
]
