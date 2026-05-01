"""
核心模块 - Core Modules

功能：
1. 性能优化
2. 插件系统
3. 状态管理
4. 主题系统
5. 窗口管理
6. 命令系统
"""

from .performance_optimization import OptimizedWebEngineView
from .plugin_system import PluginSystem, PluginInterface, PluginInfo, PluginState
from .state_manager import Store, Action, Reducer, Middleware, get_store
from .theme_system import ThemeSystem, ThemeType
from .window_manager import WindowManager, Panel, PanelPosition
from .command_system import CommandSystem, Command, get_command_system

__all__ = [
    # 性能优化
    'OptimizedWebEngineView',
    
    # 插件系统
    'PluginSystem',
    'PluginInterface',
    'PluginInfo',
    'PluginState',
    
    # 状态管理
    'Store',
    'Action',
    'Reducer',
    'Middleware',
    'get_store',
    
    # 主题系统
    'ThemeSystem',
    'ThemeType',
    
    # 窗口管理
    'WindowManager',
    'Panel',
    'PanelPosition',
    
    # 命令系统
    'CommandSystem',
    'Command',
    'get_command_system',
]