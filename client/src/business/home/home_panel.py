# =================================================================
# HomePanel - 首页面板
# =================================================================
# V2.0 功能模块：首页聚合

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QSizePolicy,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QLinearGradient, QPainter


class QuickActionCard(QFrame):
    """快捷操作卡片"""
    
    clicked = pyqtSignal(str)  # action_id
    
    def __init__(self, icon: str, title: str, subtitle: str, action_id: str, parent=None):
        super().__init__(parent)
        self.action_id = action_id
        self._init_ui(icon, title, subtitle)
    
    def _init_ui(self, icon: str, title: str, subtitle: str):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(200, 120)
        
        # 圆角 + 阴影
        self.setStyleSheet("""
            QuickActionCard {
                background-color: #ffffff;
                border-radius: 16px;
                border: 1px solid #e5e7eb;
            }
            QuickActionCard:hover {
                border: 2px solid #3b82f6;
                background-color: #eff6ff;
            }
        """)
        
        # 阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        # 图标
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 32px;")
        layout.addWidget(icon_label)
        
        # 标题
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #1f2937;")
        layout.addWidget(title_label)
        
        # 副标题
        subtitle_label = QLabel(subtitle)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setFont(QFont("Microsoft YaHei", 10))
        subtitle_label.setStyleSheet("color: #6b7280;")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.action_id)
        super().mousePressEvent(event)


