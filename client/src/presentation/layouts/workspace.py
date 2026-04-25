"""
布局系统 - 工作区占位
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ..theme import theme_manager


class WorkspaceWidget(QWidget):
    """工作区占位组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        placeholder = QLabel("工作区加载中...")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            f"color: {theme_manager.colors.TEXT_TERTIARY}; font-size: 16px;"
        )
        layout.addWidget(placeholder)
