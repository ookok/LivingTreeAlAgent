"""LanceDB vector storage backend — persistent, embedded columnar vector DB.

Maps LanceDB tables into logical DisCoGC segments. LanceDB provides:
  - Native vector search (ANN + filtering) via Lance columnar format
  - Zero-config persistence (just a directory)
  - SQL-like filtering with vector search
  - In-process, no server needed

Each DisCoGC segment maps to a batch of rows identified by segment_id.
Stale vectors (TTL-expired) are tracked for discard via SQL DELETE.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import numpy as np
from loguru import logger

from ..gc_metrics import StorageStats
from ..storage_layer import StorageBackend, StorageSegment

_SEGMENT_ROWS = 1000
_TABLE_PREFIX = "lt_vec"


class LanceDBStorageBackend(StorageBackend):
    """DisCoGC-compatible LanceDB vector storage adapter.

    Each segment maps to a batch of rows (segment_id column).
    TTL-based staleness: rows with (now - created_at) >= ttl are stale.
    Discard: SQL DELETE WHERE segment_id = X AND is_stale = true.
    Compaction: re-insert live rows with new segment_id, delete old ones.

    Falls back to in-memory list when LanceDB is unavailable.
    """

    def __init__(
        self,
        db_path: str = ".livingtree/vectors",
        table_name: str = "default",
        name: str = "",
        dimension: int = 384,
        ttl_seconds: int = 86400 * 7,
        segment_rows: int = _SEGMENT_ROWS,
    ):
        super().__init__(name=name or f"lancedb:{table_name}")
        self.db_path = os.path.abspath(db_path)
        self.table_name = f"{_TABLE_PREFIX}_{table_name}"
        self.dimension = dimension
        self.ttl_seconds = ttl_seconds
        self.segment_rows = segment_rows

        self._lock = threading.Lock()
        self._db: Any = None
        self._table: Any = None
        self._use_lancedb = False
        self._vectors: list[np.ndarray] = []
        self._metadata: list[dict[str, Any]] = []
        self._access_counts: list[int] = []
        self._created_at: list[float] = []
        self._next_id: int = 0

            import lancedb
            import pyarrow as pa
            self._pyarrow = pa
            os.makedirs(self.db_path, exist_ok=True)
            self._db = lancedb.connect(self.db_path)
            self._use_lancedb = True
            self._ensure_table()
            logger.info(
                "LanceDBBackend[%s]: connected (dim=%d, path=%s)",
                self.name, dimension, self.db_path,
            )
            logger.info(
                "LanceDBBackend[%s]: lancedb/pyarrow not installed, using memory fallback",
                self.name,
            )

    def _ensure_table(self) -> None:
        try:
            self._table = self._db.open_table(self.table_name)
            count = self._table.count_rows()
            logger.info("LanceDBBackend[%s]: opened existing table (%d rows)", self.name, count)
        except Exception:
            schema = self._pyarrow.schema([
                self._pyarrow.field("id", self._pyarrow.int64()),
                self._pyarrow.field("vector", self._pyarrow.list_(
                    self._pyarrow.float32(), self.dimension
                )),
                self._pyarrow.field("segment_id", self._pyarrow.string()),
                self._pyarrow.field("metadata_json", self._pyarrow.string()),
                self._pyarrow.field("access_count", self._pyarrow.int32()),
                self._pyarrow.field("created_at", self._pyarrow.float64()),
            ])
            self._table = self._db.create_table(self.table_name, schema=schema)
            logger.info("LanceDBBackend[%s]: created new table", self.name)

    def get_stats(self) -> StorageStats:
        with self._lock:
            if self._use_lancedb:
                count = self._table.count_rows()
            else:
                count = len(self._metadata)
            now = time.time()
            if self._use_lancedb:
                stale_count = self._table.count_rows(
                    f"created_at < {now - self.ttl_seconds}"
                )
            else:
                stale_count = sum(
                    1 for t in self._created_at if (now - t) >= self.ttl_seconds
                )
            live_count = count - stale_count
            bytes_per = self.dimension * 4 + 256
            return StorageStats(
                backend_name=self.name,
                total_bytes=count * bytes_per,
                used_bytes=count * bytes_per,
                stale_bytes=stale_count * bytes_per,
                live_bytes=live_count * bytes_per,
                segment_count=(count + self.segment_rows - 1) // self.segment_rows,
                stale_segment_count=0,
                fragmentation_ratio=stale_count / max(count, 1),
            )

    def list_segments(self) -> list[StorageSegment]:
        with self._lock:
            if self._use_lancedb:
                count = self._table.count_rows()
            else:
                count = len(self._metadata)
            if count == 0:
                return []
            segments = []
            for start_idx in range(0, count, self.segment_rows):
                end_idx = min(start_idx + self.segment_rows, count)
                seg_id = f"lancedb:{self.table_name}:{start_idx}-{end_idx - 1}"
                segments.append(StorageSegment(
                    segment_id=seg_id,
                    total_bytes=self.dimension * 4 * (end_idx - start_idx),
                    live_bytes=self.dimension * 4 * (end_idx - start_idx),
                    stale_bytes=0,
                    created_at=time.time(),
                    read_count=0,
                    write_count=end_idx - start_idx,
                ))
            return segments

    def discard_segments(self, segment_ids: list[str]) -> int:
        total_freed = 0
        with self._lock:
            for seg_id in segment_ids:
                try:
                    seg = self._parse_segment(seg_id)
                    if seg is None:
                        continue
                    start_idx, end_idx = seg
                    count = end_idx - start_idx
                    if self._use_lancedb and count > 0:
                        self._table.delete(f"segment_id = '{seg_id}'")
                        self._table.optimize()
                    total_freed += count * self.dimension * 4
                except Exception as e:
                    logger.debug("LanceDBBackend discard: %s", e)
            return total_freed

    def compact_segments(self, segment_ids: list[str]) -> tuple[int, int]:
        total_freed = 0
        total_written = 0
        with self._lock:
            now = time.time()
            for seg_id in segment_ids:
                try:
                    seg = self._parse_segment(seg_id)
                    if seg is None:
                        continue
                    if not self._use_lancedb:
                        continue
                    stale_pred = f"created_at < {now - self.ttl_seconds}"
                    stale_rows = self._table.search().where(stale_pred).where(
                        f"segment_id = '{seg_id}'"
                    ).to_list()
                    if stale_rows:
                        self._table.delete(
                            f"segment_id = '{seg_id}' AND created_at < {now - self.ttl_seconds}"
                        )
                        self._table.optimize()
                        total_freed += len(stale_rows) * self.dimension * 4
                    total_written += 1
                except Exception as e:
                    logger.debug("LanceDBBackend compact: %s", e)
            return total_freed, total_written

    def add_vectors(
        self, vectors: list[list[float]], metadata_list: list[dict] | None = None
    ) -> int:
        with self._lock:
            if not vectors:
                if self._use_lancedb:
                    return self._table.count_rows()
                return len(self._metadata)
            now = time.time()
            start_id = self._next_id
            start_seg = (start_id // self.segment_rows) * self.segment_rows
            end_seg = start_seg + self.segment_rows - 1
            seg_id = f"lancedb:{self.table_name}:{start_seg}-{end_seg}"

            if self._use_lancedb:
                rows = []
                for i, vec in enumerate(vectors):
                    rows.append({
                        "id": start_id + i,
                        "vector": [float(v) for v in vec],
                        "segment_id": seg_id,
                        "metadata_json": self._serialize_meta(
                            metadata_list[i] if metadata_list else {}
                        ),
                        "access_count": 0,
                        "created_at": now,
                    })
                self._table.add(rows)
                self._next_id = start_id + len(vectors)
                return start_id
            else:
                for i, vec in enumerate(vectors):
                    self._vectors.append(np.array(vec, dtype=np.float32))
                    self._metadata.append(metadata_list[i] if metadata_list else {})
                    self._access_counts.append(0)
                    self._created_at.append(now)
                return start_id

    def search(
        self, query_vector: list[float], k: int = 10
    ) -> list[tuple[int, float, dict]]:
        with self._lock:
            if self._use_lancedb:
                try:
                    now = time.time()
                    results = (
                        self._table.search(query_vector)
                        .metric("l2")
                        .limit(k)
                        .to_list()
                    )
                    output = []
                    for r in results:
                        if (now - r.get("created_at", 0)) >= self.ttl_seconds:
                            continue
                        output.append((
                            int(r["id"]),
                            float(r.get("_distance", 0)),
                            self._deserialize_meta(r.get("metadata_json", "{}")),
                        ))
                    return output
                except Exception as e:
                    logger.warning("LanceDBBackend search failed: %s", e)
                    return self._brute_force_search(query_vector, k)
            else:
                return self._brute_force_search(query_vector, k)

    def _brute_force_search(
        self, query_vector: list[float], k: int
    ) -> list[tuple[int, float, dict]]:
        now = time.time()
        q = np.array(query_vector, dtype=np.float32)
        scores = []
        for i, vec in enumerate(self._vectors):
            d = float(np.linalg.norm(q - np.array(vec, dtype=np.float32)))
            if (now - self._created_at[i]) < self.ttl_seconds:
                scores.append((i, d))
        scores.sort(key=lambda x: x[1])
        return [(idx, dist, dict(self._metadata[idx])) for idx, dist in scores[:k]]

    def _parse_segment(self, seg_id: str) -> tuple[int, int] | None:
        try:
            parts = seg_id.split(":")
            range_part = parts[-1]
            start_str, end_str = range_part.split("-")
            return int(start_str), int(end_str) + 1
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _serialize_meta(meta: dict) -> str:
        import json
        return json.dumps(meta, ensure_ascii=False)

    @staticmethod
    def _deserialize_meta(raw: str) -> dict:
        import json
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def record_app_write(self, bytes_written: int) -> None:
        pass

    def close(self) -> None:
        if self._use_lancedb and self._table:
            self._table.optimize()
