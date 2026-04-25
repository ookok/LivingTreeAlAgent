"""
通用组件库 - 统一对话框服务

消除91处QMessageBox重复调用。
"""

from PyQt6.QtWidgets import (
    QDialog, QMessageBox, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QDialogButtonBox, QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from typing import Optional, Callable

from ..theme import theme_manager


class DialogService:
    """
    统一对话框服务 - 静态方法类

    消除91处QMessageBox重复调用，统一对话框样式。
    """

    @staticmethod
    def info(parent: Optional[QWidget], title: str, message: str) -> None:
        """信息对话框"""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStyleSheet(DialogService._get_dialog_style())
        msg.exec()

    @staticmethod
    def warning(parent: Optional[QWidget], title: str, message: str) -> None:
        """警告对话框"""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStyleSheet(DialogService._get_dialog_style())
        msg.exec()

    @staticmethod
    def error(parent: Optional[QWidget], title: str, message: str) -> None:
        """错误对话框"""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStyleSheet(DialogService._get_dialog_style())
        msg.exec()

    @staticmethod
    def question(parent: Optional[QWidget], title: str, message: str) -> bool:
        """
        确认对话框
        Returns: True if Yes, False if No
        """
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        msg.setStyleSheet(DialogService._get_dialog_style())
        result = msg.exec()
        return result == QMessageBox.StandardButton.Yes

    @staticmethod
    def confirm(parent: Optional[QWidget], title: str, message: str,
                yes_text: str = "确认", no_text: str = "取消") -> bool:
        """
        自定义确认对话框
        Returns: True if confirmed, False otherwise
        """
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle(title)
        msg.setText(message)

        yes_btn = msg.addButton(yes_text, QMessageBox.ButtonRole.YesRole)
        no_btn = msg.addButton(no_text, QMessageBox.ButtonRole.NoRole)
        msg.setDefaultButton(yes_btn)
        msg.setStyleSheet(DialogService._get_dialog_style())
        msg.exec()

        return msg.clickedButton() == yes_btn

    @staticmethod
    def _get_dialog_style() -> str:
        """获取对话框样式"""
        c = theme_manager.colors
        return f"""
            QMessageBox {{
                background: {c.BG_MAIN};
                color: {c.TEXT_PRIMARY};
                font-size: 14px;
            }}
            QMessageBox QLabel {{
                color: {c.TEXT_PRIMARY};
                padding: 8px;
            }}
            QMessageBox QPushButton {{
                background: {c.PRIMARY};
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                padding: 6px 16px;
                font-weight: bold;
            }}
            QMessageBox QPushButton:hover {{
                background: {c.PRIMARY_HOVER};
            }}
        """


class BaseDialog(QDialog):
    """基础对话框 - 统一样式"""

    def __init__(self, title: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet(theme_manager.get_widget_style("panel"))
        self._setup_ui()

    def _setup_ui(self):
        """子类重写此方法构建UI"""
        pass

    def add_button_box(self, layout: QVBoxLayout,
                      ok_text: str = "确定", cancel_text: str = "取消"):
        """添加确定/取消按钮"""
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText(ok_text)
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText(cancel_text)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


class ConfirmDialog(BaseDialog):
    """确认对话框 - 自定义内容"""

    confirmed = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, title: str, message: str,
                 parent: Optional[QWidget] = None):
        self._message = message
        super().__init__(title, parent)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 消息
        msg_label = QLabel(self._message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(f"color: {theme_manager.colors.TEXT_PRIMARY}; font-size: 14px;")
        layout.addWidget(msg_label)

        layout.addStretch()

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        from .buttons import SecondaryButton, PrimaryButton
        cancel_btn = SecondaryButton("取消")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = PrimaryButton("确认")
        ok_btn.clicked.connect(self.accept)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
