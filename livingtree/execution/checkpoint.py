"""TaskCheckpoint — Save/restore execution state for long-running tasks.

Inspired by Hive's checkpoint-based crash recovery: persists execution
state so failed tasks can resume from the last checkpoint instead of
restarting from scratch.

Usage:
    cp = TaskCheckpoint()
    await cp.save(session_id, {"plan": [...], "completed": [0,1,2]})
    state = await cp.load(session_id)
    # resume from step 3
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field


class CheckpointState(BaseModel):
    session_id: str
    task_goal: str = ""
    plan: list[dict[str, Any]] = Field(default_factory=list)
    completed_steps: list[int] = Field(default_factory=list)
    current_step: int = 0
    execution_results: list[dict[str, Any]] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)
    success_rate: float = 0.0
    saved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 1


class TaskCheckpoint:
    """Persistent checkpoint system for task execution recovery.

    Auto-saves after each completed step. On failure, the next
    execution skips already-completed steps.
    """

    def __init__(self, store_path: str = "./data/checkpoints"):
        self._store = Path(store_path)
        self._store.mkdir(parents=True, exist_ok=True)
        self._in_memory: dict[str, CheckpointState] = {}

    async def save(self, session_id: str, state: CheckpointState) -> Path:
        """Save a checkpoint. Auto-versioned."""
        state.version += 1
        state.saved_at = datetime.now(timezone.utc).isoformat()
        self._in_memory[session_id] = state

        path = self._store / f"{session_id}.json"
        from ..core.task_guard import TaskGuard
        TaskGuard.atomic_write(path, state.model_dump_json(indent=2))
        logger.debug(f"Checkpoint saved: {session_id} v{state.version} ({state.current_step}/{len(state.plan)} steps)")
        return path

    async def load(self, session_id: str) -> Optional[CheckpointState]:
        """Load the latest checkpoint for a session."""
        if session_id in self._in_memory:
            return self._in_memory[session_id]

        path = self._store / f"{session_id}.json"
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            state = CheckpointState(**data)
            self._in_memory[session_id] = state
            logger.info(f"Checkpoint loaded: {session_id} (resume from step {state.current_step})")
            return state
        except Exception as e:
            logger.warning(f"Checkpoint load failed: {e}")
            return None

    async def resume(self, session_id: str) -> tuple[Optional[CheckpointState], list[dict[str, Any]]]:
        """Load checkpoint and return remaining uncompleted plan steps."""
        state = await self.load(session_id)
        if not state:
            return None, []

        completed = set(state.completed_steps)
        remaining = [s for i, s in enumerate(state.plan) if i not in completed]
        return state, remaining

    async def delete(self, session_id: str) -> None:
        """Remove a checkpoint after successful completion."""
        self._in_memory.pop(session_id, None)
        path = self._store / f"{session_id}.json"
        path.unlink(missing_ok=True)

    async def list_sessions(self) -> list[str]:
        return [p.stem for p in self._store.glob("*.json")]

    async def cleanup_old(self, max_age_hours: float = 24.0) -> int:
        """Remove checkpoints older than max_age_hours."""
        count = 0
        threshold = time.time() - max_age_hours * 3600
        for p in self._store.glob("*.json"):
            if p.stat().st_mtime < threshold:
                p.unlink()
                count += 1
        return count
