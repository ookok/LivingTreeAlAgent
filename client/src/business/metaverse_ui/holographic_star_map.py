"""
全息星图 - Holographic Star Map
时空引力场可视化 - 节点是星光，交易意向是引力线
"""

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal, QEasingCurve
from PyQt6.QtWidgets import QWidget, QGraphicsView, QGraphicsScene, QGraphicsItem
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QLinearGradient, QFont, QTransform, QPainterPath
from PyQt6.QtCore import QPropertyAnimation, pyqtProperty
import math
import random

from .bridge_styles import HolographicColors


# ═══════════════════════════════════════════════════════════════════════════════
# 全息节点
# ═══════════════════════════════════════════════════════════════════════════════

class HolographicNode(QGraphicsItem):
    """全息节点 - 星图中的一个节点"""
    
    # 信号
    clicked = pyqtSignal(str)  # 节点ID
    
    TYPE_SELLER = "seller"
    TYPE_BUYER = "buyer"
    TYPE_TRADE = "trade"
    TYPE_NEUTRAL = "neutral"
    
    def __init__(self, node_id: str, node_type: str = TYPE_NEUTRAL, 
                 pos: QPointF = None, size: float = 20):
        super().__init__()
        self.node_id = node_id
        self.node_type = node_type
        self._size = size
        self._glow_size = size * 2
        self._pulse_phase = random.random() * 2 * math.pi
        
        # 设置位置
        if pos:
            self.setPos(pos)
        
        # 节点属性
        self.activity = random.random()  # 活跃度 0-1
        self.intent_strength = random.uniform(0.3, 1.0)  # 意向强度
        
        # 可点击
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        
        # 颜色
        self._colors = {
            self.TYPE_SELLER: QColor(HolographicColors.HOLO_GREEN),
            self.TYPE_BUYER: QColor(HolographicColors.HOLO_ORANGE),
            self.TYPE_TRADE: QColor(HolographicColors.HOLO_GOLD),
            self.TYPE_NEUTRAL: QColor(HolographicColors.HOLO_PRIMARY),
        }
        self._base_color = self._colors.get(node_type, self._colors[self.TYPE_NEUTRAL])
    
    def boundingRect(self) -> QRectF:
        margin = self._glow_size
        return QRectF(-margin, -margin, margin * 2, margin * 2)
    
    def paint(self, painter: QPainter, option, widget=None):
        """绘制节点"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 脉冲动画
        pulse = (math.sin(self._pulse_phase) + 1) / 2
        glow_opacity = 0.3 + pulse * 0.4
        
        # 外发光
        glow_brush = QBrush(self._base_color)
        glow_brush.setColor(self._base_color)
        glow_brush.setColor(self._base_color.lighter(150))
        glow_brush.color().setAlpha(int(255 * glow_opacity))
        
        # 绘制外发光圆
        glow_gradient = QRadialGradient(self.boundingRect().center(), self._glow_size)
        glow_color = self._base_color.lighter(180)
        glow_color.setAlpha(int(255 * glow_opacity * 0.5))
        glow_gradient.setColorAt(0, glow_color)
        glow_gradient.setColorAt(0.5, self._base_color.lighter(120))
        glow_gradient.setColorAt(1, Qt.GlobalColor.transparent)
        
        glow_pen = QPen(Qt.GlobalColor.transparent)
        painter.setPen(glow_pen)
        painter.setBrush(QBrush(glow_gradient))
        painter.drawEllipse(self.boundingRect())
        
        # 绘制主体圆
        size = self._size * (0.8 + pulse * 0.2)
        
        # 根据活跃度调整颜色亮度
        color = self._base_color.lighter(int(100 + self.activity * 100))
        
        # 外圈
        pen = QPen(color.darker(150))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QBrush(color.lighter(120)))
        painter.drawEllipse(QPointF(0, 0), size, size)
        
        # 内核
        inner_gradient = QRadialGradient(QPointF(0, 0), size * 0.6)
        inner_gradient.setColorAt(0, color.lighter(200))
        inner_gradient.setColorAt(0.7, color)
        inner_gradient.setColorAt(1, color.darker(130))
        painter.setBrush(QBrush(inner_gradient))
        painter.setPen(Qt.GlobalColor.transparent)
        painter.drawEllipse(QPointF(0, 0), size * 0.7, size * 0.7)
        
        # 高光
        highlight = QBrush(color.lighter(250))
        painter.setBrush(highlight)
        painter.drawEllipse(QPointF(-size * 0.2, -size * 0.2), size * 0.25, size * 0.25)
        
        # 绘制意向强度指示器 (周围的弧线)
        if self.intent_strength > 0.5:
            self._draw_intent_arc(painter, size)
    
    def _draw_intent_arc(self, painter: QPainter, size: float):
        """绘制意向弧线"""
        pen = QPen(self._base_color.lighter(150))
        pen.setWidth(2)
        pen.setDashPattern([4, 4])
        painter.setPen(pen)
        
        # 根据意向强度绘制弧
        arc_angle = int(self.intent_strength * 270)
        rect = QRectF(-size * 1.5, -size * 1.5, size * 3, size * 3)
        painter.drawArc(rect, -90 * 16, arc_angle * 16)
    
    def hoverEnterEvent(self, event):
        """悬停事件"""
        self._size *= 1.2
        self.update()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """悬停离开"""
        self._size /= 1.2
        self.update()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.node_id)
        super().mousePressEvent(event)
    
    def advance(self, phase: int):
        """推进动画"""
        if phase == 1:
            self._pulse_phase += 0.05
            self.update()


# ═══════════════════════════════════════════════════════════════════════════════
# 引力线
# ═══════════════════════════════════════════════════════════════════════════════

class GravityLine(QGraphicsItem):
    """引力线 - 连接节点"""
    
    def __init__(self, start_node: HolographicNode, end_node: HolographicNode,
                 strength: float = 0.5):
        super().__init__()
        self.start_node = start_node
        self.end_node = end_node
        self.strength = strength
        self._phase = random.random() * 2 * math.pi
        self._flow_direction = 1 if random.random() > 0.5 else -1
        
        # 设置Z值在节点之下
        self.setZValue(-1)
    
    def boundingRect(self) -> QRectF:
        return QRectF(
            min(self.start_node.x(), self.end_node.x()) - 50,
            min(self.start_node.y(), self.end_node.y()) - 50,
            abs(self.end_node.x() - self.start_node.x()) + 100,
            abs(self.end_node.y() - self.start_node.y()) + 100
        )
    
    def paint(self, painter: QPainter, option, widget=None):
        """绘制引力线"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        start = self.start_node.scenePos()
        end = self.end_node.scenePos()
        
        # 脉冲效果
        pulse = (math.sin(self._phase) + 1) / 2
        
        # 线条颜色
        line_color = QColor(HolographicColors.HOLO_PRIMARY)
        line_color.setAlpha(int(80 + pulse * 80 * self.strength))
        
        # 外发光
        pen_glow = QPen(line_color.lighter(150))
        pen_glow.setWidth(int(4 + pulse * 2))
        pen_glow.setColor(line_color.lighter(150))
        pen_glow.color().setAlpha(int(50 * pulse))
        painter.setPen(pen_glow)
        painter.drawLine(start, end)
        
        # 主体线
        pen_main = QPen(line_color)
        pen_main.setWidth(int(1 + pulse))
        painter.setPen(pen_main)
        painter.drawLine(start, end)
        
        # 绘制流动粒子
        if self.strength > 0.3:
            self._draw_flow_particles(painter, start, end, pulse)
    
    def _draw_flow_particles(self, painter: QPainter, start: QPointF, end: QPointF, pulse: float):
        """绘制流动粒子"""
        # 计算方向
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.sqrt(dx * dx + dy * dy)
        
        if length < 1:
            return
        
        # 粒子位置
        t = (pulse + self._phase / (2 * math.pi)) % 1
        particle_x = start.x() + dx * t
        particle_y = start.y() + dy * t
        
        # 绘制粒子
        particle_color = QColor(HolographicColors.HOLO_GLOW)
        particle_color.setAlpha(int(200 * pulse))
        
        pen = QPen(particle_color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QBrush(particle_color.lighter(150)))
        painter.drawEllipse(QPointF(particle_x, particle_y), 4, 4)
    
    def advance(self, phase: int):
        """推进动画"""
        if phase == 1:
            self._phase += 0.03 * self.strength
            self.update()


