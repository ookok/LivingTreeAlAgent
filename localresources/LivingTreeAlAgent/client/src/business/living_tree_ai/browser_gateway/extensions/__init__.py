"""
浏览器扩展系统

借鉴 qutebrowser 的插件系统，为 AI 增强浏览器提供扩展功能
"""

from .extension_manager import ExtensionManager, get_extension_manager
from .plugin_system import PluginSystem, get_plugin_system
from .user_scripts import UserScriptManager, get_user_script_manager
from .api import ExtensionAPI

__all__ = [
    "ExtensionManager",
    "get_extension_manager",
    "PluginSystem",
    "get_plugin_system",
    "UserScriptManager",
    "get_user_script_manager",
    "ExtensionAPI"
]
