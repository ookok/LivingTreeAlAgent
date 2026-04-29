"""
IDE Theme System - OpenCode-inspired theme management
=====================================================

Modern theme system with:
- JSON-based theme definitions (compatible with OpenCode theme format)
- Built-in themes (tokyonight, one-dark, catppuccin, gruvbox, nord, ayu)
- Runtime theme switching with signal notifications
- QSS stylesheet generation from theme definitions
- Syntax highlighting color integration
"""

import json
import os
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class ThemeColors:
    """Theme color palette"""
    # Core
    primary: str = "#7aa2f7"
    secondary: str = "#bb9af7"
    accent: str = "#9ece6a"
    # Status
    error: str = "#f7768e"
    warning: str = "#e0af68"
    success: str = "#9ece6a"
    info: str = "#7dcfff"
    # Text
    text: str = "#c0caf5"
    text_muted: str = "#565f89"
    text_bright: str = "#ffffff"
    # Backgrounds
    background: str = "#1a1b26"
    background_panel: str = "#1f2335"
    background_element: str = "#24283b"
    background_hover: str = "#292e42"
    # Borders
    border: str = "#3b4261"
    border_active: str = "#7aa2f7"
    border_subtle: str = "#292e42"
    # Syntax (One Dark inspired defaults)
    syntax_keyword: str = "#c678dd"
    syntax_string: str = "#98c379"
    syntax_comment: str = "#5c6370"
    syntax_function: str = "#61afef"
    syntax_variable: str = "#e06c75"
    syntax_number: str = "#d19a66"
    syntax_type: str = "#e5c07b"
    syntax_operator: str = "#56b6c2"
    syntax_decorator: str = "#c678dd"
    syntax_builtin: str = "#e5c07b"
    syntax_constant: str = "#d19a66"
    # Diff
    diff_added: str = "#9ece6a"
    diff_added_bg: str = "#1e2a1e"
    diff_removed: str = "#f7768e"
    diff_removed_bg: str = "#2a1e1e"
    diff_context: str = "#565f89"
    diff_context_bg: str = "#1a1b26"
    diff_hunk_header: str = "#7dcfff"
    # Markdown
    markdown_heading: str = "#7aa2f7"
    markdown_link: str = "#7dcfff"
    markdown_code: str = "#9ece6a"
    markdown_code_block: str = "#1f2335"
    markdown_emph: str = "#bb9af7"
    markdown_strong: str = "#c0caf5"
    markdown_list: str = "#bb9af7"


# ════════════════════════════════════════════════════════════════
# Built-in Themes
# ════════════════════════════════════════════════════════════════

THEME_TOKYONIGHT: Dict[str, Any] = {
    "name": "Tokyo Night",
    "id": "tokyonight",
    "colors": {
        "primary": "#7aa2f7", "secondary": "#bb9af7", "accent": "#9ece6a",
        "error": "#f7768e", "warning": "#e0af68", "success": "#9ece6a", "info": "#7dcfff",
        "text": "#c0caf5", "text_muted": "#565f89", "text_bright": "#ffffff",
        "background": "#1a1b26", "background_panel": "#1f2335",
        "background_element": "#24283b", "background_hover": "#292e42",
        "border": "#3b4261", "border_active": "#7aa2f7", "border_subtle": "#292e42",
        "syntax_keyword": "#bb9af7", "syntax_string": "#9ece6a",
        "syntax_comment": "#565f89", "syntax_function": "#7aa2f7",
        "syntax_variable": "#c0caf5", "syntax_number": "#ff9e64",
        "syntax_type": "#2ac3de", "syntax_operator": "#89ddff",
        "syntax_decorator": "#bb9af7", "syntax_builtin": "#e0af68",
        "syntax_constant": "#ff9e64",
        "diff_added": "#9ece6a", "diff_added_bg": "#1e2a1e",
        "diff_removed": "#f7768e", "diff_removed_bg": "#2a1e1e",
    }
}

THEME_ONE_DARK: Dict[str, Any] = {
    "name": "One Dark",
    "id": "one-dark",
    "colors": {
        "primary": "#61afef", "secondary": "#c678dd", "accent": "#98c379",
        "error": "#e06c75", "warning": "#d19a66", "success": "#98c379", "info": "#61afef",
        "text": "#abb2bf", "text_muted": "#5c6370", "text_bright": "#ffffff",
        "background": "#282c34", "background_panel": "#21252b",
        "background_element": "#2c313a", "background_hover": "#353b45",
        "border": "#3e4451", "border_active": "#61afef", "border_subtle": "#2c313a",
        "syntax_keyword": "#c678dd", "syntax_string": "#98c379",
        "syntax_comment": "#5c6370", "syntax_function": "#61afef",
        "syntax_variable": "#e06c75", "syntax_number": "#d19a66",
        "syntax_type": "#e5c07b", "syntax_operator": "#56b6c2",
        "syntax_decorator": "#c678dd", "syntax_builtin": "#e5c07b",
        "syntax_constant": "#d19a66",
        "diff_added": "#98c379", "diff_added_bg": "#1e2a1e",
        "diff_removed": "#e06c75", "diff_removed_bg": "#2a1e1e",
    }
}

