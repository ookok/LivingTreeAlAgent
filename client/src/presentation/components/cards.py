"""
通用组件库 - 统一卡片组件

消除各处重复的卡片样式定义。
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QWidget, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from typing import Optional

from ..theme import theme_manager, get_card_style


class Card(QFrame):
    """基础卡片 - 统一样式"""

    clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(theme_manager.get_widget_style("card"))

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class InfoCard(Card):
    """信息卡片 - 带标题和内容"""

    def __init__(self, title: str = "", content: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui(title, content)

    def _setup_ui(self, title: str, content: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {theme_manager.colors.TEXT_PRIMARY};")
        layout.addWidget(self.title_label)

        self.content_label = QLabel(content)
        self.content_label.setStyleSheet(f"color: {theme_manager.colors.TEXT_SECONDARY}; font-size: 13px;")
        self.content_label.setWordWrap(True)
        layout.addWidget(self.content_label)

    def set_title(self, title: str):
        self.title_label.setText(title)

    def set_content(self, content: str):
        self.content_label.setText(content)


class StatsCard(Card):
    """统计卡片 - 显示数字指标"""

    def __init__(self, label: str = "", value: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui(label, value)

    def _setup_ui(self, label: str, value: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {theme_manager.colors.PRIMARY};")
        layout.addWidget(self.value_label)

        self.label_label = QLabel(label)
        self.label_label.setStyleSheet(f"color: {theme_manager.colors.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(self.label_label)

    def set_value(self, value: str):
        self.value_label.setText(value)

    def set_label(self, label: str):
        self.label_label.setText(label)


class ActionCard(Card):
    """操作卡片 - 带操作按钮"""

    action_clicked = pyqtSignal()

    def __init__(self, title: str = "", description: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui(title, description)

    def _setup_ui(self, title: str, description: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {theme_manager.colors.TEXT_PRIMARY};")
        layout.addWidget(self.title_label)

        self.desc_label = QLabel(description)
        self.desc_label.setStyleSheet(f"color: {theme_manager.colors.TEXT_SECONDARY}; font-size: 13px;")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

        layout.addStretch()

        from .buttons import PrimaryButton
        self.action_btn = PrimaryButton("查看详情")
        self.action_btn.clicked.connect(self.action_clicked.emit)
        layout.addWidget(self.action_btn)
