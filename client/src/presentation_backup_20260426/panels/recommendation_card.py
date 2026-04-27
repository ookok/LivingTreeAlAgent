"""
推荐卡片组件
自定义QWidget用于展示推荐内容
"""

from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QFont, QPalette, QColor


class RecommendationCard(QWidget):
    """
    推荐卡片组件
    支持：新闻/视频/商品三种类型
    """
    
    # 点击信号 (item_id, item_type, url)
    clicked = pyqtSignal(str, str, str)
    
    # 类型图标映射
    TYPE_ICONS = {
        "news": "📰",
        "video": "🎬",
        "product": "🛒",
    }
    
    # 类型颜色映射
    TYPE_COLORS = {
        "news": "#3b82f6",      # 蓝色
        "video": "#ef4444",     # 红色
        "product": "#f59e0b",   # 橙色
    }
    
    def __init__(self, item_data: dict, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.item_id = item_data.get("id", "")
        self.item_type = item_data.get("type", "news")
        self.url = item_data.get("url", "")
        
        self.setup_ui()
        self.apply_style()
    
    def setup_ui(self):
        """设置UI"""
        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(12)
        
        # 左侧：类型图标
        self.icon_label = QLabel()
        icon = self.TYPE_ICONS.get(self.item_type, "📄")
        self.icon_label.setText(f"<span style='font-size:28px'>{icon}</span>")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedWidth(50)
        main_layout.addWidget(self.icon_label)
        
        # 中间：文字区域
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        text_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题
        self.title_label = QLabel()
        title = self.item_data.get("title", "")
        self.title_label.setText(f"<b>{self._escape_html(title)}</b>")
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(40)
        self.title_label.setStyleSheet("font-size: 14px; color: #1f2937;")
        text_layout.addWidget(self.title_label)
        
        # 描述
        self.desc_label = QLabel()
        desc = self.item_data.get("description", "")
        if len(desc) > 60:
            desc = desc[:60] + "..."
        self.desc_label.setText(self._escape_html(desc))
        self.desc_label.setWordWrap(True)
        self.desc_label.setMaximumHeight(36)
        self.desc_label.setStyleSheet("font-size: 12px; color: #6b7280;")
        text_layout.addWidget(self.desc_label)
        
        # 元信息栏
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(8)
        
        # 来源
        self.source_label = QLabel()
        source = self.item_data.get("source", "")
        type_tag = f"[{self.item_type.upper()}]"
        self.source_label.setText(f"{type_tag} {source}")
        self.source_label.setStyleSheet(f"""
            font-size: 11px;
            color: {self.TYPE_COLORS.get(self.item_type, '#666')};
            background: #f3f4f6;
            padding: 2px 6px;
            border-radius: 4px;
        """)
        meta_layout.addWidget(self.source_label)
        
        # 时间
        self.time_label = QLabel()
        time_str = self.item_data.get("publish_time", "")
        self.time_label.setText(time_str)
        self.time_label.setStyleSheet("font-size: 11px; color: #9ca3af;")
        meta_layout.addWidget(self.time_label)
        
        meta_layout.addStretch()
        text_layout.addLayout(meta_layout)
        
        main_layout.addLayout(text_layout, 1)
        
        # 右侧：箭头
        self.arrow_label = QLabel("›")
        self.arrow_label.setStyleSheet("""
            font-size: 24px;
            color: #d1d5db;
        """)
        main_layout.addWidget(self.arrow_label)
    
    def apply_style(self):
        """应用样式"""
        self.setFixedHeight(90)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # 卡片背景
        self.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 8px;
            }
            QWidget:hover {
                background: #f9fafb;
            }
        """)
    
    def _escape_html(self, text: str) -> str:
        """转义HTML"""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item_id, self.item_type, self.url)
        super().mousePressEvent(event)
    
    def enterEvent(self, event):
        """鼠标进入"""
        self.setStyleSheet("""
            QWidget {
                background: #f0f9ff;
                border-radius: 8px;
                border: 1px solid #bfdbfe;
            }
        """)
        self.arrow_label.setStyleSheet("""
            font-size: 24px;
            color: #3b82f6;
        """)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开"""
        self.apply_style()
        super().leaveEvent(event)


class EmptyRecommendationCard(QWidget):
    """空状态卡片"""
    
    clicked = pyqtSignal()
    
    def __init__(self, message: str = "暂无推荐内容", parent=None):
        super().__init__(parent)
        self.message = message
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        
        self.icon_label = QLabel("📭")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 36px;")
        layout.addWidget(self.icon_label)
        
        self.msg_label = QLabel(self.message)
        self.msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.msg_label.setStyleSheet("font-size: 14px; color: #9ca3af;")
        layout.addWidget(self.msg_label)
        
        self.setFixedHeight(120)
        self.setStyleSheet("""
            QWidget {
                background: #f9fafb;
                border-radius: 8px;
                border: 1px dashed #d1d5db;
            }
        """)
    
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)
