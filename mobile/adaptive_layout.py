"""
Adaptive Layout - 移动端自适应布局
================================

Kivy移动端自适应布局系统

功能:
- 设备类型检测 (phone/phablet/tablet/large_tablet)
- 横竖屏自适应
- 响应式网格布局
- 动态主题
"""

import os
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass

try:
    from kivy.metrics import dp, sp
    from kivy.core.window import Window
    from kivy.properties import ObjectProperty, StringProperty, BooleanProperty
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.floatlayout import FloatLayout
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.widget import Widget
    from kivy.clock import Clock
    from kivy.animation import Animation
    KIVY_AVAILABLE = True
except ImportError:
    KIVY_AVAILABLE = False
    print("Kivy not available, mobile adaptive layout will not be functional")


@dataclass
class LayoutConfig:
    """布局配置"""
    device_type: str = "phone"  # phone/phablet/tablet/large_tablet
    orientation: str = "portrait"  # portrait/landscape
    grid_cols: int = 3
    icon_size: float = 56
    font_size: int = 14
    spacing: float = 10
    padding: float = 16
    mode: str = "mobile"  # mobile/tablet/desktop


class DeviceDetector:
    """
    设备检测器

    根据屏幕尺寸和DPI判断设备类型
    """

    # 设备类型阈值
    THRESHOLDS = {
        "phone": {"max_width": 600, "max_height": 900},
        "phablet": {"max_width": 900, "max_height": 1200},
        "tablet": {"max_width": 1200, "max_height": 1600},
        "large_tablet": {"max_width": float("inf"), "max_height": float("inf")},
    }

    # 每dp对应的像素数（根据DPI调整）
    DPI_SCALES = {
        "low": 0.8,
        "medium": 1.0,
        "high": 1.5,
        "ultra": 2.0,
    }

    @classmethod
    def detect(cls, width: int = None, height: int = None, dpi: int = None) -> str:
        """
        检测设备类型

        Returns:
            str: phone/phablet/tablet/large_tablet
        """
        if width is None or height is None:
            width, height = Window.size

        # 确保宽度小于高度（ portrait）
        if width > height:
            width, height = height, width

        # 根据尺寸判断
        if width < 600:
            return "phone"
        elif width < 900:
            return "phablet"
        elif width < 1200:
            return "tablet"
        else:
            return "large_tablet"

    @classmethod
    def get_dpi_scale(cls, dpi: int = None) -> float:
        """获取DPI缩放因子"""
        if dpi is None:
            dpi = Window.dpi

        if dpi < 120:
            return cls.DPI_SCALES["low"]
        elif dpi < 240:
            return cls.DPI_SCALES["medium"]
        elif dpi < 360:
            return cls.DPI_SCALES["high"]
        else:
            return cls.DPI_SCALES["ultra"]

    @classmethod
    def get_orientation(cls, width: int = None, height: int = None) -> str:
        """获取屏幕方向"""
        if width is None or height is None:
            width, height = Window.size

        return "landscape" if width > height else "portrait"


class LayoutConfigFactory:
    """
    布局配置工厂

    根据设备类型生成对应的布局配置
    """

    @staticmethod
    def get_config(device_type: str, orientation: str = "portrait") -> LayoutConfig:
        """获取设备对应的布局配置"""

        configs = {
            # 手机配置
            "phone": {
                "portrait": LayoutConfig(
                    device_type="phone",
                    orientation="portrait",
                    grid_cols=3,
                    icon_size=56,
                    font_size=14,
                    spacing=dp(10),
                    padding=dp(16),
                    mode="mobile"
                ),
                "landscape": LayoutConfig(
                    device_type="phone",
                    orientation="landscape",
                    grid_cols=5,
                    icon_size=48,
                    font_size=13,
                    spacing=dp(8),
                    padding=dp(12),
                    mode="mobile"
                ),
            },

            # 大屏手机/小平板配置
            "phablet": {
                "portrait": LayoutConfig(
                    device_type="phablet",
                    orientation="portrait",
                    grid_cols=4,
                    icon_size=64,
                    font_size=15,
                    spacing=dp(12),
                    padding=dp(16),
                    mode="mobile"
                ),
                "landscape": LayoutConfig(
                    device_type="phablet",
                    orientation="landscape",
                    grid_cols=6,
                    icon_size=56,
                    font_size=14,
                    spacing=dp(10),
                    padding=dp(16),
                    mode="tablet"
                ),
            },

            # 平板配置
            "tablet": {
                "portrait": LayoutConfig(
                    device_type="tablet",
                    orientation="portrait",
                    grid_cols=5,
                    icon_size=72,
                    font_size=16,
                    spacing=dp(15),
                    padding=dp(20),
                    mode="tablet"
                ),
                "landscape": LayoutConfig(
                    device_type="tablet",
                    orientation="landscape",
                    grid_cols=7,
                    icon_size=80,
                    font_size=17,
                    spacing=dp(18),
                    padding=dp(24),
                    mode="tablet"
                ),
            },

            # 大平板/折叠屏展开配置
            "large_tablet": {
                "portrait": LayoutConfig(
                    device_type="large_tablet",
                    orientation="portrait",
                    grid_cols=5,
                    icon_size=80,
                    font_size=17,
                    spacing=dp(18),
                    padding=dp(24),
                    mode="desktop"
                ),
                "landscape": LayoutConfig(
                    device_type="large_tablet",
                    orientation="landscape",
                    grid_cols=8,
                    icon_size=88,
                    font_size=18,
                    spacing=dp(20),
                    padding=dp(28),
                    mode="desktop"
                ),
            },
        }

        return configs.get(device_type, configs["phone"]).get(orientation, configs["phone"]["portrait"])


