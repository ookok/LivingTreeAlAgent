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

    async def parse_with_primitives(self, file_path: str | Path) -> tuple[ParsedDocument, list]:
        """Parse with DeepSeek Visual Primitives for spatial understanding.

        Auto-detects if visual primitives would help (images/tables/scanned docs).
        Returns (document, visual_regions).
        """
        doc = await self.parse(file_path)
        regions = []

        extractor = get_visual_extractor(self._api_key, self._base_url)
        if not extractor.should_use_visual_primitive(doc):
            return doc, regions

        path = Path(file_path)
        if path.suffix.lower() == ".pdf" and HAS_PYMUPDF:
            try:
                import fitz
                pdf = fitz.open(str(path))
                for page_num in range(min(len(pdf), 10)):  # Max 10 pages
                    page = pdf[page_num]
                    page_regions = await extractor.analyze_pdf_page(page, page_num)
                    regions.extend(page_regions)
                pdf.close()
                logger.info("VisualPrimitives: analyzed %d pages → %d regions",
                           min(len(pdf), 10), len(regions))
            except Exception as e:
                logger.debug("VisualPrimitives PDF: %s", e)
        elif path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            try:
                img_data = path.read_bytes()
                fmt = path.suffix.lstrip(".")
                page_regions = await extractor.analyze(img_data, fmt)
                regions.extend(page_regions)
            except Exception as e:
                logger.debug("VisualPrimitives image: %s", e)

        # Enrich document with spatial information
        if regions:
            for r in regions:
                if r.region_type == "table" and r.content:
                    doc.tables.append(ParsedTable(
                        index=len(doc.tables),
                        page=r.page + 1,
                        rows=[[r.content]],
                        caption=f"Spatial table ({r.bbox[0]:.0f},{r.bbox[1]:.0f})",
                    ))
                elif r.region_type in ("stamp", "signature"):
                    doc.metadata.setdefault("spatial_features", []).append(
                        f"{r.region_type} at ({r.bbox[0]:.0f},{r.bbox[1]:.0f})"
                    )

        return doc, regions

    async def parse_with_layout(self, file_path: str | Path) -> tuple[ParsedDocument, Any]:
        """Parse with full MultiDocFusion layout analysis.

        Returns (document, PageLayout list) for hierarchical chunking.
        """
        doc = await self.parse(file_path)
        path = Path(file_path)

        layouts = []
        if path.suffix.lower() == ".pdf" and HAS_PYMUPDF:
            try:
                from ..knowledge.layout_analyzer import DocumentLayoutAnalyzer
                analyzer = DocumentLayoutAnalyzer()
                pdf = fitz.open(str(path))
                for page_num in range(len(pdf)):
                    page = pdf[page_num]
                    layout = analyzer.extract_from_pymupdf(page, page_num + 1)
                    layouts.append(layout)
                pdf.close()
            except Exception as e:
                logger.debug("Layout analysis failed: %s", e)

        return doc, layouts

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


# ═══ Visual Primitives — DeepSeek spatial reasoning integration ═══

@dataclass
class VisualRegion:
    """A spatially-anchored document region extracted via visual primitives."""
    region_type: str       # "table", "text", "stamp", "signature", "chart", "title"
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1) normalized 0-1
    content: str = ""      # extracted text content
    confidence: float = 0.8
    page: int = 0


