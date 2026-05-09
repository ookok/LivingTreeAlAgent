"""LivingTree Document Renderer — Kami design system for beautiful output.

Applies Kami's design constraints to LivingTree's document engine output:
  - Warm parchment canvas (#f5f4ed), ink blue accent (#1B365D)
  - Serif typography with editorial hierarchy
  - 8 document templates, EN/CN/JP language paths
  - Markdown/HTML → styled HTML → PDF (WeasyPrint or fallback)

Inspired by: https://github.com/tw93/Kami
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RENDER_OUTPUT = PROJECT_ROOT / "output" / "rendered"

# ═══ Kami Design Tokens ═══

KAMI_COLORS = {
    "canvas":     "#f5f4ed",
    "canvas_rgb": "245, 244, 237",
    "accent":     "#1B365D",
    "accent_rgb": "27, 54, 93",
    "text":       "#2d2a26",
    "text_muted": "#6b6560",
    "border":     "#d4cdc2",
    "tag_bg":     "#2d2a26",
    "tag_text":   "#f5f4ed",
}

KAMI_FONTS = {
    "cn": {
        "serif": "TsangerJinKai02, 'Noto Serif SC', STSong, serif",
        "mono": "'JetBrains Mono', 'Cascadia Code', monospace",
    },
    "en": {
        "serif": "'Charter', 'Georgia', 'Times New Roman', serif",
        "mono": "'JetBrains Mono', 'Cascadia Code', monospace",
    },
}

# ═══ 8 Kami Templates (HTML skeletons) ═══

_TEMPLATES = {
    "one_pager": {
        "name_cn": "一页纸", "name_en": "One-Pager",
        "max_width": "720px", "heading_size": "1.6em",
    },
    "long_doc": {
        "name_cn": "长文档", "name_en": "Long Document",
        "max_width": "760px", "heading_size": "1.8em",
    },
    "letter": {
        "name_cn": "信函", "name_en": "Letter",
        "max_width": "660px", "heading_size": "1.5em",
    },
    "portfolio": {
        "name_cn": "作品集", "name_en": "Portfolio",
        "max_width": "800px", "heading_size": "1.7em",
    },
    "resume": {
        "name_cn": "简历", "name_en": "Resume",
        "max_width": "700px", "heading_size": "1.6em",
    },
    "slides": {
        "name_cn": "幻灯片", "name_en": "Slides",
        "max_width": "1024px", "heading_size": "2em",
    },
    "equity_report": {
        "name_cn": "财报点评", "name_en": "Equity Report",
        "max_width": "780px", "heading_size": "1.9em",
    },
    "changelog": {
        "name_cn": "更新日志", "name_en": "Changelog",
        "max_width": "720px", "heading_size": "1.5em",
    },
}


def _detect_lang(text: str) -> str:
    """Detect language: 'cn', 'en', or 'jp'."""
    cn_count = len(re.findall(r'[\u4e00-\u9fff]', text))
    jp_count = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))
    if jp_count > cn_count * 0.3:
        return "jp"
    if cn_count > len(text) * 0.15:
        return "cn"
    return "en"


def _markdown_to_html(markdown: str, template: str = "long_doc") -> str:
    """Convert Markdown to Kami-styled HTML."""
    import html as _html

    tpl = _TEMPLATES.get(template, _TEMPLATES["long_doc"])
    lang = _detect_lang(markdown)
    fonts = KAMI_FONTS.get(lang, KAMI_FONTS["en"])

    def _md_to_inline(text: str) -> str:
        """Basic Markdown inline → HTML."""
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'`([^`]+)`', r'<code class="inline-code">\1</code>', text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color:{accent}">\1</a>', text)
        return text

    lines = markdown.split("\n")
    html_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            html_lines.append('<br>')
            i += 1
            continue

        # Headings
        heading_match = re.match(r'^(#{1,6})\s+(.+)', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            sizes = {1: "1.6em", 2: "1.3em", 3: "1.15em", 4: "1.05em", 5: "1em", 6: "0.95em"}
            html_lines.append(
                f'<h{level} style="font-size:{sizes.get(level, "1em")};font-weight:500;'
                f'margin:1.2em 0 0.4em;color:{KAMI_COLORS["text"]};">'
                f'{_md_to_inline(heading_match.group(2))}</h{level}>'
            )
            i += 1
            continue

        # Horizontal rule
        if re.match(r'^[-*_]{3,}$', stripped):
            html_lines.append(f'<hr style="border:0;border-top:0.5px solid {KAMI_COLORS["border"]};margin:2em 0;">')
            i += 1
            continue

        # Code block
        if stripped.startswith("```"):
            lang_tag = stripped[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(_html.escape(lines[i]))
                i += 1
            i += 1  # skip closing ```
            code_html = "\n".join(code_lines)
            html_lines.append(
                f'<pre style="background:rgba({KAMI_COLORS["accent_rgb"]},0.04);'
                f'border:0.5px solid {KAMI_COLORS["border"]};border-radius:4px;'
                f'padding:1em;font-family:{fonts["mono"]};font-size:0.85em;'
                f'line-height:1.5;overflow-x:auto;margin:1em 0;">'
                f'<code>{code_html}</code></pre>'
            )
            continue

        # Blockquote
        if stripped.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].startswith(">"):
                quote_lines.append(lines[i][1:].strip() or "&nbsp;")
                i += 1
            quote_html = "<br>".join(_md_to_inline(q) for q in quote_lines)
            html_lines.append(
                f'<blockquote style="border-left:3px solid {KAMI_COLORS["accent"]};'
                f'padding:0.5em 1em;margin:1em 0;color:{KAMI_COLORS["text_muted"]};'
                f'font-style:italic;">{quote_html}</blockquote>'
            )
            continue

        # Unordered list
        if re.match(r'^[-*+]\s+', stripped):
            list_items = []
            while i < len(lines) and re.match(r'^[-*+]\s+', lines[i]):
                list_items.append(f'<li>{_md_to_inline(lines[i][2:].strip())}</li>')
                i += 1
            html_lines.append(f'<ul style="padding-left:1.5em;margin:0.6em 0;">{"".join(list_items)}</ul>')
            continue

        # Ordered list
        if re.match(r'^\d+\.\s+', stripped):
            list_items = []
            while i < len(lines) and re.match(r'^\d+\.\s+', lines[i]):
                item_text = re.sub(r'^\d+\.\s+', '', lines[i].strip())
                list_items.append(f'<li>{_md_to_inline(item_text)}</li>')
                i += 1
            html_lines.append(f'<ol style="padding-left:1.5em;margin:0.6em 0;">{"".join(list_items)}</ol>')
            continue

        # Table
        if "|" in stripped and i + 1 < len(lines) and re.match(r'^[\|\s\-:]+$', lines[i + 1].strip()):
            header_cells = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2  # skip header and separator
            body_rows = []
            while i < len(lines) and "|" in lines[i]:
                cells = [c.strip() for c in lines[i].strip("|").split("|")]
                body_rows.append("<tr>" + "".join(f'<td style="padding:0.4em 0.8em;border-bottom:0.5px solid {KAMI_COLORS["border"]};">{_md_to_inline(c)}</td>' for c in cells) + "</tr>")
                i += 1
            thead = "<tr>" + "".join(f'<th style="padding:0.4em 0.8em;border-bottom:1px solid {KAMI_COLORS["accent"]};text-align:left;">{_md_to_inline(c)}</th>' for c in header_cells) + "</tr>"
            html_lines.append(
                f'<table style="width:100%;border-collapse:collapse;margin:1em 0;font-size:0.9em;">'
                f'{thead}{"".join(body_rows)}</table>'
            )
            continue

        # Regular paragraph
        html_lines.append(f'<p style="margin:0.5em 0;line-height:1.55;">{_md_to_inline(stripped)}</p>')
        i += 1

    body_html = "\n".join(html_lines)

    return f"""<!DOCTYPE html>
