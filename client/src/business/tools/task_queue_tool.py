"""
TaskQueueTool - Task queue tool wrapper
"""

from business.tools.base_tool import BaseTool
from business.tools.tool_result import ToolResult
from business.task_queue import TaskQueue


class TaskQueueTool(BaseTool):
    """Task queue tool"""
    
    def __init__(self):
        super().__init__(
            name="task_queue",
            description="Task queue management tool",
            category="task",
            tags=["task", "queue", "management"]
        )
        self._queue = TaskQueue()
    
    def execute(self, operation="add", **kwargs):
        try:
            if operation == "add":
                result = self._queue.add(**kwargs)
                return ToolResult.ok(data=result, message="Task added to queue")
            elif operation == "get":
                result = self._queue.get(**kwargs)
                return ToolResult.ok(data=result, message="Task retrieved")
            elif operation == "update":
                result = self._queue.update(**kwargs)
                return ToolResult.ok(data=result, message="Task updated")
            else:
                return ToolResult.fail(error=f"Unknown operation: {operation}")
        except Exception as e:
            return ToolResult.fail(error=str(e))


def register_task_queue_tool():
    """Register task queue tool"""
    from business.tools.tool_registry import ToolRegistry
    registry = ToolRegistry.get_instance()
    tool = TaskQueueTool()
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
        _tool_instance = TaskQueueTool()
        
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
