"""
导航球 - Navigation Sphere
快速导航到各个舱室
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPointF
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QRadialGradient, QFont, QPainterPath
import math
import random

from .bridge_styles import HolographicColors, HolographicFonts


# ═══════════════════════════════════════════════════════════════════════════════
# 导航球
# ═══════════════════════════════════════════════════════════════════════════════

class NavigationSphere(QWidget):
    """
    导航球 - 快速跳转到各个舱室
    悬浮在右下角，显示可导航目标
    """
    
    navigation_requested = pyqtSignal(str)  # 目标舱室ID
    
    NAV_TARGETS = {
        "trade_deck": {"icon": "💬", "name": "交易舱", "color": HolographicColors.HOLO_GREEN},
        "comm_array": {"icon": "📡", "name": "通讯阵", "color": HolographicColors.HOLO_SECONDARY},
        "oracle_core": {"icon": "🔮", "name": "先知核心", "color": HolographicColors.HOLO_PURPLE},
        "intelligence": {"icon": "🎯", "name": "情报中心", "color": HolographicColors.HOLO_ORANGE},
        "market": {"icon": "🛒", "name": "商品市场", "color": HolographicColors.HOLO_GOLD},
        "settings": {"icon": "⚙️", "name": "系统设置", "color": HolographicColors.TEXT_DIM},
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._start_rotation()
    
    def _init_ui(self):
        """初始化UI"""
        self.setFixedSize(100, 120)
        
        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 标题
        title = QLabel("◈ 导航球")
        title.setObjectName("NavSphereLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {HolographicColors.HOLO_PRIMARY}; font-size: 10px;")
        layout.addWidget(title)
        
        # 球体
        self.sphere = _SphereWidget(self)
        self.sphere.navigation_requested.connect(self.navigation_requested.emit)
        layout.addWidget(self.sphere, 1, Qt.AlignmentFlag.AlignHCenter)
        
        # 当前导航提示
        self.hint_label = QLabel("交易舱")
        self.hint_label.setObjectName("NavSphereLabel")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet(f"color: {HolographicColors.TEXT_SECONDARY}; font-size: 9px;")
        layout.addWidget(self.hint_label)
    
    def _start_rotation(self):
        """开始旋转动画"""
        self._rot_timer = QTimer()
        self._rot_timer.timeout.connect(self._rotate)
        self._rot_timer.start(100)
    
    def _rotate(self):
        """旋转"""
        targets = list(self.NAV_TARGETS.keys())
        if targets:
            idx = int(self._rot_timer.remainingTime() / 100) % len(targets) if hasattr(self._rot_timer, 'remainingTime') else 0
            self.sphere.set_highlight_index(idx % len(targets))


# ═══════════════════════════════════════════════════════════════════════════════
# 球体部件
# ═══════════════════════════════════════════════════════════════════════════════

class _SphereWidget(QFrame):
    """导航球内部球体"""
    
    navigation_requested = pyqtSignal(str)
    
    NAV_TARGETS = [
        ("trade_deck", "💬", HolographicColors.HOLO_GREEN),
        ("comm_array", "📡", HolographicColors.HOLO_SECONDARY),
        ("oracle_core", "🔮", HolographicColors.HOLO_PURPLE),
        ("intelligence", "🎯", HolographicColors.HOLO_ORANGE),
        ("market", "🛒", HolographicColors.HOLO_GOLD),
        ("settings", "⚙️", HolographicColors.TEXT_DIM),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self._highlight_index = 0
        self._hover_index = -1
        self._rotation = 0
        self._target_positions = {}
        self._update_positions()
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def _update_positions(self):
        """更新目标位置"""
        self._target_positions = {}
        for i, (target_id, icon, color) in enumerate(self.NAV_TARGETS):
            # 球面上均匀分布
            phi = (i / len(self.NAV_TARGETS)) * 2 * math.pi
            theta = math.pi / 4  # 仰角
            
            x = 0.5 + 0.35 * math.cos(phi) * math.sin(theta)
            y = 0.5 - 0.35 * math.cos(theta) + 0.1
            
            self._target_positions[i] = {
                "target_id": target_id,
                "x": x,
                "y": y,
                "icon": icon,
                "color": color
            }
    
    def set_highlight_index(self, index: int):
        """设置高亮索引"""
        self._highlight_index = index
        self.update()
    
    def paintEvent(self, event):
        """绘制球体"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        radius = min(w, h) // 2 - 5
        
        # 球体渐变背景
        sphere_gradient = QRadialGradient(cx - radius/3, cy - radius/3, radius)
        sphere_gradient.setColorAt(0, QColor(HolographicColors.BACKGROUND_CARD))
        sphere_gradient.setColorAt(0.5, QColor(HolographicColors.BACKGROUND_PANEL))
        sphere_gradient.setColorAt(1, QColor(HolographicColors.BACKGROUND_DEEP))
        
        # 球体外框
        border_gradient = QRadialGradient(cx, cy, radius)
        border_gradient.setColorAt(0.8, QColor(HolographicColors.HOLO_PRIMARY).darker(150))
        border_gradient.setColorAt(0.95, QColor(HolographicColors.HOLO_PRIMARY).darker(200))
        border_gradient.setColorAt(1, QColor(HolographicColors.HOLO_PRIMARY).darker(300))
        
        painter.setBrush(QBrush(border_gradient))
        painter.setPen(Qt.GlobalColor.transparent)
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
        
        # 内球面
        inner_radius = radius - 4
        painter.setBrush(QBrush(sphere_gradient))
        painter.drawEllipse(cx - inner_radius, cy - inner_radius, 
                           inner_radius * 2, inner_radius * 2)
        
        # 赤道线 (装饰)
        equator_color = QColor(HolographicColors.HOLO_PRIMARY)
        equator_color.setAlpha(30)
        pen = QPen(equator_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawEllipse(cx - radius + 10, cy - 2, (radius - 10) * 2, 4)
        
        # 经线 (装饰)
        for i in range(4):
            angle = i * math.pi / 2 + self._rotation * 0.01
            x1 = cx + math.cos(angle) * (radius - 10)
            y1 = cy
            x2 = cx - math.cos(angle) * (radius - 10)
            y2 = cy
            
            painter.drawLine(x1, y1 - radius + 10, x2, y2 - radius + 10)
            painter.drawLine(x1, y1 + radius - 10, x2, y2 + radius - 10)
        
        # 绘制目标点
        self._draw_targets(painter, cx, cy, inner_radius - 8)
        
        # 中心光点
        center_gradient = QRadialGradient(cx, cy, 10)
        center_gradient.setColorAt(0, QColor(HolographicColors.HOLO_GLOW))
        center_gradient.setColorAt(0.5, QColor(HolographicColors.HOLO_PRIMARY).lighter(150))
        center_gradient.setColorAt(1, Qt.GlobalColor.transparent)
        painter.setBrush(QBrush(center_gradient))
        painter.setPen(Qt.GlobalColor.transparent)
        painter.drawEllipse(cx - 10, cy - 10, 20, 20)
        
        # 旋转动画
        self._rotation += 1
    
    def _draw_targets(self, painter: QPainter, cx: float, cy: float, radius: float):
        """绘制目标点"""
        for i, pos in self._target_positions.items():
            x = cx + (pos["x"] - 0.5) * radius * 2
            y = cy + (pos["y"] - 0.5) * radius * 2
            
            # 检查是否悬停
            is_highlight = (i == self._highlight_index)
            is_hover = (i == self._hover_index)
            
            # 目标颜色
            color = QColor(pos["color"])
            
            # 高亮效果
            if is_highlight or is_hover:
                # 外发光
                glow_gradient = QRadialGradient(x, y, 20)
                glow_color = color.lighter(200)
                glow_color.setAlpha(100)
                glow_gradient.setColorAt(0, glow_color)
                glow_gradient.setColorAt(1, Qt.GlobalColor.transparent)
                painter.setBrush(QBrush(glow_gradient))
                painter.setPen(Qt.GlobalColor.transparent)
                painter.drawEllipse(x - 20, y - 20, 40, 40)
                
                # 高亮圈
                pen = QPen(color, 2)
                painter.setPen(pen)
                painter.drawEllipse(x - 12, y - 12, 24, 24)
            
            # 目标点
            bg_color = color if (is_highlight or is_hover) else color.darker(150)
            painter.setBrush(QBrush(bg_color))
            painter.setPen(QPen(color.lighter(150), 1))
            painter.drawEllipse(x - 8, y - 8, 16, 16)
            
            # 图标
            icon = pos["icon"]
            font = QFont()
            font.setPointSize(8)
            painter.setFont(font)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(int(x) - 5, int(y) + 4, icon)
    
    def mouseMoveEvent(self, event):
        """鼠标移动"""
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        radius = min(w, h) // 2 - 13
        
        mx = event.position().x()
        my = event.position().y()
        
        # 计算悬停的索引
        self._hover_index = -1
        for i, pos in self._target_positions.items():
            x = cx + (pos["x"] - 0.5) * radius * 2
            y = cy + (pos["y"] - 0.5) * radius * 2
            
            dist = math.sqrt((mx - x) ** 2 + (my - y) ** 2)
            if dist < 15:
                self._hover_index = i
                break
        
        self.update()
        super().mouseMoveEvent(event)
    
    def mousePressEvent(self, event):
        """鼠标点击"""
        if self._hover_index >= 0:
            target_id = self._target_positions[self._hover_index]["target_id"]
            self.navigation_requested.emit(target_id)
        super().mousePressEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开"""
        self._hover_index = -1
        self.update()
        super().leaveEvent(event)


# ═══════════════════════════════════════════════════════════════════════════════
# 导出
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    'NavigationSphere',
]
