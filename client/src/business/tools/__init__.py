"""
统一工具层

提供统一的工具注册、发现、调用接口。

核心组件：
- ToolRegistry: 工具注册中心（单例）
- BaseTool: 工具基类
- ToolDefinition: 工具定义数据类
- ToolResult: 工具执行结果数据类
- registrar: 统一注册入口
- SemanticSearchEngine: 语义搜索引擎
- ToolPermissionManager: 工具权限管理器
- ToolMonitor: 工具监控器

使用方式：
```python
from client.src.business.tools import ToolRegistry, BaseTool

# 获取工具注册中心
registry = ToolRegistry.get_instance()

# 发现工具
tools = registry.discover("搜索")

# 执行工具
result = await registry.execute("web_crawler", url="https://example.com")
```
"""

from .tool_registry import ToolRegistry, ToolDefinition, ToolResult
from .base_tool import BaseTool
from .registrar import register_all_tools, register_tool
from .semantic_search import SemanticSearchEngine
from .tool_permissions import (
    ToolPermissionManager,
    ToolPermission,
    AgentIdentity,
    PermissionLevel,
    AgentRole
)
from .tool_monitor import (
    ToolMonitor,
    ToolCallRecord,
    ToolStatistics
)

__all__ = [
    # 核心组件
    "ToolRegistry",
    "ToolDefinition",
    "ToolResult",
    "BaseTool",
    
    # 注册函数
    "register_all_tools",
    "register_tool",
    
    # 语义搜索
    "SemanticSearchEngine",
    
    # 权限控制
    "ToolPermissionManager",
    "ToolPermission",
    "AgentIdentity",
    "PermissionLevel",
    "AgentRole",
    
    # 监控统计
    "ToolMonitor",
    "ToolCallRecord",
    "ToolStatistics"
]