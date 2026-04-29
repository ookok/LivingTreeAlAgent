"""
状态管理

响应式状态管理，支持不可变数据、批量更新、
订阅发布和持久化
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
import threading
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Subscriber:
    """订阅者"""
    callback: Callable
    selector: Optional[Callable] = None
    immediate: bool = True


class StateManager:
    """
    响应式状态管理器
    
    Features:
    - 不可变状态更新
    - 批量更新优化
    - 精确订阅（选择器）
    - 持久化支持
    - 时间旅行调试
    """
    
    def __init__(self, persist_path: Optional[str] = None):
        self._state: Dict[str, Any] = {}
        self._history: List[Dict[str, Any]] = []
        self._max_history = 100
        self._subscribers: Dict[str, List[Subscriber]] = {}  # key -> subscribers
        self._lock = threading.RLock()
        self._persist_path = persist_path
        self._pending_updates: Set[str] = set()
        self._batch_mode = False
        self._version = 0
        
        # 加载持久化数据
        if persist_path:
            self._load()
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """
        获取状态
        
        Args:
            key: 状态键
            default: 默认值
            
        Returns:
            状态值
        """
        with self._lock:
            return self._state.get(key, default)
    
    def set_state(self, key: str, value: Any, silent: bool = False):
        """
        设置状态
        
        Args:
            key: 状态键
            value: 状态值
            silent: 是否静默更新（不触发订阅）
        """
        with self._lock:
            old_value = self._state.get(key)
            
            # 浅比较
            if old_value is value:
                return
            
            # 记录历史
            self._history.append({
                "key": key,
                "old_value": old_value,
                "new_value": value,
                "timestamp": datetime.now().isoformat(),
                "version": self._version,
            })
            
            # 限制历史长度
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            
            # 更新状态
            self._state[key] = value
            self._version += 1
            
            if not silent:
                self._pending_updates.add(key)
                
                if not self._batch_mode:
                    self._notify_subscribers(key, old_value, value)
    
    def batch_update(self, updates: Dict[str, Any]):
        """
        批量更新
        
        Args:
            updates: 状态更新字典
        """
        with self._lock:
            self._batch_mode = True
        
        try:
            for key, value in updates.items():
                self.set_state(key, value, silent=True)
        finally:
            with self._lock:
                self._batch_mode = False
            
            # 批量通知
            for key in updates.keys():
                old_value = self._history[-1].get("old_value") if self._history else None
                self._notify_subscribers(key, old_value, updates[key])
    
    def update_state(self, key: str, updater: Callable):
        """
        通过函数更新状态
        
        Args:
            key: 状态键
            updater: 更新函数，接收旧值，返回新值
        """
        with self._lock:
            old_value = self._state.get(key)
            new_value = updater(old_value)
            self.set_state(key, new_value)
    
    def delete_state(self, key: str):
        """
        删除状态
        
        Args:
            key: 状态键
        """
        if key in self._state:
            old_value = self._state[key]
            del self._state[key]
            self._pending_updates.add(key)
            self._notify_subscribers(key, old_value, None)
    
    def subscribe(
        self,
        key: str,
        callback: Callable,
        selector: Optional[Callable] = None,
        immediate: bool = True
    ) -> Callable:
        """
        订阅状态变化
        
        Args:
            key: 状态键
            callback: 回调函数
            selector: 选择器，用于过滤不相关的变化
            immediate: 是否立即调用一次
            
        Returns:
            取消订阅的函数
        """
        with self._lock:
            subscriber = Subscriber(callback=callback, selector=selector, immediate=immediate)
            
            if key not in self._subscribers:
                self._subscribers[key] = []
            
            self._subscribers[key].append(subscriber)
            
            # 立即调用
            if immediate:
                current_value = self._state.get(key)
                if selector:
                    try:
                        current_value = selector(current_value)
                    except Exception:
                        pass
                callback(current_value)
        
        # 返回取消订阅函数
        def unsubscribe():
            with self._lock:
                if key in self._subscribers:
                    self._subscribers[key] = [
                        s for s in self._subscribers[key] if s.callback != callback
                    ]
        
        return unsubscribe
    
    def _notify_subscribers(self, key: str, old_value: Any, new_value: Any):
        """通知订阅者"""
        with self._lock:
            subscribers = self._subscribers.get(key, []).copy()
        
        for subscriber in subscribers:
            try:
                # 应用选择器
                if subscriber.selector:
                    try:
                        old_selected = subscriber.selector(old_value)
                        new_selected = subscriber.selector(new_value)
                        
                        # 比较选择后的值
                        if old_selected == new_selected:
                            continue
                        
                        subscriber.callback(new_selected, old_selected)
                    except Exception:
                        # 选择器出错，使用原始值
                        subscriber.callback(new_value, old_value)
                else:
                    subscriber.callback(new_value, old_value)
            except Exception as e:
                logger.error(f"Subscriber callback error: {e}")
    
    def _load(self):
        """从文件加载状态"""
        if not self._persist_path:
            return
        
        path = Path(self._persist_path)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._state = data.get("state", {})
                    self._version = data.get("version", 0)
                    logger.info(f"Loaded state from {self._persist_path}")
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
    
    def persist(self):
        """持久化状态到文件"""
        if not self._persist_path:
            return
        
        path = Path(self._persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            data = {
                "state": self._state,
                "version": self._version,
                "timestamp": datetime.now().isoformat(),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Persisted state to {self._persist_path}")
        except Exception as e:
            logger.error(f"Failed to persist state: {e}")
    
    def get_history(self, key: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """
        获取历史记录
        
        Args:
            key: 可选，筛选特定键
            limit: 返回条数
            
        Returns:
            历史记录列表
        """
        with self._lock:
            history = self._history.copy()
        
        if key:
            history = [h for h in history if h["key"] == key]
        
        return history[-limit:]
    
    def undo(self) -> bool:
        """
        撤销
        
        Returns:
            是否成功撤销
        """
        with self._lock:
            if not self._history:
                return False
            
            last = self._history.pop()
            self._state[last["key"]] = last["old_value"]
            self._version += 1
            
            # 通知
            self._notify_subscribers(last["key"], last["new_value"], last["old_value"])
            
            return True
    
    def redo(self) -> bool:
        """
        重做
        
        Returns:
            是否成功重做
        """
        with self._lock:
            # 找到最后一个可以重做的记录
            for i in range(len(self._history) - 1, -1, -1):
                if self._history[i]["version"] == self._version:
                    record = self._history[i]
                    self._state[record["key"]] = record["new_value"]
                    self._version += 1
                    
                    self._notify_subscribers(record["key"], record["old_value"], record["new_value"])
                    return True
            
            return False
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有状态"""
        with self._lock:
            return self._state.copy()
    
    def clear(self):
        """清除所有状态"""
        with self._lock:
            self._state.clear()
            self._history.clear()
            self._version = 0


