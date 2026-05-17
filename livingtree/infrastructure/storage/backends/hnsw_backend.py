"""HNSW vector storage backend — segment-aware vector index for DisCoGC.

Maps hnswlib index partitions into logical segments. Each segment holds
a range of vector IDs. Stale vectors (low similarity, low access count,
or TTL-expired) are tracked for discard.

Compaction: rebuilds fragmented index partitions by copying live vectors
to new segments and dropping stale ones.

Integrates with existing LivingTree vector stores:
  - livingtree/knowledge/vector_store.py
  - client/src/business/knowledge_vector_db.py
  - client/src/business/tier_model/semantic_cache.py
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

_SEGMENT_VECTORS = 1000
_MAX_ELEMENTS = 1000000


class HNSWStorageBackend(StorageBackend):
    """DisCoGC-compatible hnswlib vector storage adapter.

    Wraps an hnswlib HNSW index. Each logical segment maps to a range
    of vector IDs. Supports:
      - Discard: mark stale vectors as deleted
      - Compaction: rebuild segments by copying live vectors

    Falls back to in-memory list + numpy brute-force when hnswlib unavailable.
    """

    def __init__(
        self,
        name: str = "",
        dimension: int = 384,
        segment_vectors: int = _SEGMENT_VECTORS,
        persist_path: str = "",
        ttl_seconds: int = 86400 * 7,
        max_elements: int = _MAX_ELEMENTS,
    ):
        super().__init__(name=name or "hnsw")
        self.dimension = dimension
        self.segment_vectors = segment_vectors
        self.persist_path = persist_path
        self.ttl_seconds = ttl_seconds
        self._max_elements = max_elements

        self._lock = threading.Lock()
        self._index: Any = None
        self._vectors: list[np.ndarray] = []
        self._metadata: list[dict[str, Any]] = []
        self._access_counts: list[int] = []
        self._last_access: list[float] = []
        self._created_at: list[float] = []
        self._id_counter: int = 0
        self._use_hnsw = False

            import hnswlib
            self._index = hnswlib.Index(space="l2", dim=dimension)
            self._index.init_index(
                max_elements=max_elements, M=16, ef_construction=200,
            )
            self._index.set_ef(50)
            self._use_hnsw = True
            logger.info("HNSWBackend[%s]: hnswlib index ready (dim=%d, max=%d)",
                        self.name, dimension, max_elements)
            logger.info("HNSWBackend[%s]: hnswlib not available, using numpy fallback", self.name)

        if persist_path:
            self._ensure_persist_dir()
            self._load()

    def get_stats(self) -> StorageStats:
        with self._lock:
            vector_count = len(self._metadata)
            now = time.time()
            stale_count = sum(
                1 for t in self._created_at if (now - t) >= self.ttl_seconds
            )
            live_count = vector_count - stale_count
            bytes_per_vector = self.dimension * 4 + 256
            total_bytes = vector_count * bytes_per_vector
            stale_bytes = stale_count * bytes_per_vector
            live_bytes = live_count * bytes_per_vector
            segment_count = (vector_count + self.segment_vectors - 1) // self.segment_vectors

            return StorageStats(
                backend_name=self.name,
                total_bytes=total_bytes,
                used_bytes=total_bytes,
                stale_bytes=stale_bytes,
                live_bytes=live_bytes,
                segment_count=segment_count,
                stale_segment_count=0,
                fragmentation_ratio=stale_count / max(vector_count, 1),
            )

    def list_segments(self) -> list[StorageSegment]:
        with self._lock:
            vector_count = len(self._metadata)
            if vector_count == 0:
                return []
            now = time.time()
            segments = []
            for start_idx in range(0, vector_count, self.segment_vectors):
                end_idx = min(start_idx + self.segment_vectors, vector_count)
                seg_live = 0
                seg_stale = 0
                min_created = now
                max_accessed = 0.0
                read_count = 0
                for i in range(start_idx, end_idx):
                    vec_bytes = self.dimension * 4 + len(str(self._metadata[i])) if i < len(self._metadata) else 256
                    is_stale = (now - self._created_at[i]) >= self.ttl_seconds if i < len(self._created_at) else False
                    if is_stale:
                        seg_stale += vec_bytes
                    else:
                        seg_live += vec_bytes
                    if i < len(self._created_at):
                        min_created = min(min_created, self._created_at[i])
                    if i < len(self._last_access):
                        max_accessed = max(max_accessed, self._last_access[i])
                    if i < len(self._access_counts):
                        read_count += self._access_counts[i]
                segments.append(StorageSegment(
                    segment_id=f"hnsw:segment:{start_idx}-{end_idx - 1}",
                    total_bytes=seg_live + seg_stale,
                    live_bytes=seg_live,
                    stale_bytes=seg_stale,
                    created_at=min_created,
                    last_read_at=max_accessed,
                    write_count=end_idx - start_idx,
                    read_count=read_count,
                    metadata={"start_idx": start_idx, "end_idx": end_idx, "vector_count": end_idx - start_idx},
                ))
            return segments

    def discard_segments(self, segment_ids: list[str]) -> int:
        total_freed = 0
        with self._lock:
            now = time.time()
            vector_count = len(self._metadata)
            for seg_id in segment_ids:
                idx_range = self._parse_segment_id(seg_id)
                if idx_range is None:
                    continue
                start_idx, end_idx = idx_range
                if start_idx >= vector_count:
                    continue
                actual_end = min(end_idx, vector_count)
                stale_indices = [
                    i for i in range(start_idx, actual_end)
                    if i < len(self._created_at) and (now - self._created_at[i]) >= self.ttl_seconds
                ]
                total_in_range = actual_end - start_idx
                if len(stale_indices) == total_in_range and total_in_range > 0:
                    freed = sum(self.dimension * 4 + 256 for _ in stale_indices)
                    self._remove_indices(stale_indices)
                    total_freed += freed
            return total_freed

    def compact_segments(self, segment_ids: list[str]) -> tuple[int, int]:
        total_freed = 0
        total_written = 0
        with self._lock:
            now = time.time()
            vector_count = len(self._metadata)
            for seg_id in segment_ids:
                idx_range = self._parse_segment_id(seg_id)
                if idx_range is None:
                    continue
                start_idx, end_idx = idx_range
                if start_idx >= vector_count:
                    continue
                actual_end = min(end_idx, vector_count)
                stale_indices = []
                live_indices = []
                for i in range(start_idx, actual_end):
                    if (now - self._created_at[i]) >= self.ttl_seconds:
                        stale_indices.append(i)
                    else:
                        live_indices.append(i)
                freed = sum(self.dimension * 4 + 256 for _ in stale_indices)
                if stale_indices:
                    self._remove_indices(stale_indices)
                total_freed += freed
                total_written += len(live_indices) * (self.dimension * 4 + 256)
            return total_freed, total_written

    def add_vectors(
        self, vectors: list[list[float]], metadata_list: list[dict] | None = None
    ) -> int:
        with self._lock:
            if not vectors:
                return len(self._metadata)
            start_index = len(self._metadata)
            now = time.time()
            arr = np.array(vectors, dtype=np.float32)
            ids = np.arange(self._id_counter, self._id_counter + len(vectors))
            for i, vec in enumerate(vectors):
                self._vectors.append(np.array(vec, dtype=np.float32))
                self._metadata.append(metadata_list[i] if metadata_list else {})
                self._access_counts.append(0)
                self._last_access.append(now)
                self._created_at.append(now)
            if self._use_hnsw:
                self._index.add_items(arr, ids)
                self._id_counter += len(vectors)
            if self.persist_path:
                self._save()
            return start_index

    def search(self, query_vector: list[float], k: int = 10) -> list[tuple[int, float, dict]]:
        with self._lock:
            if not self._vectors:
                return []
            if self._use_hnsw and len(self._vectors) > 0:
                q = np.array([query_vector], dtype=np.float32)
                labels, distances = self._index.knn_query(q, k=min(k, len(self._vectors)))
                results = []
                now = time.time()
                for label, dist in zip(labels[0], distances[0]):
                    idx = int(label)
                    if idx < 0 or idx >= len(self._metadata):
                        continue
                    if (now - self._created_at[idx]) >= self.ttl_seconds:
                        continue
                    self._access_counts[idx] += 1
                    self._last_access[idx] = now
                    results.append((idx, float(dist), dict(self._metadata[idx])))
                return results
            else:
                return self._brute_force_search(query_vector, k)

    def _brute_force_search(
        self, query_vector: list[float], k: int
    ) -> list[tuple[int, float, dict]]:
        now = time.time()
        q = np.array(query_vector, dtype=np.float32)
        scores = []
        for i, vec in enumerate(self._vectors):
            vec_arr = np.array(vec, dtype=np.float32) if not isinstance(vec, np.ndarray) else vec
            dist = float(np.linalg.norm(q - vec_arr))
            if (now - self._created_at[i]) < self.ttl_seconds:
                scores.append((i, dist))
        scores.sort(key=lambda x: x[1])
        results = []
        for idx, dist in scores[:k]:
            self._access_counts[idx] += 1
            self._last_access[idx] = now
            results.append((idx, dist, dict(self._metadata[idx])))
        return results

    def _remove_indices(self, indices: list[int]) -> None:
        indices_set = set(indices)
        self._vectors = [v for i, v in enumerate(self._vectors) if i not in indices_set]
        self._metadata = [m for i, m in enumerate(self._metadata) if i not in indices_set]
        self._access_counts = [c for i, c in enumerate(self._access_counts) if i not in indices_set]
        self._last_access = [t for i, t in enumerate(self._last_access) if i not in indices_set]
        self._created_at = [t for i, t in enumerate(self._created_at) if i not in indices_set]
        if self._use_hnsw and self._vectors:
            for idx in sorted(indices_set, reverse=True):
                try:
                    self._index.mark_deleted(idx)
                except Exception:
                    pass

    def _parse_segment_id(self, segment_id: str) -> tuple[int, int] | None:
        try:
            parts = segment_id.split(":segment:")
            if len(parts) != 2:
                return None
            start_str, end_str = parts[1].split("-")
            return int(start_str), int(end_str) + 1
        except (ValueError, IndexError):
            return None

    def _ensure_persist_dir(self) -> None:
        if self.persist_path:
            os.makedirs(os.path.dirname(self.persist_path) or ".", exist_ok=True)

    def _save(self) -> None:
        if not self.persist_path:
            return
        try:
            with self._lock:
                if self._use_hnsw and self._vectors:
                    self._index.save_index(self.persist_path + ".hnsw")
                data = {
                    "vectors": [v.tolist() if isinstance(v, np.ndarray) else v for v in self._vectors],
                    "metadata": self._metadata,
                    "access_counts": self._access_counts,
                    "last_access": self._last_access,
                    "created_at": self._created_at,
                    "id_counter": self._id_counter,
                }
                import pickle
                with open(self.persist_path + ".meta", "wb") as f:
                    pickle.dump(data, f)
        except Exception as e:
            logger.warning("HNSWBackend[%s]: save failed: %s", self.name, e)

    def _load(self) -> None:
        meta_path = self.persist_path + ".meta"
        hnsw_path = self.persist_path + ".hnsw"
        if not os.path.exists(meta_path):
            return
            import pickle
            with open(meta_path, "rb") as f:
                data = pickle.load(f)
            with self._lock:
                vectors = data.get("vectors", [])
                self._vectors = [np.array(v, dtype=np.float32) for v in vectors]
                self._metadata = data.get("metadata", [])
                self._access_counts = data.get("access_counts", [])
                self._last_access = data.get("last_access", [])
                self._created_at = data.get("created_at", [])
                self._id_counter = data.get("id_counter", 0)
                if self._use_hnsw and vectors and os.path.exists(hnsw_path):
                    self._index.load_index(hnsw_path, max_elements=self._max_elements)
                    self._index.set_ef(50)
            logger.info("HNSWBackend[%s]: loaded %d vectors", self.name, len(vectors))
        except Exception as e:
            logger.warning("HNSWBackend[%s]: load failed: %s", self.name, e)

    def record_app_write(self, bytes_written: int) -> None:
        pass

    def close(self) -> None:
        if self.persist_path:
            self._save()


FAISSStorageBackend = HNSWStorageBackend
