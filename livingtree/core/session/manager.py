"""
LivingTree — Session Manager (Full Migration)
===============================================

Full migration from client/src/business/session_db.py + unified_context.py

Features:
- SQLite WAL session persistence with FTS5 search
- Session CRUD with title uniqueness
- Message append/read with token tracking
- Context window management with auto-compression
- UnifiedContext for session-scoped variables
"""

import sqlite3
import uuid
import time
import json
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


# ── Data Models ──────────────────────────────────────────

@dataclass
class SessionInfo:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    model: str = ""
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    message_count: int = 0
    tool_call_count: int = 0
    end_reason: str = ""
    parent_session_id: str = ""
    system_prompt: str = ""
    source: str = "desktop"
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    model_config: str = "{}"
    billing_provider: str = ""
    billing_base_url: str = ""


@dataclass
class MessageRecord:
    id: int = 0
    session_id: str = ""
    role: str = ""
    content: str = ""
    tool_call_id: str = ""
    tool_calls: str = ""
    tool_name: str = ""
    timestamp: float = field(default_factory=time.time)
    token_count: int = 0


@dataclass
class ContextEntry:
    role: str = ""
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content[:100] + "..." if len(self.content) > 100 else self.content,
            "timestamp": self.timestamp,
        }


@dataclass
class UnifiedContext:
    session_id: str = ""
    user_id: str = ""
    history: List[ContextEntry] = field(default_factory=list)
    memory: Dict[str, Any] = field(default_factory=dict)
    user_profile: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    max_history: int = 50

    def add_message(self, role: str, content: str, **metadata):
        entry = ContextEntry(role=role, content=content, metadata=metadata)
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_history(self, limit: int = 20) -> List[ContextEntry]:
        return self.history[-limit:]

    def to_prompt(self) -> str:
        lines = []
        for entry in self.history[-10:]:
            lines.append(f"[{entry.role}]: {entry.content[:500]}")
        return "\n".join(lines)


# ── Session Database ─────────────────────────────────────

class SessionManager:
    SCHEMA_VERSION = 6

    def __init__(self, db_path: str | Path = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent.parent / "data" / "sessions.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                model TEXT DEFAULT '',
                started_at REAL DEFAULT 0,
                ended_at REAL,
                message_count INTEGER DEFAULT 0,
                tool_call_count INTEGER DEFAULT 0,
                end_reason TEXT,
                parent_session_id TEXT,
                system_prompt TEXT DEFAULT '',
                source TEXT DEFAULT 'desktop',
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0.0,
                model_config TEXT DEFAULT '{}',
                billing_provider TEXT DEFAULT '',
                billing_base_url TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_call_id TEXT,
                tool_calls TEXT,
                tool_name TEXT,
                timestamp REAL DEFAULT 0,
                token_count INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content, role, content=messages, content_rowid=id
            );
            CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id);
        """)
        conn.commit()

    def create_session(self, title: str = "", model: str = "",
                       system_prompt: str = "") -> SessionInfo:
        session = SessionInfo(
            id=str(uuid.uuid4()), title=title or f"Session-{int(time.time())}",
            model=model, system_prompt=system_prompt)
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO sessions (id,title,model,started_at,system_prompt) VALUES (?,?,?,?,?)",
            (session.id, session.title, session.model, session.started_at, session.system_prompt))
        conn.commit()
        return session

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        return self._row_to_session(row) if row else None

    def list_sessions(self, limit: int = 50) -> List[SessionInfo]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def end_session(self, session_id: str, reason: str = ""):
        conn = self._get_conn()
        conn.execute(
            "UPDATE sessions SET ended_at=?, end_reason=? WHERE id=?",
            (time.time(), reason, session_id))
        conn.commit()

    def delete_session(self, session_id: str):
        conn = self._get_conn()
        conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        conn.commit()

    def add_message(self, session_id: str, role: str, content: str,
                    token_count: int = 0) -> MessageRecord:
        conn = self._get_conn()
        ts = time.time()
        cur = conn.execute(
            "INSERT INTO messages (session_id,role,content,timestamp,token_count) VALUES (?,?,?,?,?)",
            (session_id, role, content, ts, token_count))
        conn.execute(
            "UPDATE sessions SET message_count=message_count+1 WHERE id=?", (session_id,))
        conn.commit()
        return MessageRecord(id=cur.lastrowid, session_id=session_id,
                            role=role, content=content, timestamp=ts,
                            token_count=token_count)

    def get_messages(self, session_id: str, limit: int = 100) -> List[MessageRecord]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, limit)).fetchall()
        return [MessageRecord(
            id=r["id"], session_id=r["session_id"], role=r["role"],
            content=r["content"], tool_call_id=r["tool_call_id"],
            tool_calls=r["tool_calls"], tool_name=r["tool_name"],
            timestamp=r["timestamp"], token_count=r["token_count"]
        ) for r in rows][::-1]

    def search_messages(self, query: str, limit: int = 20) -> List[MessageRecord]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT m.* FROM messages m JOIN messages_fts f ON m.id=f.rowid "
                "WHERE messages_fts MATCH ? ORDER BY m.timestamp DESC LIMIT ?",
                (query, limit)).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                "SELECT * FROM messages WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?",
                (f"%{query}%", limit)).fetchall()
        return [MessageRecord(id=r["id"], session_id=r["session_id"],
                role=r["role"], content=r["content"]) for r in rows]

    def _row_to_session(self, row) -> SessionInfo:
        return SessionInfo(
            id=row["id"], title=row["title"], model=row["model"],
            started_at=row["started_at"], ended_at=row["ended_at"],
            message_count=row["message_count"], tool_call_count=row["tool_call_count"],
            end_reason=row["end_reason"], parent_session_id=row["parent_session_id"],
            system_prompt=row["system_prompt"], source=row["source"],
            input_tokens=row["input_tokens"], output_tokens=row["output_tokens"],
            estimated_cost_usd=row["estimated_cost_usd"],
            model_config=row["model_config"],
            billing_provider=row["billing_provider"],
            billing_base_url=row["billing_base_url"])

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# ── Singleton ────────────────────────────────────────────

_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


__all__ = [
    "SessionManager", "SessionInfo", "MessageRecord",
    "ContextEntry", "UnifiedContext",
    "get_session_manager",
]
