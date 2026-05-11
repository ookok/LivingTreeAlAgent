"""Knowledge management — bi-temporal documents with as-of queries.

Core concept: "曾经为真" ≠ "当前为真"

Bi-temporal model:
- valid_from/valid_to: when the knowledge is applicable in the real world
- created_at/updated_at: when the record was stored in the system

as_of query: search as if you were standing at a specific point in time.

Policy layer: Genome.expressed_genes controls which knowledge domains are visible.

Hindsight-inspired fusion (v2):
- Reciprocal Rank Fusion (RRF) from vectorize-io/hindsight
- Strongly-typed retrieval data chain: RetrievalResult → MergedCandidate → ScoredResult
- Multi-source parallel async retrieval
- Token-budget truncation (not hard top-K)
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import re
import uuid
from dataclasses import dataclass, field as dc_field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from abc import ABC, abstractmethod

from loguru import logger


# ══════════════════════════════════════════════════════════════════════
# sql-flow Pattern 3: Dynamic Schema Inference
# ══════════════════════════════════════════════════════════════════════

class InferredFieldType(str, Enum):
    STR = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    DATE = "date"
    LIST = "list"
    DICT = "dict"
    UNKNOWN = "unknown"


@dataclass
class InferredField:
    name: str
    dtype: InferredFieldType
    nullable: bool = False
    sample_count: int = 0
    null_count: int = 0
    sample_values: list[Any] = dc_field(default_factory=list)

    @property
    def null_ratio(self) -> float:
        return self.null_count / max(self.sample_count, 1)


@dataclass
class InferredSchema:
    """Auto-detected schema from data — sql-flow dynamic schema inference."""
    name: str
    fields: list[InferredField] = dc_field(default_factory=list)
    sample_count: int = 0
    inferred_at: str = ""
    source: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "fields": [{"name": f.name, "type": f.dtype.value, "nullable": f.nullable,
                        "null_ratio": round(f.null_ratio, 3)}
                       for f in self.fields],
            "sample_count": self.sample_count,
            "inferred_at": self.inferred_at,
            "source": self.source,
        }

    def create_table_sql(self) -> str:
        """Generate CREATE TABLE SQL from inferred schema."""
        cols = []
        for f in self.fields:
            sql_type = {
                InferredFieldType.STR: "TEXT", InferredFieldType.INT: "INTEGER",
                InferredFieldType.FLOAT: "REAL", InferredFieldType.BOOL: "INTEGER",
                InferredFieldType.DATE: "TEXT", InferredFieldType.LIST: "TEXT",
                InferredFieldType.DICT: "TEXT", InferredFieldType.UNKNOWN: "TEXT",
            }
            nullable = "" if f.nullable else " NOT NULL"
            cols.append(f"{f.name} {sql_type[f.dtype]}{nullable}")
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', self.name)
        return f"CREATE TABLE IF NOT EXISTS {safe_name} ({', '.join(cols)});"


class SchemaInferrer:
    """Auto-detect entity structure from data samples — no pre-defined schema needed.

    sql-flow: JSON input → table auto-creation via DuckDB
    LivingTree: document/JSON data → auto-classify entity types → register in glossary
    """

    MAX_FIELD_VALUES = 5

    def infer(self, docs: list[dict], name: str = "auto_schema",
              source: str = "unknown") -> InferredSchema:
        """Infer schema from a batch of documents."""
        schema = InferredSchema(
            name=name, sample_count=len(docs),
            inferred_at=datetime.now().isoformat(), source=source)

        if not docs:
            return schema

        # Collect all field names
        all_fields: dict[str, dict] = {}
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            for key, value in doc.items():
                if key not in all_fields:
                    all_fields[key] = {"types": set(), "nulls": 0, "samples": [], "count": 0}
                all_fields[key]["count"] += 1
                if value is None:
                    all_fields[key]["nulls"] += 1
                else:
                    all_fields[key]["types"].add(self._infer_type(value))
                    if len(all_fields[key]["samples"]) < self.MAX_FIELD_VALUES:
                        all_fields[key]["samples"].append(value)

        # Build field list
        for fname, finfo in sorted(all_fields.items()):
            # Pick dominant type (first non-unknown)
            types = finfo["types"] - {InferredFieldType.UNKNOWN}
            dtype = next(iter(types)) if types else InferredFieldType.UNKNOWN
            field = InferredField(
                name=fname, dtype=dtype,
                nullable=finfo["nulls"] > 0,
                sample_count=finfo["count"],
                null_count=finfo["nulls"],
                sample_values=finfo["samples"],
            )
            schema.fields.append(field)

        return schema

    def infer_and_register(self, docs: list[dict], name: str,
                           glossary=None, entity_registry=None) -> InferredSchema:
        """Infer schema and automatically register new entity types."""
        schema = self.infer(docs, name, source="auto_infer")

        if glossary:
            for field in schema.fields:
                try:
                    glossary.register(
                        term=field.name,
                        category="inferred_field",
                        definition=f"Auto-inferred from {name}: {field.dtype.value}",
                        priority=0.3,
                    )
                except Exception:
                    pass

        if entity_registry and schema.fields:
            try:
                entity_registry.register(
                    name=name, namespace="inferred",
                    entity_type="schema",
                    source="schema_inferrer",
                    metadata=schema.to_dict(),
                )
            except Exception:
                pass

        return schema

    @staticmethod
    def _infer_type(value: Any) -> InferredFieldType:
        if isinstance(value, bool):
            return InferredFieldType.BOOL
        if isinstance(value, int):
            return InferredFieldType.INT
        if isinstance(value, float):
            return InferredFieldType.FLOAT
        if isinstance(value, str):
            # Check if it looks like a date
            if re.match(r'\d{4}-\d{2}-\d{2}', value):
                return InferredFieldType.DATE
            return InferredFieldType.STR
        if isinstance(value, (list, tuple)):
            return InferredFieldType.LIST
        if isinstance(value, dict):
            return InferredFieldType.DICT
        return InferredFieldType.UNKNOWN


# Global schema inferrer
SCHEMA_INFERRER = SchemaInferrer()
from pydantic import BaseModel, Field


# ── Hindsight-inspired retrieval data chain ──
# vectorize-io/hindsight uses a three-tier dataclass chain:
#   RetrievalResult → MergedCandidate (RRF) → ScoredResult (rerank + temporal)

@dataclass
class RetrievalResult:
    """Raw result from a single retrieval source (semantic, keyword, graph, etc.)."""
    doc_id: str
    source: str                      # "semantic", "keyword", "graph", "temporal"
    rank: int                        # Position in source's ranked list (1-indexed)
    score: float                     # Source-specific score (not normalized)
    document: Document | None = None  # Resolved document if available
    metadata: dict[str, Any] = dc_field(default_factory=dict)


@dataclass
class MergedCandidate:
    """Document merged from multiple retrieval sources via RRF (Reciprocal Rank Fusion).

    RRF formula: score(d) = Σ 1/(k + rank_i(d)) where k=60, i ranges over sources.
    """
    doc_id: str
    rrf_score: float                 # Fused RRF score
    source_ranks: dict[str, int] = dc_field(default_factory=dict)  # {source: rank}
    source_scores: dict[str, float] = dc_field(default_factory=dict)
    document: Document | None = None

    @property
    def source_count(self) -> int:
        return len(self.source_ranks)


@dataclass
class ScoredResult:
    """Final scored result after RRF fusion + optional rerank + temporal weighting."""
    doc_id: str
    final_score: float               # Combined score
    rrf_score: float                 # Original RRF score
    rerank_score: float = 0.0        # Cross-encoder score (if available)
    recency_boost: float = 0.0       # Temporal freshness boost
    source_count: int = 0
    document: Document | None = None
    metadata: dict[str, Any] = dc_field(default_factory=dict)


@dataclass
class FusionResult:
    """Complete result of multi-source retrieval + RRF fusion pipeline."""
    query: str
    results: list[ScoredResult]
    total_candidates: int            # Raw candidates before fusion
    merged_candidates: list[MergedCandidate] = dc_field(default_factory=list)
    fusion_stats: dict[str, Any] = dc_field(default_factory=dict)


class Document(BaseModel):
    """A knowledge document with bi-temporal validity tracking.

    Bi-temporal:
    - valid_from / valid_to: real-world applicability window
    - created_at / updated_at: system record timestamps

    valid_from=None means "always valid from the beginning"
    valid_to=None means "valid indefinitely"
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str
    domain: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Bi-temporal validity window
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None

    # Record timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Provenance
    source: str = "manual"
    author: str = "system"
    revision: int = 1

    def is_valid_at(self, as_of: Optional[datetime] = None) -> bool:
        """Check if this document is valid at a given point in time.

        None = now (current validity only).
        """
        now = datetime.utcnow()
        point = as_of or now
        if self.valid_from and point < self.valid_from:
            return False
        if self.valid_to and point > self.valid_to:
            return False
        return True

    def current(self) -> bool:
        """Is this the current version of the knowledge?"""
        return self.is_valid_at(None)


