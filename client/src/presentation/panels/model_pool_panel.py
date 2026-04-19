# =================================================================
# ModelPoolPanel - 模型池面板
# =================================================================

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class ModelPoolPanel(QWidget):
    """模型池面板（占位）"""

    model_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Model Pool Panel - 功能开发中"))
        self.setLayout(layout)


__all__ = ['ModelPoolPanel']