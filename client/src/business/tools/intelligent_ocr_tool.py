"""
OCREngine Tool Wrapper

Auto-generated BaseTool wrapper for OCREngine
"""

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult
from loguru import logger

try:
    from client.src.business.intelligent_ocr.ocr_engine import OCREngine
except ImportError:
    logger.warning(f"Could not import {class_name} from {module_path}")
    OCREngine = None


class OCREngineTool(BaseTool):
    """
    OCREngine 工具包装器
    
    将 OCREngine 包装为 BaseTool 子类
    """
    
    def __init__(self):
        super().__init__(
            name="intelligent_ocr",
            description=f"Auto-generated tool wrapper for OCREngine",
            category="auto",
            tags=["auto", "intelligent_ocr"]
        )
        
        if OCREngine is not None:
            self._instance = OCREngine()
        else:
            self._instance = None
        
    def execute(self, **kwargs):
        """
        执行 OCREngine
        
        Args:
            **kwargs: 传递给底层模块的参数
            
        Returns:
            ToolResult
        """
        try:
            if self._instance is None:
                return ToolResult.fail(
                    error=f"OCREngine module not available",
                    error_code="MODULE_NOT_AVAILABLE"
                )
            
            # 调用主要方法
            if hasattr(self._instance, "recognize"):
                method = getattr(self._instance, "recognize")
                result = method(**kwargs)
                
                return ToolResult.ok(
                    data=result,
                    message=f"OCREngine executed successfully"
                )
            else:
                # 如果没有指定方法，尝试调用实例本身
                result = self._instance(**kwargs) if callable(self._instance) else None
                
                return ToolResult.ok(
                    data=result,
                    message=f"OCREngine executed successfully"
                )
                
        except Exception as e:
            logger.error(f"OCREngine execution failed: {e}")
            return ToolResult.fail(error=str(e))
    
    def health_check(self) -> bool:
        """健康检查"""
        return self._instance is not None


def register_intelligent_ocr_tool():
    """注册 intelligent_ocr 工具"""
    from client.src.business.tools.tool_registry import ToolRegistry
    
    registry = ToolRegistry.get_instance()
    tool = OCREngineTool()
    
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
        _tool_instance = OCREngineTool()
        
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
