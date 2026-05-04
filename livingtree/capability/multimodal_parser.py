"""Multimodal Parser — PDF/DOC/Image document parsing with structured extraction.

Extracts text, images, tables, and metadata from documents. When VLM is
available, generates image descriptions. Feeds structured content into
DocEngine, PipelineEngine, and StructMemory.

Backends (auto-detected on import):
- pymupdf (fitz): Full PDF parsing with images + tables
- pdfplumber: Table extraction
- PIL/Pillow: Image handling
- Pure Python fallback: Basic text extraction

Usage:
    parser = MultimodalParser(api_key="...", base_url="...")
    
    result = await parser.parse("report.pdf")
    # → {text, images, tables, metadata, image_descriptions}
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


@dataclass
class ParsedImage:
    index: int
    page: int
    data: bytes
    format: str = "png"
    description: str = ""
    position: tuple = (0, 0, 0, 0)

    def to_base64(self) -> str:
        return base64.b64encode(self.data).decode()

    def to_dict(self) -> dict:
        return {
            "index": self.index, "page": self.page,
            "format": self.format, "description": self.description,
            "size_bytes": len(self.data),
        }


@dataclass
class ParsedTable:
    index: int
    page: int
    rows: list[list[str]]
    caption: str = ""
    headers: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = []
        if self.headers:
            lines.append("| " + " | ".join(self.headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")
        for row in self.rows:
            lines.append("| " + " | ".join(str(c) for c in row) + " |")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "index": self.index, "page": self.page,
            "caption": self.caption, "rows": len(self.rows),
            "headers": self.headers,
        }


@dataclass
class ParsedDocument:
    file_path: str
    total_pages: int = 0
    text: str = ""
    images: list[ParsedImage] = field(default_factory=list)
    tables: list[ParsedTable] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path, "total_pages": self.total_pages,
            "text_length": len(self.text),
            "images_count": len(self.images),
            "tables_count": len(self.tables),
            "images": [i.to_dict() for i in self.images[:20]],
            "tables": [t.to_dict() for t in self.tables[:20]],
            "metadata": self.metadata,
        }

    def summary_text(self) -> str:
        parts = [f"Pages: {self.total_pages}, {len(self.text)} chars"]
        if self.images:
            parts.append(f"{len(self.images)} images")
        if self.tables:
            parts.append(f"{len(self.tables)} tables")
        return ", ".join(parts)


class MultimodalParser:
    """Parse documents into structured text+images+tables."""

    SUPPORTED_FORMATS = {".pdf", ".docx", ".pptx", ".txt", ".md",
                         ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

    def __init__(self, api_key: str = "", base_url: str = ""):
        self._api_key = api_key
        self._base_url = base_url

    async def parse(self, file_path: str | Path) -> ParsedDocument:
        path = Path(file_path)
        if not path.exists():
            return ParsedDocument(file_path=str(path))

        ext = path.suffix.lower()

        if ext == ".pdf" and HAS_PYMUPDF:
            return self._parse_pdf_pymupdf(path)
        elif ext == ".pdf":
            return self._parse_pdf_fallback(path)
        elif ext in (".txt", ".md"):
            return self._parse_text(path)
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
            return self._parse_image(path)
        else:
            return self._parse_text(path)

    async def describe_images(self, doc: ParsedDocument, model: str = "") -> None:
        for img in doc.images[:10]:
            try:
                desc = await self._call_vlm_describe(img.to_base64(), img.format)
                if desc:
                    img.description = desc
            except Exception as e:
                logger.debug(f"Image describe {img.index}: {e}")

    async def parse_with_descriptions(self, file_path: str | Path) -> ParsedDocument:
        doc = await self.parse(file_path)
        if doc.images:
            await self.describe_images(doc)
        return doc

    def format_for_llm(self, doc: ParsedDocument, max_chars: int = 8000) -> str:
        parts = [f"# Document: {doc.file_path}", f"Pages: {doc.total_pages}\n"]

        if doc.text:
            parts.append(doc.text[:max_chars])

        if doc.tables:
            parts.append("\n## Extracted Tables\n")
            for t in doc.tables[:10]:
                parts.append(t.to_markdown())
                parts.append("")

        if doc.images:
            parts.append("\n## Image Descriptions\n")
            for i in doc.images[:10]:
                if i.description:
                    parts.append(f"- Image {i.index+1} (page {i.page}): {i.description}")

        return "\n".join(parts)

    # ── PDF parsers ──

    def _parse_pdf_pymupdf(self, path: Path) -> ParsedDocument:
        doc = ParsedDocument(file_path=str(path))
        try:
            pdf = fitz.open(str(path))
            doc.total_pages = len(pdf)
            doc.metadata = dict(pdf.metadata) if pdf.metadata else {}

            texts = []
            img_idx = 0

            for page_num in range(len(pdf)):
                page = pdf[page_num]

                text = page.get_text("text")
                if text:
                    texts.append(f"--- Page {page_num+1} ---\n{text}")

                for img_info in page.get_image_info():
                    try:
                        xref = img_info.get("xref", 0)
                        if xref:
                            base_image = pdf.extract_image(xref)
                            if base_image and base_image.get("image"):
                                doc.images.append(ParsedImage(
                                    index=img_idx,
                                    page=page_num + 1,
                                    data=base_image["image"],
                                    format=base_image.get("ext", "png"),
                                    position=(
                                        img_info.get("x0", 0), img_info.get("y0", 0),
                                        img_info.get("x1", 0), img_info.get("y1", 0),
                                    ),
                                ))
                                img_idx += 1
                    except Exception:
                        pass

                tables = page.find_tables()
                if tables:
                    for t_idx, table in enumerate(tables):
                        try:
                            data = table.extract()
                            if data:
                                doc.tables.append(ParsedTable(
                                    index=len(doc.tables),
                                    page=page_num + 1,
                                    rows=data[1:] if len(data) > 1 else [],
                                    headers=[str(h) for h in data[0]] if data else [],
                                ))
                        except Exception:
                            pass

            doc.text = "\n".join(texts)
            pdf.close()

        except Exception as e:
            logger.warning(f"PyMuPDF parse: {e}")
        return doc

    def _parse_pdf_fallback(self, path: Path) -> ParsedDocument:
        doc = ParsedDocument(file_path=str(path))
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            cleaned = text.replace("\x00", "").strip()

            meaningful = "\n".join(
                line for line in cleaned.split("\n")
                if any(c.isalpha() for c in line) and len(line.strip()) > 3
            )
            doc.text = meaningful[:50000]
            doc.total_pages = 1

            if HAS_PIL and any(pattern in raw[:100] for pattern in [b"%PDF", b"%!", b"\x89PNG"]):
                try:
                    img = Image.open(path)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    doc.images.append(ParsedImage(
                        index=0, page=1, data=buf.getvalue(), format="png",
                    ))
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"PDF fallback: {e}")
        return doc

    def _parse_text(self, path: Path) -> ParsedDocument:
        doc = ParsedDocument(file_path=str(path), total_pages=1)
        try:
            doc.text = path.read_text(encoding="utf-8", errors="replace")[:50000]
        except Exception:
            doc.text = path.read_bytes().decode("utf-8", errors="replace")[:50000]
        return doc

    def _parse_image(self, path: Path) -> ParsedDocument:
        doc = ParsedDocument(file_path=str(path), total_pages=1)
        try:
            doc.text = f"[Image file: {path.name}]"
            if HAS_PIL:
                img = Image.open(path)
                import io
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                doc.images.append(ParsedImage(
                    index=0, page=1, data=buf.getvalue(), format="png",
                ))
        except Exception as e:
            logger.warning(f"Image parse: {e}")
        return doc

    async def _call_vlm_describe(self, image_b64: str, fmt: str) -> str:
        if not self._api_key:
            return ""
        try:
            import aiohttp
            payload = {
                "model": "deepseek/deepseek-v4-flash",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image in 1-2 sentences. Focus on key information: charts, data, objects, text."},
                        {"type": "image_url", "image_url": {"url": f"data:image/{fmt};base64,{image_b64}"}},
                    ],
                }],
                "max_tokens": 256,
            }
            headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
        except Exception:
            pass
        return ""
