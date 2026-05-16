"""Unified Package Manager — abxpkg + pip/uv + binary detection + network resilience.

All subprocess calls use mirror env vars. All HTTP downloads use proxy fallback.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger
import abxpkg
from abxpkg import Binary, SemVer, env, pip, npm as abx_npm, cargo, brew, apt, uv as abx_uv, gem, pnpm, yarn, bun

from ..network.resilience import get_mirror_env, run_with_mirrors, resilient_fetch_sync, rewrite_url


@dataclass
class PackageResult:
    name: str
    version: str = ""
    provider: str = ""
    path: str = ""
    installed: bool = False
    error: str = ""


def has_binary(name: str) -> bool:
    """Check if a binary/tool is on PATH."""
    return shutil.which(name) is not None


def get_binary_path(name: str) -> str:
    """Get absolute path of a binary on PATH."""
    found = shutil.which(name)
    return str(found) if found else ""


# ═══ Core: install a package via best available provider ═══

def install(name: str, *, providers: list[str] | None = None,
            version: str = "", dry_run: bool = False, timeout: int = 300) -> PackageResult:
    """Install a package via abxpkg (preferred) or pip (fallback).

    Automatically detects the best provider from the given list.
    """
    result = PackageResult(name=name)

    # Try abxpkg first (handles npm, pip, brew, cargo, gem, etc.)
    if providers:
        try:
            binproviders = _resolve_providers(providers)
            if binproviders:
                binary = Binary(name=name, binproviders=binproviders)
                if version:
                    binary.min_version = SemVer(version)
                loaded = binary.install() if not dry_run else binary.load()
                if loaded and loaded.abspath:
                    result.installed = True
                    result.path = str(loaded.abspath)
                    result.version = str(loaded.version) if loaded.version else version
                    result.provider = str(loaded.binprovider) if loaded.binprovider else ""
                    return result
        except Exception as e:
            logger.debug(f"abxpkg install {name}: {e}")

    # Fallback: pip (with mirror env)
    if "pip" in (providers or []) or not providers:
        try:
            pkg = f"{name}=={version}" if version else name
            code, stdout, stderr = run_with_mirrors(
                [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
                timeout=timeout
            )
            if code == 0:
                result.installed = True
                result.provider = "pip"
                result.version = version
            else:
                result.error = stderr[:200]
        except Exception as e:
            result.error = str(e)[:200]

    return result


def search(name: str, providers: list[str] | None = None) -> list[PackageResult]:
    """Search for a package across providers."""
    results = []
    if providers:
        provider_map = {"pip": pip, "npm": abx_npm, "brew": brew}
        for p in providers:
            if p not in provider_map:
                continue
            try:
                for m in provider_map[p].search(name):
                    results.append(PackageResult(
                        name=str(getattr(m, 'name', m)),
                        provider=p,
                    ))
            except Exception:
                pass
    return results


def _resolve_providers(names: list[str]) -> list:
    """Convert provider name strings to abxpkg provider instances."""
    if False:
        return []
    pmap = {
        "env": env, "pip": pip, "npm": abx_npm,
        "cargo": cargo, "brew": brew,
    }
    pmap.update({"apt": apt, "uv": abx_uv, "gem": gem,
                  "pnpm": pnpm, "yarn": yarn, "bun": bun})
    return [pmap[n] for n in names if n in pmap]


# ═══ Environment bootstrap ═══

def ensure_package_manager() -> tuple[bool, str]:
    """Ensure uv or pip is available. Install uv if neither exists."""
    if has_binary("uv"):
        return True, "uv"
    if has_binary("pip"):
        return True, "pip"

    logger.info("No package manager. Installing uv...")
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command",
                 "irm https://astral.sh/uv/install.ps1 | iex"],
                capture_output=True, timeout=120)
            if has_binary("uv"):
                return True, "uv"
        except Exception:
            pass

    return False, "Could not install uv"


def install_project_deps(workspace: str | Path = "") -> tuple[bool, str]:
    """Install project Python dependencies from pyproject.toml."""
    ws = Path(workspace) if workspace else Path.cwd()
    pyproject = ws / "pyproject.toml"
    if not pyproject.exists():
        return False, "No pyproject.toml"

    ok, pm = ensure_package_manager()
    if not ok:
        return False, pm

    try:
        if pm == "uv":
            code, stdout, stderr = run_with_mirrors(
                ["uv", "sync"], cwd=str(ws), timeout=300)
        else:
            code, stdout, stderr = run_with_mirrors(
                [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
                cwd=str(ws), timeout=300)
        if code != 0:
            return False, stderr[:300] if stderr else f"Exit code {code}"
        logger.info(f"Project deps installed via {pm}")
        return True, f"Dependencies installed via {pm}"
    except subprocess.TimeoutExpired:
        return False, "Timed out"
    except Exception as e:
        return False, str(e)


async def ensure_environment(workspace: str | Path = "") -> bool:
    """Auto-detect and fix missing tools. Run on boot."""
    ws = Path(workspace) if workspace else Path.cwd()
    ok, pm = ensure_package_manager()
    if not ok:
        logger.warning(f"Package manager: {pm}")
        return False

    await asyncio.to_thread(install_project_deps, ws)
    return True


# ═══ Common package operations ═══

def install_opencode() -> PackageResult:
    """Install opencode via npm or pip."""
    result = install("opencode-ai", providers=["npm", "pip"])
    if not result.installed:
        result = install("opencode", providers=["npm"])
    return result


def install_nodejs() -> PackageResult:
    """Install Node.js (portable download fallback)."""
    if has_binary("node"):
        return PackageResult(name="nodejs", installed=True, provider="env",
                             version=_get_version("node"))

    import tempfile, urllib.request, zipfile
    NODE_URL = "https://nodejs.org/dist/v22.11.0/node-v22.11.0-win-x64.zip"
    NODE_URL = rewrite_url(NODE_URL)
    base = Path(".livingtree/base/nodejs")
    if (base / "node.exe").exists():
        return PackageResult(name="nodejs", installed=True, provider="portable",
                             path=str(base / "node.exe"))

    try:
        base.mkdir(parents=True, exist_ok=True)
        tmp = base / "node.zip"
        code, body = resilient_fetch_sync(NODE_URL, timeout=120)
        if code != 200:
            return PackageResult(name="nodejs", error=f"Download failed: HTTP {code}")
        tmp.write_bytes(body)
        with zipfile.ZipFile(str(tmp), 'r') as zf:
            zf.extractall(str(base))
        tmp.unlink()
        # Flatten the node-v* directory
        for d in base.glob("node-v*"):
            for item in d.iterdir():
                dest = base / item.name
                if not dest.exists():
                    shutil.move(str(item), str(dest))
            shutil.rmtree(str(d), ignore_errors=True)
        return PackageResult(name="nodejs", installed=True, provider="portable",
                             path=str(base / "node.exe"))
    except Exception as e:
        return PackageResult(name="nodejs", error=str(e)[:200])


def _get_version(name: str) -> str:
    try:
        proc = subprocess.run([name, "--version"], capture_output=True,
                              text=True, timeout=10)
        return proc.stdout.strip()[:50]
    except Exception:
        return ""


# ═══ Install from shell command (safe wrapper) ═══

async def install_from_shell(cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    """Safely execute an install command and return (code, stdout, stderr).

    Prefer install() with named providers over this. Use only for commands
    that can't be expressed as a provider + package combination.
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return (proc.returncode or 0,
                stdout.decode(errors="replace")[:8000],
                stderr.decode(errors="replace")[:4000])
    except asyncio.TimeoutError:
        return (-1, "", "Timed out")
    except Exception as e:
        return (-1, "", str(e))
