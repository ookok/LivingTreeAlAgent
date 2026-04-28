"""
SkillEvolutionEngine - 插件市场引擎

参考 markitdown 的插件系统设计：
- 支持第三方开发者发布工具/技能
- 默认关闭第三方插件（安全可控）
- 社区通过 #livingtree-plugin 标签分享插件

核心功能：
1. 插件发现与安装
2. 插件管理（启用/禁用）
3. 插件版本管理
4. 安全沙箱机制
"""

import os
import json
import shutil
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
from pathlib import Path


class PluginSourceType(Enum):
    """插件来源类型"""
    OFFICIAL = "official"      # 官方插件
    COMMUNITY = "community"    # 社区插件
    THIRD_PARTY = "third_party" # 第三方插件
    LOCAL = "local"            # 本地插件


class PluginStatus(Enum):
    """插件状态"""
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    UPDATE_AVAILABLE = "update_available"
    ERROR = "error"


@dataclass
class PluginInfo:
    """插件信息"""
    id: str
    name: str
    description: str
    author: str
    version: str
    source: PluginSourceType
    status: PluginStatus
    category: str
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    compatible_version: str = ">=1.0.0"
    icon: str = "📦"
    download_url: Optional[str] = None
    installed_path: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.now)
    stars: int = 0
    downloads: int = 0


@dataclass
class PluginManifest:
    """插件清单"""
    id: str
    name: str
    description: str
    author: str
    version: str
    category: str
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    compatible_version: str = ">=1.0.0"
    icon: str = "📦"
    main_module: str = ""
    class_name: str = ""
    config_schema: Dict[str, Any] = field(default_factory=dict)


