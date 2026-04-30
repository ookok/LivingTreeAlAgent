"""
VectorDatabaseTool - Vector database tool wrapper
"""

from business.tools.base_tool import BaseTool
from business.tools.tool_result import ToolResult
from business.knowledge_vector_db import VectorDatabase


class VectorDatabaseTool(BaseTool):
    """Vector database tool"""
    
    def __init__(self):
        super().__init__(
            name="vector_database",
            description="Vector database tool for similarity search and storage",
            category="storage",
            tags=["vector", "database", "search"]
        )
        self._db = VectorDatabase()
    
    def execute(self, operation="search", **kwargs):
        try:
            if operation == "search":
                result = self._db.search(**kwargs)
                return ToolResult.ok(data=result, message="Search completed")
            elif operation == "add":
                result = self._db.add(**kwargs)
                return ToolResult.ok(data=result, message="Added to database")
            else:
                return ToolResult.fail(error=f"Unknown operation: {operation}")
        except Exception as e:
            return ToolResult.fail(error=str(e))


def register_vector_database_tool():
    """Register vector database tool"""
    from business.tools.tool_registry import ToolRegistry
    registry = ToolRegistry.get_instance()
    tool = VectorDatabaseTool()
    registry.register_tool(tool)
    return tool.name


# =============================================================================
# Auto-Registration
# =============================================================================

_registration_done = False

def _auto_register():
    """自动注册工具到 ToolRegistry"""
    global _registration_done
    
    if _registration_done:
        return
    
    try:
        # 创建工具实例
        _tool_instance = VectorDatabaseTool()
        
        # 获取 ToolRegistry 单例
        from business.tools.tool_registry import ToolRegistry
        _registry = ToolRegistry.get_instance()
        
        # 注册工具
        success = _registry.register_tool(_tool_instance)
        
        if success:
            import loguru
            loguru.logger.info(f"Auto-registered: {_tool_instance.name}")
        else:
            import loguru
            loguru.logger.warning(f"Auto-registration failed (tool already exists): {_tool_instance.name}")
        
        _registration_done = True
        
    except Exception as e:
        import loguru
        loguru.logger.error(f"Auto-registration error: {e}")


# 执行自动注册
_auto_register()
