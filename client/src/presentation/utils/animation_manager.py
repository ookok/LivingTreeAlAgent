"""
动画管理器 - 添加UI动画效果

提供现代化的动画效果，包括：
1. 渐入渐出动画
2. 滑动动画
3. 缩放动画
4. 震动动画
"""

from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, pyqtProperty, QObject, QRect
from PyQt6.QtWidgets import QWidget
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)


class AnimationManager:
    """
    动画管理器（单例模式）

    功能：
    1. 管理所有UI动画
    2. 提供便捷的动画函数
    3. 支持动画链
    4. 自动清理动画资源
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 动画列表（防止垃圾回收）
        self._animations = []

        logger.info("动画管理器初始化完成")

    def fade_in(
        self,
        widget: QWidget,
        duration: int = 300,
        callback: Optional[Callable] = None
    ):
        """
        渐入动画

        Args:
            widget: 目标控件
            duration: 动画时长（毫秒）
            callback: 动画结束回调
        """
        widget.setWindowOpacity(0.0)

        animation = QPropertyAnimation(widget, b"windowOpacity")
        animation.setDuration(duration)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        if callback:
            animation.finished.connect(callback)

        animation.start()
        self._animations.append(animation)

        logger.debug(f"渐入动画启动: {widget}")

    def fade_out(
        self,
        widget: QWidget,
        duration: int = 300,
        callback: Optional[Callable] = None
    ):
        """
        渐出动画

        Args:
            widget: 目标控件
            duration: 动画时长（毫秒）
            callback: 动画结束回调
        """
        animation = QPropertyAnimation(widget, b"windowOpacity")
        animation.setDuration(duration)
        animation.setStartValue(widget.windowOpacity())
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        if callback:
            animation.finished.connect(callback)

        animation.start()
        self._animations.append(animation)

        logger.debug(f"渐出动画启动: {widget}")

    def slide_in(
        self,
        widget: QWidget,
        duration: int = 300,
        direction: str = "left",
        callback: Optional[Callable] = None
    ):
        """
        滑入动画

        Args:
            widget: 目标控件
            duration: 动画时长（毫秒）
            direction: 滑动方向 ("left", "right", "up", "down")
            callback: 动画结束回调
        """
        # 获取初始位置
        rect = widget.geometry()
        original_pos = rect.topLeft()

        # 设置起始位置
        if direction == "left":
            rect.moveLeft(rect.left() - rect.width())
        elif direction == "right":
            rect.moveLeft(rect.right())
        elif direction == "up":
            rect.moveTop(rect.top() - rect.height())
        elif direction == "down":
            rect.moveTop(rect.bottom())

        widget.setGeometry(rect)

        # 创建动画
        animation = QPropertyAnimation(widget, b"geometry")
        animation.setDuration(duration)
        animation.setStartValue(rect)
        animation.setEndValue(widget.geometry().__class__(
            original_pos.x(),
            original_pos.y(),
            rect.width(),
            rect.height()
        ))
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        if callback:
            animation.finished.connect(callback)

        animation.start()
        self._animations.append(animation)

        logger.debug(f"滑入动画启动: {widget}, direction={direction}")

    def slide_out(
        self,
        widget: QWidget,
        duration: int = 300,
        direction: str = "left",
        callback: Optional[Callable] = None
    ):
        """
        滑出动画

        Args:
            widget: 目标控件
            duration: 动画时长（毫秒）
            direction: 滑动方向 ("left", "right", "up", "down")
            callback: 动画结束回调
        """
        rect = widget.geometry()
        end_rect = rect.__class__(*rect.getRect())

        # 设置结束位置
        if direction == "left":
            end_rect.moveLeft(end_rect.left() - end_rect.width())
        elif direction == "right":
            end_rect.moveLeft(end_rect.right())
        elif direction == "up":
            end_rect.moveTop(end_rect.top() - end_rect.height())
        elif direction == "down":
            end_rect.moveTop(end_rect.bottom())

        animation = QPropertyAnimation(widget, b"geometry")
        animation.setDuration(duration)
        animation.setStartValue(rect)
        animation.setEndValue(end_rect)
        animation.setEasingCurve(QEasingCurve.Type.InCubic)

        if callback:
            animation.finished.connect(callback)

        animation.start()
        self._animations.append(animation)

        logger.debug(f"滑出动画启动: {widget}, direction={direction}")

    def scale_in(
        self,
        widget: QWidget,
        duration: int = 300,
        callback: Optional[Callable] = None
    ):
        """
        缩放进入动画

        Args:
            widget: 目标控件
            duration: 动画时长（毫秒）
            callback: 动画结束回调
        """
        # 保存原始几何
        original_geometry = widget.geometry()

        # 设置初始状态（缩小）
        center = original_geometry.center()
        small_geometry = original_geometry.__class__(
            center.x() - 10,
            center.y() - 10,
            20,
            20
        )
        widget.setGeometry(small_geometry)

        # 创建动画
        animation = QPropertyAnimation(widget, b"geometry")
        animation.setDuration(duration)
        animation.setStartValue(small_geometry)
        animation.setEndValue(original_geometry)
        animation.setEasingCurve(QEasingCurve.Type.OutBack)

        if callback:
            animation.finished.connect(callback)

        animation.start()
        self._animations.append(animation)

        logger.debug(f"缩放进入动画启动: {widget}")

    def shake(
        self,
        widget: QWidget,
        duration: int = 300,
        intensity: int = 5,
        callback: Optional[Callable] = None
    ):
        """
        震动动画（用于错误提示）

        Args:
            widget: 目标控件
            duration: 动画时长（毫秒）
            intensity: 震动强度（像素）
            callback: 动画结束回调
        """
        rect = widget.geometry()
        original_x = rect.left()

        # 创建关键帧动画
        animation = QPropertyAnimation(widget, b"x")
        animation.setDuration(duration)

        # 关键帧
        animation.setKeyValueAt(0.0, original_x)
        animation.setKeyValueAt(0.2, original_x + intensity)
        animation.setKeyValueAt(0.4, original_x - intensity)
        animation.setKeyValueAt(0.6, original_x + intensity // 2)
        animation.setKeyValueAt(0.8, original_x - intensity // 2)
        animation.setKeyValueAt(1.0, original_x)

        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        if callback:
            animation.finished.connect(callback)

        animation.start()
        self._animations.append(animation)

        logger.debug(f"震动动画启动: {widget}")

    def pulse(
        self,
        widget: QWidget,
        duration: int = 300,
        callback: Optional[Callable] = None
    ):
        """
        脉冲动画（用于提醒）

        Args:
            widget: 目标控件
            duration: 动画时长（毫秒）
            callback: 动画结束回调
        """
        # 保存原始样式
        original_style = widget.styleSheet()

        # 创建样式动画（通过QPropertyAnimation不能直接改样式，需要自定义属性）
        # 这里用简单的显示/隐藏模拟脉冲
        animation = QPropertyAnimation(widget, b"windowOpacity")
        animation.setDuration(duration)
        animation.setStartValue(1.0)
        animation.setEndValue(0.5)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # 反向动画
        animation.finished.connect(lambda: self._reverse_pulse(widget, duration))

        if callback:
            animation.finished.connect(callback)

        animation.start()
        self._animations.append(animation)

        logger.debug(f"脉冲动画启动: {widget}")

    def _reverse_pulse(self, widget: QWidget, duration: int):
        """反向脉冲（内部使用）"""
        animation = QPropertyAnimation(widget, b"windowOpacity")
        animation.setDuration(duration)
        animation.setStartValue(widget.windowOpacity())
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        animation.start()
        self._animations.append(animation)

    def clear_animations(self):
        """清理所有动画"""
        for animation in self._animations:
            animation.stop()
            animation.deleteLater()
        self._animations.clear()
        logger.info("所有动画已清理")


# ========== 便捷函数 ==========

def get_animation_manager() -> AnimationManager:
    """获取动画管理器实例"""
    return AnimationManager()


def fade_in_widget(
    widget: QWidget,
    duration: int = 300,
    callback: Optional[Callable] = None
):
    """渐入控件"""
    get_animation_manager().fade_in(widget, duration, callback)


def fade_out_widget(
    widget: QWidget,
    duration: int = 300,
    callback: Optional[Callable] = None
):
    """渐出控件"""
    get_animation_manager().fade_out(widget, duration, callback)


def slide_in_widget(
    widget: QWidget,
    duration: int = 300,
    direction: str = "left",
    callback: Optional[Callable] = None
):
    """滑入控件"""
    get_animation_manager().slide_in(widget, duration, direction, callback)


def shake_widget(
    widget: QWidget,
    duration: int = 300,
    intensity: int = 5,
    callback: Optional[Callable] = None
):
    """震动控件"""
    get_animation_manager().shake(widget, duration, intensity, callback)


def pulse_widget(
    widget: QWidget,
    duration: int = 300,
    callback: Optional[Callable] = None
):
    """脉冲控件"""
    get_animation_manager().pulse(widget, duration, callback)


# ========== 装饰器 ==========

def with_fade_in(duration: int = 300):
    """
    渐入装饰器

    用法：
    @with_fade_in()
    def show_panel(self):
        self.panel.show()
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            # 假设第一个参数是self，且self有widget属性
            if args and hasattr(args[0], 'widget'):
                fade_in_widget(args[0].widget, duration)
            return result
        return wrapper
    return decorator


def with_shake_on_error(duration: int = 300, intensity: int = 5):
    """
    错误震动装饰器

    用法：
    @with_shake_on_error()
    def login(self):
        if error:
            self.login_button.shake()  # 自动震动
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 假设第一个参数是self，且self有widget属性
                if args and hasattr(args[0], 'widget'):
                    shake_widget(args[0].widget, duration, intensity)
                raise e
        return wrapper
    return decorator
