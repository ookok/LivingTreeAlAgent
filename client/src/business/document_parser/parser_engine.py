"""
文档解析引擎 - 核心实现

集成Unstructured.io实现多格式文档解析，支持表格提取和实体关系抽取。
"""
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List

from .models import (
    DocumentType,
    SectionType,
    ParsedDocument,
    DocumentSection,
    TableData,
    TableCell,
    EntityRelation,
)

logger = logging.getLogger(__name__)

try:
    from unstructured.partition.pdf import partition_pdf
    from unstructured.partition.docx import partition_docx
    from unstructured.partition.html import partition_html
    from unstructured.partition.text import partition_text
    from unstructured.chunking.title import chunk_by_title
    from unstructured.staging.base import elements_to_json
    HAS_UNSTRUCTURED = True
except ImportError:
    HAS_UNSTRUCTURED = False
    logger.warning("Unstructured.io not installed, falling back to basic parsing")


class DocumentParser:
    """文档解析器基类"""
    
    def __init__(self, document_type: DocumentType):
        self.document_type = document_type
    
    def parse(self, file_path: str) -> ParsedDocument:
        """解析文档"""
        raise NotImplementedError
    
    def _generate_id(self) -> str:
        """生成唯一ID"""
        return f"section_{uuid.uuid4().hex[:8]}"


