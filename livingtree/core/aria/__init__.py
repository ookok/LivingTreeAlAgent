"""
A.R.I.A - Autonomous Research & Industrial Architect

核心功能：
1. 文档解析与概念化
2. 自我驱动的内容生成
3. Markdown DSL解析与渲染
4. Word文档输出（从用户文档学习样式）
5. 流式通信支持
6. 实时思考过程可视化
7. 样式自动学习与进化

愿景：一个能够像资深咨询工程师一样思考、像熟练程序员一样编码、
     像专业排版员一样输出文档的自我进化系统。
"""
from .aria_controller import ARIAController, GenerationTask, GenerationStatus
from .markdown_dsl_parser import MarkdownDSLParser, DSLNode
from .word_renderer import WordRenderer
from .style_learner import StyleLearner, StyleDefinition, TableStyleDefinition

__all__ = [
    "ARIAController",
    "GenerationTask",
    "GenerationStatus",
    "MarkdownDSLParser",
    "DSLNode",
    "WordRenderer",
    "StyleLearner",
    "StyleDefinition",
    "TableStyleDefinition",
]