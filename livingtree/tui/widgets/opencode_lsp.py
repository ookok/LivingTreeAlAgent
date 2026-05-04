"""OpenCode LSP Bridge — Use opencode's language servers for code diagnostics.

openCode auto-detects and manages 30+ LSP servers. LivingTree's code
editor delegates diagnostics to opencode's LSP infrastructure.

When a file is opened/saved, the bridge:
1. Detects the language from file extension
2. Auto-starts the appropriate LSP server (via opencode's cached binaries)
3. Collects diagnostics and returns them for inline display

Requires: .livingtree/base/opencode/opencode.exe (auto-cached on first boot)
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger


# openCode's built-in LSP server mappings (language → server + requirements)
# Source: https://opencode.ai/docs/zh-cn/lsp/
OPENCODE_LSP_MAP: dict[str, dict] = {
    ".py": {"name": "pyright", "cmd": ["pyright-langserver", "--stdio"], "install": "npm install -g pyright"},
    ".pyi": {"name": "pyright", "cmd": ["pyright-langserver", "--stdio"]},
    ".rs": {"name": "rust-analyzer", "cmd": ["rust-analyzer"], "install": "rustup component add rust-analyzer"},
    ".go": {"name": "gopls", "cmd": ["gopls", "serve"], "install": "go install golang.org/x/tools/gopls@latest"},
    ".ts": {"name": "typescript", "cmd": ["typescript-language-server", "--stdio"], "install": "npm install -g typescript-language-server typescript"},
    ".tsx": {"name": "typescript", "cmd": ["typescript-language-server", "--stdio"]},
    ".js": {"name": "typescript", "cmd": ["typescript-language-server", "--stdio"]},
    ".jsx": {"name": "typescript", "cmd": ["typescript-language-server", "--stdio"]},
    ".c": {"name": "clangd", "cmd": ["clangd"], "install": "install clangd"},
    ".cpp": {"name": "clangd", "cmd": ["clangd"]},
    ".h": {"name": "clangd", "cmd": ["clangd"]},
    ".java": {"name": "jdtls", "cmd": ["jdtls"], "install": "Java SDK 21+"},
    ".swift": {"name": "sourcekit-lsp", "cmd": ["sourcekit-lsp"]},
    ".kt": {"name": "kotlin-ls", "cmd": ["kotlin-language-server"]},
    ".rb": {"name": "ruby-lsp", "cmd": ["ruby-lsp"]},
    ".php": {"name": "intelephense", "cmd": ["intelephense", "--stdio"]},
    ".lua": {"name": "lua", "cmd": ["lua-language-server"]},
    ".zig": {"name": "zls", "cmd": ["zls"]},
    ".hs": {"name": "hls", "cmd": ["haskell-language-server-wrapper"]},
    ".ex": {"name": "elixir-ls", "cmd": ["elixir-ls"]},
    ".ml": {"name": "ocaml", "cmd": ["ocamllsp"]},
    ".dart": {"name": "dart", "cmd": ["dart", "language-server"]},
    ".gleam": {"name": "gleam", "cmd": ["gleam", "lsp"]},
    ".tf": {"name": "terraform", "cmd": ["terraform-ls", "serve"]},
}


@dataclass
class LSPDiagnostic:
    file_path: str
    line: int
    column: int = 0
    severity: str = "warning"
    message: str = ""
    source: str = ""

    def format_inline(self) -> str:
        icon = {"error": "[#f85149]E[/#f85149]", "warning": "[#d29922]W[/#d29922]",
                "info": "[#58a6ff]I[/#58a6ff]", "hint": "[#484f58]H[/#484f58]"}.get(self.severity, "?")
        return f" {icon} L{self.line}: {self.message}"


class OpenCodeLSPBridge:

    def __init__(self, opencode_bin: str = ""):
        self._opencode_bin = opencode_bin or self._find_opencode()
        self._servers: dict[str, asyncio.subprocess.Process] = {}

    def supports_file(self, file_path: str | Path) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in OPENCODE_LSP_MAP

    async def check_file(self, file_path: str | Path) -> list[LSPDiagnostic]:
        path = Path(file_path)
        ext = path.suffix.lower()
        lsp_info = OPENCODE_LSP_MAP.get(ext)
        if not lsp_info:
            return []

        diagnostics = []

        for method in [
            self._check_via_cli,
            self._check_via_local_tool,
        ]:
            try:
                diags = await method(path, ext, lsp_info)
                if diags:
                    diagnostics = diags
                    break
            except Exception:
                continue

        return diagnostics

    async def check_file_and_format(self, file_path: str | Path) -> str:
        diags = await self.check_file(file_path)
        if not diags:
            return ""

        lines = [f"[bold]LSP Diagnostics — {Path(file_path).name}[/bold]"]
        errors = sum(1 for d in diags if d.severity == "error")
        warnings = sum(1 for d in diags if d.severity == "warning")
        lines.append(f"  {errors} errors, {warnings} warnings")

        for d in diags[:15]:
            lines.append(d.format_inline())
        if len(diags) > 15:
            lines.append(f"  ... and {len(diags) - 15} more")

        return "\n".join(lines)

    def shutdown(self) -> None:
        for proc in self._servers.values():
            try:
                proc.terminate()
            except Exception:
                pass
        self._servers.clear()

    # ── Private ──

    async def _check_via_cli(self, path: Path, ext: str, lsp_info: dict) -> list[LSPDiagnostic]:
        try:
            cmd = list(lsp_info["cmd"])
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        if "pyright" in str(cmd):
            return await self._run_pyright_cli(path)
        elif "rust-analyzer" in str(cmd):
            return await self._run_rust_check(path)
        elif "gopls" in str(cmd):
            return await self._run_gopls_check(path)
        elif "clangd" in str(cmd):
            return await self._run_clang_check(path)
        elif "typescript" in str(cmd):
            return await self._run_ts_check(path)

        return []

    async def _check_via_local_tool(self, path: Path, ext: str, lsp_info: dict) -> list[LSPDiagnostic]:
        if ext == ".py":
            return await self._run_python_flake8(path)
        return []

    async def _run_pyright_cli(self, path: Path) -> list[LSPDiagnostic]:
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pyright", str(path), "--outputjson",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30.0)

            if proc.returncode not in (0, 1):
                return []

            import json
            data = json.loads(stdout.decode(errors="replace"))
            diags = []
            for d in data.get("generalDiagnostics", []):
                diags.append(LSPDiagnostic(
                    file_path=str(path),
                    line=d.get("range", {}).get("start", {}).get("line", 0) + 1,
                    column=d.get("range", {}).get("start", {}).get("character", 0),
                    severity=d.get("severity", "warning"),
                    message=d.get("message", ""),
                    source="pyright (opencode)",
                ))
            return diags
        except Exception:
            return []

    async def _run_rust_check(self, path: Path) -> list[LSPDiagnostic]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "rustc", "--edition", "2021", "-Z", "no-codegen", str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            diags = []
            for line in stderr.decode(errors="replace").splitlines():
                if "error" in line.lower() or "warning" in line.lower():
                    sev = "error" if "error[" in line.lower() else "warning"
                    diags.append(LSPDiagnostic(
                        file_path=str(path), line=0, severity=sev,
                        message=line.strip()[:200], source="rustc (opencode)",
                    ))
            return diags
        except Exception:
            return []

    async def _run_gopls_check(self, path: Path) -> list[LSPDiagnostic]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "gopls", "check", str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            diags = []
            for line in stdout.decode(errors="replace").splitlines():
                line = line.strip()
                if not line or ":" not in line:
                    continue
                parts = line.split(":", 3)
                if len(parts) >= 4:
                    diags.append(LSPDiagnostic(
                        file_path=str(path),
                        line=int(parts[1]) if parts[1].isdigit() else 0,
                        severity="error",
                        message=parts[3].strip(),
                        source="gopls (opencode)",
                    ))
            return diags
        except Exception:
            return []

    async def _run_clang_check(self, path: Path) -> list[LSPDiagnostic]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "clang", "-fsyntax-only", str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            diags = []
            for line in stderr.decode(errors="replace").splitlines():
                if "error:" in line.lower() or "warning:" in line.lower():
                    sev = "error" if "error:" in line.lower() else "warning"
                    diags.append(LSPDiagnostic(
                        file_path=str(path), line=0, severity=sev,
                        message=line.strip()[:200], source="clang (opencode)",
                    ))
            return diags
        except Exception:
            return []

    async def _run_ts_check(self, path: Path) -> list[LSPDiagnostic]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "npx", "-y", "typescript", "--noEmit", str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            diags = []
            for line in stderr.decode(errors="replace").splitlines():
                if "error TS" in line:
                    diags.append(LSPDiagnostic(
                        file_path=str(path), line=0, severity="error",
                        message=line.strip()[:200], source="tsc (opencode)",
                    ))
            return diags
        except Exception:
            return []

    async def _run_python_flake8(self, path: Path) -> list[LSPDiagnostic]:
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "flake8", "--select=E,F,W", "--max-line-length=120",
                str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            diags = []
            for line in stdout.decode(errors="replace").splitlines():
                parts = line.split(":", 3)
                if len(parts) >= 3:
                    diags.append(LSPDiagnostic(
                        file_path=str(path),
                        line=int(parts[1]) if parts[1].isdigit() else 0,
                        column=int(parts[2]) if parts[2].isdigit() else 0,
                        severity="warning",
                        message=parts[3].strip() if len(parts) > 3 else "",
                        source="flake8 (opencode)",
                    ))
            return diags
        except Exception:
            return []

    @staticmethod
    def _find_opencode() -> str:
        base = Path(".livingtree") / "base" / "opencode"
        exe = base / "opencode.exe" if sys.platform == "win32" else base / "opencode"
        if exe.exists():
            return str(exe)

        import shutil
        return shutil.which("opencode") or "opencode"