THEME_CATPPUCCIN: Dict[str, Any] = {
    "name": "Catppuccin Mocha",
    "id": "catppuccin",
    "colors": {
        "primary": "#89b4fa", "secondary": "#cba6f7", "accent": "#a6e3a1",
        "error": "#f38ba8", "warning": "#fab387", "success": "#a6e3a1", "info": "#89dceb",
        "text": "#cdd6f4", "text_muted": "#6c7086", "text_bright": "#ffffff",
        "background": "#1e1e2e", "background_panel": "#181825",
        "background_element": "#313244", "background_hover": "#45475a",
        "border": "#585b70", "border_active": "#89b4fa", "border_subtle": "#313244",
        "syntax_keyword": "#cba6f7", "syntax_string": "#a6e3a1",
        "syntax_comment": "#6c7086", "syntax_function": "#89b4fa",
        "syntax_variable": "#cdd6f4", "syntax_number": "#fab387",
        "syntax_type": "#f9e2af", "syntax_operator": "#89dceb",
        "syntax_decorator": "#cba6f7", "syntax_builtin": "#f9e2af",
        "syntax_constant": "#fab387",
        "diff_added": "#a6e3a1", "diff_added_bg": "#1e2a1e",
        "diff_removed": "#f38ba8", "diff_removed_bg": "#2a1e1e",
    }
}

THEME_GRUVBOX: Dict[str, Any] = {
    "name": "Gruvbox Dark",
    "id": "gruvbox",
    "colors": {
        "primary": "#83a598", "secondary": "#d3869b", "accent": "#b8bb26",
        "error": "#fb4934", "warning": "#fabd2f", "success": "#b8bb26", "info": "#83a598",
        "text": "#ebdbb2", "text_muted": "#665c54", "text_bright": "#fbf1c7",
        "background": "#282828", "background_panel": "#1d2021",
        "background_element": "#32302f", "background_hover": "#3c3836",
        "border": "#504945", "border_active": "#83a598", "border_subtle": "#32302f",
        "syntax_keyword": "#fb4934", "syntax_string": "#b8bb26",
        "syntax_comment": "#665c54", "syntax_function": "#8ec07c",
        "syntax_variable": "#ebdbb2", "syntax_number": "#d3869b",
        "syntax_type": "#fabd2f", "syntax_operator": "#83a598",
        "syntax_decorator": "#d3869b", "syntax_builtin": "#fabd2f",
        "syntax_constant": "#d3869b",
        "diff_added": "#b8bb26", "diff_added_bg": "#2a2a1e",
        "diff_removed": "#fb4934", "diff_removed_bg": "#2a1e1e",
    }
}

THEME_NORD: Dict[str, Any] = {
    "name": "Nord",
    "id": "nord",
    "colors": {
        "primary": "#88c0d0", "secondary": "#b48ead", "accent": "#a3be8c",
        "error": "#bf616a", "warning": "#ebcb8b", "success": "#a3be8c", "info": "#81a1c1",
        "text": "#d8dee9", "text_muted": "#4c566a", "text_bright": "#eceff4",
        "background": "#2e3440", "background_panel": "#272c36",
        "background_element": "#3b4252", "background_hover": "#434c5e",
        "border": "#434c5e", "border_active": "#88c0d0", "border_subtle": "#3b4252",
        "syntax_keyword": "#81a1c1", "syntax_string": "#a3be8c",
        "syntax_comment": "#616e88", "syntax_function": "#88c0d0",
        "syntax_variable": "#d8dee9", "syntax_number": "#b48ead",
        "syntax_type": "#8fbcbb", "syntax_operator": "#81a1c1",
        "syntax_decorator": "#b48ead", "syntax_builtin": "#ebcb8b",
        "syntax_constant": "#d08770",
        "diff_added": "#a3be8c", "diff_added_bg": "#2a3a2e",
        "diff_removed": "#bf616a", "diff_removed_bg": "#3a2a2e",
    }
}

