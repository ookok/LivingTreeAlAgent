"""IO optimization layer — async IO, LRU cache, streaming, WAL mode.

Optimizes frequent IO hotspots:
- KnowledgeBase: SQLite WAL mode + connection reuse + prepared statements
- Checkpoint: batch writes + async file IO
- CodeGraph: file hash cache + lazy parsing
- Large documents: streaming read + memory-mapped fallback
- VectorStore: embedding cache with LRU eviction
"""

from __future__ import annotations

import asyncio
import functools
import mmap
import sqlite3
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger


# ── LRU Cache ──

class LRUCache:
    """Thread-safe LRU cache for frequently accessed data."""

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300.0):
        self._max = max_size
        self._ttl = ttl_seconds
        self._data: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._data:
                self._misses += 1
                return None
            value, ts = self._data.pop(key)
            if time.time() - ts > self._ttl:
                self._misses += 1
                return None
            self._data[key] = (value, ts)
            self._hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._data:
                self._data.pop(key)
            elif len(self._data) >= self._max:
                self._data.popitem(last=False)
            self._data[key] = (value, time.time())

    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._data), "hits": self._hits, "misses": self._misses,
                "hit_rate": self._hits / max(total, 1), "max_size": self._max,
            }

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


def cached(cache: LRUCache, key_fn: Callable | None = None):
    """Decorator: cache function results with LRU eviction."""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            k = key_fn(*args, **kwargs) if key_fn else str(args) + str(kwargs)
            val = cache.get(k)
            if val is not None:
                return val
            result = await func(*args, **kwargs)
            cache.set(k, result)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            k = key_fn(*args, **kwargs) if key_fn else str(args) + str(kwargs)
            val = cache.get(k)
            if val is not None:
                return val
            result = func(*args, **kwargs)
            cache.set(k, result)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# ── SQLite WAL mode + connection pool ──

def optimize_sqlite(conn: sqlite3.Connection) -> None:
    """Enable WAL mode and performance pragmas."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-8000")  # 8MB cache
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
    conn.execute("PRAGMA busy_timeout=5000")


# ── Streaming file reader ──

async def stream_read(path: str, chunk_size: int = 65536) -> list[str]:
    """Read large file in chunks with minimal memory.

    Returns list of chunk strings.
    """
    chunks = []
    size = Path(path).stat().st_size
    if size < chunk_size * 2:
        # Small file: direct read is faster
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        return [content]

    loop = asyncio.get_event_loop()

    def _read():
        result = []
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                result.append(chunk)
        return result

    return await loop.run_in_executor(None, _read)


def mmap_read(path: str, max_size: int = 100 * 1024 * 1024) -> str:
    """Memory-mapped file read for ultra-large files.

    Falls back to regular read if file < 10MB.
    """
    file_size = Path(path).stat().st_size
    if file_size < 10 * 1024 * 1024 or file_size > max_size:
        return Path(path).read_text(encoding="utf-8", errors="replace")

    with open(path, "r+b") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
            return m.read().decode("utf-8", errors="replace")


def smart_read(path: str, max_memory_mb: int = 50) -> str:
    """Auto-select best read strategy based on file size.

    < 10MB: direct read
    10-50MB: memory-mapped
    > 50MB: stream + summarize
    """
    size_mb = Path(path).stat().st_size / (1024 * 1024)
    if size_mb < 10:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    if size_mb < max_memory_mb:
        return mmap_read(path)
    # Too large: stream chunks
    chunks = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        while True:
            chunk = f.read(128 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
    return "\n---CHUNK---\n".join(ch for ch in chunks[:100])


# ── Batch writer ──

class BatchWriter:
    """Accumulates writes and flushes periodically.

    Reduces IOPS for frequent small writes (e.g., checkpoint saves).
    """

    def __init__(self, flush_interval: float = 5.0, max_pending: int = 100):
        self._pending: dict[str, str] = {}
        self._interval = flush_interval
        self._max_pending = max_pending
        self._lock = threading.Lock()
        self._last_flush = time.time()

    def write(self, path: str, content: str) -> None:
        with self._lock:
            self._pending[path] = content
            if len(self._pending) >= self._max_pending:
                self._flush()

    def _flush(self) -> None:
        if not self._pending:
            return
        items = dict(self._pending)
        self._pending.clear()
        for path, content in items.items():
            try:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text(content, encoding="utf-8")
            except Exception:
                pass
        self._last_flush = time.time()

    async def start_auto_flush(self) -> None:
        """Auto-flush pending writes every N seconds."""
        while True:
            await asyncio.sleep(self._interval)
            with self._lock:
                self._flush()

    def flush_now(self) -> None:
        with self._lock:
            self._flush()


# ── Embedding cache ──

class EmbeddingCache:
    """Cache vector embeddings to avoid re-computing for unchanged text."""

    def __init__(self, max_size: int = 10000):
        self._cache = LRUCache(max_size=max_size, ttl_seconds=3600.0)

    def get_embedding_key(self, text: str) -> str:
        import hashlib
        return hashlib.sha256(text.encode()).hexdigest()[:24]

    def get(self, text: str) -> Optional[list[float]]:
        return self._cache.get(self.get_embedding_key(text))

    def set(self, text: str, embedding: list[float]) -> None:
        self._cache.set(self.get_embedding_key(text), embedding)

    def stats(self) -> dict:
        return self._cache.stats()


# ── Global caches ──

_global_kb_cache = LRUCache(max_size=2000, ttl_seconds=600.0)
_global_ast_cache = LRUCache(max_size=500, ttl_seconds=300.0)
_global_embed_cache = EmbeddingCache()
_global_batch_writer = BatchWriter()
