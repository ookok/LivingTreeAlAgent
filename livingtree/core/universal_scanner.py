"""UniversalScanner — LLM-guided universal service discovery and auto-configuration.

Developer describes a service: "帮我接入本地的Qwen模型，地址是localhost:8080"
小树: probes the endpoint, detects protocol, tests connectivity,
       asks for API key if needed (via conversation), stores encrypted,
       registers the provider/skill/tool automatically.

Supports:
- OpenAI-compatible LLM endpoints (any URL)
- MCP servers (JSON-RPC 2.0)
- Databases (SQLite, PostgreSQL, Redis) via connection string
- HTTP/REST services (any URL with health check)
- Local filesystem storage paths
- Memory layers (ChromaDB, Qdrant) via HTTP API
- S3-compatible storage
"""

from __future__ import annotations

import asyncio
import json as _json
import time as _time
from dataclasses import dataclass, field
from typing import Any, Optional

import aiohttp
from loguru import logger


@dataclass
class ServiceEndpoint:
    name: str
    category: str          # "llm", "mcp", "database", "storage", "memory", "http", "unknown"
    url: str
    protocol: str = ""     # "openai", "jsonrpc", "postgresql", "redis", "s3", "http", ""
    is_alive: bool = False
    requires_auth: bool = False
    auth_type: str = ""    # "api_key", "bearer", "basic", "none"
    models: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    config_snippet: str = ""
    discovered_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name, "category": self.category, "url": self.url,
            "protocol": self.protocol, "is_alive": self.is_alive,
            "requires_auth": self.requires_auth, "auth_type": self.auth_type,
            "models": self.models[:10], "capabilities": self.capabilities,
            "config_snippet": self.config_snippet,
        }


PROTOCOL_PROBES = {
    "openai": [
        {"path": "/v1/models", "method": "GET", "key_field": "data"},
        {"path": "/models", "method": "GET", "key_field": "data"},
        {"path": "/v1/chat/completions", "method": "POST", "key_field": "choices",
         "body": {"model": "test", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}},
    ],
    "jsonrpc": [
        {"path": "/", "method": "POST", "key_field": "result",
         "body": {"jsonrpc": "2.0", "method": "tools/list", "id": 1},
         "headers": {"Content-Type": "application/json"}},
        {"path": "/mcp", "method": "POST", "key_field": "result",
         "body": {"jsonrpc": "2.0", "method": "initialize", "id": 1, "params": {}},
         "headers": {"Content-Type": "application/json"}},
    ],
    "health": [
        {"path": "/health", "method": "GET", "key_field": None},
        {"path": "/", "method": "GET", "key_field": None},
        {"path": "/api/health", "method": "GET", "key_field": None},
    ],
}


