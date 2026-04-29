# -*- coding: utf-8 -*-
"""
LivingTree Theme Manager

Theme management with light/dark theme support.
"""

import os
import json
from pathlib import Path
from typing import Optional, Callable

try:
    from PySide6.QtCore import QObject, Signal
except ImportError:
    from PyQt6.QtCore import QObject, pyqtSignal as Signal


class ThemeManager(QObject):
    """Theme manager for PyDracula-based UI

    Signals:
        theme_changed: Emitted when theme changes (is_light: bool)
    """

    theme_changed = Signal(bool)

    _instance = None

    # Theme constants
    THEME_LIGHT = "light"
    THEME_DARK = "dark"

    # Config file
    CONFIG_FILE = os.path.expanduser("~/.livingtree/ui_theme.json")

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        super().__init__()
        self._initialized = True

        # Load saved theme preference
        self._is_light = self._load_theme_preference()

        # Callbacks
        self._callbacks: list[Callable[[bool], None]] = []

    @property
    def is_light(self) -> bool:
        """Current theme is light"""
        return self._is_light

    @property
    def is_dark(self) -> bool:
        """Current theme is dark"""
        return not self._is_light

    @property
    def current_theme(self) -> str:
        """Get current theme name"""
        return self.THEME_LIGHT if self._is_light else self.THEME_DARK

    def get_theme_file(self, base_path: Optional[str] = None) -> str:
        """Get the full path to current theme file

        Args:
            base_path: Base path to themes directory. If None, uses default.

        Returns:
            Full path to theme QSS file
        """
        if base_path is None:
            # Get default theme path relative to this module
            theme_dir = Path(__file__).parent / "themes"
        else:
            theme_dir = Path(base_path)

        theme_name = "py_dracula_light.qss" if self._is_light else "py_dracula_dark.qss"
        return str(theme_dir / theme_name)

    def get_stylesheet(self, base_path: Optional[str] = None) -> str:
        """Get the current theme stylesheet content

        Args:
            base_path: Base path to themes directory

        Returns:
            Theme QSS content
        """
        theme_file = self.get_theme_file(base_path)
        try:
            with open(theme_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error loading theme: {e}")
            return ""

    def set_theme(self, is_light: bool, save: bool = True) -> None:
        """Set theme

        Args:
            is_light: True for light theme, False for dark theme
            save: Whether to save preference to disk
        """
        if self._is_light == is_light:
            return

        self._is_light = is_light

        # Save preference
        if save:
            self._save_theme_preference()

        # Notify listeners
        self.theme_changed.emit(is_light)
        for callback in self._callbacks:
            callback(is_light)

    def toggle_theme(self) -> bool:
        """Toggle between light and dark theme

        Returns:
            New theme is light
        """
        self.set_theme(not self._is_light)
        return self._is_light

    def apply_theme(self, widget, base_path: Optional[str] = None) -> None:
        """Apply current theme to a widget

        Args:
            widget: QWidget to apply theme to
            base_path: Base path to themes directory
        """
        stylesheet = self.get_stylesheet(base_path)
        if stylesheet:
            widget.setStyleSheet(stylesheet)

    def on_theme_changed(self, callback: Callable[[bool], None]) -> None:
        """Register a callback for theme changes

        Args:
            callback: Function to call (is_light: bool)
        """
        self._callbacks.append(callback)

    def _load_theme_preference(self) -> bool:
        """Load theme preference from disk

        Returns:
            True for light theme, False for dark (default)
        """
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get("theme", "light") == "light"
        except Exception:
            pass
        return True  # Default to light theme

    def _save_theme_preference(self) -> None:
        """Save theme preference to disk"""
        try:
            os.makedirs(os.path.dirname(self.CONFIG_FILE), exist_ok=True)
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump({
                    "theme": self.THEME_LIGHT if self._is_light else self.THEME_DARK
                }, f)
        except Exception as e:
            print(f"Error saving theme preference: {e}")


# Global theme manager instance
_theme_manager: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """Get the global theme manager instance"""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager
