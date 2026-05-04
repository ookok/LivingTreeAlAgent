"""Session Manager — Full session save/resume with persistence.

Extends TaskCheckpoint with full chat history and side-git integration.
Supports listing, resuming, and archiving sessions across process restarts.

Usage:
    sm = SessionManager()
    
    # Save current session
    await sm.save("my-session", messages=[...], workspace=".")
    
    # List sessions
    sessions = await sm.list_sessions()
    
    # Resume last session
    state = await sm.resume("my-session")
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field


class SessionState(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    workspace: str = "."
    messages: list[dict[str, Any]] = Field(default_factory=list)
    total_tokens: int = 0
    reasoning_effort: str = "max"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    tags: list[str] = Field(default_factory=list)
    archived: bool = False
    side_git_turns: list[int] = Field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()


class SessionManager:
    """Persistent session management for chat and agent sessions."""

    SESSIONS_DIR = ".livingtree/sessions"

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace).resolve()
        self._store = self._workspace / self.SESSIONS_DIR
        self._store.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, SessionState] = {}

    async def save(self, state: SessionState) -> Path:
        state.updated_at = datetime.now(timezone.utc).isoformat()
        self._cache[state.session_id] = state
        path = self._store / f"{state.session_id}.json"
        path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        logger.debug(f"Session saved: {state.session_id} ({len(state.messages)} msgs)")
        return path

    async def load(self, session_id: str) -> Optional[SessionState]:
        if session_id in self._cache:
            return self._cache[session_id]
        path = self._store / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            state = SessionState(**data)
            self._cache[session_id] = state
            return state
        except Exception as e:
            logger.warning(f"Session load failed: {e}")
            return None

    async def list_sessions(self, include_archived: bool = False) -> list[dict]:
        sessions = []
        for p in sorted(self._store.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                state = SessionState(**data)
                if state.archived and not include_archived:
                    continue
                sessions.append({
                    "session_id": state.session_id,
                    "name": state.name or p.stem,
                    "workspace": state.workspace,
                    "messages_count": len(state.messages),
                    "tokens": state.total_tokens,
                    "effort": state.reasoning_effort,
                    "created": state.created_at[:19],
                    "updated": state.updated_at[:19] if state.updated_at else "",
                    "archived": state.archived,
                    "tags": state.tags,
                })
            except Exception:
                continue
        return sessions

    async def delete(self, session_id: str) -> bool:
        self._cache.pop(session_id, None)
        path = self._store / f"{session_id}.json"
        path.unlink(missing_ok=True)
        return True

    async def archive(self, session_id: str) -> bool:
        state = await self.load(session_id)
        if not state:
            return False
        state.archived = True
        await self.save(state)
        return True

    async def resume_latest(self) -> Optional[SessionState]:
        sessions = await self.list_sessions()
        if not sessions:
            return None
        latest = sessions[0]
        return await self.load(latest["session_id"])

    async def cleanup_old(self, max_age_days: float = 30.0) -> int:
        import time
        threshold = time.time() - max_age_days * 86400
        removed = 0
        for p in self._store.glob("*.json"):
            if p.stat().st_mtime < threshold:
                p.unlink()
                removed += 1
        return removed
