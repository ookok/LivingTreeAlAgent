"""Stream Session Cache — supports session resume with offset tracking.

When a streaming connection drops, the client can reconnect with:
  X-Session-ID: session_abc123
  X-Received-Length: 1500

The server resumes streaming from offset 1500.
Sessions expire after 5 minutes of inactivity.
"""

import time
from typing import Optional

from loguru import logger


class StreamSessionCache:
    """In-memory cache for streaming sessions with TTL."""

    def __init__(self, ttl_seconds: int = 300):
        self._cache: dict[str, dict] = {}
        self._ttl = ttl_seconds

    def create(self, session_id: str, query: str) -> str:
        """Create a new streaming session."""
        self._cache[session_id] = {
            "query": query,
            "full_text": "",
            "created_at": time.time(),
            "last_updated": time.time(),
            "completed": False,
        }
        return session_id

    def append(self, session_id: str, text: str) -> None:
        """Append text to a streaming session."""
        session = self._cache.get(session_id)
        if session:
            session["full_text"] += text
            session["last_updated"] = time.time()

    def complete(self, session_id: str) -> None:
        """Mark session as complete."""
        session = self._cache.get(session_id)
        if session:
            session["completed"] = True
            session["last_updated"] = time.time()

    def get(self, session_id: str) -> Optional[dict]:
        """Get session if it exists and hasn't expired."""
        session = self._cache.get(session_id)
        if not session:
            return None
        if time.time() - session["last_updated"] > self._ttl:
            self._cache.pop(session_id, None)
            return None
        return session

    def cleanup(self) -> int:
        """Remove expired sessions. Returns count removed."""
        now = time.time()
        expired = [
            sid for sid, s in self._cache.items()
            if now - s["last_updated"] > self._ttl
        ]
        for sid in expired:
            self._cache.pop(sid, None)
        if expired:
            logger.debug(f"StreamSessionCache: cleaned {len(expired)} expired sessions")
        return len(expired)


# ── Singleton ──

_cache: Optional[StreamSessionCache] = None


def get_session_cache() -> StreamSessionCache:
    global _cache
    if _cache is None:
        _cache = StreamSessionCache()
    return _cache
