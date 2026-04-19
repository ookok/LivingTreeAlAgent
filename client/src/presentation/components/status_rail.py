"""
沃土状态栏 (Soil Status Rail)
位置：界面底部（固定高度 48px），轻量进度/状态展示
场景：下载进度、装配步骤、网络同步中
元素：左侧图标（旋转/静止）+ 文字 + 进度条（可选）
优点：不遮挡中心工作区，自动化可轮询状态文本

🌿 生命之树风格 · 无弹窗组件库 #3
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QRect, QParallelAnimationGroup
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QProgressBar, QFrame
)
from PyQt6.QtGui import QColor, QPainter, QFont, QTransform


class RotatingIconLabel(QLabel):
    """旋转图标（用于加载状态）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._rotation_animation = None
        self._is_rotating = False
        self.setFixedSize(20, 20)

    def set_rotating(self, rotating: bool):
        """设置是否旋转"""
        if self._is_rotating == rotating:
            return
        self._is_rotating = rotating
        if rotating:
            self._start_rotation()
        else:
            self._stop_rotation()

    def _start_rotation(self):
        """开始旋转"""
        self._rotation_timer = QTimer(self)
        self._rotation_timer.timeout.connect(self._rotate)
        self._rotation_timer.start(50)  # 每50ms更新一次

    def _stop_rotation(self):
        """停止旋转"""
        if hasattr(self, '_rotation_timer'):
            self._rotation_timer.stop()
        self._angle = 0
        self.update()

    def _rotate(self):
        """旋转"""
        self._angle = (self._angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        """绘制"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 平移到中心
        cx, cy = self.width() / 2, self.height() / 2
        painter.translate(cx, cy)
        painter.rotate(self._angle)

        # 绘制箭头图标
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#60a5fa"))
        size = 8
        painter.drawPolygon([
            self.mapFromParent(self.rect().center() + type(self.rect().center())(size, 0)),
            self.mapFromParent(self.rect().center() + type(self.rect().center())(-size//2, -size//2)),
            self.mapFromParent(self.rect().center() + type(self.rect().center())(-size//2, size//2)),
        ])


class SoilStatusRail(QWidget):
    """
    沃土状态栏 — 过程反馈组件

    使用方式:
        # 显示进度
        self.status_rail.show_progress(
            message="正在嫁接「OpenDataLoader」...",
            progress=35,
            icon="🔄"
        )

        # 显示完成
        self.status_rail.show_success("嫁接完成！")

        # 清除
        self.status_rail.clear()
    """

    # 信号
    cancelled = pyqtSignal()

    # 状态类型
    TYPE_LOADING = "loading"
    TYPE_SUCCESS = "success"
    TYPE_ERROR = "error"
    TYPE_INFO = "info"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("soil-status-rail")  # 自动化锚点
        self.setFixedHeight(48)
        self._current_icon = "🌱"
        self._is_indeterminate = False
        self._setup_ui()
        self._setup_animations()

    def _setup_ui(self):
        """初始化UI"""
        self.setStyleSheet("""
            #soil-status-rail {
                background-color: #0d0d0d;
                border-top: 1px solid #1e1e1e;
            }
        """)

        # 主布局
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 0, 16, 0)
        self._layout.setSpacing(12)

        # 状态图标
        self._icon_label = QLabel("🌱")
        self._icon_label.setObjectName("status-icon")
        self._icon_label.setFixedWidth(24)

        # 消息文本
        self._message = QLabel("就绪")
        self._message.setObjectName("status-message")
        self._message.setStyleSheet("color: #888888; font-size: 12px;")

        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("status-progress")
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2a2a2a;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 2px;
            }
        """)

        # 取消按钮
        self._cancel_btn = QLabel("✕")
        self._cancel_btn.setObjectName("status-cancel")
        self._cancel_btn.setFixedWidth(20)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.hide()
        self._cancel_btn.mousePressEvent = lambda e: self.cancelled.emit()

        # 进度百分比
        self._percent = QLabel("")
        self._percent.setObjectName("status-percent")
        self._percent.setStyleSheet("color: #60a5fa; font-size: 11px;")
        self._percent.setFixedWidth(36)
        self._percent.hide()

        # 组装
        self._layout.addWidget(self._icon_label)
        self._layout.addWidget(self._message, 1)
        self._layout.addWidget(self._progress_bar, 2)
        self._layout.addWidget(self._percent)
        self._layout.addWidget(self._cancel_btn)

    def _setup_animations(self):
        """设置动画"""
        self._slide_animation = QPropertyAnimation(self, b"maximumHeight")
        self._slide_animation.setDuration(200)

        self._fade_timer = QTimer()
        self._fade_timer.timeout.connect(self._fade_out_step)

    def _apply_type_style(self, type_name: str):
        """应用类型样式"""
        styles = {
            self.TYPE_LOADING: {
                "icon": "🔄",
                "progress_bg": "#2a2a2a",
                "progress_chunk": "#3b82f6",
                "message_color": "#888888",
                "show_cancel": True
            },
            self.TYPE_SUCCESS: {
                "icon": "✅",
                "progress_bg": "#2a3d2a",
                "progress_chunk": "#22c55e",
                "message_color": "#4ade80",
                "show_cancel": False
            },
            self.TYPE_ERROR: {
                "icon": "❌",
                "progress_bg": "#3d2a2a",
                "progress_chunk": "#ef4444",
                "message_color": "#f87171",
                "show_cancel": False
            },
            self.TYPE_INFO: {
                "icon": "💡",
                "progress_bg": "#2a2a2a",
                "progress_chunk": "#60a5fa",
                "message_color": "#888888",
                "show_cancel": False
            }
        }
        style = styles.get(type_name, styles[self.TYPE_INFO])

        self._icon_label.setText(style["icon"])
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {style['progress_bg']};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {style['progress_chunk']};
                border-radius: 2px;
            }}
        """)
        self._message.setStyleSheet(f"color: {style['message_color']}; font-size: 12px;")
        self._cancel_btn.setVisible(style["show_cancel"])

    def _animate_show(self):
        """显示动画"""
        self._slide_animation.stop()
        self._slide_animation.setStartValue(0)
        self._slide_animation.setEndValue(48)
        self._slide_animation.start()
        QWidget.show(self)

    def _animate_hide(self):
        """隐藏动画"""
        self._slide_animation.stop()
        self._slide_animation.setStartValue(48)
        self._slide_animation.setEndValue(0)
        self._slide_animation.finished.connect(self._on_hide_finished)
        self._slide_animation.start()

    def _on_hide_finished(self):
        """隐藏动画完成"""
        if self.maximumHeight() == 0:
            self.hide()
        self._slide_animation.finished.disconnect(self._on_hide_finished)

    def _fade_out_step(self):
        """渐隐步骤"""
        current = self.graphicsEffect()
        if current and current.opacity() > 0:
            current.setOpacity(current.opacity() - 0.1)
        else:
            self._fade_timer.stop()
            self.clear()

    # ========== 公共接口 ==========

    def show(
        self,
        message: str,
        progress: int = -1,
        type_name: str = TYPE_LOADING,
        icon: str = None,
        auto_hide_ms: int = 0,
        show_cancel: bool = None
    ):
        """
        显示状态

        Args:
            message: 状态消息
            progress: 进度值 0-100，-1 表示不确定
            type_name: 类型 loading/success/error/info
            icon: 自定义图标
            auto_hide_ms: 自动隐藏时间
            show_cancel: 是否显示取消按钮
        """
        self._message.setText(message)
        self._apply_type_style(type_name)

        if icon:
            self._icon_label.setText(icon)

        # 进度
        if progress >= 0:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(progress)
            self._progress_bar.show()
            self._percent.setText(f"{progress}%")
            self._percent.show()
            self._is_indeterminate = False
        else:
            self._progress_bar.setRange(0, 0)  # 不确定模式
            self._progress_bar.hide()
            self._percent.hide()
            self._is_indeterminate = True

        # 取消按钮
        if show_cancel is not None:
            self._cancel_btn.setVisible(show_cancel)

        # 显示
        if not self.isVisible():
            self._animate_show()

        # 自动隐藏
        if auto_hide_ms > 0:
            QTimer.singleShot(auto_hide_ms, lambda: self.hide(auto_hide_ms > 0))

    def show_progress(self, message: str, progress: int = -1, icon: str = None):
        """显示进度状态"""
        self.show(message, progress, self.TYPE_LOADING, icon)

    def show_success(self, message: str, auto_hide_ms: int = 3000):
        """显示成功状态"""
        self.show(message, 100, self.TYPE_SUCCESS, "✅", auto_hide_ms)

    def show_error(self, message: str, auto_hide_ms: int = 5000):
        """显示错误状态"""
        self.show(message, 0, self.TYPE_ERROR, "❌", auto_hide_ms)

    def show_info(self, message: str, auto_hide_ms: int = 3000):
        """显示信息状态"""
        self.show(message, -1, self.TYPE_INFO, "💡", auto_hide_ms)

    def update_progress(self, progress: int, message: str = None):
        """
        更新进度

        Args:
            progress: 新进度值 0-100
            message: 新消息（可选）
        """
        if message:
            self._message.setText(message)
        self._progress_bar.setValue(progress)
        self._percent.setText(f"{progress}%")
        self._percent.show()
        self._progress_bar.show()

    def hide(self, animated: bool = True):
        """隐藏状态栏"""
        if animated:
            self._animate_hide()
        else:
            super().hide()
            self._progress_bar.setValue(0)

    def clear(self):
        """清除状态（恢复默认）"""
        self._message.setText("就绪")
        self._message.setStyleSheet("color: #888888; font-size: 12px;")
        self._icon_label.setText("🌱")
        self._progress_bar.setValue(0)
        self._progress_bar.hide()
        self._percent.hide()
        self._cancel_btn.hide()
        self._percent.hide()
        if self.isVisible():
            self._animate_hide()

    def is_active(self) -> bool:
        """检查是否正在显示活动状态"""
        return self.isVisible() and self._message.text() != "就绪"

    def get_current_message(self) -> str:
        """获取当前消息"""
        return self._message.text()

    def get_current_progress(self) -> int:
        """获取当前进度"""
        return self._progress_bar.value()


# ========== 自动化测试辅助 ==========

def get_status_rail(window) -> SoilStatusRail:
    """通过 ObjectName 获取状态栏（用于自动化测试）"""
    return window.findChild(QWidget, "soil-status-rail")


def wait_for_status_active(window, timeout_ms: int = 5000) -> bool:
    """等待状态栏变为活动状态"""
    import time
    rail = get_status_rail(window)
    if not rail:
        return False

    start = time.time()
    while time.time() - start < timeout_ms / 1000:
        if rail.is_active():
            return True
    return False


def get_status_message(window) -> str:
    """获取当前状态消息"""
    rail = get_status_rail(window)
    if rail:
        return rail.get_current_message()
    return ""
