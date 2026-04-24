"""
LivingTree AI OS - 主窗口
清爽浅色主题，一切通过会话交互

核心布局 (三列结构):
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🌳 Logo  生命之树AI OS  │💬聊天│🔍深度搜索│📚知识库│🎓专家训练│💻智能IDE│✍️智能写作│⚙️│👤│
├──────────┬────────────────────────────────────────────┬────────────────────┤
│ 会话面板  │         聊天面板（默认显示）                   │   文件目录树        │
│ (可收缩)  │  ┌─────────────┬─────────────────────┐   │    (可收缩)         │
│          │  │  任务树面板  │   流式输出面板       │   │                    │
│ 历史...  │  │             │   (带进度条)         │   │  📁 项目            │
│ [+新对话]│  │             │                     │   │    ├─ src/         │
│          │  ├─────────────┴─────────────────────┤   │    └─ tests/       │
│ [市场]   │  │        输入框 + 发送按钮            │   │                    │
└──────────┴──┴─────────────────────────────────────┴──┴────────────────────┘

主题配色 (浅色清爽):
- 主色调: #10B981 (绿色)
- 背景色: #FFFFFF / #F8FAFC
- 边框色: #E8E8E8
- 文字色: #333333 / #666666 / #999999
"""

import os
import uuid
from typing import Optional, List, Tuple
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
from client.src.presentation.panels.workspace_panel import WorkspacePanel

# 导入对话框
from client.src.presentation.dialogs.settings_dialog import UserSettingsDialog, SystemSettingsDialog
from client.src.presentation.dialogs.auth_dialog import LoginDialog, RegisterDialog

try:
    from PyQt6.QtWidgets import QProgressBar
except ImportError:
    QProgressBar = None


