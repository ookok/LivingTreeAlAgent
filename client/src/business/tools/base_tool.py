"""
BaseTool - 工具抽象基类
所有工具必须继承此类
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from loguru import logger

from client.src.business.tools.tool_definition import ToolDefinition
from client.src.business.tools.tool_result import ToolResult


class BaseTool(ABC):
    """
    工具抽象基类
    
    所有工具必须继承此类，并实现 execute 方法。
    
    示例：
        class WebSearchTool(BaseTool):
            def __init__(self):
                super().__init__(
                    name="web_search",
                    description="网络搜索工具"
                )
            
            def execute(self, query: str, **kwargs) -> ToolResult:
                # 实现搜索逻辑
                return ToolResult(success=True, data=...)
    """
    
    def __init__(self, name: str, description: str, **kwargs):
        """
        初始化工具
        
        Args:
            name: 工具名称
            description: 工具描述
            **kwargs: 传递给 ToolDefinition 的其他参数
        """
        self._definition = ToolDefinition(
            name=name,
            description=description,
            handler=self.execute,
            **kwargs
        )
        self._logger = logger.bind(tool=name)
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> ToolResult:
        """
        执行工具（子类必须实现）
        
        Returns:
            ToolResult 对象
        """
        pass
    
    @property
    def definition(self) -> ToolDefinition:
        """获取工具定义"""
        return self._definition
    
    @property
    def name(self) -> str:
        """工具名称"""
        return self._definition.name
    
    @property
    def description(self) -> str:
        """工具描述"""
        return self._definition.description
    
    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, str]:
        """
        验证参数（可被子类覆盖）
        
        Args:
            params: 参数字典
            
        Returns:
            (is_valid, error_message)
        """
        return self._definition.validate_params(params)
    
    def before_execute(self, *args, **kwargs):
        """
        执行前钩子（可被子类覆盖）
        
        用于参数验证、日志记录、权限检查等
        """
        self._logger.info(f"执行工具: {self.name}, 参数: {kwargs}")
    
    def after_execute(self, result: ToolResult, *args, **kwargs):
        """
        执行后钩子（可被子类覆盖）
        
        用于结果处理、日志记录、缓存等
        """
        if result.success:
            self._logger.info(f"工具执行成功: {self.name}")
        else:
            self._logger.error(f"工具执行失败: {self.name}, 错误: {result.error}")
    
    def __call__(self, *args, **kwargs) -> ToolResult:
        """
        使工具可调用
        
        自动触发 before_execute 和 after_execute 钩子
        """
        try:
            # 参数验证
            if kwargs:
                is_valid, error_msg = self.validate_params(kwargs)
                if not is_valid:
                    return ToolResult(success=False, error=error_msg)
            
            # 执行前钩子
            self.before_execute(*args, **kwargs)
            
            # 执行工具
            result = self.execute(*args, **kwargs)
            
            # 执行后钩子
            self.after_execute(result, *args, **kwargs)
            
            return result
        
        except Exception as e:
            self._logger.exception(f"工具执行异常: {self.name}")
            return ToolResult(success=False, error=str(e))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self._definition.to_dict()
    
    def __repr__(self):
        return f"<Tool name='{self.name}' desc='{self.description[:30]}...'>"
