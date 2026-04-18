"""
视图工厂 - View Factory

支持三种视图模式：
1. 标签页视图 (Tabbed View) - 适合文档类、编辑器类插件
2. 停靠窗口 (Dockable View) - 适合工具类、监控类插件
3. 独立窗口 (Standalone View) - 适合全屏应用、复杂工作流

设计理念：
- 插件声明视图偏好，框架负责实例化和管理
- 同一插件可支持多种视图模式
- 视图可动态切换
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Type
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTabBar,
    QDockWidget, QMainWindow,
    QStackedWidget, QToolBar,
    QLabel, QPushButton,
    QMenu, QStyleFactory,
)
from PyQt6.QtGui import QIcon, QAction


class ViewMode(Enum):
    """视图模式枚举"""
    TABBED = "tabbed"           # 标签页视图
    DOCKABLE = "dockable"       # 停靠窗口
    STANDALONE = "standalone"    # 独立窗口


@dataclass
class ViewConfig:
    """视图配置"""
    mode: ViewMode = ViewMode.TABBED
    title: str = ""
    icon: Optional[str] = None
    closable: bool = True
    floatable: bool = True
    auto_hide: bool = False
    area: str = "left"  # left, right, top, bottom, center
    width: int = 400
    height: int = 600
    min_width: int = 200
    min_height: int = 150


class BaseView(QWidget):
    """
    视图基类

    所有视图都必须继承此类
    """

    # 信号定义
    closed = pyqtSignal(str)  # view_id
    visibility_changed = pyqtSignal(bool)  # visible
    title_changed = pyqtSignal(str)

    def __init__(self, view_id: str, config: ViewConfig, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.view_id = view_id
        self.config = config
        self._is_visible = True
        self._content_widget: Optional[QWidget] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """设置UI（子类重写）"""
        pass

    def set_content_widget(self, widget: QWidget) -> None:
        """设置内容Widget"""
        self._content_widget = widget
        if widget is not None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(widget)
            self._content_widget.setVisible(self._is_visible)

    def get_content_widget(self) -> Optional[QWidget]:
        """获取内容Widget"""
        return self._content_widget

    def show_view(self) -> None:
        """显示视图"""
        self._is_visible = True
        self.setVisible(True)
        if self._content_widget:
            self._content_widget.setVisible(True)
        self.visibility_changed.emit(True)

    def hide_view(self) -> None:
        """隐藏视图"""
        self._is_visible = False
        self.setVisible(False)
        if self._content_widget:
            self._content_widget.setVisible(False)
        self.visibility_changed.emit(False)

    def is_visible(self) -> bool:
        """是否可见"""
        return self._is_visible

    def set_title(self, title: str) -> None:
        """设置标题"""
        self.config.title = title
        self.title_changed.emit(title)

    def close_view(self) -> None:
        """关闭视图"""
        self.hide_view()
        self.closed.emit(self.view_id)


class TabbedView(BaseView):
    """
    标签页视图

    特点：
    - 类似浏览器标签页
    - 多个插件共享一个标签区域
    - Ctrl+Tab 切换插件
    """

    def __init__(self, view_id: str, config: ViewConfig, parent: Optional[QWidget] = None):
        self._tab_widget: Optional[QTabWidget] = None
        self._tab_index: int = -1
        super().__init__(view_id, config, parent)

    def _setup_ui(self) -> None:
        # TabbedView 本身不需要自己的布局
        # 它将由外部的 QTabWidget 管理
        pass

    def set_tab_widget(self, tab_widget: QTabWidget) -> None:
        """设置标签页Widget"""
        self._tab_widget = tab_widget

    def attach_to_tab(self, index: int) -> None:
        """附加到标签页"""
        self._tab_index = index
        if self._tab_widget and self._content_widget:
            self._tab_widget.insertTab(index, self._content_widget, self.config.title)
            if self.config.icon:
                self._tab_widget.setTabIcon(index, QIcon(self.config.icon))

    def detach_from_tab(self) -> None:
        """从标签页分离"""
        if self._tab_widget and self._tab_index >= 0:
            self._tab_widget.removeTab(self._tab_index)
            self._tab_index = -1

    def select(self) -> None:
        """选中文本标签页"""
        if self._tab_widget and self._tab_index >= 0:
            self._tab_widget.setCurrentIndex(self._tab_index)


class DockableView(BaseView):
    """
    停靠窗口视图

    特点：
    - 可停靠在主窗口四周
    - 可浮动、可拖拽、可自动隐藏
    - 适合工具类、监控类插件
    """

    def __init__(self, view_id: str, config: ViewConfig, parent: Optional[QWidget] = None):
        self._dock_widget: Optional[QDockWidget] = None
        self._area: Qt.DockWidgetArea = Qt.DockWidgetArea.LeftDockWidgetArea
        super().__init__(view_id, config, parent)

    def _setup_ui(self) -> None:
        """设置UI"""
        # DockWidget 由 ViewFactory 创建，这里只是配置
        pass

    def create_dock_widget(self, main_window: QMainWindow) -> QDockWidget:
        """创建停靠窗口"""
        self._dock_widget = QDockWidget(self.config.title, main_window)
        self._dock_widget.setObjectName(f"dock_{self.view_id}")

        if self._content_widget:
            self._dock_widget.setWidget(self._content_widget)

        # 设置停靠区
        area_map = {
            "left": Qt.DockWidgetArea.LeftDockWidgetArea,
            "right": Qt.DockWidgetArea.RightDockWidgetArea,
            "top": Qt.DockWidgetArea.TopDockWidgetArea,
            "bottom": Qt.DockWidgetArea.BottomDockWidgetArea,
        }
        self._area = area_map.get(self.config.area, Qt.DockWidgetArea.LeftDockWidgetArea)

        # 设置特性
        features = QDockWidget.DockWidgetFeature()
        if self.config.closable:
            features |= QDockWidget.DockWidgetFeature.DockWidgetClosable
        if self.config.floatable:
            features |= QDockWidget.DockWidgetFeature.DockWidgetFloatable
        features |= QDockWidget.DockWidgetFeature.DockWidgetMovable
        self._dock_widget.setFeatures(features)

        # 设置尺寸
        self._dock_widget.setMinimumSize(self.config.min_width, self.config.min_height)

        return self._dock_widget

    def get_dock_widget(self) -> Optional[QDockWidget]:
        """获取停靠窗口"""
        return self._dock_widget

    def get_area(self) -> Qt.DockWidgetArea:
        """获取停靠区域"""
        return self._area


class StandaloneView(BaseView):
    """
    独立窗口视图

    特点：
    - 完全独立窗口
    - 可跨屏幕
    - 支持多实例
    - 适合全屏应用、复杂工作流
    """

    def __init__(self, view_id: str, config: ViewConfig, parent: Optional[QWidget] = None):
        self._window: Optional[QMainWindow] = None
        self._is_standalone = True
        super().__init__(view_id, config, parent)

    def _setup_ui(self) -> None:
        """设置UI"""
        pass

    def create_window(self) -> QMainWindow:
        """创建独立窗口"""
        self._window = QMainWindow()
        self._window.setWindowTitle(self.config.title)
        self._window.setObjectName(f"standalone_{self.view_id}")

        if self.config.icon:
            self._window.setWindowIcon(QIcon(self.config.icon))

        # 设置尺寸
        self._window.resize(self.config.width, self.config.height)
        self._window.setMinimumSize(self.config.min_width, self.config.min_height)

        if self._content_widget:
            self._window.setCentralWidget(self._content_widget)

        return self._window

    def get_window(self) -> Optional[QMainWindow]:
        """获取独立窗口"""
        return self._window

    def show_view(self) -> None:
        """显示视图（作为独立窗口）"""
        if self._window:
            self._window.show()
            self._is_visible = True
            self.visibility_changed.emit(True)

    def hide_view(self) -> None:
        """隐藏视图"""
        if self._window:
            self._window.hide()
        self._is_visible = False
        self.visibility_changed.emit(False)

    def close_view(self) -> None:
        """关闭窗口"""
        if self._window:
            self._window.close()
        self.hide_view()
        self.closed.emit(self.view_id)


class ViewFactory:
    """
    视图工厂

    负责创建和管理各种视图

    使用示例：
        factory = ViewFactory(main_window)

        # 创建标签页视图
        tab_view = factory.create_view(
            view_id="kb_1",
            config=ViewConfig(mode=ViewMode.TABBED, title="知识库"),
            content_widget=kb_widget,
        )

        # 创建停靠视图
        dock_view = factory.create_view(
            view_id="chat_1",
            config=ViewConfig(mode=ViewMode.DOCKABLE, title="AI聊天", area="right"),
            content_widget=chat_widget,
        )

        # 创建独立窗口
        standalone_view = factory.create_view(
            view_id="im_1",
            config=ViewConfig(mode=ViewMode.STANDALONE, title="IM客户端"),
            content_widget=im_widget,
        )
    """

    def __init__(self, main_window: Optional[QMainWindow] = None):
        self._main_window = main_window
        self._views: Dict[str, BaseView] = {}
        self._tab_widget: Optional[QTabWidget] = None
        self._view_counters: Dict[ViewMode, int] = {
            ViewMode.TABBED: 0,
            ViewMode.DOCKABLE: 0,
            ViewMode.STANDALONE: 0,
        }

    def set_main_window(self, main_window: QMainWindow) -> None:
        """设置主窗口"""
        self._main_window = main_window

    def set_tab_widget(self, tab_widget: QTabWidget) -> None:
        """设置标签页Widget"""
        self._tab_widget = tab_widget

    def create_view(
        self,
        view_id: Optional[str],
        config: ViewConfig,
        content_widget: Optional[QWidget] = None,
    ) -> BaseView:
        """
        创建视图

        Args:
            view_id: 视图ID（可选，不提供则自动生成）
            config: 视图配置
            content_widget: 内容Widget

        Returns:
            创建的视图对象
        """
        if view_id is None:
            view_id = self._generate_view_id(config.mode)

        # 根据模式创建视图
        if config.mode == ViewMode.TABBED:
            view = TabbedView(view_id, config)
        elif config.mode == ViewMode.DOCKABLE:
            view = DockableView(view_id, config)
        elif config.mode == ViewMode.STANDALONE:
            view = StandaloneView(view_id, config)
        else:
            raise ValueError(f"Unknown view mode: {config.mode}")

        # 设置内容
        if content_widget:
            view.set_content_widget(content_widget)

        # 额外初始化
        if isinstance(view, TabbedView) and self._tab_widget:
            view.set_tab_widget(self._tab_widget)
            view.attach_to_tab(self._tab_widget.count())

        elif isinstance(view, DockableView) and self._main_window:
            dock = view.create_dock_widget(self._main_window)
            self._main_window.addDockWidget(view.get_area(), dock)

        elif isinstance(view, StandaloneView):
            window = view.create_window()

        self._views[view_id] = view
        self._view_counters[config.mode] += 1

        return view

    def get_view(self, view_id: str) -> Optional[BaseView]:
        """获取视图"""
        return self._views.get(view_id)

    def remove_view(self, view_id: str) -> bool:
        """
        移除视图

        Args:
            view_id: 视图ID

        Returns:
            是否成功移除
        """
        view = self._views.get(view_id)
        if view is None:
            return False

        # 清理视图
        if isinstance(view, TabbedView):
            view.detach_from_tab()
        elif isinstance(view, DockableView):
            if self._main_window and view.get_dock_widget():
                self._main_window.removeDockWidget(view.get_dock_widget())
        elif isinstance(view, StandaloneView):
            if view.get_window():
                view.get_window().deleteLater()

        del self._views[view_id]
        return True

    def get_views_by_mode(self, mode: ViewMode) -> List[BaseView]:
        """获取指定模式的所有视图"""
        return [v for v in self._views.values() if v.config.mode == mode]

    def get_views_by_plugin(self, plugin_id: str) -> List[BaseView]:
        """获取指定插件的所有视图"""
        # 需要从视图配置中获取插件ID
        return [v for v in self._views.values() if plugin_id in v.view_id]

    def _generate_view_id(self, mode: ViewMode) -> str:
        """生成唯一的视图ID"""
        counter = self._view_counters[mode]
        prefix = mode.value
        return f"{prefix}_{counter}"

    def get_all_views(self) -> Dict[str, BaseView]:
        """获取所有视图"""
        return self._views.copy()


# 全局单例
_view_factory_instance: Optional[ViewFactory] = None


def get_view_factory(main_window: Optional[QMainWindow] = None) -> ViewFactory:
    """获取视图工厂单例"""
    global _view_factory_instance
    if _view_factory_instance is None:
        _view_factory_instance = ViewFactory(main_window)
    return _view_factory_instance
