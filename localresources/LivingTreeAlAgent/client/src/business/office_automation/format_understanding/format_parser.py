"""
📄 格式解析器 - Format Parser

核心功能：
1. 解压 Office 文档 (ZIP) 获取 XML 文件
2. 解析所有格式相关的 XML (styles.xml, document.xml, numbering.xml 等)
3. 提取所有格式信息 (显式/继承/默认/条件格式)
4. 构建格式信息结构

支持的格式维度：
- 视觉格式: 字体/段落/页面/表格/图片
- 结构格式: 标题层级/大纲/逻辑关系/元数据
- 语义格式: 样式语义/业务含义/重要性信号
"""

import os
import zipfile
import xml.etree.ElementTree as ET
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple, Set
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


# ===== 格式类型枚举 =====

class FormatDimension(Enum):
    """格式维度"""
    VISUAL = "visual"           # 视觉格式
    STRUCTURAL = "structural"    # 结构格式
    SEMANTIC = "semantic"       # 语义格式


class ElementType(Enum):
    """元素类型"""
    PARAGRAPH = "paragraph"
    TEXT_RUN = "text_run"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    IMAGE = "image"
    SHAPE = "shape"
    CHART = "chart"
    SECTION = "section"
    HEADER = "header"
    FOOTER = "footer"
    LIST = "list"
    LIST_ITEM = "list_item"


class FormatPropertyType(Enum):
    """格式属性类型"""
    # 字体属性
    FONT_NAME = "font_name"
    FONT_SIZE = "font_size"
    FONT_COLOR = "font_color"
    FONT_BOLD = "font_bold"
    FONT_ITALIC = "font_italic"
    FONT_UNDERLINE = "font_underline"
    FONT_STRIKETHROUGH = "font_strikethrough"

    # 段落属性
    PARAGRAPH_ALIGNMENT = "alignment"
    PARAGRAPH_INDENT_LEFT = "indent_left"
    PARAGRAPH_INDENT_RIGHT = "indent_right"
    PARAGRAPH_INDENT_FIRST = "indent_first"
    PARAGRAPH_SPACING_BEFORE = "spacing_before"
    PARAGRAPH_SPACING_AFTER = "spacing_after"
    PARAGRAPH_LINE_SPACING = "line_spacing"

    # 页面属性
    PAGE_WIDTH = "page_width"
    PAGE_HEIGHT = "page_height"
    PAGE_MARGIN_TOP = "margin_top"
    PAGE_MARGIN_BOTTOM = "margin_bottom"
    PAGE_MARGIN_LEFT = "margin_left"
    PAGE_MARGIN_RIGHT = "margin_right"
    PAGE_ORIENTATION = "page_orientation"

    # 表格属性
    TABLE_BORDER = "table_border"
    TABLE_WIDTH = "table_width"
    TABLE_CELL_PADDING = "cell_padding"
    TABLE_CELL_MARGIN = "cell_margin"
    TABLE_ALIGNMENT = "table_alignment"

    # 单元格属性
    CELL_WIDTH = "cell_width"
    CELL_VERTICAL_ALIGN = "cell_vertical_align"
    CELL_BACKGROUND = "cell_background"
    CELL_SPAN = "cell_span"


# ===== 数据类 =====

@dataclass
class FormatProperty:
    """格式属性"""
    name: str
    value: Any
    source: str = "explicit"  # explicit/inherited/default/conditional
    is_style: bool = False
    style_name: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": str(self.value),
            "source": self.source,
            "is_style": self.is_style,
            "style_name": self.style_name,
        }


