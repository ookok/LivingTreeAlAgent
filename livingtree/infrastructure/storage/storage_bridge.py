"""Storage bridge — connect DisCoGC to existing LivingTree cache layers.

Provides adapters that wrap existing LivingTree cache modules
with DisCoGC-compatible StorageBackend interfaces, enabling
zero-copy discard + compaction GC for:

  - L2 LocalCache (SQLite conversation_cache)
  - L3 SemanticCache (FAISS vector index)
  - L1 MemoryCache (in-memory dict)
  - KnowledgeBase (struct_mem SQLite)

Usage:
    from livingtree.infrastructure.storage import storage_bridge

    bridge = storage_bridge.wrap_local_cache(db_path="~/.hermes-desktop/cache/conversation.db")
    disco = bridge.get_disco_gc()
    disco.start_background(interval_seconds=600)
"""

from __future__ import annotations

import threading
from typing import Optional, Dict, Any

from loguru import logger

from .storage_config import GCConfig, GCPolicy
from .disco_gc import DisCoGC, get_disco_gc
from .backends.sqlite_backend import SQLiteStorageBackend
from .backends.memory_backend import InMemoryStorageBackend
from .backends.faiss_backend import FAISSStorageBackend


class StorageBridge:
    """Bridges LivingTree cache layers to DisCoGC storage backends.

    Maintains a registry of wrapped backends and their DisCoGC instances,
    providing a unified interface for background GC across all storage layers.
    """

    def __init__(self):
        self._backends: Dict[str, DisCoGC] = {}
        self._lock = threading.Lock()

    def wrap_sqlite(
        self,
        db_path: str,
        table_name: str = "conversation_cache",
        ttl_seconds: int = 86400,
        gc_config: Optional[GCConfig] = None,
    ) -> DisCoGC:
        """Wrap an existing SQLite cache table with DisCoGC."""
        backend = SQLiteStorageBackend(
            db_path=db_path,
            table_name=table_name,
            ttl_seconds=ttl_seconds,
        )
        return self._register_backend(backend, gc_config)

    def wrap_memory_cache(
        self,
        ttl_seconds: int = 900,
        max_entries: int = 10000,
        gc_config: Optional[GCConfig] = None,
    ) -> DisCoGC:
        """Wrap an in-memory cache with DisCoGC."""
        backend = InMemoryStorageBackend(
            name="memory_cache",
            ttl_seconds=ttl_seconds,
            max_entries=max_entries,
        )
        return self._register_backend(backend, gc_config)

    def wrap_faiss(
        self,
        dimension: int = 384,
        persist_path: str = "",
        ttl_seconds: int = 86400 * 7,
        gc_config: Optional[GCConfig] = None,
    ) -> DisCoGC:
        """Wrap a FAISS vector index with DisCoGC."""
        backend = FAISSStorageBackend(
            name="faiss",
            dimension=dimension,
            persist_path=persist_path,
            ttl_seconds=ttl_seconds,
        )
        return self._register_backend(backend, gc_config)

    def wrap_knowledge_base(
        self,
        db_path: str,
        gc_config: Optional[GCConfig] = None,
    ) -> DisCoGC:
        """Wrap the knowledge base SQLite storage with DisCoGC."""
        backend = SQLiteStorageBackend(
            db_path=db_path,
            table_name="structured_memory",
            ttl_seconds=86400 * 30,
        )
        return self._register_backend(backend, gc_config)

    def _register_backend(
        self, backend, gc_config: Optional[GCConfig] = None
    ) -> DisCoGC:
        with self._lock:
            disco = get_disco_gc(backend, gc_config)
            self._backends[backend.name] = disco
            logger.info(
                "StorageBridge: registered backend '%s' (policy=%s)",
                backend.name,
                disco._config.policy.value,
            )
            return disco

    def start_all_background(self, interval_seconds: int = 600) -> None:
        with self._lock:
            for name, disco in self._backends.items():
                disco.start_background(interval_seconds)

    def stop_all_background(self) -> None:
        with self._lock:
            for disco in self._backends.values():
                disco.stop_background()

    def run_all_gc(self) -> Dict[str, int]:
        results = {}
        with self._lock:
            for name, disco in self._backends.items():
                freed = disco.run_gc()
                results[name] = freed
        return results

    def get_all_stats(self) -> Dict[str, dict]:
        with self._lock:
            return {name: disco.get_stats() for name, disco in self._backends.items()}

    def get_all_metrics(self) -> Dict[str, dict]:
        with self._lock:
            return {name: disco._metrics.snapshot() for name, disco in self._backends.items()}

    def close_all(self) -> None:
        with self._lock:
            for disco in self._backends.values():
                disco.close()
            self._backends.clear()


_storage_bridge: Optional[StorageBridge] = None
_bridge_lock = threading.Lock()


def get_storage_bridge() -> StorageBridge:
    global _storage_bridge
    if _storage_bridge is None:
        with _bridge_lock:
            if _storage_bridge is None:
                _storage_bridge = StorageBridge()
    return _storage_bridge
