"""
AIDock - 悬浮助手

始终置顶的悬浮按钮，类似 macOS Siri 或 Windows Copilot。
支持拖拽定位、点击展开快捷指令面板、多主题切换。

设计理念：
1. 始终置顶：Qt.Tool | Qt.FramelessWindowHint
2. 可拖拽移动：鼠标事件重写
3. 快捷指令：点击展开面板，显示常用意图
4. 多主题：浅色/深色/自动（跟随系统）
"""

import sys
import os
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QSystemTrayIcon, QMenu, QAction,
)
from PyQt6.QtCore import (
    Qt, QPoint, QSize, QTimer, pyqtSignal, QPropertyAnimation,
    QEasingCurve, QRect,
)
from PyQt6.QtGui import QIcon, QFont, QAction as QGuiAction, QFontMetrics

# 尝试导入 QPixmap（用于图标）
try:
    from PyQt6.QtGui import QPixmap
    HAS_PIXMAP = True
except ImportError:
    HAS_PIXMAP = False


# ──────────────────────────────────────────────────────────────
# 主题管理
# ──────────────────────────────────────────────────────────────


class AIDockTheme:
    """AIDock 主题"""

    LIGHT = {
        "name": "浅色",
        "button_bg": "rgba(240, 240, 240, 220)",
        "button_border": "rgba(200, 200, 200, 200)",
        "button_hover": "rgba(220, 220, 220, 250)",
        "panel_bg": "rgba(255, 255, 255, 240)",
        "panel_border": "rgba(200, 200, 200, 200)",
        "text_color": "#333333",
        "text_secondary": "#666666",
        "accent": "#007AFF",
        "accent_hover": "#0056CC",
    }

    DARK = {
        "name": "深色",
        "button_bg": "rgba(50, 50, 50, 220)",
        "button_border": "rgba(80, 80, 80, 200)",
        "button_hover": "rgba(70, 70, 70, 250)",
        "panel_bg": "rgba(40, 40, 40, 240)",
        "panel_border": "rgba(80, 80, 80, 200)",
        "text_color": "#EEEEEE",
        "text_secondary": "#AAAAAA",
        "accent": "#0A84FF",
        "accent_hover": "#409CFF",
    }

    AUTO = "auto"  # 跟随系统


class ThemeManager:
    """主题管理器（单例）"""

    _instance: Optional['ThemeManager'] = None
    _initialized: bool = False

    def __init__(self):
        if ThemeManager._initialized:
            return
        self._current_theme = AIDockTheme.LIGHT
        self._listeners: List[Callable[[Dict], None]] = []
        ThemeManager._initialized = True

    @classmethod
    def get_instance(cls) -> 'ThemeManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_theme(self) -> Dict:
        return self._current_theme

    def set_theme(self, theme: Any) -> None:
        if theme == "auto":
            # 检测系统主题（简化：默认浅色）
            import traceback
            try:
                # Windows：检查注册表
                if sys.platform == "win32":
                    import winreg
                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                    )
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    self._current_theme = AIDockTheme.LIGHT if value == 1 else AIDockTheme.DARK
                # macOS：检查暗黑模式
                elif sys.platform == "darwin":
                    import subprocess
                    result = subprocess.run(
                        ["defaults", "read", "-g", "AppleInterfaceStyle"],
                        capture_output=True, text=True
                    )
                    self._current_theme = AIDockTheme.DARK if "Dark" in result.stdout else AIDockTheme.LIGHT
                else:
                    self._current_theme = AIDockTheme.LIGHT
            except Exception:
                self._current_theme = AIDockTheme.LIGHT
        elif theme == AIDockTheme.LIGHT:
            self._current_theme = AIDockTheme.LIGHT
        elif theme == AIDockTheme.DARK:
            self._current_theme = AIDockTheme.DARK
        else:
            self._current_theme = AIDockTheme.LIGHT

        # 通知监听器
        for listener in self._listeners:
            try:
                listener(self._current_theme)
            except Exception:
                pass

    def add_listener(self, listener: Callable[[Dict], None]) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[Dict], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)


