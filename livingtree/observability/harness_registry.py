"""
Harness Registry — Agentic Harness-style file-level safety net.

Before any agent edits a file, this registry snapshots it. After the edit,
the diff and rollback capability ensure the file can be restored if needed.

Inspired by the Agentic Harness paper: "every file operation is a harnessed operation
with guaranteed rollback."

Usage:
    from livingtree.observability.harness_registry import get_harness, HARNESS_REGISTRY
    h = get_harness()
    idx = h.snapshot("path/to/file.py")
    # ... agent edits file ...
    diff = h.diff("path/to/file.py")
    # if something went wrong:
    h.rollback("path/to/file.py", to_index=idx)
"""

from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from loguru import logger

HARNESS_DIR = Path(".livingtree/harness")
SNAPSHOTS_DIR = HARNESS_DIR / "snapshots"
REGISTRY_FILE = HARNESS_DIR / "registry.json"


@dataclass
class FileAnnulus:
    """A single file snapshot — the atomic unit of harness protection."""
    id: str
    file: str
    index: int  # sequential index per file
    snapshot_path: str  # path to saved content
    sha256: str
    size_bytes: int
    created_at: float
    trigger: str = "manual"  # "auto", "pre_edit", "manual"

    def to_dict(self) -> dict:
        return asdict(self)


