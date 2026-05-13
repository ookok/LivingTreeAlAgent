"""LivingRenderer — Capability-probing polymorphic rendering engine.

Rendering is capability negotiation between server and client, mediated by
performance constraints. Not "pick a format" — "find the best format that works."

Capability levels (ascending):
  L0: PLAIN   — text + ANSI color + spacing (terminal, curl, 1KB)
  L1: RICH    — Markdown/HTML styled (browser, HTMX, 5KB)
  L2: STRUCT  — tables, trees, key-value (structured data, 10KB)
  L3: VISUAL  — charts, diagrams, timelines (needs JS/Canvas, 50KB)
  L4: MEDIA   — images, audio, video (needs codecs, 500KB+)
  L5: SPATIAL — 3D, VR, AR (needs WebGL/WebXR, 2MB+)

Client probing sources:
  - Accept header          → MIME preference
  - User-Agent             → device + engine inference
  - Client-Hints (Sec-CH-*)→ explicit capability declaration
  - Query ?cap=level       → explicit override
  - Query ?max_bytes=N     → performance budget
  - Connection latency     → inferred from network

Integration:
  renderer = get_living_renderer()
  caps = renderer.probe(request)                    # → CapabilityProfile
  result = renderer.render(data, caps, format="auto") # → rendered output
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass, field
from enum import IntEnum
from html import escape
from typing import Any, Optional
from pathlib import Path

from loguru import logger


# ═══ Capability Levels ═════════════════════════════════════════════


class RenderLevel(IntEnum):
    PLAIN = 0       # Terminal-friendly text + ANSI
    RICH = 1        # Markdown → styled HTML
    STRUCT = 2      # Tables, trees, KV pairs
    VISUAL = 3      # Charts, diagrams, timelines
    MEDIA = 4       # Images, audio, video
    SPATIAL = 5     # 3D, VR, AR


LEVEL_NAMES = {
    0: "plain", 1: "rich", 2: "struct", 3: "visual", 4: "media", 5: "spatial",
}

# Approximate byte budget per level (safe defaults)
LEVEL_BUDGETS = {
    RenderLevel.PLAIN: 2000,
    RenderLevel.RICH: 8000,
    RenderLevel.STRUCT: 20000,
    RenderLevel.VISUAL: 80000,
    RenderLevel.MEDIA: 500000,
    RenderLevel.SPATIAL: 2000000,
}


# ═══ Data Types ════════════════════════════════════════════════════


@dataclass
class CapabilityProfile:
    """Client rendering capability profile."""
    max_level: RenderLevel = RenderLevel.RICH
    supports_html: bool = True
    supports_svg: bool = False
    supports_webgl: bool = False
    supports_audio: bool = False
    supports_video: bool = False
    max_bytes: int = 50000          # Performance budget
    prefers_dark: bool = False
    device_type: str = "desktop"    # desktop|mobile|terminal|embedded
    connection_rtt_ms: float = 50.0 # Network latency
    source: str = "inferred"        # "inferred"|"explicit"|"default"


@dataclass
class RenderResult:
    """Rendered output with metadata."""
    content: str                    # The rendered content
    mime_type: str                  # text/plain | text/html | image/svg+xml | ...
    level: RenderLevel
    byte_size: int
    render_time_ms: float
    truncated: bool = False
    degraded_from: Optional[RenderLevel] = None  # What level was requested vs delivered


# ═══ CapabilityProber ══════════════════════════════════════════════


class CapabilityProber:
    """Probes client rendering capability from HTTP request context."""

    # User-Agent patterns → capability inference
    UA_PATTERNS: list[tuple[str, dict]] = [
        # Terminals
        (r"curl|wget|httpie|HTTPie", {"max_level": RenderLevel.PLAIN, "device_type": "terminal"}),
        # Text browsers
        (r"lynx|w3m|elinks", {"max_level": RenderLevel.PLAIN, "device_type": "terminal"}),
        # Mobile
        (r"iPhone|Android.*Mobile|Mobile Safari", {"max_level": RenderLevel.RICH, "device_type": "mobile", "max_bytes": 20000}),
        # Tablets
        (r"iPad|Android(?!.*Mobile)", {"max_level": RenderLevel.VISUAL, "device_type": "tablet", "max_bytes": 80000}),
        # Modern desktop browsers
        (r"Chrome|Firefox|Edge|Safari", {"max_level": RenderLevel.VISUAL, "supports_svg": True, "supports_webgl": True, "supports_audio": True, "supports_video": True}),
        # HTMX (prefers HTML fragments)
        (r"HX-Request", {"max_level": RenderLevel.RICH, "supports_html": True}),
    ]

    def probe(self, request: Any = None, query_params: dict = None,
              headers: dict = None) -> CapabilityProfile:
        """Probe client capabilities from multiple sources.

        Priority: explicit > Client-Hints > User-Agent > defaults
        """
        caps = CapabilityProfile()
        caps.source = "default"

        # 1. Query parameter override (highest priority)
        if query_params:
            if "cap" in query_params:
                level_str = query_params["cap"].lower()
                for level in RenderLevel:
                    if LEVEL_NAMES.get(level.value) == level_str:
                        caps.max_level = level
                        caps.source = "explicit"
                        break
            if "max_bytes" in query_params:
                try:
                    caps.max_bytes = int(query_params["max_bytes"])
                    caps.source = "explicit"
                except ValueError:
                    pass
            if "dark" in query_params:
                caps.prefers_dark = query_params["dark"].lower() in ("1", "true", "yes")

        # 2. Headers (Accept, User-Agent, Client-Hints)
        if headers:
            ua = headers.get("user-agent", headers.get("User-Agent", ""))
            for pattern, overrides in self.UA_PATTERNS:
                if re.search(pattern, ua):
                    for k, v in overrides.items():
                        setattr(caps, k, v)
                    if caps.source == "default":
                        caps.source = "inferred"
                    break

            # Accept header → MIME preference
            accept = headers.get("accept", headers.get("Accept", ""))
            if "text/html" in accept:
                caps.supports_html = True
            if "image/svg" in accept:
                caps.supports_svg = True

            # Client-Hints
            if headers.get("sec-ch-viewport-width", ""):
                caps.device_type = "mobile" if int(headers.get("sec-ch-viewport-width", "1920")) < 768 else "desktop"
                caps.source = "explicit"
            if headers.get("sec-ch-prefers-color-scheme", "") == "dark":
                caps.prefers_dark = True

        # 3. Request object (FastAPI)
        if request is not None:
            try:
                ua = request.headers.get("user-agent", "")
                for pattern, overrides in self.UA_PATTERNS:
                    if re.search(pattern, ua):
                        for k, v in overrides.items():
                            if caps.source == "default":
                                setattr(caps, k, v)
                        caps.source = "inferred"
                        break
            except Exception:
                pass

        # 4. Cap max_level by byte budget
        for level in reversed(RenderLevel):
            if LEVEL_BUDGETS[level] <= caps.max_bytes:
                caps.max_level = min(caps.max_level, level)
                break

        return caps


# ═══ PerformanceGate ═══════════════════════════════════════════════


class PerformanceGate:
    """Ensures rendered output stays within performance budget."""

    def __init__(self):
        self._render_times: list[float] = []  # Sliding window of recent render times
        self._render_window = 20

    def should_degrade(self, data_size: int, target_level: RenderLevel,
                        budget_bytes: int) -> tuple[bool, RenderLevel]:
        """Check if we need to degrade rendering level for performance.

        Returns (should_degrade, recommended_level).
        """
        estimated = self._estimate_size(data_size, target_level)
        if estimated <= budget_bytes:
            return False, target_level

        # Find the highest level that fits
        for level in reversed(RenderLevel):
            if level > target_level:
                continue
            if LEVEL_BUDGETS[level] <= budget_bytes:
                logger.debug(
                    f"PerformanceGate: degrading {LEVEL_NAMES[target_level.value]}"
                    f" → {LEVEL_NAMES[level.value]} (est={estimated} > budget={budget_bytes})"
                )
                return True, level

        return True, RenderLevel.PLAIN

    def _estimate_size(self, data_size: int, level: RenderLevel) -> int:
        """Estimate rendered output size for a given level."""
        multipliers = {
            RenderLevel.PLAIN: 1.0,
            RenderLevel.RICH: 3.0,
            RenderLevel.STRUCT: 5.0,
            RenderLevel.VISUAL: 15.0,
            RenderLevel.MEDIA: 100.0,
            RenderLevel.SPATIAL: 500.0,
        }
        return int(data_size * multipliers.get(level, 5.0))

    def record_render_time(self, ms: float) -> None:
        self._render_times.append(ms)
        if len(self._render_times) > self._render_window:
            self._render_times = self._render_times[-self._render_window:]

    @property
    def avg_render_time_ms(self) -> float:
        if not self._render_times:
            return 0
        return sum(self._render_times) / len(self._render_times)


# ═══ LivingRenderer ═══════════════════════════════════════════════


class LivingRenderer:
    """Capability-probing, performance-aware polymorphic renderer."""

    _instance: Optional["LivingRenderer"] = None

    @classmethod
    def instance(cls) -> "LivingRenderer":
        if cls._instance is None:
            cls._instance = LivingRenderer()
        return cls._instance

    def __init__(self):
        self._prober = CapabilityProber()
        self._gate = PerformanceGate()
        self._render_count = 0

    # ── Probe + Render Pipeline ────────────────────────────────────

    def probe(self, request: Any = None, params: dict = None,
              headers: dict = None) -> CapabilityProfile:
        return self._prober.probe(request, params, headers)

    def render(self, data: Any, caps: CapabilityProfile = None,
               format: str = "auto", **meta) -> RenderResult:
        """Main render pipeline: probe → degrade → render → measure."""
        self._render_count += 1
        caps = caps or CapabilityProfile()
        t0 = time.time()

        # Determine target format
        if format == "auto":
            format = LEVEL_NAMES.get(caps.max_level.value, "rich")

        # Data normalization: any input → structured dict
        if isinstance(data, str):
            try:
                normalized = json.loads(data)
                if isinstance(normalized, dict):
                    data = normalized
                else:
                    data = {"content": data}
            except (json.JSONDecodeError, ValueError):
                data = {"content": data}
        elif isinstance(data, (int, float)):
            data = {"value": data, "label": meta.get("label", "metric")}
        elif not isinstance(data, dict):
            data = {"content": str(data)[:5000]}

        # Performance check: degrade if needed
        raw_size = len(json.dumps(data, default=str) if isinstance(data, dict) else str(data))
        should_degrade, actual_level = self._gate.should_degrade(
            raw_size, caps.max_level, caps.max_bytes,
        )

        # Render
        result = self._render_at(data, actual_level, caps, format, meta)
        result.render_time_ms = (time.time() - t0) * 1000
        result.byte_size = len(result.content.encode("utf-8"))
        if should_degrade:
            result.degraded_from = caps.max_level

        self._gate.record_render_time(result.render_time_ms)
        return result

    # ── Level Renderers ────────────────────────────────────────────

    def _render_at(self, data: dict, level: RenderLevel, caps: CapabilityProfile,
                   _format: str, meta: dict) -> RenderResult:
        """Route to appropriate renderer based on level."""
        renderers = {
            RenderLevel.PLAIN: self._render_plain,
            RenderLevel.RICH: self._render_rich,
            RenderLevel.STRUCT: self._render_struct,
            RenderLevel.VISUAL: self._render_visual,
            RenderLevel.MEDIA: self._render_media,
            RenderLevel.SPATIAL: self._render_spatial,
        }
        render_fn = renderers.get(level, self._render_plain)
        return render_fn(data, caps, meta)

    # ── L0: PLAIN — Terminal-friendly text ────────────────────────

    def _render_plain(self, data: dict, caps: CapabilityProfile,
                      meta: dict) -> RenderResult:
        """Text + basic formatting. Works everywhere."""
        lines = []
        title = meta.get("title", data.get("title", ""))
        if title:
            lines.append(f"═══ {title} ═══")
            lines.append("")

        # Key-value pairs
        for k, v in data.items():
            k_display = k.replace("_", " ").title()
            if isinstance(v, (int, float)):
                lines.append(f"  {k_display}: {v}")
            elif isinstance(v, list):
                lines.append(f"  {k_display}:")
                for item in v[:10]:
                    if isinstance(item, dict):
                        lines.append(f"    - {item.get('label', item.get('summary', str(item)[:80]))}")
                    else:
                        lines.append(f"    - {str(item)[:100]}")
            elif isinstance(v, dict):
                lines.append(f"  {k_display}:")
                for dk, dv in v.items():
                    lines.append(f"    {dk}: {str(dv)[:80]}")
            elif isinstance(v, str) and len(v) < 200:
                lines.append(f"  {k_display}: {v}")
            elif isinstance(v, str):
                lines.append(f"  {k_display}: {v[:200]}...")

        # Summary / content
        content = data.get("content", data.get("summary", ""))
        if content and isinstance(content, str):
            lines.append("")
            lines.append("─" * 40)
            for paragraph in content.split("\n")[:20]:
                lines.append(paragraph[:120])

        return RenderResult(
            content="\n".join(lines),
            mime_type="text/plain",
            level=RenderLevel.PLAIN,
            byte_size=0,
            render_time_ms=0,
        )

    # ── L1: RICH — Markdown + styled HTML ─────────────────────────

    COLOR_MAP = {
        "critical": "#dc2626", "high": "#ea580c", "normal": "#2563eb",
        "low": "#6b7280", "deferred": "#9ca3af",
        "done": "#16a34a", "failed": "#dc2626", "running": "#2563eb",
    }

    def _render_rich(self, data: dict, caps: CapabilityProfile,
                     meta: dict) -> RenderResult:
        """Styled HTML with inline CSS. Works in any browser + HTMX."""
        title = escape(meta.get("title", data.get("title", "")))
        tags = data.get("tags", data.get("topics", []))

        parts = ['<div class="living-card" style="font-family:system-ui;padding:12px;border-radius:8px;']
        if caps.prefers_dark:
            parts.append('background:#1e1e2e;color:#cdd6f4;border:1px solid #313244;')
        else:
            parts.append('background:#fff;color:#1a1a2e;border:1px solid #e5e7eb;')

        priority = data.get("priority", "normal")
        color = self.COLOR_MAP.get(priority, "#6b7280")
        parts.append(f'border-left:4px solid {color};">')

        if title:
            parts.append(f'<h3 style="margin:0 0 8px 0;font-size:16px;">{title}</h3>')

        # Tags
        for tag in tags[:5]:
            parts.append(
                f'<span style="display:inline-block;padding:2px 8px;margin:2px;'
                f'border-radius:12px;font-size:11px;background:{color}20;color:{color};">'
                f'{escape(str(tag)[:20])}</span>'
            )

        # Key metrics
        metrics = data.get("metrics", data.get("data", {}))
        if isinstance(metrics, dict):
            parts.append('<div style="margin:8px 0;display:flex;gap:12px;flex-wrap:wrap;">')
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    parts.append(
                        f'<div style="text-align:center;min-width:60px;">'
                        f'<div style="font-size:20px;font-weight:bold;color:{color};">{v}</div>'
                        f'<div style="font-size:10px;color:#6b7280;">{escape(k[:15])}</div>'
                        f'</div>'
                    )
            parts.append('</div>')

        # Content
        content = data.get("content", data.get("summary", ""))
        if content and isinstance(content, str):
            parts.append(
                f'<div style="margin-top:8px;line-height:1.6;font-size:14px;">'
                f'{self._md_to_html_fragment(content[:2000])}</div>'
            )

        # Timestamp
        ts = data.get("timestamp", data.get("ts", 0))
        if ts:
            parts.append(
                f'<div style="margin-top:8px;font-size:11px;color:#9ca3af;">'
                f'{self._format_time(ts)}</div>'
            )

        parts.append('</div>')
        return RenderResult(
            content="".join(parts),
            mime_type="text/html",
            level=RenderLevel.RICH,
            byte_size=0,
            render_time_ms=0,
        )

    # ── L2: STRUCT — Tables, trees, KV ────────────────────────────

    def _render_struct(self, data: dict, caps: CapabilityProfile,
                       meta: dict) -> RenderResult:
        """Structured data rendering — tables, trees."""
        parts = []
        table_data = data.get("rows", data.get("items", data.get("events", [])))
        columns = data.get("columns", [])

        if table_data and isinstance(table_data, list) and len(table_data) > 0:
            if not columns and isinstance(table_data[0], dict):
                columns = list(table_data[0].keys())[:6]

            parts.append('<table style="width:100%;border-collapse:collapse;font-size:13px;">')
            parts.append('<thead><tr>')
            for col in columns:
                parts.append(
                    f'<th style="text-align:left;padding:8px;border-bottom:2px solid #e5e7eb;">'
                    f'{escape(str(col)[:20])}</th>'
                )
            parts.append('</tr></thead><tbody>')
            for row in table_data[:50]:
                parts.append('<tr>')
                if isinstance(row, dict):
                    for col in columns:
                        val = str(row.get(col, ""))[:100]
                        parts.append(
                            f'<td style="padding:6px 8px;border-bottom:1px solid #f3f4f6;">'
                            f'{escape(val)}</td>'
                        )
                else:
                    parts.append(
                        f'<td style="padding:6px 8px;" colspan="{len(columns)}">'
                        f'{escape(str(row)[:200])}</td>'
                    )
                parts.append('</tr>')
            parts.append('</tbody></table>')
        else:
            # Fallback to key-value list
            parts.append('<dl style="margin:0;">')
            for k, v in data.items():
                if k in ("rows", "items", "events", "columns", "type"):
                    continue
                parts.append(
                    f'<dt style="font-weight:bold;margin-top:8px;">{escape(k)}</dt>'
                    f'<dd style="margin:0 0 4px 16px;color:#6b7280;">{escape(str(v)[:200])}</dd>'
                )
            parts.append('</dl>')

        return RenderResult(
            content="".join(parts),
            mime_type="text/html",
            level=RenderLevel.STRUCT,
            byte_size=0,
            render_time_ms=0,
        )

    # ── L3: VISUAL — Charts, diagrams, timelines ──────────────────

    def _render_visual(self, data: dict, caps: CapabilityProfile,
                       meta: dict) -> RenderResult:
        """Visual rendering — embeddable charts via SVG or data URIs."""
        parts = [
            '<div style="padding:8px;">',
            f'<p style="color:#6b7280;font-size:12px;">'
            f'📊 Visual rendering requires a chart library (Chart.js/LeaferJS). '
            f'Data payload embedded for client-side rendering.</p>',
            '<script type="application/json" class="living-chart-data">',
            json.dumps(data, default=str, ensure_ascii=False),
            '</script>',
            '</div>',
        ]

        # If SVG is supported, embed a simple bar chart for metrics
        if caps.supports_svg:
            parts.append(self._render_svg_sparkline(data))

        return RenderResult(
            content="".join(parts),
            mime_type="text/html",
            level=RenderLevel.VISUAL,
            byte_size=0,
            render_time_ms=0,
        )

    def _render_svg_sparkline(self, data: dict) -> str:
        """Generate a tiny inline SVG sparkline for metric data."""
        values = data.get("values", data.get("metrics", []))
        if isinstance(values, dict):
            values = [v for v in values.values() if isinstance(v, (int, float))]
        if not values or not isinstance(values, list):
            return ""

        vals = [float(v) for v in values[:50] if isinstance(v, (int, float))]
        if len(vals) < 2:
            return ""

        w, h = 200, 40
        min_v, max_v = min(vals), max(vals)
        if max_v == min_v:
            max_v = min_v + 1

        points = []
        for i, v in enumerate(vals):
            x = (i / max(len(vals) - 1, 1)) * w
            y = h - ((v - min_v) / (max_v - min_v)) * (h - 4) - 2
            points.append(f"{x:.1f},{y:.1f}")

        return (
            f'<svg width="{w}" height="{h}" style="margin:8px 0;overflow:visible;">'
            f'<polyline points="{" ".join(points)}" '
            f'fill="none" stroke="#2563eb" stroke-width="2" stroke-linejoin="round"/>'
            f'<circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" '
            f'r="3" fill="#2563eb"/>'
            f'</svg>'
        )

    # ── L4/L5: MEDIA + SPATIAL — Placeholder + data payload ───────

    def _render_media(self, data: dict, caps: CapabilityProfile,
                      meta: dict) -> RenderResult:
        return self._render_fallback(data, "media", caps, meta)

    def _render_spatial(self, data: dict, caps: CapabilityProfile,
                        meta: dict) -> RenderResult:
        return self._render_fallback(data, "spatial", caps, meta)

    def _render_fallback(self, data: dict, level: str, caps: CapabilityProfile,
                         meta: dict) -> RenderResult:
        """When we can't render at requested level, degrade to rich + hint."""
        result = self._render_rich(data, caps, meta)
        hint = (f'<div style="margin-top:8px;padding:8px;background:#fef3c7;'
                f'border-radius:4px;font-size:12px;">'
                f'📌 {level.title()} rendering requested but degraded to Rich.'
                f' Data available via <code>?cap={level}</code> on supported clients.</div>')
        result.content = hint + result.content
        result.mime_type = "text/html"
        return result

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _md_to_html_fragment(text: str) -> str:
        """Minimal markdown-to-HTML for inline rendering."""
        if not text:
            return ""
        text = escape(text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'`(.+?)`', r'<code style="background:#f3f4f6;padding:1px 4px;border-radius:3px;">\1</code>', text)
        text = text.replace("\n\n", "<br><br>")
        return text

    @staticmethod
    def _format_time(ts: float) -> str:
        """Human-readable relative time."""
        if ts <= 0:
            return ""
        diff = time.time() - ts
        if diff < 60:
            return f"{int(diff)}秒前"
        if diff < 3600:
            return f"{int(diff/60)}分钟前"
        if diff < 86400:
            return f"{int(diff/3600)}小时前"
        return f"{int(diff/86400)}天前"

    def stats(self) -> dict:
        return {
            "renders": self._render_count,
            "avg_render_time_ms": round(self._gate.avg_render_time_ms, 2),
        }


# ═══ Singleton ════════════════════════════════════════════════════


_renderer: Optional[LivingRenderer] = None


def get_living_renderer() -> LivingRenderer:
    global _renderer
    if _renderer is None:
        _renderer = LivingRenderer()
    return _renderer


__all__ = [
    "LivingRenderer", "CapabilityProber", "PerformanceGate",
    "RenderLevel", "CapabilityProfile", "RenderResult",
    "get_living_renderer",
]