<html lang="{'zh-CN' if lang == 'cn' else 'ja' if lang == 'jp' else 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  @page {{
    size: A4;
    margin: 2cm 2.2cm;
    @bottom-center {{
      content: counter(page);
      font-family: {fonts['serif']};
      font-size: 0.7em;
      color: {KAMI_COLORS['text_muted']};
    }}
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: {KAMI_COLORS['canvas']};
    color: {KAMI_COLORS['text']};
    font-family: {fonts['serif']};
    font-size: 10.5pt;
    line-height: 1.55;
    max-width: {tpl['max_width']};
    padding: 0;
    -webkit-font-smoothing: antialiased;
  }}
  h1, h2, h3, h4 {{ font-weight: 500; color: {KAMI_COLORS['accent']}; }}
  h1 {{ font-size: {tpl['heading_size']}; border-bottom: 1px solid {KAMI_COLORS['border']}; padding-bottom: 0.3em; }}
  code.inline-code {{
    background: rgba({KAMI_COLORS['accent_rgb']}, 0.06);
    padding: 0.1em 0.3em;
    border-radius: 3px;
    font-family: {fonts['mono']};
    font-size: 0.9em;
  }}
  a {{ color: {KAMI_COLORS['accent']}; text-decoration: none; }}
  strong {{ font-weight: 500; }}
  ul, ol {{ margin: 0.6em 0; padding-left: 1.5em; }}
  li {{ margin: 0.2em 0; }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""


def render_document(
    content: str,
    *,
    template: str = "long_doc",
    title: str = "",
    output_path: str = "",
) -> dict:
    """Render Markdown content to Kami-styled HTML → PDF.

    Args:
        content: Markdown document content
        template: one of 'one_pager','long_doc','letter','portfolio','resume','slides','equity_report','changelog'
        title: document title (prepended as H1 if provided)
        output_path: output PDF path (auto-generated if empty)

    Returns:
        {"ok": True/False, "html": "...", "pdf_path": "...", "file_name": "..."}
    """
    if template not in _TEMPLATES:
        template = "long_doc"

    # Prepend title if provided
    full_content = f"# {title}\n\n{content}" if title else content

    # Generate HTML
    html = _markdown_to_html(full_content, template)

    # Generate output path
    RENDER_OUTPUT.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', (title or "document").strip())[:40]
    ts = int(time.time())
    if not output_path:
        output_path = str(RENDER_OUTPUT / f"{safe_name}_{ts}.pdf")

    # Render to PDF via WeasyPrint
    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(output_path)
        logger.info(f"Document rendered: {output_path}")
    except ImportError:
        # Fallback: save HTML only
        html_path = output_path.replace(".pdf", ".html")
        Path(html_path).write_text(html, encoding="utf-8")
        logger.warning("WeasyPrint not installed, saved HTML only. Install: pip install weasyprint")
        return {
            "ok": True,
            "html": html,
            "pdf_path": "",
            "html_path": html_path,
            "file_name": Path(html_path).name,
            "format": "html",
        }

    return {
        "ok": True,
        "html": html,
        "pdf_path": output_path,
        "file_name": Path(output_path).name,
        "format": "pdf",
    }


def list_templates() -> list[dict]:
    """List all available Kami templates."""
    return [
        {"id": k, "name_cn": v["name_cn"], "name_en": v["name_en"]}
        for k, v in _TEMPLATES.items()
    ]
