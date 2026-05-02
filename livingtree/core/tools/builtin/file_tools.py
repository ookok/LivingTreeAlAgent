"""
文件搜索与操作工具
"""

import os
import re
import fnmatch
from pathlib import Path
from typing import Any

from ..registry import ToolRegistry


def _safe_path(path: str) -> Path:
    return Path(path).resolve()


def _is_safe_path(path: str, base: str = "") -> bool:
    try:
        p = _safe_path(path)
        if base:
            base_p = _safe_path(base)
            return str(p).startswith(str(base_p))
        dangerous = [r"C:\\Windows", r"C:\\Program Files", r"C:\\Program Files (x86)"]
        for d in dangerous:
            if str(p).startswith(d):
                return False
        return True
    except Exception:
        return False


def _is_hidden(p: Path) -> bool:
    try:
        import stat
        if os.name == "nt":
            return bool(p.stat().st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN)
    except Exception:
        pass
    return p.name.startswith(".")


MAX_RESULTS = 200


def _glob_handler(ctx: dict, path: str, pattern: str = "**/*") -> str:
    base = _safe_path(path)
    if not base.is_dir():
        return f"目录不存在: {path}"
    results = []
    try:
        for p in base.glob(pattern):
            if p.is_file() and not _is_hidden(p):
                rel = p.relative_to(base)
                size = p.stat().st_size
                results.append(f"{rel}  ({_format_size(size)})")
                if len(results) >= MAX_RESULTS:
                    results.append(f"... (共 {MAX_RESULTS}+ 个文件，结果已截断)")
                    break
    except Exception as e:
        return f"Glob 搜索失败: {e}"
    if not results:
        return "未找到匹配文件"
    return "\n".join(results)


def _grep_handler(ctx: dict, path: str, pattern: str, file_pattern: str = "*",
                  limit: int = 100, ignore_case: bool = False) -> str:
    base = _safe_path(path)
    if not base.is_dir():
        return f"目录不存在: {path}"
    flags = re.IGNORECASE if ignore_case else 0
    results = []
    try:
        for p in base.rglob(file_pattern):
            if p.is_file() and not _is_hidden(p):
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(text.split("\n"), 1):
                        if re.search(pattern, line, flags):
                            rel = p.relative_to(base)
                            results.append(f"{rel}:{i}: {line.rstrip()[:200]}")
                            if len(results) >= limit:
                                break
                    if len(results) >= limit:
                        break
                except Exception:
                    pass
    except Exception as e:
        return f"Grep 搜索失败: {e}"
    if not results:
        return "未找到匹配"
    return "\n".join(results[:limit])


def _list_dir_handler(ctx: dict, path: str, file_pattern: str = "*",
                      recursive: bool = False) -> str:
    base = _safe_path(path)
    if not base.is_dir():
        return f"目录不存在: {path}"
    results = []
    try:
        iterator = base.rglob(file_pattern) if recursive else base.glob(file_pattern)
        for p in iterator:
            if _is_hidden(p):
                continue
            rel = p.relative_to(base)
            if p.is_dir():
                results.append(f"[目录] {rel}/")
            else:
                size = p.stat().st_size
                results.append(f"[文件] {rel}  ({_format_size(size)})")
            if len(results) >= MAX_RESULTS:
                results.append(f"... (共 {MAX_RESULTS}+ 项，结果已截断)")
                break
    except Exception as e:
        return f"列出目录失败: {e}"
    if not results:
        return "目录为空或无匹配项"
    return "\n".join(results)


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f}MB"
    return f"{size / (1024 * 1024 * 1024):.1f}GB"


def register_file_tools():
    ToolRegistry.register(
        "glob", "按 Glob 模式匹配文件路径",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "搜索目录路径"},
            "pattern": {"type": "string", "description": "Glob 模式，如 **/*.py 或 src/*.ts"},
        }, "required": ["path"]},
        _glob_handler, "file"
    )
    ToolRegistry.register(
        "grep", "在文件中搜索正则表达式匹配内容",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "搜索目录路径"},
            "pattern": {"type": "string", "description": "正则表达式模式"},
            "file_pattern": {"type": "string", "description": "文件名 Glob 过滤，如 *.py"},
            "limit": {"type": "integer", "description": "最大结果数，默认100"},
            "ignore_case": {"type": "boolean", "description": "是否忽略大小写，默认false"},
        }, "required": ["path", "pattern"]},
        _grep_handler, "file"
    )
    ToolRegistry.register(
        "list_dir", "列出目录内容",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "目录路径"},
            "file_pattern": {"type": "string", "description": "文件名 Glob 过滤，如 *.py"},
            "recursive": {"type": "boolean", "description": "是否递归列出子目录，默认false"},
        }, "required": ["path"]},
        _list_dir_handler, "file"
    )
