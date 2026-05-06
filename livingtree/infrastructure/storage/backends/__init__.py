"""Storage backend adapters — pluggable implementations of StorageBackend.

Backends:
  - SQLiteStorageBackend: segment-based view over SQLite tables
  - InMemoryStorageBackend: dict-based backend for testing and small caches
  - FAISSStorageBackend: vector index backend with segment awareness
"""

from .sqlite_backend import SQLiteStorageBackend
from .memory_backend import InMemoryStorageBackend
from .faiss_backend import FAISSStorageBackend

__all__ = [
    "SQLiteStorageBackend",
    "InMemoryStorageBackend",
    "FAISSStorageBackend",
]