THEME_AYU: Dict[str, Any] = {
    "name": "Ayu Dark",
    "id": "ayu",
    "colors": {
        "primary": "#73d0ff", "secondary": "#d2a6ff", "accent": "#c2d94c",
        "error": "#f26d78", "warning": "#ffb454", "success": "#c2d94c", "info": "#73d0ff",
        "text": "#e6e1cf", "text_muted": "#5c6773", "text_bright": "#ffffff",
        "background": "#0a0e14", "background_panel": "#0d1117",
        "background_element": "#131820", "background_hover": "#1a1f29",
        "border": "#1a1f29", "border_active": "#73d0ff", "border_subtle": "#131820",
        "syntax_keyword": "#ffb454", "syntax_string": "#aad94c",
        "syntax_comment": "#5c6773", "syntax_function": "#ffd580",
        "syntax_variable": "#e6e1cf", "syntax_number": "#e6b450",
        "syntax_type": "#59c2ff", "syntax_operator": "#f29668",
        "syntax_decorator": "#d2a6ff", "syntax_builtin": "#ffb454",
        "syntax_constant": "#ff8f40",
        "diff_added": "#c2d94c", "diff_added_bg": "#0a1a0e",
        "diff_removed": "#f26d78", "diff_removed_bg": "#1a0a0e",
    }
}

# Theme registry
BUILTIN_THEMES: Dict[str, Dict[str, Any]] = {
    "tokyonight": THEME_TOKYONIGHT,
    "one-dark": THEME_ONE_DARK,
    "catppuccin": THEME_CATPPUCCIN,
    "gruvbox": THEME_GRUVBOX,
    "nord": THEME_NORD,
    "ayu": THEME_AYU,
}


