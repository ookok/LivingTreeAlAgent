"""Local LLM Scanner — auto-detect ollama/vLLM/LM Studio/local services.

Scans known ports for OpenAI-compatible endpoints, discovers available models,
and optionally registers them as providers in TreeLLM.

Detected services:
- Ollama (11434) — no auth needed
- vLLM (8000) — usually no auth locally
- LM Studio (1234) — no auth
- LocalAI (8080)
- text-generation-webui / oobabooga (5000)
- llama.cpp server (8081)
- Jan (1337)
- GPT4All (4891)
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import ClassVar

import httpx
from loguru import logger


@dataclass
class LocalService:
    name: str
    host: str
    port: int
    base_url: str = ""
    alive: bool = False
    api_key: str = ""
    models: list[dict] = field(default_factory=list)
    error: str = ""

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


KNOWN_SERVICES: ClassVar[list[dict]] = [
    {"name": "ollama", "host": "127.0.0.1", "port": 11434, "key": "ollama"},
    {"name": "vllm", "host": "127.0.0.1", "port": 8000},
    {"name": "lmstudio", "host": "127.0.0.1", "port": 1234, "key": "lm-studio"},
    {"name": "localai", "host": "127.0.0.1", "port": 8080},
    {"name": "jan", "host": "127.0.0.1", "port": 1337, "path": "/v1"},
    {"name": "textgen-webui", "host": "127.0.0.1", "port": 5000, "path": "/v1"},
    {"name": "llamacpp", "host": "127.0.0.1", "port": 8081, "path": "/v1"},
    {"name": "gpt4all", "host": "127.0.0.1", "port": 4891, "path": "/v1"},
    {"name": "openwebui", "host": "127.0.0.1", "port": 3000, "path": "/api"},
    {"name": "litellm", "host": "127.0.0.1", "port": 4000},
]

SCAN_TIMEOUT = 3.0
FETCH_TIMEOUT = 10.0


class LocalScanner:
    """Discovers locally running LLM services and their models."""

    def __init__(self):
        self._services: list[LocalService] = []
        self._scanned = False

    @property
    def services(self) -> list[LocalService]:
        return self._services

    @property
    def alive_services(self) -> list[LocalService]:
        return [s for s in self._services if s.alive]

    @property
    def all_models(self) -> list[dict]:
        """Flatten all models from all alive services."""
        models = []
        for s in self.alive_services:
            for m in s.models:
                m["_service"] = s.name
                m["_local"] = True
                models.append(m)
        return models

    async def scan(self) -> list[LocalService]:
        """Scan all known ports for running LLM services."""
        self._services = []
        tasks = []

        for cfg in KNOWN_SERVICES:
            svc = LocalService(
                name=cfg["name"],
                host=cfg["host"],
                port=cfg["port"],
                base_url=f"http://{cfg['host']}:{cfg['port']}{cfg.get('path', '')}",
                api_key=cfg.get("key", ""),
            )
            self._services.append(svc)
            tasks.append(self._check_service(svc))

        await asyncio.gather(*tasks, return_exceptions=True)
        self._scanned = True

        alive = self.alive_services
        total_models = sum(len(s.models) for s in alive)
        logger.info(
            f"Local scan: {len(alive)} services alive "
            f"({', '.join(s.name for s in alive) or 'none'}), "
            f"{total_models} models found"
        )
        return alive

    async def _check_service(self, svc: LocalService):
        """Check if a service is alive and fetch its models."""
        try:
            async with httpx.AsyncClient(timeout=SCAN_TIMEOUT) as client:
                # Quick health check — try /models endpoint (OpenAI-compatible)
                models_url = f"{svc.base_url}/models"
                headers = {}
                if svc.api_key:
                    headers["Authorization"] = f"Bearer {svc.api_key}"

                resp = await client.get(models_url, headers=headers)
                if resp.status_code == 200:
                    svc.alive = True
                    await self._fetch_models(svc, client, headers)
                elif resp.status_code == 401:
                    svc.error = "requires auth"
                    logger.debug(f"  {svc.name} @ {svc.url}: requires authentication, skipped")
                else:
                    svc.error = f"HTTP {resp.status_code}"
                    logger.debug(f"  {svc.name} @ {svc.url}: {svc.error}")

        except httpx.ConnectError:
            logger.debug(f"  {svc.name} @ {svc.url}: not running")
        except asyncio.TimeoutError:
            logger.debug(f"  {svc.name} @ {svc.url}: timeout")
        except Exception as e:
            logger.debug(f"  {svc.name} @ {svc.url}: {e}")

    async def _fetch_models(self, svc: LocalService, client: httpx.AsyncClient, headers: dict):
        """Fetch and parse model list from an alive service."""
        try:
            models_url = f"{svc.base_url}/models"
            resp = await client.get(models_url, headers=headers, timeout=FETCH_TIMEOUT)
            if resp.status_code != 200:
                return

            data = resp.json()
            model_list = []

            if isinstance(data, dict):
                items = data.get("data", [])
                if not items:
                    items = [data]
                for item in items:
                    if isinstance(item, dict):
                        mid = item.get("id", "")
                        if mid:
                            model_list.append({
                                "id": mid,
                                "owned_by": item.get("owned_by", svc.name),
                                "context_length": item.get("context_length", 4096),
                                "max_tokens": item.get("max_tokens", 4096),
                            })

            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        mid = item.get("id", item.get("name", ""))
                        if mid:
                            model_list.append({
                                "id": mid,
                                "owned_by": item.get("owned_by", svc.name),
                            })
            elif isinstance(data, str):
                model_list.append({"id": data, "owned_by": svc.name})

            svc.models = model_list
            logger.info(f"  {svc.name}: {len(model_list)} models")

        except Exception as e:
            svc.error = f"model fetch: {e}"
            svc.alive = False  # mark dead if models can't be fetched


async def scan_local_models() -> list[LocalService]:
    """Convenience: scan and return alive services."""
    scanner = LocalScanner()
    return await scanner.scan()
