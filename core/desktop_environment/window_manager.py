# window_manager.py — 窗口管理器
# ============================================================================
#
# 负责管理应用窗口的创建、显示、销毁
# 支持拖拽、缩放、最小化、最大化和关闭功能
#
# ============================================================================

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum

# ============================================================================
# 配置与枚举
# ============================================================================

class WindowState(Enum):
    """窗口状态"""

from core.logger import get_logger
logger = get_logger('desktop_environment.window_manager')
    NORMAL = "normal"
    MINIMIZED = "minimized"
    MAXIMIZED = "maximized"
    FULLSCREEN = "fullscreen"
    CLOSING = "closing"

class WindowAnimation(Enum):
    """窗口动画"""
    NONE = "none"
    ZOOM = "zoom"           # 缩放动画
    FADE = "fade"           # 淡入淡出
    SLIDE = "slide"         # 滑动
    POP = "pop"             # 弹出

@dataclass
class WindowGeometry:
    """窗口几何信息"""
    x: float = 100
    y: float = 100
    width: float = 800
    height: float = 600
    min_width: float = 400
    min_height: float = 300
    max_width: float = 4096
    max_height: float = 4096

# ============================================================================
# 标题栏
# ============================================================================

class TitleBar:
    """
    窗口标题栏组件

    功能:
    1. 显示窗口标题
    2. 窗口拖拽移动
    3. 控制按钮 (最小化、最大化、关闭)
    4. 双击标题栏最大化/还原
    """

    def __init__(
        self,
        title: str = "",
        on_close: Callable = None,
        on_minimize: Callable = None,
        on_maximize: Callable = None,
        on_double_click: Callable = None,
        height: int = 32
    ):
        self.title = title
        self.height = height

        # 回调
        self._on_close = on_close
        self._on_minimize = on_minimize
        self._on_maximize = on_maximize
        self._on_double_click = on_double_click

        # 状态
        self._is_maximized = False
        self._is_dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0

    # --------------------------------------------------------------------------
    # 事件处理
    # --------------------------------------------------------------------------

    def handle_mouse_down(self, x: float, y: float, button: int = 0):
        """处理鼠标按下"""
        if button == 0:  # 左键
            self._is_dragging = True
            self._drag_start_x = x
            self._drag_start_y = y

    def handle_mouse_move(self, x: float, y: float):
        """处理鼠标移动"""
        if self._is_dragging:
            delta_x = x - self._drag_start_x
            delta_y = y - self._drag_start_y
            return (delta_x, delta_y)
        return (0, 0)

    def handle_mouse_up(self):
        """处理鼠标释放"""
        self._is_dragging = False

    def handle_double_click(self):
        """处理双击"""
        if self._on_double_click:
            self._on_double_click()
        else:
            self._is_maximized = not self._is_maximized

    def handle_close(self):
        """处理关闭"""
        if self._on_close:
            self._on_close()

    def handle_minimize(self):
        """处理最小化"""
        if self._on_minimize:
            self._on_minimize()

    def handle_maximize(self):
        """处理最大化"""
        if self._on_maximize:
            self._on_maximize()
        self._is_maximized = not self._is_maximized

    # --------------------------------------------------------------------------
    # 属性
    # --------------------------------------------------------------------------

    @property
    def is_maximized(self) -> bool:
        return self._is_maximized

    def set_title(self, title: str):
        """设置标题"""
        self.title = title

# ============================================================================
# 应用窗口
# ============================================================================

