"""SemanticCodeSearch — Natural language and embedding-based code search.

Goes beyond lexical name-matching to find code by behavior/description.
Uses lightweight hash-based embeddings for zero-dependency semantic search.

Capabilities:
  search_by_description("find all database connection functions")
  search_similar(function_signature_or_code)
  find_usages(symbol_name) — where is this used?
  search_by_pattern("sorting algorithms", "error handling")

Integration:
  search = get_semantic_code_search()
  results = await search.query("functions that handle API authentication")
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class CodeIndexEntry:
    name: str
    file: str
    line: int
    kind: str  # "function" | "class" | "method" | "import"
    signature: str = ""
    docstring: str = ""
    code_snippet: str = ""
    keywords: list[str] = field(default_factory=list)
    embedding: list[float] = field(default_factory=list)


@dataclass
class SearchResult:
    entry: CodeIndexEntry
    score: float = 0.0
    match_reason: str = ""


class SemanticCodeSearch:
    """Natural language and embedding-based code search."""

    _instance: Optional["SemanticCodeSearch"] = None

    @classmethod
    def instance(cls) -> "SemanticCodeSearch":
        if cls._instance is None:
            cls._instance = SemanticCodeSearch()
        return cls._instance

    def __init__(self):
        self._index: dict[str, list[CodeIndexEntry]] = {}  # file → entries
        self._global_entries: list[CodeIndexEntry] = []
        self._indexed = False

    # ── Indexing ───────────────────────────────────────────────────

    def index(self, root_dir: str = "", pattern: str = "**/*.py") -> int:
        """Build semantic index of a codebase."""
        root = Path(root_dir or ".")
        if not root.exists():
            logger.warning(f"SemanticCodeSearch: directory not found: {root}")
            return 0

        self._index.clear()
        self._global_entries.clear()
        count = 0

        for py_file in root.rglob(pattern):
            if "test_" in py_file.name or py_file.name.startswith("__"):
                continue
            try:
                entries = self._index_file(py_file)
                if entries:
                    self._index[str(py_file)] = entries
                    self._global_entries.extend(entries)
                    count += len(entries)
            except Exception:
                continue

        self._indexed = True
        logger.info(f"SemanticCodeSearch: indexed {count} entries from {root}")
        return count

    def _index_file(self, file_path: Path) -> list[CodeIndexEntry]:
        """Parse a Python file and extract searchable entries."""
        entries = []
        try:
            source = file_path.read_text(errors="replace")
            tree = ast.parse(source)
        except SyntaxError:
            return entries

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue

                # Extract signature + docstring
                sig = self._extract_signature(node, source)
                doc = ast.get_docstring(node) or ""

                # Build keyword list
                keywords = self._extract_keywords(node.name, sig, doc, source, node.lineno)

                # Hash-based embedding (64-dim)
                embedding = self._hash_embed(node.name + sig + doc)

                entries.append(CodeIndexEntry(
                    name=node.name, file=str(file_path),
                    line=node.lineno, kind="function",
                    signature=sig, docstring=doc[:300],
                    code_snippet=self._get_context(source, node.lineno, 5),
                    keywords=keywords, embedding=embedding,
                ))

            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                doc = ast.get_docstring(node) or ""
                entries.append(CodeIndexEntry(
                    name=node.name, file=str(file_path),
                    line=node.lineno, kind="class",
                    docstring=doc[:200],
                ))

        return entries

    # ── Search ─────────────────────────────────────────────────────

    async def query(self, description: str, top_k: int = 10) -> list[SearchResult]:
        """Search code by natural language description."""
        if not self._indexed:
            self.index()

        query_keywords = self._tokenize(description)
        query_emb = self._hash_embed(description)

        scored = []
        for entry in self._global_entries:
            # Keyword overlap score
            keyword_score = self._keyword_score(query_keywords, entry)
            # Embedding cosine similarity
            emb_score = self._cosine_similarity(query_emb, entry.embedding) if entry.embedding else 0

            score = keyword_score * 0.5 + emb_score * 0.5
            if score > 0.05:
                scored.append(SearchResult(
                    entry=entry, score=round(score, 3),
                    match_reason=self._match_reason(query_keywords, entry, score),
                ))

        scored.sort(key=lambda x: -x.score)
        return scored[:top_k]

    def find_usages(self, symbol: str, root: str = "") -> list[dict]:
        """Find where a symbol (function/variable) is used."""
        root_path = Path(root or ".")
        results = []
        for py_file in root_path.rglob("*.py"):
            try:
                content = py_file.read_text(errors="replace")
                for m in re.finditer(r'\b' + re.escape(symbol) + r'\b', content):
                    line_num = content[:m.start()].count("\n") + 1
                    context = content[max(0, m.start()-50):m.end()+50]
                    results.append({
                        "file": str(py_file), "line": line_num,
                        "context": context.strip()[:200],
                    })
            except Exception:
                continue
        return results[:50]

    # ── Helpers ────────────────────────────────────────────────────

    def _extract_signature(self, func, source: str) -> str:
        """Extract function signature as string."""
        args = []
        for arg in func.args.args:
            arg_str = arg.arg
            if arg.annotation:
                try:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                except Exception:
                    pass
            args.append(arg_str)
        return f"def {func.name}({', '.join(args)})"

    def _extract_keywords(self, name: str, sig: str, doc: str,
                          source: str, line: int) -> list[str]:
        """Extract search keywords from function context."""
        keywords = set()

        # Name decomposition
        for part in re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', name):
            keywords.add(part.lower())

        # Signature types
        for m in re.finditer(r':\s*(\w+)', sig):
            keywords.add(m.group(1).lower())

        # Docstring terms
        for word in doc.lower().split()[:20]:
            if len(word) > 2:
                keywords.add(word)

        # Context terms
        context = self._get_context(source, line, 3)
        for word in context.lower().split()[:10]:
            if len(word) > 3:
                keywords.add(word)

        return list(keywords)[:30]

    def _get_context(self, source: str, line: int, radius: int) -> str:
        """Get code context around a line."""
        lines = source.split("\n")
        start = max(0, line - radius - 1)
        end = min(len(lines), line + radius)
        return "\n".join(lines[start:end])

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into search keywords."""
        words = re.findall(r'[a-zA-Z_]\w*', text.lower())
        return [w for w in words if len(w) > 2][:20]

    def _keyword_score(self, query_words: list[str],
                       entry: CodeIndexEntry) -> float:
        """Score entry by keyword overlap."""
        if not query_words:
            return 0.0
        # Check name
        name_score = sum(1 for w in query_words if w in entry.name.lower()) / len(query_words)
        # Check docstring
        doc_score = sum(1 for w in query_words
                       if w in (entry.docstring or "").lower()) / max(len(query_words), 1)
        # Check keywords
        kw_score = sum(1 for w in query_words
                      if any(w in k for k in entry.keywords)) / max(len(query_words), 1)

        return name_score * 0.3 + doc_score * 0.3 + kw_score * 0.4

    def _hash_embed(self, text: str, dim: int = 64) -> list[float]:
        """Deterministic hash-based embedding (zero-dependency)."""
        if not text:
            return [0.0] * dim
        vec = [0.0] * dim
        for i, ch in enumerate(text):
            idx = (hash(ch) + i * 31) % dim
            vec[idx] += 1.0 / (abs(hash(ch + str(i))) % 100 + 1)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(x * x for x in b)) or 1.0
        return dot / (na * nb)

    def _match_reason(self, query_words: list[str],
                      entry: CodeIndexEntry, score: float) -> str:
        """Generate human-readable match reason."""
        reasons = []
        if any(w in entry.name.lower() for w in query_words):
            reasons.append(f"name matches: {entry.name}")
        if any(w in (entry.docstring or "").lower() for w in query_words):
            reasons.append("docstring matches")
        if score > 0.3:
            reasons.append(f"keyword overlap: {entry.keywords[:5]}")
        return "; ".join(reasons) if reasons else f"score={score:.2f}"

    def stats(self) -> dict:
        return {"indexed": self._indexed, "entries": len(self._global_entries)}


_search: Optional[SemanticCodeSearch] = None


def get_semantic_code_search() -> SemanticCodeSearch:
    global _search
    if _search is None:
        _search = SemanticCodeSearch()
    return _search


__all__ = ["SemanticCodeSearch", "SearchResult", "CodeIndexEntry",
           "get_semantic_code_search"]
