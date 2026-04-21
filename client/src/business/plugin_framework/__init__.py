"""
万能客户端插件化架构 - Plugin Framework

核心设计理念：主框架为容器，插件为灵魂
支持三种视图模式：标签页视图、停靠窗口、独立窗口

目录结构：
plugin_framework/
├── __init__.py
├── base_plugin.py          # 插件基类
├── plugin_manager.py       # 插件管理器
├── event_bus.py            # 统一事件总线
├── view_factory.py          # 视图工厂（三种视图模式）
├── theme_system.py          # 主题系统（三层结构）
├── layout_manager.py        # 布局管理器
├── plugin_manifest.py       # 插件清单
├── data_sharing.py          # 数据共享机制
└── plugins/                 # 内置插件示例
    ├── __init__.py
    ├── knowledge_base/      # 知识库插件
    ├── ai_chat/            # AI聊天插件
    └── im_client/          # IM客户端插件
"""

from .plugin_manager import PluginManager, get_plugin_manager
from .event_bus import EventBus, get_event_bus, Event, EventPriority
from .view_factory import ViewFactory, ViewMode, ViewConfig, BaseView
from .theme_system import ThemeSystem, get_theme_system, ThemeLevel, Theme, ThemeColors
from .layout_manager import LayoutManager, get_layout_manager, LayoutTemplate, LayoutConfig, ViewState
from .base_plugin import (
    BasePlugin, PluginFramework, PluginManifest, PluginType,
    ViewPreference, ViewMode as VM, PluginState, PluginInfo
)
from .plugin_manifest import ManifestLoader, ManifestExporter, ManifestValidator, create_plugin_skeleton
from .data_sharing import (
    DataFormat, SharedData,
    ClipboardEnhancer, DragDropManager, SharedWorkspace,
    get_clipboard, get_drag_drop, get_workspace
)

# 插件
from .plugins import KnowledgeBasePlugin, AIChatPlugin, IMClientPlugin

__all__ = [
    # 核心类
    'PluginManager',
    'get_plugin_manager',
    'EventBus',
    'get_event_bus',
    'Event',
    'EventPriority',
    'ViewFactory',
    'ViewMode',
    'ViewConfig',
    'BaseView',
    'get_view_factory',
    'ThemeSystem',
    'get_theme_system',
    'ThemeLevel',
    'Theme',
    'ThemeColors',
    'LayoutManager',
    'get_layout_manager',
    'LayoutTemplate',
    'LayoutConfig',
    'ViewState',
    'BasePlugin',
    'PluginFramework',
    'PluginManifest',
    'PluginType',
    'ViewPreference',
    'PluginState',
    'PluginInfo',
    'ManifestLoader',
    'ManifestExporter',
    'ManifestValidator',
    'create_plugin_skeleton',
    'DataFormat',
    'SharedData',
    'ClipboardEnhancer',
    'DragDropManager',
    'SharedWorkspace',
    'get_clipboard',
    'get_drag_drop',
    'get_workspace',
    # 内置插件
    'KnowledgeBasePlugin',
    'AIChatPlugin',
    'IMClientPlugin',
]