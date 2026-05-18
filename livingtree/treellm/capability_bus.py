"""Capability Bus — LLM-facing tool registry and execution gateway.

⚠️  ARCHITECTURE MIGRATION IN PROGRESS:
    This module currently has direct imports from capability/ (9 places).
    Target: all tool access goes through bridge.ToolRegistry.
    See ARCHITECTURE.md for the migration roadmap.

    Migration status: bridge/ layer created, registry ready.
    Next: register capability tools in registry, replace imports here.
"""



from __future__ import annotations

import asyncio
import json
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger
from scrapling.fetchers import Fetcher as _ScraplingFetcher
from scrapling.parser import Selector as _ScraplingSelector


# ═══ Capability Category ═══════════════════════════════════════════


class CapCategory(StrEnum):
    TOOL = "tool"
    SKILL = "skill"
    MCP = "mcp"
    ROLE = "role"
    USER = "user"
    LLM = "llm"
    VFS = "vfs"
    ORGAN = "organ"
    SEARCH = "search"
    KNOWLEDGE = "knowledge"
    CUSTOM = "custom"


# ═══ Unified Capability Descriptor ══════════════════════════════════


@dataclass
class CapParam:
    name: str
    type: str = "string"          # string | number | boolean | object | array
    description: str = ""
    required: bool = False
    default: Any = None


@dataclass
class Capability:
    """Unified descriptor for any capability in the system."""
    id: str                                # "tool:web_search", "skill:tabular_reason"
    name: str                              # "web_search"
    category: CapCategory                  # CapCategory.TOOL
    description: str = ""
    params: list[CapParam] = field(default_factory=list)
    returns: dict = field(default_factory=dict)  # {"type":"string","description":"..."}
    examples: list[dict] = field(default_factory=list)
    handler: Callable = None               # async callable(**params) → result
    is_available: bool = True
    cost_estimate: dict = field(default_factory=dict)  # {"tokens":100,"seconds":1}
    tags: list[str] = field(default_factory=list)
    source: str = ""                       # Where this was registered from

    def prompt_fragment(self) -> str:
        """Generate a one-line description for LLM system prompts."""
        params_str = ", ".join(
            f"{p.name}:{p.type}" for p in self.params[:3]
        )
        return f"{self.id}: {self.description[:100]} (params: {params_str})"


# ═══ Capability Adapter (abstract) ══════════════════════════════════


class CapabilityAdapter(ABC):
    """Base adapter for a category of capabilities."""

    def __init__(self, category: CapCategory):
        self.category = category
        self._caps: dict[str, Capability] = {}
        self._invoke_count = 0

    @abstractmethod
    async def discover(self) -> list[Capability]:
        """Auto-discover capabilities from existing registries."""
        ...

    def register(self, cap: Capability) -> None:
        self._caps[cap.id] = cap

    def get(self, cap_id: str) -> Optional[Capability]:
        return self._caps.get(cap_id)

    def list_all(self) -> list[Capability]:
        return list(self._caps.values())

    async def invoke(self, cap_id: str, **params) -> Any:
        """Invoke a capability by ID. Returns result."""
        cap = self._caps.get(cap_id)
        if not cap:
            return {"error": f"Capability not found: {cap_id}"}
        if not cap.handler:
            return {"error": f"No handler for: {cap_id}"}
        if not cap.is_available:
            return {"error": f"Capability unavailable: {cap_id}"}

        self._invoke_count += 1
        try:
            result = cap.handler(**params)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as e:
            logger.debug(f"CapabilityBus invoke {cap_id}: {e}")
            return {"error": str(e)[:500]}


# ═══ Concrete Adapters ══════════════════════════════════════════════


