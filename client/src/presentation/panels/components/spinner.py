"""
QSpinner - 加载旋转动画组件
用于显示加载状态的旋转指示器
"""

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QSizePolicy
from PyQt6.QtCore import Qt, QTimer, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QPen, QFont


class QSpinner(QWidget):
    """
    旋转加载指示器组件
    """

    def __init__(self, parent=None, size=40, color=None):
        super().__init__(parent)
        self._size = size
        self._color = color or QColor("#3498db")
        self._angle = 0
        self._timer = None
        self._running = False

        self.setFixedSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # 启动旋转动画
        self._start_timer()

    def _start_timer(self):
        """启动定时器"""
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._rotate)
        self._running = True
        self._timer.start(30)  # ~33 FPS

    def _rotate(self):
        """旋转动画"""
        self._angle = (self._angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        """绘制旋转动画"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 设置画笔
        pen = QPen()
        pen.setColor(self._color)
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCap.Round)
        painter.setPen(pen)

        # 计算半径
        margin = 3
        size = min(self.width(), self.height()) - margin * 2
        center = self.rect().center()
        radius = size // 2

        # 绘制弧线
        rect = [
            center.x() - radius,
            center.y() - radius,
            radius * 2,
            radius * 2
        ]

        # 绘制有头部的弧线
        span = 90
        painter.drawArc(*rect, self._angle * 16, span * 16)

        # 绘制圆点（表示旋转方向的头部）
        import math
        angle_rad = math.radians(self._angle + span / 2)
        dot_x = center.x() + radius * 0.7 * math.cos(angle_rad)
        dot_y = center.y() + radius * 0.7 * math.sin(angle_rad)

        painter.setPen(Qt.PenStyle.NoPen)
        from PyQt6.QtGui import QBrush
        painter.setBrush(self._color)
        painter.drawEllipse(int(dot_x) - 2, int(dot_y) - 2, 4, 4)

    def setColor(self, color):
        """设置颜色"""
        if isinstance(color, str):
            self._color = QColor(color)
        else:
            self._color = color
        self.update()

    def setSize(self, size):
        """设置大小"""
        self._size = size
        self.setFixedSize(size, size)

    def start(self):
        """启动旋转"""
        if not self._running:
            self._start_timer()

    def stop(self):
        """停止旋转"""
        self._running = False
        if self._timer:
            self._timer.stop()