"""
MCP接口定义 - MCP Interface Definition

功能：
1. 定义MCP工具接口
2. 工具注册机制
3. 结果格式规范
"""

import logging
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ToolType(Enum):
    """工具类型"""
    SEARCH = "search"
    CALCULATOR = "calculator"
    FILE = "file"
    BROWSER = "browser"
    CODE = "code"
    DATABASE = "database"
    API = "api"
    OTHER = "other"


@dataclass
class MCPTool:
    """MCP工具定义"""
    name: str
    description: str
    tool_type: ToolType
    parameters: List[Dict]
    return_type: str = "json"
    requires_mcp: bool = True
    fallback_available: bool = False
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'description': self.description,
            'tool_type': self.tool_type.value,
            'parameters': self.parameters,
            'return_type': self.return_type,
            'requires_mcp': self.requires_mcp,
            'fallback_available': self.fallback_available
        }


@dataclass
class MCPResult:
    """MCP调用结果"""
    success: bool
    content: Any
    tool_name: str = ""
    error: str = ""
    execution_time: float = 0.0
    metadata: Dict = None
    used_fallback: bool = False
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'content': self.content,
            'tool_name': self.tool_name,
            'error': self.error,
            'execution_time': self.execution_time,
            'metadata': self.metadata,
            'used_fallback': self.used_fallback
        }


class MCPInterface:
    """
    MCP接口基类
    
    所有MCP工具都应实现此接口
    """
    
    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}
    
    def register_tool(self, tool: MCPTool):
        """注册工具"""
        self._tools[tool.name] = tool
        logger.info(f"注册MCP工具: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[MCPTool]:
        """获取工具定义"""
        return self._tools.get(name)
    
    def get_all_tools(self) -> List[MCPTool]:
        """获取所有工具"""
        return list(self._tools.values())
    
    def call_tool(self, tool_name: str, **kwargs) -> MCPResult:
        """
        调用工具（需要子类实现）
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
        
        Returns:
            调用结果
        """
        raise NotImplementedError("子类必须实现call_tool方法")
    
    def get_tool_info(self, name: str) -> Dict:
        """获取工具信息"""
        tool = self.get_tool(name)
        if tool:
            return tool.to_dict()
        return {}
    
    def get_tools_by_type(self, tool_type: ToolType) -> List[MCPTool]:
        """按类型获取工具"""
        return [t for t in self._tools.values() if t.tool_type == tool_type]
    
    def is_tool_available(self, tool_name: str) -> bool:
        """检查工具是否可用"""
        tool = self.get_tool(tool_name)
        return tool is not None