class UnstructuredDocumentParser(DocumentParser):
    """基于Unstructured.io的文档解析器"""
    
    def __init__(self, document_type: DocumentType):
        super().__init__(document_type)
        if not HAS_UNSTRUCTURED:
            logger.warning("Unstructured.io not available, using fallback parser")
    
    def parse(self, file_path: str) -> ParsedDocument:
        """解析文档"""
        if not HAS_UNSTRUCTURED:
            return self._fallback_parse(file_path)
        
        file_path = Path(file_path)
        
        try:
            # 根据文件类型选择解析器
            elements = self._partition_file(file_path)
            
            # 转换为JSON格式以便处理
            elements_json = json.loads(elements_to_json(elements))
            
            # 构建解析文档对象
            return self._build_parsed_document(file_path, elements_json)
        
        except Exception as e:
            logger.error(f"Failed to parse document {file_path}: {e}")
            return self._fallback_parse(file_path)
    
    def _partition_file(self, file_path: Path):
        """根据文件类型调用对应的partition方法"""
        if self.document_type == DocumentType.PDF:
            return partition_pdf(
                filename=str(file_path),
                strategy="fast",
                extract_images_in_pdf=False,
            )
        elif self.document_type == DocumentType.WORD:
            return partition_docx(filename=str(file_path))
        elif self.document_type == DocumentType.HTML:
            return partition_html(filename=str(file_path))
        elif self.document_type == DocumentType.TXT:
            return partition_text(filename=str(file_path))
        else:
            return partition_text(filename=str(file_path))
    
    def _build_parsed_document(self, file_path: Path, elements_json: List[Dict]) -> ParsedDocument:
        """构建解析文档对象"""
        document = ParsedDocument(
            document_id=f"doc_{uuid.uuid4().hex[:12]}",
            file_name=file_path.name,
            document_type=self.document_type,
            sections=[],
            tables=[],
            entities=[],
            relations=[],
        )
        
        sections = []
        tables = []
        entities = set()
        relations = []
        
        current_section = None
        section_stack = []
        
        for element in elements_json:
            element_type = element.get("type", "")
            text = element.get("text", "").strip()
            
            if not text:
                continue
            
            # 处理标题
            if element_type.startswith("Title"):
                level = self._get_heading_level(element_type)
                # 弹出栈中高于当前级别的章节
                while section_stack and section_stack[-1].level >= level:
                    section_stack.pop()
                
                new_section = DocumentSection(
                    id=self._generate_id(),
                    type=self._map_section_type(element_type),
                    content=text,
                    level=level,
                    children=[],
                )
                
                if section_stack:
                    section_stack[-1].children.append(new_section)
                else:
                    sections.append(new_section)
                
                section_stack.append(new_section)
                current_section = new_section
                
                # 提取标题作为实体
                entities.add(text)
            
            # 处理表格
            elif element_type == "Table":
                table_data = self._parse_table(element)
                tables.append(table_data)
                
                # 如果有当前章节，关联表格
                if current_section:
                    current_section.table_data = table_data
                
                # 从表格中提取实体和关系
                self._extract_entities_from_table(table_data, entities, relations)
            
            # 处理段落
            elif element_type == "NarrativeText":
                if current_section:
                    # 如果当前章节已有内容，追加
                    if current_section.content and current_section.type != SectionType.TITLE:
                        current_section.content += "\n" + text
                    elif current_section.type == SectionType.TITLE:
                        # 创建子段落
                        paragraph = DocumentSection(
                            id=self._generate_id(),
                            type=SectionType.PARAGRAPH,
                            content=text,
                            level=current_section.level + 1,
                        )
                        current_section.children.append(paragraph)
            
            # 处理列表
            elif element_type == "ListItem":
                if current_section:
                    list_section = DocumentSection(
                        id=self._generate_id(),
                        type=SectionType.LIST,
                        content=text,
                        level=current_section.level + 1,
                    )
                    current_section.children.append(list_section)
        
        document.sections = sections
        document.tables = tables
        document.entities = list(entities)
        document.relations = relations
        
        # 设置文档标题（第一个标题）
        if sections:
            document.title = sections[0].content
        
        return document
    
    def _parse_table(self, element: Dict) -> TableData:
        """解析表格元素"""
        table_data = TableData()
        
        # 尝试从metadata中获取表格内容
        metadata = element.get("metadata", {})
        text_as_html = metadata.get("text_as_html", "")
        
        # 简单的HTML表格解析
        if text_as_html:
            import re
            # 提取表格行
            row_pattern = r"<tr[^>]*>(.*?)</tr>"
            cell_pattern = r"<t[dh][^>]*>(.*?)</t[dh]>"
            
            rows = re.findall(row_pattern, text_as_html, re.DOTALL)
            for i, row in enumerate(rows):
                cells = re.findall(cell_pattern, row, re.DOTALL)
                # 清理HTML标签
                clean_cells = [self._clean_html(cell) for cell in cells]
                
                if i == 0:
                    table_data.headers = clean_cells
                else:
                    table_data.rows.append([
                        TableCell(content=cell, is_header=False)
                        for cell in clean_cells
                    ])
        
        # 如果HTML解析失败，尝试从text中提取
        if not table_data.rows:
            text = element.get("text", "")
            lines = text.split("\n")
            for line in lines:
                if line.strip():
                    cells = line.split("|")
                    table_data.rows.append([
                        TableCell(content=cell.strip(), is_header=False)
                        for cell in cells if cell.strip()
                    ])
        
        return table_data
    
    def _clean_html(self, html_text: str) -> str:
        """清理HTML标签"""
        import re
        text = re.sub(r"<[^>]+>", "", html_text)
        text = text.replace("&nbsp;", " ").strip()
        return text
    
    def _get_heading_level(self, element_type: str) -> int:
        """获取标题级别"""
        if element_type == "Title":
            return 0
        match = element_type.replace("Heading", "")
        if match.isdigit():
            return int(match)
        return 1
    
    def _map_section_type(self, element_type: str) -> SectionType:
        """映射元素类型到SectionType"""
        if element_type == "Title":
            return SectionType.TITLE
        elif element_type == "Heading1":
            return SectionType.HEADING_1
        elif element_type == "Heading2":
            return SectionType.HEADING_2
        elif element_type == "Heading3":
            return SectionType.HEADING_3
        elif element_type == "Heading4":
            return SectionType.HEADING_4
        elif element_type == "NarrativeText":
            return SectionType.PARAGRAPH
        elif element_type == "Table":
            return SectionType.TABLE
        elif element_type == "ListItem":
            return SectionType.LIST
        else:
            return SectionType.PARAGRAPH
    
    def _extract_entities_from_table(self, table: TableData, entities: set, relations: list):
        """从表格中提取实体和关系"""
        # 简单的实体提取：表头和第一列作为实体
        if table.headers:
            for header in table.headers:
                entities.add(header.strip())
        
        for row in table.rows:
            if row:
                # 第一列作为实体
                entities.add(row[0].content.strip())
                
                # 如果有表头，建立关系
                if table.headers and len(table.headers) > 1:
                    entity_name = row[0].content.strip()
                    for i, cell in enumerate(row[1:], 1):
                        if i < len(table.headers):
                            relation_type = table.headers[i].strip()
                            target_entity = cell.content.strip()
                            if entity_name and target_entity and relation_type:
                                relations.append(EntityRelation(
                                    source_entity=entity_name,
                                    relation_type=relation_type,
                                    target_entity=target_entity,
                                    confidence=0.8
                                ))
    
    def _fallback_parse(self, file_path: str) -> ParsedDocument:
        """备用解析器（当unstructured不可用时）"""
        file_path = Path(file_path)
        
        document = ParsedDocument(
            document_id=f"doc_{uuid.uuid4().hex[:12]}",
            file_name=file_path.name,
            document_type=self.document_type,
        )
        
        try:
            # 简单文本读取
            if file_path.suffix.lower() in [".txt", ".md"]:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                sections = []
                lines = content.split("\n")
                current_content = []
                
                for line in lines:
                    if line.startswith("#"):
                        # 标题
                        if current_content:
                            sections.append(DocumentSection(
                                id=self._generate_id(),
                                type=SectionType.PARAGRAPH,
                                content="\n".join(current_content),
                                level=1,
                            ))
                            current_content = []
                        
                        level = line.count("#")
                        sections.append(DocumentSection(
                            id=self._generate_id(),
                            type=self._map_heading_level(level),
                            content=line.lstrip("# ").strip(),
                            level=level,
                        ))
                    else:
                        current_content.append(line)
                
                if current_content:
                    sections.append(DocumentSection(
                        id=self._generate_id(),
                        type=SectionType.PARAGRAPH,
                        content="\n".join(current_content),
                        level=1,
                    ))
                
                document.sections = sections
                if sections:
                    document.title = sections[0].content
            
        except Exception as e:
            logger.error(f"Fallback parsing failed: {e}")
        
        return document
    
    def _map_heading_level(self, level: int) -> SectionType:
        """映射Markdown标题级别"""
        mapping = {
            1: SectionType.HEADING_1,
            2: SectionType.HEADING_2,
            3: SectionType.HEADING_3,
            4: SectionType.HEADING_4,
        }
        return mapping.get(level, SectionType.HEADING_1)


class DocumentParserFactory:
    """文档解析器工厂"""
    
    @staticmethod
    def create_parser(file_path: str) -> DocumentParser:
        """根据文件路径创建解析器"""
        file_path = Path(file_path)
        ext = file_path.suffix.lower()
        
        document_type = DocumentParserFactory._detect_type(ext)
        return UnstructuredDocumentParser(document_type)
    
    @staticmethod
    def _detect_type(extension: str) -> DocumentType:
        """根据扩展名检测文档类型"""
        mapping = {
            ".pdf": DocumentType.PDF,
            ".docx": DocumentType.WORD,
            ".doc": DocumentType.WORD,
            ".html": DocumentType.HTML,
            ".htm": DocumentType.HTML,
            ".txt": DocumentType.TXT,
            ".md": DocumentType.MARKDOWN,
        }
        return mapping.get(extension, DocumentType.TXT)


# 便捷函数
def parse_document(file_path: str) -> ParsedDocument:
    """解析文档的便捷函数"""
    parser = DocumentParserFactory.create_parser(file_path)
    return parser.parse(file_path)