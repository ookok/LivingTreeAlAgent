"""FileWatcher — watch project files, auto-index changes to knowledge base.

    1. Filesystem polling: watch modified files every N seconds
    2. Change detection: hash-based or mtime-based diff
    3. Auto-index: push new/updated files to DocumentKB + IntelligentKB
    4. Semantic summary: LLM generates one-line summary of changes for KB
    5. Event hook: on_file_changed(path) → user-defined callback

    Usage:
        watcher = get_file_watcher()
        await watcher.start(hub, interval=30)  # poll every 30s
        watcher.on_change = lambda path: print(f"{path} changed")
        # Or register with hub as a background task
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

from loguru import logger


class FileWatcher:
    """Polling-based file watcher with auto-indexing to KB."""

    WATCH_EXTS = {".py", ".md", ".yaml", ".yml", ".json", ".toml", ".txt",
                  ".js", ".ts", ".html", ".css", ".sh", ".bat", ".cfg", ".ini", ".env"}
    SKIP_DIRS = {".venv", "__pycache__", ".git", "node_modules", "dist", "build",
                 ".livingtree", "toad", "output", "data", "logs"}

    def __init__(self):
        self._hashes: dict[str, str] = {}  # path → content_hash
        self._running = False
        self._task: asyncio.Task | None = None
        self.on_change: Callable[[Path], None] | None = None

    async def start(
        self,
        hub=None,
        root: str | Path = ".",
        interval: int = 30,
        auto_index: bool = True,
    ):
        """Start watching files.

        Args:
            hub: IntegrationHub (for KB indexing)
            root: Project root to watch
            interval: Polling interval in seconds
            auto_index: Auto-add changes to knowledge base
        """
        self._running = True
        root = Path(root)
        logger.info(f"FileWatcher started (root={root}, interval={interval}s, auto_index={auto_index})")

        # Initial hash snapshot
        self._scan(root)

        while self._running:
            try:
                changed = self._scan(root, detect_changes=True)
                if changed:
                    for path in changed:
                        if auto_index and hub:
                            await self._index_file(path, hub)
                        if self.on_change:
                            try:
                                self.on_change(path)
                            except Exception as e:
                                logger.debug(f"on_change callback: {e}")
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"FileWatcher tick: {e}")
                await asyncio.sleep(interval)

    def stop(self):
        """Stop watching."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    def _scan(self, root: Path, detect_changes: bool = False) -> list[Path]:
        """Scan watched files, return list of changed paths."""
        changed = []
        current: dict[str, str] = {}

        for fpath in root.rglob("*"):
            if self._should_skip(fpath):
                continue
            if fpath.is_file():
                try:
                    h = self._hash_file_quick(fpath)
                    current[str(fpath)] = h
                    if detect_changes:
                        old_h = self._hashes.get(str(fpath))
                        if old_h and old_h != h:
                            changed.append(fpath)
                except Exception:
                    pass

        # Detect deletions
        if detect_changes:
            for old_path in list(self._hashes.keys()):
                if old_path not in current:
                    logger.debug(f"File deleted: {old_path}")
                    del self._hashes[old_path]

        self._hashes = current
        return changed

    def _should_skip(self, path: Path) -> bool:
        if not path.suffix or path.suffix not in self.WATCH_EXTS:
            return True
        for part in path.parts:
            if part in self.SKIP_DIRS:
                return True
        if path.stat().st_size > 2_000_000:  # skip >2MB
            return True
        return False

    def _hash_file_quick(self, path: Path) -> str:
        """Fast hash using mtime + size + first 8KB."""
        stat = path.stat()
        key = f"{stat.st_mtime}:{stat.st_size}"
        # Add first 8KB hash for content change detection
        with open(path, "rb") as f:
            head = f.read(8192)
        key += ":" + hashlib.sha256(head).hexdigest()[:16]
        return hashlib.sha256(key.encode()).hexdigest()

    async def _index_file(self, path: Path, hub):
        """Push file changes to knowledge base."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(50000)

            # Generate summary via LLM
            summary = content[:200]
            if hub.world and len(content) > 200:
                try:
                    llm = hub.world.consciousness._llm
                    result = await llm.chat(
                        messages=[{"role": "user", "content": (
                            f"Summarize this file in ONE line (max 80 chars):\n"
                            f"File: {path.name}\n{content[:3000]}"
                        )}],
                        provider=getattr(llm, '_elected', ''),
                        temperature=0.0, max_tokens=60, timeout=10,
                    )
                    if result and result.text:
                        summary = result.text.strip()[:120]
                except Exception:
                    pass

            # Index to KBs
            try:
                from livingtree.core.unified_registry import get_registry
                reg = get_registry()
                for kb_name, kb_obj in getattr(reg, '_kbs', {}).items():
                    try:
                        kb_obj.add(
                            id=f"file:{path.name}:{int(time.time())}",
                            title=path.name,
                            content=content,
                            source=str(path),
                            summary=summary,
                        )
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"Index {path}: {e}")


_watcher: FileWatcher | None = None


def get_file_watcher() -> FileWatcher:
    global _watcher
    if _watcher is None:
        _watcher = FileWatcher()
    return _watcher