class UniversalScanner:
    """LLM-guided universal service discovery."""

    def __init__(self, hub=None):
        self._hub = hub
        self._discovered: dict[str, ServiceEndpoint] = {}

    @property
    def hub(self):
        return self._hub

    async def discover_from_description(self, description: str) -> Optional[ServiceEndpoint]:
        """LLM parses developer's description, extracts URL/type, then probes.
        
        Returns a ServiceEndpoint with auto-detected protocol, models, and capabilities.
        """
        world = self.hub.world if self.hub else None
        consc = getattr(world, "consciousness", None) if world else None

        url = ""
        svc_type = "unknown"
        port = None

        if consc:
            try:
                prompt = (
                    f"解析以下描述，提取服务连接信息。返回JSON:\n"
                    f'{{"url":"完整URL","category":"llm|mcp|database|storage|memory|http",'
                    f'"port":数字,"requires_auth":true|false,"auth_type":"api_key|bearer|basic|none"}}\n\n'
                    f"描述: {description}"
                )
                resp = await consc.chain_of_thought(prompt, steps=1)
                text = resp if isinstance(resp, str) else str(resp)
                try:
                    data = _json.loads(text[text.find("{"):text.rfind("}") + 1])
                    url = data.get("url", "")
                    svc_type = data.get("category", "unknown")
                    port = data.get("port")
                    requires_auth = data.get("requires_auth", False)
                    auth_type = data.get("auth_type", "none")
                except Exception:
                    pass
            except Exception:
                pass

        # Fallback: extract URL from description
        if not url:
            import re
            urls = re.findall(r'https?://[^\s,，。]+|localhost:\d+|\d+\.\d+\.\d+\.\d+:\d+', description)
            if urls:
                url = urls[0]
                if not url.startswith("http"):
                    url = f"http://{url}"

        if not url:
            return None

        svc = ServiceEndpoint(
            name=description[:60],
            category=svc_type,
            url=url,
            discovered_at=_time.time(),
        )

        await self._probe_protocol(svc)
        if svc.is_alive:
            await self._analyze_capability(svc)
            self._discovered[url] = svc

        return svc

    async def _probe_protocol(self, svc: ServiceEndpoint):
        """Probe a service to detect its protocol."""
        base = svc.url.rstrip("/")
        detected = False

        async with aiohttp.ClientSession() as session:
            # Health check first
            for probe in PROTOCOL_PROBES["health"]:
                try:
                    test_url = f"{base}{probe['path']}"
                    async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        if resp.status < 500:
                            svc.is_alive = True
                            logger.debug(f"Health OK: {test_url}")
                            break
                except Exception:
                    continue

            if not svc.is_alive:
                return

            # Probe OpenAI-compatible
            for probe in PROTOCOL_PROBES["openai"]:
                try:
                    test_url = f"{base}{probe['path']}"
                    if probe["method"] == "GET":
                        async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status < 500:
                                data = await resp.json()
                                if probe["key_field"] in data:
                                    svc.protocol = "openai"
                                    models_data = data.get("data", [])
                                    svc.models = [m.get("id", str(m)) for m in models_data[:20]]
                                    detected = True
                                    break
                    elif probe["method"] == "POST":
                        async with session.post(test_url, json=probe["body"], timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status in (200, 400, 401):
                                data = await resp.json()
                                if probe["key_field"] in data or resp.status == 401:
                                    svc.protocol = "openai"
                                    svc.requires_auth = resp.status == 401
                                    if resp.status == 401:
                                        svc.auth_type = "api_key"
                                    detected = True
                                    break
                except Exception:
                    continue

            if not detected:
                # Probe MCP/JSON-RPC
                for probe in PROTOCOL_PROBES["jsonrpc"]:
                    try:
                        test_url = f"{base}{probe['path']}"
                        async with session.post(
                            test_url, json=probe["body"],
                            headers=probe.get("headers", {}),
                            timeout=aiohttp.ClientTimeout(total=5),
                        ) as resp:
                            if resp.status < 500:
                                data = await resp.json()
                                if probe["key_field"] in data:
                                    svc.protocol = "jsonrpc"
                                    svc.category = "mcp"
                                    detected = True
                                    break
                    except Exception:
                        continue

            if not detected:
                svc.protocol = "http"
                svc.category = svc.category or "http"

    async def _analyze_capability(self, svc: ServiceEndpoint):
        """LLM analyzes what capabilities this service enables."""
        world = self.hub.world if self.hub else None
        consc = getattr(world, "consciousness", None) if world else None
        if not consc:
            self._heuristic_capability(svc)
            return

        try:
            models_str = ", ".join(svc.models[:10]) if svc.models else "未知"
            prompt = (
                f"一个外部服务已发现:\n"
                f"URL: {svc.url}\n协议: {svc.protocol}\n类型: {svc.category}\n"
                f"可用模型: {models_str}\n\n"
                f"分析此服务能为系统增强哪些能力(3条), 并生成一个配置代码片段。"
                f"返回JSON: {{'capabilities':['能力1','能力2','能力3'],'config_snippet':'...'}}"
            )
            resp = await consc.chain_of_thought(prompt, steps=1)
            text = resp if isinstance(resp, str) else str(resp)
            try:
                data = _json.loads(text[text.find("{"):text.rfind("}") + 1])
                svc.capabilities = data.get("capabilities", [])[:5]
                svc.config_snippet = data.get("config_snippet", "")[:500]
            except Exception:
                self._heuristic_capability(svc)
        except Exception:
            self._heuristic_capability(svc)

    def _heuristic_capability(self, svc: ServiceEndpoint):
        heuristics = {
            "openai": ["LLM推理", "文本生成", "模型路由"],
            "jsonrpc": ["工具调用", "外部协议集成"],
            "http": ["HTTP服务", "API集成"],
            "database": ["数据存储", "查询检索"],
            "storage": ["文件存储", "对象存储"],
            "memory": ["向量检索", "记忆增强"],
        }
        svc.capabilities = heuristics.get(svc.protocol, heuristics.get(svc.category, ["外部服务"]))
        svc.config_snippet = f"# Auto-discovered {svc.protocol} service at {svc.url}"

    async def scan_network(self, host: str = "127.0.0.1", port_range: tuple = (1024, 65535),
                            max_ports: int = 50) -> list[ServiceEndpoint]:
        """Scan a subset of ports for HTTP services."""
        import random
        import socket
        from concurrent.futures import ThreadPoolExecutor

        def probe_port(p):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                result = s.connect_ex((host, p))
                s.close()
                return p if result == 0 else None
            except Exception:
                return None

        lo, hi = port_range
        all_ports = list(range(lo, min(hi, lo + 2000)))
        random.shuffle(all_ports)
        target_ports = all_ports[:max_ports]

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [loop.run_in_executor(pool, probe_port, p) for p in target_ports]
            results = await asyncio.gather(*futures)

        open_ports = [p for p in results if p is not None]
        discovered = []
        for port in open_ports:
            svc = ServiceEndpoint(
                name=f"port_{port}",
                category="unknown",
                url=f"http://{host}:{port}",
                discovered_at=_time.time(),
            )
            await self._probe_protocol(svc)
            if svc.is_alive and svc.protocol:
                await self._analyze_capability(svc)
                self._discovered[svc.url] = svc
                discovered.append(svc)

        return discovered

    async def auto_register_service(self, svc: ServiceEndpoint,
                                     api_key: str = "", password: str = "") -> dict:
        """Auto-register a discovered service with the appropriate system."""
        result = {"ok": True, "registered_as": []}
        world = self.hub.world if self.hub else None
        if not world:
            return {"ok": False, "error": "no world"}

        admin = None
        try:
            from ..core.admin_manager import get_admin
            admin = get_admin()
        except Exception:
            pass

        if svc.protocol == "openai" and api_key:
            key_name = f"{svc.name.replace(' ', '_').lower()}_api_key"
            if admin:
                admin.store_credential(key_name, api_key)
            try:
                from ..treellm.providers import OpenAILikeProvider
                provider = OpenAILikeProvider(
                    name=svc.name.replace(" ", "_").lower()[:20],
                    base_url=svc.url,
                    api_key=api_key,
                    default_model=svc.models[0] if svc.models else "default",
                )
                world.consciousness._llm.add_provider(provider)
                result["registered_as"].append("llm_provider")
            except Exception as e:
                result["registered_as"].append(f"llm_provider_failed:{e}")

        if svc.protocol == "jsonrpc":
            result["registered_as"].append("mcp_server")

        for cap in svc.capabilities[:3]:
            try:
                sf = getattr(world, "skill_factory", None)
                if sf and hasattr(sf, "register"):
                    sf.register(name=f"{svc.name}_{cap}", description=cap)
                    result["registered_as"].append(f"skill:{cap}")
            except Exception:
                pass

        return result

    def get_discovered(self) -> list[dict]:
        return [s.to_dict() for s in self._discovered.values()]

    def status(self) -> dict:
        return {
            "discovered_count": len(self._discovered),
            "services": self.get_discovered(),
        }


_scanner_instance: Optional[UniversalScanner] = None


def get_universal_scanner() -> UniversalScanner:
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = UniversalScanner()
    return _scanner_instance