class AdaptiveGridLayout(GridLayout):
    """
    自适应网格布局

    根据设备类型自动调整列数和间距
    """

    config = ObjectProperty(None)
    device_type = StringProperty("phone")
    orientation = StringProperty("portrait")

    def __init__(self, **kwargs):
        self._config = None
        super().__init__(**kwargs)

        # 监听窗口大小变化
        Window.bind(size=self._on_window_size_changed)

        # 初始化
        Clock.schedule_once(self._init_layout, 0)

    def _init_layout(self, *args):
        """初始化布局"""
        self._update_device_type()
        self._apply_config()

    def _on_window_size_changed(self, window, size):
        """窗口大小变化"""
        self._update_device_type()
        self._apply_config()

    def _update_device_type(self):
        """更新设备类型"""
        new_device = DeviceDetector.detect()
        new_orientation = DeviceDetector.get_orientation()

        if new_device != self.device_type or new_orientation != self.orientation:
            self.device_type = new_device
            self.orientation = new_orientation

    def _apply_config(self):
        """应用布局配置"""
        self.config = LayoutConfigFactory.get_config(self.device_type, self.orientation)

        if self.config:
            self.cols = self.config.grid_cols
            self.spacing = self.config.spacing
            self.padding = self.config.padding


class AdaptiveBoxLayout(BoxLayout):
    """
    自适应盒子布局

    根据设备类型自动调整方向和间距
    """

    config = ObjectProperty(None)

    def __init__(self, **kwargs):
        self._config = None
        super().__init__(**kwargs)

        Window.bind(size=self._on_window_size_changed)
        Clock.schedule_once(self._init_layout, 0)

    def _init_layout(self, *args):
        """初始化布局"""
        self._update_layout()

    def _on_window_size_changed(self, window, size):
        """窗口大小变化"""
        self._update_layout()

    def _update_layout(self):
        """更新布局"""
        device_type = DeviceDetector.detect()
        orientation = DeviceDetector.get_orientation()
        self.config = LayoutConfigFactory.get_config(device_type, orientation)

        if self.config:
            # 手机竖屏用垂直布局，横屏用水平布局
            if self.config.device_type == "phone":
                self.orientation = "vertical" if orientation == "portrait" else "horizontal"
            else:
                # 平板及以上使用配置的mode
                self.orientation = "horizontal"  # 默认水平

            self.spacing = self.config.spacing
            self.padding = self.config.padding


class ResponsiveGrid:
    """
    响应式网格工具类

    提供响应式网格计算的辅助方法
    """

    @staticmethod
    def calculate_grid_cols(device_type: str, orientation: str, available_width: float) -> int:
        """
        计算网格列数

        Args:
            device_type: 设备类型
            orientation: 屏幕方向
            available_width: 可用宽度

        Returns:
            int: 列数
        """
        base_configs = {
            "phone": {"portrait": 3, "landscape": 5},
            "phablet": {"portrait": 4, "landscape": 6},
            "tablet": {"portrait": 5, "landscape": 7},
            "large_tablet": {"portrait": 5, "landscape": 8},
        }

        base_cols = base_configs.get(device_type, base_configs["phone"]).get(orientation, 3)

        # 根据可用宽度调整
        if available_width < dp(300):
            return max(2, base_cols - 1)
        elif available_width > dp(800):
            return base_cols + 1

        return base_cols

    @staticmethod
    def calculate_icon_size(device_type: str, grid_cols: int, available_width: float) -> float:
        """
        计算图标大小

        Args:
            device_type: 设备类型
            grid_cols: 列数
            available_width: 可用宽度

        Returns:
            float: 图标大小(dp)
        """
        # 计算每个格子的大小
        cell_size = available_width / grid_cols

        # 图标占格子的80%
        icon_size = cell_size * 0.8

        # 限制最大最小值
        max_sizes = {
            "phone": dp(72),
            "phablet": dp(80),
            "tablet": dp(96),
            "large_tablet": dp(112),
        }

        min_size = dp(48)

        return max(min_size, min(icon_size, max_sizes.get(device_type, dp(72))))

    @staticmethod
    def get_spacing(device_type: str, orientation: str) -> float:
        """获取间距"""
        spacing_map = {
            ("phone", "portrait"): dp(10),
            ("phone", "landscape"): dp(8),
            ("phablet", "portrait"): dp(12),
            ("phablet", "landscape"): dp(10),
            ("tablet", "portrait"): dp(15),
            ("tablet", "landscape"): dp(18),
            ("large_tablet", "portrait"): dp(18),
            ("large_tablet", "landscape"): dp(20),
        }

        return spacing_map.get((device_type, orientation), dp(10))


