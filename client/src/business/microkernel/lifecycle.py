"""
Lifecycle Manager - 生命周期管理

管理内核和插件的状态转换。
支持状态机、生命周期钩子、状态变更事件。

设计理念：
1. 状态机：明确定义状态转换规则
2. 生命周期钩子：插件可以注册钩子（on_start, on_stop, on_error）
3. 状态变更事件：状态变更时发布事件
4. 优雅启停：支持超时、强制停止
"""

import threading
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Set
import logging

# 从 plugin_framework 导入基础设施
from client.src.business.plugin_framework.event_bus import EventBus, get_event_bus

logger = logging.getLogger(__name__)


class LifecycleState(Enum):
    """生命周期状态"""
    UNKNOWN = "unknown"           # 未知状态
    INITIALIZING = "initializing" # 初始化中
    INITIALIZED = "initialized"   # 已初始化
    STARTING = "starting"         # 启动中
    RUNNING = "running"           # 运行中
    STOPPING = "stopping"        # 停止中
    STOPPED = "stopped"           # 已停止
    ERROR = "error"               # 错误状态
    DEGRADED = "degraded"       # 降级运行


class LifecycleEvent(Enum):
    """生命周期事件"""
    # 内核事件
    KERNEL_INITIALIZING = "kernel_initializing"
    KERNEL_INITIALIZED = "kernel_initialized"
    KERNEL_STARTING = "kernel_starting"
    KERNEL_RUNNING = "kernel_running"
    KERNEL_STOPPING = "kernel_stopping"
    KERNEL_STOPPED = "kernel_stopped"
    KERNEL_ERROR = "kernel_error"
    KERNEL_DEGRADED = "kernel_degraded"

    # 插件事件
    PLUGIN_LOADING = "plugin_loading"
    PLUGIN_LOADED = "plugin_loaded"
    PLUGIN_STARTING = "plugin_starting"
    PLUGIN_RUNNING = "plugin_running"
    PLUGIN_STOPPING = "plugin_stopping"
    PLUGIN_STOPPED = "plugin_stopped"
    PLUGIN_ERROR = "plugin_error"
    PLUGIN_UNLOADED = "plugin_unloaded"


