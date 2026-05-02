"""
代码编辑器服务模块

核心功能：
1. 语法高亮 - 基于 Tree-sitter 或 LSP
2. 跳转定义 - 基于 LSP 或符号分析
3. 代码格式化 - 基于 LSP 或内置格式化器
4. LSP 集成 - 优先使用 LSP 服务

优先级策略：
1. LSP 服务可用时优先使用 LSP
2. 否则使用 Tree-sitter 进行语法分析
3. 最后降级到正则表达式
"""

from .code_editor_service import (
    CodeEditorService,
    get_code_editor_service,
    LanguageSupport,
    SyntaxToken,
    SymbolLocation,
    FormatResult,
    DefinitionResult,
)

__all__ = [
    "CodeEditorService",
    "get_code_editor_service",
    "LanguageSupport",
    "SyntaxToken",
    "SymbolLocation",
    "FormatResult",
    "DefinitionResult",
]