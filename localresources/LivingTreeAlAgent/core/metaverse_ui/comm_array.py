"""
深空通讯阵 - Comm Array
P2P邮件/消息/网络状态可视化，跃迁信标风格
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPointF
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QFrame, QPushButton, QListWidget,
                             QListWidgetItem, QScrollArea)
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QLinearGradient, QFont
import math
import random
from datetime import datetime, timedelta

from .bridge_styles import HolographicColors, HolographicFonts


# ═══════════════════════════════════════════════════════════════════════════════
# 跃迁信标组件
# ═══════════════════════════════════════════════════════════════════════════════

class WarpBeacon(QFrame):
    """跃迁信标 - 邮件/消息指示器"""
    
    MESSAGE_TYPES = {
        "internal": {"color": HolographicColors.HOLO_PRIMARY, "icon": "🔵", "name": "内部"},
        "external": {"color": HolographicColors.HOLO_ORANGE, "icon": "🟠", "name": "外部"},
        "system": {"color": HolographicColors.HOLO_PURPLE, "icon": "🟣", "name": "系统"},
        "trade": {"color": HolographicColors.HOLO_GOLD, "icon": "🟡", "name": "交易"},
    }
    
    clicked = pyqtSignal(str)  # 消息ID
    
    def __init__(self, message_data: dict, parent=None):
        super().__init__(parent)
        self.message_data = message_data
        self._init_ui()
        self._start_pulse()
    
    def _init_ui(self):
        """初始化UI"""
        msg_type = self.message_data.get("type", "internal")
        type_info = self.MESSAGE_TYPES.get(msg_type, self.MESSAGE_TYPES["internal"])
        
        self.setObjectName("HoloCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(60)
        
        # 颜色
        color = QColor(type_info["color"])
        color_hex = type_info["color"]
        
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {color_hex}22,
                    stop:0.3 {color_hex}11,
                    stop:1 transparent);
                border: 1px solid {color_hex}66;
                border-radius: 8px;
            }}
            QFrame:hover {{
                border: 1px solid {color_hex};
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {color_hex}44,
                    stop:0.3 {color_hex}22,
                    stop:1 transparent);
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # 信标图标
        self.beacon_label = QLabel(type_info["icon"])
        self.beacon_label.setStyleSheet("font-size: 20px;")
        layout.addWidget(self.beacon_label)
        
        # 信标点 (脉冲动画)
        self.pulse_dot = QLabel("●")
        self.pulse_dot.setStyleSheet(f"color: {color_hex}; font-size: 8px;")
        layout.addWidget(self.pulse_dot)
        
        # 内容
        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)
        
        self.title_label = QLabel(self.message_data.get("title", "无标题"))
        self.title_label.setFont(HolographicFonts.get_font(12, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {HolographicColors.TEXT_PRIMARY};")
        content_layout.addWidget(self.title_label)
        
        self.preview_label = QLabel(self.message_data.get("preview", ""))
        self.preview_label.setFont(HolographicFonts.get_font(10))
        self.preview_label.setStyleSheet(f"color: {HolographicColors.TEXT_DIM};")
        content_layout.addWidget(self.preview_label)
        
        layout.addLayout(content_layout, 1)
        
        # 时间
        time_str = self.message_data.get("time", "")
        self.time_label = QLabel(time_str)
        self.time_label.setFont(HolographicFonts.mono_font(9))
        self.time_label.setStyleSheet(f"color: {HolographicColors.TEXT_DIM};")
        layout.addWidget(self.time_label)
    
    def _start_pulse(self):
        """开始脉冲动画"""
        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._pulse)
        self._pulse_timer.start(1500)
    
    def _pulse(self):
        """脉冲效果"""
        msg_type = self.message_data.get("type", "internal")
        color = self.MESSAGE_TYPES.get(msg_type, self.MESSAGE_TYPES["internal"])["color"]
        
        opacity = (math.sin(self._pulse_timer.remainingTime() / 1500 * math.pi) + 1) / 2
        alpha = int(100 + opacity * 155)
        
        pulse_color = QColor(color)
        pulse_color.setAlpha(alpha)
        
        self.pulse_dot.setStyleSheet(f"color: {pulse_color.name()}; font-size: {8 + opacity * 4}px;")


# ═══════════════════════════════════════════════════════════════════════════════
# P2P链路可视化
# ═══════════════════════════════════════════════════════════════════════════════

class P2PLinkVisualizer(QWidget):
    """P2P链路可视化"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes = []
        self._links = []
        self._phase = 0
        self._init_demo()
        
        self._timer = QTimer()
        self._timer.timeout.connect(self._animate)
        self._timer.start(50)
    
    def _init_demo(self):
        """初始化演示数据"""
        self._nodes = [
            {"id": "self", "x": 0.5, "y": 0.5, "active": True},
            {"id": "node_001", "x": 0.2, "y": 0.3, "active": True},
            {"id": "node_002", "x": 0.8, "y": 0.3, "active": True},
            {"id": "node_003", "x": 0.3, "y": 0.7, "active": False},
            {"id": "node_004", "x": 0.7, "y": 0.7, "active": True},
        ]
        
        self._links = [
            ("self", "node_001"),
            ("self", "node_002"),
            ("self", "node_004"),
            ("node_001", "node_003"),
        ]
    
    def paintEvent(self, event):
        """绘制链路"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # 背景
        painter.fillRect(self.rect(), QColor(HolographicColors.BACKGROUND_DEEP))
        
        # 绘制链接
        for link in self._links:
            node1 = next((n for n in self._nodes if n["id"] == link[0]), None)
            node2 = next((n for n in self._nodes if n["id"] == link[1]), None)
            
            if node1 and node2:
                x1 = node1["x"] * w
                y1 = node1["y"] * h
                x2 = node2["x"] * w
                y2 = node2["y"] * h
                
                # 流光动画
                flow_pos = (self._phase % 40) / 40
                
                # 线条颜色
                line_color = QColor(HolographicColors.HOLO_PRIMARY)
                line_color.setAlpha(80)
                
                pen = QPen(line_color)
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawLine(x1, y1, x2, y2)
                
                # 流光粒子
                fx = x1 + (x2 - x1) * flow_pos
                fy = y1 + (y2 - y1) * flow_pos
                
                glow_color = QColor(HolographicColors.HOLO_GLOW)
                glow_color.setAlpha(200)
                painter.setBrush(QBrush(glow_color))
                painter.setPen(Qt.GlobalColor.transparent)
                painter.drawEllipse(fx - 4, fy - 4, 8, 8)
        
        # 绘制节点
        for node in self._nodes:
            x = node["x"] * w
            y = node["y"] * h
            active = node["active"]
            
            # 节点颜色
            color = QColor(HolographicColors.HOLO_GREEN if active else HolographicColors.HOLO_RED)
            color_lighter = color.lighter(150)
            
            # 外发光
            glow_gradient = QRadialGradient(x, y, 20)
            glow_color = color.lighter(150)
            glow_color.setAlpha(100)
            glow_gradient.setColorAt(0, glow_color)
            glow_gradient.setColorAt(1, Qt.GlobalColor.transparent)
            painter.fillRect(x - 20, y - 20, 40, 40, QBrush(glow_gradient))
            
            # 节点
            painter.setBrush(QBrush(color_lighter))
            painter.setPen(QPen(color, 2))
            painter.drawEllipse(x - 8, y - 8, 16, 16)
            
            # 活跃脉冲
            if active:
                pulse = (math.sin(self._phase * 0.1) + 1) / 2
                pulse_color = QColor(color)
                pulse_color.setAlpha(int(100 * pulse))
                painter.setBrush(QBrush(pulse_color))
                painter.setPen(Qt.GlobalColor.transparent)
                painter.drawEllipse(x - 12 - pulse * 5, y - 12 - pulse * 5, 
                                   24 + pulse * 10, 24 + pulse * 10)
    
    def _animate(self):
        """动画"""
        self._phase += 1
        self.update()
    
    def set_latency(self, latency: float):
        """设置延迟显示"""
        # 根据延迟调整流光速度
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# 深空通讯阵 Widget
# ═══════════════════════════════════════════════════════════════════════════════

class CommArrayWidget(QWidget):
    """
    深空通讯阵 Widget
    显示邮件、消息、网络状态
    """
    
    message_selected = pyqtSignal(str)  # 消息类型
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._load_demo_messages()
    
    def _init_ui(self):
        """初始化UI"""
        self.setStyleSheet(get_bridge_stylesheet())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # ═══════════════════════════════════════════════════════════════
        # 标题栏
        # ═══════════════════════════════════════════════════════════════
        header = QHBoxLayout()
        
        title = QLabel("◈ 深空通讯阵")
        title.setObjectName("HoloLabelTitle")
        title.setStyleSheet(f"color: {HolographicColors.HOLO_SECONDARY};")
        header.addWidget(title)
        
        header.addStretch()
        
        # 网络状态Mini图
        self.mini_net = QLabel("🌐 5节点")
        self.mini_net.setObjectName("HUDLabel")
        self.mini_net.setStyleSheet(f"color: {HolographicColors.HOLO_GREEN};")
        header.addWidget(self.mini_net)
        
        self.latency_label = QLabel("23ms")
        self.latency_label.setObjectName("HUDLabel")
        self.latency_label.setStyleSheet(f"color: {HolographicColors.HOLO_GREEN};")
        header.addWidget(self.latency_label)
        
        layout.addLayout(header)
        
        # ═══════════════════════════════════════════════════════════════
        # 消息列表
        # ═══════════════════════════════════════════════════════════════
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
        """)
        
        self.message_list = QListWidget()
        self.message_list.setStyleSheet(f"""
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                background: transparent;
                border: none;
                padding: 4px;
            }}
        """)
        self.message_list.itemClicked.connect(self._on_message_clicked)
        
        scroll.setWidget(self.message_list)
        layout.addWidget(scroll, 1)
        
        # ═══════════════════════════════════════════════════════════════
        # 快速操作
        # ═══════════════════════════════════════════════════════════════
        actions = QHBoxLayout()
        
        new_msg_btn = QPushButton("✉️ 新消息")
        new_msg_btn.setObjectName("HoloButtonSecondary")
        new_msg_btn.clicked.connect(lambda: self.message_selected.emit("compose"))
        actions.addWidget(new_msg_btn)
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setObjectName("HoloButtonSecondary")
        refresh_btn.setFixedWidth(40)
        refresh_btn.clicked.connect(self._refresh)
        actions.addWidget(refresh_btn)
        
        layout.addLayout(actions)
    
    def _load_demo_messages(self):
        """加载演示消息"""
        demo_messages = [
            {
                "id": "msg_001",
                "type": "internal",
                "title": "来自 node_001 的问候",
                "preview": "你好！看到你有EN590柴油的资源...",
                "time": "刚刚"
            },
            {
                "id": "msg_002",
                "type": "trade",
                "title": "新订单: 铝锭 10吨",
                "preview": "买家 node_003 请求购买铝锭...",
                "time": "5分钟前"
            },
            {
                "id": "msg_003",
                "type": "external",
                "title": "外部邮件: 报价确认",
                "preview": "请确认以下硫磺报价...",
                "time": "15分钟前"
            },
            {
                "id": "msg_004",
                "type": "system",
                "title": "节点连接恢复",
                "preview": "node_007 已重新连接",
                "time": "1小时前"
            },
            {
                "id": "msg_005",
                "type": "trade",
                "title": "交易完成通知",
                "preview": "电解铜订单已完成付款...",
                "time": "2小时前"
            },
        ]
        
        for msg in demo_messages:
            self._add_message(msg)
    
    def _add_message(self, message_data: dict):
        """添加消息"""
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, message_data["id"])
        
        beacon = WarpBeacon(message_data)
        beacon.clicked.connect(lambda: self.message_selected.emit(message_data["type"]))
        
        item.setSizeHint(beacon.sizeHint())
        self.message_list.addItem(item)
        self.message_list.setItemWidget(item, beacon)
    
    def _on_message_clicked(self, item):
        """消息点击"""
        msg_id = item.data(Qt.ItemDataRole.UserRole)
        # 处理消息选择
        self.message_selected.emit(msg_id)
    
    def _refresh(self):
        """刷新"""
        # 模拟新消息
        if random.random() > 0.5:
            new_msg = {
                "id": f"msg_{random.randint(1000, 9999)}",
                "type": random.choice(["internal", "external", "trade", "system"]),
                "title": f"新消息 {datetime.now().strftime('%H:%M')}",
                "preview": "这是一条新消息...",
                "time": "刚刚"
            }
            self._add_message(new_msg)


