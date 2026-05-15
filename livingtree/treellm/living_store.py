"""LivingStore — Unified liquid/solid storage abstraction with auto-tiering.

Every byte of the digital lifeform flows through one of two states:
  💧 LIQUID (volatile, fast, ephemeral):
     /ram/       — in-memory dict with TTL
     /cache/     — LRU cache with size limit and expiry
     /temp/      — temporary files with automatic cleanup
     /session/   — per-session state
     /stream/    — in-flight data buffers

  🪨 SOLID (persistent, durable, eventually-consistent):
     /disk/      — local filesystem (existing VirtualFS)
     /db/        — SQLite databases
     /cloud/     — S3/OSS/COS cloud storage (pluggable)
     /vector/    — LanceDB/Qdrant vector stores
     /git/       — Git repositories
     /config/    — configuration files
     /log/       — append-only logs
     /kb/        — knowledge base (existing VirtualFS)

Auto-tiering: hot data moves 💧→🪨 for persistence, frequently-accessed
solid data gets a 💧 cache copy. All writes go through a write-back buffer.

Unified API:
  store = get_living_store()
  await store.write("/ram/cache/result", data, ttl=3600)
  data = await store.read("/disk/projects/main.py")
  await store.move("/ram/tmp/x", "/disk/archive/x")  # liquid → solid
  await store.batch_write({"k1": v1, "k2": v2}, mount="/cache")
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

from loguru import logger

VFS_DB_PATH = Path(".livingtree/living_store.db")


# ═══ Data Types ════════════════════════════════════════════════════


class StorePhase(StrEnum):
    LIQUID = "liquid"
    SOLID = "solid"


@dataclass
class StoreEntry:
    """Metadata for a stored item."""
    path: str
    phase: StorePhase
    size_bytes: int
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: float = 0.0          # 0 = no expiry
    content_hash: str = ""
    backend: str = ""


@dataclass
class StoreStats:
    """Aggregated stats per backend."""
    liquid_bytes: int = 0
    solid_bytes: int = 0
    liquid_items: int = 0
    solid_items: int = 0
    reads: int = 0
    writes: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def hit_rate(self) -> float:
        return self.cache_hits / max(self.reads, 1)


# ═══ Abstract Backend ═════════════════════════════════════════════


class StoreBackend(ABC):
    """Pluggable storage backend."""

    def __init__(self, name: str, phase: StorePhase):
        self.name = name
        self.phase = phase
        self.stats = StoreStats()

    @abstractmethod
    async def read(self, path: str) -> Optional[bytes]:
        ...

    @abstractmethod
    async def write(self, path: str, data: bytes, ttl: float = 0) -> bool:
        ...

    @abstractmethod
    async def delete(self, path: str) -> bool:
        ...

    @abstractmethod
    async def exists(self, path: str) -> bool:
        ...

    @abstractmethod
    async def list(self, prefix: str = "") -> list[str]:
        ...

    async def read_text(self, path: str) -> Optional[str]:
        data = await self.read(path)
        return data.decode("utf-8", errors="replace") if data else None

    async def write_text(self, path: str, text: str, ttl: float = 0) -> bool:
        return await self.write(path, text.encode("utf-8"), ttl)

    async def read_json(self, path: str) -> Optional[Any]:
        data = await self.read(path)
        return json.loads(data) if data else None

    async def write_json(self, path: str, obj: Any, ttl: float = 0) -> bool:
        return await self.write(path, json.dumps(obj, ensure_ascii=False).encode(), ttl)


# ═══ 💧 Liquid Backends ══════════════════════════════════════════


class RAMBackend(StoreBackend):
    """In-memory dict with TTL. Fastest, zero persistence."""

    def __init__(self):
        super().__init__("ram", StorePhase.LIQUID)
        self._data: dict[str, tuple[bytes, float, float]] = {}  # path → (data, expiry, last_access)
        self._max_bytes = 256 * 1024 * 1024  # 256MB
        self._current_bytes = 0

    async def read(self, path: str) -> Optional[bytes]:
        entry = self._data.get(path)
        if not entry:
            return None
        data, expiry, _ = entry
        if expiry > 0 and time.time() > expiry:
            await self.delete(path)
            return None
        self._data[path] = (data, expiry, time.time())
        self.stats.reads += 1
        return data

    async def write(self, path: str, data: bytes, ttl: float = 0) -> bool:
        expiry = time.time() + ttl if ttl > 0 else 0
        old_entry = self._data.get(path)
        if old_entry:
            self._current_bytes -= len(old_entry[0])
        self._current_bytes += len(data)

        if self._current_bytes > self._max_bytes:
            self._evict(len(data))

        self._data[path] = (data, expiry, time.time())
        self.stats.writes += 1
        self.stats.liquid_bytes = self._current_bytes
        self.stats.liquid_items = len(self._data)
        return True

    async def delete(self, path: str) -> bool:
        entry = self._data.pop(path, None)
        if entry:
            self._current_bytes -= len(entry[0])
            self.stats.liquid_bytes = self._current_bytes
            self.stats.liquid_items = len(self._data)
        return entry is not None

    async def exists(self, path: str) -> bool:
        entry = self._data.get(path)
        if not entry:
            return False
        _, expiry, _ = entry
        if expiry > 0 and time.time() > expiry:
            await self.delete(path)
            return False
        return True

    async def list(self, prefix: str = "") -> list[str]:
        now = time.time()
        return [
            k for k, (_, exp, _) in self._data.items()
            if k.startswith(prefix) and (exp == 0 or now <= exp)
        ]

    def _evict(self, needed: int) -> None:
        """LRU eviction to make room."""
        sorted_keys = sorted(
            self._data.keys(),
            key=lambda k: self._data[k][2],  # last_access
        )
        freed = 0
        for k in sorted_keys:
            if freed >= needed:
                break
            freed += len(self._data[k][0])
            del self._data[k]
        self._current_bytes -= freed


class CacheBackend(StoreBackend):
    """LRU cache with max size and TTL. For hot data that may be evicted."""

    def __init__(self, max_size: int = 50 * 1024 * 1024):
        super().__init__("cache", StorePhase.LIQUID)
        self._data: OrderedDict[str, tuple[bytes, float]] = OrderedDict()
        self._max_size = max_size
        self._current_size = 0

    async def read(self, path: str) -> Optional[bytes]:
        if path not in self._data:
            self.stats.cache_misses += 1
            return None
        data, expiry = self._data[path]
        if expiry > 0 and time.time() > expiry:
            await self.delete(path)
            self.stats.cache_misses += 1
            return None
        # Move to end (LRU)
        self._data.move_to_end(path)
        self._data[path] = (data, expiry)
        self.stats.reads += 1
        self.stats.cache_hits += 1
        return data

    async def write(self, path: str, data: bytes, ttl: float = 0) -> bool:
        expiry = time.time() + ttl if ttl > 0 else 0
        if path in self._data:
            self._current_size -= len(self._data[path][0])

        while self._current_size + len(data) > self._max_size and self._data:
            _, (old_data, _) = self._data.popitem(last=False)
            self._current_size -= len(old_data)

        self._data[path] = (data, expiry)
        self._current_size += len(data)
        self.stats.writes += 1
        return True

    async def delete(self, path: str) -> bool:
        if path in self._data:
            self._current_size -= len(self._data[path][0])
            del self._data[path]
            return True
        return False

    async def exists(self, path: str) -> bool:
        return path in self._data

    async def list(self, prefix: str = "") -> list[str]:
        return [k for k in self._data if k.startswith(prefix)]


class TempBackend(StoreBackend):
    """OS temp files with auto-cleanup. Good for large intermediate data."""

    def __init__(self):
        super().__init__("temp", StorePhase.LIQUID)
        self._dir = Path(tempfile.gettempdir()) / "livingtree_temp"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._files: dict[str, Path] = {}
        self._cleanup_task: asyncio.Task = None

    def _safe_path(self, path: str) -> Path:
        name = hashlib.md5(path.encode()).hexdigest()[:16]
        return self._dir / name

    async def read(self, path: str) -> Optional[bytes]:
        p = self._files.get(path) or self._safe_path(path)
        if not p.exists():
            return None
        self.stats.reads += 1
        return p.read_bytes()

    async def write(self, path: str, data: bytes, ttl: float = 0) -> bool:
        p = self._safe_path(path)
        p.write_bytes(data)
        self._files[path] = p
        self.stats.writes += 1
        if ttl > 0:
            asyncio.get_event_loop().call_later(ttl, lambda: p.unlink(missing_ok=True))
        return True

    async def delete(self, path: str) -> bool:
        p = self._files.pop(path, None) or self._safe_path(path)
        p.unlink(missing_ok=True)
        return True

    async def exists(self, path: str) -> bool:
        p = self._files.get(path) or self._safe_path(path)
        return p.exists()

    async def list(self, prefix: str = "") -> list[str]:
        return [k for k in self._files if k.startswith(prefix)]


# ═══ 🪨 Solid Backends ═══════════════════════════════════════════


class DiskBackend(StoreBackend):
    """Local filesystem. Wraps existing VirtualFS /disk/ mount."""

    def __init__(self, root: Path = None):
        super().__init__("disk", StorePhase.SOLID)
        self._root = root or Path.cwd()

    def _real_path(self, path: str) -> Path:
        clean = path.replace("\\", "/").lstrip("/")
        parts = clean.split("/", 1)
        if len(parts) > 1 and parts[0] == "disk":
            clean = parts[1]
        return (self._root / clean).resolve()

    async def read(self, path: str) -> Optional[bytes]:
        p = self._real_path(path)
        if not p.exists() or not str(p).startswith(str(self._root.resolve())):
            return None
        self.stats.reads += 1
        return p.read_bytes()

    async def write(self, path: str, data: bytes, ttl: float = 0) -> bool:
        p = self._real_path(path)
        if not str(p).startswith(str(self._root.resolve())):
            return False
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        self.stats.writes += 1
        return True

    async def delete(self, path: str) -> bool:
        p = self._real_path(path)
        if p.exists() and str(p).startswith(str(self._root.resolve())):
            p.unlink()
            return True
        return False

    async def exists(self, path: str) -> bool:
        return self._real_path(path).exists()

    async def list(self, prefix: str = "") -> list[str]:
        p = self._real_path(prefix)
        if not p.exists() or not p.is_dir():
            return []
        return [str(f.relative_to(self._root)) for f in p.rglob("*") if f.is_file()][:200]


class SQLiteBackend(StoreBackend):
    """SQLite key-value store. ACID, concurrent-read safe."""

    def __init__(self, db_path: Path = VFS_DB_PATH):
        super().__init__("db", StorePhase.SOLID)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")  # Concurrent read-safe
        self._db_lock = asyncio.Lock()
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS store (path TEXT PRIMARY KEY, data BLOB, "
            "size INTEGER, created REAL, accessed REAL)"
        )
        self._conn.commit()

    async def read(self, path: str) -> Optional[bytes]:
        async with self._db_lock:
            row = self._conn.execute(
            "SELECT data FROM store WHERE path=?", (path,)
        ).fetchone()
        if row:
            self._conn.execute("UPDATE store SET accessed=? WHERE path=?", (time.time(), path))
            self._conn.commit()
            self.stats.reads += 1
            return row[0]
        return None

    async def write(self, path: str, data: bytes, ttl: float = 0) -> bool:
        async with self._db_lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO store VALUES (?,?,?,?,?)",
                (path, data, len(data), time.time(), time.time()),
            )
            self._conn.commit()
        self.stats.writes += 1
        return True

    async def delete(self, path: str) -> bool:
        self._conn.execute("DELETE FROM store WHERE path=?", (path,))
        self._conn.commit()
        return True

    async def exists(self, path: str) -> bool:
        row = self._conn.execute("SELECT 1 FROM store WHERE path=?", (path,)).fetchone()
        return row is not None

    async def list(self, prefix: str = "") -> list[str]:
        rows = self._conn.execute(
            "SELECT path FROM store WHERE path LIKE ?", (f"{prefix}%",)
        ).fetchall()
        return [r[0] for r in rows[:200]]


class ConfigBackend(StoreBackend):
    """Configuration files. JSON with schema validation placeholder."""

    def __init__(self, config_dir: Path = None):
        super().__init__("config", StorePhase.SOLID)
        self._dir = config_dir or Path(".livingtree/config_store")
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe}.json"

    async def read(self, path: str) -> Optional[bytes]:
        p = self._path(path)
        if not p.exists():
            return None
        self.stats.reads += 1
        return p.read_bytes()

    async def write(self, path: str, data: bytes, ttl: float = 0) -> bool:
        self._path(path).write_bytes(data)
        self.stats.writes += 1
        return True

    async def delete(self, path: str) -> bool:
        p = self._path(path)
        if p.exists():
            p.unlink()
            return True
        return False

    async def exists(self, path: str) -> bool:
        return self._path(path).exists()

    async def list(self, prefix: str = "") -> list[str]:
        return [f.stem for f in self._dir.glob("*.json") if f.stem.startswith(prefix)][:200]


# ═══ LivingStore — Unified Orchestrator ══════════════════════════


class LivingStore:
    """Unified liquid/solid storage with auto-tiering and write-back caching."""

    _instance: Optional["LivingStore"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "LivingStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = LivingStore()
        return cls._instance

    def __init__(self):
        # 💧 Liquid backends
        self._ram = RAMBackend()
        self._cache = CacheBackend()
        self._temp = TempBackend()

        # 🪨 Solid backends
        self._disk = DiskBackend()
        self._db = SQLiteBackend()
        self._config = ConfigBackend()

        # Mount table
        self._mounts: dict[str, StoreBackend] = {
            "ram": self._ram,
            "cache": self._cache,
            "temp": self._temp,
            "disk": self._disk,
            "db": self._db,
            "config": self._config,
        }

        # Auto-tiering: write-back buffer
        self._write_buffer: dict[str, tuple[bytes, float]] = {}
        self._flush_lock = asyncio.Lock()
        self._flush_interval = 2.0  # Flush buffer every 2s
        self._flush_task: asyncio.Task = None

    # ── Mount Management ───────────────────────────────────────────

    def mount(self, prefix: str, backend: StoreBackend) -> None:
        """Register a new backend (e.g., cloud storage, vector store)."""
        self._mounts[prefix] = backend
        logger.info(f"LivingStore: mounted '{prefix}' → {backend.name} ({backend.phase.value})")

    def unmount(self, prefix: str) -> None:
        self._mounts.pop(prefix, None)

    # ── Unified API ────────────────────────────────────────────────

    async def read(self, path: str) -> Optional[bytes]:
        """Read from any mount. Auto-tier: solid reads get a liquid cache copy."""
        backend = self._resolve(path)
        if not backend:
            return None

        # Try cache first for solid stores
        if backend.phase == StorePhase.SOLID:
            cache_key = f"cache/{path.replace('/', '_')}"
            cached = await self._cache.read(cache_key)
            if cached is not None:
                return cached

        data = await backend.read(path)

        # Auto-cache solid reads
        if data and backend.phase == StorePhase.SOLID:
            cache_key = f"cache/{path.replace('/', '_')}"
            await self._cache.write(cache_key, data, ttl=300)

        return data

    async def write(self, path: str, data: bytes, ttl: float = 0) -> bool:
        """Write to any mount. Solid writes buffer through liquid first."""
        backend = self._resolve(path)
        if not backend:
            return False

        if backend.phase == StorePhase.SOLID:
            # Write-back: buffer in liquid, async flush to solid
            self._write_buffer[path] = (data, time.time())
            self._start_flush()
            return True

        return await backend.write(path, data, ttl)

    async def delete(self, path: str) -> bool:
        backend = self._resolve(path)
        if not backend:
            return False
        # Also clear cache
        cache_key = f"cache/{path.replace('/', '_')}"
        await self._cache.delete(cache_key)
        return await backend.delete(path)

    async def exists(self, path: str) -> bool:
        backend = self._resolve(path)
        return await backend.exists(path) if backend else False

    async def list(self, path: str) -> list[str]:
        backend = self._resolve(path)
        return await backend.list(path) if backend else []

    async def move(self, src: str, dst: str) -> bool:
        """Move data between mounts (e.g., liquid → solid)."""
        data = await self.read(src)
        if data is None:
            return False
        if await self.write(dst, data):
            await self.delete(src)
            return True
        return False

    async def batch_write(self, items: dict[str, bytes], mount: str = "cache",
                          ttl: float = 0) -> int:
        """Batch write multiple items to same mount."""
        backend = self._mounts.get(mount)
        if not backend:
            return 0
        count = 0
        tasks = [backend.write(k, v, ttl) for k, v in items.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if r is True:
                count += 1
        return count

    # ── Text/JSON Convenience ──────────────────────────────────────

    async def read_text(self, path: str) -> Optional[str]:
        data = await self.read(path)
        return data.decode("utf-8", errors="replace") if data else None

    async def write_text(self, path: str, text: str, ttl: float = 0) -> bool:
        return await self.write(path, text.encode("utf-8"), ttl)

    async def read_json(self, path: str) -> Optional[Any]:
        data = await self.read(path)
        return json.loads(data) if data else None

    async def write_json(self, path: str, obj: Any, ttl: float = 0) -> bool:
        return await self.write(path, json.dumps(obj, ensure_ascii=False).encode(), ttl)

    # ── Internal ───────────────────────────────────────────────────

    def _resolve(self, path: str) -> Optional[StoreBackend]:
        """Resolve path to backend based on mount prefix."""
        clean = path.replace("\\", "/").lstrip("/")
        for prefix, backend in self._mounts.items():
            if clean.startswith(prefix):
                return backend
        # Default: solid → disk, otherwise → ram
        if any(clean.startswith(p) for p in ["disk", "db", "config", "log", "git", "cloud", "vector", "kb"]):
            return self._disk
        return self._ram

    def _start_flush(self):
        if self._flush_task and not self._flush_task.done():
            return
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def _flush_loop(self):
        await asyncio.sleep(self._flush_interval)
        await self._flush()

    async def _flush(self) -> int:
        """Flush write-back buffer to solid stores in parallel."""
        if not self._write_buffer:
            return 0
        async with self._flush_lock:
            batch = dict(self._write_buffer)
            self._write_buffer.clear()

        async def _write_one(path, data):
            backend = self._resolve(path)
            if backend and backend.phase == StorePhase.SOLID:
                return await backend.write(path, data)
            return False

        tasks = [_write_one(p, d) for p, (d, _) in batch.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        count = sum(1 for r in results if r is True)
        if count:
            logger.debug(f"LivingStore: flushed {count} items to solid (parallel)")
        return count

    # ── Stats ──────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "mounts": len(self._mounts),
            "write_buffer": len(self._write_buffer),
            "ram": {"items": len(self._ram._data), "bytes": self._ram._current_bytes},
            "cache": {"items": len(self._cache._data), "bytes": self._cache._current_size},
            "temp": {"items": len(self._temp._files)},
            "hit_rate": round(self._cache.stats.hit_rate, 3),
        }

    async def shutdown(self):
        """Flush all buffers and clean up."""
        await self._flush()
        if self._flush_task:
            self._flush_task.cancel()


# ═══ Singleton ════════════════════════════════════════════════════

_store: Optional[LivingStore] = None
_store_lock = threading.Lock()


def get_living_store() -> LivingStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = LivingStore()
    return _store


__all__ = [
    "LivingStore", "StoreBackend", "StorePhase", "StoreEntry", "StoreStats",
    "RAMBackend", "CacheBackend", "TempBackend",
    "DiskBackend", "SQLiteBackend", "ConfigBackend",
    "get_living_store",
]
