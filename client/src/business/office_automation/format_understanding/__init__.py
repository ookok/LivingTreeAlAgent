"""
🎨 格式理解引擎 - Office 自动化系统的"格式大脑"

三大维度：
1. 视觉格式 (Visual Formatting) - 用户看到的布局/排版/视觉元素
2. 结构格式 (Structural Formatting) - 文档组织逻辑/层次/元数据
3. 语义格式 (Semantic Formatting) - 格式传达的意义/业务语义

核心模块：
- format_parser.py: 格式解析器 (XML解析 → 格式提取 → 格式图谱)
- format_graph.py: 格式图谱 (图模型表示格式结构)
- format_semantic.py: 格式语义理解 (模式识别/业务映射/意图推断)
- format_evaluator.py: 格式质量评估 (可读性/专业性/可访问性)
- format_knowledge.py: 格式知识库 (规范库/模式库/案例库)
- format_aware_workflow.py: 格式感知的AI工作流

设计理念：
"不仅仅是内容正确，格式也完美" - 企业级Office自动化的核心竞争力
"""

from core.office_automation.format_understanding.format_parser import (
    FormatParser, FormatInfo, FormatElement, FormatProperty,
    VisualFormat, StructuralFormat, SemanticFormat,
)
from core.office_automation.format_understanding.format_graph import (
    FormatGraph, FormatNode, FormatEdge, FormatRelation,
)
from core.office_automation.format_understanding.format_semantic import (
    FormatSemanticModel, FormatPattern, BusinessSemantic,
    FormatIntent, DesignIntent,
)
from core.office_automation.format_understanding.format_evaluator import (
    FormatEvaluator, QualityMetrics, ReadabilityMetrics,
    ProfessionalMetrics, AccessibilityMetrics,
)
from core.office_automation.format_understanding.format_knowledge import (
    FormatKnowledgeBase, FormatStandard, FormatPatternLibrary,
    FormatCase, UserPreference,
)

__all__ = [
    "FormatParser", "FormatInfo", "FormatElement", "FormatProperty",
    "VisualFormat", "StructuralFormat", "SemanticFormat",
    "FormatGraph", "FormatNode", "FormatEdge", "FormatRelation",
    "FormatSemanticModel", "FormatPattern", "BusinessSemantic",
    "FormatIntent", "DesignIntent",
    "FormatEvaluator", "QualityMetrics", "ReadabilityMetrics",
    "ProfessionalMetrics", "AccessibilityMetrics",
    "FormatKnowledgeBase", "FormatStandard", "FormatPatternLibrary",
    "FormatCase", "UserPreference",
]

__version__ = "1.0.0"
