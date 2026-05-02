"""
LivingTree 事件总线 (Event Bus)
===============================

支持模块间解耦通信，同步/异步事件处理。
新增：Hook 机制、事件历史记录、优先级队列。
"""

from typing import Dict, List, Callable, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock, Thread
from queue import PriorityQueue, Queue
from enum import IntEnum


class EventPriority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass(order=True)
class _PrioritizedEvent:
    priority: int
    event: Any = field(compare=False)
    sequence: int = field(compare=False)


@dataclass
class Event:
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = ""
    priority: EventPriority = EventPriority.NORMAL

    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"{self.event_type}_{self.timestamp.timestamp()}"


class EventHook:
    """
    Hook 机制 — 在事件处理前后插入自定义逻辑

    用法:
        bus = EventBus()
        bus.add_hook("before_publish", my_pre_hook)
        bus.add_hook("after_publish", my_post_hook)
    """

    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = {
            "before_publish": [],
            "after_publish": [],
            "before_subscribe": [],
            "after_subscribe": [],
            "on_error": [],
        }

    def add(self, hook_point: str, callback: Callable):
        if hook_point in self._hooks:
            self._hooks[hook_point].append(callback)

    def remove(self, hook_point: str, callback: Callable):
        if hook_point in self._hooks:
            self._hooks[hook_point] = [h for h in self._hooks[hook_point] if h != callback]

    def trigger(self, hook_point: str, *args, **kwargs):
        for callback in self._hooks.get(hook_point, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                print(f"[EventHook] Hook 执行失败 ({hook_point}): {e}")


class EventBus:
    def __init__(self, async_enabled: bool = True, max_history: int = 500):
        self._handlers: Dict[str, List[Callable]] = {}
        self._async_handlers: Dict[str, List[Callable]] = {}
        self._lock = Lock()
        self._async_enabled = async_enabled
        self._event_queue = PriorityQueue(maxsize=2000)
        self._sequence = 0

        self._history: List[Event] = []
        self._max_history = max_history

        self.hook = EventHook()
        self._subscribers_by_type: Dict[str, Set[str]] = {}

        if self._async_enabled:
            self._start_async_worker()

    def _start_async_worker(self):
        def worker():
            while True:
                try:
                    prioritized = self._event_queue.get(timeout=1)
                    self._process_async_event(prioritized.event)
                    self._event_queue.task_done()
                except Exception:
                    pass

        self._worker_thread = Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def subscribe(self, event_type: str, handler: Callable, async_mode: bool = False):
        self.hook.trigger("before_subscribe", event_type=event_type, handler=handler)

        target = self._async_handlers if async_mode else self._handlers
        if event_type not in target:
            target[event_type] = []
        target[event_type].append(handler)

        self.hook.trigger("after_subscribe", event_type=event_type, handler=handler)

    def unsubscribe(self, event_type: str, handler: Callable):
        for target in (self._handlers, self._async_handlers):
            if event_type in target and handler in target[event_type]:
                target[event_type].remove(handler)

    def publish(self, event_type: str, data: Optional[Dict[str, Any]] = None,
                priority: EventPriority = EventPriority.NORMAL):
        event = Event(event_type=event_type, data=data or {}, priority=priority)

        self._add_to_history(event)
        self.hook.trigger("before_publish", event=event)

        # 同步处理
        for handler in self._handlers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                self.hook.trigger("on_error", event=event, error=e)
                print(f"[EventBus] 事件处理失败 ({event_type}): {e}")

        # 异步处理
        if self._async_enabled and event_type in self._async_handlers:
            if not self._event_queue.full():
                self._sequence += 1
                self._event_queue.put(_PrioritizedEvent(
                    priority=event.priority.value,
                    event=event,
                    sequence=self._sequence
                ))

        self.hook.trigger("after_publish", event=event)

    def _process_async_event(self, event: Event):
        for handler in self._async_handlers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as e:
                self.hook.trigger("on_error", event=event, error=e)
                print(f"[EventBus] 异步事件处理失败 ({event.event_type}): {e}")

    def _add_to_history(self, event: Event):
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_history(self, event_type: Optional[str] = None, limit: int = 100) -> List[Event]:
        if event_type:
            return [e for e in self._history if e.event_type == event_type][-limit:]
        return self._history[-limit:]

    def get_subscribed_events(self) -> List[str]:
        return list(set(list(self._handlers.keys()) + list(self._async_handlers.keys())))

    def get_handler_count(self, event_type: str) -> int:
        return len(self._handlers.get(event_type, [])) + len(self._async_handlers.get(event_type, []))

    def clear(self):
        self._handlers.clear()
        self._async_handlers.clear()
        self._history.clear()


# ── 事件类型常量 ────────────────────────────────────────────────────

EVENTS = {
    "SYSTEM_INITIALIZED": "livingtree.system.initialized",
    "SYSTEM_SHUTDOWN": "livingtree.system.shutdown",
    "SYSTEM_ERROR": "livingtree.system.error",
    "CONFIG_UPDATED": "livingtree.config.updated",

    "REQUEST_RECEIVED": "livingtree.agent.request_received",
    "REQUEST_COMPLETED": "livingtree.agent.request_completed",
    "INTENT_PARSED": "livingtree.agent.intent_parsed",
    "CONTEXT_ASSEMBLED": "livingtree.agent.context_assembled",
    "TASK_PLANNED": "livingtree.agent.task_planned",
    "MODEL_DISPATCHED": "livingtree.agent.model_dispatched",
    "EXECUTION_STARTED": "livingtree.agent.execution_started",
    "EXECUTION_COMPLETED": "livingtree.agent.execution_completed",
    "TOOL_EXECUTED": "livingtree.agent.tool_executed",
    "REFLECTION_ARCHIVED": "livingtree.agent.reflection_archived",

    "KNOWLEDGE_INGESTED": "livingtree.memory.knowledge_ingested",
    "KNOWLEDGE_QUERIED": "livingtree.memory.knowledge_queried",
    "MEMORY_ARCHIVED": "livingtree.memory.archived",
    "WIKI_PAGE_CREATED": "livingtree.memory.wiki_page_created",
    "WIKI_PAGE_UPDATED": "livingtree.memory.wiki_page_updated",

    "SKILL_LOADED": "livingtree.skill.loaded",
    "SKILL_MATCHED": "livingtree.skill.matched",
    "SKILL_UPDATED": "livingtree.skill.updated",

    "EVOLUTION_REFLECTION": "livingtree.evolution.reflection",
    "EVOLUTION_IMPROVEMENT": "livingtree.evolution.improvement",
    "EVOLUTION_ADOPTED": "livingtree.evolution.adopted",

    "PLUGIN_LOADED": "livingtree.plugin.loaded",
    "PLUGIN_UNLOADED": "livingtree.plugin.unloaded",
    "PLUGIN_ERROR": "livingtree.plugin.error",

    "HEALTH_CHECK": "livingtree.monitor.health_check",
    "METRICS_SNAPSHOT": "livingtree.monitor.metrics_snapshot",
}


# ── 全局单例 ────────────────────────────────────────────────────────

_global_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus


def subscribe(event_type: str, handler: Callable, async_mode: bool = False):
    get_event_bus().subscribe(event_type, handler, async_mode)


def publish(event_type: str, data: Optional[Dict[str, Any]] = None,
            priority: EventPriority = EventPriority.NORMAL):
    get_event_bus().publish(event_type, data, priority)


__all__ = [
    "EventBus",
    "Event",
    "EventHook",
    "EventPriority",
    "EVENTS",
    "get_event_bus",
    "subscribe",
    "publish",
]
