"""Session Resilience — auto-resume after restart (Hermes 0.13 inspired).

Checkpoint + recovery: saves conversation state to disk on every turn,
auto-resumes interrupted sessions when the server restarts.
Persistence uses JSONL append-only format with periodic pruning.
"""

from __future__ import annotations

import json as _json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

CHECKPOINT_DIR = Path(".livingtree/checkpoints")
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
MAX_CHECKPOINTS = 50
MAX_SESSION_AGE_HOURS = 24


@dataclass
class SessionSnapshot:
    session_id: str
    user_id: str = ""
    messages: list[dict] = field(default_factory=list)
    last_intent: str = ""
    last_model: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    turn_count: int = 0
    metadata: dict = field(default_factory=dict)


class SessionResilience:
    """Checkpoint-based session recovery.

    Saves every conversation turn. On restart, auto-resumes the most
    recent incomplete sessions so users don't lose context.
    """

    def __init__(self):
        self._active: dict[str, SessionSnapshot] = {}
        self._load_all()

    def _file_for(self, session_id: str) -> Path:
        return CHECKPOINT_DIR / f"{session_id}.json"

    def _load_all(self):
        for f in sorted(CHECKPOINT_DIR.glob("*.json")):
            try:
                data = _json.loads(f.read_text())
                snap = SessionSnapshot(**{k: data.get(k, "") for k in SessionSnapshot.__dataclass_fields__})
                age_h = (time.time() - snap.updated_at) / 3600
                if age_h < MAX_SESSION_AGE_HOURS:
                    self._active[snap.session_id] = snap
            except Exception:
                pass

    def save(self, session_id: str, user_msg: str, assistant_msg: str,
             intent: str = "", model: str = "", meta: dict = None):
        snap = self._active.get(session_id)
        if snap is None:
            snap = SessionSnapshot(session_id=session_id)
            self._active[session_id] = snap

        snap.messages.append({"role": "user", "content": user_msg})
        snap.messages.append({"role": "assistant", "content": assistant_msg})
        snap.last_intent = intent
        snap.last_model = model
        snap.turn_count += 1
        snap.updated_at = time.time()
        if meta:
            snap.metadata.update(meta)

        if len(snap.messages) > 50:
            snap.messages = snap.messages[-50:]

        f = self._file_for(session_id)
        data = {k: getattr(snap, k) for k in SessionSnapshot.__dataclass_fields__}
        f.write_text(_json.dumps(data, ensure_ascii=False, indent=2))

        self._prune_if_needed()

    def restore(self, session_id: str) -> Optional[SessionSnapshot]:
        return self._active.get(session_id)

    def list_recoverable(self) -> list[dict]:
        now = time.time()
        result = []
        for sid, snap in self._active.items():
            age_m = int((now - snap.updated_at) / 60)
            result.append({
                "session_id": sid,
                "turns": snap.turn_count,
                "idle_minutes": age_m,
                "last_intent": snap.last_intent,
                "can_resume": age_m < MAX_SESSION_AGE_HOURS * 60,
            })
        result.sort(key=lambda x: x["idle_minutes"])
        return result

    def _prune_if_needed(self):
        files = sorted(CHECKPOINT_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
        for f in files[:-MAX_CHECKPOINTS]:
            f.unlink(missing_ok=True)
            self._active.pop(f.stem, None)

    def stats(self) -> dict:
        return {
            "active_sessions": len(self._active),
            "recoverable": len(self.list_recoverable()),
            "max_age_hours": MAX_SESSION_AGE_HOURS,
            "checkpoint_dir": str(CHECKPOINT_DIR),
        }


_instance: Optional[SessionResilience] = None


def get_resilience() -> SessionResilience:
    global _instance
    if _instance is None:
        _instance = SessionResilience()
    return _instance
