"""
MarkItDown Converter Tool

HTML/PDF/DOCX → Markdown 转换器
"""

from business.tools.base_tool import BaseTool
from business.tools.tool_result import ToolResult
from loguru import logger


class MarkItDownTool(BaseTool):
    """
    MarkItDown 转换器工具
    
    将 HTML/PDF/DOCX 文档转换为 Markdown 格式
    """
    
    def __init__(self):
        super().__init__(
            name="markitdown_converter",
            description="Convert HTML/PDF/DOCX to Markdown format",
            category="document",
            tags=["document", "markdown", "converter"]
        )
        self._converter = None
        
    def _get_converter(self):
        """延迟加载转换器"""
        if self._converter is None:
            try:
                from markitdown import MarkItDown
                self._converter = MarkItDown()
            except ImportError:
                logger.warning("markitdown not installed, using basic converter")
                self._converter = BasicMarkdownConverter()
        return self._converter
    
    def execute(self, **kwargs):
        """
        执行转换
        
        Args:
            file_path: 文件路径
            output_format: 输出格式（默认 markdown）
            
        Returns:
            ToolResult
        """
        try:
            file_path = kwargs.get("file_path")
            if not file_path:
                return ToolResult.fail(error="file_path is required")
            
            converter = self._get_converter()
            
            # 执行转换
            if hasattr(converter, "convert"):
                result = converter.convert(file_path)
            else:
                # 基本转换逻辑
                result = self._basic_convert(file_path)
            
            return ToolResult.ok(
                data={"markdown": result, "file_path": file_path},
                message=f"File converted successfully: {file_path}"
            )
            
        except Exception as e:
            logger.error(f"MarkItDown conversion failed: {e}")
            return ToolResult.fail(error=str(e))
    
    def _basic_convert(self, file_path: str) -> str:
        """基本转换（fallback）"""
        # 简单实现，实际应调用 markitdown 库
        return f"# Converted from {file_path}\n\nContent conversion not fully implemented."
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            converter = self._get_converter()
            return converter is not None
        except Exception:
            return False


class BasicMarkdownConverter:
    """基本 Markdown 转换器（fallback）"""
    
    def convert(self, file_path: str) -> str:
        """转换文件为 Markdown"""
        # 简单读取文本文件
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content


def register_markitdown_tool():
    """注册 markitdown_converter 工具"""
    from business.tools.tool_registry import ToolRegistry
    
    registry = ToolRegistry.get_instance()
    tool = MarkItDownTool()
    registry.register_tool(tool)
    
    logger.info(f"Registered tool: {tool.name}")
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
        _tool_instance = MarkItDownTool()
        
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