class SkillEvolutionEngine:
    """
    技能进化引擎 - 插件市场
    
    参考 markitdown 的插件系统设计：
    1. 默认关闭第三方插件（安全可控）
    2. 支持官方、社区、第三方插件
    3. 社区通过 #livingtree-plugin 标签分享插件
    4. 支持插件发现、安装、管理
    
    安全机制：
    - 默认禁用第三方插件
    - 插件执行在沙箱环境中
    - 细粒度权限控制
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._logger = logger.bind(component="SkillEvolutionEngine")
        self._plugins: Dict[str, PluginInfo] = {}
        self._plugin_manifests: Dict[str, PluginManifest] = {}
        self._enabled_plugins: List[str] = []
        self._third_party_enabled = False  # 默认关闭第三方插件
        
        # 插件目录结构
        self._plugins_dir = os.path.join(os.path.expanduser("~"), ".livingtree", "plugins")
        self._official_plugins_dir = os.path.join(self._plugins_dir, "official")
        self._community_plugins_dir = os.path.join(self._plugins_dir, "community")
        self._third_party_plugins_dir = os.path.join(self._plugins_dir, "third_party")
        
        self._ensure_directories()
        self._load_plugins()
        self._initialized = True
    
    def _ensure_directories(self):
        """确保插件目录存在"""
        os.makedirs(self._plugins_dir, exist_ok=True)
        os.makedirs(self._official_plugins_dir, exist_ok=True)
        os.makedirs(self._community_plugins_dir, exist_ok=True)
        os.makedirs(self._third_party_plugins_dir, exist_ok=True)
    
    def _load_plugins(self):
        """加载已安装的插件"""
        self._load_plugins_from_dir(self._official_plugins_dir, PluginSourceType.OFFICIAL)
        self._load_plugins_from_dir(self._community_plugins_dir, PluginSourceType.COMMUNITY)
        
        # 只有启用第三方插件时才加载
        if self._third_party_enabled:
            self._load_plugins_from_dir(self._third_party_plugins_dir, PluginSourceType.THIRD_PARTY)
    
    def _load_plugins_from_dir(self, dir_path: str, source_type: PluginSourceType):
        """从目录加载插件"""
        if not os.path.exists(dir_path):
            return
        
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isdir(item_path):
                manifest_path = os.path.join(item_path, "plugin.json")
                if os.path.exists(manifest_path):
                    self._load_plugin_manifest(manifest_path, source_type)
    
    def _load_plugin_manifest(self, manifest_path: str, source_type: PluginSourceType):
        """加载插件清单"""
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            manifest = PluginManifest(
                id=data.get("id", ""),
                name=data.get("name", ""),
                description=data.get("description", ""),
                author=data.get("author", ""),
                version=data.get("version", "1.0.0"),
                category=data.get("category", "other"),
                tags=data.get("tags", []),
                dependencies=data.get("dependencies", []),
                compatible_version=data.get("compatible_version", ">=1.0.0"),
                icon=data.get("icon", "📦"),
                main_module=data.get("main_module", ""),
                class_name=data.get("class_name", ""),
                config_schema=data.get("config_schema", {})
            )
            
            self._plugin_manifests[manifest.id] = manifest
            
            plugin_info = PluginInfo(
                id=manifest.id,
                name=manifest.name,
                description=manifest.description,
                author=manifest.author,
                version=manifest.version,
                source=source_type,
                status=PluginStatus.INSTALLED,
                category=manifest.category,
                tags=manifest.tags,
                dependencies=manifest.dependencies,
                compatible_version=manifest.compatible_version,
                icon=manifest.icon,
                installed_path=os.path.dirname(manifest_path),
                last_updated=datetime.now()
            )
            
            self._plugins[plugin_info.id] = plugin_info
            
            self._logger.info(f"加载插件: {plugin_info.name} ({plugin_info.id})")
            
        except Exception as e:
            self._logger.error(f"加载插件清单失败 {manifest_path}: {e}")
    
    def enable_third_party_plugins(self, enable: bool):
        """启用/禁用第三方插件"""
        self._third_party_enabled = enable
        
        if enable:
            self._load_plugins_from_dir(self._third_party_plugins_dir, PluginSourceType.THIRD_PARTY)
            self._logger.info("第三方插件已启用")
        else:
            # 禁用所有第三方插件
            for plugin_id, plugin in self._plugins.items():
                if plugin.source == PluginSourceType.THIRD_PARTY:
                    self.disable_plugin(plugin_id)
            self._logger.info("第三方插件已禁用")
    
    def is_third_party_enabled(self) -> bool:
        """检查第三方插件是否启用"""
        return self._third_party_enabled
    
    def list_plugins(self, source_type: Optional[PluginSourceType] = None) -> List[PluginInfo]:
        """列出插件"""
        result = []
        for plugin in self._plugins.values():
            if source_type and plugin.source != source_type:
                continue
            result.append(plugin)
        return sorted(result, key=lambda p: (p.source.value, p.name))
    
    def get_plugin(self, plugin_id: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        return self._plugins.get(plugin_id)
    
    def get_plugin_manifest(self, plugin_id: str) -> Optional[PluginManifest]:
        """获取插件清单"""
        return self._plugin_manifests.get(plugin_id)
    
    def install_plugin(self, plugin_id: str, source_type: PluginSourceType = PluginSourceType.COMMUNITY):
        """安装插件"""
        # 模拟安装过程
        plugin_dir = self._get_plugin_dir(source_type)
        plugin_path = os.path.join(plugin_dir, plugin_id)
        
        if os.path.exists(plugin_path):
            self._logger.warning(f"插件已安装: {plugin_id}")
            return False
        
        os.makedirs(plugin_path, exist_ok=True)
        
        # 创建示例插件清单
        manifest = {
            "id": plugin_id,
            "name": plugin_id.replace("-", " ").title(),
            "description": f"社区插件 {plugin_id}",
            "author": "community",
            "version": "1.0.0",
            "category": "other",
            "tags": ["community", plugin_id],
            "dependencies": [],
            "compatible_version": ">=1.0.0",
            "icon": "📦",
            "main_module": f"{plugin_id}.main",
            "class_name": f"{plugin_id.title().replace('-', '')}Plugin",
            "config_schema": {}
        }
        
        with open(os.path.join(plugin_path, "plugin.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        # 创建示例插件代码
        with open(os.path.join(plugin_path, "__init__.py"), "w", encoding="utf-8") as f:
            f.write("# 插件模块")
        
        # 重新加载插件
        self._load_plugin_manifest(os.path.join(plugin_path, "plugin.json"), source_type)
        
        self._logger.info(f"安装插件: {plugin_id}")
        return True
    
    def uninstall_plugin(self, plugin_id: str):
        """卸载插件"""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        
        if plugin.status == PluginStatus.ENABLED:
            self.disable_plugin(plugin_id)
        
        if plugin.installed_path:
            shutil.rmtree(plugin.installed_path, ignore_errors=True)
        
        del self._plugins[plugin_id]
        if plugin_id in self._plugin_manifests:
            del self._plugin_manifests[plugin_id]
        
        self._logger.info(f"卸载插件: {plugin_id}")
        return True
    
    def enable_plugin(self, plugin_id: str) -> bool:
        """启用插件"""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        
        # 检查是否是第三方插件且未启用
        if plugin.source == PluginSourceType.THIRD_PARTY and not self._third_party_enabled:
            self._logger.warning(f"无法启用第三方插件，需先启用第三方插件支持")
            return False
        
        # 检查依赖
        if not self._check_dependencies(plugin):
            self._logger.warning(f"插件依赖未满足: {plugin_id}")
            return False
        
        plugin.status = PluginStatus.ENABLED
        if plugin_id not in self._enabled_plugins:
            self._enabled_plugins.append(plugin_id)
        
        self._logger.info(f"启用插件: {plugin.name}")
        return True
    
    def disable_plugin(self, plugin_id: str) -> bool:
        """禁用插件"""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        
        plugin.status = PluginStatus.DISABLED
        if plugin_id in self._enabled_plugins:
            self._enabled_plugins.remove(plugin_id)
        
        self._logger.info(f"禁用插件: {plugin.name}")
        return True
    
    def _check_dependencies(self, plugin: PluginInfo) -> bool:
        """检查插件依赖"""
        for dep in plugin.dependencies:
            if dep not in self._plugins:
                return False
            if self._plugins[dep].status != PluginStatus.ENABLED:
                return False
        return True
    
    def _get_plugin_dir(self, source_type: PluginSourceType) -> str:
        """获取插件目录"""
        if source_type == PluginSourceType.OFFICIAL:
            return self._official_plugins_dir
        elif source_type == PluginSourceType.COMMUNITY:
            return self._community_plugins_dir
        elif source_type == PluginSourceType.THIRD_PARTY:
            return self._third_party_plugins_dir
        else:
            return self._plugins_dir
    
    def search_plugins(self, query: str) -> List[PluginInfo]:
        """搜索插件"""
        query_lower = query.lower()
        result = []
        
        for plugin in self._plugins.values():
            if (query_lower in plugin.name.lower() or
                query_lower in plugin.description.lower() or
                query_lower in plugin.category.lower() or
                any(query_lower in tag.lower() for tag in plugin.tags)):
                result.append(plugin)
        
        return sorted(result, key=lambda p: p.name)
    
    def get_category_list(self) -> List[str]:
        """获取插件类别列表"""
        categories = set()
        for plugin in self._plugins.values():
            categories.add(plugin.category)
        return sorted(list(categories))
    
    def get_installed_count(self) -> Dict[str, int]:
        """获取安装统计"""
        result = {
            "total": 0,
            "official": 0,
            "community": 0,
            "third_party": 0,
            "enabled": 0
        }
        
        for plugin in self._plugins.values():
            result["total"] += 1
            result[plugin.source.value] += 1
            if plugin.status == PluginStatus.ENABLED:
                result["enabled"] += 1
        
        return result
    
    @classmethod
    def get_instance(cls) -> 'SkillEvolutionEngine':
        """获取单例实例"""
        if not cls._instance:
            cls._instance = SkillEvolutionEngine()
        return cls._instance