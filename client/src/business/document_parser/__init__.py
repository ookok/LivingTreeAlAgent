"""
文档解析模块 - Unstructured.io集成

支持解析PDF、Word、HTML等多种格式文档，提取结构化内容。

核心功能：
1. 多格式文档解析（PDF/Word/HTML/TXT）
2. 表格提取与结构化转换
3. 标题层级识别
4. 实体关系抽取
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