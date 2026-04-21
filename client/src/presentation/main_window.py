"""
主窗口 — 全新仪表盘主界面
=========================
采用响应式卡片布局，支持横向和纵向滚动，自适应不同分辨率
集成所有系统功能模块：AI核心、网络协作、经济系统、工具设置等
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_root))

from core.error_logger import setup_error_logger, get_logger

# 设置日志系统
logger = get_logger("client.main_window")

from PyQt6 import QtCore
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QScrollArea, QFrame, QPushButton,
    QGraphicsDropShadowEffect, QMessageBox, QApplication
)
from PyQt6.QtGui import QFont, QColor


class ResponsiveFlowLayout(QWidget):
    """
    响应式流式布局
    自动根据容器宽度调整每行卡片数量，支持自适应不同分辨率
    """
    
    def __init__(self, parent=None, spacing=16, min_card_width=280):
        super().__init__(parent)
        self._spacing = spacing
        self._min_card_width = min_card_width
        self._widgets = []
        self._widget_heights = {}
    
    def addWidget(self, widget, height=None):
        """添加widget，可选指定高度"""
        self._widgets.append(widget)
        widget.setParent(self)
        if height is not None:
            self._widget_heights[id(widget)] = height
        self.update_layout()
    
    def removeWidget(self, widget):
        """移除widget"""
        if widget in self._widgets:
            self._widgets.remove(widget)
            widget.setParent(None)
            self._widget_heights.pop(id(widget), None)
            self.update_layout()
    
    def clear(self):
        """清空所有widget"""
        for w in self._widgets:
            w.setParent(None)
            w.deleteLater()
        self._widgets.clear()
        self._widget_heights.clear()
    
    def update_layout(self):
        """更新布局位置"""
        available_width = self.width() - 2 * self._spacing
        if available_width <= 0:
            return
        
        # 计算每行可以放多少个卡片
        card_width = max(self._min_card_width, (available_width - (self._spacing * 2)) // 2)
        
        cols = max(1, (available_width + self._spacing) // (card_width + self._spacing))
        
        x = self._spacing
        y = self._spacing
        row_height = 0
        
        for i, widget in enumerate(self._widgets):
            col = i % cols
            
            if col > 0:
                x = self._spacing + col * (card_width + self._spacing)
            else:
                x = self._spacing
                if i > 0:
                    y += row_height + self._spacing
                    row_height = 0
            
            widget_height = self._widget_heights.get(id(widget), widget.sizeHint().height())
            widget.setGeometry(x, y, card_width, widget_height)
            row_height = max(row_height, widget_height)
        
        # 更新容器最小尺寸
        total_height = y + row_height + self._spacing if self._widgets else self._spacing * 2
        self.setMinimumSize(available_width + self._spacing * 2, total_height)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_layout()


class MainCard(QFrame):
    """主功能卡片 - 大卡片样式"""
    
    def __init__(self, icon: str, title: str, description: str, color: str, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._title = title
        self._description = description
        self._color = color
        self._init_ui()
    
    def _init_ui(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.setStyleSheet(f"""
            MainCard {{
                background-color: {self._color};
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
        
        icon_label = QLabel(self._icon)
        icon_label.setStyleSheet("font-size: 48px;")
        icon_label.setFixedSize(60, 60)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        
        title_label = QLabel(self._title)
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #1f2937;")
        text_layout.addWidget(title_label)
        
        desc_label = QLabel(self._description)
        desc_label.setFont(QFont("Microsoft YaHei", 11))
        desc_label.setStyleSheet("color: #6b7280;")
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()
    
    def sizeHint(self):
        return QSize(320, 140)


class StatCard(QFrame):
    """统计卡片 - 小卡片样式"""
    
    def __init__(self, icon: str, label: str, value: str, color: str, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._label = label
        self._value = value
        self._color = color
        self._init_ui()
    
    def _init_ui(self):
        self.setStyleSheet(f"""
            StatCard {{
                background-color: {self._color};
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
        
        icon_label = QLabel(self._icon)
        icon_label.setStyleSheet("font-size: 32px;")
        icon_label.setFixedSize(44, 44)
        layout.addWidget(icon_label)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        value_label = QLabel(self._value)
        value_label.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        value_label.setStyleSheet("color: #1f2937;")
        text_layout.addWidget(value_label)
        
        label_label = QLabel(self._label)
        label_label.setFont(QFont("Microsoft YaHei", 10))
        label_label.setStyleSheet("color: #6b7280;")
        text_layout.addWidget(label_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()
    
    def sizeHint(self):
        return QSize(250, 100)


class ToolCard(QFrame):
    """工具卡片 - 紧凑样式"""
    
    def __init__(self, icon: str, title: str, desc: str, color: str, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._title = title
        self._desc = desc
        self._color = color
        self._init_ui()
    
    def _init_ui(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(80)
        
        self.setStyleSheet(f"""
            ToolCard {{
                background-color: {self._color};
                border-radius: 12px;
                border: 1px solid #e5e7eb;
            }}
            ToolCard:hover {{
                border: 2px solid #3b82f6;
                background-color: #ffffff;
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(4)
        shadow.setColor(QColor(0, 0, 0, 10))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        icon_label = QLabel(self._icon)
        icon_label.setStyleSheet("font-size: 28px;")
        icon_label.setFixedSize(36, 36)
        layout.addWidget(icon_label)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        t_label = QLabel(self._title)
        t_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        t_label.setStyleSheet("color: #1f2937;")
        text_layout.addWidget(t_label)
        
        d_label = QLabel(self._desc)
        d_label.setFont(QFont("Microsoft YaHei", 9))
        d_label.setStyleSheet("color: #6b7280;")
        text_layout.addWidget(d_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()


class SectionTitle(QLabel):
    """区块标题"""
    
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        self.setStyleSheet("color: #1f2937; margin-top: 32px; margin-bottom: 16px;")


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
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(59, 130, 246, 60))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 32)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        
        greeting = QLabel(" 欢迎回来！")
        greeting.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        greeting.setStyleSheet("color: #ffffff;")
        text_layout.addWidget(greeting)
        
        subtitle = QLabel("Hermes Desktop - 您的 AI 智能工作台")
        subtitle.setFont(QFont("Microsoft YaHei", 14))
        subtitle.setStyleSheet("color: #e0e7ff;")
        text_layout.addWidget(subtitle)
        
        desc = QLabel("集成对话、写作、研究、装配、经济、社交等多功能于一体")
        desc.setFont(QFont("Microsoft YaHei", 12))
        desc.setStyleSheet("color: #c7d2fe;")
        text_layout.addWidget(desc)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        icon_label = QLabel("🤖")
        icon_label.setStyleSheet("font-size: 80px;")
        layout.addWidget(icon_label)
    
    def sizeHint(self):
        return QSize(400, 160)


class MainWindow(QWidget):
    """
    主窗口 - 全新仪表盘设计
    
    特性：
    - 支持横向和纵向滚动
    - 响应式布局，自适应不同分辨率
    - 集成所有系统功能模块
    """
    
    switch_to_writing = pyqtSignal(str)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.current_session_id = None
        self._agent = None
        
        self._build_ui()
        
        self.setWindowTitle("Hermes Desktop v2.0")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)
    
    def _build_ui(self):
        """构建UI布局"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 顶部导航栏
        nav_bar = self._create_nav_bar()
        main_layout.addWidget(nav_bar)
        
        # 双层滚动：横向 + 纵向
        h_scroll = QScrollArea()
        h_scroll.setWidgetResizable(True)
        h_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        h_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        h_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        h_content = QWidget()
        h_layout = QHBoxLayout(h_content)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        
        v_scroll = QScrollArea()
        v_scroll.setWidgetResizable(True)
        v_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        v_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        v_scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: #f8fafc; }
            QScrollBar:vertical {
                border: none; background: #f1f5f9; width: 10px; border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1; border-radius: 5px; min-height: 40px;
            }
            QScrollBar::handle:vertical:hover { background: #94a3b8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(32, 32, 32, 32)
        content_layout.setSpacing(28)
        
        self._build_welcome_section(content_layout)
        self._build_stats_section(content_layout)
        self._build_core_modules_section(content_layout)
        self._build_ai_modules_section(content_layout)
        self._build_network_section(content_layout)
        self._build_economy_section(content_layout)
        self._build_tools_section(content_layout)
        self._build_footer(content_layout)
        
        v_scroll.setWidget(content_area)
        h_layout.addWidget(v_scroll)
        h_scroll.setWidget(h_content)
        main_layout.addWidget(h_scroll)
    
    def _create_nav_bar(self):
        """创建顶部导航栏"""
        nav = QFrame()
        nav.setFixedHeight(60)
        nav.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-bottom: 1px solid #e5e7eb;
            }
        """)
        
        layout = QHBoxLayout(nav)
        layout.setContentsMargins(24, 0, 24, 0)
        
        logo = QLabel("🌿 Hermes")
        logo.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        logo.setStyleSheet("color: #1f2937;")
        layout.addWidget(logo)
        
        layout.addStretch()
        
        nav_buttons = [
            ("🏠 首页", "home"),
            ("💬 系统大脑", "brain"),
            ("✍️ 写作", "writing"),
            ("🔍 研究", "research"),
            ("🚀 舰桥", "bridge"),
        ]
        
        for text, action_id in nav_buttons:
            btn = QPushButton(text)
            btn.setFont(QFont("Microsoft YaHei", 11))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent; color: #6b7280;
                    border: none; padding: 8px 16px; border-radius: 8px;
                }
                QPushButton:hover { background-color: #f3f4f6; color: #1f2937; }
            """)
            layout.addWidget(btn)
        
        layout.addStretch()
        
        settings_btn = QPushButton("⚙️ 设置")
        settings_btn.setFont(QFont("Microsoft YaHei", 11))
        settings_btn.setObjectName("SettingsBtn")
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6; color: #ffffff;
                border: none; padding: 8px 20px; border-radius: 8px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(settings_btn)
        
        return nav
    
    def _open_settings(self):
        """打开设置对话框"""
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.config, self)
        dialog.config_changed.connect(self._on_config_changed)
        dialog.exec()
    
    def _on_config_changed(self, new_config):
        """配置已更改"""
        self.config = new_config
        # 保存配置到文件
        self._save_config()
        self._refresh_stats()
        self._show_config_saved_message()
    
    def _save_config(self):
        """保存配置到文件"""
        try:
            import json
            from pathlib import Path
            from core.config import AppConfig
            
            config_path = Path.home() / ".hermes" / "config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 使用 model_dump 序列化配置
            config_dict = self.config.model_dump()
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"配置已保存到: {config_path}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
    
    def _refresh_stats(self):
        """刷新统计卡片"""
        try:
            # 更新 Agent 状态
            if self._agent:
                self._update_stat_card("🤖", "Agent 状态", "已就绪", "#22c55e")
            else:
                self._update_stat_card("🤖", "Agent 状态", "未初始化", "#fef3c7")
            
            # 更新模型数量
            from core.model_manager import ModelManager
            model_manager = ModelManager(self.config)
            available_models = model_manager.get_available_models()
            self._update_stat_card("🧠", "可用模型", f"{len(available_models)} 个", "#eff6ff")
            
            # 更新默认模型显示
            if available_models:
                default_model = self.config.ollama.default_model
                self._update_stat_card("🧠", "默认模型", default_model, "#eff6ff")
        except Exception as e:
            logger.warning(f"刷新统计失败: {e}")
    
    def _update_stat_card(self, icon, label, value, color):
        """更新统计卡片显示"""
        # 这里需要找到对应的 StatCard 并更新它
        # 暂时通过重新加载配置来更新
        pass
    
    def _show_config_saved_message(self):
        """显示配置保存成功的消息"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("配置已保存")
        msg_box.setText("配置已成功保存！\n\n新的配置将在下次启动时生效。")
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
    
    def _build_welcome_section(self, layout):
        """欢迎区域"""
        banner = WelcomeBanner()
        layout.addWidget(banner)
    
    def _build_stats_section(self, layout):
        """系统概览统计"""
        title = SectionTitle("📊 系统概览")
        layout.addWidget(title)
        
        flow = ResponsiveFlowLayout(self, spacing=16, min_card_width=200)
        
        stats = [
            ("🤖", "Agent 状态", "未初始化", "#fef3c7"),
            ("🧠", "可用模型", "0 个", "#eff6ff"),
            ("💬", "会话数量", "0", "#f0fdf4"),
            ("⚡", "系统性能", "良好", "#fce7f3"),
            ("💾", "磁盘空间", "充足", "#e0f2fe"),
            ("🌐", "网络状态", "已连接", "#dcfce7"),
        ]
        
        for icon, label, value, color in stats:
            flow.addWidget(StatCard(icon, label, value, color), 100)
        
        layout.addWidget(flow)
    
    def _build_core_modules_section(self, layout):
        """核心功能模块"""
        title = SectionTitle("🚀 核心功能")
        layout.addWidget(title)
        
        flow = ResponsiveFlowLayout(self, spacing=16, min_card_width=300)
        
        modules = [
            ("🧠", "系统大脑", "AI 对话交互中心，支持多轮对话、工具调用、思考链展示、会话管理", "#eff6ff"),
            ("✍️", "写作助手", "文档创作与编辑，支持智能续写、改写、摘要生成、格式排版", "#fef3c7"),
            ("🔍", "研究助手", "深度搜索与分析，支持网络搜索、数据分析、报告生成、趋势预测", "#f0fdf4"),
            ("⚗️", "嫁接园", "工具装配平台，集成 MCP 协议，支持自定义工具链、工作流编排", "#fce7f3"),
            ("🚀", "舰桥", "元宇宙工作台，可视化操作界面，支持多任务管理、全息星图导航", "#e0f2fe"),
            ("📁", "文件管理", "文件浏览、上传、下载，支持多种格式预览、版本控制、协作编辑", "#ede9fe"),
        ]
        
        for icon, mod_title, desc, color in modules:
            flow.addWidget(MainCard(icon, mod_title, desc, color), 140)
        
        layout.addWidget(flow)
    
    def _build_ai_modules_section(self, layout):
        """AI 核心能力模块"""
        title = SectionTitle(" AI 核心能力")
        layout.addWidget(title)
        
        flow = ResponsiveFlowLayout(self, spacing=16, min_card_width=300)
        
        ai_modules = [
            ("🔍", "FusionRAG 检索", "四层混合检索系统：精确缓存、会话缓存、知识库、数据库层，智能路由", "#dbeafe"),
            ("📡", "情报中心", "多源搜索聚合、谣言检测与舆情分析、竞品监控流、预警与分发、自动报告", "#dcfce7"),
            ("🧩", "技能市场", "Skill 插件生态、去中心化技能交易、收益代币化、技能组合与推荐", "#fef3c7"),
            ("🎭", "数字分身", "个性化 AI 角色、行为学习、习惯迁移、多身份切换、数字遗产继承", "#ede9fe"),
            ("📝", "智能记忆", "对话记忆管理、知识图谱构建、经验沉淀、遗忘曲线、关联推荐", "#fce7f3"),
            ("", "决策引擎", "多方案对比、风险评估、成本预估、概率分析、最优解推荐", "#e0f2fe"),
        ]
        
        for icon, mod_title, desc, color in ai_modules:
            flow.addWidget(MainCard(icon, mod_title, desc, color), 140)
        
        layout.addWidget(flow)
    
    def _build_network_section(self, layout):
        """网络与协作模块"""
        title = SectionTitle("🌐 网络与协作")
        layout.addWidget(title)
        
        flow = ResponsiveFlowLayout(self, spacing=16, min_card_width=300)
        
        network_modules = [
            ("🔗", "P2P 网络", "根系网络连接、节点发现与触碰、季风广播、中继水源、伪域名解析", "#e0f2fe"),
            ("👥", "LAN 聊天", "局域网即时通讯、文件传输、群组聊天、消息加密、离线消息", "#fef3c7"),
            ("🔐", "身份认证", "用户注册、JWT Token、第三方 OAuth (GitHub/Google/微信)、节点注册", "#dcfce7"),
            ("📋", "任务管理", "分布式任务调度、防重放、状态追踪、优先级队列、强容错执行", "#ede9fe"),
            ("🔄", "配置同步", "多端配置同步、版本管理、冲突解决、增量更新、回滚恢复", "#fce7f3"),
        ]
        
        for icon, mod_title, desc, color in network_modules:
            flow.addWidget(MainCard(icon, mod_title, desc, color), 140)
        
        layout.addWidget(flow)
    
    def _build_economy_section(self, layout):
        """经济与社交模块"""
        title = SectionTitle("💰 经济与社交")
        layout.addWidget(title)
        
        flow = ResponsiveFlowLayout(self, spacing=16, min_card_width=300)
        
        economy_modules = [
            ("💰", "积分经济", "动态积分发放、智能消耗、分层共识、状态通道、概率性最终性", "#fef3c7"),
            ("🎮", "挂机等级", "智能挂机积分、数据挖矿/节点耕作/AI训练场、10级体系、等级特权", "#fce7f3"),
            ("🏆", "成就系统", "全链路成就追踪、时间胶囊、成就进化、组合技、元宇宙画廊、基因传承", "#ede9fe"),
            ("🏪", "资产生态", "数字/物理资产交易、5种交付方式、物流集成、信任网络、微型社会DAO", "#f0f9ff"),
            ("🎁", "充值与VIP", "积分充值、首充奖励、VIP等级体系、每日赠送、升级奖励、支付网关", "#dbeafe"),
        ]
        
        for icon, mod_title, desc, color in economy_modules:
            flow.addWidget(MainCard(icon, mod_title, desc, color), 140)
        
        layout.addWidget(flow)
    
    def _build_tools_section(self, layout):
        """工具与设置区域"""
        title = SectionTitle("🛠️ 工具与设置")
        layout.addWidget(title)
        
        flow = ResponsiveFlowLayout(self, spacing=12, min_card_width=220)
        
        tools = [
            ("⚙️", "系统设置", "模型配置、API管理、主题切换", "#f3f4f6"),
            ("📦", "模型管理", "下载、切换、管理本地模型", "#f3f4f6"),
            ("🔧", "工具市场", "浏览、安装扩展工具", "#f3f4f6"),
            ("📊", "数据统计", "使用统计、性能分析", "#f3f4f6"),
            ("🔑", "管理员授权", "角色管理、序列号生成", "#f3f4f6"),
            ("🗄️", "数据库管理", "会话管理、数据备份", "#f3f4f6"),
            ("🧪", "调试工具", "日志查看、性能监控", "#f3f4f6"),
            ("📖", "帮助文档", "使用指南、常见问题", "#f3f4f6"),
        ]
        
        for icon, tool_title, desc, color in tools:
            flow.addWidget(ToolCard(icon, tool_title, desc, color), 80)
        
        layout.addWidget(flow)
    
    def _build_footer(self, layout):
        """底部信息"""
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: #f3f4f6;
                border-radius: 12px;
            }
        """)
        
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 16, 24, 16)
        
        version = QLabel("Hermes Desktop v2.0")
        version.setFont(QFont("Microsoft YaHei", 10))
        version.setStyleSheet("color: #6b7280;")
        footer_layout.addWidget(version)
        
        footer_layout.addStretch()
        
        tech_stack = QLabel("PyQt6 | Ollama | GPT4All | ModelScope | FastAPI | SQLite")
        tech_stack.setFont(QFont("Microsoft YaHei", 9))
        tech_stack.setStyleSheet("color: #9ca3af;")
        footer_layout.addWidget(tech_stack)
        
        footer_layout.addStretch()
        
        copyright_label = QLabel("© 2026 Hermes Desktop")
        copyright_label.setFont(QFont("Microsoft YaHei", 9))
        copyright_label.setStyleSheet("color: #9ca3af;")
        footer_layout.addWidget(copyright_label)
        
        layout.addWidget(footer)


__all__ = ['MainWindow']
