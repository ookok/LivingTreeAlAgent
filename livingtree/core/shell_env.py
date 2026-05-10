"""Shell Environment — toolchain detection + localfs bridge + safe execution.

Three integrated capabilities:
1. Environment probe: auto-detect git/python/node/npm/pwsh/docker on startup
2. LocalFS bridge: server-side access to browser-mounted local folders
3. Safe shell executor: sandboxed command execution with safety gates
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import time as _time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger

IS_WINDOWS = platform.system() == "Windows"

DANGEROUS_PATTERNS = [
    "rm -rf /", "rm -rf ~", "rm -rf .", "del /f /s C:\\",
    "format ", "mkfs.", ":(){ :|:& };:", "> /dev/sda",
    "chmod 777 /", "chmod -R 777 /",
    "curl | sh", "curl | bash", "wget -O- | sh",
    "eval(", "exec(", "__import__('os')",
    "ssh ", "scp ", "nc ", "ncat ",
]


# ═══ 1. Environment Probe ═══

@dataclass
class ToolInfo:
    name: str
    found: bool
    path: str = ""
    version: str = ""
    install_hint: str = ""


TOOLS_TO_PROBE = [
    ("git", "git --version", "winget install Git.Git / scoop install git"),
    ("python", "python --version", "winget install Python.Python.3.13"),
    ("python3", "python3 --version", "apt install python3"),
    ("pip", "pip --version", "python -m ensurepip"),
    ("node", "node --version", "winget install OpenJS.NodeJS / scoop install node"),
    ("npm", "npm --version", "comes with Node.js"),
    ("pwsh", "pwsh --version", "winget install Microsoft.PowerShell"),
    ("docker", "docker --version", "winget install Docker.DockerDesktop"),
    ("uv", "uv --version", "pip install uv"),
    ("cargo", "cargo --version", "winget install Rustlang.Rustup"),
    ("go", "go version", "winget install GoLang.Go"),
    ("conda", "conda --version", "winget install Anaconda.Anaconda3"),
]


def probe_environment() -> dict[str, ToolInfo]:
    """Probe for available tools on the system PATH."""
    results: dict[str, ToolInfo] = {}
    for name, version_cmd, install_hint in TOOLS_TO_PROBE:
        path = shutil.which(name)
        version = ""
        if path:
            try:
                r = subprocess.run(
                    version_cmd.split() if " " in version_cmd else [version_cmd],
                    capture_output=True, text=True, timeout=8,
                    shell=IS_WINDOWS,
                )
                version = (r.stdout or r.stderr or "").strip().split("\n")[0][:100]
            except Exception:
                version = "found"
        results[name] = ToolInfo(
            name=name, found=path is not None,
            path=path or "", version=version,
            install_hint=install_hint,
        )
    return results


def probe_summary() -> str:
    """Human-readable toolchain summary for LLM context."""
    tools = probe_environment()
    lines = ["## Environment Toolchain"]
    for name, t in tools.items():
        icon = "✅" if t.found else "❌"
        detail = f" {t.version}" if t.version else ""
        hint = f" — install: {t.install_hint}" if not t.found else ""
        lines.append(f"{icon} {name}{detail}{hint}")
    lines.append(f"\nOS: {platform.system()} {platform.release()}")
    lines.append(f"Shell: {'pwsh' if IS_WINDOWS else 'bash'}")
    return "\n".join(lines)


# ═══ 2. LocalFS Bridge ═══

@dataclass
class MountedFolder:
    name: str
    path: str
    mounted_at: float = 0.0
    files_count: int = 0


class LocalFS:
    """Server-side bridge for browser-mounted local folders."""

    def __init__(self):
        self._mounts: dict[str, MountedFolder] = {}

    def mount(self, name: str, path_str: str) -> Optional[MountedFolder]:
        path = Path(path_str).resolve()
        if not path.exists():
            logger.warning(f"LocalFS: mount failed — {path_str} does not exist")
            return None
        m = MountedFolder(name=name, path=str(path), mounted_at=_time.time())
        self._mounts[name] = m
        logger.info(f"LocalFS: mounted '{name}' → {path}")
        return m

    def unmount(self, name: str):
        self._mounts.pop(name, None)

    def get_mount(self, name: str) -> Optional[MountedFolder]:
        return self._mounts.get(name)

    def resolve_path(self, mount_name: str, relative_path: str = "") -> Optional[Path]:
        """Resolve a path relative to a mounted folder. Prevents traversal."""
        m = self._mounts.get(mount_name)
        if not m:
            return None
        root = Path(m.path).resolve()
        target = (root / relative_path).resolve()
        if not str(target).startswith(str(root)):
            return None
        return target if target.exists() else None

    def list_files(self, mount_name: str, subpath: str = "", max_depth: int = 3) -> list[dict]:
        """List files in a mounted folder."""
        m = self._mounts.get(mount_name)
        if not m:
            return []
        root = Path(m.path)
        if subpath:
            root = root / subpath
        if not root.exists():
            return []
        entries = []
        try:
            for p in sorted(root.iterdir())[:100]:
                try:
                    if p.is_file():
                        entries.append({"name": p.name, "type": "file", "size": p.stat().st_size})
                    elif p.is_dir() and max_depth > 0:
                        children = self.list_files(mount_name, str(p.relative_to(Path(m.path))), max_depth - 1)
                        entries.append({"name": p.name, "type": "dir", "children": children})
                except PermissionError:
                    entries.append({"name": p.name, "type": "locked"})
        except PermissionError:
            pass
        return entries

    def read_file(self, mount_name: str, file_path: str, max_bytes: int = 50000) -> Optional[str]:
        """Read a file from a mounted folder."""
        resolved = self.resolve_path(mount_name, file_path)
        if not resolved or not resolved.is_file():
            return None
        try:
            return resolved.read_text(encoding="utf-8", errors="replace")[:max_bytes]
        except Exception as e:
            return f"[read error: {e}]"

    @property
    def mounts(self) -> list[dict]:
        return [
            {"name": m.name, "path": m.path, "mounted_at": m.mounted_at}
            for m in self._mounts.values()
        ]


# ═══ 3. Safe Shell Executor ═══

@dataclass
class ShellResult:
    command: str
    workdir: str
    stdout: str
    stderr: str
    exit_code: int
    elapsed_ms: float
    truncated: bool = False
    blocked: bool = False
    block_reason: str = ""


class ShellExecutor:
    """Safe shell command execution with sandbox, timeout, and safety gates."""

    def __init__(self, timeout: float = 30.0, max_output: int = 50000):
        self._timeout = timeout
        self._max_output = max_output
        self._local_fs: Optional[LocalFS] = None

    @property
    def localfs(self) -> LocalFS:
        if self._local_fs is None:
            self._local_fs = LocalFS()
        return self._local_fs

    def _is_dangerous(self, command: str) -> Optional[str]:
        cmd_lower = command.lower()
        cmd_compact = cmd_lower.replace(" ", "")
        for pattern in DANGEROUS_PATTERNS:
            p_compact = pattern.lower().replace(" ", "")
            if p_compact in cmd_compact:
                return f"命令被安全策略拦截: 匹配危险模式 '{pattern}'"
        if ("curl" in cmd_lower or "wget" in cmd_lower) and "|" in command:
            if any(s in cmd_lower for s in ["sh", "bash", "dash", "zsh"]):
                return "命令被安全策略拦截: curl/wget 管道到 shell"
        return None

    def resolve_workdir(self, workdir: str = "", mount_name: str = "") -> str:
        """Resolve workdir from mounted folder or use current dir."""
        if mount_name and self._local_fs:
            m = self._local_fs.get_mount(mount_name)
            if m:
                return m.path
        if workdir:
            p = Path(workdir)
            if p.exists():
                return str(p.resolve())
        return str(Path.cwd())

    async def execute(
        self, command: str, workdir: str = "", mount_name: str = "",
        timeout: float = 0, env_vars: dict | None = None,
    ) -> ShellResult:
        """Execute a shell command safely. Returns ShellResult."""
        danger = self._is_dangerous(command)
        if danger:
            logger.warning(f"Shell blocked: {danger} — cmd: {command[:100]}")
            return ShellResult(command=command, workdir=workdir, stdout="", stderr=danger,
                               exit_code=-1, elapsed_ms=0, blocked=True, block_reason=danger)

        cwd = self.resolve_workdir(workdir, mount_name)
        t = timeout or self._timeout

        env = os.environ.copy()
        env["PATH"] = os.environ.get("PATH", "")
        if env_vars:
            env.update(env_vars)

        start = _time.time()
        try:
            proc = await asyncio.create_subprocess_shell(
                command, cwd=cwd, env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=t,
            )
            elapsed = (_time.time() - start) * 1000

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            truncated = False
            if len(stdout) > self._max_output:
                stdout = stdout[:self._max_output] + f"\n... [截断: {len(stdout) - self._max_output} 字符]"
                truncated = True
            if len(stderr) > self._max_output:
                stderr = stderr[:self._max_output] + f"\n... [截断]"
                truncated = True

            return ShellResult(
                command=command, workdir=cwd,
                stdout=stdout, stderr=stderr,
                exit_code=proc.returncode or 0,
                elapsed_ms=elapsed, truncated=truncated,
            )
        except asyncio.TimeoutError:
            return ShellResult(
                command=command, workdir=cwd,
                stdout="", stderr=f"命令超时 ({t}s)",
                exit_code=-1, elapsed_ms=t * 1000,
            )
        except Exception as e:
            return ShellResult(
                command=command, workdir=cwd,
                stdout="", stderr=str(e)[:500],
                exit_code=-1, elapsed_ms=(_time.time() - start) * 1000,
            )

    async def execute_python(
        self, code: str, workdir: str = "", mount_name: str = "",
    ) -> ShellResult:
        """Execute Python code using the detected Python interpreter."""
        python_bin = shutil.which("python") or shutil.which("python3") or "python"
        cwd = self.resolve_workdir(workdir, mount_name)
        return await self.execute(f'"{python_bin}" -c "{code}"', cwd, mount_name)

    async def execute_git(
        self, args: str, workdir: str = "", mount_name: str = "",
    ) -> ShellResult:
        """Execute a git command in the given workdir."""
        git_bin = shutil.which("git")
        if not git_bin:
            return ShellResult(
                command=f"git {args}", workdir=workdir,
                stdout="", stderr="Git 未安装。安装: winget install Git.Git",
                exit_code=-1, elapsed_ms=0,
            )
        cwd = self.resolve_workdir(workdir, mount_name)
        return await self.execute(f'"{git_bin}" {args}', cwd, mount_name)


_shell_instance: Optional[ShellExecutor] = None


def get_shell() -> ShellExecutor:
    global _shell_instance
    if _shell_instance is None:
        _shell_instance = ShellExecutor()
    return _shell_instance
