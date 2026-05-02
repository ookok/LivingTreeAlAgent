"""
集成层 (Integration Layer)

系统间协作基础设施:
1. 事件总线 (EventBus) - 发布/订阅模式
2. 跨系统调用器 (CrossSystemCaller) - 子系统方法调用
3. 上下文管理器 (ContextManager) - 会话与全局上下文
4. 集成协调器 (IntegrationCoordinator) - 工作流编排
5. 服务管理器 (UnifiedServiceManager) - 服务生命周期
6. 系统管理器 (SystemManager) - 子系统统一管理
"""

from .event_bus import (
    EventBus, Event, EventType,
    get_event_bus, subscribe, publish,
)

from .cross_system_caller import (
    CrossSystemCaller,
    get_cross_system_caller,
    cross_system_call,
)

from .context_manager import (
    ContextManager, SessionContext,
    get_context_manager,
)

from .integration_coordinator import (
    IntegrationCoordinator,
    WorkflowInstance, WorkflowStep, WorkflowStatus,
    get_integration_coordinator,
)

from .service_manager import (
    UnifiedServiceManager, ServiceIntegration,
    ServiceStatus, ServiceInfo,
)

from .system_manager import (
    SystemManager, SystemState as SysState, SubsystemInfo,
    get_system_manager,
)

__all__ = [
    "EventBus", "Event", "EventType", "get_event_bus", "subscribe", "publish",
    "CrossSystemCaller", "get_cross_system_caller", "cross_system_call",
    "ContextManager", "SessionContext", "get_context_manager",
    "IntegrationCoordinator", "WorkflowInstance", "WorkflowStep", "WorkflowStatus",
    "get_integration_coordinator",
    "UnifiedServiceManager", "ServiceIntegration", "ServiceStatus", "ServiceInfo",
    "SystemManager", "SysState", "SubsystemInfo", "get_system_manager",
]
