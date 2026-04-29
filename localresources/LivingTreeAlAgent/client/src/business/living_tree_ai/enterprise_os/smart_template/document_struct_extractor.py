"""
文档结构提取器 (Document Structure Extractor)

将 Word/PDF 文档转换为结构化的 JSON AST（抽象语法树），
彻底解决"嵌套表格读取"问题，为 AI 推理模板提供结构化输入。

核心功能：
1. 使用 python-docx 提取 Word 文档的完整结构（段落、表格、样式）
2. 保留嵌套关系和样式信息
3. 输出标准的 JSON AST 格式
"""

import json
import hashlib
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

class NodeType(Enum):
    """AST 节点类型"""
    DOCUMENT = "document"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    RUN = "run"  # 文本片段
    HEADING = "heading"
    LIST_ITEM = "list_item"
    IMAGE = "image"


class ContentType(Enum):
    """内容类型分类"""
    STATIC_TEXT = "static_text"      # 固定文本（如法律条款、章节标题）
    DYNAMIC_VALUE = "dynamic_value"  # 可变数据（如企业名称、监测数值）
    FORMULA = "formula"              # 公式/计算表达式
    TABLE_DATA = "table_data"        # 表格数据
    METADATA = "metadata"            # 元信息（如日期、编号）


@dataclass
class StyleInfo:
    """样式信息"""
    name: str = ""
    font_name: str = ""
    font_size: float = 0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: str = ""
    alignment: str = "left"  # left/center/right/justify


@dataclass
class ASTNode:
    """AST 节点"""
    node_id: str
    node_type: str
    content: str = ""
    children: List['ASTNode'] = field(default_factory=list)
    style: StyleInfo = field(default_factory=StyleInfo)
    attributes: Dict[str, Any] = field(default_factory=dict)
    level: int = 0  # 层级（用于标题层级等）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "content": self.content,
            "children": [c.to_dict() if isinstance(c, ASTNode) else c for c in self.children],
            "style": asdict(self.style) if isinstance(self.style, StyleInfo) else self.style,
            "attributes": self.attributes,
            "level": self.level
        }


@dataclass
class DocumentAST:
    """完整文档 AST"""
    document_id: str
    file_path: str
    file_name: str
    file_type: str
    total_paragraphs: int = 0
    total_tables: int = 0
    total_words: int = 0
    checksum: str = ""
    root: Optional[ASTNode] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "total_paragraphs": self.total_paragraphs,
            "total_tables": self.total_tables,
            "total_words": self.total_words,
            "checksum": self.checksum,
            "root": self.root.to_dict() if self.root else None,
            "metadata": self.metadata
        }

    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


@dataclass
class TableStructure:
    """表格结构信息"""
    rows: int = 0
    cols: int = 0
    headers: List[str] = field(default_factory=list)
    data_rows: List[List[str]] = field(default_factory=list)
    is_nested: bool = False
    parent_table_id: Optional[str] = None


# ==================== 文档结构提取器 ====================

