"""Milvus vector store backend — production-grade vector search with zero-config local option.

Integrates Vector Graph RAG (ZillizTech) design: pure vector search for graph RAG.
Supports Milvus Lite (single .db file, like SQLite), Milvus Server, and Milvus Cloud.

Usage:
    from livingtree.knowledge.milvus_store import MilvusVectorStore, MilvusEmbeddingBackend
    backend = MilvusEmbeddingBackend()            # OpenAI-compatible or local
    store = MilvusVectorStore(backend, "my_collection")  # Milvus Lite by default
    store.add_vectors([("id1", [0.1, 0.2, ...]), ...])
    results = store.search_similar(query_vec, top_k=5)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

from .vector_store import EmbeddingBackend, VectorStore, LocalEmbeddingBackend

try:
    from pymilvus import (  # type: ignore
        Collection, CollectionSchema, DataType, FieldSchema,
        MilvusClient, connections, utility,
    )
except ImportError:
    MilvusClient = None


class MilvusEmbeddingBackend(EmbeddingBackend):
    """Embedding backend using OpenAI-compatible API (text-embedding-3-large default).

    Also supports HuggingFace local models via sentence-transformers.
    Falls back to LocalEmbeddingBackend if no API configured.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-large",
        dim: int = 1536,
    ) -> None:
        self.endpoint = endpoint or os.environ.get("OPENAI_BASE_URL", "")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.dim = dim
        self._local = LocalEmbeddingBackend()

    def embed(self, texts: List[str]) -> List[List[float]]:
        if self.endpoint and self.api_key:
            try:
                import aiohttp
                import asyncio

                async def _call():
                    url = f"{self.endpoint.rstrip('/')}/embeddings"
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    }
                    payload = {"input": texts, "model": self.model}
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, json=payload, headers=headers) as resp:
                            data = await resp.json()
                            return [d["embedding"] for d in data["data"]]

                return asyncio.run(_call())
            except Exception as e:
                logger.info(f"API embedding failed: {e}, falling back to local")
        return self._local.embed(texts)


