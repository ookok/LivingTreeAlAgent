"""JIT加速 — Numba即时编译用于向量相似度和文档分块等热路径.

LivingTree's compute-heavy inner loops (cosine similarity, BM25 scoring,
document splitting) benefit significantly from JIT compilation.

自动检测 + 降级:
  Numba JIT → 10-100x for numeric loops
  NumPy vectorized → 5-10x for batch operations  
  Pure Python → baseline

所有JIT函数都有纯Python回退，确保无Numba时也能正常工作.

Usage:
    from livingtree.core.jit_accel import cosine_similarity_batch, bm25_score
    scores = cosine_similarity_batch(query_vec, doc_vecs)  # JIT accelerated
"""

from __future__ import annotations

import math
from typing import Any

from loguru import logger

try:
    from numba import jit, njit, prange  # type: ignore
    _HAS_NUMBA = True
    logger.debug("JIT: Numba available")
except ImportError:
    _HAS_NUMBA = False
    logger.debug("JIT: Numba not installed — using pure Python fallback")

    # Dummy decorator for when numba is not installed
    def njit(*args: Any, **kwargs: Any) -> Any:
        """No-op decorator when numba unavailable."""
        def decorator(func):
            return func
        return decorator(args[0]) if args and callable(args[0]) else decorator

    def prange(n: int) -> range:
        return range(n)

    jit = njit  # type: ignore


# ═══ JIT: 批处理余弦相似度 ═══

@njit(parallel=True, fastmath=True, cache=True)
def _cosine_similarity_batch_jit(
    query: Any, docs: Any, out: Any,
) -> None:
    """Numba JIT: 批量余弦相似度计算."""
    n_docs = len(docs)
    for i in prange(n_docs):
        dot = 0.0
        norm_q = 0.0
        norm_d = 0.0
        for j in range(len(query)):
            dot += query[j] * docs[i][j]
            norm_q += query[j] * query[j]
            norm_d += docs[i][j] * docs[i][j]
        if norm_q > 0 and norm_d > 0:
            out[i] = dot / math.sqrt(norm_q * norm_d)
        else:
            out[i] = 0.0


def cosine_similarity_batch(
    query_vec: list[float], doc_vecs: list[list[float]],
) -> list[float]:
    """批量余弦相似度（JIT加速）."""
    if not doc_vecs:
        return []

    import numpy as np
    q = np.array(query_vec, dtype=np.float32)
    d = np.array(doc_vecs, dtype=np.float32)

    if _HAS_NUMBA:
        import numpy as np
        out = np.zeros(len(doc_vecs), dtype=np.float32)
        _cosine_similarity_batch_jit(q, d, out)
        return out.tolist()

    # Pure NumPy fallback (still fast)
    q_norm = np.linalg.norm(q)
    d_norm = np.linalg.norm(d, axis=1)
    dot = np.dot(d, q)
    denom = q_norm * d_norm
    denom[denom == 0] = 1.0
    return (dot / denom).tolist()


# ═══ JIT: BM25 评分 ═══

@njit(fastmath=True, cache=True)
def _bm25_score_jit(
    tf: float, doc_len: int, avg_doc_len: float,
    doc_count: int, doc_freq: int, k1: float = 1.2, b: float = 0.75,
) -> float:
    """Numba JIT: BM25 单词评分."""
    idf = math.log(1.0 + (doc_count - doc_freq + 0.5) / (doc_freq + 0.5))
    tf_norm = (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * doc_len / avg_doc_len))
    return idf * tf_norm


def bm25_score(
    tf: float, doc_len: int, avg_doc_len: float,
    doc_count: int, doc_freq: int, k1: float = 1.2, b: float = 0.75,
) -> float:
    """BM25 评分（JIT 加速）."""
    if _HAS_NUMBA:
        return _bm25_score_jit(tf, doc_len, avg_doc_len, doc_count, doc_freq, k1, b)

    # Pure Python fallback
    idf = math.log(1.0 + (doc_count - doc_freq + 0.5) / max(doc_freq + 0.5, 0.5))
    tf_norm = (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * doc_len / max(avg_doc_len, 1.0)))
    return idf * tf_norm


# ═══ JIT: 文档分块边界检测 ═══

@njit(fastmath=True, cache=True)
def _find_chunk_boundaries_jit(
    sentence_lengths: Any, max_chunk_size: int, overlap: int,
) -> Any:
    """Numba JIT: 找到分块边界."""
    n = len(sentence_lengths)
    boundaries = []
    current = 0
    i = 0

    while i < n:
        if current + sentence_lengths[i] > max_chunk_size and current > 0:
            boundaries.append(i)
            # Overlap: go back
            overlap_size = 0
            j = i - 1
            while j >= 0 and overlap_size < overlap:
                overlap_size += sentence_lengths[j]
                j -= 1
            i = max(0, j + 1)
            current = 0
        else:
            current += sentence_lengths[i]
            i += 1

    if current > 0:
        boundaries.append(i)

    return boundaries


# ═══ JIT: Jaccard 相似度 ═══

@njit(fastmath=True, cache=True)
def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Jaccard 相似度（JIT 加速，用于文档去重）."""
    intersection = 0
    for item in set_a:
        if item in set_b:
            intersection += 1
    union = len(set_a) + len(set_b) - intersection
    return intersection / union if union > 0 else 0.0


# ═══ Status ═══

def jit_status() -> dict[str, Any]:
    """JIT 加速状态报告."""
    import numpy as np
    return {
        "numba_available": _HAS_NUMBA,
        "numpy_available": True,
        "recommended": "pip install numba" if not _HAS_NUMBA else "✓ JIT enabled",
    }
