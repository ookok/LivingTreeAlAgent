"""
插件系统 - Plugin System

功能：
1. 动态模块加载
2. 插件生命周期管理
3. 统一接口协议
4. 插件通信机制
"""

import os
import json
import importlib.util
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PluginState(Enum):
    """插件状态"""
    LOADED = "loaded"
    ACTIVATED = "activated"
    DEACTIVATED = "deactivated"
    ERROR = "error"


@dataclass
class PluginInfo:
    """插件信息"""
    id: str
    name: str
    version: str
    description: str
    author: str
    entry: str
    dependencies: List[str] = None
    state: PluginState = PluginState.LOADED
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class PluginInterface:
    """
    插件接口协议
    
    所有插件必须实现此接口
    """
    
    def activate(self):
        """激活插件"""
        pass
    
    def deactivate(self):
        """停用插件"""
        pass
    
    def get_info(self) -> Dict:
        """获取插件信息"""
        return {}
    
    def handle_event(self, event_name: str, data: Dict):
        """处理事件"""
        pass


class PluginSystem:
    """
    插件系统 - 管理所有插件
    
    核心功能：
    1. 插件发现与加载
    2. 生命周期管理
    3. 插件间通信
    4. 依赖解析
    """
    
    def __init__(self):
        self._plugins: Dict[str, Any] = {}
        self._plugin_info: Dict[str, PluginInfo] = {}
        self._event_listeners: Dict[str, List[Callable]] = {}
        self._plugins_dir = "extensions"
    
    def set_plugins_dir(self, directory: str):
        """设置插件目录"""
        self._plugins_dir = directory
    
    def discover_plugins(self) -> List[str]:
        """发现可用插件"""
        plugins = []
        
        if not os.path.exists(self._plugins_dir):
            os.makedirs(self._plugins_dir, exist_ok=True)
            return plugins
        
        for item in os.listdir(self._plugins_dir):
            item_path = os.path.join(self._plugins_dir, item)
            if os.path.isdir(item_path):
                pkg_path = os.path.join(item_path, "package.json")
                if os.path.exists(pkg_path):
                    plugins.append(item)
        
        return plugins
    
    def load_plugin(self, plugin_id: str) -> bool:
        """加载插件"""
        plugin_dir = os.path.join(self._plugins_dir, plugin_id)
        pkg_path = os.path.join(plugin_dir, "package.json")
        
        if not os.path.exists(pkg_path):
            logger.error(f"插件配置文件不存在: {pkg_path}")
            return False
        
        try:
            # 读取插件配置
            with open(pkg_path, 'r', encoding='utf-8') as f:
                pkg = json.load(f)
            
            # 解析依赖
            dependencies = pkg.get('dependencies', [])
            for dep in dependencies:
                if dep not in self._plugins or self._plugin_info[dep].state != PluginState.ACTIVATED:
                    if not self.load_plugin(dep):
                        logger.warning(f"插件依赖未加载: {dep}")
            
            # 加载入口模块
            entry = pkg.get('main', 'main.py')
            entry_path = os.path.join(plugin_dir, entry)
            
            if not os.path.exists(entry_path):
                logger.error(f"插件入口不存在: {entry_path}")
                return False
            
            # 动态导入
            spec = importlib.util.spec_from_file_location(pkg['name'], entry_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 实例化插件
            plugin_class = getattr(module, pkg['name'])
            plugin_instance = plugin_class()
            
            # 验证接口
            if not isinstance(plugin_instance, PluginInterface):
                logger.error(f"插件未实现PluginInterface: {plugin_id}")
                return False
            
            # 存储插件
            self._plugins[plugin_id] = plugin_instance
            self._plugin_info[plugin_id] = PluginInfo(
                id=plugin_id,
                name=pkg['name'],
                version=pkg.get('version', '1.0.0'),
                description=pkg.get('description', ''),
                author=pkg.get('author', ''),
                entry=entry,
                dependencies=dependencies
            )
            
            logger.info(f"插件加载成功: {plugin_id}")
            return True
            
        except Exception as e:
            logger.error(f"加载插件失败 {plugin_id}: {e}")
            return False
    
    def activate_plugin(self, plugin_id: str) -> bool:
        """激活插件"""
        if plugin_id not in self._plugins:
            if not self.load_plugin(plugin_id):
                return False
        
        try:
            self._plugins[plugin_id].activate()
            self._plugin_info[plugin_id].state = PluginState.ACTIVATED
            logger.info(f"插件激活成功: {plugin_id}")
            return True
        except Exception as e:
            logger.error(f"激活插件失败 {plugin_id}: {e}")
            self._plugin_info[plugin_id].state = PluginState.ERROR
            return False
    
    def deactivate_plugin(self, plugin_id: str):
        """停用插件"""
        if plugin_id in self._plugins:
            try:
                self._plugins[plugin_id].deactivate()
                self._plugin_info[plugin_id].state = PluginState.DEACTIVATED
                logger.info(f"插件停用成功: {plugin_id}")
            except Exception as e:
                logger.error(f"停用插件失败 {plugin_id}: {e}")
    
    def load_all_plugins(self):
        """加载所有插件"""
        plugins = self.discover_plugins()
        for plugin_id in plugins:
            self.load_plugin(plugin_id)
    
    def activate_all_plugins(self):
        """激活所有插件"""
        for plugin_id in self._plugins:
            self.activate_plugin(plugin_id)
    
    def get_plugin(self, plugin_id: str) -> Optional[Any]:
        """获取插件实例"""
        return self._plugins.get(plugin_id)
    
    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        return self._plugin_info.get(plugin_id)
    
    def get_all_plugins(self) -> Dict[str, PluginInfo]:
        """获取所有插件信息"""
        return self._plugin_info
    
    def subscribe_event(self, event_name: str, handler: Callable):
        """订阅事件"""
        if event_name not in self._event_listeners:
            self._event_listeners[event_name] = []
        
        if handler not in self._event_listeners[event_name]:
            self._event_listeners[event_name].append(handler)
    
    def unsubscribe_event(self, event_name: str, handler: Callable):
        """取消订阅事件"""
        if event_name in self._event_listeners and handler in self._event_listeners[event_name]:
            self._event_listeners[event_name].remove(handler)
    
    def publish_event(self, event_name: str, data: Dict = None):
        """发布事件"""
        if event_name in self._event_listeners:
            for handler in self._event_listeners[event_name]:
                try:
                    handler(event_name, data or {})
                except Exception as e:
                    logger.error(f"事件处理失败 {event_name}: {e}")
    
    def shutdown(self):
        """关闭插件系统"""
        for plugin_id in list(self._plugins.keys()):
            self.deactivate_plugin(plugin_id)
        
        self._plugins.clear()
        self._plugin_info.clear()
        logger.info("插件系统已关闭")