"""
文件操作工具集
注册到 ToolRegistry
"""

import os
import re
import json
from pathlib import Path
from core.tools_registry import ToolRegistry, tool, SCHEMA


def _safe_path(path: str) -> Path:
    """安全化路径（防止路径穿越）"""
    p = Path(path).resolve()
    return p


def _is_safe_path(path: str, base: Path | None = None) -> bool:
    """检查路径安全性"""
    try:
        p = _safe_path(path)
        if base:
            return str(p).startswith(str(base.resolve()))
        # 禁止系统路径
        dangerous = ["/", "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)"]
        for d in dangerous:
            if str(p).startswith(d):
                return False
        return True
    except Exception:
        return False


def register_file_tools(agent):
    """注册文件工具"""

    @tool(
        name="read_file",
        description="读取文件内容",
        parameters=SCHEMA["read_file"],
        toolset="file",
    )
    def read_file(ctx: dict, path: str, limit: int | None = None, offset: int = 0) -> str:
        if not _is_safe_path(path):
            return f"错误：路径不安全 {path}"
        p = _safe_path(path)
        if not p.exists():
            return f"文件不存在: {path}"
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.split("\n")
            if offset > 0:
                lines = lines[offset:]
            if limit:
                lines = lines[:limit]
            return "\n".join(lines)
        except Exception as e:
            return f"读取失败: {e}"

    @tool(
        name="write_file",
        description="写入文件内容",
        parameters=SCHEMA["write_file"],
        toolset="file",
    )
    def write_file(ctx: dict, path: str, content: str) -> str:
        if not _is_safe_path(path):
            return f"错误：路径不安全 {path}"
        p = _safe_path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"已写入: {path} ({len(content)} 字符)"
        except Exception as e:
            return f"写入失败: {e}"

    @tool(
        name="patch",
        description="替换文件中的文本（精确匹配）",
        parameters=SCHEMA["patch"],
        toolset="file",
    )
    def patch(ctx: dict, path: str, old_str: str, new_str: str) -> str:
        if not _is_safe_path(path):
            return f"错误：路径不安全 {path}"
        p = _safe_path(path)
        if not p.exists():
            return f"文件不存在: {path}"
        try:
            text = p.read_text(encoding="utf-8")
            if old_str not in text:
                return f"未找到要替换的文本: {old_str[:50]}..."
            new_text = text.replace(old_str, new_str, 1)
            p.write_text(new_text, encoding="utf-8")
            return f"已替换: {path}"
        except Exception as e:
            return f"替换失败: {e}"

    @tool(
        name="search_files",
        description="在目录中搜索文件内容（正则匹配）",
        parameters=SCHEMA["search_files"],
        toolset="file",
    )
    def search_files(ctx: dict, path: str, pattern: str, file_pattern: str = "*") -> str:
        base = _safe_path(path)
        if not base.is_dir():
            return f"目录不存在: {path}"

        results = []
        try:
            for p in base.rglob(file_pattern):
                if p.is_file() and not _is_hidden(p):
                    try:
                        text = p.read_text(encoding="utf-8", errors="ignore")
                        for i, line in enumerate(text.split("\n"), 1):
                            if re.search(pattern, line):
                                results.append(f"{p}:{i}: {line.rstrip()}")
                    except Exception:
                        pass
        except Exception as e:
            return f"搜索失败: {e}"

        if not results:
            return "未找到匹配"
        return "\n".join(results[:100])  # 限制返回数量

    @tool(
        name="list_dir",
        description="列出目录内容",
        parameters=SCHEMA["list_dir"],
        toolset="file",
    )
    def list_dir(ctx: dict, path: str) -> str:
        base = _safe_path(path)
        if not base.is_dir():
            return f"目录不存在: {path}"

        items = []
        try:
            for entry in sorted(base.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.name.startswith("."):
                    continue
                icon = "📁" if entry.is_dir() else "📄"
                size = ""
                if entry.is_file():
                    try:
                        size = _format_size(entry.stat().st_size)
                    except Exception:
                        pass
                items.append(f"{icon} {entry.name} {size}")
        except Exception as e:
            return f"列出失败: {e}"

        return "\n".join(items) or "空目录"


def _is_hidden(p: Path) -> bool:
    try:
        return bool(os.stat(p).st_file_attributes & 2)
    except Exception:
        return p.name.startswith(".")


def _format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
