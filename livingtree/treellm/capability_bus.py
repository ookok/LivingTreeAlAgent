"""CapabilityBus — Unified interface for ALL digital lifeform capabilities.

Every capability — tool, skill, MCP, expert role, user profile, LLM, VFS —
exposes a single unified interface. The CapabilityBus auto-discovers and
registers all capabilities from existing registries.

Unified invocation:
    bus = get_capability_bus()
    result = await bus.invoke("tool:web_search", query="AI papers")
    result = await bus.invoke("skill:tabular_reason", data={...})
    result = await bus.invoke("mcp:chrome_screenshot", url="...")
    result = await bus.invoke("role:code_architect", task="...")
    result = await bus.invoke("user:profile", user_id="perpetual")
    result = await bus.invoke("llm:chat", messages=[...])
    result = await bus.invoke("vfs:read", path="/disk/main.py")

Discovery:
    all_caps = bus.list_all()
    tools    = bus.list("tool")
    skills   = bus.list("skill")

This is the single entry point that LLMs, frontends, and all other subsystems
use to discover and invoke capabilities.
"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger


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
            from ..capability.tool_market import get_tool_market
            market = get_tool_market()
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
                "web_search": ("Search the internet", "query"),
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

    def _read_file(self, path: str) -> str:
        try:
            return Path(path).resolve().read_text(errors="replace")[:10000]
        except Exception as e:
            return f"Error: {e}"

    def _write_file(self, args: str) -> str:
        try:
            parts = args.split("\n", 1)
            p = Path(parts[0].strip()).resolve()
            content = parts[1] if len(parts) > 1 else ""
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"Wrote {len(content)} bytes"
        except Exception as e:
            return f"Error: {e}"


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
            from ..capability.skill_factory import get_skill_factory
            factory = get_skill_factory()
            for name, skill in factory._skills.items():
                cap_id = f"skill:{name}"
                if cap_id not in self._caps:
                    cap = Capability(
                        id=cap_id, name=name, category=CapCategory.SKILL,
                        description=getattr(skill, 'description', '')[:200],
                        params=[CapParam(name="input", type="object")],
                        handler=lambda input=None, _f=factory, _n=name: _f.execute_skill(_n, input),
                        source="skill_factory",
                    )
                    caps.append(cap)
                    self.register(cap)
        except Exception as e:
            logger.debug(f"SkillAdapter factory: {e}")
        return caps


class MCPAdapter(CapabilityAdapter):
    """Adapter for MCP tools (server, chrome, city)."""

    def __init__(self):
        super().__init__(CapCategory.MCP)

    async def discover(self) -> list[Capability]:
        caps = []
        try:
            from ..mcp.server import MCPServer
            for t in MCPServer.TOOLS:
                cap = Capability(
                    id=f"mcp:{t.get('name','')}", name=t.get('name', ''),
                    category=CapCategory.MCP,
                    description=t.get('description', '')[:200],
                    handler=t.get('handler'),
                    source="mcp_server",
                )
                caps.append(cap)
                self.register(cap)
        except Exception as e:
            logger.debug(f"MCPAdapter server: {e}")
        return caps


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

    @classmethod
    def instance(cls) -> "CapabilityBus":
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
        lines = ["可用能力:"]
        for cat in cats:
            adapter = self._adapters.get(cat)
            if not adapter:
                continue
            for cap in adapter.list_all()[:10]:
                lines.append(f"  {cap.prompt_fragment()}")
        return "\n".join(lines)

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

_bus: Optional[CapabilityBus] = None


def get_capability_bus() -> CapabilityBus:
    global _bus
    if _bus is None:
        _bus = CapabilityBus()
    return _bus


__all__ = [
    "CapabilityBus", "Capability", "CapabilityAdapter",
    "CapCategory", "CapParam",
    "ToolAdapter", "SkillAdapter", "MCPAdapter",
    "RoleAdapter", "UserAdapter", "LLMAdapter", "VFSAdapter",
    "get_capability_bus",
]
