"""
主窗口 - 重写版
简化实现，确保样式表正确应用
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QFrame, QLabel, QPushButton,
    QMenu, QScrollArea
)
from PyQt6.QtGui import QPixmap, QAction
from typing import Optional

from ..theme.theme_manager import theme_manager
from ..theme.dracula_theme import get_dracula_stylesheet
from ..router.router import get_router, Router
from .sidebar import SidebarWidget

from business.auth_system import AuthSystem, UserProfile


class MainWindow(QMainWindow):
    """
    主窗口 - 简化版
    
    功能：
    1. 布局管理（左侧栏 + 工作区）
    2. 路由注册和切换
    3. 主题切换
    4. 用户登录/登出
    """

    theme_changed = pyqtSignal(str)
    login_status_changed = pyqtSignal(bool, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌙 生命之树 AI")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 600)

        # 认证系统
        self.auth_system = AuthSystem()
        self.current_user: Optional[UserProfile] = None

        # 路由管理器
        self._router: Router = get_router()
        self._router.set_parent(self)
        self._router.register_route_changed_listener(self._on_route_changed)

        # 设置UI
        self._setup_ui()
        
        # 注册路由
        self._register_default_routes()
        
        # 应用主题（必须在UI设置之后）
        self._apply_theme()

        # 恢复会话
        self._restore_session()

    def _setup_ui(self):
        """构建UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧：侧边栏
        self.sidebar = SidebarWidget(self)
        self.sidebar.route_selected.connect(self._on_route_selected)
        self.sidebar.setFixedWidth(240)
        main_layout.addWidget(self.sidebar)

        # 右侧：工作区
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 顶部工具栏
        self.toolbar = self._create_toolbar()
        right_layout.addWidget(self.toolbar)

        # 工作区（路由容器）
        self.work_area = QStackedWidget()
        right_layout.addWidget(self.work_area, 1)

        main_layout.addWidget(right_widget, 1)

    def _create_toolbar(self) -> QWidget:
        """创建顶部工具栏"""
        toolbar = QFrame()
        toolbar.setFixedHeight(56)
        
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(16)

        # 标题
        self.title_label = QLabel("💬 智能对话")
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #f8f8f2;
            }
        """)
        layout.addWidget(self.title_label)

        layout.addStretch()

        # 主题切换按钮
        self.theme_btn = QPushButton("🎨")
        self.theme_btn.setFixedSize(36, 36)
        self.theme_btn.setStyleSheet("""
            QPushButton {
                background-color: #44475a;
                color: #f8f8f2;
                border: none;
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #6272a4;
            }
        """)
        self.theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_btn)

        # 用户头像/登录按钮
        self.user_btn = QPushButton("👤")
        self.user_btn.setFixedSize(36, 36)
        self.user_btn.setStyleSheet("""
            QPushButton {
                background-color: #44475a;
                color: #f8f8f2;
                border: none;
                border-radius: 50%;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #6272a4;
            }
        """)
        self.user_btn.clicked.connect(self._toggle_user_menu)
        layout.addWidget(self.user_btn)

        return toolbar

    def _register_default_routes(self):
        """注册默认路由"""
        from ..router.routes import register_default_routes
        register_default_routes(self._router)

    def _on_route_selected(self, route_id: str):
        """路由选择回调"""
        panel = self._router.navigate_to(route_id)
        if panel:
            # 检查面板是否已经在工作区中
            existing_index = self.work_area.indexOf(panel)
            if existing_index >= 0:
                self.work_area.setCurrentIndex(existing_index)
            else:
                self.work_area.addWidget(panel)
                self.work_area.setCurrentWidget(panel)

            route = self._router.get_route(route_id)
            if route:
                self.title_label.setText(f"{route.emoji} {route.name}")

    def _on_route_changed(self, route_id: str):
        """路由变化回调"""
        pass

    def _toggle_theme(self):
        """切换主题"""
        themes = ["dracula", "light", "dark"]
        current_index = themes.index(theme_manager.current_theme)
        next_index = (current_index + 1) % len(themes)
        new_theme = themes[next_index]
        
        theme_manager.set_theme(new_theme)
        self._apply_theme()
        
        theme_names = {
            "dracula": "🎨",
            "light": "☀️",
            "dark": "🌙"
        }
        self.theme_btn.setText(theme_names[new_theme])

    def _apply_theme(self):
        """应用主题"""
        # 应用全局样式
        stylesheet = get_dracula_stylesheet()
        self.setStyleSheet(stylesheet)
        
        # 重新应用侧边栏主题
        self.sidebar._apply_theme()

    def _toggle_user_menu(self):
        """切换用户菜单"""
        pass

    def _restore_session(self):
        """恢复会话 - 默认导航到聊天面板"""
        self._on_route_selected("chat")