"""
Offline-First 单机模式 (Standalone Mode)
=======================================

核心理念：单机即"原子节点"，不依赖任何外部服务。

架构原则：
- 无网络启动：拔掉网线也能正常打开软件
- 数据封闭：所有文件严格存储在安装目录下
- 单机模式是"内核版"，不是"阉割版"

运行时模式：
- standalone: 单机模式（默认）
- distributed: 分布式模式
"""

from .runtime import (
    RuntimeMode,
    RuntimeConfig,
    StandaloneRuntime,
    create_runtime,
    get_runtime,
)
from .local_identity import (
    LocalIdentity,
    create_local_identity,
    DeviceFingerprint,
)
from .local_mailbox import (
    LocalMailbox,
    LocalMessage,
    create_local_mailbox,
    MessageObserver,
)
from .local_ai import (
    LocalAIEngine,
    create_local_ai_engine,
    ModelType,
    AICapability,
)
from .local_storage import (
    LocalStorage,
    create_local_storage,
    StorageScope,
)
from .event_bus import (
    EventBus,
    Event,
    EventHandler,
    create_event_bus,
)

__all__ = [
    # 运行时
    "RuntimeMode",
    "RuntimeConfig",
    "StandaloneRuntime",
    "create_runtime",
    "get_runtime",
    # 本地身份
    "LocalIdentity",
    "create_local_identity",
    "DeviceFingerprint",
    # 本地邮件
    "LocalMailbox",
    "LocalMessage",
    "create_local_mailbox",
    "MessageObserver",
    # 本地 AI
    "LocalAIEngine",
    "create_local_ai_engine",
    "ModelType",
    "AICapability",
    # 本地存储
    "LocalStorage",
    "create_local_storage",
    "StorageScope",
    # 事件总线
    "EventBus",
    "Event",
    "EventHandler",
    "create_event_bus",
]