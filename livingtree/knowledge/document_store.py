"""DocumentStore — Unified KB backend replacing 8 fragmented stores.

Single SQLite DB + LanceDB vectors replaces: SQLiteBackend, DocumentKB,
VectorStore, LanceDBStore, HypergraphStore, StructMemory, ContextWiki,
EngramStore, MilvusStore.

Schema (5 tables, 3 indexes, 1 FTS5, 1 LanceDB):
  documents       — articles, wiki pages, memories, engrams, chunks
  docs_fts        — FTS5 full‑text index (unicode61 tokenizer)
  relations       — hypergraph edges, wiki cross‑refs, precedence, co‑occurrence
  event_entries   — StructMem dual‑perspective event binding (FACT + RELATION)
  synthesis_blocks— consolidated cross‑event summaries
  vectors/        — LanceDB columnar vector store (384‑dim, all‑MiniLM‑L6‑v2)
"""

from __future__ import annotations

import hashlib, json, math, sqlite3, time, uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import lancedb, pyarrow as pa
from loguru import logger
from sentence_transformers import SentenceTransformer

DB_PATH = ".livingtree/document_store.db"
VECTOR_PATH = ".livingtree/vectors"
EMBED_MODEL = "all-MiniLM-L6-v2"
EMBED_DIM = 384
RRF_K = 60
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
NGRAM_MIN, NGRAM_MAX, NGRAM_MOD = 2, 4, 100003
CAT_DOC = "document"
CAT_CHUNK = "chunk"
CAT_WIKI = "wiki_page"
CAT_MEMORY = "memory"
CAT_ENGRAM = "engram"
REL_REF = "references"
REL_PREC = "precedence"
REL_COOC = "cooccurrence"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, title TEXT, content TEXT,
    domain TEXT DEFAULT 'general', category TEXT DEFAULT 'document',
    source TEXT DEFAULT 'manual', author TEXT DEFAULT 'system',
    revision INTEGER DEFAULT 1, importance REAL DEFAULT 0.0,
    parent_id TEXT, section_path TEXT DEFAULT '',
    valid_from TEXT, valid_to TEXT,
    created_at REAL DEFAULT (unixepoch()),
    updated_at REAL DEFAULT (unixepoch()),
    metadata TEXT DEFAULT '{}',
    doc_id TEXT, chunk_index INTEGER, start_char INTEGER
);
CREATE INDEX IF NOT EXISTS idx_docs_domain ON documents(domain);
CREATE INDEX IF NOT EXISTS idx_docs_category ON documents(category);
CREATE INDEX IF NOT EXISTS idx_docs_parent ON documents(parent_id);
CREATE INDEX IF NOT EXISTS idx_docs_doc_id ON documents(doc_id);
CREATE INDEX IF NOT EXISTS idx_docs_section ON documents(section_path);
CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
    title, content, domain, category, section_path,
    tokenize='unicode61', content='documents', content_rowid='rowid'
);
CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL, target_id TEXT NOT NULL,
    relation TEXT DEFAULT 'references', weight REAL DEFAULT 1.0,
    properties TEXT DEFAULT '{}',
    created_at REAL DEFAULT (unixepoch()),
    UNIQUE(source_id, target_id, relation)
);
CREATE INDEX IF NOT EXISTS idx_rel_source ON relations(source_id);
CREATE INDEX IF NOT EXISTS idx_rel_target ON relations(target_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON relations(relation);
CREATE TABLE IF NOT EXISTS event_entries (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    fact_perspective TEXT DEFAULT '',
    rel_perspective TEXT DEFAULT '',
    embedding TEXT DEFAULT '[]',
    sources TEXT DEFAULT '[]',
    persona_domain TEXT DEFAULT '',
    emotional_valence REAL DEFAULT 0.0,
    memory_tier TEXT DEFAULT 'hot',
    access_count INTEGER DEFAULT 0,
    last_access REAL DEFAULT 0.0,
    created_at REAL DEFAULT (unixepoch()),
    updated_at REAL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_events_session ON event_entries(session_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON event_entries(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_tier ON event_entries(memory_tier);
CREATE TABLE IF NOT EXISTS synthesis_blocks (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    content TEXT NOT NULL,
    source_entries TEXT DEFAULT '[]',
    session_ids TEXT DEFAULT '[]',
    model_category TEXT DEFAULT 'general',
    confidence REAL DEFAULT 0.5,
    evidence_count INTEGER DEFAULT 0,
    created_at REAL DEFAULT (unixepoch()),
    updated_at REAL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_synth_timestamp ON synthesis_blocks(timestamp);
"""


class DocumentStore:
    """Unified knowledge store: SQLite + FTS5 + LanceDB + engram index."""

    _model: Optional[SentenceTransformer] = None
    _store: Optional["DocumentStore"] = None

    def __init__(self, db_path: str = DB_PATH, vector_path: str = VECTOR_PATH):
        self._db_path = db_path
        self._vector_path = vector_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(vector_path).mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-8000")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

        self._lance_db = lancedb.connect(vector_path)
        self._vector_table = None
        self._ensure_vector_table()

        self._engram_idx: dict[int, set[str]] = defaultdict(set)
        self._engram_keys: dict[str, str] = {}
        self._build_engram_index()
        logger.info("DocumentStore: {} + {}", db_path, vector_path)

    # ═══ Internal helpers ══════════════════════════════════════════════════

    @classmethod
    def _get_embedder(cls) -> SentenceTransformer:
        if cls._model is None:
            cls._model = SentenceTransformer(EMBED_MODEL)
        return cls._model

    def _embed(self, text: str) -> list[float]:
        return self._get_embedder().encode(text[:2000]).tolist()

    def _ensure_vector_table(self):
        try:
            self._vector_table = self._lance_db.open_table("documents")
        except Exception:
            self._vector_table = self._lance_db.create_table("documents", pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), EMBED_DIM)),
                pa.field("text", pa.string()),
            ]))

    def _get_rowid(self, doc_id: str) -> int:
        row = self._conn.execute("SELECT rowid FROM documents WHERE id=?", (doc_id,)).fetchone()
        return row[0] if row else -1

    def _fts_insert(self, rowid: int):
        self._conn.execute("INSERT INTO docs_fts(rowid) VALUES (?)", (rowid,))

    def _fts_delete(self, rowid: int):
        self._conn.execute("INSERT INTO docs_fts(docs_fts, rowid) VALUES('delete', ?)", (rowid,))

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        if d.get("metadata"):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except (json.JSONDecodeError, TypeError):
                d["metadata"] = {}
        return d

    # ═══ Chunking ══════════════════════════════════════════════════════════

    @staticmethod
    def _split_chunks(text: str) -> list[dict]:
        chunks: list[dict] = []
        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            if end < len(text):
                para = text.rfind("\n\n", start, min(end + 500, len(text)))
                if para > start:
                    end = para + 2
            chunks.append({"text": text[start:end], "start_char": start})
            start = end - CHUNK_OVERLAP if end < len(text) else end
        return chunks

    # ═══ N-gram Engram ═════════════════════════════════════════════════════

    @staticmethod
    def _compute_ngrams(text: str) -> set[str]:
        clean = text.lower().strip()
        ngrams: set[str] = set()
        for n in range(NGRAM_MIN, NGRAM_MAX + 1):
            for i in range(len(clean) - n + 1):
                ngrams.add(clean[i:i + n])
        return ngrams

    @staticmethod
    def _ngram_hashes(ngrams: set[str]) -> list[int]:
        return [int(hashlib.md5(ng.encode()).hexdigest()[:8], 16) % NGRAM_MOD for ng in ngrams]

    def _build_engram_index(self):
        rows = self._conn.execute(
            "SELECT id, title, content FROM documents WHERE category IN (?, ?)",
            (CAT_ENGRAM, CAT_DOC),
        ).fetchall()
        for row in rows:
            ngrams = self._compute_ngrams(row["title"] + " " + row["content"][:500])
            for h in self._ngram_hashes(ngrams):
                self._engram_idx[h].add(row["id"])
            if row["title"]:
                self._engram_keys[row["id"]] = row["title"]

    # ═══ Add Documents ═════════════════════════════════════════════════════

    def add_document(
        self, title: str, content: str, domain: str = "general",
        category: str = CAT_DOC, source: str = "manual",
        author: str = "system", metadata: dict | None = None,
        importance: float = 0.0, parent_id: str | None = None,
        section_path: str = "", auto_chunk: bool = True,
    ) -> str:
        doc_id = str(uuid.uuid4())
        now = time.time()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        self._conn.execute(
            """INSERT INTO documents(id, title, content, domain, category, source,
               author, importance, parent_id, section_path, created_at, updated_at,
               metadata) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (doc_id, title, content, domain, category, source, author,
             importance, parent_id, section_path, now, now, meta_json),
        )
        self._fts_insert(self._conn.lastrowid)

        if category == CAT_ENGRAM:
            ngrams = self._compute_ngrams(title + " " + content[:500])
            for h in self._ngram_hashes(ngrams):
                self._engram_idx[h].add(doc_id)
            self._engram_keys[doc_id] = title

        try:
            self._vector_table.add(pa.table({
                "id": [doc_id], "vector": [self._embed(content)],
                "text": [content[:1000]],
            }))
        except Exception as e:
            logger.debug(f"Vector embed skipped: {e}")

        if auto_chunk and len(content) > CHUNK_SIZE and category in (CAT_DOC, CAT_ENGRAM):
            self.add_chunks(doc_id, self._split_chunks(content))

        self._conn.commit()
        return doc_id

    def add_chunks(self, doc_id: str, chunks: list[dict]):
        now = time.time()
        for i, ch in enumerate(chunks):
            cid = f"{doc_id}-chunk-{i}"
            chunk_text = ch["text"].replace("\x00", " ")
            self._conn.execute(
                """INSERT INTO documents(id, title, content, domain, category,
                   parent_id, doc_id, chunk_index, start_char, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (cid, "", chunk_text, "general", CAT_CHUNK,
                 doc_id, doc_id, i, ch["start_char"], now, now),
            )
            self._fts_insert(self._conn.lastrowid)
        self._conn.commit()

    # ═══ Wiki Pages ════════════════════════════════════════════════════════

    def add_wiki_page(
        self, title: str, path: str, content: str, section: str,
        tags: list[str] | None = None, cross_refs: list[str] | None = None,
        importance: float = 0.5, source_stage: str = "",
    ) -> str:
        doc_id = self.add_document(
            title=title, content=content, domain="wiki", category=CAT_WIKI,
            source=source_stage, metadata={"tags": tags or [], "path": path},
            importance=importance, section_path=section, auto_chunk=False,
        )
        for ref in cross_refs or []:
            ref_id = self._resolve_wiki_ref(ref, section)
            if ref_id:
                self.add_relation(doc_id, ref_id, REL_REF)
                self.add_relation(ref_id, doc_id, REL_REF)
        return doc_id

    def _resolve_wiki_ref(self, ref_path: str, section: str) -> Optional[str]:
        search = ref_path if ref_path.startswith("/") else f"{section}/{ref_path}"
        row = self._conn.execute(
            "SELECT id FROM documents WHERE section_path=? AND category=? LIMIT 1",
            (search, CAT_WIKI),
        ).fetchone()
        return row["id"] if row else None

    def get_wiki_pages(self, section: str | None = None) -> list[dict[str, Any]]:
        if section:
            rows = self._conn.execute(
                "SELECT * FROM documents WHERE category=? AND section_path LIKE ?",
                (CAT_WIKI, f"{section}/%"),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM documents WHERE category=?", (CAT_WIKI,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ═══ Engram ════════════════════════════════════════════════════════════

    def add_engram(self, key: str, value: str, category: str = "general") -> str:
        return self.add_document(
            title=key, content=value, domain="engram", category=CAT_ENGRAM,
            source="engram", metadata={"engram_category": category},
        )

    def search_engram(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        q_ngrams = self._compute_ngrams(query)
        q_hashes = set(self._ngram_hashes(q_ngrams))
        scores: dict[str, int] = defaultdict(int)
        for h in q_hashes:
            for did in self._engram_idx.get(h, set()):
                scores[did] += 1

        results: list[dict[str, Any]] = []
        for did, score in sorted(scores.items(), key=lambda x: -x[1])[:top_k]:
            row = self._conn.execute(
                "SELECT id, title, content, category FROM documents WHERE id=?", (did,),
            ).fetchone()
            if row:
                results.append({
                    "id": row["id"], "key": row["title"], "value": row["content"],
                    "score": round(score / max(len(q_hashes), 1), 3),
                    "category": row["category"],
                })
        return results

    # ═══ Event Entries (StructMem) ════════════════════════════════════════

    def add_event(
        self, session_id: str, role: str, content: str,
        fact_perspective: str = "", rel_perspective: str = "",
        sources: list[str] | None = None, persona_domain: str = "",
        emotional_valence: float = 0.0, memory_tier: str = "hot",
        embed: bool = False,
    ) -> str:
        ts = datetime.now(timezone.utc).isoformat()
        event_id = f"ev-{hashlib.sha1(f'{session_id}{ts}{role}'.encode()).hexdigest()[:12]}"
        if embed:
            emb = json.dumps(self._embed(content))
        else:
            emb = "[]"
        self._conn.execute(
            """INSERT OR REPLACE INTO event_entries(id, session_id, timestamp, role,
               content, fact_perspective, rel_perspective, embedding, sources,
               persona_domain, emotional_valence, memory_tier)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (event_id, session_id, ts, role, content,
             fact_perspective, rel_perspective, emb,
             json.dumps(sources or [], ensure_ascii=False),
             persona_domain, emotional_valence, memory_tier),
        )
        self._conn.commit()
        return event_id

    def bind_events(
        self, session_id: str, messages: list[dict],
        timestamp: str | None = None,
    ) -> list[str]:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        ids: list[str] = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "").strip()
            if role not in ("user", "assistant") or len(content) < 10:
                continue
            event_id = f"ev-{hashlib.sha1(f'{session_id}{ts}{role}'.encode()).hexdigest()[:12]}"
            if self._conn.execute("SELECT 1 FROM event_entries WHERE id=?", (event_id,)).fetchone():
                continue
            self._conn.execute(
                """INSERT INTO event_entries(id, session_id, timestamp, role, content)
                   VALUES (?,?,?,?,?)""",
                (event_id, session_id, ts, role, content),
            )
            ids.append(event_id)
        self._conn.commit()
        self._update_memory_tiers(session_id)
        return ids

    def get_session_events(self, session_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM event_entries WHERE session_id=? ORDER BY timestamp",
            (session_id,),
        ).fetchall()
        return [self._event_row_to_dict(r) for r in rows]

    def get_recent_events(self, limit: int = 50,
                          tier: str | None = None) -> list[dict[str, Any]]:
        if tier:
            rows = self._conn.execute(
                "SELECT * FROM event_entries WHERE memory_tier=? "
                "ORDER BY timestamp DESC LIMIT ?", (tier, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM event_entries ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._event_row_to_dict(r) for r in rows]

    def search_events(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        pattern = f"%{query}%"
        rows = self._conn.execute(
            """SELECT * FROM event_entries
               WHERE content LIKE ? OR fact_perspective LIKE ?
               ORDER BY timestamp DESC LIMIT ?""",
            (pattern, pattern, limit),
        ).fetchall()
        results: list[dict[str, Any]] = []
        for r in rows:
            d = self._event_row_to_dict(r)
            d["relevance"] = 1.0
            results.append(d)
        return results

    def _event_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for f in ("embedding", "sources"):
            try:
                d[f] = json.loads(d.get(f, "[]"))
            except (json.JSONDecodeError, TypeError):
                d[f] = [] if f == "sources" else []
        return d

    def _update_memory_tiers(self, session_id: str):
        """Age-based tier reclassification: hot(<30min), warm(<24h), cold(>24h)."""
        now = time.time()
        self._conn.execute(
            """UPDATE event_entries SET memory_tier='warm'
               WHERE session_id=? AND memory_tier='hot'
               AND ? - created_at > 1800""",
            (session_id, now),
        )
        self._conn.execute(
            """UPDATE event_entries SET memory_tier='cold'
               WHERE session_id=? AND memory_tier='warm'
               AND ? - created_at > 86400""",
            (session_id, now),
        )
        self._conn.commit()

    def prune_events(self, max_total: int = 10000):
        cnt = self._conn.execute("SELECT COUNT(*) FROM event_entries").fetchone()[0]
        if cnt <= max_total:
            return
        self._conn.execute(
            """DELETE FROM event_entries WHERE id IN (
               SELECT id FROM event_entries
               WHERE memory_tier='cold'
               ORDER BY timestamp ASC LIMIT ?)""",
            (cnt - max_total,),
        )
        self._conn.commit()

    # ═══ Synthesis Blocks ══════════════════════════════════════════════════

    def add_synthesis(
        self, content: str, source_entries: list[str] | None = None,
        session_ids: list[str] | None = None,
        model_category: str = "general", confidence: float = 0.5,
        evidence_count: int = 0,
    ) -> str:
        ts = datetime.now(timezone.utc).isoformat()
        sid = f"syn-{uuid.uuid4().hex[:12]}"
        self._conn.execute(
            """INSERT INTO synthesis_blocks(id, timestamp, content, source_entries,
               session_ids, model_category, confidence, evidence_count)
               VALUES (?,?,?,?,?,?,?,?)""",
            (sid, ts, content,
             json.dumps(source_entries or [], ensure_ascii=False),
             json.dumps(session_ids or [], ensure_ascii=False),
             model_category, confidence, evidence_count),
        )
        self._conn.commit()
        return sid

    def get_synthesis_blocks(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM synthesis_blocks ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        results: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            for f in ("source_entries", "session_ids"):
                try:
                    d[f] = json.loads(d.get(f, "[]"))
                except (json.JSONDecodeError, TypeError):
                    d[f] = []
            results.append(d)
        return results

    def retrieve_for_query(
        self, query: str, top_k_events: int = 60,
        n_synthesis: int = 5,
    ) -> dict[str, Any]:
        events = self.search_events(query, limit=top_k_events)
        synthesis = self.get_synthesis_blocks(limit=n_synthesis)
        vec_events: list[dict[str, Any]] = []
        try:
            vec_results = self.search_vector(query, top_k=top_k_events)
            for vr in vec_results:
                vid = vr.get("id", "")
                if vid.startswith("ev-"):
                    row = self._conn.execute(
                        "SELECT * FROM event_entries WHERE id=?", (vid,),
                    ).fetchone()
                    if row:
                        d = self._event_row_to_dict(row)
                        d["vector_score"] = vr.get("vector_score", 0)
                        vec_events.append(d)
        except Exception:
            pass
        return {
            "event_entries": events,
            "synthesis_blocks": synthesis,
            "vector_events": vec_events,
        }

    # ═══ Mental Models & Opinions ══════════════════════════════════════════

    def store_opinion(
        self, text: str, category: str = "general",
        confidence: float = 0.5, evidence_count: int = 0,
        sources: list[str] | None = None,
    ) -> str:
        return self.add_document(
            title=text[:80], content=text, domain="opinion",
            category=CAT_MEMORY,
            metadata={
                "opinion_text": text, "opinion_category": category,
                "confidence": confidence, "evidence_count": evidence_count,
                "sources": sources or [],
            },
        )

    def get_opinions(self, category: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if category:
            rows = self._conn.execute(
                """SELECT * FROM documents WHERE domain='opinion'
                   AND json_extract(metadata, '$.opinion_category')=?
                   ORDER BY updated_at DESC LIMIT ?""",
                (category, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM documents WHERE domain='opinion' ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ═══ Cleanup: dedup session events ═════════════════════════════════════

    def deduplicate_events(self, session_id: str):
        """Remove near-duplicate events within a session (content hash collision)."""
        seen: set[str] = set()
        dupes: list[str] = []
        rows = self._conn.execute(
            "SELECT id, content FROM event_entries WHERE session_id=? ORDER BY timestamp",
            (session_id,),
        ).fetchall()
        for r in rows:
            h = hashlib.md5(r["content"][:200].encode()).hexdigest()
            if h in seen:
                dupes.append(r["id"])
            else:
                seen.add(h)
        for did in dupes:
            self._conn.execute("DELETE FROM event_entries WHERE id=?", (did,))
        if dupes:
            self._conn.commit()
            logger.debug(f"DocumentStore: deduplicated {len(dupes)} events in {session_id}")

    # ═══ Relations ═════════════════════════════════════════════════════════

    def add_relation(self, source_id: str, target_id: str,
                     relation: str = REL_REF, weight: float = 1.0,
                     properties: dict | None = None) -> int:
        self._conn.execute(
            """INSERT OR REPLACE INTO relations(source_id, target_id, relation,
               weight, properties) VALUES (?,?,?,?,?)""",
            (source_id, target_id, relation, weight,
             json.dumps(properties or {}, ensure_ascii=False)),
        )
        self._conn.commit()
        return self._conn.lastrowid

    def get_relations(self, doc_id: str, direction: str = "both") -> list[dict]:
        rows: list[sqlite3.Row] = []
        if direction in ("outbound", "both"):
            rows += self._conn.execute(
                "SELECT * FROM relations WHERE source_id=?", (doc_id,),
            ).fetchall()
        if direction in ("inbound", "both"):
            rows += self._conn.execute(
                "SELECT * FROM relations WHERE target_id=? AND source_id!=?",
                (doc_id, doc_id),
            ).fetchall()
        results: list[dict] = []
        for r in rows:
            d = dict(r)
            d["direction"] = "outbound" if r["source_id"] == doc_id else "inbound"
            try:
                d["properties"] = json.loads(d["properties"])
            except (json.JSONDecodeError, TypeError):
                d["properties"] = {}
            results.append(d)
        return results

    def delete_relations(self, source_id: str):
        self._conn.execute(
            "DELETE FROM relations WHERE source_id=? OR target_id=?",
            (source_id, source_id),
        )
        self._conn.commit()

    # ═══ Search ════════════════════════════════════════════════════════════

    def search(self, query: str, domain: str | None = None,
               top_k: int = 10) -> list[dict[str, Any]]:
        fts_results = self.search_fts(query, domain=domain, limit=top_k * 2)
        vec_results = self.search_vector(query, top_k=top_k * 2)
        id_to_doc: dict[str, dict] = {}
        fts_ranked: list[tuple[str, int, str]] = []
        for i, doc in enumerate(fts_results):
            id_to_doc[doc["id"]] = doc
            fts_ranked.append((doc["id"], i + 1, "fts"))
        vec_ranked: list[tuple[str, int, str]] = []
        for i, doc in enumerate(vec_results):
            did = doc["id"]
            if did not in id_to_doc:
                id_to_doc[did] = doc
            vec_ranked.append((did, i + 1, "vector"))

        merged = self._rrf_merge(fts_ranked, vec_ranked)
        final: list[dict[str, Any]] = []
        for doc_id, rrf_score in merged[:top_k]:
            doc = id_to_doc.get(doc_id)
            if doc:
                doc["rrf_score"] = round(rrf_score, 4)
                doc.setdefault("fts_score", None)
                doc.setdefault("vector_score", None)
                final.append(doc)
        return final

    def search_fts(self, query: str, domain: str | None = None,
                   limit: int = 20) -> list[dict[str, Any]]:
        safe = query.replace('"', '""')
        try:
            rows = self._conn.execute(
                "SELECT rowid, rank FROM docs_fts WHERE docs_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (f'"{safe}"', limit),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = self._conn.execute(
                "SELECT rowid, 0.5 AS rank FROM documents WHERE content LIKE ? "
                "AND category='document' ORDER BY updated_at DESC LIMIT ?",
                (f"%{safe}%", limit),
            ).fetchall()

        results: list[dict[str, Any]] = []
        for r in rows:
            doc = self._conn.execute(
                "SELECT * FROM documents WHERE rowid=?", (r["rowid"],),
            ).fetchone()
            if doc:
                if domain and doc["domain"] != domain:
                    continue
                d = self._row_to_dict(doc)
                d["fts_score"] = round(1.0 / max(float(r["rank"] or 1.0), 1.0), 4)
                results.append(d)
        return results[:limit]

    def search_vector(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        try:
            qvec = self._embed(query)
            rows = self._vector_table.search(qvec).limit(top_k).to_list()
        except Exception:
            return []

        output: list[dict[str, Any]] = []
        for r in rows:
            doc_id = r.get("id", "")
            if not doc_id:
                continue
            doc = self._conn.execute(
                "SELECT * FROM documents WHERE id=?", (doc_id,),
            ).fetchone()
            if doc:
                d = self._row_to_dict(doc)
                d["vector_score"] = round(1.0 - float(r.get("_distance", 0)), 4)
                output.append(d)
            else:
                output.append({
                    "id": doc_id, "text": r.get("text", ""),
                    "vector_score": round(1.0 - float(r.get("_distance", 0)), 4),
                })
        return output

    @staticmethod
    def _rrf_merge(
        list_a: list[tuple[str, int, str]],
        list_b: list[tuple[str, int, str]],
    ) -> list[tuple[str, float]]:
        scores: dict[str, float] = defaultdict(float)
        for doc_id, rank, _ in list_a + list_b:
            scores[doc_id] += 1.0 / (RRF_K + rank)
        return sorted(scores.items(), key=lambda x: -x[1])

    # ═══ Retrieve ══════════════════════════════════════════════════════════

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM documents WHERE id=?", (doc_id,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_chunks(self, doc_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM documents WHERE doc_id=? AND category=? "
            "ORDER BY chunk_index", (doc_id, CAT_CHUNK),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_documents(self, domain: str | None = None,
                       category: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM documents WHERE 1=1"
        params: list[Any] = []
        if domain:
            sql += " AND domain=?"
            params.append(domain)
        if category:
            sql += " AND category=?"
            params.append(category)
        sql += " ORDER BY updated_at DESC"
        return [self._row_to_dict(r) for r in self._conn.execute(sql, params).fetchall()]

    # ═══ Delete ════════════════════════════════════════════════════════════

    def delete_document(self, doc_id: str):
        rowid = self._get_rowid(doc_id)
        if rowid < 0:
            return
        chunk_rows = self._conn.execute(
            "SELECT id FROM documents WHERE doc_id=?", (doc_id,),
        ).fetchall()
        for cr in chunk_rows:
            cr_rowid = self._get_rowid(cr["id"])
            if cr_rowid > 0:
                self._fts_delete(cr_rowid)
        self._conn.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
        self._fts_delete(rowid)
        self._conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        self.delete_relations(doc_id)
        try:
            self._vector_table.delete(f"id='{doc_id}'")
        except Exception:
            pass
        self._engram_idx.clear()
        self._engram_keys.pop(doc_id, None)
        self._build_engram_index()
        self._conn.commit()

    # ═══ Stats & Close ═════════════════════════════════════════════════════

    def stats(self) -> dict[str, Any]:
        total = self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunks = self._conn.execute(
            "SELECT COUNT(*) FROM documents WHERE category=?", (CAT_CHUNK,),
        ).fetchone()[0]
        wiki = self._conn.execute(
            "SELECT COUNT(*) FROM documents WHERE category=?", (CAT_WIKI,),
        ).fetchone()[0]
        engram = self._conn.execute(
            "SELECT COUNT(*) FROM documents WHERE category=?", (CAT_ENGRAM,),
        ).fetchone()[0]
        rels = self._conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        events = self._conn.execute("SELECT COUNT(*) FROM event_entries").fetchone()[0]
        synths = self._conn.execute("SELECT COUNT(*) FROM synthesis_blocks").fetchone()[0]
        hot = self._conn.execute(
            "SELECT COUNT(*) FROM event_entries WHERE memory_tier='hot'",
        ).fetchone()[0]
        warm = self._conn.execute(
            "SELECT COUNT(*) FROM event_entries WHERE memory_tier='warm'",
        ).fetchone()[0]
        cold = self._conn.execute(
            "SELECT COUNT(*) FROM event_entries WHERE memory_tier='cold'",
        ).fetchone()[0]
        vec_count = 0
        try:
            vec_count = self._vector_table.count_rows()
        except Exception:
            pass
        return {
            "total_documents": total,
            "chunks": chunks, "wiki_pages": wiki, "engram_entries": engram,
            "regular_documents": total - chunks - wiki - engram,
            "relations": rels, "vectors": vec_count,
            "event_entries": events, "synthesis_blocks": synths,
            "memory_tiers": {"hot": hot, "warm": warm, "cold": cold},
            "engram_buckets": len(self._engram_idx),
            "db_path": self._db_path, "vector_path": self._vector_path,
        }

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ═══ Singleton ══════════════════════════════════════════════════════════════

_store: Optional[DocumentStore] = None


def get_document_store(db_path: str = DB_PATH,
                       vector_path: str = VECTOR_PATH) -> DocumentStore:
    global _store
    if _store is None:
        _store = DocumentStore(db_path=db_path, vector_path=vector_path)
    return _store


__all__ = [
    "DocumentStore", "get_document_store",
    "CAT_DOC", "CAT_CHUNK", "CAT_WIKI", "CAT_MEMORY", "CAT_ENGRAM",
    "REL_REF", "REL_PREC", "REL_COOC",
]
