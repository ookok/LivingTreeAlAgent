"""
Intelligent IDE Module v4
=========================

OpenCode-inspired modern IDE with:
- 6 built-in themes (Tokyo Night, One Dark, Catppuccin, Gruvbox, Nord, Ayu)
- Performance-optimized (async I/O, thread management, bounded history)
- CodeTool v3 pipeline integration
- Serena LSP diagnostics
- Multi-provider model support
- Clean VS Code-style layout (Activity Bar + Chat + Editor + Sidebar)
"""

from .panel_v4 import IntelligentIDEPanel
from .opencode_ide_panel import OpenCodeIDEPanel, opencode_stylesheet, OpenCodeColors
from .theme import IDEThemeManager, get_theme_manager, BUILTIN_THEMES

__all__ = [
    # v4 Panel (classic style)
    "IntelligentIDEPanel",
    # OpenCode Panel (new, chat-first design)
    "OpenCodeIDEPanel",
    "opencode_stylesheet",
    "OpenCodeColors",
    # Theme
    "IDEThemeManager",
    "get_theme_manager",
    "BUILTIN_THEMES",
]