# ──────────────────────────────────────────────────────────────
# 悬浮按钮
# ──────────────────────────────────────────────────────────────


class AIDockButton(QPushButton):
    """悬浮按钮（圆形/椭圆形）"""

    # 信号
    clicked_expand = pyqtSignal()  # 点击展开
    drag_finished = pyqtSignal(QPoint)  # 拖拽完成

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(60, 60)
        self._is_dragging = False
        self._drag_start_pos = QPoint()
        self._window_start_pos = QPoint()
        self._theme = AIDockTheme.LIGHT

        # 初始化 UI
        self._init_ui()

    def _init_ui(self) -> None:
        """初始化 UI"""
        self.setText("AI")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 字体
        font = QFont("Arial", 16, QFont.Weight.Bold)
        self.setFont(font)

        # 应用样式
        self._apply_theme()

    def _apply_theme(self) -> None:
        """应用主题"""
        style = f"""
            QPushButton {{
                background-color: {self._theme["button_bg"]};
                border: 2px solid {self._theme["button_border"]};
                border-radius: 30px;
                color: {self._theme["accent"]};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self._theme["button_hover"]};
            }}
            QPushButton:pressed {{
                background-color: {self._theme["accent"]};
                color: white;
            }}
        """
        self.setStyleSheet(style)

    def set_theme(self, theme: Dict) -> None:
        """设置主题"""
        self._theme = theme
        self._apply_theme()

    def mousePressEvent(self, event) -> None:
        """鼠标按下事件（开始拖拽）"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = event.globalPosition().toPoint()
            self._window_start_pos = self.window().pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """鼠标移动事件（拖拽中）"""
        if self._is_dragging:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            new_pos = self._window_start_pos + delta
            self.window().move(new_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """鼠标释放事件（结束拖拽 / 点击）"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_dragging:
                # 判断是否真的是拖拽（移动距离 > 5px）
                delta = event.globalPosition().toPoint() - self._drag_start_pos
                if delta.manhattanLength() > 5:
                    self.drag_finished.emit(self.window().pos())
                else:
                    # 点击（不是拖拽）
                    self.clicked_expand.emit()
            self._is_dragging = False
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        """鼠标进入事件（悬停效果）"""
        # 可以放大动画
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """鼠标离开事件"""
        super().leaveEvent(event)


# ──────────────────────────────────────────────────────────────
# 快捷指令面板
# ──────────────────────────────────────────────────────────────


