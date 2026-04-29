"""
扩展管理器

借鉴 qutebrowser 的扩展管理机制，管理浏览器扩展的生命周期
"""

import os
import importlib
import importlib.util
from typing import Dict, List, Optional
from dataclasses import dataclass

from ..browser_pool import BrowserSession
from .api import ExtensionAPI


@dataclass
class Extension:
    """扩展信息"""
    name: str
    version: str
    author: str
    description: str
    path: str
    module: Optional[object] = None
    enabled: bool = True
    api: Optional[ExtensionAPI] = None


class ExtensionManager:
    """扩展管理器"""
    
    def __init__(self):
        self._extensions: Dict[str, Extension] = {}
        self._extension_paths: List[str] = []
        self._session: Optional[BrowserSession] = None
    
    def add_extension_path(self, path: str):
        """
        添加扩展路径
        
        Args:
            path: 扩展路径
        """
        if path not in self._extension_paths:
            self._extension_paths.append(path)
    
    def load_extensions(self, session: BrowserSession):
        """
        加载所有扩展
        
        Args:
            session: 浏览器会话
        """
        self._session = session
        
        for path in self._extension_paths:
            if os.path.isdir(path):
                self._load_extensions_from_dir(path)
    
    def _load_extensions_from_dir(self, dir_path: str):
        """
        从目录加载扩展
        
        Args:
            dir_path: 目录路径
        """
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "manifest.json")):
                self._load_extension(item_path)
    
    def _load_extension(self, extension_path: str):
        """
        加载单个扩展
        
        Args:
            extension_path: 扩展路径
        """
        try:
            # 加载 manifest.json
            import json
            manifest_path = os.path.join(extension_path, "manifest.json")
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            # 创建扩展实例
            extension = Extension(
                name=manifest.get("name"),
                version=manifest.get("version", "1.0.0"),
                author=manifest.get("author", "Unknown"),
                description=manifest.get("description", ""),
                path=extension_path
            )
            
            # 加载扩展模块
            main_module = manifest.get("main", "main.py")
            main_path = os.path.join(extension_path, main_module)
            
            if os.path.exists(main_path):
                spec = importlib.util.spec_from_file_location(
                    f"extension_{extension.name}", main_path
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    extension.module = module
            
            # 创建 API 实例
            extension.api = ExtensionAPI(self._session, extension)
            
            # 初始化扩展
            if extension.module and hasattr(extension.module, "init"):
                extension.module.init(extension.api)
            
            self._extensions[extension.name] = extension
            print(f"Loaded extension: {extension.name} v{extension.version}")
            
        except Exception as e:
            print(f"Failed to load extension from {extension_path}: {e}")
    
    def get_extension(self, name: str) -> Optional[Extension]:
        """
        获取扩展
        
        Args:
            name: 扩展名称
            
        Returns:
            Extension: 扩展实例
        """
        return self._extensions.get(name)
    
    def list_extensions(self) -> List[Extension]:
        """
        列出所有扩展
        
        Returns:
            List[Extension]: 扩展列表
        """
        return list(self._extensions.values())
    
    def enable_extension(self, name: str):
        """
        启用扩展
        
        Args:
            name: 扩展名称
        """
        if name in self._extensions:
            self._extensions[name].enabled = True
            if hasattr(self._extensions[name].module, "enable"):
                self._extensions[name].module.enable()
    
    def disable_extension(self, name: str):
        """
        禁用扩展
        
        Args:
            name: 扩展名称
        """
        if name in self._extensions:
            self._extensions[name].enabled = False
            if hasattr(self._extensions[name].module, "disable"):
                self._extensions[name].module.disable()
    
    def unload_extensions(self):
        """
        卸载所有扩展
        """
        for extension in self._extensions.values():
            if hasattr(extension.module, "cleanup"):
                try:
                    extension.module.cleanup()
                except Exception as e:
                    print(f"Error cleaning up extension {extension.name}: {e}")
        
        self._extensions.clear()
        self._session = None


# 单例实例
_extension_manager: Optional[ExtensionManager] = None


def get_extension_manager() -> ExtensionManager:
    """
    获取扩展管理器实例
    
    Returns:
        ExtensionManager: 扩展管理器实例
    """
    global _extension_manager
    if _extension_manager is None:
        _extension_manager = ExtensionManager()
    return _extension_manager