class AdvancedChatPanel(QWidget):
    """高级聊天面板 - 包含任务树、流式输出、输入框"""
    
    send_requested = pyqtSignal(str)
    stop_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            AdvancedChatPanel {
                background: #FFFFFF;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # === 上方区域：任务树 + 流式输出（水平分割） ===
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.setHandleWidth(1)
        top_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #E8E8E8;
            }
        """)
        
        # 左侧：任务树面板
        self.task_tree_panel = self._create_task_tree_panel()
        self.task_tree_panel.setMinimumWidth(200)
        top_splitter.addWidget(self.task_tree_panel)
        
        # 右侧：流式输出面板
        self.stream_panel = self._create_stream_panel()
        top_splitter.addWidget(self.stream_panel)
        
        # 设置分割比例：左侧25%，右侧75%
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 3)
        
        layout.addWidget(top_splitter, 1)
        
        # === 下方：输入区域 ===
        self._create_input_area()
        layout.addWidget(self.input_widget)
    
    def _create_task_tree_panel(self) -> QWidget:
        """创建任务树面板"""
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background: #F8FAFC;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # 标题
        title = QLabel("任务树")
        title.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            padding: 4px;
        """)
        layout.addWidget(title)
        
        # 任务列表（模拟）
        self.task_list = QTextEdit()
        self.task_list.setReadOnly(True)
        self.task_list.setStyleSheet("""
            QTextEdit {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 4px;
                color: #666666;
                font-size: 12px;
            }
        """)
        self.task_list.setPlainText("暂无任务")
        layout.addWidget(self.task_list, 1)
        
        return panel
    
    def _create_stream_panel(self) -> QWidget:
        """创建流式输出面板"""
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 标题
        title = QLabel("对话")
        title.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            padding: 4px;
        """)
        layout.addWidget(title)
        
        # 消息区域
        self.message_area = QTextEdit()
        self.message_area.setReadOnly(True)
        self.message_area.setStyleSheet("""
            QTextEdit {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 4px;
                color: #333333;
                font-size: 14px;
                padding: 8px;
            }
        """)
        self.message_area.setPlainText("你好！有什么可以帮助你的吗？")
        layout.addWidget(self.message_area, 1)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #E8E8E8;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #10B981;
                border-radius: 2px;
            }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        return panel
    
    def _create_input_area(self):
        """创建输入区域"""
        self.input_widget = QWidget()
        self.input_widget.setStyleSheet("""
            QWidget {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
            }
        """)
        
        layout = QHBoxLayout(self.input_widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # 输入框
        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("输入消息...")
        self.input_box.setMaximumHeight(80)
        self.input_box.setStyleSheet("""
            QTextEdit {
                background: #F8FAFC;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                padding: 8px 12px;
                color: #333333;
                font-size: 14px;
            }
            QTextEdit:focus {
                border: 1px solid #10B981;
            }
        """)
        layout.addWidget(self.input_box, 1)
        
        # 发送按钮
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(80, 40)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        self.send_btn.clicked.connect(self._on_send)
        layout.addWidget(self.send_btn)
    
    def _on_send(self):
        """发送消息"""
        text = self.input_box.toPlainText().strip()
        if text:
            self.send_requested.emit(text)
            self.input_box.clear()
    
    def add_user_message(self, text: str):
        """添加用户消息"""
        current = self.message_area.toPlainText()
        self.message_area.setPlainText(current + f"\n\n[用户]: {text}")
    
    def add_assistant_message(self, text: str):
        """添加助手消息"""
        current = self.message_area.toPlainText()
        self.message_area.setPlainText(current + f"\n\n[助手]: {text}")
    
    def set_generating(self, generating: bool):
        """设置生成状态"""
        if generating:
            self.progress_bar.show()
            self.progress_bar.setRange(0, 0)  # 不确定进度
        else:
            self.progress_bar.hide()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)


class ModuleBar(QWidget):
    """顶部横排模块选择器 - 左右结构"""
    
    module_changed = pyqtSignal(str)  # module_id
    
    MODULES = [
        ("💬", "聊天", "chat"),        # 聊天模块 - 第一个位置
        ("🔍", "深度搜索", "deep_search"),
        ("📚", "知识库", "knowledge_base"),
        ("🎓", "专家训练", "expert_training"),
        ("💻", "智能IDE", "smart_ide"),
        ("✍️", "智能写作", "smart_writing"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_module = "home"
        self._setup_ui()
    
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
        left_layout.addWidget(self.modules_scroll, 1)  # 模块列表可扩展
        
        main_layout.addWidget(left_widget, 1)  # 左侧占据剩余空间
        
        # === 右侧：设置区 ===
        right_widget = QWidget()
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 12, 0)
        right_layout.setSpacing(4)
        
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
    
    def _add_separator(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("background: #E8E8E8;")
        sep.setFixedWidth(1)
        layout.addWidget(sep)
    
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


class SessionPanel(QWidget):
    """左侧会话历史面板"""
    
    new_chat_requested = pyqtSignal()
    chat_selected = pyqtSignal(str)  # chat_id
    market_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._sessions = []  # {id, title, preview, timestamp}
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
        # 插入到 stretch 之前
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
        # QLabel ellipsis is controlled via size policy, not a method
        
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
        # Ellipsis handled via size policy
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


class WelcomeCard(QWidget):
    """欢迎卡片 - 无消息时显示"""
    
    quick_actions = pyqtSignal(str)  # action_id
    
    QUICK_ACTIONS = [
        ("🔍", "深度搜索", "搜索全网信息"),
        ("📚", "知识库问答", "查询私有知识"),
        ("💻", "写代码", "生成/调试代码"),
        ("✍️", "智能写作", "撰写文章报告"),
        ("📊", "数据分析", "分析数据图表"),
        ("🌐", "翻译助手", "多语言翻译"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            WelcomeCard {
                background: transparent;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)
        
        # Logo
        logo_layout = QVBoxLayout()
        logo_layout.setSpacing(16)
        
        self.logo_label = QLabel("🌳")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setStyleSheet("font-size: 64px;")
        
        self.title_label = QLabel("生命之树AI OS")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("""
            color: #10B981;
            font-size: 28px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        
        self.subtitle_label = QLabel("你的智能助手，一切通过对话完成")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet("""
            color: #888888;
            font-size: 14px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        
        logo_layout.addWidget(self.logo_label)
        logo_layout.addWidget(self.title_label)
        logo_layout.addWidget(self.subtitle_label)
        layout.addLayout(logo_layout)
        
        # 快捷操作
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)
        
        for emoji, name, desc in self.QUICK_ACTIONS:
            btn = QPushButton(f"{emoji}\n{name}")
            btn.setFixedSize(100, 80)
            btn.setStyleSheet("""
                QPushButton {
                    background: #FFFFFF;
                    border: 1px solid #E8E8E8;
                    border-radius: 12px;
                    color: #333333;
                    font-size: 14px;
                    padding: 8px;
                }
                QPushButton:hover {
                    background: #F0FDF4;
                    border-color: #10B981;
                }
            """)
            actions_layout.addWidget(btn)
        
        layout.addLayout(actions_layout)
        layout.addStretch()


class InputArea(QWidget):
    """底部输入区域"""
    
    send_requested = pyqtSignal(str)  # text
    attach_requested = pyqtSignal(str)  # attach_type
    stop_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_generating = False
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            InputArea {
                background: #FFFFFF;
                border-top: 1px solid #E8E8E8;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)
        
        # 附件栏
        attach_layout = QHBoxLayout()
        attach_layout.setSpacing(8)
        
        self.attach_btn = QPushButton("📎")
        self.attach_btn.setFixedSize(32, 32)
        self.attach_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F5;
                border: none;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #E8E8E8;
            }
        """)
        self.attach_btn.clicked.connect(lambda: self._show_attach_menu())
        
        self.image_btn = QPushButton("🖼️")
        self.image_btn.setFixedSize(32, 32)
        self.image_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F5;
                border: none;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #E8E8E8;
            }
        """)
        self.image_btn.clicked.connect(lambda: self.attach_requested.emit("image"))
        
        self.doc_btn = QPushButton("📄")
        self.doc_btn.setFixedSize(32, 32)
        self.doc_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F5;
                border: none;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #E8E8E8;
            }
        """)
        self.doc_btn.clicked.connect(lambda: self.attach_requested.emit("document"))
        
        self.voice_btn = QPushButton("🎤")
        self.voice_btn.setFixedSize(32, 32)
        self.voice_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F5;
                border: none;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #E8E8E8;
            }
        """)
        self.voice_btn.clicked.connect(lambda: self.attach_requested.emit("voice"))
        
        attach_layout.addWidget(self.attach_btn)
        attach_layout.addWidget(self.image_btn)
        attach_layout.addWidget(self.doc_btn)
        attach_layout.addWidget(self.voice_btn)
        attach_layout.addStretch()
        
        layout.addLayout(attach_layout)
        
        # 输入框和发送按钮
        input_layout = QHBoxLayout()
        input_layout.setSpacing(12)
        
        # 输入框
        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("输入消息，或告诉我想帮你做什么...")
        self.input_box.setMinimumHeight(44)
        self.input_box.setMaximumHeight(120)
        self.input_box.setStyleSheet("""
            QTextEdit {
                background: #F5F5F5;
                border: none;
                border-radius: 12px;
                padding: 12px 16px;
                color: #333333;
                font-size: 14px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QTextEdit::placeholder {
                color: #999999;
            }
            QTextEdit:focus {
                background: #FFFFFF;
                border: 1px solid #10B981;
            }
        """)
        self.input_box.setAcceptRichText(False)
        
        input_layout.addWidget(self.input_box, 1)
        
        # 发送按钮
        self.send_btn = QPushButton("➤")
        self.send_btn.setFixedSize(44, 44)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                border: none;
                border-radius: 12px;
                color: #FFFFFF;
                font-size: 20px;
            }
            QPushButton:hover {
                background: #059669;
            }
            QPushButton:disabled {
                background: #CCCCCC;
                color: #999999;
            }
        """)
        self.send_btn.clicked.connect(self._on_send)
        
        # 停止按钮（生成中显示）
        self.stop_btn = QPushButton("⬛")
        self.stop_btn.setFixedSize(44, 44)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #EF4444;
                border: none;
                border-radius: 12px;
                color: #FFFFFF;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #DC2626;
            }
        """)
        self.stop_btn.hide()
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        
        input_layout.addWidget(self.send_btn)
        input_layout.addWidget(self.stop_btn)
        
        layout.addLayout(input_layout)
    
    def _show_attach_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                color: #333333;
                font-size: 13px;
            }
            QMenu::item:selected {
                background: #F0FDF4;
            }
        """)
        menu.addAction("📷 图片", lambda: self.attach_requested.emit("image"))
        menu.addAction("📄 文档", lambda: self.attach_requested.emit("document"))
        menu.addAction("📁 文件夹", lambda: self.attach_requested.emit("folder"))
        menu.exec(self.attach_btn.mapToGlobal(self.attach_btn.rect().bottomLeft()))
    
    def _on_send(self):
        text = self.input_box.toPlainText().strip()
        if text:
            self.send_requested.emit(text)
            self.input_box.clear()
    
    def set_generating(self, generating: bool):
        """设置是否正在生成"""
        self._is_generating = generating
        self.send_btn.setVisible(not generating)
        self.stop_btn.setVisible(generating)
        self.input_box.setReadOnly(generating)
    
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._on_send()
        else:
            super().keyPressEvent(event)


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
        self.dot.setStyleSheet("color: #10B981; font-size: 10px;")
        
        self.label = QLabel("就绪")
        self.label.setStyleSheet("""
            color: #888888;
            font-size: 12px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        
        layout.addWidget(self.dot)
        layout.addWidget(self.label)
        layout.addStretch()
    
    def set_status(self, text: str, color: str = "#00D4AA"):
        self.dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        self.label.setText(text)
        self.label.setStyleSheet(f"""
            color: {color};
            font-size: 12px;
            font-family: "Microsoft YaHei", sans-serif;
        """)


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
        self._current_module = "home"
        self._current_chat_id = None
        self._workspace_folder = None
        self._attachments = []
        self._user_info = self._get_user_info()
        
        self._setup_ui()
        self._connect_signals()
    
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
        
        # ====== 三列布局（充满区域，水平拖动） ======
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
        
        # === 中间：功能模块区域 ===
        self.center_panel = QWidget()
        self.center_panel.setStyleSheet("background: #F8FAFC;")
        self.center_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        
        # 欢迎卡片（默认隐藏）
        self.welcome_card = WelcomeCard()
        self.welcome_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.welcome_card.hide()
        center_layout.addWidget(self.welcome_card, 1)
        
        # 高级聊天面板（默认显示）
        self.chat_panel = AdvancedChatPanel()
        self.chat_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        center_layout.addWidget(self.chat_panel, 1)
        
        # 输入区域（隐藏，聊天面板自带）
        self.input_area = InputArea()
        self.input_area.hide()
        self.input_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        center_layout.addWidget(self.input_area)
        
        content.addWidget(self.center_panel)
        
        # === 右侧：文件目录树（可收缩） ===
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
        
        # 设置初始宽度（定时执行，确保窗口已创建）
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
        self.status_bar.showMessage("🌳 生命之树AI OS 已就绪")
        main_layout.addWidget(self.status_bar)
    
    def _init_panel_widths(self, splitter):
        """初始化面板宽度"""
        total_width = splitter.width()
        splitter.setStretchFactor(0, 0)  # 左侧固定
        splitter.setStretchFactor(1, 1)  # 中间自适应
        splitter.setStretchFactor(2, 0)  # 右侧固定
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
            # 恢复宽度
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
            # 恢复宽度
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
        
        # 高级聊天面板信号
        self.chat_panel.send_requested.connect(self._on_chat_send)
        
        # 输入区域（用于非聊天模块）
        self.input_area.send_requested.connect(self._on_send_message)
        self.input_area.stop_requested.connect(self._on_stop_generating)
        self.input_area.attach_requested.connect(self._on_attach_requested)
        
        # 工作区 (如果支持folder_changed信号才连接)
        if hasattr(self.workspace_panel, 'folder_changed'):
            self.workspace_panel.folder_changed.connect(self._on_workspace_changed)
    
    def _on_module_changed(self, module_id: str):
        """模块切换 - 内容在中间面板显示"""
        self._current_module = module_id
        self.module_bar.set_active_module(module_id)
        self.module_changed.emit(module_id)
        
        # 隐藏中间面板所有内容
        self.welcome_card.hide()
        self.chat_panel.hide()
        self.input_area.hide()
        
        # 根据模块更新UI - 内容显示在中间面板
        if module_id == "chat":
            # 聊天模块 - 默认显示高级聊天面板
            self.chat_panel.show()
        elif module_id == "home":
            # 主界面 - 显示欢迎卡片
            self.welcome_card.show()
        elif module_id in ["deep_search", "knowledge_base", "expert_training", "smart_ide", "smart_writing"]:
            # 功能模块 - 显示输入区
            self.input_area.show()
        elif module_id == "settings":
            self._open_settings()
            return
        elif module_id == "user":
            self._open_user_settings()
            return
        
        self.status_indicator.set_status(f"当前: {module_id}")
    
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
        self.welcome_card.hide()
        self.input_area.show()
        self.status_bar.showMessage(f"新会话: {self._current_chat_id}")
    
    def _on_chat_selected(self, chat_id: str):
        """选择会话"""
        self._current_chat_id = chat_id
        self.session_panel.select_session(chat_id)
        self.welcome_card.hide()
        self.chat_panel.show()
        self.input_area.show()
        self.status_bar.showMessage(f"加载会话: {chat_id}")
    
    def _on_send_message(self, text: str):
        """发送消息"""
        self.send_message.emit(text, self._attachments.copy())
        self._attachments.clear()
        self.input_area.set_generating(True)
        self.status_indicator.set_status("思考中...", "#FFD700")
    
    def _on_chat_send(self, text: str):
        """聊天面板发送消息"""
        self.send_message.emit(text, [])
        self.status_indicator.set_status("思考中...", "#FFD700")
    
    def _on_stop_generating(self):
        """停止生成"""
        self.input_area.set_generating(False)
        self.status_indicator.set_status("已停止")
    
    def _on_attach_requested(self, attach_type: str):
        """请求附件"""
        if attach_type == "image":
            files, _ = QFileDialog.getOpenFileNames(
                self, "选择图片", "",
                "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
            )
            if files:
                self._attachments.extend(files)
        elif attach_type == "document":
            files, _ = QFileDialog.getOpenFileNames(
                self, "选择文档", "",
                "文档文件 (*.pdf *.doc *.docx *.txt *.md)"
            )
            if files:
                self._attachments.extend(files)
        elif attach_type == "folder":
            folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
            if folder:
                self._attachments.append(folder)
    
    def _on_workspace_changed(self, folder_path: str):
        """工作区改变"""
        self._workspace_folder = folder_path
        self.workspace_changed.emit(folder_path)
        self.status_bar.showMessage(f"工作区: {folder_path}")
    
    def _get_user_info(self) -> dict:
        """获取用户信息"""
        # TODO: 从数据库或配置文件加载用户信息
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
        self.input_area.setEnabled(enabled)
    
    def show_generating(self, generating: bool):
        """显示生成状态"""
        self.input_area.set_generating(generating)
        if generating:
            self.status_indicator.set_status("生成中...", "#10B981")
        else:
            self.status_indicator.set_status("就绪")
    
    def show_message(self, text: str, sender: str = "assistant"):
        """显示消息"""
        # 通过聊天面板显示
        if sender == "user":
            self.chat_panel.add_user_message(text)
        else:
            self.chat_panel.add_assistant_message(text)


# ── 导出 ──────────────────────────────────────────────────────────────


__all__ = [
    "MainWindow",
    "ModuleBar",
    "SessionPanel",
    "SessionItem",
    "ChatArea",
    "InputArea",
    "WorkspacePanel",
    "WelcomeCard",
    "StatusIndicator",
]
