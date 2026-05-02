# -*- coding: utf-8 -*-
"""
Markdown转Word文档系统 - DOCX生成器
====================================

功能：
- 将Markdown AST转换为Word文档
- 支持样式模板
- 支持图片、表格、代码块
- 生成目录、页眉页脚

作者：Hermes Desktop Team
版本：1.0.0
"""

import os
import io
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import zipfile
import xml.etree.ElementTree as ET

from .models import (
    DocumentNode, DocumentElement, ElementType,
    ConversionConfig, StyleTemplate, get_default_template,
    ImageConfig, TableConfig, PageConfig
)
from .markdown_parser import MarkdownParser, parse_markdown


class DOCXGenerator:
    """DOCX文档生成器"""

    # Word XML命名空间
    NAMESPACES = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
        'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
        'ct': 'http://schemas.openxmlformats.org/package/2006/content-types',
        'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
    }

    # 注册命名空间
    for prefix, uri in NAMESPACES.items():
        ET.register_namespace(prefix, uri)

    def __init__(self, config: Optional[ConversionConfig] = None):
        self.config = config or ConversionConfig()
        self.template = get_default_template()
        self.images: List[Tuple[str, bytes]] = []  # (image_id, data)
        self.image_counter = 0
        self._paragraph_id = 1

    def generate(self, document: DocumentNode) -> bytes:
        """生成DOCX文档字节数据"""
        # 创建文档结构
        self._create_document_structure(document)

        # 生成DOCX文件
        return self._generate_docx()

    def generate_from_markdown(self, markdown_text: str) -> bytes:
        """从Markdown文本生成DOCX"""
        parser = MarkdownParser(self.config)
        result = parser.parse(markdown_text)

        if not result.success or not result.document:
            raise ValueError(f"Markdown解析失败: {result.errors}")

        return self.generate(result.document)

    def generate_file(self, document: DocumentNode, output_path: str):
        """生成DOCX文件"""
        docx_data = self.generate(document)

        with open(output_path, 'wb') as f:
            f.write(docx_data)

    def generate_file_from_markdown(self, markdown_text: str, output_path: str):
        """从Markdown文本生成DOCX文件"""
        docx_data = self.generate_from_markdown(markdown_text)

        with open(output_path, 'wb') as f:
            f.write(docx_data)

    def _create_document_structure(self, document: DocumentNode):
        """创建文档内部结构"""
        self.document = document
        self.elements = document.elements
        self.image_counter = 0

    def _generate_docx(self) -> bytes:
        """生成DOCX文件"""
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 创建[Content_Types].xml
            zf.writestr('[Content_Types].xml', self._create_content_types())

            # 创建_rels/.rels
            zf.writestr('_rels/.rels', self._create_rels())

            # 创建word/_rels/document.xml.rels
            zf.writestr('word/_rels/document.xml.rels', self._create_document_rels())

            # 创建word/document.xml
            zf.writestr('word/document.xml', self._create_document_xml())

            # 创建word/styles.xml
            zf.writestr('word/styles.xml', self._create_styles_xml())

            # 创建word/settings.xml
            zf.writestr('word/settings.xml', self._create_settings_xml())

            # 创建word/theme/theme1.xml
            zf.writestr('word/theme/theme1.xml', self._create_theme_xml())

            # 添加图片
            for image_id, image_data in self.images:
                zf.writestr(f'word/media/{image_id}', image_data)

        return buffer.getvalue()

    def _create_content_types(self) -> str:
        """创建内容类型文件"""
        content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Default Extension="png" ContentType="image/png"/>
    <Default Extension="jpg" ContentType="image/jpeg"/>
    <Default Extension="jpeg" ContentType="image/jpeg"/>
    <Default Extension="gif" ContentType="image/gif"/>
    <Default Extension="bmp" ContentType="image/bmp"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
    <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
    <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
    <Override PartName="/word/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
