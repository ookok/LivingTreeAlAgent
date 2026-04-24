# -*- coding: utf-8 -*-
"""
插件市场模块 - Plugin Marketplace
==================================

功能：
1. 插件注册与发现
2. 插件商店浏览
3. 安装与卸载
4. 版本管理
5. 评分与评论

Author: Hermes Desktop Team
"""

from .plugin import Plugin, PluginCategory, PluginVersion
from .store import PluginStore, PluginListing
from .manager import PluginManager
from .installer import PluginInstaller

__all__ = [
    'Plugin',
    'PluginCategory',
    'PluginVersion',
    'PluginStore',
    'PluginListing',
    'PluginManager',
    'PluginInstaller',
]
