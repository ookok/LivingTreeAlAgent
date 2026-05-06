"""Extended Web Providers — Claude, Gemini, Kimi.

Auth strategies per platform:
  Claude: cookie-based (user extracts session cookie from browser once)
  Gemini: API key (free tier available, no web scraping needed)
  Kimi:   phone/wechat login → session token

Scinet requirement:
  Claude (claude.ai)    — YES, hosted overseas, needs acceleration
  Gemini (gemini.com)   — YES, hosted overseas, needs acceleration  
  Kimi (moonshot.cn)    — NO, Chinese platform, direct access
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


# ═══ Claude Web Provider ═══

class ClaudeWebProvider(WebProvider):
    """Claude.ai web → API (cookie-based auth).

    Setup:
      1. Open claude.ai in browser, login
      2. F12 → Application → Cookies → copy 'sessionKey' value
      3. Register: provider uses cookie as account 'token'
    
    Uses Anthropic's internal organization API endpoints.
    """

    CLAUDE_API = "https://claude.ai/api/organizations"
    CLAUDE_CHAT = "https://claude.ai/api/append_message"

    def __init__(self):
        super().__init__(name="claude-web", base_url="https://claude.ai")

    async def login(self, account: WebAccount) -> bool:
        """Verify the stored cookie is still valid."""
        if not account.token:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.CLAUDE_API,
                    headers=self._headers(account),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list) and len(data) > 0:
                            org_id = data[0].get("uuid", "")
                            account.cookies["org_id"] = org_id
                            logger.info("ClaudeWeb: cookie valid, org=%s", org_id[:12])
                            return True
                    logger.warning("ClaudeWeb: cookie invalid (HTTP %d)", resp.status)
                    return False
        except Exception as e:
            logger.warning("ClaudeWeb login: %s", e)
            return False

    async def chat(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0) -> ProviderResult:
        result = ProviderResult(account_used=account.email or "claude-cookie")
        if not account.token:
            result.error = "No session cookie — extract from browser F12 → Cookies → sessionKey"
            return result

        org_id = account.cookies.get("org_id", "")
        if not org_id:
            ok = await self.login(account)
            if not ok:
                result.error = "Cookie expired"
                return result
            org_id = account.cookies.get("org_id", "")

        # Convert to Claude's message format
        prompt = self._format_messages(messages)

        payload = {
            "completion": {
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens_to_sample": max_tokens,
            },
            "organization_uuid": org_id,
            "conversation_uuid": account.cookies.get("conversation_id", ""),
            "text": messages[-1]["content"] if messages else "",
            "attachments": [],
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.CLAUDE_CHAT,
                    json=payload,
                    headers=self._headers(account),
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result.text = data.get("completion", "")
                        return result
                    result.error = f"HTTP {resp.status}"
                    return result
        except Exception as e:
            result.error = str(e)
            return result

    async def chat_stream(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0):
        result = await self.chat(messages, account, temperature, max_tokens, timeout)
        yield result.text

    def supports_tools(self) -> bool:
        return True

    def model_name(self) -> str:
        return "claude-sonnet-4-20250514"

    def _headers(self, account: WebAccount) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0",
            "Cookie": f"sessionKey={account.token}",
            "Content-Type": "application/json",
            "Origin": "https://claude.ai",
            "Referer": "https://claude.ai/",
        }

    @staticmethod
    def _format_messages(messages: list[dict]) -> str:
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            else:
                parts.append(f"Human: {content}")
        return "\n\n".join(parts) + "\n\nAssistant:"


# ═══ Gemini Web Provider ═══

class GeminiWebProvider(WebProvider):
    """Gemini → API via free API key (no web scraping needed).

    Gemini has a generous free tier:
      - gemini-2.5-flash: 1500 req/day free
      - No credit card required
      - Get key at: https://aistudio.google.com/apikey

    This provider uses the official API (not web scraping).
    No scinet needed if using API endpoint directly.
    """

    GEMINI_API = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self):
        super().__init__(name="gemini-web", base_url=self.GEMINI_API)

    async def login(self, account: WebAccount) -> bool:
        """Verify API key by listing models."""
        if not account.token:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.GEMINI_API}/models?key={account.token}",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def chat(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0) -> ProviderResult:
        result = ProviderResult(account_used="gemini-api-key")

        # Convert to Gemini format
        contents = []
        system_instruction = None
        for msg in messages:
            role = "user" if msg["role"] in ("user", "system") else "model"
            if msg["role"] == "system":
                system_instruction = {"parts": [{"text": msg["content"]}]}
            else:
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            body["systemInstruction"] = system_instruction

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.GEMINI_API}/models/gemini-2.5-flash:generateContent?key={account.token}",
                    json=body,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            result.text = "".join(p.get("text", "") for p in parts)
                            return result
                    result.error = f"HTTP {resp.status}: {await resp.text()}"
                    return result
        except Exception as e:
            result.error = str(e)
            return result

    async def chat_stream(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0):
        result = await self.chat(messages, account, temperature, max_tokens, timeout)
        yield result.text

    def model_name(self) -> str:
        return "gemini-2.5-flash"


# ═══ Kimi Web Provider ═══

class KimiWebProvider(WebProvider):
    """Kimi (kimi.moonshot.cn) web → API.

    Kimi uses phone/wechat login → session token → chat API.
    Login flow:
      1. POST /api/auth/login → get token
      2. POST /api/chat → send messages
    
    No scinet needed — Kimi is hosted in China (moonshot.cn).
    """

    KIMI_API = "https://kimi.moonshot.cn"
    KIMI_LOGIN = "https://kimi.moonshot.cn/api/auth/login"
    KIMI_CHAT = "https://kimi.moonshot.cn/api/chat"

    def __init__(self):
        super().__init__(name="kimi-web", base_url=self.KIMI_API)

    async def login(self, account: WebAccount) -> bool:
        """Login to Kimi and get session token."""
        if not account.password:
            # Try pre-stored token first
            if account.token:
                return await self._verify_token(account)
            return False

        payload = {
            "phone": account.email,       # Kimi uses phone as account
            "password": account.password,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.KIMI_LOGIN,
                    json=payload,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0",
                        "Content-Type": "application/json",
                        "Origin": "https://kimi.moonshot.cn",
                        "Referer": "https://kimi.moonshot.cn/",
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        token = data.get("token") or data.get("access_token") or ""
                        if token:
                            account.token = token
                            account.cookies = {k: v.value for k, v in resp.cookies.items()}
                            logger.info("KimiWeb: login OK")
                            return True
                    
                    # Check if response indicates too many attempts
                    text = await resp.text()
                    if "频繁" in text or "验证码" in text:
                        logger.warning("KimiWeb: captcha/rate-limit for %s", account.email)
                    
                    logger.warning("KimiWeb login: HTTP %d", resp.status)
                    return False
        except Exception as e:
            logger.warning("KimiWeb login: %s", e)
            return False

    async def _verify_token(self, account: WebAccount) -> bool:
        """Check if stored token is still valid."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.KIMI_API + "/api/user",
                    headers=self._headers(account),
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def chat(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0) -> ProviderResult:
        result = ProviderResult(account_used=account.email or "kimi")
        
        if not account.token:
            result.error = "Not logged in"
            return result

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.KIMI_CHAT,
                    json=payload,
                    headers=self._headers(account),
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result.text = data.get("response", "") or data.get("content", "")
                        choices = data.get("choices", [])
                        if choices:
                            result.text = choices[0].get("message", {}).get("content", "")
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

    async def chat_stream(self, messages, account, temperature=0.7, max_tokens=4096, timeout=60.0):
        result = await self.chat(messages, account, temperature, max_tokens, timeout)
        yield result.text

    def model_name(self) -> str:
        return "kimi"

    def _headers(self, account: WebAccount) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0",
            "Authorization": f"Bearer {account.token}",
            "Content-Type": "application/json",
            "Origin": "https://kimi.moonshot.cn",
            "Referer": "https://kimi.moonshot.cn/",
        }
