# desktop_environment/__init__.py — 智能路由桌面环境系统
# ============================================================================
#
# 核心理念: "让你的应用成为可编程的智能路由操作系统"
#
# 架构:
# ┌─────────────────────────────────────────────────────────────────┐
# │                    DesktopEnvironment (桌面环境)                    │
# ├─────────────────────────────────────────────────────────────────┤
# │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
# │  │ DesktopManager│  │ WindowManager │  │  AppManager  │          │
# │  │  (桌面管理)   │  │  (窗口管理)   │  │  (应用管理)  │          │
# │  └──────────────┘  └──────────────┘  └──────────────┘          │
# │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
# │  │ Taskbar/Dock │  │PluginManager │  │ ThemeSystem  │          │
# │  │  (任务栏)    │  │  (插件管理)   │  │  (主题系统)  │          │
# │  └──────────────┘  └──────────────┘  └──────────────┘          │
# └─────────────────────────────────────────────────────────────────┘
#
# ============================================================================

from pathlib import Path

# 数据目录
_DATA_DIR = Path.home() / ".hermes-desktop" / "desktop_environment"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

__version__ = "1.0.0"

from .desktop_manager import (
    DesktopManager, DesktopConfig, WallpaperMode, GridLayout, get_desktop_manager,
)

from .desktop_icon import (
    DesktopIcon, IconSize, IconState, DesktopIconGrid,
)

from .window_manager import (
    WindowManager, AppWindow, WindowState, TitleBar, WindowAnimation,
)

from .app_manager import (
    AppManager, AppInfo, AppState, AppSandbox, get_app_manager,
)

from .plugin_manager import (
    PluginManager, PluginInfo, PluginState, PluginSecurityError, get_plugin_manager,
)

from .taskbar import (
    Taskbar, TaskbarItem, TaskbarPosition, SystemTray, NotificationCenter,
)

from .theme_system import (
    ThemeSystem, Theme, ThemeColors, AnimationConfig, get_theme_system,
)

from .search import (
    GlobalSearch, SearchResult, SearchCategory,
)

from .desktop_window import (
    DesktopWindow, MobileDesktop,
)

__all__ = [
    "__version__",
    "DesktopManager", "DesktopConfig", "WallpaperMode", "GridLayout", "get_desktop_manager",
    "DesktopIcon", "IconSize", "IconState", "DesktopIconGrid",
    "WindowManager", "AppWindow", "WindowState", "TitleBar", "WindowAnimation",
    "AppManager", "AppInfo", "AppState", "AppSandbox", "get_app_manager",
    "PluginManager", "PluginInfo", "PluginState", "PluginSecurityError", "get_plugin_manager",
    "Taskbar", "TaskbarItem", "TaskbarPosition", "SystemTray", "NotificationCenter",
    "ThemeSystem", "Theme", "ThemeColors", "AnimationConfig", "get_theme_system",
    "GlobalSearch", "SearchResult", "SearchCategory",
    "DesktopWindow", "MobileDesktop",
]