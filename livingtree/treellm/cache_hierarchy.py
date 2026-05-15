"""3-Tier LLM Response Cache Hierarchy.

Design: Unified cache layer replacing isolated prompt_cache.py and response_cache.py.
Three tiers with automatic promotion and semantic similarity search.

Tiers:
  L1_MEMORY   — in-process OrderedDict, <1ms, LRU eviction at 500 entries
  L2_SQLITE   — aiosqlite disk cache, ~5ms, 24h TTL + LRU overflow at 10000 entries
  L3_SEMANTIC — embedding cosine similarity, ~50ms, threshold 0.85, 5000 entries

Flow:
  get(key, prompt) → L1 hit → return (response, L1)
                   → L1 miss → L2 hit → return (response, L2)
                   → L2 miss → L3 semantic → return (response, L3) if sim >= threshold
                   → total miss → return (None, None)

  set(key, response, model, tokens, prompt) → store in all 3 tiers

  Auto-promotion: entries accessed PROMOTE_ACCESS_COUNT (3) times from L2/L3
  are promoted to L1 for sub-millisecond access.

Integration:
  Should be used by treellm/prompt_cache.py and treellm/response_cache.py,
  replacing their current isolated implementations.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    import aiosqlite
    _HAS_AIOSQLITE = True
except ImportError:  # pragma: no cover
    _HAS_AIOSQLITE = False
    aiosqlite = None  # type: ignore

try:
    from livingtree.knowledge.vector_store import VectorStore, LocalEmbeddingBackend
    _HAS_VECTOR_STORE = True
except ImportError:  # pragma: no cover
    _HAS_VECTOR_STORE = False
    VectorStore = None  # type: ignore
    LocalEmbeddingBackend = None  # type: ignore


class CacheTier(str, Enum):
    """Three cache hierarchy levels with distinct latency characteristics."""
    L1_MEMORY = "L1_MEMORY"       # in-process dict, <1ms
    L2_SQLITE = "L2_SQLITE"       # aiosqlite disk, ~5ms
    L3_SEMANTIC = "L3_SEMANTIC"   # embedding cosine similarity, ~50ms


@dataclass
class CacheEntry:
    """A single cached LLM response stored across tiers."""
    key: str
    response_text: str
    tokens: int = 0
    model: str = ""
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    tier: CacheTier = CacheTier.L1_MEMORY

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_accessed


@dataclass
class TierStats:
    """Per-tier hit/miss/size statistics."""
    hits: int = 0
    misses: int = 0
    entries: int = 0
    memory_bytes: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / max(1, total)


@dataclass
class CacheStats:
    """Aggregate cache hierarchy statistics."""
    l1: TierStats = field(default_factory=TierStats)
    l2: TierStats = field(default_factory=TierStats)
    l3: TierStats = field(default_factory=TierStats)

    @property
    def total_hits(self) -> int:
        return self.l1.hits + self.l2.hits + self.l3.hits

    @property
    def total_misses(self) -> int:
        return self.l1.misses + self.l2.misses + self.l3.misses

    @property
    def hit_rate(self) -> float:
        total = self.total_hits + self.total_misses
        return self.total_hits / max(1, total)

    @property
    def total_entries(self) -> int:
        return self.l1.entries + self.l2.entries + self.l3.entries

    @property
    def memory_bytes(self) -> int:
        return self.l1.memory_bytes + self.l2.memory_bytes + self.l3.memory_bytes


class CacheHierarchy:
    """3-tier LLM response cache hierarchy.

    Replaces isolated prompt_cache.py and response_cache.py with a unified
    tiered cache supporting automatic promotion, semantic search, and
    configurable eviction policies.

    L1 (Memory):  In-process OrderedDict with LRU eviction. Max 500 entries.
    L2 (SQLite):  aiosqlite disk persistence. Max 10000 entries, 24h TTL.
    L3 (Semantic): Embedding cosine similarity via VectorStore. Threshold 0.85.
    """

    # ── Default Configuration ──

    L1_MAX_ENTRIES: int = 500

    L2_MAX_ENTRIES: int = 10000
    L2_TTL_SECONDS: int = 86400  # 24 hours
    L2_DB_PATH: str = ".livingtree/cache_l2.db"

    L3_MAX_ENTRIES: int = 5000
    L3_SIMILARITY_THRESHOLD: float = 0.85

    PROMOTE_ACCESS_COUNT: int = 3

    def __init__(
        self,
        l1_max: int | None = None,
        l2_max: int | None = None,
        l2_ttl: int | None = None,
        l2_db_path: str | None = None,
        l3_max: int | None = None,
        l3_threshold: float | None = None,
    ) -> None:
        # ── L1: in-process OrderedDict LRU ──
        self._l1: OrderedDict[str, CacheEntry] = OrderedDict()
        self._l1_max: int = l1_max if l1_max is not None else self.L1_MAX_ENTRIES
        self._l1_hits: int = 0
        self._l1_misses: int = 0

        # ── L2: aiosqlite disk ──
        self._l2_db_path: Path = Path(l2_db_path or self.L2_DB_PATH)
        self._l2_max: int = l2_max if l2_max is not None else self.L2_MAX_ENTRIES
        self._l2_ttl: int = l2_ttl if l2_ttl is not None else self.L2_TTL_SECONDS
        self._l2_initialized: bool = False
        self._l2_init_lock: asyncio.Lock = asyncio.Lock()
        self._l2_hits: int = 0
        self._l2_misses: int = 0

        # ── L3: embedding semantic cache ──
        self._l3_max: int = l3_max if l3_max is not None else self.L3_MAX_ENTRIES
        self._l3_threshold: float = l3_threshold if l3_threshold is not None else self.L3_SIMILARITY_THRESHOLD
        self._l3_keys: OrderedDict[str, CacheEntry] = OrderedDict()
        self._l3_embeddings: dict[str, list[float]] = {}
        self._l3_hits: int = 0
        self._l3_misses: int = 0
        self._vector_store: Optional[VectorStore] = None

        if _HAS_VECTOR_STORE:
            try:
                backend = LocalEmbeddingBackend()
                self._vector_store = VectorStore(backend, collection_name="cache_l3")
                logger.info("CacheHierarchy L3: VectorStore ready")
            except Exception as e:
                logger.warning(f"CacheHierarchy L3 init failed: {e}")

        logger.info(
            f"CacheHierarchy: L1(max={self._l1_max}) "
            f"L2(max={self._l2_max}, ttl={self._l2_ttl // 3600}h) "
            f"L3(max={self._l3_max}, threshold={self._l3_threshold})"
        )

    # ═══════════════════════════════════════════════════
    #  L2: aiosqlite initialization (lazy, on first use)
    # ═══════════════════════════════════════════════════

    async def _init_l2(self) -> None:
        """Initialize L2 SQLite database. Safe to call multiple times."""
        if self._l2_initialized or not _HAS_AIOSQLITE:
            return
        async with self._l2_init_lock:
            if self._l2_initialized:
                return
            try:
                self._l2_db_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiosqlite.connect(str(self._l2_db_path)) as db:
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS cache_l2 (
                            key TEXT PRIMARY KEY,
                            response_text TEXT NOT NULL,
                            tokens INTEGER DEFAULT 0,
                            model TEXT DEFAULT '',
                            created_at REAL NOT NULL,
                            last_accessed REAL NOT NULL,
                            access_count INTEGER DEFAULT 0
                        )
                    """)
                    await db.execute(
                        "CREATE INDEX IF NOT EXISTS idx_l2_accessed "
                        "ON cache_l2(last_accessed DESC)"
                    )
                    await db.execute(
                        "CREATE INDEX IF NOT EXISTS idx_l2_created "
                        "ON cache_l2(created_at)"
                    )
                    await db.execute(
                        "CREATE INDEX IF NOT EXISTS idx_l2_access_count "
                        "ON cache_l2(access_count DESC)"
                    )
                    await db.commit()
                self._l2_initialized = True
                logger.info(f"CacheHierarchy L2: SQLite ready at {self._l2_db_path}")
            except Exception as e:
                logger.warning(f"CacheHierarchy L2 init failed: {e}")

    # ═══════════════════
    #  Key generation
    # ═══════════════════

    @staticmethod
    def _hash_key(key: str) -> str:
        """Produce a stable 32-char hex digest from the cache key."""
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    # ═══════════════════
    #  Core: get (tiered lookup)
    # ═══════════════════

    async def get(
        self, key: str, prompt_text: str = "",
    ) -> tuple[Optional[str], Optional[CacheTier]]:
        """Tiered cache lookup: L1 → L2 → L3.

        Args:
            key: Cache key (query hash or canonical key).
            prompt_text: Original prompt text, required for L3 semantic search.

        Returns:
            (response_text, hit_tier) on hit, or (None, None) on miss.
        """
        hashed = self._hash_key(key)

        # ── L1: in-process memory ──
        if hashed in self._l1:
            entry = self._l1[hashed]
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._l1.move_to_end(hashed)
            self._l1_hits += 1
            logger.debug(f"CacheHierarchy L1 hit: {key[:60]}")
            return entry.response_text, CacheTier.L1_MEMORY
        self._l1_misses += 1

        # ── L2: aiosqlite disk ──
        await self._init_l2()
        if self._l2_initialized:
            try:
                async with aiosqlite.connect(str(self._l2_db_path)) as db:
                    db.row_factory = aiosqlite.Row
                    cursor = await db.execute(
                        "SELECT response_text, tokens, model, created_at, "
                        "last_accessed, access_count FROM cache_l2 WHERE key = ?",
                        (hashed,),
                    )
                    row = await cursor.fetchone()
                    if row is not None:
                        created_at = row["created_at"]
                        if (time.time() - created_at) <= self._l2_ttl:
                            new_count = row["access_count"] + 1
                            now = time.time()
                            await db.execute(
                                "UPDATE cache_l2 SET access_count = ?, last_accessed = ? "
                                "WHERE key = ?",
                                (new_count, now, hashed),
                            )
                            await db.commit()

                            entry = CacheEntry(
                                key=hashed,
                                response_text=row["response_text"],
                                tokens=row["tokens"],
                                model=row["model"],
                                created_at=created_at,
                                last_accessed=now,
                                access_count=new_count,
                                tier=CacheTier.L2_SQLITE,
                            )

                            # Auto-promotion: frequent L2 access → L1
                            if new_count >= self.PROMOTE_ACCESS_COUNT:
                                self._l1[hashed] = entry
                                self._evict_l1()
                                logger.debug(
                                    f"CacheHierarchy: promoted {key[:40]} "
                                    f"(access={new_count}) from L2 to L1"
                                )

                            self._l2_hits += 1
                            logger.debug(f"CacheHierarchy L2 hit: {key[:60]}")
                            return entry.response_text, CacheTier.L2_SQLITE
            except Exception as e:
                logger.debug(f"CacheHierarchy L2 get error: {e}")
        self._l2_misses += 1

        # ── L3: semantic embedding search ──
        if prompt_text and self._vector_store and self._l3_embeddings:
            result = self._semantic_search(prompt_text)
            if result is not None:
                response_text, match_key = result
                entry = self._l3_keys[match_key]
                entry.access_count += 1
                entry.last_accessed = time.time()

                if entry.access_count >= self.PROMOTE_ACCESS_COUNT:
                    self._l1[match_key] = entry
                    self._evict_l1()
                    logger.debug(
                        f"CacheHierarchy: promoted {key[:40]} "
                        f"(access={entry.access_count}) from L3 to L1"
                    )

                self._l3_hits += 1
                logger.debug(
                    f"CacheHierarchy L3 hit: sim={match_key[:20]} for {key[:60]}"
                )
                return response_text, CacheTier.L3_SEMANTIC
        self._l3_misses += 1

        return None, None

    # ═══════════════════
    #  Core: set (store in all tiers)
    # ═══════════════════

    async def set(
        self,
        key: str,
        response: str,
        model: str = "",
        tokens: int = 0,
        prompt_text: str = "",
    ) -> None:
        """Store an entry in all three cache tiers.

        Args:
            key: Cache key.
            response: LLM response text to cache.
            model: Source model name (for analytics).
            tokens: Token count of the response.
            prompt_text: Original prompt text, used to compute L3 embedding.
        """
        if not response:
            return

        hashed = self._hash_key(key)
        now = time.time()

        entry = CacheEntry(
            key=hashed,
            response_text=response,
            tokens=tokens,
            model=model,
            created_at=now,
            last_accessed=now,
            access_count=0,
            tier=CacheTier.L1_MEMORY,
        )

        # ── L1 store ──
        self._l1[hashed] = entry
        self._evict_l1()

        # ── L2 store ──
        await self._init_l2()
        if self._l2_initialized:
            try:
                async with aiosqlite.connect(str(self._l2_db_path)) as db:
                    await db.execute(
                        "INSERT OR REPLACE INTO cache_l2 "
                        "(key, response_text, tokens, model, created_at, "
                        "last_accessed, access_count) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (hashed, response, tokens, model, now, now, 0),
                    )
                    await db.commit()
                await self._evict_l2_lru()
            except Exception as e:
                logger.debug(f"CacheHierarchy L2 set error: {e}")

        # ── L3 store ──
        if prompt_text and self._vector_store:
            try:
                embedding = self._vector_store.embed(prompt_text)
                self._l3_keys[hashed] = entry
                self._l3_embeddings[hashed] = embedding
                self._l3_keys.move_to_end(hashed)
                self._evict_l3()
            except Exception as e:
                logger.debug(f"CacheHierarchy L3 set error: {e}")

        logger.debug(
            f"CacheHierarchy set: {key[:60]} (tokens={tokens}, model={model})"
        )

    # ═══════════════════
    #  Invalidate
    # ═══════════════════

    async def invalidate(self, key: str) -> bool:
        """Remove an entry from all three tiers. Returns True if any removed."""
        hashed = self._hash_key(key)
        removed = False

        if hashed in self._l1:
            del self._l1[hashed]
            removed = True

        await self._init_l2()
        if self._l2_initialized:
            try:
                async with aiosqlite.connect(str(self._l2_db_path)) as db:
                    cursor = await db.execute(
                        "DELETE FROM cache_l2 WHERE key = ?", (hashed,)
                    )
                    await db.commit()
                    if cursor.rowcount > 0:
                        removed = True
            except Exception as e:
                logger.debug(f"CacheHierarchy L2 invalidate error: {e}")

        if hashed in self._l3_keys:
            del self._l3_keys[hashed]
            self._l3_embeddings.pop(hashed, None)
            removed = True

        if removed:
            logger.debug(f"CacheHierarchy invalidated: {key[:60]}")
        return removed

    # ═══════════════════
    #  Semantic Search
    # ═══════════════════

    def _semantic_search(self, prompt_text: str) -> Optional[tuple[str, str]]:
        """Internal: find the best L3 match via cosine similarity.

        Returns (response_text, matched_key) or None if no match meets threshold.
        """
        if not self._vector_store or not self._l3_embeddings:
            return None

        query_embedding = self._vector_store.embed(prompt_text)
        best_key: Optional[str] = None
        best_sim: float = -1.0

        for entry_key, stored_embedding in self._l3_embeddings.items():
            sim = self._cosine_similarity(query_embedding, stored_embedding)
            if sim > best_sim:
                best_sim = sim
                best_key = entry_key

        if best_key is not None and best_sim >= self._l3_threshold:
            entry = self._l3_keys[best_key]
            self._l3_keys.move_to_end(best_key)
            return entry.response_text, best_key

        return None

    def semantic_search(
        self, prompt_text: str, threshold: float | None = None,
    ) -> Optional[str]:
        """Find semantically similar cached response via embedding cosine similarity.

        Args:
            prompt_text: Prompt text to find semantically similar cached entries for.
            threshold: Minimum cosine similarity (defaults to configured 0.85).

        Returns:
            Matched response_text or None.
        """
        original_threshold = self._l3_threshold
        self._l3_threshold = threshold if threshold is not None else original_threshold
        try:
            result = self._semantic_search(prompt_text)
            return result[0] if result else None
        finally:
            self._l3_threshold = original_threshold

    # ═══════════════════
    #  Warmup
    # ═══════════════════

    async def warmup(self) -> int:
        """Preload frequently accessed L2 entries into L1. Returns count loaded."""
        await self._init_l2()
        if not self._l2_initialized:
            return 0

        count = 0
        try:
            async with aiosqlite.connect(str(self._l2_db_path)) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT key, response_text, tokens, model, created_at, "
                    "last_accessed, access_count FROM cache_l2 "
                    "WHERE access_count >= ? "
                    "ORDER BY access_count DESC LIMIT ?",
                    (self.PROMOTE_ACCESS_COUNT, self._l1_max // 2),
                )
                rows = await cursor.fetchall()
                for row in rows:
                    entry_key = row["key"]
                    if entry_key not in self._l1:
                        entry = CacheEntry(
                            key=entry_key,
                            response_text=row["response_text"],
                            tokens=row["tokens"],
                            model=row["model"],
                            created_at=row["created_at"],
                            last_accessed=row["last_accessed"],
                            access_count=row["access_count"],
                            tier=CacheTier.L1_MEMORY,
                        )
                        self._l1[entry_key] = entry
                        count += 1
                self._evict_l1()
        except Exception as e:
            logger.warning(f"CacheHierarchy warmup error: {e}")

        logger.info(f"CacheHierarchy warmup: {count} entries loaded into L1")
        return count

    # ═══════════════════
    #  Eviction
    # ═══════════════════

    def _evict_l1(self) -> int:
        """LRU eviction from L1 when size exceeds max. Returns count evicted."""
        evicted = 0
        while len(self._l1) > self._l1_max:
            self._l1.popitem(last=False)
            evicted += 1
        if evicted:
            logger.debug(f"CacheHierarchy L1 evicted {evicted} entries")
        return evicted

    def evict_l1(self) -> int:
        """Public: force LRU eviction on L1."""
        return self._evict_l1()

    async def _evict_l2_lru(self) -> int:
        """LRU overflow eviction on L2. Evicts entries exceeding L2 max."""
        await self._init_l2()
        if not self._l2_initialized:
            return 0

        try:
            async with aiosqlite.connect(str(self._l2_db_path)) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM cache_l2")
                row = await cursor.fetchone()
                count = row[0] if row else 0

                excess = count - self._l2_max
                if excess > 0:
                    await db.execute(
                        "DELETE FROM cache_l2 WHERE key IN ("
                        "  SELECT key FROM cache_l2 "
                        "  ORDER BY last_accessed ASC LIMIT ?"
                        ")",
                        (excess,),
                    )
                    await db.commit()
                    logger.debug(
                        f"CacheHierarchy L2 LRU evicted {excess} entries"
                    )
                    return excess
        except Exception as e:
            logger.debug(f"CacheHierarchy L2 LRU eviction error: {e}")

        return 0

    async def evict_l2(self) -> int:
        """Time-based eviction (24h TTL) + LRU overflow on L2.
        Returns total entries removed.
        """
        await self._init_l2()
        if not self._l2_initialized:
            return 0

        total_evicted = 0
        try:
            async with aiosqlite.connect(str(self._l2_db_path)) as db:
                # Time-based eviction
                cutoff = time.time() - self._l2_ttl
                cursor = await db.execute(
                    "DELETE FROM cache_l2 WHERE created_at < ?", (cutoff,)
                )
                await db.commit()
                ttl_evicted = cursor.rowcount
                total_evicted += ttl_evicted

                # LRU overflow
                cursor = await db.execute("SELECT COUNT(*) FROM cache_l2")
                row = await cursor.fetchone()
                count = row[0] if row else 0
                excess = count - self._l2_max
                if excess > 0:
                    await db.execute(
                        "DELETE FROM cache_l2 WHERE key IN ("
                        "  SELECT key FROM cache_l2 "
                        "  ORDER BY last_accessed ASC LIMIT ?"
                        ")",
                        (excess,),
                    )
                    await db.commit()
                    total_evicted += excess

                # Reclaim disk space
                await db.execute("PRAGMA optimize")
                await db.commit()
        except Exception as e:
            logger.warning(f"CacheHierarchy L2 eviction error: {e}")

        if total_evicted:
            logger.info(
                f"CacheHierarchy L2 evicted {total_evicted} entries "
                f"(TTL retired + LRU overflow)"
            )
        return total_evicted

    def _evict_l3(self) -> int:
        """LRU eviction from L3 when size exceeds max. Returns count evicted."""
        evicted = 0
        while len(self._l3_keys) > self._l3_max:
            oldest_key, _ = self._l3_keys.popitem(last=False)
            self._l3_embeddings.pop(oldest_key, None)
            evicted += 1
        if evicted:
            logger.debug(f"CacheHierarchy L3 evicted {evicted} entries")
        return evicted

    # ═══════════════════
    #  Stats
    # ═══════════════════

    def stats(self) -> CacheStats:
        """Return CacheStats with per-tier hit/miss/size breakdown."""
        l1_bytes = sum(
            len(e.response_text.encode("utf-8", errors="replace"))
            + len(e.key)
            + 128
            for e in self._l1.values()
        )

        l2_bytes = (
            self._l2_db_path.stat().st_size
            if self._l2_db_path.exists()
            else 0
        )

        l3_bytes = sum(
            len(e.response_text.encode("utf-8", errors="replace"))
            + len(e.key)
            + 128
            + len(emb) * 8
            for e, emb in zip(
                self._l3_keys.values(), self._l3_embeddings.values()
            )
        )

        return CacheStats(
            l1=TierStats(
                hits=self._l1_hits,
                misses=self._l1_misses,
                entries=len(self._l1),
                memory_bytes=l1_bytes,
            ),
            l2=TierStats(
                hits=self._l2_hits,
                misses=self._l2_misses,
                entries=0,  # populated on demand via _l2_count
                memory_bytes=l2_bytes,
            ),
            l3=TierStats(
                hits=self._l3_hits,
                misses=self._l3_misses,
                entries=len(self._l3_keys),
                memory_bytes=l3_bytes,
            ),
        )

    # ═══════════════════
    #  Flush
    # ═══════════════════

    async def flush(self) -> int:
        """Flush all cache tiers. Returns total entries removed."""
        l1_count = len(self._l1)
        self._l1.clear()

        l2_count = 0
        await self._init_l2()
        if self._l2_initialized:
            try:
                async with aiosqlite.connect(str(self._l2_db_path)) as db:
                    cursor = await db.execute("SELECT COUNT(*) FROM cache_l2")
                    row = await cursor.fetchone()
                    l2_count = row[0] if row else 0
                    await db.execute("DELETE FROM cache_l2")
                    await db.commit()
            except Exception as e:
                logger.warning(f"CacheHierarchy flush L2 error: {e}")

        l3_count = len(self._l3_keys)
        self._l3_keys.clear()
        self._l3_embeddings.clear()

        total = l1_count + l2_count + l3_count
        logger.info(
            f"CacheHierarchy flushed: {total} entries "
            f"(L1={l1_count}, L2={l2_count}, L3={l3_count})"
        )
        return total

    # ═══════════════════
    #  Utility: cosine similarity
    # ═══════════════════

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Cosine similarity between two embedding vectors. Range [-1, 1]."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
        norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
        return dot / (norm_a * norm_b)

    # ═══════════════════
    #  Observable state (for admin dashboards)
    # ═══════════════════

    @property
    def l1_size(self) -> int:
        return len(self._l1)

    @property
    def l3_size(self) -> int:
        return len(self._l3_keys)

    @property
    def l2_ready(self) -> bool:
        return self._l2_initialized

    @property
    def l3_ready(self) -> bool:
        return self._vector_store is not None


# ═══════════════════════════════════════════════════════════
#  Singleton
# ═══════════════════════════════════════════════════════════

_cache_hierarchy: Optional[CacheHierarchy] = None
_cache_hierarchy_lock = threading.Lock()


def get_cache_hierarchy() -> CacheHierarchy:
    """Get or create the singleton CacheHierarchy instance.

    Usage:
        from livingtree.treellm.cache_hierarchy import get_cache_hierarchy
        cache = get_cache_hierarchy()
        response, tier = await cache.get(key, prompt_text)
        await cache.set(key, response, model="deepseek", tokens=150, prompt_text=text)
    """
    global _cache_hierarchy
    if _cache_hierarchy is None:
        with _cache_hierarchy_lock:
            if _cache_hierarchy is None:
                _cache_hierarchy = CacheHierarchy()
    return _cache_hierarchy