@dataclass
class VisualFormat:
    """视觉格式信息"""
    # 字体
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    font_color: Optional[str] = None
    font_bold: bool = False
    font_italic: bool = False
    font_underline: bool = False

    # 段落
    alignment: str = "left"  # left/center/right/justify
    indent_left: float = 0.0
    indent_right: float = 0.0
    indent_first: float = 0.0
    spacing_before: float = 0.0
    spacing_after: float = 0.0
    line_spacing: float = 1.5

    # 页面
    page_width: float = 210.0   # mm (A4)
    page_height: float = 297.0
    margin_top: float = 25.4
    margin_bottom: float = 25.4
    margin_left: float = 31.7
    margin_right: float = 31.7
    orientation: str = "portrait"

    # 表格
    table_border_width: float = 0.5
    table_width: float = 100.0  # %
    cell_padding: float = 5.0

    # 背景/装饰
    background_color: Optional[str] = None
    border_color: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "font": {
                "name": self.font_name,
                "size": self.font_size,
                "color": self.font_color,
                "bold": self.font_bold,
                "italic": self.font_italic,
                "underline": self.font_underline,
            },
            "paragraph": {
                "alignment": self.alignment,
                "indent": {
                    "left": self.indent_left,
                    "right": self.indent_right,
                    "first": self.indent_first,
                },
                "spacing": {
                    "before": self.spacing_before,
                    "after": self.spacing_after,
                    "line": self.line_spacing,
                },
            },
            "page": {
                "width": self.page_width,
                "height": self.page_height,
                "margins": {
                    "top": self.margin_top,
                    "bottom": self.margin_bottom,
                    "left": self.margin_left,
                    "right": self.margin_right,
                },
                "orientation": self.orientation,
            },
            "table": {
                "border_width": self.table_border_width,
                "width": self.table_width,
                "cell_padding": self.cell_padding,
            },
        }


@dataclass
class StructuralFormat:
    """结构格式信息"""
    element_type: ElementType = ElementType.PARAGRAPH
    style_name: str = ""
    style_id: str = ""
    outline_level: int = 0       # 大纲级别 0-9
    heading_level: int = 0       # 标题级别 0-9 (0=非标题)
    list_info: Dict = field(default_factory=dict)  # 列表信息
    parent_style: str = ""       # 父样式
    is_first_in_style: bool = False
    is_last_in_style: bool = False
    element_index: int = 0       # 在父容器中的索引
    children_count: int = 0      # 子元素数量

    # 逻辑关系
    bookmarks: List[str] = field(default_factory=list)
    hyperlinks: List[Dict] = field(default_factory=list)
    cross_references: List[Dict] = field(default_factory=list)

    # 元数据
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "element_type": self.element_type.value,
            "style_name": self.style_name,
            "style_id": self.style_id,
            "outline_level": self.outline_level,
            "heading_level": self.heading_level,
            "list_info": self.list_info,
            "parent_style": self.parent_style,
            "bookmarks": self.bookmarks,
            "hyperlinks": self.hyperlinks,
            "metadata": self.metadata,
        }


@dataclass
class SemanticFormat:
    """语义格式信息"""
    importance_level: int = 0     # 0-3: 普通/注意/重要/关键
    is_emphasis: bool = False    # 是否强调
    is_heading: bool = False    # 是否标题
    heading_rank: int = 0        # 标题级别

    # 语义角色
    semantic_role: str = ""       # heading/title/body/caption/note/code/quote
    business_type: str = ""       # 业务类型: clause/figure/table/formula
    legal_effect: str = ""       # 法律效力标记

    # 重要性信号
    visual_emphasis: List[str] = field(default_factory=list)  # bold/italic/color/size/caps
    color_meaning: str = ""      # 颜色含义: warning/error/info/success

    def to_dict(self) -> dict:
        return {
            "importance_level": self.importance_level,
            "is_emphasis": self.is_emphasis,
            "is_heading": self.is_heading,
            "heading_rank": self.heading_rank,
            "semantic_role": self.semantic_role,
            "business_type": self.business_type,
            "legal_effect": self.legal_effect,
            "visual_emphasis": self.visual_emphasis,
            "color_meaning": self.color_meaning,
        }


@dataclass
class FormatElement:
    """格式元素 - 完整格式信息"""
    element_id: str
    element_type: ElementType
    text_content: str = ""
    visual: VisualFormat = field(default_factory=VisualFormat)
    structural: StructuralFormat = field(default_factory=StructuralFormat)
    semantic: SemanticFormat = field(default_factory=SemanticFormat)
    raw_properties: Dict[str, FormatProperty] = field(default_factory=dict)
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.element_id,
            "type": self.element_type.value,
            "text_content": self.text_content[:100] if self.text_content else "",
            "visual": self.visual.to_dict(),
            "structural": self.structural.to_dict(),
            "semantic": self.semantic.to_dict(),
        }