class HarnessRegistry:
    """Manages file-level snapshots for safe agent editing.

    Core API:
    - snapshot(file): capture current state
    - diff(file, from_idx, to_idx): compute changes
    - rollback(file, to_idx): restore from snapshot
    - list_snapshots(file): show history
    - clean(older_than_days): prune old snapshots
    """

    def __init__(self):
        HARNESS_DIR.mkdir(parents=True, exist_ok=True)
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        self._annuli: list[dict] = []
        self._load()

    # ── Core Operations ──

    def snapshot(self, file_path: str | Path, trigger: str = "auto") -> int:
        """Take a snapshot of a file. Returns the snapshot index.

        If the file doesn't exist, records a "not found" marker.
        Auto-computes SHA-256 for integrity verification.
        """
        file_path = Path(file_path)
        rel_path = str(file_path)
        existing = [a for a in self._annuli if a["file"] == rel_path]
        next_idx = max((a["index"] for a in existing), default=-1) + 1

        if not file_path.exists():
            annulus = FileAnnulus(
                id=f"snap_{hashlib.md5(f'{rel_path}:{next_idx}'.encode()).hexdigest()[:12]}",
                file=rel_path,
                index=next_idx,
                snapshot_path="",
                sha256="",
                size_bytes=0,
                created_at=time.time(),
                trigger=trigger,
            )
            self._annuli.append(annulus.to_dict())
            self._save()
            logger.debug(f"Harness snapshot [{next_idx}]: {rel_path} (file not found)")
            return next_idx

        # Read and hash the file
        content = file_path.read_bytes()
        sha = hashlib.sha256(content).hexdigest()

        # Save snapshot copy
        snap_name = f"{Path(rel_path).name}.{next_idx}.snap"
        snap_path = SNAPSHOTS_DIR / snap_name
        snap_path.write_bytes(content)

        annulus = FileAnnulus(
            id=f"snap_{sha[:12]}",
            file=rel_path,
            index=next_idx,
            snapshot_path=str(snap_path),
            sha256=sha,
            size_bytes=len(content),
            created_at=time.time(),
            trigger=trigger,
        )
        self._annuli.append(annulus.to_dict())
        self._save()
        logger.debug(f"Harness snapshot [{next_idx}]: {rel_path} ({len(content)}B, sha={sha[:8]})")
        return next_idx

    def diff(self, file_path: str | Path, from_idx: int = -2, to_idx: int = -1) -> str:
        """Compute unified diff between two snapshots of a file.

        Defaults: from_idx=-2 (second-to-last), to_idx=-1 (last/current).
        If from_idx < 0, it counts from the end (Python-style negative indexing).
        """
        file_path = Path(file_path)
        rel_path = str(file_path)
        annuli = sorted(
            [a for a in self._annuli if a["file"] == rel_path],
            key=lambda a: a["index"],
        )
        if len(annuli) < 2:
            return "Need at least 2 snapshots to diff"

        if from_idx < 0:
            from_idx = max(0, len(annuli) + from_idx)
        if to_idx < 0:
            to_idx = max(0, len(annuli) + to_idx)

        a_from = annuli[from_idx] if from_idx < len(annuli) else annuli[-1]
        a_to = annuli[to_idx] if to_idx < len(annuli) else annuli[-1]

        text_from = self._read_snapshot_content(a_from)
        text_to = self._read_snapshot_content(a_to)

        diff_lines = difflib.unified_diff(
            text_from.splitlines(keepends=True) if text_from else [],
            text_to.splitlines(keepends=True) if text_to else [],
            fromfile=f"{rel_path}@{a_from['index']}",
            tofile=f"{rel_path}@{a_to['index']}",
        )
        return "".join(diff_lines) or "No differences"

    def rollback(self, file_path: str | Path, to_index: int) -> bool:
        """Restore a file to the state captured at the given snapshot index.

        The current state is first snapshotted (as a safety net) before rollback.
        """
        file_path = Path(file_path)
        rel_path = str(file_path)
        annuli = sorted(
            [a for a in self._annuli if a["file"] == rel_path],
            key=lambda a: a["index"],
        )
        target = next((a for a in annuli if a["index"] == to_index), None)
        if not target:
            logger.warning(f"No snapshot at index {to_index} for {rel_path}")
            return False

        # Safety: snapshot current state first
        if file_path.exists():
            self.snapshot(rel_path, trigger="pre_rollback")

        # Restore content
        content = self._read_snapshot_bytes(target)
        if content is not None:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(content)
            logger.info(f"Rollback complete: {rel_path} → snapshot[{to_index}]")
            return True

        logger.warning(f"Snapshot content missing for {rel_path}[{to_index}]")
        return False

    # ── Query ──

    def list_snapshots(self, file_path: str | Path) -> list[FileAnnulus]:
        """List all snapshots for a file, ordered by index."""
        rel_path = str(Path(file_path))
        annuli = sorted(
            [a for a in self._annuli if a["file"] == rel_path],
            key=lambda a: a["index"],
        )
        return [FileAnnulus(**a) for a in annuli]

    def verify_integrity(self, file_path: str | Path | None = None) -> dict:
        """Verify SHA-256 integrity of snapshots. Returns verification report."""
        annuli = self._annuli
        if file_path:
            rel = str(Path(file_path))
            annuli = [a for a in annuli if a["file"] == rel]

        ok = 0
        missing = 0
        corrupted = 0

        for a in annuli:
            if not a["snapshot_path"] or not a["sha256"]:
                missing += 1
                continue
            snap = Path(a["snapshot_path"])
            if not snap.exists():
                missing += 1
                continue
            actual_sha = hashlib.sha256(snap.read_bytes()).hexdigest()
            if actual_sha != a["sha256"]:
                corrupted += 1
            else:
                ok += 1

        return {"total": len(annuli), "ok": ok, "missing": missing, "corrupted": corrupted,
                "healthy": corrupted == 0 and missing == 0}

    def clean(self, older_than_days: int = 30) -> int:
        """Remove snapshots older than N days. Returns count removed."""
        cutoff = time.time() - older_than_days * 86400
        removed = 0
        for a in list(self._annuli):
            if a["created_at"] < cutoff:
                # Delete snapshot file
                snap = Path(a["snapshot_path"])
                if snap.exists():
                    try:
                        snap.unlink()
                    except Exception:
                        pass
                self._annuli.remove(a)
                removed += 1
        if removed:
            self._save()
        logger.info(f"Harness cleanup: removed {removed} snapshots older than {older_than_days}d")
        return removed

    def get_stats(self) -> dict:
        """Get aggregate statistics about the harness registry."""
        files = {a["file"] for a in self._annuli}
        total_snapshots = len(self._annuli)
        total_size = sum(a.get("size_bytes", 0) for a in self._annuli)
        return {
            "files_tracked": len(files),
            "total_snapshots": total_snapshots,
            "total_size_mb": round(total_size / 1_000_000, 2),
            "files": sorted(files)[:20],
        }

    # ── Internal ──

    def _read_snapshot_content(self, annulus: dict) -> str | None:
        """Read snapshot content as text."""
        snap = Path(annulus["snapshot_path"])
        if snap.exists():
            return snap.read_text(encoding="utf-8", errors="replace")
        return None

    def _read_snapshot_bytes(self, annulus: dict) -> bytes | None:
        """Read snapshot content as bytes."""
        snap = Path(annulus["snapshot_path"])
        if snap.exists():
            return snap.read_bytes()
        return None

    def _save(self):
        try:
            REGISTRY_FILE.write_text(
                json.dumps(self._annuli, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save harness registry: {e}")

    def _load(self):
        if REGISTRY_FILE.exists():
            try:
                self._annuli = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._annuli = []


# ── Singleton ──

HARNESS_REGISTRY = HarnessRegistry()


def get_harness() -> HarnessRegistry:
    """Get the global HarnessRegistry singleton."""
    return HARNESS_REGISTRY
