"""SessionSearch — FTS5 full-text search across conversation history.

Inspired by Hermes Agent FTS5 + LLM summarization for cross-session recall.
Stores conversation turns in SQLite FTS5 table for sub-millisecond search.

Commands: /recall <query>
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

DB_FILE = Path(".livingtree/session_search.db")


@dataclass
class SearchHit:
    session_id: str
    turn_id: int
    role: str  # "user" or "assistant"
    content: str
    snippet: str = ""
    timestamp: float = 0.0
    score: float = 0.0


class SessionSearch:
    """FTS5 full-text conversation search."""

    def __init__(self):
        self._db = sqlite3.connect(str(DB_FILE))
        self._db.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self._db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
                session_id, turn_id, role, content,
                timestamp,
                tokenize='unicode61'
            )
        """)
        self._db.commit()

    def index_turn(self, session_id: str, turn_id: int, role: str, content: str):
        """Index a conversation turn."""
        try:
            self._db.execute(
                "INSERT INTO turns_fts(session_id, turn_id, role, content, timestamp) VALUES (?,?,?,?,?)",
                (session_id, turn_id, role, content[:8000], time.time())
            )
            self._db.commit()
        except Exception as e:
            logger.debug(f"FTS index: {e}")

    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        """Full-text search across all indexed conversations."""
        try:
            # Escape FTS5 special chars
            safe_query = query.replace('"', '""')
            rows = self._db.execute(
                """SELECT session_id, turn_id, role, content, timestamp,
                   snippet(turns_fts, 0, '<mark>', '</mark>', '...', 40) as snippet,
                   rank
                   FROM turns_fts
                   WHERE turns_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (f'"{safe_query}"', limit)
            ).fetchall()

            hits = []
            for row in rows:
                content = row["content"] or ""
                # Generate context snippet
                snippet = row["snippet"] or content[:200]
                hits.append(SearchHit(
                    session_id=row["session_id"],
                    turn_id=row["turn_id"],
                    role=row["role"],
                    content=content[:500],
                    snippet=snippet,
                    timestamp=row["timestamp"],
                    score=row["rank"],
                ))
            return hits
        except sqlite3.OperationalError as e:
            # FTS5 may complain about malformed queries — try simple LIKE fallback
            logger.debug(f"FTS search fallback: {e}")
            return self._like_search(query, limit)
        except Exception as e:
            logger.debug(f"FTS search: {e}")
            return []

    def _like_search(self, query: str, limit: int) -> list[SearchHit]:
        """Simple LIKE fallback when FTS5 query fails."""
        like_q = f"%{query}%"
        rows = self._db.execute(
            "SELECT session_id, turn_id, role, content, timestamp FROM turns_fts WHERE content LIKE ? LIMIT ?",
            (like_q, limit)
        ).fetchall()
        hits = []
        for row in rows:
            content = row["content"] or ""
            hits.append(SearchHit(
                session_id=row["session_id"], turn_id=row["turn_id"],
                role=row["role"], content=content[:500],
                snippet=content[:200], timestamp=row["timestamp"],
            ))
        return hits

    def get_stats(self) -> dict:
        try:
            count = self._db.execute("SELECT COUNT(*) FROM turns_fts").fetchone()[0]
            latest = self._db.execute("SELECT MAX(timestamp) FROM turns_fts").fetchone()[0]
            return {"indexed_turns": count, "latest": latest or 0}
        except Exception:
            return {"indexed_turns": 0, "latest": 0}

    def close(self):
        self._db.close()


# ═══ Global ═══

_search: SessionSearch | None = None


def get_search() -> SessionSearch:
    global _search
    if _search is None:
        _search = SessionSearch()
    return _search
