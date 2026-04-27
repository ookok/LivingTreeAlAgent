"""
ToolRegistry - 工具注册中心（单例模式）
所有工具通过此类注册和调用
"""

from typing import Any, Dict, List, Optional, Type, Callable
from loguru import logger
import threading

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_definition import ToolDefinition
from client.src.business.tools.tool_result import ToolResult


class ToolRegistry:
    """
    工具注册中心（单例模式）
    
    职责：
    - 工具注册/注销
    - 工具查找/搜索
    - 工具执行
    - 工具生命周期管理
    
    用法：
        registry = ToolRegistry.get_instance()
        registry.register_tool(my_tool)
        result = registry.execute_tool("my_tool", param1="value1")
    """
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        """获取单例实例（线程安全）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """初始化注册中心"""
        if ToolRegistry._instance is not None:
            raise RuntimeError("ToolRegistry 是单例类，请使用 ToolRegistry.get_instance() 获取实例")
        
        self._tools: Dict[str, BaseTool] = {}
        self._categories: Dict[str, List[str]] = {}  # category -> [tool_names]
        self._tags: Dict[str, List[str]] = {}       # tag -> [tool_names]
        self._logger = logger.bind(component="ToolRegistry")
        self._logger.info("ToolRegistry 初始化完成")
    
    def register_tool(
        self, 
        tool: Optional[BaseTool] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        handler: Optional[Callable] = None,
        **kwargs
    ) -> bool:
        """
        注册工具（支持两种用法）
        
        用法 1（推荐）：
            registry.register_tool(my_tool)
        
        用法 2（快速注册函数）：
            registry.register_tool(
                name="my_tool",
                description="我的工具",
                handler=my_function
            )
        
        Returns:
            是否注册成功
        """
        # 用法 2：快速注册函数
        if tool is None and name is not None and handler is not None:
            from client.src.business.tools.tool_definition import ToolDefinition
            
            definition = ToolDefinition(
                name=name,
                description=description or "",
                handler=handler,
                **kwargs
            )
            
            # 创建匿名工具类
            class AnonymousTool(BaseTool):
                def execute(self, *args, **kwargs) -> ToolResult:
                    try:
                        result = handler(*args, **kwargs)
                        return ToolResult(success=True, data=result)
                    except Exception as e:
                        return ToolResult(success=False, error=str(e))
            
            tool = AnonymousTool(name, description or "")
            tool._definition = definition
        
        # 用法 1：注册工具实例
        if not isinstance(tool, BaseTool):
            self._logger.error(f"注册失败：{tool} 不是 BaseTool 的实例")
            return False
        
        if tool.name in self._tools:
            self._logger.warning(f"工具 {tool.name} 已存在，将覆盖")
        
        # 注册工具
        self._tools[tool.name] = tool
        
        # 更新分类索引
        category = tool.definition.category
        if category not in self._categories:
            self._categories[category] = []
        if tool.name not in self._categories[category]:
            self._categories[category].append(tool.name)
        
        # 更新标签索引
        for tag in tool.definition.tags:
            if tag not in self._tags:
                self._tags[tag] = []
            if tool.name not in self._tags[tag]:
                self._tags[tag].append(tool.name)
        
        self._logger.info(f"工具已注册: {tool.name} (分类: {category})")
        return True
    
    def unregister_tool(self, name: str) -> bool:
        """
        注销工具
        
        Args:
            name: 工具名称
            
        Returns:
            是否注销成功
        """
        if name not in self._tools:
            self._logger.warning(f"工具 {name} 不存在，无法注销")
            return False
        
        tool = self._tools[name]
        
        # 从分类索引中移除
        category = tool.definition.category
        if category in self._categories:
            self._categories[category] = [t for t in self._categories[category] if t != name]
        
        # 从标签索引中移除
        for tag in tool.definition.tags:
            if tag in self._tags:
                self._tags[tag] = [t for t in self._tags[tag] if t != name]
        
        # 注销工具
        del self._tools[name]
        
        self._logger.info(f"工具已注销: {name}")
        return True
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        获取工具
        
        Args:
            name: 工具名称
            
        Returns:
            工具实例，不存在则返回 None
        """
        tool = self._tools.get(name)
        if tool is None:
            self._logger.warning(f"工具 {name} 不存在")
            return None
        
        if not tool.definition.is_enabled:
            self._logger.warning(f"工具 {name} 已被禁用")
            return None
        
        return tool
    
    def execute_tool(self, name: str, *args, **kwargs) -> ToolResult:
        """
        执行工具
        
        Args:
            name: 工具名称
            *args, **kwargs: 传递给工具的参数
            
        Returns:
            ToolResult 对象
        """
        tool = self.get_tool(name)
        if tool is None:
            return ToolResult(success=False, error=f"工具 {name} 不存在或已被禁用")
        
        try:
            self._logger.info(f"执行工具: {name}, 参数: {kwargs}")
            result = tool(*args, **kwargs)
            
            if not isinstance(result, ToolResult):
                # 如果工具返回的不是 ToolResult，自动包装
                result = ToolResult(success=True, data=result)
            
            return result
        
        except Exception as e:
            self._logger.exception(f"执行工具 {name} 时发生异常")
            return ToolResult(success=False, error=str(e))
    
    def list_tools(self, category: Optional[str] = None) -> List[ToolDefinition]:
        """
        列出所有工具
        
        Args:
            category: 可选，按分类过滤
            
        Returns:
            工具定义列表
        """
        if category:
            tool_names = self._categories.get(category, [])
            return [self._tools[name].definition for name in tool_names if name in self._tools]
        
        return [tool.definition for tool in self._tools.values()]
    
    def search_tools(self, query: str) -> List[ToolDefinition]:
        """
        搜索工具（按名称、描述、标签）
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的工具定义列表
        """
        query = query.lower()
        results = []
        
        for tool in self._tools.values():
            definition = tool.definition
            
            # 搜索名称
            if query in definition.name.lower():
                results.append(definition)
                continue
            
            # 搜索描述
            if query in definition.description.lower():
                results.append(definition)
                continue
            
            # 搜索标签
            if any(query in tag.lower() for tag in definition.tags):
                results.append(definition)
                continue
        
        return results
    
    def enable_tool(self, name: str) -> bool:
        """启用工具"""
        if name not in self._tools:
            return False
        self._tools[name].definition.is_enabled = True
        self._logger.info(f"工具已启用: {name}")
        return True
    
    def disable_tool(self, name: str) -> bool:
        """禁用工具"""
        if name not in self._tools:
            return False
        self._tools[name].definition.is_enabled = False
        self._logger.info(f"工具已禁用: {name}")
        return True
    
    def get_categories(self) -> List[str]:
        """获取所有分类"""
        return list(self._categories.keys())
    
    def get_tools_by_tag(self, tag: str) -> List[ToolDefinition]:
        """按标签获取工具"""
        tool_names = self._tags.get(tag, [])
        return [self._tools[name].definition for name in tool_names if name in self._tools]
    
    def clear(self):
        """清空所有工具（用于测试）"""
        self._tools.clear()
        self._categories.clear()
        self._tags.clear()
        self._logger.info("已清空所有工具")
    
    def stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_tools": len(self._tools),
            "categories": {k: len(v) for k, v in self._categories.items()},
            "enabled": sum(1 for t in self._tools.values() if t.definition.is_enabled),
            "disabled": sum(1 for t in self._tools.values() if not t.definition.is_enabled)
        }
