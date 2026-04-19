# =================================================================
# WritingTab - 写作标签页
# =================================================================

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class WritingTab(QWidget):
    """写作标签页（占位）"""

    status_changed = pyqtSignal(str)

    def __init__(self, parent=None, agent=None):
        super().__init__(parent)
        self.agent = agent
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Writing Tab - 功能开发中"))
        self.setLayout(layout)


__all__ = ['WritingTab']