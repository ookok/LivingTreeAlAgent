"""
事件总线 - Event Bus

功能：
1. 发布/订阅模式
2. 事件路由与分发
3. 事件持久化
4. 事件追溯

支持的事件类型：
- 记忆事件：记忆创建/更新/删除
- 学习事件：学习任务开始/完成/失败
- 推理事件：推理请求/结果/错误
- 健康事件：健康状态变化/告警
- 自我意识事件：反思/目标/自主级别变化
- MCP事件：服务连接/断开/调用
"""

import logging
import time
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型"""
    # 记忆事件
    MEMORY_CREATED = "memory_created"
    MEMORY_UPDATED = "memory_updated"
    MEMORY_DELETED = "memory_retrieved"
    
    # 学习事件
    LEARNING_STARTED = "learning_started"
    LEARNING_COMPLETED = "learning_completed"
    LEARNING_FAILED = "learning_failed"
    TASK_ADDED = "task_added"
    
    # 推理事件
    REASONING_REQUEST = "reasoning_request"
    REASONING_COMPLETED = "reasoning_completed"
    REASONING_FAILED = "reasoning_failed"
    
    # 健康事件
    HEALTH_STATUS_CHANGED = "health_status_changed"
    HEALTH_ALERT = "health_alert"
    REPAIR_STARTED = "repair_started"
    REPAIR_COMPLETED = "repair_completed"
    
    # 自我意识事件
    REFLECTION_COMPLETED = "reflection_completed"
    GOAL_SET = "goal_set"
    GOAL_UPDATED = "goal_updated"
    AUTONOMY_CHANGED = "autonomy_changed"
    
    # MCP事件
    MCP_CONNECTED = "mcp_connected"
    MCP_DISCONNECTED = "mcp_disconnected"
    MCP_TOOL_CALLED = "mcp_tool_called"
    MCP_FALLBACK_USED = "mcp_fallback_used"
    
    # 系统事件
    SYSTEM_INITIALIZED = "system_initialized"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SUBSYSTEM_STATUS_CHANGED = "subsystem_status_changed"


@dataclass
class Event:
    """事件封装"""
    event_type: EventType
    source: str
    data: Dict = field(default_factory=dict)
    timestamp: float = None
    event_id: str = None
    metadata: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.event_id is None:
            self.event_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'source': self.source,
            'data': self.data,
            'timestamp': self.timestamp,
            'metadata': self.metadata
        }


class EventBus:
    """
    事件总线 - 实现发布/订阅模式
    
    核心功能：
    1. 事件发布
    2. 事件订阅/取消订阅
    3. 事件路由
    4. 事件持久化（可选）
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
        
        # 预注册内置订阅者
        self._register_builtin_subscribers()
    
    def _register_builtin_subscribers(self):
        """注册内置订阅者"""
        self.subscribe(EventType.MEMORY_CREATED, self._on_memory_created)
        self.subscribe(EventType.LEARNING_COMPLETED, self._on_learning_completed)
        self.subscribe(EventType.REASONING_COMPLETED, self._on_reasoning_completed)
        self.subscribe(EventType.REFLECTION_COMPLETED, self._on_reflection_completed)
        self.subscribe(EventType.HEALTH_ALERT, self._on_health_alert)
        self.subscribe(EventType.MCP_DISCONNECTED, self._on_mcp_disconnected)
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """
        订阅事件
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        key = event_type.value
        if key not in self._subscribers:
            self._subscribers[key] = []
        
        if handler not in self._subscribers[key]:
            self._subscribers[key].append(handler)
            logger.debug(f"订阅事件: {event_type.value}")
    
    def unsubscribe(self, event_type: EventType, handler: Callable):
        """
        取消订阅事件
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        key = event_type.value
        if key in self._subscribers and handler in self._subscribers[key]:
            self._subscribers[key].remove(handler)
            logger.debug(f"取消订阅事件: {event_type.value}")
    
    def publish(self, event: Event):
        """
        发布事件
        
        Args:
            event: 事件对象
        """
        logger.debug(f"发布事件: {event.event_type.value} from {event.source}")
        
        # 记录历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        # 分发事件
        key = event.event_type.value
        if key in self._subscribers:
            for handler in self._subscribers[key]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"事件处理失败 {event.event_type.value}: {e}")
    
    def publish_simple(self, event_type: EventType, source: str, data: Dict = None):
        """
        简化发布事件
        
        Args:
            event_type: 事件类型
            source: 事件源
            data: 事件数据
        """
        event = Event(
            event_type=event_type,
            source=source,
            data=data or {}
        )
        self.publish(event)
    
    def get_event_history(self, limit: int = 50) -> List[Event]:
        """获取事件历史"""
        return self._event_history[-limit:]
    
    def get_events_by_type(self, event_type: EventType, limit: int = 20) -> List[Event]:
        """按类型获取事件"""
        events = [e for e in self._event_history if e.event_type == event_type]
        return events[-limit:]
    
    def clear_history(self):
        """清空事件历史"""
        self._event_history = []
    
    def _on_memory_created(self, event: Event):
        """处理记忆创建事件"""
        from .cross_system_caller import get_cross_system_caller
        caller = get_cross_system_caller()
        
        # 将新记忆同步到学习系统
        caller.call('continual_learning', 'learn_from_memory', 
                   content=event.data.get('content', ''))
        
        # 将新记忆同步到推理系统
        caller.call('cognitive_reasoning', 'update_knowledge',
                   memory=event.data)
    
    def _on_learning_completed(self, event: Event):
        """处理学习完成事件"""
        from .cross_system_caller import get_cross_system_caller
        caller = get_cross_system_caller()
        
        # 将学习结果存入长期记忆
        caller.call('brain_memory', 'store_long_term',
                   content=event.data.get('result', ''),
                   metadata={'source': 'learning'})
        
        # 触发自我反思
        caller.call('self_awareness', 'reflect')
    
    def _on_reasoning_completed(self, event: Event):
        """处理推理完成事件"""
        from .cross_system_caller import get_cross_system_caller
        caller = get_cross_system_caller()
        
        # 将推理结果存入记忆
        caller.call('brain_memory', 'store_short_term',
                   content=event.data.get('result', ''),
                   metadata={'source': 'reasoning'})
    
    def _on_reflection_completed(self, event: Event):
        """处理反思完成事件"""
        from .cross_system_caller import get_cross_system_caller
        caller = get_cross_system_caller()
        
        suggestions = event.data.get('suggestions', [])
        
        # 根据反思建议调整系统
        for suggestion in suggestions:
            if "学习" in suggestion or "训练" in suggestion:
                caller.call('continual_learning', 'add_task',
                           description=suggestion)
            elif "记忆" in suggestion:
                caller.call('brain_memory', 'consolidate')
    
    def _on_health_alert(self, event: Event):
        """处理健康告警事件"""
        from .cross_system_caller import get_cross_system_caller
        caller = get_cross_system_caller()
        
        # 触发自我修复
        caller.call('self_healing', 'repair',
                   issue=event.data)
    
    def _on_mcp_disconnected(self, event: Event):
        """处理MCP断开事件"""
        from .cross_system_caller import get_cross_system_caller
        caller = get_cross_system_caller()
        
        # 通知自我意识系统降级
        caller.call('self_awareness', 'update_system_state',
                   mcp_available=False)


# 单例模式
_bus_instance = None

def get_event_bus() -> EventBus:
    """获取事件总线实例"""
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = EventBus()
    return _bus_instance


def subscribe(event_type: EventType, handler: Callable):
    """订阅事件（便捷函数）"""
    get_event_bus().subscribe(event_type, handler)


def publish(event_type: EventType, source: str, data: Dict = None):
    """发布事件（便捷函数）"""
    get_event_bus().publish_simple(event_type, source, data)