"""OpenCode Serve Adapter — Connect LivingTree to opencode's headless API.

When opencode serve is running (default :4096), LivingTree can use it
as an LLM provider. The adapter wraps opencode's session-based API into
a simple prompt→response interface compatible with LivingTree's router.

Usage:
    adapter = OpenCodeServeAdapter(base_url="http://localhost:4096")
    
    if await adapter.ping():
        response = await adapter.chat("write a quick sort function")
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from loguru import logger


class OpenCodeServeAdapter:
    """Wraps opencode's session-based API into prompt→response calls."""

    def __init__(self, base_url: str = "http://localhost:4096",
                 username: str = "", password: str = ""):
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._session_id: str = ""
        self._available: bool | None = None

    async def ping(self) -> bool:
        if self._available is not None:
            return self._available

        import aiohttp
        try:
            async with aiohttp.ClientSession() as s:
                auth = self._get_auth()
                async with s.get(
                    f"{self._base_url}/health",
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    self._available = resp.status == 200
        except Exception:
            self._available = False

        if self._available:
            logger.info(f"OpenCode serve available at {self._base_url}")
        return self._available

    async def chat(self, prompt: str, model: str = "opencode/zen") -> str:
        if not await self.ping():
            return ""

        await self._ensure_session()

        import aiohttp
        try:
            async with aiohttp.ClientSession() as s:
                auth = self._get_auth()
                async with s.post(
                    f"{self._base_url}/session/{self._session_id}/prompt",
                    json={"prompt": prompt, "model": model},
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("response", data.get("result", ""))
                    elif resp.status == 404:
                        self._session_id = ""
                        return await self.chat(prompt, model)
                    else:
                        logger.debug(f"OpenCode serve: {resp.status}")
                        return ""
        except Exception as e:
            logger.debug(f"OpenCode serve chat: {e}")
            return ""

    async def chat_stream(self, prompt: str, model: str = "opencode/zen") -> AsyncIterator[str]:
        result = await self.chat(prompt, model)
        if result:
            for token in result.split():
                yield token + " "

    def close(self) -> None:
        self._session_id = ""
        self._available = None

    async def _ensure_session(self) -> None:
        if self._session_id:
            return

        import aiohttp
        try:
            async with aiohttp.ClientSession() as s:
                auth = self._get_auth()
                async with s.post(
                    f"{self._base_url}/session",
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._session_id = data.get("id", "")
        except Exception as e:
            logger.debug(f"OpenCode serve session: {e}")

    def _get_auth(self):
        if self._username and self._password:
            import aiohttp
            return aiohttp.BasicAuth(self._username, self._password)
        return None


async def discover_opencode_serve() -> dict | None:
    adapter = OpenCodeServeAdapter()
    if await adapter.ping():
        return {
            "name": "opencode-serve",
            "base_url": adapter._base_url,
            "available": True,
        }
    return None
