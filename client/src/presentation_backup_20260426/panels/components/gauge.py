# -*- coding: utf-8 -*-
"""
QGauge - 自定义仪表盘组件
用于显示进度、速度等数值
"""

from PyQt6.QtWidgets import QWidget, QProgressBar
from PyQt6.QtCore import Qt, pyqtProperty, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont


class QGauge(QWidget):
    """
    自定义仪表盘组件
    支持圆弧式仪表盘显示
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._min_value = 0
        self._max_value = 100
        self._warning_value = 70
        self._critical_value = 90
        self._gauge_color = QColor("#4CAF50")  # 绿色
        self._warning_color = QColor("#FFC107")  # 黄色
        self._critical_color = QColor("#F44336")  # 红色
        self._bg_color = QColor("#2a2a2a")
        self._text_color = QColor("#ffffff")
        self.setMinimumSize(100, 100)

    @pyqtProperty(int)
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = max(self._min_value, min(self._max_value, val))
        self.update()

    @pyqtProperty(int)
    def minValue(self):
        return self._min_value

    @minValue.setter
    def minValue(self, val):
        self._min_value = val
        self.update()

    @pyqtProperty(int)
    def maxValue(self):
        return self._max_value

    @maxValue.setter
    def maxValue(self, val):
        self._max_value = val
        self.update()

    def setRange(self, min_val, max_val):
        self._min_value = min_val
        self._max_value = max_val
        self.update()

    def setValue(self, val):
        self.value = val

    def setWarningValue(self, val):
        self._warning_value = val
        self.update()

    def setCriticalValue(self, val):
        self._critical_value = val
        self.update()

    def setGaugeColor(self, color):
        self._gauge_color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        size = min(width, height)

        # 计算颜色
        percentage = (self._value - self._min_value) / (self._max_value - self._min_value) * 100
        if percentage >= self._critical_value:
            current_color = self._critical_color
        elif percentage >= self._warning_value:
            current_color = self._warning_color
        else:
            current_color = self._gauge_color

        # 绘制背景圆弧
        painter.setPen(QPen(self._bg_color, 20))
        rect = QRectF(20, 20, size - 40, size - 40)
        painter.drawArc(rect, 45 * 16, 270 * 16)

        # 绘制值圆弧
        painter.setPen(QPen(current_color, 20))
        span = int((self._value - self._min_value) / (self._max_value - self._min_value) * 270)
        painter.drawArc(rect, 45 * 16, span * 16)

        # 绘制中心文本
        painter.setPen(QPen(self._text_color))
        font = QFont()
        font.setPixelSize(int(size / 4))
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self._value}")

        # 绘制单位文本
        font_unit = QFont()
        font_unit.setPixelSize(int(size / 8))
        painter.setFont(font_unit)
        painter.drawText(QRectF(0, height * 0.65, width, height * 0.2),
                        Qt.AlignmentFlag.AlignCenter, "%")
