# -*- coding: utf-8 -*-
"""
Custom Grips Module

Custom window resize grips for frameless window.
"""

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QSizeGrip, QWidget
except ImportError:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QSizeGrip, QWidget


class CustomGrip(QSizeGrip):
    """Custom size grip for window resizing"""

    def __init__(self, parent=None, edge=Qt.LeftEdge, custom=True):
        super().__init__(parent)
        self.edge = edge
        self.custom = custom
        self.setFixedSize(10, 10) if custom else None

    def mousePressEvent(self, event):
        if self.custom:
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.custom:
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.custom:
            event.accept()
        else:
            super().mouseReleaseEvent(event)
