"""OpenHarness 插件系统集成"""

import os
import importlib.util
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass


@dataclass
class Plugin:
    """插件定义"""
    name: str
    description: str
    version: str
    author: str
    entry_point: Callable
    dependencies: List[str] = None
    config: Dict[str, Any] = None


class PluginSystem:
    """OpenHarness 插件系统"""
    
    def __init__(self, plugins_dir: str = "~/.living_tree_ai/openharness/plugins"):
        """初始化插件系统"""
        self.plugins_dir = os.path.expanduser(plugins_dir)
        self.plugins: Dict[str, Plugin] = {}
        self._ensure_plugins_dir()
        self._load_builtin_plugins()
    
    def _ensure_plugins_dir(self):
        """确保插件目录存在"""
        os.makedirs(self.plugins_dir, exist_ok=True)
    
    def _load_builtin_plugins(self):
        """加载内置插件"""
        # 内置插件定义
        builtin_plugins = [
            {
                "name": "logger",
                "description": "日志记录插件",
                "version": "1.0.0",
                "author": "OpenHarness",
                "entry_point": self._logger_plugin,
                "dependencies": [],
                "config": {
                    "level": "INFO",
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                }
            },
            {
                "name": "metrics",
                "description": " metrics 收集插件",
                "version": "1.0.0",
                "author": "OpenHarness",
                "entry_point": self._metrics_plugin,
                "dependencies": [],
                "config": {
                    "enabled": True,
                    "interval": 60
                }
            }
        ]
        
        for plugin_data in builtin_plugins:
            plugin = Plugin(**plugin_data)
            self.plugins[plugin.name] = plugin
        
        print(f"[PluginSystem] 加载了 {len(builtin_plugins)} 个内置插件")
    
    def load_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """加载插件"""
        # 检查内存中是否已加载
        if plugin_name in self.plugins:
            return self.plugins[plugin_name]
        
        # 从文件加载
        plugin_file = os.path.join(self.plugins_dir, f"{plugin_name}.py")
        if os.path.exists(plugin_file):
            try:
                # 动态导入插件模块
                spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # 检查模块是否有必要的属性
                    if hasattr(module, "PLUGIN_INFO") and hasattr(module, "entry_point"):
                        plugin_info = module.PLUGIN_INFO
                        plugin = Plugin(
                            name=plugin_info.get("name", plugin_name),
                            description=plugin_info.get("description", ""),
                            version=plugin_info.get("version", "1.0.0"),
                            author=plugin_info.get("author", "Unknown"),
                            entry_point=module.entry_point,
                            dependencies=plugin_info.get("dependencies", []),
                            config=plugin_info.get("config", {})
                        )
                        self.plugins[plugin.name] = plugin
                        print(f"[PluginSystem] 加载插件: {plugin.name}")
                        return plugin
            except Exception as e:
                print(f"[PluginSystem] 加载插件失败 {plugin_name}: {e}")
                return None
        
        print(f"[PluginSystem] 插件不存在: {plugin_name}")
        return None
    
    def register_plugin(self, plugin: Plugin):
        """注册插件"""
        self.plugins[plugin.name] = plugin
        # 保存插件到文件
        self._save_plugin(plugin)
        print(f"[PluginSystem] 注册插件: {plugin.name} - {plugin.description}")
    
    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """获取插件"""
        return self.load_plugin(plugin_name)
    
    def get_all_plugins(self) -> List[Dict[str, Any]]:
        """获取所有插件"""
        return [
            {
                "name": plugin.name,
                "description": plugin.description,
                "version": plugin.version,
                "author": plugin.author,
                "dependencies": plugin.dependencies
            }
            for plugin in self.plugins.values()
        ]
    
    def execute_plugin(self, plugin_name: str, **kwargs) -> Any:
        """执行插件"""
        plugin = self.get_plugin(plugin_name)
        if plugin:
            try:
                result = plugin.entry_point(**kwargs)
                print(f"[PluginSystem] 插件执行成功: {plugin_name}")
                return result
            except Exception as e:
                print(f"[PluginSystem] 插件执行失败 {plugin_name}: {e}")
                raise
        else:
            raise ValueError(f"Plugin not found: {plugin_name}")
    
    def _save_plugin(self, plugin: Plugin):
        """保存插件到文件"""
        plugin_content = f"""
# {plugin.name} 插件

PLUGIN_INFO = {{
    "name": "{plugin.name}",
    "description": "{plugin.description}",
    "version": "{plugin.version}",
    "author": "{plugin.author}",
    "dependencies": {plugin.dependencies},
    "config": {plugin.config}
}}

def entry_point(**kwargs):
    '''插件入口点'''
    # 插件实现
    pass
"""
        
        plugin_file = os.path.join(self.plugins_dir, f"{plugin.name}.py")
        with open(plugin_file, 'w', encoding='utf-8') as f:
            f.write(plugin_content)
    
    def delete_plugin(self, plugin_name: str):
        """删除插件"""
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
            
            # 删除文件
            plugin_file = os.path.join(self.plugins_dir, f"{plugin_name}.py")
            if os.path.exists(plugin_file):
                os.remove(plugin_file)
                print(f"[PluginSystem] 删除插件文件: {plugin_file}")
            
            print(f"[PluginSystem] 删除插件: {plugin_name}")
        else:
            print(f"[PluginSystem] 插件不存在: {plugin_name}")
    
    # 内置插件实现
    def _logger_plugin(self, **kwargs):
        """日志记录插件"""
        import logging
        
        level = kwargs.get("level", "INFO")
        format = kwargs.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        logging.basicConfig(level=level, format=format)
        logger = logging.getLogger("OpenHarness")
        
        message = kwargs.get("message", "")
        if message:
            logger.info(message)
        
        return logger
    
    def _metrics_plugin(self, **kwargs):
        """metrics 收集插件"""
        import time
        
        enabled = kwargs.get("enabled", True)
        interval = kwargs.get("interval", 60)
        
        if enabled:
            metrics = {
                "timestamp": time.time(),
                "interval": interval,
                "status": "active"
            }
            print(f"[Metrics] 收集 metrics: {metrics}")
            return metrics
        else:
            return {"status": "disabled"}
