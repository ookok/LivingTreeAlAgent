"""Knowledge management — bi-temporal documents with as-of queries.

Core concept: "曾经为真" ≠ "当前为真"

Bi-temporal model:
- valid_from/valid_to: when the knowledge is applicable in the real world
- created_at/updated_at: when the record was stored in the system

as_of query: search as if you were standing at a specific point in time.

Policy layer: Genome.expressed_genes controls which knowledge domains are visible.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Optional
from abc import ABC, abstractmethod

from loguru import logger
from pydantic import BaseModel, Field


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
        return doc_id

    def search(self, vector_query: str, top_k: int = 5,
               as_of: Optional[datetime] = None,
               domain: Optional[str] = None) -> list[Document]:
        """Bi-temporal + policy-aware semantic search.

        Args:
            vector_query: semantic search query
            top_k: max results
            as_of: time-point filter (None = current only)
            domain: optional domain filter

        Only returns documents:
        1. Valid at the given `as_of` time (bi-temporal)
        2. In domains enabled by Genome expressed_genes (policy)
        """
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
