"""
Foldable Support - 折叠屏设备支持
=============================

折叠屏设备的特殊处理:
- 屏幕状态变化（折叠/展开）
- 双屏模式
- 屏幕角度检测
- 自适应布局切换
"""

from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum

try:
    from kivy.core.window import Window
    from kivy.properties import ObjectProperty
    from kivy.uix.boxlayout import BoxLayout
    KIVY_AVAILABLE = True
except ImportError:
    KIVY_AVAILABLE = False


class FoldState(Enum):
    """折叠状态"""
    FLAT = "flat"           # 完全展开
    HALF_OPENED = "half"    # 半开（帐篷/笔记本模式）
    FOLDED = "folded"        # 折叠状态
    UNKNOWN = "unknown"


class ScreenOrientation(Enum):
    """屏幕方向"""
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    SQUARE = "square"


@dataclass
class FoldableInfo:
    """折叠屏信息"""
    is_foldable: bool = False
    fold_state: FoldState = FoldState.UNKNOWN
    screen_count: int = 1
    hinge_angle: float = 0.0  # 铰链角度
    hinge_position: str = ""  # 铰链位置 (top/bottom/left/right)
    screen_width: float = 0
    screen_height: float = 0


class FoldableDetector:
    """
    折叠屏检测器

    检测设备是否为折叠屏及其状态
    """

    def __init__(self):
        self._info = FoldableInfo()
        self._listeners: List[Callable] = []

    def detect(self) -> FoldableInfo:
        """
        检测折叠屏信息

        Returns:
            FoldableInfo: 折叠屏信息
        """
        if KIVY_AVAILABLE:
            width, height = Window.size

            # 根据屏幕尺寸和比例判断是否为折叠屏
            # 折叠屏通常有较大的宽高比或特殊的尺寸
            aspect_ratio = max(width, height) / min(width, height)

            # 检测是否为折叠设备
            # 这需要实际设备的API支持，这里是简化实现
            self._info.is_foldable = False
            self._info.screen_count = 1
            self._info.screen_width = width
            self._info.screen_height = height

            # 检测折叠状态
            if hasattr(Window, 'hinge'):
                hinge = Window.hinge
                if hinge:
                    self._info.is_foldable = True
                    self._info.hinge_angle = hinge.get('angle', 0)
                    self._info.hinge_position = hinge.get('position', '')

                    # 根据铰链角度判断折叠状态
                    angle = self._info.hinge_angle
                    if angle < 10:
                        self._info.fold_state = FoldState.FLAT
                    elif angle < 170:
                        self._info.fold_state = FoldState.HALF_OPENED
                    else:
                        self._info.fold_state = FoldState.FOLDED

        return self._info

    def add_listener(self, callback: Callable):
        """添加状态变化监听器"""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable):
        """移除监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self, old_state: FoldState, new_state: FoldState):
        """通知监听器"""
        for callback in self._listeners:
            try:
                callback(old_state, new_state, self._info)
            except Exception as e:
                print(f"[FoldableDetector] Listener error: {e}")


class FoldableLayoutManager:
    """
    折叠屏布局管理器

    根据折叠状态自动调整布局
    """

    # 布局模式
    MODE_SINGLE = "single"       # 单屏模式
    MODE_DUAL = "dual"          # 双屏模式
    MODE_TENT = "tent"          # 帐篷模式
    MODE_TABLETOP = "tabletop"  # 笔记本模式

    def __init__(self):
        self.detector = FoldableDetector()
        self._current_mode = self.MODE_SINGLE
        self._listeners: List[Callable] = []

    def get_layout_mode(self, info: FoldableInfo = None) -> str:
        """
        获取布局模式

        Args:
            info: 折叠屏信息，如果为None则自动检测

        Returns:
            str: 布局模式
        """
        if info is None:
            info = self.detector.detect()

        if not info.is_foldable:
            return self.MODE_SINGLE

        if info.fold_state == FoldState.FLAT:
            return self.MODE_SINGLE
        elif info.fold_state == FoldState.HALF_OPENED:
            # 根据铰链角度判断具体模式
            if info.hinge_position in ('top', 'bottom'):
                return self.MODE_TABLETOP  # 水平铰链=笔记本模式
            else:
                return self.MODE_TENT  # 垂直铰链=帐篷模式
        else:  # FOLDED
            return self.MODE_DUAL

    def get_layout_config(
        self,
        total_width: float,
        total_height: float,
        mode: str = None
    ) -> Dict[str, Any]:
        """
        获取布局配置

        Args:
            total_width: 总宽度
            total_height: 总高度
            mode: 布局模式

        Returns:
            Dict: 布局配置
        """
        if mode is None:
            mode = self._current_mode

        configs = {
            self.MODE_SINGLE: self._single_screen_config(total_width, total_height),
            self.MODE_DUAL: self._dual_screen_config(total_width, total_height),
            self.MODE_TENT: self._tent_mode_config(total_width, total_height),
            self.MODE_TABLETOP: self._tabletop_mode_config(total_width, total_height),
        }

        return configs.get(mode, configs[self.MODE_SINGLE])

    def _single_screen_config(
        self,
        width: float,
        height: float
    ) -> Dict[str, Any]:
        """单屏配置"""
        return {
            "mode": self.MODE_SINGLE,
            "screens": [
                {
                    "id": 0,
                    "x": 0,
                    "y": 0,
                    "width": width,
                    "height": height,
                }
            ]
        }

    def _dual_screen_config(
        self,
        width: float,
        height: float
    ) -> Dict[str, Any]:
        """双屏配置（折叠状态）"""
        half_width = width / 2
        return {
            "mode": self.MODE_DUAL,
            "screens": [
                {
                    "id": 0,
                    "x": 0,
                    "y": 0,
                    "width": half_width,
                    "height": height,
                },
                {
                    "id": 1,
                    "x": half_width,
                    "y": 0,
                    "width": half_width,
                    "height": height,
                }
            ]
        }

    def _tent_mode_config(
        self,
        width: float,
        height: float
    ) -> Dict[str, Any]:
        """帐篷模式配置（倒V形）"""
        # 帐篷模式下下半部分朝上
        return {
            "mode": self.MODE_TENT,
            "screens": [
                {
                    "id": 0,
                    "x": 0,
                    "y": 0,
                    "width": width,
                    "height": height,
                    "rotation": 0,  # 可根据需要旋转
                }
            ],
            "interaction_hint": "tent_mode",  # 提示用户使用手势控制
        }

    def _tabletop_mode_config(
        self,
        width: float,
        height: float
    ) -> Dict[str, Any]:
        """笔记本模式配置"""
        half_height = height / 2
        return {
            "mode": self.MODE_TABLETOP,
            "screens": [
                {
                    "id": 0,
                    "x": 0,
                    "y": 0,
                    "width": width,
                    "height": half_height,
                    "role": "display",  # 显示区域
                },
                {
                    "id": 1,
                    "x": 0,
                    "y": half_height,
                    "width": width,
                    "height": half_height,
                    "role": "input",  # 输入区域
                }
            ]
        }

    def switch_mode(self, new_mode: str):
        """切换布局模式"""
        if new_mode != self._current_mode:
            old_mode = self._current_mode
            self._current_mode = new_mode
            self._notify_listeners(old_mode, new_mode)

    def add_listener(self, callback: Callable):
        """添加模式变化监听器"""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def _notify_listeners(self, old_mode: str, new_mode: str):
        """通知监听器"""
        for callback in self._listeners:
            try:
                callback(old_mode, new_mode)
            except Exception as e:
                print(f"[FoldableLayoutManager] Listener error: {e}")


class FoldableAdaptiveLayout(BoxLayout if KIVY_AVAILABLE else object):
    """
    折叠屏自适应布局组件

    根据折叠状态自动切换布局
    """

    if KIVY_AVAILABLE:
        config = ObjectProperty(None)

    def __init__(self, **kwargs):
        if KIVY_AVAILABLE:
            super().__init__(**kwargs)

        self.foldable_detector = FoldableDetector()
        self.layout_manager = FoldableLayoutManager()

        # 监听窗口变化
        if KIVY_AVAILABLE:
            Window.bind(size=self._on_window_changed)

        # 绑定监听器
        self.foldable_detector.add_listener(self._on_fold_state_changed)
        self.layout_manager.add_listener(self._on_layout_mode_changed)

    def _on_window_changed(self, window, size):
        """窗口大小变化"""
        info = self.foldable_detector.detect()
        new_mode = self.layout_manager.get_layout_mode(info)

        if new_mode != self.layout_manager._current_mode:
            self.layout_manager.switch_mode(new_mode)

    def _on_fold_state_changed(
        self,
        old_state: FoldState,
        new_state: FoldState,
        info: FoldableInfo
    ):
        """折叠状态变化"""
        new_mode = self.layout_manager.get_layout_mode(info)

        if new_mode != self.layout_manager._current_mode:
            self.layout_manager.switch_mode(new_mode)

    def _on_layout_mode_changed(self, old_mode: str, new_mode: str):
        """布局模式变化"""
        # 子类可以重写此方法来实现具体的布局切换
        self._apply_layout(new_mode)

    def _apply_layout(self, mode: str):
        """应用布局"""
        if KIVY_AVAILABLE:
            config = self.layout_manager.get_layout_config(
                Window.width,
                Window.height,
                mode
            )
            self.config = config


# ==================== 设备能力检测 ====================

class DeviceCapabilityDetector:
    """
    设备能力检测

    检测设备支持的特性和能力
    """

    # 能力定义
    CAPABILITIES = {
        # 折叠相关
        "foldable": False,
        "multi_screen": False,
        "hinge_angle": False,

        # 输入相关
        "touch": True,
        "multi_touch": True,
        "stylus": False,
        "keyboard": False,
        "mouse": False,

        # 显示相关
        "high_dpi": False,
        "hdr": False,
        "wide_color": False,

        # 网络相关
        "5g": False,
        "wifi_6": False,
        "bluetooth_5": False,

        # 传感器
        "gyroscope": False,
        "accelerometer": False,
        "gps": False,
        "nfc": False,
    }

    @classmethod
    def detect_all(cls) -> Dict[str, bool]:
        """
        检测所有能力

        Returns:
            Dict[str, bool]: 能力字典
        """
        capabilities = dict(cls.CAPABILITIES)

        if KIVY_AVAILABLE:
            # 触摸检测
            capabilities["touch"] = True
            capabilities["multi_touch"] = True

            # 平台检测
            import platform
            system = platform.system()

            if system == "Android":
                capabilities = cls._detect_android_capabilities(capabilities)
            elif system == "iOS":
                capabilities = cls._detect_ios_capabilities(capabilities)
            elif system == "Windows":
                capabilities = cls._detect_windows_capabilities(capabilities)
            elif system == "Linux":
                capabilities = cls._detect_linux_capabilities(capabilities)

        return capabilities

    @classmethod
    def _detect_android_capabilities(cls, caps: Dict[str, bool]) -> Dict[str, bool]:
        """检测Android设备能力"""
        try:
            import subprocess
            result = subprocess.check_output(
                ["getprop", "ro.product.model"],
                stderr=subprocess.DEVNULL
            ).decode().strip()

            # 检查是否为折叠屏
            if "fold" in result.lower() or "flip" in result.lower():
                caps["foldable"] = True

            # 检查手写笔支持 (Samsung S Pen等)
            if "samsung" in result.lower():
                caps["stylus"] = True

        except:
            pass

        # 通用Android能力
        caps["gyroscope"] = True
        caps["accelerometer"] = True
        caps["gps"] = True
        caps["nfc"] = True

        return caps

    @classmethod
    def _detect_ios_capabilities(cls, caps: Dict[str, bool]) -> Dict[str, bool]:
        """检测iOS设备能力"""
        # iPad Pro支持键盘和Apple Pencil
        caps["stylus"] = True
        caps["keyboard"] = True

        return caps

    @classmethod
    def _detect_windows_capabilities(cls, caps: Dict[str, bool]) -> Dict[str, bool]:
        """检测Windows设备能力"""
        caps["keyboard"] = True
        caps["mouse"] = True

        return caps

    @classmethod
    def _detect_linux_capabilities(cls, caps: Dict[str, bool]) -> Dict[str, bool]:
        """检测Linux设备能力"""
        caps["keyboard"] = True
        caps["mouse"] = True

        return caps

    @classmethod
    def is_capable(cls, capability: str) -> bool:
        """检查特定能力"""
        caps = cls.detect_all()
        return caps.get(capability, False)

    @classmethod
    def get_recommended_features(cls) -> List[str]:
        """获取推荐功能列表"""
        caps = cls.detect_all()
        features = []

        # 根据能力推荐功能
        if caps.get("foldable"):
            features.extend(["dual_screen_mode", "tent_mode", "tabletop_mode"])

        if caps.get("multi_touch"):
            features.extend(["gesture_control", "pinch_zoom"])

        if caps.get("stylus"):
            features.extend(["handwriting", "drawing", "pressure_sensitivity"])

        if caps.get("keyboard"):
            features.extend(["keyboard_shortcuts", "external_keyboard"])

        if caps.get("mouse"):
            features.extend(["right_click", "hover_states"])

        return features