"""
自动工具包装器

自动扫描现有模块，为其生成 BaseTool 包装器并注册到 ToolRegistry。
"""

import os
import importlib
import inspect
from typing import Any, Dict, List, Optional, Callable
from loguru import logger

from business.tools.base_tool import BaseTool
from business.tools.tool_result import ToolResult
from business.tools.tool_registry import ToolRegistry
from business.tools.tool_definition import ToolDefinition


class AutoToolWrapper:
    """
    自动工具包装器
    
    自动为现有模块生成 BaseTool 包装器。
    
    用法：
        wrapper = AutoToolWrapper()
        wrapper.wrap_module("client.src.business.vector_database")
        wrapper.wrap_all_modules("client/src/business")
    """
    
    def __init__(self, registry: Optional[ToolRegistry] = None):
        """
        初始化自动包装器
        
        Args:
            registry: ToolRegistry 实例，默认使用单例
        """
        self._registry = registry or ToolRegistry.get_instance()
        self._logger = logger.bind(component="AutoToolWrapper")
        self._wrapped_count = 0
        self._failed_modules = []
    
    def wrap_module(
        self,
        module_name: str,
        main_class_or_func: Optional[str] = None
    ) -> List[str]:
        """
        包装单个模块
        
        Args:
            module_name: 模块名称（如 "client.src.business.vector_database"）
            main_class_or_func: 可选，指定要包装的主类或函数名
            
        Returns:
            已包装的工具名称列表
        """
        wrapped_tools = []
        
        try:
            module = importlib.import_module(module_name)
            
            # 如果指定了主类/函数，只包装它
            if main_class_or_func:
                if hasattr(module, main_class_or_func):
                    obj = getattr(module, main_class_or_func)
                    tool_name = self._wrap_object(obj, module_name)
                    if tool_name:
                        wrapped_tools.append(tool_name)
                else:
                    self._logger.warning(f"模块 {module_name} 中未找到 {main_class_or_func}")
            else:
                # 自动发现：包装所有可调用对象
                for name, obj in inspect.getmembers(module):
                    # 跳过私有对象
                    if name.startswith("_"):
                        continue
                    
                    # 包装类（必须是 BaseTool 的子类，但不是 BaseTool 本身）
                    if (inspect.isclass(obj) and 
                        issubclass(obj, BaseTool) and 
                        obj != BaseTool):
                        # 已经是 BaseTool 子类，直接注册
                        try:
                            tool_instance = obj()
                            if self._registry.register_tool(tool_instance):
                                wrapped_tools.append(tool_instance.name)
                                self._wrapped_count += 1
                        except Exception as e:
                            self._logger.error(f"注册工具 {name} 失败: {e}")
                    
                    # 包装函数
                    elif inspect.isfunction(obj) or inspect.ismethod(obj):
                        tool_name = self._wrap_function(obj, module_name)
                        if tool_name:
                            wrapped_tools.append(tool_name)
            
            self._logger.info(f"模块 {module_name} 包装完成，共 {len(wrapped_tools)} 个工具")
            return wrapped_tools
        
        except Exception as e:
            self._logger.exception(f"包装模块 {module_name} 失败: {e}")
            self._failed_modules.append(module_name)
            return []
    
    def _wrap_object(self, obj: Any, module_name: str) -> Optional[str]:
        """
        包装对象（类或函数）
        
        Args:
            obj: 要包装的对象
            module_name: 模块名称
            
        Returns:
            工具名称，失败返回 None
        """
        try:
            # 如果是类，实例化并注册
            if inspect.isclass(obj):
                if issubclass(obj, BaseTool) and obj != BaseTool:
                    # 已经是 BaseTool 子类
                    instance = obj()
                else:
                    # 创建包装器
                    wrapper_class = self._create_wrapper_class(obj, module_name)
                    instance = wrapper_class()
                
                if self._registry.register_tool(instance):
                    self._wrapped_count += 1
                    return instance.name
            
            # 如果是函数，创建函数工具
            elif inspect.isfunction(obj) or inspect.ismethod(obj):
                return self._wrap_function(obj, module_name)
            
            return None
        
        except Exception as e:
            self._logger.error(f"包装对象失败: {e}")
            return None
    
    def _wrap_function(self, func: Callable, module_name: str) -> Optional[str]:
        """
        包装函数
        
        Args:
            func: 要包装的函数
            module_name: 模块名称
            
        Returns:
            工具名称，失败返回 None
        """
        try:
            tool_name = f"{module_name.split('.')[-1]}_{func.__name__}"
            description = func.__doc__ or f"函数 {func.__name__}"
            
            # 创建匿名工具类
            class FunctionTool(BaseTool):
                def __init__(self):
                    super().__init__(
                        name=tool_name,
                        description=description[:100],  # 限制长度
                        category="auto_wrapped",
                        tags=["auto", module_name.split('.')[-1]]
                    )
                
                def execute(self, *args, **kwargs) -> ToolResult:
                    try:
                        result = func(*args, **kwargs)
                        return ToolResult.ok(data=result)
                    except Exception as e:
                        return ToolResult.fail(error=str(e))
            
            # 注册工具
            tool_instance = FunctionTool()
            if self._registry.register_tool(tool_instance):
                self._wrapped_count += 1
                return tool_instance.name
            
            return None
        
        except Exception as e:
            self._logger.error(f"包装函数 {func.__name__} 失败: {e}")
            return None
    
    def _create_wrapper_class(self, cls: type, module_name: str) -> type:
        """
        为类创建 BaseTool 包装器子类
        
        Args:
            cls: 要包装的类
            module_name: 模块名称
            
        Returns:
            新的 BaseTool 子类
        """
        class_name = f"{cls.__name__}Tool"
        description = cls.__doc__ or f"工具 {cls.__name__}"
        
        # 动态创建子类
        WrapperClass = type(
            class_name,
            (BaseTool,),
            {
                "__init__": lambda self: super(type(self), self).__init__(
                    name=cls.__name__.lower(),
                    description=description[:100],
                    category="auto_wrapped",
                    tags=["auto", module_name.split('.')[-1]]
                ),
                "execute": lambda self, *args, **kwargs: ToolResult.ok(
                    data=cls()(*args, **kwargs)
                ) if not kwargs else ToolResult.ok(
                    data=cls()(**kwargs)
                )
            }
        )
        
        return WrapperClass
    
    def wrap_all_modules(
        self,
        base_dir: str,
        modules_to_wrap: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        批量包装多个模块
        
        Args:
            base_dir: 基础目录（相对于项目根目录）
            modules_to_wrap: 指定要包装的模块列表，为 None 则自动扫描
            
        Returns:
            模块名 -> 工具名列表的字典
        """
        results = {}
        
        if modules_to_wrap:
            # 包装指定的模块
            for module_name in modules_to_wrap:
                tools = self.wrap_module(module_name)
                results[module_name] = tools
        else:
            # 自动扫描目录
            self._logger.info(f"开始自动扫描目录: {base_dir}")
            
            project_root = self._get_project_root()
            target_dir = os.path.join(project_root, base_dir)
            
            if not os.path.exists(target_dir):
                self._logger.error(f"目录不存在: {target_dir}")
                return results
            
            # 扫描 Python 文件
            for root, dirs, files in os.walk(target_dir):
                # 跳过特殊目录
                dirs[:] = [d for d in dirs if not d.startswith("_") and d not in ["__pycache__", "tests", "test"]]
                
                for file in files:
                    if file.endswith(".py") and not file.startswith("_"):
                        file_path = os.path.join(root, file)
                        module_name = self._path_to_module(file_path, project_root)
                        
                        if module_name:
                            tools = self.wrap_module(module_name)
                            if tools:
                                results[module_name] = tools
        
        self._logger.info(f"批量包装完成，共 {self._wrapped_count} 个工具")
        return results
    
    def _path_to_module(self, file_path: str, project_root: str) -> Optional[str]:
        """将文件路径转换为模块名称"""
        try:
            rel_path = os.path.relpath(file_path, project_root)
            if rel_path.endswith(".py"):
                rel_path = rel_path[:-3]
            module_name = rel_path.replace(os.sep, ".")
            return module_name
        except Exception as e:
            self._logger.error(f"转换路径失败: {file_path}, 错误: {e}")
            return None
    
    def _get_project_root(self) -> str:
        """获取项目根目录"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        while True:
            if (os.path.exists(os.path.join(current_dir, ".git")) or 
                os.path.exists(os.path.join(current_dir, "main.py"))):
                return current_dir
            parent = os.path.dirname(current_dir)
            if parent == current_dir:
                return os.path.dirname(os.path.dirname(current_dir))
            current_dir = parent
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取包装统计"""
        return {
            "wrapped_count": self._wrapped_count,
            "failed_modules": self._failed_modules,
            "registry_stats": self._registry.stats()
        }


def auto_wrap_and_register(
    modules: List[str],
    registry: Optional[ToolRegistry] = None
) -> Dict[str, List[str]]:
    """
    便捷函数：自动包装并注册多个模块
    
    Args:
        modules: 模块名称列表
        registry: 可选，ToolRegistry 实例
        
    Returns:
        模块名 -> 工具名列表的字典
    """
    wrapper = AutoToolWrapper(registry=registry)
    results = {}
    
    for module_name in modules:
        tools = wrapper.wrap_module(module_name)
        if tools:
            results[module_name] = tools
    
    return results


if __name__ == "__main__":
    # 测试：包装单个模块
    wrapper = AutoToolWrapper()
    
    # 测试包装 task_decomposer
    tools = wrapper.wrap_module("client.src.business.task_decomposer")
    print(f"已包装工具: {tools}")
    
    # 获取统计
    stats = wrapper.get_statistics()
    print(f"统计信息: {stats}")
