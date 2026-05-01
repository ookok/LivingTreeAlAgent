"""
MCP服务独立架构 (Model Context Protocol)

核心能力：
1. MCP服务管理 - 统一管理外部工具服务
2. 服务注册与发现 - 自动发现可用服务
3. 平滑降级 - 无MCP时优雅降级
4. 服务隔离 - 故障隔离机制

架构设计：
- MCP服务作为独立进程运行
- 主应用通过IPC/RPC调用
- 支持多种通信协议（本地、网络）
- 自动重试和故障转移
"""

from .mcp_interface import MCPInterface, MCPTool, MCPResult
from .mcp_client import MCPClient, ServiceStatus
from .mcp_manager import MCPManager, get_mcp_manager
from .fallback_system import FallbackSystem, FallbackStrategy
from .service_registry import ServiceRegistry, ServiceInfo

__all__ = [
    # 接口定义
    'MCPInterface',
    'MCPTool',
    'MCPResult',
    
    # 客户端
    'MCPClient',
    'ServiceStatus',
    
    # 管理器
    'MCPManager',
    'get_mcp_manager',
    
    # 降级系统
    'FallbackSystem',
    'FallbackStrategy',
    
    # 服务注册
    'ServiceRegistry',
    'ServiceInfo',
]


def call_mcp_tool(tool_name: str, **kwargs) -> dict:
    """
    统一MCP工具调用接口
    
    Args:
        tool_name: 工具名称
        **kwargs: 工具参数
    
    Returns:
        调用结果
    """
    manager = get_mcp_manager()
    return manager.call_tool(tool_name, **kwargs)