class AppWindow:
    """
    应用窗口

    功能:
    1. 窗口拖拽移动
    2. 窗口缩放调整大小
    3. 最小化/最大化/关闭
    4. 动态加载应用内容
    5. 窗口动画
    6. 层级管理 (z-index)
    """

    def __init__(
        self,
        window_id: str = None,
        title: str = "应用窗口",
        geometry: WindowGeometry = None,
        module: str = "",
        parent: "WindowManager" = None
    ):
        # 基础信息
        self.window_id = window_id or str(uuid.uuid4())
        self.title = title
        self.geometry = geometry or WindowGeometry()
        self.module = module

        # 父窗口管理器
        self._parent = parent

        # 状态
        self.state = WindowState.NORMAL
        self.z_index = 0
        self.is_visible = True

        # 标题栏
        self.title_bar = TitleBar(
            title=title,
            on_close=self.close,
            on_minimize=self.minimize,
            on_maximize=self.toggle_maximize,
            on_double_click=self.toggle_maximize
        )

        # 应用内容
        self._content = None
        self._app_instance = None

        # 拖拽状态
        self._is_dragging = False
        self._is_resizing = False
        self._resize_edge = ""

        # 动画
        self.animation = WindowAnimation.ZOOM
        self.animation_duration = 0.3

    # --------------------------------------------------------------------------
    # 窗口控制
    # --------------------------------------------------------------------------

    def show(self):
        """显示窗口"""
        self.is_visible = True
        self.state = WindowState.NORMAL
        if self._parent:
            self._parent.activate_window(self.window_id)

    def hide(self):
        """隐藏窗口"""
        self.is_visible = False

    def close(self):
        """关闭窗口"""
        self.state = WindowState.CLOSING
        if self._parent:
            self._parent.remove_window(self.window_id)

    def minimize(self):
        """最小化窗口"""
        self.state = WindowState.MINIMIZED
        self.is_visible = False

    def maximize(self):
        """最大化窗口"""
        self.state = WindowState.MAXIMIZED

    def restore(self):
        """还原窗口"""
        self.state = WindowState.NORMAL
        self.is_visible = True

    def toggle_maximize(self):
        """切换最大化状态"""
        if self.state == WindowState.MAXIMIZED:
            self.restore()
        else:
            self.maximize()

    def toggle_fullscreen(self):
        """切换全屏状态"""
        if self.state == WindowState.FULLSCREEN:
            self.state = WindowState.NORMAL
        else:
            self.state = WindowState.FULLSCREEN

    def activate(self):
        """激活窗口 (带到最前)"""
        if self._parent:
            self._parent.activate_window(self.window_id)

    # --------------------------------------------------------------------------
    # 窗口移动和缩放
    # --------------------------------------------------------------------------

    def move_to(self, x: float, y: float):
        """移动窗口到指定位置"""
        self.geometry.x = x
        self.geometry.y = y

    def resize(self, width: float, height: float):
        """调整窗口大小"""
        # 边界检查
        width = max(self.geometry.min_width, min(width, self.geometry.max_width))
        height = max(self.geometry.min_height, min(height, self.geometry.max_height))

        self.geometry.width = width
        self.geometry.height = height

    def start_drag(self, start_x: float, start_y: float):
        """开始拖拽移动"""
        self._is_dragging = True

    def drag(self, delta_x: float, delta_y: float):
        """拖拽移动"""
        if self._is_dragging:
            self.geometry.x += delta_x
            self.geometry.y += delta_y

    def end_drag(self):
        """结束拖拽"""
        self._is_dragging = False

    def start_resize(self, edge: str):
        """开始缩放"""
        self._is_resizing = True
        self._resize_edge = edge

    def resize_by_edge(self, delta_width: float, delta_height: float):
        """按边缘缩放"""
        if not self._is_resizing:
            return

        edge = self._resize_edge

        if "e" in edge:  # 右边缘
            self.geometry.width += delta_width
        if "w" in edge:  # 左边缘
            self.geometry.x += delta_width
            self.geometry.width -= delta_width
        if "s" in edge:  # 下边缘
            self.geometry.height += delta_height
        if "n" in edge:  # 上边缘
            self.geometry.y += delta_height
            self.geometry.height -= delta_height

        # 边界检查
        self.geometry.width = max(
            self.geometry.min_width,
            min(self.geometry.width, self.geometry.max_width)
        )
        self.geometry.height = max(
            self.geometry.min_height,
            min(self.geometry.height, self.geometry.max_height)
        )

    def end_resize(self):
        """结束缩放"""
        self._is_resizing = False
        self._resize_edge = ""

    # --------------------------------------------------------------------------
    # 应用内容加载
    # --------------------------------------------------------------------------

    def set_content(self, content):
        """设置窗口内容"""
        self._content = content

    def get_content(self):
        """获取窗口内容"""
        return self._content

    def load_app(self, module_path: str, system_api: dict = None) -> Any:
        """
        动态加载应用模块

        Args:
            module_path: 模块路径
            system_api: 系统 API

        Returns:
            应用实例
        """
        import importlib

        try:
            module = importlib.import_module(module_path)
            if hasattr(module, "App"):
                self._app_instance = module.App(parent=self)
                if system_api:
                    self._app_instance.system = system_api
                self._content = self._app_instance
                return self._app_instance
        except Exception as e:
            logger.info(f"Failed to load app module {module_path}: {e}")

        return None

    def get_app_instance(self):
        """获取应用实例"""
        return self._app_instance

    # --------------------------------------------------------------------------
    # 序列化
    # --------------------------------------------------------------------------

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "window_id": self.window_id,
            "title": self.title,
            "geometry": {
                "x": self.geometry.x,
                "y": self.geometry.y,
                "width": self.geometry.width,
                "height": self.geometry.height,
            },
            "state": self.state.value,
            "module": self.module,
        }

    @classmethod
    def from_dict(cls, data: dict, parent: "WindowManager" = None) -> "AppWindow":
        """从字典创建"""
        geometry = WindowGeometry(**data.get("geometry", {}))
        window = cls(
            window_id=data.get("window_id"),
            title=data.get("title", ""),
            geometry=geometry,
            module=data.get("module", ""),
            parent=parent
        )
        return window

# ============================================================================
# 窗口管理器
# ============================================================================

