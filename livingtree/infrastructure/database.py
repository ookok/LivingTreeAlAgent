"""
LivingTree 数据库管理
=====================

统一的数据库抽象层，支持 SQLite / PostgreSQL。
"""

import os
import sqlite3
from typing import Optional, Dict, Any, List, Tuple
from threading import Lock
from datetime import datetime


class Database:
    def __init__(self, db_path: str = ""):
        if not db_path:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "livingtree.db"
            )
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = Lock()
        self._migrate()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _migrate(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                tokens INTEGER DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS execution_records (
                id TEXT PRIMARY KEY,
                trace_id TEXT,
                intent_type TEXT,
                complexity REAL,
                success INTEGER,
                duration_ms REAL,
                tokens_used INTEGER,
                errors TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT,
                memory_type TEXT,
                source TEXT,
                relevance REAL DEFAULT 0.0,
                created_at TEXT,
                metadata TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_execution_trace ON execution_records(trace_id);
        """)
        conn.commit()

    # ── 会话操作 ──

    def create_session(self, session_id: str) -> bool:
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)",
                (session_id, datetime.now().isoformat(), datetime.now().isoformat())
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def add_message(self, session_id: str, role: str, content: str,
                    tokens: int = 0):
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO messages (session_id, role, content, tokens, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, tokens, datetime.now().isoformat())
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), session_id)
        )
        conn.commit()

    def get_messages(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id = ? "
            "ORDER BY id ASC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── 执行记录 ──

    def record_execution(self, record_id: str, trace_id: str,
                         intent_type: str, complexity: float,
                         success: bool, duration_ms: float,
                         tokens_used: int, errors: str = ""):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO execution_records "
            "(id, trace_id, intent_type, complexity, success, "
            "duration_ms, tokens_used, errors, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (record_id, trace_id, intent_type, complexity,
             int(success), duration_ms, tokens_used, errors,
             datetime.now().isoformat())
        )
        conn.commit()

    def get_execution_stats(self, hours: int = 24) -> Dict[str, Any]:
        conn = self._get_conn()
        cutoff = (datetime.now() - datetime.timedelta(hours=hours)).isoformat()

        row = conn.execute(
            "SELECT COUNT(*) as total, AVG(CASE WHEN success THEN 1 ELSE 0 END) as success_rate, "
            "AVG(duration_ms) as avg_duration, SUM(tokens_used) as total_tokens "
            "FROM execution_records WHERE created_at >= ?",
            (cutoff,)
        ).fetchone()

        return {
            "total": row["total"] or 0,
            "success_rate": row["success_rate"] or 0.0,
            "avg_duration_ms": row["avg_duration"] or 0.0,
            "total_tokens": row["total_tokens"] or 0,
            "period_hours": hours,
        }

    # ── 记忆存储 ──

    def store_memory(self, memory_id: str, content: str,
                     memory_type: str = "mid_term",
                     source: str = "", metadata: str = ""):
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO memories "
            "(id, content, memory_type, source, created_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (memory_id, content, memory_type, source,
             datetime.now().isoformat(), metadata)
        )
        conn.commit()

    def search_memories(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM memories WHERE content LIKE ? "
            "ORDER BY created_at DESC LIMIT ?",
            (f"%{keyword}%", limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


__all__ = ["Database"]
