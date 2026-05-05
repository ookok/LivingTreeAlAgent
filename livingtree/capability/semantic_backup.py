"""SemanticBackup — auto-backup with LLM-generated commit messages.

    1. Timestamped backups: save file snapshots to .livingtree/backups/
    2. LLM summary: generate semantic commit message describing what changed
    3. Rollback: restore any previous version by timestamp or message search
    4. Auto-prune: keep last N backups, remove older ones
    5. Pre-commit hook: backup before every edit to protected files

    Usage:
        sb = get_semantic_backup()
        msg = await sb.backup("config.py", hub)
        # → "Changed server port from 8100 to 8888"
        await sb.restore("config.py", "2026-05-05T14:30:00")
        sb.prune("config.py", keep=10)
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

BACKUP_DIR = Path(".livingtree/backups")


@dataclass
class BackupEntry:
    path: Path
    timestamp: float
    backup_path: Path
    size: int
    message: str = ""
    diff_summary: str = ""


@dataclass
class BackupResult:
    path: Path
    backed_up: bool = False
    backup_path: Path | None = None
    message: str = ""
    history: list[BackupEntry] = field(default_factory=list)


class SemanticBackup:
    """Smart backup with LLM-generated semantic commit messages."""

    def __init__(self, auto_backup_on_edit: bool = False):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        self.auto_backup_on_edit = auto_backup_on_edit
        self._index: dict[str, list[BackupEntry]] = {}  # path → entries
        self._load_index()

    async def backup(
        self,
        filepath: str | Path,
        hub=None,
        message: str = "",
    ) -> BackupResult:
        """Create a timestamped backup with optional LLM-generated message.

        Args:
            filepath: File to back up
            hub: LLM access for semantic message
            message: Manual message (overrides LLM)
        """
        filepath = Path(filepath).resolve()
        if not filepath.exists():
            return BackupResult(path=filepath)

        ts = time.time()
        ts_str = time.strftime("%Y%m%dT%H%M%S", time.localtime(ts))
        backup_name = f"{filepath.stem}_{ts_str}_{hash(str(filepath))[:8]}{filepath.suffix}"
        backup_path = BACKUP_DIR / backup_name

        shutil.copy2(filepath, backup_path)

        # Generate semantic message
        msg = message
        diff_summary = ""
        if hub and hub.world and not msg:
            msg, diff_summary = await self._generate_message(filepath, hub)
        if not msg:
            msg = f"Backup {filepath.name} at {ts_str}"

        entry = BackupEntry(
            path=filepath, timestamp=ts, backup_path=backup_path,
            size=filepath.stat().st_size, message=msg, diff_summary=diff_summary,
        )

        key = str(filepath)
        if key not in self._index:
            self._index[key] = []
        self._index[key].append(entry)
        self._index[key].sort(key=lambda e: e.timestamp, reverse=True)
        self._save_index()

        return BackupResult(
            path=filepath, backed_up=True, backup_path=backup_path,
            message=msg, history=self._index.get(key, []),
        )

    async def restore(
        self,
        filepath: str | Path,
        identifier: str = "",  # timestamp str or message substring
    ) -> BackupResult:
        """Restore a file from backup.

        Args:
            filepath: File to restore
            identifier: Timestamp ("2026-05-05T14:30"), message keyword ("changed port"),
                        or empty for latest
        """
        filepath = Path(filepath).resolve()
        key = str(filepath)
        history = self._index.get(key, [])

        if not history:
            return BackupResult(path=filepath, history=[])

        target = history[0]  # default: latest
        if identifier:
            for e in history:
                ts_str = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(e.timestamp))
                if identifier in ts_str or identifier.lower() in e.message.lower():
                    target = e
                    break

        # Backup current first (safety net)
        if filepath.exists():
            safety = BACKUP_DIR / f"pre_restore_{filepath.name}_{int(time.time())}"
            shutil.copy2(filepath, safety)

        shutil.copy2(target.backup_path, filepath)

        return BackupResult(
            path=filepath, backup_path=target.backup_path,
            message=target.message, history=history,
        )

    def prune(self, filepath: str | Path, keep: int = 10):
        """Remove old backups, keep only the N most recent."""
        filepath = Path(filepath).resolve()
        key = str(filepath)
        entries = self._index.get(key, [])
        if len(entries) <= keep:
            return

        to_delete = entries[keep:]
        for e in to_delete:
            e.backup_path.unlink(missing_ok=True)

        self._index[key] = entries[:keep]
        self._save_index()

    def list(self, filepath: str | Path) -> list[BackupEntry]:
        """List all backups for a file."""
        key = str(Path(filepath).resolve())
        return self._index.get(key, [])

    def list_all(self) -> dict[str, list[BackupEntry]]:
        """List all backed-up files."""
        return dict(self._index)

    def __contains__(self, filepath: str | Path) -> bool:
        key = str(Path(filepath).resolve())
        return key in self._index and len(self._index[key]) > 0

    async def _generate_message(self, filepath: Path, hub) -> tuple[str, str]:
        """LLM compares latest backup with current to describe changes."""
        key = str(filepath)
        history = self._index.get(key, [])
        if not history:
            return "", ""

        prev = history[0].backup_path
        if not prev.exists():
            return "", ""

        try:
            with open(prev, "r", encoding="utf-8", errors="replace") as f:
                old = f.read(5000)
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                new = f.read(5000)
        except Exception:
            return "", ""

        if old == new:
            return "No changes", ""

        llm = hub.world.consciousness._llm
        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"Compare these two versions of {filepath.name} and write a "
                    f"ONE-line git-style commit message (max 80 chars) describing the changes:\n\n"
                    f"OLD:\n```\n{old[-3000:]}\n```\n\n"
                    f"NEW:\n```\n{new[-3000:]}\n```\n\n"
                    f"Output ONLY: verb: change description"
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.1, max_tokens=80, timeout=15,
            )
            if result and result.text:
                msg = result.text.strip()[:120]
                return msg, f"- {msg}"
        except Exception as e:
            logger.debug(f"Backup message: {e}")

        return filepath.name, ""

    def _save_index(self):
        data = {}
        for key, entries in self._index.items():
            data[key] = [
                {"path": str(e.path), "timestamp": e.timestamp,
                 "backup_path": str(e.backup_path), "size": e.size,
                 "message": e.message, "diff_summary": e.diff_summary}
                for e in entries
            ]
        (BACKUP_DIR / "index.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

    def _load_index(self):
        idx_path = BACKUP_DIR / "index.json"
        if not idx_path.exists():
            return
        try:
            data = json.loads(idx_path.read_text(encoding="utf-8"))
            for key, entries in data.items():
                self._index[key] = [
                    BackupEntry(
                        path=Path(e["path"]),
                        timestamp=e["timestamp"],
                        backup_path=Path(e["backup_path"]),
                        size=e["size"],
                        message=e.get("message", ""),
                        diff_summary=e.get("diff_summary", ""),
                    )
                    for e in entries
                ]
        except Exception:
            pass


_sb: SemanticBackup | None = None


def get_semantic_backup() -> SemanticBackup:
    global _sb
    if _sb is None:
        _sb = SemanticBackup()
    return _sb
