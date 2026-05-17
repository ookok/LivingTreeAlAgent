"""Document style DNA — LLM-driven atomic formatting extraction and retrieval.

Atomic tools:
  parse_style(filepath) → extract raw StyleDNA (LLM decides domain/tags)
  save_style(json_spec)  → save style to knowledge base
  find_style(domain)     → retrieve best-matching style
  apply_style(domain)    → format_docx JSON snippet from stored style

LLM controls the entire pipeline — no hardcoded logic.
"""

from __future__ import annotations

import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from loguru import logger

STYLE_DB = Path(".livingtree/style_db.json")


class StyleDNA:
    """Extracted formatting profile from a document — its visual identity."""

    def __init__(self):
        self.source: str = ""
        self.page_size: str = "A4"
        self.margins: dict = {"top": 3.7, "bottom": 3.5, "left": 2.8, "right": 2.6}
        self.default_font: str = "SimSun"
        self.default_size: int = 12
        self.default_color: str = "#333333"
        self.heading_fonts: dict = {}  # {level: font_name}
        self.heading_sizes: dict = {}  # {level: pt}
        self.heading_colors: dict = {}  # {level: color}
        self.line_spacing: float = 1.5
        self.first_indent_cm: float = 0.74
        self.alignment: str = "justify"
        self.header_text: str = ""
        self.footer_text: str = ""
        self.watermark_text: str = ""
        self.table_style: str = "Table Grid"
        self.domain: str = ""  # eia/report/contract/letter
        self.tags: list[str] = []

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    @classmethod
    def from_dict(cls, d: dict) -> "StyleDNA":
        s = cls()
        for k, v in d.items():
            if hasattr(s, k):
                setattr(s, k, v)
        return s

    def to_format_docx_prompt(self) -> str:
        """Generate a format_docx JSON snippet from this style."""
        spec = {
            "page": {"size": self.page_size,
                     "margin_top_cm": self.margins["top"],
                     "margin_bottom_cm": self.margins["bottom"],
                     "margin_left_cm": self.margins["left"],
                     "margin_right_cm": self.margins["right"]},
        }
        if self.header_text:
            spec["header"] = {"text": self.header_text, "font_size": 9}
        if self.footer_text:
            spec["footer"] = {"text": self.footer_text, "font_size": 9}
        if self.watermark_text:
            spec["watermark"] = {"text": self.watermark_text, "font_size": 72}

        return json.dumps(spec, ensure_ascii=False, indent=2)


