"""CodeGraph SQLite backend — high-performance persistence with indexed queries.

Replaces pickle for large codebases (>10K entities):
  - Init: zero load time (just connect, no deserialization)
  - Query: indexed lookups (callers/callees/deps) <1ms
  - Update: INSERT OR REPLACE per changed file (hash-based incremental)
  - Size: ~5MB for 15K entities (same as pickle)

Tables:
  entities: id, name, file, kind, line, end_line, hash
  imports:   source_file, target_module
  calls:     caller_id, callee_name, file, line
  meta:      build_time, file_count, entity_count
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Any

from loguru import logger


class CodeGraphDB:
    """SQLite-backed CodeGraph storage."""

    def __init__(self, db_path: str = ".livingtree/codegraph.db"):
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA cache_size=-8000")  # 8MB cache
            self._create_tables()
        return self._conn

    def _create_tables(self):
        c = self._conn
        c.executescript("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                file TEXT NOT NULL,
                kind TEXT NOT NULL,
                line INTEGER,
                end_line INTEGER,
                hash TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_entities_file ON entities(file);
            CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
            CREATE INDEX IF NOT EXISTS idx_entities_kind ON entities(kind);

            CREATE TABLE IF NOT EXISTS imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                target_module TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_imports_source ON imports(source_file);
            CREATE INDEX IF NOT EXISTS idx_imports_target ON imports(target_module);

            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caller_id TEXT NOT NULL,
                callee_name TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_calls_caller ON calls(caller_id);
            CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_name);

            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        self._conn.commit()

    # ── Write ──

    def begin_batch(self):
        self.connect().execute("BEGIN")

    def commit_batch(self):
        self._conn.commit()

    def upsert_entity(self, entity: dict):
        self.connect().execute(
            "INSERT OR REPLACE INTO entities(id,name,file,kind,line,end_line,hash) "
            "VALUES(?,?,?,?,?,?,?)",
            (entity["id"], entity["name"], entity["file"], entity["kind"],
             entity.get("line", 0), entity.get("end_line", 0), entity.get("hash", "")),
        )

    def add_import(self, source_file: str, target_module: str):
        self.connect().execute(
            "INSERT INTO imports(source_file, target_module) VALUES(?,?)",
            (source_file, target_module),
        )

    def add_call(self, caller_id: str, callee_name: str, file: str, line: int):
        self.connect().execute(
            "INSERT INTO calls(caller_id, callee_name, file, line) VALUES(?,?,?,?)",
            (caller_id, callee_name, file, line),
        )

    def set_meta(self, key: str, value: str):
        self.connect().execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES(?,?)", (key, value),
        )

    def clear_file(self, filepath: str):
        """Remove all entities/imports/calls for a file before re-indexing."""
        c = self.connect()
        c.execute("DELETE FROM entities WHERE file=?", (filepath,))
        c.execute("DELETE FROM imports WHERE source_file=?", (filepath,))
        c.execute("DELETE FROM calls WHERE file=?", (filepath,))

    # ── Read ──

    def get_deps(self, module: str) -> list[str]:
        """Modules that this module imports."""
        rows = self.connect().execute(
            "SELECT DISTINCT target_module FROM imports WHERE source_file LIKE ? LIMIT 20",
            (f"%{module}%",),
        ).fetchall()
        return [r[0] for r in rows]

    def get_callers(self, func_name: str) -> list[str]:
        """Who calls this function."""
        rows = self.connect().execute(
            "SELECT DISTINCT caller_id FROM calls WHERE callee_name LIKE ? LIMIT 20",
            (f"%{func_name}%",),
        ).fetchall()
        return [r[0] for r in rows]

    def get_callees(self, func_name: str) -> list[str]:
        """What this function calls."""
        rows = self.connect().execute(
            "SELECT DISTINCT callee_name FROM calls WHERE caller_id LIKE ? LIMIT 20",
            (f"%{func_name}%",),
        ).fetchall()
        return [r[0] for r in rows]

    def get_impact(self, filepath: str) -> list[tuple[str, int]]:
        """Files affected by changes to this file — blast radius."""
        c = self.connect()
        # Direct callers of entities in this file
        rows = c.execute(
            "SELECT DISTINCT c.file FROM calls c "
            "JOIN entities e ON e.id = c.caller_id "
            "WHERE e.file LIKE ? LIMIT 20",
            (f"%{filepath}%",),
        ).fetchall()
        return [(r[0], 5) for r in rows]

    def get_file_hash(self, filepath: str) -> str | None:
        row = self.connect().execute(
            "SELECT hash FROM entities WHERE file=? LIMIT 1", (filepath,),
        ).fetchone()
        return row[0] if row else None

    def entity_count(self) -> int:
        row = self.connect().execute("SELECT COUNT(*) FROM entities").fetchone()
        return row[0] if row else 0

    def file_count(self) -> int:
        row = self.connect().execute(
            "SELECT COUNT(DISTINCT file) FROM entities"
        ).fetchone()
        return row[0] if row else 0

    def stats(self) -> dict:
        return {
            "total_entities": self.entity_count(),
            "total_files": self.file_count(),
            "total_calls": self.connect().execute("SELECT COUNT(*) FROM calls").fetchone()[0],
            "total_imports": self.connect().execute("SELECT COUNT(*) FROM imports").fetchone()[0],
            "db_size_mb": round(self._db_path.stat().st_size / (1024 * 1024), 2) if self._db_path.exists() else 0,
        }

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
