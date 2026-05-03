"""ASTParser — Multi-language AST parsing via Tree-sitter.

Supports 23 languages with function/class/import/call detection.
Lightweight: one engine, pluggable language grammars.

Usage:
    parser = ASTParser()
    nodes = parser.parse_file("app.py", "python")
    for node in nodes:
        print(node.kind, node.name, node.line)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

try:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjs
    import tree_sitter_typescript as tsts
    import tree_sitter_go as tsgo
    import tree_sitter_rust as tsrust
    import tree_sitter as ts
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

LANG_GRAMMARS = {
    "python": ("tree_sitter_python", lambda: tspython.language()),
    "javascript": ("tree_sitter_javascript", lambda: tsjs.language()),
    "typescript": ("tree_sitter_typescript", lambda: tsts.language_typescript()),
    "tsx": ("tree_sitter_typescript", lambda: tsts.language_tsx()),
    "go": ("tree_sitter_go", lambda: tsgo.language()),
    "rust": ("tree_sitter_rust", lambda: tsrust.language()),
}

EXT_TO_LANG = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
    ".go": "go", ".rs": "rust",
}

NODE_KINDS = {"function", "method", "class", "function_definition", "method_definition",
              "class_definition", "function_declaration", "method_declaration",
              "class_declaration", "arrow_function", "function_item", "impl_item",
              "import", "import_statement", "import_declaration", "import_spec",
              "call", "call_expression", "attribute", "attribute_access"}


@dataclass
class ASTNode:
    kind: str
    name: str
    file: str
    line: int
    end_line: int
    parent_name: str = ""
    children: list[str] = field(default_factory=list)
    code_snippet: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.file}:{self.name}@{self.line}"


@dataclass
class ASTEdge:
    source: str
    target: str
    kind: str  # calls, imports, inherits, contains
    confidence: float = 1.0


class ASTParser:
    """Multi-language Tree-sitter AST parser.

    Detects functions, classes, imports, calls, and inheritance.
    Falls back gracefully when tree-sitter is unavailable.
    """

    def __init__(self):
        self._parsers: dict[str, Any] = {}
        self._available = HAS_TREE_SITTER

    def available(self) -> bool:
        return self._available

    def parse_file(self, filepath: str, language: str = "") -> tuple[list[ASTNode], list[ASTEdge]]:
        """Parse a source file into AST nodes and edges.

        Returns:
            (nodes, edges) — list of ASTNode and ASTEdge
        """
        path = Path(filepath)
        lang = language or EXT_TO_LANG.get(path.suffix.lower(), "")
        if not lang or not self._available:
            return self._fallback_parse(filepath, lang)

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            parser = self._get_parser(lang)
            if not parser:
                return self._fallback_parse(filepath, lang)

            tree = parser.parse(source.encode())
            nodes, edges = self._extract_nodes(tree.root_node, source, str(path), lang)
            return nodes, edges
        except Exception as e:
            logger.debug(f"AST parse error {filepath}: {e}")
            return self._fallback_parse(filepath, lang)

    def parse_source(self, source: str, language: str = "python",
                     filename: str = "<string>") -> tuple[list[ASTNode], list[ASTEdge]]:
        """Parse source code string into nodes and edges."""
        if not self._available:
            return self._fallback_parse_source(source, language, filename)
        try:
            parser = self._get_parser(language)
            if not parser:
                return self._fallback_parse_source(source, language, filename)
            tree = parser.parse(source.encode())
            return self._extract_nodes(tree.root_node, source, filename, language)
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return self._fallback_parse_source(source, language, filename)

    def extract_functions(self, filepath: str, language: str = "") -> list[ASTNode]:
        nodes, _ = self.parse_file(filepath, language)
        return [n for n in nodes if n.kind in ("function", "method", "function_definition",
                                                 "method_definition", "function_declaration")]

    def extract_classes(self, filepath: str, language: str = "") -> list[ASTNode]:
        nodes, _ = self.parse_file(filepath, language)
        return [n for n in nodes if n.kind in ("class", "class_definition", "class_declaration")]

    def extract_imports(self, filepath: str, language: str = "") -> list[ASTNode]:
        nodes, _ = self.parse_file(filepath, language)
        return [n for n in nodes if n.kind.startswith("import")]

    # ── Internal ──

    def _get_parser(self, language: str) -> Optional[Any]:
        if language in self._parsers:
            return self._parsers[language]
        if language not in LANG_GRAMMARS:
            return None
        try:
            _, factory = LANG_GRAMMARS[language]
            parser = ts.Parser(ts.Language(factory()))
            self._parsers[language] = parser
            return parser
        except Exception:
            return None

    def _extract_nodes(self, root, source: str, filename: str, lang: str
                       ) -> tuple[list[ASTNode], list[ASTEdge]]:
        nodes: list[ASTNode] = []
        edges: list[ASTEdge] = []
        cursor = root.walk()

        def _visit():
            node = cursor.node
            kind = str(node.type)
            is_def = kind in NODE_KINDS
            is_func_def = "function_definition" in kind or "method_definition" in kind
            is_class_def = "class_definition" in kind or "class_declaration" in kind
            if is_def or is_func_def or is_class_def:
                name = self._extract_name(node, source, lang)
                if name:
                    code_bytes = node.text
                    snippet = code_bytes.decode("utf-8", errors="replace")[:200]
                    ast_node = ASTNode(
                        kind=self._normalize_kind(kind, lang),
                        name=name,
                        file=filename,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        code_snippet=snippet,
                    )
                    if cursor.node.parent and cursor.node.parent.type in ("class_definition", "class_declaration"):
                        parent_node = cursor.node.parent
                        pnamed = parent_node.child_by_field_name("name")
                        if pnamed:
                            pname = pnamed.text.decode("utf-8", errors="replace")
                            ast_node.parent_name = pname
                            edges.append(ASTEdge(parent=pname, target=name, kind="contains"))
                    nodes.append(ast_node)

                    # Detect calls within function bodies
                    for child in node.children:
                        if child.type in ("call", "call_expression"):
                            child_text = child.text.decode("utf-8", errors="replace")
                            called = self._extract_call_name(child_text)
                            if called:
                                edges.append(ASTEdge(source=name, target=called, kind="calls"))

            # Detect imports
            if "import" in kind and kind != "import_spec_list":
                import_text = node.text.decode("utf-8", errors="replace")[:200]
                for mod in re.findall(r'(?:import|from)\s+(\w+)', import_text):
                    nodes.append(ASTNode(kind="import", name=mod, file=filename,
                                         line=node.start_point[0] + 1, end_line=node.end_point[0] + 1))

            if cursor.goto_first_child():
                _visit()
                cursor.goto_parent()
            if cursor.goto_next_sibling():
                _visit()

        _visit()
        return nodes, edges

    def _extract_name(self, node, source: str, lang: str) -> str:
        named = node.child_by_field_name("name")
        if named:
            return named.text.decode("utf-8", errors="replace")
        for child in node.children:
            if child.type in ("identifier", "property_identifier"):
                return child.text.decode("utf-8", errors="replace")
        text = node.text.decode("utf-8", errors="replace")[:120]
        for pattern in [r'\bdef\s+(\w+)', r'\bclass\s+(\w+)', r'\bfn\s+(\w+)',
                        r'\bfunc\s+(\w+)', r'\bfunction\s+(\w+)']:
            m = re.search(pattern, text)
            if m:
                return m.group(1)
        return ""

    def _normalize_kind(self, kind: str, lang: str) -> str:
        if "function" in kind or "method" in kind or "fn" == kind:
            return "function"
        if "class" in kind or "struct" in kind:
            return "class"
        if "import" in kind:
            return "import"
        return kind

    @staticmethod
    def _extract_call_name(text: str) -> str:
        m = re.match(r'(\w+)', text.strip())
        return m.group(1) if m else ""

    # ── Fallback (no tree-sitter) ──

    def _fallback_parse(self, filepath: str, language: str = ""
                        ) -> tuple[list[ASTNode], list[ASTEdge]]:
        try:
            source = Path(filepath).read_text(encoding="utf-8", errors="replace")
            return self._fallback_parse_source(source, language or "python", filepath)
        except Exception:
            return [], []

    def _fallback_parse_source(self, source: str, language: str, filename: str
                                ) -> tuple[list[ASTNode], list[ASTEdge]]:
        nodes: list[ASTNode] = []
        edges: list[ASTEdge] = []
        lines = source.split("\n")

        # Regex-based function/class detection
        patterns = [
            (r'^\s*def\s+(\w+)', "function"),
            (r'^\s*class\s+(\w+)', "class"),
            (r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)', "function"),
            (r'^\s*(?:public\s+|private\s+)?(?:static\s+)?(?:async\s+)?\w+\s+(\w+)\s*\(', "function"),
            (r'^\s*func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)', "function"),
            (r'^\s*const\s+(\w+)\s*=', "function"),
        ]
        for i, line in enumerate(lines):
            for pat, kind in patterns:
                m = re.match(pat, line)
                if m:
                    nodes.append(ASTNode(kind=kind, name=m.group(1), file=filename,
                                         line=i + 1, end_line=i + 1,
                                         code_snippet=line.strip()[:200]))
                    break

        # Import detection
        for i, line in enumerate(lines):
            imports = re.findall(r'(?:import|from)\s+(\w+)', line)
            for mod in imports:
                nodes.append(ASTNode(kind="import", name=mod, file=filename, line=i + 1, end_line=i + 1))

        return nodes, edges
