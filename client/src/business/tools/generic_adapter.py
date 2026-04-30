"""
通用工具适配器

自动为现有模块生成 BaseTool 包装器，无需手动编写每个工具的包装代码。
"""

import importlib
import inspect
import asyncio
from typing import Any, Dict, List, Optional, Callable, Type
from loguru import logger

from business.tools.base_tool import BaseTool
from business.tools.tool_result import ToolResult
from business.tools.tool_definition import ToolDefinition
from business.tools.tool_registry import ToolRegistry


class GenericToolAdapter(BaseTool):
    """
    通用工具适配器
    
    自动将现有模块的函数或类方法包装为 BaseTool。
    
    用法：
        # 包装函数
        adapter = GenericToolAdapter.from_function(
            module_name="client.src.business.vector_database",
            func_name="search",
            tool_name="vector_search"
        )
        
        # 包装类的所有公共方法
        adapters = GenericToolAdapter.from_class(
            module_name="client.src.business.task_queue",
            class_name="TaskQueue",
            method_filter=["add", "get", "update", "delete"]
        )
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable,
        category: str = "auto_adapted",
        tags: Optional[List[str]] = None,
        param_schema: Optional[Dict[str, Any]] = None
    ):
        """
        初始化适配器
        
        Args:
            name: 工具名称
            description: 工具描述
            handler: 处理函数（同步或异步）
            category: 工具分类
            tags: 标签列表
            param_schema: 参数 Schema（可选，自动推断）
        """
        super().__init__(
            name=name,
            description=description,
            category=category,
            tags=tags or ["auto", "adapted"]
        )
        self._handler = handler
        self._param_schema = param_schema
        self._is_async = asyncio.iscoroutinefunction(handler)
        
        # 自动推断参数 Schema
        if self._param_schema is None:
            self._param_schema = self._infer_param_schema(handler)
    
    def execute(self, **kwargs) -> ToolResult:
        """
        执行工具
        
        自动处理同步/异步函数
        """
        try:
            # 调用处理函数
            if self._is_async:
                # 异步函数：需要在事件循环中执行
                result = asyncio.get_event_loop().run_until_complete(
                    self._handler(**kwargs)
                )
            else:
                # 同步函数：直接调用
                result = self._handler(**kwargs)
            
            # 包装返回结果
            if isinstance(result, ToolResult):
                return result
            else:
                return ToolResult.ok(
                    data=result,
                    message=f"工具 {self.name} 执行成功"
                )
        
        except Exception as e:
            self._logger.exception(f"工具执行失败: {self.name}")
            return ToolResult.fail(error=str(e))
    
    def _infer_param_schema(self, func: Callable) -> Dict[str, Any]:
        """
        自动推断参数 Schema
        
        从函数的签名中提取参数信息
        """
        try:
            import inspect
            
            sig = inspect.signature(func)
            params = sig.parameters
            
            properties = {}
            required = []
            
            for name, param in params.items():
                # 跳过 self 参数
                if name == "self":
                    continue
                
                # 推断参数类型
                param_type = "string"  # 默认类型
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int:
                        param_type = "integer"
                    elif param.annotation == float:
                        param_type = "number"
                    elif param.annotation == bool:
                        param_type = "boolean"
                    elif param.annotation == list or param.annotation == List:
                        param_type = "array"
                    elif param.annotation == dict or param.annotation == Dict:
                        param_type = "object"
                
                properties[name] = {
                    "type": param_type,
                    "description": f"参数 {name}"
                }
                
                # 检查是否必需
                if param.default == inspect.Parameter.empty:
                    required.append(name)
            
            return {
                "type": "object",
                "properties": properties,
                "required": required
            }
        
        except Exception as e:
            self._logger.warning(f"推断参数 Schema 失败: {e}")
            return {
                "type": "object",
                "properties": {},
                "required": []
            }
    
    @classmethod
    def from_function(
        cls,
        module_name: str,
        func_name: str,
        tool_name: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "auto_adapted",
        tags: Optional[List[str]] = None
    ) -> Optional["GenericToolAdapter"]:
        """
        从函数创建适配器
        
        Args:
            module_name: 模块名称
            func_name: 函数名称
            tool_name: 工具名称（默认使用函数名）
            description: 工具描述（默认使用函数 docstring）
            category: 工具分类
            tags: 标签列表
            
        Returns:
            GenericToolAdapter 实例，失败返回 None
        """
        try:
            # 导入模块
            module = importlib.import_module(module_name)
            
            # 获取函数
            if not hasattr(module, func_name):
                logger.error(f"模块 {module_name} 中未找到函数 {func_name}")
                return None
            
            func = getattr(module, func_name)
            
            # 检查是否是函数
            if not callable(func):
                logger.error(f"{func_name} 不是可调用对象")
                return None
            
            # 创建适配器
            adapter = cls(
                name=tool_name or func_name,
                description=description or func.__doc__ or f"函数 {func_name}",
                handler=func,
                category=category,
                tags=tags or ["auto", module_name.split(".")[-1]]
            )
            
            logger.info(f"已创建函数适配器: {adapter.name}")
            return adapter
        
        except Exception as e:
            logger.exception(f"创建函数适配器失败: {e}")
            return None
    
    @classmethod
    def from_class_method(
        cls,
        module_name: str,
        class_name: str,
        method_name: str,
        tool_name: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "auto_adapted",
        tags: Optional[List[str]] = None,
        init_args: Optional[Dict[str, Any]] = None
    ) -> Optional["GenericToolAdapter"]:
        """
        从类方法创建适配器
        
        Args:
            module_name: 模块名称
            class_name: 类名称
            method_name: 方法名称
            tool_name: 工具名称（默认使用 "class_method"）
            description: 工具描述
            category: 工具分类
            tags: 标签列表
            init_args: 类实例化参数（可选）
            
        Returns:
            GenericToolAdapter 实例，失败返回 None
        """
        try:
            # 导入模块
            module = importlib.import_module(module_name)
            
            # 获取类
            if not hasattr(module, class_name):
                logger.error(f"模块 {module_name} 中未找到类 {class_name}")
                return None
            
            cls_obj = getattr(module, class_name)
            
            # 实例化类
            instance = cls_obj(**(init_args or {}))
            
            # 获取方法
            if not hasattr(instance, method_name):
                logger.error(f"类 {class_name} 中未找到方法 {method_name}")
                return None
            
            method = getattr(instance, method_name)
            
            # 创建适配器
            adapter = cls(
                name=tool_name or f"{class_name.lower()}_{method_name}",
                description=description or method.__doc__ or f"{class_name}.{method_name}",
                handler=method,
                category=category,
                tags=tags or ["auto", class_name.lower()]
            )
            
            logger.info(f"已创建方法适配器: {adapter.name}")
            return adapter
        
        except Exception as e:
            logger.exception(f"创建方法适配器失败: {e}")
            return None
    
    @classmethod
    def from_class_all_methods(
        cls,
        module_name: str,
        class_name: str,
        method_filter: Optional[List[str]] = None,
        category: str = "auto_adapted"
    ) -> List["GenericToolAdapter"]:
        """
        从类的所有公共方法创建适配器
        
        Args:
            module_name: 模块名称
            class_name: 类名称
            method_filter: 方法名过滤列表（可选）
            category: 工具分类
            
        Returns:
            GenericToolAdapter 实例列表
        """
        adapters = []
        
        try:
            # 导入模块
            module = importlib.import_module(module_name)
            
            # 获取类
            if not hasattr(module, class_name):
                logger.error(f"模块 {module_name} 中未找到类 {class_name}")
                return adapters
            
            cls_obj = getattr(module, class_name)
            
            # 实例化类
            instance = cls_obj()
            
            # 遍历所有方法
            for name, method in inspect.getmembers(instance, predicate=inspect.ismethod):
                # 跳过私有方法
                if name.startswith("_"):
                    continue
                
                # 应用过滤
                if method_filter and name not in method_filter:
                    continue
                
                # 创建适配器
                adapter = cls(
                    name=f"{class_name.lower()}_{name}",
                    description=method.__doc__ or f"{class_name}.{name}",
                    handler=method,
                    category=category,
                    tags=["auto", class_name.lower()]
                )
                
                adapters.append(adapter)
            
            logger.info(f"已为类 {class_name} 创建 {len(adapters)} 个方法适配器")
        
        except Exception as e:
            logger.exception(f"创建类方法适配器失败: {e}")
        
        return adapters


class BatchAdapter:
    """
    批量适配器
    
    批量将现有模块包装为 BaseTool 并注册到 ToolRegistry。
    """
    
    def __init__(self, registry: Optional[ToolRegistry] = None):
        """
        初始化批量适配器
        
        Args:
            registry: ToolRegistry 实例，默认使用单例
        """
        self._registry = registry or ToolRegistry.get_instance()
        self._adapted_count = 0
        self._failed = []
    
    def adapt_function(
        self,
        module_name: str,
        func_name: str,
        tool_name: Optional[str] = None,
        category: str = "auto_adapted"
    ) -> bool:
        """
        适配单个函数并注册
        
        Returns:
            是否成功
        """
        adapter = GenericToolAdapter.from_function(
            module_name=module_name,
            func_name=func_name,
            tool_name=tool_name,
            category=category
        )
        
        if adapter:
            success = self._registry.register_tool(adapter)
            if success:
                self._adapted_count += 1
            return success
        
        self._failed.append(f"{module_name}.{func_name}")
        return False
    
    def adapt_class_methods(
        self,
        module_name: str,
        class_name: str,
        methods: List[str],
        category: str = "auto_adapted"
    ) -> int:
        """
        适配类的多个方法并注册
        
        Returns:
            成功适配的方法数
        """
        count = 0
        
        for method_name in methods:
            adapter = GenericToolAdapter.from_class_method(
                module_name=module_name,
                class_name=class_name,
                method_name=method_name,
                category=category
            )
            
            if adapter:
                success = self._registry.register_tool(adapter)
                if success:
                    count += 1
                    self._adapted_count += 1
        
        return count
    
    def adapt_module_all(
        self,
        module_name: str,
        category: Optional[str] = None
    ) -> int:
        """
        适配模块中的所有可调用对象
        
        Returns:
            成功适配的数量
        """
        count = 0
        
        try:
            module = importlib.import_module(module_name)
            
            # 遍历模块所有成员
            for name, obj in inspect.getmembers(module):
                # 跳过私有对象
                if name.startswith("_"):
                    continue
                
                # 跳过已适配的对象
                if name in [t.name for t in self._registry.list_tools()]:
                    continue
                
                # 适配函数
                if callable(obj) and not inspect.isclass(obj):
                    adapter = GenericToolAdapter.from_function(
                        module_name=module_name,
                        func_name=name,
                        category=category or "auto_adapted"
                    )
                    
                    if adapter:
                        success = self._registry.register_tool(adapter)
                        if success:
                            count += 1
                            self._adapted_count += 1
            
            logger.info(f"已适配模块 {module_name} 中的 {count} 个可调用对象")
        
        except Exception as e:
            logger.exception(f"适配模块失败: {module_name}")
        
        return count
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取适配统计"""
        return {
            "adapted_count": self._adapted_count,
            "failed": self._failed,
            "registry_stats": self._registry.stats()
        }


if __name__ == "__main__":
    # 测试：适配 task_decomposer 模块
    batch = BatchAdapter()
    
    # 适配单个函数
    success = batch.adapt_function(
        module_name="client.src.business.task_decomposer",
        func_name="decompose",
        tool_name="task_decomposer"
    )
    
    print(f"适配结果: {success}")
    print(f"统计: {batch.get_statistics()}")