def parse_style(filepath: str) -> str:
    """Extract raw formatting DNA from a .docx file.

    Returns JSON with: fonts, margins, colors, spacing, headers, watermarks.
    LLM decides domain/tags — this tool just extracts, nothing more.
    """
    p = Path(filepath)
    if not p.exists():
        return f"File not found: {filepath}"
    if p.suffix.lower() != ".docx":
        return f"Not a .docx file: {filepath}"

    try:
        dna = _extract_raw(p)
        return json.dumps(dna.to_dict(), ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Parse error: {e}"


def save_style(json_spec: str) -> str:
    """Save a style spec to the style database.

    Args: JSON with source, domain, tags, and style fields.
    LLM controls domain and tags — no hardcoded logic.
    """
    try:
        data = json.loads(json_spec)
        dna = StyleDNA.from_dict(data)
        db = _get_db()
        # Deduplicate by source
        existing = [i for i, s in enumerate(db) if s.source == dna.source]
        for idx in existing:
            db[idx] = dna
        if not existing:
            db.append(dna)
        _save_db(db)
        return f"Style saved: domain={dna.domain} tags={dna.tags} source={dna.source}"
    except Exception as e:
        return f"Save error: {e}"


def find_style(query: str) -> str:
    """Find best-matching style by domain or tags.

    Args: "eia" or "eia,formal,report" (domain + comma-separated tags)
    """
    parts = query.split(",")
    domain = parts[0].strip()
    tags = [t.strip() for t in parts[1:]] if len(parts) > 1 else []

    db = _get_db()
    candidates = [s for s in db if s.domain == domain] if domain else list(db)
    if tags:
        tagged = [s for s in candidates if any(t in s.tags for t in tags)]
        if tagged:
            candidates = tagged

    if not candidates:
        return f"No style found for domain={domain} tags={tags}"

    return json.dumps(candidates[0].to_dict(), ensure_ascii=False, indent=2)


def apply_style(domain: str) -> str:
    """Retrieve best style and output format_docx JSON snippet.

    LLM can directly paste the output into a format_docx call.
    """
    parts = domain.split(",")
    dom = parts[0].strip()
    tags = [t.strip() for t in parts[1:]] if len(parts) > 1 else []

    db = _get_db()
    candidates = [s for s in db if s.domain == dom] if dom else list(db)
    if tags:
        tagged = [s for s in candidates if any(t in s.tags for t in tags)]
        if tagged:
            candidates = tagged

    if not candidates:
        return f"No style found. Use parse_style to extract from a template first."

    dna = candidates[0]
    spec = {
        "page": {
            "size": dna.page_size,
            "margin_top_cm": dna.margins["top"],
            "margin_bottom_cm": dna.margins["bottom"],
            "margin_left_cm": dna.margins["left"],
            "margin_right_cm": dna.margins["right"],
        },
    }
    if dna.header_text:
        spec["header"] = {"text": dna.header_text, "font_size": 9}
    if dna.footer_text:
        spec["footer"] = {"text": dna.footer_text, "font_size": 9}
    if dna.watermark_text:
        spec["watermark"] = {"text": dna.watermark_text, "font_size": 72}

    # Paragraph style
    spec["default_paragraph"] = {
        "font": dna.default_font, "size": dna.default_size,
        "color": dna.default_color, "align": dna.alignment,
        "line_spacing": dna.line_spacing, "first_line_indent_cm": dna.first_indent_cm,
    }
    if dna.heading_sizes:
        spec["headings"] = {
            str(lv): {"font": dna.heading_fonts.get(lv, dna.default_font),
                      "size": dna.heading_sizes.get(lv, 16 + (3-lv)*2)}
            for lv in sorted(dna.heading_sizes)
        }

    return json.dumps(spec, ensure_ascii=False, indent=2)


def list_styles() -> str:
    """List all stored styles."""
    db = _get_db()
    if not db:
        return "No styles stored. Use parse_style to extract from templates."
    items = [
        {"source": s.source, "domain": s.domain, "tags": s.tags,
         "font": s.default_font, "page": s.page_size}
        for s in db
    ]
    return json.dumps(items, ensure_ascii=False, indent=2)


# ═══ Internal ═══

def _get_db() -> list[StyleDNA]:
    if not STYLE_DB.exists():
        return []
    try:
        data = json.loads(STYLE_DB.read_text(encoding="utf-8"))
        return [StyleDNA.from_dict(d) for d in data]
    except Exception:
        return []


def _save_db(db: list[StyleDNA]):
    STYLE_DB.parent.mkdir(parents=True, exist_ok=True)
    data = [s.to_dict() for s in db]
    STYLE_DB.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_raw(p: Path) -> "StyleDNA":
    dna = StyleDNA()
    dna.source = str(p)
    with zipfile.ZipFile(p) as z:
        if "word/styles.xml" in z.namelist():
            _parse_styles_xml(dna, z.read("word/styles.xml"))
        if "word/document.xml" in z.namelist():
            _parse_doc_xml(dna, z.read("word/document.xml"))
        for name in z.namelist():
            if "header" in name.lower() and name.endswith(".xml"):
                texts = [t.text or "" for t in ET.fromstring(z.read(name)).iter()
                         if t.tag.endswith("}t") and t.text]
                if texts and not dna.header_text:
                    dna.header_text = " ".join(texts)[:100]
            if "footer" in name.lower() and name.endswith(".xml"):
                texts = [t.text or "" for t in ET.fromstring(z.read(name)).iter()
                         if t.tag.endswith("}t") and t.text]
                if texts and not dna.footer_text:
                    dna.footer_text = " ".join(texts)[:100]
    return dna
    """Parse word/styles.xml for font/size/color defaults."""
    NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    root = ET.fromstring(xml_bytes)
    for style in root.iter(f"{NS}style"):
        style_id = style.get(f"{NS}styleId", "")
        # Default paragraph style
        if style_id == "Normal" or style_id == "a":
            for rpr in style.iter(f"{NS}rPr"):
                for rf in rpr.iter(f"{NS}rFonts"):
                    font = rf.get(f"{NS}ascii") or rf.get(f"{NS}eastAsia") or ""
                    if font:
                        dna.default_font = font
                for sz in rpr.iter(f"{NS}sz"):
                    val = sz.get(f"{NS}val", "")
                    if val:
                        dna.default_size = int(val) // 2
                for color in rpr.iter(f"{NS}color"):
                    val = color.get(f"{NS}val", "")
                    if val and val != "auto":
                        dna.default_color = f"#{val}"
        # Heading styles
        if style_id and style_id.startswith("Heading") or style_id.startswith("heading"):
            level = 1
            for c in style_id:
                if c.isdigit():
                    level = int(c)
                    break
            for rpr in style.iter(f"{NS}rPr"):
                for rf in rpr.iter(f"{NS}rFonts"):
                    font = rf.get(f"{NS}ascii") or rf.get(f"{NS}eastAsia") or ""
                    if font:
                        dna.heading_fonts[level] = font
                for sz in rpr.iter(f"{NS}sz"):
                    val = sz.get(f"{NS}val", "")
                    if val:
                        dna.heading_sizes[level] = int(val) // 2
                for color in rpr.iter(f"{NS}color"):
                    val = color.get(f"{NS}val", "")
                    if val and val != "auto":
                        dna.heading_colors[level] = f"#{val}"


def _parse_doc_xml(dna: StyleDNA, xml_bytes: bytes):
    """Parse word/document.xml for paragraph formatting."""
    NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    root = ET.fromstring(xml_bytes)

    # Page size from sectPr
    for sp in root.iter(f"{NS}sectPr"):
        for pg_sz in sp.iter(f"{NS}pgSz"):
            w = pg_sz.get(f"{NS}w", "")
            h = pg_sz.get(f"{NS}h", "")
            if w and h:
                w_mm = int(w) / 567
                h_mm = int(h) / 567
                if 200 < w_mm < 220:
                    dna.page_size = "A4"
                elif 280 < w_mm < 300:
                    dna.page_size = "A3"
                else:
                    dna.page_size = f"{w_mm:.0f}x{h_mm:.0f}mm"
        for pm in sp.iter(f"{NS}pgMar"):
            dna.margins["top"] = _twips_to_cm(pm.get(f"{NS}top", ""))
            dna.margins["bottom"] = _twips_to_cm(pm.get(f"{NS}bottom", ""))
            dna.margins["left"] = _twips_to_cm(pm.get(f"{NS}left", ""))
            dna.margins["right"] = _twips_to_cm(pm.get(f"{NS}right", ""))

    # First paragraph's formatting
    for p in root.iter(f"{NS}p"):
        ppr = p.find(f"{NS}pPr")
        if ppr is not None:
            spacing = ppr.find(f"{NS}spacing")
            if spacing is not None:
                line = spacing.get(f"{NS}line", "")
                if line:
                    dna.line_spacing = round(int(line) / 240, 1)
            ind = ppr.find(f"{NS}ind")
            if ind is not None:
                first = ind.get(f"{NS}firstLine", "")
                if first:
                    dna.first_indent_cm = _twips_to_cm(first)
            jc = ppr.find(f"{NS}jc")
            if jc is not None:
                val = jc.get(f"{NS}val", "")
                dna.alignment = {"left": "left", "center": "center", "right": "right",
                                 "both": "justify"}.get(val, "justify")
        break  # Only first paragraph


def _twips_to_cm(twips: str) -> float:
    try:
        return round(int(twips) / 567, 1)
    except (ValueError, TypeError):
        return 0.0



