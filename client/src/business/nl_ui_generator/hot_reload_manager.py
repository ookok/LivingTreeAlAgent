"""
Hot Reload Manager - 热重载管理器
==================================

UI热重载，支持模板和组件的动态更新。

功能:
- 监听模板变更
- 向所有窗口推送更新
- 平滑过渡动画
- 状态保存和恢复
"""

import json
import asyncio
import time
from typing import Optional, Any, Callable, Dict, List
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


class ReloadEventType(Enum):
    """重载事件类型"""
    TEMPLATE_CHANGED = "template_changed"
    COMPONENT_ADDED = "component_added"
    COMPONENT_REMOVED = "component_removed"
    COMPONENT_MODIFIED = "component_modified"
    FULL_RELOAD = "full_reload"


@dataclass
class ReloadEvent:
    """重载事件"""
    type: ReloadEventType
    template_id: str
    component_id: str = ""
    changes: dict = field(default_factory=dict)
    timestamp: float = 0
    source: str = "system"

    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = ReloadEventType(self.type)
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class WindowState:
    """窗口状态"""
    window_id: str
    template_id: str
    scroll_position: float = 0
    selected_components: list = field(default_factory=list)
    expanded_slots: list = field(default_factory=list)
    custom_state: dict = field(default_factory=dict)


