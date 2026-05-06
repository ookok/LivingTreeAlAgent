"""DeepSeek Web Provider — chat.deepseek.com → OpenAI-compatible API.

Uses DeepSeek's internal chat API endpoints (the same ones the web UI calls).
No browser automation needed — pure HTTP with session tokens.

Internal endpoints:
  - Login: https://chat.deepseek.com/api/v0/users/login
  - Chat:  https://chat.deepseek.com/api/v0/chat/completion
  - Clear: https://chat.deepseek.com/api/v0/chat_session/clear

References:
  - CJackHwang/ds2api (Go implementation)
  - DeepSeek web client network traces
"""

from __future__ import annotations

import json
import time
from typing import AsyncIterator, Optional

from loguru import logger

from .base_provider import WebProvider, WebAccount, ProviderResult

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


DEEPSEEK_LOGIN_URL = "https://chat.deepseek.com/api/v0/users/login"
DEEPSEEK_CHAT_URL = "https://chat.deepseek.com/api/v0/chat/completion"
DEEPSEEK_CLEAR_URL = "https://chat.deepseek.com/api/v0/chat_session/clear"
DEEPSEEK_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"


class DeepSeekWebProvider(WebProvider):
    """DeepSeek chat.deepseek.com web → API provider.

    Usage:
        provider = DeepSeekWebProvider()
        account = WebAccount(email="user@email.com", password="pass")
        await provider.login(account)

        result = await provider.chat(
            [{"role": "user", "content": "环评是什么？"}],
            account,
        )
        print(result.text)
    """

    def __init__(self):
        super().__init__(name="deepseek-web", base_url="https://chat.deepseek.com")

    async def login(self, account: WebAccount) -> bool:
        """Login to DeepSeek web and get auth token."""
        if not HAS_AIOHTTP:
            logger.error("aiohttp required for DeepSeek web provider")
            return False

        payload = {"email": account.email, "password": account.password}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DEEPSEEK_LOGIN_URL,
                    json=payload,
                    headers={
                        "User-Agent": DEEPSEEK_USER_AGENT,
                        "Content-Type": "application/json",
                        "Origin": "https://chat.deepseek.com",
                        "Referer": "https://chat.deepseek.com/",
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        token = data.get("data", {}).get("biz_data", {}).get("token", "")
                        if token:
                            account.token = token
                            account.cookies = {k: v.value for k, v in resp.cookies.items()}
                            logger.info("DeepSeekWeb: login OK for %s", account.email[:20])
                            return True

                    logger.warning("DeepSeekWeb login: HTTP %d for %s", resp.status, account.email[:20])
                    return False
        except Exception as e:
            logger.warning("DeepSeekWeb login error: %s", e)
            return False

    async def chat(
        self, messages: list[dict], account: WebAccount,
        temperature: float = 0.7, max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> ProviderResult:
        result = ProviderResult(account_used=account.email)
        if not account.token:
            result.error = "Not logged in"
            return result

        payload = self._build_chat_payload(messages, temperature, max_tokens)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DEEPSEEK_CHAT_URL,
                    json=payload,
                    headers=self._build_headers(account),
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        choices = data.get("data", {}).get("biz_data", {}).get("choices", [])
                        if choices:
                            result.text = choices[0].get("message", {}).get("content", "")
                            result.model = data.get("data", {}).get("biz_data", {}).get("model", "deepseek")
                            result.finish_reason = choices[0].get("finish_reason", "stop")
                            return result

                    if resp.status == 401:
                        account.status = "expired"
                        result.error = "Token expired"
                        return result

                    result.error = f"HTTP {resp.status}"
                    return result

        except Exception as e:
            result.error = str(e)
            return result

    async def chat_stream(
        self, messages: list[dict], account: WebAccount,
        temperature: float = 0.7, max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> AsyncIterator[str]:
        if not account.token:
            yield ""
            return

        payload = self._build_chat_payload(messages, temperature, max_tokens)
        payload["stream"] = True

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DEEPSEEK_CHAT_URL,
                    json=payload,
                    headers=self._build_headers(account),
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status == 200:
                        async for line in resp.content:
                            text = line.decode("utf-8", errors="replace").strip()
                            if text.startswith("data: "):
                                data_str = text[6:]
                                if data_str == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                                except json.JSONDecodeError:
                                    pass
        except Exception as e:
            logger.debug("DeepSeekWeb stream error: %s", e)

    def _build_chat_payload(self, messages: list[dict], temperature: float, max_tokens: int) -> dict:
        return {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "model": "deepseek-chat",
            "stream": False,
        }

    def _build_headers(self, account: WebAccount) -> dict:
        return {
            "User-Agent": DEEPSEEK_USER_AGENT,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {account.token}",
            "Origin": "https://chat.deepseek.com",
            "Referer": "https://chat.deepseek.com/",
        }


# ═══ Claude Web Provider Template ═══

class ClaudeWebProvider(WebProvider):
    """Claude.ai web → API provider (template — needs Claude session extraction).

    Claude uses Anthropic's internal API with session cookies.
    Login flow: OAuth → session cookie → use cookie in API calls.
    """

    def __init__(self):
        super().__init__(name="claude-web", base_url="https://claude.ai")

    async def login(self, account: WebAccount) -> bool:
        logger.info("ClaudeWeb: login not yet implemented — needs browser OAuth")
        return False

    async def chat(self, messages, account, **kwargs) -> ProviderResult:
        return ProviderResult(error="Claude web provider not yet implemented")

    async def chat_stream(self, messages, account, **kwargs) -> AsyncIterator[str]:
        yield ""


# ═══ Gemini Web Provider Template ═══

class GeminiWebProvider(WebProvider):
    """Gemini (gemini.google.com) web → API provider template."""

    def __init__(self):
        super().__init__(name="gemini-web", base_url="https://gemini.google.com")

    async def login(self, account: WebAccount) -> bool:
        logger.info("GeminiWeb: login requires Google OAuth — use API key instead")
        return False

    async def chat(self, messages, account, **kwargs) -> ProviderResult:
        return ProviderResult(error="Gemini web provider not yet implemented")

    async def chat_stream(self, messages, account, **kwargs) -> AsyncIterator[str]:
        yield ""
