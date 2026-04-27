"""
会话面板 — 左侧栏
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem, QLabel, QMenu,
)
from PyQt6.QtGui import QIcon, QAction


class SessionPanel(QWidget):
    """
    左侧会话列表面板。

    信号
    ----
    new_chat_requested()
    session_selected(session_id: str)
    session_deleted(session_id: str)
    settings_requested()
    """

    session_selected   = pyqtSignal(str)
    session_deleted    = pyqtSignal(str)
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SessionPanel")
        self.setMinimumWidth(220)
        self.setMaximumWidth(320)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)

        # Logo + 标题
        title = QLabel("⬡  Hermes")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #e8e8e8; padding: 4px 4px 8px;")
        layout.addWidget(title)

        # 会话列表
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("SessionList")
        self.list_widget.currentItemChanged.connect(self._on_item_changed)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.list_widget)

        # 底部：设置按钮
        self.settings_btn = QPushButton("⚙  设置")
        self.settings_btn.setObjectName("SettingsButton")
        self.settings_btn.clicked.connect(self.settings_requested)
        layout.addWidget(self.settings_btn)

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def add_session(self, session_id: str, title: str, select: bool = False):
        item = QListWidgetItem(title)
        item.setData(Qt.ItemDataRole.UserRole, session_id)
        self.list_widget.insertItem(0, item)
        if select:
            self.list_widget.setCurrentItem(item)

    def rename_session(self, session_id: str, new_title: str):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == session_id:
                item.setText(new_title)
                break

    def remove_session(self, session_id: str):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == session_id:
                self.list_widget.takeItem(i)
                break

    def clear_sessions(self):
        self.list_widget.clear()

    # ------------------------------------------------------------------
    # 内部槽
    # ------------------------------------------------------------------

    def _on_item_changed(self, current, previous):
        if current:
            sid = current.data(Qt.ItemDataRole.UserRole)
            if sid:
                self.session_selected.emit(sid)

    def _filter_sessions(self, text: str):
        text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text not in item.text().lower())

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#1e1e1e;border:1px solid #333;color:#ccc;border-radius:5px;}"
            "QMenu::item{padding:6px 20px;}"
            "QMenu::item:selected{background:#252550;}"
        )
        delete_action = menu.addAction("🗑  删除会话")
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == delete_action:
            sid = item.data(Qt.ItemDataRole.UserRole)
            self.session_deleted.emit(sid)
