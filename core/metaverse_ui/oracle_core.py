"""
先知核心 - Oracle Core
AI领航员全息投影界面，自然语言交互
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPointF, QEasingCurve
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QFrame, QPushButton, QTextEdit,
                             QLineEdit, QScrollArea)
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QLinearGradient, QFont, QMovie
from PyQt6.QtCore import QPropertyAnimation, pyqtProperty
import math
import random
from datetime import datetime

from .bridge_styles import HolographicColors, HolographicFonts


# ═══════════════════════════════════════════════════════════════════════════════
# AI全息投影组件
# ═══════════════════════════════════════════════════════════════════════════════

class AIHologram(QFrame):
    """AI全息投影 - 右上角悬浮小人"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._start_animation()
    
    def _init_ui(self):
        """初始化UI"""
        self.setFixedSize(80, 100)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 状态
        self._phase = 0
        self._hovered = False
        self.state = "idle"  # idle, thinking, speaking, alert
        
        # 动画定时器
        self._timer = QTimer()
        self._timer.timeout.connect(self._animate)
        self._timer.start(50)
    
    def _start_animation(self):
        """开始动画"""
        pass
    
    def paintEvent(self, event):
        """绘制AI全息投影"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        
        # 浮动动画
        float_y = math.sin(self._phase * 0.1) * 3
        
        # 状态颜色
        state_colors = {
            "idle": HolographicColors.HOLO_PRIMARY,
            "thinking": HolographicColors.HOLO_ORANGE,
            "speaking": HolographicColors.HOLO_GREEN,
            "alert": HolographicColors.HOLO_RED,
        }
        main_color = QColor(state_colors.get(self.state, HolographicColors.HOLO_PRIMARY))
        
        # 底部光晕
        glow_gradient = QRadialGradient(cx, h, w // 2)
        glow_color = main_color.lighter(150)
        glow_color.setAlpha(50)
        glow_gradient.setColorAt(0, glow_color)
        glow_gradient.setColorAt(1, Qt.GlobalColor.transparent)
        painter.fillRect(self.rect(), QBrush(glow_gradient))
        
        # 光柱
        pillar_gradient = QLinearGradient(cx - 10, 0, cx + 10, 0)
        pillar_color = main_color.lighter(150)
        pillar_color.setAlpha(30)
        pillar_gradient.setColorAt(0, Qt.GlobalColor.transparent)
        pillar_gradient.setColorAt(0.5, pillar_color)
        pillar_gradient.setColorAt(1, Qt.GlobalColor.transparent)
        
        painter.fillRect(cx - 10, 20 + float_y, 20, h - 20, QBrush(pillar_gradient))
        
        # AI主体 (简化的人形)
        body_y = 30 + float_y
        
        # 头部
        head_radius = 18
        head_gradient = QRadialGradient(cx, body_y - 15, head_radius)
        head_gradient.setColorAt(0, main_color.lighter(200))
        head_gradient.setColorAt(0.7, main_color)
        head_gradient.setColorAt(1, main_color.darker(150))
        
        painter.setBrush(QBrush(head_gradient))
        painter.setPen(QPen(main_color.darker(150), 1))
        painter.drawEllipse(cx, body_y - 15, head_radius * 2, head_radius * 2)
        
        # 眼睛
        eye_color = Qt.GlobalColor.white
        eye_brush = QBrush(eye_color)
        painter.setBrush(eye_brush)
        
        # 眨眼动画
        blink = abs(math.sin(self._phase * 0.05)) > 0.95
        eye_height = 2 if blink else 5
        
        painter.drawEllipse(cx - 8, body_y - 18, 5, eye_height)
        painter.drawEllipse(cx + 3, body_y - 18, 5, eye_height)
        
        # 身体轮廓
        body_gradient = QLinearGradient(cx - 20, body_y + 10, cx + 20, body_y + 60)
        body_gradient.setColorAt(0, main_color.lighter(150).darker(130))
        body_gradient.setColorAt(0.5, main_color.lighter(150))
        body_gradient.setColorAt(1, main_color.darker(150))
        
        painter.setBrush(QBrush(body_gradient))
        painter.setPen(QPen(main_color, 1))
        
        # 简化的身体形状
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        path.moveTo(cx - 15, body_y + 10)  # 左肩
        path.lineTo(cx - 20, body_y + 40)  # 左腰
        path.lineTo(cx - 8, body_y + 70)    # 左腿
        path.lineTo(cx, body_y + 80)        # 脚
        path.lineTo(cx + 8, body_y + 70)    # 右腿
        path.lineTo(cx + 20, body_y + 40)   # 右腰
        path.lineTo(cx + 15, body_y + 10)   # 右肩
        path.closeSubpath()
        painter.drawPath(path)
        
        # 扫描线效果 (thinking状态)
        if self.state == "thinking":
            scan_y = (self._phase * 3) % 60
            scan_color = QColor(main_color.lighter(200))
            scan_color.setAlpha(100)
            pen = QPen(scan_color, 2)
            painter.setPen(pen)
            painter.drawLine(cx - 15, body_y + 10 + scan_y, cx + 15, body_y + 10 + scan_y)
        
        # 声波效果 (speaking状态)
        if self.state == "speaking":
            for i in range(3):
                wave_radius = 25 + i * 8 + (self._phase % 20)
                wave_alpha = max(0, 100 - i * 30 - int(self._phase % 20) * 5)
                wave_color = QColor(main_color.lighter(200))
                wave_color.setAlpha(wave_alpha)
                pen = QPen(wave_color, 2)
                painter.setPen(pen)
                painter.drawEllipse(cx, body_y - 15, head_radius * 2 + wave_radius, head_radius * 2 + wave_radius)
        
        # 悬停光圈
        if self._hovered:
            hover_color = QColor(main_color.lighter(200))
            hover_color.setAlpha(50)
            pen = QPen(hover_color, 3)
            pen.setDashPattern([5, 5])
            painter.setPen(pen)
            painter.drawEllipse(cx - 5, body_y - 20, 10, 10)
    
    def _animate(self):
        """动画"""
        self._phase += 1
        self.update()
    
    def set_state(self, state: str):
        """设置状态"""
        self.state = state
        self.update()
    
    def enterEvent(self, event):
        """悬停"""
        self._hovered = True
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """悬停离开"""
        self._hovered = False
        self.update()
        super().leaveEvent(event)


# ═══════════════════════════════════════════════════════════════════════════════
# AI对话气泡
# ═══════════════════════════════════════════════════════════════════════════════

class AIBubble(QFrame):
    """AI对话气泡"""
    
    def __init__(self, text: str, is_user: bool = False, parent=None):
        super().__init__(parent)
        self.text = text
        self.is_user = is_user
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        
        label = QLabel(self.text)
        label.setWordWrap(True)
        label.setMaximumWidth(300)
        
        if self.is_user:
            label.setStyleSheet(f"""
                QLabel {{
                    color: {HolographicColors.TEXT_PRIMARY};
                    background: {HolographicColors.HOLO_PRIMARY}33;
                    border: 1px solid {HolographicColors.HOLO_PRIMARY}66;
                    border-radius: 12px;
                    padding: 8px 12px;
                }}
            """)
            label.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            label.setStyleSheet(f"""
                QLabel {{
                    color: {HolographicColors.HOLO_GREEN};
                    background: {HolographicColors.HOLO_SECONDARY}22;
                    border: 1px solid {HolographicColors.HOLO_SECONDARY}44;
                    border-radius: 12px;
                    padding: 8px 12px;
                    font-style: italic;
                }}
            """)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        layout.addWidget(label)


# ═══════════════════════════════════════════════════════════════════════════════
# 先知核心 Widget
# ═══════════════════════════════════════════════════════════════════════════════

class OracleCoreWidget(QWidget):
    """
    先知核心 Widget
    AI领航员交互界面
    """
    
    action_requested = pyqtSignal(str)  # 操作请求
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._start_intro_animation()
    
    def _init_ui(self):
        """初始化UI"""
        self.setStyleSheet(get_bridge_stylesheet())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # ═══════════════════════════════════════════════════════════════
        # 标题栏
        # ═══════════════════════════════════════════════════════════════
        header = QHBoxLayout()
        
        title = QLabel("◈ 先知核心")
        title.setObjectName("HoloLabelTitle")
        title.setStyleSheet(f"color: {HolographicColors.HOLO_PURPLE};")
        header.addWidget(title)
        
        header.addStretch()
        
        # 状态指示
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet(f"color: {HolographicColors.HOLO_GREEN}; font-size: 12px;")
        header.addWidget(self.status_indicator)
        
        self.status_text = QLabel("在线")
        self.status_text.setObjectName("HoloLabelDim")
        header.addWidget(self.status_text)
        
        layout.addLayout(header)
        
        # ═══════════════════════════════════════════════════════════════
        # AI投影 + 对话区
        # ═══════════════════════════════════════════════════════════════
        content = QHBoxLayout()
        
        # AI投影
        self.ai_holo = AIHologram()
        content.addWidget(self.ai_holo, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # 对话滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
        """)
        
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.chat_layout.setSpacing(8)
        
        scroll.setWidget(self.chat_container)
        content.addWidget(scroll, 1)
        
        layout.addLayout(content, 1)
        
        # ═══════════════════════════════════════════════════════════════
        # 输入区
        # ═══════════════════════════════════════════════════════════════
        input_frame = QFrame()
        input_frame.setObjectName("HoloCard")
        input_layout = QHBoxLayout(input_frame)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("输入指令或问题...")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background: {HolographicColors.BACKGROUND_DEEP};
                border: 1px solid {HolographicColors.BORDER_NORMAL};
                border-radius: 6px;
                color: {HolographicColors.TEXT_PRIMARY};
                padding: 8px 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {HolographicColors.HOLO_PURPLE};
            }}
        """)
        self.input_field.returnPressed.connect(self._on_send)
        input_layout.addWidget(self.input_field, 1)
        
        send_btn = QPushButton("➤")
        send_btn.setObjectName("HoloButton")
        send_btn.setFixedWidth(40)
        send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(send_btn)
        
        layout.addWidget(input_frame)
        
        # 快捷命令
        quick_layout = QHBoxLayout()
        quick_layout.addStretch()
        
        commands = [
            ("📸 扫描", "scan"),
            ("💡 建议", "suggest"),
            ("🔍 分析", "analyze"),
        ]
        
        for label, cmd in commands:
            btn = QPushButton(label)
            btn.setObjectName("HoloButtonSecondary")
            btn.setMaximumWidth(80)
            btn.clicked.connect(lambda checked, c=cmd: self._on_quick_command(c))
            quick_layout.addWidget(btn)
        
        layout.addLayout(quick_layout)
    
    def _start_intro_animation(self):
        """开始介绍动画"""
        intro_texts = [
            "检测到 3 个潜在交易信号",
            "时空引力场稳定",
            "赫耳墨斯引擎在线"
        ]
        
        for i, text in enumerate(intro_texts):
            QTimer.singleShot(i * 1000, lambda t=text: self._add_ai_message(t))
    
    def _add_ai_message(self, text: str):
        """添加AI消息"""
        bubble = AIBubble(text, is_user=False)
        self.chat_layout.addWidget(bubble)
        
        # 滚动到底
        scroll = self.chat_container.parent()
        if scroll:
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    
    def _on_send(self):
        """发送消息"""
        text = self.input_field.text().strip()
        if not text:
            return
        
        # 添加用户消息
        user_bubble = AIBubble(text, is_user=True)
        self.chat_layout.addWidget(user_bubble)
        self.input_field.clear()
        
        # AI思考
        self.ai_holo.set_state("thinking")
        
        # 模拟AI回复
        QTimer.singleShot(1000, lambda: self._ai_response(text))
    
    def _ai_response(self, query: str):
        """AI响应"""
        self.ai_holo.set_state("speaking")
        
        # 根据输入生成响应
        if "扫描" in query or "分析" in query:
            response = "已完成引力场扫描，发现附近 5 个活跃交易节点。建议关注卖家 'seller_001'，交易意向强度 0.87。"
        elif "建议" in query or "推荐" in query:
            response = "基于当前市场分析，建议上架工业照明设备，需求热度 +15%。"
        else:
            response = "收到指令，正在处理... 如需帮助，请说「帮助」查看可用命令。"
        
        self._add_ai_message(response)
        
        QTimer.singleShot(2000, lambda: self.ai_holo.set_state("idle"))
    
    def _on_quick_command(self, command: str):
        """快捷命令"""
        self.action_requested.emit(command)
        
        # 模拟响应
        responses = {
            "scan": "正在扫描周围节点...",
            "suggest": "根据您的偏好，推荐以下商品...",
            "analyze": "正在分析交易模式..."
        }
        
        self.ai_holo.set_state("thinking")
        QTimer.singleShot(500, lambda: self._add_ai_message(responses.get(command, "")))
        QTimer.singleShot(2000, lambda: self.ai_holo.set_state("idle"))


# ═══════════════════════════════════════════════════════════════════════════════
# 先知核心管理器
# ═══════════════════════════════════════════════════════════════════════════════

class OracleCore:
    """
    先知核心 - AI领航员
    提供智能建议、交易分析、网络优化建议
    """
    
    def __init__(self):
        self._state = "idle"
        self._suggestions = []
        self._alerts = []
    
    @property
    def state(self) -> str:
        return self._state
    
    def set_state(self, state: str):
        """设置状态"""
        self._state = state
    
    def get_suggestion(self) -> str:
        """获取建议"""
        suggestions = [
            "检测到 3 个潜在交易信号",
            "建议关注节点 seller_001，交易意向强度 0.87",
            "当前网络延迟较低，适合进行大宗交易",
            "发现新的商品上架，符合您的购买偏好",
            "建议检查网络连接，有 1 个节点离线",
        ]
        return random.choice(suggestions)
    
    def analyze_trade(self, trade_data: dict) -> dict:
        """分析交易"""
        return {
            "risk_level": random.choice(["low", "medium", "high"]),
            "suggested_price": trade_data.get("price", 0) * random.uniform(0.9, 1.1),
            "confidence": random.uniform(0.7, 0.95),
            "notes": "交易风险较低，建议进行"
        }
    
    def predict_market(self, category: str) -> dict:
        """预测市场趋势"""
        trends = ["up", "down", "stable"]
        return {
            "category": category,
            "trend": random.choice(trends),
            "change_percent": random.uniform(-10, 15),
            "confidence": random.uniform(0.6, 0.9)
        }


# 单例
_oracle_instance = None

def get_oracle_core() -> OracleCore:
    """获取先知核心单例"""
    global _oracle_instance
    if _oracle_instance is None:
        _oracle_instance = OracleCore()
    return _oracle_instance
