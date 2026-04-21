"""
插件系统

借鉴 qutebrowser 的插件系统，为 AI 增强浏览器提供插件功能
"""

import os
import importlib
import importlib.util
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass


@dataclass
class Plugin:
    """插件信息"""
    name: str
    version: str
    description: str
    author: str
    path: str
    module: Optional[object] = None
    enabled: bool = True
    hooks: Dict[str, List[Callable]] = None
    commands: Dict[str, Callable] = None
    
    def __post_init__(self):
        if self.hooks is None:
            self.hooks = {}
        if self.commands is None:
            self.commands = {}


class PluginSystem:
    """插件系统"""
    
    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self._plugin_paths: List[str] = []
        self._hooks: Dict[str, List[Callable]] = {}
    
    def add_plugin_path(self, path: str):
        """
        添加插件路径
        
        Args:
            path: 插件路径
        """
        if path not in self._plugin_paths:
            self._plugin_paths.append(path)
    
    def load_plugins(self):
        """
        加载所有插件
        """
        for path in self._plugin_paths:
            if os.path.isdir(path):
                self._load_plugins_from_dir(path)
    
    def _load_plugins_from_dir(self, dir_path: str):
        """
        从目录加载插件
        
        Args:
            dir_path: 目录路径
        """
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "plugin.json")):
                self._load_plugin(item_path)
    
    def _load_plugin(self, plugin_path: str):
        """
        加载单个插件
        
        Args:
            plugin_path: 插件路径
        """
        try:
            # 加载 plugin.json
            import json
            plugin_info_path = os.path.join(plugin_path, "plugin.json")
            with open(plugin_info_path, "r", encoding="utf-8") as f:
                plugin_info = json.load(f)
            
            # 创建插件实例
            plugin = Plugin(
                name=plugin_info.get("name"),
                version=plugin_info.get("version", "1.0.0"),
                description=plugin_info.get("description", ""),
                author=plugin_info.get("author", "Unknown"),
                path=plugin_path
            )
            
            # 加载插件模块
            main_module = plugin_info.get("main", "main.py")
            main_path = os.path.join(plugin_path, main_module)
            
            if os.path.exists(main_path):
                spec = importlib.util.spec_from_file_location(
                    f"plugin_{plugin.name}", main_path
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    plugin.module = module
            
            # 注册插件的钩子和命令
            if plugin.module:
                # 注册钩子
                if hasattr(plugin.module, "register_hooks"):
                    plugin.module.register_hooks(self, plugin)
                
                # 注册命令
                if hasattr(plugin.module, "register_commands"):
                    plugin.module.register_commands(self, plugin)
            
            self._plugins[plugin.name] = plugin
            print(f"Loaded plugin: {plugin.name} v{plugin.version}")
            
        except Exception as e:
            print(f"Failed to load plugin from {plugin_path}: {e}")
    
    def register_hook(self, plugin: Plugin, hook_name: str, callback: Callable):
        """
        注册钩子
        
        Args:
            plugin: 插件实例
            hook_name: 钩子名称
            callback: 回调函数
        """
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append(callback)
        
        if hook_name not in plugin.hooks:
            plugin.hooks[hook_name] = []
        plugin.hooks[hook_name].append(callback)
    
    def register_command(self, plugin: Plugin, command_name: str, callback: Callable):
        """
        注册命令
        
        Args:
            plugin: 插件实例
            command_name: 命令名称
            callback: 回调函数
        """
        plugin.commands[command_name] = callback
    
    def run_hook(self, hook_name: str, *args, **kwargs):
        """
        运行钩子
        
        Args:
            hook_name: 钩子名称
            *args: 位置参数
            **kwargs: 关键字参数
        """
        if hook_name in self._hooks:
            for callback in self._hooks[hook_name]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    print(f"Error running hook {hook_name}: {e}")
    
    def execute_command(self, command_name: str, *args, **kwargs) -> Optional[object]:
        """
        执行命令
        
        Args:
            command_name: 命令名称
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            object: 命令执行结果
        """
        for plugin in self._plugins.values():
            if plugin.enabled and command_name in plugin.commands:
                try:
                    return plugin.commands[command_name](*args, **kwargs)
                except Exception as e:
                    print(f"Error executing command {command_name}: {e}")
        return None
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """
        获取插件
        
        Args:
            name: 插件名称
            
        Returns:
            Plugin: 插件实例
        """
        return self._plugins.get(name)
    
    def list_plugins(self) -> List[Plugin]:
        """
        列出所有插件
        
        Returns:
            List[Plugin]: 插件列表
        """
        return list(self._plugins.values())
    
    def enable_plugin(self, name: str):
        """
        启用插件
        
        Args:
            name: 插件名称
        """
        if name in self._plugins:
            self._plugins[name].enabled = True
            if hasattr(self._plugins[name].module, "enable"):
                self._plugins[name].module.enable()
    
    def disable_plugin(self, name: str):
        """
        禁用插件
        
        Args:
            name: 插件名称
        """
        if name in self._plugins:
            self._plugins[name].enabled = False
            if hasattr(self._plugins[name].module, "disable"):
                self._plugins[name].module.disable()
    
    def unload_plugins(self):
        """
        卸载所有插件
        """
        for plugin in self._plugins.values():
            if hasattr(plugin.module, "cleanup"):
                try:
                    plugin.module.cleanup()
                except Exception as e:
                    print(f"Error cleaning up plugin {plugin.name}: {e}")
        
        self._plugins.clear()
        self._hooks.clear()


# 单例实例
_plugin_system: Optional[PluginSystem] = None


def get_plugin_system() -> PluginSystem:
    """
    获取插件系统实例
    
    Returns:
        PluginSystem: 插件系统实例
    """
    global _plugin_system
    if _plugin_system is None:
        _plugin_system = PluginSystem()
    return _plugin_system