class AdaptiveLabel:
    """
    自适应标签工具类

    根据设备类型返回合适的字体大小
    """

    @staticmethod
    def get_font_size(device_type: str, text_type: str = "body") -> float:
        """
        获取字体大小

        Args:
            device_type: 设备类型
            text_type: 文本类型 (title/subtitle/body/caption)

        Returns:
            float: 字体大小(sp)
        """
        base_sizes = {
            "phone": {"title": 20, "subtitle": 16, "body": 14, "caption": 12},
            "phablet": {"title": 22, "subtitle": 18, "body": 15, "caption": 13},
            "tablet": {"title": 24, "subtitle": 20, "body": 16, "caption": 14},
            "large_tablet": {"title": 26, "subtitle": 22, "body": 17, "caption": 15},
        }

        sizes = base_sizes.get(device_type, base_sizes["phone"])
        return sp(sizes.get(text_type, sizes["body"]))


# ==================== 设备适配管理器 ====================

class AdaptiveManager:
    """
    自适应管理器

    管理全局的设备适配状态
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._device_type = "phone"
        self._orientation = "portrait"
        self._config = LayoutConfigFactory.get_config("phone", "portrait")
        self._listeners: list = []

        # 监听窗口变化
        Window.bind(size=self._on_window_changed)

        # 初始化
        self._update_device_info()

    def _on_window_changed(self, *args):
        """窗口变化处理"""
        self._update_device_info()
        self._notify_listeners()

    def _update_device_info(self):
        """更新设备信息"""
        self._device_type = DeviceDetector.detect()
        self._orientation = DeviceDetector.get_orientation()
        self._config = LayoutConfigFactory.get_config(self._device_type, self._orientation)

    def _notify_listeners(self):
        """通知监听器"""
        for callback in self._listeners:
            try:
                callback(self._device_type, self._orientation, self._config)
            except Exception as e:
                print(f"[AdaptiveManager] Listener error: {e}")

    def add_listener(self, callback: Callable):
        """添加监听器"""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable):
        """移除监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)

    @property
    def device_type(self) -> str:
        """当前设备类型"""
        return self._device_type

    @property
    def orientation(self) -> str:
        """当前屏幕方向"""
        return self._orientation

    @property
    def config(self) -> LayoutConfig:
        """当前布局配置"""
        return self._config

    @property
    def is_mobile(self) -> bool:
        """是否为移动设备"""
        return self._device_type in ("phone", "phablet")

    @property
    def is_tablet(self) -> bool:
        """是否为平板设备"""
        return self._device_type in ("tablet", "large_tablet")

    @property
    def is_landscape(self) -> bool:
        """是否为横屏"""
        return self._orientation == "landscape"


# 全局管理器实例
def get_adaptive_manager() -> AdaptiveManager:
    """获取自适应管理器"""
    return AdaptiveManager()


# ==================== Kivy 特性检测 ====================

class FeatureDetector:
    """
    设备特性检测

    检测设备特性如键盘、手写笔等
    """

    @staticmethod
    def has_keyboard() -> bool:
        """是否有物理键盘"""
        # 平板连接键盘时
        return Window.builtin_keyboard or False

    @staticmethod
    def has_stylus() -> bool:
        """是否有手写笔"""
        # Android平板支持S Pen等
        return hasattr(Window, 'stencils') and Window.stencils

    @staticmethod
    def has_multitouch() -> bool:
        """是否支持多点触控"""
        return True  # Kivy默认支持

    @staticmethod
    def supports_split_screen() -> bool:
        """是否支持分屏"""
        return FeatureDetector.has_multitouch()

    @staticmethod
    def get_device_capabilities() -> Dict[str, bool]:
        """获取设备能力"""
        return {
            "keyboard": FeatureDetector.has_keyboard(),
            "stylus": FeatureDetector.has_stylus(),
            "multitouch": FeatureDetector.has_multitouch(),
            "split_screen": FeatureDetector.supports_split_screen(),
        }