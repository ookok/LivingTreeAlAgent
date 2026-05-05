"""ActivityFeed — unified real-time event stream for all agent actions.

    Inspired by Mission Control's activity feed. Features:
    1. Event types: election, tool_call, cache, eval, synthesizer, modify, consolidate, error
    2. Timestamped, filterable by agent/type/severity
    3. In-memory ring buffer (last 500 events) + persistent append-only log
    4. Real-time SSE push for UI (optional)
    5. Automatic: every action auto-logged via hub hooks

    Usage:
        feed = get_activity_feed()
        feed.log("election", "nvidia-reasoning", "elected: score=0.87 cache=0.92")
        events = feed.query(limit=20, type_filter="tool_call")
        feed.subscribe(callback)  # real-time updates
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from loguru import logger

FEED_DIR = Path(".livingtree/activity")
FEED_LOG = FEED_DIR / "activity.jsonl"
MAX_BUFFER = 500


class EventType(str, Enum):
    ELECTION = "election"
    TOOL_CALL = "tool_call"
    CACHE = "cache"
    EVAL = "eval"
    SYNTHESIZE = "synthesize"
    MODIFY = "modify"
    CONSOLIDATE = "consolidate"
    ERROR = "error"
    PROVIDER = "provider"
    NETWORK = "network"
    SYSTEM = "system"


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    SUCCESS = "success"


@dataclass
class ActivityEvent:
    type: str
    agent: str
    message: str
    timestamp: float = 0.0
    severity: str = "info"
    metadata: dict = field(default_factory=dict)


class ActivityFeed:
    """Unified real-time event stream."""

    def __init__(self):
        FEED_DIR.mkdir(parents=True, exist_ok=True)
        self._buffer: deque[ActivityEvent] = deque(maxlen=MAX_BUFFER)
        self._subscribers: list[Callable] = []
        self._total_events: int = 0
        self._load_recent()

    def log(
        self,
        event_type: str,
        agent: str,
        message: str,
        severity: str = "info",
        metadata: dict | None = None,
    ) -> ActivityEvent:
        """Log an activity event. Persists to append-only log.

        Args:
            event_type: ELECTION, TOOL_CALL, CACHE, EVAL, etc.
            agent: Agent/tool/provider name
            message: Human-readable description
            severity: info, warn, error, success
            metadata: Extra data dict
        """
        event = ActivityEvent(
            type=event_type,
            agent=agent,
            message=message,
            timestamp=time.time(),
            severity=severity,
            metadata=metadata or {},
        )
        self._buffer.append(event)
        self._total_events += 1

        # Append to JSONL log
        try:
            with open(FEED_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "type": event.type, "agent": event.agent,
                    "message": event.message, "timestamp": event.timestamp,
                    "severity": event.severity, "metadata": event.metadata,
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass

        # Notify subscribers
        for cb in self._subscribers[:10]:  # cap at 10
            try:
                cb(event)
            except Exception:
                pass

        return event

    # ── Convenience loggers ──

    def election(self, provider: str, score: float, reason: str = ""):
        self.log("election", provider,
                 f"Elected {provider}: score={score:.2f}" + (f" {reason}" if reason else ""),
                 severity="info", metadata={"score": score})

    def tool_call(self, tool: str, success: bool, latency_ms: float = 0, details: str = ""):
        self.log("tool_call", tool,
                 f"{'✓' if success else '✗'} {tool}" + (f" ({latency_ms:.0f}ms)" if latency_ms else ""),
                 severity="success" if success else "error",
                 metadata={"success": success, "latency_ms": latency_ms})

    def cache_hit(self, provider: str, hit_rate: float, savings: float):
        self.log("cache", provider,
                 f"Cache: {hit_rate:.0%} hit | saved ¥{savings:.4f}",
                 severity="success", metadata={"hit_rate": hit_rate, "savings": savings})

    def synthesize(self, tool: str, success: bool, version: int = 1):
        self.log("synthesize", tool,
                 f"{'✓' if success else '✗'} Tool synthesized: {tool} v{version}",
                 severity="success" if success else "warn")

    def modify(self, files: list[str], success: bool):
        self.log("modify", "self",
                 f"{'✓' if success else '✗'} Modified {len(files)} files: {', '.join(files[:3])}",
                 severity="success" if success else "error",
                 metadata={"files": files})

    def consolidate(self, topic: str, count: int):
        self.log("consolidate", "idle",
                 f"Consolidated {count} knowledge entries: {topic[:60]}",
                 severity="info")

    def error(self, agent: str, error_msg: str, metadata: dict | None = None):
        self.log("error", agent, error_msg[:200], severity="error", metadata=metadata)

    # ── Queries ──

    def query(
        self,
        limit: int = 20,
        event_type: str = "",
        agent: str = "",
        severity: str = "",
    ) -> list[ActivityEvent]:
        """Query recent events with optional filters."""
        results = list(self._buffer)

        if event_type:
            results = [e for e in results if e.type == event_type]
        if agent:
            results = [e for e in results if agent.lower() in e.agent.lower()]
        if severity:
            results = [e for e in results if e.severity == severity]

        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[-limit:]

    def subscribe(self, callback: Callable[[ActivityEvent], None]):
        """Subscribe to real-time events."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def stats(self) -> dict[str, Any]:
        """Aggregate statistics."""
        by_type = {}
        by_severity = {}
        recent = list(self._buffer)
        for e in recent[-100:]:
            by_type[e.type] = by_type.get(e.type, 0) + 1
            by_severity[e.severity] = by_severity.get(e.severity, 0) + 1

        errors = [e for e in recent[-50:] if e.severity == "error"]

        return {
            "total_events": self._total_events,
            "buffer_size": len(recent),
            "by_type": by_type,
            "by_severity": by_severity,
            "recent_errors": [
                {"agent": e.agent, "message": e.message[:100], "time": e.timestamp}
                for e in errors[-5:]
            ],
        }

    def summary_24h(self) -> str:
        """Human-readable 24h summary."""
        cutoff = time.time() - 86400
        recent = [e for e in self._buffer if e.timestamp > cutoff]
        if not recent:
            return "No activity in last 24h"

        errors = [e for e in recent if e.severity == "error"]
        elections = [e for e in recent if e.type == "election"]
        tools = [e for e in recent if e.type == "tool_call"]
        synth = [e for e in recent if e.type == "synthesize"]

        return (
            f"Activity: {len(recent)} events | "
            f"{len(elections)} elections | {len(tools)} tool calls | "
            f"{len(synth)} syntheses | {len(errors)} errors"
        )

    def _load_recent(self):
        """Load last N events from persistent log."""
        if not FEED_LOG.exists():
            return
        try:
            lines = FEED_LOG.read_text(encoding="utf-8").strip().split("\n")[-MAX_BUFFER:]
            for line in lines:
                if not line.strip():
                    continue
                d = json.loads(line)
                self._buffer.append(ActivityEvent(
                    type=d.get("type", ""),
                    agent=d.get("agent", ""),
                    message=d.get("message", ""),
                    timestamp=d.get("timestamp", 0),
                    severity=d.get("severity", "info"),
                    metadata=d.get("metadata", {}),
                ))
                self._total_events += 1
        except Exception:
            pass


def get_activity_feed() -> ActivityFeed:
    global _feed
    if _feed is None:
        _feed = ActivityFeed()
    return _feed


_feed: ActivityFeed | None = None
