# =================================================================
# ResearchPanel - 研究面板
# =================================================================

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class ResearchPanel(QWidget):
    """研究面板（占位）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_tool = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Research Panel - 功能开发中"))
        self.setLayout(layout)

    def set_search_tool(self, tool):
        """设置搜索工具"""
        self._search_tool = tool


__all__ = ['ResearchPanel']