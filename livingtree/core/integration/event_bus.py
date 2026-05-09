"""Core integration event bus shim — re-exports from infrastructure."""

from livingtree.infrastructure.event_bus import (
    EventBus, Event, EventHook, EventPriority, EVENTS,
    get_event_bus, subscribe, publish,
)

from enum import Enum


class EventType(str, Enum):
    MEMORY_CREATED = "memory_created"
    MEMORY_UPDATED = "memory_updated"
    MEMORY_DELETED = "memory_retrieved"
    MEMORY_RETRIEVED = "memory_retrieved"
    LEARNING_STARTED = "learning_started"
    LEARNING_COMPLETED = "learning_completed"
    LEARNING_FAILED = "learning_failed"
    TASK_ADDED = "task_added"
    REASONING_REQUEST = "reasoning_request"
    REASONING_COMPLETED = "reasoning_completed"
    REASONING_FAILED = "reasoning_failed"
    HEALTH_STATUS_CHANGED = "health_status_changed"
    HEALTH_ALERT = "health_alert"
    REPAIR_STARTED = "repair_started"
    REPAIR_COMPLETED = "repair_completed"
    REFLECTION_COMPLETED = "reflection_completed"
    GOAL_SET = "goal_set"
    GOAL_UPDATED = "goal_updated"
    AUTONOMY_CHANGED = "autonomy_changed"
    MCP_CONNECTED = "mcp_connected"
    MCP_DISCONNECTED = "mcp_disconnected"
    MCP_TOOL_CALLED = "mcp_tool_called"
    MCP_FALLBACK_USED = "mcp_fallback_used"
    SYSTEM_INITIALIZED = "system_initialized"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SUBSYSTEM_STATUS_CHANGED = "subsystem_status_changed"


__all__ = [
    "EventBus", "Event", "EventHook", "EventPriority", "EVENTS",
    "EventType", "get_event_bus", "subscribe", "publish",
]
