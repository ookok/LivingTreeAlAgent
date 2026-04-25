"""
颜色常量定义 - 消除1865处硬编码颜色值

使用方式：
    from client.src.presentation.theme.colors import LIGHT_THEME, DARK_THEME
    bg = LIGHT_THEME.BG_MAIN
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ThemeColors:
    """主题颜色定义"""
    # 主色调
    PRIMARY: str = "#10B981"
    PRIMARY_HOVER: str = "#059669"
    PRIMARY_LIGHT: str = "#E8F5E9"
    PRIMARY_DARK: str = "#064E3B"

    # 背景色
    BG_MAIN: str = "#FFFFFF"
    BG_SECONDARY: str = "#F8FAFC"
    BG_TERTIARY: str = "#F5F5F5"
    BG_DARK_MAIN: str = "#0D0D0D"
    BG_DARK_SECONDARY: str = "#1A1A1A"
    BG_DARK_TERTIARY: str = "#252525"

    # 边框
    BORDER: str = "#E8E8E8"
    BORDER_HOVER: str = "#D0D0D0"
    BORDER_DARK: str = "#333333"
    BORDER_DARK_HOVER: str = "#444444"

    # 文字
    TEXT_PRIMARY: str = "#333333"
    TEXT_SECONDARY: str = "#666666"
    TEXT_TERTIARY: str = "#888888"
    TEXT_PLACEHOLDER: str = "#999999"
    TEXT_LIGHT: str = "#FFFFFF"
    TEXT_DARK_SECONDARY: str = "#A0A0A0"

    # 语义色
    SUCCESS: str = "#10B981"
    WARNING: str = "#F59E0B"
    ERROR: str = "#EF4444"
    INFO: str = "#3B82F6"

    # 卡片
    CARD_BG: str = "#FFFFFF"
    CARD_HOVER: str = "#F0FDF4"
    CARD_DARK_BG: str = "#1A1A1A"
    CARD_DARK_HOVER: str = "#222222"

    # IDE 风格（保留原有IDE配色）
    IDE_BG: str = "#1e1e1e"
    IDE_SIDEBAR: str = "#252526"
    IDE_ACCENT: str = "#007ACC"
    IDE_ACCENT_HOVER: str = "#1C8CE0"
    IDE_TEXT: str = "#CCCCCC"
    IDE_GREEN: str = "#89CD85"
    IDE_BLUE: str = "#569CD6"
    IDE_ORANGE: str = "#CE9178"
    IDE_YELLOW: str = "#DCDCAA"
    IDE_PURPLE: str = "#C586C0"

    # 滚动条
    SCROLL_BG: str = "#F8FAFC"
    SCROLL_HANDLE: str = "#CCCCCC"
    SCROLL_HOVER: str = "#888888"


class LightTheme:
    """浅色主题颜色"""
    BG_MAIN = ThemeColors.BG_MAIN
    BG_SECONDARY = ThemeColors.BG_SECONDARY
    BG_TERTIARY = ThemeColors.BG_TERTIARY
    BORDER = ThemeColors.BORDER
    BORDER_HOVER = ThemeColors.BORDER_HOVER
    TEXT_PRIMARY = ThemeColors.TEXT_PRIMARY
    TEXT_SECONDARY = ThemeColors.TEXT_SECONDARY
    TEXT_TERTIARY = ThemeColors.TEXT_TERTIARY
    TEXT_PLACEHOLDER = ThemeColors.TEXT_PLACEHOLDER
    PRIMARY = ThemeColors.PRIMARY
    PRIMARY_HOVER = ThemeColors.PRIMARY_HOVER
    PRIMARY_LIGHT = ThemeColors.PRIMARY_LIGHT
    SUCCESS = ThemeColors.SUCCESS
    WARNING = ThemeColors.WARNING
    ERROR = ThemeColors.ERROR
    INFO = ThemeColors.INFO
    CARD_BG = ThemeColors.CARD_BG
    CARD_HOVER = ThemeColors.CARD_HOVER
    SCROLL_BG = ThemeColors.SCROLL_BG
    SCROLL_HANDLE = ThemeColors.SCROLL_HANDLE


class DarkTheme:
    """深色主题颜色"""
    BG_MAIN = ThemeColors.BG_DARK_MAIN
    BG_SECONDARY = ThemeColors.BG_DARK_SECONDARY
    BG_TERTIARY = ThemeColors.BG_DARK_TERTIARY
    BORDER = ThemeColors.BORDER_DARK
    BORDER_HOVER = ThemeColors.BORDER_DARK_HOVER
    TEXT_PRIMARY = ThemeColors.TEXT_LIGHT
    TEXT_SECONDARY = ThemeColors.TEXT_DARK_SECONDARY
    TEXT_TERTIARY = ThemeColors.TEXT_TERTIARY
    TEXT_PLACEHOLDER = ThemeColors.TEXT_PLACEHOLDER
    PRIMARY = ThemeColors.PRIMARY
    PRIMARY_HOVER = ThemeColors.PRIMARY_HOVER
    PRIMARY_LIGHT = ThemeColors.PRIMARY_DARK
    SUCCESS = ThemeColors.SUCCESS
    WARNING = ThemeColors.WARNING
    ERROR = ThemeColors.ERROR
    INFO = ThemeColors.INFO
    CARD_BG = ThemeColors.CARD_DARK_BG
    CARD_HOVER = ThemeColors.CARD_DARK_HOVER
    SCROLL_BG = ThemeColors.BG_DARK_SECONDARY
    SCROLL_HANDLE = ThemeColors.BORDER_DARK


# 快捷访问
LIGHT = LightTheme()
DARK = DarkTheme()


def get_colors(theme_name: str = "light") -> object:
    """获取指定主题的颜色对象"""
    return LIGHT if theme_name == "light" else DARK


# 常用样式模板（使用颜色常量构建）
def get_button_primary_style(bg: str = None) -> str:
    """主要按钮样式"""
    bg = bg or LIGHT.PRIMARY
    hover = LIGHT.PRIMARY_HOVER if bg == LIGHT.PRIMARY else DARK.PRIMARY_HOVER
    return f"""
        QPushButton {{
            background: {bg};
            border: none;
            border-radius: 8px;
            color: #FFFFFF;
            padding: 8px 16px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background: {hover};
        }}
        QPushButton:disabled {{
            background: {LIGHT.BORDER};
            color: {LIGHT.TEXT_TERTIARY};
        }}
    """


def get_button_secondary_style() -> str:
    """次要按钮样式"""
    return f"""
        QPushButton {{
            background: {LIGHT.BG_TERTIARY};
            border: 1px solid {LIGHT.BORDER};
            border-radius: 8px;
            color: {LIGHT.TEXT_PRIMARY};
            padding: 8px 16px;
        }}
        QPushButton:hover {{
            border-color: {LIGHT.PRIMARY};
            color: {LIGHT.PRIMARY};
        }}
    """


def get_input_style() -> str:
    """输入框样式"""
    return f"""
        QLineEdit, QTextEdit {{
            background: {LIGHT.BG_TERTIARY};
            border: 1px solid {LIGHT.BORDER};
            border-radius: 8px;
            padding: 10px 14px;
            color: {LIGHT.TEXT_PRIMARY};
            font-size: 14px;
        }}
        QLineEdit:focus, QTextEdit:focus {{
            border: 1px solid {LIGHT.PRIMARY};
            background: {LIGHT.BG_MAIN};
        }}
        QLineEdit::placeholder, QTextEdit::placeholder {{
            color: {LIGHT.TEXT_PLACEHOLDER};
        }}
    """


def get_card_style() -> str:
    """卡片样式"""
    return f"""
        QFrame {{
            background: {LIGHT.CARD_BG};
            border: 1px solid {LIGHT.BORDER};
            border-radius: 12px;
        }}
        QFrame:hover {{
            border-color: {LIGHT.PRIMARY};
        }}
    """


def get_scrollbar_style() -> str:
    """滚动条样式"""
    return f"""
        QScrollBar:vertical {{
            background: {LIGHT.SCROLL_BG};
            width: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle {{
            background: {LIGHT.SCROLL_HANDLE};
            border-radius: 4px;
        }}
        QScrollBar::handle:hover {{
            background: {LIGHT.SCROLL_HOVER};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """
