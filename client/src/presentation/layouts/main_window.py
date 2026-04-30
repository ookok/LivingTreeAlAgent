"""
主窗口 - 使用 Dracula 主题

基于 Dracula UI 框架的现代化客户端界面。
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
from ..router.router import get_router, Router
from .sidebar import SidebarWidget

# 导入认证系统
from business.auth_system import AuthSystem, UserProfile


class MainWindow(QWidget):
    """
    主窗口 - Dracula 主题版
    
    功能：
    1. 布局管理（左侧栏 + 工作区）
    2. 路由注册和切换
    3. 主题切换
    4. 用户登录/登出
    5. 登录状态显示
    """

    theme_changed = pyqtSignal(str)
    login_status_changed = pyqtSignal(bool, object)

    def __init__(self, parent=None):
        print("  MainWindow: Initializing...")
        super().__init__(parent)
        self.setWindowTitle("🌙 生命之树 AI")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 600)

        # 认证系统
        print("  MainWindow: Creating AuthSystem...")
        self.auth_system = AuthSystem()
        self.current_user: Optional[UserProfile] = None

        # 路由管理器
        print("  MainWindow: Getting router...")
        self._router: Router = get_router()
        self._router.set_parent(self)
        self._router.register_route_changed_listener(self._on_route_changed)

        print("  MainWindow: Setting up UI...")
        self._setup_ui()
        
        print("  MainWindow: Registering routes...")
        self._register_default_routes()
        
        print("  MainWindow: Applying theme...")
        self._apply_theme()

        # 检查是否已登录
        print("  MainWindow: Restoring session...")
        self._restore_session()
        
        print("  MainWindow: Initialized!")

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
        self.work_area.setObjectName("WorkArea")
        right_layout.addWidget(self.work_area, 1)

        main_layout.addWidget(right_widget, 1)

    def _create_toolbar(self) -> QWidget:
        """创建顶部工具栏 - Dracula 风格"""
        toolbar = QFrame()
        toolbar.setFixedHeight(56)
        toolbar.setObjectName("Toolbar")

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(16)

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
        self.theme_btn = QPushButton("🎨")
        self.theme_btn.setObjectName("ThemeButton")
        self.theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_btn)

        return toolbar

    def _create_user_widget(self) -> QWidget:
        """创建用户组件"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

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
        self.avatar_label.setFixedSize(36, 36)
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
        user = self.auth_system.current_user
        if user:
            self.current_user = user
            self._update_user_display()
            self.login_status_changed.emit(True, user)

    def _update_user_display(self):
        """更新用户显示"""
        if self.current_user:
            self.login_btn.setVisible(False)
            self.user_info_widget.setVisible(True)

            display_name = self.current_user.display_name or self.current_user.username
            self.username_label.setText(display_name)

            if self.current_user.avatar:
                try:
                    pixmap = QPixmap(self.current_user.avatar)
                    if not pixmap.isNull():
                        scaled = pixmap.scaled(
                            36, 36,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.avatar_label.setPixmap(scaled)
                except Exception:
                    self.avatar_label.setText("👤")
        else:
            self.login_btn.setVisible(True)
            self.user_info_widget.setVisible(False)

    def _show_user_menu(self):
        """显示用户菜单"""
        menu = QMenu(self)

        profile_action = QAction("👤 个人资料", self)
        profile_action.triggered.connect(self._show_profile)
        menu.addAction(profile_action)

        settings_action = QAction("⚙️ 设置", self)
        settings_action.triggered.connect(self._show_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        logout_action = QAction("🚪 登出", self)
        logout_action.triggered.connect(self._logout)
        menu.addAction(logout_action)

        menu.exec(
            self.user_menu_btn.mapToGlobal(
                self.user_menu_btn.rect().bottomLeft()
            )
        )

    def _show_profile(self):
        """显示个人资料"""
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
        """恢复会话 - 默认导航到聊天面板"""
        # 默认导航到聊天面板
        self._on_route_selected("chat")

    def _register_default_routes(self):
        """注册默认路由"""
        from ..router.routes import register_default_routes
        register_default_routes(self._router)

        categories = ["main", "domain", "tool"]
        for category in categories:
            routes = self._router.get_routes_by_category(category)
            for route in routes:
                self.sidebar.add_route(route)

    def _on_route_selected(self, route_id: str):
        """路由选择回调"""
        print(f"  MainWindow: Navigating to route: {route_id}")
        panel = self._router.navigate_to(route_id)
        
        if panel:
            print(f"  MainWindow: Panel found: {type(panel).__name__}")
            
            # 检查面板是否已经在工作区中
            existing_index = self.work_area.indexOf(panel)
            if existing_index >= 0:
                print(f"  MainWindow: Panel already in work area at index {existing_index}")
                self.work_area.setCurrentIndex(existing_index)
            else:
                print(f"  MainWindow: Adding panel to work area...")
                self.work_area.addWidget(panel)
                self.work_area.setCurrentWidget(panel)
                print(f"  MainWindow: Panel added successfully")

            route = self._router.get_route(route_id)
            if route:
                self.title_label.setText(f"{route.emoji} {route.name}")
                print(f"  MainWindow: Title updated to: {route.emoji} {route.name}")
        else:
            print(f"  MainWindow: Panel not found for route: {route_id}")

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
        """应用 Dracula 主题 - 添加错误处理"""
        try:
            stylesheet = theme_manager.get_stylesheet()
            # 验证样式表语法
            self.setStyleSheet(stylesheet)
            print("  MainWindow: Theme applied successfully")
        except Exception as e:
            print(f"  MainWindow: Failed to apply theme: {e}")
            # 使用简化的样式表作为后备
            fallback_stylesheet = """
                QWidget {
                    background-color: #282a36;
                    color: #f8f8f2;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                    font-size: 14px;
                }
                QPushButton {
                    background-color: #44475a;
                    border: 2px solid #44475a;
                    border-radius: 8px;
                    color: #f8f8f2;
                    padding: 10px 20px;
                }
                QPushButton:hover {
                    background-color: #343746;
                    border-color: #bd93f9;
                }
                QLineEdit, QTextEdit {
                    background-color: #44475a;
                    border: 2px solid #44475a;
                    border-radius: 8px;
                    padding: 12px 16px;
                    color: #f8f8f2;
                }
            """
            self.setStyleSheet(fallback_stylesheet)