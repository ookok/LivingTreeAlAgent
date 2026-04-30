"""
万能客户端主窗口 - Main Dock Window

支持四种区域设计：
┌─────────────────────────────────────────────────────┐
│ 菜单栏  [文件 编辑 视图 插件 窗口 帮助]             │
├─────────────────┬─────────────────┬───────────────┤
│                 │                 │               │
│  插件面板       │                 │   插件仓库    │
│  (可折叠)       │   主工作区       │  (可选)       │
│                 │  (MDI区域)      │               │
│  • 知识库       │                 │               │
│  • 压缩工具     ├─────────────────┤               │
│  • 图片编辑     │   属性面板       │               │
│  • AI聊天       │  (动态)         │               │
│  • IM客户端     │                 │               │
│  • 项目管理     │                 │               │
│                 │                 │               │
└─────────────────┴─────────────────┴───────────────┘

支持三种视图模式：
1. 标签页视图 (Tabbed View)
2. 停靠窗口 (Dockable View)
3. 独立窗口 (Standalone Window)

设计理念：主框架为容器，插件为灵魂
"""

from typing import Dict, List, Optional, Any, Callable
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QLabel, QMessageBox, QStackedWidget, QTabWidget,
    QPushButton, QMenuBar, QMenu, QToolBar, QDockWidget,
    QMainWindow, QStatusBar, QSystemTrayIcon, QAction,
    QDialog, QListWidget, QListWidgetItem, QInputDialog,
    QFileDialog, QApplication,
)
from PyQt6.QtGui import QKeyEvent, QAction, QIcon, QCloseEvent
from PyQt6.QtCore import QEvent

from .business.plugin_framework import (
    PluginManager, get_plugin_manager,
    EventBus, get_event_bus,
    ViewFactory, ViewMode,
    ThemeSystem, get_theme_system,
    LayoutManager, get_layout_manager,
    BasePlugin, PluginManifest, PluginType,
)
from core.plugin_framework.plugins import (
    KnowledgeBasePlugin, AIChatPlugin, IMClientPlugin,
)


