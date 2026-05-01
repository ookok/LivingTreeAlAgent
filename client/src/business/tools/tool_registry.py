"""
ToolRegistry - 工具注册中心

统一管理所有工具的注册、发现和调用。

遵循自我进化原则：
- 支持语义搜索发现工具
- 自动检测工具变更
- 支持动态注册新工具
"""

from typing import Dict, List, Optional, Callable, Any, Type, ClassVar
from dataclasses import dataclass, field
from loguru import logger
import json


class BaseTool:
    """
    工具基类
    
    所有自定义工具应继承此类。
    """
    
    name: ClassVar[str] = "base_tool"
    description: ClassVar[str] = "基础工具"
    category: ClassVar[str] = "general"
    
    def __init__(self):
        self.logger = logger.bind(component=f"Tool.{self.name}")
    
    async def execute(self, **kwargs) -> Any:
        """
        执行工具
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            执行结果
        """
        raise NotImplementedError("子类必须实现 execute 方法")
    
    def get_schema(self) -> Dict[str, Any]:
        """
        获取工具的 JSON Schema 定义
        
        Returns:
            JSON Schema 字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": {}
        }


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    handler: Callable
    parameters: Dict[str, str]
    returns: str
    category: str
    version: str = "1.0"
    author: str = "system"


@dataclass
class ToolResult:
    """
    工具执行结果
    
    遵循强制验证原则：
    - success=False 时必须提供 error
    - success=True 时必须提供 evidence（验证证据）
    - 不允许以"看起来没问题"作为完成标准
    """
    success: bool
    data: Any
    error: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    anti_rationalization_check: Optional[Dict[str, Any]] = None
    
    @classmethod
    def success_result(cls, data: Any, evidence: Optional[Dict[str, Any]] = None):
        """创建成功结果（必须提供验证证据）"""
        return cls(success=True, data=data, evidence=evidence)
    
    @classmethod
    def error_result(cls, error: str, evidence: Optional[Dict[str, Any]] = None):
        """创建失败结果"""
        return cls(success=False, data=None, error=error, evidence=evidence)
    
    def validate(self) -> Optional[str]:
        """验证结果是否合法"""
        if not self.success:
            if not self.error:
                return "失败结果必须提供 error 信息"
            return None
        
        if not self.evidence:
            return "成功结果必须提供 evidence（验证证据），不允许仅凭主观判断"
        
        if self.anti_rationalization_check:
            if self.anti_rationalization_check.get("triggered_patterns"):
                return f"检测到反合理化模式: {', '.join(self.anti_rationalization_check['triggered_patterns'])}"
        
        return None


class ToolRegistry:
    """
    工具注册中心（单例模式）
    
    功能：
    1. 注册工具
    2. 发现工具（语义搜索）
    3. 执行工具
    4. 管理工具生命周期
    """
    
    _instance = None
    _tools: Dict[str, ToolDefinition] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._logger = logger.bind(component="ToolRegistry")
            cls._instance._tools = {}
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> 'ToolRegistry':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register(self, tool_def: ToolDefinition):
        """注册工具"""
        self._tools[tool_def.name] = tool_def
        self._logger.info(f"已注册工具: {tool_def.name}")
    
    def unregister(self, tool_name: str):
        """注销工具"""
        if tool_name in self._tools:
            del self._tools[tool_name]
            self._logger.info(f"已注销工具: {tool_name}")
    
    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        """获取工具定义"""
        return self._tools.get(tool_name)
    
    def list_tools(self) -> List[ToolDefinition]:
        """列出所有工具"""
        return list(self._tools.values())
    
    def list_tools_by_category(self, category: str) -> List[ToolDefinition]:
        """按类别列出工具"""
        return [t for t in self._tools.values() if t.category == category]
    
    def discover(self, query: str) -> List[ToolDefinition]:
        """
        发现工具（语义搜索）
        
        Args:
            query: 搜索查询词
            
        Returns:
            相关工具列表（按相关性排序）
        """
        results = []
        
        for tool in self._tools.values():
            # 简单的关键词匹配（可扩展为语义搜索）
            score = 0
            
            # 匹配工具名称
            if query.lower() in tool.name.lower():
                score += 3
            
            # 匹配工具描述
            if query.lower() in tool.description.lower():
                score += 2
            
            # 匹配参数
            for param_name in tool.parameters.keys():
                if query.lower() in param_name.lower():
                    score += 1
            
            # 匹配类别
            if query.lower() in tool.category.lower():
                score += 1
            
            if score > 0:
                results.append((tool, score))
        
        # 按相关性排序
        results.sort(key=lambda x: x[1], reverse=True)
        
        return [r[0] for r in results]
    
    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """
        执行工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            ToolResult
        """
        tool_def = self._tools.get(tool_name)
        if not tool_def:
            return ToolResult.error_result(f"工具 {tool_name} 未找到")
        
        try:
            self._logger.debug(f"执行工具: {tool_name}, 参数: {kwargs}")
            result = await tool_def.handler(**kwargs)
            self._logger.debug(f"工具 {tool_name} 执行成功")
            return ToolResult.success_result(result)
        except Exception as e:
            self._logger.error(f"工具 {tool_name} 执行失败: {e}")
            return ToolResult.error_result(str(e))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        category_counts = {}
        for tool in self._tools.values():
            category_counts[tool.category] = category_counts.get(tool.category, 0) + 1
        
        return {
            "total_tools": len(self._tools),
            "categories": category_counts
        }
    
    def to_json(self) -> str:
        """导出工具列表为 JSON"""
        tools_data = []
        for tool in self._tools.values():
            tools_data.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "returns": tool.returns,
                "category": tool.category,
                "version": tool.version,
                "author": tool.author
            })
        
        return json.dumps(tools_data, ensure_ascii=False, indent=2)