class MilvusVectorStore:
    """Milvus-backed vector store — scales to billions of vectors.

    Three modes:
      - Milvus Lite:   uri="./milvus.db"  (single file, zero config)
      - Milvus Server: uri="http://localhost:19530"
      - Milvus Cloud:  uri="https://..." + token

    Stores three collections (Vector Graph RAG design):
      - {name}_entities:   entity embeddings + metadata
      - {name}_relations:  relation embeddings + entity links
      - {name}_passages:   passage embeddings + entity/relation links
    """

    COLLECTION_TYPES = ("entities", "relations", "passages")

    def __init__(
        self,
        embedding_backend=None,
        collection_name: str = "default",
        uri: str = "",
        token: str = "",
        dim: int = 1536,
    ) -> None:
        self.collection_name = collection_name
        self.embedding_backend = embedding_backend or MilvusEmbeddingBackend(dim=dim)
        self.dim = dim

        if not uri:
            uri = str(Path(".livingtree/milvus.db").absolute())
            Path(uri).parent.mkdir(parents=True, exist_ok=True)

        self.uri = uri
        self.token = token

        self._client: Optional[MilvusClient] = None
        self._connected = False
        self._fallback: Optional[VectorStore] = None

    @property
    def client(self) -> Optional[MilvusClient]:
        if not self._ensure_connected():
            return None
        return self._client

    def _ensure_connected(self) -> bool:
        if self._connected and self._client:
            return True
        if MilvusClient is None:
            if self._fallback is None:
                logger.info("pymilvus not installed, using in-memory VectorStore fallback")
                self._fallback = VectorStore(self.embedding_backend, self.collection_name)
            return False
        try:
            if self.uri.endswith(".db"):
                self._client = MilvusClient(uri=self.uri)
            elif self.uri.startswith("http"):
                self._client = MilvusClient(uri=self.uri, token=self.token or None)
            else:
                self._client = MilvusClient(uri=self.uri, token=self.token or None)
            self._connected = True
            logger.info(f"Milvus connected: {self.uri}")
            return True
        except Exception as e:
            logger.warning(f"Milvus connection failed ({e}), using in-memory fallback")
            if self._fallback is None:
                self._fallback = VectorStore(self.embedding_backend, self.collection_name)
            return False

    def _ensure_collections(self) -> None:
        cl = self.client
        if cl is None:
            return
        for suffix in self.COLLECTION_TYPES:
            col_name = f"{self.collection_name}_{suffix}"
            if not cl.has_collection(col_name):
                schema = self._build_schema(col_name, suffix)
                cl.create_collection(collection_name=col_name, schema=schema)
                idx_params = cl.prepare_index_params()
                idx_params.add_index(
                    field_name="vector",
                    index_type="IVF_FLAT",
                    metric_type="COSINE",
                    params={"nlist": 128},
                )
                cl.create_index(collection_name=col_name, index_params=idx_params)
                logger.debug(f"Created Milvus collection: {col_name}")

    @staticmethod
    def _build_schema(col_name: str, col_type: str) -> CollectionSchema:
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=256),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=1536),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        ]
        if col_type == "relations":
            fields.append(FieldSchema(name="entity_ids", dtype=DataType.VARCHAR, max_length=65535))
        elif col_type == "passages":
            fields.append(FieldSchema(name="entity_ids", dtype=DataType.VARCHAR, max_length=65535))
            fields.append(FieldSchema(name="relation_ids", dtype=DataType.VARCHAR, max_length=65535))
        return CollectionSchema(fields=fields, description=f"Vector Graph RAG: {col_name}")

    def embed(self, text: str) -> list[float]:
        vecs = self.embedding_backend.embed([text])
        return vecs[0]

    def add_vectors(
        self,
        items: list[tuple[str, list[float]]],
        collection_suffix: str = "passages",
        metadata: Optional[dict] = None,
    ) -> None:
        meta = metadata or {}
        cl = self.client
        if cl is None:
            if self._fallback:
                self._fallback.add_vectors(items)
            return
        self._ensure_collections()
        col_name = f"{self.collection_name}_{collection_suffix}"
        data = []
        for doc_id, vec in items:
            row = {
                "id": doc_id,
                "vector": vec,
                "text": meta.get("text", doc_id),
            }
            if collection_suffix == "relations":
                row["entity_ids"] = json.dumps(meta.get("entity_ids", []))
            elif collection_suffix == "passages":
                row["entity_ids"] = json.dumps(meta.get("entity_ids", []))
                row["relation_ids"] = json.dumps(meta.get("relation_ids", []))
            data.append(row)
        cl.insert(collection_name=col_name, data=data)
        cl.flush(collection_name=col_name)

    def search_similar(
        self, query_vec: list[float], top_k: int = 5,
        collection_suffix: str = "passages",
    ) -> list[str]:
        cl = self.client
        if cl is None:
            if self._fallback:
                return self._fallback.search_similar(query_vec, top_k)
            return []
        self._ensure_collections()
        col_name = f"{self.collection_name}_{collection_suffix}"
        results = cl.search(
            collection_name=col_name,
            data=[query_vec],
            limit=top_k,
            output_fields=["id", "text"],
        )
        if results:
            return [r["id"] for r in results[0] if r.get("id")]
        return []

    def search_similar_with_meta(
        self, query_vec: list[float], top_k: int = 5,
        collection_suffix: str = "passages",
    ) -> list[dict]:
        """Search and return full metadata (id, text, entity_ids, relation_ids, score)."""
        cl = self.client
        if cl is None:
            return []
        self._ensure_collections()
        col_name = f"{self.collection_name}_{collection_suffix}"
        output_fields = ["id", "text"]
        if collection_suffix == "relations":
            output_fields.append("entity_ids")
        elif collection_suffix == "passages":
            output_fields += ["entity_ids", "relation_ids"]
        try:
            results = cl.search(
                collection_name=col_name,
                data=[query_vec],
                limit=top_k,
                output_fields=output_fields,
            )
            if results:
                return [
                    {
                        "id": r.get("id", ""),
                        "distance": r.get("distance", 0),
                        **{k: r.get(k, "") for k in output_fields if k != "id"},
                    }
                    for r in results[0]
                ]
        except Exception:
            pass
        return []

    def get_by_ids(
        self, ids: list[str], collection_suffix: str = "passages",
    ) -> list[dict]:
        """Fetch entities/relations/passages by ID — enables subgraph expansion."""
        cl = self.client
        if cl is None:
            return []
        col_name = f"{self.collection_name}_{collection_suffix}"
        try:
            results = cl.get(
                collection_name=col_name,
                ids=ids,
                output_fields=["*"],
            )
            return results if results else []
        except Exception:
            return []

    def delete_vector(self, doc_id: str, collection_suffix: str = "passages") -> None:
        cl = self.client
        if cl is None:
            if self._fallback:
                self._fallback.delete_vector(doc_id)
            return
        col_name = f"{self.collection_name}_{collection_suffix}"
        try:
            cl.delete(collection_name=col_name, ids=[doc_id])
        except Exception:
            pass

    def create_collection(self, name: str) -> None:
        self.collection_name = name
        self._ensure_collections()

    def count(self, collection_suffix: str = "passages") -> int:
        cl = self.client
        if cl is None:
            return len(self._fallback._vectors) if self._fallback else 0
        col_name = f"{self.collection_name}_{collection_suffix}"
        try:
            stats = cl.get_collection_stats(collection_name=col_name)
            return stats.get("row_count", 0)
        except Exception:
            return 0

    def drop_collections(self) -> None:
        cl = self.client
        if cl is None:
            return
        for suffix in self.COLLECTION_TYPES:
            col_name = f"{self.collection_name}_{suffix}"
            try:
                if cl.has_collection(col_name):
                    cl.drop_collection(collection_name=col_name)
            except Exception:
                pass


def get_milvus_store(
    collection_name: str = "default",
    uri: str = "",
    token: str = "",
) -> MilvusVectorStore:
    """Get a MilvusVectorStore instance — Milvus Lite by default."""
    return MilvusVectorStore(
        collection_name=collection_name,
        uri=uri or os.environ.get("MILVUS_URI", ""),
        token=token or os.environ.get("MILVUS_TOKEN", ""),
    )


__all__ = ["MilvusVectorStore", "MilvusEmbeddingBackend", "get_milvus_store"]
