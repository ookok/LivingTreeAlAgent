"""TUI Orchestrator v2 — routes LLM structured output through Toad's ACP widgets.

Toad's Conversation natively renders these message types:
  - Update(type, text)          → AgentResponse (markdown streaming)
  - Thinking(type, text)        → AgentThought (collapsible thinking)
  - ToolCall(tool_call)         → ToolCall widget (expandable, diffs/text/markdown)
  - ToolCallUpdate(tool_call, update) → updates ToolCall in-place
  - Plan(entries)               → Plan widget in SideBar
  - AvailableCommandsUpdate     → slash commands in prompt

This orchestrator maps our 10 output schemas to Toad's native ACP messages,
so structured LLM output renders automatically in the correct Toad widget.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from .response_schemas import OutputType, get_schema, get_system_prompt
from .response_parser import ResponseParser, ParsedOutput


@dataclass
class ACPDispatch:
    """A Toad ACP message to post, with its payload."""
    message_type: str  # "update", "thinking", "tool_call", "plan", "commands"
    payload: dict[str, Any]
    widget_hint: str = ""


@dataclass
class OrchestrationStats:
    total_requests: int = 0
    structured_hits: int = 0
    parse_failures: int = 0
    widget_renders: dict[str, int] = field(default_factory=dict)
    avg_latency_ms: float = 0.0


class ToadOrchestrator:
    """Routes LLM structured output → Toad ACP messages → Toad widgets.

    On each LLM response:
      1. Parse JSON blocks → detect output type
      2. Map to Toad ACP message (Update/Thinking/ToolCall/Plan)
      3. Track success for self-evolution
      4. Evolve system prompt every 50 requests
    """

    EVOLVE_INTERVAL = 50
    STATS_FILE = Path(".livingtree/orchestrator_stats.json")

    def __init__(self):
        self.parser = ResponseParser()
        self.stats = OrchestrationStats()
        self._request_count = 0
        self._latency_samples: list[float] = []
        self._load_stats()

    def get_system_prompt(self) -> str:
        """Generate the LLM system prompt with Toad output formats + system tools + formulas."""
        base = get_system_prompt()

        try:
            from ..tui.widgets.enhanced_tool_call import format_tool_list, SYSTEM_TOOLS
            tool_list = format_tool_list()

            # Append formulas for physics tools (老子→方程)
            formula_lines = ["\n## PHYSICS MODELS — Exact Formulas", ""]
            for name, tool in SYSTEM_TOOLS.items():
                if tool.get("category") == "physics" and tool.get("formula"):
                    formula_lines.append(f"### {tool['name']} ({name})")
                    formula_lines.append(f"**公式**: {tool['formula']}")
                    formula_lines.append(f"**参数**: {', '.join(f'{k}: {v}' for k, v in tool['params'].items())}")
                    formula_lines.append(f"**输出**: {tool.get('output', 'N/A')}")
                    formula_lines.append(f"**标准**: {tool.get('standard', 'N/A')}")
                    formula_lines.append("")
                    formula_lines.append("**何时使用**: 当用户提供具体数值需要精确计算时，使用 /compute 命令。")
                    formula_lines.append("当用户描述场景需要定性分析时，使用文字描述 + 引用模型名称。")
                    formula_lines.append("")
            tool_list += "\n" + "\n".join(formula_lines)
        except Exception:
            tool_list = ""

        return base + "\n\n## Available System Tools\n" + tool_list

    def process(self, llm_output: str) -> list[ACPDispatch]:
        """Parse LLM output → list of Toad ACP dispatches."""
        t0 = time.monotonic()
        self._request_count += 1
        self.stats.total_requests += 1

        outputs = self.parser.parse(llm_output)
        dispatches = []

        for out in outputs:
            if not out.is_valid:
                self.stats.parse_failures += 1
                continue

            dispatch = self._to_acp(out)
            if dispatch:
                dispatches.append(dispatch)
                self.stats.structured_hits += 1
                self.stats.widget_renders[dispatch.widget_hint] = (
                    self.stats.widget_renders.get(dispatch.widget_hint, 0) + 1
                )

        elapsed = (time.monotonic() - t0) * 1000
        self._latency_samples.append(elapsed)
        if len(self._latency_samples) > 100:
            self._latency_samples = self._latency_samples[-100:]
        self.stats.avg_latency_ms = sum(self._latency_samples) / len(self._latency_samples)

        if self._request_count % self.EVOLVE_INTERVAL == 0:
            self._evolve()

        return dispatches

    def _to_acp(self, out: ParsedOutput) -> ACPDispatch | None:
        """Map parsed output to a Toad ACP message type."""
        data = out.data
        otype = out.output_type

        if otype == OutputType.CHAT:
            return ACPDispatch(
                message_type="update",
                payload={"type": "text", "text": data.get("content", "")},
                widget_hint="AgentResponse",
            )

        elif otype == OutputType.TOOL_CALL:
            # Toad's ToolCall widget expects acp protocol.ToolCall format
            tool_call = {
                "toolCallId": f"orch-{int(time.time()*1000)}",
                "title": data.get("tool", "tool"),
                "status": "in_progress",
                "rawInput": {"toolName": data.get("tool", ""), "toolArgs": data.get("params", {})},
                "kind": "text",
            }
            return ACPDispatch(
                message_type="tool_call",
                payload={"tool_call": tool_call},
                widget_hint="ToolCall",
            )

        elif otype == OutputType.CODE:
            text = self._format_code(data)
            return ACPDispatch(
                message_type="update",
                payload={"type": "text", "text": text},
                widget_hint="AgentResponse",
            )

        elif otype == OutputType.DIFF:
            # Toad's ToolCall with diff content
            tool_call = {
                "toolCallId": f"diff-{int(time.time()*1000)}",
                "title": f"Diff: {data.get('filename', 'file')}",
                "status": "completed",
                "rawInput": {"description": data.get("description", "")},
                "kind": "diff",
            }
            # ToolCall with diff uses ToolCallUpdate to provide before/after
            return ACPDispatch(
                message_type="tool_call",
                payload={"tool_call": tool_call},
                widget_hint="ToolCall",
            )

        elif otype == OutputType.CHART:
            text = self._format_chart(data)
            return ACPDispatch(
                message_type="update",
                payload={"type": "text", "text": text},
                widget_hint="AgentResponse",
            )

        elif otype == OutputType.MAP:
            text = self._format_map(data)
            return ACPDispatch(
                message_type="update",
                payload={"type": "text", "text": text},
                widget_hint="AgentResponse",
            )

        elif otype == OutputType.TABLE:
            text = self._format_table(data)
            return ACPDispatch(
                message_type="update",
                payload={"type": "text", "text": text},
                widget_hint="AgentResponse",
            )

        elif otype == OutputType.DOCUMENT:
            text = self._format_document(data)
            return ACPDispatch(
                message_type="update",
                payload={"type": "text", "text": text},
                widget_hint="AgentResponse",
            )

        elif otype == OutputType.PLAN:
            steps = data.get("steps", [])
            entries = []
            for s in steps:
                entries.append({
                    "entry": s.get("name", str(s)),
                    "priority": s.get("priority", "medium"),
                    "status": s.get("status", "pending"),
                })
            return ACPDispatch(
                message_type="plan",
                payload={"entries": entries},
                widget_hint="Plan",
            )

        elif otype == OutputType.SEARCH:
            text = self._format_search(data)
            return ACPDispatch(
                message_type="update",
                payload={"type": "text", "text": text},
                widget_hint="AgentResponse",
            )

        return None

    # ═══ Format helpers — produce markdown for AgentResponse ═══

    @staticmethod
    def _format_code(data: dict) -> str:
        lang = data.get("language", "")
        code = data.get("code", "")
        explanation = data.get("explanation", "")
        lines = []
        if explanation:
            lines.append(explanation)
        lines.append(f"```{lang}\n{code}\n```")
        filename = data.get("filename", "")
        if filename:
            lines.append(f"*Suggested filename: `{filename}`*")
        return "\n\n".join(lines)

    @staticmethod
    def _format_chart(data: dict) -> str:
        title = data.get("title", "Chart")
        chart_type = data.get("chart_type", "bar")
        d = data.get("data", {})
        labels = d.get("labels", [])
        values = d.get("values", [])
        points = d.get("points", [])

        lines = [f"### 📊 {title}", ""]
        if labels and values:
            lines.append("| Label | Value |")
            lines.append("|-------|-------|")
            for l, v in zip(labels, values):
                lines.append(f"| {l} | {v} |")
        elif points:
            lines.append("| X | Y |")
            lines.append("|---|---|")
            for x, y in points:
                lines.append(f"| {x} | {y} |")
        lines.append("")
        lines.append(f"*Chart type: {chart_type}*")
        return "\n".join(lines)

    @staticmethod
    def _format_map(data: dict) -> str:
        lat = data.get("lat", 0)
        lon = data.get("lon", 0)
        zoom = data.get("zoom", 12)
        label = data.get("label", "")
        return (
            f"### 🗺 {label or 'Location'}\n\n"
            f"📍 **Coordinates**: {lat:.4f}, {lon:.4f} (zoom {zoom})\n\n"
            f"*Open in maps: [Google Maps](https://maps.google.com/?q={lat},{lon}) | "
            f"[OpenStreetMap](https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom={zoom})*"
        )

    @staticmethod
    def _format_table(data: dict) -> str:
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        title = data.get("title", "")
        lines = []
        if title:
            lines.append(f"### {title}")
            lines.append("")
        if headers:
            lines.append("| " + " | ".join(str(h) for h in headers) + " |")
            lines.append("|" + "|".join("---" for _ in headers) + "|")
            for row in rows:
                cells = [str(c) for c in row]
                # Pad to match header count
                while len(cells) < len(headers):
                    cells.append("")
                lines.append("| " + " | ".join(cells[:len(headers)]) + " |")
        return "\n".join(lines)

    @staticmethod
    def _format_document(data: dict) -> str:
        title = data.get("title", "Document")
        content = data.get("content", "")
        fmt = data.get("format", "markdown")
        sections = data.get("sections", [])
        lines = [f"### 📄 {title}", ""]
        if sections:
            lines.append("**Sections:** " + " → ".join(str(s) for s in sections))
            lines.append("")
        lines.append(content if fmt == "markdown" else f"```\n{content}\n```")
        return "\n".join(lines)

    @staticmethod
    def _format_search(data: dict) -> str:
        query = data.get("query", "")
        results = data.get("results", [])
        lines = [f"### 🔍 Search: {query}", ""]
        for r in results:
            title = r.get("title", r.get("name", ""))
            url = r.get("url", r.get("href", ""))
            summary = r.get("summary", r.get("body", ""))
            lines.append(f"- **[{title}]({url})**")
            if summary:
                lines.append(f"  {summary[:200]}")
            lines.append("")
        return "\n".join(lines)

    # ═══ Self-evolution ═══

    def feed_back(self, output_type: OutputType, success: bool, text: str = ""):
        schema = get_schema(output_type)
        schema.usage_count += 1
        if success:
            schema.success_count += 1
        if not success and text:
            self.parser.learn_pattern(text, output_type)

    def _evolve(self):
        weak = []
        for stype, stats in self.parser._stats.items():
            if isinstance(stype, OutputType):
                rate = stats["success"] / max(stats["total"], 1)
                if stats["total"] > 5 and rate < 0.5:
                    weak.append((stype, rate))

        if weak:
            for stype, _ in weak:
                schema = get_schema(stype)
                if "IMPORTANT" not in schema.prompt_hint:
                    schema.prompt_hint = (
                        f"IMPORTANT: Always output in this format for {stype.value}.\n"
                        + schema.prompt_hint
                    )

        self._save_stats()
        logger.info(
            f"ToadOrch: {self.stats.total_requests} reqs, "
            f"{self.stats.structured_hits} structured, "
            f"{self.stats.parse_failures} fails"
        )

    def get_status(self) -> dict:
        return {
            "total_requests": self.stats.total_requests,
            "structured_hits": self.stats.structured_hits,
            "hit_rate": self.stats.structured_hits / max(self.stats.total_requests, 1),
            "parse_failures": self.stats.parse_failures,
            "avg_latency_ms": round(self.stats.avg_latency_ms, 1),
            "widget_renders": dict(self.stats.widget_renders),
            "parser_stats": self.parser.get_stats(),
        }

    def _save_stats(self):
        try:
            self.STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.STATS_FILE.write_text(json.dumps(self.get_status(), indent=2))
        except Exception:
            pass

    def _load_stats(self):
        try:
            if self.STATS_FILE.exists():
                data = json.loads(self.STATS_FILE.read_text())
                self.stats.total_requests = data.get("total_requests", 0)
                self.stats.structured_hits = data.get("structured_hits", 0)
        except Exception:
            pass


# ═══ Global singleton ═══

_orchestrator: ToadOrchestrator | None = None


def get_orchestrator() -> ToadOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ToadOrchestrator()
    return _orchestrator
