"""
通用组件库 - 统一按钮组件

消除各处重复的按钮样式定义。
"""

from PyQt6.QtWidgets import QPushButton, QWidget, QSizePolicy
from PyQt6.QtCore import Qt
from typing import Optional

from ..theme import theme_manager, get_button_primary_style, get_button_secondary_style


class PrimaryButton(QPushButton):
    """主要按钮 - 使用主题主色调"""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self._setup_style()

    def _setup_style(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(theme_manager.get_widget_style("button_primary"))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class SecondaryButton(QPushButton):
    """次要按钮 - 使用主题次要色"""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self._setup_style()

    def _setup_style(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(theme_manager.get_widget_style("button_secondary"))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class IconButton(QPushButton):
    """图标按钮 - 只显示图标，无边框"""

    def __init__(self, emoji: str = "", parent: Optional[QWidget] = None):
        super().__init__(emoji, parent)
        self._setup_style()

    def _setup_style(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 18px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background: rgba(128, 128, 128, 30);
                border-radius: 4px;
            }
        """)
        self.setFixedSize(36, 36)


class DangerButton(QPushButton):
    """危险操作按钮 - 红色"""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self._setup_style()

    def _setup_style(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        c = theme_manager.colors
        self.setStyleSheet(f"""
            QPushButton {{
                background: {c.ERROR};
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #DC2626;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
