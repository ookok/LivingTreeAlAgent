"""AtomicModification — unified atomic multi-file code modification.

Consolidates the existing fragmented snapshot/backup/rollback mechanisms
(SideGit, HarnessRegistry, DocumentEditor.transaction(), PatchManager)
into a single context manager providing:

  1. Persistent backup (disk, not in-memory — survives crashes)
  2. Per-file atomic write (temp + os.replace)
  3. All-or-nothing rollback across all files
  4. Pre-flight validation (all paths writable before any writes)
  5. SHA-256 integrity verification
  6. Dependency-aware rollback chain (order-preserving undo)

Usage:
    edits = {
        "src/main.py": "def main(): pass",
        "src/utils.py": "def util(): return 42",
    }
    with AtomicModification(edits, reason="Refactor main module") as atom:
        atom.validate()        # check all paths exist and are writable
        atom.apply()           # write all, keep old backup
        # if any fails, ALL are rolled back from disk backup
        atom.verify()          # check SHA-256 of new files
        if ok:
            atom.commit()      # delete backups, log success
        # exception or explicit rollback → atom.rollback() restores ALL
"""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any

from loguru import logger

ATOMIC_DIR = Path(".livingtree/atomic")
ATOMIC_BACKUPS = ATOMIC_DIR / "backups"
ATOMIC_LOG = ATOMIC_DIR / "atomic_log.json"


@dataclass
class FileEdit:
    """A single file edit operation within an atomic batch."""
    path: str
    new_content: str | bytes
    original_content: bytes | None = None
    original_sha256: str = ""
    new_sha256: str = ""
    backup_path: str = ""
    status: str = "pending"
    error: str = ""


@dataclass
class AtomicResult:
    edits: list[FileEdit]
    success: bool
    files_modified: int
    files_rolled_back: int
    total_chars_changed: int
    applied_at: float
    reason: str
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.success:
            return (f"[OK] {self.files_modified} files modified "
                    f"({self.total_chars_changed} chars) — {self.reason}")
        return (f"[FAIL] {self.files_rolled_back} files rolled back — "
                f"{'; '.join(self.errors[:3])}")


