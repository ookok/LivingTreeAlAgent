"""Profiler — Runtime performance profiling via py-spy integration.

Sampling profiler that attaches to a running process or launches a new one:
  - Statistical sampling (py-spy) — low overhead, production-safe
  - Flamegraph generation (SVG)
  - Top-N hotspot ranking
  - Speedscope-compatible output
  - Timeline recording for temporal analysis
  - Memory allocation tracing (native extension support)

Profiling modes:
  - attach: connect to a running Python process by PID
  - launch: profile a command from start to finish
  - timeline: record sampling over time for pattern detection

Integration:
  profiler = get_profiler()
  report = await profiler.profile_process(pid=12345, duration=30)
  report = await profiler.profile_command("pytest tests/", duration=60)
  flame = await profiler.flamegraph(pid=12345, duration=30)
"""

from __future__ import annotations

import asyncio
import json
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .unified_exec import run, pip_install, ExecResult


@dataclass
class Hotspot:
    function: str
    file: str = ""
    line: int = 0
    self_pct: float = 0.0     # percentage of samples in this function
    total_pct: float = 0.0     # percentage including children
    samples: int = 0
    module: str = ""


@dataclass
class FrameNode:
    name: str
    value: int = 0             # sample count
    children: list["FrameNode"] = field(default_factory=list)


@dataclass
class ProfileReport:
    hotspots: list[Hotspot] = field(default_factory=list)
    flamegraph_svg: str = ""                        # raw SVG content
    speedscope_json: str = ""                       # speedscope-compatible JSON
    summary: str = ""
    total_samples: int = 0
    duration_s: float = 0.0
    sampling_rate_hz: float = 100.0
    top_function: str = ""
    top_pct: float = 0.0
    pid: int = 0
    error: str = ""
    raw_output: str = ""


class ProfileMode:
    ATTACH = "attach"
    LAUNCH = "launch"
    TIMELINE = "timeline"


