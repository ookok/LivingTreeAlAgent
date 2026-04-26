"""
主窗口 V2 - 带登录/登出功能

新增功能：
1. 顶部工具栏显示登录状态
2. 未登录时显示登录按钮
3. 登录后显示用户头像和登出按钮
4. 集成登录对话框
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QFrame, QLabel, QPushButton,
    QMenu
)
from PyQt6.QtGui import QPixmap, QAction
from typing import Optional

from ..theme import theme_manager
from ..router import get_router, Router
from .sidebar import SidebarWidget

# 导入认证系统
from client.src.business.auth_system import AuthSystem, UserProfile


class MainWindow(QWidget):
    """
    主窗口 V2 - 带登录功能
    
    功能：
    1. 布局管理（左侧栏 + 工作区）
    2. 路由注册和切换
    3. 主题切换
    4. 用户登录/登出
    5. 登录状态显示
    """

    theme_changed = pyqtSignal(str)
    login_status_changed = pyqtSignal(bool, object)  # logged_in, user

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌳 生命之树 AI")
        self.resize(1400, 900)

        # 认证系统
        self.auth_system = AuthSystem()
        self.current_user: Optional[UserProfile] = None

        # 路由管理器
        self._router: Router = get_router()
        self._router.set_parent(self)
        self._router.route_changed.connect(self._on_route_changed)

        self._setup_ui()
        self._register_default_routes()
        self._apply_theme()

        # 检查是否已登录（从保存的会话恢复）
        self._restore_session()

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

        # 用户区域（登录/用户信息）
        self.user_widget = self._create_user_widget()
        layout.addWidget(self.user_widget)

        # 主题切换按钮
        from ..components.buttons import IconButton
        self.theme_btn = IconButton("🌙" if theme_manager.current_theme == "light" else "☀️")
        self.theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_btn)

        return toolbar

    def _create_user_widget(self) -> QWidget:
        """创建用户组件（登录按钮或用户信息）"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 登录按钮（未登录时显示）
        self.login_btn = QPushButton("👤 登录")
        self.login_btn.setObjectName("LoginButton")
        self.login_btn.clicked.connect(self._show_login_dialog)
        layout.addWidget(self.login_btn)

        # 用户信息（登录后显示）
        self.user_info_widget = QWidget()
        user_layout = QHBoxLayout(self.user_info_widget)
        user_layout.setContentsMargins(0, 0, 0, 0)
        user_layout.setSpacing(8)

        # 用户头像
        self.avatar_label = QLabel("👤")
        self.avatar_label.setObjectName("UserAvatar")
        self.avatar_label.setFixedSize(32, 32)
        user_layout.addWidget(self.avatar_label)

        # 用户名
        self.username_label = QLabel()
        self.username_label.setObjectName("UsernameLabel")
        user_layout.addWidget(self.username_label)

        # 下拉菜单按钮
        self.user_menu_btn = QPushButton("▼")
        self.user_menu_btn.setObjectName("UserMenuButton")
        self.user_menu_btn.setFixedSize(24, 24)
        self.user_menu_btn.clicked.connect(self._show_user_menu)
        user_layout.addWidget(self.user_menu_btn)

        self.user_info_widget.setVisible(False)
        layout.addWidget(self.user_info_widget)

        return widget

    def _show_login_dialog(self):
        """显示登录对话框"""
        from ..dialogs.auth_dialog import LoginDialog
        dialog = LoginDialog(self)
        dialog.login_success.connect(self._on_login_success)
        dialog.exec()

    def _on_login_success(self, user_data: dict):
        """登录成功回调"""
        # 获取完整用户信息
        user = self.auth_system.current_user
        if user:
            self.current_user = user
            self._update_user_display()
            self.login_status_changed.emit(True, user)

    def _update_user_display(self):
        """更新用户显示"""
        if self.current_user:
            # 隐藏登录按钮，显示用户信息
            self.login_btn.setVisible(False)
            self.user_info_widget.setVisible(True)

            # 更新用户名
            display_name = self.current_user.display_name or self.current_user.username
            self.username_label.setText(display_name)

            # 更新头像（如果有）
            if self.current_user.avatar:
                try:
                    pixmap = QPixmap(self.current_user.avatar)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(
                            32, 32,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.avatar_label.setPixmap(scaled)
                except Exception:
                    self.avatar_label.setText("👤")
        else:
            # 显示登录按钮，隐藏用户信息
            self.login_btn.setVisible(True)
            self.user_info_widget.setVisible(False)

    def _show_user_menu(self):
        """显示用户菜单"""
        menu = QMenu(self)

        # 个人资料
        profile_action = QAction("👤 个人资料", self)
        profile_action.triggered.connect(self._show_profile)
        menu.addAction(profile_action)

        # 设置
        settings_action = QAction("⚙️ 设置", self)
        settings_action.triggered.connect(self._show_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        # 登出
        logout_action = QAction("🚪 登出", self)
        logout_action.triggered.connect(self._logout)
        menu.addAction(logout_action)

        # 显示菜单
        menu.exec(
            self.user_menu_btn.mapToGlobal(
                self.user_menu_btn.rect().bottomLeft()
            )
        )

    def _show_profile(self):
        """显示个人资料"""
        # TODO: 打开个人资料面板
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "个人资料",
            f"用户名: {self.current_user.username}\n"
            f"邮箱: {self.current_user.email}\n"
            f"角色: {self.current_user.role.value}"
        )

    def _show_settings(self):
        """显示设置"""
        self.sidebar.settings_requested.emit()

    def _logout(self):
        """用户登出"""
        self.auth_system.logout()
        self.current_user = None
        self._update_user_display()
        self.login_status_changed.emit(False, None)

        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "提示", "已登出")

    def _restore_session(self):
        """恢复会话（自动登录）"""
        # TODO: 从保存的token恢复登录状态
        # 目前每次启动都需要重新登录
        pass

    def _register_default_routes(self):
        """注册默认路由"""
        from .routes import register_default_routes
        register_default_routes(self._router)

        # 注册所有类别的路由到侧边栏
        categories = ["main", "domain", "tool"]
        for category in categories:
            routes = self._router.get_routes_by_category(category)
            for route in routes:
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
            QPushButton#LoginButton {{
                background: {c.PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 6px 16px;
                font-size: 13px;
            }}
            QPushButton#LoginButton:hover {{
                background: {c.PRIMARY_LIGHT};
            }}
            QLabel#UserAvatar {{
                background: {c.BG_TERTIARY};
                border-radius: 16px;
                font-size: 18px;
                qproperty-alignment: AlignCenter;
            }}
            QLabel#UsernameLabel {{
                font-size: 13px;
                color: {c.TEXT_PRIMARY};
            }}
            QPushButton#UserMenuButton {{
                background: transparent;
                border: none;
                color: {c.TEXT_SECONDARY};
                font-size: 10px;
            }}
            QPushButton#UserMenuButton:hover {{
                color: {c.TEXT_PRIMARY};
            }}
        """)
