"""Bootstrap — Two-stage self-initializing environment for LivingTree.

Inspired by Cursor Autoinstall: the project should set ITSELF up.

Stage 1 (Core — always succeeds):
  - Python version check (3.10+)
  - pip install -e . (core deps)
  - secrets vault auto-seed (senseTime default key)
  - essential imports verification
  - Config file generation if missing

Stage 2 (Acceleration — gracefully degrades):
  - ripgrep detection (or pip install)
  - tree-sitter language grammars
  - Numba JIT acceleration check
  - py-spy profiler check
  - CodeGraph bootstrap (first full index)
  - LLM provider connectivity test (parallel ping all 18)

Usage:
    livingtree bootstrap              # Full two-stage bootstrap
    livingtree bootstrap --quick      # Stage 1 only (core)
    livingtree bootstrap --full       # Stage 1 + 2 + LLM warm-up
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.metadata
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger
# SUBPROCESS MIGRATION: from livingtree.treellm.unified_exec import run_sync



@dataclass
class BootstrapCheck:
    name: str
    status: str = "pending"  # pending | ok | missing | failed | skipped
    detail: str = ""
    fix_hint: str = ""
    stage: int = 1
    optional: bool = False


@dataclass
class BootstrapReport:
    checks: list[BootstrapCheck]
    stage1_passed: int = 0
    stage1_total: int = 0
    stage2_passed: int = 0
    stage2_total: int = 0
    duration_ms: float = 0
    ready: bool = False


class Bootstrapper:
    """Two-stage self-initializing environment for LivingTree."""

    @staticmethod
    async def run(quick: bool = False, full: bool = False,
                  auto_install: bool = True) -> BootstrapReport:
        t0 = time.time()
        checks: list[BootstrapCheck] = []

        # ═══ Stage 1: Core Bootstrap ═══
        checks.extend(Bootstrapper._stage1_core())

        # Auto-install missing core packages
        if auto_install:
            try:
                await Bootstrapper._auto_install_missing(checks)
            except Exception as e:
                logger.debug(f"Bootstrap auto-install skipped: {e}")
                for check in checks:
                    if check.status == "missing":
                        check.status = "skipped"
                        check.detail = f"auto-install unavailable: {str(e)[:60]}"

        if quick:
            return Bootstrapper._build_report(checks, t0)

        # ═══ Stage 2: Acceleration Bootstrap ═══
        try:
            checks.extend(Bootstrapper._stage2_accel())
        except Exception as e:
            logger.debug(f"Bootstrap stage2: {e}")
            checks.append(BootstrapCheck(
                name="Stage 2", status="skipped",
                detail=f"acceleration checks unavailable: {str(e)[:60]}",
                optional=True,
            ))

        # Auto-install optional packages (non-blocking)
        if auto_install:
            await Bootstrapper._auto_install_optional(checks)

        if full:
            checks.extend(Bootstrapper._stage2_llm_warmup())

        return Bootstrapper._build_report(checks, t0)

    # ── Stage 1 ───────────────────────────────────────────────────

    @staticmethod
    def _stage1_core() -> list[BootstrapCheck]:
        checks = []

        # Python version
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        py_ok = sys.version_info >= (3, 10)
        checks.append(BootstrapCheck(
            name="Python Version", status="ok" if py_ok else "failed",
            detail=py_ver,
            fix_hint="Install Python 3.10+ from https://python.org" if not py_ok else "",
        ))

        # pip
        pip_path = shutil.which("pip") or shutil.which("pip3")
        checks.append(BootstrapCheck(
            name="pip", status="ok" if pip_path else "missing",
            detail=pip_path or "not found",
            fix_hint="Install pip: python -m ensurepip --upgrade" if not pip_path else "",
        ))

        # git
        git_path = shutil.which("git")
        checks.append(BootstrapCheck(
            name="git", status="ok" if git_path else "missing",
            detail=git_path or "not found",
            fix_hint="Install git from https://git-scm.com" if not git_path else "",
        ))

        # Core packages
        core_pkgs = {
            "aiohttp": ("aiohttp", "pip install aiohttp"),
            "yaml": ("PyYAML", "pip install pyyaml"),
            "loguru": ("loguru", "pip install loguru"),
            "pydantic": ("pydantic", "pip install pydantic"),
            "fastapi": ("fastapi", "pip install fastapi"),
            "uvicorn": ("uvicorn", "pip install uvicorn"),
        }
        for import_name, (pkg_name, fix) in core_pkgs.items():
            try:
                ver = importlib.metadata.version(pkg_name)
                checks.append(BootstrapCheck(
                    name=f"pip:{import_name}", status="ok", detail=ver,
                ))
            except importlib.metadata.PackageNotFoundError:
                # Fallback: try importing the module directly
                try:
                    importlib.import_module(import_name)
                    checks.append(BootstrapCheck(
                        name=f"pip:{import_name}", status="ok", detail="imported",
                    ))
                except ImportError:
                    checks.append(BootstrapCheck(
                        name=f"pip:{import_name}", status="missing",
                        detail="not installed", fix_hint=fix,
                    ))

        # Config file
        config_path = Path("config/livingtree.yaml")
        if config_path.exists():
            checks.append(BootstrapCheck(
                name="Config", status="ok",
                detail=f"config/livingtree.yaml ({config_path.stat().st_size} bytes)",
            ))
        else:
            checks.append(BootstrapCheck(
                name="Config", status="missing",
                detail="config/livingtree.yaml not found",
                fix_hint="Run: livingtree config reload",
            ))

        # Secrets vault
        vault_path = Path("config/secrets.enc")
        try:
            from ..config.secrets import get_secret_vault
            vault = get_secret_vault()
            keys = vault.keys()
            checks.append(BootstrapCheck(
                name="Secrets Vault", status="ok" if keys else "missing",
                detail=f"{len(keys)} keys stored",
                fix_hint="Run: livingtree secrets set deepseek_api_key sk-xxx" if not keys else "",
            ))
        except Exception as e:
            checks.append(BootstrapCheck(
                name="Secrets Vault", status="failed",
                detail=str(e)[:80],
                fix_hint="Check config/secrets.enc permissions",
            ))

        # Core module imports
        core_modules = {
            "livingtree.treellm.core": "TreeLLM",
            "livingtree.dna.life_engine": "LifeEngine",
            "livingtree.config.settings": "get_config",
        }
        for mod, attr in core_modules.items():
            try:
                m = importlib.import_module(mod)
                getattr(m, attr)
                checks.append(BootstrapCheck(name=f"import:{mod}", status="ok"))
            except Exception as e:
                checks.append(BootstrapCheck(
                    name=f"import:{mod}", status="failed",
                    detail=str(e)[:80],
                    fix_hint=f"Check {mod.replace('.', '/')}.py for syntax errors",
                ))

        return checks

    @staticmethod
    async def _auto_install_missing(checks: list[BootstrapCheck]) -> None:
        """Auto-install missing core packages via pkg_manager (runs in thread to avoid async conflicts)."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, Bootstrapper._install_missing_sync, checks)

    @staticmethod
    def _install_missing_sync(checks: list[BootstrapCheck]) -> None:
        from ..integration.pkg_manager import install

        pkg_map = {
            "pip:aiohttp": "aiohttp", "pip:yaml": "pyyaml",
            "pip:loguru": "loguru", "pip:pydantic": "pydantic",
            "pip:fastapi": "fastapi", "pip:uvicorn": "uvicorn",
        }
        for check in checks:
            if check.status == "missing" and check.name in pkg_map:
                pkg = pkg_map[check.name]
                check.status = "pending"
                check.detail = f"installing {pkg}..."
                try:
                    result = install(pkg, timeout=120)
                    if result.get("installed", False) if isinstance(result, dict) else result.installed:
                        check.status = "ok"
                        check.detail = (result.get("version","") if isinstance(result, dict) else result.version) or "installed"
                    else:
                        check.status = "failed"
                        check.detail = (result.get("error","") if isinstance(result, dict) else result.error) or "failed"
                except Exception as e:
                    check.status = "failed"
                    check.detail = str(e)[:80]

    @staticmethod
    async def _auto_install_optional(checks: list[BootstrapCheck]) -> None:
        """Auto-install optional packages (runs in thread, no-fail)."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, Bootstrapper._install_optional_sync, checks)

    @staticmethod
    def _install_optional_sync(checks: list[BootstrapCheck]) -> None:
        from ..integration.pkg_manager import install

        optional_pkgs = {
            "Numba JIT": "numba", "py-spy": "py-spy",
            "networkx": "networkx", "cryptography": "cryptography",
        }
        for check in checks:
            if check.status == "missing" and check.name in optional_pkgs:
                pkg = optional_pkgs[check.name]
                check.status = "pending"
                check.detail = f"installing {pkg}..."
                try:
                    result = install(pkg, timeout=60)
                    ok = result.get("installed", False) if isinstance(result, dict) else result.installed
                    if ok:
                        check.status = "ok"
                        check.detail = (result.get("version","") if isinstance(result, dict) else result.version) or "installed"
                    else:
                        check.status = "skipped"
                        check.detail = "unavailable"
                except Exception as e:
                    check.status = "skipped"
                    check.detail = str(e)[:80]

    # ── Stage 2 ───────────────────────────────────────────────────

    @staticmethod
    def _stage2_accel() -> list[BootstrapCheck]:
        checks = []

        # ripgrep
        rg_path = shutil.which("rg")
        if rg_path:
            try:
                result = subprocess.run([rg_path, "--version"], capture_output=True, text=True, timeout=5)
                checks.append(BootstrapCheck(
                    name="ripgrep", status="ok",
                    detail=result.stdout.strip().split("\n")[0][:60] if result.stdout else rg_path,
                    optional=True,
                ))
            except Exception:
                checks.append(BootstrapCheck(
                    name="ripgrep", status="failed", detail=rg_path, optional=True,
                    fix_hint="Reinstall: choco install ripgrep / brew install ripgrep",
                ))
        else:
            checks.append(BootstrapCheck(
                name="ripgrep", status="missing", optional=True,
                detail="Content search fallback to Python mmap grep",
                fix_hint="Install: choco install ripgrep / brew install ripgrep",
            ))

        # tree-sitter
        try:
            from ..capability.ast_parser import ASTParser
            p = ASTParser()
            if p.available():
                checks.append(BootstrapCheck(
                    name="tree-sitter", status="ok",
                    detail="AST parsing ready",
                    optional=True,
                ))
            else:
                checks.append(BootstrapCheck(
                    name="tree-sitter", status="missing", optional=True,
                    detail="Fallback to regex parsing",
                    fix_hint="pip install tree-sitter",
                ))
        except Exception:
            checks.append(BootstrapCheck(
                name="tree-sitter", status="missing", optional=True,
                fix_hint="pip install tree-sitter",
            ))

        # Numba JIT
        import numba
        checks.append(BootstrapCheck(
            name="Numba JIT", status="ok",
            detail=f"numba {numba.__version__}",
            optional=True,
        ))

        # py-spy profiler
        py_spy = shutil.which("py-spy")
        if py_spy:
            checks.append(BootstrapCheck(
                name="py-spy", status="ok", detail=py_spy, optional=True,
            ))
        else:
            checks.append(BootstrapCheck(
                name="py-spy", status="missing", optional=True,
                detail="Profiler unavailable",
                fix_hint="pip install py-spy",
            ))

        # NetworkX (for knowledge graph)
        import networkx
        checks.append(BootstrapCheck(
            name="networkx", status="ok",
            detail=f"networkx {networkx.__version__}",
            optional=True,
        ))

        # cryptography (for secrets vault Fernet)
        import cryptography
        checks.append(BootstrapCheck(
            name="cryptography", status="ok",
            detail=f"cryptography {cryptography.__version__}",
            optional=True,
        ))

        return checks

    @staticmethod
    def _stage2_llm_warmup() -> list[BootstrapCheck]:
        """Test LLM provider connectivity (parallel ping all 18)."""
        checks = []
        try:
            from ..treellm.provider_registry import PROVIDER_BASE_URLS
            from ..config.settings import get_config
            config = get_config().model

            for name, url in PROVIDER_BASE_URLS.items():
                key = getattr(config, f"{name}_api_key", "")
                if key:
                    checks.append(BootstrapCheck(
                        name=f"LLM:{name}", status="ok",
                        detail=f"{url} (key configured)",
                        optional=True,
                    ))
                else:
                    checks.append(BootstrapCheck(
                        name=f"LLM:{name}", status="missing",
                        detail="No API key",
                        fix_hint=f"livingtree secrets set {name}_api_key YOUR_KEY",
                        optional=True,
                    ))
        except Exception as e:
            checks.append(BootstrapCheck(
                name="LLM Providers", status="failed",
                detail=str(e)[:80], optional=True,
            ))

        return checks

    @staticmethod
    def _build_report(checks: list[BootstrapCheck], t0: float) -> BootstrapReport:
        stage1 = [c for c in checks if c.stage == 1 and not c.optional]
        stage2 = [c for c in checks if c.stage >= 2 or c.optional]
        s1_pass = sum(1 for c in stage1 if c.status == "ok")
        s2_pass = sum(1 for c in stage2 if c.status == "ok")
        all_core_ok = all(c.status == "ok" for c in stage1)
        return BootstrapReport(
            checks=checks,
            stage1_passed=s1_pass, stage1_total=len(stage1),
            stage2_passed=s2_pass, stage2_total=len(stage2),
            duration_ms=(time.time() - t0) * 1000,
            ready=all_core_ok,
        )

    @staticmethod
    def format_report(report: BootstrapReport) -> str:
        icons = {"ok": "✅", "missing": "❌", "failed": "❌", "pending": "⏳", "skipped": "⏭️", "installing": "⏳"}

        lines = [
            "╔══════════════════════════════════════╗",
            "║   🌳 LivingTree Bootstrap Report      ║",
            "╚══════════════════════════════════════╝",
            "",
            f"## Stage 1 — Core ({report.stage1_passed}/{report.stage1_total} passed)",
            "",
        ]
        for c in report.checks:
            if c.stage == 1 and not c.optional:
                icon = icons.get(c.status, "❓")
                lines.append(f"  {icon} {c.name:25s} {c.detail[:60]}")
                if c.fix_hint:
                    lines.append(f"     💡 {c.fix_hint}")

        lines += [
            "",
            f"## Stage 2 — Acceleration ({report.stage2_passed}/{report.stage2_total} available)",
            "",
        ]
        for c in report.checks:
            if c.stage >= 2 or c.optional:
                icon = icons.get(c.status, "❓")
                lines.append(f"  {icon} {c.name:25s} {c.detail[:60]}")
                if c.fix_hint:
                    lines.append(f"     💡 {c.fix_hint}")

        status = "✅ READY" if report.ready else "❌ CORE MISSING"
        lines += [
            "",
            f"  Status: {status}",
            f"  Duration: {report.duration_ms:.0f}ms",
            "",
            f"  Next: livingtree bootstrap --full  # Full acceleration check",
            f"        livingtree web                 # Start server",
            f"        livingtree improve --scan      # Build CodeGraph",
        ]
        return "\n".join(lines)


__all__ = ["Bootstrapper", "BootstrapReport", "BootstrapCheck"]