# 响应式装饰器工厂
def reactive(initial_value: Any = None):
    """
    创建响应式状态
    
    Args:
        initial_value: 初始值
        
    Returns:
        属性描述符
    """
    class ReactiveProperty:
        def __init__(self, value):
            self.value = value
            self._subscribers: List[Callable] = []
        
        def __get__(self, obj, objtype=None):
            return self.value
        
        def __set__(self, obj, value):
            old_value = self.value
            self.value = value
            for callback in self._subscribers:
                callback(value, old_value)
        
        def subscribe(self, callback: Callable):
            self._subscribers.append(callback)
            return lambda: self._subscribers.remove(callback)
    
    return ReactiveProperty(initial_value)


# 状态存储创建器
def create_state_store(initial_state: Dict[str, Any] = None) -> StateManager:
    """
    创建状态存储
    
    Args:
        initial_state: 初始状态
        
    Returns:
        StateManager实例
    """
    manager = StateManager()
    if initial_state:
        manager.batch_update(initial_state)
    return manager


# 全局状态存储
_global_store: Optional[StateManager] = None


def get_global_store() -> StateManager:
    """获取全局状态存储"""
    global _global_store
    if _global_store is None:
        _global_store = StateManager()
    return _global_store


__all__ = [
    "StateManager",
    "Subscriber",
    "reactive",
    "create_state_store",
    "get_global_store",
]
