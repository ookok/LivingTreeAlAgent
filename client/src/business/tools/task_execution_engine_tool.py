"""
TaskExecutionEngineTool - Task execution engine tool wrapper
"""

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from client.src.business.task_execution_engine import TaskExecutionEngine


class TaskExecutionEngineTool(BaseTool):
    """Task execution engine tool"""
    
    def __init__(self):
        super().__init__(
            name="task_execution_engine",
            description="Task execution engine for running tasks",
            category="task",
            tags=["task", "execution", "engine"]
        )
        self._engine = TaskExecutionEngine()
    
    def execute(self, task_id=None, **kwargs):
        try:
            if task_id:
                result = self._engine.execute(task_id=task_id)
            else:
                result = self._engine.execute(**kwargs)
            return ToolResult.ok(data=result, message="Task executed successfully")
        except Exception as e:
            return ToolResult.fail(error=str(e))


def register_task_execution_engine_tool():
    """Register task execution engine tool"""
    from client.src.business.tools.tool_registry import ToolRegistry
    registry = ToolRegistry.get_instance()
    tool = TaskExecutionEngineTool()
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
        _tool_instance = TaskExecutionEngineTool()
        
        # 获取 ToolRegistry 单例
        from client.src.business.tools.tool_registry import ToolRegistry
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
