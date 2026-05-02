"""
JSON Schema First 文档生成系统

核心功能：
1. 基于JSON Schema定义文档结构
2. 支持多种输出格式（Word/PDF/Markdown）
3. 自动化报告生成
4. 数据驱动的内容填充
"""
from .document_generator import DocumentGenerator, ReportTemplate, ReportSection
from .json_schema import ReportSchema, SchemaValidator

__all__ = [
    "DocumentGenerator",
    "ReportTemplate",
    "ReportSection",
    "ReportSchema",
    "SchemaValidator",
]