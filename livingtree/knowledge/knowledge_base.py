"""Central knowledge management for LivingTree.

This module provides a lightweight, pluggable knowledge base with:
- Document model (via Pydantic)
- Abstract storage backend with optional SQLite/File/Redis implementations
- Vector store integration for semantic search
- Basic CRUD and domain-scoped queries
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple
from abc import ABC, abstractmethod

from loguru import logger
from pydantic import BaseModel, Field


class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str
    domain: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StorageBackend(ABC):
    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def add_document(self, doc: Document) -> str:
        pass

    @abstractmethod
    def get_document(self, id: str) -> Optional[Document]:
        pass

    @abstractmethod
    def update_document(self, doc: Document) -> None:
        pass

    @abstractmethod
    def delete_document(self, id: str) -> None:
        pass

    @abstractmethod
    def get_documents_by_domain(self, domain: Optional[str]) -> List[Document]:
        pass

    @abstractmethod
    def list_documents(self) -> List[Document]:
        pass


class SQLiteBackend(StorageBackend):
    """Simple SQLite-based storage backend for Documents."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        cur = self._conn.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            title TEXT,
            content TEXT,
            domain TEXT,
            metadata TEXT,
            created_at TEXT
        )"""
        )
        self._conn.commit()

    def add_document(self, doc: Document) -> str:
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO documents (id, title, content, domain, metadata, created_at) VALUES (?,?,?,?,?,?)",
            (
                doc.id,
                doc.title,
                doc.content,
                doc.domain,
                json.dumps(doc.metadata),
                doc.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        return doc.id

    def _row_to_doc(self, row: sqlite3.Row) -> Document:
        return Document(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            domain=row["domain"],
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def get_document(self, id: str) -> Optional[Document]:
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM documents WHERE id = ?", (id,))
        row = cur.fetchone()
        return self._row_to_doc(row) if row else None

    def update_document(self, doc: Document) -> None:
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE documents SET title=?, content=?, domain=?, metadata=?, created_at=? WHERE id=?",
            (
                doc.title,
                doc.content,
                doc.domain,
                json.dumps(doc.metadata),
                doc.created_at.isoformat(),
                doc.id,
            ),
        )
        self._conn.commit()

    def delete_document(self, id: str) -> None:
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        cur.execute("DELETE FROM documents WHERE id = ?", (id,))
        self._conn.commit()

    def get_documents_by_domain(self, domain: Optional[str]) -> List[Document]:
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        if domain:
            cur.execute("SELECT * FROM documents WHERE domain = ?", (domain,))
        else:
            cur.execute("SELECT * FROM documents")
        rows = cur.fetchall()
        return [self._row_to_doc(r) for r in rows]

    def list_documents(self) -> List[Document]:
        return self.get_documents_by_domain(None)


class FileBackend(StorageBackend):
    """Simple file-based storage backend (one JSON per document)."""

    def __init__(self, directory: str):
        import os
        self._dir = directory
        os.makedirs(self._dir, exist_ok=True)

    def connect(self) -> None:
        pass

    def _path_for(self, doc_id: str) -> str:
        import os
        return os.path.join(self._dir, f"{doc_id}.json")

    def add_document(self, doc: Document) -> str:
        path = self._path_for(doc.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc.dict(), f, default=str)
        return doc.id

    def get_document(self, id: str) -> Optional[Document]:
        path = self._path_for(id)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Document.parse_obj(data)
        except FileNotFoundError:
            return None

    def update_document(self, doc: Document) -> None:
        self.add_document(doc)

    def delete_document(self, id: str) -> None:
        import os
        try:
            os.remove(self._path_for(id))
        except FileNotFoundError:
            pass

    def get_documents_by_domain(self, domain: Optional[str]) -> List[Document]:
        import os
        results: List[Document] = []
        for fname in os.listdir(self._dir):
            if not fname.endswith('.json'):
                continue
            with open(os.path.join(self._dir, fname), 'r', encoding='utf-8') as f:
                data = json.load(f)
                doc = Document.parse_obj(data)
                if domain is None or doc.domain == domain:
                    results.append(doc)
        return results

    def list_documents(self) -> List[Document]:
        return self.get_documents_by_domain(None)


class KnowledgeBase:
    """High-level API for storing, indexing and querying knowledge."""

    def __init__(self, storage: Optional[StorageBackend] = None, vector_store: Optional["VectorStore"] = None) -> None:
        self.storage: StorageBackend
        if storage is None:
            # Default to in-memory SQLite for portability; this is lightweight for demos
            self.storage = SQLiteBackend(db_path=":memory:")
        else:
            self.storage = storage
        self.storage.connect()

        from .vector_store import VectorStore
        self.vector_store: VectorStore = vector_store or VectorStore()

        logger.info("KnowledgeBase initialized with storage backend: %s and vector store: %s",
                    type(self.storage).__name__, type(self.vector_store).__name__)

    # ----- CRUD / Query API -----
    def add_knowledge(self, doc: Document) -> str:
        # Persist document
        doc_id = self.storage.add_document(doc)
        # Index via vector store
        try:
            vec = self.vector_store.embed(doc.content)
            self.vector_store.add_vectors([(doc_id, vec)])
        except Exception as e:
            logger.warning("Vector indexing failed for document %s: %s", doc_id, e)
        return doc_id

    def search(self, vector_query: str, top_k: int = 5) -> List[Document]:
        query_vec = self.vector_store.embed(vector_query)
        ids = self.vector_store.search_similar(query_vec, top_k)
        results: List[Document] = []
        for did in ids:
            doc = self.storage.get_document(did)
            if doc:
                results.append(doc)
        return results

    def retrieve(self, id: str) -> Optional[Document]:
        return self.storage.get_document(id)

    def update(self, doc: Document) -> None:
        self.storage.update_document(doc)
        try:
            vec = self.vector_store.embed(doc.content)
            self.vector_store.add_vectors([(doc.id, vec)])
        except Exception as e:
            logger.warning("Vector update failed for document %s: %s", doc.id, e)

    def delete(self, id: str) -> None:
        self.storage.delete_document(id)
        self.vector_store.delete_vector(id) if hasattr(self.vector_store, 'delete_vector') else None

    def get_by_domain(self, domain: Optional[str]) -> List[Document]:
        return self.storage.get_documents_by_domain(domain)

    def merge_knowledge(self, docs: List[Document]) -> List[str]:
        ids: List[str] = []
        for d in docs:
            ids.append(self.add_knowledge(d))
        return ids


__all__ = ["Document", "StorageBackend", "SQLiteBackend", "FileBackend", "KnowledgeBase"]