class IDEThemeManager(QObject):
    """
    IDE theme manager

    Manages theme loading, switching, and QSS stylesheet generation.
    Compatible with OpenCode JSON theme format.
    """

    theme_changed = pyqtSignal(str)  # theme_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_theme_id = "tokyonight"
        self._current_colors = ThemeColors()
        self._custom_themes: Dict[str, Dict] = {}
        self._load_preferences()
        self.apply_theme(self._current_theme_id)

    @property
    def current_theme_id(self) -> str:
        return self._current_theme_id

    @property
    def colors(self) -> ThemeColors:
        return self._current_colors

    def get_available_themes(self) -> Dict[str, str]:
        """Get {theme_id: display_name} for all available themes."""
        themes = {}
        for tid, tdata in BUILTIN_THEMES.items():
            themes[tid] = tdata.get("name", tid)
        for tid, tdata in self._custom_themes.items():
            themes[tid] = tdata.get("name", tid)
        return themes

    def apply_theme(self, theme_id: str) -> bool:
        """Apply a theme by ID. Returns True if successful."""
        theme_data = BUILTIN_THEMES.get(theme_id) or self._custom_themes.get(theme_id)
        if not theme_data:
            # Fallback to tokyonight
            theme_data = BUILTIN_THEMES["tokyonight"]
            theme_id = "tokyonight"

        raw_colors = theme_data.get("colors", {})
        self._current_colors = ThemeColors(**{
            k: v for k, v in raw_colors.items() if hasattr(ThemeColors, k)
        })
        self._current_theme_id = theme_id
        self._save_preferences()
        self.theme_changed.emit(theme_id)
        return True

    def generate_qss(self) -> str:
        """Generate a complete QSS stylesheet from the current theme colors."""
        c = self._current_colors
        return f"""
        /* === Global === */
        QWidget {{
            background-color: {c.background};
            color: {c.text};
            font-family: "Segoe UI", "Microsoft YaHei UI", "Noto Sans SC", sans-serif;
            font-size: 13px;
        }}

        /* === Scrollbar === */
        QScrollBar:vertical {{
            background: {c.background_panel};
            width: 10px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {c.border};
            border-radius: 5px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {c.text_muted};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: {c.background_panel};
            height: 10px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: {c.border};
            border-radius: 5px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {c.text_muted};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* === QSplitter === */
        QSplitter::handle {{
            background-color: {c.border};
        }}
        QSplitter::handle:hover {{
            background-color: {c.primary};
        }}

        /* === Tab Widget === */
        QTabWidget::pane {{
            border: 1px solid {c.border};
            background: {c.background};
        }}
        QTabBar::tab {{
            background: {c.background_panel};
            color: {c.text_muted};
            padding: 8px 16px;
            border: 1px solid {c.border};
            border-bottom: none;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background: {c.background};
            color: {c.text};
            border-bottom: 2px solid {c.primary};
        }}
        QTabBar::tab:hover:!selected {{
            background: {c.background_element};
            color: {c.text};
        }}

        /* === Push Button === */
        QPushButton {{
            background-color: {c.background_element};
            color: {c.text};
            border: 1px solid {c.border};
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {c.background_hover};
            border-color: {c.primary};
        }}
        QPushButton:pressed {{
            background-color: {c.primary};
            color: {c.background};
        }}
        QPushButton:disabled {{
            background-color: {c.background_panel};
            color: {c.text_muted};
            border-color: {c.border_subtle};
        }}

        /* Primary button variant (set via property) */
        QPushButton[class="primary"] {{
            background-color: {c.primary};
            color: #ffffff;
            border: none;
        }}
        QPushButton[class="primary"]:hover {{
            background-color: {c.primary};
            opacity: 0.9;
        }}

        /* === Line Edit === */
        QLineEdit, QTextEdit {{
            background-color: {c.background_element};
            color: {c.text};
            border: 1px solid {c.border};
            border-radius: 6px;
            padding: 8px 12px;
            selection-background-color: {c.primary};
            selection-color: #ffffff;
        }}
        QLineEdit:focus, QTextEdit:focus {{
            border-color: {c.border_active};
        }}
        QLineEdit::placeholder {{
            color: {c.text_muted};
        }}

        /* === Combo Box === */
        QComboBox {{
            background-color: {c.background_element};
            color: {c.text};
            border: 1px solid {c.border};
            border-radius: 6px;
            padding: 6px 12px;
        }}
        QComboBox:hover {{
            border-color: {c.primary};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {c.background_panel};
            color: {c.text};
            border: 1px solid {c.border};
            selection-background-color: {c.primary};
            selection-color: #ffffff;
        }}

        /* === Tree Widget === */
        QTreeWidget, QTreeWidget::item {{
            background-color: {c.background};
            color: {c.text};
            border: none;
            padding: 4px 8px;
        }}
        QTreeWidget::item:selected {{
            background-color: {c.primary}33;
            color: {c.text_bright};
        }}
        QTreeWidget::item:hover:!selected {{
            background-color: {c.background_hover};
        }}
        QTreeWidget::indicator {{
            width: 16px;
            height: 16px;
        }}
        QHeaderView::section {{
            background-color: {c.background_panel};
            color: {c.text_muted};
            border: 1px solid {c.border};
            padding: 6px 8px;
            font-weight: bold;
            font-size: 12px;
        }}

        /* === List Widget === */
        QListWidget, QListWidget::item {{
            background-color: {c.background};
            color: {c.text};
            border: none;
            padding: 6px 10px;
        }}
        QListWidget::item:selected {{
            background-color: {c.primary}33;
        }}

        /* === Label === */
        QLabel {{
            background: transparent;
        }}

        /* === Frame / GroupBox === */
        QFrame[frameShape="4"] {{ /* HLine */
            color: {c.border};
        }}
        QFrame[frameShape="5"] {{ /* VLine */
            color: {c.border};
        }}
        QGroupBox {{
            border: 1px solid {c.border};
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 16px;
            font-weight: bold;
            color: {c.text};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
        }}

        /* === Menu === */
        QMenu {{
            background-color: {c.background_panel};
            border: 1px solid {c.border};
            border-radius: 8px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {c.primary}44;
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {c.border};
            margin: 4px 8px;
        }}

        /* === Tooltip === */
        QToolTip {{
            background-color: {c.background_element};
            color: {c.text};
            border: 1px solid {c.border};
            border-radius: 4px;
            padding: 4px 8px;
        }}

        /* === Progress Bar === */
        QProgressBar {{
            background-color: {c.background_element};
            border: 1px solid {c.border};
            border-radius: 4px;
            text-align: center;
            color: {c.text};
        }}
        QProgressBar::chunk {{
            background-color: {c.primary};
            border-radius: 3px;
        }}

        /* === Status Bar === */
        QStatusBar {{
            background-color: {c.background_panel};
            color: {c.text_muted};
            border-top: 1px solid {c.border};
            font-size: 12px;
        }}

        /* === Check Box === */
        QCheckBox {{
            spacing: 8px;
            color: {c.text};
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {c.border};
            border-radius: 3px;
            background-color: {c.background_element};
        }}
        QCheckBox::indicator:checked {{
            background-color: {c.primary};
            border-color: {c.primary};
        }}

        /* === Dialog === */
        QDialog {{
            background-color: {c.background};
        }}
        QMessageBox {{
            background-color: {c.background};
        }}
        """

    def _get_config_path(self) -> str:
        """Get theme preferences file path."""
        config_dir = os.path.expanduser("~/.hermes-desktop")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, "ide_theme.json")

    def _load_preferences(self):
        """Load theme preference from disk."""
        config_path = self._get_config_path()
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._current_theme_id = data.get("theme_id", "tokyonight")
        except Exception:
            pass

    def _save_preferences(self):
        """Save theme preference to disk."""
        config_path = self._get_config_path()
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"theme_id": self._current_theme_id}, f, indent=2)
        except Exception:
            pass


# Singleton
_theme_manager_instance: Optional[IDEThemeManager] = None


def get_theme_manager() -> IDEThemeManager:
    """Get the global theme manager singleton."""
    global _theme_manager_instance
    if _theme_manager_instance is None:
        _theme_manager_instance = IDEThemeManager()
    return _theme_manager_instance
