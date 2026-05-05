"""SessionContinuity — cross-session context persistence.

    Remembers what you were doing across restarts:
    1. Auto-save: persist session state before shutdown
    2. Resume: on next boot, show "Continue from last session?"
    3. Context carrier: last conversation summary, open files, active task
    4. Time-aware: shorter sessions = more detail, longer = summarized
    5. Multi-project: separate continuity per project directory

    Usage:
        sc = get_session_continuity()
        sc.save(hub)  # called on shutdown
        context = sc.load()  # called on boot
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

CONTINUITY_FILE = Path(".livingtree/session_continuity.json")


@dataclass
class SessionState:
    timestamp: float
    project_root: str = ""
    active_task: str = ""
    last_conversation_summary: str = ""
    open_files: list[str] = field(default_factory=list)
    decisions_made: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    providers_elected: list[str] = field(default_factory=list)
    session_duration_minutes: float = 0.0
    continuation_hint: str = ""


class SessionContinuity:
    """Cross-session persistence layer."""

    def __init__(self):
        self._state = SessionState(timestamp=0)
        self._start_time = time.time()

    async def save(self, hub=None) -> SessionState:
        """Save current session state before exit."""
        self._state.timestamp = time.time()
        self._state.project_root = str(Path.cwd())
        self._state.session_duration_minutes = (time.time() - self._start_time) / 60

        # Gather context
        self._state.open_files = self._scan_open_context()
        self._state.providers_elected = self._get_providers_active()

        # LLM summary if available
        if hub and hub.world:
            self._state.last_conversation_summary = await self._summarize_session(hub)
            self._state.continuation_hint = await self._generate_hint(hub)

        # Persist
        CONTINUITY_FILE.write_text(json.dumps({
            "timestamp": self._state.timestamp,
            "project_root": self._state.project_root,
            "active_task": self._state.active_task,
            "last_conversation_summary": self._state.last_conversation_summary,
            "open_files": self._state.open_files,
            "decisions_made": self._state.decisions_made,
            "tools_used": self._state.tools_used,
            "session_duration_minutes": self._state.session_duration_minutes,
            "continuation_hint": self._state.continuation_hint,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info(f"Session saved: {self._state.last_conversation_summary[:60]}...")
        return self._state

    def load(self) -> SessionState | None:
        """Load continuation context from last session."""
        if not CONTINUITY_FILE.exists():
            return None

        try:
            d = json.loads(CONTINUITY_FILE.read_text(encoding="utf-8"))
            # Validate: not too old (7 days)
            age_hours = (time.time() - d.get("timestamp", 0)) / 3600
            if age_hours > 7 * 24:
                CONTINUITY_FILE.unlink(missing_ok=True)
                return None

            self._state = SessionState(
                timestamp=d.get("timestamp", 0),
                project_root=d.get("project_root", ""),
                active_task=d.get("active_task", ""),
                last_conversation_summary=d.get("last_conversation_summary", ""),
                open_files=d.get("open_files", []),
                decisions_made=d.get("decisions_made", []),
                tools_used=d.get("tools_used", []),
                session_duration_minutes=d.get("session_duration_minutes", 0),
                continuation_hint=d.get("continuation_hint", ""),
            )
            return self._state
        except Exception as e:
            logger.debug(f"Session load: {e}")
            return None

    def resume_text(self) -> str:
        """Generate brief resume text for UI."""
        state = self.load()
        if not state:
            return ""

        lines = ["[dim]上次:[/dim]"]
        if state.last_conversation_summary:
            lines.append(f"  {state.last_conversation_summary[:120]}")
        if state.decisions_made:
            lines.append(f"  [dim]决策: {state.decisions_made[0][:80]}[/dim]")
        if state.continuation_hint:
            lines.append(f"\n[bold]{state.continuation_hint}[/bold]")

        # Age
        age = (time.time() - state.timestamp) / 3600
        if age < 1:
            lines.append(f"  [dim]{int(age * 60)}分钟前[/dim]")
        elif age < 24:
            lines.append(f"  [dim]{int(age)}小时前[/dim]")
        else:
            lines.append(f"  [dim]{int(age / 24)}天前[/dim]")

        return "\n".join(lines)

    def mark_decision(self, decision: str):
        """Record a key decision made."""
        self._state.decisions_made.append(decision)
        if len(self._state.decisions_made) > 20:
            self._state.decisions_made = self._state.decisions_made[-20:]

    def set_active_task(self, task: str):
        self._state.active_task = task

    def _get_providers_active(self) -> list[str]:
        try:
            from ..dna.dual_consciousness import _instance
            if hasattr(_instance, '_llm'):
                return _instance()._llm.provider_names
        except Exception:
            pass
        return []

    def _scan_open_context(self) -> list[str]:
        """Detect recently modified files in project."""
        files = []
        try:
            for p in sorted(Path(".").rglob("*.py"), key=os.path.getmtime, reverse=True)[:5]:
                if ".venv" not in str(p) and "__pycache__" not in str(p):
                    mtime = os.path.getmtime(p)
                    if time.time() - mtime < 3600:  # last hour
                        files.append(str(p))
        except Exception:
            pass
        return files

    async def _summarize_session(self, hub) -> str:
        llm = hub.world.consciousness._llm
        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    f"Summarize this coding session in ONE line (max 80 chars). "
                    f"What was the main task accomplished?\n"
                    f"Session: {self._state.session_duration_minutes:.0f}min\n"
                    f"Open files: {', '.join(self._state.open_files[:5])}\n"
                    f"Decisions: {', '.join(self._state.decisions_made[:5])}"
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.0, max_tokens=60, timeout=10,
            )
            return (result.text or "").strip()[:120] if result else ""
        except Exception:
            return ""

    async def _generate_hint(self, hub) -> str:
        llm = hub.world.consciousness._llm
        try:
            result = await llm.chat(
                messages=[{"role": "user", "content": (
                    "Write a 1-line suggestion for what to do next when the user returns. "
                    "Be specific and actionable.\n"
                    "Summary: " + self._state.last_conversation_summary
                )}],
                provider=getattr(llm, '_elected', ''),
                temperature=0.2, max_tokens=50, timeout=8,
            )
            return (result.text or "").strip()[:120] if result else ""
        except Exception:
            return ""


_sc: SessionContinuity | None = None


def get_session_continuity() -> SessionContinuity:
    global _sc
    if _sc is None:
        _sc = SessionContinuity()
    return _sc