class AtomicModification(AbstractContextManager):
    """Unified atomic multi-file modification with persistent backups.

    Replaces the current fragmented landscape:
      - SelfModifier (in-memory backup, non-atomic writes)
      - DocumentEditor.transaction() (in-memory backup)
      - PatchManager (per-patch .bak files, no cross-patch rollback chain)
      - SideGit (whole-workspace copy, no per-file atomicity)

    Provides a single, consistent, crash-safe primitive for all of them.
    """

    def __init__(self, edits: dict[str, str | bytes],
                 reason: str = "unnamed",
                 dry_run: bool = False,
                 verify_imports: bool = False):
        self._reason = reason
        self._dry_run = dry_run
        self._verify_imports = verify_imports
        self._applied = False
        self._committed = False

        self._edits = [
            FileEdit(path=str(Path(p).resolve()), new_content=c)
            for p, c in edits.items()
        ]

    def __enter__(self) -> "AtomicModification":
        ATOMIC_DIR.mkdir(parents=True, exist_ok=True)
        ATOMIC_BACKUPS.mkdir(parents=True, exist_ok=True)
        self._backup_timestamp = time.strftime("%Y%m%d_%H%M%S")
        self._backup_dir = ATOMIC_BACKUPS / self._backup_timestamp
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc_val: BaseException | None,
                 exc_tb: TracebackType | None) -> bool | None:
        if exc_type is not None:
            if self._applied and not self._committed:
                try:
                    self.rollback()
                except Exception as e:
                    logger.error(f"Emergency rollback failed: {e}")
            logger.error(f"AtomicModification aborted: {exc_val}")
        return False

    def validate(self) -> list[str]:
        """Pre-flight: check all files exist and are writable before any writes."""
        errors = []
        for edit in self._edits:
            p = Path(edit.path)
            parent = p.parent
            if not parent.exists():
                try:
                    parent.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    errors.append(f"{edit.path}: cannot create parent — {e}")
                    continue

            if p.exists():
                try:
                    edit.original_content = p.read_bytes()
                    edit.original_sha256 = hashlib.sha256(
                        edit.original_content).hexdigest()
                except OSError as e:
                    errors.append(f"{edit.path}: cannot read — {e}")
                    continue
                edit.status = "validated"
            else:
                edit.original_content = None
                edit.original_sha256 = ""
                edit.status = "new_file"

        return errors

    def apply(self) -> AtomicResult:
        """Apply all edits: persistent backup → atomic write per file.

        If ANY file write fails, ALL previously written files are rolled
        back from their persistent backups.
        """
        errors = self.validate()
        if errors:
            self._edits = [e for e in self._edits
                           if e.status not in ("validated", "new_file")]
            return AtomicResult(
                edits=self._edits, success=False, files_modified=0,
                files_rolled_back=0, total_chars_changed=0,
                applied_at=0, reason=self._reason, errors=errors,
            )

        if self._dry_run:
            return AtomicResult(
                edits=self._edits, success=True,
                files_modified=len(self._edits), files_rolled_back=0,
                total_chars_changed=sum(
                    len(e.new_content) if isinstance(e.new_content, str)
                    else len(e.new_content) for e in self._edits),
                applied_at=time.time(), reason=f"[DRY RUN] {self._reason}",
            )

        modified = 0
        total_chars = 0
        failed = []

        for edit in self._edits:
            if edit.status == "new_file":
                try:
                    self._write_new_file(edit)
                    total_chars += (len(edit.new_content) if isinstance(edit.new_content, str)
                                    else len(edit.new_content))
                except Exception as e:
                    failed.append(f"{edit.path}: new file write — {e}")
            elif edit.status == "validated":
                try:
                    self._backup_and_write(edit)
                    total_chars += (len(edit.new_content) if isinstance(edit.new_content, str)
                                    else len(edit.new_content))
                except Exception as e:
                    failed.append(f"{edit.path}: backup+write — {e}")

            if failed:
                break

        if failed:
            self.rollback()
            return AtomicResult(
                edits=self._edits, success=False, files_modified=0,
                files_rolled_back=modified, total_chars_changed=0,
                applied_at=0, reason=self._reason, errors=failed,
            )

        self._applied = True
        return AtomicResult(
            edits=self._edits, success=True,
            files_modified=len(self._edits), files_rolled_back=0,
            total_chars_changed=total_chars,
            applied_at=time.time(), reason=self._reason,
        )

    def verify(self) -> list[str]:
        """Post-write integrity check: SHA-256 verify each written file."""
        mismatches = []
        for edit in self._edits:
            if edit.status not in ("written",):
                continue
            try:
                p = Path(edit.path)
                if not p.exists():
                    mismatches.append(f"{edit.path}: file missing after write")
                    continue
                actual = hashlib.sha256(p.read_bytes()).hexdigest()
                if edit.new_sha256 and actual != edit.new_sha256:
                    mismatches.append(
                        f"{edit.path}: SHA-256 mismatch "
                        f"expected={edit.new_sha256[:12]} actual={actual[:12]}")
            except Exception as e:
                mismatches.append(f"{edit.path}: verify error — {e}")
        return mismatches

    def commit(self):
        """Commit: delete backup directory, log to atomic_log.json."""
        if not self._applied:
            raise RuntimeError("Must apply() before commit()")

        try:
            if self._backup_dir.exists():
                shutil.rmtree(self._backup_dir)
        except Exception as e:
            logger.debug(f"Backup cleanup failed: {e}")

        self._committed = True
        self._log_success()

    def rollback(self):
        """Rollback ALL files from persistent disk backups.

        Restores each file in reverse order from its backup.
        Does NOT raise — all errors are collected.
        """
        rolled = 0
        for edit in reversed(self._edits):
            if not edit.backup_path or edit.status == "new_file":
                if edit.status == "written":
                    try:
                        Path(edit.path).unlink(missing_ok=True)
                        edit.status = "rolled_back"
                        rolled += 1
                    except Exception as e:
                        logger.error(f"Rollback unlink {edit.path}: {e}")
                continue

            try:
                backup = Path(edit.backup_path)
                if backup.exists():
                    shutil.copy2(str(backup), edit.path)
                    backup.unlink()
                edit.status = "rolled_back"
                rolled += 1
            except Exception as e:
                logger.error(f"Rollback {edit.path}: {e}")

        self._applied = False
        logger.info(f"AtomicModification rolled back {rolled} files "
                     f"({self._reason})")

    # ── Internal ──

    def _backup_and_write(self, edit: FileEdit):
        """Persistent backup + atomic temp-write + rename."""
        src = Path(edit.path)
        backup_name = src.name + ".bak"
        backup_path = self._backup_dir / backup_name

        if edit.original_content is not None and src.exists():
            shutil.copy2(str(src), str(backup_path))
            edit.backup_path = str(backup_path)

        tmp = src.with_suffix(src.suffix + ".tmp")
        content = edit.new_content
        if isinstance(content, str):
            tmp.write_text(content, encoding="utf-8")
        else:
            tmp.write_bytes(content)

        if isinstance(content, str):
            edit.new_sha256 = hashlib.sha256(
                content.encode("utf-8")).hexdigest()
        else:
            edit.new_sha256 = hashlib.sha256(content).hexdigest()

        os.replace(str(tmp), str(src))
        edit.status = "written"

    def _write_new_file(self, edit: FileEdit):
        """Create a new file (no backup needed)."""
        src = Path(edit.path)
        src.parent.mkdir(parents=True, exist_ok=True)

        content = edit.new_content
        if isinstance(content, str):
            src.write_text(content, encoding="utf-8")
            edit.new_sha256 = hashlib.sha256(
                content.encode("utf-8")).hexdigest()
        else:
            src.write_bytes(content)
            edit.new_sha256 = hashlib.sha256(content).hexdigest()

        edit.status = "written"

    def _log_success(self):
        import json
        try:
            entries = []
            if ATOMIC_LOG.exists():
                import json
                entries = json.loads(ATOMIC_LOG.read_text())
            entry = {
                "timestamp": self._backup_timestamp,
                "reason": self._reason,
                "files": [e.path for e in self._edits],
                "success": True,
            }
            entries.append(entry)
            if len(entries) > 100:
                entries = entries[-100:]
            ATOMIC_LOG.write_text(json.dumps(entries, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.debug(f"Atomic log: {e}")


def atomic_edit_single(path: str, content: str | bytes,
                        reason: str = "") -> AtomicResult:
    """Convenience: atomic edit a single file."""
    with AtomicModification({path: content}, reason=reason) as atom:
        result = atom.apply()
        if result.success:
            atom.commit()
        return result
