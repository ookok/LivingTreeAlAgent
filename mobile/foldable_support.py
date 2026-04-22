"""
折叠屏支持模块
=========

支持华为 Mate X 系列、三星 Galaxy Z Fold 系列等折叠屏设备

功能:
- 折叠状态检测
- 铰链角度感知
- 多窗口自适应
- 折叠动画
"""

from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class FoldState(Enum):
    """折叠状态"""
    FULLY_OPEN = "fully_open"       # 完全展开 (180°)
   _HALF_OPEN = "half_open"         # 半开 (90°-179°)
    FLIPPED = "flipped"             # 翻转 (0°-89°)
    COVER_ONLY = "cover_only"       # 仅外屏
    INNER_ONLY = "inner_only"       # 仅内屏


@dataclass
class HingeAngle:
    """铰链角度"""
    angle: float = 180.0            # 角度 (0-180)
    is_supported: bool = False
    update_timestamp: float = 0.0


class FoldableManager:
    """
    折叠屏管理器

    管理折叠屏设备的特殊功能
    """

    def __init__(self):
        self._fold_state = FoldState.FULLY_OPEN
        self._hinge_angle = HingeAngle()
        self._callbacks: Dict[str, Callable] = {}
        self._is_foldable = self._detect_foldable()

    def _detect_foldable(self) -> bool:
        """检测是否支持折叠屏"""
        # 在 Kivy 中可以通过窗口特性检测
        try:
            from kivy.core.window import Window
            # Windows 上的 Surface Duo 等设备
            return hasattr(Window, 'is_foldable') and Window.is_foldable
        except ImportError:
            return False

    def get_fold_state(self) -> FoldState:
        """获取当前折叠状态"""
        if not self._is_foldable:
            return FoldState.FULLY_OPEN

        angle = self._hinge_angle.angle

        if angle >= 170:
            return FoldState.FULLY_OPEN
        elif angle >= 90:
            return FoldState._HALF_OPEN
        else:
            return FoldState.FLIPPED

    def get_hinge_angle(self) -> HingeAngle:
        """获取铰链角度"""
        return self._hinge_angle

    def get_optimal_layout(self) -> Dict[str, Any]:
        """根据折叠状态获取最优布局"""
        state = self.get_fold_state()

        layouts = {
            FoldState.FULLY_OPEN: {
                "mode": "desktop",
                "columns": 8,
                "orientation": "landscape",
                "multi_window": True,
            },
            FoldState._HALF_OPEN: {
                "mode": "tablet",
                "columns": 5,
                "orientation": "portrait",
                "multi_window": True,
            },
            FoldState.FLIPPED: {
                "mode": "mobile",
                "columns": 3,
                "orientation": "portrait",
                "multi_window": False,
            },
        }

        return layouts.get(state, layouts[FoldState.FULLY_OPEN])

    def on_fold_state_change(self, callback: Callable):
        """注册折叠状态变化回调"""
        self._callbacks['fold_state'] = callback

    def on_hinge_angle_change(self, callback: Callable):
        """注册铰链角度变化回调"""
        self._callbacks['hinge_angle'] = callback

    def simulate_fold(self, angle: float):
        """
        模拟折叠（用于测试）

        Args:
            angle: 铰链角度 (0-180)
        """
        self._hinge_angle.angle = angle
        self._hinge_angle.update_timestamp = __import__('time').time()

        new_state = self.get_fold_state()
        if new_state != self._fold_state:
            self._fold_state = new_state
            if 'fold_state' in self._callbacks:
                self._callbacks['fold_state'](new_state)
            if 'hinge_angle' in self._callbacks:
                self._callbacks['hinge_angle'](self._hinge_angle)


# 全局实例
_foldable_manager: Optional[FoldableManager] = None


def get_foldable_manager() -> FoldableManager:
    """获取折叠屏管理器"""
    global _foldable_manager
    if _foldable_manager is None:
        _foldable_manager = FoldableManager()
    return _foldable_manager
