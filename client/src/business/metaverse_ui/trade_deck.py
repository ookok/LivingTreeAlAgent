"""
星际贸易舱 - Trade Deck
商品全息投影界面，支持拖拽上架
"""

from PyQt6.QtCore import Qt, QTimer, QPointF, pyqtSignal, QEasingCurve, QPropertyAnimation, QRectF
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QFrame, QPushButton, QScrollArea,
                             QGraphicsView, QGraphicsScene, QGraphicsItem,
                             QListWidget, QListWidgetItem)
from PyQt6.QtGui import (QPainter, QColor, QBrush, QPen, QLinearGradient,
                          QFont, QDragEnterEvent, QPixmap, QImage, QDropEvent)
from PyQt6.QtCore import pyqtProperty
import math
import random
from datetime import datetime

from .bridge_styles import HolographicColors, HolographicFonts


# ═══════════════════════════════════════════════════════════════════════════════
# 商品全息投影项
# ═══════════════════════════════════════════════════════════════════════════════

class HolographicProductItem(QGraphicsItem):
    """商品全息投影项 - 悬浮旋转展示"""
    
    def __init__(self, product_data: dict, size: float = 150):
        super().__init__()
        self.product_data = product_data
        self._size = size
        self._rotation = 0
        self._hovered = False
        
        # 可点击
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        
        # 动画
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(30)
        
        # 属性
        self.title = product_data.get("title", "未知商品")
        self.price = product_data.get("price", 0)
        self.currency = product_data.get("currency", "¥")
        self.condition = product_data.get("condition", "new")
        self.category = product_data.get("category", "misc")
        self.image_path = product_data.get("image_path", "")
        
        # 颜色方案
        condition_colors = {
            "new": HolographicColors.HOLO_GREEN,
            "used": HolographicColors.HOLO_ORANGE,
            "refurbished": HolographicColors.HOLO_PURPLE,
        }
        self.condition_color = QColor(condition_colors.get(self.condition, HolographicColors.HOLO_PRIMARY))
    
    def boundingRect(self) -> QRectF:
        return QRectF(-self._size/2, -self._size/2, self._size, self._size)
    
    def paint(self, painter: QPainter, option, widget=None):
        """绘制商品全息投影"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # 浮动动画
        float_y = math.sin(self._rotation * 0.1) * 5
        
        # 缩放 (悬停时放大)
        scale = 1.15 if self._hovered else 1.0
        
        # 应用变换
        painter.save()
        painter.translate(0, float_y)
        painter.scale(scale, scale)
        
        # 外发光
        glow_rect = self.boundingRect().adjusted(-20, -20, 20, 20)
        glow_gradient = QRadialGradient(QPointF(0, 0), self._size * 0.8)
        glow_color = self.condition_color.lighter(150)
        glow_color.setAlpha(50 if not self._hovered else 100)
        glow_gradient.setColorAt(0, glow_color)
        glow_gradient.setColorAt(0.5, self.condition_color.lighter(120))
        glow_gradient.setColorAt(1, Qt.GlobalColor.transparent)
        painter.setPen(Qt.GlobalColor.transparent)
        painter.setBrush(QBrush(glow_gradient))
        painter.drawEllipse(glow_rect)
        
        # 全息卡片背景
        card_rect = QRectF(-self._size/2 + 10, -self._size/2 + 10, self._size - 20, self._size - 20)
        
        # 卡片渐变背景
        card_gradient = QLinearGradient(card_rect.topLeft(), card_rect.bottomRight())
        card_gradient.setColorAt(0, QColor(HolographicColors.BACKGROUND_CARD))
        card_gradient.setColorAt(0.5, QColor(HolographicColors.BACKGROUND_PANEL))
        card_gradient.setColorAt(1, QColor(HolographicColors.BACKGROUND_CARD))
        
        card_pen = QPen(self.condition_color)
        card_pen.setWidth(2)
        painter.setPen(card_pen)
        painter.setBrush(QBrush(card_gradient))
        painter.drawRoundedRect(card_rect, 15, 15)
        
        # 绘制商品图片占位符
        img_rect = QRectF(card_rect.x() + 10, card_rect.y() + 10, 
                         card_rect.width() - 20, card_rect.height() * 0.6)
        
        # 图片背景
        img_gradient = QLinearGradient(img_rect.topLeft(), img_rect.bottomRight())
        img_gradient.setColorAt(0, QColor(HolographicColors.HOLO_PRIMARY).lighter(150))
        img_gradient.setColorAt(1, QColor(HolographicColors.HOLO_SECONDARY).darker(130))
        painter.setPen(Qt.GlobalColor.transparent)
        painter.setBrush(QBrush(img_gradient))
        painter.drawRoundedRect(img_rect, 8, 8)
        
        # 商品图标/文字
        icon_font = HolographicFonts.get_font(36, QFont.Weight.Bold)
        painter.setFont(icon_font)
        painter.setPen(self.condition_color)
        painter.drawText(img_rect, Qt.AlignmentFlag.AlignCenter, "📦")
        
        # 标题
        title_rect = QRectF(card_rect.x(), card_rect.y() + card_rect.height() * 0.6,
                           card_rect.width(), card_rect.height() * 0.2)
        title_font = HolographicFonts.get_font(11, QFont.Weight.Bold)
        painter.setFont(title_font)
        title_color = QColor(HolographicColors.TEXT_PRIMARY)
        painter.setPen(title_color)
        
        # 截断标题
        title = self.title[:12] + "..." if len(self.title) > 12 else self.title
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, title)
        
        # 价格
        price_rect = QRectF(card_rect.x(), card_rect.y() + card_rect.height() * 0.8,
                           card_rect.width(), card_rect.height() * 0.2)
        price_font = HolographicFonts.get_font(14, QFont.Weight.Bold)
        painter.setFont(price_font)
        price_color = QColor(HolographicColors.HOLO_GOLD)
        painter.setPen(price_color)
        price_text = f"{self.currency}{self.price:,.0f}"
        painter.drawText(price_rect, Qt.AlignmentFlag.AlignCenter, price_text)
        
        # 边框装饰
        self._draw_corner_decorations(painter, card_rect)
        
        painter.restore()
        
        # 悬浮时显示参数光环
        if self._hovered:
            self._draw_params_halo(painter)
    
    def _draw_corner_decorations(self, painter: QPainter, rect: QRectF):
        """绘制角落装饰"""
        corner_size = 8
        painter.setPen(QPen(self.condition_color.lighter(150), 2))
        
        # 左上角
        painter.drawLine(rect.topLeft().x(), rect.topLeft().y() + corner_size,
                        rect.topLeft().x(), rect.topLeft().y())
        painter.drawLine(rect.topLeft().x(), rect.topLeft().y(),
                        rect.topLeft().x() + corner_size, rect.topLeft().y())
        
        # 右上角
        painter.drawLine(rect.topRight().x() - corner_size, rect.topRight().y(),
                        rect.topRight().x(), rect.topRight().y())
        painter.drawLine(rect.topRight().x(), rect.topRight().y(),
                        rect.topRight().x(), rect.topRight().y() + corner_size)
        
        # 左下角
        painter.drawLine(rect.bottomLeft().x(), rect.bottomLeft().y() - corner_size,
                        rect.bottomLeft().x(), rect.bottomLeft().y())
        painter.drawLine(rect.bottomLeft().x(), rect.bottomLeft().y(),
                        rect.bottomLeft().x() + corner_size, rect.bottomLeft().y())
        
        # 右下角
        painter.drawLine(rect.bottomRight().x() - corner_size, rect.bottomRight().y(),
                        rect.bottomRight().x(), rect.bottomRight().y())
        painter.drawLine(rect.bottomRight().x(), rect.bottomRight().y() - corner_size,
                        rect.bottomRight().x(), rect.bottomRight().y())
    
    def _draw_params_halo(self, painter: QPainter):
        """绘制参数光环 (HUD风格)"""
        halo_color = QColor(HolographicColors.HOLO_GLOW)
        halo_color.setAlpha(100)
        pen = QPen(halo_color)
        pen.setWidth(1)
        pen.setDashPattern([3, 3])
        painter.setPen(pen)
        
        halo_rect = self.boundingRect().adjusted(-10, -10, 10, 10)
        painter.drawRect(halo_rect)
        
        # 参数文字
        params = [
            f"类别: {self.category}",
            f"成色: {self.condition}",
            f"价格: {self.currency}{self.price}",
        ]
        
        font = HolographicFonts.mono_font(9)
        painter.setFont(font)
        painter.setPen(halo_color)
        
        y = halo_rect.bottom() + 15
        for param in params:
            painter.drawText(-30, y, param)
            y += 12
    
    def _animate(self):
        """动画"""
        self._rotation += 1
        self.update()
    
    def hoverEnterEvent(self, event):
        """悬停"""
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        """悬停离开"""
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)


# ═══════════════════════════════════════════════════════════════════════════════
# 商品场景
# ═══════════════════════════════════════════════════════════════════════════════

class ProductDisplayScene(QGraphicsScene):
    """商品展示场景"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-300, -200, 600, 400)
        self.setBackgroundBrush(QBrush(QColor(HolographicColors.BACKGROUND_DEEP)))
        
        self.products = []
    
    def add_product(self, product_data: dict):
        """添加商品"""
        # 网格布局
        index = len(self.products)
        row = index // 3
        col = index % 3
        
        x = -200 + col * 180
        y = -150 + row * 180
        
        item = HolographicProductItem(product_data, size=140)
        item.setPos(x, y)
        self.addItem(item)
        self.products.append(item)


# ═══════════════════════════════════════════════════════════════════════════════
# 物质重组器 (拖拽上传区)
# ═══════════════════════════════════════════════════════════════════════════════

class MatterReorganizer(QFrame):
    """
    物质重组器 - 拖拽图片上传区域
    用户拖拽图片到这里，AI扫描生成全息草案
    """
    
    image_dropped = pyqtSignal(list)  # 图片路径列表
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.setAcceptDrops(True)
    
    def _init_ui(self):
        """初始化UI"""
        self.setObjectName("HoloCard")
        self.setMinimumHeight(150)
        self.setMaximumHeight(200)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 图标
        self.icon_label = QLabel("🔮")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 48px;")
        layout.addWidget(self.icon_label)
        
        # 标题
        self.title_label = QLabel("物质重组器")
        self.title_label.setObjectName("HoloLabelTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(f"color: {HolographicColors.HOLO_PRIMARY};")
        layout.addWidget(self.title_label)
        
        # 提示
        self.hint_label = QLabel("拖拽图片到这里，AI将扫描生成全息草案")
        self.hint_label.setObjectName("HoloLabelDim")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)
        
        # 状态指示器
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_dropping(True)
    
    def dragLeaveEvent(self, event):
        """拖拽离开"""
        self._set_dropping(False)
    
    def dropEvent(self, event):
        """放下"""
        self._set_dropping(False)
        
        urls = event.mimeData().urls()
        if urls:
            paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            if paths:
                self.status_label.setText("⏳ 正在扫描...")
                self.status_label.setStyleSheet(f"color: {HolographicColors.HOLO_ORANGE};")
                self.image_dropped.emit(paths)
    
    def _set_dropping(self, dropping: bool):
        """设置拖拽状态"""
        if dropping:
            self.setStyleSheet(f"""
                QFrame {{
                    border: 2px dashed {HolographicColors.HOLO_PRIMARY};
                    background: {HolographicColors.HOLO_PRIMARY}22;
                }}
            """)
            self.hint_label.setText("松开以扫描...")
        else:
            self.setStyleSheet("")
            self.hint_label.setText("拖拽图片到这里，AI将扫描生成全息草案")
            self.status_label.setText("")
    
    def set_scanning(self, scanning: bool):
        """设置扫描状态"""
        if scanning:
            self.icon_label.setText("⚙️")
            self.title_label.setText("扫描中...")
        else:
            self.icon_label.setText("🔮")
            self.title_label.setText("物质重组器")
    
    def show_result(self, category: str, confidence: float):
        """显示扫描结果"""
        self.status_label.setText(f"✓ 识别: {category} (置信度: {confidence:.0%})")
        self.status_label.setStyleSheet(f"color: {HolographicColors.HOLO_GREEN};")


# ═══════════════════════════════════════════════════════════════════════════════
# 撮合雷达
# ═══════════════════════════════════════════════════════════════════════════════

class MatchingRadar(QFrame):
    """撮合雷达 - 显示附近匹配"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._pulse_phase = 0
        self._matches = []
        
        # 动画
        self._timer = QTimer()
        self._timer.timeout.connect(self._animate)
        self._timer.start(50)
    
    def _init_ui(self):
        """初始化UI"""
        self.setMinimumSize(150, 150)
        self.setMaximumSize(200, 200)
        
        # 标题
        layout = QVBoxLayout(self)
        title = QLabel("◈ 撮合雷达")
        title.setObjectName("HoloLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
    
    def paintEvent(self, event):
        """绘制雷达"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        radius = min(w, h) // 2 - 20
        
        # 背景
        painter.fillRect(self.rect(), QColor(HolographicColors.BACKGROUND_DEEP))
        
        # 外圈
        for i in range(3):
            r = radius - i * (radius // 4)
            color = QColor(HolographicColors.HOLO_PRIMARY)
            color.setAlpha(30 + i * 20)
            pen = QPen(color)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        
        # 十字线
        cross_color = QColor(HolographicColors.HOLO_PRIMARY)
        cross_color.setAlpha(40)
        pen_cross = QPen(cross_color)
        pen_cross.setWidth(1)
        painter.setPen(pen_cross)
        painter.drawLine(cx - radius, cy, cx + radius, cy)
        painter.drawLine(cx, cy - radius, cx, cy + radius)
        
        # 脉冲波纹
        pulse = (math.sin(self._pulse_phase) + 1) / 2
        pulse_color = QColor(HolographicColors.HOLO_ORANGE)
        pulse_color.setAlpha(int(100 * (1 - pulse)))
        pen_pulse = QPen(pulse_color)
        pen_pulse.setWidth(2)
        painter.setPen(pen_pulse)
        pulse_radius = radius * pulse
        painter.drawEllipse(cx - pulse_radius, cy - pulse_radius, 
                           pulse_radius * 2, pulse_radius * 2)
        
        # 匹配点
        for match in self._matches:
            angle = match.get("angle", 0)  # 弧度
            dist = match.get("distance", 0.5)  # 0-1
            
            mx = cx + math.cos(angle) * dist * radius
            my = cy + math.sin(angle) * dist * radius
            
            match_type = match.get("type", "buyer")
            color = QColor(HolographicColors.HOLO_GREEN) if match_type == "buyer" else QColor(HolographicColors.HOLO_ORANGE)
            
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.GlobalColor.transparent)
            painter.drawEllipse(mx - 5, my - 5, 10, 10)
        
        # 中心点
        center_gradient = QRadialGradient(cx, cy, 15)
        center_gradient.setColorAt(0, QColor(HolographicColors.HOLO_PRIMARY))
        center_gradient.setColorAt(1, Qt.GlobalColor.transparent)
        painter.setBrush(QBrush(center_gradient))
        painter.setPen(Qt.GlobalColor.transparent)
        painter.drawEllipse(cx - 15, cy - 15, 30, 30)
    
    def _animate(self):
        """动画"""
        self._pulse_phase += 0.1
        self.update()
    
    def add_match(self, match_type: str, distance: float = 0.5):
        """添加匹配点"""
        angle = random.uniform(0, 2 * math.pi)
        self._matches.append({
            "type": match_type,
            "angle": angle,
            "distance": distance
        })
        
        # 限制数量
        if len(self._matches) > 10:
            self._matches.pop(0)
        
        self.update()
    
    def clear_matches(self):
        """清除匹配"""
        self._matches.clear()
        self.update()