class ShortcutPanel(QWidget):
    """快捷指令面板"""

    # 信号
    shortcut_selected = pyqtSignal(str)  # 选中了某个快捷指令

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme = AIDockTheme.LIGHT
        self._shortcuts: List[Dict[str, Any]] = []
        self._init_ui()
        self._load_default_shortcuts()

    def _init_ui(self) -> None:
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 标题
        title = QLabel("快捷指令")
        title.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {self._theme['text_color']};")
        layout.addWidget(title)

        # 快捷指令列表
        self._list_widget = QListWidget()
        self._list_widget.setStyleSheet(self._get_list_style())
        self._list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list_widget)

        # 底部按钮栏
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)

        self._settings_btn = QPushButton("设置")
        self._settings_btn.setFixedSize(60, 28)
        self._settings_btn.setStyleSheet(self._get_button_style())

        button_layout.addWidget(self._settings_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.setFixedSize(280, 400)

    def _get_list_style(self) -> str:
        """获取列表样式"""
        return f"""
            QListWidget {{
                background-color: transparent;
                border: none;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                border-radius: 6px;
                color: {self._theme["text_color"]};
            }}
            QListWidget::item:hover {{
                background-color: {self._theme["accent"]}20;
            }}
            QListWidget::item:selected {{
                background-color: {self._theme["accent"]};
                color: white;
            }}
        """

    def _get_button_style(self) -> str:
        """获取按钮样式"""
        return f"""
            QPushButton {{
                background-color: {self._theme["button_bg"]};
                border: 1px solid {self._theme["button_border"]};
                border-radius: 4px;
                color: {self._theme["text_color"]};
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {self._theme["button_hover"]};
            }}
        """

    def _load_default_shortcuts(self) -> None:
        """加载默认快捷指令"""
        defaults = [
            {"title": "💬 聊天对话", "intent": "打开聊天"},
            {"title": "✍️ 智能写作", "intent": "打开智能写作"},
            {"title": "🔍 深度搜索", "intent": "打开深度搜索"},
            {"title": "📝 代码生成", "intent": "帮我写代码"},
            {"title": "🐛 调试代码", "intent": "帮我调试代码"},
            {"title": "📊 知识查询", "intent": "查询知识库"},
            {"title": "🎨 生成图片", "intent": "生成图片"},
            {"title": "📊 数据分析", "intent": "分析数据"},
        ]
        self.set_shortcuts(defaults)

    def set_shortcuts(self, shortcuts: List[Dict[str, Any]]) -> None:
        """
        设置快捷指令

        Args:
            shortcuts: [{"title": "xxx", "intent": "xxx"}, ...]
        """
        self._shortcuts = shortcuts
        self._list_widget.clear()

        for shortcut in shortcuts:
            item = QListWidgetItem(shortcut["title"])
            item.setData(1000, shortcut["intent"])  # 1000 = Qt.UserRole
            self._list_widget.addItem(item)

    def add_shortcut(self, title: str, intent: str) -> None:
        """添加快捷指令"""
        self._shortcuts.append({"title": title, "intent": intent})
        item = QListWidgetItem(title)
        item.setData(1000, intent)
        self._list_widget.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """点击快捷指令"""
        intent = item.data(1000)
        if intent:
            self.shortcut_selected.emit(intent)

    def set_theme(self, theme: Dict) -> None:
        """设置主题"""
        self._theme = theme
        self._apply_theme()

    def _apply_theme(self) -> None:
        """应用主题"""
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {self._theme["panel_bg"]};
                border: 1px solid {self._theme["panel_border"]};
                border-radius: 12px;
            }}
            QLabel {{
                color: {self._theme["text_color"]};
            }}
        """)
        self._list_widget.setStyleSheet(self._get_list_style())
        self._settings_btn.setStyleSheet(self._get_button_style())


# ──────────────────────────────────────────────────────────────
# 主悬浮窗口
# ──────────────────────────────────────────────────────────────


class AIDockWidget(QWidget):
    """
    悬浮助手主窗口

    使用示例：
        dock = AIDockWidget()
        dock.show()

        # 设置主题
        dock.set_theme(AIDockTheme.DARK)

        # 添加快捷指令
        dock.add_shortcut("生成代码", "帮我写代码")

        # 监听快捷指令
        dock.shortcut_selected.connect(lambda intent: print(f"Selected: {intent}"))
    """

    # 信号
    shortcut_selected = pyqtSignal(str)  # 选中了某个快捷指令
    position_changed = pyqtSignal(QPoint)  # 位置改变

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme = AIDockTheme.LIGHT
        self._is_expanded = False
        self._init_window()
        self._init_ui()
        self._init_tray()
        self._init_animations()

    def _init_window(self) -> None:
        """初始化窗口属性"""
        # 窗口标志：工具窗口 + 无边框 + 始终置顶
        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(60, 60)

    def _init_ui(self) -> None:
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 悬浮按钮
        self._button = AIDockButton()
        self._button.clicked_expand.connect(self._toggle_panel)
        self._button.drag_finished.connect(self._on_drag_finished)
        layout.addWidget(self._button, alignment=Qt.AlignmentFlag.AlignCenter)

        # 快捷指令面板（初始隐藏）
        self._panel = ShortcutPanel()
        self._panel.setParent(self)
        self._panel.move(70, 0)
        self._panel.hide()
        self._panel.shortcut_selected.connect(self._on_shortcut_selected)

        self.setLayout(layout)

    def _init_tray(self) -> None:
        """初始化系统托盘"""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = QSystemTrayIcon(self)
            self._tray.setIcon(QIcon.fromTheme("assistant"))
            self._tray.setToolTip("AIDock - LivingTreeAI")

            # 托盘菜单
            tray_menu = QMenu()
            show_action = QAction("显示", self)
            hide_action = QAction("隐藏", self)
            quit_action = QAction("退出", self)

            show_action.triggered.connect(self.show)
            hide_action.triggered.connect(self.hide)
            quit_action.triggered.connect(self.close)

            tray_menu.addAction(show_action)
            tray_menu.addAction(hide_action)
            tray_menu.addSeparator()
            tray_menu.addAction(quit_action)

            self._tray.setContextMenu(tray_menu)
            self._tray.show()
        else:
            self._tray = None

    def _init_animations(self) -> None:
        """初始化动画"""
        # 展开/收起动画
        self._expand_animation = QPropertyAnimation(self, b"geometry")
        self._expand_animation.setDuration(300)
        self._expand_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _toggle_panel(self) -> None:
        """切换面板展开/收起"""
        if self._is_expanded:
            self._collapse_panel()
        else:
            self._expand_panel()

    def _expand_panel(self) -> None:
        """展开面板"""
        self._is_expanded = True
        self._panel.show()
        # 动画效果
        start_rect = QRect(self.pos(), QSize(60, 60))
        end_rect = QRect(self.pos(), QSize(350, 460))
        self._expand_animation.setStartValue(start_rect)
        self._expand_animation.setEndValue(end_rect)
        self._expand_animation.start()

    def _collapse_panel(self) -> None:
        """收起面板"""
        self._is_expanded = False
        self._panel.hide()
        # 动画效果
        start_rect = QRect(self.pos(), QSize(350, 460))
        end_rect = QRect(self.pos(), QSize(60, 60))
        self._expand_animation.setStartValue(start_rect)
        self._expand_animation.setEndValue(end_rect)
        self._expand_animation.start()

    def _on_drag_finished(self, pos: QPoint) -> None:
        """拖拽完成"""
        self.position_changed.emit(pos)

    def _on_shortcut_selected(self, intent: str) -> None:
        """快捷指令被选中"""
        self.shortcut_selected.emit(intent)
        # 收起面板
        if self._is_expanded:
            self._collapse_panel()

    def set_theme(self, theme: Any) -> None:
        """
        设置主题

        Args:
            theme: AIDockTheme.LIGHT / AIDockTheme.DARK / "auto"
        """
        theme_manager = ThemeManager.get_instance()
        theme_manager.set_theme(theme)
        self._theme = theme_manager.get_theme()
        self._apply_theme()

    def _apply_theme(self) -> None:
        """应用主题"""
        self._button.set_theme(self._theme)
        self._panel.set_theme(self._theme)

    def add_shortcut(self, title: str, intent: str) -> None:
        """添加快捷指令"""
        self._panel.add_shortcut(title, intent)

    def set_shortcuts(self, shortcuts: List[Dict[str, Any]]) -> None:
        """设置快捷指令列表"""
        self._panel.set_shortcuts(shortcuts)

    def showEvent(self, event) -> None:
        """显示事件"""
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        """隐藏事件"""
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        """关闭事件"""
        if hasattr(self, '_tray') and self._tray:
            self._tray.hide()
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────
# 便捷函数
# ──────────────────────────────────────────────────────────────


def create_aidock() -> AIDockWidget:
    """
    创建悬浮助手

    Returns:
        AIDockWidget 实例
    """
    return AIDockWidget()
