"""
代码理解系统 (Code Understanding System)

多维度代码分析引擎：
1. 代码分析 (CodeAnalyzer) - AST 解析、结构分析、复杂度评估
2. 代码图谱 (CodeGraph) - 调用关系、依赖关系图
3. 代码解析 (TreeSitterParser) - 多语言语法解析
4. 模式识别 (PatternRecognizer) - 设计模式和反模式检测
5. Git 分析 (GitAnalyzer) - 提交历史和代码演进分析
"""

from .code_analyzer import CodeAnalyzer, CodeAnalysis
from .code_graph import CodeGraph, CodeNode
from .code_parser import TreeSitterParser, LanguageSupport
from .pattern_recognizer import PatternRecognizer, CodePattern
from .git_analyzer import GitAnalyzer, GitCommitInfo

__all__ = [
    "CodeAnalyzer", "CodeAnalysis",
    "CodeGraph", "CodeNode",
    "TreeSitterParser", "LanguageSupport",
    "PatternRecognizer", "CodePattern",
    "GitAnalyzer", "GitCommitInfo",
]
