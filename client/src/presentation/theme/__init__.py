"""
主题系统包 - 统一主题管理

使用方式：
    from presentation.theme import theme_manager, LIGHT, DARK
    from presentation.theme.colors import get_button_primary_style

    # 应用主题
    theme_manager.set_theme("dark")

    # 获取颜色
    color = LIGHT.PRIMARY

    # 获取样式
    style = get_button_primary_style()
"""

from .theme_manager import ThemeManager, theme_manager
from .colors import (
    LightTheme, DarkTheme,
    LIGHT, DARK,
    get_button_primary_style,
    get_button_secondary_style,
    get_input_style,
    get_card_style,
    get_scrollbar_style,
)

__all__ = [
    "ThemeManager",
    "theme_manager",
    "LightTheme",
    "DarkTheme",
    "LIGHT",
    "DARK",
    "get_button_primary_style",
    "get_button_secondary_style",
    "get_input_style",
    "get_card_style",
    "get_scrollbar_style",
]
