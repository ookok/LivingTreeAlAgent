"""
LivingTree 文档解析模块
======================

Full migration from client/src/business/document_parser/

支持解析PDF、Word、HTML等多种格式文档，提取结构化内容。
集成Unstructured.io实现多格式文档解析，支持表格提取和实体关系抽取。
"""

from .parser_engine import (
    DocumentParser,
    DocumentParserFactory,
    UnstructuredDocumentParser,
    parse_document,
)
from .models import (
    DocumentType,
    SectionType,
    ParsedDocument,
    DocumentSection,
    TableData,
    TableCell,
    EntityRelation,
)

__all__ = [
    "DocumentParser",
    "DocumentParserFactory",
    "UnstructuredDocumentParser",
    "parse_document",
    "DocumentType",
    "SectionType",
    "ParsedDocument",
    "DocumentSection",
    "TableData",
    "TableCell",
    "EntityRelation",
]
