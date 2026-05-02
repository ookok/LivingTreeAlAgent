"""
文档解析模块 - Unstructured.io集成

Full migration complete. → livingtree.core.document_parser

支持解析PDF、Word、HTML等多种格式文档，提取结构化内容。
"""
from .parser_engine import DocumentParser, DocumentParserFactory
from .models import ParsedDocument, DocumentSection, TableData, EntityRelation

__all__ = [
    "DocumentParser",
    "DocumentParserFactory",
    "ParsedDocument",
    "DocumentSection",
    "TableData",
    "EntityRelation",
]