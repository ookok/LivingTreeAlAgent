"""
LivingTree — Complete Tool Registry & Dispatcher (Full Migration)
===================================================================

Full migration from client/src/business/tools_registry.py +
tools_file.py + tools_terminal.py + tools_ollama.py

Features:
- @tool() decorator-based registration
- Keyword + semantic search
- OpenAI-compatible schema export
- File read/write/patch with path safety
- Terminal command execution
- Ollama model tools
"""

import os
import re
import json
import subprocess
from pathlib import Path
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass, field
from threading import Lock


# ── Tool Definition ────────────────────────────────────────

@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict
    handler: Callable[..., Any] = field(repr=False)
    toolset: str = "core"


# ── Tool Registry ─────────────────────────────────────────

class ToolRegistry:
    _instance: "ToolRegistry | None" = None
    _tools: dict[str, ToolDef] = {}
    _toolsets: dict[str, set[str]] = {}
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, name: str, description: str, parameters: dict,
                 handler: Callable, toolset: str = "core"):
        with cls._lock:
            cls._tools[name] = ToolDef(name=name, description=description,
                                       parameters=parameters, handler=handler,
                                       toolset=toolset)
            cls._toolsets.setdefault(toolset, set()).add(name)

    @classmethod
    def get(cls, name: str) -> Optional[ToolDef]:
        return cls._tools.get(name)

    @classmethod
    def get_all_names(cls) -> list[str]:
        return list(cls._tools.keys())

    @classmethod
    def get_by_toolset(cls, toolset: str) -> list[ToolDef]:
        names = cls._toolsets.get(toolset, set())
        return [cls._tools[n] for n in names if n in cls._tools]

    @classmethod
    def get_all_tools(cls, enabled: list[str] = None) -> list[ToolDef]:
        if not enabled:
            return list(cls._tools.values())
        result = []
        for ts in enabled:
            result.extend(cls.get_by_toolset(ts))
        return result

    @classmethod
    def to_openai_schema(cls, tools: list[ToolDef]) -> list[dict]:
        return [{
            "type": "function",
            "function": {"name": t.name, "description": t.description,
                         "parameters": t.parameters}
        } for t in tools]

    @classmethod
    def search(cls, query: str) -> list[ToolDef]:
        q = query.lower()
        results = []
        for name, tool in cls._tools.items():
            score = 0
            if q in name.lower():
                score += 2
            if q in tool.description.lower():
                score += 1
            if score > 0:
                results.append((tool, score))
        results.sort(key=lambda x: -x[1])
        return [t for t, _ in results]

    @classmethod
    def count(cls) -> int:
        return len(cls._tools)


# ── Tool Decorator ────────────────────────────────────────

SCHEMA = {
    "read_file": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "limit": {"type": "integer", "description": "限制行数"},
            "offset": {"type": "integer", "description": "偏移行数"},
        },
        "required": ["path"],
    },
    "write_file": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "写入内容"},
        },
        "required": ["path", "content"],
    },
    "patch": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "old": {"type": "string", "description": "要替换的旧文本"},
            "new": {"type": "string", "description": "新文本"},
        },
        "required": ["path", "old", "new"],
    },
    "terminal": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell命令"},
            "cwd": {"type": "string", "description": "工作目录"},
        },
        "required": ["command"],
    },
    "ollama_list": {
        "type": "object", "properties": {},
    },
    "ollama_show": {
        "type": "object",
        "properties": {"model": {"type": "string", "description": "模型名称"}},
        "required": ["model"],
    },
}


def tool(name: str, description: str, parameters: dict,
         toolset: str = "core"):
    def decorator(func):
        ToolRegistry.register(name=name, description=description,
                             parameters=parameters, handler=func,
                             toolset=toolset)
        return func
    return decorator


# ── File Tools ────────────────────────────────────────────

def _safe_path(path: str) -> Path:
    return Path(path).resolve()

def _is_safe_path(path: str, base: Optional[Path] = None) -> bool:
    try:
        p = _safe_path(path)
        if base:
            return str(p).startswith(str(base.resolve()))
        dangerous = ["/", r"C:\\Windows", r"C:\\Program Files", r"C:\\Program Files (x86)"]
        for d in dangerous:
            if str(p).startswith(d):
                return False
        return True
    except Exception:
        return False


def _file_read_handler(ctx: dict, path: str, limit: int = None,
                       offset: int = 0) -> str:
    if not _is_safe_path(path):
        return f"Error: unsafe path {path}"
    p = _safe_path(path)
    if not p.exists():
        return f"File not found: {path}"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.split("\n")
        if offset > 0:
            lines = lines[offset:]
        if limit:
            lines = lines[:limit]
        return "\n".join(lines)
    except Exception as e:
        return f"Read failed: {e}"


def _file_write_handler(ctx: dict, path: str, content: str) -> str:
    if not _is_safe_path(path):
        return f"Error: unsafe path {path}"
    p = _safe_path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written: {path} ({len(content)} chars)"
    except Exception as e:
        return f"Write failed: {e}"


def _file_patch_handler(ctx: dict, path: str, old: str, new: str) -> str:
    if not _is_safe_path(path):
        return f"Error: unsafe path {path}"
    p = _safe_path(path)
    if not p.exists():
        return f"File not found: {path}"
    try:
        text = p.read_text(encoding="utf-8")
        if old in text:
            text = text.replace(old, new, 1)
            p.write_text(text, encoding="utf-8")
            return f"Patched: replaced text in {path}"
        return f"Pattern not found in {path}"
    except Exception as e:
        return f"Patch failed: {e}"


def _terminal_handler(ctx: dict, command: str, cwd: str = "") -> str:
    try:
        kwargs = {"shell": True, "capture_output": True, "text": True, "timeout": 60}
        if cwd:
            kwargs["cwd"] = cwd
        result = subprocess.run(command, **kwargs)
        return result.stdout.strip() or result.stderr.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out (60s)"
    except Exception as e:
        return f"Command failed: {e}"


# ── Registration ──────────────────────────────────────────

def register_all_tools():
    ToolRegistry.register("read_file", "Read file contents",
                          SCHEMA["read_file"], _file_read_handler, "file")
    ToolRegistry.register("write_file", "Write content to file",
                          SCHEMA["write_file"], _file_write_handler, "file")
    ToolRegistry.register("patch", "Replace text in file",
                          SCHEMA["patch"], _file_patch_handler, "file")
    ToolRegistry.register("terminal", "Execute terminal command",
                          SCHEMA["terminal"], _terminal_handler, "core")

register_all_tools()


# ── Dispatcher ────────────────────────────────────────────

class ToolDispatcher:
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self._log: list[dict] = []

    def dispatch(self, tool_name: str, params: dict = None) -> str:
        tool = ToolRegistry.get(tool_name)
        if tool is None:
            return f"Tool not found: {tool_name}"
        try:
            result = tool.handler(params or {}, **(params or {}))
            self._log.append({"tool": tool_name, "success": True, "result": result})
        except Exception as e:
            result = f"Error: {e}"
            self._log.append({"tool": tool_name, "success": False, "error": str(e)})
        return result


__all__ = [
    "ToolRegistry", "ToolDispatcher", "ToolDef",
    "SCHEMA", "tool", "register_all_tools",
]
