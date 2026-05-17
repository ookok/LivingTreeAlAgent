"""unified_exec — unified subprocess/command execution.

ALL subprocess/os.system calls MUST route through this module.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from dataclasses import dataclass


@dataclass
class ExecResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    success: bool = False
    elapsed_ms: float = 0.0


async def run(command: str, timeout: float = 30.0, cwd: str = "") -> ExecResult:
    try:
        from ..core.shell_env import get_shell
        shell = get_shell()
        result = await shell.execute(command, timeout=timeout, workdir=cwd)
        if result.blocked:
            return ExecResult(stderr="BLOCKED: dangerous command", exit_code=-1)
        return ExecResult(
            stdout=result.stdout[:50000],
            stderr=result.stderr[:10000],
            exit_code=result.exit_code,
            success=result.exit_code == 0,
            elapsed_ms=result.elapsed_ms,
        )
    except ImportError:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: _raw_run(command, timeout, cwd))


def _raw_run(command: str, timeout: float, cwd: str) -> ExecResult:
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
        return ExecResult(stderr="Timeout", exit_code=-1, elapsed_ms=timeout * 1000)
    except Exception as e:
        return ExecResult(stderr=str(e)[:500], exit_code=-1)


async def git(args: str, timeout: float = 30.0) -> ExecResult:
    return await run(f"git {args}", timeout=timeout)


async def pip_install(package: str, timeout: float = 120.0) -> bool:
    result = await run(f"pip install {package}", timeout=timeout)
    return result.success


def run_sync(command: str, timeout: float = 30.0, cwd: str = "") -> ExecResult:
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
        return ExecResult(stderr="Timeout", exit_code=-1, elapsed_ms=timeout * 1000)
    except Exception as e:
        return ExecResult(stderr=str(e)[:500], exit_code=-1)


def check_output_sync(command: str, timeout: float = 30.0) -> str:
    r = run_sync(command, timeout=timeout)
    if not r.success:
        raise RuntimeError(r.stderr or f"Command failed with code {r.exit_code}")
    return r.stdout


__all__ = ["run", "run_sync", "check_output_sync", "git", "pip_install", "ExecResult"]
