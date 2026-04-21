"""
🏢 Office 自动化系统 - Hermes Agent 智能中枢

基于 Token 化设计系统的 Office 文档自动化：
- Create: 从零创建专业文档 (15种封面风格)
- Fill/Edit: 智能填充与编辑 (零格式损失)
- Format/Apply: 专业格式化与验证

支持格式: DOCX / XLSX / PPTX / PDF
"""

from core.office_automation.office_manager import OfficeManager
from core.office_automation.design_system import (
    DesignSystem, DesignToken, TokenType, ColorToken,
    FontToken, SpacingToken, DocumentTheme
)
from core.office_automation.template_router import TemplateRouter, TemplateMatch
from core.office_automation.model_router import ModelRouter, ModelCapability
from core.office_automation.quality_checker import QualityChecker, CheckResult, CheckLevel
from core.office_automation.document_context import DocumentContext, DocumentIntent

__all__ = [
    "OfficeManager",
    "DesignSystem", "DesignToken", "TokenType", "ColorToken",
    "FontToken", "SpacingToken", "DocumentTheme",
    "TemplateRouter", "TemplateMatch",
    "ModelRouter", "ModelCapability",
    "QualityChecker", "CheckResult", "CheckLevel",
    "DocumentContext", "DocumentIntent",
]

__version__ = "1.0.0"
