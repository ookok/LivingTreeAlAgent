"""
深度集成层 - 向后兼容层

⚠️ 已迁移至 livingtree.core.integration
本模块保留为兼容层，所有导入将自动重定向到新位置。
"""

from livingtree.core.integration import (
    EventBus, Event, EventType, get_event_bus, subscribe, publish,
    CrossSystemCaller, get_cross_system_caller, cross_system_call,
    ContextManager, SessionContext, get_context_manager,
    IntegrationCoordinator, WorkflowInstance, WorkflowStep, WorkflowStatus,
    get_integration_coordinator,
    UnifiedServiceManager, ServiceIntegration, ServiceStatus, ServiceInfo,
)

__all__ = [
    'EventBus', 'Event', 'EventType', 'get_event_bus', 'subscribe', 'publish',
    'CrossSystemCaller', 'get_cross_system_caller', 'cross_system_call',
    'ContextManager', 'SessionContext', 'get_context_manager',
    'IntegrationCoordinator', 'WorkflowInstance', 'WorkflowStep', 'WorkflowStatus',
    'get_integration_coordinator',
    'UnifiedServiceManager', 'ServiceIntegration', 'ServiceStatus', 'ServiceInfo',
]
