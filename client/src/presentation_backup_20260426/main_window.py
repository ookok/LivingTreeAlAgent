"""
LivingTree AI OS - 主窗口

功能：
  - 三列布局：会话面板 + 功能模块区 + 工作区
  - 集成 AgentChat：L0/L3/L4 分层模型
  - 系统启动时初始化 Agent 并显示问候语
  - 流式输出集成
  - 深度搜索、专家训练等模块切换

布局：
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🌳 Logo  生命之树AI OS  │💬聊天│🔍深度搜索│📚知识库│🎓专家训练│💻智能IDE│✍️智能写作│⚙️│👤│
├──────────┬────────────────────────────────────────────┬────────────────────┤
│ 会话面板  │         功能模块区域（默认聊天）              │   工作区           │
│ (可收缩)  │  ┌─────────────────────────────────────┐ │   (可收缩)         │
│          │  │  聊天面板 / 深度搜索面板 / ...        │ │                    │
│ [+新对话]│  │                                     │ │  📁 项目           │
│          │  │                                     │ │    ├─ src/         │
│ [市场]   │  │                                     │ │    └─ tests/       │
└──────────┴──┴─────────────────────────────────────┴──┴────────────────────┘
"""

import os
import uuid
from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QAction, QKeyEvent, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLineEdit, QTextEdit, QLabel,
    QScrollArea, QSizePolicy, QFrame, QMenu,
    QToolButton, QStatusBar, QFileDialog,
    QMessageBox, QDialog,
)
try:
    from PyQt6.QtSvgWidgets import QSvgWidget
except ImportError:
    QSvgWidget = None  # 可选的SVG支持

# 导入现有组件
from client.src.presentation.panels.chat_panel import ChatPanel
from client.src.presentation.panels.workspace_panel import (
    WorkspacePanel,
    SystemFeaturesPanel,
    KnowledgeBaseInitPanel,
    KnowledgeBaseViewPanel,
    MemoryPalacePanel,
    KnowledgeGraphPanel,
    WorkflowPanel,
    ChainOfThoughtPanel,
    SkillLibraryPanel,
    SystemStatsPanel,
)

# 导入对话框
from client.src.presentation.dialogs.settings_dialog import UserSettingsDialog, SystemSettingsDialog

try:
    from PyQt6.QtWidgets import QProgressBar
except ImportError:
    QProgressBar = None


# ── Agent Chat 集成 ──────────────────────────────────────────────────────

def create_agent_chat_instance():
    """
    创建 AgentChat 实例

    整合 AgentChat 的核心功能：
    - L0/L3/L4 分层模型
    - 流式输出
    - TTS 朗读
    - 知识库工具注册
    - 增强模式（意图识别、Query压缩、上下文管理）
    """
    try:
        from core.agent_chat import create_agent_chat, AgentChat

        # 创建 AgentChat 实例
        chat = create_agent_chat(
            backend="ollama",
            enable_enhancement=True,
        )

        return chat
    except ImportError as e:
        print(f"[MainWindow] AgentChat 导入失败: {e}")
        return None
    except Exception as e:
        print(f"[MainWindow] AgentChat 初始化失败: {e}")
        return None


# ── 模块栏 ──────────────────────────────────────────────────────────────

