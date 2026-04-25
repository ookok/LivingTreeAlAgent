"""
Microkernel - 微内核架构

LivingTreeAI 的微内核实现。
内核只负责最基础的功能：插件生命周期、服务注册、扩展点管理、事件总线集成。

架构：
┌─────────────────────────────────────────────┐
│              Application Layer             │
│    (Plugins: UI, Agents, Skills, etc.)   │
├─────────────────────────────────────────────┤
│            Microkernel Layer                │
│  ┌──────────┬──────────┬──────────┐      │
│  │ Service   │Extension │ Plugin   │      │
│  │ Registry  │Point Mgr │ Manager  │      │
│  └──────────┴──────────┴──────────┘      │
│  ┌──────────┬──────────┐                  │
│  │ EventBus  │ Config   │                  │
│  │           │ Manager  │                  │
│  └──────────┴──────────┘                  │
├─────────────────────────────────────────────┤
│              Infrastructure Layer            │
│    (Python, PyQt6, File System, Network)  │
└─────────────────────────────────────────────┘
"""

from .kernel import Microkernel, get_kernel, init_kernel, shutdown_kernel
from .service_registry import ServiceRegistry, ServiceDescriptor, ServiceScope
from .extension_point import ExtensionPointManager, ExtensionPoint, Extension
from .lifecycle import LifecycleManager, LifecycleState, LifecycleEvent
from .kernel_events import KernelEvents, KernelState

__version__ = "1.0.0"
__all__ = [
    # 内核
    "Microkernel", "get_kernel", "init_kernel", "shutdown_kernel",
    # 服务注册
    "ServiceRegistry", "ServiceDescriptor", "ServiceScope",
    # 扩展点
    "ExtensionPointManager", "ExtensionPoint", "Extension",
    # 生命周期
    "LifecycleManager", "LifecycleState", "LifecycleEvent",
    # 事件
    "KernelEvents", "KernelState",
]
