"""
Tools Package - 统一工具层

导出所有核心类，方便导入：
    from client.src.business.tools import ToolRegistry, BaseTool, ToolDefinition, ToolResult
    
也支持从 unified_tool_registry 导入兼容 API：
    from client.src.business.unified_tool_registry import tool, ToolRegistry
"""

from client.src.business.tools.tool_result import ToolResult
from client.src.business.tools.tool_definition import ToolDefinition
from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_registry import ToolRegistry
from client.src.business.tools.registrar import ToolRegistrar, auto_register_all, register_tool

# 便捷访问：获取 ToolRegistry 单例
def get_registry() -> ToolRegistry:
    """获取 ToolRegistry 单例"""
    return ToolRegistry.get_instance()

# 版本信息
__version__ = "1.0.0"
__all__ = [
    "ToolResult",
    "ToolDefinition", 
    "BaseTool",
    "ToolRegistry",
    "ToolRegistrar",
    "auto_register_all",
    "register_tool",
    "get_registry"
]
