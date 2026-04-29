"""
轻量级UI系统

轻量级渲染引擎、虚拟DOM优化、智能缓存管理、
异步更新机制、响应式设计组件库
"""

from .models import (
    ComponentType,
    LayoutType,
    ResponsiveBreakpoint,
    UIState,
    ComponentEvent,
    AnimationType,
)
from .virtual_dom import VirtualDOM, VirtualNode, DOMPatcher
from .state_manager import StateManager, create_state_store, reactive
from .components import (
    LightweightButton,
    LightweightInput,
    LightweightSelect,
    LightweightCard,
    LightweightModal,
    LightweightToast,
    LightweightProgress,
    LightweightList,
    LightweightTable,
)
from .performance import (
    PerformanceMonitor,
    FPSCounter,
    MemoryOptimizer,
    AsyncUpdater,
)
from .layout import FlexLayout, GridLayout, ResponsiveLayout

# 网络优化模块
from .network_probe import NetworkProbeManager, NATType, NetworkType, ConnectionQuality, NetworkProbe
from .protocol_fallback import (
    ProtocolFallbackManager, ProtocolType, ConnectionState,
    FallbackLevel, RelayEndpoint
)
from .quality_monitor import QualityMonitor, QualityLevel, QualityMetrics, QualityAlert
from .fast_recovery import FastRecoveryManager, FaultType, RecoveryAction
from .adaptive_connection import (
    AdaptiveConnectionPool, ConnectionLoadBalancer,
    ConnectionType, ConnectionStatus, ConnectionInfo,
    ConnectionPoolConfig, RelayConfig
)
from .relay_client import (
    RelayClient, RelayServerManager, RelayState,
    RelayServerConfig, PeerInfo, QueuedMessage
)

# 统一调度器
class LightweightUI:
    """
    轻量级UI系统统一调度器
    
    Features:
    - 虚拟DOM高效渲染
    - 响应式状态管理
    - 性能监控优化
    - 响应式布局
    """
    
    def __init__(self):
        self.state_manager = StateManager()
        self.virtual_dom = VirtualDOM()
        self.performance_monitor = PerformanceMonitor()
        self.fps_counter = FPSCounter()
        self.memory_optimizer = MemoryOptimizer()
        self.async_updater = AsyncUpdater()
        
        self._running = False
        self._components = {}
    
    def start(self):
        """启动UI系统"""
        if self._running:
            return
        
        self._running = True
        self.performance_monitor.start()
        self.fps_counter.start()
        self.async_updater.start()
        
        return {
            "fps": 60,
            "memory_usage": 0,
            "active_components": 0,
        }
    
    def stop(self):
        """停止UI系统"""
        if not self._running:
            return
        
        self._running = False
        self.performance_monitor.stop()
        self.fps_counter.stop()
        self.async_updater.stop()
    
    def register_component(self, component_id: str, component):
        """注册组件"""
        self._components[component_id] = component
    
    def get_component(self, component_id: str):
        """获取组件"""
        return self._components.get(component_id)
    
    def update_component(self, component_id: str, state: dict):
        """更新组件状态"""
        component = self.get_component(component_id)
        if component:
            self.state_manager.set_state(component_id, state)
            self.virtual_dom.schedule_update(component_id)
    
    def get_performance_stats(self) -> dict:
        """获取性能统计"""
        return {
            "fps": self.fps_counter.get_fps(),
            "memory": self.memory_optimizer.get_memory_usage(),
            "update_queue": self.virtual_dom.get_update_queue_size(),
            "active_updates": self.async_updater.get_active_count(),
        }


# 单例实例
_ui_instance = None


def get_lightweight_ui() -> LightweightUI:
    """获取轻量级UI系统实例"""
    global _ui_instance
    if _ui_instance is None:
        _ui_instance = LightweightUI()
    return _ui_instance


__all__ = [
    # 模型
    "ComponentType",
    "LayoutType",
    "ResponsiveBreakpoint",
    "UIState",
    "ComponentEvent",
    "AnimationType",
    # 虚拟DOM
    "VirtualDOM",
    "VirtualNode",
    "DOMPatcher",
    # 状态管理
    "StateManager",
    "create_state_store",
    "reactive",
    # 组件
    "LightweightButton",
    "LightweightInput",
    "LightweightSelect",
    "LightweightCard",
    "LightweightModal",
    "LightweightToast",
    "LightweightProgress",
    "LightweightList",
    "LightweightTable",
    # 性能
    "PerformanceMonitor",
    "FPSCounter",
    "MemoryOptimizer",
    "AsyncUpdater",
    # 布局
    "FlexLayout",
    "GridLayout",
    "ResponsiveLayout",
    # 网络优化
    "NetworkProbeManager",
    "NATType",
    "NetworkType",
    "ConnectionQuality",
    "NetworkProbe",
    "ProtocolFallbackManager",
    "ProtocolType",
    "ConnectionState",
    "FallbackLevel",
    "RelayEndpoint",
    "QualityMonitor",
    "QualityLevel",
    "QualityMetrics",
    "QualityAlert",
    "FastRecoveryManager",
    "FaultType",
    "RecoveryAction",
    "AdaptiveConnectionPool",
    "ConnectionLoadBalancer",
    "ConnectionType",
    "ConnectionStatus",
    "ConnectionInfo",
    "ConnectionPoolConfig",
    "RelayConfig",
    "RelayClient",
    "RelayServerManager",
    "RelayState",
    "RelayServerConfig",
    "PeerInfo",
    "QueuedMessage",
    # 统一调度器
    "LightweightUI",
    "get_lightweight_ui",
]
