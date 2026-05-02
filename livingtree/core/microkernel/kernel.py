"""
Microkernel - 微内核主类

最小内核：只负责插件生命周期、服务注册、扩展点管理、事件集成。
所有业务功能都通过插件实现，内核不绑定任何具体功能。
"""

import logging
import threading
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Callable, Set

# 从业务层导入基础设施
from ..enhanced_event_bus import EnhancedEventBus, get_enhanced_event_bus
from ..plugin_framework.event_bus import EventBus
from ..plugin_framework.plugin_manager import PluginManager, get_plugin_manager
from ..plugin_framework.base_plugin import BasePlugin, PluginManifest

from .service_registry import ServiceRegistry, ServiceDescriptor
from .extension_point import ExtensionPointManager, ExtensionPoint
from .lifecycle import LifecycleManager, LifecycleState, LifecycleEvent
from .kernel_events import KernelEvents, KernelState

logger = logging.getLogger(__name__)


class KernelState(Enum):
    """内核状态"""
    BOOTSTRAPPING = "bootstrapping"   # 启动中
    RUNNING = "running"                # 运行中
    DEGRADED = "degraded"             # 降级运行（部分插件失败）
    MAINTENANCE = "maintenance"        # 维护模式（不接收新请求）
    SHUTTING_DOWN = "shutting_down"   # 关闭中
    STOPPED = "stopped"               # 已停止


@dataclass
class KernelInfo:
    """内核信息"""
    version: str = "1.0.0"
    state: KernelState = KernelState.BOOTSTRAPPING
    plugin_count: int = 0
    service_count: int = 0
    extension_point_count: int = 0
    uptime_seconds: float = 0.0
    started_at: float = 0.0