@dataclass
class FormatInfo:
    """完整格式信息"""
    file_path: str
    file_type: str  # docx/xlsx/pptx
    elements: List[FormatElement] = field(default_factory=list)
    styles: Dict[str, Dict] = field(default_factory=dict)  # style_id -> style_def
    numbering: Dict[str, Dict] = field(default_factory=dict)  # numbering_id -> num_def
    document_settings: Dict = field(default_factory=dict)
    element_tree: Dict = field(default_factory=dict)  # id -> {parent, children}

    # 统计
    total_paragraphs: int = 0
    total_tables: int = 0
    total_images: int = 0
    total_headings: int = 0
    style_count: int = 0

    # 全局格式特征
    primary_font: str = ""
    primary_font_size: float = 12.0
    color_scheme: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "stats": {
                "paragraphs": self.total_paragraphs,
                "tables": self.total_tables,
                "images": self.total_images,
                "headings": self.total_headings,
                "styles": self.style_count,
            },
            "primary_font": self.primary_font,
            "color_scheme": self.color_scheme,
        }


# ===== 格式解析器 =====

class FormatParser:
    """
    Office 文档格式解析器

    支持格式:
    - DOCX: Word 文档 (styles.xml, document.xml, numbering.xml, settings.xml)
    - XLSX: Excel 电子表格 (styles.xml, worksheets/*.xml)
    - PPTX: PowerPoint 演示文稿 (slideMasters, slides, layouts)

    工作流程:
    1. 解压文档 (ZIP)
    2. 解析 XML
    3. 提取格式信息
    4. 构建格式图谱
    5. 推断语义格式
    """

    # XML 命名空间
    NAMESPACES = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    }

    # 样式名称到语义的映射
    STYLE_SEMANTIC_MAP = {
        "heading": "heading",
        "title": "title",
        "subtitle": "subtitle",
        "normal": "body",
        "body": "body",
        "caption": "caption",
        "note": "note",
        "code": "code",
        "quote": "quote",
        "toc": "toc",
        "header": "header",
        "footer": "footer",
    }

    def __init__(self):
        self.element_counter = 0
        self.current_file = ""

    def parse(self, file_path: str) -> FormatInfo:
        """
        解析 Office 文档

        Args:
            file_path: 文档路径

        Returns:
            FormatInfo 完整格式信息
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        self.current_file = file_path
        self.element_counter = 0

        ext = Path(file_path).suffix.lower()
        if ext == ".docx":
            return self._parse_docx(file_path)
        elif ext == ".xlsx":
            return self._parse_xlsx(file_path)
        elif ext == ".pptx":
            return self._parse_pptx(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")

    def _parse_docx(self, file_path: str) -> FormatInfo:
        """解析 DOCX 文档"""
        info = FormatInfo(file_path=file_path, file_type="docx")

        with zipfile.ZipFile(file_path, 'r') as z:
            # 解析 styles.xml
            styles_xml = self._read_xml(z, "word/styles.xml")
            if styles_xml:
                info.styles = self._parse_styles_xml(styles_xml)

            # 解析 numbering.xml
            numbering_xml = self._read_xml(z, "word/numbering.xml")
            if numbering_xml:
                info.numbering = self._parse_numbering_xml(numbering_xml)

            # 解析 document.xml
            doc_xml = self._read_xml(z, "word/document.xml")
            if doc_xml:
                elements = self._parse_document_xml(doc_xml, info)
                info.elements = elements

            # 解析 settings.xml
            settings_xml = self._read_xml(z, "word/settings.xml")
            if settings_xml:
                info.document_settings = self._parse_settings_xml(settings_xml)

        # 统计
        self._compute_statistics(info)

        return info

    def _parse_xlsx(self, file_path: str) -> FormatInfo:
        """解析 XLSX 文档"""
        info = FormatInfo(file_path=file_path, file_type="xlsx")

        with zipfile.ZipFile(file_path, 'r') as z:
            # 解析 styles.xml
            styles_xml = self._read_xml(z, "xl/styles.xml")
            if styles_xml:
                info.styles = self._parse_xlsx_styles(styles_xml)

            # 解析工作表
            worksheet_files = [f for f in z.namelist() if f.startswith("xl/worksheets/")]
            for ws_file in worksheet_files:
                ws_xml = self._read_xml(z, ws_file)
                if ws_xml:
                    elements = self._parse_xlsx_worksheet(ws_xml, info)
                    info.elements.extend(elements)

        self._compute_statistics(info)
        return info

    def _parse_pptx(self, file_path: str) -> FormatInfo:
        """解析 PPTX 文档"""
        info = FormatInfo(file_path=file_path, file_type="pptx")

        with zipfile.ZipFile(file_path, 'r') as z:
            # 解析幻灯片
            slide_files = sorted([f for f in z.namelist() if f.startswith("ppt/slides/slide") and f.endswith(".xml")])
            for slide_file in slide_files:
                slide_xml = self._read_xml(z, slide_file)
                if slide_xml:
                    elements = self._parse_pptx_slide(slide_xml, info)
                    info.elements.extend(elements)

        self._compute_statistics(info)
        return info

    # ===== DOCX 解析方法 =====

    def _read_xml(self, z: zipfile.ZipFile, name: str) -> Optional[ET.Element]:
        """读取并解析 XML 文件"""
        try:
            with z.open(name) as f:
                content = f.read()
                return ET.fromstring(content)
        except Exception as e:
            logger.debug(f"无法读取 {name}: {e}")
            return None

    def _parse_styles_xml(self, root: ET.Element) -> Dict:
        """解析 styles.xml"""
        styles = {}
        ns = self.NAMESPACES["w"]

        for style_elem in root.findall(f".//{{{ns}}}style"):
            style_id = style_elem.get(f"{{{ns}}}styleId", "")
            style_type = style_elem.get(f"{{{ns}}}type", "")

            style_info = {
                "id": style_id,
                "type": style_type,
                "name": "",
                "based_on": "",
                "next_style": "",
                "properties": {},
            }

            # 样式名称
            name_elem = style_elem.find(f"{{{ns}}}name")
            if name_elem is not None:
                style_info["name"] = name_elem.get(f"{{{ns}}}val", "")

            # 基于样式
            based_on_elem = style_elem.find(f"{{{ns}}}basedOn")
            if based_on_elem is not None:
                style_info["based_on"] = based_on_elem.get(f"{{{ns}}}val", "")

            # 下一个样式
            next_elem = style_elem.find(f"{{{ns}}}next")
            if next_elem is not None:
                style_info["next_style"] = next_elem.get(f"{{{ns}}}val", "")

            # 字体属性
            rpr_elem = style_elem.find(f"{{{ns}}}rPr")
            if rpr_elem is not None:
                style_info["properties"]["font"] = self._parse_run_properties(rpr_elem, ns)

            # 段落属性
            ppr_elem = style_elem.find(f"{{{ns}}}pPr")
            if ppr_elem is not None:
                style_info["properties"]["paragraph"] = self._parse_paragraph_properties(ppr_elem, ns)

            styles[style_id] = style_info

        return styles

    def _parse_numbering_xml(self, root: ET.Element) -> Dict:
        """解析 numbering.xml"""
        numbering = {}
        ns = self.NAMESPACES["w"]

        for abstract_num in root.findall(f".//{{{ns}}}abstractNum"):
            abstract_id = abstract_num.get(f"{{{ns}}}abstractNumId", "")

            for lvl in abstract_num.findall(f"{{{ns}}}lvl"):
                ilvl = lvl.get(f"{{{ns}}}ilvl", "0")

                num_info = {
                    "abstract_id": abstract_id,
                    "level": int(ilvl),
                    "format": "",
                    "start": 1,
                    "text": "",
                }

                # 编号格式
                num_fmt = lvl.find(f"{{{ns}}}numFmt")
                if num_fmt is not None:
                    num_info["format"] = num_fmt.get(f"{{{ns}}}val", "decimal")

                # 起始值
                start = lvl.find(f"{{{ns}}}start")
                if start is not None:
                    num_info["start"] = int(start.get(f"{{{ns}}}val", "1"))

                # 级别文本
                lvl_text = lvl.find(f"{{{ns}}}lvlText")
                if lvl_text is not None:
                    num_info["text"] = lvl_text.get(f"{{{ns}}}val", "")

                numbering[f"{abstract_id}_{ilvl}"] = num_info

        return numbering

    def _parse_document_xml(self, root: ET.Element, info: FormatInfo) -> List[FormatElement]:
        """解析 document.xml"""
        elements = []
        ns = self.NAMESPACES["w"]

        for para_elem in root.findall(f".//{{{ns}}}p"):
            element = self._parse_paragraph(para_elem, info, ns)
            elements.append(element)

        for table_elem in root.findall(f".//{{{ns}}}tbl"):
            element = self._parse_table(table_elem, info, ns)
            elements.append(element)

        return elements

    def _parse_paragraph(self, para_elem: ET.Element, info: FormatInfo, ns: str) -> FormatElement:
        """解析段落元素"""
        self.element_counter += 1
        element_id = f"para_{self.element_counter:05d}"

        # 提取文本
        text_parts = []
        for t in para_elem.findall(f".//{{{ns}}}t"):
            if t.text:
                text_parts.append(t.text)
        text_content = "".join(text_parts)

        # 结构信息
        structural = StructuralFormat(element_type=ElementType.PARAGRAPH)

        # 样式
        ppr_elem = para_elem.find(f"{{{ns}}}pPr")
        if ppr_elem is not None:
            # 样式引用
            pstyle = ppr_elem.find(f"{{{ns}}}pStyle")
            if pstyle is not None:
                structural.style_id = pstyle.get(f"{{{ns}}}val", "")
                structural.style_name = info.styles.get(structural.style_id, {}).get("name", "")

            # 大纲级别
            outline_lvl = ppr_elem.find(f"{{{ns}}}outlineLvl")
            if outline_lvl is not None:
                lvl = outline_lvl.get(f"{{{ns}}}val", "0")
                structural.outline_level = int(lvl)
                structural.heading_level = int(lvl) + 1 if int(lvl) >= 0 else 0

            # 列表信息
            num_pr = ppr_elem.find(f"{{{ns}}}numPr")
            if num_pr is not None:
                structural.list_info = self._parse_list_info(num_pr, ns)

        # 视觉格式
        visual = VisualFormat()
        if ppr_elem:
            visual = self._parse_paragraph_properties(ppr_elem, ns)

        # 推断语义格式
        semantic = self._infer_semantic(structural, visual, text_content)

        return FormatElement(
            element_id=element_id,
            element_type=ElementType.PARAGRAPH,
            text_content=text_content,
            visual=visual,
            structural=structural,
            semantic=semantic,
        )

    def _parse_table(self, table_elem: ET.Element, info: FormatInfo, ns: str) -> FormatElement:
        """解析表格元素"""
        self.element_counter += 1
        element_id = f"table_{self.element_counter:05d}"

        visual = VisualFormat()

        # 表格属性
        tbl_pr = table_elem.find(f"{{{ns}}}tblPr")
        if tbl_pr is not None:
            tbl_width = tbl_pr.find(f"{{{ns}}}tblW")
            if tbl_width is not None:
                w_val = tbl_width.get(f"{{{ns}}}w", "0")
                w_type = tbl_width.get(f"{{{ns}}}type", "auto")
                if w_type == "pct":
                    visual.table_width = float(w_val) / 100.0
                else:
                    visual.table_width = float(w_val) / 567.0  # EMU to pt

        return FormatElement(
            element_id=element_id,
            element_type=ElementType.TABLE,
            text_content="[表格]",
            visual=visual,
        )

    def _parse_run_properties(self, rpr_elem: ET.Element, ns: str) -> Dict:
        """解析文本属性"""
        props = {}

        # 字体
        rFonts = rpr_elem.find(f"{{{ns}}}rFonts")
        if rFonts is not None:
            props["font_name"] = rFonts.get(f"{{{ns}}}ascii", "")

        # 大小
        sz = rpr_elem.find(f"{{{ns}}}sz")
        if sz is not None:
            props["font_size"] = int(sz.get(f"{{{ns}}}val", "24")) / 2.0  # half-points to pt

        # 颜色
        color = rpr_elem.find(f"{{{ns}}}color")
        if color is not None:
            props["font_color"] = color.get(f"{{{ns}}}val", "000000")

        # 加粗
        b = rpr_elem.find(f"{{{ns}}}b")
        if b is not None:
            props["font_bold"] = True

        # 斜体
        i = rpr_elem.find(f"{{{ns}}}i")
        if i is not None:
            props["font_italic"] = True

        # 下划线
        u = rpr_elem.find(f"{{{ns}}}u")
        if u is not None:
            props["font_underline"] = True

        return props

    def _parse_paragraph_properties(self, ppr_elem: ET.Element, ns: str) -> VisualFormat:
        """解析段落属性"""
        visual = VisualFormat()

        # 对齐
        jc = ppr_elem.find(f"{{{ns}}}jc")
        if jc is not None:
            visual.alignment = jc.get(f"{{{ns}}}val", "left")

        # 缩进
        ind = ppr_elem.find(f"{{{ns}}}ind")
        if ind is not None:
            visual.indent_left = float(ind.get(f"{{{ns}}}left", "0")) / 567.0
            visual.indent_right = float(ind.get(f"{{{ns}}}right", "0")) / 567.0
            visual.indent_first = float(ind.get(f"{{{ns}}}firstLine", "0")) / 567.0

        # 间距
        spacing = ppr_elem.find(f"{{{ns}}}spacing")
        if spacing is not None:
            before = spacing.get(f"{{{ns}}}before", "0")
            after = spacing.get(f"{{{ns}}}after", "0")
            line = spacing.get(f"{{{ns}}}line", "240")
            visual.spacing_before = int(before) / 20.0  # twips to pt
            visual.spacing_after = int(after) / 20.0
            visual.line_spacing = int(line) / 240.0

        return visual

    def _parse_list_info(self, num_pr: ET.Element, ns: str) -> Dict:
        """解析列表信息"""
        info = {}

        num_id = num_pr.find(f"{{{ns}}}numId")
        if num_id is not None:
            info["num_id"] = num_id.get(f"{{{ns}}}val", "")

        ilvl = num_pr.find(f"{{{ns}}}ilvl")
        if ilvl is not None:
            info["level"] = int(ilvl.get(f"{{{ns}}}val", "0"))

        return info

    def _parse_settings_xml(self, root: ET.Element) -> Dict:
        """解析 settings.xml"""
        settings = {}
        ns = self.NAMESPACES["w"]

        # 默认语言
        lang = root.find(f".//{{{ns}}}lang")
        if lang is not None:
            settings["language"] = lang.get(f"{{{ns}}}val", "en-US")

        # 默认制表符
        tabs = root.find(f".//{{{ns}}}tabs")
        if tabs is not None:
            settings["tabs"] = []
            for tab in tabs.findall(f"{{{ns}}}tab"):
                settings["tabs"].append({
                    "pos": tab.get(f"{{{ns}}}val", "0"),
                    "leader": tab.get(f"{{{ns}}}leader", "none"),
                })

        return settings

    # ===== XLSX 解析方法 =====

    def _parse_xlsx_styles(self, root: ET.Element) -> Dict:
        """解析 XLSX 样式"""
        styles = {}
        ns = self.NAMESPACES["x"]

        # 解析字体
        fonts = []
        for font_elem in root.findall(f".//{{{ns}}}font"):
            font_info = {}
            name = font_elem.find(f"{{{ns}}}name")
            if name is not None:
                font_info["name"] = name.get(f"{{{ns}}}val", "")
            fonts.append(font_info)

        styles["fonts"] = fonts

        # 解析填充
        fills = []
        for fill_elem in root.findall(f".//{{{ns}}}fill"):
            fill_info = {}
            pattern = fill_elem.find(f"{{{ns}}}patternFill")
            if pattern is not None:
                fill_info["pattern"] = pattern.get(f"{{{ns}}}patternType", "")
                fg = pattern.find(f"{{{ns}}}fgColor")
                if fg is not None:
                    fill_info["fg_color"] = fg.get(f"{{{ns}}}rgb", "")
            fills.append(fill_info)

        styles["fills"] = fills

        return styles

    def _parse_xlsx_worksheet(self, root: ET.Element, info: FormatInfo) -> List[FormatElement]:
        """解析 XLSX 工作表"""
        elements = []
        ns = self.NAMESPACES["x"]

        for row_elem in root.findall(f".//{{{ns}}}row"):
            for cell_elem in row_elem.findall(f"{{{ns}}}c"):
                cell_ref = cell_elem.get("r", "")
                value_elem = cell_elem.find(f"{{{ns}}}v")

                element = FormatElement(
                    element_id=f"cell_{cell_ref}",
                    element_type=ElementType.TABLE_CELL,
                    text_content=value_elem.text if value_elem is not None else "",
                )
                elements.append(element)

        return elements

    # ===== PPTX 解析方法 =====

    def _parse_pptx_slide(self, root: ET.Element, info: FormatInfo) -> List[FormatElement]:
        """解析 PPTX 幻灯片"""
        elements = []
        ns = self.NAMESPACES["p"]

        for shape_elem in root.findall(f".//{{{ns}}}sp"):
            # 提取文本
            text_elem = shape_elem.find(f".//{{{ns}}}t")
            text_content = text_elem.text if text_elem is not None else ""

            element = FormatElement(
                element_id=f"shape_{len(elements)}",
                element_type=ElementType.SHAPE,
                text_content=text_content,
            )
            elements.append(element)

        return elements

    # ===== 辅助方法 =====

    def _infer_semantic(self, structural: StructuralFormat,
                        visual: VisualFormat, text: str) -> SemanticFormat:
        """推断语义格式"""
        semantic = SemanticFormat()

        # 标题推断
        if structural.heading_level > 0:
            semantic.is_heading = True
            semantic.heading_rank = structural.heading_level
            semantic.semantic_role = "heading"

            # 重要性等级
            if structural.heading_level <= 1:
                semantic.importance_level = 3  # 关键
            elif structural.heading_level <= 2:
                semantic.importance_level = 2  # 重要
            else:
                semantic.importance_level = 1  # 注意

        # 强调推断
        if visual.font_bold or visual.font_italic:
            semantic.is_emphasis = True
            semantic.visual_emphasis.append("bold" if visual.font_bold else "italic")

        # 颜色含义
        if visual.font_color:
            if visual.font_color.upper() in ["FF0000", "CC0000", "E74C3C"]:
                semantic.color_meaning = "error"
                semantic.importance_level = max(semantic.importance_level, 2)
            elif visual.font_color.upper() in ["FFFF00", "FFC000", "F39C12"]:
                semantic.color_meaning = "warning"
            elif visual.font_color.upper() in ["00FF00", "27AE60", "2ECC71"]:
                semantic.color_meaning = "success"

        # 代码推断
        if visual.font_name and "code" in visual.font_name.lower():
            semantic.semantic_role = "code"

        return semantic

    def _compute_statistics(self, info: FormatInfo):
        """计算统计信息"""
        info.total_paragraphs = sum(1 for e in info.elements if e.element_type == ElementType.PARAGRAPH)
        info.total_tables = sum(1 for e in info.elements if e.element_type == ElementType.TABLE)
        info.total_images = sum(1 for e in info.elements if e.element_type == ElementType.IMAGE)
        info.total_headings = sum(1 for e in info.elements if e.semantic.is_heading)
        info.style_count = len(info.styles)

        # 主要字体
        font_counts = defaultdict(int)
        for elem in info.elements:
            if elem.visual.font_name:
                font_counts[elem.visual.font_name] += 1
        if font_counts:
            info.primary_font = max(font_counts, key=font_counts.get)
