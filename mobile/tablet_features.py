"""
Tablet Features - 平板增强功能
===========================

平板设备的增强功能:
- 分屏模式
- 多窗口支持
- 键盘快捷键
- 手写笔支持
- 外接显示器扩展
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass

try:
    from kivy.core.window import Window
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.floatlayout import FloatLayout
    from kivy.uix.modalview import ModalView
    from kivy.properties import BooleanProperty, ObjectProperty
    KIVY_AVAILABLE = True
except ImportError:
    KIVY_AVAILABLE = False


@dataclass
class WindowState:
    """窗口状态"""
    window_id: str
    title: str
    x: float
    y: float
    width: float
    height: float
    is_maximized: bool
    is_minimized: bool
    z_order: int


class SplitScreenLayout:
    """
    分屏布局

    平板设备支持左右分屏或上下分屏
    """

    ORIENTATION_HORIZONTAL = "horizontal"  # 左右分屏
    ORIENTATION_VERTICAL = "vertical"  # 上下分屏

    def __init__(
        self,
        orientation: str = ORIENTATION_HORIZONTAL,
        split_ratio: float = 0.5
    ):
        self.orientation = orientation
        self.split_ratio = split_ratio
        self.left_panel = None
        self.right_panel = None

    def get_layout_config(self, total_width: float, total_height: float) -> Dict[str, Any]:
        """获取布局配置"""
        if self.orientation == self.ORIENTATION_HORIZONTAL:
            return {
                "left": {
                    "x": 0,
                    "y": 0,
                    "width": total_width * self.split_ratio,
                    "height": total_height,
                },
                "right": {
                    "x": total_width * self.split_ratio,
                    "y": 0,
                    "width": total_width * (1 - self.split_ratio),
                    "height": total_height,
                },
            }
        else:  # vertical
            return {
                "top": {
                    "x": 0,
                    "y": total_height * (1 - self.split_ratio),
                    "width": total_width,
                    "height": total_height * self.split_ratio,
                },
                "bottom": {
                    "x": 0,
                    "y": 0,
                    "width": total_width,
                    "height": total_height * (1 - self.split_ratio),
                },
            }


class MultiWindowManager:
    """
    多窗口管理器

    支持在大平板上同时打开多个应用窗口
    """

    def __init__(self, max_windows: int = 4):
        self.max_windows = max_windows
        self.windows: Dict[str, WindowState] = {}
        self._window_counter = 0

    def create_window(
        self,
        title: str,
        width: float = 400,
        height: float = 300,
        x: float = None,
        y: float = None
    ) -> str:
        """创建新窗口"""
        if len(self.windows) >= self.max_windows:
            raise Exception(f"Maximum windows ({self.max_windows}) reached")

        self._window_counter += 1
        window_id = f"window_{self._window_counter}"

        # 默认位置：级联排列
        if x is None:
            x = 50 + (self._window_counter - 1) * 30
        if y is None:
            y = 50 + (self._window_counter - 1) * 30

        self.windows[window_id] = WindowState(
            window_id=window_id,
            title=title,
            x=x,
            y=y,
            width=width,
            height=height,
            is_maximized=False,
            is_minimized=False,
            z_order=self._window_counter
        )

        return window_id

    def close_window(self, window_id: str) -> bool:
        """关闭窗口"""
        if window_id in self.windows:
            del self.windows[window_id]
            return True
        return False

    def maximize_window(self, window_id: str) -> bool:
        """最大化窗口"""
        if window_id in self.windows:
            self.windows[window_id].is_maximized = True
            return True
        return False

    def minimize_window(self, window_id: str) -> bool:
        """最小化窗口"""
        if window_id in self.windows:
            self.windows[window_id].is_minimized = True
            return True
        return False

    def restore_window(self, window_id: str) -> bool:
        """还原窗口"""
        if window_id in self.windows:
            self.windows[window_id].is_minimized = False
            self.windows[window_id].is_maximized = False
            return True
        return False

    def bring_to_front(self, window_id: str) -> bool:
        """将窗口置顶"""
        if window_id in self.windows:
            max_z = max(w.z_order for w in self.windows.values())
            self.windows[window_id].z_order = max_z + 1
            return True
        return False

    def get_windows_by_z_order(self) -> List[WindowState]:
        """按Z轴顺序获取窗口"""
        return sorted(self.windows.values(), key=lambda w: w.z_order)


class KeyboardShortcuts:
    """
    键盘快捷键管理器

    支持物理键盘快捷键
    """

    # 默认快捷键映射
    DEFAULT_SHORTCUTS = {
        # 全局
        "ctrl+s": "save",
        "ctrl+z": "undo",
        "ctrl+y": "redo",
        "ctrl+c": "copy",
        "ctrl+v": "paste",
        "ctrl+x": "cut",
        "ctrl+a": "select_all",
        "ctrl+f": "find",
        "ctrl+q": "quit",

        # 导航
        "ctrl+tab": "next_tab",
        "ctrl+shift+tab": "prev_tab",
        "ctrl+w": "close_tab",
        "ctrl+t": "new_tab",
        "ctrl+n": "new_window",

        # 平板特定
        "ctrl+/": "toggle_sidebar",
        "ctrl+shift+f": "toggle_fullscreen",
        "f11": "fullscreen",
        "f5": "refresh",
    }

    def __init__(self):
        self._shortcuts = dict(self.DEFAULT_SHORTCUTS)
        self._handlers: Dict[str, Callable] = {}
        self._enabled = True

    def register_handler(self, action: str, handler: Callable):
        """注册动作处理器"""
        self._handlers[action] = handler

    def unregister_handler(self, action: str):
        """注销动作处理器"""
        if action in self._handlers:
            del self._handlers[action]

    def handle_key(self, key_string: str) -> bool:
        """
        处理按键

        Args:
            key_string: 按键字符串，如 "ctrl+s"

        Returns:
            True if handled, False otherwise
        """
        if not self._enabled:
            return False

        key_string = key_string.lower()

        if key_string in self._shortcuts:
            action = self._shortcuts[key_string]

            if action in self._handlers:
                self._handlers[action]()
                return True

        return False

    def add_shortcut(self, key: str, action: str):
        """添加快捷键"""
        self._shortcuts[key.lower()] = action

    def remove_shortcut(self, key: str):
        """移除快捷键"""
        if key.lower() in self._shortcuts:
            del self._shortcuts[key.lower()]

    def enable(self):
        """启用快捷键"""
        self._enabled = True

    def disable(self):
        """禁用快捷键"""
        self._enabled = False


class StylusSupport:
    """
    手写笔支持

    支持压感、手写识别
    """

    def __init__(self):
        self._stylus_detected = False
        self._pressure_sensitivity = 1.0
        self._handlers: Dict[str, Callable] = {}

    def detect_stylus(self) -> bool:
        """检测手写笔"""
        # Kivy中通过Window属性检测
        if KIVY_AVAILABLE:
            self._stylus_detected = hasattr(Window, 'stencils')
        return self._stylus_detected

    def get_pressure(self) -> float:
        """获取压感值 (0.0 - 1.0)"""
        # 需要绑定到实际的触摸事件
        return self._pressure_sensitivity

    def register_draw_handler(self, handler: Callable):
        """注册绘图处理器"""
        self._handlers['draw'] = handler

    def register_gesture_handler(self, handler: Callable):
        """注册手势处理器"""
        self._handlers['gesture'] = handler

    def handle_draw(self, x: float, y: float, pressure: float):
        """处理绘图输入"""
        if 'draw' in self._handlers:
            self._handlers['draw'](x, y, pressure)

    def handle_gesture(self, gesture_type: str, points: List[tuple]):
        """处理手势输入"""
        if 'gesture' in self._handlers:
            self._handlers['gesture'](gesture_type, points)


class ExternalDisplaySupport:
    """
    外接显示器支持

    支持扩展桌面模式
    """

    def __init__(self):
        self._displays: List[Dict[str, Any]] = []
        self._primary_display = 0
        self._extended_mode = False

    def detect_displays(self) -> List[Dict[str, Any]]:
        """检测外接显示器"""
        if KIVY_AVAILABLE:
            # Kivy中获取显示列表
            # 这里简化实现
            self._displays = [
                {
                    "id": 0,
                    "name": "Primary Display",
                    "width": Window.width,
                    "height": Window.height,
                    "is_primary": True,
                }
            ]
        return self._displays

    def set_extended_mode(self, enabled: bool):
        """设置扩展模式"""
        self._extended_mode = enabled

    def get_optimal_window_position(
        self,
        window_width: float,
        window_height: float,
        target_display: int = None
    ) -> tuple:
        """获取窗口在外接显示器上的最佳位置"""
        if not self._displays:
            self.detect_displays()

        if target_display is None:
            # 使用外接显示器（如果有）
            target_display = self._primary_display
            for i, display in enumerate(self._displays):
                if not display.get("is_primary", False):
                    target_display = i
                    break

        display = self._displays[target_display]

        # 居中位置
        x = (display["width"] - window_width) / 2
        y = (display["height"] - window_height) / 2

        return x, y


# ==================== 平板增强管理器 ====================

class TabletEnhancementManager:
    """
    平板增强管理器

    统一管理所有平板增强功能
    """

    def __init__(self):
        self.split_screen = SplitScreenLayout()
        self.multi_window = MultiWindowManager(max_windows=4)
        self.keyboard = KeyboardShortcuts()
        self.stylus = StylusSupport()
        self.external_display = ExternalDisplaySupport()

        self._enabled_features: set = set()

    def enable_tablet_features(self, device_type: str):
        """
        根据设备类型启用相应功能

        Args:
            device_type: tablet/large_tablet
        """
        if device_type in ('tablet', 'large_tablet'):
            self._enabled_features.add('split_screen')
            self._enabled_features.add('keyboard_shortcuts')

            if device_type == 'large_tablet':
                self._enabled_features.add('multi_window')
                self._enabled_features.add('external_display')

    def is_feature_enabled(self, feature: str) -> bool:
        """检查功能是否启用"""
        return feature in self._enabled_features

    def get_split_screen_layout(
        self,
        orientation: str = "horizontal",
        split_ratio: float = 0.5
    ):
        """获取分屏布局配置"""
        if not self.is_feature_enabled('split_screen'):
            return None

        self.split_screen.orientation = orientation
        self.split_screen.split_ratio = split_ratio

        return self.split_screen.get_layout_config(
            Window.width,
            Window.height
        )