class ToolAdapter(CapabilityAdapter):
    """Adapter for system tools (ReactExecutor, ToolMarket)."""

    def __init__(self):
        super().__init__(CapCategory.TOOL)

    async def discover(self) -> list[Capability]:
        caps = []
        try:
            from ...bridge.registry import get_tool_registry
            market = get_tool_registry().get("tool_market")  # via bridge
            for name, tool in market._tools.items():
                desc = getattr(tool, 'description', '') or str(tool)[:100]
                category = getattr(tool, 'category', '')
                cap = Capability(
                    id=f"tool:{name}", name=name, category=CapCategory.TOOL,
                    description=desc[:200],
                    params=[CapParam(name="input", type="string", description="Tool input")],
                    handler=lambda input="", _name=name, _market=market: self._invoke_tool(_name, input, _market),
                    source="tool_market",
                    tags=[category] if category else [],
                )
                caps.append(cap)
                self.register(cap)
        except Exception as e:
            logger.debug(f"ToolAdapter discover: {e}")

        # Add core tools from ReactExecutor
        try:
            from ..execution.react_executor import ReactExecutor
            rex_tools = {
                "web_search": ("Search the internet for current information, news, or facts", "query"),
                "browser_browse": ("Open a page in browser, type/click/extract. For JS-rendered or interactive sites", "url + task"),
                "web_fetch": ("Fetch a static page by URL (Scrapling with TLS impersonation)", "url"),
                "browser_screenshot": ("Take a screenshot of the current browser page for visual analysis", "none"),
                "browser_session_open": ("Open a persistent browser session (reuse across multiple browse calls)", "url"),
                "browser_session_close": ("Close the current browser session", "none"),
                "browser_session_list": ("List active browser sessions", "none"),
                "browser_inject": ("Lightweight WebView browser with JS injection. Navigate + extract + click + type. For sites that block headless browsers", "url + task"),
                # ── Automation / DevOps tools ──
                "system_health": ("Check system health across all subsystems (CPU, memory, models, errors)", "none"),
                "system_metrics": ("Get Prometheus-style metrics snapshot (LLM calls, latency, cost)", "none"),
                "cron_add": ("Schedule a recurring task. Format: name|schedule|task_description", "name|schedule|task"),
                "cron_list": ("List all scheduled cron jobs", "none"),
                "cron_remove": ("Remove a cron job by name", "name"),
                "improve_scan": ("Scan codebase for defects, vulnerabilities, and improvement opportunities", "none"),
                "improve_propose": ("Propose code improvements (auto test gen, config centralize, refactor)", "none"),
                "improve_apply": ("Apply a specific code improvement by proposal id. Requires confirmation", "id"),
                "overnight_start": ("Start a long-running autonomous task (LLM decomposes goal into steps)", "goal description"),
                "overnight_status": ("Check status of running overnight tasks", "none"),
                "overnight_cancel": ("Cancel an overnight task", "task_id"),
                "api_search": ("Find available API endpoints (weather, maps, translation) by keyword. Use before api_call", "keyword"),
                "kb_search": ("Search knowledge base", "query"),
                "read_file": ("Read a file", "path"),
                "write_file": ("Write to a file", "path\\ncontent"),
                "run_command": ("Run a shell command", "command"),
            }
            for name, (desc, param_hint) in rex_tools.items():
                cap_id = f"tool:{name}"
                if cap_id not in self._caps:
                    cap = Capability(
                        id=cap_id, name=name, category=CapCategory.TOOL,
                        description=desc,
                        params=[CapParam(name="input", type="string", description=param_hint)],
                        handler=lambda input="", _name=name: self._invoke_rex(_name, input),
                        source="react_executor",
                    )
                    caps.append(cap)
                    self.register(cap)
        except Exception as e:
            logger.debug(f"ToolAdapter rex: {e}")
        return caps

    def _invoke_tool(self, name: str, input_str: str, market) -> Any:
        return market.execute(name, {"input": input_str})

    async def _invoke_rex(self, name: str, input_str: str) -> Any:
        # Route file operations through VFS for unified safety + mount support
        if name in ("read_file", "write_file"):
            store = None
            try:
                from .living_store import get_living_store
                store = get_living_store()
            except Exception:
                pass
            if store:
                if name == "read_file":
                    text = await store.read_text(input_str.strip())
                    return text[:10000] if text else ""
                if name == "write_file":
                    parts = input_str.split("\n", 1)
                    path = parts[0].strip()
                    content = parts[1] if len(parts) > 1 else ""
                    await store.write_text(path, content)
                    return f"[vfs] wrote {len(content)} bytes to {path}"

        try:
            from ..execution.react_executor import ReactExecutor
            rex = ReactExecutor()
            methods = {
                "web_search": rex._tool_web_search,
                "browser_browse": lambda s: self._browser_browse(s),
                "web_fetch": lambda s: self._web_fetch(s),
                "browser_screenshot": lambda s: self._browser_screenshot(s),
                "browser_session_open": lambda s: self._browser_session(s, "open", s),
                "browser_session_close": lambda s: self._browser_session(s, "close", ""),
                "browser_session_list": lambda s: self._browser_session_list(),
                "browser_inject": lambda s: self._browser_inject(s),
                "system_health": lambda s: self._system_health(),
                "system_metrics": lambda s: self._system_metrics(),
                "cron_add": lambda s: self._cron_add(s),
                "cron_list": lambda s: self._cron_list(),
                "cron_remove": lambda s: self._cron_remove(s),
                "improve_scan": lambda s: self._improve_scan(),
                "improve_propose": lambda s: self._improve_propose(),
                "improve_apply": lambda s: self._improve_apply(s),
                "overnight_start": lambda s: self._overnight_start(s),
                "overnight_status": lambda s: self._overnight_status(),
                "overnight_cancel": lambda s: self._overnight_cancel(s),
                "api_search": lambda s: self._api_search(s),
                "kb_search": rex._tool_kb_search,
                "read_file": lambda s: self._read_file(s),
                "write_file": lambda s: self._write_file(s),
                "run_command": rex._tool_run_command,
            }
            fn = methods.get(name)
            if fn:
                result = fn(input_str)
                return await result if asyncio.iscoroutine(result) else result
        except Exception as e:
            return {"error": str(e)}
        return {"error": f"Unknown tool: {name}"}

    # ═══ Web Tools ═══════════════════════════════════════════════════

    async def _browser_browse(self, input_str: str) -> dict:
        """LLM-driven browser: navigate, search, extract JS-rendered pages."""
        try:
            from ...bridge.registry import get_tool_registry; _browser = lambda: get_tool_registry().get("browser_agent")  # via bridge  # TODO(bridge): migrate to bridge.ToolRegistry  # TODO(bridge): migrate to bridge.ToolRegistry  # TODO(bridge): migrate to bridge.ToolRegistry
            args = self._parse_tool_args(input_str)
            url = args.get("url", "")
            task = args.get("task", input_str)
            agent = get_tool_registry().get("browser_agent")
            r = await agent.browse(url=url, task=task)
            return {
                "success": r.success,
                "url": r.url,
                "title": r.title,
                "items": r.items,
                "count": r.count,
                "method": r.method,
                "elapsed_ms": r.elapsed_ms,
                "error": r.error,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "source": "browser_browse"}

    async def _web_fetch(self, input_str: str) -> dict:
        """Fetch a static page via Scrapling Fetcher (TLS impersonation, HTTP/3)."""
        args = self._parse_tool_args(input_str)
        url = args.get("url", input_str.strip())
        page = _ScraplingFetcher.get(url, timeout=15, stealthy_headers=True)
        title = page.css("title::text").get() or ""
        clean = page.get_all_text(strip=True)[:8000] if hasattr(page, 'get_all_text') else (page.text or "")[:8000]
        links = []
        for a in page.css("a[href]"):
            href = a.attrib.get("href", "")
            if any(href.lower().endswith(e) for e in [".pdf", ".docx", ".xlsx", ".zip"]):
                links.append({"url": href, "title": (a.text or "").strip()[:80]})
        return {"success": True, "url": url, "title": title, "text": clean, "links": links[:20]}

    async def _browser_screenshot(self, input_str: str) -> dict:
        """Take screenshot of current browser page, return base64 for LLM analysis."""
        try:
            # browser_agent migrated to bridge.ToolRegistry
            import base64
            agent = get_tool_registry().get("browser_agent")
            result = await agent.screenshot()
            return {
                "success": result.get("success", False),
                "base64_preview": result.get("base64", "")[:200] + "...",
                "width": result.get("width", 0),
                "height": result.get("height", 0),
                "error": result.get("error", ""),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _browser_session(self, input_str: str, action: str) -> dict:
        """Manage persistent browser sessions: open / close."""
        try:
            # browser_agent migrated to bridge.ToolRegistry
            agent = get_tool_registry().get("browser_agent")
            if action == "open":
                args = self._parse_tool_args(input_str)
                url = args.get("url", "")
                result = await agent.session_open(url)
                return result
            elif action == "close":
                result = await agent.session_close()
                return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _browser_session_list(self) -> dict:
        """List active browser sessions."""
        try:
            agent = get_tool_registry().get("browser_agent")
            return agent.session_list()
        except Exception as e:
            return {"sessions": [], "error": str(e)}

    async def _browser_inject(self, input_str: str) -> str:
        """Lightweight WebView browser with JS injection bridge."""
        from ..capability.webview_agent import browser_inject
        parts = input_str.strip().split("\n", 1)
        url = parts[0].strip() if parts else ""
        task = parts[1].strip() if len(parts) > 1 else "extract"
        return await browser_inject(url, task)

    async def _api_search(self, input_str: str) -> dict:
        """Search registered APIs by keyword."""
        try:
            from ..treellm.api_map import get_api_map
            m = get_api_map()
            args = self._parse_tool_args(input_str)
            keyword = args.get("keyword", input_str.strip())
            results = m.search(keyword, max_results=5)
            return {
                "success": len(results) > 0,
                "keyword": keyword,
                "apis": results,
                "count": len(results),
            }
        except Exception as e:
            return {"success": False, "error": str(e), "source": "api_search"}

    @staticmethod
    def _parse_tool_args(input_str: str) -> dict:
        s = input_str.strip()
        if s.startswith("{"):
            try:
                import json
                return json.loads(s)
            except json.JSONDecodeError:
                pass
        return {"text": s}

    # ═══ Automation / DevOps Handlers ══════════════════════════════

    async def _system_health(self) -> dict:
        try:
            from ..core.system_health import get_system_health
            report = get_system_health().check()
            return {"success": True, "status": getattr(report, 'status', 'unknown'),
                    "overall_score": getattr(report, 'overall_score', 0),
                    "actors": getattr(report, 'actors', {}),
                    "actions": getattr(report, 'actions', [])}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _system_metrics(self) -> dict:
        try:
            from ..core.telemetry import get_telemetry
            t = get_telemetry()
            return {"success": True, "metrics": t.stats(), "prometheus": t.prometheus_metrics()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _cron_add(self, input_str: str) -> dict:
        try:
            from ..execution.cron_scheduler import get_scheduler
            parts = input_str.strip().split("|", 2)
            name = parts[0].strip() if len(parts) > 0 else "unnamed"
            schedule = parts[1].strip() if len(parts) > 1 else "daily 08:00"
            task = parts[2].strip() if len(parts) > 2 else input_str
            get_scheduler().add(name=name, schedule=schedule, prompt=task)
            return {"success": True, "name": name, "schedule": schedule, "task": task}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _cron_list(self) -> dict:
        try:
            from ..execution.cron_scheduler import get_scheduler
            jobs = get_scheduler().list()
            return {"success": True, "jobs": jobs, "count": len(jobs)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _cron_remove(self, input_str: str) -> dict:
        try:
            from ..execution.cron_scheduler import get_scheduler
            get_scheduler().remove(input_str.strip())
            return {"success": True, "removed": input_str.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _improve_scan(self) -> dict:
        try:
            from ..treellm.self_improver import get_self_improver
            si = get_self_improver()
            defects = si._scanner.scan() if hasattr(si, '_scanner') else []
            return {"success": True, "defects": defects[:20], "count": len(defects)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _improve_propose(self) -> dict:
        try:
            from ..treellm.self_improver import get_self_improver
            si = get_self_improver()
            proposals = si._proposer.propose() if hasattr(si, '_proposer') else []
            return {"success": True, "proposals": proposals[:10], "count": len(proposals)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _improve_apply(self, input_str: str) -> dict:
        try:
            from ..treellm.self_improver import get_self_improver
            si = get_self_improver()
            result = await si._implement(input_str.strip()) if hasattr(si, '_implement') else None
            return {"success": True, "applied": input_str.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _overnight_start(self, input_str: str) -> dict:
        try:
            from ...bridge.registry import get_tool_registry as _reg  # TODO(bridge): migrate to bridge.ToolRegistry  # TODO(bridge): migrate to bridge.ToolRegistry  # TODO(bridge): migrate to bridge.ToolRegistry
            ot = _reg().get("overnight_task")
            task_id = await ot.start(input_str.strip(), hub=None)
            return {"success": True, "task_id": task_id, "goal": input_str[:200]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _overnight_status(self) -> dict:
        try:
            from ...bridge.registry import get_tool_registry as _reg
            ot = _reg().get("overnight_task")
            tasks = ot.list_tasks() if hasattr(ot, 'list_tasks') else []
            return {"success": True, "tasks": tasks}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _overnight_cancel(self, input_str: str) -> dict:
        try:
            from ...bridge.registry import get_tool_registry as _reg
            ot = _reg().get("overnight_task")
            await ot.cancel(input_str.strip())
            return {"success": True, "cancelled": input_str.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _read_file(self, path: str) -> str:
        """Read file — VFS (LivingStore) is primary path, raw disk is sandboxed fallback."""
        try:
            p = Path(path).resolve()
            if not self._path_is_safe(p):
                return "Error: path outside allowed sandbox"
            return p.read_text(errors="replace")[:10000]
        except Exception as e:
            return f"Error: {e}"

    def _write_file(self, args: str) -> str:
        """Write file — VFS (LivingStore) is primary path, raw disk is sandboxed fallback."""
        parts = args.split("\n", 1)
        try:
            p = Path(parts[0].strip()).resolve()
            if not self._path_is_safe(p):
                return "Error: path outside allowed sandbox"
            content = parts[1] if len(parts) > 1 else ""
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} bytes to {parts[0].strip()}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _path_is_safe(p: Path) -> bool:
        cwd = Path.cwd().resolve()
        sandbox = cwd / ".livingtree"
        try:
            p.relative_to(cwd)
            return True
        except ValueError:
            pass
        try:
            p.relative_to(sandbox)
            return True
        except ValueError:
            return False


class SkillAdapter(CapabilityAdapter):
    """Adapter for skills (UnifiedSkillSystem, SkillFactory, SkillHub)."""

    def __init__(self):
        super().__init__(CapCategory.SKILL)

    async def discover(self) -> list[Capability]:
        caps = []
        try:
            from ..dna.unified_skill_system import get_skill_system
            uss = get_skill_system()
            for name, skill in uss._skills.items():
                cap = Capability(
                    id=f"skill:{name}", name=name, category=CapCategory.SKILL,
                    description=skill.description[:200],
                    params=[CapParam(name="task", type="string")],
                    handler=lambda task="", _n=name: {"skill": _n, "task": task, "status": "proposed"},
                    source="unified_skill_system",
                )
                caps.append(cap)
                self.register(cap)
        except Exception as e:
            logger.debug(f"SkillAdapter uss: {e}")

        try:
            from ...bridge.registry import get_tool_registry as _reg2  # TODO(bridge): migrate to bridge.ToolRegistry
            factory = _reg2().get("skill_factory")
            for name, skill in factory._skills.items():
                cap_id = f"skill:{name}"
                if cap_id not in self._caps:
                    skill_instance = factory._instances.get(name)
                    cap = Capability(
                        id=cap_id, name=name, category=CapCategory.SKILL,
                        description=getattr(skill, 'description', '')[:200],
                        params=[CapParam(name="input", type="object")],
                        handler=lambda input=None, _si=skill_instance, _n=name: _si.execute(input) if _si else {"skill": _n, "error": "not instantiated"},
                        source="skill_factory",
                    )
                    caps.append(cap)
                    self.register(cap)
        except Exception as e:
            logger.debug(f"SkillAdapter factory: {e}")
        return caps


class MCPAdapter(CapabilityAdapter):
    """Adapter for MCP tools (server, chrome, city, external MCP hosts).

    Discovers tools from:
    1. LivingTree's own MCP server (43 built-in tools) → **LocalToolBus direct invoke**
    2. External MCP servers (Parallel Search web_search/web_fetch, etc.) → subprocess fallback

    Local tools use LocalToolBus for zero-overhead direct Python invocation.
    External MCP hosts use subprocess-based JSON-RPC (100ms+ overhead).
    """

    def __init__(self):
        super().__init__(CapCategory.MCP)
        self._mcp_hosts: dict[str, Any] = {}
        self._local_bus = None

    async def discover(self) -> list[Capability]:
        caps = []
        try:
            from ..mcp.server import MCPServer, TOOLS as MCP_TOOLS
            from .local_tool_bus import get_local_tool_bus
            self._local_bus = get_local_tool_bus()
            for t in MCP_TOOLS:
                tool_name = t.get("name", "")
                handler = self._local_bus._registry.get(tool_name)
                if handler is None:
                    continue
                cap = Capability(
                    id=f"mcp:{tool_name}", name=tool_name,
                    category=CapCategory.MCP,
                    description=t.get("description", "")[:200],
                    handler=handler,
                    source="mcp_server",
                    cost_estimate={"seconds": 0.001, "tokens": 0},
                )
                caps.append(cap)
                self.register(cap)
        except Exception as e:
            logger.debug(f"MCPAdapter server: {e}")

        await self._discover_external_hosts(caps)
        return caps

    async def _discover_external_hosts(self, caps: list) -> None:
        """Connect to registered external MCP servers and register their tools."""
        from .mcp_host_client import (
            _SERVER_PRESETS, get_mcp_host, MCPHostClient,
        )

        for server_id, preset in _SERVER_PRESETS.items():
            try:
                host = await get_mcp_host(server_id, preset.get("command"),
                                           preset.get("args"))
                if host is None or not host.is_ready:
                    continue
                self._mcp_hosts[server_id] = host
                for tool_name, tool in host.tools.items():
                    cap_id = f"mcp:{server_id}:{tool_name}"
                    cap = Capability(
                        id=cap_id, name=tool_name,
                        category=CapCategory.MCP,
                        description=f"[{server_id}] {tool.description}"[:200],
                        params=[
                            CapParam(name=k, type=v.get("type", "string"),
                                      description=v.get("description", ""))
                            for k, v in tool.input_schema.get("properties", {}).items()
                        ],
                        handler=lambda _sid=server_id, _tn=tool_name, **kw:
                            self._invoke_mcp_host(_sid, _tn, kw),
                        source=server_id,
                    )
                    caps.append(cap)
                    self.register(cap)
                logger.info(f"MCPAdapter: connected to {server_id} "
                             f"({len(host.tools)} tools)")
            except Exception as e:
                logger.debug(f"MCPAdapter host [{server_id}]: {e}")

    async def _invoke_mcp_host(self, server_id: str, tool_name: str,
                                 params: dict) -> Any:
        """Invoke a tool on an external MCP host and return result text."""
        from .mcp_host_client import call_mcp_tool
        result = await call_mcp_tool(server_id, tool_name, **params)
        if result.success:
            return result.content
        return f"[mcp:{server_id}:{tool_name}] Error: {result.error}"

    async def shutdown(self) -> None:
        """Shutdown all external MCP host connections."""
        from .mcp_host_client import shutdown_all_hosts
        await shutdown_all_hosts()
        self._mcp_hosts.clear()


class RoleAdapter(CapabilityAdapter):
    """Adapter for expert roles (ExpertRoleManager, AgentRoles)."""

    ROLES = {
        "code_architect": "高级软件架构师,擅长系统设计和代码审查",
        "data_scientist": "数据科学家,擅长分析和建模",
        "devops_engineer": "DevOps工程师,擅长部署和运维",
        "security_expert": "安全专家,擅长安全审计和漏洞分析",
        "qa_engineer": "测试工程师,擅长质量保证和测试策略",
        "product_manager": "产品经理,擅长需求分析和优先级排序",
        "tech_writer": "技术文档撰写,擅长清晰准确的文档",
        "perception_analyst": "感知分析专家,擅长信息提取和上下文理解",
        "decision_synthesizer": "决策综合专家,擅长多维度权衡和最优解",
    }

    def __init__(self):
        super().__init__(CapCategory.ROLE)

    async def discover(self) -> list[Capability]:
        caps = []
        for name, desc in self.ROLES.items():
            cap = Capability(
                id=f"role:{name}", name=name, category=CapCategory.ROLE,
                description=desc,
                params=[CapParam(name="task", type="string", description="任务描述")],
                handler=lambda task="", _n=name, _d=desc: {"role": _n, "persona": _d, "task": task},
                source="capability_bus",
            )
            caps.append(cap)
            self.register(cap)
        return caps


class UserAdapter(CapabilityAdapter):
    """Adapter for user profiles (UserModel, PersonaMemory)."""

    def __init__(self):
        super().__init__(CapCategory.USER)

    async def discover(self) -> list[Capability]:
        caps = []
        try:
            from ..memory.user_model import get_user_model
            um = get_user_model()
            profile = um.inject_into_prompt() or ""
            cap = Capability(
                id="user:profile", name="profile", category=CapCategory.USER,
                description="当前用户画像和偏好",
                handler=lambda: {"profile": profile[:500]},
                source="user_model",
            )
            caps.append(cap)
            self.register(cap)
        except Exception:
            pass
        return caps


class LLMAdapter(CapabilityAdapter):
    """Adapter for LLM providers (TreeLLM, chat, stream)."""

    def __init__(self):
        super().__init__(CapCategory.LLM)
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            try:
                from .core import TreeLLM
                self._llm = TreeLLM()
            except Exception:
                pass
        return self._llm

    async def discover(self) -> list[Capability]:
        llm = self._get_llm()
        providers = list(llm._providers.keys()) if llm and llm._providers else []

        cap = Capability(
            id="llm:chat", name="chat", category=CapCategory.LLM,
            description=f"与AI对话 (可用提供商: {', '.join(providers[:5])})",
            params=[
                CapParam(name="messages", type="array", description="对话消息"),
                CapParam(name="provider", type="string", description="提供商名称", required=False),
            ],
            handler=lambda messages=None, provider="", _llm=llm: self._llm_chat(messages, provider, _llm),
            source="treellm",
        )
        self.register(cap)
        return [cap]

    async def _llm_chat(self, messages, provider: str, llm):
        if not llm or not messages:
            return {"error": "LLM not available"}
        result = await llm.chat(messages, provider=provider)
        return {"text": getattr(result, 'text', '') or str(result)}


class VFSAdapter(CapabilityAdapter):
    """Adapter for VFS (LivingStore + VirtualFS)."""

    def __init__(self):
        super().__init__(CapCategory.VFS)

    async def discover(self) -> list[Capability]:
        caps = []
        try:
            from .living_store import get_living_store
            store = get_living_store()
            ops = ["read", "write", "delete", "list", "move", "exists"]
            for op in ops:
                cap = Capability(
                    id=f"vfs:{op}", name=op, category=CapCategory.VFS,
                    description=f"VFS {op} 操作 (支持 /ram, /cache, /disk, /db, /config)",
                    params=[CapParam(name="path", type="string")] + (
                        [CapParam(name="data", type="string")] if op == "write" else []
                    ),
                    handler=lambda path="", data=None, _op=op, _store=store: self._vfs_op(_op, path, data, _store),
                    source="living_store",
                )
                caps.append(cap)
                self.register(cap)
        except Exception as e:
            logger.debug(f"VFSAdapter: {e}")
        return caps

    async def _vfs_op(self, op: str, path: str, data, store) -> Any:
        if op == "read":
            text = await store.read_text(path)
            return {"content": text[:5000] if text else ""}
        if op == "write":
            await store.write_text(path, str(data)[:100000])
            return {"written": len(str(data))}
        if op == "delete":
            return {"deleted": await store.delete(path)}
        if op == "list":
            items = await store.list(path)
            return {"items": items[:100]}
        if op == "move":
            dst = str(data) if data else "/ram/tmp/moved"
            return {"moved": await store.move(path, dst)}
        if op == "exists":
            return {"exists": await store.exists(path)}
        return {"error": f"Unknown op: {op}"}


# ═══ CapabilityBus ═════════════════════════════════════════════════


class CapabilityBus:
    """Unified capability registry and invocation bus.

    Single entry point for ALL digital lifeform capabilities.
    Auto-discovers from existing registries on first access.
    """

    _instance: Optional["CapabilityBus"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "CapabilityBus":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = CapabilityBus()
        return cls._instance

    def __init__(self):
        self._adapters: dict[CapCategory, CapabilityAdapter] = {
            CapCategory.TOOL: ToolAdapter(),
            CapCategory.SKILL: SkillAdapter(),
            CapCategory.MCP: MCPAdapter(),
            CapCategory.ROLE: RoleAdapter(),
            CapCategory.USER: UserAdapter(),
            CapCategory.LLM: LLMAdapter(),
            CapCategory.VFS: VFSAdapter(),
        }
        self._discovered = False
        self._invoke_count = 0

    async def _ensure_discovered(self):
        if self._discovered:
            return
        tasks = [adapter.discover() for adapter in self._adapters.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._discovered = True
        total = sum(len(a.list_all()) for a in self._adapters.values())
        logger.info(f"CapabilityBus: discovered {total} capabilities")

    # ── Public API ─────────────────────────────────────────────────

    async def invoke(self, cap_id: str, **params) -> Any:
        """Invoke any capability by its unified ID. E.g., 'tool:web_search'."""
        await self._ensure_discovered()
        self._invoke_count += 1
        t0 = __import__('time').time()
        for adapter in self._adapters.values():
            cap = adapter.get(cap_id)
            if cap:
                result = await adapter.invoke(cap_id, **params)
                # ── Closed loop: tool feedback → update weights ──
                try:
                    success = not isinstance(result, dict) or "error" not in str(result).lower()[:100]
                    if cap:
                        cap.is_available = success and cap.is_available
                except Exception:
                    pass
                # ── Recording capture: tool/skill/mcp call ──
                try:
                    from .recording_engine import get_recording_engine, RecordLayer
                    get_recording_engine().capture(
                        RecordLayer.TOOL, "tool_call",
                        params=params, capability=cap_id,
                        result=result, render="table" if isinstance(result, (list, dict)) else "card",
                        duration_ms=(__import__('time').time() - t0) * 1000,
                    )
                except Exception:
                    pass
                # ── PromptEngine feedback ──
                try:
                    from .prompt_engine import get_prompt_engine, get_prompt_compiler
                    engine = get_prompt_engine()
                    success = not isinstance(result, dict) or "error" not in str(result)
                    engine.feedback(cap_id, params, result, success)
                    # Also update compiler
                    compiler = get_prompt_compiler()
                    quality = 0.8 if success else 0.3
                    compiler.feedback(cap_id, quality)
                except Exception:
                    pass
                return result
        return {"error": f"Capability not found: {cap_id}"}

    async def list_all(self) -> list[dict]:
        """List all capabilities across all categories."""
        await self._ensure_discovered()
        result = []
        for adapter in self._adapters.values():
            for cap in adapter.list_all():
                result.append({
                    "id": cap.id, "name": cap.name,
                    "category": cap.category.value,
                    "description": cap.description[:200],
                    "available": cap.is_available,
                    "source": cap.source,
                })
        return result

    async def list(self, category: str) -> list[dict]:
        """List capabilities in a specific category."""
        await self._ensure_discovered()
        try:
            cat = CapCategory(category)
        except ValueError:
            return []
        adapter = self._adapters.get(cat)
        if not adapter:
            return []
        return [{
            "id": c.id, "name": c.name, "description": c.description[:200],
            "available": c.is_available, "source": c.source,
        } for c in adapter.list_all()]

    async def prompt_fragment(self, categories: list[str] = None) -> str:
        """Generate a system prompt fragment listing available capabilities."""
        await self._ensure_discovered()
        cats = [CapCategory(c) for c in categories] if categories else list(self._adapters.keys())
        lines = ["Discovered dynamic tools:"]
        for cat in cats:
            adapter = self._adapters.get(cat)
            if not adapter:
                continue
            for cap in adapter.list_all()[:10]:
                lines.append(f"  {cap.prompt_fragment()}")
        return "\n".join(lines)

    def prompt_fragment_sync(self, categories: list[str] = None) -> str:
        """Synchronous version for use in core.py chat() prompt injection."""
        if not self._discovered:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._ensure_discovered())
                else:
                    loop.run_until_complete(self._ensure_discovered())
            except RuntimeError:
                try:
                    asyncio.run(self._ensure_discovered())
                except RuntimeError:
                    pass
        cats = [CapCategory(c) for c in categories] if categories else list(self._adapters.keys())
        lines = []
        for cat in cats:
            adapter = self._adapters.get(cat)
            if not adapter:
                continue
            count = 0
            for cap in adapter.list_all():
                if count >= 8:
                    break
                lines.append(f"  {cap.prompt_fragment()}")
                count += 1
        return "\n".join(lines) if lines else ""

    async def invoke_all(self, cap_id: str, params_list: list[dict]) -> list[Any]:
        """Batch invoke the same capability with multiple param sets."""
        tasks = [self.invoke(cap_id, **p) for p in params_list]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def register(self, cap: Capability) -> None:
        adapter = self._adapters.get(cap.category)
        if adapter:
            adapter.register(cap)

    def stats(self) -> dict:
        return {
            "invocations": self._invoke_count,
            "categories": {
                cat.value: len(adapter.list_all())
                for cat, adapter in self._adapters.items()
            },
        }


# ═══ Singleton ════════════════════════════════════════════════════


def get_capability_bus() -> CapabilityBus:
    return CapabilityBus.instance()


__all__ = [
    "CapabilityBus", "Capability", "CapabilityAdapter",
    "CapCategory", "CapParam",
    "ToolAdapter", "SkillAdapter", "MCPAdapter",
    "RoleAdapter", "UserAdapter", "LLMAdapter", "VFSAdapter",
    "get_capability_bus",
]
