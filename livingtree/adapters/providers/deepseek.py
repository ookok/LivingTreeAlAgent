"""
DeepSeek Provider — OpenAI-Compat + Thinking Mode
===================================================

Models:
- deepseek-chat (standard)
- deepseek-reasoner (thinking mode — returns reasoning_content)
"""

import json
import time
from typing import Optional, Dict, Any, AsyncGenerator

from .ollama import ProviderBase, ChatCompletionRequest, ChatCompletionResponse


class DeepSeekProvider(ProviderBase):
    """DeepSeek API Provider (OpenAI-compatible endpoint)"""

    MODELS = {
        "deepseek-chat": {"max_tokens": 8192, "thinking": False},
        "deepseek-reasoner": {"max_tokens": 8192, "thinking": True},
    }

    def __init__(self, api_key: str = "", base_url: str = "https://api.deepseek.com",
                 default_model: str = "deepseek-chat"):
        super().__init__(base_url=base_url, api_key=api_key)
        self.default_model = default_model

    def chat_sync(self, req: ChatCompletionRequest,
                  enable_thinking: bool = False) -> ChatCompletionResponse:
        """同步调用 DeepSeek API"""
        import requests

        model = req.model or self.default_model
        start = time.time()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        messages = []
        for msg in req.messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }

        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload, headers=headers, timeout=120
            )
            data = resp.json()

            if "error" in data:
                return ChatCompletionResponse(
                    success=False,
                    error=data["error"].get("message", str(data["error"])),
                )

            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})

            content = msg.get("content", "") or ""
            reasoning = msg.get("reasoning_content", "")

            if reasoning:
                content = f"[thinking]\n{reasoning}\n[/thinking]\n\n{content}"

            usage = data.get("usage", {})
            return ChatCompletionResponse(
                content=content,
                model=model,
                tokens_input=usage.get("prompt_tokens", 0),
                tokens_output=usage.get("completion_tokens", 0),
                success=True,
            )
        except Exception as e:
            return ChatCompletionResponse(success=False, error=str(e))

    async def chat(self, req: ChatCompletionRequest,
                   enable_thinking: bool = False) -> ChatCompletionResponse:
        import aiohttp

        model = req.model or self.default_model
        start = time.time()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        messages = []
        for msg in req.messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    data = await resp.json()

                    if "error" in data:
                        return ChatCompletionResponse(
                            success=False,
                            error=data["error"].get("message", str(data["error"])),
                        )

                    choice = data.get("choices", [{}])[0]
                    msg = choice.get("message", {})

                    content = msg.get("content", "") or ""
                    reasoning = msg.get("reasoning_content", "")

                    if reasoning:
                        content = f"[thinking]\n{reasoning}\n[/thinking]\n\n{content}"

                    usage = data.get("usage", {})
                    return ChatCompletionResponse(
                        content=content,
                        model=model,
                        tokens_input=usage.get("prompt_tokens", 0),
                        tokens_output=usage.get("completion_tokens", 0),
                        success=True,
                    )
        except Exception as e:
            return ChatCompletionResponse(success=False, error=str(e))

    async def stream_chat(self, req: ChatCompletionRequest,
                          enable_thinking: bool = False) -> AsyncGenerator[str, None]:
        import aiohttp

        model = req.model or self.default_model

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        messages = []
        for msg in req.messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": True,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    async for line in resp.content:
                        line_str = line.decode("utf-8").strip()
                        if not line_str.startswith("data: "):
                            continue
                        data_str = line_str[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "") or ""
                            reasoning = delta.get("reasoning_content", "") or ""
                            if reasoning:
                                yield f"[thinking] {reasoning} "
                            if content:
                                yield content
                        except Exception:
                            continue
        except Exception as e:
            yield f"[Error: {e}]"


def create_deepseek_provider(config=None) -> DeepSeekProvider:
    if config is None:
        from livingtree.infrastructure.config import get_config
        config = get_config()

    return DeepSeekProvider(
        api_key=config.deepseek.api_key,
        base_url=config.deepseek.base_url,
        default_model=config.deepseek.default_model,
    )


__all__ = ["DeepSeekProvider", "create_deepseek_provider"]
