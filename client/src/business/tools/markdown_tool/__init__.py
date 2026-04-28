"""
Markdown 转换工具模块
"""

from .markdown_converter import MarkdownConverter


def register():
    """注册 Markdown 转换工具"""
    from client.src.business.tools.tool_registry import ToolRegistry
    from client.src.business.tools.tool_definition import ToolDefinition
    
    registry = ToolRegistry.get_instance()
    tool = MarkdownConverter()
    registry.register(ToolDefinition(
        name=tool.name,
        description=tool.description,
        handler=tool.execute,
        parameters=tool.parameters,
        returns=tool.returns,
        category=tool.category,
        tags=["markdown", "converter", "document"]
    ))