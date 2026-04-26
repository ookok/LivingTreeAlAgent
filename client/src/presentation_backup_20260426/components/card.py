"""
QCardWidget - 卡片组件
用于显示模型卡片、商品卡片等信息卡片
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor


class QCardWidget(QFrame):
    """
    卡片组件
    提供带标题、内容和可选底部操作的卡片容器
    """

    clicked = pyqtSignal()

    def __init__(self, parent=None, title: str = "", content: str = ""):
        super().__init__(parent)
        self._title = title
        self._content = content
        self._setup_ui()

    def _setup_ui(self):
        """设置卡片UI"""
        # 卡片样式
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            QCardWidget {
                background: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 8px;
                padding: 12px;
            }
            QCardWidget:hover {
                border: 1px solid #3498db;
            }
        """)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # 标题
        if self._title:
            title_label = QLabel(self._title)
            title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            title_label.setStyleSheet("color: #ffffff;")
            main_layout.addWidget(title_label)

        # 内容
        if self._content:
            content_label = QLabel(self._content)
            content_label.setFont(QFont("Segoe UI", 9))
            content_label.setStyleSheet("color: #b0b0b0;")
            content_label.setWordWrap(True)
            main_layout.addWidget(content_label)

        main_layout.addStretch()

    def setTitle(self, title: str):
        """设置标题"""
        self._title = title
        self.update()

    def setContent(self, content: str):
        """设置内容"""
        self._content = content
        self.update()

    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)