@dataclass
class LifecycleRecord:
    """生命周期记录"""
    component_id: str
    component_type: str  # "kernel" or "plugin"
    state: LifecycleState = LifecycleState.UNKNOWN
    last_event: Optional[LifecycleEvent] = None
    last_event_time: float = 0.0
    error_message: str = ""
    start_time: float = 0.0
    stop_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class LifecycleManager:
    """
    生命周期管理器

    管理内核和所有插件的生命周期。

    使用示例：
        manager = LifecycleManager(kernel)

        # 注册生命周期钩子
        manager.register_hook(
            LifecycleEvent.KERNEL_RUNNING,
            lambda: print("Kernel is running!")
        )

        # 获取组件状态
        state = manager.get_state("kernel")

        # 获取生命周期记录
        record = manager.get_record("my_plugin")
    """

    def __init__(self, kernel):
        self._kernel = kernel
        self._event_bus: Optional[EventBus] = None
        self._records: Dict[str, LifecycleRecord] = {}
        self._hooks: Dict[LifecycleEvent, List[Callable[[], None]]] = {}
        self._lock = threading.RLock()
        self._logger = logging.getLogger("LifecycleManager")

        # 初始化 EventBus
        try:
            self._event_bus = get_event_bus()
        except Exception:
            pass

        # 注册内核记录
        self._register_component("kernel", "kernel")

        self._logger.info("[LifecycleManager] Initialized")

    def _register_component(self, component_id: str, component_type: str) -> None:
        """注册组件"""
        with self._lock:
            if component_id not in self._records:
                self._records[component_id] = LifecycleRecord(
                    component_id=component_id,
                    component_type=component_type,
                    state=LifecycleState.UNKNOWN,
                )
                self._logger.debug(f"Registered component: {component_id} ({component_type})")

    def register_hook(self, event: LifecycleEvent, callback: Callable[[], None]) -> None:
        """
        注册生命周期钩子

        Args:
            event: 生命周期事件
            callback: 回调函数
        """
        with self._lock:
            if event not in self._hooks:
                self._hooks[event] = []
            self._hooks[event].append(callback)
            self._logger.debug(f"Registered lifecycle hook for {event.value}")

    def unregister_hook(self, event: LifecycleEvent, callback: Callable[[], None]) -> bool:
        """
        注销生命周期钩子

        Args:
            event: 生命周期事件
            callback: 回调函数

        Returns:
            是否成功注销
        """
        with self._lock:
            if event not in self._hooks:
                return False
            before = len(self._hooks[event])
            self._hooks[event] = [cb for cb in self._hooks[event] if cb != callback]
            after = len(self._hooks[event])
            return after < before

    def transition(self, component_id: str, new_state: LifecycleState,
                  event: Optional[LifecycleEvent] = None,
                  error_message: str = "") -> bool:
        """
        状态转换

        Args:
            component_id: 组件ID
            new_state: 新状态
            event: 触发的事件（可选）
            error_message: 错误信息（可选）

        Returns:
            是否成功转换
        """
        with self._lock:
            if component_id not in self._records:
                self._register_component(component_id, "unknown")

            record = self._records[component_id]
            old_state = record.state

            # 验证状态转换（简化：允许所有转换，实际应该检查合法性）
            # TODO: 实现完整的状态机验证

            # 更新记录
            record.state = new_state
            if event:
                record.last_event = event
                record.last_event_time = time.time()
            if error_message:
                record.error_message = error_message

            if new_state == LifecycleState.RUNNING:
                record.start_time = time.time()
            elif new_state in (LifecycleState.STOPPED, LifecycleState.ERROR):
                record.stop_time = time.time()

            self._logger.info(
                f"[Lifecycle] {component_id}: {old_state.value} → {new_state.value}"
            )

            # 触发钩子
            if event:
                self._trigger_hooks(event)

            # 发布事件
            if self._event_bus:
                self._publish_event(component_id, old_state, new_state, event, error_message)

            return True

    def _trigger_hooks(self, event: LifecycleEvent) -> None:
        """触发生命周期钩子"""
        if event not in self._hooks:
            return
        for callback in self._hooks[event]:
            try:
                callback()
            except Exception as e:
                self._logger.error(f"Lifecycle hook error for {event.value}: {e}")
                self._logger.error(traceback.format_exc())

    def _publish_event(self, component_id: str, old_state: LifecycleState,
                      new_state: LifecycleState, event: Optional[LifecycleEvent],
                      error_message: str) -> None:
        """发布生命周期事件到 EventBus"""
        if not self._event_bus:
            return
        try:
            from client.src.business.plugin_framework.event_bus import Event
            event_obj = Event(
                type=f"lifecycle.{event.value if event else 'unknown'}",
                data={
                    "component_id": component_id,
                    "old_state": old_state.value,
                    "new_state": new_state.value,
                    "event": event.value if event else "unknown",
                    "error_message": error_message,
                    "timestamp": time.time(),
                },
                source="LifecycleManager",
            )
            self._event_bus.publish(event_obj)
        except Exception as e:
            self._logger.error(f"Failed to publish lifecycle event: {e}")

    def get_state(self, component_id: str) -> Optional[LifecycleState]:
        """获取组件状态"""
        with self._lock:
            if component_id not in self._records:
                return None
            return self._records[component_id].state

    def get_record(self, component_id: str) -> Optional[LifecycleRecord]:
        """获取生命周期记录"""
        with self._lock:
            return self._records.get(component_id)

    def get_all_records(self) -> Dict[str, LifecycleRecord]:
        """获取所有生命周期记录"""
        with self._lock:
            return self._records.copy()

    def get_components_by_state(self, state: LifecycleState) -> List[str]:
        """获取指定状态的所有组件"""
        with self._lock:
            return [
                cid for cid, rec in self._records.items()
                if rec.state == state
            ]

    def is_running(self, component_id: str) -> bool:
        """检查组件是否正在运行"""
        state = self.get_state(component_id)
        return state == LifecycleState.RUNNING

    def is_stopped(self, component_id: str) -> bool:
        """检查组件是否已停止"""
        state = self.get_state(component_id)
        return state in (LifecycleState.STOPPED, LifecycleState.ERROR)

    def get_uptime(self, component_id: str) -> float:
        """获取组件运行时间（秒）"""
        record = self.get_record(component_id)
        if not record:
            return 0.0
        if record.start_time == 0.0:
            return 0.0
        if record.stop_time > 0.0:
            return record.stop_time - record.start_time
        return time.time() - record.start_time

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            state_counts: Dict[str, int] = {}
            for record in self._records.values():
                state_name = record.state.value
                state_counts[state_name] = state_counts.get(state_name, 0) + 1

            return {
                "total_components": len(self._records),
                "state_counts": state_counts,
                "hooks_count": sum(len(hooks) for hooks in self._hooks.values()),
            }

    def clear(self) -> None:
        """清空所有记录（关闭内核时调用）"""
        with self._lock:
            self._records.clear()
            self._hooks.clear()
            # 重新注册内核
            self._register_component("kernel", "kernel")
            self._logger.info("[LifecycleManager] Cleared all records")