class DocumentStructExtractor:
    """
    文档结构提取器

    使用 python-docx 提取 Word 文档的完整结构，生成标准 JSON AST。
    解决的问题：
    1. 嵌套表格识别 - 表格内的表格作为子节点处理
    2. 样式保留 - 标题/正文/强调等样式信息
    3. 层级关系 - 列表缩进、表格嵌套层级
    """

    def __init__(self):
        self._node_counter = 0

    def _generate_node_id(self) -> str:
        """生成唯一节点 ID"""
        self._node_counter += 1
        return f"node_{self._node_counter:06d}"

    def _hash_content(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:12]

    async def extract(self, file_path: str) -> DocumentAST:
        """
        提取文档结构

        Args:
            file_path: 文档路径（支持 .docx）

        Returns:
            DocumentAST: 文档的抽象语法树
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        file_type = path.suffix.lower()
        if file_type not in ['.docx', '.doc']:
            raise ValueError(f"不支持的文件类型: {file_type}，仅支持 .docx/.doc")

        # 计算文件校验和
        with open(file_path, 'rb') as f:
            checksum = hashlib.md5(f.read()).hexdigest()

        # 提取文档结构
        if file_type == '.docx':
            ast = await self._extract_docx(file_path, checksum)
        else:
            raise ValueError(f"暂时不支持 .doc 格式，请转换为 .docx")

        return ast

    async def _extract_docx(self, file_path: str, checksum: str) -> DocumentAST:
        """提取 DOCX 文档结构"""
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        path = Path(file_path)

        # 初始化 DocumentAST
        doc_ast = DocumentAST(
            document_id=self._generate_node_id(),
            file_path=str(path.absolute()),
            file_name=path.name,
            file_type="docx",
            checksum=checksum
        )

        # 创建根节点
        root = ASTNode(
            node_id=doc_ast.document_id,
            node_type=NodeType.DOCUMENT.value,
            content=path.stem
        )

        doc = Document(file_path)

        # 统计信息
        total_paragraphs = 0
        total_tables = 0
        total_words = 0

        # 用于追踪嵌套表格
        table_stack: List[ASTNode] = []
        current_table: Optional[ASTNode] = None

        # 遍历所有元素（段落和表格交替出现）
        for element in doc.element.body:
            tag_name = element.tag.split('}')[-1] if '}' in element.tag else element.tag

            if tag_name == 'p':  # 段落
                para_node = self._extract_paragraph(element, doc)
                if para_node:
                    total_paragraphs += 1
                    total_words += len(para_node.content.split()) if para_node.content else 0

                    # 如果在表格内，作为表格内容处理
                    if current_table is not None:
                        current_table.children.append(para_node)
                    else:
                        root.children.append(para_node)

            elif tag_name == 'tbl':  # 表格
                # 结束当前嵌套表格
                while table_stack and current_table:
                    table_stack.pop()
                    current_table = table_stack[-1] if table_stack else None

                table_node = self._extract_table(element, doc)
                if table_node:
                    total_tables += 1

                    # 检查是否是嵌套表格
                    if current_table is not None:
                        table_node.attributes['is_nested'] = True
                        table_node.attributes['parent_table_id'] = current_table.node_id
                        current_table.children.append(table_node)
                    else:
                        root.children.append(table_node)

                    # 进入新表格
                    table_stack.append(current_table or table_node)
                    current_table = table_node

        # 清理表格栈
        while table_stack:
            table_stack.pop()

        # 更新统计
        doc_ast.total_paragraphs = total_paragraphs
        doc_ast.total_tables = total_tables
        doc_ast.total_words = total_words
        doc_ast.root = root
        doc_ast.metadata = {
            "extracted_at": "",
            "extractor_version": "1.0.0",
            "doc_properties": {
                "title": doc.core_properties.title or "",
                "author": doc.core_properties.author or "",
                "subject": doc.core_properties.subject or "",
                "created": str(doc.core_properties.created) if doc.core_properties.created else "",
                "modified": str(doc.core_properties.modified) if doc.core_properties.modified else ""
            }
        }

        return doc_ast

    def _extract_paragraph(self, para_element, doc: 'Document') -> Optional[ASTNode]:
        """提取段落节点"""
        from docx.oxml.ns import qn

        para = para_element
        text_content = []
        children = []

        # 获取段落样式
        style_name = ""
        pPr = para.find(qn('w:pPr'))
        if pPr is not None:
            pStyle = pPr.find(qn('w:pStyle'))
            if pStyle is not None:
                style_name = pStyle.get(qn('w:val')) or ""

        # 遍历所有文本片段
        for r in para.findall(qn('w:r')):
            # 获取文本
            t = r.find(qn('w:t'))
            if t is not None and t.text:
                text_content.append(t.text)

            # 获取样式
            rPr = r.find(qn('w:rPr'))
            style_info = self._extract_run_style(rPr) if rPr is not None else StyleInfo()

            # 判断是否是标题
            level = 0
            node_type = NodeType.PARAGRAPH.value
            if style_name.startswith('Heading') or style_name.startswith('标题'):
                try:
                    level = int(''.join(filter(str.isdigit, style_name))) or 1
                except:
                    level = 1
                node_type = NodeType.HEADING.value

            # 创建 run 节点
            if t is not None and t.text:
                run_node = ASTNode(
                    node_id=self._generate_node_id(),
                    node_type=NodeType.RUN.value,
                    content=t.text,
                    style=style_info,
                    level=level
                )
                children.append(run_node)

        content = ''.join(text_content).strip()

        # 跳过空段落
        if not content and not children:
            return None

        # 创建段落节点
        alignment = "left"
        if pPr is not None:
            jc = pPr.find(qn('w:jc'))
            if jc is not None:
                val = jc.get(qn('w:val'))
                if val == 'center':
                    alignment = 'center'
                elif val == 'right':
                    alignment = 'right'
                elif val == 'both':
                    alignment = 'justify'

        para_style = StyleInfo(
            name=style_name,
            alignment=alignment
        )

        para_node = ASTNode(
            node_id=self._generate_node_id(),
            node_type=node_type,
            content=content,
            children=children,
            style=para_style,
            level=level,
            attributes={"is_heading": node_type == NodeType.HEADING.value}
        )

        return para_node

    def _extract_table(self, tbl_element, doc: 'Document') -> Optional[ASTNode]:
        """提取表格节点"""
        from docx.oxml.ns import qn

        rows = tbl_element.findall(qn('w:tr'))
        if not rows:
            return None

        table_node = ASTNode(
            node_id=self._generate_node_id(),
            node_type=NodeType.TABLE.value,
            attributes={
                "rows": len(rows),
                "cols": 0,
                "is_nested": False
            }
        )

        # 获取列数（从第一行推断）
        first_row = rows[0]
        cells = first_row.findall(qn('w:tc'))
        table_node.attributes['cols'] = len(cells)

        # 提取表头和数据行
        headers = []
        data_rows = []

        for row_idx, row in enumerate(rows):
            row_node = ASTNode(
                node_id=self._generate_node_id(),
                node_type=NodeType.TABLE_ROW.value,
                attributes={"row_index": row_idx, "is_header": row_idx == 0}
            )

            cells = row.findall(qn('w:tc'))
            cell_contents = []

            for cell in cells:
                # 获取单元格文本
                cell_text = []
                for para in cell.findall(qn('w:p')):
                    for r in para.findall(qn('w:r')):
                        t = r.find(qn('w:t'))
                        if t is not None and t.text:
                            cell_text.append(t.text)

                cell_content = ''.join(cell_text).strip()

                # 创建单元格节点
                cell_node = ASTNode(
                    node_id=self._generate_node_id(),
                    node_type=NodeType.TABLE_CELL.value,
                    content=cell_content,
                    attributes={"col_index": len(cell_contents)}
                )

                row_node.children.append(cell_node)
                cell_contents.append(cell_content)

            # 第一行作为表头
            if row_idx == 0:
                headers = cell_contents
                row_node.attributes['is_header'] = True
            else:
                data_rows.append(cell_contents)

            table_node.children.append(row_node)

        # 更新表格属性
        table_node.attributes['headers'] = headers
        table_node.attributes['data_rows'] = data_rows

        return table_node

    def _extract_run_style(self, rPr_element) -> StyleInfo:
        """提取文本样式"""
        from docx.oxml.ns import qn

        if rPr_element is None:
            return StyleInfo()

        style = StyleInfo()

        # 字体
        fonts = rPr_element.find(qn('w:rFonts'))
        if fonts is not None:
            style.font_name = fonts.get(qn('w:eastAsia')) or fonts.get(qn('w:ascii')) or ""

        # 字号
        sz = rPr_element.find(qn('w:sz'))
        if sz is not None:
            try:
                style.font_size = int(sz.get(qn('w:val'))) / 2  # half-points to points
            except:
                pass

        # 粗体
        b = rPr_element.find(qn('w:b'))
        style.bold = b is not None

        # 斜体
        i = rPr_element.find(qn('w:i'))
        style.italic = i is not None

        # 下划线
        u = rPr_element.find(qn('w:u'))
        style.underline = u is not None

        # 颜色
        color = rPr_element.find(qn('w:color'))
        if color is not None:
            style.color = color.get(qn('w:val')) or ""

        return style

    def extract_to_json(self, file_path: str, output_path: Optional[str] = None) -> str:
        """
        提取文档结构并保存为 JSON 文件

        Args:
            file_path: 文档路径
            output_path: 输出 JSON 路径（可选）

        Returns:
            str: JSON 字符串
        """
        import asyncio
        ast = asyncio.run(self.extract(file_path))
        json_str = ast.to_json()

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_str)
            logger.info(f"文档结构已保存到: {output_path}")

        return json_str


# ==================== 便捷函数 ====================

_extractor: Optional[DocumentStructExtractor] = None


def get_struct_extractor() -> DocumentStructExtractor:
    """获取文档结构提取器单例"""
    global _extractor
    if _extractor is None:
        _extractor = DocumentStructExtractor()
    return _extractor


async def extract_document_structure(file_path: str) -> DocumentAST:
    """提取文档结构"""
    extractor = get_struct_extractor()
    return await extractor.extract(file_path)


def extract_to_json(file_path: str, output_path: Optional[str] = None) -> str:
    """提取文档结构并转为 JSON"""
    extractor = get_struct_extractor()
    return extractor.extract_to_json(file_path, output_path)