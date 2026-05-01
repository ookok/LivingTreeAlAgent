import importlib
import os
import json
from typing import List, Dict, Any, Optional, Type
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod

class PluginType(Enum):
    TOOL = "tool"
    UI = "ui"
    SERVICE = "service"
    MODIFIER = "modifier"
    STORAGE = "storage"

class PluginStatus(Enum):
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"

@dataclass
class PluginInfo:
    id: str
    name: str
    description: str
    version: str
    author: str
    type: PluginType
    status: PluginStatus
    dependencies: List[str] = None
    settings: Dict[str, Any] = None
    metadata: Dict[str, Any] = None

class BasePlugin(ABC):
    """插件基类"""
    
    def __init__(self, plugin_info: PluginInfo):
        self.plugin_info = plugin_info
        self._initialized = False
    
    @abstractmethod
    def initialize(self):
        """初始化插件"""
        pass
    
    @abstractmethod
    def shutdown(self):
        """关闭插件"""
        pass
    
    def is_initialized(self) -> bool:
        return self._initialized

class ToolPlugin(BasePlugin):
    """工具插件"""
    
    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """获取插件提供的工具"""
        pass

class UIPlugin(BasePlugin):
    """UI插件"""
    
    @abstractmethod
    def get_components(self) -> List[Dict[str, Any]]:
        """获取插件提供的UI组件"""
        pass

class ServicePlugin(BasePlugin):
    """服务插件"""
    
    @abstractmethod
    def start_service(self):
        """启动服务"""
        pass
    
    @abstractmethod
    def stop_service(self):
        """停止服务"""
        pass

class ModifierPlugin(BasePlugin):
    """修改器插件"""
    
    @abstractmethod
    def modify_input(self, input_data: Any) -> Any:
        """修改输入数据"""
        pass
    
    @abstractmethod
    def modify_output(self, output_data: Any) -> Any:
        """修改输出数据"""
        pass

class StoragePlugin(BasePlugin):
    """存储插件"""
    
    @abstractmethod
    def save(self, key: str, data: Any):
        """保存数据"""
        pass
    
    @abstractmethod
    def load(self, key: str) -> Any:
        """加载数据"""
        pass
    
    @abstractmethod
    def delete(self, key: str):
        """删除数据"""
        pass

class PluginManager:
    """插件管理器"""
    
    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_info_cache: Dict[str, PluginInfo] = {}
        self._discover_plugins()
    
    def _discover_plugins(self):
        """发现插件"""
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir)
            return
        
        for item in os.listdir(self.plugins_dir):
            item_path = os.path.join(self.plugins_dir, item)
            if os.path.isdir(item_path):
                self._load_plugin(item_path)
    
    def _load_plugin(self, plugin_dir: str):
        """加载插件"""
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            return
        
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            plugin_info = PluginInfo(
                id=manifest.get("id", os.path.basename(plugin_dir)),
                name=manifest.get("name", ""),
                description=manifest.get("description", ""),
                version=manifest.get("version", "1.0.0"),
                author=manifest.get("author", ""),
                type=PluginType(manifest.get("type", "tool")),
                status=PluginStatus.INSTALLED,
                dependencies=manifest.get("dependencies", []),
                settings=manifest.get("settings", {}),
                metadata=manifest.get("metadata", {})
            )
            
            main_module = manifest.get("main", "main")
            module_path = os.path.join(plugin_dir, f"{main_module}.py")
            
            if os.path.exists(module_path):
                spec = importlib.util.spec_from_file_location(plugin_info.id, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                plugin_class = getattr(module, manifest.get("class", "Plugin"))
                plugin = plugin_class(plugin_info)
                
                self.plugins[plugin_info.id] = plugin
                self.plugin_info_cache[plugin_info.id] = plugin_info
        
        except Exception as e:
            print(f"加载插件失败 {plugin_dir}: {e}")
    
    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """获取插件"""
        return self.plugins.get(plugin_id)
    
    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        return self.plugin_info_cache.get(plugin_id)
    
    def get_all_plugins(self) -> List[PluginInfo]:
        """获取所有插件信息"""
        return list(self.plugin_info_cache.values())
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[PluginInfo]:
        """按类型获取插件"""
        return [p for p in self.plugin_info_cache.values() if p.type == plugin_type]
    
    def initialize_plugin(self, plugin_id: str) -> bool:
        """初始化插件"""
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return False
        
        try:
            plugin.initialize()
            plugin_info = self.plugin_info_cache.get(plugin_id)
            if plugin_info:
                plugin_info.status = PluginStatus.ENABLED
            return True
        except Exception as e:
            plugin_info = self.plugin_info_cache.get(plugin_id)
            if plugin_info:
                plugin_info.status = PluginStatus.ERROR
            return False
    
    def shutdown_plugin(self, plugin_id: str):
        """关闭插件"""
        plugin = self.get_plugin(plugin_id)
        if plugin:
            plugin.shutdown()
            plugin_info = self.plugin_info_cache.get(plugin_id)
            if plugin_info:
                plugin_info.status = PluginStatus.DISABLED
    
    def initialize_all_plugins(self):
        """初始化所有插件"""
        for plugin_id in self.plugins:
            self.initialize_plugin(plugin_id)
    
    def shutdown_all_plugins(self):
        """关闭所有插件"""
        for plugin_id in self.plugins:
            self.shutdown_plugin(plugin_id)
    
    def install_plugin(self, plugin_path: str) -> bool:
        """安装插件"""
        try:
            import shutil
            
            plugin_name = os.path.basename(plugin_path)
            dest_path = os.path.join(self.plugins_dir, plugin_name)
            
            if os.path.exists(dest_path):
                shutil.rmtree(dest_path)
            
            if os.path.isdir(plugin_path):
                shutil.copytree(plugin_path, dest_path)
            else:
                shutil.copy(plugin_path, dest_path)
            
            self._load_plugin(dest_path)
            return True
        except Exception as e:
            print(f"安装插件失败: {e}")
            return False
    
    def uninstall_plugin(self, plugin_id: str) -> bool:
        """卸载插件"""
        plugin_info = self.plugin_info_cache.get(plugin_id)
        if not plugin_info:
            return False
        
        self.shutdown_plugin(plugin_id)
        
        plugin_path = os.path.join(self.plugins_dir, plugin_id)
        if os.path.exists(plugin_path):
            import shutil
            shutil.rmtree(plugin_path)
        
        if plugin_id in self.plugins:
            del self.plugins[plugin_id]
        if plugin_id in self.plugin_info_cache:
            del self.plugin_info_cache[plugin_id]
        
        return True
    
    def get_plugin_stats(self) -> Dict[str, Any]:
        """获取插件统计"""
        stats = {
            "total_plugins": len(self.plugins),
            "enabled_plugins": sum(1 for p in self.plugin_info_cache.values() if p.status == PluginStatus.ENABLED),
            "disabled_plugins": sum(1 for p in self.plugin_info_cache.values() if p.status == PluginStatus.DISABLED),
            "type_distribution": {}
        }
        
        for plugin_type in PluginType:
            count = sum(1 for p in self.plugin_info_cache.values() if p.type == plugin_type)
            stats["type_distribution"][plugin_type.value] = count
        
        return stats