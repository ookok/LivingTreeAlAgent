"""
Toast 通知系统
Toast Notification System

右下角冒泡提示，支持：
- 自动消失
- 多种类型（成功/警告/错误/信息）
- 点击回调
- 队列管理
- 可开关设置
"""

import sys
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QRect, QPoint
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QGraphicsOpacityEffect
from PyQt6.QtGui import QFont, QIcon, QPainter, QColor, QBrush, QPen
from PyQt6.QtCore import QDateTime
from typing import Callable, Optional
from enum import Enum


class ToastType(Enum):
    """通知类型"""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"
    QUESTION = "question"


class ToastWidget(QWidget):
    """
    单个 Toast 通知组件
    
    特性：
    - 圆角矩形背景
    - 自动消失
    - 可选关闭按钮
    - 透明度动画
    """
    
    # 颜色配置
    COLORS = {
        ToastType.SUCCESS: ("#10b981", "#ecfdf5"),  # 绿色
        ToastType.WARNING: ("#f59e0b", "#fffbeb"),   # 橙色
        ToastType.ERROR: ("#ef4444", "#fef2f2"),    # 红色
        ToastType.INFO: ("#3b82f6", "#eff6ff"),     # 蓝色
        ToastType.QUESTION: ("#8b5cf6", "#f5f3ff"), # 紫色
    }
    
    closed = pyqtSignal()  # 关闭信号
    
    def __init__(
        self,
        message: str,
        toast_type: ToastType = ToastType.INFO,
        duration: int = 3000,
        title: str = None,
        show_close: bool = True,
        click_callback: Callable = None
    ):
        """
        初始化 Toast
        
        Args:
            message: 通知消息
            toast_type: 通知类型
            duration: 显示时长（毫秒），0 表示不自动消失
            title: 可选的标题
            show_close: 是否显示关闭按钮
            click_callback: 点击回调
        """
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        
        self.toast_type = toast_type
        self.duration = duration
        self.click_callback = click_callback
        self._is_hovered = False
        
        # 颜色
        border_color, bg_color = self.COLORS.get(toast_type, self.COLORS[ToastType.INFO])
        self._border_color = border_color
        self._bg_color = bg_color
        
        # 布局
        self._setup_ui(message, title, show_close)
        
        # 动画效果
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(0)
        
        # 自动消失计时器
        if duration > 0:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._start_close_animation)
            self._timer.setSingleShot(True)
            self._timer.start(duration)
        else:
            self._timer = None
        
        # 鼠标跟踪
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
    
    def _setup_ui(self, message: str, title: str, show_close: bool):
        """设置UI"""
        # 大小
        self.setFixedWidth(320)
        self.setMinimumHeight(60)
        
        # 样式
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {self._bg_color};
                border: 2px solid {self._border_color};
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
                color: #1f2937;
            }}
            QPushButton {{
                background: transparent;
                border: none;
                color: {self._border_color};
                font-size: 16px;
                padding: 4px;
            }}
            QPushButton:hover {{
                background: rgba(0,0,0,0.05);
                border-radius: 4px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # 标题行
        if title:
            title_label = QLabel(title)
            title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            layout.addWidget(title_label)
        
        # 消息行
        msg_layout = QVBoxLayout()
        msg_layout.setSpacing(4)
        
        # 类型图标
        icon_label = QLabel(self._get_icon())
        icon_label.setFont(QFont("Segoe UI", 14))
        icon_label.setFixedWidth(24)
        
        # 消息
        msg_label = QLabel(message)
        msg_label.setFont(QFont("Segoe UI", 10))
        msg_label.setWordWrap(True)
        msg_label.setMinimumWidth(240)
        
        h_layout = QVBoxLayout()
        h_layout.setSpacing(0)
        h_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        h_layout.addWidget(msg_label, 1)
        
        layout.addLayout(h_layout)
        
        # 关闭按钮
        if show_close:
            close_btn = QPushButton("×")
            close_btn.setFixedSize(24, 24)
            close_btn.clicked.connect(self._start_close_animation)
            layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)
    
    def _get_icon(self) -> str:
        """获取类型图标"""
        icons = {
            ToastType.SUCCESS: "✓",
            ToastType.WARNING: "⚠",
            ToastType.ERROR: "✕",
            ToastType.INFO: "ℹ",
            ToastType.QUESTION: "?",
        }
        return icons.get(self.toast_type, "ℹ")
    
    def showEvent(self, event):
        """显示动画"""
        super().showEvent(event)
        self._fade_in()
    
    def _fade_in(self):
        """淡入动画"""
        anim = QPropertyAnimation(self._opacity, b"opacity")
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
    
    def _start_close_animation(self):
        """开始关闭动画"""
        if self._timer:
            self._timer.stop()
        
        self._fade_out()
    
    def _fade_out(self):
        """淡出动画"""
        anim = QPropertyAnimation(self._opacity, b"opacity")
        anim.setDuration(200)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(self._on_close)
        anim.start()
    
    def _on_close(self):
        """关闭"""
        self.close()
        self.closed.emit()
    
    def enterEvent(self, event):
        """鼠标进入"""
        self._is_hovered = True
        # 暂停自动消失计时器
        if self._timer and self._timer.isActive():
            self._timer.stop()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开"""
        self._is_hovered = False
        # 重新启动计时器
        if self._timer and self.duration > 0:
            remaining = self.duration  # 重置计时器
            self._timer.start(remaining)
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """鼠标点击"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.click_callback:
                self.click_callback()
            self._start_close_animation()
        super().mousePressEvent(event)


class ToastManager:
    """
    Toast 通知管理器
    
    功能：
    - 队列管理多个通知
    - 自动定位到右下角
    - 通知堆叠显示
    """
    
    def __init__(self, parent=None):
        """
        初始化管理器
        
        Args:
            parent: 父窗口（用于定位）
        """
        self.parent = parent
        self._toasts: list[ToastWidget] = []
        self._enabled = True
        self._max_visible = 3  # 最多同时显示3个
        self._spacing = 10  # 间距
        self._offset_x = 20  # 右偏移
        self._offset_y = 20  # 下偏移
    
    @property
    def enabled(self) -> bool:
        """是否启用"""
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        """设置启用状态"""
        self._enabled = value
    
    def show(
        self,
        message: str,
        toast_type: ToastType = ToastType.INFO,
        duration: int = 3000,
        title: str = None,
        show_close: bool = True,
        click_callback: Callable = None
    ) -> Optional[ToastWidget]:
        """
        显示通知
        
        Args:
            message: 消息内容
            toast_type: 类型
            duration: 显示时长（毫秒），0 为不自动消失
            title: 可选标题
            show_close: 显示关闭按钮
            click_callback: 点击回调
            
        Returns:
            ToastWidget 实例
        """
        if not self._enabled:
            return None
        
        # 创建 Toast
        toast = ToastWidget(
            message=message,
            toast_type=toast_type,
            duration=duration,
            title=title,
            show_close=show_close,
            click_callback=click_callback
        )
        
        # 关闭时从队列移除
        toast.closed.connect(lambda: self._remove_toast(toast))
        
        # 定位
        self._position_toast(toast)
        
        # 显示
        toast.show()
        
        # 添加到队列
        self._toasts.append(toast)
        
        # 调整已有 toast 位置
        self._reposition_all()
        
        return toast
    
    def success(self, message: str, duration: int = 3000, **kwargs) -> Optional[ToastWidget]:
        """显示成功通知"""
        return self.show(message, ToastType.SUCCESS, duration, **kwargs)
    
    def warning(self, message: str, duration: int = 4000, **kwargs) -> Optional[ToastWidget]:
        """显示警告通知"""
        return self.show(message, ToastType.WARNING, duration, **kwargs)
    
    def error(self, message: str, duration: int = 5000, **kwargs) -> Optional[ToastWidget]:
        """显示错误通知"""
        return self.show(message, ToastType.ERROR, duration, **kwargs)
    
    def info(self, message: str, duration: int = 3000, **kwargs) -> Optional[ToastWidget]:
        """显示信息通知"""
        return self.show(message, ToastType.INFO, duration, **kwargs)
    
    def question(self, message: str, duration: int = 0, **kwargs) -> Optional[ToastWidget]:
        """显示问题通知（不自动消失）"""
        return self.show(message, ToastType.QUESTION, duration, **kwargs)
    
    def _position_toast(self, toast: ToastWidget):
        """定位新 Toast"""
        # 获取屏幕几何
        if self.parent:
            screen = self.parent.screen()
        else:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
        
        screen_geo = screen.geometry()
        
        # 右下角位置
        x = screen_geo.x() + screen_geo.width() - toast.width() - self._offset_x
        y = screen_geo.y() + screen_geo.height() - toast.height() - self._offset_y
        
        toast.move(x, y)
    
    def _remove_toast(self, toast: ToastWidget):
        """移除 Toast"""
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._reposition_all()
    
    def _reposition_all(self):
        """重新定位所有 Toast"""
        # 从下往上堆叠
        visible_toasts = self._toasts[-self._max_visible:]
        
        if self.parent:
            screen = self.parent.screen()
        else:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
        
        screen_geo = screen.geometry()
        
        base_y = screen_geo.y() + screen_geo.height() - self._offset_y
        
        for i, toast in enumerate(reversed(visible_toasts)):
            y = base_y - (i + 1) * (toast.height() + self._spacing)
            x = screen_geo.x() + screen_geo.width() - toast.width() - self._offset_x
            
            toast.move(x, y)
    
    def clear_all(self):
        """清除所有通知"""
        for toast in self._toasts[:]:
            toast._start_close_animation()
    
    def update_position(self):
        """更新位置（窗口大小变化时调用）"""
        self._reposition_all()


# 全局 Toast 管理器
_toast_manager: Optional[ToastManager] = None


def get_toast_manager(parent=None) -> ToastManager:
    """获取 Toast 管理器单例"""
    global _toast_manager
    if _toast_manager is None:
        _toast_manager = ToastManager(parent)
    return _toast_manager


def show_toast(
    message: str,
    toast_type: ToastType = ToastType.INFO,
    duration: int = 3000,
    **kwargs
) -> Optional[ToastWidget]:
    """快捷函数：显示通知"""
    return get_toast_manager().show(message, toast_type, duration, **kwargs)


def toast_success(message: str, **kwargs) -> Optional[ToastWidget]:
    """快捷函数：显示成功通知"""
    return get_toast_manager().success(message, **kwargs)


def toast_error(message: str, **kwargs) -> Optional[ToastWidget]:
    """快捷函数：显示错误通知"""
    return get_toast_manager().error(message, **kwargs)


def toast_warning(message: str, **kwargs) -> Optional[ToastWidget]:
    """快捷函数：显示警告通知"""
    return get_toast_manager().warning(message, **kwargs)


def toast_info(message: str, **kwargs) -> Optional[ToastWidget]:
    """快捷函数：显示信息通知"""
    return get_toast_manager().info(message, **kwargs)
