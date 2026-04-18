"""
LivingTreeAI Communication - 四层通信协议栈
============================================

架构：
┌─────────────────────────────────────┐
│         应用层 (业务逻辑)            │
├─────────────────────────────────────┤
│         会话层 (MessagePack RPC)     │
├─────────────────────────────────────┤
│     传输层 (WebRTC + TCP + WS)      │
├─────────────────────────────────────┤
│     发现层 (UDP组播 + 中心索引)      │
└─────────────────────────────────────┘

模块：
- discovery/  : 节点发现与寻址
- transport/  : 跨平台连接建立
- session/    : 消息路由与RPC
- security/  : 端到端加密

Author: LivingTreeAI Community
License: Apache 2.0
"""

__version__ = "1.0.0"

# 核心组件
from .discovery import (
    NodeDiscovery,
    DiscoveryResult,
    DiscoveredNode,
    DiscoveryType,
    get_discovery,
)
from .transport import (
    NodeConnection,
    ConnectionStrategy,
    TransportType,
    NodeEndpoint,
    ConnectionInfo,
    get_transport,
)
from .session import (
    NodeRPCServer,
    NodeRPCClient,
    MessageRouter,
    RPCRequest,
    RPCResponse,
    RPCError,
    get_rpc_server,
)
from .security import (
    NoiseProtocol,
    SecurityContext,
    SecureChannel,
    get_security,
)
from .server_main import (
    LifeTreeServer,
    LifeTreeClient,
    ServerConfig,
    start_server,
)

__all__ = [
    # 版本
    "__version__",
    # 发现层
    "NodeDiscovery",
    "DiscoveryResult",
    "DiscoveredNode",
    "DiscoveryType",
    "get_discovery",
    # 传输层
    "NodeConnection",
    "ConnectionStrategy",
    "TransportType",
    "NodeEndpoint",
    "ConnectionInfo",
    "get_transport",
    # 会话层
    "NodeRPCServer",
    "NodeRPCClient",
    "MessageRouter",
    "RPCRequest",
    "RPCResponse",
    "RPCError",
    "get_rpc_server",
    # 安全层
    "NoiseProtocol",
    "SecurityContext",
    "SecureChannel",
    "get_security",
    # 服务端
    "LifeTreeServer",
    "LifeTreeClient",
    "ServerConfig",
    "start_server",
]