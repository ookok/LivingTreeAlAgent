"""
统一工具注册入口
整合新旧两个 ToolRegistry 系统

- 新系统 (tools/tool_registry.py): BaseTool 架构，支持分类/标签/语义搜索
- 旧系统 (tools_registry.py): 简单轻量，用于 Agent 函数调用

本模块提供统一的访问入口
"""

from client.src.business.tools.tool_registry import ToolRegistry

# 为了向后兼容，提供与旧系统相同的 API
from client.src.business.tools.tool_registry import (
    ToolRegistry as _NewToolRegistry,
    ToolDefinition,
    ToolResult,
    BaseTool,
)

# ── 兼容性别名 ────────────────────────────────────────────────────────

class CompatibleToolRegistry(_NewToolRegistry):
    """
    兼容新旧两个系统的统一工具注册中心
    
    新增功能：
    - 与旧 tools_registry.py 完全兼容
    - 支持 @tool 装饰器
    - 支持 OpenAI tools schema 导出
    - 支持工具集 (toolset) 概念
    """
    
    _toolsets: dict[str, set[str]] = {}
    
    @classmethod
    def register(
        cls,
        name: str,
        description: str,
        parameters: dict,
        handler,
        toolset: str = "core",
    ):
        """
        注册工具（兼容旧系统 API）
        
        Args:
            name: 工具名称
            description: 工具描述
            parameters: JSON Schema 格式的参数定义
            handler: 处理函数
            toolset: 工具集名称
        """
        instance = cls.get_instance()
        
        # 创建兼容的工具
        from client.src.business.tools.tool_definition import ToolDefinition as TD
        
        definition = TD(
            name=name,
            description=description,
            handler=handler,
            category="general",
            tags=[toolset],
        )
        
        # 注册到新系统
        instance._tools[name] = _CompatibleTool(name, description, definition, handler)
        
        # 更新工具集索引
        if not hasattr(cls, '_toolsets'):
            cls._toolsets = {}
        cls._toolsets.setdefault(toolset, set()).add(name)
        
        # 更新分类索引
        instance._categories.setdefault("general", []).append(name)
    
    @classmethod
    def get(cls, name: str):
        """获取工具定义"""
        instance = cls.get_instance()
        tool = instance.get_tool(name)
        if tool:
            return _CompatibleToolDef(
                name=tool.name,
                description=tool.definition.description,
                parameters=tool.definition.parameters or {},
                handler=tool.definition.handler,
                toolset=tool.definition.tags[0] if tool.definition.tags else "core",
            )
        return None
    
    @classmethod
    def get_by_toolset(cls, toolset: str):
        """按工具集获取工具"""
        if not hasattr(cls, '_toolsets'):
            return []
        names = cls._toolsets.get(toolset, set())
        return [cls.get(name) for name in names if cls.get(name)]
    
    @classmethod
    def get_all_tools(cls, enabled: list = None) -> list:
        """获取所有工具"""
        instance = cls.get_instance()
        tools = instance.list_tools()
        if enabled:
            # 按工具集过滤
            if not hasattr(cls, '_toolsets'):
                return tools
            result = []
            for ts in enabled:
                for name in cls._toolsets.get(ts, set()):
                    tool = cls.get(name)
                    if tool:
                        result.append(tool)
            return result
        return [cls.get(t.name) for t in tools]
    
    @classmethod
    def to_openai_schema(cls, tools: list) -> list:
        """转换为 OpenAI tools schema"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
            }
            for t in tools if t
        ]
    
    @classmethod
    def get_all_names(cls) -> list[str]:
        """获取所有工具名称"""
        instance = cls.get_instance()
        return list(instance._tools.keys())


class _CompatibleToolDef:
    """兼容旧系统的工具定义"""
    def __init__(self, name, description, parameters, handler, toolset="core"):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self.toolset = toolset


class _CompatibleTool:
    """兼容旧系统的工具实例"""
    def __init__(self, name, description, definition, handler):
        self.name = name
        self.definition = definition
        self._handler = handler
    
    def __call__(self, *args, **kwargs):
        return self._handler(*args, **kwargs)


# ── @tool 装饰器 ──────────────────────────────────────────────────────

def tool(name: str, description: str, parameters: dict, toolset: str = "core"):
    """
    工具注册装饰器（兼容旧系统）
    
    用法：
        @tool(
            name="my_tool",
            description="我的工具",
            parameters={"type": "object", "properties": {...}},
            toolset="custom"
        )
        def my_tool_handler(context, **args):
            return "result"
    """
    def decorator(func):
        CompatibleToolRegistry.register(
            name=name,
            description=description,
            parameters=parameters,
            handler=func,
            toolset=toolset,
        )
        return func
    return decorator


# ── 全局实例兼容 ────────────────────────────────────────────────────────

# 为了向后兼容，提供全局别名
ToolRegistry = CompatibleToolRegistry


# ── 便捷函数 ────────────────────────────────────────────────────────────

def get_registry() -> ToolRegistry:
    """获取统一工具注册中心"""
    return ToolRegistry.get_instance()


def register_tool(tool_instance: BaseTool) -> bool:
    """注册 BaseTool 实例"""
    return ToolRegistry.get_instance().register_tool(tool_instance)


def execute_tool(name: str, *args, **kwargs) -> ToolResult:
    """执行工具"""
    return ToolRegistry.get_instance().execute_tool(name, *args, **kwargs)


def search_tools(query: str) -> list:
    """搜索工具"""
    return ToolRegistry.get_instance().search_tools(query)


def list_all_tools(category: str = None) -> list:
    """列出工具"""
    return ToolRegistry.get_instance().list_tools(category)


def get_stats() -> dict:
    """获取统计信息"""
    return ToolRegistry.get_instance().stats()
