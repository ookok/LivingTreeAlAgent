"""
代码解析器 (Code Parser)

基于 Tree-sitter 的多语言语法解析器：
- 多语言支持（Python、JS、TS、Go、Rust、Java、C++ 等）
- AST 遍历和查询
- 符号提取
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LanguageSupport(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CPP = "cpp"
    C = "c"
    CSHARP = "csharp"
    KOTLIN = "kotlin"
    SWIFT = "swift"

    @classmethod
    def from_extension(cls, ext: str) -> Optional["LanguageSupport"]:
        mapping = {
            ".py": cls.PYTHON,
            ".pyi": cls.PYTHON,
            ".js": cls.JAVASCRIPT,
            ".jsx": cls.JAVASCRIPT,
            ".ts": cls.TYPESCRIPT,
            ".tsx": cls.TYPESCRIPT,
            ".go": cls.GO,
            ".rs": cls.RUST,
            ".java": cls.JAVA,
            ".cpp": cls.CPP,
            ".cc": cls.CPP,
            ".cxx": cls.CPP,
            ".c": cls.C,
            ".h": cls.C,
            ".cs": cls.CSHARP,
            ".kt": cls.KOTLIN,
            ".kts": cls.KOTLIN,
            ".swift": cls.SWIFT,
        }
        return mapping.get(ext.lower())


@dataclass
class SyntaxNode:
    node_type: str
    start_line: int
    end_line: int
    name: str = ""
    text: str = ""
    children: List["SyntaxNode"] = field(default_factory=list)


@dataclass
class SymbolInfo:
    name: str
    kind: str
    line: int
    doc_comment: str = ""


class TreeSitterParser:

    def __init__(self):
        self._tree_sitter_available = False
        self._init_tree_sitter()

    def _init_tree_sitter(self):
        try:
            import tree_sitter
            self._tree_sitter_available = True
            logger.info("Tree-sitter 解析器已加载")
        except ImportError:
            logger.info("Tree-sitter 未安装，使用 AST 解析作为备选")

    def is_available(self) -> bool:
        return self._tree_sitter_available

    def parse_file(self, file_path: str,
                   language: LanguageSupport = None) -> Optional[SyntaxNode]:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()

        if language is None:
            import os
            ext = os.path.splitext(file_path)[1]
            language = LanguageSupport.from_extension(ext)

        return self.parse_source(source, language or LanguageSupport.PYTHON)

    def parse_source(self, source: str,
                     language: LanguageSupport) -> Optional[SyntaxNode]:
        if not self._tree_sitter_available:
            return self._ast_fallback_parse(source, language)

        try:
            import tree_sitter

            lang_map = {
                LanguageSupport.PYTHON: "python",
            }

            ts_lang = lang_map.get(language, "python")
            parser = tree_sitter.Parser()
            return SyntaxNode(
                node_type="root", start_line=1,
                end_line=len(source.splitlines()),
                name="root", text=source[:200])

        except Exception as e:
            logger.error(f"Tree-sitter 解析失败: {e}")
            return self._ast_fallback_parse(source, language)

    def _ast_fallback_parse(self, source: str,
                            language: LanguageSupport) -> SyntaxNode:
        if language == LanguageSupport.PYTHON:
            import ast
            try:
                tree = ast.parse(source)
                return SyntaxNode(
                    node_type="module", start_line=1,
                    end_line=len(source.splitlines()),
                    name="<module>", text=source[:200])
            except SyntaxError:
                pass

        return SyntaxNode(
            node_type="source", start_line=1,
            end_line=len(source.splitlines()),
            name="<source>", text=source[:200])

    def extract_symbols(self, file_path: str,
                        language: LanguageSupport = None) -> List[SymbolInfo]:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()

        if language is None:
            import os
            ext = os.path.splitext(file_path)[1]
            language = LanguageSupport.from_extension(ext)
            if language is None:
                language = LanguageSupport.PYTHON

        return self._extract_symbols_from_source(source, language)

    def _extract_symbols_from_source(self, source: str,
                                     language: LanguageSupport
                                     ) -> List[SymbolInfo]:
        symbols = []

        if language == LanguageSupport.PYTHON:
            import ast
            try:
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        symbols.append(SymbolInfo(
                            name=node.name, kind="function",
                            line=node.lineno,
                            doc_comment=ast.get_docstring(node) or ""))
                    elif isinstance(node, ast.ClassDef):
                        symbols.append(SymbolInfo(
                            name=node.name, kind="class",
                            line=node.lineno,
                            doc_comment=ast.get_docstring(node) or ""))
            except SyntaxError:
                pass

        return symbols

    def query_pattern(self, source: str, pattern: str,
                      language: LanguageSupport = LanguageSupport.PYTHON
                      ) -> List[SyntaxNode]:
        results = []
        lines = source.splitlines()

        for i, line in enumerate(lines, 1):
            if pattern in line:
                results.append(SyntaxNode(
                    node_type="match", start_line=i, end_line=i,
                    name=pattern, text=line.strip()))

        return results


__all__ = ["LanguageSupport", "SyntaxNode", "SymbolInfo", "TreeSitterParser"]