# ═══════════════════════════════════════════════════════════════════════════════
# 深空通讯阵管理器
# ═══════════════════════════════════════════════════════════════════════════════

class CommArray:
    """
    深空通讯阵管理器
    处理P2P消息、邮件、网络状态
    """
    
    def __init__(self):
        self._messages = []
        self._nodes = {}
        self._latency = 0
    
    def add_message(self, message: dict):
        """添加消息"""
        message["timestamp"] = datetime.now()
        self._messages.append(message)
    
    def get_messages(self, msg_type: str = None, limit: int = 50) -> list:
        """获取消息"""
        msgs = self._messages
        if msg_type:
            msgs = [m for m in msgs if m.get("type") == msg_type]
        return msgs[-limit:]
    
    def get_unread_count(self, msg_type: str = None) -> int:
        """获取未读数"""
        msgs = self.get_messages(msg_type)
        return len([m for m in msgs if not m.get("read", False)])
    
    def mark_read(self, message_id: str):
        """标记已读"""
        for msg in self._messages:
            if msg.get("id") == message_id:
                msg["read"] = True
                break
    
    def update_node_status(self, node_id: str, status: dict):
        """更新节点状态"""
        self._nodes[node_id] = status
    
    def get_active_nodes(self) -> int:
        """获取活跃节点数"""
        return len([n for n in self._nodes.values() if n.get("active", False)])
    
    def set_latency(self, latency: float):
        """设置延迟"""
        self._latency = latency
    
    def get_latency(self) -> float:
        """获取延迟"""
        return self._latency


# 单例
_comm_array_instance = None

def get_comm_array() -> CommArray:
    """获取通讯阵单例"""
    global _comm_array_instance
    if _comm_array_instance is None:
        _comm_array_instance = CommArray()
    return _comm_array_instance