</Types>'''
        return content_types

    def _create_rels(self) -> str:
        """创建关系文件"""
        rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''
        return rels

    def _create_document_rels(self) -> str:
        """创建文档关系文件"""
        rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']

        # 样式关系
        rels.append('    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
        rels.append('    <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>')
        rels.append('    <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>')

        # 图片关系
        for i, (image_id, _) in enumerate(self.images, start=10):
            rels.append(f'    <Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{image_id}"/>')

        rels.append('</Relationships>')
        return '\n'.join(rels)

    def _create_document_xml(self) -> str:
        """创建文档XML"""
        parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                 '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
                 '  <w:body>']

        # 添加标题
        if self.document.title:
            # 创建一个临时的标题元素
            title_elem = DocumentElement(
                element_type=ElementType.HEADING_1,
                content=self.document.title,
                level=1
            )
            title_xml = self._create_paragraph_xml(title_elem)
            parts.append(f'    {title_xml}')

        # 添加段落
        for elem in self.elements:
            elem_xml = self._element_to_xml(elem)
            if elem_xml:
                parts.append(f'    {elem_xml}')

        # 添加分页符（如果需要目录）
        if self.config.enable_table_of_contents:
            parts.append('    <w:p><w:r><w:br w:type="page"/></w:r></w:p>')

        # 添加文档结尾
        parts.append(f'    <w:sectPr>')
        parts.append(f'      <w:pgSz w:w="{self._pt_to_twips(210)}" w:h="{self._pt_to_twips(297)}"/>')  # A4
        parts.append(f'      <w:pgMar w:top="{self._cm_to_twips(self.config.page.margin_top)}" '
                     f'w:right="{self._cm_to_twips(self.config.page.margin_right)}" '
                     f'w:bottom="{self._cm_to_twips(self.config.page.margin_bottom)}" '
                     f'w:left="{self._cm_to_twips(self.config.page.margin_left)}"/>')
        parts.append(f'    </w:sectPr>')

        parts.append('  </w:body>')
        parts.append('</w:document>')

        return '\n'.join(parts)

    def _element_to_xml(self, elem: DocumentElement) -> Optional[str]:
        """将元素转换为Word XML"""
        if elem.element_type == ElementType.PARAGRAPH:
            return self._create_paragraph_xml(elem)
        elif elem.element_type in [ElementType.HEADING_1, ElementType.HEADING_2,
                                    ElementType.HEADING_3, ElementType.HEADING_4,
                                    ElementType.HEADING_5, ElementType.HEADING_6]:
            return self._create_heading_xml(elem)
        elif elem.element_type == ElementType.CODE_BLOCK:
            return self._create_code_block_xml(elem)
        elif elem.element_type == ElementType.BLOCKQUOTE:
            return self._create_blockquote_xml(elem)
        elif elem.element_type == ElementType.UNORDERED_LIST:
            return self._create_list_xml(elem, 'bullet')
        elif elem.element_type == ElementType.ORDERED_LIST:
            return self._create_list_xml(elem, 'number')
        elif elem.element_type == ElementType.TABLE:
            return self._create_table_xml(elem)
        elif elem.element_type == ElementType.TASK_ITEM:
            return self._create_task_item_xml(elem)
        elif elem.element_type == ElementType.HORIZONTAL_RULE:
            return '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="auto"/></w:pBdr></w:pPr></w:p>'
        elif elem.element_type == ElementType.MATH:
            return self._create_math_xml(elem)

        return None

    def _create_paragraph_xml(self, elem: DocumentElement, style: str = None) -> str:
        """创建段落XML"""
        para_id = self._paragraph_id
        self._paragraph_id += 1

        parts = [f'<w:p>']

        # 段落属性
        if style or elem.style_name:
            parts.append('<w:pPr>')
            if style or elem.style_name:
                style_name = style or elem.style_name
                parts.append(f'<w:pStyle w:val="{style_name}"/>')
            parts.append('</w:pPr>')

        # 段落内容
        parts.append('<w:r>')
        parts.append('<w:rPr>')

        if elem.bold:
            parts.append('<w:b/>')
        if elem.italic:
            parts.append('<w:i/>')

        parts.append('<w:sz w:val="24"/>')  # 12pt = 24 half-points
        parts.append('</w:rPr>')

        text = self._escape_xml(elem.content or self._get_element_text(elem))
        parts.append(f'<w:t xml:space="preserve">{text}</w:t>')
        parts.append('</w:r>')
        parts.append('</w:p>')

        return '\n'.join(parts)

    def _create_heading_xml(self, elem: DocumentElement) -> str:
        """创建标题XML"""
        level = elem.level if hasattr(elem, 'level') else 1
        style = f'Heading{level}'

        parts = [f'<w:p>',
                 '<w:pPr>',
                 f'<w:pStyle w:val="{style}"/>',
                 '</w:pPr>',
                 '<w:r>',
                 '<w:rPr>',
                 '<w:b/>',
                 f'<w:sz w:val="{48 - (level - 1) * 8}"/>',  # 标题大小递减
                 '</w:rPr>',
                 ]

        text = self._escape_xml(elem.content)
        parts.append(f'<w:t xml:space="preserve">{text}</w:t>')
        parts.append('</w:r>')
        parts.append('</w:p>')

        return '\n'.join(parts)

    def _create_code_block_xml(self, elem: DocumentElement) -> str:
        """创建代码块XML"""
        parts = ['<w:p>',
                 '<w:pPr>',
                 '<w:pStyle w:val="Code"/>',
                 '<w:ind w:left="720"/>',
                 '</w:pPr>',
                 '<w:r>',
                 '<w:rPr>',
                 '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>',
                 '<w:sz w:val="20"/>',
                 '<w:shd w:val="clear" w:color="auto" w:fill="F5F5F5"/>',
                 '</w:rPr>',
                 ]

        code = self._escape_xml(elem.content)
        parts.append(f'<w:t xml:space="preserve">{code}</w:t>')
        parts.append('</w:r>')
        parts.append('</w:p>')

        return '\n'.join(parts)

    def _create_blockquote_xml(self, elem: DocumentElement) -> str:
        """创建引用块XML"""
        parts = ['<w:p>',
                 '<w:pPr>',
                 '<w:pStyle w:val="Quote"/>',
                 '<w:ind w:left="720"/>',
                 '<w:pBdr>',
                 '<w:left w:val="single" w:sz="12" w:space="8" w:color="808080"/>',
                 '</w:pBdr>',
                 '</w:pPr>',
                 '<w:r>',
                 '<w:rPr>',
                 '<w:i/>',
                 '<w:color w:val="666666"/>',
                 '</w:rPr>',
                 ]

        text = self._escape_xml(elem.content or self._get_element_text(elem))
        parts.append(f'<w:t xml:space="preserve">{text}</w:t>')
        parts.append('</w:r>')
        parts.append('</w:p>')

        return '\n'.join(parts)

    def _create_list_xml(self, elem: DocumentElement, list_type: str) -> str:
        """创建列表XML"""
        parts = []

        for item in elem.children:
            parts.append('<w:p>')
            parts.append('<w:pPr>')

            if list_type == 'bullet':
                parts.append('<w:numPr>')
                parts.append('<w:ilvl w:val="0"/>')
                parts.append('<w:numId w:val="1"/>')
                parts.append('</w:numPr>')
            else:
                parts.append('<w:numPr>')
                parts.append('<w:ilvl w:val="0"/>')
                parts.append('<w:numId w:val="2"/>')
                parts.append('</w:numPr>')

            parts.append('</w:pPr>')
            parts.append('<w:r>')

            text = self._escape_xml(item.content)
            parts.append(f'<w:t xml:space="preserve">{text}</w:t>')
            parts.append('</w:r>')
            parts.append('</w:p>')

        return '\n'.join(parts)

    def _create_table_xml(self, elem: DocumentElement) -> str:
        """创建表格XML"""
        rows = []
        cols = elem.col_count if elem.col_count > 0 else 2

        # 处理表格数据
        current_row = []
        for i, child in enumerate(elem.children):
            current_row.append(child.content)
            if (i + 1) % cols == 0:
                rows.append(current_row)
                current_row = []

        if not rows:
            return ''

        parts = [f'<w:tbl>',
                 '<w:tblPr>',
                 '<w:tblStyle w:val="TableGrid"/>',
                 '<w:tblW w:w="0" w:type="auto"/>',
                 '<w:tblBorders>',
                 '<w:top w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>',
                 '<w:left w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>',
                 '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>',
                 '<w:right w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>',
                 '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>',
                 '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>',
                 '</w:tblBorders>',
                 '</w:tblPr>',
                 '<w:tblGrid>',
                 ]

        # 添加列定义
        for _ in range(cols):
            parts.append('<w:gridCol/>')

        parts.append('</w:tblGrid>')

        # 添加行
        for row_idx, row in enumerate(rows):
            parts.append('<w:tr>')

            for cell_idx, cell_text in enumerate(row):
                is_header = row_idx == 0

                parts.append('<w:tc>')
                parts.append('<w:tcPr>')

                if is_header:
                    parts.append('<w:shd w:val="clear" w:color="auto" w:fill="E0E0E0"/>')

                parts.append('</w:tcPr>')
                parts.append('<w:p>')
                parts.append('<w:r>')

                if is_header:
                    parts.append('<w:rPr><w:b/></w:rPr>')

                parts.append(f'<w:t xml:space="preserve">{self._escape_xml(cell_text)}</w:t>')
                parts.append('</w:r>')
                parts.append('</w:p>')
                parts.append('</w:tc>')

            parts.append('</w:tr>')

        parts.append('</w:tbl>')

        return '\n'.join(parts)

    def _create_task_item_xml(self, elem: DocumentElement) -> str:
        """创建任务项XML"""
        checked = elem.checked if hasattr(elem, 'checked') else False

        parts = ['<w:p>',
                 '<w:pPr>',
                 '<w:numPr>',
                 '<w:ilvl w:val="0"/>',
                 '<w:numId w:val="1"/>',
                 '</w:numPr>',
                 '</w:pPr>',
                 '<w:r>',
                 ]

        # 复选框
        checkbox = '☒' if checked else '☐'
        parts.append(f'<w:t xml:space="preserve">{checkbox} </w:t>')
        parts.append('</w:r>')

        # 文本
        parts.append('<w:r>')
        text = self._escape_xml(elem.content)
        parts.append(f'<w:t xml:space="preserve">{text}</w:t>')
        parts.append('</w:r>')

        parts.append('</w:p>')

        return '\n'.join(parts)

    def _create_math_xml(self, elem: DocumentElement) -> str:
        """创建数学公式XML"""
        parts = ['<w:p>',
                 '<w:pPr>',
                 '<w:jc w:val="center"/>',
                 '</w:pPr>',
                 '<w:r>',
                 '<w:rPr>',
                 '<w:rFonts w:ascii="Cambria Math"/>',
                 '</w:rPr>',
                 ]

        math_text = self._escape_xml(elem.content)
        parts.append(f'<w:t xml:space="preserve">{math_text}</w:t>')
        parts.append('</w:r>')
        parts.append('</w:p>')

        return '\n'.join(parts)

    def _create_styles_xml(self) -> str:
        """创建样式文件"""
        styles = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                  '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">']

        # 默认样式
        styles.append(self._create_style_xml('Normal', 'Normal', '', '24', '000000'))

        # 标题样式
        heading_sizes = ['48', '40', '36', '32', '28', '24']
        for i, size in enumerate(heading_sizes, 1):
            styles.append(self._create_style_xml(f'Heading{i}', f'标题 {i}', 'heading', size, '000000', bold=True))

        # 代码样式
        styles.append(self._create_code_style_xml())

        # 引用样式
        styles.append(self._create_style_xml('Quote', '引用', 'quote', '24', '666666', italic=True, left_indent='720'))

        # 表格样式
        styles.append('''<w:style w:type="table" w:styleId="TableGrid">
            <w:name w:val="Table Grid"/>
            <w:tblPr>
                <w:tblBorders>
                    <w:top w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
                    <w:left w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
                    <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
                    <w:right w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
                    <w:insideH w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
                    <w:insideV w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
                </w:tblBorders>
            </w:tblPr>
        </w:style>''')

        styles.append('</w:styles>')

        return '\n'.join(styles)

    def _create_style_xml(self, style_id: str, name: str, based_on: str,
                          size: str, color: str, bold: bool = False,
                          italic: bool = False, left_indent: str = '') -> str:
        """创建样式XML片段"""
        parts = [f'<w:style w:type="paragraph" w:styleId="{style_id}">',
                 f'<w:name w:val="{name}"/>']

        if based_on:
            parts.append(f'<w:basedOn w:val="{based_on}"/>')

        parts.append('<w:rPr>')
        parts.append(f'<w:sz w:val="{size}"/>')
        parts.append(f'<w:color w:val="{color}"/>')

        if bold:
            parts.append('<w:b/>')
        if italic:
            parts.append('<w:i/>')

        if left_indent:
            parts.append(f'<w:ind w:left="{left_indent}"/>')

        parts.append('</w:rPr>')
        parts.append('</w:style>')

        return '\n'.join(parts)

    def _create_code_style_xml(self) -> str:
        """创建代码样式"""
        return '''<w:style w:type="paragraph" w:styleId="Code">
            <w:name w:val="Code"/>
            <w:basedOn w:val="Normal"/>
            <w:rPr>
                <w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>
                <w:sz w:val="20"/>
                <w:shd w:val="clear" w:color="auto" w:fill="F5F5F5"/>
            </w:rPr>
        </w:style>'''

    def _create_settings_xml(self) -> str:
        """创建设置文件"""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:defaultTabStop w:val="720"/>
    <w:compat>
        <w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="14"/>
    </w:compat>
</w:settings>'''

    def _create_theme_xml(self) -> str:
        """创建主题文件"""
        return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme">
    <a:themeElements>
        <a:clrScheme name="Office">
            <a:dk1><a:sysClr val="windowText"/></a:dk1>
            <a:lt1><a:sysClr val="window"/></a:lt1>
            <a:dk2><a:srgbClr val="1F497D"/></a:dk2>
            <a:lt2><a:srgbClr val="EEF1F8"/></a:lt2>
        </a:clrScheme>
        <a:fontScheme name="Office">
            <a:majorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
            <a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>
        </a:fontScheme>
        <a:fmtScheme name="Office">
            <a:fillStyleList>
                <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
                <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
                <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
            </a:fillStyleList>
        </a:fmtScheme>
    </a:themeElements>
