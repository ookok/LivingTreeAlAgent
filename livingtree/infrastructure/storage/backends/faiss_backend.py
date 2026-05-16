"""FAISS vector storage backend — segment-aware vector index for DisCoGC.

Maps FAISS index partitions into logical segments. Each segment holds
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
from pathlib import Path
from typing import Any, List, Dict, Optional

from loguru import logger

from ..storage_layer import StorageBackend, StorageSegment
from ..gc_metrics import StorageStats

try:
    import numpy as np
except ImportError:
    np = None

_SEGMENT_VECTORS = 1000  # Vectors per logical segment

try:
    import faiss
except ImportError:
    faiss = None

# Hardware accelerator support
try:
    from livingtree.core.hardware_acceleration import get_accelerator
except ImportError:
    get_accelerator = None


class FAISSStorageBackend(StorageBackend):
    """DisCoGC-compatible FAISS vector storage adapter.

    Wraps a FAISS index or a simple list-based fallback. Each logical
    segment maps to a range of vector IDs. Supports:
      - Discard: remove stale vectors in-place from a segment
      - Compaction: rebuild segments by copying live vectors

    Falls back to in-memory list-based storage when FAISS is unavailable.
    """

    def __init__(
        self,
        name: str = "",
        dimension: int = 384,
        segment_vectors: int = _SEGMENT_VECTORS,
        persist_path: str = "",
        ttl_seconds: int = 86400 * 7,
    ):
        super().__init__(name=name or "faiss")
        self.dimension = dimension
        self.segment_vectors = segment_vectors
        self.persist_path = persist_path
        self.ttl_seconds = ttl_seconds

        self._lock = threading.Lock()
        self._index: Any = None
        self._vectors: List[np.ndarray] = [] if np is not None else []
        self._metadata: List[Dict[str, Any]] = []
        self._access_counts: List[int] = []
        self._last_access: List[float] = []
        self._created_at: List[float] = []
        self._accelerator = None

        # Try to use hardware accelerator for GPU FAISS
        if get_accelerator is not None:
            try:
                self._accelerator = get_accelerator()
            except Exception as e:
                logger.debug("HardwareAccelerator init failed: %s", e)

        if faiss is not None and faiss is not None:
            # Use GPU index if accelerator says so
            if self._accelerator and self._accelerator.has_cuda:
                try:
                    self._index = self._accelerator.faiss_gpu_index(dimension)
                    logger.info("FAISSStorageBackend[%s]: Using GPU FAISS index", self.name)
                except Exception as e:
                    logger.warning("FAISS GPU index failed: %s, falling back to CPU", e)
                    self._index = faiss.IndexFlatL2(dimension)
            else:
                self._index = faiss.IndexFlatL2(dimension)
        elif np is not None:
            logger.info("FAISSStorageBackend[%s]: FAISS not available, using list fallback", self.name)
        else:
            logger.warning("FAISSStorageBackend[%s]: numpy not available, limited functionality", self.name)
            self._vectors = []

        if persist_path:
            self._ensure_persist_dir()
            self._load()

    def get_stats(self) -> StorageStats:
        with self._lock:
            vector_count = len(self._metadata)
            now = time.time()
            stale_count = sum(
                1 for t in self._created_at
                if (now - t) >= self.ttl_seconds
            )
            live_count = vector_count - stale_count

            bytes_per_vector = self.dimension * 4 + 256  # vector + metadata estimate
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

    def list_segments(self) -> List[StorageSegment]:
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
                seg_metadata_bytes = 0
                min_created = now
                max_accessed = 0.0
                read_count = 0

                for i in range(start_idx, end_idx):
                    vec_bytes = self.dimension * 4 + seg_metadata_bytes
                    seg_metadata_bytes += len(str(self._metadata[i])) if i < len(self._metadata) else 0
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

                segment = StorageSegment(
                    segment_id=f"faiss:segment:{start_idx}-{end_idx - 1}",
                    total_bytes=seg_live + seg_stale,
                    live_bytes=seg_live,
                    stale_bytes=seg_stale,
                    created_at=min_created,
                    last_read_at=max_accessed,
                    write_count=end_idx - start_idx,
                    read_count=read_count,
                    metadata={
                        "start_idx": start_idx,
                        "end_idx": end_idx,
                        "vector_count": end_idx - start_idx,
                    },
                )
                segments.append(segment)

            return segments

    def discard_segments(self, segment_ids: List[str]) -> int:
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
                    if i < len(self._created_at)
                    and (now - self._created_at[i]) >= self.ttl_seconds
                ]

                total_in_range = actual_end - start_idx
                if len(stale_indices) == total_in_range and total_in_range > 0:
                    freed = sum(self.dimension * 4 + 256 for _ in stale_indices)
                    self._remove_indices(stale_indices)
                    total_freed += freed
                    logger.debug(
                        "FAISSBackend[%s]: discarded segment %s (%d vectors)",
                        self.name, seg_id, len(stale_indices),
                    )

            return total_freed

    def compact_segments(self, segment_ids: List[str]) -> tuple[int, int]:
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
                    is_stale = (now - self._created_at[i]) >= self.ttl_seconds
                    if is_stale:
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
        self, vectors: List[List[float]], metadata_list: Optional[List[Dict]] = None
    ) -> int:
        """Add vectors to the index. Returns the starting index."""
        with self._lock:
            if not vectors:
                return len(self._metadata)

            start_index = len(self._metadata)
            now = time.time()

            if np is not None:
                arr = np.array(vectors, dtype=np.float32)
            else:
                arr = vectors

            for i, vec in enumerate(vectors):
                if np is not None:
                    self._vectors.append(np.array(vec, dtype=np.float32))
                else:
                    self._vectors.append(vec)
                self._metadata.append(metadata_list[i] if metadata_list else {})
                self._access_counts.append(0)
                self._last_access.append(now)
                self._created_at.append(now)

            if self._index is not None and np is not None:
                self._index.add(arr)

            if self.persist_path:
                self._save()

            return start_index

    def search(self, query_vector: List[float], k: int = 10) -> List[Tuple[int, float, Dict]]:
        """Search the index. Returns list of (index, distance, metadata)."""
        with self._lock:
            if not self._vectors:
                return []

            if self._index is not None and np is not None:
                q = np.array([query_vector], dtype=np.float32)
                distances, indices = self._index.search(q, min(k, self._index.ntotal))
                results = []
                now = time.time()
                for dist, idx in zip(distances[0], indices[0]):
                    if idx < 0 or idx >= len(self._metadata):
                        continue
                    if (now - self._created_at[idx]) >= self.ttl_seconds:
                        continue
                    self._access_counts[idx] += 1
                    self._last_access[idx] = now
                    results.append((int(idx), float(dist), dict(self._metadata[idx])))
                return results
            else:
                return self._brute_force_search(query_vector, k)

    def _brute_force_search(
        self, query_vector: List[float], k: int
    ) -> List[Tuple[int, float, Dict]]:
        if not np is not None:
            return []
        now = time.time()
        q = np.array(query_vector, dtype=np.float32)
        scores = []
        for i, vec in enumerate(self._vectors):
            vec_arr = np.array(vec, dtype=np.float32) if not isinstance(vec, np.ndarray) else vec
            dist = float(np.linalg.norm(q - vec_arr))
            is_stale = (now - self._created_at[i]) >= self.ttl_seconds
            if not is_stale:
                scores.append((i, dist))
        scores.sort(key=lambda x: x[1])
        results = []
        for idx, dist in scores[:k]:
            self._access_counts[idx] += 1
            self._last_access[idx] = now
            results.append((idx, dist, dict(self._metadata[idx])))
        return results

    def _remove_indices(self, indices: List[int]) -> None:
        indices_set = set(indices)
        self._vectors = [
            v for i, v in enumerate(self._vectors) if i not in indices_set
        ]
        self._metadata = [
            m for i, m in enumerate(self._metadata) if i not in indices_set
        ]
        self._access_counts = [
            c for i, c in enumerate(self._access_counts) if i not in indices_set
        ]
        self._last_access = [
            t for i, t in enumerate(self._last_access) if i not in indices_set
        ]
        self._created_at = [
            t for i, t in enumerate(self._created_at) if i not in indices_set
        ]

        if self._index is not None and np is not None and self._vectors:
            dim = self.dimension
            new_index = faiss.IndexFlatL2(dim)
            arr = np.array([v.tolist() if isinstance(v, np.ndarray) else v for v in self._vectors], dtype=np.float32)
            if len(arr) > 0:
                new_index.add(arr)
            self._index = new_index

    def _parse_segment_id(self, segment_id: str) -> Optional[tuple[int, int]]:
        try:
            parts = segment_id.split(":segment:")
            if len(parts) != 2:
                return None
            range_part = parts[1]
            start_str, end_str = range_part.split("-")
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
            import pickle
            with self._lock:
                data = {
                    "vectors": [v.tolist() if isinstance(v, np.ndarray) else v for v in self._vectors],
                    "metadata": self._metadata,
                    "access_counts": self._access_counts,
                    "last_access": self._last_access,
                    "created_at": self._created_at,
                }
            with open(self.persist_path, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.warning("FAISSBackend[%s]: save failed: %s", self.name, e)

    def _load(self) -> None:
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        try:
            import pickle
            with open(self.persist_path, "rb") as f:
                data = pickle.load(f)
            with self._lock:
                vectors = data.get("vectors", [])
                if np is not None:
                    self._vectors = [np.array(v, dtype=np.float32) for v in vectors]
                    if self._index is not None and vectors:
                        arr = np.array(vectors, dtype=np.float32)
                        self._index.add(arr)
                else:
                    self._vectors = vectors
                self._metadata = data.get("metadata", [])
                self._access_counts = data.get("access_counts", [])
                self._last_access = data.get("last_access", [])
                self._created_at = data.get("created_at", [])
            logger.info("FAISSBackend[%s]: loaded %d vectors from %s", self.name, len(vectors), self.persist_path)
        except Exception as e:
            logger.warning("FAISSBackend[%s]: load failed: %s", self.name, e)

    def record_app_write(self, bytes_written: int) -> None:
        pass

    def close(self) -> None:
        if self.persist_path:
            self._save()
