"""LSP Manager — Language Server Protocol inline diagnostics.

Backed by OpenCode's LSP infrastructure (30+ languages). Delegates to
opencode's auto-detection of language servers. Falls back to direct CLI
tools when opencode bridge is unavailable.

Usage:
    lsp = LSPManager()
    await lsp.start()
    diags = await lsp.check_file("src/main.py")
"""
# DEPRECATED — candidate for removal. No active references found.


from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class LSPDiagnostic:
    file_path: str
    line: int
    column: int = 0
    severity: str = "warning"
    message: str = ""
    source: str = ""

    def format_inline(self) -> str:
        icon = {"error": "E", "warning": "W", "info": "I", "hint": "H"}.get(self.severity, "")
        return f"  [{icon}] L{self.line}:{self.column} {self.message}"


@dataclass
class LSPCheckResult:
    file_path: str
    diagnostics: list[LSPDiagnostic] = field(default_factory=list)
    errors: int = 0
    warnings: int = 0
    infos: int = 0
    duration_ms: float = 0.0


class LSPManager:

    def __init__(self, opencode_bin: str = ""):
        self._opencode_bridge = None
        self._opencode_bin = opencode_bin
        self._running = False

    async def start(self) -> None:
        self._running = True
        # OpenCodeLSPBridge removed (TUI stub). LSP operates standalone.
        logger.debug("LSP Manager started (opencode bridge unavailable — TUI removed)")

    async def stop(self) -> None:
        self._running = False

    async def check_file(self, file_path: str | Path) -> LSPCheckResult:
        t0 = time.monotonic()
        path = Path(file_path)
        if not path.exists():
            return LSPCheckResult(file_path=str(path))

        result = LSPCheckResult(file_path=str(path))

        if self._opencode_bridge:
            try:
                diags = await self._opencode_bridge.check_file(path)
                result.diagnostics = [
                    LSPDiagnostic(
                        file_path=d.file_path, line=d.line, column=d.column,
                        severity=d.severity, message=d.message, source=f"opencode:{d.source}",
                    )
                    for d in diags
                ]
            except Exception as e:
                logger.debug(f"LSP check: {e}")

        result.errors = sum(1 for d in result.diagnostics if d.severity == "error")
        result.warnings = sum(1 for d in result.diagnostics if d.severity == "warning")
        result.infos = sum(1 for d in result.diagnostics if d.severity == "info")
        result.duration_ms = (time.monotonic() - t0) * 1000
        return result

    async def check_files(self, file_paths: list[str | Path]) -> list[LSPCheckResult]:
        return await asyncio.gather(*[self.check_file(p) for p in file_paths])

    def format_diagnostics_summary(self, result: LSPCheckResult) -> str:
        if not result.diagnostics:
            return ""
        lines = [f"\nLSP Diagnostics — {Path(result.file_path).name}"]
        lines.append(f"  {result.errors} errors, {result.warnings} warnings")
        for d in result.diagnostics[:15]:
            lines.append(d.format_inline())
        if len(result.diagnostics) > 15:
            lines.append(f"  ... and {len(result.diagnostics) - 15} more")
        return "\n".join(lines)
