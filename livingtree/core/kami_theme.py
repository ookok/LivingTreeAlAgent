"""Kami Theme System — editorial design tokens for autonomous UI generation.

Extracts Kami's design philosophy into a programmatic token system that:
- The Living Canvas can apply to auto-generated layouts
- LLM prompts can reference for Kami-compliant HTML generation
- Theme switching (dark/light/Kami) unified through the same token API

Design principles (from tw93/Kami):
- Warm parchment canvas (#f5f4ed) — not cold, not stark
- Ink blue accent (#1B365D) — scholarly, trustworthy
- Serif typography with editorial hierarchy — human, readable
- Proportional spacing (1.2em/1.55 line-height) — breathing room
- Thin borders (0.5px) — subtle definition, not shouting
- Max-width containers (660-1024px) — focused reading width
"""

from __future__ import annotations

from typing import Literal

ThemeName = Literal["dark", "light", "kami"]


KAMI_TOKENS = {
    "colors": {
        "canvas":     "#f5f4ed",
        "canvas_rgb": "245, 244, 237",
        "surface":    "#faf9f5",
        "accent":     "#1B365D",
        "accent_rgb": "27, 54, 93",
        "accent_light": "#2d5a8e",
        "text":       "#2d2a26",
        "text_muted": "#6b6560",
        "border":     "#d4cdc2",
        "border_light":"#e5dfd6",
        "tag_bg":     "#2d2a26",
        "tag_text":   "#f5f4ed",
        "warn":       "#c47a20",
        "err":        "#c04040",
        "success":    "#3a7d44",
    },
    "typography": {
        "body_font": "'Charter', 'Georgia', 'Noto Serif SC', STSong, serif",
        "mono_font": "'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace",
        "heading_font": "'Charter', 'Georgia', 'Noto Serif SC', STSong, serif",
        "base_size": "15px",
        "line_height": 1.55,
        "heading_sizes": {
            "h1": "1.8em", "h2": "1.4em", "h3": "1.15em",
            "h4": "1.05em", "h5": "1em", "h6": "0.9em",
        },
        "heading_weight": 500,
        "heading_color_var": "accent",
    },
    "layout": {
        "max_widths": {
            "narrow":  "660px",
            "normal":  "760px",
            "wide":    "900px",
            "full":    "1024px",
        },
        "spacing": {
            "heading_top": "1.2em",
            "heading_bottom": "0.4em",
            "paragraph": "0.5em",
            "list": "0.6em",
            "hr_top": "2em",
            "block_padding": "16px",
            "card_gap": "12px",
            "section_gap": "24px",
        },
        "border": {
            "width": "0.5px",
            "accent_width": "3px",
            "radius": "4px",
            "card_radius": "8px",
        },
    },
}


DARK_TOKENS = {
    "colors": {
        "canvas":     "#0a0a0f",
        "canvas_rgb": "10, 10, 15",
        "surface":    "#12121a",
        "accent":     "#6c8",
        "accent_rgb": "100, 150, 100",
        "accent_light": "#8da",
        "text":       "#c8c8d4",
        "text_muted": "#667",
        "border":     "#1e1e2e",
        "border_light":"#2a2a3a",
        "tag_bg":     "#1a2a1a",
        "tag_text":   "#6c8",
        "warn":       "#e8a030",
        "err":        "#e05050",
        "success":    "#6c8",
    },
    "typography": {
        "body_font": "system-ui, -apple-system, sans-serif",
        "mono_font": "'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace",
        "heading_font": "system-ui, -apple-system, sans-serif",
        "base_size": "14px",
        "line_height": 1.6,
        "heading_sizes": KAMI_TOKENS["typography"]["heading_sizes"],
        "heading_weight": 600,
        "heading_color_var": "accent",
    },
    "layout": KAMI_TOKENS["layout"],
}


LIGHT_TOKENS = {
    "colors": {
        "canvas":     "#ffffff",
        "canvas_rgb": "255, 255, 255",
        "surface":    "#f8f8f8",
        "accent":     "#0366d6",
        "accent_rgb": "3, 102, 214",
        "accent_light": "#2684ff",
        "text":       "#24292e",
        "text_muted": "#6a737d",
        "border":     "#e1e4e8",
        "border_light":"#f0f0f0",
        "tag_bg":     "#0366d6",
        "tag_text":   "#ffffff",
        "warn":       "#d93f0b",
        "err":        "#cb2431",
        "success":    "#28a745",
    },
    "typography": {
        "body_font": "system-ui, -apple-system, sans-serif",
        "mono_font": "'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace",
        "heading_font": "system-ui, -apple-system, sans-serif",
        "base_size": "14px",
        "line_height": 1.6,
        "heading_sizes": KAMI_TOKENS["typography"]["heading_sizes"],
        "heading_weight": 600,
        "heading_color_var": "accent",
    },
    "layout": KAMI_TOKENS["layout"],
}


