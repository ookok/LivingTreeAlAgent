"""
深度集成层 - Deep Integration Layer

功能：
1. 系统间事件总线
2. 跨系统调用机制
3. 数据共享与同步
4. 智能协调与决策
5. 统一上下文管理

核心能力：
- 事件驱动架构
- 跨系统数据流转
- 智能决策协调
- 上下文感知路由
"""

from .event_bus import EventBus, Event, EventType, subscribe, publish
from .cross_system_caller import CrossSystemCaller, get_cross_system_caller
from .context_manager import ContextManager, get_context_manager
from .integration_coordinator import IntegrationCoordinator, get_integration_coordinator
from .service_manager import UnifiedServiceManager, ServiceIntegration, ServiceStatus, ServiceInfo

__all__ = [
    # 事件总线
    'EventBus',
    'Event',
    'EventType',
    'subscribe',
    'publish',
    
    # 跨系统调用
    'CrossSystemCaller',
    'get_cross_system_caller',
    
    # 上下文管理
    'ContextManager',
    'get_context_manager',
    
    # 集成协调器
    'IntegrationCoordinator',
    'get_integration_coordinator',
    
    # 服务管理
    'UnifiedServiceManager',
    'ServiceIntegration',
    'ServiceStatus',
    'ServiceInfo',
]