class MainDockWindow(QMainWindow):
    """
    万能客户端主窗口

    支持：
    - 插件管理
    - 三种视图模式
    - 布局保存/加载
    - 主题切换
    - 系统托盘
    """

    # 信号定义
    plugin_view_created = pyqtSignal(str)  # plugin_id
    layout_changed = pyqtSignal(str)  # layout_id

    def __init__(self):
        super().__init__()
        self._plugin_manager: Optional[PluginManager] = None
        self._event_bus: Optional[EventBus] = None
        self._view_factory: Optional[ViewFactory] = None
        self._theme_system: Optional[ThemeSystem] = None
        self._layout_manager: Optional[LayoutManager] = None

        self._active_plugins: Dict[str, BasePlugin] = {}
        self._plugin_views: Dict[str, Any] = {}  # plugin_id -> view

        self._current_view_mode: str = "tabbed"  # tabbed, dock, standalone
        self._standalone_windows: Dict[str, QWidget] = {}

        self._setup_ui()
        self._setup_plugin_system()
        self._setup_tray()

    def _setup_ui(self) -> None:
        """设置UI"""
        self.setWindowTitle("万能客户端 - Plugin Framework Demo")
        self.setMinimumSize(1000, 700)

        # 创建菜单栏
        self._create_menu_bar()

        # 创建工具栏
        self._create_tool_bar()

        # 创建状态栏
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪")

        # 创建中心区域
        self._create_central_area()

        # 创建停靠区域
        self._create_dock_areas()

    def _create_menu_bar(self) -> None:
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        new_action = QAction("新建", self)
        new_action.setShortcut("Ctrl+N")
        file_menu.addAction(new_action)

        open_action = QAction("打开...", self)
        open_action.setShortcut("Ctrl+O")
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_layout_action = QAction("保存布局", self)
        save_layout_action.triggered.connect(self._on_save_layout)
        file_menu.addAction(save_layout_action)

        load_layout_action = QAction("加载布局...", self)
        load_layout_action.triggered.connect(self._on_load_layout)
        file_menu.addAction(load_layout_action)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图")

        theme_menu = view_menu.addMenu("主题")
        dark_action = QAction("深色主题", self, checkable=True)
        dark_action.setChecked(True)
        dark_action.triggered.connect(lambda: self._on_change_theme("dark"))
        theme_menu.addAction(dark_action)

        light_action = QAction("浅色主题", self, checkable=True)
        light_action.triggered.connect(lambda: self._on_change_theme("light"))
        theme_menu.addAction(light_action)

        view_menu.addSeparator()

        layout_menu = view_menu.addMenu("布局模板")
        for layout_id, layout_name in [
            ("default", "默认布局"),
            ("coding", "编码模式"),
            ("chat", "聊天模式"),
        ]:
            action = QAction(layout_name, self)
            action.triggered.connect(lambda checked, lid=layout_id: self._on_apply_layout(lid))
            layout_menu.addAction(action)

        # 插件菜单
        plugin_menu = menubar.addMenu("插件")

        self._plugin_menu_actions: Dict[str, QAction] = {}

        manage_action = QAction("插件管理...", self)
        manage_action.triggered.connect(self._on_plugin_manager)
        plugin_menu.addAction(manage_action)

        plugin_menu.addSeparator()

        reload_action = QAction("重载插件", self)
        reload_action.triggered.connect(self._on_reload_plugins)
        plugin_menu.addAction(reload_action)

        # 窗口菜单
        window_menu = menubar.addMenu("窗口")

        self._tabbed_action = QAction("标签页视图", self, checkable=True)
        self._tabbed_action.setChecked(True)
        self._tabbed_action.triggered.connect(self._on_switch_tabbed)
        window_menu.addAction(self._tabbed_action)

        self._dock_action = QAction("停靠视图", self, checkable=True)
        self._dock_action.triggered.connect(self._on_switch_dock)
        window_menu.addAction(self._dock_action)

        self._standalone_action = QAction("独立窗口视图", self, checkable=True)
        self._standalone_action.triggered.connect(self._on_switch_standalone)
        window_menu.addAction(self._standalone_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _create_tool_bar(self) -> None:
        """创建工具栏"""
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # 快速启动插件按钮
        self._quick_buttons: Dict[str, QPushButton] = {}

        plugins = [
            ("知识库", "kb"),
            ("AI聊天", "chat"),
            ("IM", "im"),
        ]

        for name, plugin_id in plugins:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, pid=plugin_id: self._on_toggle_plugin(pid))
            toolbar.addWidget(btn)
            self._quick_buttons[plugin_id] = btn

        toolbar.addSeparator()

        # 布局切换
        layout_label = QLabel("布局:")
        toolbar.addWidget(layout_label)

        for name, layout_id in [
            ("默认", "default"),
            ("编码", "coding"),
            ("聊天", "chat"),
        ]:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, lid=layout_id: self._on_apply_layout(lid))
            toolbar.addWidget(btn)

    def _create_central_area(self) -> None:
        """创建中心区域"""
        # 标签页控件
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.tabCloseRequested.connect(self._on_close_tab)
        self.setCentralWidget(self._tab_widget)

    def _create_dock_areas(self) -> None:
        """创建停靠区域"""
        # 左侧插件面板
        self._left_dock = QDockWidget("插件面板", self)
        self._left_dock.setObjectName("left_dock")
        self._left_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self._left_plugin_list = QListWidget()
        self._left_plugin_list.itemClicked.connect(self._on_plugin_list_item_clicked)
        self._left_dock.setWidget(self._left_plugin_list)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._left_dock)

        # 右侧插件仓库（可选）
        self._right_dock = QDockWidget("插件仓库", self)
        self._right_dock.setObjectName("right_dock")
        self._right_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self._right_plugin_list = QListWidget()
        self._right_plugin_list.setAlternatingRowColors(True)
        self._right_dock.setWidget(self._right_plugin_list)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._right_dock)
        self._right_dock.setVisible(False)  # 默认隐藏

    def _setup_plugin_system(self) -> None:
        """初始化插件系统"""
        # 初始化管理器
        self._plugin_manager = get_plugin_manager()
        self._plugin_manager.initialize(main_window=self)

        # 初始化事件总线
        self._event_bus = get_event_bus()

        # 初始化视图工厂
        self._view_factory = get_view_factory(self)
        self._view_factory.set_tab_widget(self._tab_widget)

        # 初始化主题系统
        self._theme_system = get_theme_system()
        self._theme_system.set_app(QApplication.instance())

        # 初始化布局管理器
        self._layout_manager = get_layout_manager(self)
        self._layout_manager.set_view_factory(self._view_factory)

        # 注册内置插件
        self._register_builtin_plugins()

        # 更新插件列表
        self._update_plugin_lists()

    def _register_builtin_plugins(self) -> None:
        """注册内置插件"""
        # 知识库插件
        self._plugin_manager.register_plugin_class(
            KnowledgeBasePlugin,
            KnowledgeBasePlugin.MANIFEST
        )

        # AI聊天插件
        self._plugin_manager.register_plugin_class(
            AIChatPlugin,
            AIChatPlugin.MANIFEST
        )

        # IM客户端插件
        self._plugin_manager.register_plugin_class(
            IMClientPlugin,
            IMClientPlugin.MANIFEST
        )

        self._status_bar.showMessage(f"已加载 {len(self._plugin_manager.get_all_plugins())} 个内置插件")

    def _update_plugin_lists(self) -> None:
        """更新插件列表"""
        # 左侧面板
        self._left_plugin_list.clear()
        plugins = self._plugin_manager.get_all_plugins()
        for plugin_id, info in plugins.items():
            item = QListWidgetItem(info.manifest.name)
            item.setData(Qt.ItemDataRole.UserRole, plugin_id)
            self._left_plugin_list.addItem(item)

        # 右侧仓库
        self._right_plugin_list.clear()
        for plugin_id, info in plugins.items():
            item = QListWidgetItem(f"{info.manifest.name} v{info.manifest.version}")
            item.setData(Qt.ItemDataRole.UserRole, plugin_id)
            self._right_plugin_list.addItem(item)

    def _on_plugin_list_item_clicked(self, item: QListWidgetItem) -> None:
        """插件列表项点击"""
        plugin_id = item.data(Qt.ItemDataRole.UserRole)
        self._toggle_plugin_view(plugin_id)

    def _toggle_plugin_view(self, plugin_id: str) -> None:
        """切换插件视图"""
        if plugin_id in self._plugin_views:
            # 已经显示，切换到前台
            view = self._plugin_views[plugin_id]
            if hasattr(view, 'select'):
                view.select()
            return

        # 激活插件
        if not self._plugin_manager.activate_plugin(plugin_id):
            self._status_bar.showMessage(f"插件激活失败: {plugin_id}")
            return

        plugin = self._plugin_manager.get_plugin(plugin_id)
        if not plugin or not plugin.widget:
            return

        # 获取视图偏好
        pref = plugin.manifest.view_preference

        # 根据偏好创建视图
        from core.plugin_framework.view_factory import ViewConfig
        config = ViewConfig(
            mode=pref.preferred_mode,
            title=plugin.manifest.name,
            icon=pref.icon,
            closable=pref.closable,
            floatable=pref.floatable,
            area=pref.dock_area,
            width=pref.default_width,
            height=pref.default_height,
            min_width=pref.min_width,
            min_height=pref.min_height,
        )

        view = self._view_factory.create_view(
            view_id=f"{plugin_id}_view",
            config=config,
            content_widget=plugin.widget,
        )

        self._plugin_views[plugin_id] = view
        self.plugin_view_created.emit(plugin_id)
        self._status_bar.showMessage(f"打开插件: {plugin.manifest.name}")

    def _on_toggle_plugin(self, plugin_id: str) -> None:
        """切换插件（工具栏按钮）"""
        self._toggle_plugin_view(plugin_id)

    def _on_close_tab(self, index: int) -> None:
        """关闭标签页"""
        self._tab_widget.removeTab(index)

    def _on_save_layout(self) -> None:
        """保存布局"""
        name, ok = QInputDialog.getText(self, "保存布局", "布局名称:")
        if ok and name:
            layout_id = name.lower().replace(" ", "_")
            self._layout_manager.save_layout(layout_id, name)
            self._status_bar.showMessage(f"布局已保存: {name}")

    def _on_load_layout(self) -> None:
        """加载布局"""
        layouts = list(self._layout_manager.get_all_layouts().keys())
        if not layouts:
            self._status_bar.showMessage("没有已保存的布局")
            return

        layout_id, ok = QInputDialog.getItem(self, "加载布局", "选择布局", layouts)
        if ok:
            self._layout_manager.apply_layout(layout_id)
            self.layout_changed.emit(layout_id)
            self._status_bar.showMessage(f"已应用布局: {layout_id}")

    def _on_apply_layout(self, layout_id: str) -> None:
        """应用布局"""
        self._layout_manager.apply_layout(layout_id)
        self.layout_changed.emit(layout_id)
        self._status_bar.showMessage(f"已应用布局: {layout_id}")

    def _on_change_theme(self, theme_id: str) -> None:
        """切换主题"""
        self._theme_system.apply_theme(theme_id)
        self._status_bar.showMessage(f"已切换到主题: {theme_id}")

    def _on_plugin_manager(self) -> None:
        """插件管理对话框"""
        dialog = PluginManagerDialog(self._plugin_manager, self)
        dialog.exec()

    def _on_reload_plugins(self) -> None:
        """重载插件"""
        self._plugin_manager.initialize_all()
        self._update_plugin_lists()
        self._status_bar.showMessage("插件已重载")

    def _on_switch_tabbed(self) -> None:
        """切换到标签页视图"""
        self._tabbed_action.setChecked(True)
        self._dock_action.setChecked(False)
        self._standalone_action.setChecked(False)
        
        # 恢复标签页视图
        if hasattr(self, '_tab_widget') and self._tab_widget:
            self.setCentralWidget(self._tab_widget)
            self._tab_widget.setVisible(True)
        
        # 隐藏停靠窗口
        if hasattr(self, '_dock_area') and self._dock_area:
            self._dock_area.setVisible(False)
        
        self._current_view_mode = "tabbed"
        self._status_bar.showMessage("已切换到标签页视图")
        self.layout_changed.emit("tabbed")

    def _on_switch_dock(self) -> None:
        """切换到停靠视图"""
        self._tabbed_action.setChecked(False)
        self._dock_action.setChecked(True)
        self._standalone_action.setChecked(False)
        
        # 创建并显示停靠区域
        if not hasattr(self, '_dock_area') or not self._dock_area:
            self._create_dock_areas()
        
        if self._dock_area:
            self._dock_area.setVisible(True)
        
        # 隐藏标签页
        if hasattr(self, '_tab_widget') and self._tab_widget:
            self._tab_widget.setVisible(False)
        
        self._current_view_mode = "dock"
        self._status_bar.showMessage("已切换到停靠视图")
        self.layout_changed.emit("dock")

    def _on_switch_standalone(self) -> None:
        """切换到独立窗口视图"""
        self._tabbed_action.setChecked(False)
        self._dock_action.setChecked(False)
        self._standalone_action.setChecked(True)
        
        # 为每个活跃插件创建独立窗口
        for plugin_id, plugin in self._active_plugins.items():
            if plugin.widget and plugin_id not in self._standalone_windows:
                window = QWidget(None, Qt.WindowType.Window)
                window.setWindowTitle(plugin.manifest.name)
                window.setMinimumSize(600, 400)
                
                layout = QVBoxLayout(window)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(plugin.widget)
                
                window.show()
                self._standalone_windows[plugin_id] = window
        
        # 隐藏主工作区
        if hasattr(self, '_tab_widget') and self._tab_widget:
            self._tab_widget.setVisible(False)
        if hasattr(self, '_dock_area') and self._dock_area:
            self._dock_area.setVisible(False)
        
        self._current_view_mode = "standalone"
        self._status_bar.showMessage("已切换到独立窗口视图")
        self.layout_changed.emit("standalone")

    def _on_about(self) -> None:
        """关于对话框"""
        QMessageBox.about(
            self,
            "关于万能客户端",
            "万能客户端 - Plugin Framework Demo\n\n"
            "基于 PyQt6 的插件化桌面应用框架\n"
            "支持三种视图模式：标签页、停靠、独立窗口\n\n"
            "设计理念：主框架为容器，插件为灵魂"
        )

    def _setup_tray(self) -> None:
        """设置系统托盘"""
        self._tray = QSystemTrayIcon(self)

        # 创建托盘菜单
        tray_menu = QMenu()

        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        for name, plugin_id in [
            ("知识库", "kb"),
            ("AI聊天", "chat"),
            ("IM客户端", "im"),
        ]:
            action = QAction(name, self)
            action.triggered.connect(lambda checked, pid=plugin_id: self._toggle_plugin_view(pid))
            tray_menu.addAction(action)

        tray_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        tray_menu.addAction(exit_action)

        self._tray.setContextMenu(tray_menu)
        self._tray.setToolTip("万能客户端")
        self._tray.show()

    def closeEvent(self, event: QCloseEvent) -> None:
        """关闭事件"""
        # 保存布局
        if self._layout_manager:
            self._layout_manager.save_layout("last", "上次布局")
        event.accept()


