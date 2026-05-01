"""
Plugin System - 插件系统

核心功能：
1. 插件管理 - 安装、卸载、启用、禁用插件
2. 插件发现 - 自动发现可用插件
3. 插件通信 - 插件间通信机制
4. 扩展点 - 定义和使用扩展点

设计理念：
- 松耦合的插件架构
- 支持热插拔
- 统一的插件接口
"""

import json
import importlib
import os
import sys
from typing import Dict, Any, Optional, List, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    """插件状态"""
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


class PluginType(Enum):
    """插件类型"""
    CORE = "core"           # 核心插件
    FEATURE = "feature"     # 功能插件
    UTILITY = "utility"     # 工具插件
    INTEGRATION = "integration"  # 集成插件


@dataclass
class PluginInfo:
    """插件信息"""
    id: str
    name: str
    version: str
    description: str
    author: str
    type: PluginType
    status: PluginStatus
    entry_point: str
    dependencies: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    installed_at: datetime = field(default_factory=datetime.now)


@dataclass
class ExtensionPoint:
    """扩展点"""
    id: str
    name: str
    description: str
    interface: Type
    plugins: List[str] = field(default_factory=list)


class BasePlugin:
    """插件基类"""
    
    def __init__(self):
        self._info: Optional[PluginInfo] = None
    
    def initialize(self, info: PluginInfo):
        """初始化插件"""
        self._info = info
    
    def get_info(self) -> PluginInfo:
        """获取插件信息"""
        return self._info
    
    def activate(self):
        """激活插件"""
        pass
    
    def deactivate(self):
        """停用插件"""
        pass
    
    def get_extensions(self) -> Dict[str, Callable]:
        """获取插件扩展"""
        return {}


