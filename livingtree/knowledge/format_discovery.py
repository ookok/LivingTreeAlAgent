"""Document format auto-discovery powered by Google Magika AI.

Magika: 200+ content types, 99% accuracy, ~5ms per file, model ~3 MB.
Uses content-based detection (first 512 bytes) — not just file extensions.

Routing hints from Magika's `group` field:
  image    → OCR (modern_ocr.py)
  document → universal_parser.py + hierarchical_chunker.py
  code     → AST absorption (phage.py)
  text     → direct chunking (knowledge_base.py)
  binary   → reject or metadata-only
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from loguru import logger

try:
    from docx import Document as DocxDocument  # type: ignore
except Exception:  # pragma: no cover
    DocxDocument = None  # type: ignore

try:
    import pypdf  # type: ignore
except Exception:
    pypdf = None  # type: ignore

try:
    from magika import Magika  # type: ignore
except Exception:
    Magika = None  # type: ignore


class Template(BaseModel):
    """Document template with format metadata."""
    name: str
    formats: Set[str] = Field(default_factory=set)
    structure: Dict[str, List[str]] = Field(default_factory=dict)
    group: str = ""          # Magika group: code/document/image/text/binary
    confidence: float = 0.0  # Magika prediction score (0.0-1.0)
    mime_type: str = ""      # IANA MIME type


class FormatDiscovery:
    """AI-powered file format detection and document analysis.

    Uses Google Magika for content-based detection with extension fallback.
    Supports PDF, DOCX, Markdown, Plain Text for text extraction.
    """

    SUPPORTED_FORMATS: Set[str] = {"PDF", "DOCX", "Markdown", "PlainText"}

    def __init__(self) -> None:
        self._magika: Optional[Magika] = None
        if Magika is not None:
            try:
                self._magika = Magika()
            except Exception as e:
                logger.debug(f"Magika model load failed, using extension fallback: {e}")

    def _detect_with_magika(self, path: str) -> Optional[Tuple[str, str, float, str]]:
        """Content-based detection via Magika. Returns (label, group, score, mime_type) or None."""
        if self._magika is None:
            return None
        try:
            res = self._magika.identify_path(path)
            out = res.output
            return (out.label, out.group, res.score, out.mime_type)
        except Exception as e:
            logger.debug(f"Magika detection failed for {path}: {e}")
            return None

    def _detect_bytes(self, data: bytes) -> Optional[Tuple[str, str, float, str]]:
        """Content-based detection from bytes."""
        if self._magika is None:
            return None
        try:
            res = self._magika.identify_bytes(data)
            out = res.output
            return (out.label, out.group, res.score, out.mime_type)
        except Exception as e:
            logger.debug(f"Magika bytes detection failed: {e}")
            return None

    def detect(self, path: str) -> Template:
        """Full content-based detection → Template with routing metadata."""
        p = Path(path)
        label = "unknown"
        group = ""
        score = 0.0
        mime = ""

        mg = self._detect_with_magika(path)
        if mg:
            label, group, score, mime = mg

        fmt = self._label_to_format(label) if label else self._detect_format_fallback(path)

        return Template(
            name=p.name,
            formats={fmt},
            structure={},
            group=group,
            confidence=score,
            mime_type=mime,
        )

    def detect_bytes(self, data: bytes, filename: str = "unnamed") -> Template:
        """Detect format from raw bytes (for uploads/in-memory content)."""
        label = "unknown"
        group = ""
        score = 0.0
        mime = ""

        mg = self._detect_bytes(data)
        if mg:
            label, group, score, mime = mg

        fmt = self._label_to_format(label) if label else self._detect_format_fallback(filename)

        return Template(
            name=filename,
            formats={fmt},
            structure={},
            group=group,
            confidence=score,
            mime_type=mime,
        )

    def route_target(self, template: Template) -> str:
        """Return routing target based on Magika group."""
        routes = {
            "image": "ocr",
            "document": "parser",
            "code": "phage",
            "text": "chunk",
        }
        if template.group:
            return routes.get(template.group, "chunk")
        return "chunk"

    def analyze_document(self, path: str) -> Template:
        template = self.detect(path)
        text = self._extract_text(path, template.formats)
        if text:
            template.structure = self.detect_structure(text)
        return template

    def detect_structure(self, text: str) -> Dict[str, List[str]]:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        headings: List[str] = []
        sections: List[str] = []
        for ln in lines:
            if ln.startswith("#"):
                headings.append(ln.strip("# \t"))
            elif ln.isupper() and len(ln) > 3:
                sections.append(ln)
        return {"headings": headings, "sections": sections}

    def extract_template(self, text: str) -> Template:
        return Template(
            name="anonymous",
            formats={"PlainText"},
            structure=self.detect_structure(text),
        )

    def learn_format(self, text: str) -> None:
        pass

    def supports_formats(self, formats: Set[str]) -> bool:
        return formats.issubset(self.SUPPORTED_FORMATS)

    @staticmethod
    def _label_to_format(label: str) -> str:
        """Convert Magika label to internal format name."""
        mapping = {
            "pdf": "PDF",
            "docx": "DOCX",
            "markdown": "Markdown",
            "md": "Markdown",
            "text": "PlainText",
            "plaintext": "PlainText",
        }
        return mapping.get(label.lower(), "PlainText")

    @staticmethod
    def _detect_format_fallback(path: str) -> str:
        """Extension-based fallback when Magika is unavailable."""
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix == ".pdf":
            return "PDF"
        if suffix in {".docx"}:
            return "DOCX"
        if suffix in {".md", ".markdown"}:
            return "Markdown"
        return "PlainText"

    def _extract_text(self, path: str, formats: Set[str]) -> Optional[str]:
        try:
            if "PDF" in formats and pypdf is not None:
                with open(path, "rb") as f:
                    reader = pypdf.PdfReader(f)  # type: ignore
                    pages = [p.extract_text() or "" for p in reader.pages]
                    return "\n".join(pages)
            if "DOCX" in formats and DocxDocument is not None:
                doc = DocxDocument(path)
                texts = [para.text for para in doc.paragraphs]
                return "\n".join(texts)
            if "Markdown" in formats or "PlainText" in formats:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception:  # pragma: no cover
            return None
        return None


__all__ = ["Template", "FormatDiscovery"]