class PluginManagerDialog(QDialog):
    """插件管理对话框"""

    def __init__(self, plugin_manager: PluginManager, parent=None):
        super().__init__(parent)
        self._plugin_manager = plugin_manager
        self._setup_ui()
        self._load_plugins()

    def _setup_ui(self) -> None:
        """设置UI"""
        self.setWindowTitle("插件管理")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        # 插件列表
        self._plugin_list = QListWidget()
        layout.addWidget(self._plugin_list)

        # 按钮
        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._load_plugins)
        btn_layout.addWidget(refresh_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _load_plugins(self) -> None:
        """加载插件列表"""
        self._plugin_list.clear()
        plugins = self._plugin_manager.get_all_plugins()

        for plugin_id, info in plugins.items():
            state_icon = {
                "registered": "○",
                "loaded": "◐",
                "active": "●",
                "inactive": "◌",
                "error": "⚠",
            }.get(info.state.value, "?")

            item = QListWidgetItem(f"{state_icon} {info.manifest.name} ({plugin_id})")
            item.setData(Qt.ItemDataRole.UserRole, plugin_id)
            self._plugin_list.addItem(item)


def create_main_window() -> MainDockWindow:
    """创建主窗口"""
    return MainDockWindow()


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 应用主题
    theme_system = get_theme_system()
    theme_system.set_app(app)
    theme_system.apply_theme("dark")

    window = create_main_window()
    window.show()

    sys.exit(app.exec())
