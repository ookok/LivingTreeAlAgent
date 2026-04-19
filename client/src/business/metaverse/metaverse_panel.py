# =================================================================
# MetaversePanel - 元宇宙面板（舰桥）
# =================================================================
# V2.0 功能模块：数字孪生、星际导航

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class MetaversePanel(QWidget):
    """元宇宙面板（占位）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("🚀 舰桥 - 功能开发中"))
        self.setLayout(layout)


__all__ = ['MetaversePanel']