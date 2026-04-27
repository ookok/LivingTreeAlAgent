"""
KBAutoIngest Tool Wrapper

Auto-generated BaseTool wrapper for KBAutoIngest
"""

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from loguru import logger

try:
    from client.src.business.knowledge_auto_ingest import KBAutoIngest
except ImportError:
    logger.warning(f"Could not import {class_name} from {module_path}")
    KBAutoIngest = None


class KBAutoIngestTool(BaseTool):
    """
    KBAutoIngest 工具包装器
    
    将 KBAutoIngest 包装为 BaseTool 子类
    """
    
    def __init__(self):
        super().__init__(
            name="kb_auto_ingest",
            description=f"Auto-generated tool wrapper for KBAutoIngest",
            category="auto",
            tags=["auto", "kb_auto_ingest"]
        )
        
        if KBAutoIngest is not None:
            self._instance = KBAutoIngest()
        else:
            self._instance = None
        
    def execute(self, **kwargs):
        """
        执行 KBAutoIngest
        
        Args:
            **kwargs: 传递给底层模块的参数
            
        Returns:
            ToolResult
        """
        try:
            if self._instance is None:
                return ToolResult.fail(
                    error=f"KBAutoIngest module not available",
                    error_code="MODULE_NOT_AVAILABLE"
                )
            
            # 调用主要方法
            if hasattr(self._instance, "ingest"):
                method = getattr(self._instance, "ingest")
                result = method(**kwargs)
                
                return ToolResult.ok(
                    data=result,
                    message=f"KBAutoIngest executed successfully"
                )
            else:
                # 如果没有指定方法，尝试调用实例本身
                result = self._instance(**kwargs) if callable(self._instance) else None
                
                return ToolResult.ok(
                    data=result,
                    message=f"KBAutoIngest executed successfully"
                )
                
        except Exception as e:
            logger.error(f"KBAutoIngest execution failed: {e}")
            return ToolResult.fail(error=str(e))
    
    def health_check(self) -> bool:
        """健康检查"""
        return self._instance is not None


def register_kb_auto_ingest_tool():
    """注册 kb_auto_ingest 工具"""
    from client.src.business.tools.tool_registry import ToolRegistry
    
    registry = ToolRegistry.get_instance()
    tool = KBAutoIngestTool()
    
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
        _tool_instance = KBAutoIngestTool()
        
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
