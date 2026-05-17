"""Format Observer — LLM observes and reproduces formatting by pattern matching.

Core insight: LLM doesn't need to understand CSS/docx XML. It observes raw
formatted content, describes patterns in natural language, stores them in the
knowledge base, and reproduces them when generating similar content.

Universal: works for .docx, HTML, Markdown, PDF, .pptx — any formatted document.

Architecture:
  1. observe_format(filepath) → dump raw content as text
  2. LLM analyzes the text, describes style patterns in its own words
  3. LLM calls save_pattern(description) → stores in knowledge base
  4. LLM calls find_pattern(domain) → retrieves pattern for reproduction
  5. LLM applies the pattern when generating new content

This is not XML parsing. This is LLM observing and imitating — exactly how
humans learn design by looking at examples.
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

PATTERN_DB = Path(".livingtree/format_patterns.json")


# ═══ Core: observe raw content ═══

def observe_format(filepath: str) -> str:
    """Dump a formatted document as raw text for LLM observation.

    The LLM sees the structure and describes patterns in its own words.
    No hardcoded parsing — pure observation.
    """
    p = Path(filepath)
    if not p.exists():
        return f"File not found: {filepath}"

    suffix = p.suffix.lower()

    if suffix == ".docx":
        return _dump_docx(p)
    elif suffix == ".html" or suffix == ".htm":
        return _dump_html(p)
    elif suffix == ".md":
        return _dump_markdown(p)
    elif suffix == ".pptx":
        return _dump_pptx(p)
    elif suffix == ".pdf":
        return _dump_pdf(p)
    else:
        # Generic: just show raw content
        try:
            return p.read_text(encoding="utf-8", errors="replace")[:8000]
        except Exception:
            return f"Cannot read: {filepath}"


def _dump_docx(p: Path) -> str:
    """Dump docx as structured text with formatting markers."""
    import zipfile, xml.etree.ElementTree as ET
    NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    try:
        with zipfile.ZipFile(p) as z:
            doc_xml = z.read("word/document.xml") if "word/document.xml" in z.namelist() else b""
            styles_xml = z.read("word/styles.xml") if "word/styles.xml" in z.namelist() else b""

        lines = [f"=== Document: {p.name} ===", f"Raw size: {p.stat().st_size} bytes", ""]

        if doc_xml:
            root = ET.fromstring(doc_xml)
            lines.append("--- BODY ---")
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "p":
                    # Paragraph
                    ppr = elem.find(f"{NS}pPr")
                    style_info = ""
                    if ppr is not None:
                        pstyle = ppr.find(f"{NS}pStyle")
                        if pstyle is not None:
                            style_info = f' [style={pstyle.get(f"{NS}val","")}]'
                        jc = ppr.find(f"{NS}jc")
                        if jc is not None:
                            style_info += f' [align={jc.get(f"{NS}val","")}]'

                    texts = []
                    for t in elem.iter(f"{NS}t"):
                        if t.text:
                            texts.append(t.text)
                        # Bold/italic markers
                        rpr = None
                        for parent in elem.iter():
                            if parent.tag.endswith("}rPr"):
                                rpr = parent
                                break
                        if rpr is not None:
                            for b in rpr.iter(f"{NS}b"):
                                if texts:
                                    texts[-1] = f"**{texts[-1]}**"
                            for i in rpr.iter(f"{NS}i"):
                                if texts:
                                    texts[-1] = f"*{texts[-1]}*"

                    text = "".join(texts)
                    if text.strip():
                        lines.append(f"{style_info} {text.strip()[:200]}")

                elif tag == "tbl":
                    lines.append("[TABLE]")

        if styles_xml:
            root = ET.fromstring(styles_xml)
            lines.append("\n--- STYLES ---")
            for style in root.iter(f"{NS}style"):
                sid = style.get(f"{NS}styleId", "")
                sname = style.find(f"{NS}name")
                name = sname.get(f"{NS}val", "") if sname is not None else ""
                if sid or name:
                    # Font info
                    font_info = ""
                    for rpr in style.iter(f"{NS}rPr"):
                        for rf in rpr.iter(f"{NS}rFonts"):
                            f = rf.get(f"{NS}ascii", "") or rf.get(f"{NS}eastAsia", "")
                            if f:
                                font_info += f" font={f}"
                        for sz in rpr.iter(f"{NS}sz"):
                            val = sz.get(f"{NS}val", "")
                            if val:
                                font_info += f" size={int(val)//2}pt"
                    if font_info:
                        lines.append(f"  [{sid}] {name}:{font_info}")

        return "\n".join(lines[:200])
    except Exception as e:
        return f"docx dump error: {e}"


def _dump_html(p: Path) -> str:
    """Dump HTML showing tag structure and inline styles."""
    import re
    content = p.read_text(encoding="utf-8", errors="replace")[:15000]

    # Extract CSS
    styles = re.findall(r'<style[^>]*>(.*?)</style>', content, re.DOTALL)
    body = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
    body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL)

    # Show structure with class/id
    tags = re.findall(r'<(/?\w+)[^>]*class="([^"]*)"[^>]*>', body)
    ids = re.findall(r'<(/?\w+)[^>]*id="([^"]*)"[^>]*>', body)

    lines = [f"=== HTML: {p.name} ===", ""]
    if styles:
        lines.append(f"--- CSS ({len(styles)} blocks) ---")
        for s in styles[:5]:
            lines.append(s.strip()[:500])

    lines.append(f"\n--- Structure ({len(tags)} class tags, {len(ids)} id tags) ---")
    for tag, cls in tags[:30]:
        lines.append(f"  <{tag} class=\"{cls}\">")
    for tag, iid in ids[:10]:
        lines.append(f"  <{tag} id=\"{iid}\">")

    return "\n".join(lines[:150])


def _dump_markdown(p: Path) -> str:
    """Dump Markdown showing heading hierarchy and formatting."""
    import re
    content = p.read_text(encoding="utf-8", errors="replace")[:10000]

    lines = [f"=== Markdown: {p.name} ===", ""]
    headings = re.findall(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)
    if headings:
        lines.append("--- Heading Hierarchy ---")
        for level, title in headings[:20]:
            depth = len(level)
            indent = "  " * (depth - 1)
            lines.append(f"{indent}{'#'*depth} {title.strip()}")

    # Tables
    tables = re.findall(r'^\|.+\|$', content, re.MULTILINE)
    if tables:
        lines.append(f"\n--- Tables ({len(tables)} rows) ---")
        for t in tables[:10]:
            lines.append(t.strip()[:150])

    # Code blocks
    code_blocks = re.findall(r'```(\w*)\n(.*?)```', content, re.DOTALL)
    if code_blocks:
        lines.append(f"\n--- Code Blocks ({len(code_blocks)}) ---")
        for lang, _ in code_blocks[:5]:
            lines.append(f"  lang={lang or 'plain'}")

    return "\n".join(lines[:100])


def _dump_pptx(p: Path) -> str:
    """Dump PowerPoint showing slide structure."""
    import zipfile, xml.etree.ElementTree as ET
    try:
        with zipfile.ZipFile(p) as z:
            slides = [n for n in z.namelist() if n.startswith("ppt/slides/slide")]
            lines = [f"=== PPT: {p.name} === {len(slides)} slides", ""]
            for sn in slides[:15]:
                xml = z.read(sn)
                root = ET.fromstring(xml)
                texts = [t.text for t in root.iter() if t.tag.endswith("}t") and t.text]
                lines.append(f"\n--- {sn.split('/')[-1]} ---")
                for t in texts[:8]:
                    lines.append(f"  {t[:150]}")
            return "\n".join(lines[:150])
    except Exception as e:
        return f"pptx dump error: {e}"


def _dump_pdf(p: Path) -> str:
    """Dump PDF text content."""
    try:
        import fitz
        doc = fitz.open(p)
        lines = [f"=== PDF: {p.name} === {len(doc)} pages", ""]
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                lines.append(f"\n--- Page {i+1} ---")
                lines.append(text[:1000])
            if len(lines) > 100:
                break
        doc.close()
        return "\n".join(lines[:150])
    except ImportError:
        return f"PDF reading requires PyMuPDF: pip install PyMuPDF"
    except Exception as e:
        return f"PDF dump error: {e}"


# ═══ Pattern storage (LLM-described) ═══

def save_pattern(json_spec: str) -> str:
    """Save an LLM-described formatting pattern to the knowledge base.

    The LLM describes what it observed in its own words and structured format.
    This is stored for future retrieval when generating similar documents.

    Expected JSON:
    {
      "domain": "环评报告",
      "source": "template.docx",
      "description": "正式公文风格，SimSun正文12pt，标题黑体加粗，1.5倍行距，A4页面...",
      "structure": {"headings": [...], "paragraph_style": {...}, "page": {...}},
      "tags": ["formal", "environment", "government"],
      "applies_to": ["docx", "pdf"],
      "prompt_hint": "使用正式的环评报告格式，SimSun字体..."
    }
    """
    try:
        data = json.loads(json_spec)
        patterns = _load_patterns()
        # Deduplicate by source
        patterns = [p for p in patterns if p.get("source") != data.get("source")]
        patterns.append(data)
        _save_patterns(patterns)
        domain = data.get("domain", "unknown")
        return f"Pattern saved: domain={domain} ({len(patterns)} total)"
    except Exception as e:
        return f"Save error: {e}"


def find_pattern(query: str) -> str:
    """Find matching patterns by domain or tags.

    Args: "eia" or "eia,formal" (domain + comma-separated tags)
    """
    parts = query.split(",")
    domain = parts[0].strip().lower()
    need_tags = [t.strip().lower() for t in parts[1:]] if len(parts) > 1 else []

    patterns = _load_patterns()
    if not patterns:
        return "No patterns stored. Use observe_format to look at examples, then save_pattern."

    # Match by domain
    candidates = [
        p for p in patterns
        if domain in p.get("domain", "").lower()
    ]
    if not candidates:
        # Fuzzy match on any field
        candidates = [
            p for p in patterns
            if domain in json.dumps(p).lower()
        ]

    # Filter by tags
    if need_tags and candidates:
        tagged = [
            p for p in candidates
            if all(
                any(t in tag.lower() for tag in p.get("tags", []))
                for t in need_tags
            )
        ]
        if tagged:
            candidates = tagged

    if not candidates:
        return f"No pattern found for '{query}'. Available domains: " + \
               ", ".join(set(p.get("domain","?") for p in patterns))

    return json.dumps(candidates[0], ensure_ascii=False, indent=2)


def list_patterns() -> str:
    """List all stored patterns."""
    patterns = _load_patterns()
    if not patterns:
        return "No patterns stored."
    items = [
        {"domain": p.get("domain", "?"), "source": p.get("source", "?"),
         "tags": p.get("tags", []), "applies_to": p.get("applies_to", [])}
        for p in patterns
    ]
    return json.dumps(items, ensure_ascii=False, indent=2)


def _load_patterns() -> list[dict]:
    if not PATTERN_DB.exists():
        return []
    try:
        return json.loads(PATTERN_DB.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_patterns(patterns: list[dict]):
    PATTERN_DB.parent.mkdir(parents=True, exist_ok=True)
    PATTERN_DB.write_text(json.dumps(patterns, ensure_ascii=False, indent=2), encoding="utf-8")
