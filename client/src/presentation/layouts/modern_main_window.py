"""
现代化主窗口 - 全新设计

特性：
- 现代扁平化设计
- 清晰的布局结构
- 流畅的动画过渡
- 响应式布局
- 美观的深色主题
"""

from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QFrame, QLabel, QPushButton,
    QToolButton, QSpacerItem, QSizePolicy
)
from PyQt6.QtGui import QPalette, QColor

from ..theme.dracula_theme import DRACULA
from ..router.router import get_router, Router
from .sidebar import SidebarWidget

from business.auth_system import AuthSystem, UserProfile


class ModernMainWindow(QMainWindow):
    """
    现代化主窗口
    
    布局结构：
    ┌─────────────────────────────────────────────────────────────┐
    │  TopBar: Logo | Title | Search | Theme | User             │
    ├───────────────┬───────────────────────────────────────────┤
    │   Sidebar     │                                          │
    │   Navigation  │              Workspace                    │
    │               │                                          │
    │   [Chat]      │     ┌───────────────────────────────┐     │
    │   [Knowledge] │     │   Chat Panel / Main Content   │     │
    │   [Search]    │     │                               │     │
    │   [Tools]     │     │                               │     │
    │   [Settings]  │     │                               │     │
    │               │     └───────────────────────────────┘     │
    └───────────────┴───────────────────────────────────────────┘
    """

    theme_changed = pyqtSignal(str)
    login_status_changed = pyqtSignal(bool, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌙 生命之树 AI")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 600)

        # 初始化系统组件
        self.auth_system = AuthSystem()
        self._router = get_router()
        self._router.set_parent(self)
        self._router.register_route_changed_listener(self._on_route_changed)

        # 初始化状态
        self._is_sidebar_collapsed = False
        self._current_route = None

        # 构建UI
        self._build_ui()
        
        # 注册路由
        self._register_routes()
        
        # 应用主题
        self._apply_modern_theme()

        # 默认导航到聊天面板
        self._navigate_to("chat")

    def _build_ui(self):
        """构建现代化UI"""
        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 侧边栏
        self._sidebar = ModernSidebar(self)
        self._sidebar.route_selected.connect(self._navigate_to)
        self._sidebar.collapsed.connect(self._toggle_sidebar)
        main_layout.addWidget(self._sidebar)

        # 主内容区域
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 顶部工具栏
        self._top_bar = ModernTopBar(self)
        self._top_bar.theme_toggled.connect(self._toggle_theme)
        self._top_bar.search_triggered.connect(self._on_search)
        content_layout.addWidget(self._top_bar)

        # 工作区（路由容器）
        self._workspace = QStackedWidget()
        self._workspace.setStyleSheet(f"background-color: {DRACULA.BG_MAIN};")
        content_layout.addWidget(self._workspace, 1)

        main_layout.addWidget(content_area, 1)

    def _register_routes(self):
        """注册路由"""
        from ..router.routes import register_default_routes
        register_default_routes(self._router)

    def _navigate_to(self, route_id: str):
        """导航到指定路由"""
        self._current_route = route_id
        
        # 获取面板
        panel = self._router.navigate_to(route_id)
        if panel:
            # 检查面板是否已存在
            existing_index = self._workspace.indexOf(panel)
            if existing_index >= 0:
                self._workspace.setCurrentIndex(existing_index)
            else:
                # 添加面板并设置动画
                self._workspace.addWidget(panel)
                self._animate_panel_switch(self._workspace.count() - 1)
            
            # 更新标题
            route = self._router.get_route(route_id)
            if route:
                self._top_bar.set_title(f"{route.emoji} {route.name}")
            
            # 更新侧边栏选中状态
            self._sidebar.set_selected(route_id)

    def _animate_panel_switch(self, index: int):
        """面板切换动画"""
        current_widget = self._workspace.currentWidget()
        if current_widget:
            # 淡出当前面板
            fade_out = QPropertyAnimation(current_widget, b"windowOpacity")
            fade_out.setDuration(200)
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.3)
            fade_out.start()
        
        # 切换面板
        self._workspace.setCurrentIndex(index)
        
        # 淡入新面板
        new_widget = self._workspace.currentWidget()
        if new_widget:
            new_widget.setWindowOpacity(0.3)
            fade_in = QPropertyAnimation(new_widget, b"windowOpacity")
            fade_in.setDuration(200)
            fade_in.setStartValue(0.3)
            fade_in.setEndValue(1.0)
            fade_in.start()

    def _toggle_sidebar(self):
        """切换侧边栏展开/折叠"""
        self._is_sidebar_collapsed = not self._is_sidebar_collapsed
        
        if self._is_sidebar_collapsed:
            self._sidebar.collapse()
        else:
            self._sidebar.expand()

    def _toggle_theme(self):
        """切换主题"""
        # 主题切换逻辑
        self._apply_modern_theme()

    def _on_search(self, query: str):
        """处理搜索"""
        if query:
            self._navigate_to("search")

    def _on_route_changed(self, route_id: str):
        """路由变化回调"""
        self._navigate_to(route_id)

    def _apply_modern_theme(self):
        """应用现代化深色主题"""
        c = DRACULA
        
        # 主窗口样式
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {c.BG_MAIN};
                color: {c.TEXT_PRIMARY};
            }}
            QWidget {{
                background-color: {c.BG_MAIN};
                color: {c.TEXT_PRIMARY};
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }}
        """)


class ModernSidebar(QWidget):
    """现代化侧边栏"""
    
    route_selected = pyqtSignal(str)
    collapsed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = {}
        self._selected_id = None
        self._is_collapsed = False
        
        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        """构建侧边栏UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo区域
        logo_frame = QFrame()
        logo_frame.setFixedHeight(60)
        logo_layout = QHBoxLayout(logo_frame)
        logo_layout.setContentsMargins(16, 0, 16, 0)
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._logo_label = QLabel("🌙")
        self._logo_label.setStyleSheet("font-size: 24px;")
        logo_layout.addWidget(self._logo_label)

        self._title_label = QLabel("生命之树")
        logo_layout.addWidget(self._title_label)

        layout.addWidget(logo_frame)

        # 导航按钮区域
        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(8, 16, 8, 16)
        nav_layout.setSpacing(4)

        # 定义导航项 - 四个核心功能
        nav_items = [
            ("chat", "💬", "智能对话"),
            ("smart_ide", "💻", "代码开发"),
            ("settings", "⚙️", "系统设置"),
            ("profile", "👤", "用户设置"),
        ]

        for route_id, emoji, name in nav_items:
            btn = QToolButton()
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setText(f"{emoji} {name}")
            btn.setFixedHeight(44)
            btn.clicked.connect(lambda checked, rid=route_id: self._on_route_click(rid))
            
            self._buttons[route_id] = btn
            nav_layout.addWidget(btn)

        layout.addLayout(nav_layout)

        # 分隔线
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {DRACULA.BORDER};")
        layout.addWidget(divider)

        # 底部操作区
        bottom_layout = QVBoxLayout()
        bottom_layout.setContentsMargins(8, 16, 8, 16)
        bottom_layout.setSpacing(4)

        # 折叠按钮
        collapse_btn = QToolButton()
        collapse_btn.setText("◀")
        collapse_btn.setFixedHeight(36)
        collapse_btn.clicked.connect(self.collapsed.emit)
        bottom_layout.addWidget(collapse_btn)

        layout.addLayout(bottom_layout)

        # 设置最小/最大宽度
        self.setMinimumWidth(60)
        self.setMaximumWidth(240)
        self.setFixedWidth(240)

    def _apply_style(self):
        """应用侧边栏样式"""
        c = DRACULA
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {c.BG_SECONDARY};
            }}
            QLabel {{
                color: {c.TEXT_PRIMARY};
                font-size: 16px;
                font-weight: bold;
                margin-left: 8px;
            }}
            QToolButton {{
                background-color: transparent;
                border: none;
                border-radius: 8px;
                color: {c.TEXT_SECONDARY};
                padding: 10px 12px;
                text-align: left;
                font-size: 14px;
                font-weight: 500;
            }}
            QToolButton:hover {{
                background-color: {c.BG_TERTIARY};
                color: {c.TEXT_PRIMARY};
            }}
            QToolButton:checked {{
                background-color: {c.PRIMARY_LIGHT};
                color: {c.PRIMARY};
            }}
        """)

    def _on_route_click(self, route_id: str):
        """处理路由点击"""
        self.set_selected(route_id)
        self.route_selected.emit(route_id)

    def set_selected(self, route_id: str):
        """设置选中状态"""
        if self._selected_id in self._buttons:
            self._buttons[self._selected_id].setChecked(False)
        
        self._selected_id = route_id
        
        if route_id in self._buttons:
            self._buttons[route_id].setChecked(True)

    def collapse(self):
        """折叠侧边栏"""
        self._is_collapsed = True
        self.setFixedWidth(60)
        self._title_label.hide()
        
        for route_id, btn in self._buttons.items():
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            btn.setText(self._get_emoji(route_id))

    def expand(self):
        """展开侧边栏"""
        self._is_collapsed = False
        self.setFixedWidth(240)
        self._title_label.show()
        
        nav_items = {
            "chat": "💬 智能对话",
            "smart_ide": "💻 代码开发",
            "settings": "⚙️ 系统设置",
            "profile": "👤 用户设置",
        }
        
        for route_id, btn in self._buttons.items():
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setText(nav_items.get(route_id, route_id))

    def _get_emoji(self, route_id: str) -> str:
        """获取路由图标"""
        emojis = {
            "chat": "💬",
            "smart_ide": "💻",
            "settings": "⚙️",
            "profile": "👤",
        }
        return emojis.get(route_id, "📄")


class ModernTopBar(QWidget):
    """现代化顶部工具栏"""
    
    theme_toggled = pyqtSignal()
    search_triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        """构建工具栏UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(16)

        # 标题
        self._title_label = QLabel("💬 智能对话")
        layout.addWidget(self._title_label)

        # 搜索框
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        
        self._search_input = QLabel("🔍 搜索...")
        self._search_input.setStyleSheet("""
            QLabel {
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 13px;
            }
        """)
        search_layout.addWidget(self._search_input)
        
        layout.addLayout(search_layout)

        # 占位符
        layout.addStretch()

        # 快捷操作按钮
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        # 主题切换按钮
        self._theme_btn = QToolButton()
        self._theme_btn.setText("🎨")
        self._theme_btn.setFixedSize(36, 36)
        self._theme_btn.clicked.connect(self.theme_toggled.emit)
        actions_layout.addWidget(self._theme_btn)

        # 用户按钮
        self._user_btn = QToolButton()
        self._user_btn.setText("👤")
        self._user_btn.setFixedSize(36, 36)
        actions_layout.addWidget(self._user_btn)

        layout.addLayout(actions_layout)

        # 设置固定高度
        self.setFixedHeight(56)

    def _apply_style(self):
        """应用工具栏样式"""
        c = DRACULA
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c.BG_SECONDARY};
                border-bottom: 1px solid {c.BORDER};
            }}
            QLabel {{
                font-size: 18px;
                font-weight: bold;
                color: {c.TEXT_PRIMARY};
            }}
            QToolButton {{
                background-color: {c.BG_TERTIARY};
                color: {c.TEXT_PRIMARY};
                border: none;
                border-radius: 8px;
                font-size: 16px;
            }}
            QToolButton:hover {{
                background-color: {c.BORDER_LIGHT};
            }}
        """)

    def set_title(self, title: str):
        """设置标题"""
        self._title_label.setText(title)