# ═══════════════════════════════════════════════════════════════════════════════
# 全息星图场景
# ═══════════════════════════════════════════════════════════════════════════════

class HolographicStarMapScene(QGraphicsScene):
    """全息星图场景"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-500, -400, 1000, 800)
        self.setBackgroundBrush(QBrush(QColor(HolographicColors.BACKGROUND_DEEP)))
        
        # 节点和引力线
        self.nodes = []
        self.lines = []
        
        # 绘制背景网格
        self._draw_background_grid()
    
    def _draw_background_grid(self):
        """绘制背景网格"""
        # 将在paint事件中绘制
    
    def add_node(self, node: HolographicNode):
        """添加节点"""
        self.nodes.append(node)
        self.addItem(node)
    
    def remove_node(self, node_id: str):
        """移除节点"""
        for node in self.nodes:
            if node.node_id == node_id:
                self.nodes.remove(node)
                self.removeItem(node)
                break
    
    def connect_nodes(self, node1_id: str, node2_id: str, strength: float = 0.5):
        """连接两个节点"""
        node1 = self._find_node(node1_id)
        node2 = self._find_node(node2_id)
        
        if node1 and node2:
            line = GravityLine(node1, node2, strength)
            self.lines.append(line)
            self.addItem(line)
    
    def _find_node(self, node_id: str) -> HolographicNode:
        """查找节点"""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None
    
    def advance(self):
        """推进所有动画"""
        for node in self.nodes:
            node.advance(1)
        for line in self.lines:
            line.advance(1)


# ═══════════════════════════════════════════════════════════════════════════════
# 全息星图视图
# ═══════════════════════════════════════════════════════════════════════════════

class HolographicStarMap(QGraphicsView):
    """
    全息星图视图
    显示时空引力场，节点是星光，交易意向是引力线
    """
    
    node_selected = pyqtSignal(str)  # 节点ID
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 场景
        self.scene = HolographicStarMapScene(self)
        self.setScene(self.scene)
        
        # 视图设置
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setBackgroundBrush(QBrush(QColor(HolographicColors.BACKGROUND_DEEP)))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        
        # 缩放
        self._zoom = 1.0
        self.setMinimumSize(400, 300)
        
        # 中心节点
        self._center_node_id = "node_8848"
        
        # 初始化节点
        self._init_demo_nodes()
        
        # 动画定时器
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(50)
    
    def _init_demo_nodes(self):
        """初始化演示节点"""
        # 中心节点 (自己)
        center = HolographicNode(self._center_node_id, HolographicNode.TYPE_NEUTRAL, 
                                  QPointF(0, 0), 30)
        self.scene.add_node(center)
        
        # 周围的节点
        positions = [
            (QPointF(-200, -100), HolographicNode.TYPE_SELLER, "seller_001"),
            (QPointF(180, -150), HolographicNode.TYPE_BUYER, "buyer_001"),
            (QPointF(220, 80), HolographicNode.TYPE_SELLER, "seller_002"),
            (QPointF(-180, 120), HolographicNode.TYPE_TRADE, "trade_001"),
            (QPointF(-50, -220), HolographicNode.TYPE_BUYER, "buyer_002"),
            (QPointF(100, 200), HolographicNode.TYPE_SELLER, "seller_003"),
            (QPointF(-250, -50), HolographicNode.TYPE_NEUTRAL, "node_x"),
            (QPointF(50, -180), HolographicNode.TYPE_TRADE, "trade_002"),
        ]
        
        for pos, ntype, nid in positions:
            node = HolographicNode(nid, ntype, pos, 18)
            node.clicked.connect(self._on_node_clicked)
            self.scene.add_node(node)
            
            # 连接到中心
            self.scene.connect_nodes(self._center_node_id, nid, random.uniform(0.3, 0.9))
        
        # 连接一些节点之间的引力线
        self.scene.connect_nodes("seller_001", "buyer_001", 0.7)
        self.scene.connect_nodes("seller_002", "buyer_002", 0.5)
        self.scene.connect_nodes("trade_001", "seller_003", 0.6)
    
    def _on_node_clicked(self, node_id: str):
        """节点被点击"""
        self.node_selected.emit(node_id)
    
    def _animate(self):
        """动画循环"""
        self.scene.advance()
        self.update()
    
    def refresh_nodes(self):
        """刷新节点 (重新生成)"""
        # 清空
        for node in self.scene.nodes[:]:
            self.scene.removeItem(node)
        for line in self.scene.lines[:]:
            self.scene.removeItem(line)
        self.scene.nodes.clear()
        self.scene.lines.clear()
        
        # 重新初始化
        self._init_demo_nodes()
    
    def set_node_id(self, node_id: str):
        """设置中心节点ID"""
        self._center_node_id = node_id
        # 重建
        self.refresh_nodes()
    
    def wheelEvent(self, event):
        """鼠标滚轮缩放"""
        delta = event.angleDelta().y()
        zoom_factor = 1.1 if delta > 0 else 0.9
        
        new_zoom = self._zoom * zoom_factor
        if 0.3 <= new_zoom <= 3.0:
            self._zoom = new_zoom
            self.scale(zoom_factor, zoom_factor)
    
    def drawBackground(self, painter: QPainter, rect: QRectF):
        """绘制背景"""
        super().drawBackground(painter, rect)
        
        # 绘制网格
        self._draw_grid(painter, rect)
        
        # 绘制星空背景
        self._draw_stars(painter, rect)
    
    def _draw_grid(self, painter: QPainter, rect: QRectF):
        """绘制全息网格"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        grid_color = QColor(HolographicColors.HOLO_PRIMARY)
        grid_color.setAlpha(20)
        pen = QPen(grid_color)
        pen.setWidth(1)
        painter.setPen(pen)
        
        spacing = 50
        
        # 垂直线
        x = rect.left() - rect.left() % spacing
        while x <= rect.right():
            painter.drawLine(x, rect.top(), x, rect.bottom())
            x += spacing
        
        # 水平线
        y = rect.top() - rect.top() % spacing
        while y <= rect.bottom():
            painter.drawLine(rect.left(), y, rect.right(), y)
            y += spacing
        
        # 中心十字线
        center = self.sceneRect().center()
        cross_color = QColor(HolographicColors.HOLO_PRIMARY)
        cross_color.setAlpha(40)
        pen_cross = QPen(cross_color)
        pen_cross.setWidth(2)
        painter.setPen(pen_cross)
        
        painter.drawLine(center.x() - 100, center.y(), center.x() + 100, center.y())
        painter.drawLine(center.x(), center.y() - 100, center.x(), center.y() + 100)
    
    def _draw_stars(self, painter: QPainter, rect: QRectF):
        """绘制背景星星"""
        import random
        random.seed(42)  # 固定种子，保持一致
        
        star_count = 100
        for _ in range(star_count):
            x = random.uniform(rect.left(), rect.right())
            y = random.uniform(rect.top(), rect.bottom())
            size = random.uniform(0.5, 2)
            
            star_color = QColor(255, 255, 255)
            star_color.setAlpha(random.randint(20, 80))
            
            painter.setBrush(QBrush(star_color))
            painter.setPen(Qt.GlobalColor.transparent)
            painter.drawEllipse(x, y, size, size)


# ═══════════════════════════════════════════════════════════════════════════════
# 导出
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    'HolographicNode',
    'GravityLine',
    'HolographicStarMapScene',
    'HolographicStarMap',
]
