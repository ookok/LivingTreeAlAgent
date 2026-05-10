"""CapabilityScanner — auto-discovers external services and analyzes their impact.

When an external service appears (OnlyOffice, OpenCode, local LLM, web2api, etc.),
the scanner:
  1. Detects the service via port probe or process scan
  2. Uses LLM to analyze what new capabilities this service enables
  3. Auto-registers capabilities in skill system, tool market, model registry
  4. Reports to Living Canvas for real-time visualization

Everything unknown becomes known through active analysis.
"""

from __future__ import annotations

import asyncio
import json as _json
import platform
import socket
import subprocess
import time as _time
from dataclasses import dataclass, field
from typing import Any, Optional

import aiohttp
from loguru import logger


@dataclass
class DiscoveredService:
    name: str
    service_type: str    # "llm", "office", "lsp", "proxy", "storage", "unknown"
    endpoint: str
    port: int
    is_alive: bool = False
    capabilitiy_analysis: str = ""
    enabled_capabilities: list[str] = field(default_factory=list)
    discovered_at: float = 0.0
    last_check: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.service_type,
            "endpoint": self.endpoint,
            "port": self.port,
            "is_alive": self.is_alive,
            "analysis": self.capabilitiy_analysis,
            "capabilities": self.enabled_capabilities,
            "discovered_at": self.discovered_at,
        }


KNOWN_SERVICES = [
    {"name": "OpenCode Serve", "type": "lsp", "port": 4096, "path": "/health"},
    {"name": "OnlyOffice", "type": "office", "port": 9000, "path": "/"},
    {"name": "Ollama", "type": "llm", "port": 11434, "path": "/"},
    {"name": "vLLM", "type": "llm", "port": 8000, "path": "/"},
    {"name": "LM Studio", "type": "llm", "port": 1234, "path": "/v1/models"},
    {"name": "LocalAI", "type": "llm", "port": 8080, "path": "/v1/models"},
    {"name": "Web2API", "type": "llm", "port": 5001, "path": "/v1/models"},
    {"name": "llama.cpp", "type": "llm", "port": 8081, "path": "/v1/models"},
    {"name": "Jan", "type": "llm", "port": 1337, "path": "/v1/models"},
    {"name": "text-generation-webui", "type": "llm", "port": 5000, "path": "/v1/models"},
    {"name": "GPT4All", "type": "llm", "port": 4891, "path": "/v1/models"},
    {"name": "OpenWebUI", "type": "llm", "port": 3000, "path": "/api/models"},
    {"name": "LiteLLM Proxy", "type": "llm", "port": 4000, "path": "/v1/models"},
    {"name": "Scinet Proxy", "type": "proxy", "port": 7890, "path": "/"},
    {"name": "LivingTree Relay", "type": "relay", "port": 8888, "path": "/health"},
    {"name": "Docker API", "type": "infra", "port": 2375, "path": "/version"},
    {"name": "Redis", "type": "storage", "port": 6379, "path": ""},
    {"name": "PostgreSQL", "type": "storage", "port": 5432, "path": ""},
]