class StorageBackend(ABC):
    @abstractmethod
    def connect(self) -> None: ...
    @abstractmethod
    def add_document(self, doc: Document) -> str: ...
    @abstractmethod
    def get_document(self, id: str) -> Optional[Document]: ...
    @abstractmethod
    def update_document(self, doc: Document) -> None: ...
    @abstractmethod
    def delete_document(self, id: str) -> None: ...
    @abstractmethod
    def list_documents(self) -> list[Document]: ...
    @abstractmethod
    def search_as_of(self, as_of: Optional[datetime] = None,
                     domain: Optional[str] = None) -> list[Document]: ...


class SQLiteBackend(StorageBackend):
    def __init__(self, db_path: str = ":memory:"):
        self._path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # WAL mode for concurrent reads + faster writes
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-8000")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, title TEXT, content TEXT, domain TEXT,
                metadata TEXT, valid_from TEXT, valid_to TEXT,
                created_at TEXT, updated_at TEXT, source TEXT DEFAULT 'manual',
                author TEXT DEFAULT 'system', revision INTEGER DEFAULT 1
            )
        """)
        self._conn.commit()

    def add_document(self, doc: Document) -> str:
        if not self._conn:
            self.connect()
        self._conn.execute(
            "INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (doc.id, doc.title, doc.content, doc.domain, json.dumps(doc.metadata),
             doc.valid_from.isoformat() if doc.valid_from else None,
             doc.valid_to.isoformat() if doc.valid_to else None,
             doc.created_at.isoformat(), doc.updated_at.isoformat(),
             doc.source, doc.author, doc.revision),
        )
        self._conn.commit()
        return doc.id

    def _row_to_doc(self, row: sqlite3.Row) -> Document:
        def parse_dt(val: Optional[str]) -> Optional[datetime]:
            return datetime.fromisoformat(val) if val else None

        return Document(
            id=row["id"], title=row["title"], content=row["content"],
            domain=row["domain"], metadata=json.loads(row["metadata"] or "{}"),
            valid_from=parse_dt(row["valid_from"]),
            valid_to=parse_dt(row["valid_to"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            source=row["source"] or "manual",
            author=row["author"] or "system",
            revision=row["revision"] or 1,
        )

    def get_document(self, id: str) -> Optional[Document]:
        if not self._conn:
            self.connect()
        row = self._conn.execute("SELECT * FROM documents WHERE id=?", (id,)).fetchone()
        return self._row_to_doc(row) if row else None

    def update_document(self, doc: Document) -> None:
        if not self._conn:
            self.connect()
        doc.updated_at = datetime.utcnow()
        doc.revision += 1
        self._conn.execute(
            "UPDATE documents SET title=?,content=?,domain=?,metadata=?,"
            "valid_from=?,valid_to=?,updated_at=?,revision=? WHERE id=?",
            (doc.title, doc.content, doc.domain, json.dumps(doc.metadata),
             doc.valid_from.isoformat() if doc.valid_from else None,
             doc.valid_to.isoformat() if doc.valid_to else None,
             doc.updated_at.isoformat(), doc.revision, doc.id),
        )
        self._conn.commit()

    def delete_document(self, id: str) -> None:
        if not self._conn:
            self.connect()
        self._conn.execute("DELETE FROM documents WHERE id=?", (id,))
        self._conn.commit()

    def list_documents(self) -> list[Document]:
        if not self._conn:
            self.connect()
        rows = self._conn.execute("SELECT * FROM documents").fetchall()
        return [self._row_to_doc(r) for r in rows]

    def search_as_of(self, as_of: Optional[datetime] = None,
                     domain: Optional[str] = None) -> list[Document]:
        """Bi-temporal search: return documents valid at `as_of` time point."""
        if not self._conn:
            self.connect()
        all_docs = [self._row_to_doc(r) for r in
                    self._conn.execute("SELECT * FROM documents").fetchall()]

        filtered = []
        for doc in all_docs:
            if domain and doc.domain != domain:
                continue
            if not doc.is_valid_at(as_of):
                continue
            filtered.append(doc)
        return filtered


class FileBackend(StorageBackend):
    def __init__(self, directory: str):
        self._dir = directory
        os.makedirs(self._dir, exist_ok=True)

    def connect(self) -> None:
        pass

    def _path_for(self, doc_id: str) -> str:
        return os.path.join(self._dir, f"{doc_id}.json")

    def add_document(self, doc: Document) -> str:
        with open(self._path_for(doc.id), "w", encoding="utf-8") as f:
            json.dump(doc.model_dump(mode="json"), f, default=str)
        return doc.id

    def get_document(self, id: str) -> Optional[Document]:
        try:
            with open(self._path_for(id), encoding="utf-8") as f:
                return Document.model_validate(json.load(f))
        except FileNotFoundError:
            return None

    def update_document(self, doc: Document) -> None:
        self.add_document(doc)

    def delete_document(self, id: str) -> None:
        try:
            os.remove(self._path_for(id))
        except FileNotFoundError:
            pass

    def list_documents(self) -> list[Document]:
        results = []
        for fn in os.listdir(self._dir):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(self._dir, fn), encoding="utf-8") as f:
                results.append(Document.model_validate(json.load(f)))
        return results

    def search_as_of(self, as_of: Optional[datetime] = None,
                     domain: Optional[str] = None) -> list[Document]:
        return [d for d in self.list_documents()
                if (not domain or d.domain == domain) and d.is_valid_at(as_of)]


import os  # noqa: E402 — needed by FileBackend above


class KnowledgeBase:
    """Bi-temporal knowledge base with policy-aware semantic search."""

    def __init__(self, storage: Optional[StorageBackend] = None,
                 vector_store: Optional["VectorStore"] = None,
                 genome: Any = None):
        self.storage: StorageBackend = storage or SQLiteBackend(":memory:")
        self.storage.connect()

        from .vector_store import VectorStore
        self.vector_store: VectorStore = vector_store or VectorStore()
        self.genome = genome
        self.dedup_enabled = True
        logger.info(f"KB: {type(self.storage).__name__} + {type(self.vector_store).__name__}")

    def add_knowledge(self, doc: Document, skip_dedup: bool = False) -> str:
        """Add knowledge with dedup check."""
        # Dedup check
        if self.dedup_enabled and not skip_dedup and len(doc.content) > 50:
            try:
                from .dedup import DedupEngine
                engine = DedupEngine(vector_store=self.vector_store, kb=self)
                result = engine.check(doc.content, content_id=doc.id,
                                      check_exact=True, check_near=True, check_semantic=False)
                if result["is_duplicate"]:
                    logger.info(f"Dedup: blocked '{doc.title}' — {result['suggestion']}")
                    return result.get("duplicate_of", doc.id)
            except Exception:
                pass

        doc_id = self.storage.add_document(doc)
        try:
            vec = self.vector_store.embed(doc.content)
            self.vector_store.add_vectors([(doc_id, vec)])
        except Exception as e:
            logger.warning(f"Vector index: {e}")

        # ── Auto-index for lazy (section-level) retrieval ──
        try:
            from .lazy_index import _global_lazy_index
            li = _global_lazy_index()
            li.index_document(doc_id, doc.title or doc_id[:30], doc.content)
        except Exception:
            logger.debug(f"LazyIndex: skipped for '{doc.title}' (not imported yet)")

        return doc_id

    def search(self, vector_query: str, top_k: int = 5,
               as_of: Optional[datetime] = None,
               domain: Optional[str] = None) -> list[Document]:
        """Bi-temporal + policy-aware semantic search with Engram O(1) priority."""

        try:
            from .engram_store import get_engram_store
            engram = get_engram_store(seed=False)
            hit = engram.lookup(vector_query)
            if hit:
                doc = Document(
                    id=f"engram-{hash(hit) % 10000}", content=hit,
                    domain=domain or "standard", valid_from=datetime.min,
                    valid_to=datetime.max, created_at=datetime.now(),
                )
                return [doc]
        except Exception:
            pass

        query_vec = self.vector_store.embed(vector_query)
        ids = self.vector_store.search_similar(query_vec, top_k * 2)
        results: list[Document] = []
        for did in ids:
            doc = self.storage.get_document(did)
            if doc and self._policy_allows(doc) and doc.is_valid_at(as_of):
                results.append(doc)
        return results[:top_k]

    def search_as_of(self, query: str, as_of: Optional[datetime] = None,
                     top_k: int = 5) -> list[Document]:
        """Convenience: bi-temporal search at a specific time point."""
        return self.search(query, top_k=top_k, as_of=as_of)

    def search_current(self, query: str, top_k: int = 5) -> list[Document]:
        """Search only currently-valid documents."""
        return self.search(query, top_k=top_k, as_of=datetime.utcnow())

    def retrieve(self, id: str) -> Optional[Document]:
        return self.storage.get_document(id)

    def update(self, doc: Document) -> None:
        self.storage.update_document(doc)
        try:
            vec = self.vector_store.embed(doc.content)
            self.vector_store.add_vectors([(doc.id, vec)])
        except Exception as e:
            logger.warning(f"Vector update: {e}")

    def delete(self, id: str) -> None:
        self.storage.delete_document(id)
        if hasattr(self.vector_store, 'delete_vector'):
            self.vector_store.delete_vector(id)

    def get_by_domain(self, domain: Optional[str] = None) -> list[Document]:
        return self.storage.search_as_of(domain=domain)

    def expired(self) -> list[Document]:
        """Find documents whose validity has expired."""
        return self.storage.search_as_of()

    def merge_knowledge(self, docs: list[Document]) -> list[str]:
        return [self.add_knowledge(d) for d in docs]

    # ── History: bi-temporal replay ──

    def history(self, domain: Optional[str] = None) -> list[Document]:
        """Return ALL documents including expired ones (for provenance)."""
        return self.storage.list_documents()

    def at_time(self, point: datetime) -> list[Document]:
        """What did the knowledge base look like at a past time point?"""
        return self.storage.search_as_of(as_of=point)

    def changes_since(self, since: datetime) -> list[Document]:
        """Documents created or updated since a given time."""
        return [d for d in self.storage.list_documents() if d.updated_at >= since]

    # ── Policy layer ──

    # ── Incremental & Regex Search (Clibor-inspired) ──

    def search_incremental(self, query: str, top_k: int = 20) -> list[Document]:
        """Incremental prefix-based search — real-time filtering as user types.

        Scores: title prefix=10, title contains=6, content prefix=8, content contains=4.
        """
        if not query:
            return []
        qlower = query.lower()
        scored: list[tuple[int, Document]] = []
        for doc in self.storage.list_documents():
            score = 0
            title_lower = doc.title.lower()
            content_lower = doc.content.lower()
            if title_lower.startswith(qlower):
                score = 10
            elif qlower in title_lower:
                score = 6
            elif content_lower[:100].startswith(qlower):
                score = 8
            elif qlower in content_lower:
                score = 4
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:top_k]]

    def search_regex(self, pattern: str, fields: list[str] | None = None,
                     top_k: int = 20) -> list[Document]:
        """Regex search across document fields.

        fields: ["title", "content", "domain"] (default: ["title", "content"])
        """
        import re as _re
        try:
            regex = _re.compile(pattern, _re.IGNORECASE)
        except _re.error as e:
            logger.warning(f"Invalid regex '{pattern}': {e}")
            return []
        targets = fields or ["title", "content"]
        results: list[Document] = []
        for doc in self.storage.list_documents():
            for field in targets:
                val = getattr(doc, field, "")
                if regex.search(val):
                    results.append(doc)
                    break
        return results[:top_k]

    def search_keyword(self, keywords: list[str], case_sensitive: bool = False,
                       top_k: int = 20) -> list[Document]:
        """Keyword-based search with logical AND between keywords.

        Supports case-sensitive/insensitive matching across title and content.
        """
        if not keywords:
            return []
        results: list[Document] = []
        for doc in self.storage.list_documents():
            text = f"{doc.title} {doc.content}"
            if not case_sensitive:
                text = text.lower()
                kw = [k.lower() for k in keywords]
            else:
                kw = keywords
            if all(k in text for k in kw):
                results.append(doc)
        return results[:top_k]

    # ── Hindsight-inspired RRF Fusion + Multi-Source Retrieval ──

    RRF_K = 60  # Default k constant for reciprocal rank fusion (from hindsight)

    def _reciprocal_rank_fusion(self, source_results: list[list[RetrievalResult]],
                                k: int | None = None) -> list[MergedCandidate]:
        """Fuse ranked results from multiple retrieval sources using RRF.

        RRF formula (vectorize-io/hindsight):
            score(d) = Σ 1/(k + rank_i(d))

        where k=60 prevents single high-rank results from dominating,
        and rank is the 1-indexed position in each source's ranked list.

        Returns merged candidates sorted by descending RRF score.
        """
        mk = k or self.RRF_K
        merged: dict[str, MergedCandidate] = {}

        for source_idx, results in enumerate(source_results):
            source_name = results[0].source if results else f"source_{source_idx}"
            for result in results:
                if result.doc_id not in merged:
                    merged[result.doc_id] = MergedCandidate(
                        doc_id=result.doc_id,
                        rrf_score=0.0,
                        source_ranks={},
                        source_scores={},
                        document=result.document,
                    )
                merged[result.doc_id].source_ranks[source_name] = result.rank
                merged[result.doc_id].source_scores[source_name] = result.score

        # Compute RRF scores
        for c in merged.values():
            c.rrf_score = sum(1.0 / (mk + rank) for rank in c.source_ranks.values())

        # Sort descending
        candidates = sorted(merged.values(), key=lambda c: c.rrf_score, reverse=True)
        return candidates

    def _collect_retrieval_results(self, docs: list[Document],
                                   source: str, rank_start: int = 1) -> list[RetrievalResult]:
        """Convert Document list to RetrievalResult list for a given source."""
        results: list[RetrievalResult] = []
        for i, doc in enumerate(docs):
            results.append(RetrievalResult(
                doc_id=doc.id,
                source=source,
                rank=rank_start + i,
                score=1.0 / (1 + i),  # Simple positional decay
                document=doc,
            ))
        return results

    async def multi_source_retrieve(self, query: str,
                                    sources: list[str] | None = None,
                                    top_k: int = 20,
                                    rrf_k: int | None = None,
                                    as_of: datetime | None = None) -> FusionResult:
        """Hindsight-style multi-source parallel retrieval with RRF fusion.

        Retrieves from semantic, keyword, incremental, and temporal sources
        in parallel (asyncio.gather), then fuses results via reciprocal rank fusion.

        Args:
            query: Search query
            sources: Which sources to use ("semantic", "keyword", "incremental", "temporal")
                     Default: ["semantic", "keyword", "incremental"]
            top_k: Max results per source
            rrf_k: RRF k constant (default: 60)
            as_of: Bi-temporal time point

        Returns:
            FusionResult with fused ScoredResults
        """
        source_names = sources or ["semantic", "keyword", "incremental"]

        # Build retrieval tasks for each source in parallel
        tasks: list[asyncio.Task] = []

        if "semantic" in source_names:
            async def _semantic():
                if as_of:
                    return self.search(query, top_k=top_k, as_of=as_of)
                return self.search(query, top_k=top_k)
            tasks.append(_semantic())

        if "keyword" in source_names:
            # Tokenize query for keyword search (from hindsight tokenize_query pattern)
            keywords = query.lower().split()
            words = [w for w in keywords if len(w) > 2 and w not in
                     ("the", "and", "for", "are", "was", "that", "this", "with",
                      "from", "have", "has", "had", "not", "but")]
            async def _keyword():
                return self.search_keyword(words[:6], top_k=top_k)
            tasks.append(_keyword())

        if "incremental" in source_names:
            async def _incremental():
                return self.search_incremental(query, top_k=top_k)
            tasks.append(_incremental())

        if "temporal" in source_names:
            async def _temporal():
                docs = self.storage.list_documents()
                docs.sort(key=lambda d: d.updated_at if d.updated_at else d.created_at, reverse=True)
                return docs[:top_k]
            tasks.append(_temporal())

        # Parallel execution (hindsight uses asyncio.gather for 4-way retrieval)
        source_results_raw: list[list[Document]] = await asyncio.gather(*tasks)
        logger.info(f"Multi-source retrieval: {len(source_names)} sources → {sum(len(r) for r in source_results_raw)} raw results")

        # Convert each source's results to RetrievalResult lists
        retrieval_sources: list[list[RetrievalResult]] = []
        for src_name, docs in zip(source_names, source_results_raw):
            if docs:
                retrieval_sources.append(
                    self._collect_retrieval_results(docs, source=src_name))

        if not retrieval_sources:
            return FusionResult(query=query, results=[], total_candidates=0)

        # RRF fusion
        merged = self._reciprocal_rank_fusion(retrieval_sources, k=rrf_k)

        # Token-budget driven selection (not top-K — hindsight trims by token budget)
        scored: list[ScoredResult] = []
        total_chars = 0
        budget_chars = 8000  # ~2K tokens, adjustable

        for mc in merged:
            if total_chars >= budget_chars:
                break
            doc_content = ""
            if mc.document:
                doc_content = mc.document.content
            scored.append(ScoredResult(
                doc_id=mc.doc_id,
                final_score=mc.rrf_score,
                rrf_score=mc.rrf_score,
                source_count=mc.source_count,
                document=mc.document,
            ))
            total_chars += len(doc_content)

        # Recency boost: up-rank documents updated within 7 days
        now = datetime.now()
        for sr in scored:
            if sr.document and sr.document.updated_at:
                age_days = (now - sr.document.updated_at).days
                if age_days < 7:
                    sr.recency_boost = 0.2 * (1 - age_days / 7)
                    sr.final_score += sr.recency_boost

        # Re-sort after recency boost
        scored.sort(key=lambda s: s.final_score, reverse=True)

        # OKH-RAG: Order-aware reranking (sequence coherence)
        try:
            from .order_aware_reranker import get_order_aware_reranker
            reranker = get_order_aware_reranker()
            oa_result = reranker.rerank(
                scored, query, blend_weight=0.25, min_order_confidence=0.3,
            )
            if oa_result.order_confidence >= 0.3:
                scored = oa_result.reranked_docs
                reranker.learn_from_retrieved(scored, query)
        except Exception:
            pass

        return FusionResult(
            query=query,
            results=scored[:top_k],
            total_candidates=sum(len(s) for s in retrieval_sources),
            merged_candidates=merged,
            fusion_stats={
                "sources_used": source_names,
                "rrf_k": rrf_k or self.RRF_K,
                "merged_count": len(merged),
                "final_count": len(scored),
                "budget_chars": budget_chars,
                "order_aware": True,
            },
        )

    # ── RuView-inspired Attention-Weighted Fusion ──

    def _text_to_vec(self, text: str, dim: int = 128) -> list[float]:
        """Lightweight TF-IDF hash embedding (RuView: signal → vector encoding).

        Maps text to a fixed-dim embedding for query-source attention computation.
        Uses character n-gram hashing — no external model needed.
        """
        if not text:
            return [0.0] * dim
        import hashlib
        vec = [0.0] * dim
        text_lower = text.lower()
        # Char 3-grams for Chinese + English robustness
        for i in range(0, len(text_lower) - 2, 2):
            gram = text_lower[i:i+3]
            h = int(hashlib.md5(gram.encode()).hexdigest()[:8], 16)
            vec[h % dim] += 1.0
        # Normalize
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def _cosine_sim(self, a: list[float], b: list[float]) -> float:
        """Cosine similarity between two vectors."""
        if not a or not b:
            return 0.0
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return max(0.0, min(1.0, dot / (na * nb)))

    _SOURCE_SPECIALTIES: dict[str, str] = {
        "semantic": "conceptual meaning semantic understanding deep knowledge abstraction",
        "keyword": "exact match literal query term precision specific words",
        "incremental": "real-time prefix partial dynamic streaming current recent",
        "temporal": "time-based recency freshness newest latest most-recent chronological",
    }

    def _attention_weighted_fusion(
        self, query: str,
        source_results: list[list[RetrievalResult]],
        rrf_k: int = 60,
    ) -> list[MergedCandidate]:
        """Attention-weighted reciprocal rank fusion (RuView multi-band pattern).

        Standard RRF treats all sources equally: score(d) = Σ 1/(k + rank_i(d)).
        Attention-weighted RRF weights each source's contribution by its query relevance:

            score(d) = Σ attention_weight(source_i) / (k + rank_i(d))

        where attention_weight = softmax(cosine_sim(query_vec, source_specialty_vec)).
        This ensures the fusion prioritizes sources most relevant to the current query
        (RuView: Flash Attention across subcarrier groups → spatial focus regions).
        """
        query_vec = self._text_to_vec(query)

        # Compute source attention weights via cosine similarity
        source_names = [r[0].source if r else f"source_{i}"
                        for i, r in enumerate(source_results)]
        raw_weights: list[float] = []
        for src_name in source_names:
            specialty = self._SOURCE_SPECIALTIES.get(src_name, src_name)
            src_vec = self._text_to_vec(specialty)
            sim = self._cosine_sim(query_vec, src_vec)
            raw_weights.append(sim)

        # Softmax normalization (with temperature for sharper distinction)
        temperature = 0.5
        max_w = max(raw_weights) if raw_weights else 0.0
        exp_weights = [pow(2.71828, (w - max_w) / temperature) for w in raw_weights]
        sum_exp = sum(exp_weights) or 1.0
        attention_weights = [ew / sum_exp for ew in exp_weights]

        # Attention-weighted RRF
        merged: dict[str, MergedCandidate] = {}
        for src_idx, results in enumerate(source_results):
            src_weight = attention_weights[src_idx] if src_idx < len(attention_weights) else 0.2
            src_name = source_names[src_idx]
            for result in results:
                if result.doc_id not in merged:
                    merged[result.doc_id] = MergedCandidate(
                        doc_id=result.doc_id,
                        rrf_score=0.0,
                        source_ranks={},
                        source_scores={},
                        document=result.document,
                    )
                merged[result.doc_id].source_ranks[src_name] = result.rank
                merged[result.doc_id].source_scores[src_name] = result.score

        # Weighted RRF: w_i / (k + rank)
        for c in merged.values():
            weighted_sum = 0.0
            for src_idx, src_name in enumerate(source_names):
                rank = c.source_ranks.get(src_name)
                if rank is not None:
                    w = attention_weights[src_idx] if src_idx < len(attention_weights) else 0.2
                    weighted_sum += w / (rrf_k + rank)
            c.rrf_score = weighted_sum

        candidates = sorted(merged.values(), key=lambda c: c.rrf_score, reverse=True)
        return candidates, dict(zip(source_names, attention_weights))

    def _compute_attention_weights(self, query: str, sources: list[str]) -> dict[str, float]:
        """Compute per-source attention weights for a query (standalone).

        Useful for pre-fusion source filtering: skip sources with weight < 0.1.
        """
        query_vec = self._text_to_vec(query)
        weights: dict[str, float] = {}
        for src in sources:
            specialty = self._SOURCE_SPECIALTIES.get(src, src)
            src_vec = self._text_to_vec(specialty)
            weights[src] = self._cosine_sim(query_vec, src_vec)
        # Normalize
        total = sum(weights.values()) or 1.0
        return {s: w / total for s, w in weights.items()}

    def multi_source_retrieve_sync(self, query: str,
                                   sources: list[str] | None = None,
                                   top_k: int = 20,
                                   rrf_k: int | None = None) -> FusionResult:
        """Synchronous wrapper for multi_source_retrieve."""
        return asyncio.run(self.multi_source_retrieve(
            query, sources=sources, top_k=top_k, rrf_k=rrf_k))

    def _policy_allows(self, doc: Document) -> bool:
        """Check if the document's domain is allowed by genome policy."""
        if not self.genome:
            return True
        genes = getattr(self.genome, 'expressed_genes', None)
        if not genes:
            return True
        domain_map = {
            "eia": genes.dna_engine,
            "emergency": genes.dna_engine,
            "finance": genes.knowledge_layer,
            "code": genes.capability_layer,
            "general": True,
        }
        return domain_map.get(doc.domain, True)


__all__ = ["Document", "StorageBackend", "SQLiteBackend", "FileBackend", "KnowledgeBase"]
