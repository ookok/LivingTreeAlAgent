"""
侧边栏组件 - Dracula 主题版

左侧固定栏：显示所有模块导航（按分类组织）。
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QScrollArea
)
from typing import Optional

from ..theme.theme_manager import theme_manager
from ..router.router import Route


class SidebarWidget(QWidget):
    """
    侧边栏 - Dracula 主题版
    """

    route_selected = pyqtSignal(str)
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        self._categories: dict[str, QWidget] = {}
        self._current_route: Optional[str] = None
        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo + 标题
        header = QFrame()
        header.setFixedHeight(60)
        header.setObjectName("SidebarHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_label = QLabel("🌙")
        logo_label.setStyleSheet("font-size: 26px;")
        header_layout.addWidget(logo_label)

        title_label = QLabel("生命之树")
        title_label.setObjectName("SidebarTitle")
        header_layout.addWidget(title_label)

        layout.addWidget(header)

        # 导航区域（可滚动）
        nav_container = QWidget()
        self._nav_layout = QVBoxLayout(nav_container)
        self._nav_layout.setContentsMargins(8, 8, 8, 8)
        self._nav_layout.setSpacing(4)

        # 分类容器
        self._category_layouts = {}
        self._add_category("main", "核心功能")
        self._add_category("domain", "专业领域")
        self._add_category("tool", "工具")

        self._nav_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(nav_container)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        layout.addWidget(scroll, 1)

        # 底部设置按钮
        footer = QFrame()
        footer.setObjectName("SidebarFooter")
        footer.setFixedHeight(56)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 0, 16, 0)

        settings_btn = QPushButton("⚙️ 设置")
        settings_btn.setObjectName("SidebarSettingsBtn")
        settings_btn.clicked.connect(self.settings_requested.emit)
        footer_layout.addWidget(settings_btn)

        layout.addWidget(footer)

    def _add_category(self, category_id: str, title: str):
        """添加分类区域"""
        title_label = QLabel(title)
        title_label.setObjectName("CategoryTitle")
        title_label.setFixedHeight(36)
        self._nav_layout.addWidget(title_label)

        category_container = QWidget()
        category_layout = QVBoxLayout(category_container)
        category_layout.setContentsMargins(0, 0, 0, 12)
        category_layout.setSpacing(4)

        self._nav_layout.addWidget(category_container)
        self._category_layouts[category_id] = category_layout

    def add_route(self, route: Route):
        """添加路由按钮"""
        btn = QPushButton(f"{route.emoji}  {route.name}")
        btn.setObjectName("SidebarButton")
        btn.setCheckable(True)
        btn.setFixedHeight(44)
        btn.clicked.connect(lambda checked, rid=route.route_id: self._on_button_clicked(rid))

        self._buttons[route.route_id] = btn

        category_layout = self._category_layouts.get(route.category)
        if category_layout:
            category_layout.addWidget(btn)
        else:
            self._nav_layout.addWidget(btn)

        if len(self._buttons) == 1:
            self._on_button_clicked(route.route_id)

    def _on_button_clicked(self, route_id: str):
        """按钮点击"""
        self._set_active(route_id)
        self.route_selected.emit(route_id)

    def _set_active(self, route_id: str):
        """设置激活状态"""
        for rid, btn in self._buttons.items():
            btn.setChecked(rid == route_id)
        self._current_route = route_id

    def _apply_theme(self):
        """应用 Dracula 主题"""
        c = theme_manager.colors
        self.setStyleSheet(f"""
            QFrame#SidebarHeader {{
                background: {c.PRIMARY};
            }}
            QLabel#SidebarTitle {{
                color: {c.BG_MAIN};
                font-size: 16px;
                font-weight: bold;
                margin-left: 8px;
            }}
            QLabel#CategoryTitle {{
                color: {c.TEXT_TERTIARY};
                font-size: 11px;
                font-weight: bold;
                padding: 12px 12px 4px 12px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            QPushButton#SidebarButton {{
                background: transparent;
                border: none;
                border-radius: 8px;
                color: {c.TEXT_SECONDARY};
                padding: 10px 16px;
                text-align: left;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton#SidebarButton:hover {{
                background: {c.BG_TERTIARY};
                color: {c.TEXT_PRIMARY};
            }}
            QPushButton#SidebarButton:checked {{
                background: {c.PRIMARY_LIGHT};
                color: {c.PRIMARY};
                font-weight: bold;
            }}
            QFrame#SidebarFooter {{
                border-top: 1px solid {c.BORDER};
            }}
            QPushButton#SidebarSettingsBtn {{
                background: transparent;
                border: none;
                border-radius: 8px;
                color: {c.TEXT_SECONDARY};
                padding: 10px 16px;
                text-align: left;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton#SidebarSettingsBtn:hover {{
                background: {c.BG_TERTIARY};
                color: {c.TEXT_PRIMARY};
            }}
        """)