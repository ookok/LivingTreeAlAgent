"""LivingTree TUI — Windows Terminal + Textual AI Development Platform.

A keyboard-first, mouse-friendly terminal interface with:
- AI Chat (DeepSeek dual-model streaming)
- Code Editor (syntax highlight + AI assist)
- Document Manager (file tree + preview + analysis)
- Map/GIS Viewer (天地图 integration)
- Settings & Configuration

Usage:
    python -m livingtree tui
    livingtree tui

Key bindings:
    Ctrl+T     New tab / Switch focus
    Ctrl+Q     Quit
    Ctrl+S     Save
    F1         Help
    Tab         Next widget
"""

from .app import LivingTreeTuiApp
from .screens.chat import ChatScreen
from .screens.code import CodeScreen
from .screens.docs import DocsScreen
from .screens.map_viewer import MapScreen
from .screens.settings import SettingsScreen

__all__ = [
    "LivingTreeTuiApp",
    "ChatScreen",
    "CodeScreen",
    "DocsScreen",
    "MapScreen",
    "SettingsScreen",
]
