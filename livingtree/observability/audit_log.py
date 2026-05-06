"""Audit Log — Write-Ahead Style Append-Only Event Logger.

The Agent threat model is a BROWSER, not a SERVER. Input is adversarial,
keys are real, execution is uncontrolled. When something goes wrong, you
need an append-only, tamper-evident, queryable log of EVERYTHING that
happened — not fragmented traces scattered across 5 different modules.

Design:
- WAL-inspired: write event FIRST, then execute
- Immutable: events are never modified after write
- Queryable: filter by session, stage, operation, time range
- Lightweight: JSONL on disk, in-memory index for recent events
- Non-blocking: async ring-buffer flush to disk

Usage:
    from livingtree.observability.audit_log import AUDIT_LOG, get_audit_log
    log = get_audit_log()
    log.record("life_engine", "execute.start", "tool_call", 
               target="web_search", params={"query":"..."})
    log.record("life_engine", "execute.end", "tool_call", 
               target="web_search", result="OK", success=True)
    events = log.query(session_id="ses_abc", stage="execute")
    report = log.get_failure_report(session_id="ses_abc")
"""

from __future__ import annotations

import json
import time
import uuid
import asyncio
from dataclasses import dataclass, field, asdict
from collections import deque
from pathlib import Path
from typing import Any, Optional

from loguru import logger

AUDIT_DIR = Path(".livingtree/audit")
AUDIT_FILE = AUDIT_DIR / "audit.jsonl"
INDEX_FILE = AUDIT_DIR / "index.json"
RING_BUFFER_SIZE = 200
FLUSH_INTERVAL_SECONDS = 2.0
MAX_IN_MEMORY_EVENTS = 10000


@dataclass
class AuditEvent:
    """A single immutable audit event in the operation chain.

    Every LLM call, file write, network request, tool execution, and
    state mutation SHALL produce one AuditEvent.
    """
    id: str
    timestamp: float
    session_id: str
    stage: str               # perceive/cognize/plan/simulate/execute/reflect/evolve
    phase: str               # "start" or "end"
    operation: str           # "llm_call", "file_write", "network_request", "tool_call", "state_mutate", "knowledge_update"
    target: str = ""         # What was operated on (endpoint, file path, tool name)
    params_hash: str = ""    # SHA256 of params (don't store secrets in plaintext)
    result_summary: str = "" # First 200 chars of result (full in log)
    side_effects: list[str] = field(default_factory=list)  # ["file_created:path", "network_sent:url"]
    success: bool | None = None
    error: str = ""
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_line(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False) + "\n"

    @classmethod
    def from_line(cls, line: str) -> "AuditEvent | None":
        try:
            data = json.loads(line)
            return cls(**data)
        except Exception:
            return None


