"""
事件总线 (Event Bus)

实现模块间的解耦通信，支持同步和异步事件处理。
"""

from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from threading import Lock, Thread
from queue import Queue
from datetime import datetime
import asyncio


@dataclass
class Event:
    """事件定义"""
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = ""
    
    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"{self.event_type}_{self.timestamp.timestamp()}"


class EventBus:
    """
    事件总线
    
    功能：
    1. 事件订阅：注册事件处理器
    2. 事件发布：发布事件到所有订阅者
    3. 异步处理：支持异步事件处理
    4. 事件队列：支持事件队列缓冲
    
    事件类型定义：
    - TERM_ADDED: 术语添加
    - TERM_UPDATED: 术语更新
    - DOCUMENT_VALIDATED: 文档验证完成
    - DOCUMENT_ADDED: 文档添加
    - FEEDBACK_RECORDED: 反馈记录
    - TRAINING_STARTED: 训练开始
    - TRAINING_COMPLETED: 训练完成
    - RETRIEVAL_PERFORMED: 检索执行
    
    使用方式：
    bus = EventBus()
    bus.subscribe("TERM_ADDED", my_handler)
    bus.publish("TERM_ADDED", {"term": term})
    """
    
    def __init__(self, async_enabled: bool = True):
        self._handlers: Dict[str, List[Callable]] = {}
        self._async_handlers: Dict[str, List[Callable]] = {}
        self._lock = Lock()
        self._async_enabled = async_enabled
        self._event_queue = Queue(maxsize=1000)
        
        # 启动异步处理线程
        if self._async_enabled:
            self._start_async_worker()
        
        print("[EventBus] 初始化完成")
    
    def _start_async_worker(self):
        """启动异步事件处理线程"""
        def worker():
            while True:
                try:
                    event = self._event_queue.get(timeout=1)
                    self._process_async_event(event)
                    self._event_queue.task_done()
                except:
                    pass
        
        self._worker_thread = Thread(target=worker, daemon=True)
        self._worker_thread.start()
    
    def subscribe(self, event_type: str, handler: Callable, async_mode: bool = False):
        """
        订阅事件
        
        Args:
            event_type: 事件类型
            handler: 事件处理器函数
            async_mode: 是否异步处理
        """
        if async_mode:
            if event_type not in self._async_handlers:
                self._async_handlers[event_type] = []
            self._async_handlers[event_type].append(handler)
        else:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
        
        print(f"[EventBus] 已订阅事件: {event_type} (async={async_mode})")
    
    def unsubscribe(self, event_type: str, handler: Callable):
        """取消订阅"""
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
        
        if event_type in self._async_handlers and handler in self._async_handlers[event_type]:
            self._async_handlers[event_type].remove(handler)
    
    def publish(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """
        发布事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        event = Event(event_type=event_type, data=data or {})
        
        # 同步处理
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    print(f"[EventBus] 事件处理失败 ({event_type}): {e}")
        
        # 异步处理
        if self._async_enabled and event_type in self._async_handlers:
            if not self._event_queue.full():
                self._event_queue.put(event)
    
    def _process_async_event(self, event: Event):
        """处理异步事件"""
        if event.event_type in self._async_handlers:
            for handler in self._async_handlers[event.event_type]:
                try:
                    handler(event)
                except Exception as e:
                    print(f"[EventBus] 异步事件处理失败 ({event.event_type}): {e}")
    
    def get_subscribed_events(self) -> List[str]:
        """获取所有已订阅的事件类型"""
        return list(set(list(self._handlers.keys()) + list(self._async_handlers.keys())))
    
    def get_handler_count(self, event_type: str) -> int:
        """获取事件的处理器数量"""
        sync_count = len(self._handlers.get(event_type, []))
        async_count = len(self._async_handlers.get(event_type, []))
        return sync_count + async_count


# 事件类型常量
EVENTS = {
    # 术语相关
    "TERM_ADDED": "term_added",
    "TERM_UPDATED": "term_updated",
    "TERM_CONFLICT": "term_conflict",
    
    # 文档相关
    "DOCUMENT_VALIDATED": "document_validated",
    "DOCUMENT_ADDED": "document_added",
    "DOCUMENT_REMOVED": "document_removed",
    
    # 反馈相关
    "FEEDBACK_RECORDED": "feedback_recorded",
    "FEEDBACK_ANALYZED": "feedback_analyzed",
    
    # 训练相关
    "TRAINING_STARTED": "training_started",
    "TRAINING_STAGE_COMPLETED": "training_stage_completed",
    "TRAINING_COMPLETED": "training_completed",
    
    # 检索相关
    "RETRIEVAL_PERFORMED": "retrieval_performed",
    "KNOWLEDGE_DISCOVERED": "knowledge_discovered",
    
    # 知识库相关
    "KNOWLEDGE_INGESTED": "knowledge_ingested",
    "KNOWLEDGE_QUERIED": "knowledge_queried",
    "KNOWLEDGE_LINTED": "knowledge_linted",
    "WIKI_PAGE_CREATED": "wiki_page_created",
    "WIKI_PAGE_UPDATED": "wiki_page_updated",
    
    # 系统相关
    "CONFIG_UPDATED": "config_updated",
    "SYSTEM_INITIALIZED": "system_initialized",
    "CHAT_CLEAR": "chat_clear"
}


# 全局事件总线实例
_global_event_bus = EventBus()


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    return _global_event_bus


def subscribe_event(event_type: str, handler: Callable, async_mode: bool = False):
    """订阅事件到全局事件总线"""
    _global_event_bus.subscribe(event_type, handler, async_mode)


def publish_event(event_type: str, data: Optional[Dict[str, Any]] = None):
    """向全局事件总线发布事件"""
    _global_event_bus.publish(event_type, data)


__all__ = [
    "EventBus",
    "Event",
    "EVENTS",
    "get_event_bus",
    "subscribe_event",
    "publish_event"
]