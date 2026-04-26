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

    new_chat_requested = pyqtSignal()
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
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(12)

        # Logo + 标题
        title = QLabel("⬡  Hermes")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #F1F5F9; padding: 4px 8px 16px;")
        layout.addWidget(title)

        # 新建对话按钮
        self.new_btn = QPushButton("＋ 新建对话")
        self.new_btn.setObjectName("NewChatButton")
        self.new_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 14px;
                font-weight: 500;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
        """)
        self.new_btn.clicked.connect(self.new_chat_requested)
        layout.addWidget(self.new_btn)

        # 搜索框
        self.search = QLineEdit()
        self.search.setObjectName("SessionSearch")
        self.search.setPlaceholderText("🔍 搜索会话…")
        self.search.setStyleSheet("""
            QLineEdit {
                background-color: #334155;
                border: 1px solid #475569;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                color: #F1F5F9;
            }
            QLineEdit:focus {
                border-color: #3B82F6;
                outline: none;
            }
            QLineEdit::placeholder {
                color: #94A3B8;
            }
        """)
        self.search.textChanged.connect(self._filter_sessions)
        layout.addWidget(self.search)

        # 会话列表
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("SessionList")
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                color: #CBD5E1;
                padding: 10px 12px;
                border-radius: 6px;
                margin-bottom: 4px;
            }
            QListWidget::item:selected {
                background-color: #3B82F6;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #334155;
            }
        """)
        self.list_widget.currentItemChanged.connect(self._on_item_changed)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.list_widget)

        # 底部间距
        layout.addStretch()

        # 底部：设置按钮
        self.settings_btn = QPushButton("⚙ 设置")
        self.settings_btn.setObjectName("SettingsButton")
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94A3B8;
                border: 1px solid #475569;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #F1F5F9;
            }
        """)
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
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                background-color: transparent;
                color: #CBD5E1;
                padding: 10px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #3B82F6;
                color: white;
            }
        """)
        delete_action = menu.addAction("🗑 删除会话")
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == delete_action:
            sid = item.data(Qt.ItemDataRole.UserRole)
            self.session_deleted.emit(sid)
