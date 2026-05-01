"""
事件总线 - 模块间通信
"""

import asyncio
import logging
from typing import Dict, List, Callable, Any
from dataclasses import dataclass
from enum import Enum
from threading import Lock
import json


logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型"""
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    MEMORY_UPDATE = "memory.update"
    TASK_UPDATE = "task.update"
    CHAT_MESSAGE = "chat.message"
    UI_NOTIFICATION = "ui.notification"
    FAULT_DETECTED = "fault.detected"
    RECOVERY_DONE = "recovery.done"
    LEARNING_COMPLETE = "learning.complete"
    REASONING_RESULT = "reasoning.result"


@dataclass
class Event:
    """事件对象"""
    event_type: EventType
    data: Dict[str, Any]
    source: str = "system"
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            import time
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict:
        return {
            "type": self.event_type.value if isinstance(self.event_type, Enum) else self.event_type,
            "data": self.data,
            "source": self.source,
            "timestamp": self.timestamp
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class EventBus:
    """事件总线"""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = Lock()
        self._event_queue = asyncio.Queue()
        self._running = False
        
    def subscribe(self, event_type: str, callback: Callable):
        """订阅事件"""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to {event_type}")
    
    def unsubscribe(self, event_type: str, callback: Callable):
        """取消订阅"""
        with self._lock:
            if event_type in self._subscribers:
                if callback in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(callback)
        logger.debug(f"Unsubscribed from {event_type}")
    
    def publish(self, event: Event):
        """发布事件"""
        event_str = event.event_type.value if isinstance(event.event_type, Enum) else event.event_type
        
        callbacks = []
        with self._lock:
            if event_str in self._subscribers:
                callbacks = list(self._subscribers[event_str])
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event))
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        logger.debug(f"Published event: {event_str}")
    
    def emit(self, event_type: str, data: Dict[str, Any], source: str = "system"):
        """快捷发送事件"""
        event = Event(
            event_type=event_type,
            data=data,
            source=source
        )
        self.publish(event)
