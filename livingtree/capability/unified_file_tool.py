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
    """Unified search across all content sources."""

    def __init__(self, workspace: str | Path = "."):
        self._workspace = Path(workspace)

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
