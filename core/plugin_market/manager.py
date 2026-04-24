# -*- coding: utf-8 -*-
"""
插件管理器 - Plugin Manager
"""

from __future__ import annotations
import json
import logging
import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable

from .plugin import Plugin, PluginStatus
from .store import get_plugin_store
from .installer import PluginInstaller

logger = logging.getLogger(__name__)


@dataclass
class InstalledPlugin:
    """已安装插件"""
    plugin_id: str = ""
    name: str = ""
    version: str = ""
    installed_at: datetime = field(default_factory=datetime.now)
    enabled: bool = True
    settings: Dict = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "installed_at": self.installed_at.isoformat(),
            "enabled": self.enabled,
            "settings": self.settings,
            "error": self.error
        }


class PluginManager:
    """
    插件管理器
    
    管理本地插件的安装、启用、禁用、更新
    """
    
    def __init__(self, plugins_dir: Optional[str] = None):
        # 默认插件目录
        if plugins_dir is None:
            home = os.path.expanduser("~")
            plugins_dir = os.path.join(home, ".livingtree", "plugins")
        
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置文件
        self.config_file = self.plugins_dir / "plugins.json"
        
        # 已安装插件
        self._installed: Dict[str, InstalledPlugin] = {}
        self._plugins: Dict[str, Plugin] = {}  # 本地插件定义
        
        # 加载已安装插件
        self._load_installed()
        
        # 商店和安装器
        self._store = get_plugin_store()
        self._installer = PluginInstaller(self.plugins_dir)
    
    # ── 生命周期 ──────────────────────────────────────────────────────────────
    
    def install(self, plugin_id: str) -> bool:
        """安装插件"""
        # 获取插件信息
        plugin = self._store.get_plugin(plugin_id)
        if not plugin:
            logger.error(f"Plugin not found: {plugin_id}")
            return False
        
        # 检查是否已安装
        if plugin_id in self._installed:
            logger.warning(f"Plugin already installed: {plugin_id}")
            return False
        
        # 执行安装
        latest_version = plugin.get_latest_version()
        if not latest_version:
            logger.error(f"No available version: {plugin_id}")
            return False
        
        try:
            success = self._installer.install(
                plugin_id=plugin_id,
                download_url=latest_version.download_url,
                version=latest_version.version,
                permissions=plugin.required_permissions
            )
            
            if success:
                # 记录安装
                installed = InstalledPlugin(
                    plugin_id=plugin_id,
                    name=plugin.name,
                    version=latest_version.version
                )
                self._installed[plugin_id] = installed
                self._save_installed()
                
                logger.info(f"Plugin installed: {plugin_id}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Installation failed: {e}")
            return False
    
    def uninstall(self, plugin_id: str) -> bool:
        """卸载插件"""
        if plugin_id not in self._installed:
            return False
        
        # 先禁用
        if self._installed[plugin_id].enabled:
            self.disable(plugin_id)
        
        try:
            # 执行卸载
            success = self._installer.uninstall(plugin_id)
            
            if success:
                del self._installed[plugin_id]
                self._save_installed()
                logger.info(f"Plugin uninstalled: {plugin_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Uninstallation failed: {e}")
            return False
    
    def enable(self, plugin_id: str) -> bool:
        """启用插件"""
        if plugin_id not in self._installed:
            return False
        
        plugin = self._installed[plugin_id]
        
        if plugin.enabled:
            return True
        
        # 尝试加载
        if self._try_load_plugin(plugin_id):
            plugin.enabled = True
            plugin.error = None
            self._save_installed()
            logger.info(f"Plugin enabled: {plugin_id}")
            return True
        else:
            plugin.error = "Failed to load plugin"
            self._save_installed()
            return False
    
    def disable(self, plugin_id: str) -> bool:
        """禁用插件"""
        if plugin_id not in self._installed:
            return False
        
        plugin = self._installed[plugin_id]
        plugin.enabled = False
        self._save_installed()
        
        # 卸载插件代码
        self._unload_plugin(plugin_id)
        
        logger.info(f"Plugin disabled: {plugin_id}")
        return True
    
    def update(self, plugin_id: str) -> bool:
        """更新插件"""
        if plugin_id not in self._installed:
            return False
        
        current = self._installed[plugin_id]
        
        # 获取最新版本
        plugin = self._store.get_plugin(plugin_id)
        if not plugin or not plugin.has_update():
            logger.info("No update available")
            return False
        
        latest = plugin.get_latest_version()
        if not latest:
            return False
        
        try:
            # 禁用旧版本
            self.disable(plugin_id)
            
            # 执行更新
            success = self._installer.update(
                plugin_id=plugin_id,
                download_url=latest.download_url,
                version=latest.version
            )
            
            if success:
                current.version = latest.version
                current.error = None
                self._save_installed()
                
                # 重新启用
                self.enable(plugin_id)
                
                logger.info(f"Plugin updated: {plugin_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return False
    
    # ── 加载管理 ──────────────────────────────────────────────────────────────
    
    def _try_load_plugin(self, plugin_id: str) -> bool:
        """尝试加载插件"""
        plugin_dir = self.plugins_dir / plugin_id
        
        if not plugin_dir.exists():
            return False
        
        # 检查主文件
        main_file = plugin_dir / "main.py"
        if not main_file.exists():
            return False
        
        try:
            # 动态导入
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                f"plugins.{plugin_id}.main",
                main_file
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys = __import__('sys')
                sys.modules[f"plugins.{plugin_id}.main"] = module
                spec.loader.exec_module(module)
                
                # 调用初始化
                if hasattr(module, 'on_enable'):
                    module.on_enable()
                
                return True
            
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_id}: {e}")
        
        return False
    
    def _unload_plugin(self, plugin_id: str):
        """卸载插件代码"""
        import sys
        mod_name = f"plugins.{plugin_id}"
        
        # 调用禁用钩子
        if mod_name in sys.modules:
            module = sys.modules[mod_name]
            if hasattr(module, 'on_disable'):
                try:
                    module.on_disable()
                except:
                    pass
        
        # 移除模块
        for key in list(sys.modules.keys()):
            if key.startswith(mod_name):
                del sys.modules[key]
    
    # ── 查询 ──────────────────────────────────────────────────────────────────
    
    def get_installed(self) -> List[InstalledPlugin]:
        """获取已安装插件"""
        return list(self._installed.values())
    
    def get_enabled(self) -> List[InstalledPlugin]:
        """获取已启用插件"""
        return [p for p in self._installed.values() if p.enabled]
    
    def get_update_available(self) -> List[Plugin]:
        """获取有更新的插件"""
        updates = []
        for installed in self._installed.values():
            plugin = self._store.get_plugin(installed.plugin_id)
            if plugin and plugin.has_update():
                updates.append(plugin)
        return updates
    
    def is_installed(self, plugin_id: str) -> bool:
        """是否已安装"""
        return plugin_id in self._installed
    
    def is_enabled(self, plugin_id: str) -> bool:
        """是否已启用"""
        return self._installed.get(plugin_id, InstalledPlugin()).enabled
    
    # ── 设置 ──────────────────────────────────────────────────────────────────
    
    def get_settings(self, plugin_id: str) -> Dict:
        """获取插件设置"""
        plugin = self._installed.get(plugin_id)
        if not plugin:
            return {}
        return plugin.settings
    
    def update_settings(self, plugin_id: str, settings: Dict) -> bool:
        """更新插件设置"""
        plugin = self._installed.get(plugin_id)
        if not plugin:
            return False
        
        plugin.settings.update(settings)
        self._save_installed()
        return True
    
    # ── 持久化 ────────────────────────────────────────────────────────────────
    
    def _load_installed(self):
        """加载已安装插件"""
        if not self.config_file.exists():
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for plugin_id, plugin_data in data.items():
                installed = InstalledPlugin(
                    plugin_id=plugin_id,
                    name=plugin_data.get('name', plugin_id),
                    version=plugin_data.get('version', '1.0.0'),
                    installed_at=datetime.fromisoformat(
                        plugin_data.get('installed_at', datetime.now().isoformat())
                    ),
                    enabled=plugin_data.get('enabled', True),
                    settings=plugin_data.get('settings', {})
                )
                self._installed[plugin_id] = installed
                
        except Exception as e:
            logger.error(f"Failed to load installed plugins: {e}")
    
    def _save_installed(self):
        """保存已安装插件"""
        try:
            data = {}
            for plugin_id, plugin in self._installed.items():
                data[plugin_id] = {
                    "name": plugin.name,
                    "version": plugin.version,
                    "installed_at": plugin.installed_at.isoformat(),
                    "enabled": plugin.enabled,
                    "settings": plugin.settings
                }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save installed plugins: {e}")


# ── 全局实例 ──────────────────────────────────────────────────────────────────

_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """获取插件管理器"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager
