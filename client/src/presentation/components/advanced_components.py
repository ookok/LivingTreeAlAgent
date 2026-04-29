"""
高级UI组件 - 支持仪表盘、流程图、地图、CAD等丰富的渐进式渲染

功能支持：
1. 仪表盘组件 - 数据可视化仪表盘
2. 流程图组件 - 流程图展示和编辑
3. 地图组件 - 地图展示
4. CAD预览组件 - CAD文件预览
5. 图表组件 - 各种图表类型
6. 进度追踪组件 - 任务进度展示
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QSizePolicy, QScrollArea, QToolButton, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QSize, QTimer
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QPolygonF, QIcon
)

from .minimal_ui_framework import (
    ColorScheme, Spacing, MinimalCard, UIComponentFactory
)


# ── 仪表盘组件 ───────────────────────────────────────────────────────────────

class GaugeType(Enum):
    """仪表盘类型"""
    LINEAR = "linear"
    RADIAL = "radial"
    SEMICIRCLE = "semicircle"


class GaugeWidget(QWidget):
    """仪表盘组件"""
    
    value_changed = pyqtSignal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self._min_value = 0.0
        self._max_value = 100.0
        self._title = ""
        self._subtitle = ""
        self._gauge_type = GaugeType.SEMICIRCLE
        self._colors = [
            QColor(ColorScheme.SUCCESS.value),
            QColor(ColorScheme.WARNING.value),
            QColor(ColorScheme.ERROR.value)
        ]
        self.setMinimumSize(200, 150)
    
    def set_value(self, value: float):
        """设置值"""
        self._value = max(self._min_value, min(self._max_value, value))
        self.value_changed.emit(self._value)
        self.update()
    
    def set_range(self, min_val: float, max_val: float):
        """设置范围"""
        self._min_value = min_val
        self._max_value = max_val
        self.update()
    
    def set_title(self, title: str):
        """设置标题"""
        self._title = title
        self.update()
    
    def set_subtitle(self, subtitle: str):
        """设置副标题"""
        self._subtitle = subtitle
        self.update()
    
    def set_gauge_type(self, gauge_type: GaugeType):
        """设置仪表盘类型"""
        self._gauge_type = gauge_type
        self.update()
    
    def paintEvent(self, event):
        """绘制仪表盘"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        center_x = rect.width() // 2
        center_y = rect.height() // 2
        
        if self._gauge_type == GaugeType.SEMICIRCLE:
            self._draw_semicircle_gauge(painter, center_x, center_y, rect.width() // 2 - 20)
        elif self._gauge_type == GaugeType.RADIAL:
            self._draw_radial_gauge(painter, center_x, center_y, rect.width() // 2 - 20)
        else:
            self._draw_linear_gauge(painter, rect)
    
    def _draw_semicircle_gauge(self, painter: QPainter, cx: int, cy: int, radius: int):
        """绘制半圆形仪表盘"""
        # 绘制背景弧
        painter.setPen(QPen(QColor(ColorScheme.BORDER.value), 12, cap=Qt.PenCapStyle.RoundCap))
        painter.drawArc(cx - radius, cy - radius, radius * 2, radius * 2, 180 * 16, 180 * 16)
        
        # 绘制进度弧
        progress = (self._value - self._min_value) / (self._max_value - self._min_value)
        angle = int(progress * 180 * 16)
        
        gradient = QColor(self._get_color(progress))
        painter.setPen(QPen(gradient, 12, cap=Qt.PenCapStyle.RoundCap))
        painter.drawArc(cx - radius, cy - radius, radius * 2, radius * 2, 180 * 16, -angle)
        
        # 绘制刻度
        painter.setPen(QPen(QColor(ColorScheme.TEXT_SECONDARY.value), 1))
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)
        
        for i in range(0, 11):
            angle_deg = 180 - i * 18
            angle_rad = angle_deg * 3.1416 / 180
            x = cx + (radius - 30) * -1 * (angle_rad - 3.1416)
            y = cy + (radius - 30) * 1
            painter.drawText(QRectF(x - 10, y - 5, 20, 10), Qt.AlignmentFlag.AlignCenter, str(i * 10))
        
        # 绘制指针
        pointer_length = radius - 30
        pointer_angle = (1 - progress) * 3.1416
        end_x = cx + pointer_length * -1 * (pointer_angle - 3.1416)
        end_y = cy + pointer_length * 1
        
        painter.setPen(QPen(QColor(ColorScheme.TEXT_PRIMARY.value), 3, cap=Qt.PenCapStyle.RoundCap))
        painter.drawLine(cx, cy, end_x, end_y)
        
        # 绘制中心圆
        painter.setBrush(QBrush(QColor(ColorScheme.PRIMARY.value)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(cx - 6, cy - 6, 12, 12)
        
        # 绘制标题和数值
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor(ColorScheme.TEXT_PRIMARY.value)))
        painter.drawText(QRectF(0, cy + 20, self.width(), 30), Qt.AlignmentFlag.AlignCenter, f"{int(self._value)}%")
        
        if self._title:
            font.setPointSize(12)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QPen(QColor(ColorScheme.TEXT_SECONDARY.value)))
            painter.drawText(QRectF(0, cy + 50, self.width(), 20), Qt.AlignmentFlag.AlignCenter, self._title)
    
    def _draw_radial_gauge(self, painter: QPainter, cx: int, cy: int, radius: int):
        """绘制圆形仪表盘"""
        # 绘制背景圆
        painter.setPen(QPen(QColor(ColorScheme.BORDER.value), 8, cap=Qt.PenCapStyle.RoundCap))
        painter.drawArc(cx - radius, cy - radius, radius * 2, radius * 2, 0, 360 * 16)
        
        # 绘制进度
        progress = (self._value - self._min_value) / (self._max_value - self._min_value)
        angle = int(progress * 360 * 16)
        
        painter.setPen(QPen(QColor(self._get_color(progress)), 8, cap=Qt.PenCapStyle.RoundCap))
        painter.drawArc(cx - radius, cy - radius, radius * 2, radius * 2, 90 * 16, -angle)
        
        # 绘制中心数值
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor(ColorScheme.TEXT_PRIMARY.value)))
        painter.drawText(QRectF(cx - 30, cy - 15, 60, 30), Qt.AlignmentFlag.AlignCenter, f"{int(self._value)}")
    
    def _draw_linear_gauge(self, painter: QPainter, rect):
        """绘制线性仪表盘"""
        bar_height = 20
        bar_y = rect.height() // 2 - bar_height // 2
        
        # 绘制背景
        painter.setBrush(QBrush(QColor(ColorScheme.BORDER.value)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(20, bar_y, rect.width() - 40, bar_height, 10, 10)
        
        # 绘制进度
        progress = (self._value - self._min_value) / (self._max_value - self._min_value)
        progress_width = int((rect.width() - 40) * progress)
        
        painter.setBrush(QBrush(QColor(self._get_color(progress))))
        painter.drawRoundedRect(20, bar_y, progress_width, bar_height, 10, 10)
        
        # 绘制数值
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor(ColorScheme.TEXT_PRIMARY.value)))
        painter.drawText(QRectF(0, bar_y + bar_height + 10, rect.width(), 20), Qt.AlignmentFlag.AlignCenter, f"{int(self._value)}%")
    
    def _get_color(self, progress: float) -> str:
        """根据进度获取颜色"""
        if progress < 0.6:
            return ColorScheme.SUCCESS.value
        elif progress < 0.85:
            return ColorScheme.WARNING.value
        else:
            return ColorScheme.ERROR.value


