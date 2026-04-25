"""
布局系统 - 侧边栏

左侧固定栏：显示主模块导航。
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QFrame,
)
from typing import Optional

from ..theme import theme_manager
from ..router import Route


class SidebarWidget(QWidget):
    """
    侧边栏 - 新版

    原有 ModuleBar 有1034行，逻辑混乱。
    新版只负责：显示路由 + 发送选择信号。
    """

    route_selected = pyqtSignal(str)  # route_id
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
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
        header.setFixedHeight(52)
        header.setObjectName("SidebarHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        logo_label = QLabel("🌳")
        logo_label.setStyleSheet("font-size: 22px;")
        header_layout.addWidget(logo_label)

        title_label = QLabel("生命之树")
        title_label.setObjectName("SidebarTitle")
        header_layout.addWidget(title_label)

        layout.addWidget(header)

        # 导航区域（可滚动）
        nav_container = QWidget()
        self._nav_layout = QVBoxLayout(nav_container)
        self._nav_layout.setContentsMargins(8, 8, 8, 8)
        self._nav_layout.setSpacing(2)
        self._nav_layout.addStretch()

        from PyQt6.QtWidgets import QScrollArea
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
        footer.setFixedHeight(52)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 0, 16, 0)

        settings_btn = QPushButton("⚙️ 设置")
        settings_btn.setObjectName("SidebarSettingsBtn")
        settings_btn.clicked.connect(self.settings_requested.emit)
        footer_layout.addWidget(settings_btn)

        layout.addWidget(footer)

    def add_route(self, route: Route):
        """添加路由按钮"""
        btn = QPushButton(f"{route.emoji}  {route.name}")
        btn.setObjectName("SidebarButton")
        btn.setCheckable(True)
        btn.setFixedHeight(40)
        btn.clicked.connect(lambda checked, rid=route.route_id: self._on_button_clicked(rid))

        self._buttons[route.route_id] = btn
        # 插入到倒数第二个位置（在stretch之前）
        self._nav_layout.insertWidget(self._nav_layout.count() - 1, btn)

        # 默认选中第一个
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
        """应用主题"""
        c = theme_manager.colors
        self.setStyleSheet(f"""
            QFrame#SidebarHeader {{
                background: {c.PRIMARY};
                border-bottom: 1px solid {c.BORDER};
            }}
            QLabel#SidebarTitle {{
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton#SidebarButton {{
                background: transparent;
                border: none;
                border-radius: 8px;
                color: {c.TEXT_SECONDARY};
                padding: 8px 12px;
                text-align: left;
                font-size: 13px;
            }}
            QPushButton#SidebarButton:hover {{
                background: {c.BG_TERTIARY};
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
                padding: 8px 12px;
                text-align: left;
                font-size: 13px;
            }}
            QPushButton#SidebarSettingsBtn:hover {{
                background: {c.BG_TERTIARY};
            }}
        """)