class ModuleBar(QWidget):
    """顶部横排模块选择器"""

    module_changed = pyqtSignal(str)  # module_id

    MODULES = [
        ("💬", "聊天", "chat"),        # 聊天模块
        ("🔍", "深度搜索", "deep_search"),
        ("📚", "知识库", "knowledge_base"),
        ("🎓", "专家训练", "expert_training"),
        ("💻", "智能IDE", "smart_ide"),
        ("✍️", "智能写作", "smart_writing"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_module = "chat"  # 默认聊天
        self._setup_ui()
        self.set_active_module("chat")

    def _setup_ui(self):
        self.setFixedHeight(52)
        self.setStyleSheet("""
            ModuleBar {
                background: #FFFFFF;
                border-bottom: 1px solid #E8E8E8;
            }
        """)

        # 主布局：左右分割
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 左侧：Logo + 模块列表 ===
        left_widget = QWidget()
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(12, 0, 8, 0)
        left_layout.setSpacing(6)

        # Logo
        self.logo_label = QLabel("🌳")
        self.logo_label.setStyleSheet("font-size: 22px; padding: 0 4px;")

        # 标题
        self.title_label = QLabel("生命之树AI")
        self.title_label.setStyleSheet("""
            color: #10B981;
            font-size: 15px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
            padding-right: 12px;
        """)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("background: #E8E8E8;")
        sep.setFixedWidth(1)

        # 模块按钮区域（带滚动）
        self.modules_scroll = QScrollArea()
        self.modules_scroll.setFixedHeight(52)
        self.modules_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.modules_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.modules_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QWidget#modules_container {
                background: transparent;
            }
        """)

        modules_container = QWidget()
        modules_container.setObjectName("modules_container")
        modules_layout = QHBoxLayout(modules_container)
        modules_layout.setContentsMargins(8, 8, 8, 8)
        modules_layout.setSpacing(6)

        self.module_buttons = {}
        for emoji, name, module_id in self.MODULES:
            btn = self._create_module_button(emoji, name, module_id)
            self.module_buttons[module_id] = btn
            modules_layout.addWidget(btn)

        self.modules_scroll.setWidget(modules_container)
        self.modules_scroll.setWidgetResizable(False)

        left_layout.addWidget(self.logo_label)
        left_layout.addWidget(self.title_label)
        left_layout.addWidget(sep)
        left_layout.addWidget(self.modules_scroll, 1)

        main_layout.addWidget(left_widget, 1)

        # === 右侧：状态 + 设置 ===
        right_widget = QWidget()
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 12, 0)
        right_layout.setSpacing(8)

        # Agent 状态指示器
        self.agent_status = QLabel("●")
        self.agent_status.setStyleSheet("color: #CCCCCC; font-size: 12px;")
        self.agent_status.setToolTip("Agent 状态")
        right_layout.addWidget(self.agent_status)

        # 设置按钮
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 8px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: #F0F0F0;
            }
        """)
        self.settings_btn.clicked.connect(lambda: self.module_changed.emit("settings"))

        # 用户按钮
        self.user_btn = QPushButton("👤")
        self.user_btn.setFixedSize(36, 36)
        self.user_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 8px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: #F0F0F0;
            }
        """)
        self.user_btn.clicked.connect(lambda: self.module_changed.emit("user"))

        right_layout.addWidget(self.agent_status)
        right_layout.addWidget(self.settings_btn)
        right_layout.addWidget(self.user_btn)

        main_layout.addWidget(right_widget)

    def _create_module_button(self, emoji: str, name: str, module_id: str) -> QPushButton:
        btn = QPushButton(f"{emoji} {name}")
        btn.setFixedHeight(36)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 8px;
                color: #666666;
                font-size: 14px;
                padding: 0 16px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #F0F0F0;
                color: #333333;
            }
            QPushButton[active="true"] {
                background: #10B98120;
                color: #10B981;
                border: 1px solid #10B981;
            }
        """)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self._on_module_click(module_id))
        return btn

    def _on_module_click(self, module_id: str):
        self.set_active_module(module_id)
        self.module_changed.emit(module_id)

    def set_active_module(self, module_id: str):
        """设置当前激活的模块"""
        self.current_module = module_id
        for mid, btn in self.module_buttons.items():
            btn.setProperty("active", "true" if mid == module_id else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_agent_status(self, status: str, color: str):
        """
        设置 Agent 状态

        Args:
            status: 状态文本
            color: 状态颜色 (绿色=#10B981, 黄色=#FFD700, 红色=#EF4444, 灰色=#CCCCCC)
        """
        self.agent_status.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.agent_status.setToolTip(status)


# ── 会话面板 ──────────────────────────────────────────────────────────────

class SessionPanel(QWidget):
    """左侧会话历史面板"""

    new_chat_requested = pyqtSignal()
    chat_selected = pyqtSignal(str)  # chat_id
    market_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sessions = []
        self._setup_ui()
        self._load_demo_sessions()

    def _setup_ui(self):
        self.setFixedWidth(240)
        self.setStyleSheet("""
            SessionPanel {
                background: #F8FAFC;
                border-right: 1px solid #E8E8E8;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(12)

        # 新建会话按钮
        self.new_chat_btn = QPushButton("➕ 新建会话")
        self.new_chat_btn.setFixedHeight(40)
        self.new_chat_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        self.new_chat_btn.clicked.connect(self.new_chat_requested.emit)
        layout.addWidget(self.new_chat_btn)

        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 搜索会话...")
        self.search_box.setFixedHeight(36)
        self.search_box.setStyleSheet("""
            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                padding: 0 12px;
                color: #333333;
                font-size: 13px;
            }
            QLineEdit::placeholder {
                color: #999999;
            }
            QLineEdit:focus {
                border: 1px solid #10B981;
            }
        """)
        layout.addWidget(self.search_box)

        # 会话列表
        self.session_list = QScrollArea()
        self.session_list.setWidgetResizable(True)
        self.session_list.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)

        self.session_container = QWidget()
        self.session_layout = QVBoxLayout(self.session_container)
        self.session_layout.setContentsMargins(0, 0, 0, 0)
        self.session_layout.setSpacing(8)
        self.session_layout.addStretch()

        self.session_list.setWidget(self.session_container)
        layout.addWidget(self.session_list)

        # 底部市场按钮
        spacer = QWidget()
        spacer.setFixedHeight(1)
        layout.addWidget(spacer)

        self.market_btn = QPushButton("🛒 市场")
        self.market_btn.setFixedHeight(40)
        self.market_btn.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                color: #666666;
                font-size: 14px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #F0F0F0;
                color: #333333;
            }
        """)
        self.market_btn.clicked.connect(self.market_requested.emit)
        layout.addWidget(self.market_btn)

    def _load_demo_sessions(self):
        """加载演示会话"""
        demos = [
            ("s1", "Python异步编程问题", "我想了解asyncio的用法...", "10:30"),
            ("s2", "项目架构设计", "帮我分析下微服务架构...", "昨天"),
            ("s3", "数据可视化方案", "用什么库画图表好...", "周三"),
            ("s4", "代码审查请求", "帮我看看这段代码...", "周二"),
        ]
        for sid, title, preview, time in demos:
            self.add_session(sid, title, preview, time)

    def add_session(self, session_id: str, title: str, preview: str = "", timestamp: str = ""):
        """添加会话项"""
        item = SessionItem(session_id, title, preview, timestamp)
        item.clicked.connect(lambda: self.chat_selected.emit(session_id))
        self.session_layout.insertWidget(self.session_layout.count() - 1, item)
        self._sessions.append({"id": session_id, "widget": item})

    def select_session(self, session_id: str):
        """选中会话"""
        for sess in self._sessions:
            sess["widget"].set_selected(sess["id"] == session_id)


