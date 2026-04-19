"""
会话数据库
参考 hermes-agent 的 hermes_state.py 架构
SQLite + FTS5 全文搜索
"""

import sqlite3
import uuid
import time
import json
import random
import threading
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


# ── 数据模型 ────────────────────────────────────────────────────────

@dataclass
class SessionInfo:
    id: str
    title: str
    model: str
    started_at: float
    ended_at: float | None = None
    message_count: int = 0
    tool_call_count: int = 0
    end_reason: str | None = None
    parent_session_id: str | None = None
    system_prompt: str = ''
    source: str = 'desktop'
    # v5 迁移
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    # v6 迁移
    model_config: str = '{}'
    billing_provider: str = ''
    billing_base_url: str = ''


@dataclass
class MessageRecord:
    id: int
    session_id: str
    role: str
    content: str
    tool_call_id: str | None = None
    tool_calls: str | None = None
    tool_name: str | None = None
    timestamp: float = 0.0
    token_count: int = 0


# ── 数据库 ─────────────────────────────────────────────────────────

class SessionDB:
    """
    会话持久化数据库（SQLite WAL 模式）
    支持：
    - 会话创建/结束/删除
    - 消息追加/读取
    - FTS5 全文搜索
    - 标题唯一性处理
    """

    SCHEMA_VERSION = 6
    _WRITE_RETRIES = 15
    _RETRY_MIN = 0.020
    _RETRY_MAX = 0.150
    _CHECKPOINT_EVERY = 50

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            from core.config import get_config_dir
            db_path = get_config_dir() / "sessions.db"
        self.db_path = Path(db_path)
        self._write_count = 0
        self._local = threading.local()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        """线程本地连接"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                timeout=30,
                isolation_level=None,  # autocommit via IMMEDIATE
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _add_column_if_not_exists(self, conn: sqlite3.Connection, table: str, column: str, col_type: str):
        """安全地添加列（如果不存在）"""
        try:
            cursor = conn.execute(f"PRAGMA table_info({table})")
            existing_columns = [row[1] for row in cursor.fetchall()]
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except Exception:
            pass

    def _init_db(self):
        """初始化数据库"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._conn()

        # 检查 schema 版本
        try:
            ver = conn.execute("PRAGMA user_version").fetchone()[0]
        except Exception:
            ver = 0

        if ver < 1:
            self._migrate_v1(conn)
        if ver < 2:
            self._migrate_v2(conn)
        if ver < 3:
            self._migrate_v3(conn)
        if ver < 4:
            self._migrate_v4(conn)
        if ver < 5:
            self._migrate_v5(conn)
        if ver < 6:
            self._migrate_v6(conn)

        conn.execute(f"PRAGMA user_version={self.SCHEMA_VERSION}")

    # ── 迁移脚本 ────────────────────────────────────────────────

    def _migrate_v1(self, conn: sqlite3.Connection):
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                model TEXT DEFAULT '',
                started_at REAL NOT NULL,
                ended_at REAL,
                end_reason TEXT,
                message_count INTEGER DEFAULT 0,
                tool_call_count INTEGER DEFAULT 0,
                parent_session_id TEXT,
                system_prompt TEXT DEFAULT '',
                source TEXT DEFAULT 'desktop'
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_call_id TEXT,
                tool_calls TEXT,
                tool_name TEXT,
                timestamp REAL NOT NULL,
                token_count INTEGER DEFAULT 0,
                finish_reason TEXT,
                reasoning TEXT DEFAULT '',
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
        """)

    def _migrate_v2(self, conn: sqlite3.Connection):
        self._add_column_if_not_exists(conn, "messages", "finish_reason", "TEXT")

    def _migrate_v3(self, conn: sqlite3.Connection):
        self._add_column_if_not_exists(conn, "sessions", "title", "TEXT")

    def _migrate_v4(self, conn: sqlite3.Connection):
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_title ON sessions(title)")

    def _migrate_v5(self, conn: sqlite3.Connection):
        self._add_column_if_not_exists(conn, "sessions", "input_tokens", "INTEGER DEFAULT 0")
        self._add_column_if_not_exists(conn, "sessions", "output_tokens", "INTEGER DEFAULT 0")
        self._add_column_if_not_exists(conn, "sessions", "estimated_cost_usd", "REAL DEFAULT 0")

    def _migrate_v6(self, conn: sqlite3.Connection):
        self._add_column_if_not_exists(conn, "messages", "reasoning", "TEXT DEFAULT ''")
        self._add_column_if_not_exists(conn, "messages", "reasoning_details", "TEXT DEFAULT ''")
        self._add_column_if_not_exists(conn, "sessions", "model_config", "TEXT DEFAULT '{}'")
        self._add_column_if_not_exists(conn, "sessions", "billing_provider", "TEXT DEFAULT ''")
        self._add_column_if_not_exists(conn, "sessions", "billing_base_url", "TEXT DEFAULT ''")
        # FTS5 虚拟表
        conn.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                content=messages,
                content_rowid=id,
                tokenize='porter unicode61'
            );

            CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
            END;

            CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
            END;

            CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
                INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
            END;
        """)

    # ── 会话管理 ────────────────────────────────────────────────

    def _retry_write(self, fn, *args, **kwargs):
        """带随机抖动的写锁重试"""
        for i in range(self._WRITE_RETRIES):
            try:
                return fn(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and i < self._WRITE_RETRIES - 1:
                    time.sleep(random.uniform(self._RETRY_MIN, self._RETRY_MAX))
                else:
                    raise

    def create_session(self, title: str = "", model: str = "") -> str:
        sid = str(uuid.uuid4())
        now = time.time()
        if not title:
            title = f"新会话 {time.strftime('%H:%M')}"

        def _do():
            conn = self._conn()
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO sessions(id,title,model,started_at) VALUES(?,?,?,?)",
                (sid, title, model, now),
            )
            conn.execute("COMMIT")
            self._checkpoint()
            return sid

        return self._retry_write(_do)

    def end_session(self, session_id: str, reason: str = "stop"):
        def _do():
            self._conn().execute(
                "UPDATE sessions SET ended_at=?,end_reason=? WHERE id=?",
                (time.time(), reason, session_id),
            )
        self._retry_write(_do)

    def get_session(self, session_id: str) -> SessionInfo | None:
        row = self._conn().execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not row:
            return None
        return SessionInfo(**dict(row))

    def list_sessions(self, limit: int = 50) -> list[SessionInfo]:
        rows = self._conn().execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [SessionInfo(**dict(r)) for r in rows]

    def delete_session(self, session_id: str):
        def _do():
            self._conn().execute("BEGIN IMMEDIATE")
            self._conn().execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            self._conn().execute("DELETE FROM sessions WHERE id=?", (session_id,))
            self._conn().execute("COMMIT")
        self._retry_write(_do)

    def set_session_title(self, session_id: str, title: str):
        title = self._sanitize_title(title)
        def _do():
            conn = self._conn()
            conn.execute("BEGIN IMMEDIATE")
            # 处理标题唯一性
            existing = conn.execute(
                "SELECT id FROM sessions WHERE title=? AND id!=?",
                (title, session_id)
            ).fetchone()
            if existing:
                base = title
                idx = 2
                while True:
                    alt = f"{base} #{idx}"
                    if not conn.execute("SELECT 1 FROM sessions WHERE title=?", (alt,)).fetchone():
                        title = alt
                        break
                    idx += 1
            conn.execute("UPDATE sessions SET title=? WHERE id=?", (title, session_id))
            conn.execute("COMMIT")
        self._retry_write(_do)

    def _sanitize_title(self, title: str) -> str:
        """清理标题中的非法字符"""
        import re
        title = re.sub(r'[\x00-\x1f\x7f]', '', title)
        title = re.sub(r'[\u200b-\u200f\u2028-\u202f]', '', title)
        title = re.sub(r'\s+', ' ', title).strip()
        return title[:100]

    # ── 消息管理 ────────────────────────────────────────────────

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_call_id: str | None = None,
        tool_calls: list[dict] | None = None,
        tool_name: str | None = None,
        token_count: int = 0,
        reasoning: str = "",
    ) -> int:
        now = time.time()
        tc_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None

        def _do():
            conn = self._conn()
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """INSERT INTO messages
                   (session_id,role,content,tool_call_id,tool_calls,tool_name,timestamp,token_count,reasoning)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (session_id, role, content, tool_call_id, tc_json, tool_name,
                 now, token_count, reasoning)
            )
            msg_id = cur.lastrowid
            # 更新会话统计
            conn.execute(
                "UPDATE sessions SET message_count=message_count+1,"
                "tool_call_count=tool_call_count+? WHERE id=?",
                (1 if tool_name else 0, session_id)
            )
            conn.execute("COMMIT")
            self._checkpoint()
            return msg_id

        return self._retry_write(_do)

    def get_messages(self, session_id: str) -> list[MessageRecord]:
        rows = self._conn().execute(
            "SELECT * FROM messages WHERE session_id=? ORDER BY id",
            (session_id,)
        ).fetchall()
        return [MessageRecord(**dict(r)) for r in rows]

    def get_messages_for_llm(self, session_id: str) -> list[dict]:
        """获取适合 LLM API 的消息格式"""
        rows = self._conn().execute(
            "SELECT role,content,tool_call_id,tool_calls,tool_name "
            "FROM messages WHERE session_id=? ORDER BY id",
            (session_id,)
        ).fetchall()
        result = []
        for r in rows:
            msg = {"role": r["role"], "content": r["content"]}
            if r["tool_call_id"]:
                msg["tool_call_id"] = r["tool_call_id"]
            if r["tool_calls"]:
                try:
                    msg["tool_calls"] = json.loads(r["tool_calls"])
                except Exception:
                    pass
            if r["tool_name"]:
                msg["tool_name"] = r["tool_name"]
            result.append(msg)
        return result

    # ── 搜索 ────────────────────────────────────────────────────

    def search_messages(self, query: str, limit: int = 20) -> list[dict]:
        """FTS5 全文搜索"""
        safe = self._sanitize_fts5(query)
        rows = self._conn().execute(
            f"""SELECT m.*, sessions.title as session_title
                FROM messages_fts f
                JOIN messages m ON m.id = f.rowid
                JOIN sessions ON sessions.id = m.session_id
                WHERE messages_fts MATCH ?
                ORDER BY rank
                LIMIT ?""",
            (safe, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _sanitize_fts5(query: str) -> str:
        """安全处理 FTS5 查询"""
        import re
        # 移除 FTS5 特殊字符
        safe = re.sub(r'["()*^\[\]"]', ' ', query)
        # 包裹含空格的词为引号
        safe = re.sub(r'(\S+:\S+)', r'"\1"', safe)
        return safe.strip()

    # ── 内部 ────────────────────────────────────────────────────

    def _checkpoint(self):
        self._write_count += 1
        if self._write_count % self._CHECKPOINT_EVERY == 0:
            try:
                self._conn().execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                pass
