# -*- coding: utf-8 -*-
"""
LivingTree AI Agent - PyDracula UI Framework Integration

A modern GUI framework based on PyDracula with light/dark theme support.
"""

__version__ = "1.0.0"
__author__ = "Wanderson M. Pimenta (Original) / LivingTree Team (Integration)"

from .main_window import MainWindow
from .theme_manager import ThemeManager, get_theme_manager
from . import modules
from . import bindings

__all__ = ['MainWindow', 'ThemeManager', 'get_theme_manager', 'modules', 'bindings']
