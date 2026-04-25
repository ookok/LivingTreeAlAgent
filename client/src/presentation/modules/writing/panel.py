"""
智能写作模块 - 新版占位面板
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ...theme import theme_manager


class Panel(QWidget):
    """智能写作面板 - 新版（占位）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        placeholder = QLabel("✍️ 智能写作模块\n\n新版UI重建中...")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            f"color: {theme_manager.colors.TEXT_TERTIARY};"
            f"font-size: 16px;"
        )
        layout.addWidget(placeholder)
        layout.addStretch()
