"""LayoutEngine — natural language UI layout generation for Toad/Textual.

    No more hand-writing TCSS. Describe what you want, system generates it,
    validates it, and auto-fixes parse errors.

    Architecture:
      NL description → JSON layout spec → TCSS generation
        → validation (parse check) → auto-fix loop → hot-reload

    Presets (5 built-in):
      tree     — file tree (30% left) + chat + status bar
      tabs     — tabbed panels with sidebar
      minimal  — chat only, no chrome
      full     — all panels visible
      eia      — EIA report optimized (wide tables, big text, 2-column)

    Styles (4 built-in):
      dark-compact    —  tight spacing, dark theme
      light-spacious  —  light, comfortable reading
      eia-professional — formal, high-contrast for reports
      hacker          —  monospace everything, green on black

    Usage:
        engine = get_layout_engine()
        result = await engine.apply("左侧文件树30%宽，右侧对话区，底部状态栏", hub)
        # → validates TCSS, auto-fixes, hot-reloads

        layout = engine.get_preset("eia")
        # → returns JSON layout spec with all sections

    Commands:
        /layout tree|tabs|minimal|full|eia        — apply preset
        /layout style dark-compact|light|hacker    — switch theme
        /layout <描述>                               — custom NL layout
        /layout save <名称>                          — save current
        /layout load <名称>                          — load saved
        /layout list                                 — list presets + saved
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

LAYOUT_DIR = Path(".livingtree/layouts")
THEME_FILE = Path("livingtree/tui/styles/theme.tcss")
PRESETS_FILE = LAYOUT_DIR / "presets.json"
SAVED_FILE = LAYOUT_DIR / "saved_layouts.json"


# ═══ Layout Presets (JSON description, not TCSS) ═══

PRESETS: dict[str, dict] = {
    "tree": {
        "name": "树形布局",
        "description": "左侧30%文件树 + 右侧对话区 + 底部状态栏",
        "layout": {
            "type": "horizontal",
            "left": {"name": "sidebar", "widget": "TreeView", "width": "30%"},
            "right": {
                "type": "vertical",
                "top": {"name": "conversation", "widget": "Conversation", "flex": 1},
                "bottom": {"name": "status", "widget": "StatusBar", "height": 1},
            },
        },
    },
    "tabs": {
        "name": "标签页布局",
        "description": "顶部标签页 + 左侧侧边栏 + 主内容区",
        "layout": {
            "type": "vertical",
            "top": {"name": "tabs", "widget": "TabPane", "height": 2},
            "bottom": {
                "type": "horizontal",
                "left": {"name": "sidebar", "widget": "Sidebar", "width": "25%"},
                "right": {"name": "main", "widget": "Conversation", "flex": 1},
            },
        },
    },
    "minimal": {
        "name": "极简布局",
        "description": "仅对话区，无侧边栏和状态栏",
        "layout": {
            "type": "vertical",
            "top": {"name": "conversation", "widget": "Conversation", "flex": 1},
            "bottom": {"name": "prompt", "widget": "Prompt", "height": 3},
        },
    },
    "full": {
        "name": "全功能布局",
        "description": "所有面板可见: 文件树+对话+右侧信息面板+底部状态",
        "layout": {
            "type": "horizontal",
            "left": {"name": "sidebar", "widget": "TreeView", "width": "25%"},
            "center": {"name": "conversation", "widget": "Conversation", "flex": 1},
            "right": {"name": "info", "widget": "InfoPanel", "width": "20%"},
        },
    },
    "eia": {
        "name": "环评报告布局",
        "description": "优化报告编写: 左侧目录(15%) + 中间编辑器(60%) + 右侧预览(25%)",
        "layout": {
            "type": "horizontal",
            "left": {"name": "outline", "widget": "TreeView", "width": "15%"},
            "center": {"name": "editor", "widget": "DocumentEditor", "flex": 2},
            "right": {"name": "preview", "widget": "MarkdownPreview", "flex": 1},
        },
    },
}


# ═══ Style Themes ═══

STYLES: dict[str, dict] = {
    "dark-compact": {
        "name": "暗色紧凑",
        "colors": {
            "background": "#0a0c10",
            "surface": "#161b22",
            "border": "#30363d",
            "text": "#c9d1d9",
            "accent": "#58a6ff",
            "success": "#238636",
            "warning": "#d29922",
            "error": "#da3633",
        },
        "spacing": {"padding": 2, "margin": 1, "gap": 1},
        "fonts": {"size": 13, "line_height": 1.4},
    },
    "light-spacious": {
        "name": "浅色宽松",
        "colors": {
            "background": "#ffffff",
            "surface": "#f6f8fa",
            "border": "#d0d7de",
            "text": "#1f2328",
            "accent": "#0969da",
            "success": "#1a7f37",
            "warning": "#9a6700",
            "error": "#cf222e",
        },
        "spacing": {"padding": 6, "margin": 3, "gap": 2},
        "fonts": {"size": 15, "line_height": 1.6},
    },
    "eia-professional": {
        "name": "环评专业",
        "colors": {
            "background": "#fafbfc",
            "surface": "#ffffff",
            "border": "#2c3e50",
            "text": "#2c3e50",
            "accent": "#2980b9",
            "success": "#27ae60",
            "warning": "#e67e22",
            "error": "#c0392b",
        },
        "spacing": {"padding": 8, "margin": 4, "gap": 3},
        "fonts": {"size": 14, "line_height": 1.8},
    },
    "hacker": {
        "name": "黑客极简",
        "colors": {
            "background": "#0d1117",
            "surface": "#010409",
            "border": "#238636",
            "text": "#00ff41",
            "accent": "#39ff14",
            "success": "#00ff41",
            "warning": "#ffd700",
            "error": "#ff4444",
        },
        "spacing": {"padding": 1, "margin": 0, "gap": 0},
        "fonts": {"size": 12, "line_height": 1.1},
    },
}


@dataclass
class LayoutResult:
    description: str
    preset: str = ""
    tcss: str = ""
    validated: bool = False
    parse_errors: list[str] = field(default_factory=list)
    fix_attempts: int = 0
    applied: bool = False


class LayoutEngine:
    """Natural language → valid TCSS → hot-reload."""

    MAX_FIX_ATTEMPTS = 3

    def __init__(self):
        LAYOUT_DIR.mkdir(parents=True, exist_ok=True)
        self._current_preset: str = ""
        self._current_style: str = "dark-compact"
        self._saved: dict[str, dict] = {}
        self._load_saved()

    # ═══ NL → Layout ═══

    async def generate(self, description: str, hub=None) -> LayoutResult:
        """Convert natural language description to validated TCSS.

        Args:
            description: e.g. "左侧文件树30%宽，右侧对话区，底部状态栏"
            hub: LLM access for parsing NL to layout spec
        """
        result = LayoutResult(description=description)

        # Phase 1: Parse NL → layout JSON
        if hub and hub.world:
            layout_spec = await self._nl_to_spec(description, hub)
        else:
            layout_spec = self._keyword_to_spec(description)

        if not layout_spec:
            result.parse_errors = ["Could not parse layout description"]
            return result

        # Phase 2: Generate TCSS
        style = STYLES.get(self._current_style, STYLES["dark-compact"])
        result.tcss = self._spec_to_tcss(layout_spec, style)

        # Phase 3: Validate + auto-fix
        result.validated, errors = self._validate_tcss(result.tcss)

        while not result.validated and result.fix_attempts < self.MAX_FIX_ATTEMPTS and hub and hub.world:
            result.fix_attempts += 1
            result.tcss = await self._auto_fix(result.tcss, errors, hub)
            result.validated, errors = self._validate_tcss(result.tcss)
            if result.validated:
                break

        result.parse_errors = errors
        return result

    async def apply(self, description: str, hub=None) -> LayoutResult:
        """Generate + validate + apply TCSS to the running app.

        Hot-reload: writes to theme.tcss and triggers Textual CSS refresh.
        """
        result = await self.generate(description, hub)

        if result.validated:
            self._write_tcss(result.tcss)
            result.applied = True

            # Trigger Textual hot-reload
            try:
                THEME_FILE.touch()
                logger.info(f"Layout applied: {result.description[:60]}...")
            except Exception:
                pass

        return result

    def apply_preset(self, preset_name: str) -> LayoutResult:
        """Apply a built-in preset."""
        preset = PRESETS.get(preset_name)
        if not preset:
            return LayoutResult(description=f"Preset {preset_name} not found")

        style = STYLES.get(self._current_style, STYLES["dark-compact"])
        tcss = self._spec_to_tcss(preset["layout"], style)

        result = LayoutResult(
            description=preset["description"],
            preset=preset_name,
            tcss=tcss,
            validated=True,
            applied=False,
        )

        self._write_tcss(tcss)
        result.applied = True
        self._current_preset = preset_name
        logger.info(f"Preset applied: {preset_name}")
        return result

    def apply_style(self, style_name: str) -> bool:
        """Switch color/font theme while keeping current layout."""
        if style_name not in STYLES:
            return False

        self._current_style = style_name

        # Re-generate TCSS with new style + current layout
        layout = PRESETS.get(self._current_preset, PRESETS["tree"])["layout"]
        style = STYLES[style_name]
        tcss = self._spec_to_tcss(layout, style)
        self._write_tcss(tcss)
        logger.info(f"Style applied: {style_name}")
        return True

    def save(self, name: str, description: str, tcss: str = ""):
        """Save a layout under a name."""
        self._saved[name] = {"description": description, "tcss": tcss, "saved_at": time.time()}
        self._save_to_disk()

    def load(self, name: str) -> LayoutResult:
        """Load a saved layout and apply it."""
        saved = self._saved.get(name)
        if not saved:
            return LayoutResult(description=f"Layout {name} not found")

        tcss = saved.get("tcss", "")
        if tcss:
            self._write_tcss(tcss)
            return LayoutResult(description=saved["description"], tcss=tcss, validated=True, applied=True)

        return LayoutResult(description=saved["description"])

    def list_all(self) -> dict:
        return {
            "presets": {k: v["description"] for k, v in PRESETS.items()},
            "styles": {k: v["name"] for k, v in STYLES.items()},
            "saved": {k: v["description"] for k, v in self._saved.items()},
            "current": {"preset": self._current_preset or "custom", "style": STYLES[self._current_style]["name"]},
        }

    # ═══ TCSS Generation ═══

    def _spec_to_tcss(self, layout: dict, style: dict) -> str:
        """Convert JSON layout spec to TCSS."""
        c = style["colors"]
        s = style["spacing"]
        f = style["fonts"]

        lines = [
            "/* Generated by LayoutEngine */",
            "/* " + style["name"] + " */",
            "",
            "Screen {",
            f"    background: {c['background']};",
            f"    color: {c['text']};",
            "}",
            "",
            "Conversation {",
            f"    background: {c['background']};",
            f"    padding: {s['padding']};",
            "}",
            "",
            "AgentResponse {",
            f"    background: {c['surface']};",
            f"    border: solid {c['border']};",
            f"    margin: {s['margin']};",
            f"    padding: {s['padding']};",
            f"    text-style: none;",
            "}",
            "",
            "Prompt {",
            f"    background: {c['surface']};",
            f"    border-top: solid {c['border']};",
            f"    padding: {s['padding']};",
            f"    height: 3;",
            "}",
            "",
            "Sidebar, TreeView {",
            f"    background: {c['surface']};",
            f"    border-right: solid {c['border']};",
            f"    width: 30%;",
            "}",
            "",
            "StatusBar {",
            f"    background: {c['surface']};",
            f"    border-top: solid {c['border']};",
            f"    height: 1;",
            f"    text-style: bold;",
            "}",
            "",
            "ToolCall {",
            f"    background: {c['surface']};",
            f"    border: solid {c['accent']};",
            f"    margin: {s['margin']};",
            "}",
            "",
            "Note {",
            f"    color: {c['text']};",
            f"    padding: {s['padding']};",
            "}",
            "",
            "MarkdownBlock {",
            f"    padding: {s['padding']};",
            f"    margin: {s['margin']};",
            "}",
            "",
            "h1 { color: " + c['accent'] + "; }",
            "h2 { color: " + c['accent'] + "; border-bottom: solid " + c['border'] + "; }",
            "code { background: " + c['surface'] + "; }",
            f"Link {{ color: {c['accent']}; }}",
            "",
            "Loading {",
            f"    color: {c['accent']};",
            "}",
            "",
            f".dim {{ color: {c['text']} 70%; }}",
            f".err {{ color: {c['error']}; }}",
            f".success {{ color: {c['success']}; }}",
        ]

        # Layout-specific rules
        if layout.get("type") == "horizontal":
            left = layout.get("left", {})
            if left:
                width = left.get("width", "30%")
                lines.append(f"")
                lines.append(f"/* Layout: {left.get('name', 'left')} */")
                lines.append(f"TreeView, Sidebar {{")
                lines.append(f"    width: {width};")
                lines.append(f"}}")

        return "\n".join(lines)

    # ═══ Validation ═══

    def _validate_tcss(self, tcss: str) -> tuple[bool, list[str]]:
        """Validate TCSS by attempting to parse it.

        Textual CSS is parsed by the Textual framework. We detect
        common error patterns and invalid property names.
        """
        errors = []

        # Check for known-invalid Textual CSS properties
        invalid_props = ["font-family", "display", "position", "float", "z-index", "overflow"]
        for line_no, line in enumerate(tcss.splitlines(), 1):
            for prop in invalid_props:
                if re.match(rf'\s*{prop}\s*:', line):
                    errors.append(f"Line {line_no}: unsupported property '{prop}' in Textual CSS")

        # Check for $variable references (Textual doesn't support CSS variables in TCSS)
        if re.search(r'\$\w+', tcss):
            errors.append("CSS variable references ($variable) not supported in Textual TCSS")

        return len(errors) == 0, errors

    async def _auto_fix(self, tcss: str, errors: list[str], hub) -> str:
        """LLM fixes TCSS parse errors."""
        if not errors:
            return tcss

        llm = hub.world.consciousness._llm
        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    "Fix these Textual CSS (TCSS) parse errors.\n\n"
                    "TCSS rules:\n"
                    "- NO font-family property (unsupported by Textual)\n"
                    "- NO CSS variables like $var (use hex colors)\n"
                    "- NO display, position, float, z-index, overflow\n"
                    "- Properties: background, color, border, padding, margin, width, height, dock, text-style, text-opacity\n\n"
                    "ERRORS:\n" + "\n".join(errors) + "\n\n"
                    "CURRENT TCSS:\n```css\n" + tcss + "\n```\n\n"
                    "Output ONLY the corrected TCSS. No explanation."
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.0, max_tokens=2000, timeout=15,
            )
            if result and result.text:
                fixed = result.text.strip()
                fixed = re.sub(r'^```\w*\n?', '', fixed)
                fixed = re.sub(r'\n?```$', '', fixed)
                return fixed
        except Exception:
            pass

        # Fallback: strip known-bad properties
        for line in tcss.splitlines():
            for prop in ["font-family", "display", "position", "float", "z-index"]:
                if re.match(rf'\s*{prop}\s*:', line):
                    tcss = tcss.replace(line, f"/* Removed: {line.strip()} */")
        return tcss

    # ═══ NL Parsing ═══

    async def _nl_to_spec(self, description: str, hub) -> dict | None:
        """LLM converts NL to layout JSON."""
        llm = hub.world.consciousness._llm
        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    "Convert this UI layout description to a JSON layout spec.\n\n"
                    "DESCRIPTION: " + description + "\n\n"
                    "Layout types: horizontal (left/right) or vertical (top/bottom)\n"
                    "Supported widgets: Sidebar, TreeView, Conversation, Prompt, StatusBar, TabPane, InfoPanel, DocumentEditor, MarkdownPreview\n"
                    "Sizes: percentage (30%), flex (1/2/3), height (number of rows)\n\n"
                    'Output JSON: {"type":"horizontal","left":{"name":"sidebar","widget":"TreeView","width":"30%"},'
                    '"right":{"type":"vertical","top":{"name":"chat","widget":"Conversation","flex":1},'
                    '"bottom":{"name":"status","widget":"StatusBar","height":1}}}'
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.1, max_tokens=400, timeout=15,
            )
            if result and result.text:
                m = re.search(r'\{[\s\S]*\}', result.text)
                if m:
                    return json.loads(m.group())
        except Exception:
            pass
        return None

    def _keyword_to_spec(self, description: str) -> dict:
        """Keyword matching fallback when LLM unavailable."""
        dl = description.lower()
        if "文件树" in dl or "tree" in dl or "侧边栏" in dl:
            return PRESETS["tree"]["layout"]
        if "标签" in dl or "tabs" in dl:
            return PRESETS["tabs"]["layout"]
        if "极小" in dl or "minimal" in dl or "只" in dl:
            return PRESETS["minimal"]["layout"]
        if "报告" in dl or "eia" in dl or "环评" in dl:
            return PRESETS["eia"]["layout"]
        return PRESETS["tree"]["layout"]

    # ═══ File I/O ═══

    def _write_tcss(self, tcss: str):
        THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
        THEME_FILE.write_text(tcss, encoding="utf-8")

    def _save_to_disk(self):
        SAVED_FILE.write_text(json.dumps(self._saved, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_saved(self):
        if not SAVED_FILE.exists():
            return
        try:
            self._saved = json.loads(SAVED_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass


_le: LayoutEngine | None = None


def get_layout_engine() -> LayoutEngine:
    global _le
    if _le is None:
        _le = LayoutEngine()
    return _le
