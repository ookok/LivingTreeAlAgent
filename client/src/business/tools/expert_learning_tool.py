"""
ExpertLearningSystem Tool Wrapper

Auto-generated BaseTool wrapper for ExpertLearningSystem
"""

from business.tools.base_tool import BaseTool
from business.tools.tool_result import ToolResult
from loguru import logger

try:
    from business.expert_learning.learning_system import ExpertLearningSystem
except ImportError:
    logger.warning(f"Could not import {class_name} from {module_path}")
    ExpertLearningSystem = None


class ExpertLearningSystemTool(BaseTool):
    """
    ExpertLearningSystem 工具包装器
    
    将 ExpertLearningSystem 包装为 BaseTool 子类
    """
    
    def __init__(self):
        super().__init__(
            name="expert_learning",
            description=f"Auto-generated tool wrapper for ExpertLearningSystem",
            category="auto",
            tags=["auto", "expert_learning"]
        )
        
        if ExpertLearningSystem is not None:
            self._instance = ExpertLearningSystem()
        else:
            self._instance = None
        
    def execute(self, **kwargs):
        """
        执行 ExpertLearningSystem
        
        Args:
            **kwargs: 传递给底层模块的参数
            
        Returns:
            ToolResult
        """
        try:
            if self._instance is None:
                return ToolResult.fail(
                    error=f"ExpertLearningSystem module not available",
                    error_code="MODULE_NOT_AVAILABLE"
                )
            
            # 调用主要方法
            if hasattr(self._instance, "learn"):
                method = getattr(self._instance, "learn")
                result = method(**kwargs)
                
                return ToolResult.ok(
                    data=result,
                    message=f"ExpertLearningSystem executed successfully"
                )
            else:
                # 如果没有指定方法，尝试调用实例本身
                result = self._instance(**kwargs) if callable(self._instance) else None
                
                return ToolResult.ok(
                    data=result,
                    message=f"ExpertLearningSystem executed successfully"
                )
                
        except Exception as e:
            logger.error(f"ExpertLearningSystem execution failed: {e}")
            return ToolResult.fail(error=str(e))
    
    def health_check(self) -> bool:
        """健康检查"""
        return self._instance is not None


def register_expert_learning_tool():
    """注册 expert_learning 工具"""
    from business.tools.tool_registry import ToolRegistry
    
    registry = ToolRegistry.get_instance()
    tool = ExpertLearningSystemTool()
    
    try:
        registry.register_tool(tool)
        logger.info(f"Registered tool: {tool.name}")
        return tool.name
    except Exception as e:
        logger.error(f"Failed to register tool {tool.name}: {e}")
        return None


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
        _tool_instance = ExpertLearningSystemTool()
        
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