</a:theme>'''

    def _get_element_text(self, elem: DocumentElement) -> str:
        """获取元素文本"""
        if elem.content:
            return elem.content
        return ''.join(self._get_element_text(child) for child in elem.children)

    def _escape_xml(self, text: str) -> str:
        """转义XML特殊字符"""
        if not text:
            return ''
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))

    def _pt_to_twips(self, pt: float) -> int:
        """将磅值转换为twips（1磅 = 20twips）"""
        return int(pt * 20)

    def _cm_to_twips(self, cm: float) -> int:
        """将厘米转换为twips（1厘米 = 567twips）"""
        return int(cm * 567)

    def add_image(self, image_data: bytes, extension: str = 'png') -> str:
        """添加图片并返回图片ID"""
        image_id = f'image{self.image_counter}.{extension}'
        self.image_counter += 1
        self.images.append((image_id, image_data))
        return image_id


# ============================================================================
# 便捷函数
# ============================================================================

def generate_docx(markdown_text: str,
                  output_path: Optional[str] = None,
                  config: Optional[ConversionConfig] = None) -> Tuple[bool, str]:
    """
    生成DOCX文档的便捷函数

    参数:
        markdown_text: Markdown文本内容
        output_path: 输出文件路径（可选）
        config: 转换配置（可选）

    返回:
        (success, message_or_path)
    """
    try:
        generator = DOCXGenerator(config)
        docx_data = generator.generate_from_markdown(markdown_text)

        if output_path:
            with open(output_path, 'wb') as f:
                f.write(docx_data)
            return True, output_path
        else:
            # 返回临时文件路径
            import tempfile
            import os
            temp_path = os.path.join(tempfile.gettempdir(), 'output.docx')
            with open(temp_path, 'wb') as f:
                f.write(docx_data)
            return True, temp_path

    except Exception as e:
        return False, str(e)


def markdown_to_docx(input_path: str,
                     output_path: Optional[str] = None,
                     config: Optional[ConversionConfig] = None) -> Tuple[bool, str]:
    """
    将Markdown文件转换为DOCX的便捷函数

    参数:
        input_path: 输入Markdown文件路径
        output_path: 输出DOCX文件路径（可选）
        config: 转换配置（可选）

    返回:
        (success, message_or_path)
    """
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            markdown_text = f.read()

        if not output_path:
            output_path = input_path.rsplit('.', 1)[0] + '.docx'

        return generate_docx(markdown_text, output_path, config)

    except Exception as e:
        return False, str(e)