class Microkernel:
    """
    微内核

    职责：
    1. 管理内核状态机（BOOTSTRAPPING → RUNNING → SHUTTING_DOWN → STOPPED）
    2. 初始化基础设施（EventBus、PluginManager、ServiceRegistry、ExtensionPointManager）
    3. 提供统一的启动/关闭流程
    4. 管理服务注册表（插件可以注册和发现服务）
    5. 管理扩展点（插件可以定义和扩展）
    6. 提供插件间通信的高级 API

    设计原则：
    - 内核不实现任何业务逻辑
    - 所有功能都通过插件提供
    - 内核只提供最小 API（服务注册、扩展点、事件）
    - 内核可以在不重启的情况下替换插件
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._state = KernelState.BOOTSTRAPPING
        self._started_at = 0.0
        self._lock = threading.RLock()

        # 基础设施（由内核初始化）
        self._event_bus: Optional[EnhancedEventBus] = None
        self._plugin_manager: Optional[PluginManager] = None
        self._service_registry: Optional[ServiceRegistry] = None
        self._extension_manager: Optional[ExtensionPointManager] = None
        self._lifecycle_manager: Optional[LifecycleManager] = None

        # 内核事件
        self._kernel_events = KernelEvents()

        # 已注册的后初始化钩子
        self._post_init_hooks: List[Callable[[], None]] = []

        logger.info("[Microkernel] Created in BOOTSTRAPPING state")

    # ─────────────────────────────────────────────────────────────
    # 启动流程
    # ─────────────────────────────────────────────────────────────

    def start(self, main_window=None, plugin_dirs: Optional[List[str]] = None) -> bool:
        """
        启动内核

        流程：
        1. 初始化基础设施
        2. 加载插件
        3. 启动服务
        4. 切换到 RUNNING 状态

        Args:
            main_window: PyQt6 主窗口（可选）
            plugin_dirs: 插件目录列表

        Returns:
            是否成功启动
        """
        with self._lock:
            if self._state != KernelState.BOOTSTRAPPING:
                logger.warning(f"[Microkernel] Cannot start from state: {self._state.value}")
                return False

            try:
                logger.info("[Microkernel] Starting...")

                # 1. 初始化基础设施
                self._init_infrastructure()

                # 2. 初始化插件管理器
                self._init_plugin_manager(main_window, plugin_dirs)

                # 3. 发布内核启动事件
                self._event_bus.publish(self._kernel_events.kernel_starting())

                # 4. 加载并初始化插件
                # （由 PluginManager 负责，内核不直接操作）

                # 5. 执行后初始化钩子
                for hook in self._post_init_hooks:
                    try:
                        hook()
                    except Exception as e:
                        logger.error(f"[Microkernel] Post-init hook failed: {e}")

                # 6. 切换到 RUNNING 状态
                self._state = KernelState.RUNNING
                self._started_at = __import__('time').time()

                # 7. 发布内核就绪事件
                self._event_bus.publish(self._kernel_events.kernel_ready())

                logger.info("[Microkernel] Started successfully (RUNNING)")
                return True

            except Exception as e:
                logger.error(f"[Microkernel] Start failed: {e}")
                logger.error(traceback.format_exc())
                self._state = KernelState.DEGRADED
                return False

    def _init_infrastructure(self) -> None:
        """初始化基础设施"""
        # EnhancedEventBus（全局单例）
        self._event_bus = get_enhanced_event_bus()
        logger.debug("[Microkernel] EnhancedEventBus initialized")

        # ServiceRegistry（内核拥有）
        from .service_registry import get_service_registry
        self._service_registry = get_service_registry()
        logger.debug("[Microkernel] ServiceRegistry initialized")

        # ExtensionPointManager（内核拥有）
        from .extension_point import get_extension_point_manager
        self._extension_manager = get_extension_point_manager()
        logger.debug("[Microkernel] ExtensionPointManager initialized")

        # LifecycleManager（内核拥有）
        self._lifecycle_manager = LifecycleManager(self)
        logger.debug("[Microkernel] LifecycleManager initialized")

    def _init_plugin_manager(self, main_window, plugin_dirs) -> None:
        """初始化插件管理器"""
        self._plugin_manager = get_plugin_manager()
        self._plugin_manager.initialize(
            main_window=main_window,
            plugin_dirs=plugin_dirs,
        )
        logger.debug("[Microkernel] PluginManager initialized")

    # ─────────────────────────────────────────────────────────────
    # 关闭流程
    # ─────────────────────────────────────────────────────────────

    def shutdown(self, timeout: float = 30.0) -> bool:
        """
        关闭内核

        Args:
            timeout: 等待插件停止的超时时间（秒）

        Returns:
            是否成功关闭
        """
        with self._lock:
            if self._state == KernelState.STOPPED:
                return True

            self._state = KernelState.SHUTTING_DOWN
            logger.info("[Microkernel] Shutting down...")

            # 发布内核关闭事件
            if self._event_bus:
                self._event_bus.publish(self._kernel_events.kernel_shutting_down())

            # 停止所有插件
            if self._plugin_manager:
                try:
                    self._plugin_manager.shutdown_all(timeout=timeout)
                except Exception as e:
                    logger.error(f"[Microkernel] Plugin shutdown error: {e}")

            # 清理服务注册表
            if self._service_registry:
                self._service_registry.clear()

            # 清理扩展点
            if self._extension_manager:
                self._extension_manager.clear()

            # 切换到 STOPPED 状态
            self._state = KernelState.STOPPED

            # 发布内核停止事件
            if self._event_bus:
                self._event_bus.publish(self._kernel_events.kernel_stopped())

            logger.info("[Microkernel] Shut down successfully (STOPPED)")
            return True

    # ─────────────────────────────────────────────────────────────
    # 状态查询
    # ─────────────────────────────────────────────────────────────

    @property
    def state(self) -> KernelState:
        """获取内核状态"""
        return self._state

    @property
    def is_running(self) -> bool:
        """内核是否正在运行"""
        return self._state == KernelState.RUNNING

    @property
    def is_degraded(self) -> bool:
        """内核是否降级运行"""
        return self._state == KernelState.DEGRADED

    def get_info(self) -> KernelInfo:
        """获取内核信息"""
        import time
        return KernelInfo(
            version="1.0.0",
            state=self._state,
            plugin_count=len(self._plugin_manager.get_all_plugins()) if self._plugin_manager else 0,
            service_count=self._service_registry.get_service_count() if self._service_registry else 0,
            extension_point_count=self._extension_manager.get_extension_point_count() if self._extension_manager else 0,
            uptime_seconds=time.time() - self._started_at if self._started_at else 0.0,
            started_at=self._started_at,
        )

    # ─────────────────────────────────────────────────────────────
    # 服务注册表 API
    # ─────────────────────────────────────────────────────────────

    def register_service(self, descriptor: ServiceDescriptor) -> bool:
        """
        注册服务

        Args:
            descriptor: 服务描述符

        Returns:
            是否成功注册
        """
        if not self._service_registry:
            logger.error("[Microkernel] ServiceRegistry not initialized")
            return False
        return self._service_registry.register(descriptor)

    def unregister_service(self, service_id: str) -> bool:
        """
        注销服务

        Args:
            service_id: 服务ID

        Returns:
            是否成功注销
        """
        if not self._service_registry:
            return False
        return self._service_registry.unregister(service_id)

    def get_service(self, service_id: str) -> Optional[Any]:
        """
        获取服务实例

        Args:
            service_id: 服务ID

        Returns:
            服务实例，不存在则返回 None
        """
        if not self._service_registry:
            return None
        return self._service_registry.get_service(service_id)

    def has_service(self, service_id: str) -> bool:
        """检查服务是否存在"""
        if not self._service_registry:
            return False
        return self._service_registry.has_service(service_id)

    def list_services(self, interface: Optional[str] = None) -> List[ServiceDescriptor]:
        """
        列出所有服务

        Args:
            interface: 按接口过滤（可选）

        Returns:
            服务描述符列表
        """
        if not self._service_registry:
            return []
        return self._service_registry.list_services(interface)

    # ─────────────────────────────────────────────────────────────
    # 扩展点 API
    # ─────────────────────────────────────────────────────────────

    def register_extension_point(self, point: ExtensionPoint) -> bool:
        """
        注册扩展点

        Args:
            point: 扩展点定义

        Returns:
            是否成功注册
        """
        if not self._extension_manager:
            logger.error("[Microkernel] ExtensionPointManager not initialized")
            return False
        return self._extension_manager.register_extension_point(point)

    def unregister_extension_point(self, point_id: str) -> bool:
        """
        注销扩展点

        Args:
            point_id: 扩展点ID

        Returns:
            是否成功注销
        """
        if not self._extension_manager:
            return False
        return self._extension_manager.unregister_extension_point(point_id)

    def register_extension(self, point_id: str, extension: 'Extension') -> bool:
        """
        注册扩展（为某个扩展点提供实现）

        Args:
            point_id: 扩展点ID
            extension: 扩展实现

        Returns:
            是否成功注册
        """
        if not self._extension_manager:
            return False
        return self._extension_manager.register_extension(point_id, extension)

    def get_extensions(self, point_id: str) -> List['Extension']:
        """
        获取扩展点的所有扩展

        Args:
            point_id: 扩展点ID

        Returns:
            扩展列表（按优先级排序）
        """
        if not self._extension_manager:
            return []
        return self._extension_manager.get_extensions(point_id)

    # ─────────────────────────────────────────────────────────────
    # 插件管理 API（委托给 PluginManager）
    # ─────────────────────────────────────────────────────────────

    def get_plugin_manager(self) -> Optional[PluginManager]:
        """获取插件管理器"""
        return self._plugin_manager

    def get_event_bus(self) -> Optional[EventBus]:
        """获取事件总线"""
        return self._event_bus

    # ─────────────────────────────────────────────────────────────
    # 后初始化钩子
    # ─────────────────────────────────────────────────────────────

    def add_post_init_hook(self, hook: Callable[[], None]) -> None:
        """添加后初始化钩子"""
        self._post_init_hooks.append(hook)

    # ─────────────────────────────────────────────────────────────
    # 维护模式
    # ─────────────────────────────────────────────────────────────

    def enter_maintenance_mode(self) -> None:
        """进入维护模式（不接收新请求）"""
        with self._lock:
            if self._state == KernelState.RUNNING:
                self._state = KernelState.MAINTENANCE
                logger.warning("[Microkernel] Entered MAINTENANCE mode")
                if self._event_bus:
                    self._event_bus.publish(self._kernel_events.kernel_maintenance_enter())

    def exit_maintenance_mode(self) -> None:
        """退出维护模式"""
        with self._lock:
            if self._state == KernelState.MAINTENANCE:
                self._state = KernelState.RUNNING
                logger.info("[Microkernel] Exited MAINTENANCE mode")
                if self._event_bus:
                    self._event_bus.publish(self._kernel_events.kernel_maintenance_exit())

    # ─────────────────────────────────────────────────────────────
    # 字符串表示
    # ─────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        info = self.get_info()
        return (
            f"Microkernel(state={info.state.value}, "
            f"plugins={info.plugin_count}, "
            f"services={info.service_count}, "
            f"extensions={info.extension_point_count})"
        )


# ─────────────────────────────────────────────────────────────
# 全局单例
# ─────────────────────────────────────────────────────────────

_kernel_instance: Optional[Microkernel] = None
_kernel_lock = threading.RLock()


def get_kernel() -> Optional[Microkernel]:
    """获取内核单例"""
    global _kernel_instance
    return _kernel_instance


def init_kernel(config: Optional[Dict[str, Any]] = None) -> Microkernel:
    """
    初始化内核单例

    Args:
        config: 内核配置

    Returns:
        内核实例
    """
    global _kernel_instance
    with _kernel_lock:
        if _kernel_instance is None:
            _kernel_instance = Microkernel(config)
        return _kernel_instance


def shutdown_kernel(timeout: float = 30.0) -> bool:
    """
    关闭内核

    Args:
        timeout: 超时时间（秒）

    Returns:
        是否成功关闭
    """
    global _kernel_instance
    with _kernel_lock:
        if _kernel_instance is None:
            return True
        result = _kernel_instance.shutdown(timeout=timeout)
        _kernel_instance = None
        return result
