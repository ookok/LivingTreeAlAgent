"""
主题系统 - Theme System

三层结构：
1. 全局主题 - 主框架控制的基础主题
2. 插件级主题 - 插件可自定义的样式
3. 用户级覆盖 - 用户自定义CSS

设计理念：
- 主题可叠加、可继承
- 插件可以声明自己的样式
- 用户可以覆盖任何级别
"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor


class ThemeLevel(Enum):
    """主题层级"""
    GLOBAL = "global"        # 全局主题
    PLUGIN = "plugin"       # 插件级
    USER = "user"          # 用户级覆盖


@dataclass
class ThemeColors:
    """主题颜色定义"""
    # 基础色
    primary: str = "#5a5aff"       # 主色（按钮、链接等）
    secondary: str = "#8080ff"     # 次色
    accent: str = "#00d4aa"        # 强调色
    background: str = "#1a1a1a"   # 主背景
    surface: str = "#252525"       # 卡片/面板背景
    border: str = "#333333"        # 边框
    text_primary: str = "#e8e8e8"  # 主文本
    text_secondary: str = "#a0a0a0"  # 次文本
    disabled: str = "#555555"      # 禁用状态

    # 语义色
    success: str = "#4caf50"       # 成功
    warning: str = "#ff9800"       # 警告
    error: str = "#f44336"         # 错误
    info: str = "#2196f3"         # 信息

    # 状态色
    hover: str = "#303030"         # 悬停
    active: str = "#404040"        # 激活
    selected: str = "#252550"      # 选中


@dataclass
class Theme:
    """主题定义"""
    id: str
    name: str
    colors: ThemeColors = field(default_factory=ThemeColors)
    is_dark: bool = True
    css_template: str = ""
    parent_theme: Optional[str] = None  # 父主题ID（用于继承）

    def to_css(self, level: ThemeLevel = ThemeLevel.GLOBAL) -> str:
        """生成完整的CSS"""
        prefix = f"/* {self.name} - {level.value} */\n"

        base_css = self.css_template or self._get_default_css()
        return prefix + base_css

    def _get_default_css(self) -> str:
        """获取默认CSS模板"""
        c = self.colors
        return f"""
/* ═══════════════════════════════════════════════════════════════
   {self.name} 主题
═══════════════════════════════════════════════════════════════ */

* {{
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 13px;
}}

QMainWindow, QWidget {{
    background-color: {c.background};
    color: {c.text_primary};
}}

/* 按钮样式 */
QPushButton {{
    background-color: {c.primary};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    min-width: 60px;
}}
QPushButton:hover {{ background-color: {c.hover}; }}
QPushButton:pressed {{ background-color: {c.active}; }}
QPushButton:disabled {{ background-color: {c.disabled}; color: {c.text_secondary}; }}

/* 输入框样式 */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {c.surface};
    color: {c.text_primary};
    border: 1px solid {c.border};
    border-radius: 4px;
    padding: 6px;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c.primary};
}}

/* 滚动条样式 */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c.border};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {c.text_secondary}; }}
QScrollBar:add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {c.border};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{ background: {c.text_secondary}; }}

/* 标签页样式 */
QTabWidget::pane {{
    border: 1px solid {c.border};
    background-color: {c.background};
}}
QTabBar::tab {{
    background-color: {c.surface};
    color: {c.text_secondary};
    padding: 8px 16px;
    border: 1px solid {c.border};
    border-bottom: none;
}}
QTabBar::tab:selected {{
    background-color: {c.primary};
    color: white;
}}
QTabBar::tab:hover {{ background-color: {c.hover}; }}

/* 停靠窗口样式 */
QDockWidget {{
    titlebar-normal-color: {c.surface};
    titlebar-active-color: {c.primary};
}}
QDockWidget::title {{
    background-color: {c.surface};
    padding: 4px;
    border: 1px solid {c.border};
}}

/* 菜单样式 */
QMenu {{
    background-color: {c.surface};
    border: 1px solid {c.border};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px;
    border-radius: 2px;
}}
QMenu::item:selected {{ background-color: {c.primary}; }}

