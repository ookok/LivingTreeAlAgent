"""TreeOrchestrator — Unified architecture controller.

Single entry point that routes ALL data through the four unified layers:

  输入 (LivingInputBus)  →  any device → canonical LivingInput
  能力 (CapabilityBus)   →  any action → unified invoke
  存储 (LivingStore)     →  any storage → liquid/solid auto-tier
  输出 (LivingRenderer)  →  any format → capability-probed rendering

TreeLLM is the brain; TreeOrchestrator is the nervous system that connects
all organs through unified interfaces. Every request flows:

  Input → TreeLLM.elect → TreeLLM.chat/stream → Tool calls → CapabilityBus
                                                    ↓
                                              VFS ops → LivingStore
                                                    ↓
                                              Output → LivingRenderer
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class OrchestratedRequest:
    """A fully-processed request through all unified layers."""
    input_id: str
    provider: str = ""
    result: Any = None
    tool_calls: int = 0
    vfs_ops: int = 0
    capabilities_used: list[str] = field(default_factory=list)
    render_level: str = "rich"
    latency_ms: float = 0.0
    error: str = ""


class TreeOrchestrator:
    """Unified architecture controller — routes everything through unified layers."""

    _instance: Optional["TreeOrchestrator"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "TreeOrchestrator":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = TreeOrchestrator()
        return cls._instance

    def __init__(self):
        self._requests = 0
        self._tool_invocations = 0
        self._vfs_operations = 0

    # ── Main Pipeline ──────────────────────────────────────────────

    async def process(
        self, raw_input: Any, source: str = "web",
        hub: Any = None, request: Any = None,
    ) -> OrchestratedRequest:
        """Process a request through ALL unified layers.

        This is THE entry point. Every input flows through here.
        """
        t0 = time.time()
        req = OrchestratedRequest(input_id=f"req_{int(t0*1000)}")
        self._requests += 1

        try:
            # ═══ Layer 1: Input Normalization ═══
            inp = await self._normalize_input(raw_input, source, request)

            # ═══ Layer 2: Context Enrichment (ContextMoE memory) ═══
            message = await self._enrich_context(inp, hub)

            # ═══ Layer 3: LLM Routing + Execution ═══
            result, provider, tool_count = await self._route_and_execute(
                message, inp, hub,
            )
            req.provider = provider
            req.tool_calls = tool_count
            req.result = result

            # ═══ Layer 4: Output Rendering ═══
            req.render_level = self._determine_render_level(request)

        except Exception as e:
            req.error = str(e)[:500]
            logger.error(f"TreeOrchestrator: {e}")

        req.latency_ms = (time.time() - t0) * 1000
        return req

    # ── Layer 1: Input ══════════════════════════════════════════════

    async def _normalize_input(self, raw: Any, source: str, request: Any) -> Any:
        """Normalize raw input through LivingInputBus → canonical LivingInput."""
        try:
            from .living_input_bus import get_living_input_bus, InputSource
            bus = get_living_input_bus()
            source_enum = getattr(InputSource, source.upper(), InputSource.WEB) if hasattr(InputSource, source.upper()) else InputSource.WEB
            return await bus.normalize_and_route(source_enum, request or raw, None, return_input_only=True)
        except Exception:
            # Fallback: raw text
            from .living_input_bus import LivingInput, InputSource
            inp = LivingInput(source=InputSource.WEB)
            inp.text = str(raw)[:100000] if raw else ""
            return inp

    async def _enrich_context(self, inp: Any, hub: Any) -> str:
        """Enrich input with ContextMoE memory."""
        message = getattr(inp, 'text', str(inp)) if inp else ""
        if not message:
            return ""

        try:
            from .context_moe import get_context_moe
            moe = get_context_moe()
            task_type = getattr(inp, 'task_type', 'general') if hasattr(inp, 'task_type') else 'general'
            result = await moe.query(message, task_type)
            enriched = moe.build_enriched_message(message, result)
            if enriched != message:
                return enriched
        except Exception:
            pass
        return message

    # ── Layer 3: LLM + Tools ════════════════════════════════════════

    async def _route_and_execute(
        self, message: str, inp: Any, hub: Any,
    ) -> tuple[Any, str, int]:
        """Route through TreeLLM with unified tool/capability execution."""
        if not message:
            return None, "", 0

        provider = ""
        tool_count = 0
        result = None

        try:
            from .core import TreeLLM
            llm = TreeLLM()

            # Election
            try:
                provider = await llm.smart_route(message, task_type=getattr(inp, 'task_type', 'general') if hasattr(inp, 'task_type') else 'general')
            except Exception:
                pass

            # Chat with tools enabled
            kwargs = {
                "tools": True,
                "task_type": getattr(inp, 'task_type', 'general') if hasattr(inp, 'task_type') else 'general',
            }
            if hasattr(inp, 'system_prompt') and inp.system_prompt:
                kwargs["system_prompt"] = inp.system_prompt

            messages = [{"role": "user", "content": message}]
            if hasattr(inp, 'files') and inp.files:
                file_context = self._build_file_context(inp.files)
                messages.insert(0, {"role": "system", "content": file_context})

            result = await llm.chat(messages, provider=provider, **kwargs)

            # Count tool invocations via CapabilityBus
            tool_count = self._tool_invocations

        except Exception as e:
            logger.debug(f"TreeOrchestrator route: {e}")
            # Fallback through hub
            if hub:
                result = await hub.chat(message)

        return result, provider, tool_count

    # ── Layer 4: Output ═════════════════════════════════════════════

    def _determine_render_level(self, request: Any) -> str:
        """Determine rendering level based on client capabilities."""
        try:
            from .living_renderer import get_living_renderer
            renderer = get_living_renderer()
            caps = renderer.probe(request)
            return caps.max_level.name.lower() if hasattr(caps.max_level, 'name') else "rich"
        except Exception:
            return "rich"

    # ── Helpers ═════════════════════════════════════════════════════

    def _build_file_context(self, files: list) -> str:
        """Build context from file payloads for LLM prompt."""
        lines = ["[附带文件]"]
        for f in files[:10]:
            name = getattr(f, 'name', 'unknown')
            size = getattr(f, 'size_bytes', 0)
            content = getattr(f, 'content', '')
            lines.append(f"  {name} ({size}B)")
            if content and size < 5000:
                lines.append(f"  --- {name} ---\n{content[:2000]}")
        return "\n".join(lines)

    # ── Capability Shortcut ─────────────────────────────────────────

    async def invoke_capability(self, cap_id: str, **params) -> Any:
        """Shortcut to invoke any capability through the unified bus."""
        try:
            from .capability_bus import get_capability_bus
            return await get_capability_bus().invoke(cap_id, **params)
        except Exception as e:
            return {"error": str(e)}

    async def list_capabilities(self, category: str = "") -> list[dict]:
        """Shortcut to list capabilities."""
        try:
            from .capability_bus import get_capability_bus
            bus = get_capability_bus()
            return await bus.list(category) if category else await bus.list_all()
        except Exception:
            return []

    # ── VFS Shortcut ────────────────────────────────────────────────

    async def vfs_read(self, path: str) -> str:
        try:
            from .living_store import get_living_store
            text = await get_living_store().read_text(path)
            return text or ""
        except Exception as e:
            return f"[vfs error: {e}]"

    async def vfs_write(self, path: str, data: str) -> bool:
        try:
            from .living_store import get_living_store
            return await get_living_store().write_text(path, data)
        except Exception:
            return False

    # ── Render Shortcut ─────────────────────────────────────────────

    async def render_output(self, data: Any, request: Any = None,
                            format: str = "auto") -> str:
        """Render data through capability-probing renderer."""
        try:
            from .living_renderer import get_living_renderer
            renderer = get_living_renderer()
            caps = renderer.probe(request)
            result = renderer.render(data, caps, format=format)
            return result.content
        except Exception:
            return str(data)[:5000]

    # ── Stats ───────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "requests": self._requests,
            "tool_invocations": self._tool_invocations,
            "vfs_operations": self._vfs_operations,
        }


# ═══ Singleton ════════════════════════════════════════════════════

_orchestrator: Optional[TreeOrchestrator] = None
_orchestrator_lock = threading.Lock()


def get_tree_orchestrator() -> TreeOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        with _orchestrator_lock:
            if _orchestrator is None:
                _orchestrator = TreeOrchestrator()
    return _orchestrator


__all__ = ["TreeOrchestrator", "OrchestratedRequest", "get_tree_orchestrator"]
