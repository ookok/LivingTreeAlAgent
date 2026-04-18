# desktop_window.py — 桌面窗口 UI (PyQt 实现)
# ============================================================================
#
# 负责桌面环境的 PyQt UI 实现
# 包括桌面、图标、窗口、任务栏等组件
#
# ============================================================================

import sys
from typing import Optional, Callable

# PyQt6 导入
try:
    from PyQt6.QtCore import (
        Qt, QTimer, QPropertyAnimation, QEasingCurve,
        QParallelAnimationGroup, QPoint, QSize, pyqtSignal, QRect
    )
    from PyQt6.QtGui import (
        QPixmap, QIcon, QPainter, QColor, QBrush, QPen, QCursor, QAction
    )
    from PyQt6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QMenu, QStackedWidget, QFrame,
        QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
        QGraphicsItem, QLineEdit, QListWidget, QListWidgetItem,
        QSystemTrayIcon, QApplication, QDialog
    )
    from PyQt6.QtSvg import QSvgRenderer
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt6 not available, desktop UI disabled")

# ============================================================================
# 桌面窗口 (PyQt)
# ============================================================================

if PYQT_AVAILABLE:

    class DesktopWindow(QMainWindow):
        """
        桌面主窗口

        功能:
        1. 桌面背景和壁纸
        2. 应用图标网格
        3. 多窗口管理
        4. 任务栏
        5. 全局搜索 (Ctrl+K)
        6. 右键菜单
        """

        # 信号
        icon_double_clicked = pyqtSignal(str)  # icon_id
        icon_right_clicked = pyqtSignal(str, QPoint)  # icon_id, position
        window_closed = pyqtSignal(str)  # window_id
        search_triggered = pyqtSignal(str)  # query

        def __init__(self, parent=None):
            super().__init__(parent)

            # 初始化组件
            self._desktop_manager = None
            self._window_manager = None
            self._app_manager = None
            self._theme_system = None
            self._search = None

            # 拖拽状态
            self._dragging_icon = None
            self._drag_start_pos = QPoint()

            # 初始化 UI
            self._init_ui()

            # 加载配置
            self._load_config()

        def _init_ui(self):
            """初始化 UI"""
            # 主窗口设置
            self.setWindowTitle("Hermes Desktop")
            self.setMinimumSize(800, 600)
            self.showFullScreen()  # 全屏桌面

            # 中央部件 - 堆叠窗口
            self._central_stack = QStackedWidget()
            self.setCentralWidget(self._central_stack)

            # 桌面页面
            self._desktop_page = QWidget()
            self._desktop_layout = QVBoxLayout(self._desktop_page)
            self._desktop_layout.setContentsMargins(0, 0, 0, 0)
            self._central_stack.addWidget(self._desktop_page)

            # 桌面背景
            self._desktop_background = QLabel()
            self._desktop_layout.addWidget(self._desktop_background)

            # 应用图标网格
            self._icon_grid = QGridLayout()
            self._icon_grid.setSpacing(16)
            self._icon_grid.setContentsMargins(16, 16, 16, 16)
            self._desktop_layout.addLayout(self._icon_grid)

            # 任务栏
            self._init_taskbar()

            # 搜索对话框
            self._init_search_dialog()

            # 右键菜单
            self._init_context_menu()

            # 键盘事件
            self._install_event_filters()

        def _init_taskbar(self):
            """初始化任务栏"""
            # 任务栏容器
            self._taskbar = QWidget()
            self._taskbar_layout = QHBoxLayout(self._taskbar)
            self._taskbar_layout.setContentsMargins(8, 4, 8, 4)

            # 任务栏高度
            self._taskbar.setFixedHeight(48)
            self._taskbar.setStyleSheet("""
                QWidget {
                    background: rgba(30, 30, 30, 0.9);
                    border-top: 1px solid #3D3D3D;
                }
            """)

            # 任务栏项容器
            self._taskbar_items = QWidget()
            self._taskbar_items_layout = QHBoxLayout(self._taskbar_items)
            self._taskbar_items_layout.setSpacing(8)
            self._taskbar_items_layout.setContentsMargins(0, 0, 0, 0)

            # 任务栏按钮
            self._start_button = QPushButton("🚀")
            self._start_button.setFixedSize(40, 40)
            self._start_button.setStyleSheet("border: none;")

            # 搜索按钮
            self._search_button = QPushButton("🔍")
            self._search_button.setFixedSize(40, 40)
            self._search_button.setStyleSheet("border: none;")
            self._search_button.clicked.connect(self._show_search)

            # 系统托盘按钮
            self._tray_button = QPushButton("📁")
            self._tray_button.setFixedSize(40, 40)
            self._tray_button.setStyleSheet("border: none;")

            # 布局
            self._taskbar_layout.addWidget(self._start_button)
            self._taskbar_layout.addWidget(self._taskbar_items)
            self._taskbar_layout.addStretch()
            self._taskbar_layout.addWidget(self._search_button)
            self._taskbar_layout.addWidget(self._tray_button)

            # 添加到桌面布局底部
            self._desktop_layout.addWidget(self._taskbar)

        def _init_search_dialog(self):
            """初始化搜索对话框"""
            self._search_dialog = QDialog(self, Qt.WindowType.FramelessWindowHint)
            self._search_dialog.setModal(True)
            self._search_dialog.setFixedSize(600, 400)
            self._search_dialog.setStyleSheet("""
                QDialog {
                    background: #2D2D2D;
                    border-radius: 12px;
                }
            """)

            layout = QVBoxLayout(self._search_dialog)
            layout.setContentsMargins(16, 16, 16, 16)

            # 搜索框
            self._search_input = QLineEdit()
            self._search_input.setPlaceholderText("搜索应用、功能、设置...")
            self._search_input.setStyleSheet("""
                QLineEdit {
                    background: #1E1E1E;
                    border: 1px solid #3D3D3D;
                    border-radius: 8px;
                    padding: 12px;
                    font-size: 16px;
                    color: white;
                }
            """)
            self._search_input.textChanged.connect(self._on_search_changed)
            layout.addWidget(self._search_input)

            # 结果列表
            self._search_results = QListWidget()
            self._search_results.setStyleSheet("""
                QListWidget {
                    background: transparent;
                    border: none;
                }
                QListWidget::item {
                    padding: 8px;
                    border-radius: 4px;
                }
                QListWidget::item:selected {
                    background: #4A90D9;
                }
            """)
            layout.addWidget(self._search_results)

            # 提示
            hint = QLabel("按 Enter 执行 · Esc 关闭")
            hint.setStyleSheet("color: #808080; font-size: 12px;")
            layout.addWidget(hint)

        def _init_context_menu(self):
            """初始化右键菜单"""
            self._context_menu = QMenu(self)
            self._context_menu.addAction("刷新", self._refresh_desktop)
            self._context_menu.addAction("桌面设置", self._show_desktop_settings)
            self._context_menu.addSeparator()
            self._context_menu.addAction("粘贴", self._paste)
            self._context_menu.addAction("新建文件夹", self._new_folder)

        def _install_event_filters(self):
            """安装事件过滤器"""
            self._desktop_page.installEventFilter(self)

        def _load_config(self):
            """加载配置"""
            from .desktop_manager import get_desktop_manager
            from .window_manager import WindowManager
            from .app_manager import get_app_manager
            from .theme_system import get_theme_system
            from .search import GlobalSearch

            self._desktop_manager = get_desktop_manager()
            self._window_manager = WindowManager()
            self._app_manager = get_app_manager()
            self._theme_system = get_theme_system()
            self._search = GlobalSearch()

            # 应用主题
            self._apply_theme()

        def _apply_theme(self):
            """应用主题"""
            theme = self._theme_system.get_current_theme()
            colors = theme.colors

            # 壁纸
            wallpaper = self._theme_system.get_wallpaper()
            if wallpaper:
                pixmap = QPixmap(wallpaper)
                scaled = pixmap.scaled(
                    self.size(),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._desktop_background.setPixmap(scaled)
            else:
                # 纯色背景
                self._desktop_background.setStyleSheet(
                    f"background-color: {colors.background};"
                )

        # --------------------------------------------------------------------------
        # 公开接口
        # --------------------------------------------------------------------------

        def register_icon(self, icon_id: str, name: str, icon_path: str = ""):
            """注册桌面图标"""
            icon_widget = self._create_icon_widget(icon_id, name, icon_path)
            self._icon_grid.addWidget(icon_widget)

        def _create_icon_widget(self, icon_id: str, name: str, icon_path: str) -> QWidget:
            """创建图标部件"""
            container = QWidget()
            container.setFixedSize(80, 90)
            container.setCursor(Qt.CursorShape.PointingHandCursor)

            layout = QVBoxLayout(container)
            layout.setSpacing(4)
            layout.setContentsMargins(0, 0, 0, 0)

            # 图标
            icon_label = QLabel()
            icon_label.setFixedSize(64, 64)
            if icon_path:
                icon_label.setPixmap(QPixmap(icon_path).scaled(64, 64))
            else:
                icon_label.setText("📦")
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_label.setStyleSheet("font-size: 32px;")
            layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)

            # 名称
            name_label = QLabel(name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setStyleSheet("""
                color: white;
                background: transparent;
                font-size: 12px;
            """)
            name_label.setWordWrap(True)
            layout.addWidget(name_label, 0, Qt.AlignmentFlag.AlignCenter)

            # 点击事件
            container.mousePressEvent = lambda e, i=icon_id: self._on_icon_clicked(i, e)
            container.mouseDoubleClickEvent = lambda e, i=icon_id: self._on_icon_double_clicked(i, e)

            return container

        def _on_icon_clicked(self, icon_id: str, event):
            """图标点击"""
            if event.button() == Qt.MouseButton.RightButton:
                pos = event.globalPosition().toPoint()
                self._context_menu.exec(QCursor.pos())
            else:
                self.icon_right_clicked.emit(icon_id, QCursor.pos())

        def _on_icon_double_clicked(self, icon_id: str, event):
            """图标双击"""
            self.icon_double_clicked.emit(icon_id)

        def _refresh_desktop(self):
            """刷新桌面"""
            self._desktop_manager.rearrange_icons()

        def _show_desktop_settings(self):
            """显示桌面设置"""
            pass

        def _paste(self):
            """粘贴"""
            pass

        def _new_folder(self):
            """新建文件夹"""
            pass

        def _show_search(self):
            """显示搜索对话框"""
            self._search_dialog.move(
                self.x() + (self.width() - self._search_dialog.width()) // 2,
                self.y() + 100
            )
            self._search_dialog.show()
            self._search_input.setFocus()

        def _on_search_changed(self, text: str):
            """搜索文本变化"""
            self._search_results.clear()

            if not text:
                return

            # 执行搜索
            results = self._search.quick_search(text)

            for result in results:
                item = QListWidgetItem(f"📦 {result.title}")
                item.setData(Qt.ItemDataRole.UserRole, result)
                self._search_results.addItem(item)

        # --------------------------------------------------------------------------
        # 事件处理
        # --------------------------------------------------------------------------

        def keyPressEvent(self, event):
            """键盘事件"""
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                if event.key() == Qt.Key.Key_K:
                    self._show_search()

        def eventFilter(self, obj, event):
            """事件过滤器"""
            return super().eventFilter(obj, event)

# ============================================================================
# 移动端桌面 (Kivy - 简化实现)
# ============================================================================

class MobileDesktop:
    """
    移动端桌面 (Kivy 实现)

    功能:
    1. 可缩放的桌面画布
    2. 应用网格容器
    3. 长按进入编辑模式
    4. 多点触控支持
    """

    def __init__(self, **kwargs):
        try:
            from kivy.uix.scatter import Scatter
            from kivy.uix.gridlayout import GridLayout
            from kivy.uix.boxlayout import BoxLayout
            from kivy.clock import Clock
            from kivy.properties import BooleanProperty
        except ImportError:
            print("Kivy not available")
            return

        self.kivy_available = True

        # Scatter 用于缩放和拖拽
        self.scatter = Scatter(
            do_rotation=False,
            do_scale=True,
            do_translation=True,
            **kwargs
        )

        # 应用网格
        self.app_container = GridLayout(
            cols=4,
            spacing=20,
            padding=20,
            size_hint=(None, None)
        )

        self.scatter.add_widget(self.app_container)
        self._setup_touch_handling()

    def _setup_touch_handling(self):
        """设置触摸处理"""
        pass

    def add_app(self, app_id: str, name: str, icon: str = ""):
        """添加应用到桌面"""
        # 创建图标按钮
        from kivy.uix.button import Button
        btn = Button(
            text=name,
            size_hint=(None, None),
            size=(80, 90),
            background_color=(0.2, 0.2, 0.2, 0.8),
            color=(1, 1, 1, 1)
        )
        btn.bind(on_release=lambda x: self._on_app_click(app_id))
        self.app_container.add_widget(btn)

    def _on_app_click(self, app_id: str):
        """应用点击"""
        pass

    def on_touch_down(self, touch):
        """触摸按下"""
        # 双击检测
        if touch.is_double_tap:
            self._open_app(touch)
        return super().on_touch_down(touch)

    def _open_app(self, touch):
        """打开应用"""
        pass

else:
    # PyQt 不可用时的占位符
    class DesktopWindow:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("PyQt6 is required for DesktopWindow")

    class MobileDesktop:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Kivy is required for MobileDesktop")