class VisualPrimitiveExtractor:
    """Use DeepSeek-V4-Flash visual primitives for spatial document understanding.

    Core concept from DeepSeek's "Thinking with Visual Primitives" (2026.4.30):
      - Model outputs bounding box coordinates alongside content
      - Points and bounding boxes become minimal thinking units
      - Links abstract language logic to concrete spatial positions

    Usage:
        vpe = VisualPrimitiveExtractor(api_key, base_url)
        regions = await vpe.analyze(image_data)
        for r in regions:
            print(f"{r.region_type} at {r.bbox}: {r.content[:100]}")
    """

    VISUAL_PRIMITIVES_PROMPT = """Analyze this document image with spatial awareness.
For each distinct region, output JSON with bounding box and content:

{
  "regions": [
    {
      "type": "title|text|table|stamp|signature|chart|header|footer",
      "bbox": [x0, y0, x1, y1],  // normalized 0.0-1.0, top-left origin
      "content": "extracted text or description",
      "confidence": 0.0-1.0
    }
  ],
  "layout": "single_column|two_column|mixed",
  "has_stamp": false,
  "has_table": false,
  "orientation": "portrait|landscape"
}

Important:
- Use EXACT bounding box coordinates based on what you see
- For stamps/seals: mark type="stamp", extract any readable text
- For tables: mark type="table", extract headers + data
- For signatures: mark type="signature"
- Normalize all coordinates to 0.0-1.0 range
Return ONLY the JSON, no other text."""

    def __init__(self, api_key: str = "", base_url: str = ""):
        self._api_key = api_key
        self._base_url = base_url or "https://api.deepseek.com"

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def analyze(self, image_data: bytes, image_format: str = "png",
                      page_number: int = 0) -> list[VisualRegion]:
        """Analyze an image/document page using visual primitives.

        Args:
            image_data: raw image bytes
            image_format: "png", "jpeg", "webp"
            page_number: page index for multi-page documents

        Returns:
            List of VisualRegion objects with spatial coordinates
        """
        if not self._api_key:
            return []

        import base64
        b64 = base64.b64encode(image_data).decode()

        payload = {
            "model": "deepseek-v4-flash",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": self.VISUAL_PRIMITIVES_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/{image_format};base64,{b64}"}},
                ],
            }],
            "temperature": 0.0,
            "max_tokens": 4096,
        }

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data["choices"][0]["message"]["content"]
                        return self._parse_regions(text, page_number)
        except Exception as e:
            logger.debug("VisualPrimitive analyze: %s", e)

        return []

    async def analyze_pdf_page(self, fitz_page, page_number: int = 0,
                              dpi: int = 200) -> list[VisualRegion]:
        """Analyze a single PDF page via visual primitives.

        Renders the page to an image, then sends to DeepSeek-V4-Flash.
        """
        if not self._api_key:
            return []

        try:
            pix = fitz_page.get_pixmap(dpi=dpi)
            regions = await self.analyze(pix.tobytes(), "png", page_number)

            # Map normalized coordinates to page coordinates
            page_rect = fitz_page.rect
            for r in regions:
                r.bbox = (
                    r.bbox[0] * page_rect.width,
                    r.bbox[1] * page_rect.height,
                    r.bbox[2] * page_rect.width,
                    r.bbox[3] * page_rect.height,
                )
            return regions
        except Exception as e:
            logger.debug("VisualPrimitive PDF: %s", e)
            return []

    def _parse_regions(self, text: str, page: int) -> list[VisualRegion]:
        """Parse LLM response into VisualRegion list."""
        import json
        try:
            if "{" in text:
                text = text[text.index("{"):text.rindex("}") + 1]
            data = json.loads(text)
            regions_data = data.get("regions", [])

            return [
                VisualRegion(
                    region_type=r.get("type", "text"),
                    bbox=tuple(r.get("bbox", [0, 0, 1, 1])),
                    content=r.get("content", "")[:500],
                    confidence=r.get("confidence", 0.8),
                    page=page,
                )
                for r in regions_data
            ]
        except Exception:
            return []

    def should_use_visual_primitive(self, doc: ParsedDocument) -> bool:
        if not doc:
            return False
        if doc.images:
            return True
        if doc.tables:
            return True
        return False

        # Has images that need spatial understanding
        if doc.images and len(doc.images) > 0:
            return True

        # Has tables (spatial structure)
        if doc.tables and len(doc.tables) > 0:
            return True

        # Scanned document indicator: total_pages > 0 but no clear text
        if doc.total_pages > 0 and (not doc.text or len(doc.text) < 200):
            return True

        return False


def get_visual_extractor(api_key: str = "", base_url: str = "") -> VisualPrimitiveExtractor:
    """Auto-configure visual primitive extractor from config."""
    if not api_key:
        try:
            from ..config import get_config
            config = get_config()
            api_key = config.deepseek_api_key or ""
            base_url = config.deepseek_base_url or "https://api.deepseek.com"
        except Exception:
            pass

    return VisualPrimitiveExtractor(api_key=api_key, base_url=base_url)

