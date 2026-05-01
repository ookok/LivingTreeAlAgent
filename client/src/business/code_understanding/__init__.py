"""
代码理解引擎 - 基于 Tree-sitter 的代码分析能力

核心功能：
1. 代码语法分析（支持多种语言）
2. 代码结构提取
3. 依赖关系分析
4. 代码模式识别
5. Git 仓库分析（GitNexus 风格）- 已迁移到 git_nexus 模块
"""

from .code_parser import CodeParser, LanguageSupport
from .code_analyzer import CodeAnalyzer
from .pattern_recognizer import PatternRecognizer
from .code_graph import CodeGraph

# 从 git_nexus 导入增强的代码智能引擎
from ..git_nexus import GitNexus, GitAnalyzer

__all__ = [
    "CodeParser",
    "LanguageSupport",
    "CodeAnalyzer",
    "PatternRecognizer",
    "CodeGraph",
    "GitNexus",
    "GitAnalyzer"
]