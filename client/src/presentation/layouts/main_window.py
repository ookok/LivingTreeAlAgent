"""
布局系统 - 主窗口

新设计：
- 左侧：固定侧边栏（导航）
- 右侧：工作区（路由切换）
- 顶部：全局工具栏（设置、主题切换）
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QFrame, QLabel,
)
from typing import Optional

from ..theme import theme_manager
from ..router import get_router, Router


class MainWindow(QWidget):
    """
    主窗口 - 新版

    原有 main_window.py 有1034行，职责混乱。
    新版只负责：
    1. 布局管理（左侧栏 + 工作区）
    2. 路由注册和切换
    3. 主题切换
    """

    theme_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌳 生命之树 AI - 新版")
        self.resize(1400, 900)

        # 路由管理器
        self._router: Router = get_router()
        self._router.set_parent(self)
        self._router.route_changed.connect(self._on_route_changed)

        self._setup_ui()
        self._register_default_routes()

        # 应用主题
        self._apply_theme()

    def _setup_ui(self):
        """构建UI"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧：侧边栏
        self.sidebar = SidebarWidget(self)
        self.sidebar.route_selected.connect(self._on_route_selected)
        self.sidebar.setFixedWidth(220)
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
        toolbar.setFixedHeight(52)
        toolbar.setObjectName("Toolbar")

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # 当前模块标题
        self.title_label = QLabel("💬 聊天")
        self.title_label.setObjectName("ToolbarTitle")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # 主题切换按钮
        from ..components.buttons import IconButton
        self.theme_btn = IconButton("🌙" if theme_manager.current_theme == "light" else "☀️")
        self.theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_btn)

        return toolbar

    def _register_default_routes(self):
        """注册默认路由"""
        from .routes import register_default_routes
        register_default_routes(self._router)

        # 注册主模块到侧边栏
        main_routes = self._router.get_routes_by_category("main")
        for route in main_routes:
            self.sidebar.add_route(route)

    def _on_route_selected(self, route_id: str):
        """路由选择回调"""
        panel = self._router.navigate_to(route_id)
        if panel:
            # 切换到对应面板
            self.work_area.addWidget(panel)
            self.work_area.setCurrentWidget(panel)

            # 更新标题
            route = self._router.get_route(route_id)
            if route:
                self.title_label.setText(f"{route.emoji} {route.name}")

    def _on_route_changed(self, route_id: str):
        """路由变化回调"""
        pass

    def _toggle_theme(self):
        """切换主题"""
        new_theme = "dark" if theme_manager.current_theme == "light" else "light"
        theme_manager.set_theme(new_theme)
        self._apply_theme()

        # 更新按钮图标
        self.theme_btn.setText("🌙" if new_theme == "light" else "☀️")

    def _apply_theme(self):
        """应用主题到窗口"""
        c = theme_manager.colors
        self.setStyleSheet(f"""
            QWidget {{
                background: {c.BG_MAIN};
                color: {c.TEXT_PRIMARY};
            }}
            QFrame#Toolbar {{
                background: {c.BG_SECONDARY};
                border-bottom: 1px solid {c.BORDER};
            }}
            QLabel#ToolbarTitle {{
                font-size: 15px;
                font-weight: bold;
                color: {c.TEXT_PRIMARY};
            }}
        """)
