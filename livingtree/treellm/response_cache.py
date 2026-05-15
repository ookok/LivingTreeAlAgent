"""Hot Response Cache — instant responses for frequent queries.

Design (#5): Hash user queries → cache LLM responses → instant <5ms return on hit.

Cache tiers:
  L1 (memory):   LRU dict, < 1000 entries, < 1ms lookup
  L2 (disk):     SQLite, unlimited entries, < 5ms lookup

Cache invalidation:
  - TTL-based: entries expire after configurable time (default 1 hour)
  - Pattern-based: queries containing "now"/"today"/"最新" bypass cache
  - Manual flush: /api/cache/flush endpoint

Integration:
  FlashFirstOrchestrator.chat_stream() → checks cache before any LLM call.
  hub.chat() → optional cache layer.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class CachedResponse:
    """A cached chat response."""
    query: str
    response: str
    intent: str = ""
    model: str = ""
    timestamp: float = field(default_factory=time.time)
    hit_count: int = 0
    ttl_seconds: int = 3600  # 1 hour default

    @property
    def expired(self) -> bool:
        return (time.time() - self.timestamp) > self.ttl_seconds


class ResponseCache:
    """Two-tier response cache with TTL-based expiration.

    L1 (memory): OrderedDict LRU, max 1000 entries.
    L2 (disk): SQLite, unlimited.
    """

    # Queries containing these keywords ALWAYS bypass cache
    BYPASS_KEYWORDS = [
        "现在", "此刻", "今天", "刚刚", "最新", "实时",
        "now", "today", "latest", "current", "realtime",
        "当前时间", "当前日期",
    ]

    def __init__(
        self,
        max_l1_entries: int = 1000,
        disk_path: str = ".livingtree/response_cache.db",
        default_ttl: int = 3600,
    ):
        self._l1: OrderedDict[str, CachedResponse] = OrderedDict()
        self._max_l1 = max_l1_entries
        self._disk_path = Path(disk_path)
        self._default_ttl = default_ttl
        self._stats = {"hits": 0, "misses": 0, "l1_size": 0}
        self._init_l2()

    # ── L2 (Disk) ──

    def _init_l2(self) -> None:
        """Initialize SQLite cache table."""
        try:
            self._disk_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._disk_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    query_hash TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL,
                    intent TEXT DEFAULT '',
                    model TEXT DEFAULT '',
                    timestamp REAL NOT NULL,
                    hit_count INTEGER DEFAULT 0,
                    ttl_seconds INTEGER DEFAULT 3600
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hits ON cache(hit_count DESC)")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"ResponseCache L2 init: {e}")

    # ── Core API ──

    def _should_bypass(self, query: str) -> bool:
        """Check if query contains time-sensitive keywords."""
        query_lower = query.lower()
        return any(kw in query_lower for kw in self.BYPASS_KEYWORDS)

    def _hash_query(self, query: str) -> str:
        """Normalize + hash query for cache key."""
        normalized = query.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    async def get(self, query: str) -> Optional[str]:
        """Try to retrieve cached response. Returns None on miss."""
        if self._should_bypass(query):
            self._stats["misses"] += 1
            return None

        key = self._hash_query(query)

        # L1 (memory) check
        if key in self._l1:
            cached = self._l1[key]
            if not cached.expired:
                cached.hit_count += 1
                self._stats["hits"] += 1
                self._stats["l1_size"] = len(self._l1)
                # Move to end (LRU)
                self._l1.move_to_end(key)
                logger.debug(f"ResponseCache L1 hit: {query[:50]}")
                return cached.response
            else:
                del self._l1[key]

        # L2 (disk) check
        try:
            conn = sqlite3.connect(str(self._disk_path))
            row = conn.execute(
                "SELECT response, timestamp, ttl_seconds, hit_count FROM cache WHERE query_hash=?",
                (key,),
            ).fetchone()
            conn.close()

            if row:
                response, ts, ttl, hits = row
                if (time.time() - ts) <= ttl:
                    # Promote to L1
                    cached = CachedResponse(
                        query=query, response=response,
                        timestamp=ts, ttl_seconds=ttl, hit_count=hits + 1,
                    )
                    self._l1[key] = cached
                    self._evict_l1_if_needed()
                    self._stats["hits"] += 1
                    return response
        except Exception as e:
            logger.debug(f"ResponseCache L2 get: {e}")

        self._stats["misses"] += 1
        return None

    async def set(self, query: str, response: str, ttl: int = None) -> None:
        """Cache a response."""
        if self._should_bypass(query) or not response:
            return

        key = self._hash_query(query)
        ttl = ttl or self._default_ttl

        cached = CachedResponse(
            query=query, response=response, ttl_seconds=ttl,
        )

        # L1 store
        self._l1[key] = cached
        self._evict_l1_if_needed()

        # L2 store (async, fire-and-forget)
        try:
            conn = sqlite3.connect(str(self._disk_path))
            conn.execute(
                """INSERT OR REPLACE INTO cache
                   (query_hash, query, response, timestamp, ttl_seconds)
                   VALUES (?, ?, ?, ?, ?)""",
                (key, query[:500], response, cached.timestamp, ttl),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"ResponseCache L2 set: {e}")

    def _evict_l1_if_needed(self) -> None:
        """LRU eviction if L1 exceeds max size."""
        while len(self._l1) > self._max_l1:
            self._l1.popitem(last=False)  # Pop oldest

    def flush(self) -> int:
        """Flush all caches. Returns number of entries removed."""
        l1_count = len(self._l1)
        self._l1.clear()

        try:
            conn = sqlite3.connect(str(self._disk_path))
            conn.execute("DELETE FROM cache")
            l2_count = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            conn.commit()
            conn.close()
        except Exception:
            l2_count = 0

        total = l1_count + l2_count
        logger.info(f"ResponseCache flushed: {total} entries")
        return total

    @property
    def stats(self) -> dict:
        return {
            **self._stats,
            "l1_size": len(self._l1),
            "hit_rate": (
                self._stats["hits"] / max(1, self._stats["hits"] + self._stats["misses"])
            ),
        }


# ── Singleton ──

_cache: Optional[ResponseCache] = None
_cache_lock = threading.Lock()


def get_response_cache() -> ResponseCache:
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = ResponseCache()
    return _cache
