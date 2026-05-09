"""Event Bus — decoupled publish/subscribe messaging for the digital lifeform.

Lightweight, in-process event bus with async support.
Serves as the communication backbone across subsystems:
  - memory, learning, reasoning, health, self-awareness, MCP, system events.

Usage:
    from livingtree.infrastructure.event_bus import get_event_bus, subscribe, publish

    bus = get_event_bus()
    bus.subscribe("memory_created", my_handler)
    bus.publish("memory_created", {"key": "value"})
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class EventPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class EventHook:
    """Callback wrapper with priority and metadata."""

    def __init__(
        self,
        handler: Callable,
        priority: EventPriority = EventPriority.NORMAL,
        once: bool = False,
        filter_fn: Callable | None = None,
    ):
        self.handler = handler
        self.priority = priority
        self.once = once
        self.filter_fn = filter_fn
        self.calls = 0

    def __repr__(self):
        return f"EventHook({self.handler.__name__}, priority={self.priority})"


@dataclass
class Event:
    """A typed event envelope carrying data across the bus.

    Attributes:
        event_type: String event type key (e.g. 'memory_created', 'health_alert')
        data: Arbitrary payload dict
        source: Which module/component emitted the event
        timestamp: UTC epoch seconds (filled automatically)
        event_id: Unique event UUID (filled automatically)
        metadata: Extra tags for routing/filtering
    """
    event_type: str
    data: dict | None = None
    source: str = ""
    timestamp: float = 0.0
    event_id: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.event_id:
            self.event_id = uuid.uuid4().hex[:16]

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "data": self.data or {},
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


# ═══ Event Type Constants ═══

EVENTS: dict[str, str] = {
    # Memory events
    "MEMORY_CREATED": "memory_created",
    "MEMORY_UPDATED": "memory_updated",
    "MEMORY_RETRIEVED": "memory_retrieved",
    "MEMORY_DELETED": "memory_deleted",
    # Learning events
    "LEARNING_STARTED": "learning_started",
    "LEARNING_COMPLETED": "learning_completed",
    "LEARNING_FAILED": "learning_failed",
    "TASK_ADDED": "task_added",
    # Reasoning events
    "REASONING_REQUEST": "reasoning_request",
    "REASONING_COMPLETED": "reasoning_completed",
    "REASONING_FAILED": "reasoning_failed",
    # LifeEngine events
    "STAGE_STARTED": "stage_started",
    "STAGE_COMPLETED": "stage_completed",
    "STAGE_FAILED": "stage_failed",
    "CYCLE_COMPLETED": "cycle_completed",
    "CYCLE_FAILED": "cycle_failed",
    "EVOLUTION_TRIGGERED": "evolution_triggered",
    # Health events
    "HEALTH_STATUS_CHANGED": "health_status_changed",
    "HEALTH_ALERT": "health_alert",
    "REPAIR_STARTED": "repair_started",
    "REPAIR_COMPLETED": "repair_completed",
    # Self-awareness events
    "REFLECTION_COMPLETED": "reflection_completed",
    "GOAL_SET": "goal_set",
    "GOAL_UPDATED": "goal_updated",
    "AUTONOMY_CHANGED": "autonomy_changed",
    # MCP events
    "MCP_CONNECTED": "mcp_connected",
    "MCP_DISCONNECTED": "mcp_disconnected",
    "MCP_TOOL_CALLED": "mcp_tool_called",
    "MCP_FALLBACK_USED": "mcp_fallback_used",
    # System events
    "SYSTEM_INITIALIZED": "system_initialized",
    "SYSTEM_SHUTDOWN": "system_shutdown",
    "SUBSYSTEM_STATUS_CHANGED": "subsystem_status_changed",
    # Knowledge events
    "KNOWLEDGE_INGESTED": "knowledge_ingested",
    "KNOWLEDGE_DISCOVERED": "knowledge_discovered",
    "KNOWLEDGE_LINTED": "knowledge_linted",
    "DOCUMENT_VALIDATED": "document_validated",
    # Chat events
    "CHAT_CLEAR": "chat_clear",
    "CHAT_MESSAGE": "chat_message",
    "FEEDBACK_RECORDED": "feedback_recorded",
    # Training events
    "TRAINING_STARTED": "training_started",
    "TRAINING_COMPLETED": "training_completed",
    "TERM_ADDED": "term_added",
}


class EventBus:
    """In-process publish/subscribe event bus with async support.

    Supports:
      - Typed event routing (string keys)
      - Priority-ordered handler dispatch (LOW → CRITICAL)
      - Sync + async handler support
      - One-shot (once) subscriptions
      - Optional event history
      - Event filtering via filter_fn
    """

    def __init__(self, async_enabled: bool = True):
        self._subscribers: dict[str, list[EventHook]] = defaultdict(list)
        self._async_enabled = async_enabled
        self._event_history: list[Event] = []
        self._max_history = 1000

    def subscribe(
        self,
        event_type: str,
        handler: Callable,
        priority: EventPriority = EventPriority.NORMAL,
        once: bool = False,
    ) -> EventHook:
        """Subscribe a handler to an event type.

        Handlers are called with a single Event argument.
        For async handlers, they are awaited.
        """
        hook = EventHook(handler=handler, priority=priority, once=once)
        self._subscribers[event_type].append(hook)
        # Maintain priority order (higher priority first)
        self._subscribers[event_type].sort(key=lambda h: -h.priority.value)
        return hook

    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """Remove a subscription."""
        hooks = self._subscribers.get(event_type, [])
        before = len(hooks)
        self._subscribers[event_type] = [h for h in hooks if h.handler is not handler]
        return len(self._subscribers[event_type]) < before

    def publish(self, event_type: str, data: dict | None = None) -> None:
        """Synchronously publish an event to all subscribers.

        Async handlers are scheduled via asyncio.ensure_future
        (no blocking). Sync handlers are called inline.
        """
        event = Event(event_type=event_type, data=data or {})
        self._record(event)
        hooks = list(self._subscribers.get(event_type, []))
        removals: list[EventHook] = []

        for hook in hooks:
            if hook.filter_fn and not hook.filter_fn(event.to_dict()):
                continue
            try:
                result = hook.handler(event)
                if asyncio.iscoroutine(result):
                    if self._async_enabled:
                        asyncio.ensure_future(self._safe_await(result, event, hook))
                    else:
                        raise RuntimeError(
                            f"Async handler registered for '{event_type}' but async_enabled=False"
                        )
                hook.calls += 1
            except Exception:
                pass
            if hook.once:
                removals.append(hook)

        for hook in removals:
            if hook in self._subscribers[event_type]:
                self._subscribers[event_type].remove(hook)

    def publish_simple(self, event_type: str, source: str = "", data: dict | None = None) -> None:
        """Publish with explicit source field."""
        event = Event(event_type=event_type, source=source, data=data or {})
        self._record(event)
        hooks = list(self._subscribers.get(event_type, []))
        removals: list[EventHook] = []

        for hook in hooks:
            if hook.filter_fn and not hook.filter_fn(event.to_dict()):
                continue
            try:
                result = hook.handler(event)
                if asyncio.iscoroutine(result):
                    if self._async_enabled:
                        asyncio.ensure_future(self._safe_await(result, event, hook))
                hook.calls += 1
            except Exception:
                pass
            if hook.once:
                removals.append(hook)

        for hook in removals:
            if hook in self._subscribers[event_type]:
                self._subscribers[event_type].remove(hook)

    async def _safe_await(self, coro, event: Event, hook: EventHook) -> None:
        try:
            await coro
            hook.calls += 1
        except Exception:
            pass

    def get_history(self, event_type: str | None = None, limit: int = 100) -> list[Event]:
        history = self._event_history
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        return history[-limit:]

    def _record(self, event: Event) -> None:
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

    def stats(self) -> dict:
        return {
            "event_types": len(self._subscribers),
            "total_subscribers": sum(len(h) for h in self._subscribers.values()),
            "history_size": len(self._event_history),
        }


# ═══ Singleton ═══

_bus_instance: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = EventBus(async_enabled=True)
    return _bus_instance


def subscribe(event_type: str, handler: Callable, priority: EventPriority = EventPriority.NORMAL) -> EventHook:
    return get_event_bus().subscribe(event_type, handler, priority)


def publish(event_type: str, source: str = "", data: dict | None = None) -> None:
    get_event_bus().publish_simple(event_type, source=source, data=data)


__all__ = [
    "EventBus", "Event", "EventHook", "EventPriority", "EVENTS",
    "get_event_bus", "subscribe", "publish",
]