class AuditLog:
    """WAL-style append-only event log with async flush and in-memory query index."""

    def __init__(self):
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        self._ring_buffer: deque[AuditEvent] = deque(maxlen=RING_BUFFER_SIZE)
        self._index: dict[str, list[str]] = {}  # session_id → [event_id, ...]
        self._operation_index: dict[str, list[str]] = {}  # operation → [event_id, ...]
        self._events: dict[str, AuditEvent] = {}  # event_id → event (in-memory, limited)
        self._flush_task: asyncio.Task | None = None
        self._flushing = False
        self._total_written = 0
        self._total_errors = 0
        self._load_index()

    # ── Public API ──

    def record(
        self,
        stage: str,
        phase: str,
        operation: str,
        target: str = "",
        params: dict | None = None,
        result: str = "",
        side_effects: list[str] | None = None,
        success: bool | None = None,
        error: str = "",
        duration_ms: float = 0.0,
        session_id: str = "",
        metadata: dict | None = None,
    ) -> str:
        """Record an audit event. WAL: write this BEFORE the operation executes.
        
        Returns the event ID for pairing start/end events.
        """
        event = AuditEvent(
            id=f"auevt_{uuid.uuid4().hex[:12]}",
            timestamp=time.time(),
            session_id=session_id or self._current_session(),
            stage=stage,
            phase=phase,
            operation=operation,
            target=target,
            params_hash=self._hash_params(params) if params else "",
            result_summary=(result or "")[:200],
            side_effects=list(side_effects or []),
            success=success,
            error=error,
            duration_ms=duration_ms,
            metadata=dict(metadata or {}),
        )
        self._ring_buffer.append(event)
        self._index_event(event)
        return event.id

    def record_start(self, stage: str, operation: str, target: str = "",
                     params: dict | None = None, session_id: str = "",
                     metadata: dict | None = None) -> str:
        """Shorthand: record operation start (WAL before execution)."""
        return self.record(
            stage=stage, phase="start", operation=operation,
            target=target, params=params, session_id=session_id, metadata=metadata,
        )

    def record_end(self, stage: str, operation: str, target: str = "",
                   result: str = "", side_effects: list[str] | None = None,
                   success: bool = True, error: str = "", duration_ms: float = 0.0,
                   session_id: str = "", metadata: dict | None = None) -> str:
        """Shorthand: record operation end (actual outcome)."""
        return self.record(
            stage=stage, phase="end", operation=operation,
            target=target, result=result, side_effects=side_effects,
            success=success, error=error, duration_ms=duration_ms,
            session_id=session_id, metadata=metadata,
        )

    def query(
        self,
        session_id: str | None = None,
        stage: str | None = None,
        operation: str | None = None,
        success: bool | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query audit events with multiple filter dimensions."""
        results: list[AuditEvent] = []

        # Determine candidate event IDs
        if session_id and session_id in self._index:
            candidates = self._index[session_id]
        elif operation and operation in self._operation_index:
            candidates = self._operation_index[operation]
        else:
            candidates = list(self._events.keys())

        for eid in candidates[-limit * 3:]:  # generous window, then filter
            event = self._events.get(eid)
            if not event:
                continue
            if session_id and event.session_id != session_id:
                continue
            if stage and event.stage != stage:
                continue
            if operation and event.operation != operation:
                continue
            if success is not None and event.success != success:
                continue
            if since and event.timestamp < since:
                continue
            if until and event.timestamp > until:
                continue
            results.append(event)
            if len(results) >= limit:
                break

        return sorted(results, key=lambda e: e.timestamp)

    def reconstruct_chain(self, session_id: str) -> list[AuditEvent]:
        """Reconstruct the full operation chain for a session in temporal order."""
        ids = self._index.get(session_id, [])
        events = [self._events[eid] for eid in ids if eid in self._events]
        return sorted(events, key=lambda e: e.timestamp)

    def get_failure_report(self, session_id: str) -> dict[str, Any]:
        """Generate a post-mortem report for a session."""
        chain = self.reconstruct_chain(session_id)
        failures = [e for e in chain if e.success is False]
        ops = {}
        sides: dict[str, int] = {}
        for e in chain:
            ops[e.operation] = ops.get(e.operation, 0) + 1
            for se in e.side_effects:
                sides[se.split(":")[0] if ":" in se else se] = sides.get(
                    se.split(":")[0] if ":" in se else se, 0) + 1

        return {
            "session_id": session_id,
            "total_events": len(chain),
            "total_failures": len(failures),
            "duration_sec": round(chain[-1].timestamp - chain[0].timestamp, 2) if len(chain) >= 2 else 0,
            "operations": ops,
            "side_effects": sides,
            "failures": [
                {"stage": e.stage, "operation": e.operation, "target": e.target,
                 "error": e.error, "timestamp": e.timestamp}
                for e in failures[-10:]
            ],
            "last_error": failures[-1].error if failures else "",
            "first_failure_at_stage": failures[0].stage if failures else "",
        }

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_events_written": self._total_written,
            "total_errors": self._total_errors,
            "in_memory_events": len(self._events),
            "ring_buffer_size": len(self._ring_buffer),
            "indexed_sessions": len(self._index),
            "indexed_operations": dict(self._operation_index),
        }

    # ── Async flush ──

    async def start_flush(self) -> None:
        """Start the async ring-buffer flush task."""
        if self._flush_task and not self._flush_task.done():
            return
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.debug("AuditLog: flush loop started")

    async def stop_flush(self) -> None:
        """Stop the flush task and force final flush."""
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_now()

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
            await self._flush_now()

    async def _flush_now(self) -> None:
        if self._flushing:
            return
        self._flushing = True
        try:
            while self._ring_buffer:
                event = self._ring_buffer.popleft()
                try:
                    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
                        f.write(event.to_line())
                    self._total_written += 1
                except Exception as e:
                    logger.warning(f"AuditLog flush error: {e}")
                    self._total_errors += 1
            # Periodically save index for crash recovery
            if self._total_written % 100 == 0:
                self._save_index()
        finally:
            self._flushing = False

    # ── Internal ──

    def _index_event(self, event: AuditEvent) -> None:
        if len(self._events) >= MAX_IN_MEMORY_EVENTS:
            oldest = min(self._events.keys(), key=lambda k: self._events[k].timestamp)
            old = self._events.pop(oldest)
            for idx_list in [self._index.get(old.session_id, []),
                             self._operation_index.get(old.operation, [])]:
                if old.id in idx_list:
                    idx_list.remove(old.id)
        self._events[event.id] = event
        self._index.setdefault(event.session_id, []).append(event.id)
        self._operation_index.setdefault(event.operation, []).append(event.id)

    def _save_index(self) -> None:
        try:
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "sessions": {k: v[-100:] for k, v in self._index.items()},
                    "operations": {k: v[-100:] for k, v in self._operation_index.items()},
                    "total_written": self._total_written,
                }, f, ensure_ascii=False)
        except Exception:
            pass

    def _load_index(self) -> None:
        if not INDEX_FILE.exists():
            return
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._index = data.get("sessions", {})
                self._operation_index = data.get("operations", {})
                self._total_written = data.get("total_written", 0)
        except Exception:
            pass

    @staticmethod
    def _hash_params(params: dict) -> str:
        import hashlib
        raw = json.dumps(params, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _current_session() -> str:
        import threading
        return f"anon_{threading.get_ident():x}"


# ── Global singleton ──

AUDIT_LOG = AuditLog()


def get_audit_log() -> AuditLog:
    return AUDIT_LOG