class DashboardWidget(QWidget):
    """仪表盘组件 - 包含多个仪表盘"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._gauges = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(Spacing.LG)
    
    def add_gauge(self, title: str, value: float = 0, max_value: float = 100) -> GaugeWidget:
        """添加仪表盘"""
        card = MinimalCard()
        card_layout = card.layout()
        
        gauge = GaugeWidget()
        gauge.set_title(title)
        gauge.set_value(value)
        gauge.set_range(0, max_value)
        gauge.set_gauge_type(GaugeType.SEMICIRCLE)
        
        card_layout.addWidget(gauge)
        self._layout.addWidget(card)
        self._gauges.append(gauge)
        
        return gauge
    
    def add_stat_card(self, title: str, value: str, subtitle: str = "") -> QWidget:
        """添加统计卡片"""
        card = MinimalCard()
        card_layout = card.layout()
        
        title_label = UIComponentFactory.create_label(card, title, ColorScheme.TEXT_SECONDARY, 12)
        value_label = UIComponentFactory.create_label(card, value, ColorScheme.TEXT_PRIMARY, 28)
        value_label.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {ColorScheme.TEXT_PRIMARY.value};")
        
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        
        if subtitle:
            subtitle_label = UIComponentFactory.create_label(card, subtitle, ColorScheme.TEXT_SECONDARY, 12)
            card_layout.addWidget(subtitle_label)
        
        self._layout.addWidget(card)
        return card


# ── 流程图组件 ───────────────────────────────────────────────────────────────

@dataclass
class FlowNode:
    """流程图节点"""
    id: str
    label: str
    x: int = 50
    y: int = 50
    width: int = 120
    height: int = 60
    node_type: str = "process"  # process, decision, start, end, input, output
    color: str = ColorScheme.PRIMARY.value


@dataclass
class FlowEdge:
    """流程图边"""
    from_node: str
    to_node: str
    label: str = ""
    points: List[Tuple[int, int]] = field(default_factory=list)


class FlowChartWidget(QWidget):
    """流程图组件"""
    
    node_clicked = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes: List[FlowNode] = []
        self._edges: List[FlowEdge] = []
        self._selected_node: Optional[str] = None
        self._dragging_node: Optional[str] = None
        self._drag_offset = QPointF(0, 0)
        self.setMinimumSize(600, 400)
    
    def add_node(self, node: FlowNode):
        """添加节点"""
        self._nodes.append(node)
        self.update()
    
    def add_edge(self, edge: FlowEdge):
        """添加边"""
        self._edges.append(edge)
        self.update()
    
    def clear(self):
        """清空流程图"""
        self._nodes.clear()
        self._edges.clear()
        self.update()
    
    def paintEvent(self, event):
        """绘制流程图"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制边
        for edge in self._edges:
            self._draw_edge(painter, edge)
        
        # 绘制节点
        for node in self._nodes:
            self._draw_node(painter, node)
    
    def _draw_node(self, painter: QPainter, node: FlowNode):
        """绘制节点"""
        is_selected = node.id == self._selected_node
        
        # 设置颜色
        if node.node_type == "start" or node.node_type == "end":
            color = QColor(ColorScheme.SUCCESS.value)
            shape = "circle"
        elif node.node_type == "decision":
            color = QColor(ColorScheme.WARNING.value)
            shape = "diamond"
        else:
            color = QColor(node.color)
            shape = "rectangle"
        
        # 绘制背景
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(ColorScheme.TEXT_PRIMARY.value), 2 if is_selected else 1))
        
        if shape == "circle":
            radius = min(node.width, node.height) // 2
            painter.drawEllipse(node.x - radius, node.y - radius, node.width, node.height)
        elif shape == "diamond":
            points = [
                QPointF(node.x, node.y - node.height // 2),
                QPointF(node.x + node.width // 2, node.y),
                QPointF(node.x, node.y + node.height // 2),
                QPointF(node.x - node.width // 2, node.y)
            ]
            painter.drawPolygon(QPolygonF(points))
        else:
            painter.drawRoundedRect(
                node.x - node.width // 2,
                node.y - node.height // 2,
                node.width,
                node.height,
                8, 8
            )
        
        # 绘制标签
        painter.setPen(QPen(Qt.GlobalColor.white))
        font = QFont()
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(
            QRectF(node.x - node.width // 2, node.y - node.height // 2, node.width, node.height),
            Qt.AlignmentFlag.AlignCenter,
            node.label
        )
    
    def _draw_edge(self, painter: QPainter, edge: FlowEdge):
        """绘制边"""
        from_node = next((n for n in self._nodes if n.id == edge.from_node), None)
        to_node = next((n for n in self._nodes if n.id == edge.to_node), None)
        
        if not from_node or not to_node:
            return
        
        # 计算起点和终点
        start_x = from_node.x + from_node.width // 2
        start_y = from_node.y
        end_x = to_node.x - to_node.width // 2
        end_y = to_node.y
        
        # 绘制连线
        painter.setPen(QPen(QColor(ColorScheme.TEXT_SECONDARY.value), 2))
        
        # 使用贝塞尔曲线
        path = QPainterPath()
        path.moveTo(start_x, start_y)
        
        mid_x = (start_x + end_x) // 2
        path.cubicTo(mid_x, start_y, mid_x, end_y, end_x, end_y)
        painter.drawPath(path)
        
        # 绘制箭头
        arrow_size = 10
        angle = (end_x - start_x) / (end_y - start_y) if (end_y - start_y) != 0 else 0
        arrow_angle = 3.1416 / 6
        
        painter.drawLine(
            end_x, end_y,
            end_x - arrow_size * (angle + arrow_angle),
            end_y - arrow_size
        )
        painter.drawLine(
            end_x, end_y,
            end_x - arrow_size * (angle - arrow_angle),
            end_y - arrow_size
        )
        
        # 绘制标签
        if edge.label:
            painter.setPen(QPen(QColor(ColorScheme.TEXT_PRIMARY.value)))
            font = QFont()
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(
                QRectF(mid_x - 30, min(start_y, end_y) - 25, 60, 20),
                Qt.AlignmentFlag.AlignCenter,
                edge.label
            )
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        for node in self._nodes:
            rect = QRectF(
                node.x - node.width // 2,
                node.y - node.height // 2,
                node.width,
                node.height
            )
            if rect.contains(event.pos()):
                self._selected_node = node.id
                self._dragging_node = node.id
                self._drag_offset = QPointF(event.pos().x() - node.x, event.pos().y() - node.y())
                self.update()
                self.node_clicked.emit(node.id)
                return
        
        self._selected_node = None
        self.update()
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self._dragging_node:
            node = next((n for n in self._nodes if n.id == self._dragging_node), None)
            if node:
                node.x = event.pos().x() - self._drag_offset.x()
                node.y = event.pos().y() - self._drag_offset.y()
                self.update()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        self._dragging_node = None


# ── 地图组件 ─────────────────────────────────────────────────────────────────

class MapWidget(QWidget):
    """地图组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom = 1.0
        self._center = QPointF(0, 0)
        self._markers = []
        self.setMinimumSize(400, 300)
    
    def add_marker(self, x: float, y: float, label: str, color: str = ColorScheme.PRIMARY.value):
        """添加标记"""
        self._markers.append({"x": x, "y": y, "label": label, "color": color})
        self.update()
    
    def clear_markers(self):
        """清空标记"""
        self._markers.clear()
        self.update()
    
    def set_zoom(self, zoom: float):
        """设置缩放"""
        self._zoom = max(0.1, min(5.0, zoom))
        self.update()
    
    def paintEvent(self, event):
        """绘制地图"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # 绘制网格背景
        painter.setPen(QPen(QColor(ColorScheme.BORDER.value), 0.5))
        grid_size = 40 * self._zoom
        
        for x in range(int(-self._center.x() % grid_size), rect.width(), int(grid_size)):
            painter.drawLine(x, 0, x, rect.height())
        
        for y in range(int(-self._center.y() % grid_size), rect.height(), int(grid_size)):
            painter.drawLine(0, y, rect.width(), y)
        
        # 绘制标记
        for marker in self._markers:
            screen_x = marker["x"] * self._zoom + rect.width() // 2
            screen_y = marker["y"] * self._zoom + rect.height() // 2
            
            # 绘制标记背景
            painter.setBrush(QBrush(QColor(marker["color"])))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(screen_x - 8, screen_y - 8, 16, 16)
            
            # 绘制标记边框
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            painter.drawEllipse(screen_x - 8, screen_y - 8, 16, 16)
            
            # 绘制标签
            painter.setPen(QPen(QColor(ColorScheme.TEXT_PRIMARY.value)))
            font = QFont()
            font.setPointSize(11)
            painter.setFont(font)
            painter.drawText(
                QRectF(screen_x - 40, screen_y + 12, 80, 20),
                Qt.AlignmentFlag.AlignCenter,
                marker["label"]
            )
        
        # 绘制缩放提示
        painter.setPen(QPen(QColor(ColorScheme.TEXT_SECONDARY.value)))
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(
            QRectF(rect.width() - 60, rect.height() - 20, 50, 15),
            Qt.AlignmentFlag.AlignRight,
            f"Zoom: {int(self._zoom * 100)}%"
        )


# ── CAD预览组件 ──────────────────────────────────────────────────────────────

class CADPreviewWidget(QWidget):
    """CAD预览组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layers = []
        self._selected_layer = None
        self.setMinimumSize(400, 300)
    
    def add_layer(self, name: str, visible: bool = True):
        """添加图层"""
        self._layers.append({"name": name, "visible": visible, "items": []})
        self.update()
    
    def add_shape(self, layer_index: int, shape_type: str, points: List[Tuple[int, int]]):
        """添加形状"""
        if layer_index < len(self._layers):
            self._layers[layer_index]["items"].append({
                "type": shape_type,
                "points": points
            })
            self.update()
    
    def paintEvent(self, event):
        """绘制CAD预览"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # 绘制背景
        painter.setBrush(QBrush(QColor("#F8F9FA")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
        
        # 绘制边框
        painter.setPen(QPen(QColor(ColorScheme.BORDER.value), 2))
        painter.drawRect(5, 5, rect.width() - 10, rect.height() - 10)
        
        # 绘制栅格
        painter.setPen(QPen(QColor("#E9ECEF"), 0.5))
        grid_size = 20
        
        for x in range(10, rect.width() - 10, grid_size):
            painter.drawLine(x, 10, x, rect.height() - 10)
        
        for y in range(10, rect.height() - 10, grid_size):
            painter.drawLine(10, y, rect.width() - 10, y)
        
        # 绘制图形
        for layer in self._layers:
            if not layer["visible"]:
                continue
            
            for item in layer["items"]:
                self._draw_shape(painter, item)
        
        # 绘制提示文字
        if not self._layers:
            painter.setPen(QPen(QColor(ColorScheme.TEXT_SECONDARY.value)))
            font = QFont()
            font.setPointSize(14)
            painter.setFont(font)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                "📐 CAD预览区域\n\n拖放CAD文件或点击查看详情"
            )
    
    def _draw_shape(self, painter: QPainter, item):
        """绘制形状"""
        painter.setPen(QPen(QColor(ColorScheme.PRIMARY.value), 2))
        
        if item["type"] == "line":
            points = item["points"]
            if len(points) >= 2:
                painter.drawLine(points[0][0], points[0][1], points[1][0], points[1][1])
        elif item["type"] == "rect":
            points = item["points"]
            if len(points) >= 2:
                painter.drawRect(points[0][0], points[0][1], points[1][0] - points[0][0], points[1][1] - points[0][1])
        elif item["type"] == "circle":
            points = item["points"]
            if len(points) >= 2:
                radius = ((points[1][0] - points[0][0])**2 + (points[1][1] - points[0][1])**2)**0.5
                painter.drawEllipse(points[0][0] - radius, points[0][1] - radius, radius * 2, radius * 2)
        elif item["type"] == "polyline":
            points = item["points"]
            if len(points) >= 2:
                path = QPainterPath()
                path.moveTo(points[0][0], points[0][1])
                for point in points[1:]:
                    path.lineTo(point[0], point[1])
                painter.drawPath(path)


# ── 图表组件 ─────────────────────────────────────────────────────────────────

class ChartType(Enum):
    """图表类型"""
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    AREA = "area"


class ChartWidget(QWidget):
    """图表组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._chart_type = ChartType.BAR
        self._data = []
        self._labels = []
        self._title = ""
        self._colors = [
            ColorScheme.PRIMARY.value,
            ColorScheme.SUCCESS.value,
            ColorScheme.WARNING.value,
            ColorScheme.ERROR.value,
            ColorScheme.INFO.value
        ]
        self.setMinimumSize(300, 200)
    
    def set_data(self, data: List[float], labels: List[str]):
        """设置数据"""
        self._data = data
        self._labels = labels
        self.update()
    
    def set_title(self, title: str):
        """设置标题"""
        self._title = title
        self.update()
    
    def set_chart_type(self, chart_type: ChartType):
        """设置图表类型"""
        self._chart_type = chart_type
        self.update()
    
    def paintEvent(self, event):
        """绘制图表"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        padding = 40
        chart_rect = QRectF(padding, padding, rect.width() - padding * 2, rect.height() - padding * 2)
        
        if not self._data:
            painter.setPen(QPen(QColor(ColorScheme.TEXT_SECONDARY.value)))
            painter.drawText(chart_rect, Qt.AlignmentFlag.AlignCenter, "暂无数据")
            return
        
        if self._chart_type == ChartType.BAR:
            self._draw_bar_chart(painter, chart_rect)
        elif self._chart_type == ChartType.LINE:
            self._draw_line_chart(painter, chart_rect)
        elif self._chart_type == ChartType.PIE:
            self._draw_pie_chart(painter, chart_rect)
    
    def _draw_bar_chart(self, painter: QPainter, rect: QRectF):
        """绘制柱状图"""
        if not self._data:
            return
        
        max_value = max(self._data) if self._data else 1
        bar_width = rect.width() / len(self._data) * 0.7
        gap = rect.width() / len(self._data) * 0.3
        
        for i, value in enumerate(self._data):
            x = rect.left() + i * (bar_width + gap) + gap / 2
            height = (value / max_value) * rect.height() * 0.9
            y = rect.bottom() - height
            
            color = QColor(self._colors[i % len(self._colors)])
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, bar_width, height, 4, 4)
            
            # 绘制数值标签
            painter.setPen(QPen(QColor(ColorScheme.TEXT_PRIMARY.value)))
            font = QFont()
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(QRectF(x, y - 20, bar_width, 15), Qt.AlignmentFlag.AlignCenter, f"{int(value)}")
        
        # 绘制X轴标签
        painter.setPen(QPen(QColor(ColorScheme.TEXT_SECONDARY.value)))
        font.setPointSize(10)
        painter.setFont(font)
        
        for i, label in enumerate(self._labels):
            x = rect.left() + i * (bar_width + gap) + gap / 2
            painter.drawText(QRectF(x, rect.bottom() + 10, bar_width, 15), Qt.AlignmentFlag.AlignCenter, label)
    
    def _draw_line_chart(self, painter: QPainter, rect: QRectF):
        """绘制折线图"""
        if not self._data:
            return
        
        max_value = max(self._data) if self._data else 1
        point_width = rect.width() / (len(self._data) - 1) if len(self._data) > 1 else 0
        
        # 绘制折线
        painter.setPen(QPen(QColor(self._colors[0]), 2))
        path = QPainterPath()
        
        for i, value in enumerate(self._data):
            x = rect.left() + i * point_width
            y = rect.bottom() - (value / max_value) * rect.height() * 0.9
            
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        
        painter.drawPath(path)
        
        # 绘制数据点
        for i, value in enumerate(self._data):
            x = rect.left() + i * point_width
            y = rect.bottom() - (value / max_value) * rect.height() * 0.9
            
            painter.setBrush(QBrush(QColor(self._colors[0])))
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            painter.drawEllipse(x - 4, y - 4, 8, 8)
    
    def _draw_pie_chart(self, painter: QPainter, rect: QRectF):
        """绘制饼图"""
        if not self._data:
            return
        
        total = sum(self._data)
        start_angle = 0
        
        for i, value in enumerate(self._data):
            angle = int((value / total) * 360 * 16)
            color = QColor(self._colors[i % len(self._colors)])
            
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPie(rect, start_angle, angle)
            
            start_angle += angle


# ── 进度追踪组件 ─────────────────────────────────────────────────────────────

class ProgressTrackerWidget(QWidget):
    """进度追踪组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps = []
        self._current_step = 0
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
    
    def add_step(self, title: str, description: str = "", completed: bool = False):
        """添加步骤"""
        self._steps.append({
            "title": title,
            "description": description,
            "completed": completed
        })
        self.update()
    
    def set_current_step(self, step_index: int):
        """设置当前步骤"""
        self._current_step = max(0, min(len(self._steps) - 1, step_index))
        
        # 标记之前的步骤为完成
        for i in range(self._current_step):
            self._steps[i]["completed"] = True
        
        self.update()
    
    def update(self):
        """更新UI"""
        # 清空布局
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 重新创建步骤组件
        for i, step in enumerate(self._steps):
            step_widget = self._create_step_widget(i, step)
            self._layout.addWidget(step_widget)
            
            if i < len(self._steps) - 1:
                line = UIComponentFactory.create_divider(self)
                line.setFixedHeight(20)
                self._layout.addWidget(line)
    
    def _create_step_widget(self, index: int, step: dict) -> QWidget:
        """创建步骤控件"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MD)
        
        # 步骤编号
        circle = QFrame()
        circle.setFixedSize(32, 32)
        circle.setStyleSheet(f"""
            QFrame {{
                background-color: {'#22C55E' if step['completed'] else '#3B82F6' if index == self._current_step else '#E5E7EB'};
                border-radius: 16px;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
        """)
        
        circle_layout = QVBoxLayout(circle)
        number_label = QLabel(str(index + 1))
        number_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        circle_layout.addWidget(number_label)
        
        layout.addWidget(circle)
        
        # 步骤内容
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel(step["title"])
        title_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: {'bold' if index == self._current_step else 'normal'};
            color: {'#1F2937' if step['completed'] or index == self._current_step else '#9CA3AF'};
        """)
        content_layout.addWidget(title_label)
        
        if step["description"]:
            desc_label = QLabel(step["description"])
            desc_label.setStyleSheet("font-size: 12px; color: #6B7280;")
            content_layout.addWidget(desc_label)
        
        layout.addWidget(content)
        layout.addStretch()
        
        # 状态图标
        status_label = QLabel()
        if step["completed"]:
            status_label.setText("✓")
            status_label.setStyleSheet("color: #22C55E; font-size: 16px;")
        elif index == self._current_step:
            status_label.setText("⏳")
            status_label.setStyleSheet("color: #3B82F6; font-size: 16px;")
        
        layout.addWidget(status_label)
        
        return widget


# 导出接口
__all__ = [
    "GaugeType",
    "GaugeWidget",
    "DashboardWidget",
    "FlowNode",
    "FlowEdge",
    "FlowChartWidget",
    "MapWidget",
    "CADPreviewWidget",
    "ChartType",
    "ChartWidget",
    "ProgressTrackerWidget"
]