"""
文档解析数据模型
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class DocumentType(Enum):
    PDF = "pdf"
    WORD = "word"
    HTML = "html"
    TXT = "txt"
    MARKDOWN = "markdown"


class SectionType(Enum):
    TITLE = "title"
    HEADING_1 = "h1"
    HEADING_2 = "h2"
    HEADING_3 = "h3"
    HEADING_4 = "h4"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST = "list"
    IMAGE = "image"
    FOOTER = "footer"
    HEADER = "header"


@dataclass
class TableCell:
    """表格单元格"""
    content: str
    is_header: bool = False
    row_span: int = 1
    col_span: int = 1


@dataclass
class TableData:
    """表格数据"""
    caption: Optional[str] = None
    headers: List[str] = field(default_factory=list)
    rows: List[List[TableCell]] = field(default_factory=list)
    
    @property
    def as_dict(self):
        """转换为字典格式"""
        return {
            "caption": self.caption,
            "headers": self.headers,
            "rows": [[cell.content for cell in row] for row in self.rows]
        }


@dataclass
class DocumentSection:
    """文档章节"""
    id: str
    type: SectionType
    content: str
    level: int = 0
    table_data: Optional[TableData] = None
    children: List['DocumentSection'] = field(default_factory=list)
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityRelation:
    """实体关系"""
    source_entity: str
    relation_type: str
    target_entity: str
    confidence: float = 1.0
    evidence: Optional[str] = None


@dataclass
class ParsedDocument:
    """解析后的文档"""
    document_id: str
    file_name: str
    document_type: DocumentType
    title: Optional[str] = None
    sections: List[DocumentSection] = field(default_factory=list)
    tables: List[TableData] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    relations: List[EntityRelation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    total_pages: Optional[int] = None
    word_count: int = 0
    
    def get_section_by_id(self, section_id: str) -> Optional[DocumentSection]:
        """根据ID获取章节"""
        for section in self.sections:
            if section.id == section_id:
                return section
            child = self._find_in_children(section, section_id)
            if child:
                return child
        return None
    
    def _find_in_children(self, section: DocumentSection, section_id: str) -> Optional[DocumentSection]:
        """递归查找子章节"""
        for child in section.children:
            if child.id == section_id:
                return child
            found = self._find_in_children(child, section_id)
            if found:
                return found
        return None
    
    def get_tables_by_section(self, section_id: str) -> List[TableData]:
        """获取指定章节的表格"""
        # TODO: 根据章节ID筛选表格
        return self.tables