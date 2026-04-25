"""
Kernel Events - 内核事件定义

统一所有内核事件的类型和数据格式。
事件通过 EventBus 发布，所有插件都可以订阅。

事件命名规范：
  kernel.starting    - 内核正在启动
  kernel.ready       - 内核就绪（可以接收请求）
  kernel.stopping    - 内核正在停止
  kernel.stopped     - 内核已停止
  kernel.degraded    - 内核降级运行
  kernel.maintenance.enter   - 进入维护模式
  kernel.maintenance.exit    - 退出维护模式
  plugin.loading     - 插件正在加载
  plugin.loaded      - 插件加载完成
  plugin.starting    - 插件正在启动
  plugin.running     - 插件运行中
  plugin.stopping    - 插件正在停止
  plugin.stopped     - 插件已停止
  plugin.error       - 插件错误
  plugin.unloaded    - 插件已卸载
  service.registered - 服务已注册
  service.unregistered - 服务已注销
  extension_point.registered - 扩展点已注册
  extension_point.unregistered - 扩展点已注销
  extension.registered - 扩展已注册
  extension.unregistered - 扩展已注销
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from enum import Enum

# 延迟导入：避免循环导入
# from core.plugin_framework.event_bus import Event


class KernelState(Enum):
    """内核状态（字符串枚举，用于事件数据）"""
    BOOTSTRAPPING = "bootstrapping"
    RUNNING = "running"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


@dataclass
class KernelEventData:
    """内核事件数据模板"""
    event_type: str
    timestamp: float = field(default_factory=lambda: time.time())
    data: Dict[str, Any] = field(default_factory=dict)

    def to_event(self, source: str = "Microkernel"):
        """转换为 EventBus 的 Event 对象"""
        # 延迟导入
        from core.plugin_framework.event_bus import Event
        return Event(
            type=self.event_type,
            data=self.data,
            source=source,
            timestamp=self.timestamp,
        )


class KernelEvents:
    """
    内核事件工厂

    提供创建所有内核事件的方法。
    所有事件都通过 EventBus 发布。

    使用示例：
        events = KernelEvents()
        event_bus.publish(events.kernel_starting())
        event_bus.publish(events.kernel_ready())
    """

    # ──────────────────────────────────────────────────────────────
    # 内核事件
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def kernel_starting() -> Any:
        """内核正在启动"""
        return KernelEventData(
            event_type="kernel.starting",
            data={
                "state": KernelState.BOOTSTRAPPING.value,
                "message": "Kernel is starting...",
            },
        ).to_event()

    @staticmethod
    def kernel_ready() -> Any:
        """内核就绪（可以接收请求）"""
        return KernelEventData(
            event_type="kernel.ready",
            data={
                "state": KernelState.RUNNING.value,
                "message": "Kernel is ready",
            },
        ).to_event()

    @staticmethod
    def kernel_stopping() -> Any:
        """内核正在停止"""
        return KernelEventData(
            event_type="kernel.stopping",
            data={
                "state": KernelState.SHUTTING_DOWN.value,
                "message": "Kernel is stopping...",
            },
        ).to_event()

    @staticmethod
    def kernel_stopped() -> Any:
        """内核已停止"""
        return KernelEventData(
            event_type="kernel.stopped",
            data={
                "state": KernelState.STOPPED.value,
                "message": "Kernel stopped",
            },
        ).to_event()

    @staticmethod
    def kernel_degraded(error_message: str = "") -> Any:
        """内核降级运行（部分插件失败）"""
        return KernelEventData(
            event_type="kernel.degraded",
            data={
                "state": KernelState.DEGRADED.value,
                "message": "Kernel running in degraded mode",
                "error_message": error_message,
            },
        ).to_event()

    @staticmethod
    def kernel_maintenance_enter() -> Any:
        """进入维护模式"""
        return KernelEventData(
            event_type="kernel.maintenance.enter",
            data={
                "state": KernelState.MAINTENANCE.value,
                "message": "Kernel entered maintenance mode",
            },
        ).to_event()

    @staticmethod
    def kernel_maintenance_exit() -> Any:
        """退出维护模式"""
        return KernelEventData(
            event_type="kernel.maintenance.exit",
            data={
                "state": KernelState.RUNNING.value,
                "message": "Kernel exited maintenance mode",
            },
        ).to_event()

    # ──────────────────────────────────────────────────────────────
    # 插件事件
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def plugin_loading(plugin_id: str, plugin_name: str = "") -> Any:
        """插件正在加载"""
        return KernelEventData(
            event_type="plugin.loading",
            data={
                "plugin_id": plugin_id,
                "plugin_name": plugin_name,
                "message": f"Plugin {plugin_id} is loading...",
            },
        ).to_event()

    @staticmethod
    def plugin_loaded(plugin_id: str, plugin_name: str = "", load_time: float = 0.0) -> Any:
        """插件加载完成"""
        return KernelEventData(
            event_type="plugin.loaded",
            data={
                "plugin_id": plugin_id,
                "plugin_name": plugin_name,
                "load_time": load_time,
                "message": f"Plugin {plugin_id} loaded successfully",
            },
        ).to_event()

    @staticmethod
    def plugin_starting(plugin_id: str) -> Any:
        """插件正在启动"""
        return KernelEventData(
            event_type="plugin.starting",
            data={
                "plugin_id": plugin_id,
                "message": f"Plugin {plugin_id} is starting...",
            },
        ).to_event()

    @staticmethod
    def plugin_running(plugin_id: str) -> Any:
        """插件运行中"""
        return KernelEventData(
            event_type="plugin.running",
            data={
                "plugin_id": plugin_id,
                "message": f"Plugin {plugin_id} is running",
            },
        ).to_event()

    @staticmethod
    def plugin_stopping(plugin_id: str) -> Any:
        """插件正在停止"""
        return KernelEventData(
            event_type="plugin.stopping",
            data={
                "plugin_id": plugin_id,
                "message": f"Plugin {plugin_id} is stopping...",
            },
        ).to_event()

    @staticmethod
    def plugin_stopped(plugin_id: str) -> Any:
        """插件已停止"""
        return KernelEventData(
            event_type="plugin.stopped",
            data={
                "plugin_id": plugin_id,
                "message": f"Plugin {plugin_id} stopped",
            },
        ).to_event()

    @staticmethod
    def plugin_error(plugin_id: str, error_message: str = "") -> Any:
        """插件错误"""
        return KernelEventData(
            event_type="plugin.error",
            data={
                "plugin_id": plugin_id,
                "error_message": error_message,
                "message": f"Plugin {plugin_id} error: {error_message}",
            },
        ).to_event()

    @staticmethod
    def plugin_unloaded(plugin_id: str) -> Any:
        """插件已卸载"""
        return KernelEventData(
            event_type="plugin.unloaded",
            data={
                "plugin_id": plugin_id,
                "message": f"Plugin {plugin_id} unloaded",
            },
        ).to_event()

    # ──────────────────────────────────────────────────────────────
    # 服务事件
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def service_registered(service_id: str, interface: str, plugin_id: str = "") -> Any:
        """服务已注册"""
        return KernelEventData(
            event_type="service.registered",
            data={
                "service_id": service_id,
                "interface": interface,
                "plugin_id": plugin_id,
                "message": f"Service {service_id} registered",
            },
        ).to_event()

    @staticmethod
    def service_unregistered(service_id: str, interface: str) -> Any:
        """服务已注销"""
        return KernelEventData(
            event_type="service.unregistered",
            data={
                "service_id": service_id,
                "interface": interface,
                "message": f"Service {service_id} unregistered",
            },
        ).to_event()

    # ──────────────────────────────────────────────────────────────
    # 扩展点事件
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def extension_point_registered(point_id: str, interface: str, plugin_id: str = "") -> Any:
        """扩展点已注册"""
        return KernelEventData(
            event_type="extension_point.registered",
            data={
                "point_id": point_id,
                "interface": interface,
                "plugin_id": plugin_id,
                "message": f"Extension point {point_id} registered",
            },
        ).to_event()

    @staticmethod
    def extension_point_unregistered(point_id: str) -> Any:
        """扩展点已注销"""
        return KernelEventData(
            event_type="extension_point.unregistered",
            data={
                "point_id": point_id,
                "message": f"Extension point {point_id} unregistered",
            },
        ).to_event()

    # ──────────────────────────────────────────────────────────────
    # 扩展事件
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def extension_registered(point_id: str, extension_id: str, plugin_id: str = "") -> Any:
        """扩展已注册"""
        return KernelEventData(
            event_type="extension.registered",
            data={
                "point_id": point_id,
                "extension_id": extension_id,
                "plugin_id": plugin_id,
                "message": f"Extension {extension_id} registered to point {point_id}",
            },
        ).to_event()

    @staticmethod
    def extension_unregistered(point_id: str, extension_id: str) -> Any:
        """扩展已注销"""
        return KernelEventData(
            event_type="extension.unregistered",
            data={
                "point_id": point_id,
                "extension_id": extension_id,
                "message": f"Extension {extension_id} unregistered from point {point_id}",
            },
        ).to_event()


# ──────────────────────────────────────────────────────────────
# 事件订阅辅助函数
# ──────────────────────────────────────────────────────────────

def subscribe_kernel_events(event_bus, callback) -> None:
    """
    订阅所有内核事件

    Args:
        event_bus: EventBus 实例
        callback: 回调函数（接收 event 参数）
    """
    kernel_events = [
        "kernel.starting",
        "kernel.ready",
        "kernel.stopping",
        "kernel.stopped",
        "kernel.degraded",
        "kernel.maintenance.*",
    ]
    for event_type in kernel_events:
        event_bus.subscribe(event_type, "kernel_subscriber", callback)


def subscribe_plugin_events(event_bus, callback) -> None:
    """
    订阅所有插件事件

    Args:
        event_bus: EventBus 实例
        callback: 回调函数（接收 event 参数）
    """
    plugin_events = [
        "plugin.loading",
        "plugin.loaded",
        "plugin.starting",
        "plugin.running",
        "plugin.stopping",
        "plugin.stopped",
        "plugin.error",
        "plugin.unloaded",
    ]
    for event_type in plugin_events:
        event_bus.subscribe(event_type, "plugin_subscriber", callback)


def subscribe_all_kernel_related(event_bus, callback) -> None:
    """
    订阅所有内核相关事件（内核 + 插件 + 服务 + 扩展）

    Args:
        event_bus: EventBus 实例
        callback: 回调函数（接收 event 参数）
    """
    subscribe_kernel_events(event_bus, callback)
    subscribe_plugin_events(event_bus, callback)

    # 服务事件
    service_events = [
        "service.registered",
        "service.unregistered",
    ]
    for event_type in service_events:
        event_bus.subscribe(event_type, "service_subscriber", callback)

    # 扩展事件
    extension_events = [
        "extension_point.registered",
        "extension_point.unregistered",
        "extension.registered",
        "extension.unregistered",
    ]
    for event_type in extension_events:
        event_bus.subscribe(event_type, "extension_subscriber", callback)
