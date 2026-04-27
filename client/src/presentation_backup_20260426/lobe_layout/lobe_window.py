"""
Lobe 风格主窗口

整合左-中-右三栏布局
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QStatusBar
)
from PyQt6.QtGui import QFont, QAction

from .session_nav import SessionNavWidget
from .chat_area import ChatAreaWidget, StatusFlowBar
from .toolbox_drawer import ToolboxDrawerWidget
from .skill_binding import SkillToggleBinding, LobeMessageProcessor, RelayConfig
from .lobe_models import SessionType, ChatMessage


class LobeStyleWindow(QMainWindow):
    """
    Lobe 风格主窗口

    布局结构：
    ┌──────────────────────────────────────────────────────────┐
    │  菜单栏                                                    │
    ├────────┬─────────────────────────────────┬─────────────┤
    │        │                                 │             │
    │  会话   │       聊天工作区                  │   技能抽屉   │
    │  导航   │                                 │             │
    │  (左)   │          (中)                    │    (右)     │
    │        │                                 │             │
    │        ├─────────────────────────────────┤             │
    │        │  状态流条 │ Token计数器            │             │
    ├────────┴─────────────────────────────────┴─────────────┤
    │  状态栏                                                    │
    └──────────────────────────────────────────────────────────┘
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._setup_binding()
        self._setup_connections()

    def _setup_ui(self):
        """初始化UI"""
        self.setWindowTitle("Hermes Desktop - Lobe 风格")
        self.setMinimumSize(1200, 800)

        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 左侧：会话导航
        self.session_nav = SessionNavWidget()
        self.session_nav.setMaximumWidth(220)
        root_layout.addWidget(self.session_nav)

        # 分隔线
        left_line = QFrame()
        left_line.setFrameShape(QFrame.Shape.VLine)
        left_line.setStyleSheet("background: #e0e0e0;")
        root_layout.addWidget(left_line)

        # 中间：聊天工作区
        self.chat_area = ChatAreaWidget()
        root_layout.addWidget(self.chat_area, stretch=5)

        # 分隔线
        right_line = QFrame()
        right_line.setFrameShape(QFrame.Shape.VLine)
        right_line.setStyleSheet("background: #e0e0e0;")
        root_layout.addWidget(right_line)

        # 右侧：技能抽屉
        self.toolbox_drawer = ToolboxDrawerWidget()
        root_layout.addWidget(self.toolbox_drawer, stretch=2)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("⚡ 就绪")

        # 菜单栏
        self._create_menu_bar()

    def _setup_binding(self):
        """初始化绑定"""
        # Relay 配置
        self.relay_config = RelayConfig()

        # 技能开关绑定
        self.skill_binding = SkillToggleBinding(self.relay_config)
        self.skill_binding.add_config_callback(self._on_config_changed)

        # 消息处理器
        self.message_processor = LobeMessageProcessor(self.skill_binding)

    def _setup_connections(self):
        """连接信号"""
        # 会话切换
        self.session_nav.session_changed.connect(self._on_session_changed)
        self.session_nav.new_session_requested.connect(self._on_new_session)

        # 发送消息
        self.chat_area.send_message.connect(self._on_send_message)

        # 技能开关
        self.toolbox_drawer.skill_changed.connect(self._on_skill_changed)

    def _create_menu_bar(self):
        """创建菜单栏"""
        menu_bar = self.menuBar()

        # 文件菜单
        file_menu = menu_bar.addMenu("文件")

        new_session_action = QAction("新建会话", self)
        new_session_action.setShortcut("Ctrl+N")
        new_session_action.triggered.connect(lambda: self.session_nav._on_new_session(SessionType.CUSTOM))
        file_menu.addAction(new_session_action)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 视图菜单
        view_menu = menu_bar.addMenu("视图")

        toggle_toolbox_action = QAction("切换技能抽屉", self)
        toggle_toolbox_action.setShortcut("Ctrl+T")
        toggle_toolbox_action.triggered.connect(self._toggle_toolbox)
        view_menu.addAction(toggle_toolbox_action)

        # 帮助菜单
        help_menu = menu_bar.addMenu("帮助")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _toggle_toolbox(self):
        """切换技能抽屉显示"""
        is_visible = self.toolbox_drawer.isVisible()
        self.toolbox_drawer.setVisible(not is_visible)

    def _show_about(self):
        """显示关于"""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "关于 Hermes Desktop",
            "Hermes Desktop v2.0\n\n"
            "Lobe 风格 AI 助手\n\n"
            "集成的后端能力：\n"
            "• RelayFreeLLM 网关\n"
            "• SmolLM2 轻量路由\n"
            "• P2P 搜索代理\n"
            "• 记忆宫殿\n"
            "• 角色智库"
        )

    # ==================== 事件处理 ====================

    def _on_session_changed(self, session_id: str):
        """会话切换"""
        session = self.session_nav.get_active_session()
        if not session:
            return

        # 更新聊天区
        self.chat_area.set_session(session)

        # 更新技能抽屉
        if session.config:
            self.toolbox_drawer.set_session_type(session.config.session_type)

            # 应用会话预设到绑定器
            if session.config.session_type:
                self.skill_binding.apply_session_preset(session.config.session_type)

        # 更新状态栏
        self.status_bar.showMessage(f"当前会话：{session.config.name if session.config else '未知'}")

        # 更新窗口标题
        if session.config:
            self.setWindowTitle(f"Hermes Desktop - {session.config.icon} {session.config.name}")

    def _on_new_session(self, session_type: SessionType):
        """新建会话"""
        # 设置技能抽屉
        self.toolbox_drawer.set_session_type(session_type)

        # 应用预设
        self.skill_binding.apply_session_preset(session_type)

    def _on_send_message(self, content: str):
        """发送消息"""
        session = self.session_nav.get_active_session()
        if not session:
            return

        # 添加用户消息
        user_msg = ChatMessage(role="user", content=content)
        session.messages.append(user_msg)
        self.chat_area.add_message(user_msg)

        # 显示状态流
        self.chat_area.set_status_flow(["local"])

        # 异步处理
        QTimer.singleShot(50, lambda: self._async_process_message(content))

    async def _async_process_message(self, content: str):
        """异步处理消息"""
        try:
            # 处理消息
            result = await self.message_processor.process_message(content)

            # 更新状态流
            self.chat_area.set_status_flow(result.get("flow", []))

            # 添加 AI 回复
            assistant_msg = ChatMessage(
                role="assistant",
                content=result.get("response", ""),
                skill_used=self.relay_config.skills.copy()
            )
            session = self.session_nav.get_active_session()
            if session:
                session.messages.append(assistant_msg)

            self.chat_area.add_message(assistant_msg)

            # 更新 Token 计数
            self.chat_area.update_tokens(
                result.get("tokens", 0),
                result.get("model", "")
            )

            # 更新状态栏
            self.status_bar.showMessage(f"✅ 完成 - {result.get('model', '')}")

        except Exception as e:
            self.status_bar.showMessage(f"❌ 错误: {e}")
            self.chat_area.set_status_flow(["error"])

    def _on_skill_changed(self, skill_id: str, enabled: bool):
        """技能开关变化"""
        self.skill_binding.on_skill_changed(skill_id, enabled)

        # 更新状态栏
        status = "启用" if enabled else "禁用"
        self.status_bar.showMessage(f"技能 {skill_id} {status}")

    def _on_config_changed(self, config: RelayConfig):
        """配置变化"""
        # 这里应该通知后端重新配置
        # 目前只打印日志
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Config updated: {config.to_dict()}")
