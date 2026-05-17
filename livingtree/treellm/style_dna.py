"""Document style extraction and retrieval — LLM mimics formatting without understanding it.

Workflow:
  1. Index a document → extract its "style DNA" (fonts, margins, colors, spacing)
  2. Store style DNA in knowledge base alongside content
  3. When generating a new document, retrieve the best-matching style by domain
  4. Inject style into format_docx spec or generation prompt

LLM doesn't need to know what "SimSun 12pt justified 1.5 line-spacing" means.
It just retrieves and applies — pure mimicry.
"""

from __future__ import annotations

import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

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


def extract_style(filepath: str, domain: str = "") -> StyleDNA | None:
    """Extract visual formatting DNA from a .docx file.

    Reads XML directly (no python-docx needed for basic extraction).
    """
    p = Path(filepath)
    if not p.exists() or p.suffix.lower() != ".docx":
        return None

    dna = StyleDNA()
    dna.source = str(p)
    dna.domain = domain or _guess_domain(p.name)

    try:
        with zipfile.ZipFile(p) as z:
            # Read styles
            if "word/styles.xml" in z.namelist():
                styles_xml = z.read("word/styles.xml")
                _parse_styles(dna, styles_xml)

            # Read document body for default paragraph properties
            if "word/document.xml" in z.namelist():
                doc_xml = z.read("word/document.xml")
                _parse_document(dna, doc_xml)

            # Read header/footer
            for name in z.namelist():
                if "header" in name.lower() and name.endswith(".xml"):
                    hdr_xml = z.read(name)
                    texts = [t.text or "" for t in ET.fromstring(hdr_xml).iter()
                             if t.tag.endswith("}t") and t.text]
                    if texts and not dna.header_text:
                        dna.header_text = " ".join(texts)[:100]
                if "footer" in name.lower() and name.endswith(".xml"):
                    ftr_xml = z.read(name)
                    texts = [t.text or "" for t in ET.fromstring(ftr_xml).iter()
                             if t.tag.endswith("}t") and t.text]
                    if texts and not dna.footer_text:
                        dna.footer_text = " ".join(texts)[:100]

        logger.info(f"StyleDNA extracted: {dna.domain} from {p.name}")
        return dna
    except Exception as e:
        logger.warning(f"Style extraction failed for {filepath}: {e}")
        return None


def _parse_styles(dna: StyleDNA, xml_bytes: bytes):
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


def _parse_document(dna: StyleDNA, xml_bytes: bytes):
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


def _guess_domain(filename: str) -> str:
    name = filename.lower()
    if any(kw in name for kw in ["环评", "eia", "environment", "环境"]):
        return "eia"
    if any(kw in name for kw in ["合同", "contract", "agreement", "协议"]):
        return "contract"
    if any(kw in name for kw in ["报告", "report", "分析"]):
        return "report"
    if any(kw in name for kw in ["论文", "paper", "thesis", "学术"]):
        return "academic"
    if any(kw in name for kw in ["信", "letter", "通知", "notice"]):
        return "letter"
    return "general"


# ═══ Style Database — store and retrieve ═══

class StyleDatabase:
    """Maintains a library of extracted document styles for retrieval."""

    def __init__(self, db_path: str = str(STYLE_DB)):
        self._path = Path(db_path)
        self._styles: list[StyleDNA] = []
        self._load()

    def index(self, filepath: str, domain: str = "") -> StyleDNA | None:
        """Extract and store style from a document."""
        dna = extract_style(filepath, domain)
        if dna:
            # Deduplicate: replace if same domain+source
            existing = [i for i, s in enumerate(self._styles) if s.source == str(filepath)]
            for idx in existing:
                self._styles[idx] = dna
            if not existing:
                self._styles.append(dna)
            self._save()
        return dna

    def find_best(self, domain: str = "", tags: list[str] | None = None) -> StyleDNA | None:
        """Find the best-matching style for a domain."""
        candidates = self._styles

        if domain:
            domain_matches = [s for s in candidates if s.domain == domain]
            if domain_matches:
                candidates = domain_matches

        if tags:
            tagged = [s for s in candidates if any(t in s.tags for t in tags)]
            if tagged:
                candidates = tagged

        return candidates[0] if candidates else None

    def list_styles(self) -> list[dict]:
        return [
            {"source": s.source, "domain": s.domain, "font": s.default_font,
             "size": s.default_size, "page": s.page_size}
            for s in self._styles
        ]

    def _save(self):
        data = [s.to_dict() for s in self._styles]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self):
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._styles = [StyleDNA.from_dict(d) for d in data]
        except Exception:
            pass


# Singleton
_style_db: StyleDatabase | None = None


def get_style_database() -> StyleDatabase:
    global _style_db
    if _style_db is None:
        _style_db = StyleDatabase()
    return _style_db