class WindowManager:
    """
    窗口管理器

    职责:
    1. 管理所有打开的窗口
    2. 处理窗口的层级关系
    3. 处理窗口的激活、聚焦
    4. 提供窗口的增删改查接口
    """

    def __init__(self):
        # 窗口存储
        self._windows: Dict[str, AppWindow] = {}
        self._z_index_counter = 0

        # 回调
        self._on_window_opened: Optional[Callable] = None
        self._on_window_closed: Optional[Callable] = None
        self._on_window_activated: Optional[Callable] = None

    # --------------------------------------------------------------------------
    # 窗口管理
    # --------------------------------------------------------------------------

    def add_window(self, window: AppWindow) -> str:
        """
        添加窗口

        Args:
            window: AppWindow 实例

        Returns:
            window_id
        """
        window._parent = self
        self._windows[window.window_id] = window
        self._z_index_counter += 1
        window.z_index = self._z_index_counter

        if self._on_window_opened:
            self._on_window_opened(window)

        return window.window_id

    def remove_window(self, window_id: str) -> bool:
        """
        移除窗口

        Args:
            window_id: 窗口 ID

        Returns:
            是否成功
        """
        if window_id in self._windows:
            window = self._windows.pop(window_id)
            if self._on_window_closed:
                self._on_window_closed(window)
            return True
        return False

    def get_window(self, window_id: str) -> Optional[AppWindow]:
        """获取窗口"""
        return self._windows.get(window_id)

    def get_all_windows(self) -> List[AppWindow]:
        """获取所有窗口"""
        return list(self._windows.values())

    def get_visible_windows(self) -> List[AppWindow]:
        """获取所有可见窗口"""
        return [w for w in self._windows.values() if w.is_visible]

    def get_window_count(self) -> int:
        """获取窗口数量"""
        return len(self._windows)

    # --------------------------------------------------------------------------
    # 窗口激活和层级
    # --------------------------------------------------------------------------

    def activate_window(self, window_id: str) -> bool:
        """
        激活窗口 (带到最前)

        Args:
            window_id: 窗口 ID

        Returns:
            是否成功
        """
        if window_id not in self._windows:
            return False

        self._z_index_counter += 1
        self._windows[window_id].z_index = self._z_index_counter

        if self._on_window_activated:
            self._on_window_activated(self._windows[window_id])

        return True

    def get_top_window(self) -> Optional[AppWindow]:
        """获取最顶层的窗口"""
        if not self._windows:
            return None
        return max(self._windows.values(), key=lambda w: w.z_index)

    def get_windows_at_point(self, x: float, y: float) -> List[AppWindow]:
        """获取指定坐标的所有窗口 (从上到下)"""
        windows = []
        for window in self._windows.values():
            if not window.is_visible:
                continue

            geo = window.geometry
            if (geo.x <= x <= geo.x + geo.width and
                geo.y <= y <= geo.y + geo.height):
                windows.append(window)

        # 按 z-index 排序
        windows.sort(key=lambda w: w.z_index)
        return windows

    # --------------------------------------------------------------------------
    # 批量操作
    # --------------------------------------------------------------------------

    def minimize_all(self):
        """最小化所有窗口"""
        for window in self._windows.values():
            window.minimize()

    def close_all(self):
        """关闭所有窗口"""
        window_ids = list(self._windows.keys())
        for window_id in window_ids:
            self.remove_window(window_id)

    def cascade_windows(self, start_x: int = 50, start_y: int = 50, offset: int = 30):
        """层叠窗口"""
        for i, window in enumerate(self._windows.values()):
            window.geometry.x = start_x + i * offset
            window.geometry.y = start_y + i * offset
            window.show()

    def tile_windows(self):
        """平铺窗口 (所有窗口并排显示)"""
        count = len(self._windows)
        if count == 0:
            return

        from screeninfo import get_monitors

        monitors = get_monitors()
        if not monitors:
            return

        monitor = monitors[0]
        total_width = monitor.width
        total_height = monitor.height

        cols = int(count ** 0.5) + 1
        rows = (count + cols - 1) // cols

        width = total_width // cols
        height = total_height // rows

        for i, window in enumerate(self._windows.values()):
            row = i // cols
            col = i % cols
            window.geometry.x = col * width
            window.geometry.y = row * height
            window.geometry.width = width
            window.geometry.height = height
            window.show()

    # --------------------------------------------------------------------------
    # 事件回调
    # --------------------------------------------------------------------------

    def set_on_window_opened(self, callback: Callable[[AppWindow], None]):
        """设置窗口打开回调"""
        self._on_window_opened = callback

    def set_on_window_closed(self, callback: Callable[[AppWindow], None]):
        """设置窗口关闭回调"""
        self._on_window_closed = callback

    def set_on_window_activated(self, callback: Callable[[AppWindow], None]):
        """设置窗口激活回调"""
        self._on_window_activated = callback

    # --------------------------------------------------------------------------
    # 查找
    # --------------------------------------------------------------------------

    def find_by_title(self, title: str) -> List[AppWindow]:
        """按标题查找窗口"""
        return [w for w in self._windows.values() if title in w.title]

    def find_by_module(self, module: str) -> Optional[AppWindow]:
        """按模块查找窗口"""
        for window in self._windows.values():
            if window.module == module:
                return window
        return None

    def is_module_running(self, module: str) -> bool:
        """检查模块是否正在运行"""
        return self.find_by_module(module) is not None