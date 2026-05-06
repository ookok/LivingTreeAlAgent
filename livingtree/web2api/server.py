"""Web2API Plugin Registry — extensible provider system + FastAPI server.

Register any WebProvider subclass to expose it as an OpenAI-compatible API.
New platforms just need to implement WebProvider.login() and WebProvider.chat().

Server endpoints:
  POST /v1/chat/completions     OpenAI-compatible chat
  GET  /v1/models                 List available models
  GET  /admin/stats               Account pool + provider stats
  POST /admin/accounts/add        Add a new account
  GET  /admin/providers           List registered providers
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Optional

from loguru import logger

from .base_provider import WebProvider, WebAccount, AccountPool, ProviderResult
from .deepseek_provider import DeepSeekWebProvider
from .extended_providers import ClaudeWebProvider, GeminiWebProvider, KimiWebProvider
from .chinese_providers import (
    QwenWebProvider, GLMWebProvider, DoubaoWebProvider,
    SparkWebProvider, BaichuanWebProvider, YuanbaoWebProvider,
    MiniMaxWebProvider, StepChatWebProvider,
)


# ═══ Plugin Registry ═══

class ProviderRegistry:
    """Registry of all WebProvider plugins."""

    def __init__(self):
        self._providers: dict[str, WebProvider] = {}
        self._pools: dict[str, AccountPool] = {}
        self._register_builtin()

    def _register_builtin(self) -> None:
        self.register(DeepSeekWebProvider())
        self.register(ClaudeWebProvider())
        self.register(GeminiWebProvider())
        self.register(KimiWebProvider())
        # Chinese platforms
        self.register(QwenWebProvider())
        self.register(GLMWebProvider())
        self.register(DoubaoWebProvider())
        self.register(SparkWebProvider())
        self.register(BaichuanWebProvider())
        self.register(YuanbaoWebProvider())
        self.register(MiniMaxWebProvider())
        self.register(StepChatWebProvider())

    def register(self, provider: WebProvider) -> None:
        self._providers[provider.name] = provider
        if provider.name not in self._pools:
            self._pools[provider.name] = AccountPool()
        logger.info("Web2API: registered provider '%s'", provider.name)

    def get_provider(self, name: str) -> Optional[WebProvider]:
        return self._providers.get(name)

    def get_pool(self, name: str) -> Optional[AccountPool]:
        return self._pools.get(name)

    def add_account(self, provider_name: str, email: str, password: str = "",
                    token: str = "") -> bool:
        provider = self._providers.get(provider_name)
        if not provider:
            return False
        pool = self._pools[provider_name]
        pool.add(WebAccount(email=email, password=password, token=token))
        return True

    def list_providers(self) -> list[dict]:
        return [
            {
                "name": p.name,
                "base_url": p.base_url,
                "accounts": self._pools.get(p.name, AccountPool()).get_stats(),
                "supports_tools": p.supports_tools(),
                "model": p.model_name(),
            }
            for p in self._providers.values()
        ]

    def get_all_stats(self) -> dict:
        return {
            "providers": self.list_providers(),
            "total_accounts": sum(
                p.get_stats()["total"] for p in self._pools.values()
            ),
            "active_accounts": sum(
                p.get_stats()["active"] for p in self._pools.values()
            ),
        }


# ═══ OpenAI-Compatible Server ═══

class Web2APIServer:
    """FastAPI server exposing OpenAI-compatible endpoints.

    Usage:
        server = Web2APIServer()
        server.add_account("deepseek-web", "user@email.com", "password")
        await server.start(port=5001)
        # → http://localhost:5001/v1/chat/completions
    """

    def __init__(self):
        self._registry = ProviderRegistry()
        self._app = None
        self._runner = None

    def add_account(self, provider_name: str, email: str, password: str = "",
                    token: str = "") -> None:
        self._registry.add_account(provider_name, email, password, token)

    async def start(self, host: str = "0.0.0.0", port: int = 5001) -> None:
        try:
            from aiohttp import web
        except ImportError:
            raise RuntimeError("aiohttp required")

        app = web.Application()
        app.router.add_post("/v1/chat/completions", self._handle_chat)
        app.router.add_get("/v1/models", self._handle_models)
        app.router.add_get("/admin/stats", self._handle_stats)
        app.router.add_post("/admin/accounts/add", self._handle_add_account)
        app.router.add_get("/admin/providers", self._handle_list_providers)
        app.router.add_get("/health", self._handle_health)

        self._app = app
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        self._runner = runner

        logger.info("Web2API server started on http://%s:%d/v1", host, port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    # ═══ Handlers ═══

    async def _handle_chat(self, request) -> dict:
        try:
            body = await request.json()
        except Exception:
            return self._error("Invalid JSON")

        messages = body.get("messages", [])
        model = body.get("model", "deepseek-web")
        temperature = body.get("temperature", 0.7)
        max_tokens = body.get("max_tokens", 4096)
        stream = body.get("stream", False)

        provider = self._registry.get_provider(model)
        if not provider:
            # Try finding any provider
            providers = self._registry._providers
            if not providers:
                return self._error("No providers registered")
            provider = list(providers.values())[0]

        pool = self._registry.get_pool(provider.name)
        if not pool:
            return self._error("No account pool")

        account = await pool.acquire()
        if not account:
            return self._error("No available accounts")

        # Ensure logged in
        if not account.token:
            login_ok = await provider.login(account)
            if not login_ok:
                pool.mark_error(account)
                return self._error("Login failed")

        if stream:
            from aiohttp import web
            resp = web.StreamResponse()
            resp.headers["Content-Type"] = "text/event-stream"
            await resp.prepare(request)

            async for chunk in provider.chat_stream(messages, account, temperature, max_tokens):
                data = json.dumps({
                    "choices": [{"delta": {"content": chunk}, "index": 0}],
                    "object": "chat.completion.chunk",
                })
                await resp.write(f"data: {data}\n\n".encode())

            await resp.write(b"data: [DONE]\n\n")
            pool.mark_success(account)
            return resp

        result = await provider.chat(messages, account, temperature, max_tokens)
        if result.error:
            pool.mark_error(account)
            return self._error(result.error)

        pool.mark_success(account)
        return {
            "id": f"web2api-{int(time.time())}",
            "object": "chat.completion",
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": result.text},
                "finish_reason": result.finish_reason,
            }],
            "usage": {"total_tokens": result.tokens},
        }

    async def _handle_models(self, request) -> dict:
        return {
            "object": "list",
            "data": [
                {"id": p["name"], "object": "model"}
                for p in self._registry.list_providers()
            ],
        }

    async def _handle_stats(self, request) -> dict:
        return self._registry.get_all_stats()

    async def _handle_add_account(self, request) -> dict:
        body = await request.json()
        provider = body.get("provider", "deepseek-web")
        email = body.get("email", "")
        password = body.get("password", "")
        if not email or not password:
            return {"error": "email and password required"}
        success = self._registry.add_account(provider, email, password)
        return {"ok": success}

    async def _handle_list_providers(self, request) -> dict:
        return {"providers": self._registry.list_providers()}

    async def _handle_health(self, request) -> dict:
        return {"status": "ok"}

    @staticmethod
    def _error(msg: str) -> dict:
        return {"error": {"message": msg, "type": "web2api_error"}}


# ═══ Singleton ═══

_server: Optional[Web2APIServer] = None

def get_web2api_server() -> Web2APIServer:
    global _server
    if _server is None:
        _server = Web2APIServer()
    return _server
