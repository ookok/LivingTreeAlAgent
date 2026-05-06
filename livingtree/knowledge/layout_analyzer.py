"""DocumentLayoutAnalyzer — vision-based document region detection.

Implements the layout analysis component of MultiDocFusion:
  - Region detection: title area, text body, tables, figures, sidebars
  - Figure-caption binding: associate images with their captions
  - Column detection: multi-column text flow recognition
  - Layout-to-tree mapping: map detected regions to DocSection tree

Enhances MultimodalParser with layout-aware document understanding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

from .document_tree import DocSection


@dataclass
class LayoutRegion:
    """A detected region on a document page.

    Attributes:
        region_id: unique region identifier
        page: page number
        region_type: "title", "body", "table", "figure", "sidebar", "header", "footer"
        bbox: bounding box (x0, y0, x1, y1) in page coordinates
        text: extracted text content
        confidence: detection confidence
        metadata: extra info (font sizes, styles, etc.)
    """
    region_id: str
    page: int
    region_type: str
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    text: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def area(self) -> float:
        return (self.bbox[2] - self.bbox[0]) * (self.bbox[3] - self.bbox[1])

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]


@dataclass
class FigureCaption:
    """A figure-caption association."""
    figure_region: LayoutRegion
    caption_region: LayoutRegion
    page: int
    confidence: float = 1.0

    @property
    def caption_text(self) -> str:
        return self.caption_region.text

    @property
    def figure_id(self) -> str:
        return self.figure_region.region_id


@dataclass
class PageLayout:
    """Complete layout analysis for one page."""
    page_number: int
    width: float = 0.0
    height: float = 0.0
    regions: list[LayoutRegion] = field(default_factory=list)
    figure_captions: list[FigureCaption] = field(default_factory=list)
    column_count: int = 1
    has_header: bool = False
    has_footer: bool = False

    @property
    def body_regions(self) -> list[LayoutRegion]:
        return [r for r in self.regions if r.region_type == "body"]

    @property
    def title_regions(self) -> list[LayoutRegion]:
        return [r for r in self.regions if r.region_type == "title"]

    @property
    def table_regions(self) -> list[LayoutRegion]:
        return [r for r in self.regions if r.region_type == "table"]

    @property
    def figure_regions(self) -> list[LayoutRegion]:
        return [r for r in self.regions if r.region_type == "figure"]


class DocumentLayoutAnalyzer:
    """Vision-based document layout analysis engine.

    Detects page regions, associates figures with captions, and maps
    layout regions to the DSHP document tree.

    Works with PyMuPDF for PDF analysis and falls back to heuristic
    text-based detection for non-PDF documents.

    Usage:
        analyzer = DocumentLayoutAnalyzer()
        layout = analyzer.analyze_page(page_blocks, page_number=1)
        tree = analyzer.map_to_tree(layouts, text)
    """

    def __init__(self):
        self._figure_patterns = [
            r'(?:图|Figure|Fig\.)\s*\d+',
            r'(?:表|Table)\s*\d+',
            r'(?:图表|Chart|Graph)\s*\d*',
        ]

    def analyze_page(
        self,
        blocks: list[dict],
        page_number: int = 1,
        page_width: float = 0,
        page_height: float = 0,
    ) -> PageLayout:
        """Analyze a single page's layout from PyMuPDF blocks.

        Args:
            blocks: list of text blocks from PyMuPDF (each has bbox, lines, etc.)
            page_number: 1-indexed page number
            page_width, page_height: page dimensions
        """
        page = PageLayout(
            page_number=page_number,
            width=page_width,
            height=page_height,
        )

        if not blocks:
            return page

        for i, block in enumerate(blocks):
            region = self._classify_block(block, i, page_number, page_width, page_height)
            page.regions.append(region)

        page.figure_captions = self._bind_figures_to_captions(page.regions)
        page.column_count = self._detect_columns(page.regions, page_width)
        page.has_header = any(r.region_type == "header" for r in page.regions)
        page.has_footer = any(r.region_type == "footer" for r in page.regions)

        return page

    def analyze_pages(
        self,
        all_blocks: list[list[dict]],
        page_widths: list[float] = None,
        page_heights: list[float] = None,
    ) -> list[PageLayout]:
        """Analyze all pages of a document."""
        layouts = []
        for i, blocks in enumerate(all_blocks):
            w = page_widths[i] if page_widths and i < len(page_widths) else 0
            h = page_heights[i] if page_heights and i < len(page_heights) else 0
            layouts.append(self.analyze_page(blocks, i + 1, w, h))
        return layouts

    def map_to_tree(
        self,
        layouts: list[PageLayout],
        base_tree,
    ) -> None:
        """Map layout regions to document tree sections.

        Enriches each DocSection with page ranges and bounding boxes
        derived from the layout analysis. This enables spatial-aware
        chunking and retrieval.
        """
        if not layouts or not base_tree:
            return

        page_to_sections = self._build_page_section_map(base_tree)

        for layout in layouts:
            for region in layout.regions:
                if region.region_type == "title" and region.text:
                    section = base_tree.find_section_by_title(region.text, fuzzy=True)
                    if section:
                        if section.page_range == (0, 0):
                            section.page_range = (layout.page_number, layout.page_number)
                        else:
                            start = min(section.page_range[0], layout.page_number)
                            end = max(section.page_range[1], layout.page_number)
                            section.page_range = (start, end)
                        section.bbox.append(region.bbox)

    def extract_from_pymupdf(self, fitz_page, page_number: int = 1) -> PageLayout:
        """Extract layout from a PyMuPDF page object."""
        try:
            page_rect = fitz_page.rect
            blocks = fitz_page.get_text("dict", flags=0)["blocks"]
        except Exception as e:
            logger.warning("PyMuPDF layout extraction failed: %s", e)
            return PageLayout(page_number=page_number)

        return self.analyze_page(
            blocks=blocks,
            page_number=page_number,
            page_width=page_rect.width if page_rect else 0,
            page_height=page_rect.height if page_rect else 0,
        )

    def _classify_block(
        self, block: dict, index: int, page: int,
        page_width: float, page_height: float,
    ) -> LayoutRegion:
        bbox = self._extract_bbox(block)
        text = self._extract_text(block)
        font_sizes = self._extract_font_sizes(block)

        region_type = "body"
        confidence = 0.7

        if not text.strip():
            region_type = "whitespace"
            confidence = 0.9
        elif self._is_title_block(text, bbox, page_width, font_sizes):
            region_type = "title"
            confidence = 0.9
        elif self._is_header_region(bbox, page_height):
            region_type = "header"
            confidence = 0.85
        elif self._is_footer_region(bbox, page_height):
            region_type = "footer"
            confidence = 0.85
        elif self._is_table_block(block):
            region_type = "table"
            confidence = 0.8
        elif self._is_figure_caption(text):
            region_type = "figure"
            confidence = 0.75
        elif self._is_sidebar(bbox, page_width):
            region_type = "sidebar"
            confidence = 0.7

        return LayoutRegion(
            region_id=f"p{page}_b{index}",
            page=page,
            region_type=region_type,
            bbox=bbox,
            text=text,
            confidence=confidence,
            metadata={"font_sizes": font_sizes},
        )

    def _bind_figures_to_captions(self, regions: list[LayoutRegion]) -> list[FigureCaption]:
        """Associate figure regions with their caption texts."""
        bindings = []
        figure_regions = [r for r in regions if r.region_type == "figure"]
        caption_regions = [r for r in regions if self._is_figure_caption(r.text)]

        for fig in figure_regions:
            best_caption = None
            best_distance = float('inf')

            for cap in caption_regions:
                if cap.page != fig.page:
                    continue
                distance = self._bbox_distance(fig.bbox, cap.bbox)
                caption_above = cap.bbox[3] <= fig.bbox[1]
                caption_below = cap.bbox[1] >= fig.bbox[3]

                if (caption_above or caption_below) and distance < best_distance:
                    best_distance = distance
                    best_caption = cap

            if best_caption:
                bindings.append(FigureCaption(
                    figure_region=fig,
                    caption_region=best_caption,
                    page=fig.page,
                    confidence=max(0.5, 1.0 - best_distance / 1000),
                ))

        return bindings

    def _detect_columns(self, regions: list[LayoutRegion], page_width: float) -> int:
        """Detect number of text columns on a page."""
        if not page_width or not regions:
            return 1

        body_regions = [r for r in regions if r.region_type == "body"]
        if not body_regions:
            return 1

        x_centers = [r.bbox[0] + r.width / 2 for r in body_regions]
        if not x_centers:
            return 1

        x_centers.sort()
        gaps = [(x_centers[i] - x_centers[i-1]) for i in range(1, len(x_centers))]

        if not gaps:
            return 1

        avg_gap = sum(gaps) / len(gaps)
        threshold = page_width * 0.05

        significant_gaps = sum(1 for g in gaps if g > threshold)
        return min(3, significant_gaps + 1)

    @staticmethod
    def _build_page_section_map(tree) -> dict:
        """Build page-to-section mapping for tree enrichment."""
        return {}  # Implemented via map_to_tree directly

    @staticmethod
    def _extract_bbox(block: dict) -> tuple[float, float, float, float]:
        bbox = block.get("bbox", (0, 0, 0, 0))
        return (bbox[0], bbox[1], bbox[2], bbox[3])

    @staticmethod
    def _extract_text(block: dict) -> str:
        lines = block.get("lines", [])
        text_parts = []
        for line in lines:
            spans = line.get("spans", [])
            line_text = "".join(s.get("text", "") for s in spans)
            text_parts.append(line_text)
        return "\n".join(text_parts)

    @staticmethod
    def _extract_font_sizes(block: dict) -> list[float]:
        sizes = []
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size", 0)
                if size:
                    sizes.append(size)
        return sizes

    @staticmethod
    def _is_header_region(bbox: tuple, page_height: float) -> bool:
        if not page_height:
            return False
        return bbox[1] < page_height * 0.08

    @staticmethod
    def _is_footer_region(bbox: tuple, page_height: float) -> bool:
        if not page_height:
            return False
        return bbox[1] > page_height * 0.92

    @staticmethod
    def _is_title_block(text: str, bbox: tuple, page_width: float, font_sizes: list[float] = None) -> bool:
        if not text.strip():
            return False
        avg_font = sum(font_sizes) / len(font_sizes) if font_sizes else 12
        # Very top of page with tiny font → header, not title
        if bbox[1] < 30 and avg_font <= 10:
            return False
        if bbox[1] < 50:
            return True
        if avg_font > 16:
            return True
        if avg_font > 14 and len(text.strip()) < 200:
            return True
        return False
        avg_font = sum(font_sizes) / len(font_sizes) if font_sizes else 12
        if bbox[1] < 50:
            return True
        # Title: large font, short text, or at top of page
        if avg_font > 16:
            return True
        if avg_font > 14 and len(text.strip()) < 200:
            return True
        return False

    @staticmethod
    def _is_table_block(block: dict) -> bool:
        lines = block.get("lines", [])
        if len(lines) < 3:
            return False
        for line in lines:
            spans = line.get("spans", [])
            for span in spans:
                if span.get("flags", 0) & 4:
                    return True
        return len(lines) >= 5 and all(
            len(line.get("spans", [])) >= 2 for line in lines
        )

    @staticmethod
    def _is_figure_caption(text: str) -> bool:
        import re
        patterns = [
            r'^(?:图|Figure|Fig\.)\s*\d',
            r'^(?:表|Table)\s*\d',
            r'^(?:图表|Chart|Graph)\s*\d',
        ]
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _is_sidebar(bbox: tuple, page_width: float) -> bool:
        if not page_width:
            return False
        return bbox[2] < page_width * 0.3 or bbox[0] > page_width * 0.7

    @staticmethod
    def _bbox_distance(a: tuple, b: tuple) -> float:
        center_a = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
        center_b = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
        return ((center_a[0] - center_b[0]) ** 2 + (center_a[1] - center_b[1]) ** 2) ** 0.5