class SessionItem(QWidget):
    """会话项组件"""

    clicked = pyqtSignal()

    def __init__(self, session_id: str, title: str, preview: str = "", timestamp: str = "", parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self._setup_ui(title, preview, timestamp)

    def _setup_ui(self, title: str, preview: str, timestamp: str):
        self.setFixedHeight(72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # 标题行
        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)

        self.icon_label = QLabel("💬")
        self.icon_label.setStyleSheet("font-size: 14px;")

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)

        self.time_label = QLabel(timestamp)
        self.time_label.setStyleSheet("""
            color: #999999;
            font-size: 11px;
        """)

        title_layout.addWidget(self.icon_label)
        title_layout.addWidget(self.title_label, 1)
        title_layout.addWidget(self.time_label)
        layout.addLayout(title_layout)

        # 预览
        self.preview_label = QLabel(preview)
        self.preview_label.setStyleSheet("""
            color: #888888;
            font-size: 12px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(self.preview_label)

    def set_selected(self, selected: bool):
        if selected:
            self.setStyleSheet("""
                SessionItem {
                    background: #E8F5E9;
                    border-radius: 8px;
                }
            """)
            self.title_label.setStyleSheet("""
                color: #10B981;
                font-size: 13px;
                font-weight: bold;
                font-family: "Microsoft YaHei", sans-serif;
            """)
        else:
            self.setStyleSheet("""
                SessionItem {
                    background: transparent;
                    border-radius: 8px;
                }
                SessionItem:hover {
                    background: #F5F5F5;
                }
            """)
            self.title_label.setStyleSheet("""
                color: #333333;
                font-size: 13px;
                font-weight: bold;
                font-family: "Microsoft YaHei", sans-serif;
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


# ── 主窗口 ──────────────────────────────────────────────────────────────


class MainWindow(QWidget):
    """
    生命之树AI OS 主窗口

    信号:
        module_changed(str) - 模块切换
        send_message(str) - 发送消息
        new_chat() - 新建会话
        open_settings(str) - 打开设置
    """

    # 信号定义
    module_changed = pyqtSignal(str)
    send_message = pyqtSignal(str, list)  # text, attachments
    new_chat = pyqtSignal()
    open_settings = pyqtSignal(str)  # settings type
    workspace_changed = pyqtSignal(str)  # folder_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_module = "chat"
        self._current_chat_id = None
        self._workspace_folder = None
        self._attachments = []
        self._user_info = self._get_user_info()

        # AgentChat 实例
        self._agent_chat = None
        self._agent_initialized = False

        self._setup_ui()
        self._connect_signals()

        # 延迟初始化 Agent
        QTimer.singleShot(100, self._init_agent)

    def _setup_ui(self):
        self.setWindowTitle("🌳 生命之树AI OS")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("""
            QMainWindow, MainWindow {
                background: #F8FAFC;
            }
            QStatusBar {
                background: #FFFFFF;
                border-top: 1px solid #E8E8E8;
                color: #666666;
            }
        """)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 顶部模块栏
        self.module_bar = ModuleBar()
        main_layout.addWidget(self.module_bar)

        # ====== 三列布局 ======
        content = QSplitter(Qt.Orientation.Horizontal)
        content.setHandleWidth(1)
        content.setContentsMargins(0, 0, 0, 0)
        content.setStyleSheet("""
            QSplitter {
                background: #F8FAFC;
            }
            QSplitter::handle {
                background: #E8E8E8;
            }
        """)

        # === 左侧：会话面板（可收缩） ===
        self.left_panel = QWidget()
        self.left_panel.setStyleSheet("background: #FFFFFF;")
        self.left_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 收缩按钮
        self.left_toggle = QPushButton("◀")
        self.left_toggle.setFixedHeight(28)
        self.left_toggle.setStyleSheet("""
            QPushButton {
                background: #F5F5F5;
                border: none;
                border-bottom: 1px solid #E8E8E8;
                color: #666666;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #E8E8E8;
            }
        """)
        self.left_toggle.clicked.connect(self._toggle_left_panel)
        left_layout.addWidget(self.left_toggle)

        # 会话面板
        self.session_panel = SessionPanel()
        self.session_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout.addWidget(self.session_panel, 1)

        content.addWidget(self.left_panel)

        # === 中间：聊天面板 ===
        self.center_panel = QWidget()
        self.center_panel.setStyleSheet("background: #F8FAFC;")
        self.center_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # 聊天面板
        self.chat_panel = ChatPanel()
        self.chat_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        center_layout.addWidget(self.chat_panel, 1)

        content.addWidget(self.center_panel)

        # === 右侧：工作区（可收缩） ===
        self.right_panel = QWidget()
        self.right_panel.setStyleSheet("background: #FFFFFF;")
        self.right_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 收缩按钮
        self.right_toggle = QPushButton("▶")
        self.right_toggle.setFixedHeight(28)
        self.right_toggle.setStyleSheet("""
            QPushButton {
                background: #F5F5F5;
                border: none;
                border-bottom: 1px solid #E8E8E8;
                color: #666666;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #E8E8E8;
            }
        """)
        self.right_toggle.clicked.connect(self._toggle_right_panel)
        right_layout.addWidget(self.right_toggle)

        # 工作区面板
        self.workspace_panel = WorkspacePanel()
        self.workspace_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout.addWidget(self.workspace_panel, 1)

        content.addWidget(self.right_panel)

        # 保存初始宽度
        self._left_panel_width = 220
        self._right_panel_width = 280

        # 设置初始宽度
        QTimer.singleShot(10, lambda: self._init_panel_widths(content))

        main_layout.addWidget(content, 1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: #FFFFFF;
                border-top: 1px solid #E8E8E8;
                color: #666666;
                font-size: 12px;
            }
        """)
        self.status_indicator = StatusIndicator()
        self.status_bar.addPermanentWidget(self.status_indicator)
        self.status_bar.showMessage("🌳 生命之树AI OS 正在初始化...")
        main_layout.addWidget(self.status_bar)

    def _init_agent(self):
        """
        初始化 Agent（异步执行）

        流程：
        1. 显示初始化进度
        2. 创建 AgentChat 实例
        3. 调用 sayhello() 显示问候语
        """
        # 显示初始化进度
        self.chat_panel.show_initialization_progress([
            "连接 Ollama 服务",
            "加载 L0 路由模型",
            "加载 L3 推理模型",
            "加载 L4 生成模型",
            "初始化知识库",
            "启动 Agent...",
        ])

        # 延迟创建 Agent
        QTimer.singleShot(100, self._create_agent_chat)

    def _create_agent_chat(self):
        """创建 AgentChat 实例"""
        try:
            # 显示模型调用状态
            self.chat_panel.show_model_inference("qwen2.5:1.5b", "正在连接 Ollama...")

            # 创建 AgentChat
            self._agent_chat = create_agent_chat_instance()

            if self._agent_chat:
                self._agent_initialized = True
                self.module_bar.set_agent_status("Agent 就绪", "#10B981")
                self.status_bar.showMessage("Agent 初始化完成")

                # 调用 sayhello() 显示问候语
                self._do_sayhello()
            else:
                self.module_bar.set_agent_status("Agent 未连接", "#CCCCCC")
                self.status_bar.showMessage("Agent 初始化失败，请检查 Ollama 连接")
                self.chat_panel.add_error_message("Agent 初始化失败，请检查 Ollama 服务是否运行")

        except Exception as e:
            self._agent_initialized = False
            self.module_bar.set_agent_status("Agent 错误", "#EF4444")
            self.status_bar.showMessage(f"Agent 初始化错误: {str(e)[:50]}")
            self.chat_panel.add_error_message(f"Agent 初始化失败: {str(e)}")

    def _do_sayhello(self):
        """执行 sayhello - 显示问候语"""
        if not self._agent_chat:
            return

        try:
            # 显示问候语
            greeting = self._agent_chat.sayhello()
            # 在聊天面板显示问候语（流式输出风格）
            self.chat_panel.show_greeting(greeting)
        except Exception as e:
            # 如果 sayhello 失败，显示默认问候
            self.chat_panel.show_greeting(
                "你好！我是生命之树AI，你的 AI 桌面助手。\n"
                "请检查 Ollama 服务是否正常运行。"
            )

    def _init_panel_widths(self, splitter):
        """初始化面板宽度"""
        total_width = splitter.width()
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([self._left_panel_width, total_width - self._left_panel_width - self._right_panel_width, self._right_panel_width])

    def _toggle_left_panel(self):
        """切换左侧面板显示/隐藏"""
        if self.left_panel.isVisible():
            self._left_panel_width = self.left_panel.width()
            self.left_panel.hide()
            self.left_toggle.setText("▶")
        else:
            self.left_panel.show()
            self.left_toggle.setText("◀")
            splitter = self.center_panel.parent()
            if splitter:
                sizes = splitter.sizes()
                total = sum(sizes)
                splitter.setSizes([self._left_panel_width, total - self._left_panel_width - self._right_panel_width, self._right_panel_width])

    def _toggle_right_panel(self):
        """切换右侧面板显示/隐藏"""
        if self.right_panel.isVisible():
            self._right_panel_width = self.right_panel.width()
            self.right_panel.hide()
            self.right_toggle.setText("◀")
        else:
            self.right_panel.show()
            self.right_toggle.setText("▶")
            splitter = self.center_panel.parent()
            if splitter:
                sizes = splitter.sizes()
                total = sum(sizes)
                splitter.setSizes([self._left_panel_width, total - self._left_panel_width - self._right_panel_width, self._right_panel_width])

    def _connect_signals(self):
        # 模块切换
        self.module_bar.module_changed.connect(self._on_module_changed)

        # 会话操作
        self.session_panel.new_chat_requested.connect(self._on_new_chat)
        self.session_panel.chat_selected.connect(self._on_chat_selected)
        self.session_panel.market_requested.connect(lambda: self.module_changed.emit("market"))

        # 聊天面板信号
        self.chat_panel.send_requested.connect(self._on_chat_send)
        self.chat_panel.stop_requested.connect(self._on_stop_generating)

        # 工作区
        if hasattr(self.workspace_panel, 'folder_changed'):
            self.workspace_panel.folder_changed.connect(self._on_workspace_changed)

        # 知识库相关信号
        if hasattr(self.workspace_panel, 'kb_init_requested'):
            self.workspace_panel.kb_init_requested.connect(self._on_kb_init_requested)
        if hasattr(self.workspace_panel, 'feature_changed'):
            self.workspace_panel.feature_changed.connect(self._on_feature_changed)

    def _on_module_changed(self, module_id: str):
        """模块切换"""
        self._current_module = module_id
        self.module_bar.set_active_module(module_id)
        self.module_changed.emit(module_id)

        if module_id == "settings":
            self._open_settings()
        elif module_id == "user":
            self._open_user_settings()

        self.status_bar.showMessage(f"当前模块: {module_id}")

    def _open_settings(self):
        """打开系统设置"""
        dialog = SystemSettingsDialog(self)
        dialog.exec()

    def _open_user_settings(self):
        """打开用户设置"""
        dialog = UserSettingsDialog(self._get_user_info(), self)
        if dialog.exec() == dialog.Accepted:
            self._user_info = dialog.get_settings()
            self.status_bar.showMessage("用户设置已保存")

    def _on_new_chat(self):
        """新建会话"""
        self._current_chat_id = str(uuid.uuid4())[:8]
        self.new_chat.emit()
        self.chat_panel.clear_messages()
        self.status_bar.showMessage(f"新会话: {self._current_chat_id}")

        # 如果 Agent 就绪，调用 sayhello
        if self._agent_initialized:
            self._do_sayhello()

    def _on_chat_selected(self, chat_id: str):
        """选择会话"""
        self._current_chat_id = chat_id
        self.session_panel.select_session(chat_id)
        self.status_bar.showMessage(f"加载会话: {chat_id}")

    def _on_chat_send(self, text: str):
        """聊天面板发送消息"""
        if not self._agent_initialized or not self._agent_chat:
            self.chat_panel.add_error_message("Agent 未初始化，请等待初始化完成或检查 Ollama 服务")
            return

        # 显示用户消息
        self.chat_panel.add_user_message(text)

        # 显示流式输出状态
        self.chat_panel.start_streaming_output("qwen3.5:4b")

        # 调用 AgentChat（异步）
        self._send_to_agent(text)

    def _send_to_agent(self, text: str):
        """发送消息到 Agent"""
        def run_agent():
            try:
                # 调用 chat
                response = self._agent_chat.chat(text)

                # 在主线程更新
                def update_ui():
                    self.chat_panel.end_streaming_output()
                    if response:
                        self.chat_panel.add_assistant_message(response)
                    else:
                        self.chat_panel.add_error_message("Agent 返回为空")

                QTimer.singleShot(0, update_ui)

            except Exception as e:
                def update_error():
                    self.chat_panel.end_streaming_output()
                    self.chat_panel.add_error_message(f"Agent 调用失败: {str(e)}")
                QTimer.singleShot(0, update_error)

        # 在后台线程执行
        import threading
        t = threading.Thread(target=run_agent, daemon=True)
        t.start()

    def _on_stop_generating(self):
        """停止生成"""
        self.chat_panel.end_streaming_output()
        self.chat_panel.set_running(False)
        self.status_bar.showMessage("已停止生成")

    def _on_workspace_changed(self, folder_path: str):
        """工作区改变"""
        self._workspace_folder = folder_path
        self.workspace_changed.emit(folder_path)
        self.status_bar.showMessage(f"工作区: {folder_path}")

    def _on_kb_init_requested(self):
        """知识库初始化请求"""
        self.status_bar.showMessage("正在初始化知识库...")
        # 实际初始化逻辑会在后台执行
        QTimer.singleShot(100, lambda: self.status_bar.showMessage("知识库初始化完成"))

    def _on_feature_changed(self, feature_id: str):
        """系统特色功能切换"""
        feature_names = {
            "memory_palace": "记忆宫殿",
            "knowledge_graph": "知识图谱",
            "workflow": "工作流",
            "chain_of_thought": "思维链",
            "skill_library": "技能库",
            "system_stats": "系统统计",
            "knowledge_base": "知识库",
            "auto_deploy": "自动化部署",
            "performance": "性能监控",
            "message_queue": "消息队列",
        }
        name = feature_names.get(feature_id, feature_id)
        self.status_bar.showMessage(f"当前功能: {name}")

    def _get_user_info(self) -> dict:
        """获取用户信息"""
        return {
            "username": "Guest",
            "email": "",
            "avatar": "",
            "credit_balance": 0,
            "digital_identity": {
                "level": 1,
                "title": "新手用户",
                "experience": 0,
            },
            "workspace_folder": self._workspace_folder or "",
        }

    def set_chat_enabled(self, enabled: bool):
        """启用/禁用聊天"""
        self.chat_panel.input_box.setEnabled(enabled)

    def show_generating(self, generating: bool):
        """显示生成状态"""
        self.chat_panel.set_running(generating)
        if generating:
            self.module_bar.set_agent_status("思考中...", "#FFD700")
        else:
            self.module_bar.set_agent_status("Agent 就绪", "#10B981")

    def show_message(self, text: str, sender: str = "assistant"):
        """显示消息"""
        if sender == "user":
            self.chat_panel.add_user_message(text)
        else:
            self.chat_panel.add_assistant_message(text)


class StatusIndicator(QWidget):
    """状态指示器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedSize(120, 24)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        self.dot = QLabel("●")
        self.dot.setStyleSheet("color: #CCCCCC; font-size: 10px;")

        self.label = QLabel("未连接")
        self.label.setStyleSheet("""
            color: #888888;
            font-size: 12px;
            font-family: "Microsoft YaHei", sans-serif;
        """)

        layout.addWidget(self.dot)
        layout.addWidget(self.label)
        layout.addStretch()

    def set_status(self, text: str, color: str = "#CCCCCC"):
        self.dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        self.label.setText(text)
        self.label.setStyleSheet(f"""
            color: {color};
            font-size: 12px;
            font-family: "Microsoft YaHei", sans-serif;
        """)


# ── 导出 ──────────────────────────────────────────────────────────────


__all__ = [
    "MainWindow",
    "ModuleBar",
    "SessionPanel",
    "SessionItem",
    "ChatPanel",
    "WorkspacePanel",
    "StatusIndicator",
]
