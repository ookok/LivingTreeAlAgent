"""ErrorReplay — operation recording + LLM replay analysis + self-healing.

    Like a dashcam for AI operations. Records every action, file state,
    and dependency so the LLM can rewind and understand WHY an error happened —
    not just read the error message.

    Four-layer recording:
      Layer 1 — Timeline: timestamped events (user input, tool call, error)
      Layer 2 — Snapshots: file state before/after each modification
      Layer 3 — Dependencies: DataLineage graph at point of failure
      Layer 4 — Lessons: accumulated fix patterns across sessions

    Self-healing loop:
      Error → Record complete session → Idle time triggers replay
        → LLM analyzes root cause → Proposes fix → Sandbox test
        → Valid? Apply fix + update TrustScore
        → Invalid? Escalate to user with full replay

    Commands:
      /errors        — list recent error replays
      /replay <id>   — replay a specific error session
      /replay fix    — trigger self-healing on latest error

    Usage:
        recorder = get_error_recorder()
        session = recorder.start_session("config-edit")
        recorder.record("user_input", "改config.yaml端口")
        recorder.record("file_read", "config.yaml", content_before)
        recorder.record("file_write", "config.yaml", content_after)
        recorder.record("error", "ImportError: server.py port mismatch")
        recorder.close_session()

        await replay_engine.analyze(session, hub)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

REPLAY_DIR = Path(".livingtree/replays")
REPLAY_INDEX = REPLAY_DIR / "index.json"
LESSONS_FILE = REPLAY_DIR / "lessons.json"
MAX_SESSIONS = 50
MAX_SNAPSHOT_SIZE = 50000  # bytes


# ═══ Data Classes ═══

@dataclass
class TimelineEvent:
    seq: int
    event_type: str        # user_input, file_read, file_write, tool_call, llm_response, error, fix_applied
    description: str = ""
    filepath: str = ""
    content_hash: str = ""    # SHA256 of content at this point
    content_preview: str = "" # first N chars
    error_msg: str = ""
    error_type: str = ""      # ImportError, SyntaxError, OSError, ValueError...
    metadata: dict = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class ReplaySession:
    session_id: str
    task: str = ""                          # what the user was trying to do
    status: str = "recording"              # recording, closed, analyzed, fixed, escalated
    events: list[TimelineEvent] = field(default_factory=list)
    started_at: float = 0.0
    ended_at: float = 0.0
    error_count: int = 0
    root_cause: str = ""                    # LLM's analysis
    fix_proposal: str = ""                  # LLM's proposed fix
    fix_applied: bool = False
    fix_validated: bool = False
    analysis_at: float = 0.0
    lesson_id: str = ""                     # link to lesson in lessons.json


@dataclass
class Lesson:
    lesson_id: str
    pattern: str = ""                       # "config change without server restart"
    root_cause: str = ""                    # typical root cause
    fix_strategy: str = ""                  # how to fix
    occurrences: int = 1
    last_seen: float = 0.0
    auto_fix_confidence: float = 0.5


# ═══ Operation Recorder ═══

class OperationRecorder:
    """Records operation timeline with file state snapshots."""

    def __init__(self):
        REPLAY_DIR.mkdir(parents=True, exist_ok=True)
        self._active: dict[str, ReplaySession] = {}
        self._sessions: dict[str, ReplaySession] = {}
        self._lessons: dict[str, Lesson] = {}
        self._seq = 0
        self._load()

    def start_session(self, task: str = "") -> str:
        """Start recording a new operation session.

        Args:
            task: What the user is trying to accomplish
        Returns:
            session_id
        """
        session_id = f"replay_{int(time.time())}_{hashlib.md5(task.encode()).hexdigest()[:6]}"
        session = ReplaySession(
            session_id=session_id,
            task=task,
            status="recording",
            started_at=time.time(),
        )
        self._active[session_id] = session
        self._active["_current"] = session  # current session shortcut
        logger.debug(f"Recording started: {session_id}")
        return session_id

    def record(
        self,
        event_type: str,
        description: str = "",
        filepath: str = "",
        content: str = "",
        error_msg: str = "",
        error_type: str = "",
        metadata: dict | None = None,
    ):
        """Record an event in the current session.

        Args:
            event_type: user_input, file_read, file_write, tool_call, llm_response, error, fix
            description: Human-readable what happened
            filepath: Affected file path
            content: File content (for file_read/write events)
            error_msg: Error message (for error events)
            error_type: Python exception type
            metadata: Extra data
        """
        session = self._active.get("_current")
        if not session:
            session = self._active[self.start_session("unknown")]

        self._seq += 1
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16] if content else ""
        preview = content[:200] if content else ""

        if event_type == "error":
            session.error_count += 1
            session.status = "closed"
            session.ended_at = time.time()

        event = TimelineEvent(
            seq=self._seq,
            event_type=event_type,
            description=description,
            filepath=filepath,
            content_hash=content_hash,
            content_preview=preview,
            error_msg=error_msg[:500],
            error_type=error_type,
            metadata=metadata or {},
            timestamp=time.time(),
        )
        session.events.append(event)

        # Auto-save on error
        if event_type == "error":
            self._save_session(session)

    def close_session(self) -> str:
        """Close current session and persist."""
        session = self._active.pop("_current", None)
        if not session:
            return ""
        session.status = "closed" if not session.error_count else session.status
        session.ended_at = time.time()
        self._save_session(session)
        self._trim_old_sessions()
        return session.session_id

    def get_session(self, session_id: str) -> ReplaySession | None:
        return self._sessions.get(session_id)

    def list_sessions(self, n: int = 20) -> list[ReplaySession]:
        return sorted(
            self._sessions.values(),
            key=lambda s: s.started_at,
            reverse=True,
        )[:n]

    def recent_errors(self, n: int = 5) -> list[ReplaySession]:
        return [
            s for s in self.list_sessions(n * 2)
            if s.error_count > 0
        ][:n]

    def _save_session(self, session: ReplaySession):
        self._sessions[session.session_id] = session
        fpath = REPLAY_DIR / f"{session.session_id}.json"
        data = {
            "session_id": session.session_id,
            "task": session.task,
            "status": session.status,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "error_count": session.error_count,
            "root_cause": session.root_cause,
            "fix_proposal": session.fix_proposal,
            "fix_applied": session.fix_applied,
            "fix_validated": session.fix_validated,
            "lesson_id": session.lesson_id,
            "events": [
                {
                    "seq": e.seq, "event_type": e.event_type,
                    "description": e.description, "filepath": e.filepath,
                    "content_hash": e.content_hash,
                    "content_preview": e.content_preview,
                    "error_msg": e.error_msg, "error_type": e.error_type,
                    "metadata": e.metadata, "timestamp": e.timestamp,
                }
                for e in session.events
            ],
        }
        fpath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _trim_old_sessions(self):
        all_sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.started_at, reverse=True,
        )
        for old in all_sessions[MAX_SESSIONS:]:
            fpath = REPLAY_DIR / f"{old.session_id}.json"
            fpath.unlink(missing_ok=True)
            self._sessions.pop(old.session_id, None)

    def _load(self):
        if not REPLAY_DIR.exists():
            return
        for fpath in sorted(REPLAY_DIR.glob("*.json")):
            if fpath.name in ("index.json", "lessons.json"):
                continue
            try:
                d = json.loads(fpath.read_text(encoding="utf-8"))
                session = ReplaySession(
                    session_id=d.get("session_id", ""),
                    task=d.get("task", ""),
                    status=d.get("status", ""),
                    started_at=d.get("started_at", 0),
                    ended_at=d.get("ended_at", 0),
                    error_count=d.get("error_count", 0),
                    root_cause=d.get("root_cause", ""),
                    fix_proposal=d.get("fix_proposal", ""),
                    fix_applied=d.get("fix_applied", False),
                    fix_validated=d.get("fix_validated", False),
                    lesson_id=d.get("lesson_id", ""),
                )
                session.events = [
                    TimelineEvent(
                        seq=e.get("seq", 0), event_type=e.get("event_type", ""),
                        description=e.get("description", ""),
                        filepath=e.get("filepath", ""),
                        content_hash=e.get("content_hash", ""),
                        content_preview=e.get("content_preview", ""),
                        error_msg=e.get("error_msg", ""),
                        error_type=e.get("error_type", ""),
                        metadata=e.get("metadata", {}),
                        timestamp=e.get("timestamp", 0),
                    )
                    for e in d.get("events", [])
                ]
                self._sessions[session.session_id] = session
            except Exception:
                pass

        self._load_lessons()

    def _load_lessons(self):
        if not LESSONS_FILE.exists():
            return
        try:
            data = json.loads(LESSONS_FILE.read_text(encoding="utf-8"))
            for lid, d in data.items():
                self._lessons[lid] = Lesson(
                    lesson_id=lid,
                    pattern=d.get("pattern", ""),
                    root_cause=d.get("root_cause", ""),
                    fix_strategy=d.get("fix_strategy", ""),
                    occurrences=d.get("occurrences", 1),
                    last_seen=d.get("last_seen", 0),
                    auto_fix_confidence=d.get("auto_fix_confidence", 0.5),
                )
        except Exception:
            pass

    def _save_lessons(self):
        data = {}
        for lid, l in self._lessons.items():
            data[lid] = {
                "lesson_id": l.lesson_id,
                "pattern": l.pattern,
                "root_cause": l.root_cause,
                "fix_strategy": l.fix_strategy,
                "occurrences": l.occurrences,
                "last_seen": l.last_seen,
                "auto_fix_confidence": l.auto_fix_confidence,
            }
        LESSONS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ═══ Replay Engine ═══

class ReplayEngine:
    """LLM replays recorded operations to find root cause and propose fixes."""

    def __init__(self, recorder: OperationRecorder):
        self._recorder = recorder

    async def analyze(self, session_id: str, hub) -> ReplaySession | None:
        """LLM replays a session to find the root cause.

        Returns the session with root_cause and fix_proposal populated.
        """
        session = self._recorder.get_session(session_id)
        if not session or not hub or not hub.world:
            return session

        # Build timeline for LLM
        timeline = "\n".join(
            f"  [{e.seq}] {e.event_type}: {e.description[:120]}"
            + (f" (file: {e.filepath})" if e.filepath else "")
            + (f" ERROR: {e.error_msg[:100]}" if e.error_type else "")
            for e in session.events
        )[:6000]

        # Include file states from read/write events
        file_changes = "\n".join(
            f"  [{e.seq}] {e.event_type} {e.filepath}: {e.content_preview[:150]}"
            for e in session.events
            if e.event_type in ("file_read", "file_write") and e.content_preview
        )[:3000]

        errors = [e for e in session.events if e.event_type == "error"]

        # Check if similar pattern exists in lessons
        matched_lesson = self._match_lesson(session)

        llm = hub.world.consciousness._llm
        try:
            prompt = (
                f"Analyze this operation replay to find the ROOT CAUSE of the error.\n\n"
                f"TASK: {session.task}\n\n"
                f"TIMELINE:\n{timeline}\n\n"
                + (f"FILE CHANGES:\n{file_changes}\n\n" if file_changes else "")
                + (f"PREVIOUS LESSON: {matched_lesson.fix_strategy}\n\n" if matched_lesson else "")
                + "Output JSON:\n"
                '{"root_cause": "one-line explanation of WHY this happened", '
                '"fix_proposal": "specific fix (code or action)", '
                '"lesson_pattern": "reusable pattern name", '
                '"auto_fix_confidence": 0.0-1.0, '
                '"affected_files": ["file1", "file2"]}'
            )

            result = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.2, max_tokens=600, timeout=25,
            )

            if result and result.text:
                import re
                m = re.search(r'\{[\s\S]*\}', result.text)
                if m:
                    d = json.loads(m.group())
                    session.root_cause = d.get("root_cause", "")
                    session.fix_proposal = d.get("fix_proposal", "")
                    session.analysis_at = time.time()
                    session.status = "analyzed"

                    # Save as lesson
                    lid = f"lesson_{hashlib.md5(d.get('lesson_pattern', '').encode()).hexdigest()[:10]}"
                    if lid not in self._recorder._lessons:
                        self._recorder._lessons[lid] = Lesson(
                            lesson_id=lid,
                            pattern=d.get("lesson_pattern", ""),
                            root_cause=d.get("root_cause", ""),
                            fix_strategy=d.get("fix_proposal", ""),
                            occurrences=1,
                            last_seen=time.time(),
                            auto_fix_confidence=d.get("auto_fix_confidence", 0.5),
                        )
                    else:
                        l = self._recorder._lessons[lid]
                        l.occurrences += 1
                        l.last_seen = time.time()
                        l.auto_fix_confidence = min(0.95, l.auto_fix_confidence + 0.05)
                    session.lesson_id = lid
                    self._recorder._save_lessons()
                    self._recorder._save_session(session)

                    logger.info(f"Replay analyzed: {session.root_cause[:80]}...")
        except Exception as e:
            logger.debug(f"Replay analyze: {e}")

        return session

    async def self_heal(self, session_id: str, hub) -> dict:
        """Attempt to auto-fix based on replay analysis.

        Returns {success, applied, message}
        """
        session = self._recorder.get_session(session_id)
        if not session or not session.root_cause:
            return {"success": False, "message": "Session not analyzed yet"}

        lesson = self._recorder._lessons.get(session.lesson_id) if session.lesson_id else None
        if lesson and lesson.auto_fix_confidence < 0.7:
            return {"success": False, "message": f"Confidence too low ({lesson.auto_fix_confidence:.0%}), needs human review"}

        # Try to apply fix
        try:
            from ..capability.self_modifier import get_self_modifier
            sm = get_self_modifier()
            result = await sm.modify(session.fix_proposal, hub, dry_run=False)

            if result.success and not result.rolled_back:
                session.fix_applied = True
                session.fix_validated = True
                session.status = "fixed"
                self._recorder._save_session(session)
                return {"success": True, "message": f"Fix applied: {', '.join(result.files_changed[:5])}"}
            else:
                session.status = "escalated"
                self._recorder._save_session(session)
                return {"success": False, "message": result.error or "Fix validation failed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _match_lesson(self, session: ReplaySession) -> Lesson | None:
        """Find a matching lesson based on error type pattern."""
        error_types = set(e.error_type for e in session.events if e.error_type)
        for lesson in self._recorder._lessons.values():
            if any(et.lower() in lesson.pattern.lower() for et in error_types):
                return lesson
            if any(et.lower() in lesson.root_cause.lower() for et in error_types):
                return lesson
        return None


# ═══ Convenience ═══

class ErrorReplay:
    """Unified error recording + replay + self-healing."""

    def __init__(self):
        self.recorder = OperationRecorder()
        self.replay = ReplayEngine(self.recorder)

    async def auto_heal_cycle(self, hub):
        """Run during idle: analyze latest unanalyzed errors and auto-fix.

        Called by IdleConsolidator.
        """
        unanalyzed = [
            s for s in self.recorder.list_sessions(20)
            if s.status in ("closed",) and not s.root_cause
        ]
        for session in unanalyzed[:3]:
            await self.replay.analyze(session.session_id, hub)
            if session.root_cause and session.fix_proposal:
                result = await self.replay.self_heal(session.session_id, hub)
                logger.info(f"Self-heal: {result['message'][:100]}")

    def wrap_error(self, error: Exception, context: str = "") -> str:
        """Record an error and return session ID."""
        import traceback
        tb = traceback.format_exc()
        sid = self.recorder.start_session(context or str(error)[:80])
        self.recorder.record(
            "error",
            description=context,
            error_msg=str(error),
            error_type=type(error).__name__,
            metadata={"traceback": tb[:2000]},
        )
        self.recorder.close_session()
        return sid


_er: ErrorReplay | None = None


def get_error_replay() -> ErrorReplay:
    global _er
    if _er is None:
        _er = ErrorReplay()
    return _er