class CapabilityScanner:
    """Auto-discovers and analyzes external services."""

    def __init__(self, hub=None):
        self._hub = hub
        self._services: dict[str, DiscoveredService] = {}
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None

    @property
    def hub(self):
        return self._hub

    async def start(self):
        if self._running:
            return
        self._running = True
        self._scan_task = asyncio.create_task(self._scan_loop())
        logger.info("CapabilityScanner: active service discovery started")

    async def stop(self):
        self._running = False
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass

    async def _scan_loop(self):
        """Periodically scan for known services."""
        await self.scan_all()
        while self._running:
            await self.scan_all()
            await asyncio.sleep(60)

    async def scan_all(self) -> list[DiscoveredService]:
        """Scan all known service ports concurrently."""
        tasks = []
        for svc in KNOWN_SERVICES:
            tasks.append(self._probe_service(svc))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        discovered = []
        for r in results:
            if isinstance(r, DiscoveredService):
                discovered.append(r)
                self._services[r.name] = r
                if r.is_alive:
                    await self._analyze_capability(r)

        return discovered

    async def _probe_service(self, svc_def: dict) -> Optional[DiscoveredService]:
        """Probe a single service port."""
        name = svc_def["name"]
        port = svc_def["port"]
        path = svc_def.get("path", "/")
        svc_type = svc_def["type"]

        existing = self._services.get(name)
        was_alive = existing.is_alive if existing else False

        svc = DiscoveredService(
            name=name,
            service_type=svc_type,
            endpoint=f"http://localhost:{port}{path}",
            port=port,
            discovered_at=existing.discovered_at if existing else _time.time(),
            last_check=_time.time(),
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://localhost:{port}{path}",
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as resp:
                    svc.is_alive = resp.status < 500
        except Exception:
            svc.is_alive = False

        if svc.is_alive and not was_alive:
            logger.info(f"Service appeared: {name} (port {port}, type {svc_type})")
        elif not svc.is_alive and was_alive:
            logger.info(f"Service disappeared: {name} (port {port})")

        return svc

    async def _analyze_capability(self, svc: DiscoveredService):
        """Use LLM to analyze what capabilities a new service enables."""
        world = self.hub.world if self.hub else None
        consc = getattr(world, "consciousness", None) if world else None

        if not consc:
            self._heuristic_analysis(svc)
            return

        try:
            prompt = (
                f"一个新的外部服务已接入 LivingTree 系统:\n"
                f"名称: {svc.name}\n"
                f"类型: {svc.service_type}\n"
                f"端口: {svc.port}\n\n"
                f"请分析这个服务能为系统增强哪些具体能力(3-5条)。"
                f"每条以短横线开头，简洁描述能力名称。"
            )
            resp = await consc.chain_of_thought(prompt, steps=1)
            text = resp if isinstance(resp, str) else str(resp)
            lines = [l.strip().lstrip("-•* ").strip() for l in text.split("\n") if l.strip() and (l.strip().startswith("-") or l.strip().startswith("•"))]
            if lines:
                svc.capabilitiy_analysis = "; ".join(lines[:5])
                svc.enabled_capabilities = lines[:5]
                logger.info(f"Capability analysis for {svc.name}: {svc.capabilitiy_analysis[:100]}")
                await self._register_capabilities(svc)
                return
        except Exception as e:
            logger.debug(f"LLM capability analysis failed for {svc.name}: {e}")

        self._heuristic_analysis(svc)

    def _heuristic_analysis(self, svc: DiscoveredService):
        """Fallback: heuristic capability analysis."""
        heuristics = {
            "OpenCode Serve": ["代码诊断", "LSP支持", "智能补全"],
            "OnlyOffice": ["文档编辑", "协同办公", "模板填充", "格式转换"],
            "Ollama": ["本地推理", "离线LLM", "隐私计算"],
            "vLLM": ["高吞吐推理", "批量处理", "本地LLM"],
            "LM Studio": ["本地LLM", "模型管理"],
            "LocalAI": ["本地LLM", "多模态推理"],
            "Web2API": ["API代理", "模型聚合"],
            "Scinet Proxy": ["海外加速", "智能路由"],
            "LivingTree Relay": ["节点发现", "消息路由", "负载均衡"],
            "Redis": ["缓存加速", "会话存储"],
            "PostgreSQL": ["数据持久化", "向量存储"],
        }
        caps = heuristics.get(svc.name, [f"{svc.service_type}服务"])
        svc.capabilitiy_analysis = "; ".join(caps)
        svc.enabled_capabilities = caps

    async def _register_capabilities(self, svc: DiscoveredService):
        """Register discovered capabilities with the skill/tool systems."""
        world = self.hub.world if self.hub else None
        if not world or not svc.enabled_capabilities:
            return

        sf = getattr(world, "skill_factory", None)
        for cap in svc.enabled_capabilities[:3]:
            if sf and hasattr(sf, "register"):
                try:
                    sf.register(
                        name=f"{svc.name}_{cap}",
                        description=f"来自 {svc.name} 的 {cap} 能力",
                    )
                except Exception:
                    pass

    def get_services(self) -> list[dict]:
        return [s.to_dict() for s in self._services.values()]

    def get_alive_services(self) -> list[dict]:
        return [s.to_dict() for s in self._services.values() if s.is_alive]

    def status(self) -> dict:
        alive = sum(1 for s in self._services.values() if s.is_alive)
        total = len(self._services)
        new_services = [s for s in self._services.values() if s.is_alive and s.capabilitiy_analysis and s.discovered_at > _time.time() - 120]
        return {
            "total_known": len(KNOWN_SERVICES),
            "alive": alive,
            "dead": total - alive,
            "services": self.get_alive_services(),
            "recently_discovered": [s.to_dict() for s in new_services],
            "enabled_capabilities": sum(len(s.enabled_capabilities) for s in self._services.values() if s.is_alive),
        }


_scanner_instance: Optional[CapabilityScanner] = None


def get_capability_scanner() -> CapabilityScanner:
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = CapabilityScanner()
    return _scanner_instance
