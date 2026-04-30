"""增强事件总线 - 添加缺失功能"""

from client.src.business.shared.event_bus import EventBus, Event
from typing import Dict, Callable, Any, Optional, List
import time

class EnhancedEventBus(EventBus):
    """增强事件总线"""
    
    def __init__(self, async_enabled: bool = True):
        super().__init__(async_enabled)
        self._filters: Dict[str, List[Callable]] = {}
        self._retry_policy: Dict[str, int] = {}
        self._history: List[Event] = []
        self._max_history_size = 1000
    
    def add_filter(self, event_type: str, filter_func: Callable[[Dict[str, Any]], bool]):
        """添加事件过滤器"""
        if event_type not in self._filters:
            self._filters[event_type] = []
        self._filters[event_type].append(filter_func)
    
    def set_retry_policy(self, event_type: str, max_retries: int):
        """设置重试策略"""
        self._retry_policy[event_type] = max_retries
    
    def get_event_history(self, event_type: Optional[str] = None, limit: int = 100) -> List[Event]:
        """获取事件历史"""
        history = self._history
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        return history[-limit:]
    
    def publish(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """发布事件（增强版）"""
        if event_type in self._filters:
            for filter_func in self._filters[event_type]:
                if not filter_func({"event_type": event_type, "data": data}):
                    print(f"[EnhancedEventBus] 事件被过滤: {event_type}")
                    return
        
        super().publish(event_type, data)
        
        self._history.append(Event(event_type, data))
        if len(self._history) > self._max_history_size:
            self._history.pop(0)
    
    def _process_async_event(self, event: Event):
        """处理异步事件（增强版）"""
        max_retries = self._retry_policy.get(event.event_type, 1)
        
        for attempt in range(max_retries):
            try:
                super()._process_async_event(event)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
                else:
                    print(f"[EnhancedEventBus] 异步事件处理失败 ({event.event_type}): {e}")
    
    def get_history_size(self) -> int:
        """获取历史记录大小"""
        return len(self._history)
    
    def clear_history(self):
        """清空历史记录"""
        self._history.clear()

_global_enhanced_bus = EnhancedEventBus()

def get_enhanced_event_bus() -> EnhancedEventBus:
    """获取增强事件总线实例"""
    return _global_enhanced_bus