"""Document format auto-discovery and template learning.

Supports: PDF, DOCX, Markdown, Plain Text
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set
from pathlib import Path
from pydantic import BaseModel, Field
from dataclasses import dataclass

try:
    from docx import Document as DocxDocument  # type: ignore
except Exception:  # pragma: no cover
    DocxDocument = None  # type: ignore

try:
    import pypdf  # type: ignore
except Exception:
    pypdf = None  # type: ignore


class Template(BaseModel):
    name: str
    formats: Set[str] = Field(default_factory=set)
    structure: Dict[str, List[str]] = Field(default_factory=dict)


class FormatDiscovery:
    SUPPORTED_FORMATS: Set[str] = {"PDF", "DOCX", "Markdown", "PlainText"}

    def analyze_document(self, path: str) -> Template:
        fmt = self._detect_format(path)
        text = self._extract_text(path, fmt)
        structure = self.detect_structure(text or "")
        template = Template(name=Path(path).name, formats={fmt}, structure=structure)
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
        return Template(name="anonymous", formats={"PlainText"}, structure=self.detect_structure(text))

    def learn_format(self, text: str) -> None:
        # Placeholder for learning logic; could be extended to update a schema store
        pass

    def supports_formats(self, formats: Set[str]) -> bool:
        return formats.issubset(self.SUPPORTED_FORMATS)

    # Internal helpers
    def _detect_format(self, path: str) -> str:
        p = Path(path)
        if p.suffix.lower() == ".pdf":
            return "PDF"
        if p.suffix.lower() in {".docx"}:
            return "DOCX"
        if p.suffix.lower() in {".md", ".markdown"}:
            return "Markdown"
        return "PlainText"

    def _extract_text(self, path: str, fmt: str) -> Optional[str]:
        try:
            if fmt == "PDF" and pypdf is not None:
                with open(path, "rb") as f:
                    reader = pypdf.PdfReader(f)  # type: ignore
                    pages = [p.extract_text() or "" for p in reader.pages]
                    return "\n".join(pages)
            if fmt == "DOCX" and DocxDocument is not None:
                doc = DocxDocument(path)
                texts = []
                for para in doc.paragraphs:
                    texts.append(para.text)
                return "\n".join(texts)
            if fmt == "Markdown" or fmt == "PlainText":
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:  # pragma: no cover
            # Best-effort best-effort parsing; fall through to empty text
            return None
        return None


__all__ = ["Template", "FormatDiscovery"]
