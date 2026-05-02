# -*- coding: utf-8 -*-
"""
Markdown转Word文档系统 - Markdown解析器
=======================================

支持：
- 标准Markdown解析
- GitHub Flavored Markdown (GFM)
- 数学公式 (LaTeX)
- 表格扩展
- 任务列表

作者：Hermes Desktop Team
版本：1.0.0
"""

import re
import uuid
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

from .models import (
    DocumentNode, DocumentElement, ElementType,
    ConversionConfig, ImageConfig, CodeConfig, LinkConfig
)


@dataclass
class ParseResult:
    """解析结果"""
    success: bool = False
    document: Optional[DocumentNode] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    statistics: Dict[str, int] = field(default_factory=dict)


class MarkdownParser:
    """Markdown解析器"""

    # 正则表达式定义
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$')
    CODE_BLOCK_PATTERN = re.compile(r'^```(\w*)\n([\s\S]*?)```', re.MULTILINE)
    INLINE_CODE_PATTERN = re.compile(r'`([^`]+)`')
    BOLD_PATTERN = re.compile(r'\*\*([^\*]+)\*\*|__([^_]+)__')
    ITALIC_PATTERN = re.compile(r'\*([^\*]+)\*|_([^_]+)_')
    STRIKETHROUGH_PATTERN = re.compile(r'~~([^~]+)~~')
    LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
    TABLE_PATTERN = re.compile(r'^\|(.+)\|\s*$')
    TABLE_SEPARATOR_PATTERN = re.compile(r'^[\s|:\-]+$')
    BLOCKQUOTE_PATTERN = re.compile(r'^>\s*(.*)$')
    UNORDERED_LIST_PATTERN = re.compile(r'^[\*\-\+]\s+(.+)$')
    ORDERED_LIST_PATTERN = re.compile(r'^\d+\.\s+(.+)$')
    TASK_LIST_PATTERN = re.compile(r'^[\*\-\+]\s+\[([ xX])\]\s+(.+)$')
    HORIZONTAL_RULE_PATTERN = re.compile(r'^[-*_]{3,}\s*$')
    MATH_INLINE_PATTERN = re.compile(r'\$([^$\n]+)\$')
    MATH_BLOCK_PATTERN = re.compile(r'\$\$([\s\S]+?)\$\$')

    def __init__(self, config: Optional[ConversionConfig] = None):
        self.config = config or ConversionConfig()
        self.current_line = 0
        self.lines: List[str] = []

    def parse(self, markdown_text: str) -> ParseResult:
        """解析Markdown文本"""
        result = ParseResult()
        self.lines = markdown_text.split('\n')
        self.current_line = 0

        try:
            document = DocumentNode()
            elements = self._parse_block_elements()

            for elem in elements:
                document.add_element(elem)

            # 提取文档标题
            document.title = self._extract_title(elements)
            document.created_at = None

            result.success = True
            result.document = document
            result.statistics = self._calculate_statistics(elements)

        except Exception as e:
            result.errors.append(f"解析错误: {str(e)}")

        return result

    def parse_file(self, file_path: str) -> ParseResult:
        """解析Markdown文件"""
        result = ParseResult()

        try:
            with open(file_path, 'r', encoding=self.config.source_encoding) as f:
                content = f.read()

            result = self.parse(content)
            if result.document:
                result.document.metadata['source_file'] = file_path

        except Exception as e:
            result.errors.append(f"文件读取错误: {str(e)}")

        return result

    def _parse_block_elements(self) -> List[DocumentElement]:
        """解析块级元素"""
        elements: List[DocumentElement] = []
        i = 0

        while i < len(self.lines):
            line = self.lines[i]

            # 跳过空行
            if not line.strip():
                i += 1
                continue

            # 标题
            heading_match = self.HEADING_PATTERN.match(line)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2).strip()
                elem = self._create_heading_element(level, text)
                elements.append(elem)
                i += 1
                continue

            # 代码块
            if line.startswith('```'):
                code_elem, new_i = self._parse_code_block(i)
                elements.append(code_elem)
                i = new_i
                continue

            # 表格
            if line.startswith('|'):
                table_elem, new_i = self._parse_table(i)
                elements.append(table_elem)
                i = new_i
                continue

            # 引用块
            if line.startswith('>'):
                quote_elem, new_i = self._parse_blockquote(i)
                elements.append(quote_elem)
                i = new_i
                continue

            # 任务列表
            task_match = self.TASK_LIST_PATTERN.match(line)
            if task_match:
                checked = task_match.group(1).lower() == 'x'
                text = task_match.group(2)
                elem = self._create_task_item(text, checked)
                elements.append(elem)
                i += 1
                continue

            # 无序列表
            if self.UNORDERED_LIST_PATTERN.match(line):
                list_elem, new_i = self._parse_unordered_list(i)
                elements.append(list_elem)
                i = new_i
                continue

            # 有序列表
            if self.ORDERED_LIST_PATTERN.match(line):
                list_elem, new_i = self._parse_ordered_list(i)
                elements.append(list_elem)
                i = new_i
                continue

            # 水平线
            if self.HORIZONTAL_RULE_PATTERN.match(line):
                elem = DocumentElement(element_type=ElementType.HORIZONTAL_RULE)
                elements.append(elem)
                i += 1
                continue

            # 数学公式块
            math_match = self.MATH_BLOCK_PATTERN.search(line)
            if math_match:
                elem = DocumentElement(
                    element_type=ElementType.MATH,
                    content=math_match.group(1).strip()
                )
                elements.append(elem)
                i += 1
                continue

            # 普通段落
            paragraph_lines = [line]
            while i + 1 < len(self.lines) and self.lines[i + 1].strip():
                if self.HEADING_PATTERN.match(self.lines[i + 1]):
                    break
                if self.lines[i + 1].startswith('```'):
                    break
                if self.lines[i + 1].startswith('>'):
                    break
                if self.lines[i + 1].startswith('|'):
                    break
                paragraph_lines.append(self.lines[i + 1])
                i += 1

            text = ' '.join(paragraph_lines)
            if text.strip():
                elem = self._parse_inline_elements(text, ElementType.PARAGRAPH)
                elements.append(elem)

            i += 1

        return elements

    def _parse_code_block(self, start_i: int) -> Tuple[DocumentElement, int]:
        """解析代码块"""
        first_line = self.lines[start_i]
        lang_match = re.match(r'^```(\w*)', first_line)
        language = lang_match.group(1) if lang_match else ""

        code_lines = []
        i = start_i + 1

        while i < len(self.lines):
            if self.lines[i].rstrip() == '```' or self.lines[i].startswith('```'):
                break
            code_lines.append(self.lines[i])
            i += 1

        code = '\n'.join(code_lines)
        elem = DocumentElement(
            element_type=ElementType.CODE_BLOCK,
            content=code,
            language=language,
        )

        return elem, i + 1

    def _parse_table(self, start_i: int) -> Tuple[DocumentElement, int]:
        """解析表格"""
        rows = []
        i = start_i

        while i < len(self.lines) and self.lines[i].startswith('|'):
            # 跳过分隔行
            if self.TABLE_SEPARATOR_PATTERN.match(self.lines[i]):
                i += 1
                continue

            # 解析行
            row_content = self.lines[i].strip('|')
            cells = [cell.strip() for cell in row_content.split('|')]
            rows.append(cells)
            i += 1

        if len(rows) < 2:
            # 至少需要表头和一行数据
            return DocumentElement(
                element_type=ElementType.PARAGRAPH,
                content=self.lines[start_i]
            ), start_i + 1

        # 创建表格元素
        elem = DocumentElement(
            element_type=ElementType.TABLE,
            row_count=len(rows),
            col_count=len(rows[0]) if rows else 0,
        )

        # 添加表头行
        for cell in rows[0]:
            header_cell = DocumentElement(
                element_type=ElementType.TEXT,
                content=cell,
                bold=True,
            )
            elem.add_child(header_cell)

        # 添加数据行
        for row in rows[1:]:
            for cell in row:
                data_cell = DocumentElement(
                    element_type=ElementType.TEXT,
                    content=cell,
                )
                elem.add_child(data_cell)

        return elem, i

    def _parse_blockquote(self, start_i: int) -> Tuple[DocumentElement, int]:
        """解析引用块"""
        quote_lines = []
        i = start_i

        while i < len(self.lines) and self.lines[i].startswith('>'):
            content = self.lines[i].lstrip('>').strip()
            if content:
                quote_lines.append(content)
            i += 1

        quote_content = '\n'.join(quote_lines)
        quote_children = self._parse_inline_elements(quote_content, ElementType.BLOCKQUOTE)

        elem = DocumentElement(
            element_type=ElementType.BLOCKQUOTE,
        )
        for child in quote_children.children if hasattr(quote_children, 'children') else [quote_children]:
            elem.add_child(child)

        return elem, i

    def _parse_unordered_list(self, start_i: int) -> Tuple[DocumentElement, int]:
        """解析无序列表"""
        list_elem = DocumentElement(element_type=ElementType.UNORDERED_LIST)
        i = start_i

        while i < len(self.lines):
            match = self.UNORDERED_LIST_PATTERN.match(self.lines[i])
            if not match:
                # 检查任务列表
                task_match = self.TASK_LIST_PATTERN.match(self.lines[i])
                if task_match:
                    checked = task_match.group(1).lower() == 'x'
                    text = task_match.group(2)
                    item = self._create_task_item(text, checked)
                    list_elem.add_child(item)
                    i += 1
                    continue
                break

            text = match.group(1)
            item = self._create_list_item(text, ElementType.LIST_ITEM)
            list_elem.add_child(item)
            i += 1

        return list_elem, i

    def _parse_ordered_list(self, start_i: int) -> Tuple[DocumentElement, int]:
        """解析有序列表"""
        list_elem = DocumentElement(element_type=ElementType.ORDERED_LIST)
        i = start_i

        while i < len(self.lines):
            match = self.ORDERED_LIST_PATTERN.match(self.lines[i])
            if not match:
                break

            text = match.group(1)
            item = self._create_list_item(text, ElementType.LIST_ITEM)
            list_elem.add_child(item)
            i += 1

        return list_elem, i

    def _parse_inline_elements(self, text: str, base_type: ElementType) -> DocumentElement:
        """解析行内元素"""
        # 处理数学公式
        text = self.MATH_BLOCK_PATTERN.sub(lambda m: self._create_math_element(m), text)

        # 处理图片（先处理，避免图片内的文字被其他模式处理）
        def replace_image(m):
            alt_text = m.group(1)
            url = m.group(2)
            return f'[{alt_text}]({url})'

        # 处理链接
        def replace_link(m):
            link_text = m.group(1)
            url = m.group(2)
            elem = DocumentElement(
                element_type=ElementType.LINK,
                content=link_text,
                url=url,
            )
            return f'[[LINK:{url}]]{link_text}[[/LINK]]'

        # 临时标记链接
        text_with_links = self.IMAGE_PATTERN.sub(replace_image, text)
        text_with_links = self.LINK_PATTERN.sub(replace_link, text_with_links)

        # 创建段落元素
        elem = DocumentElement(element_type=base_type)

        # 处理剩余的标记
        parts = re.split(r'(\[\[LINK:[^\]]+\]\]|\[\[/LINK\]\])', text_with_links)

        for part in parts:
            if part.startswith('[[LINK:'):
                url = re.search(r'\[\[LINK:([^\]]+)\]\]', part)
                if url:
                    continue  # 链接标签由后面的文本处理
            elif part == '[[/LINK]]':
                continue

            # 处理粗体
            bold_match = self.BOLD_PATTERN.search(part)
            if bold_match:
                for match in self.BOLD_PATTERN.finditer(part):
                    bold_text = match.group(1) or match.group(2)
                    child = DocumentElement(
                        element_type=ElementType.BOLD,
                        content=bold_text,
                        bold=True,
                    )
                    elem.add_child(child)

            # 处理斜体
            italic_match = self.ITALIC_PATTERN.search(part)
            if italic_match:
                for match in self.ITALIC_PATTERN.finditer(part):
                    italic_text = match.group(1) or match.group(2)
                    child = DocumentElement(
                        element_type=ElementType.ITALIC,
                        content=italic_text,
                        italic=True,
                    )
                    elem.add_child(child)

            # 处理删除线
            for match in self.STRIKETHROUGH_PATTERN.finditer(part):
                text = match.group(1)
                child = DocumentElement(
                    element_type=ElementType.STRIKETHROUGH,
                    content=text,
                    strikethrough=True,
                )
                elem.add_child(child)

            # 处理行内代码
            for match in self.INLINE_CODE_PATTERN.finditer(part):
                code_text = match.group(1)
                child = DocumentElement(
                    element_type=ElementType.CODE,
                    content=code_text,
                    style_name='code_inline',
                )
                elem.add_child(child)

            # 处理纯文本
            clean_text = self.INLINE_CODE_PATTERN.sub('', part)
            clean_text = self.BOLD_PATTERN.sub(r'\1\2', clean_text)
            clean_text = self.ITALIC_PATTERN.sub(r'\1\2', clean_text)
            clean_text = self.STRIKETHROUGH_PATTERN.sub(r'\1', clean_text)

            if clean_text and clean_text.strip():
                child = DocumentElement(
                    element_type=ElementType.TEXT,
                    content=clean_text,
                )
                elem.add_child(child)

        # 如果没有子元素，使用content
        if not elem.children and text:
            elem.content = text

        return elem

    def _create_heading_element(self, level: int, text: str) -> DocumentElement:
        """创建标题元素"""
        element_types = {
            1: ElementType.HEADING_1,
            2: ElementType.HEADING_2,
            3: ElementType.HEADING_3,
            4: ElementType.HEADING_4,
            5: ElementType.HEADING_5,
            6: ElementType.HEADING_6,
        }

        elem = DocumentElement(
            element_type=element_types.get(level, ElementType.HEADING_1),
            content=text,
            level=level,
            bold=True,
        )

        # 处理标题内的格式
        if any(marker in text for marker in ['**', '*', '`', '[']):
            parsed = self._parse_inline_elements(text, elem.element_type)
            elem.children = parsed.children

        return elem

    def _create_list_item(self, text: str, item_type: ElementType) -> DocumentElement:
        """创建列表项元素"""
        elem = DocumentElement(element_type=item_type, content=text)

        if any(marker in text for marker in ['**', '*', '`', '[']):
            parsed = self._parse_inline_elements(text, item_type)
            elem.children = parsed.children

        return elem

    def _create_task_item(self, text: str, checked: bool) -> DocumentElement:
        """创建任务项元素"""
        elem = DocumentElement(
            element_type=ElementType.TASK_ITEM,
            content=text,
            checked=checked,
        )

        if any(marker in text for marker in ['**', '*', '`', '[']):
            parsed = self._parse_inline_elements(text, ElementType.TASK_ITEM)
            elem.children = parsed.children

        return elem

    def _create_math_element(self, match) -> str:
        """创建数学公式元素（标记）"""
        return f'[[MATH:{match.group(1)}]]'

    def _extract_title(self, elements: List[DocumentElement]) -> str:
        """提取文档标题"""
        for elem in elements:
            if elem.element_type == ElementType.HEADING_1:
                return elem.content
        return ""

    def _calculate_statistics(self, elements: List[DocumentElement]) -> Dict[str, int]:
        """计算统计信息"""
        stats = {
            'paragraph_count': 0,
            'heading_count': 0,
            'code_block_count': 0,
            'table_count': 0,
            'list_count': 0,
            'image_count': 0,
            'link_count': 0,
            'blockquote_count': 0,
            'task_count': 0,
            'word_count': 0,
        }

        for elem in elements:
            self._count_element(elem, stats)

        return stats

    def _count_element(self, elem: DocumentElement, stats: Dict[str, int]):
        """递归统计元素"""
        if elem.element_type == ElementType.PARAGRAPH:
            stats['paragraph_count'] += 1
        elif elem.element_type in [ElementType.HEADING_1, ElementType.HEADING_2,
                                     ElementType.HEADING_3, ElementType.HEADING_4,
                                     ElementType.HEADING_5, ElementType.HEADING_6]:
            stats['heading_count'] += 1
        elif elem.element_type == ElementType.CODE_BLOCK:
            stats['code_block_count'] += 1
        elif elem.element_type == ElementType.TABLE:
            stats['table_count'] += 1
        elif elem.element_type in [ElementType.UNORDERED_LIST, ElementType.ORDERED_LIST]:
            stats['list_count'] += 1
        elif elem.element_type == ElementType.BLOCKQUOTE:
            stats['blockquote_count'] += 1
        elif elem.element_type == ElementType.TASK_ITEM:
            stats['task_count'] += 1

        # 统计图片和链接
        if '![' in elem.content or '[' in elem.content:
            stats['image_count'] += len(re.findall(r'!\[', elem.content))
            stats['link_count'] += len(re.findall(r'\]\(', elem.content)) - stats['image_count']

        # 统计字数
        text = elem.get_text() if hasattr(elem, 'get_text') else elem.content
        stats['word_count'] += len(text)

        # 递归处理子元素
        for child in elem.children:
            self._count_element(child, stats)


# ============================================================================
# 便捷函数
# ============================================================================

def parse_markdown(markdown_text: str, config: Optional[ConversionConfig] = None) -> ParseResult:
    """解析Markdown文本"""
    parser = MarkdownParser(config)
    return parser.parse(markdown_text)


def parse_markdown_file(file_path: str, config: Optional[ConversionConfig] = None) -> ParseResult:
    """解析Markdown文件"""
    parser = MarkdownParser(config)
    return parser.parse_file(file_path)
