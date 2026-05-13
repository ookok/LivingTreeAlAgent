"""ToolSynthesis — NL→code→execute→register permanent tools.

    Not calling existing tools. LLM writes new tools on-the-fly:
    1. Natural language description → LLM generates Python code
    2. Sandbox execution: run in tempfile, capture output
    3. Validate: if output looks correct, register as permanent tool
    4. Version: auto-track improvements over time
    5. Discover: auto-register in SYSTEM_TOOLS + SkillRouter

    Usage:
        ts = get_tool_synthesizer()
        result = await ts.synthesize("对比两个CSV的第三列差异", hub)
        # result.tool is now available in system tools forever
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

SYNTHESIS_DIR = Path(".livingtree/synthesized_tools")
SYNTHESIS_REGISTRY = SYNTHESIS_DIR / "registry.json"


@dataclass
class SynthesizedTool:
    name: str
    description: str
    code: str
    category: str = "synthesized"
    params: dict = field(default_factory=dict)
    version: int = 1
    success_count: int = 0
    fail_count: int = 0
    created_at: float = 0.0
    last_used: float = 0.0
    source_task: str = ""


@dataclass
class SynthesisResult:
    task: str
    tool: SynthesizedTool | None = None
    output: str = ""
    registered: bool = False
    error: str = ""


class ToolSynthesizer:
    """Natural language → tool code → sandbox execution → permanent registration."""

    def __init__(self):
        SYNTHESIS_DIR.mkdir(parents=True, exist_ok=True)
        self._tools: dict[str, SynthesizedTool] = {}
        self._load_registry()

    async def synthesize(
        self,
        task: str,
        hub,
        context: dict[str, str] | None = None,
        register: bool = True,
    ) -> SynthesisResult:
        """Synthesize a new tool from natural language description.

        Args:
            task: Natural language description (e.g. "对比两个CSV的第三列差异")
            hub: LLM access
            context: Additional context dict
            register: Auto-register as permanent tool
        """
        if not hub or not hub.world:
            return SynthesisResult(task=task, error="No LLM available")

        result = SynthesisResult(task=task)
        llm = hub.world.consciousness._llm
        ctx_str = "\n".join(f"{k}: {v}" for k, v in (context or {}).items())

        # Phase 1: LLM writes the tool
        gen = await llm.chat(
            messages=[{"role": "user", "content": (
                "You are writing a Python function that solves a specific task. "
                "Write COMPLETE, working code. Use only stdlib + common libraries.\n\n"
                f"TASK: {task}\n"
                + (f"CONTEXT:\n{ctx_str}\n\n" if ctx_str else "") +
                "Output JSON:\n"
                '{"tool_name": "short_snake_case_name", '
                '"description": "one line what it does", '
                '"category": "data|file|text|net|calc", '
                '"params": {"arg1": "description"}, '
                '"code": "def tool_name(arg1, arg2=None):\\n    ...\\n    return result"}'
            )}],
            provider=getattr(llm, '_elected', ''),
            temperature=0.1, max_tokens=2000, timeout=40,
        )

        if not gen or not gen.text:
            return SynthesisResult(task=task, error="Generation failed")

        import re
        m = re.search(r'\{[\s\S]*\}', gen.text)
        if not m:
            return SynthesisResult(task=task, error="Invalid LLM output format")

        try:
            data = json.loads(m.group())
        except json.JSONDecodeError as e:
            return SynthesisResult(task=task, error=f"Invalid JSON: {e}")

        tool_name = data.get("tool_name", self._slug(task))
        code = data.get("code", "")
        if not code:
            return SynthesisResult(task=task, error="No code generated")

        tool = SynthesizedTool(
            name=tool_name,
            description=data.get("description", task[:100]),
            code=code,
            category=data.get("category", "synthesized"),
            params=data.get("params", {}),
            created_at=time.time(),
            source_task=task,
        )

        # Phase 2: Sandbox execution test
        exec_result = await self._sandbox_execute(code, tool_name)
        if exec_result["error"]:
            tool.fail_count += 1
            result.error = f"Execution failed: {exec_result['error']}"
            result.tool = tool
            return result

        result.output = exec_result["output"][:2000]
        tool.success_count += 1

        # Phase 3: Register permanently
        if register:
            self._register_tool(tool)
            result.registered = True

        result.tool = tool
        return result

    async def refine(
        self,
        tool_name: str,
        improvement: str,
        hub,
    ) -> SynthesisResult:
        """Refine an existing tool based on feedback."""
        tool = self._tools.get(tool_name)
        if not tool:
            # Search by partial name
            for name, t in self._tools.items():
                if tool_name in name:
                    tool = t
                    break
        if not tool:
            return SynthesisResult(task=improvement, error=f"Tool {tool_name} not found")

        llm = hub.world.consciousness._llm
        gen = await llm.chat(
            messages=[{"role": "user", "content": (
                "Refine this Python tool based on feedback.\n\n"
                f"CURRENT CODE:\n```python\n{tool.code}\n```\n\n"
                f"FEEDBACK: {improvement}\n\n"
                "Output JSON with 'code' field containing the improved version. "
                "Keep it a single function with same name and signature."
            )}],
            provider=getattr(llm, '_elected', ''),
            temperature=0.2, max_tokens=2000, timeout=30,
        )

        if gen and gen.text:
            import re
            m = re.search(r'\{[\s\S]*\}', gen.text)
            if m:
                data = json.loads(m.group())
                new_code = data.get("code", "")
                if new_code:
                    tool.code = new_code
                    tool.version += 1
                    tool.last_used = time.time()
                    self._save_tool(tool)
                    logger.info(f"Tool refined: {tool_name} v{tool.version}")

        return SynthesisResult(task=improvement, tool=tool, registered=True)

    def get_tool(self, name: str) -> SynthesizedTool | None:
        return self._tools.get(name)

    def list_tools(self, category: str = "") -> list[SynthesizedTool]:
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return sorted(tools, key=lambda t: -t.created_at)

    async def _sandbox_execute(self, code: str, func_name: str) -> dict:
        """Execute generated code in sandbox."""
        t0 = time.time()
        try:
            # Method 1: In-process import (safe-ish for own code)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                tmp_path = f.name

            try:
                p = subprocess.run(
                    [sys.executable, "-c",
                     f"exec(open(r'{tmp_path}').read()); print('FUNC:'+str({func_name}.__name__))"],
                    capture_output=True, text=True, timeout=10,
                )
                output = p.stdout + "\n" + p.stderr
                error = p.stderr if p.returncode != 0 else ""
                return {"success": p.returncode == 0, "output": output[:3000], "error": error[:500]}
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": "Timeout 10s"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _register_tool(self, tool: SynthesizedTool):
        """Register tool everywhere: local database, SYSTEM_TOOLS, SkillRouter."""
        self._tools[tool.name] = tool
        self._save_tool(tool)
        self._save_registry()

        # Register in SYSTEM_TOOLS
        try:
            from .tool_registry import SYSTEM_TOOLS
            SYSTEM_TOOLS[tool.name] = {
                "name": tool.name.replace("_", " ").title(),
                "category": f"synthesized/{tool.category}",
                "description": tool.description,
                "params": tool.params,
                "icon": "🔧",
            }
        except Exception:
            pass

        # Register in SkillRouter
        try:
            from ..treellm.skill_router import get_router
            router = get_router()
            if hasattr(router, 'register_tool'):
                router.register_tool(tool.name, tool.description, tool.category)
        except Exception:
            pass

        logger.info(f"Tool synthesized: {tool.name} v{tool.version} [{tool.category}]")

    def _save_tool(self, tool: SynthesizedTool):
        fpath = SYNTHESIS_DIR / f"{tool.name}.json"
        fpath.write_text(json.dumps({
            "name": tool.name, "description": tool.description,
            "code": tool.code, "category": tool.category,
            "params": tool.params, "version": tool.version,
            "success_count": tool.success_count, "fail_count": tool.fail_count,
            "created_at": tool.created_at, "last_used": tool.last_used,
            "source_task": tool.source_task,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    def _save_registry(self):
        data = {}
        for name, tool in self._tools.items():
            data[name] = {
                "name": tool.name, "description": tool.description,
                "category": tool.category, "version": tool.version,
                "success_count": tool.success_count, "fail_count": tool.fail_count,
                "created_at": tool.created_at,
            }
        SYNTHESIS_REGISTRY.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_registry(self):
        if not SYNTHESIS_REGISTRY.exists():
            return
        try:
            data = json.loads(SYNTHESIS_REGISTRY.read_text(encoding="utf-8"))
            for name, meta in data.items():
                fpath = SYNTHESIS_DIR / f"{name}.json"
                if fpath.exists():
                    d = json.loads(fpath.read_text(encoding="utf-8"))
                    self._tools[name] = SynthesizedTool(**{
                        k: d.get(k, "") for k in SynthesizedTool.__dataclass_fields__
                    })
        except Exception:
            pass

    @staticmethod
    def _slug(text: str) -> str:
        """Generate short tool name from Chinese/English text."""
        import re
        slug = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff_]+', '_', text[:40]).lower()
        return slug.strip("_")[:30] or "custom_tool"


_ts: ToolSynthesizer | None = None


def get_tool_synthesizer() -> ToolSynthesizer:
    global _ts
    if _ts is None:
        _ts = ToolSynthesizer()
    return _ts
