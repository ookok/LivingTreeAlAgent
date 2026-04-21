"""
统一事件总线 - Event Bus

实现插件间的松耦合通信机制

设计理念：
1. 发布-订阅模式：插件间通过事件进行通信
2. 主题过滤：支持通配符订阅
3. 优先级：支持事件优先级
4. 异步处理：支持异步事件处理
"""

import uuid
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Set
from threading import Lock
from collections import defaultdict
import logging


class EventPriority(Enum):
    """事件优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    """
    事件对象

    Attributes:
        type: 事件类型（如 "file_opened", "user_clicked"）
        data: 事件数据
        source: 事件来源插件ID
        target: 目标插件ID（可选，用于直接消息）
        priority: 事件优先级
        timestamp: 事件时间戳
        id: 事件唯一ID
        propagation: 事件传播深度（用于防止无限循环）
    """
    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""  # 源插件ID
    target: str = ""  # 目标插件ID（空表示广播）
    priority: EventPriority = EventPriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    propagation: int = 10  # 最大传播深度

    def __post_init__(self):
        # 确保type不为空
        if not self.type:
            raise ValueError("Event type cannot be empty")

    def clone(self) -> 'Event':
        """创建事件的深拷贝"""
        return Event(
            type=self.type,
            data=self.data.copy(),
            source=self.source,
            target=self.target,
            priority=self.priority,
            timestamp=self.timestamp,
            propagation=self.propagation,
        )

    def with_data(self, **kwargs) -> 'Event':
        """链式API：添加数据"""
        new_event = self.clone()
        new_event.data.update(kwargs)
        return new_event


class Subscriber:
    """订阅者"""

    def __init__(
        self,
        plugin_id: str,
        callback: Callable[['Event'], None],
        priority: EventPriority = EventPriority.NORMAL,
        is_recursive: bool = False,  # 是否接收自己发布的事件
    ):
        self.id = str(uuid.uuid4())
        self.plugin_id = plugin_id
        self.callback = callback
        self.priority = priority
        self.is_recursive = is_recursive
        self.is_active = True

    def __repr__(self):
        return f"Subscriber(plugin={self.plugin_id}, priority={self.priority.name})"


class EventBus:
    """
    统一事件总线

    提供插件间的异步通信机制

    使用示例：
        # 订阅事件
        def on_file_opened(event):
            print(f"File opened: {event.data['path']}")

        event_bus.subscribe("file_opened", "plugin_a", on_file_opened)

        # 发布事件
        event = Event(type="file_opened", data={"path": "/tmp/test.txt"}, source="plugin_a")
        event_bus.publish(event)
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Subscriber]] = defaultdict(list)
        self._wildcard_subscribers: List[Subscriber] = []
        self._pending_events: List[Event] = []
        self._processing = False
        self._lock = Lock()
        self._logger = logging.getLogger("EventBus")
        self._event_history: List[Event] = []
        self._max_history = 1000

    def subscribe(
        self,
        event_type: str,
        plugin_id: str,
        callback: Callable[['Event'], None],
        priority: EventPriority = EventPriority.NORMAL,
        is_recursive: bool = False,
    ) -> str:
        """
        订阅事件

        Args:
            event_type: 事件类型（支持通配符如 "file_*"）
            plugin_id: 订阅者插件ID
            callback: 事件处理回调
            priority: 优先级
            is_recursive: 是否接收自己发布的事件

        Returns:
            订阅者ID
        """
        subscriber = Subscriber(
            plugin_id=plugin_id,
            callback=callback,
            priority=priority,
            is_recursive=is_recursive,
        )

        with self._lock:
            if '*' in event_type or '?' in event_type:
                # 通配符订阅
                self._wildcard_subscribers.append(subscriber)
            else:
                # 精确订阅
                self._subscribers[event_type].append(subscriber)
                # 按优先级排序
                self._subscribers[event_type].sort(key=lambda s: s.priority.value, reverse=True)

        self._logger.debug(f"Subscribed {plugin_id} to {event_type}")
        return subscriber.id

    def unsubscribe(self, event_type: str, plugin_id: str) -> bool:
        """
        取消订阅

        Args:
            event_type: 事件类型
            plugin_id: 插件ID

        Returns:
            是否成功取消
        """
        with self._lock:
            if '*' in event_type or '?' in event_type:
                before = len(self._wildcard_subscribers)
                self._wildcard_subscribers = [
                    s for s in self._wildcard_subscribers
                    if not (s.plugin_id == plugin_id and self._matches_wildcard(event_type, s.plugin_id))
                ]
                return len(self._wildcard_subscribers) < before
            else:
                if event_type in self._subscribers:
                    before = len(self._subscribers[event_type])
                    self._subscribers[event_type] = [
                        s for s in self._subscribers[event_type]
                        if s.plugin_id != plugin_id
                    ]
                    return len(self._subscribers[event_type]) < before
        return False

    def unsubscribe_by_id(self, subscriber_id: str) -> bool:
        """通过订阅者ID取消订阅"""
        with self._lock:
            # 精确订阅
            for event_type, subscribers in self._subscribers.items():
                for i, s in enumerate(subscribers):
                    if s.id == subscriber_id:
                        subscribers.pop(i)
                        return True
            # 通配符订阅
            for i, s in enumerate(self._wildcard_subscribers):
                if s.id == subscriber_id:
                    self._wildcard_subscribers.pop(i)
                    return True
        return False

    def publish(self, event: Event) -> int:
        """
        发布事件

        Args:
            event: 事件对象

        Returns:
            接收事件的订阅者数量
        """
        if event.propagation <= 0:
            self._logger.warning(f"Event propagation limit reached: {event.type}")
            return 0

        with self._lock:
            # 记录历史
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)

        self._logger.debug(f"Publishing event: {event.type} from {event.source}")

        received = 0
        processed_targets: Set[str] = set()

        with self._lock:
            # 处理精确匹配的订阅者
            if event.type in self._subscribers:
                for subscriber in self._subscribers[event.type]:
                    if not subscriber.is_active:
                        continue
                    if subscriber.plugin_id == event.source and not subscriber.is_recursive:
                        continue
                    if subscriber.plugin_id in processed_targets:
                        continue

                    try:
                        subscriber.callback(event)
                        received += 1
                        processed_targets.add(subscriber.plugin_id)
                    except Exception as e:
                        self._logger.error(f"Event handler error: {e}")

            # 处理通配符匹配的订阅者
            for subscriber in self._wildcard_subscribers:
                if not subscriber.is_active:
                    continue
                if subscriber.plugin_id == event.source and not subscriber.is_recursive:
                    continue
                if subscriber.plugin_id in processed_targets:
                    continue

                # 检查是否匹配通配符模式
                if self._matches_wildcard(event.type, subscriber.plugin_id):
                    try:
                        subscriber.callback(event)
                        received += 1
                        processed_targets.add(subscriber.plugin_id)
                    except Exception as e:
                        self._logger.error(f"Wildcard event handler error: {e}")

        return received

    def publish_sync(self, event: Event) -> int:
        """同步发布事件（立即处理）"""
        return self.publish(event)

    def publish_async(self, event: Event) -> None:
        """异步发布事件（放入队列）"""
        with self._lock:
            self._pending_events.append(event)

    def process_pending(self) -> int:
        """处理待处理事件"""
        with self._lock:
            events = self._pending_events.copy()
            self._pending_events.clear()

        total = 0
        for event in events:
            total += self.publish(event)
        return total

    def _matches_wildcard(self, event_type: str, subscriber_id: str) -> bool:
        """
        检查通配符匹配（简化实现，实际应该用正则或fnmatch）

        支持的通配符：
        - * 匹配任意字符
        - ? 匹配单个字符
        """
        import fnmatch
        return fnmatch.fnmatch(subscriber_id, event_type)

    def get_subscribers(self, event_type: str) -> List[Subscriber]:
        """获取指定事件类型的订阅者列表"""
        with self._lock:
            result = []
            if event_type in self._subscribers:
                result.extend(self._subscribers[event_type])
            result.extend([s for s in self._wildcard_subscribers if s.is_active])
            return result

    def get_history(self, event_type: Optional[str] = None, limit: int = 100) -> List[Event]:
        """
        获取事件历史

        Args:
            event_type: 过滤事件类型
            limit: 返回数量限制

        Returns:
            事件列表
        """
        with self._lock:
            history = self._event_history[-limit:] if limit > 0 else self._event_history
            if event_type:
                history = [e for e in history if e.type == event_type]
            return history

    def clear_history(self) -> None:
        """清空事件历史"""
        with self._lock:
            self._event_history.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取事件总线统计信息"""
        with self._lock:
            total_subscribers = sum(len(s) for s in self._subscribers.values())
            total_subscribers += len(self._wildcard_subscribers)

            event_types = list(self._subscribers.keys())
            event_counts = {e.type: 0 for e in self._event_history}
            for e in self._event_history:
                event_counts[e.type] += 1

            return {
                "total_subscribers": total_subscribers,
                "event_types_count": len(event_types),
                "event_types": event_types,
                "history_size": len(self._event_history),
                "pending_events": len(self._pending_events),
                "event_counts": event_counts,
            }


# 全局单例
_event_bus_instance: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取事件总线单例"""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance


def Event(type: str, **kwargs) -> Event:
    """快捷创建事件"""
    return Event(type=type, **kwargs)
