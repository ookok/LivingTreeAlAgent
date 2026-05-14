"""unified_exec — Lightweight universal execution shim for ShellExecutor + pkg_manager.

All modules should route through this instead of raw subprocess.
Provides the same interface as raw subprocess but with safety gates.

Usage (drop-in replacement for subprocess.run):
  from livingtree.treellm.unified_exec import run, git, pip_install

  result = await run("ls -la", timeout=10)            # → ShellResult
  result = await git("add -A")                        # → ShellResult
  result = await pip_install("requests")               # → bool
"""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class ExecResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    success: bool = False
    elapsed_ms: float = 0.0


async def run(command: str, timeout: float = 30.0,
              cwd: str = "", check: bool = False) -> ExecResult:
    """Execute a shell command through unified ShellExecutor with safety gates.

    Drop-in replacement for subprocess.run() with automatic:
    - DANGEROUS_PATTERNS checking (36 patterns)
    - Cross-platform shell selection (pwsh/bash)
    - Timeout with process kill
    - Output truncation (50KB stdout, 10KB stderr)
    """
    try:
        from ..core.shell_env import get_shell
        shell = get_shell()
        result = await shell.execute(command, timeout=timeout, cwd=cwd)
        if result.blocked:
            return ExecResult(stderr=f"BLOCKED: dangerous command", exit_code=-1)
        return ExecResult(
            stdout=result.stdout[:50000],
            stderr=result.stderr[:10000],
            exit_code=result.exit_code,
            success=result.exit_code == 0,
            elapsed_ms=result.elapsed_ms,
        )
    except ImportError:
        # Fallback: raw subprocess
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: _raw_run(command, timeout, cwd),
        )


def _raw_run(command: str, timeout: float, cwd: str) -> ExecResult:
    """Last-resort fallback when ShellExecutor unavailable."""
    import time
    t0 = time.time()
    try:
        r = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd or None,
        )
        return ExecResult(
            stdout=r.stdout[:50000], stderr=r.stderr[:10000],
            exit_code=r.returncode, success=r.returncode == 0,
            elapsed_ms=(time.time() - t0) * 1000,
        )
    except subprocess.TimeoutExpired:
        return ExecResult(stderr="Timeout", exit_code=-1, elapsed_ms=timeout*1000)
    except Exception as e:
        return ExecResult(stderr=str(e)[:500], exit_code=-1)


async def git(args: str, timeout: float = 30.0) -> ExecResult:
    """Execute a git command through ShellExecutor."""
    return await run(f"git {args}", timeout=timeout)


async def pip_install(package: str, timeout: float = 120.0) -> bool:
    """Install a pip package through unified pkg_manager."""
    try:
        from ..integration.pkg_manager import install as pkg_install
        return pkg_install(package) is not False
    except ImportError:
        result = await run(f"pip install {package}", timeout=timeout)
        return result.success


async def npm_install(package: str, global_install: bool = True,
                      timeout: float = 120.0) -> bool:
    """Install an npm package."""
    flag = "-g" if global_install else ""
    result = await run(f"npm install {flag} {package}", timeout=timeout)
    return result.success


async def gh(args: str, timeout: float = 60.0) -> ExecResult:
    """Execute a GitHub CLI command."""
    return await run(f"gh {args}", timeout=timeout)


async def pytest(args: str = "", timeout: float = 300.0) -> ExecResult:
    """Run pytest."""
    return await run(f"pytest {args}", timeout=timeout)


__all__ = ["run", "git", "pip_install", "npm_install", "gh", "pytest", "ExecResult"]
