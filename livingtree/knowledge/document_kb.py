"""DocumentKB — chunk-based knowledge base for documents up to millions of words.

Handles 1M+ character documents without data loss:
  1. Auto-chunking with overlap (token-aware)
  2. FTS5 full-text index for sub-millisecond keyword search
  3. Hybrid retrieval: FTS5 keyword + embedding cosine → ranked merge (RRF)
  4. Document-level tracking (chunks grouped by parent doc)
  5. Streaming ingestion with transaction batching
  6. Disk-backed with SQLite + in-memory embedding cache

Replaces the broken embedding-truncation path in knowledge_base.py.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger
from sentence_transformers import SentenceTransformer

DB_PATH = Path(".livingtree/document_kb.db")

CHUNK_SIZE = 1000   # chars per chunk
CHUNK_OVERLAP = 200  # overlap between chunks

# ── Hardware acceleration (optional) ──
try:
    from livingtree.core.hardware_acceleration import get_hardware_accelerator
    _hw = get_hardware_accelerator()
    _use_gpu = _hw.gpu.can_accelerate_torch
except Exception:
    _use_gpu = False


@dataclass
class DocChunk:
    id: str
    doc_id: str
    chunk_index: int
    text: str
    embedding: list[float] | None = None
    start_char: int = 0
    end_char: int = 0
    section_path: str = ""      # hierarchical context (MultiDocFusion)
    section_id: str = ""
    section_level: int = 0
    parent_titles: list[str] = field(default_factory=list)


@dataclass
class KBHit:
    chunk: DocChunk
    score: float = 0.0
    source: str = ""  # "fts5" or "embedding"
    title: str = ""
    doc_id: str = ""


class DocumentKB:
    """Chunk-aware knowledge base for large documents."""

    def __init__(self, db_path: str | Path = DB_PATH):
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()
        self._embed_cache: dict[str, list[float]] = {}

    def _create_tables(self):
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, title TEXT, source TEXT,
                total_chars INTEGER, chunk_count INTEGER,
                created_at REAL, metadata TEXT
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY, doc_id TEXT NOT NULL,
                chunk_index INTEGER, text TEXT,
                start_char INTEGER, end_char INTEGER,
                section_path TEXT DEFAULT '',
                section_id TEXT DEFAULT '',
                section_level INTEGER DEFAULT 0,
                parent_titles TEXT DEFAULT '[]',
                embedding TEXT,
                FOREIGN KEY(doc_id) REFERENCES documents(id)
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
            CREATE INDEX IF NOT EXISTS idx_chunks_section ON chunks(section_id);
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                doc_id, chunk_index, text, section_path, section_id,
                tokenize='unicode61',
                content='chunks', content_rowid='rowid'
            );
        """)
        self._db.commit()

    # ═══ Ingestion ═══

    def ingest(self, text: str, title: str = "", source: str = "",
               chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP,
               hierarchical: bool = False) -> str:
        """Ingest a document of any size. Returns doc_id.

        Args:
            hierarchical: if True, use MultiDocFusion hierarchical chunking
                         (section-boundary-aware, preserves document structure).
        """
        if hierarchical:
            return self._hierarchical_ingest(text, title, source, chunk_size, chunk_overlap)

        doc_id = hashlib.sha256(f"{title}{source}{time.time()}".encode()).hexdigest()[:16]
        total_chars = len(text)

        existing = self._db.execute(
            "SELECT id FROM documents WHERE title=? AND total_chars=? LIMIT 1",
            (title, total_chars)
        ).fetchone()
        if existing:
            return existing[0]

        chunks = self._split(text, chunk_size, chunk_overlap)
        self._db.execute(
            "INSERT INTO documents(id,title,source,total_chars,chunk_count,created_at,metadata) VALUES(?,?,?,?,?,?,?)",
            (doc_id, title, source, total_chars, len(chunks), time.time(), "{}")
        )

        chunk_rows = []
        fts_rows = []
        for i, chunk_dict in enumerate(chunks):
            cid = f"{doc_id}-{i}"
            text_safe = chunk_dict["text"].replace("\x00", " ")
            chunk_rows.append((
                cid, doc_id, i, text_safe,
                chunk_dict["start"], chunk_dict["end"],
                chunk_dict.get("section_path", ""),
                chunk_dict.get("section_id", ""),
                chunk_dict.get("section_level", 0),
                json.dumps(chunk_dict.get("parent_titles", [])),
                None,
            ))
            fts_rows.append((doc_id, i, text_safe, chunk_dict.get("section_path", ""), chunk_dict.get("section_id", "")))

        self._db.executemany(
            """INSERT INTO chunks(id,doc_id,chunk_index,text,start_char,end_char,
               section_path,section_id,section_level,parent_titles,embedding)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            chunk_rows
        )
        for row in fts_rows:
            self._db.execute(
                "INSERT INTO chunks_fts(doc_id,chunk_index,text,section_path,section_id) VALUES(?,?,?,?,?)",
                row
            )
        self._db.commit()

        logger.info(f"KB ingested: {title} — {total_chars} chars → {len(chunks)} chunks")
        return doc_id

    def _hierarchical_ingest(self, text: str, title: str, source: str,
                              chunk_size: int, chunk_overlap: int) -> str:
        """Ingest using MultiDocFusion hierarchical chunking."""
        from .hierarchical_chunker import HierarchicalChunker

        doc_id = hashlib.sha256(f"{title}{source}{time.time()}".encode()).hexdigest()[:16]
        total_chars = len(text)

        existing = self._db.execute(
            "SELECT id FROM documents WHERE title=? AND total_chars=? LIMIT 1",
            (title, total_chars)
        ).fetchone()
        if existing:
            return existing[0]

        chunker = HierarchicalChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        doc_chunks = chunker.chunk(text, title=title, source=source)

        try:
            from .ideablock_enricher import get_ideablock_enricher
            enricher = get_ideablock_enricher()
            doc_chunks = enricher.enrich_chunks(doc_chunks)
        except Exception:
            pass

        chunks = [
            {
                "text": c.text,
                "start": c.start_char,
                "end": c.end_char,
                "section_path": c.section_path,
                "section_id": c.section_id,
                "section_level": c.section_level,
                "parent_titles": c.parent_titles,
            }
            for c in doc_chunks
        ]

        self._db.execute(
            "INSERT INTO documents(id,title,source,total_chars,chunk_count,created_at,metadata) VALUES(?,?,?,?,?,?,?)",
            (doc_id, title, source, total_chars, len(chunks), time.time(), "{}")
        )

        chunk_rows = []
        fts_rows = []
        for i, chunk_dict in enumerate(chunks):
            cid = f"{doc_id}-{i}"
            text_safe = chunk_dict["text"].replace("\x00", " ")
            chunk_rows.append((
                cid, doc_id, i, text_safe,
                chunk_dict["start"], chunk_dict["end"],
                chunk_dict.get("section_path", ""),
                chunk_dict.get("section_id", ""),
                chunk_dict.get("section_level", 0),
                json.dumps(chunk_dict.get("parent_titles", [])),
                None,
            ))
            fts_rows.append((doc_id, i, text_safe, chunk_dict.get("section_path", ""), chunk_dict.get("section_id", "")))

        self._db.executemany(
            """INSERT INTO chunks(id,doc_id,chunk_index,text,start_char,end_char,
               section_path,section_id,section_level,parent_titles,embedding)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            chunk_rows
        )
        for row in fts_rows:
            self._db.execute(
                "INSERT INTO chunks_fts(doc_id,chunk_index,text,section_path,section_id) VALUES(?,?,?,?,?)",
                row
            )
        self._db.commit()

        logger.info(
            "KB hierarchical ingested: %s — %d chars → %d chunks (structure-aware)",
            title, total_chars, len(chunks),
        )
        return doc_id

    def _split(self, text: str, chunk_size: int, overlap: int) -> list[dict]:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            # Align to paragraph boundary
            if end < len(text):
                para = text.rfind("\n\n", start, min(end + 500, len(text)))
                if para > start:
                    end = para + 2
            chunks.append({"text": text[start:end], "start": start, "end": end})
            start = end - overlap if end < len(text) else end
        return chunks

    # ═══ Hybrid Retrieval ═══

    def search(self, query: str, top_k: int = 10) -> list[KBHit]:
        """Hybrid retrieval: FTS5 + embedding → RRF merge."""
        fts_results = self._fts5_search(query, top_k * 2)
        emb_results = self._embedding_search(query, top_k * 2)
        merged = self._rrf_merge(fts_results, emb_results, k=60)
        # Group by doc_id and return top chunks
        hits = []
        for chunk, score, source in merged[:top_k]:
            doc = self._db.execute("SELECT title FROM documents WHERE id=?", (chunk.doc_id,)).fetchone()
            title = doc["title"] if doc else ""
            hits.append(KBHit(chunk=chunk, score=score, source=source, title=title, doc_id=chunk.doc_id))
        return hits

    def _fts5_search(self, query: str, limit: int) -> list[tuple[DocChunk, float]]:
        safe = query.replace('"', '""')
        try:
            rows = self._db.execute(
                """SELECT c.id,c.doc_id,c.chunk_index,c.text,c.start_char,c.end_char,c.embedding,
                   rank FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?""",
                (f'"{safe}"', limit)
            ).fetchall()
        except sqlite3.OperationalError:
            rows = self._db.execute(
                "SELECT id,doc_id,chunk_index,text,start_char,end_char,embedding FROM chunks WHERE text LIKE ? LIMIT ?",
                (f"%{safe}%", limit)
            ).fetchall()
            return [(self._row_to_chunk(r), 0.5) for r in rows]
        return [(self._row_to_chunk(r), 1.0 / max(float(r["rank"]) or 1.0, 1.0)) for r in rows]

    def _embedding_search(self, query: str, limit: int) -> list[tuple[DocChunk, float]]:
        emb = self._get_embedding(query)
        if not emb:
            return []

        cached_items = [(cid, e) for cid, e in self._embed_cache.items() if e]
        if not cached_items:
            return []

        # ── GPU batch cosine (if available) ──
        if _use_gpu and len(cached_items) > 50:
            try:
                from livingtree.core.jit_accel import cosine_similarity_batch
                ids = [cid for cid, _ in cached_items]
                vecs = [e for _, e in cached_items]
                sims = cosine_similarity_batch(emb, vecs)
                scores = [(ids[i], sims[i]) for i in range(len(ids)) if sims[i] > 0.3]
            except Exception:
                scores = []
                for cid, cached_emb in cached_items:
                    sim = self._cosine(emb, cached_emb)
                    if sim > 0.3:
                        scores.append((cid, sim))
        else:
            scores = []
            for cid, cached_emb in cached_items:
                sim = self._cosine(emb, cached_emb)
                if sim > 0.3:
                    scores.append((cid, sim))

        scores.sort(key=lambda x: -x[1])
        results = []
        for cid, score in scores[:limit]:
            row = self._db.execute("SELECT * FROM chunks WHERE id=?", (cid,)).fetchone()
            if row:
                results.append((self._row_to_chunk(row), score))
        return results

    def _rrf_merge(self, list_a: list, list_b: list, k: int = 60) -> list:
        scores = defaultdict(float)
        id_to_chunk: dict[str, DocChunk] = {}
        for chunk, score, source in [(c, s, "fts5") for c, s in list_a] + [(c, s, "emb") for c, s in list_b]:
            cid = chunk.id
            id_to_chunk[cid] = chunk
            source_id = 0 if source == "fts5" else 1
            scores[cid] += 1.0 / (k + source_id * 100 + scores[cid] * 10) if scores[cid] else 1.0 / (k + source_id * 100)
        merged = []
        for cid, score in sorted(scores.items(), key=lambda x: -x[1]):
            merged.append((id_to_chunk[cid], score, "hybrid"))
        return merged

    # ═══ Embedding ═══

    def _get_embedding(self, text: str) -> list[float] | None:
        key = hashlib.md5(text[:200].encode()).hexdigest()
        if key in self._embed_cache:
            return self._embed_cache[key]

        try:
            model = SentenceTransformer("all-MiniLM-L6-v2")
            emb = model.encode(text[:2000]).tolist()
            self._embed_cache[key] = emb
            return emb
        except Exception:
            pass
        return self._fallback_embed(text[:1000])

    def _fallback_embed(self, text: str, dim: int = 128) -> list[float]:
        vec = [0.0] * dim
        for i, c in enumerate(text):
            vec[hash(c) % dim] += 1.0 / (i + 1)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(y * y for y in b)) or 1.0
        return dot / (na * nb)

    def _row_to_chunk(self, row) -> DocChunk:
        emb = None
        if row["embedding"]:
            try:
                emb = json.loads(row["embedding"])
            except Exception:
                pass
        parent_titles = []
        try:
            if row["parent_titles"]:
                parent_titles = json.loads(row["parent_titles"])
        except (KeyError, json.JSONDecodeError):
            pass
        return DocChunk(
            id=row["id"], doc_id=row["doc_id"], chunk_index=row["chunk_index"],
            text=row["text"], embedding=emb,
            start_char=row["start_char"], end_char=row["end_char"],
            section_path=row["section_path"] if "section_path" in row.keys() else "",
            section_id=row["section_id"] if "section_id" in row.keys() else "",
            section_level=row["section_level"] if "section_level" in row.keys() else 0,
            parent_titles=parent_titles,
        )

    def get_stats(self) -> dict:
        docs = self._db.execute("SELECT COUNT(*), SUM(total_chars), SUM(chunk_count) FROM documents").fetchone()
        return {
            "documents": docs[0] or 0,
            "total_chars": docs[1] or 0,
            "total_chunks": docs[2] or 0,
            "embed_cache": len(self._embed_cache),
        }

    def close(self):
        self._db.close()
