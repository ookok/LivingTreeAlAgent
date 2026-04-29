"""
BabelDoc-style Bilingual Document System - 双语对照文档系统
============================================================

参考 BabelDoc (https://github.com/funstory-ai/BabelDoc) 设计的文档翻译和双语对照系统。

核心功能：
- 智能判断是否需要双语对照
- 多格式文档解析 (PDF/DOCX/Markdown/TXT)
- 多翻译引擎支持
- 双语对照渲染

典型工作流：
    文档输入 → 语言检测 → 智能判断(是否双语) → 翻译 → 双语渲染 → 输出
"""

from .document_parser import DocumentParser, ParsedDocument, TextBlock, TableBlock
from .bilingual_detector import BilingualDetector, BilingualDecision, Language
from .translator import Translator, TranslationResult, TranslationProvider
from .renderer import BilingualRenderer, RenderFormat, RenderLayout
from .document_manager import DocumentManager, BilingualDocument

__all__ = [
    # 解析器
    "DocumentParser",
    "ParsedDocument",
    "TextBlock",
    "TableBlock",
    # 双语检测
    "BilingualDetector",
    "BilingualDecision",
    "Language",
    # 翻译器
    "Translator",
    "TranslationResult",
    "TranslationProvider",
    # 渲染器
    "BilingualRenderer",
    "RenderFormat",
    "RenderLayout",
    # 管理器
    "DocumentManager",
    "BilingualDocument",
]

__version__ = "1.0.0"
