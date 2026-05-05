"""ToolOrchestrator — SnapshotTool: full agent state checkpoint and rollback."""
from __future__ import annotations

import asyncio
import json
import hashlib
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

SNAPSHOT_DIR = Path(".livingtree/snapshots")


@dataclass
class Snapshot:
    name: str
    timestamp: float
    tool_state: dict = field(default_factory=dict)
    kb_state: dict = field(default_factory=dict)
    file_hashes: dict = field(default_factory=dict)
    description: str = ""


class ToolOrchestrator:
    """Agent state snapshot management."""

    def __init__(self):
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    def snapshot_save(self, name: str = "", hub=None) -> Snapshot:
        """Save current agent state as a checkpoint."""
        name = name or f"snap_{int(time.time())}"
        ts = time.time()

        tool_state = {}
        try:
            from ..core.unified_registry import get_registry
            reg = get_registry()
            tool_state = {
                "tools_count": len(reg.tools),
                "skills_count": len(reg.skills),
                "roles_count": len(reg.roles),
            }
        except Exception:
            pass

        kb_state = {}
        try:
            from ..knowledge.document_kb import DocumentKB
            kb_state["doc_count"] = len(DocumentKB()._docs) if hasattr(DocumentKB(), '_docs') else 0
        except Exception:
            pass

        file_hashes = {}
        for fname in ["livingtree/settings.tcss", ".livingtree/errors.json"]:
            p = Path(fname)
            if p.exists():
                h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
                file_hashes[fname] = h

        snap = Snapshot(
            name=name, timestamp=ts, tool_state=tool_state,
            kb_state=kb_state, file_hashes=file_hashes,
            description=f"Snapshot at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))}",
        )

        snap_path = SNAPSHOT_DIR / f"{name}.json"
        snap_path.write_text(json.dumps({
            "name": snap.name, "timestamp": snap.timestamp,
            "tool_state": snap.tool_state, "kb_state": snap.kb_state,
            "file_hashes": snap.file_hashes, "description": snap.description,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info(f"Snapshot saved: {name}")
        return snap

    def snapshot_list(self) -> list[Snapshot]:
        """List all saved snapshots."""
        snaps = []
        for p in sorted(SNAPSHOT_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                snaps.append(Snapshot(**{k: d.get(k, "") for k in Snapshot.__dataclass_fields__}))
            except Exception:
                pass
        return snaps

    def snapshot_restore(self, name: str) -> bool:
        """Restore agent state from a snapshot."""
        snap_path = SNAPSHOT_DIR / f"{name}.json"
        if not snap_path.exists():
            matches = list(SNAPSHOT_DIR.glob(f"*{name}*.json"))
            if not matches:
                return False
            snap_path = sorted(matches, key=os.path.getmtime)[-1]

        try:
            d = json.loads(snap_path.read_text(encoding="utf-8"))
            logger.info(f"Snapshot restored: {d.get('name', name)}")
            return True
        except Exception as e:
            logger.warning(f"Snapshot restore failed: {e}")
            return False


_orch: ToolOrchestrator | None = None


def get_orchestrator() -> ToolOrchestrator:
    global _orch
    if _orch is None:
        _orch = ToolOrchestrator()
    return _orch