/* 工具栏样式 */
QToolBar {{
    background-color: {c.surface};
    border: none;
    spacing: 4px;
    padding: 4px;
}}
QToolBar::separator {{
    background-color: {c.border};
    width: 1px;
    margin: 4px;
}}

/* 树形视图样式 */
QTreeWidget, QTreeView {{
    background-color: {c.background};
    border: 1px solid {c.border};
    outline: none;
}}
QTreeWidget::item:hover, QTreeView::item:hover {{
    background-color: {c.hover};
}}
QTreeWidget::item:selected, QTreeView::item:selected {{
    background-color: {c.selected};
    color: white;
}}

/* 列表样式 */
QListWidget, QListView {{
    background-color: {c.background};
    border: 1px solid {c.border};
    outline: none;
}}
QListWidget::item:hover, QListView::item:hover {{
    background-color: {c.hover};
}}
QListWidget::item:selected, QListView::item:selected {{
    background-color: {c.selected};
    color: white;
}}

/* 表格样式 */
QTableWidget, QTableView {{
    background-color: {c.background};
    border: 1px solid {c.border};
    gridline-color: {c.border};
}}
QHeaderView::section {{
    background-color: {c.surface};
    color: {c.text_primary};
    padding: 6px;
    border: 1px solid {c.border};
}}

/* 消息提示 */
QToolTip {{
    background-color: {c.surface};
    color: {c.text_primary};
    border: 1px solid {c.border};
    padding: 4px;
}}