class StatusCard(QFrame):
    """状态卡片"""
    
    def __init__(self, icon: str, title: str, status_text: str, status_color: str, parent=None):
        super().__init__(parent)
        self._init_ui(icon, title, status_text, status_color)
    
    def _init_ui(self, icon: str, title: str, status_text: str, status_color: str):
        self.setFixedHeight(80)
        
        self.setStyleSheet(f"""
            StatusCard {{
                background-color: {status_color};
                border-radius: 12px;
                border: 1px solid #e5e7eb;
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(6)
        shadow.setColor(QColor(0, 0, 0, 10))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)
        
        # 图标
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 28px;")
        layout.addWidget(icon_label)
        
        # 文字区域
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #1f2937;")
        text_layout.addWidget(title_label)
        
        status_label = QLabel(status_text)
        status_label.setFont(QFont("Microsoft YaHei", 10))
        status_label.setStyleSheet("color: #6b7280;")
        text_layout.addWidget(status_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()


class SectionTitle(QLabel):
    """区块标题"""
    
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        self.setStyleSheet("color: #1f2937; margin-top: 16px; margin-bottom: 12px;")


class HomePanel(QWidget):
    """首页面板"""
    
    action_triggered = pyqtSignal(str)  # action_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        # 主布局 - 使用滚动区域
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f8fafc;
            }
            QScrollBar:vertical {
                border: none;
                background: #f1f5f9;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
        """)
        
        # 内容容器
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)
        
        # 欢迎区域
        self._build_welcome_section(content_layout)
        
        # 快捷操作区域
        self._build_quick_actions_section(content_layout)
        
        # 系统状态区域
        self._build_status_section(content_layout)
        
        # 功能导航区域
        self._build_feature_section(content_layout)
        
        # 底部提示
        self._build_tips_section(content_layout)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
    
    def _build_welcome_section(self, parent_layout):
        """欢迎区域"""
        # 渐变背景卡片
        welcome_card = QFrame()
        welcome_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3b82f6, stop:1 #8b5cf6);
                border-radius: 16px;
                padding: 24px;
            }
        """)
        
        welcome_layout = QHBoxLayout(welcome_card)
        welcome_layout.setContentsMargins(24, 24, 24, 24)
        
        # 左侧：欢迎文字
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        
        greeting = QLabel(" 欢迎使用 Hermes Desktop")
        greeting.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        greeting.setStyleSheet("color: #ffffff;")
        text_layout.addWidget(greeting)
        
        subtitle = QLabel("AI 驱动的智能助手，帮助您更高效地工作")
        subtitle.setFont(QFont("Microsoft YaHei", 12))
        subtitle.setStyleSheet("color: #e0e7ff;")
        text_layout.addWidget(subtitle)
        
        welcome_layout.addLayout(text_layout)
        welcome_layout.addStretch()
        
        # 右侧：图标
        icon_label = QLabel("🤖")
        icon_label.setStyleSheet("font-size: 64px;")
        welcome_layout.addWidget(icon_label)
        
        parent_layout.addWidget(welcome_card)
    
    def _build_quick_actions_section(self, parent_layout):
        """快捷操作区域"""
        title = SectionTitle("⚡ 快捷操作")
        parent_layout.addWidget(title)
        
        # 快捷操作网格
        grid = QGridLayout()
        grid.setSpacing(16)
        
        actions = [
            ("💬", "系统大脑", "开始对话", "open_brain"),
            ("✏️", "写作助手", "创建文档", "open_writing"),
            ("🔍", "研究助手", "搜索分析", "open_research"),
            ("⚗️", "嫁接园", "装配工具", "open_assembler"),
            ("📊", "数据分析", "数据处理", "open_analysis"),
            ("⚙️", "系统设置", "配置管理", "open_settings"),
        ]
        
        row, col = 0, 0
        for icon, title_text, subtitle, action_id in actions:
            card = QuickActionCard(icon, title_text, subtitle, action_id)
            card.clicked.connect(self._on_action_triggered)
            grid.addWidget(card, row, col)
            
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        parent_layout.addLayout(grid)
    
    def _build_status_section(self, parent_layout):
        """系统状态区域"""
        title = SectionTitle("📊 系统状态")
        parent_layout.addWidget(title)
        
        status_layout = QGridLayout()
        status_layout.setSpacing(12)
        
        statuses = [
            ("🤖", "Hermes Agent", "已就绪", "#ecfdf5"),
            ("🧠", "L0 模型", "qwen2.5:0.5b", "#eff6ff"),
            ("🌐", "Ollama 服务", "在线", "#ecfdf5"),
            ("💾", "磁盘空间", "可用", "#fff7ed"),
        ]
        
        row, col = 0, 0
        for icon, title_text, status_text, color in statuses:
            card = StatusCard(icon, title_text, status_text, color)
            status_layout.addWidget(card, row, col)
            
            col += 1
            if col >= 2:
                col = 0
                row += 1
        
        parent_layout.addLayout(status_layout)
    
    def _build_feature_section(self, parent_layout):
        """功能导航区域"""
        title = SectionTitle("🚀 功能模块")
        parent_layout.addWidget(title)
        
        features_layout = QGridLayout()
        features_layout.setSpacing(12)
        
        features = [
            ("🏠", "首页", "功能聚合中心", "#f0f9ff"),
            ("📝", "写作", "文档创作编辑", "#fef3c7"),
            ("🔬", "研究", "深度搜索分析", "#ede9fe"),
            ("⚗️", "嫁接园", "工具装配平台", "#fce7f3"),
            ("🚀", "舰桥", "元宇宙工作台", "#e0f2fe"),
            ("🧠", "系统大脑", "AI 对话交互", "#ecfdf5"),
        ]
        
        row, col = 0, 0
        for icon, f_title, f_desc, color in features:
            card = QFrame()
            card.setFixedHeight(100)
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {color};
                    border-radius: 12px;
                    border: 1px solid #e5e7eb;
                    padding: 16px;
                }}
                QFrame:hover {{
                    border: 2px solid #3b82f6;
                }}
            """)
            
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(6)
            shadow.setColor(QColor(0, 0, 0, 10))
            shadow.setOffset(0, 2)
            card.setGraphicsEffect(shadow)
            
            layout = QHBoxLayout(card)
            layout.setContentsMargins(16, 12, 16, 12)
            layout.setSpacing(12)
            
            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 36px;")
            layout.addWidget(icon_label)
            
            text_layout = QVBoxLayout()
            text_layout.setSpacing(4)
            
            f_title_label = QLabel(f_title)
            f_title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
            f_title_label.setStyleSheet("color: #1f2937;")
            text_layout.addWidget(f_title_label)
            
            f_desc_label = QLabel(f_desc)
            f_desc_label.setFont(QFont("Microsoft YaHei", 10))
            f_desc_label.setStyleSheet("color: #6b7280;")
            text_layout.addWidget(f_desc_label)
            
            layout.addLayout(text_layout)
            layout.addStretch()
            
            features_layout.addWidget(card, row, col)
            
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        parent_layout.addLayout(features_layout)
    
    def _build_tips_section(self, parent_layout):
        """提示区域"""
        tips_card = QFrame()
        tips_card.setStyleSheet("""
            QFrame {
                background-color: #fffbeb;
                border-radius: 12px;
                border: 1px solid #fbbf24;
                padding: 16px;
            }
        """)
        
        tips_layout = QHBoxLayout(tips_card)
        tips_layout.setContentsMargins(20, 16, 20, 16)
        tips_layout.setSpacing(16)
        
        icon_label = QLabel("💡")
        icon_label.setStyleSheet("font-size: 24px;")
        tips_layout.addWidget(icon_label)
        
        tips_text = QLabel(
            "<b>使用提示：</b> 您可以通过左侧面板切换不同功能模块。"
            "在系统大脑中与 AI 对话，或在写作助手中创建文档。"
            "点击右上角的 <b>设置</b> 按钮配置模型和 API。"
        )
        tips_text.setFont(QFont("Microsoft YaHei", 11))
        tips_text.setStyleSheet("color: #92400e;")
        tips_text.setWordWrap(True)
        tips_layout.addWidget(tips_text)
        
        parent_layout.addWidget(tips_card)
    
    def _on_action_triggered(self, action_id: str):
        """快捷操作触发"""
        self.action_triggered.emit(action_id)


__all__ = ['HomePanel']
