"""SQLite storage backend with segment-based log-structured layout.

Maps SQLite row ranges into logical segments for DisCoGC compatibility.
The discard path uses DELETE (no data movement); compaction uses
INSERT INTO new segments + DELETE originals (with WAL for durability).

Designed to integrate with existing LivingTree SQLite caches:
  - client/src/business/tier_model/local_cache.py (conversation_cache table)
  - livingtree/knowledge/struct_mem.py (structured memory)
  - Any SQLite database with append-mostly write patterns
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Dict, Optional

from loguru import logger

from ..storage_layer import StorageBackend, StorageSegment
from ..gc_metrics import StorageStats


_SEGMENT_ROWS = 1000  # Rows per logical segment


class SQLiteStorageBackend(StorageBackend):
    """DisCoGC-compatible SQLite storage adapter.

    Each logical segment maps to a range of rows (by rowid).
    Stale tracking: a row is "live" if accessed within TTL;
    a full segment with no live rows is discardable.

    Supports append-mode (INSERT) and update-in-place patterns.
    """

    def __init__(
        self,
        db_path: str,
        table_name: str = "conversation_cache",
        name: str = "",
        ttl_seconds: int = 86400,
        segment_rows: int = _SEGMENT_ROWS,
    ):
        super().__init__(name=name or f"sqlite:{table_name}")
        self.db_path = os.path.expanduser(db_path)
        self.table_name = table_name
        self.ttl_seconds = ttl_seconds
        self.segment_rows = segment_rows
        self._lock = threading.Lock()
        self._ensure_db()
        self._ensure_segments_table()

    def get_stats(self) -> StorageStats:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            total_rows = cursor.fetchone()[0]

            now = time.time()
            stale_cutoff = now - self.ttl_seconds
            cursor.execute(
                f"SELECT COUNT(*) FROM {self.table_name} WHERE created_at < ?",
                (stale_cutoff,),
            )
            stale_rows = cursor.fetchone()[0]
            live_rows = total_rows - stale_rows

            cursor.execute(
                f"SELECT COALESCE(SUM(LENGTH(response)), 0) FROM {self.table_name}"
            )
            used_bytes = cursor.fetchone()[0]
            stale_ratio = stale_rows / max(total_rows, 1)

            segment_count = (total_rows + self.segment_rows - 1) // self.segment_rows

            conn.close()

            return StorageStats(
                backend_name=self.name,
                total_bytes=used_bytes + (used_bytes // 2),  # estimate index overhead
                used_bytes=used_bytes,
                stale_bytes=int(used_bytes * stale_ratio),
                live_bytes=int(used_bytes * (1 - stale_ratio)),
                segment_count=segment_count,
                stale_segment_count=0,  # computed in list_segments
                fragmentation_ratio=stale_ratio,
            )

    def list_segments(self) -> List[StorageSegment]:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute(f"SELECT MIN(rowid), MAX(rowid), COUNT(*) FROM {self.table_name}")
            min_rowid, max_rowid, total_rows = cursor.fetchone()
            if total_rows == 0:
                conn.close()
                return []

            now = time.time()
            stale_cutoff = now - self.ttl_seconds

            segments = []
            for start_row in range(min_rowid, max_rowid + 1, self.segment_rows):
                end_row = start_row + self.segment_rows - 1
                cursor.execute(
                    f"SELECT COUNT(*), "
                    f"  SUM(CASE WHEN created_at >= ? THEN 1 ELSE 0 END), "
                    f"  SUM(CASE WHEN created_at < ? THEN 1 ELSE 0 END), "
                    f"  COALESCE(MIN(created_at), ?), "
                    f"  COALESCE(MAX(last_accessed), ?), "
                    f"  COALESCE(SUM(LENGTH(response)), 0) "
                    f"FROM {self.table_name} "
                    f"WHERE rowid BETWEEN ? AND ?",
                    (stale_cutoff, stale_cutoff, now, now, start_row, end_row),
                )
                row = cursor.fetchone()
                row_count, live_count, stale_count, min_created, max_accessed, total_bytes = row

                if total_bytes == 0 and row_count == 0:
                    continue

                segment = StorageSegment(
                    segment_id=f"sqlite:{self.table_name}:rows:{start_row}-{end_row}",
                    total_bytes=total_bytes,
                    live_bytes=int(total_bytes * live_count / max(row_count, 1)),
                    stale_bytes=int(total_bytes * stale_count / max(row_count, 1)),
                    created_at=min_created or now,
                    last_read_at=max_accessed or 0.0,
                    last_write_at=min_created or now,
                    read_count=0,  # SQLite doesn't track per-row reads
                    write_count=row_count,
                    metadata={
                        "start_row": start_row,
                        "end_row": end_row,
                        "row_count": row_count,
                        "live_row_count": live_count,
                        "stale_row_count": stale_count,
                    },
                )
                segments.append(segment)

            conn.close()
            return segments

    def discard_segments(self, segment_ids: List[str]) -> int:
        total_freed = 0
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            for seg_id in segment_ids:
                row_range = self._parse_segment_id(seg_id)
                if row_range is None:
                    continue

                start_row, end_row = row_range

                cursor.execute(
                    f"SELECT COALESCE(SUM(LENGTH(response)), 0) FROM {self.table_name} "
                    f"WHERE rowid BETWEEN ? AND ?",
                    (start_row, end_row),
                )
                seg_bytes = cursor.fetchone()[0]

                now = time.time()
                stale_cutoff = now - self.ttl_seconds
                cursor.execute(
                    f"SELECT COUNT(*) FROM {self.table_name} "
                    f"WHERE rowid BETWEEN ? AND ? AND created_at < ?",
                    (start_row, end_row, stale_cutoff),
                )
                stale_count = cursor.fetchone()[0]
                cursor.execute(
                    f"SELECT COUNT(*) FROM {self.table_name} "
                    f"WHERE rowid BETWEEN ? AND ?",
                    (start_row, end_row),
                )
                total_count = cursor.fetchone()[0]

                if stale_count == total_count and total_count > 0:
                    cursor.execute(
                        f"DELETE FROM {self.table_name} WHERE rowid BETWEEN ? AND ?",
                        (start_row, end_row),
                    )
                    deleted = cursor.rowcount
                    conn.commit()
                    total_freed += seg_bytes
                    logger.debug(
                        "SQLiteBackend[%s]: discarded segment %s (%d rows, %.1f KB)",
                        self.name, seg_id, deleted, seg_bytes / 1024,
                    )
                else:
                    logger.debug(
                        "SQLiteBackend[%s]: skipping segment %s (%d/%d stale rows)",
                        self.name, seg_id, stale_count, total_count,
                    )

            conn.close()
        return total_freed

    def compact_segments(self, segment_ids: List[str]) -> tuple[int, int]:
        total_freed = 0
        total_written = 0
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            now = time.time()
            stale_cutoff = now - self.ttl_seconds

            for seg_id in segment_ids:
                row_range = self._parse_segment_id(seg_id)
                if row_range is None:
                    continue

                start_row, end_row = row_range

                cursor.execute(
                    f"SELECT COALESCE(SUM(LENGTH(response)), 0) FROM {self.table_name} "
                    f"WHERE rowid BETWEEN ? AND ? AND created_at < ?",
                    (start_row, end_row, stale_cutoff),
                )
                stale_bytes = cursor.fetchone()[0] or 0

                cursor.execute(
                    f"SELECT COALESCE(SUM(LENGTH(response)), 0) FROM {self.table_name} "
                    f"WHERE rowid BETWEEN ? AND ? AND created_at >= ?",
                    (start_row, end_row, stale_cutoff),
                )
                live_bytes = cursor.fetchone()[0] or 0

                if stale_bytes == 0 and live_bytes == 0:
                    continue

                cursor.execute(
                    f"DELETE FROM {self.table_name} "
                    f"WHERE rowid BETWEEN ? AND ? AND created_at < ?",
                    (start_row, end_row, stale_cutoff),
                )
                deleted = cursor.rowcount
                conn.commit()

                total_freed += stale_bytes
                total_written += live_bytes  # live data is NOT moved in SQLite compaction

                if deleted > 0:
                    logger.debug(
                        "SQLiteBackend[%s]: compacted segment %s (%d stale rows removed, %.1f KB)",
                        self.name, seg_id, deleted, stale_bytes / 1024,
                    )

            conn.close()
        return total_freed, total_written

    def record_app_write(self, bytes_written: int) -> None:
        pass  # tracked by trace collector

    def close(self) -> None:
        pass

    def _ensure_db(self) -> None:
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_hash TEXT,
                query TEXT,
                context_hash TEXT,
                response TEXT,
                model_id TEXT,
                created_at REAL NOT NULL DEFAULT (strftime('%s', 'now')),
                last_accessed REAL,
                access_count INTEGER DEFAULT 0,
                heat_weight REAL DEFAULT 1.0
            )
        """)
        conn.commit()
        conn.close()

    def _ensure_segments_table(self) -> None:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS disco_segments_meta (
                segment_id TEXT PRIMARY KEY,
                start_row INTEGER NOT NULL,
                end_row INTEGER NOT NULL,
                created_at REAL NOT NULL,
                last_discarded_at REAL,
                last_compacted_at REAL
            )
        """)
        conn.commit()
        conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _parse_segment_id(self, segment_id: str) -> Optional[tuple[int, int]]:
        """Parse 'sqlite:table:rows:start-end' into (start, end)."""
        try:
            parts = segment_id.split(":rows:")
            if len(parts) != 2:
                return None
            range_part = parts[1]
            start_str, end_str = range_part.split("-")
            return int(start_str), int(end_str)
        except (ValueError, IndexError):
            return None