class Profiler:
    """py-spy based statistical profiling as a living tool."""

    _instance: Optional["Profiler"] = None

    @classmethod
    def instance(cls) -> "Profiler":
        if cls._instance is None:
            cls._instance = Profiler()
        return cls._instance

    def __init__(self):
        self._reports: list[ProfileReport] = []
        self._py_spy_available: bool | None = None
        self._default_duration: float = 30.0
        self._sampling_rate: int = 100     # Hz

    async def _ensure_py_spy(self) -> bool:
        if self._py_spy_available is not None:
            return self._py_spy_available
        result = await run("py-spy --version", timeout=10)
        self._py_spy_available = result.success
        if not self._py_spy_available:
            installed = await pip_install("py-spy", timeout=60)
            self._py_spy_available = installed
        return self._py_spy_available is True

    # ── Profiling APIs ───────────────────────────────────────

    async def profile_process(self, pid: int, duration: float = 0) -> ProfileReport:
        """Profile a running Python process by PID."""
        if not await self._ensure_py_spy():
            return ProfileReport(error="py-spy not available; install with: pip install py-spy")

        dur = duration or self._default_duration
        target = str(pid)

        native_flag = "--native" if self._has_native_support(pid) else ""
        result = await run(
            f"py-spy record --pid {target} --duration {int(dur)} "
            f"--rate {self._sampling_rate} {native_flag} --format raw --output - 2>&1",
            timeout=dur + 30,
        )
        return self._parse_raw_output(result, pid, dur)

    async def profile_command(self, command: str, duration: float = 0) -> ProfileReport:
        """Profile a command from start to finish."""
        if not await self._ensure_py_spy():
            return ProfileReport(error="py-spy not available; install with: pip install py-spy")

        dur = duration or self._default_duration
        result = await run(
            f"py-spy record -- {command}",
            timeout=dur + 60,
        )

        if not result.stdout.strip():
            result = await run(
                f"py-spy record --duration {int(dur)} --rate {self._sampling_rate} "
                f"--format raw --output - -- {command} 2>&1",
                timeout=dur + 60,
            )

        return self._parse_raw_output(result, 0, dur)

    async def flamegraph(self, pid: int = 0, command: str = "",
                         duration: float = 0) -> ProfileReport:
        """Generate a flamegraph SVG for a process or command."""
        if not await self._ensure_py_spy():
            return ProfileReport(error="py-spy not available")

        dur = duration or self._default_duration

        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            svg_path = f.name

        try:
            if pid:
                result = await run(
                    f"py-spy record --pid {pid} --duration {int(dur)} "
                    f"--rate {self._sampling_rate} --output {svg_path} 2>&1",
                    timeout=dur + 30,
                )
            else:
                result = await run(
                    f"py-spy record --duration {int(dur)} --rate {self._sampling_rate} "
                    f"--output {svg_path} -- {command} 2>&1",
                    timeout=dur + 60,
                )

            svg_content = ""
            try:
                svg_content = Path(svg_path).read_text(errors="replace")
            except Exception:
                pass

            report = self._parse_raw_output(result, pid, dur)
            report.flamegraph_svg = svg_content

            try:
                Path(svg_path).unlink(missing_ok=True)
            except Exception:
                pass

            return report
        except Exception as e:
            try:
                Path(svg_path).unlink(missing_ok=True)
            except Exception:
                pass
            return ProfileReport(error=str(e)[:500])

    async def top(self, pid: int = 0, command: str = "",
                  top_n: int = 20, duration: float = 0) -> ProfileReport:
        """Live top-like hotspot view, returning top-N functions."""
        if not await self._ensure_py_spy():
            return ProfileReport(error="py-spy not available")

        dur = duration or self._default_duration

        if pid:
            result = await run(
                f"py-spy top --pid {pid} --rate {self._sampling_rate} "
                f"--output json 2>&1",
                timeout=dur + 30,
            )
        else:
            result = await run(
                f"py-spy top -- {command} 2>&1",
                timeout=dur + 60,
            )

        report = ProfileReport(pid=pid, duration_s=dur)
        if result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                for item in data[:top_n]:
                    report.hotspots.append(Hotspot(
                        function=item.get("function", ""),
                        file=item.get("filename", ""),
                        line=item.get("line", 0),
                        self_pct=item.get("own_time_percent", 0),
                        total_pct=item.get("total_time_percent", 0),
                        samples=item.get("samples", 0),
                        module=item.get("module", ""),
                    ))
            except json.JSONDecodeError:
                pass

        report.summary = self._build_summary(report)
        self._reports.append(report)
        return report

    async def timeline(self, pid: int, duration: float = 0) -> ProfileReport:
        """Record sampling timeline for pattern analysis."""
        if not await self._ensure_py_spy():
            return ProfileReport(error="py-spy not available")

        dur = duration or self._default_duration
        result = await run(
            f"py-spy record --pid {pid} --duration {int(dur)} "
            f"--rate {self._sampling_rate} --format speedscope "
            f"--output - 2>&1",
            timeout=dur + 30,
        )

        report = self._parse_raw_output(result, pid, dur)
        if result.stdout.strip():
            try:
                json.loads(result.stdout)
                report.speedscope_json = result.stdout
            except json.JSONDecodeError:
                pass

        return report

    # ── Parsing ──────────────────────────────────────────────

    def _parse_raw_output(self, result: ExecResult,
                          pid: int, duration: float) -> ProfileReport:
        report = ProfileReport(pid=pid, duration_s=duration,
                               sampling_rate_hz=self._sampling_rate,
                               raw_output=result.stdout[:100000])

        if result.stderr and not result.stdout:
            report.error = result.stderr[:500]
            report.summary = f"Profiling error: {result.stderr[:200]}"
            return report

        if not result.stdout.strip():
            report.summary = "No profiling samples collected."
            return report

        report.hotspots = self._parse_raw_frames(result.stdout)

        if report.hotspots:
            report.top_function = report.hotspots[0].function
            report.top_pct = report.hotspots[0].self_pct
            report.total_samples = sum(h.samples for h in report.hotspots)

        report.summary = self._build_summary(report)
        self._reports.append(report)
        return report

    def _parse_raw_frames(self, raw: str) -> list[Hotspot]:
        """Parse py-spy raw format output.

        Format: function (file:line) count
        Thread/Process headers are skipped.
        """
        hotspots: list[Hotspot] = []
        frame_re = re.compile(
            r'^\s*(.+?)\s+\((.+?):(\d+)\)\s+(\d+)$'
        )

        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            m = frame_re.match(line)
            if not m:
                continue
            function = m.group(1).strip()
            file = m.group(2).strip()
            line_no = int(m.group(3))
            count = int(m.group(4))
            hotspots.append(Hotspot(
                function=function, file=file, line=line_no,
                samples=count, self_pct=0, total_pct=0,
            ))

        if not hotspots:
            return []

        total = sum(h.samples for h in hotspots)
        if total > 0:
            for h in hotspots:
                h.self_pct = round(h.samples / total * 100, 2)

        hotspots.sort(key=lambda h: h.samples, reverse=True)
        return hotspots

    def _has_native_support(self, pid: int) -> bool:
        try:
            import ctypes, sys
            if sys.platform != "linux":
                return False
            return True
        except Exception:
            return False

    @staticmethod
    def _build_summary(report: ProfileReport) -> str:
        if report.error:
            return f"Profile failed: {report.error[:200]}"
        parts = [
            f"PID={report.pid}, {report.duration_s:.1f}s, @{report.sampling_rate_hz}Hz",
            f"Top: {report.top_function[:60]} ({report.top_pct:.1f}%)" if report.top_function else "No data",
        ]
        if report.flamegraph_svg:
            parts.append(f"Flamegraph: {len(report.flamegraph_svg)} bytes SVG")
        return " | ".join(parts)

    def stats(self) -> dict:
        return {"profiles": len(self._reports)}

    def clear_reports(self) -> None:
        self._reports.clear()

    # ── Markdown output ──────────────────────────────────────

    def format_markdown(self, report: ProfileReport) -> str:
        lines = [
            f"## Profile Report — {report.duration_s:.1f}s @{report.sampling_rate_hz}Hz",
            "",
            report.summary,
            "",
        ]
        if report.error:
            lines.append(f"**Error:** {report.error[:300]}")
            lines.append("")
            return "\n".join(lines)

        if report.hotspots:
            lines.append(f"### Top Hotspots ({len(report.hotspots)})")
            lines.append("")
            lines.append("| Rank | Function | File | Line | Samples | Self% |")
            lines.append("|------|----------|------|------|---------|-------|")
            for i, h in enumerate(report.hotspots[:30], 1):
                lines.append(
                    f"| {i} | {h.function[:50]} | {h.file[:30]} "
                    f"| L{h.line} | {h.samples} | {h.self_pct:.1f}% |"
                )

        if report.flamegraph_svg:
            lines.append("")
            lines.append("### Flamegraph")
            lines.append(f"<details><summary>SVG ({len(report.flamegraph_svg)} bytes)</summary>")
            lines.append("")
            lines.append(report.flamegraph_svg)
            lines.append("")
            lines.append("</details>")

        lines.append("")
        return "\n".join(lines)


_profiler: Optional[Profiler] = None


def get_profiler() -> Profiler:
    global _profiler
    if _profiler is None:
        _profiler = Profiler()
    return _profiler


__all__ = ["Profiler", "ProfileReport", "Hotspot", "FrameNode",
           "ProfileMode", "get_profiler"]
