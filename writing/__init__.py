"""
全学科智能写作助手模块

导入所有写作相关组件
"""

# 先导入枚举和基础类型
from writing.intent_detector import (
    IntentDetector,
    IntentResult,
    AnalysisContext,
    DocType,
    SubjectDomain,
    WritingFormat,
    get_intent_detector,
)

from writing.latex_processor import (
    LatexProcessor,
    ParsedFormula,
    FormulaType,
    OperatorType,
    get_latex_processor,
)

# 在枚举导入后才能导入依赖它们的模块
from writing.outline_generator import (
    OutlineGenerator,
    OutlineSection,
    OutlineTemplate,
    OutlineStyle,
    get_outline_generator,
)

from writing.citation_manager import (
    CitationManager,
    Citation,
    CitationType,
    CitationStyle,
    get_citation_manager,
)

# AI 写作助手最后导入，因为它依赖上面的模块
from writing.ai_writer import (
    AIWriter,
    WritingContext,
    WritingResult,
    WritingMode,
    get_ai_writer,
)

# 旧版兼容
from writing.doc_manager import DocManager
from writing.file_watcher import ProjectFileWatcher
from writing.converter import TransparentConverter, MARKITDOWN_AVAILABLE
from writing.event_handler import ConverterEventHandler

__all__ = [
    # 意图识别
    "IntentDetector",
    "IntentResult",
    "AnalysisContext",
    "DocType",
    "SubjectDomain",
    "WritingFormat",
    "get_intent_detector",
    # LaTeX
    "LatexProcessor",
    "ParsedFormula",
    "FormulaType",
    "OperatorType",
    "get_latex_processor",
    # AI 写作
    "AIWriter",
    "WritingContext",
    "WritingResult",
    "WritingMode",
    "get_ai_writer",
    # 大纲
    "OutlineGenerator",
    "OutlineSection",
    "OutlineTemplate",
    "OutlineStyle",
    "get_outline_generator",
    # 引用
    "CitationManager",
    "Citation",
    "CitationType",
    "CitationStyle",
    "get_citation_manager",
    # 兼容
    "DocManager",
    "ProjectFileWatcher",
    "TransparentConverter",
    "MARKITDOWN_AVAILABLE",
    "ConverterEventHandler",
]