class HotReloadManager:
    """热重载管理器"""

    def __init__(self):
        # 监听器
        self.listeners: Dict[str, List[Callable]] = defaultdict(list)

        # 窗口状态
        self.window_states: Dict[str, WindowState] = {}

        # 模板缓存
        self.template_cache: Dict[str, dict] = {}

        # 变更统计
        self.stats = {
            "total_reloads": 0,
            "successful_reloads": 0,
            "failed_reloads": 0,
            "last_reload_time": 0,
        }

        # 批量更新缓冲
        self._update_buffer: List[ReloadEvent] = []
        self._is_buffering = False

        # 观察者
        self.observers: List[Callable] = []

    def register_listener(self, template_id: str, callback: Callable):
        """
        注册监听器

        Args:
            template_id: 模板ID
            callback: 回调函数
        """
        self.listeners[template_id].append(callback)

    def unregister_listener(self, template_id: str, callback: Callable) -> bool:
        """注销监听器"""
        if callback in self.listeners.get(template_id, []):
            self.listeners[template_id].remove(callback)
            return True
        return False

    async def notify_change(
        self,
        template_id: str,
        event_type: ReloadEventType,
        component_id: str = "",
        changes: dict = None,
        source: str = "system",
    ):
        """
        通知模板变更

        Args:
            template_id: 模板ID
            event_type: 事件类型
            component_id: 组件ID
            changes: 变更数据
            source: 变更来源
        """
        event = ReloadEvent(
            type=event_type,
            template_id=template_id,
            component_id=component_id,
            changes=changes or {},
            source=source,
        )

        self.stats["total_reloads"] += 1
        self.stats["last_reload_time"] = event.timestamp

        # 如果正在缓冲，添加到缓冲区
        if self._is_buffering:
            self._update_buffer.append(event)
            return

        # 发布事件
        await self._publish_event(event)

    async def _publish_event(self, event: ReloadEvent):
        """发布事件到所有监听器"""
        # 获取该模板的监听器
        callbacks = self.listeners.get(event.template_id, [])

        # 也通知全局监听器
        global_callbacks = self.listeners.get("*", [])
        all_callbacks = callbacks + global_callbacks

        # 执行所有回调
        results = await asyncio.gather(
            *[self._safe_call_callback(cb, event) for cb in all_callbacks],
            return_exceptions=True,
        )

        # 统计成功/失败
        for result in results:
            if isinstance(result, Exception):
                self.stats["failed_reloads"] += 1
            else:
                self.stats["successful_reloads"] += 1

        # 通知观察者
        for observer in self.observers:
            try:
                observer(event)
            except Exception:
                pass

    async def _safe_call_callback(self, callback: Callable, event: ReloadEvent):
        """安全调用回调"""
        if asyncio.iscoroutinefunction(callback):
            return await callback(event)
        else:
            return callback(event)

    def start_batching(self):
        """开始批量更新"""
        self._is_buffering = True
        self._update_buffer.clear()

    async def end_batching(self, debounce_ms: int = 100):
        """
        结束批量更新

        Args:
            debounce_ms: 防抖延迟（毫秒）
        """
        self._is_buffering = False

        # 等待防抖
        if debounce_ms > 0:
            await asyncio.sleep(debounce_ms / 1000)

        # 合并缓冲区中的事件
        if self._update_buffer:
            merged_event = self._merge_events(self._update_buffer)
            await self._publish_event(merged_event)
            self._update_buffer.clear()

    def _merge_events(self, events: List[ReloadEvent]) -> ReloadEvent:
        """合并多个事件为一个"""
        if len(events) == 1:
            return events[0]

        # 合并变更
        all_changes = {}
        for event in events:
            all_changes.update(event.changes)

        # 返回第一个事件的模板ID，但使用最后事件的时间戳
        return ReloadEvent(
            type=ReloadEventType.TEMPLATE_CHANGED,
            template_id=events[0].template_id,
            changes={"merged": True, "events": len(events), "changes": all_changes},
            timestamp=events[-1].timestamp,
            source="batch",
        )

    # ========== 窗口状态管理 ==========

    def save_window_state(self, window_id: str, template_id: str) -> WindowState:
        """
        保存窗口状态

        Args:
            window_id: 窗口ID
            template_id: 模板ID

        Returns:
            WindowState: 窗口状态
        """
        state = WindowState(
            window_id=window_id,
            template_id=template_id,
        )
        self.window_states[window_id] = state
        return state

    def update_window_state(self, window_id: str, **kwargs):
        """更新窗口状态"""
        if window_id in self.window_states:
            state = self.window_states[window_id]
            for key, value in kwargs.items():
                if hasattr(state, key):
                    setattr(state, key, value)

    def get_window_state(self, window_id: str) -> Optional[WindowState]:
        """获取窗口状态"""
        return self.window_states.get(window_id)

    def delete_window_state(self, window_id: str) -> bool:
        """删除窗口状态"""
        if window_id in self.window_states:
            del self.window_states[window_id]
            return True
        return False

    # ========== 模板缓存管理 ==========

    def cache_template(self, template_id: str, template_data: dict):
        """缓存模板"""
        self.template_cache[template_id] = {
            "data": template_data,
            "cached_at": time.time(),
            "version": template_data.get("version", "1.0.0"),
        }

    def get_cached_template(self, template_id: str) -> Optional[dict]:
        """获取缓存的模板"""
        return self.template_cache.get(template_id, {}).get("data")

    def is_template_cached(self, template_id: str) -> bool:
        """检查模板是否已缓存"""
        return template_id in self.template_cache

    def invalidate_template_cache(self, template_id: str):
        """使模板缓存失效"""
        if template_id in self.template_cache:
            del self.template_cache[template_id]

    def clear_all_caches(self):
        """清空所有缓存"""
        self.template_cache.clear()

    # ========== 统计和监控 ==========

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.stats.copy()

    def reset_stats(self):
        """重置统计"""
        self.stats = {
            "total_reloads": 0,
            "successful_reloads": 0,
            "failed_reloads": 0,
            "last_reload_time": 0,
        }

    # ========== 观察者 ==========

    def add_observer(self, observer: Callable):
        """添加观察者"""
        self.observers.append(observer)

    def remove_observer(self, observer: Callable) -> bool:
        """移除观察者"""
        if observer in self.observers:
            self.observers.remove(observer)
            return True
        return False


# 全局单例
_reload_manager: Optional[HotReloadManager] = None


def get_hot_reload_manager() -> HotReloadManager:
    """获取热重载管理器单例"""
    global _reload_manager
    if _reload_manager is None:
        _reload_manager = HotReloadManager()
    return _reload_manager