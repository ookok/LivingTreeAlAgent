"""SQLite WAL mode enabler — concurrent reads without blocking writes.

Call `enable_wal(connection)` on any sqlite3 connection to enable
Write-Ahead Logging. Idempotent — safe to call on already-WAL connections.
"""

from __future__ import annotations

import sqlite3
from loguru import logger


_WAL_ENABLED: set[int] = set()


def enable_wal(conn: sqlite3.Connection):
    """Enable WAL mode and set busy timeout for concurrent access."""
    conn_id = id(conn)
    if conn_id in _WAL_ENABLED:
        return
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        _WAL_ENABLED.add(conn_id)
    except Exception:
        pass  # in-memory or read-only — WAL not applicable


def open_db(path: str) -> sqlite3.Connection:
    """Open a SQLite database with WAL and row factory."""
    conn = sqlite3.connect(path, check_same_thread=False)
    enable_wal(conn)
    conn.row_factory = sqlite3.Row
    return conn