class PluginSystem:
    """
    插件系统
    
    核心特性：
    1. 插件管理 - 安装、卸载、启用、禁用插件
    2. 插件发现 - 自动发现可用插件
    3. 插件通信 - 插件间通信机制
    4. 扩展点 - 定义和使用扩展点
    """
    
    def __init__(self):
        self._plugins: Dict[str, PluginInfo] = {}
        self._loaded_plugins: Dict[str, BasePlugin] = {}
        self._extension_points: Dict[str, ExtensionPoint] = {}
        self._plugin_directory = "plugins"
        
        # 预定义扩展点
        self._register_default_extension_points()
        
        logger.info("✅ PluginSystem 初始化完成")
    
    def _register_default_extension_points(self):
        """注册默认扩展点"""
        extension_points = [
            ExtensionPoint(
                id="llm_provider",
                name="LLM服务商",
                description="扩展LLM服务商支持",
                interface=BasePlugin
            ),
            ExtensionPoint(
                id="code_generator",
                name="代码生成器",
                description="扩展代码生成能力",
                interface=BasePlugin
            ),
            ExtensionPoint(
                id="task_processor",
                name="任务处理器",
                description="扩展任务处理能力",
                interface=BasePlugin
            ),
            ExtensionPoint(
                id="ui_component",
                name="UI组件",
                description="扩展UI组件",
                interface=BasePlugin
            ),
            ExtensionPoint(
                id="data_source",
                name="数据源",
                description="扩展数据源支持",
                interface=BasePlugin
            )
        ]
        
        for ep in extension_points:
            self._extension_points[ep.id] = ep
    
    def set_plugin_directory(self, path: str):
        """设置插件目录"""
        self._plugin_directory = path
    
    def discover_plugins(self) -> List[str]:
        """
        发现插件
        
        Returns:
            插件ID列表
        """
        plugins = []
        
        if not os.path.exists(self._plugin_directory):
            return plugins
        
        for item in os.listdir(self._plugin_directory):
            item_path = os.path.join(self._plugin_directory, item)
            
            # 检查是否为插件目录
            if os.path.isdir(item_path):
                # 检查是否有插件定义文件
                plugin_json = os.path.join(item_path, "plugin.json")
                if os.path.exists(plugin_json):
                    try:
                        with open(plugin_json, 'r', encoding='utf-8') as f:
                            plugin_data = json.load(f)
                            plugins.append(plugin_data.get("id", item))
                    except Exception as e:
                        logger.error(f"读取插件定义失败: {item}, 错误: {e}")
        
        return plugins
    
    def install_plugin(self, plugin_id: str, source_path: str) -> bool:
        """
        安装插件
        
        Args:
            plugin_id: 插件ID
            source_path: 插件源码路径
        
        Returns:
            是否安装成功
        """
        try:
            # 读取插件定义
            plugin_json = os.path.join(source_path, "plugin.json")
            with open(plugin_json, 'r', encoding='utf-8') as f:
                plugin_data = json.load(f)
            
            # 创建插件信息
            info = PluginInfo(
                id=plugin_id,
                name=plugin_data.get("name", plugin_id),
                version=plugin_data.get("version", "1.0.0"),
                description=plugin_data.get("description", ""),
                author=plugin_data.get("author", "Unknown"),
                type=PluginType(plugin_data.get("type", "feature")),
                status=PluginStatus.INSTALLED,
                entry_point=plugin_data.get("entry_point", ""),
                dependencies=plugin_data.get("dependencies", []),
                config=plugin_data.get("config", {})
            )
            
            self._plugins[plugin_id] = info
            
            # 复制插件文件到插件目录
            import shutil
            dest_path = os.path.join(self._plugin_directory, plugin_id)
            if os.path.exists(dest_path):
                shutil.rmtree(dest_path)
            shutil.copytree(source_path, dest_path)
            
            logger.info(f"✅ 插件安装成功: {plugin_id}")
            return True
        
        except Exception as e:
            logger.error(f"插件安装失败: {plugin_id}, 错误: {e}")
            return False
    
    def uninstall_plugin(self, plugin_id: str) -> bool:
        """卸载插件"""
        if plugin_id not in self._plugins:
            return False
        
        # 如果插件已加载，先停用
        if plugin_id in self._loaded_plugins:
            self.disable_plugin(plugin_id)
        
        # 删除插件信息
        del self._plugins[plugin_id]
        
        # 删除插件文件
        plugin_path = os.path.join(self._plugin_directory, plugin_id)
        if os.path.exists(plugin_path):
            import shutil
            shutil.rmtree(plugin_path)
        
        logger.info(f"✅ 插件卸载成功: {plugin_id}")
        return True
    
    def enable_plugin(self, plugin_id: str) -> bool:
        """启用插件"""
        if plugin_id not in self._plugins:
            return False
        
        info = self._plugins[plugin_id]
        
        try:
            # 添加插件目录到路径
            plugin_path = os.path.join(self._plugin_directory, plugin_id)
            if plugin_path not in sys.path:
                sys.path.insert(0, plugin_path)
            
            # 加载插件模块
            if info.entry_point:
                module_name, class_name = info.entry_point.rsplit('.', 1)
                module = importlib.import_module(module_name)
                plugin_class = getattr(module, class_name)
                
                # 实例化插件
                plugin = plugin_class()
                plugin.initialize(info)
                plugin.activate()
                
                self._loaded_plugins[plugin_id] = plugin
                
                # 更新状态
                info.status = PluginStatus.ENABLED
                
                # 注册扩展
                self._register_extensions(plugin_id)
                
                logger.info(f"✅ 插件启用成功: {plugin_id}")
                return True
        
        except Exception as e:
            logger.error(f"插件启用失败: {plugin_id}, 错误: {e}")
            info.status = PluginStatus.ERROR
            return False
        
        return False
    
    def disable_plugin(self, plugin_id: str) -> bool:
        """禁用插件"""
        if plugin_id not in self._loaded_plugins:
            return False
        
        plugin = self._loaded_plugins[plugin_id]
        
        try:
            plugin.deactivate()
            del self._loaded_plugins[plugin_id]
            
            # 更新状态
            self._plugins[plugin_id].status = PluginStatus.DISABLED
            
            logger.info(f"✅ 插件禁用成功: {plugin_id}")
            return True
        
        except Exception as e:
            logger.error(f"插件禁用失败: {plugin_id}, 错误: {e}")
            return False
    
    def _register_extensions(self, plugin_id: str):
        """注册插件扩展"""
        plugin = self._loaded_plugins.get(plugin_id)
        if not plugin:
            return
        
        extensions = plugin.get_extensions()
        for ext_id, ext_func in extensions.items():
            # 查找匹配的扩展点
            for ep in self._extension_points.values():
                # 简单匹配：检查扩展名是否包含扩展点ID
                if ep.id.lower() in ext_id.lower():
                    if plugin_id not in ep.plugins:
                        ep.plugins.append(plugin_id)
    
    def get_extensions(self, extension_point_id: str) -> List[Callable]:
        """
        获取扩展点的所有扩展
        
        Args:
            extension_point_id: 扩展点ID
        
        Returns:
            扩展函数列表
        """
        ep = self._extension_points.get(extension_point_id)
        if not ep:
            return []
        
        extensions = []
        for plugin_id in ep.plugins:
            plugin = self._loaded_plugins.get(plugin_id)
            if plugin:
                plugin_extensions = plugin.get_extensions()
                for ext_id, ext_func in plugin_extensions.items():
                    if extension_point_id.lower() in ext_id.lower():
                        extensions.append(ext_func)
        
        return extensions
    
    def get_plugins(self, status: Optional[PluginStatus] = None) -> List[PluginInfo]:
        """获取插件列表"""
        if status:
            return [p for p in self._plugins.values() if p.status == status]
        return list(self._plugins.values())
    
    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        return self._plugins.get(plugin_id)
    
    def call_extension(self, extension_point_id: str, *args, **kwargs) -> List[Any]:
        """
        调用扩展点的所有扩展
        
        Args:
            extension_point_id: 扩展点ID
        
        Returns:
            所有扩展的返回值列表
        """
        results = []
        extensions = self.get_extensions(extension_point_id)
        
        for ext in extensions:
            try:
                result = ext(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"扩展调用失败: {e}")
        
        return results


