"""
registrar - 统一注册入口
负责扫描和注册所有工具
"""

import os
import importlib
import inspect
from typing import List, Type, Optional
from loguru import logger

from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_registry import ToolRegistry


class ToolRegistrar:
    """
    工具注册器
    
    职责：
    - 扫描指定目录下的工具模块
    - 自动注册所有 BaseTool 子类
    - 支持手动注册单个工具
    
    用法：
        registrar = ToolRegistrar()
        registrar.scan_and_register("client/src/business")
        registrar.register_tool(my_tool)
    """
    
    def __init__(self, registry: Optional[ToolRegistry] = None):
        """
        初始化注册器
        
        Args:
            registry: 工具注册中心实例，默认使用单例
        """
        self._registry = registry or ToolRegistry.get_instance()
        self._logger = logger.bind(component="ToolRegistrar")
        self._registered_modules: List[str] = []
    
    def register_tool(self, tool: BaseTool) -> bool:
        """
        注册单个工具
        
        Args:
            tool: 工具实例
            
        Returns:
            是否注册成功
        """
        return self._registry.register_tool(tool)
    
    def register_from_module(self, module_name: str) -> int:
        """
        从模块中注册所有工具
        
        Args:
            module_name: 模块名称（如 "client.src.business.web_crawler"）
            
        Returns:
            成功注册的工具数量
        """
        try:
            module = importlib.import_module(module_name)
            
            count = 0
            for name, obj in inspect.getmembers(module):
                # 检查是否是 BaseTool 的子类（且不是 BaseTool 本身）
                if (inspect.isclass(obj) and 
                    issubclass(obj, BaseTool) and 
                    obj != BaseTool):
                    
                    # 实例化并注册
                    try:
                        tool_instance = obj()
                        if self._registry.register_tool(tool_instance):
                            count += 1
                    except Exception as e:
                        self._logger.error(f"实例化工具 {name} 失败: {e}")
            
            self._logger.info(f"从模块 {module_name} 注册了 {count} 个工具")
            return count
        
        except Exception as e:
            self._logger.exception(f"从模块 {module_name} 注册工具失败: {e}")
            return 0
    
    def scan_and_register(self, base_dir: str, recursive: bool = True) -> int:
        """
        扫描目录并注册所有工具
        
        Args:
            base_dir: 要扫描的目录（相对于项目根目录）
            recursive: 是否递归扫描子目录
            
        Returns:
            成功注册的工具总数
        """
        project_root = self._get_project_root()
        target_dir = os.path.join(project_root, base_dir)
        
        if not os.path.exists(target_dir):
            self._logger.error(f"目录不存在: {target_dir}")
            return 0
        
        self._logger.info(f"开始扫描目录: {target_dir}")
        
        total_count = 0
        
        # 扫描 Python 文件
        for root, dirs, files in os.walk(target_dir):
            # 跳过特殊目录
            dirs[:] = [d for d in dirs if not d.startswith("_") and d not in ["__pycache__", "tests", "test"]]
            
            for file in files:
                if file.endswith(".py") and not file.startswith("_"):
                    module_path = os.path.join(root, file)
                    module_name = self._path_to_module(module_path, project_root)
                    
                    if module_name:
                        count = self.register_from_module(module_name)
                        total_count += count
            
            if not recursive:
                break
        
        self._logger.info(f"扫描完成，共注册 {total_count} 个工具")
        return total_count
    
    def _path_to_module(self, file_path: str, project_root: str) -> Optional[str]:
        """
        将文件路径转换为模块名称
        
        Args:
            file_path: 文件路径
            project_root: 项目根目录
            
        Returns:
            模块名称（如 "client.src.business.web_crawler.engine"）
        """
        try:
            # 获取相对路径
            rel_path = os.path.relpath(file_path, project_root)
            
            # 移除 .py 后缀
            if rel_path.endswith(".py"):
                rel_path = rel_path[:-3]
            
            # 转换为模块路径（用 . 替换 / 或 \）
            module_name = rel_path.replace(os.sep, ".")
            
            return module_name
        
        except Exception as e:
            self._logger.error(f"转换路径失败: {file_path}, 错误: {e}")
            return None
    
    def _get_project_root(self) -> str:
        """获取项目根目录"""
        # registrar.py 在 client/src/business/tools/ 下
        # 向上 4 级：tools/ → business/ → src/ → client/ → 项目根目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 方法1：向上查找标记文件
        check_dir = current_dir
        for _ in range(10):  # 最多向上 10 级
            # 检查标记文件
            has_git = os.path.exists(os.path.join(check_dir, ".git"))
            has_main = os.path.exists(os.path.join(check_dir, "main.py"))
            
            if has_git or has_main:
                return check_dir
            
            # 向上一级
            parent = os.path.dirname(check_dir)
            if parent == check_dir:
                break  # 到达文件系统根目录
            check_dir = parent
        
        # 方法2：假设当前文件在 client/src/business/tools/，直接向上 4 级
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
        return project_root
    
    def get_registered_modules(self) -> List[str]:
        """获取已注册的模块列表"""
        return self._registered_modules.copy()
    
    def clear_all(self):
        """清空所有工具（用于测试）"""
        self._registry.clear()
        self._registered_modules.clear()
        self._logger.info("已清空所有工具")


# 便捷函数
def auto_register_all(base_dir: str = "client/src/business") -> int:
    """
    自动扫描并注册所有工具（便捷函数）
    
    Args:
        base_dir: 要扫描的目录
        
    Returns:
        成功注册的工具总数
    """
    registrar = ToolRegistrar()
    return registrar.scan_and_register(base_dir, recursive=True)


def register_tool(tool: BaseTool) -> bool:
    """
    注册单个工具（便捷函数）
    
    Args:
        tool: 工具实例
        
    Returns:
        是否注册成功
    """
    registry = ToolRegistry.get_instance()
    return registry.register_tool(tool)
