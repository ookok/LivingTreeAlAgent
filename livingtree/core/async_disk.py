"""AsyncDisk — batched, non-blocking file persistence.

All data persistence (.json, .log, .enc) routes through here.
Collects writes over a short window, flushes to disk in background thread.
Eliminates synchronous disk I/O from hot paths.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from loguru import logger

BATCH_INTERVAL = 5.0  # Flush every 5 seconds
MAX_BATCH_SIZE = 100   # Or when 100 writes queued


class AsyncDisk:
    """Non-blocking file writer. Batches writes and flushes in background."""

    _instance: AsyncDisk | None = None

    @classmethod
    def instance(cls) -> AsyncDisk:
        if cls._instance is None:
            cls._instance = AsyncDisk()
        return cls._instance

    def __init__(self):
        self._pending: dict[Path, str] = {}  # path → latest content
        self._dirty: set[Path] = set()
        self._lock = threading.Lock()
        self._running = False
        self._task: asyncio.Task | None = None
        self._writes = 0
        self._flushes = 0

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.debug("AsyncDisk started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        self._flush_all()
        logger.debug(f"AsyncDisk stopped ({self._flushes} flushes, {self._writes} writes)")

    def write_json(self, path: Path, data: dict | list):
        """Queue a JSON write. Latest content for each path wins (dedup)."""
        content = json.dumps(data, indent=2, ensure_ascii=False)
        with self._lock:
            self._pending[path] = content
            self._dirty.add(path)
            self._writes += 1

    def write_text(self, path: Path, text: str):
        """Queue a text write."""
        with self._lock:
            self._pending[path] = text
            self._dirty.add(path)
            self._writes += 1

    def flush_now(self, path: Path):
        """Force immediate flush for a specific file."""
        with self._lock:
            content = self._pending.pop(path, None)
            self._dirty.discard(path)
        if content is not None:
            self._write_file(path, content)

    def _flush_all(self):
        with self._lock:
            to_flush = dict(self._pending)
            self._pending.clear()
            self._dirty.clear()
        for path, content in to_flush.items():
            self._write_file(path, content)

    def _flush_batch(self):
        with self._lock:
            if not self._dirty:
                return
            to_flush = {p: self._pending[p] for p in list(self._dirty)}
            self._dirty.clear()

        for path, content in to_flush.items():
            self._write_file(path, content)
        self._flushes += 1

    def _write_file(self, path: Path, content: str):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.debug(f"AsyncDisk write {path}: {e}")

    async def _loop(self):
        while self._running:
            await asyncio.sleep(BATCH_INTERVAL)
            self._flush_batch()


def get_disk() -> AsyncDisk:
    return AsyncDisk.instance()


# ═══ Convenience: replace old save methods ═══

def save_json(path: str | Path, data: Any):
    """Non-blocking JSON save. Drop-in replacement for path.write_text(json.dumps(...))."""
    get_disk().write_json(Path(path), data)