/* 状态栏 */
QStatusBar {{
    background-color: {c.surface};
    color: {c.text_secondary};
}}
"""


class ThemeSystem(QObject):
    """
    主题系统

    管理全局主题、插件主题和用户覆盖

    使用示例：
        theme_system = ThemeSystem()

        # 注册主题
        theme_system.register_theme(Theme(id="dark", name="深色主题"))

        # 应用主题
        theme_system.apply_theme("dark")

        # 插件注册自己的样式
        theme_system.register_plugin_css("my_plugin", "/* plugin CSS */")

        # 用户覆盖
        theme_system.set_user_override("QPushButton { min-width: 80px; }")
    """

    # 信号定义
    theme_changed = pyqtSignal(str)  # theme_id
    stylesheet_changed = pyqtSignal(str)  # stylesheet

    def __init__(self):
        super().__init__()
        self._themes: Dict[str, Theme] = {}
        self._current_theme_id: Optional[str] = None
        self._plugin_css: Dict[str, str] = {}
        self._user_overrides: List[str] = []
        self._combined_css: str = ""
        self._app: Optional[QApplication] = None

        # 注册默认主题
        self._register_default_themes()

    def _register_default_themes(self) -> None:
        """注册默认主题"""
        # 深色主题（默认）
        dark_theme = Theme(
            id="dark",
            name="深色主题",
            colors=ThemeColors(
                primary="#5a5aff",
                secondary="#8080ff",
                accent="#00d4aa",
                background="#1a1a1a",
                surface="#252525",
                border="#333333",
                text_primary="#e8e8e8",
                text_secondary="#a0a0a0",
                disabled="#555555",
                success="#4caf50",
                warning="#ff9800",
                error="#f44336",
                info="#2196f3",
                hover="#303030",
                active="#404040",
                selected="#252550",
            ),
            is_dark=True,
        )
        self.register_theme(dark_theme)

        # 浅色主题
        light_theme = Theme(
            id="light",
            name="浅色主题",
            colors=ThemeColors(
                primary="#5a5aff",
                secondary="#8080ff",
                accent="#00d4aa",
                background="#ffffff",
                surface="#f5f5f5",
                border="#e0e0e0",
                text_primary="#333333",
                text_secondary="#666666",
                disabled="#cccccc",
                success="#4caf50",
                warning="#ff9800",
                error="#f44336",
                info="#2196f3",
                hover="#eeeeee",
                active="#e0e0e0",
                selected="#e8e8f0",
            ),
            is_dark=False,
        )
        self.register_theme(light_theme)

        # 设置默认主题为浅色
        self._current_theme_id = "light"

    def set_app(self, app: QApplication) -> None:
        """设置QApplication实例"""
        self._app = app

    def register_theme(self, theme: Theme) -> None:
        """
        注册主题

        Args:
            theme: 主题对象
        """
        self._themes[theme.id] = theme

    def unregister_theme(self, theme_id: str) -> bool:
        """
        注销主题

        Args:
            theme_id: 主题ID

        Returns:
            是否成功
        """
        if theme_id == self._current_theme_id:
            return False  # 不能注销当前主题
        if theme_id in self._themes:
            del self._themes[theme_id]
            return True
        return False

    def get_theme(self, theme_id: str) -> Optional[Theme]:
        """获取主题"""
        return self._themes.get(theme_id)

    def get_current_theme(self) -> Optional[Theme]:
        """获取当前主题"""
        if self._current_theme_id:
            return self._themes.get(self._current_theme_id)
        return None

    def apply_theme(self, theme_id: str) -> bool:
        """
        应用主题

        Args:
            theme_id: 主题ID

        Returns:
            是否成功
        """
        if theme_id not in self._themes:
            return False

        self._current_theme_id = theme_id
        self._rebuild_stylesheet()
        self.theme_changed.emit(theme_id)
        return True

    def register_plugin_css(self, plugin_id: str, css: str) -> None:
        """
        注册插件CSS

        Args:
            plugin_id: 插件ID
            css: CSS字符串
        """
        self._plugin_css[plugin_id] = css
        self._rebuild_stylesheet()

    def unregister_plugin_css(self, plugin_id: str) -> None:
        """
        注销插件CSS

        Args:
            plugin_id: 插件ID
        """
        if plugin_id in self._plugin_css:
            del self._plugin_css[plugin_id]
            self._rebuild_stylesheet()

    def set_user_override(self, css: str) -> None:
        """
        设置用户覆盖样式

        Args:
            css: CSS字符串
        """
        self._user_overrides.append(css)
        self._rebuild_stylesheet()

    def clear_user_overrides(self) -> None:
        """清空用户覆盖"""
        self._user_overrides.clear()
        self._rebuild_stylesheet()

    def _rebuild_stylesheet(self) -> None:
        """重新构建完整样式表"""
        parts = []

        # 1. 全局主题
        theme = self.get_current_theme()
        if theme:
            parts.append(theme.to_css(ThemeLevel.GLOBAL))

        # 2. 插件级样式
        for plugin_id, css in self._plugin_css.items():
            parts.append(f"/* Plugin: {plugin_id} */\n{css}")

        # 3. 用户覆盖
        if self._user_overrides:
            parts.append("/* User Overrides */\n" + "\n".join(self._user_overrides))

        self._combined_css = "\n\n".join(parts)

        # 应用到应用
        if self._app:
            self._app.setStyleSheet(self._combined_css)

        self.stylesheet_changed.emit(self._combined_css)

    def get_stylesheet(self) -> str:
        """获取完整样式表"""
        return self._combined_css

    def get_available_themes(self) -> List[Theme]:
        """获取所有可用主题"""
        return list(self._themes.values())

    def save_user_preferences(self) -> Dict[str, Any]:
        """保存用户偏好"""
        return {
            "current_theme": self._current_theme_id,
            "user_overrides": self._user_overrides,
        }

    def load_user_preferences(self, data: Dict[str, Any]) -> None:
        """加载用户偏好"""
        if "current_theme" in data:
            self.apply_theme(data["current_theme"])
        if "user_overrides" in data:
            self._user_overrides = data["user_overrides"]
            self._rebuild_stylesheet()


# 全局单例
_theme_system_instance: Optional[ThemeSystem] = None


def get_theme_system() -> ThemeSystem:
    """获取主题系统单例"""
    global _theme_system_instance
    if _theme_system_instance is None:
        _theme_system_instance = ThemeSystem()
    return _theme_system_instance
