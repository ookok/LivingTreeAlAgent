"""
LivingTree JSON Schema First 文档生成系统
========================================

Full migration from client/src/business/document_generator/

基于JSON Schema定义文档结构，支持Word/PDF/Markdown多格式输出。
"""

from .document_generator import (
    DocumentGenerator,
    DocumentGenerationResult,
)
from .json_schema import (
    ReportSchema,
    ReportSection,
    ReportType,
    ContentType,
    SchemaValidator,
    ReportTemplates,
)

__all__ = [
    "DocumentGenerator",
    "DocumentGenerationResult",
    "ReportSchema",
    "ReportSection",
    "ReportType",
    "ContentType",
    "SchemaValidator",
    "ReportTemplates",
]
