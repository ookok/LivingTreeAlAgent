"""SideGit — Workspace rollback via side-git pre/post-turn snapshots.

Inspired by DeepSeek-TUI's workspace rollback feature. Creates automatic
git snapshots before and after each agent turn, without touching the
user's actual .git repository. Uses a separate .livingtree-git directory.

Usage:
    sidegit = SideGit(workspace_path=".")
    
    # Before agent actions
    turn_id = await sidegit.pre_turn()
    
    # ... agent modifies files ...
    
    # After — can rollback if needed
    await sidegit.post_turn(turn_id)
    
    # Rollback to a specific turn
    await sidegit.restore(turn_id)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger


class TurnSnapshot:
    """Snapshot of the workspace at a specific turn."""

    def __init__(
        self,
        turn_id: int,
        workspace: str,
        snapshot_path: Path,
        timestamp: str | None = None,
    ):
        self.turn_id = turn_id
        self.workspace = workspace
        self.snapshot_path = snapshot_path
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def model_dump(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "workspace": self.workspace,
            "timestamp": self.timestamp,
        }


class SideGit:
    """Non-invasive git snapshot system for workspace rollback.

    Creates snapshots in .livingtree/snapshots/ using git rather than
    the user's .git directory. Allows /restore to revert all agent
    changes without touching the user's repository state.
    """

    def __init__(self, workspace_path: str = "."):
        self._workspace = Path(workspace_path).resolve()
        self._snapshots_dir = self._workspace / ".livingtree" / "snapshots"
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._turns: list[TurnSnapshot] = []
        self._turn_counter = 0

    async def pre_turn(self) -> int:
        """Create a pre-turn snapshot. Returns turn_id."""
        self._turn_counter += 1
        turn_id = self._turn_counter
        snapshot_path = self._snapshots_dir / f"turn_{turn_id}"

        try:
            await self._save_snapshot(snapshot_path)
            snap = TurnSnapshot(
                turn_id=turn_id,
                workspace=str(self._workspace),
                snapshot_path=snapshot_path,
            )
            self._turns.append(snap)
            logger.debug(f"SideGit pre_turn {turn_id}: saved {len(list(snapshot_path.rglob('*')))} files")
        except Exception as e:
            logger.warning(f"SideGit pre_turn {turn_id} failed: {e}")

        return turn_id

    async def post_turn(self, turn_id: int) -> list[str]:
        """Create a post-turn diff. Returns list of changed files."""
        before = self._snapshots_dir / f"turn_{turn_id}"
        after = self._snapshots_dir / f"turn_{turn_id}_after"

        try:
            await self._save_snapshot(after)
            changes = self._diff_snapshots(before, after)
            logger.debug(f"SideGit post_turn {turn_id}: {len(changes)} changed files")
            return changes
        except Exception as e:
            logger.warning(f"SideGit post_turn {turn_id} failed: {e}")
            return []

    async def restore(self, turn_id: int) -> bool:
        """Restore workspace to the state at turn_id."""
        snapshot_path = self._snapshots_dir / f"turn_{turn_id}"
        if not snapshot_path.exists():
            logger.warning(f"Snapshot turn_{turn_id} not found")
            return False

        try:
            changed = self._diff_snapshots(
                snapshot_path,
                self._snapshots_dir / f"turn_{turn_id}_after",
            ) if (self._snapshots_dir / f"turn_{turn_id}_after").exists() else []

            for root, dirs, files in os.walk(snapshot_path):
                rel_root = Path(root).relative_to(snapshot_path)
                for fname in files:
                    src = snapshot_path / rel_root / fname
                    dst = self._workspace / rel_root / fname
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src), str(dst))

            for changed_file in changed:
                p = self._workspace / changed_file
                if not p.exists():
                    p.unlink(missing_ok=True)

            logger.info(f"SideGit restore turn_{turn_id}: workspace restored ({len(changed)} files)")
            return True
        except Exception as e:
            logger.error(f"SideGit restore turn_{turn_id} failed: {e}")
            return False

    async def revert_turn(self, turn_id: int) -> bool:
        """Alias for restore. Revert workspace to state before turn_id."""
        return await self.restore(turn_id)

    async def list_turns(self) -> list[dict]:
        """List all available snapshots."""
        return [
            {
                "turn_id": t.turn_id,
                "timestamp": t.timestamp,
                "workspace": t.workspace,
            }
            for t in self._turns
        ]

    async def cleanup(self, keep_last: int = 20) -> int:
        """Remove old snapshots, keeping the most recent N."""
        removed = 0
        to_keep = set()
        for snap in self._turns[-keep_last:]:
            to_keep.add(f"turn_{snap.turn_id}")
            to_keep.add(f"turn_{snap.turn_id}_after")

        for p in sorted(self._snapshots_dir.iterdir()):
            if p.is_dir() and p.name not in to_keep:
                shutil.rmtree(str(p), ignore_errors=True)
                removed += 1

        self._turns = self._turns[-keep_last:]
        return removed

    async def _save_snapshot(self, dest: Path) -> None:
        """Save current workspace state to dest directory."""
        if dest.exists():
            shutil.rmtree(str(dest), ignore_errors=True)
        dest.mkdir(parents=True, exist_ok=True)

        excluded = {
            ".git", ".livingtree", "__pycache__", ".venv", "venv",
            "node_modules", ".mypy_cache", ".pytest_cache",
            "*.pyc", ".DS_Store", "*.egg-info",
        }

        for root, dirs, files in os.walk(str(self._workspace), topdown=True):
            dirs[:] = [d for d in dirs if d not in excluded]

            rel_root = Path(root).relative_to(self._workspace)

            for fname in files:
                if any(fname.endswith(s.replace("*", "")) for s in excluded):
                    continue
                src = Path(root) / fname
                dst = dest / rel_root / fname
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(str(src), str(dst))
                except (PermissionError, OSError):
                    pass

    def _diff_snapshots(self, before: Path, after: Path) -> list[str]:
        """Return list of files changed between two snapshots."""
        changes = []
        if not before.exists():
            return changes

        after_files = {}
        if after.exists():
            for f in after.rglob("*"):
                if f.is_file():
                    rel = str(f.relative_to(after))
                    after_files[rel] = f

        for f in before.rglob("*"):
            if f.is_file():
                rel = str(f.relative_to(before))
                if rel in after_files:
                    try:
                        b_data = f.read_bytes()
                        a_data = after_files[rel].read_bytes()
                        if b_data != a_data:
                            changes.append(rel)
                    except Exception:
                        changes.append(rel)
                else:
                    changes.append(rel)

        changes.extend(
            rel for rel in after_files
            if rel not in {str(f.relative_to(before)) for f in before.rglob("*") if f.is_file()}
        )

        return changes
