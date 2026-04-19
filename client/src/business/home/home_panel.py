# =================================================================
# HomePanel - 首页面板
# =================================================================
# V2.0 功能模块：首页聚合

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class HomePanel(QWidget):
    """首页面板（占位）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("🏠 首页 - 功能开发中"))
        self.setLayout(layout)


__all__ = ['HomePanel']