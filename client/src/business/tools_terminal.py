"""
终端命令工具集
注册到 ToolRegistry
"""

import subprocess
from pathlib import Path
from client.src.business.tools_registry import ToolRegistry, tool, SCHEMA


def register_terminal_tools(agent):
    """注册终端工具"""

    @tool(
        name="terminal",
        description="执行 Windows 终端命令（PowerShell）",
        parameters=SCHEMA["terminal"],
        toolset="terminal",
    )
    def terminal(ctx: dict, command: str, cwd: str | None = None) -> str:
        """
        执行终端命令（Windows PowerShell）
        注意：限制危险命令
        """
        # 危险命令黑名单
        dangerous = [
            r"rm\s+-rf\s+/", r"format\s+[a-z]:", r"del\s+/[fqs]\s+/",
            r"Remove-Item\s+-Recurse\s+/\s", r"Invoke-WebRequest.*-OutFile",
        ]
        import re
        for pat in dangerous:
            if re.search(pat, command, re.IGNORECASE):
                return f"禁止执行危险命令: {command[:50]}..."

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
                cwd=cwd or None,
            )
            out = result.stdout or ""
            err = result.stderr or ""
            if result.returncode != 0 and err:
                out = out + f"\n[stderr] {err}"
            return out[:8000] or "(命令执行完成，无输出)"
        except subprocess.TimeoutExpired:
            return "命令超时（120秒）"
        except Exception as e:
            return f"执行失败: {e}"
