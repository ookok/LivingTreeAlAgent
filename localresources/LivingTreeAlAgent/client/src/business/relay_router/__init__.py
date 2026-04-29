"""
智能中继路由系统 (Smart Relay Router)
=====================================

三层混合网络架构：
1. 公共基础设施层（零成本）- 野狗信令/腾讯STUN/GoodLink TURN
2. 私有服务器增强层 - 可选的P2P信令/TURN/业务API
3. Hermes Agent智能路由层 - 自动选择最佳路径

Author: Hermes Desktop AI Assistant
"""

from .relay_config import (
    RelayEndpoint,
    RelayType,
    ConnectionType,
    RelayConfig,
    get_relay_config,
)

from .health_monitor import (
    RelayHealthStatus,
    RelayHealthMonitor,
    get_health_monitor,
)

from .smart_router import (
    RelayPath,
    PathScore,
    SmartRelayRouter,
    get_smart_router,
)

from .connection_manager import (
    ConnectionState,
    ConnectionStateMachine,
    get_connection_manager,
)

__all__ = [
    # 配置
    'RelayEndpoint',
    'RelayType',
    'ConnectionType',
    'RelayConfig',
    'get_relay_config',

    # 健康监控
    'RelayHealthStatus',
    'RelayHealthMonitor',
    'get_health_monitor',

    # 智能路由
    'RelayPath',
    'PathScore',
    'SmartRelayRouter',
    'get_smart_router',

    # 连接管理
    'ConnectionState',
    'ConnectionStateMachine',
    'get_connection_manager',
]

__version__ = '1.0.0'