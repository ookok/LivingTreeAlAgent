"""
会话导航组件 (SessionNavWidget)

Lobe 风格的左侧会话导航栏
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QButtonGroup,
    QFrame, QSizePolicy
)
from PyQt6.QtGui import QFont, QIcon, QAction

from .lobe_models import (
    SessionType, SessionConfig, SESSION_PRESETS, LobeSession
)


class SessionNavWidget(QWidget):
    """
    会话导航组件

    功能：
    - 显示预设会话类型按钮组
    - 管理会话列表
    - 切换活跃会话
    """

    # 信号
    session_changed = pyqtSignal(str)  # session_id
    new_session_requested = pyqtSignal(SessionType)  # 新建会话请求
    delete_session_requested = pyqtSignal(str)  # 删除会话请求

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sessions: dict[str, LobeSession] = {}
        self._active_session_id: str = ""
        self._setup_ui()
        self._create_default_sessions()

    def _setup_ui(self):
        """初始化UI"""
        self.setMaximumWidth(220)
        self.setMinimumWidth(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        title = QLabel("会话")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # 新建会话按钮组
        new_group = QLabel("新建")
        new_group.setFont(QFont("Microsoft YaHei", 9))
        new_group.setStyleSheet("color: #666;")
        layout.addWidget(new_group)

        self.session_buttons = QButtonGroup()
        session_types = [
            (SessionType.TRADE, "💬", "电商咨询"),
            (SessionType.CODE, "💻", "代码助手"),
            (SessionType.SEARCH, "🌐", "全网搜索"),
            (SessionType.RAG, "📦", "文档库"),
            (SessionType.PERSONA, "🧙", "角色对话"),
        ]

        for stype, icon, name in session_types:
            btn = QPushButton(f"{icon} {name}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 8px 12px;
                    border: none;
                    border-radius: 6px;
                    background: transparent;
                    color: #333;
                }
                QPushButton:hover {
                    background: #f0f0f0;
                }
                QPushButton:pressed {
                    background: #e0e0e0;
                }
            """)
            btn.clicked.connect(lambda checked, s=stype: self._on_new_session(s))
            self.session_buttons.addButton(btn)
            layout.addWidget(btn)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background: #e0e0e0;")
        layout.addWidget(line)

        # 历史会话列表
        history_label = QLabel("历史会话")
        history_label.setFont(QFont("Microsoft YaHei", 9))
        history_label.setStyleSheet("color: #666;")
        layout.addWidget(history_label)

        self.session_list = QListWidget()
        self.session_list.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 6px;
                margin: 2px 0;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
            }
            QListWidget::item:hover {
                background: #f5f5f5;
            }
        """)
        self.session_list.itemClicked.connect(self._on_session_clicked)
        layout.addWidget(self.session_list, stretch=1)

        # 底部操作
        layout.addStretch()

        # 清空按钮
        clear_btn = QPushButton("🗑️ 清空历史")
        clear_btn.setStyleSheet("""
            QPushButton {
                border: none;
                padding: 8px;
                color: #999;
            }
            QPushButton:hover {
                color: #d32f2f;
            }
        """)
        clear_btn.clicked.connect(self._on_clear_history)
        layout.addWidget(clear_btn)

    def _create_default_sessions(self):
        """创建默认会话"""
        for stype, config in SESSION_PRESETS.items():
            session = LobeSession(
                config=config,
                is_active=(stype == SessionType.TRADE)
            )
            self._sessions[session.session_id] = session
            self._add_session_to_list(session)
            if session.is_active:
                self._active_session_id = session.session_id

    def _add_session_to_list(self, session: LobeSession):
        """添加会话到列表"""
        config = session.config
        icon = config.icon if config else "💬"
        name = config.name if config else "新会话"

        item = QListWidgetItem(f"{icon} {name}")
        item.setData(Qt.ItemDataRole.UserRole, session.session_id)
        self.session_list.addItem(item)

    def _on_new_session(self, session_type: SessionType):
        """新建会话"""
        config = SESSION_PRESETS.get(session_type)
        if not config:
            return

        session = LobeSession(config=config)
        self._sessions[session.session_id] = session
        self._add_session_to_list(session)

        # 激活新会话
        self._set_active_session(session.session_id)
        self.new_session_requested.emit(session_type)

    def _on_session_clicked(self, item: QListWidgetItem):
        """点击会话"""
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id:
            self._set_active_session(session_id)

    def _set_active_session(self, session_id: str):
        """设置活跃会话"""
        # 取消之前的激活状态
        for sid, session in self._sessions.items():
            if session.is_active:
                session.is_active = False

        # 设置新的激活状态
        if session_id in self._sessions:
            self._sessions[session_id].is_active = True
            self._active_session_id = session_id

            # 更新列表选中
            for i in range(self.session_list.count()):
                item = self.session_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == session_id:
                    self.session_list.setCurrentItem(item)
                    break

            self.session_changed.emit(session_id)

    def _on_clear_history(self):
        """清空历史会话"""
        # 保留默认会话，只清空历史
        default_ids = [s.session_id for s in self._sessions.values() if s.config]
        for sid in list(self._sessions.keys()):
            if sid not in default_ids:
                del self._sessions[sid]

        self.session_list.clear()
        for session in self._sessions.values():
            self._add_session_to_list(session)

        if self._sessions:
            first_id = next(iter(self._sessions))
            self._set_active_session(first_id)

    # ==================== 公共接口 ====================

    def get_active_session(self) -> LobeSession | None:
        """获取活跃会话"""
        return self._sessions.get(self._active_session_id)

    def get_active_session_id(self) -> str:
        """获取活跃会话ID"""
        return self._active_session_id

    def add_message_to_active(self, role: str, content: str, **kwargs):
        """向活跃会话添加消息"""
        session = self.get_active_session()
        if session:
            from .lobe_models import ChatMessage
            msg = ChatMessage(role=role, content=content, **kwargs)
            session.messages.append(msg)
            return msg
        return None