THEMES: dict[ThemeName, dict] = {
    "dark": DARK_TOKENS,
    "light": LIGHT_TOKENS,
    "kami": KAMI_TOKENS,
}


def get_theme(name: ThemeName = "dark") -> dict:
    return THEMES.get(name, DARK_TOKENS)


def generate_css(theme_name: ThemeName = "dark") -> str:
    """Generate complete CSS from design tokens."""
    t = get_theme(theme_name)
    c = t["colors"]
    tp = t["typography"]
    lo = t["layout"]
    bd = lo["border"]

    return f"""/* LivingTree Kami Theme: {theme_name} */
:root {{
  --bg: {c['canvas']}; --panel: {c['surface']}; --border: {c['border']};
  --text: {c['text']}; --accent: {c['accent']}; --dim: {c['text_muted']};
  --warn: {c['warn']}; --err: {c['err']}; --success: {c['success']};
  --tag-bg: {c['tag_bg']}; --tag-text: {c['tag_text']};
  --font-body: {tp['body_font']}; --font-mono: {tp['mono_font']};
  --font-heading: {tp['heading_font']};
  --line-height: {tp['line_height']};
  --heading-weight: {tp['heading_weight']};
  --card-radius: {bd['card_radius']};
  --card-padding: {lo['spacing']['block_padding']};
  --card-gap: {lo['spacing']['card_gap']};
  --content-max: {lo['max_widths']['normal']};
}}
body {{
  background: var(--bg); color: var(--text);
  font: {tp['base_size']}/var(--line-height) var(--font-body);
  -webkit-font-smoothing: antialiased;
}}
h1,h2,h3,h4 {{ font-family: var(--font-heading); font-weight: var(--heading-weight); color: var(--accent); }}
h1 {{ font-size: {tp['heading_sizes']['h1']}; }}
h2 {{ font-size: {tp['heading_sizes']['h2']}; }}
h3 {{ font-size: {tp['heading_sizes']['h3']}; }}
h4 {{ font-size: {tp['heading_sizes']['h4']}; }}
pre,code {{ font-family: var(--font-mono); }}
.card {{ background: var(--panel); border: {bd['width']} solid var(--border); border-radius: var(--card-radius); padding: var(--card-padding); }}
a {{ color: var(--accent); }}
::-webkit-scrollbar {{ width: 4px; }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 2px; }}
"""


def generate_llm_ui_prompt(theme_name: ThemeName = "kami") -> str:
    """Generate LLM prompt constraints for Kami-compliant HTML generation.

    Used by the generative UI system (P4) to ensure auto-generated HTML
    follows Kami design principles.
    """
    t = get_theme(theme_name)
    c = t["colors"]
    lo = t["layout"]

    return (
        "你是 Kami 设计系统的 HTML 生成器。遵循以下设计约束:\n\n"
        "配色:\n"
        f"- 画布背景: {c['canvas']}\n"
        f"- 卡片背景: {c['surface']}\n"
        f"- 主题色: {c['accent']} (用于标题/链接/强调)\n"
        f"- 正文色: {c['text']}\n"
        f"- 辅助色: {c['text_muted']}\n"
        f"- 边框色: {c['border']}\n\n"
        "排版:\n"
        f"- 使用衬线字体族: Charter, Georgia, Noto Serif SC\n"
        f"- 标题字重: {t['typography']['heading_weight']}\n"
        f"- 行高: {t['typography']['line_height']}\n\n"
        "布局:\n"
        f"- 卡片内边距: {lo['spacing']['block_padding']}\n"
        f"- 卡片间距: {lo['spacing']['card_gap']}\n"
        f"- 最大宽度: {lo['max_widths']['normal']}\n"
        f"- 边框: {lo['border']['width']} solid {c['border']}\n"
        f"- 圆角: {lo['border']['card_radius']}\n\n"
        "风格:\n"
        "- 编辑风格，简洁雅致，留白充分\n"
        "- 用 class='card' 包裹各组件\n"
        "- 卡片内标题使用 <h2> 或 <h3>\n"
        "- 表格使用 thin border，header 用主题色底线\n"
        "- blockquote 使用 3px 主题色左边框\n"
        "- 代码块使用 0.04 透明度主题色背景\n"
        "- 只输出 HTML 片段，不要 markdown 代码块\n"
    )


def apply_kami_to_html(html: str, theme_name: ThemeName = "kami") -> str:
    """Post-process auto-generated HTML to inject Kami styling when missing."""
    t = get_theme(theme_name)
    c = t["colors"]

    # If HTML already has style attributes, don't override
    # Only inject when no styling present
    if 'style="' not in html and "style='" not in html:
        html = html.replace(
            '<div class="card">',
            f'<div class="card" style="background:{c["surface"]};border:{t["layout"]["border"]["width"]} solid {c["border"]};border-radius:{t["layout"]["border"]["card_radius"]};padding:{t["layout"]["spacing"]["block_padding"]}">',
        )
    return html
