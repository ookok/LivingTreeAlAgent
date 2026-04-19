# =================================================================
# WorkspacePanel - 工作区面板
# =================================================================

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class WorkspacePanel(QWidget):
    """工作区面板（占位）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Workspace Panel - 功能开发中"))
        self.setLayout(layout)


__all__ = ['WorkspacePanel']