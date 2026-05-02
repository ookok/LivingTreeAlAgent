"""
主窗口 - Main Window

功能：
1. 集成所有核心模块
2. 实现类VSCode布局
3. 提供完美桌面体验
"""

import sys
import logging
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLayout, QHBoxLayout, QVBoxLayout,
    QSplitter, QStatusBar, QToolBar, QFrame, QLabel, QPushButton, QMenu
)
from PyQt6.QtCore import Qt, QSize, QUrl, QPoint
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtGui import QIcon, QAction, QCursor

from .core import (
    OptimizedWebEngineView,
    PluginSystem,
    ThemeSystem,
    WindowManager,
    Panel,
    PanelPosition,
    CommandSystem,
    Command,
    get_command_system,
    get_store,
    Action
)

from .web_ui.web_channel_backend import WebChannelBackend

logger = logging.getLogger(__name__)


class SidebarPanel(Panel):
    """侧边栏面板"""
    def __init__(self):
        super().__init__("sidebar", "侧边栏")
        self._nav_items = [
            ("dashboard", "控制面板", "📊"),
            ("memory", "记忆系统", "🧠"),
            ("learning", "持续学习", "📚"),
            ("reasoning", "认知推理", "🤔"),
            ("selfawareness", "自我意识", "🔧"),
            ("mcp", "MCP服务", "🔌")
        ]
    
    def _create_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Logo
        logo_label = QLabel("🧠 Hermes")
        logo_label.setStyleSheet("font-size: 24px; font-weight: bold; text-align: center; margin-bottom: 20px;")
        layout.addWidget(logo_label)
        
        # 导航按钮
        for item_id, label, icon in self._nav_items:
            btn = QPushButton(f"{icon} {label}")
            btn.setObjectName(f"nav-btn-{item_id}")
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 12px 16px;
                    margin-bottom: 8px;
                    border-radius: 10px;
                    border: none;
                    background: transparent;
                    color: rgba(255, 255, 255, 0.7);
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.1);
                    color: white;
                }
                QPushButton.active {
                    background: linear-gradient(135deg, #00d4ff, #7b2fff);
                    color: white;
                }
            """)
            btn.clicked.connect(lambda checked, id=item_id: self._on_nav_click(id))
            layout.addWidget(btn)
        
        layout.addStretch()
        
        return widget
    
    def _on_nav_click(self, item_id):
        """处理导航点击"""
        store = get_store()
        store.dispatch(Action('SET_ACTIVE_TAB', item_id))


class StatusBarWidget(QStatusBar):
    """状态栏组件"""
    def __init__(self):
        super().__init__()
        self._init_status_items()
    
    def _init_status_items(self):
        # 系统状态
        self._status_indicator = QLabel()
        self._status_indicator.setStyleSheet("color: #00ff88;")
        self.addWidget(self._status_indicator)
        
        self.addPermanentWidget(QLabel("|"))
        
        # CPU使用率
        self._cpu_label = QLabel("CPU: --%")
        self.addPermanentWidget(self._cpu_label)
        
        # 内存使用率
        self._memory_label = QLabel("内存: --%")
        self.addPermanentWidget(self._memory_label)
        
        # 当前时间
        self._time_label = QLabel()
        self.addPermanentWidget(self._time_label)
        
        self._update_time()
    
    def _update_time(self):
        """更新时间"""
        from datetime import datetime
        self._time_label.setText(datetime.now().strftime("%H:%M:%S"))
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1000, self._update_time)
    
    def update_system_status(self, online: bool):
        """更新系统状态"""
        if online:
            self._status_indicator.setText("✓ 系统在线")
        else:
            self._status_indicator.setText("✗ 系统离线")
    
    def update_metrics(self, cpu: float, memory: float):
        """更新性能指标"""
        self._cpu_label.setText(f"CPU: {cpu:.1f}%")
        self._memory_label.setText(f"内存: {memory:.1f}%")


class CustomTitleBar(QWidget):
    """自定义标题栏"""
    def __init__(self, parent):
        super().__init__()
        self._parent = parent
        self._init_ui()
        self._dragging = False
        self._drag_start_pos = QPoint()
    
    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 左侧：应用图标和名称
        icon_label = QLabel("🧠")
        icon_label.setStyleSheet("font-size: 20px; padding: 0 8px;")
        layout.addWidget(icon_label)
        
        app_name = QLabel("Hermes AI Agent")
        app_name.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(app_name)
        
        layout.addStretch()
        
        # 窗口控制按钮
        self._min_btn = QPushButton("−")
        self._max_btn = QPushButton("□")
        self._close_btn = QPushButton("×")
        
        for btn in [self._min_btn, self._max_btn, self._close_btn]:
            btn.setFixedSize(46, 32)
            btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background: transparent;
                    font-size: 16px;
                    color: rgba(255, 255, 255, 0.7);
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.1);
                }
                QPushButton#close-btn:hover {
                    background: #ff4757;
                    color: white;
                }
            """)
            layout.addWidget(btn)
        
        self._min_btn.clicked.connect(self._parent.showMinimized)
        self._max_btn.clicked.connect(self._toggle_maximize)
        self._close_btn.setObjectName("close-btn")
        self._close_btn.clicked.connect(self._parent.close)
    
    def _toggle_maximize(self):
        """切换最大化"""
        if self._parent.isMaximized():
            self._parent.showNormal()
        else:
            self._parent.showMaximized()
    
    def mousePressEvent(self, event):
        """鼠标按下事件（用于拖动）"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.globalPosition().toPoint() - self._parent.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件（用于拖动）"""
        if self._dragging:
            self._parent.move(event.globalPosition().toPoint() - self._drag_start_pos)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        self._dragging = False


