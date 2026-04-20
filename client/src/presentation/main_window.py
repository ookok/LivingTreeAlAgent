"""
主窗口 — 全新仪表盘主界面
=========================
采用现代卡片式设计，集成所有功能模块
"""

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QScrollArea, QFrame, QGridLayout, QPushButton,
    QGraphicsDropShadowEffect, QMessageBox, QTabWidget
)
from PyQt6.QtGui import QFont, QColor


class MainCard(QFrame):
    """主功能卡片"""
    
    def __init__(self, icon: str, title: str, description: str, color: str, parent=None):
        super().__init__(parent)
        self._init_ui(icon, title, description, color)
    
    def _init_ui(self, icon: str, title: str, description: str, color: str):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(160)
        
        self.setStyleSheet(f"""
            MainCard {{
                background-color: {color};
                border-radius: 20px;
                border: 2px solid transparent;
            }}
            MainCard:hover {{
                border: 2px solid #3b82f6;
                background-color: #ffffff;
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(20)
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 48px;")
        layout.addWidget(icon_label)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #1f2937;")
        text_layout.addWidget(title_label)
        
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Microsoft YaHei", 11))
        desc_label.setStyleSheet("color: #6b7280;")
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()


class QuickStatCard(QFrame):
    """快捷统计卡片"""
    
    def __init__(self, icon: str, label: str, value: str, color: str, parent=None):
        super().__init__(parent)
        self._init_ui(icon, label, value, color)
    
    def _init_ui(self, icon: str, label: str, value: str, color: str):
        self.setFixedHeight(100)
        
        self.setStyleSheet(f"""
            QuickStatCard {{
                background-color: {color};
                border-radius: 16px;
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
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 32px;")
        layout.addWidget(icon_label)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        value_label = QLabel(value)
        value_label.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        value_label.setStyleSheet("color: #1f2937;")
        text_layout.addWidget(value_label)
        
        label_label = QLabel(label)
        label_label.setFont(QFont("Microsoft YaHei", 10))
        label_label.setStyleSheet("color: #6b7280;")
        text_layout.addWidget(label_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()


class SectionTitle(QLabel):
    """区块标题"""
    
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        self.setStyleSheet("color: #1f2937; margin-top: 24px; margin-bottom: 16px;")


class WelcomeBanner(QFrame):
    """欢迎横幅"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        self.setStyleSheet("""
            WelcomeBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:0.5 #8b5cf6, stop:1 #ec4899);
                border-radius: 24px;
            }
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(59, 130, 246, 80))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        
        greeting = QLabel(" 欢迎回来！")
        greeting.setFont(QFont("Microsoft YaHei", 22, QFont.Weight.Bold))
        greeting.setStyleSheet("color: #ffffff;")
        text_layout.addWidget(greeting)
        
        subtitle = QLabel("Hermes Desktop - 您的 AI 智能工作台")
        subtitle.setFont(QFont("Microsoft YaHei", 13))
        subtitle.setStyleSheet("color: #e0e7ff;")
        text_layout.addWidget(subtitle)
        
        desc = QLabel("集成对话、写作、研究、装配等多功能于一体")
        desc.setFont(QFont("Microsoft YaHei", 11))
        desc.setStyleSheet("color: #c7d2fe;")
        text_layout.addWidget(desc)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        icon_label = QLabel("🤖")
        icon_label.setStyleSheet("font-size: 80px;")
        layout.addWidget(icon_label)


class MainWindow(QWidget):
    """主窗口 - 全新仪表盘设计"""
    
    switch_to_writing = pyqtSignal(str)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_session_id = None
        self._agent = None
        
        self._build_ui()
        
        self.setWindowTitle("Hermes Desktop v2.0")
        self.resize(1200, 800)
    
    def _build_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 顶部导航栏
        nav_bar = self._create_nav_bar()
        main_layout.addWidget(nav_bar)
        
        # 内容区域
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)
        
        # 欢迎横幅
        welcome = WelcomeBanner()
        content_layout.addWidget(welcome)
        
        # 快捷统计
        self._build_stats_section(content_layout)
        
        # 核心功能模块
        self._build_modules_section(content_layout)
        
        # 工具与设置
        self._build_tools_section(content_layout)
        
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
        scroll.setWidget(content_area)
        main_layout.addWidget(scroll)
    
    def _create_nav_bar(self):
        """创建顶部导航栏"""
        nav = QFrame()
        nav.setFixedHeight(64)
        nav.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-bottom: 1px solid #e5e7eb;
            }
        """)
        
        layout = QHBoxLayout(nav)
        layout.setContentsMargins(24, 0, 24, 0)
        
        # Logo
        logo = QLabel("🌿 Hermes")
        logo.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        logo.setStyleSheet("color: #1f2937;")
        layout.addWidget(logo)
        
        layout.addStretch()
        
        # 导航按钮
        nav_buttons = [
            ("🏠 首页", "home"),
            ("💬 对话", "chat"),
            ("📝 写作", "write"),
            ("🔍 研究", "research"),
            ("⚗️ 装配", "assemble"),
        ]
        
        for text, action_id in nav_buttons:
            btn = QPushButton(text)
            btn.setFont(QFont("Microsoft YaHei", 11))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #6b7280;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #f3f4f6;
                    color: #1f2937;
                }
            """)
            layout.addWidget(btn)
        
        layout.addStretch()
        
        # 设置按钮
        settings_btn = QPushButton("⚙️ 设置")
        settings_btn.setFont(QFont("Microsoft YaHei", 11))
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                padding: 8px 20px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        layout.addWidget(settings_btn)
        
        return nav
    
    def _build_stats_section(self, parent_layout):
        """构建统计区域"""
        title = SectionTitle("📊 系统概览")
        parent_layout.addWidget(title)
        
        grid = QGridLayout()
        grid.setSpacing(16)
        
        stats = [
            ("🤖", "Agent 状态", "未初始化", "#fef3c7"),
            ("🧠", "可用模型", "0 个", "#eff6ff"),
            ("💬", "会话数量", "0", "#f0fdf4"),
            ("⚡", "系统性能", "良好", "#fce7f3"),
        ]
        
        row, col = 0, 0
        for icon, label, value, color in stats:
            card = QuickStatCard(icon, label, value, color)
            grid.addWidget(card, row, col)
            col += 1
            if col >= 4:
                col = 0
                row += 1
        
        parent_layout.addLayout(grid)
    
    def _build_modules_section(self, parent_layout):
        """构建核心功能模块"""
        title = SectionTitle("🚀 核心功能")
        parent_layout.addWidget(title)
        
        grid = QGridLayout()
        grid.setSpacing(16)
        
        modules = [
            ("🧠", "系统大脑", "AI 对话交互中心，支持多轮对话、工具调用、思考链展示", "#eff6ff"),
            ("✍️", "写作助手", "文档创作与编辑，支持智能续写、改写、摘要生成", "#fef3c7"),
            ("🔍", "研究助手", "深度搜索与分析，支持网络搜索、数据分析、报告生成", "#f0fdf4"),
            ("⚗️", "嫁接园", "工具装配平台，集成 MCP 协议，支持自定义工具链", "#fce7f3"),
            ("🚀", "舰桥", "元宇宙工作台，可视化操作界面，支持多任务管理", "#e0f2fe"),
            ("📁", "文件管理", "文件浏览、上传、下载，支持多种格式预览", "#ede9fe"),
        ]
        
        row, col = 0, 0
        for icon, mod_title, desc, color in modules:
            card = MainCard(icon, mod_title, desc, color)
            grid.addWidget(card, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1
        
        parent_layout.addLayout(grid)
    
    def _build_tools_section(self, parent_layout):
        """构建工具与设置区域"""
        title = SectionTitle("🛠️ 工具与设置")
        parent_layout.addWidget(title)
        
        grid = QGridLayout()
        grid.setSpacing(12)
        
        tools = [
            ("⚙️", "系统设置", "配置模型、API、主题等", "#f3f4f6"),
            ("📦", "模型管理", "下载、切换、管理模型", "#f3f4f6"),
            ("🔧", "工具市场", "浏览、安装扩展工具", "#f3f4f6"),
            ("📊", "数据统计", "使用统计、性能分析", "#f3f4f6"),
        ]
        
        row, col = 0, 0
        for icon, tool_title, desc, color in tools:
            card = QFrame()
            card.setFixedHeight(90)
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {color};
                    border-radius: 16px;
                    border: 1px solid #e5e7eb;
                    padding: 16px;
                }}
                QFrame:hover {{
                    border: 2px solid #3b82f6;
                    background-color: #ffffff;
                }}
            """)
            
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(6)
            shadow.setColor(QColor(0, 0, 0, 10))
            shadow.setOffset(0, 2)
            card.setGraphicsEffect(shadow)
            
            layout = QHBoxLayout(card)
            layout.setContentsMargins(20, 16, 20, 16)
            layout.setSpacing(16)
            
            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 36px;")
            layout.addWidget(icon_label)
            
            text_layout = QVBoxLayout()
            text_layout.setSpacing(4)
            
            t_label = QLabel(tool_title)
            t_label.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
            t_label.setStyleSheet("color: #1f2937;")
            text_layout.addWidget(t_label)
            
            d_label = QLabel(desc)
            d_label.setFont(QFont("Microsoft YaHei", 10))
            d_label.setStyleSheet("color: #6b7280;")
            text_layout.addWidget(d_label)
            
            layout.addLayout(text_layout)
            layout.addStretch()
            
            grid.addWidget(card, row, col)
            col += 1
            if col >= 4:
                col = 0
                row += 1
        
        parent_layout.addLayout(grid)