# 全局单例
_global_plugin_system: Optional[PluginSystem] = None


def get_plugin_system() -> PluginSystem:
    """获取全局插件系统单例"""
    global _global_plugin_system
    if _global_plugin_system is None:
        _global_plugin_system = PluginSystem()
    return _global_plugin_system


# 测试插件示例
class TestPlugin(BasePlugin):
    """测试插件"""
    
    def activate(self):
        print("🔌 测试插件已激活")
    
    def deactivate(self):
        print("🔌 测试插件已停用")
    
    def get_extensions(self):
        return {
            "llm_provider_test": self.test_llm_provider,
            "code_generator_test": self.test_code_generator
        }
    
    def test_llm_provider(self, *args, **kwargs):
        return {"provider": "test", "result": "success"}
    
    def test_code_generator(self, *args, **kwargs):
        return {"generator": "test", "result": "success"}


# 测试函数
def test_plugin_system():
    """测试插件系统"""
    print("🧪 测试插件系统")
    print("="*60)
    
    plugin_system = get_plugin_system()
    
    # 发现插件
    print("\n🔍 发现插件:")
    plugins = plugin_system.discover_plugins()
    print(f"   发现 {len(plugins)} 个插件")
    
    # 安装测试插件
    print("\n📦 安装测试插件:")
    # 创建临时插件目录
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建插件定义
        plugin_dir = os.path.join(tmpdir, "test_plugin")
        os.makedirs(plugin_dir)
        
        plugin_def = {
            "id": "test_plugin",
            "name": "测试插件",
            "version": "1.0.0",
            "description": "测试插件描述",
            "author": "Test",
            "type": "feature",
            "entry_point": "test_plugin.main.TestPlugin",
            "dependencies": []
        }
        
        with open(os.path.join(plugin_dir, "plugin.json"), 'w', encoding='utf-8') as f:
            json.dump(plugin_def, f)
        
        # 创建插件代码
        main_dir = os.path.join(plugin_dir, "test_plugin")
        os.makedirs(main_dir)
        
        with open(os.path.join(main_dir, "__init__.py"), 'w') as f:
            pass
        
        plugin_code = """
from business.plugin_system import BasePlugin

class TestPlugin(BasePlugin):
    def activate(self):
        pass
    def deactivate(self):
        pass
    def get_extensions(self):
        return {
            "llm_provider_test": lambda: {"provider": "test"}
        }
"""
        with open(os.path.join(main_dir, "main.py"), 'w') as f:
            f.write(plugin_code)
        
        # 安装插件
        success = plugin_system.install_plugin("test_plugin", plugin_dir)
        print(f"   安装成功: {success}")
    
    # 获取插件列表
    print("\n📋 插件列表:")
    plugins = plugin_system.get_plugins()
    for p in plugins:
        print(f"   {p.id} - {p.name} ({p.status.value})")
    
    print("\n🎉 插件系统测试完成！")
    return True


if __name__ == "__main__":
    test_plugin_system()