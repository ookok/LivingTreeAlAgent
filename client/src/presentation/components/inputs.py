"""
通用组件库 - 统一输入框组件

消除各处重复的输入框样式定义。
"""

from PyQt6.QtWidgets import QLineEdit, QTextEdit, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from typing import Optional

from ..theme import theme_manager, get_input_style


class PrimaryLineEdit(QLineEdit):
    """主要输入框 - 统一样式"""

    return_pressed = pyqtSignal()

    def __init__(self, placeholder: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setStyleSheet(theme_manager.get_widget_style("input"))
        self.returnPressed.connect(self.return_pressed.emit)


class SearchInput(QLineEdit):
    """搜索输入框 - 带搜索图标风格"""

    search_triggered = pyqtSignal(str)

    def __init__(self, placeholder: str = "搜索...", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setStyleSheet(theme_manager.get_widget_style("input"))
        self.returnPressed.connect(self._on_return)

    def _on_return(self):
        self.search_triggered.emit(self.text())


class PrimaryTextEdit(QTextEdit):
    """主要文本编辑框 - 统一样式"""

    def __init__(self, placeholder: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setStyleSheet(theme_manager.get_widget_style("input"))


class LabeledInput(QWidget):
    """带标签的输入框"""

    def __init__(self, label: str, placeholder: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.label = QLabel(label)
        self.label.setStyleSheet(f"color: {theme_manager.colors.TEXT_SECONDARY}; font-size: 12px;")
        self.input = PrimaryLineEdit(placeholder)

        layout.addWidget(self.label)
        layout.addWidget(self.input)

    def text(self) -> str:
        return self.input.text()

    def set_text(self, text: str):
        self.input.setText(text)