class MainWindow(QMainWindow):
    """
    主窗口 - 集成所有核心模块
    
    特性：
    1. 自定义标题栏
    2. 多面板布局
    3. WebEngine集成
    4. 完整的命令系统
    """
    
    def __init__(self):
        super().__init__()
        self._init_config()
        self._init_core_modules()
        self._init_ui()
        self._init_command_system()
        self._init_event_listeners()
        
        logger.info("主窗口初始化完成")
    
    def _init_config(self):
        """初始化配置"""
        self.setWindowTitle("Hermes AI Agent Platform")
        self.setGeometry(100, 100, 1400, 900)
        
        # 隐藏默认标题栏（使用自定义标题栏）
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
    
    def _init_core_modules(self):
        """初始化核心模块"""
        self._plugin_system = PluginSystem()
        self._theme_system = ThemeSystem()
        self._command_system = get_command_system()
        self._store = get_store()
        
        # 加载主题偏好
        self._theme_system.load_preference()
    
    def _init_ui(self):
        """初始化UI"""
        # 创建中央组件
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        
        # 主布局（垂直布局：标题栏 + 内容区域）
        self._main_layout = QVBoxLayout(self._central_widget)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
        
        # 自定义标题栏
        self._title_bar = CustomTitleBar(self)
        self._main_layout.addWidget(self._title_bar)
        
        # 内容区域（水平分隔器）
        self._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_layout.addWidget(self._content_splitter)
        
        # 侧边栏
        self._sidebar = SidebarPanel()
        self._sidebar_widget = self._sidebar.get_widget()
        self._sidebar_widget.setFixedWidth(280)
        self._content_splitter.addWidget(self._sidebar_widget)
        
        # 主内容区域（WebEngine）
        self._web_view = OptimizedWebEngineView()
        self._content_splitter.addWidget(self._web_view)
        
        # 设置分隔器比例
        self._content_splitter.setStretchFactor(0, 1)
        self._content_splitter.setStretchFactor(1, 4)
        
        # 状态栏
        self._status_bar = StatusBarWidget()
        self.setStatusBar(self._status_bar)
        
        # 初始化WebChannel
        self._init_web_channel()
        
        # 加载Web UI
        self._load_web_ui()
    
    def _init_web_channel(self):
        """初始化WebChannel通信"""
        self._web_channel = QWebChannel()
        self._backend = WebChannelBackend()
        self._web_channel.registerObject("backend", self._backend)
        self._web_view.page().setWebChannel(self._web_channel)
    
    def _load_web_ui(self):
        """加载Web UI页面"""
        import os
        ui_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(ui_dir, 'web_ui', 'index.html')
        
        if os.path.exists(html_path):
            url = QUrl.fromLocalFile(html_path)
            self._web_view.load(url)
        else:
            logger.error(f"未找到UI文件: {html_path}")
            self._status_bar.update_system_status(False)
    
    def _init_command_system(self):
        """初始化命令系统"""
        commands = [
            Command(
                id="app.quit",
                name="退出应用",
                description="关闭Hermes AI Agent",
                handler=self.close,
                shortcut="Ctrl+Q",
                category="应用"
            ),
            Command(
                id="window.maximize",
                name="最大化窗口",
                description="将窗口最大化",
                handler=self.showMaximized,
                shortcut="F11",
                category="窗口"
            ),
            Command(
                id="window.minimize",
                name="最小化窗口",
                description="将窗口最小化",
                handler=self.showMinimized,
                shortcut="Ctrl+M",
                category="窗口"
            ),
            Command(
                id="window.toggle-fullscreen",
                name="切换全屏",
                description="切换全屏模式",
                handler=self._toggle_fullscreen,
                shortcut="F11",
                category="窗口"
            ),
            Command(
                id="system.initialize",
                name="初始化系统",
                description="初始化所有子系统",
                handler=self._initialize_systems,
                category="系统"
            ),
            Command(
                id="system.refresh",
                name="刷新页面",
                description="刷新Web页面",
                handler=self._web_view.reload,
                shortcut="Ctrl+R",
                category="系统"
            ),
            Command(
                id="view.sidebar.toggle",
                name="切换侧边栏",
                description="显示/隐藏侧边栏",
                handler=self._toggle_sidebar,
                shortcut="Ctrl+B",
                category="视图"
            ),
            Command(
                id="theme.dark",
                name="切换深色主题",
                description="切换到深色主题",
                handler=lambda: self._theme_system.set_theme(ThemeType.DARK),
                category="主题"
            ),
            Command(
                id="theme.light",
                name="切换浅色主题",
                description="切换到浅色主题",
                handler=lambda: self._theme_system.set_theme(ThemeType.LIGHT),
                category="主题"
            )
        ]
        
        self._command_system.register_commands(commands)
    
    def _init_event_listeners(self):
        """初始化事件监听器"""
        # 监听状态变化
        self._store.subscribe(self._on_state_change)
        
        # 监听键盘快捷键
        self.installEventFilter(self)
    
    def _on_state_change(self, state):
        """处理状态变化"""
        active_tab = state.get('app', {}).get('active_tab')
        if active_tab:
            # 更新导航按钮状态
            for btn in self._sidebar_widget.findChildren(QPushButton):
                btn.setProperty('class', '')
                btn.setStyleSheet(btn.styleSheet().replace('QPushButton.active', 'QPushButton'))
                
                if btn.objectName() == f"nav-btn-{active_tab}":
                    btn.setStyleSheet(btn.styleSheet().replace(
                        'QPushButton {',
                        'QPushButton.active {'
                    ))
    
    def _toggle_fullscreen(self):
        """切换全屏"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def _toggle_sidebar(self):
        """切换侧边栏显示"""
        if self._sidebar_widget.isVisible():
            self._sidebar_widget.hide()
        else:
            self._sidebar_widget.show()
    
    def _initialize_systems(self):
        """初始化系统"""
        self._status_bar.update_system_status(False)
        
        from livingtree.core.integration.system_manager import get_system_manager
        system_manager = get_system_manager()
        system_manager.initialize()
        
        self._status_bar.update_system_status(True)
    
    def eventFilter(self, obj, event):
        """事件过滤器（处理快捷键）"""
        from PyQt6.QtGui import QKeyEvent
        
        if isinstance(event, QKeyEvent):
            # 构建快捷键字符串
            modifiers = []
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                modifiers.append("Ctrl")
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                modifiers.append("Shift")
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                modifiers.append("Alt")
            
            key = event.key()
            key_name = QKeyEvent.keyToString(key)
            
            if modifiers:
                shortcut = "+".join(modifiers) + "+" + key_name
            else:
                shortcut = key_name
            
            # 尝试执行命令
            result = self._command_system.execute_by_shortcut(shortcut)
            if result is not None:
                return True
        
        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        """关闭事件处理"""
        # 保存窗口状态
        self._save_window_state()
        
        # 关闭插件系统
        self._plugin_system.shutdown()
        
        # 关闭后端
        self._backend.deleteLater()
        
        event.accept()
    
    def _save_window_state(self):
        """保存窗口状态"""
        import json
        import os
        
        state = {
            'geometry': {
                'x': self.x(),
                'y': self.y(),
                'width': self.width(),
                'height': self.height()
            },
            'maximized': self.isMaximized()
        }
        
        state_path = os.path.join(os.path.expanduser("~"), ".hermes", "window_state.json")
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2)


def run_app():
    """运行应用"""
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyleSheet("""
        QWidget {
            background: #1a1a2e;
            color: white;
        }
        QSplitter::handle {
            background: rgba(255, 255, 255, 0.1);
            width: 4px;
        }
        QSplitter::handle:hover {
            background: rgba(255, 255, 255, 0.2);
        }
    """)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())