# ═══════════════════════════════════════════════════════════════════════════════
# 星际贸易舱
# ═══════════════════════════════════════════════════════════════════════════════

class TradeDeck(QWidget):
    """
    星际贸易舱
    整合: 物质重组器 + 商品展示 + 撮合雷达
    """
    
    listing_published = pyqtSignal(dict)  # 商品发布信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._init_demo_products()
    
    def _init_ui(self):
        """初始化UI"""
        self.setStyleSheet(get_bridge_stylesheet())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # ═══════════════════════════════════════════════════════════════
        # 顶部: 标题栏
        # ═══════════════════════════════════════════════════════════════
        header = QFrame()
        header_layout = QHBoxLayout(header)
        
        title = QLabel("◈ 星际贸易舱")
        title.setObjectName("HoloLabelTitle")
        title.setStyleSheet(f"color: {HolographicColors.HOLO_PRIMARY}; font-size: 18px;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # 撮合雷达
        self.radar = MatchingRadar()
        header_layout.addWidget(self.radar)
        
        layout.addWidget(header)
        
        # ═══════════════════════════════════════════════════════════════
        # 中部: 物质重组器
        # ═══════════════════════════════════════════════════════════════
        self.reorganizer = MatterReorganizer()
        self.reorganizer.image_dropped.connect(self._on_images_dropped)
        layout.addWidget(self.reorganizer)
        
        # ═══════════════════════════════════════════════════════════════
        # 商品展示
        # ═══════════════════════════════════════════════════════════════
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.product_scene = ProductDisplayScene()
        self.product_view = QGraphicsView(self.product_scene)
        self.product_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.product_view.setBackgroundBrush(QBrush(QColor(HolographicColors.BACKGROUND_DEEP)))
        
        scroll.setWidget(self.product_view)
        layout.addWidget(scroll, 1)
        
        # ═══════════════════════════════════════════════════════════════
        # 底部: 操作栏
        # ═══════════════════════════════════════════════════════════════
        footer = QFrame()
        footer_layout = QHBoxLayout(footer)
        
        footer_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 刷新引力场")
        refresh_btn.setObjectName("HoloButtonSecondary")
        refresh_btn.clicked.connect(self._refresh)
        footer_layout.addWidget(refresh_btn)
        
        publish_btn = QPushButton("🚀 发布商品")
        publish_btn.setObjectName("HoloButtonSuccess")
        publish_btn.clicked.connect(self._publish)
        footer_layout.addWidget(publish_btn)
        
        layout.addWidget(footer)
    
    def _init_demo_products(self):
        """初始化演示商品"""
        demo_products = [
            {"title": "LED工矿灯 100W", "price": 299, "condition": "new", "category": "照明"},
            {"title": "不锈钢轴承 6205", "price": 45, "condition": "used", "category": "机械"},
            {"title": "工业模具 定做", "price": 2500, "condition": "new", "category": "模具"},
            {"title": "二手发电机 50KW", "price": 8500, "condition": "used", "category": "电源"},
            {"title": "铝锭 99.7%", "price": 15800, "condition": "new", "category": "原材料"},
            {"title": "塑料粒子 ABS", "price": 12000, "condition": "new", "category": "化工"},
        ]
        
        for product in demo_products:
            self.product_scene.add_product(product)
            # 添加随机撮合
            if random.random() > 0.5:
                self.radar.add_match("buyer" if random.random() > 0.5 else "seller")
    
    def _on_images_dropped(self, paths: list):
        """图片拖拽"""
        self.reorganizer.set_scanning(True)
        
        # 模拟AI识别
        QTimer.singleShot(1500, lambda: self._show_recognition_result(paths))
    
    def _show_recognition_result(self, paths: list):
        """显示识别结果"""
        categories = ["照明设备", "机械配件", "电子元件", "化工原料", "金属材料"]
        category = random.choice(categories)
        confidence = random.uniform(0.75, 0.98)
        
        self.reorganizer.set_scanning(False)
        self.reorganizer.show_result(category, confidence)
        
        # 添加撮合
        for _ in range(random.randint(1, 3)):
            self.radar.add_match("buyer" if random.random() > 0.5 else "seller")
    
    def _refresh(self):
        """刷新"""
        self.radar.clear_matches()
        
        # 重新演示
        for _ in range(random.randint(2, 5)):
            self.radar.add_match("buyer" if random.random() > 0.5 else "seller")
    
    def _publish(self):
        """发布商品"""
        self.listing_published.emit({"status": "success", "message": "商品已发布"})
    
    def add_product(self, product_data: dict):
        """添加商品"""
        self.product_scene.add_product(product_data)


# ═══════════════════════════════════════════════════════════════════════════════
# 导出
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    'HolographicProductItem',
    'MatterReorganizer',
    'MatchingRadar',
    'TradeDeck',
]
