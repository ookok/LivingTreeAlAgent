"""UnifiedFileTool — single entry point for all file/content search.

Routes queries across 6 backends, merges and ranks results:
  1. FileSystem: Toad PathSearch fuzzy finder (files by name)
  2. CodeGraph: AST-based code entity search (functions, classes, imports)
  3. DocumentKB: FTS5 + embedding hybrid (document content)
  4. SessionSearch: FTS5 conversation history recall
  5. KnowledgeBase: bi-temporal cosine semantic search
  6. KnowledgeGraph: entity linking + graph traversal

Command: /find <query> — searches ALL backends, shows unified results.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FileHit:
    path: str = ""
    name: str = ""
    content_preview: str = ""
    source: str = ""  # "filesystem", "code", "document", "history", "kb", "graph"
    score: float = 0.0
    relevance: str = ""


class UnifiedFileTool:
    """Unified search across all content sources.

    Index: SQLite FTS5 for Everything-like instant filename search.
    Content: mmap-based grep when ripgrep not installed.
    """

    _INDEX_DB = Path(".livingtree/file_index.db")

    def __init__(self, workspace: str | Path = "."):
        self._workspace = Path(workspace)
        self._index_conn: Any = None

    def _ensure_index(self):
        if self._index_conn is not None:
            return
        self._INDEX_DB.parent.mkdir(parents=True, exist_ok=True)
        try:
            import sqlite3
            self._index_conn = sqlite3.connect(str(self._INDEX_DB))
            self._index_conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS files USING fts5(path, name, suffix)")
            self._index_conn.execute("PRAGMA cache_size=-2000")
        except Exception:
            self._index_conn = None

    def build_index(self) -> dict:
        """Build FTS5 file index — Everything-like instant search."""
        self._ensure_index()
        if not self._index_conn:
            return {"error": "sqlite3 not available"}
        t0 = time.time()
        self._index_conn.execute("DELETE FROM files")
        count = 0
        for f in self._workspace.rglob("*"):
            if f.is_file() and not any(p.startswith(".") for p in f.parts if p != "."):
                try:
                    self._index_conn.execute(
                        "INSERT INTO files(path, name, suffix) VALUES(?,?,?)",
                        (str(f), f.name, f.suffix),
                    )
                    count += 1
                except Exception:
                    pass
        self._index_conn.commit()
        return {"files": count, "ms": (time.time() - t0) * 1000}

    def search_instant(self, query: str, limit: int = 20) -> list[str]:
        """Everything-like instant filename search via FTS5 index."""
        self._ensure_index()
        if not self._index_conn:
            return []
        try:
            rows = self._index_conn.execute(
                "SELECT path FROM files WHERE files MATCH ? LIMIT ?",
                (query, limit),
            ).fetchall()
            return [r[0] for r in rows]
        except Exception:
            return []

    def grep_content(self, pattern: str, path: str = ".", limit: int = 30) -> str:
        """High-performance content search. mmap-based, no ripgrep needed.

        For files <10MB: read_text + Boyer-Moore-like substring search.
        For files >10MB: mmap + chunked scan.
        """
        import mmap as _mmap
        import re as _re
        lines = []
        p = Path(path)
        files = list(p.rglob("*.py"))[:200] if p.is_dir() else [p]

        for f in files:
            try:
                size = f.stat().st_size
                if size > 10 * 1024 * 1024:
                    with open(f, "r+b") as fh:
                        with _mmap.mmap(fh.fileno(), 0, access=_mmap.ACCESS_READ) as m:
                            content = m.read().decode("utf-8", errors="replace")
                else:
                    content = f.read_text(encoding="utf-8", errors="replace")

                for i, line in enumerate(content.split("\n"), 1):
                    if pattern.lower() in line.lower():
                        lines.append(f"{f}:{i}: {line.strip()[:200]}")
                        if len(lines) >= limit:
                            break
                if len(lines) >= limit:
                    break
            except Exception:
                continue

        return "\n".join(lines) if lines else f"No matches for '{pattern}' in {path}"

    async def search(self, query: str, max_results: int = 15) -> list[FileHit]:
        """Search all backends in parallel, merge and rank results."""
        t0 = time.time()
        tasks = [
            self._search_filesystem(query),
            self._search_code(query),
            self._search_documents(query),
            self._search_history(query),
            self._search_kb(query),
            self._search_graph(query),
        ]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        merged: dict[str, FileHit] = {}
        for results in all_results:
            if isinstance(results, Exception):
                continue
            for hit in results:
                key = hit.path or hit.name
                if key and key in merged:
                    merged[key].score += hit.score
                elif key:
                    merged[key] = hit

        ranked = sorted(merged.values(), key=lambda h: -h.score)
        return ranked[:max_results]

    async def _search_filesystem(self, query: str) -> list[FileHit]:
        """Fuzzy search files by name (fast)."""
        try:
            hits = []
            for root, dirs, files in self._walk_limited(self._workspace):
                for f in files:
                    if query.lower() in f.lower():
                        full = str(Path(root) / f)
                        hits.append(FileHit(
                            path=full, name=f,
                            source="filesystem",
                            score=0.6 if query.lower() in f.lower() else 0.3,
                            relevance="文件名匹配",
                        ))
                if len(hits) > 30:
                    break
            return hits[:10]
        except Exception:
            return []

    async def _search_code(self, query: str) -> list[FileHit]:
        """AST-based code entity search."""
        try:
            from ..capability.code_graph import CodeGraph
            cg = CodeGraph()
            entities = cg.search(query)
            hits = []
            for e in entities[:10]:
                hits.append(FileHit(
                    path=e.file_path or "", name=e.name,
                    content_preview=e.signature or e.name,
                    source="code",
                    score=0.7,
                    relevance=f"代码实体: {e.kind or 'symbol'}",
                ))
            return hits
        except Exception:
            return []

    async def _search_documents(self, query: str) -> list[FileHit]:
        """FTS5 + embedding document search."""
        try:
            from ..knowledge.document_kb import DocumentKB
            dkb = DocumentKB()
            results = dkb.search(query, top_k=10)
            hits = []
            for r in results:
                hits.append(FileHit(
                    path=f"kb://{r.doc_id}/{r.chunk.chunk_index}",
                    name=r.title or f"Chunk {r.chunk.chunk_index}",
                    content_preview=r.chunk.text[:150],
                    source="document",
                    score=r.score,
                    relevance="文档内容匹配",
                ))
            return hits
        except Exception:
            return []

    async def _search_history(self, query: str) -> list[FileHit]:
        """FTS5 conversation history search."""
        try:
            from ..knowledge.session_search import get_search
            ss = get_search()
            results = ss.search(query, limit=10)
            hits = []
            for r in results:
                hits.append(FileHit(
                    path=f"session://{r.session_id}/{r.turn_id}",
                    name=f"{r.role}: {r.snippet[:60]}",
                    content_preview=r.content[:150],
                    source="history",
                    score=0.4,
                    relevance="历史对话",
                ))
            return hits
        except Exception:
            return []

    async def _search_kb(self, query: str) -> list[FileHit]:
        """Bi-temporal knowledge base search."""
        try:
            from ..knowledge.knowledge_base import KnowledgeBase
            kb = KnowledgeBase()
            docs = kb.search(query, top_k=5)
            hits = []
            for doc in docs:
                hits.append(FileHit(
                    path=f"kb://{doc.id}",
                    name=doc.title or doc.id,
                    content_preview=doc.content[:150] if doc.content else "",
                    source="kb",
                    score=0.5,
                    relevance="知识库匹配",
                ))
            return hits
        except Exception:
            return []

    async def _search_graph(self, query: str) -> list[FileHit]:
        """Knowledge graph entity search."""
        try:
            from ..knowledge.knowledge_graph import KnowledgeGraph
            kg = KnowledgeGraph()
            entities = kg.entity_linking(query)
            hits = []
            for entity in entities[:5]:
                neighbors = kg.query_graph(entity)
                for n in neighbors[:3]:
                    hits.append(FileHit(
                        name=n.get("label", entity),
                        source="graph",
                        score=0.3,
                        relevance="知识图谱关联",
                    ))
            return hits
        except Exception:
            return []

    @staticmethod
    def _walk_limited(root: Path, max_depth: int = 4):
        """Walk filesystem with depth limit."""
        for current in root.iterdir():
            if current.name.startswith(".") and current.name not in (".gitignore",):
                continue
            if current.is_dir() and max_depth > 0:
                yield from UnifiedFileTool._walk_limited(current, max_depth - 1)
            elif current.is_file():
                yield (str(current.parent), [], [current.name])
