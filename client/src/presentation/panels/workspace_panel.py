"""
增强版工作区面板 — 右侧栏
=========================
功能：
  - 系统特色快捷入口：记忆宫殿、知识图谱、工作流、思维链、技能库
  - 动态内容展示区（根据选中功能显示）
  - 保留原有文件树和记忆选项卡
  - 知识库初始化引导
  - 知识库初始化逻辑

信号:
    feature_changed(str) - 特色功能切换
    kb_init_requested() - 知识库初始化请求
    kb_search_requested(str) - 知识库搜索
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QPalette, QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QPushButton,
    QTabWidget, QFrame, QScrollArea, QSizePolicy,
    QToolButton, QStackedWidget, QLineEdit, QMenu,
)
from PyQt6.QtCore import QUrl

# 导入统一代理面板
try:
    from ui.unified_proxy_panel import UnifiedProxyPanel
    HAS_UNIFIED_PROXY = True
except ImportError:
    HAS_UNIFIED_PROXY = False


class UserGuidePanel(QWidget):
    """用户须知面板 - 快速访问文档"""

    doc_requested = pyqtSignal(str)  # doc_type: architecture/dev/operation

    DOC_ITEMS = [
        ("architecture", "architecture_manual.md", "📐", "架构手册", "系统架构与设计模式"),
        ("dev", "developer_manual.md", "🔧", "开发手册", "开发规范与代码示例"),
        ("operation", "operation_manual.md", "📖", "操作手册", "日常操作指南"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 标题
        header = QLabel("📋 用户须知")
        header.setStyleSheet("""
            color: #333333;
            font-size: 12px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
            padding: 4px 0;
        """)
        layout.addWidget(header)

        # 文档按钮列表
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        for doc_id, filename, icon, title, desc in self.DOC_ITEMS:
            btn = self._create_doc_button(doc_id, icon, title, desc)
            container_layout.addWidget(btn)

        layout.addWidget(container)

    def _create_doc_button(self, doc_id: str, icon: str, title: str, desc: str) -> QWidget:
        """创建文档按钮"""
        btn = QWidget()
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QWidget {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                padding: 10px;
            }
            QWidget:hover {
                background: #F8FAFC;
                border-color: #10B981;
            }
        """)
        layout = QHBoxLayout(btn)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 图标
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 20px;")
        layout.addWidget(icon_label)

        # 文字
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: #333333;
            font-size: 12px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        text_layout.addWidget(title_label)

        desc_label = QLabel(desc)
        desc_label.setStyleSheet("""
            color: #999999;
            font-size: 10px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)

        # 箭头
        arrow = QLabel("›")
        arrow.setStyleSheet("""
            color: #CCCCCC;
            font-size: 16px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(arrow)

        # 点击事件
        btn.mousePressEvent = lambda e, did=doc_id: self._on_click(did)
        return btn

    def _on_click(self, doc_id: str):
        """点击事件"""
        self.doc_requested.emit(doc_id)

    def open_document(self, doc_type: str):
        """打开文档"""
        # 获取项目根目录
        root_dir = Path(__file__).parent.parent.parent.parent.parent
        doc_map = {
            "architecture": "docs/architecture_manual.md",
            "dev": "docs/developer_manual.md",
            "operation": "docs/operation_manual.md",
        }
        doc_path = root_dir / doc_map.get(doc_type, "")

        if doc_path.exists():
            # 使用默认应用打开
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(doc_path)))
        else:
            # 如果文档不存在，打开项目根目录
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(root_dir)))


class SystemFeatureButton(QToolButton):
    """系统特色功能按钮"""

    def __init__(self, icon: str, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.icon = icon
        self.title = title
        self.subtitle = subtitle
        self._is_active = False
        self._setup_ui()

    def _setup_ui(self):
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._update_style()

    def _update_style(self):
        if self._is_active:
            self.setStyleSheet("""
                QToolButton {
                    background: #E8F5E9;
                    border: 1px solid #10B981;
                    border-radius: 8px;
                    padding: 6px 10px;
                    text-align: left;
                    color: #10B981;
                }
                QToolButton:hover {
                    background: #C8E6C9;
                }
            """)
        else:
            self.setStyleSheet("""
                QToolButton {
                    background: #FFFFFF;
                    border: 1px solid #E8E8E8;
                    border-radius: 8px;
                    padding: 6px 10px;
                    text-align: left;
                    color: #666666;
                }
                QToolButton:hover {
                    background: #F5F5F5;
                    border-color: #CCCCCC;
                    color: #333333;
                }
            """)

    def set_active(self, active: bool):
        self._is_active = active
        self._update_style()

    def paintEvent(self, event):
        from PyQt6.QtWidgets import QStyle, QStyleOptionToolButton
        from PyQt6.QtGui import QPainter

        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制图标和文字
        opt = QStyleOptionToolButton()
        opt.initFrom(self)
        opt.icon = self.icon
        opt.toolButtonStyle = Qt.ToolButtonStyle.ToolButtonTextBesideIcon

        # 布局计算
        margin = 8
        icon_size = 24
        text_rect = self.rect().adjusted(margin, 0, -margin, 0)

        # 绘制图标
        icon_rect = QRect(margin, (self.height() - icon_size) // 2, icon_size, icon_size)
        if isinstance(self.icon, str) and len(self.icon) <= 4:
            # 文本emoji
            painter.setFont(self.font())
            painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, self.icon)
        else:
            self.style().drawItemText(painter, icon_rect, Qt.AlignmentFlag.AlignLeft,
                                       self.palette(), True, self.icon, QPalette.ColorRole.WindowText)

        # 绘制标题
        title_font = self.font()
        title_font.setPointSize(10)
        title_font.setBold(True)
        painter.setFont(title_font)
        title_rect = QRect(
            margin + icon_size + 8,
            text_rect.top() + 4,
            text_rect.width() - icon_size - 8,
            18
        )
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title)

        # 绘制副标题
        if self.subtitle:
            subtitle_font = self.font()
            subtitle_font.setPointSize(8)
            painter.setFont(subtitle_font)
            painter.setPen(QColor("#999999"))
            subtitle_rect = QRect(
                margin + icon_size + 8,
                text_rect.top() + 20,
                text_rect.width() - icon_size - 8,
                14
            )
            painter.drawText(subtitle_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.subtitle)


class SystemFeaturesPanel(QWidget):
    """系统特色功能面板"""

    feature_selected = pyqtSignal(str)  # feature_id

    FEATURES = [
        ("memory_palace", "🧠", "记忆宫殿", "长期记忆与上下文"),
        ("knowledge_graph", "🕸️", "知识图谱", "实体关系可视化"),
        ("workflow", "📊", "工作流", "任务分解与执行"),
        ("chain_of_thought", "🔮", "思维链", "推理过程追踪"),
        ("skill_library", "🛠️", "技能库", "技能管理与进化"),
        ("system_stats", "📈", "系统统计", "运行状态一览"),
        ("auto_deploy", "🚀", "自动化部署", "模型部署与管理"),
        ("performance", "⚡", "性能监控", "资源使用分析"),
        ("message_queue", "📨", "消息队列", "任务队列管理"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_feature = "memory_palace"
        self._feature_widgets = {}
        self._setup_ui()
        self._init_feature_widgets()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 标题
        header = QLabel("🔮 系统特色")
        header.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
            padding: 4px 0;
        """)
        layout.addWidget(header)

        # 功能按钮网格
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("border: none; background: transparent;")

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        self.feature_buttons = {}
        for feature_id, icon, title, subtitle in self.FEATURES:
            btn = SystemFeatureButton(icon, title, subtitle)
            btn.clicked.connect(lambda checked, fid=feature_id: self._on_feature_click(fid))
            self.feature_buttons[feature_id] = btn
            container_layout.addWidget(btn)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # 初始化第一个为激活状态
        self._on_feature_click(self._active_feature)

    def _init_feature_widgets(self):
        """初始化各功能的展示控件"""
        pass  # 由 WorkspacePanel 填充

    def set_feature_widget(self, feature_id: str, widget: QWidget):
        """设置功能展示控件"""
        self._feature_widgets[feature_id] = widget

    def _on_feature_click(self, feature_id: str):
        """切换功能"""
        self._active_feature = feature_id
        for fid, btn in self.feature_buttons.items():
            btn.set_active(fid == feature_id)
        self.feature_selected.emit(feature_id)


class KnowledgeBaseInitPanel(QWidget):
    """知识库初始化引导面板"""

    init_requested = pyqtSignal()
    status_updated = pyqtSignal(str)  # status message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addStretch()

        # 图标
        icon_label = QLabel("📚")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 48px;")
        layout.addWidget(icon_label)

        # 标题
        title = QLabel("知识库待初始化")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            color: #333333;
            font-size: 16px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(title)

        # 说明
        desc = QLabel(
            "知识库可以存储和检索文档知识，\n"
            "为 AI 提供更准确的信息支持。\n\n"
            "支持功能：\n"
            "• 文档向量化存储\n"
            "• 混合检索（语义+关键词）\n"
            "• 知识图谱构建"
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("""
            color: #666666;
            font-size: 12px;
            font-family: "Microsoft YaHei", sans-serif;
            line-height: 1.6;
        """)
        layout.addWidget(desc)

        # 初始化按钮
        self.init_btn = QPushButton("🚀 立即初始化")
        self.init_btn.setFixedHeight(40)
        self.init_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        self.init_btn.clicked.connect(self.init_requested.emit)
        layout.addWidget(self.init_btn)

        layout.addStretch()


class KnowledgeBaseViewPanel(QWidget):
    """知识库内容视图"""

    search_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stats = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 搜索框
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 搜索知识库...")
        self.search_box.setFixedHeight(32)
        self.search_box.setStyleSheet("""
            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                padding: 0 12px;
                color: #333333;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #10B981;
            }
        """)
        self.search_box.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.search_box, 1)

        self.search_btn = QPushButton("搜索")
        self.search_btn.setFixedSize(60, 32)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        self.search_btn.clicked.connect(self._on_search)
        search_layout.addWidget(self.search_btn)
        layout.addLayout(search_layout)

        # 统计卡片
        stats_container = QWidget()
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(8)

        self.stats_cards = []
        stats_data = [
            ("📄", "文档", "0"),
            ("🧩", "分块", "0"),
            ("🕸️", "实体", "0"),
            ("🔗", "关系", "0"),
        ]
        for icon, label, value in stats_data:
            card = self._create_stat_card(icon, label, value)
            self.stats_cards.append(card)
            stats_layout.addWidget(card)

        layout.addWidget(stats_container)

        # 内容区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        self.content_layout.addStretch()

        scroll.setWidget(self.content_area)
        layout.addWidget(scroll, 1)

        # 刷新按钮
        refresh_layout = QHBoxLayout()
        refresh_layout.addStretch()
        self.refresh_btn = QPushButton("↻ 刷新")
        self.refresh_btn.setFixedSize(80, 28)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F5;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                color: #666666;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #E8E8E8;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        refresh_layout.addWidget(self.refresh_btn)
        layout.addLayout(refresh_layout)

    def _create_stat_card(self, icon: str, label: str, value: str) -> QWidget:
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(icon_label)

        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setObjectName("stat_value")
        value_label.setStyleSheet("""
            color: #333333;
            font-size: 16px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(value_label)

        label_text = QLabel(label)
        label_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_text.setStyleSheet("""
            color: #999999;
            font-size: 10px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(label_text)

        card._value_label = value_label
        return card

    def _on_search(self):
        text = self.search_box.text().strip()
        if text:
            self.search_requested.emit(text)

    def update_stats(self, stats: Dict[str, int]):
        """更新统计信息"""
        self._stats = stats
        keys = ["documents", "chunks", "entities", "relations"]
        values = [stats.get(k, 0) for k in keys]
        for card, value in zip(self.stats_cards, values):
            if hasattr(card, '_value_label'):
                card._value_label.setText(str(value))

    def set_content(self, items: list):
        """设置内容列表"""
        # 清空现有内容
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for item in items:
            self._add_content_item(item)

    def _add_content_item(self, item: Dict[str, Any]):
        """添加内容项"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 标题
        title = QLabel(item.get("title", ""))
        title.setStyleSheet("""
            color: #333333;
            font-size: 12px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(title)

        # 摘要
        if item.get("summary"):
            summary = QLabel(item.get("summary", ""))
            summary.setStyleSheet("""
                color: #666666;
                font-size: 11px;
                font-family: "Microsoft YaHei", sans-serif;
            """)
            summary.setWordWrap(True)
            layout.addWidget(summary)

        self.content_layout.insertWidget(self.content_layout.count() - 1, widget)


class MemoryPalacePanel(QWidget):
    """记忆宫殿面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._memory_data = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        header = QLabel("🧠 记忆结构")
        header.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(header)

        # 记忆类型卡片
        memory_types = [
            ("💬", "工作记忆", "当前会话上下文", "#E3F2FD"),
            ("📋", "短期记忆", "近期交互记录", "#FFF3E0"),
            ("🏛️", "长期记忆", "持久化知识", "#E8F5E9"),
            ("⚡", "工作流记忆", "任务执行状态", "#FCE4EC"),
        ]

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(8)

        self.memory_cards = {}
        for icon, title, desc, color in memory_types:
            card = self._create_memory_card(icon, title, desc, color)
            self.memory_cards[title] = card
            container_layout.addWidget(card)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # 查看详情按钮
        self.detail_btn = QPushButton("📖 查看完整记忆")
        self.detail_btn.setFixedHeight(36)
        self.detail_btn.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                color: #666666;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #F5F5F5;
                border-color: #CCCCCC;
            }
        """)
        layout.addWidget(self.detail_btn)

    def _create_memory_card(self, icon: str, title: str, desc: str, color: str) -> QWidget:
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background: {color};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24px;")
        layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        text_layout.addWidget(title_label)

        desc_label = QLabel(desc)
        desc_label.setStyleSheet("""
            color: #666666;
            font-size: 11px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)
        layout.addStretch()

        return card

    def update_memory_stats(self, stats: Dict[str, Any]):
        """更新记忆统计"""
        self._memory_data = stats


class KnowledgeGraphPanel(QWidget):
    """知识图谱面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        header = QLabel("🕸️ 知识图谱")
        header.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(header)

        # 统计信息
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background: #F8FAFC;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setSpacing(16)

        self.entity_count = self._create_stat_item("🧩", "实体", "0")
        self.relation_count = self._create_stat_item("🔗", "关系", "0")
        self.triple_count = self._create_stat_item("📊", "三元组", "0")

        stats_layout.addWidget(self.entity_count)
        stats_layout.addWidget(self.relation_count)
        stats_layout.addWidget(self.triple_count)
        layout.addWidget(stats_frame)

        # 最近实体列表
        recent_label = QLabel("📌 最近实体")
        recent_label.setStyleSheet("""
            color: #666666;
            font-size: 11px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(recent_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        self.entity_list = QWidget()
        self.entity_list_layout = QVBoxLayout(self.entity_list)
        self.entity_list_layout.setContentsMargins(0, 0, 0, 0)
        self.entity_list_layout.setSpacing(6)

        scroll.setWidget(self.entity_list)
        layout.addWidget(scroll, 1)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.add_btn = QPushButton("➕ 添加")
        self.add_btn.setFixedHeight(32)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        btn_layout.addWidget(self.add_btn)

        self.view_btn = QPushButton("🕸️ 全景")
        self.view_btn.setFixedHeight(32)
        self.view_btn.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                color: #666666;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #F5F5F5;
            }
        """)
        btn_layout.addWidget(self.view_btn)

        layout.addLayout(btn_layout)

    def _create_stat_item(self, icon: str, label: str, value: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setObjectName("kg_stat_value")
        value_label.setStyleSheet("""
            color: #333333;
            font-size: 18px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(value_label)

        label_text = QLabel(label)
        label_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_text.setStyleSheet("""
            color: #999999;
            font-size: 10px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(label_text)

        widget._value_label = value_label
        return widget

    def update_stats(self, entities: int, relations: int, triples: int):
        """更新统计"""
        if hasattr(self.entity_count, '_value_label'):
            self.entity_count._value_label.setText(str(entities))
        if hasattr(self.relation_count, '_value_label'):
            self.relation_count._value_label.setText(str(relations))
        if hasattr(self.triple_count, '_value_label'):
            self.triple_count._value_label.setText(str(triples))

    def set_recent_entities(self, entities: list):
        """设置最近实体"""
        while self.entity_list_layout.count():
            item = self.entity_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for entity in entities[:10]:  # 最多显示10个
            item = QWidget()
            item.setStyleSheet("""
                QWidget {
                    background: #FFFFFF;
                    border: 1px solid #E8E8E8;
                    border-radius: 6px;
                    padding: 8px;
                }
            """)
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(8)

            icon = QLabel("🔹")
            icon.setStyleSheet("font-size: 12px; color: #10B981;")
            item_layout.addWidget(icon)

            name = QLabel(entity.get("name", ""))
            name.setStyleSheet("""
                color: #333333;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            """)
            item_layout.addWidget(name, 1)

            type_label = QLabel(entity.get("type", ""))
            type_label.setStyleSheet("""
                color: #999999;
                font-size: 10px;
                font-family: "Microsoft YaHei", sans-serif;
            """)
            item_layout.addWidget(type_label)

            self.entity_list_layout.addWidget(item)


class WorkflowPanel(QWidget):
    """工作流面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_tasks = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        header = QLabel("📊 工作流")
        header.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(header)

        # 当前任务
        task_label = QLabel("⚡ 进行中任务")
        task_label.setStyleSheet("""
            color: #666666;
            font-size: 11px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(task_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        self.task_list = QWidget()
        self.task_list_layout = QVBoxLayout(self.task_list)
        self.task_list_layout.setContentsMargins(0, 0, 0, 0)
        self.task_list_layout.setSpacing(6)

        scroll.setWidget(self.task_list)
        layout.addWidget(scroll, 1)

        # 历史记录按钮
        self.history_btn = QPushButton("📜 查看执行历史")
        self.history_btn.setFixedHeight(32)
        self.history_btn.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                color: #666666;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #F5F5F5;
            }
        """)
        layout.addWidget(self.history_btn)

    def set_active_tasks(self, tasks: list):
        """设置进行中的任务"""
        self._active_tasks = tasks

        while self.task_list_layout.count():
            item = self.task_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not tasks:
            empty = QLabel("暂无进行中的任务")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("""
                color: #999999;
                font-size: 12px;
                padding: 20px;
            """)
            self.task_list_layout.addWidget(empty)
            return

        for task in tasks:
            self._add_task_item(task)

    def _add_task_item(self, task: Dict[str, Any]):
        """添加任务项"""
        item = QWidget()
        status_color = {
            "running": "#10B981",
            "pending": "#FFD700",
            "completed": "#CCCCCC",
            "failed": "#EF4444",
        }.get(task.get("status", "pending"), "#999999")

        item.setStyleSheet("""
            QWidget {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(item)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 任务名称和状态
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        status_dot = QLabel("●")
        status_dot.setStyleSheet(f"color: {status_color}; font-size: 10px;")
        top_layout.addWidget(status_dot)

        name = QLabel(task.get("name", "未命名任务"))
        name.setStyleSheet("""
            color: #333333;
            font-size: 12px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        top_layout.addWidget(name, 1)
        layout.addLayout(top_layout)

        # 进度条（如果有进度）
        if "progress" in task:
            progress = QFrame()
            progress.setStyleSheet("""
                QFrame {
                    background: #F5F5F5;
                    border-radius: 3px;
                    height: 6px;
                }
            """)
            progress_layout = QVBoxLayout(progress)
            progress_layout.setContentsMargins(0, 0, 0, 0)

            bar = QFrame()
            bar.setFixedHeight(6)
            bar.setStyleSheet(f"""
                QFrame {{
                    background: {status_color};
                    border-radius: 3px;
                    width: {task['progress']}%;
                }}
            """)
            progress_layout.addWidget(bar)
            layout.addWidget(progress)

        self.task_list_layout.addWidget(item)


class ChainOfThoughtPanel(QWidget):
    """思维链面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thought_chains = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        header = QLabel("🔮 思维链")
        header.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(header)

        # 说明
        desc = QLabel("记录 AI 推理过程，帮助理解决策逻辑")
        desc.setStyleSheet("""
            color: #666666;
            font-size: 11px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        self.chain_list = QWidget()
        self.chain_list_layout = QVBoxLayout(self.chain_list)
        self.chain_list_layout.setContentsMargins(0, 0, 0, 0)
        self.chain_list_layout.setSpacing(8)

        scroll.setWidget(self.chain_list)
        layout.addWidget(scroll, 1)

        # 清空按钮
        self.clear_btn = QPushButton("🗑️ 清空历史")
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                color: #999999;
                font-size: 11px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #FFF3E0;
                border-color: #FFB74D;
                color: #E65100;
            }
        """)
        layout.addWidget(self.clear_btn)

    def add_thought_chain(self, chain: Dict[str, Any]):
        """添加思维链"""
        self._thought_chains.insert(0, chain)

        # 保持最多显示20条
        if len(self._thought_chains) > 20:
            self._thought_chains = self._thought_chains[:20]

        self._refresh_chains()

    def _refresh_chains(self):
        """刷新显示"""
        while self.chain_list_layout.count():
            item = self.chain_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, chain in enumerate(self._thought_chains[:5]):  # 最多显示5条
            self._add_chain_item(chain, i + 1)

    def _add_chain_item(self, chain: Dict[str, Any], index: int):
        """添加思维链项"""
        item = QWidget()
        item.setStyleSheet("""
            QWidget {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(item)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 序号和类型
        top_layout = QHBoxLayout()

        index_label = QLabel(f"#{index}")
        index_label.setStyleSheet("""
            color: #10B981;
            font-size: 11px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        top_layout.addWidget(index_label)

        type_label = QLabel(chain.get("type", "推理"))
        type_label.setStyleSheet("""
            color: #999999;
            font-size: 10px;
            background: #F5F5F5;
            padding: 2px 8px;
            border-radius: 4px;
        """)
        top_layout.addWidget(type_label)
        top_layout.addStretch()

        layout.addLayout(top_layout)

        # 问题
        query = QLabel(chain.get("query", ""))
        query.setStyleSheet("""
            color: #333333;
            font-size: 11px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        query.setWordWrap(True)
        layout.addWidget(query)

        # 推理摘要
        if chain.get("summary"):
            summary = QLabel(chain.get("summary", ""))
            summary.setStyleSheet("""
                color: #666666;
                font-size: 10px;
                font-family: "Microsoft YaHei", sans-serif;
                background: #F8FAFC;
                padding: 6px;
                border-radius: 4px;
            """)
            summary.setWordWrap(True)
            layout.addWidget(summary)

        self.chain_list_layout.addWidget(item)


class SkillLibraryPanel(QWidget):
    """技能库面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._skills = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        header = QLabel("🛠️ 技能库")
        header.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(header)

        # 统计
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background: #F8FAFC;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setSpacing(16)

        self.skill_count = self._create_stat_item("📦", "技能总数", "0")
        self.active_count = self._create_stat_item("✅", "活跃", "0")
        self.evolving_count = self._create_stat_item("🔄", "进化中", "0")

        stats_layout.addWidget(self.skill_count)
        stats_layout.addWidget(self.active_count)
        stats_layout.addWidget(self.evolving_count)
        layout.addWidget(stats_frame)

        # 技能列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        self.skill_list = QWidget()
        self.skill_list_layout = QVBoxLayout(self.skill_list)
        self.skill_list_layout.setContentsMargins(0, 0, 0, 0)
        self.skill_list_layout.setSpacing(6)

        scroll.setWidget(self.skill_list)
        layout.addWidget(scroll, 1)

        # 创建新技能按钮
        self.create_btn = QPushButton("➕ 创建新技能")
        self.create_btn.setFixedHeight(32)
        self.create_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        layout.addWidget(self.create_btn)

    def _create_stat_item(self, icon: str, label: str, value: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setObjectName("skill_stat_value")
        value_label.setStyleSheet("""
            color: #333333;
            font-size: 16px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(value_label)

        label_text = QLabel(label)
        label_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_text.setStyleSheet("""
            color: #999999;
            font-size: 10px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(label_text)

        widget._value_label = value_label
        return widget

    def update_stats(self, total: int, active: int, evolving: int):
        """更新统计"""
        if hasattr(self.skill_count, '_value_label'):
            self.skill_count._value_label.setText(str(total))
        if hasattr(self.active_count, '_value_label'):
            self.active_count._value_label.setText(str(active))
        if hasattr(self.evolving_count, '_value_label'):
            self.evolving_count._value_label.setText(str(evolving))

    def set_skills(self, skills: list):
        """设置技能列表"""
        self._skills = skills

        while self.skill_list_layout.count():
            item = self.skill_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not skills:
            empty = QLabel("暂无技能，请创建第一个技能")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("""
                color: #999999;
                font-size: 12px;
                padding: 20px;
            """)
            self.skill_list_layout.addWidget(empty)
            return

        for skill in skills:
            self._add_skill_item(skill)

    def _add_skill_item(self, skill: Dict[str, Any]):
        """添加技能项"""
        item = QWidget()
        item.setStyleSheet("""
            QWidget {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                padding: 10px;
            }
            QWidget:hover {
                border-color: #10B981;
            }
        """)
        layout = QHBoxLayout(item)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 图标
        icon = QLabel(skill.get("icon", "🛠️"))
        icon.setStyleSheet("font-size: 20px;")
        layout.addWidget(icon)

        # 信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name = QLabel(skill.get("name", "未命名"))
        name.setStyleSheet("""
            color: #333333;
            font-size: 12px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        info_layout.addWidget(name)

        desc = QLabel(skill.get("description", ""))
        desc.setStyleSheet("""
            color: #999999;
            font-size: 10px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        info_layout.addWidget(desc)

        layout.addLayout(info_layout, 1)

        # 状态标签
        status = skill.get("status", "active")
        status_label = QLabel("✅" if status == "active" else "🔄")
        status_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(status_label)

        self.skill_list_layout.addWidget(item)


class SystemStatsPanel(QWidget):
    """系统统计面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stats = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        header = QLabel("📈 系统统计")
        header.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(header)

        # 统计卡片网格
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(8)

        self.stat_cards = {}

        # 创建统计卡片
        stats_data = [
            ("💬", "会话数", "sessions", "0", "#E3F2FD"),
            ("📝", "消息数", "messages", "0", "#FFF3E0"),
            ("🧩", "实体数", "entities", "0", "#E8F5E9"),
            ("🔗", "关系数", "relations", "0", "#FCE4EC"),
            ("📦", "技能数", "skills", "0", "#F3E5F5"),
            ("⏱️", "运行时长", "uptime", "0:00", "#E0F7FA"),
        ]

        for icon, title, key, default_value, color in stats_data:
            card = self._create_stat_card(icon, title, default_value, color)
            self.stat_cards[key] = card
            container_layout.addWidget(card)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # 刷新按钮
        self.refresh_btn = QPushButton("↻ 刷新统计")
        self.refresh_btn.setFixedHeight(32)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                color: #666666;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #F5F5F5;
            }
        """)
        layout.addWidget(self.refresh_btn)

    def _create_stat_card(self, icon: str, title: str, value: str, color: str) -> QWidget:
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background: {color};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 20px;")
        layout.addWidget(icon_label)

        value_label = QLabel(value)
        value_label.setObjectName("stat_value")
        value_label.setStyleSheet("""
            color: #333333;
            font-size: 22px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(value_label)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: #666666;
            font-size: 11px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(title_label)

        card._value_label = value_label
        return card

    def update_stats(self, stats: Dict[str, Any]):
        """更新统计数据"""
        self._stats = stats
        for key, card in self.stat_cards.items():
            if hasattr(card, '_value_label') and key in stats:
                card._value_label.setText(str(stats[key]))


# ── 增强版工作区面板 ──────────────────────────────────────────────────────


class WorkspacePanel(QWidget):
    """
    增强版工作区面板

    整合了：
    - 系统特色功能区（顶部快捷入口）
    - 动态内容展示区（根据选中功能显示）
    - 原有文件树和记忆选项卡（底部）
    - 知识库初始化引导（未初始化时显示）

    信号:
        feature_changed(str) - 特色功能切换
        kb_init_requested() - 知识库初始化请求
        kb_search_requested(str) - 知识库搜索
        workspace_changed(str) - 工作区路径变更
    """

    feature_changed = pyqtSignal(str)
    kb_init_requested = pyqtSignal()
    kb_search_requested = pyqtSignal(str)
    workspace_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WorkspacePanel")
        self.setMinimumWidth(280)
        self.setMaximumWidth(400)

        self._workspace_path: str = ""
        self._kb_initialized = False  # 知识库是否已初始化

        # 子面板实例
        self._feature_panels: Dict[str, QWidget] = {}

        self._build_ui()
        self._check_knowledge_base()

    def _build_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── 用户须知区 ──────────────────────────────────────────────
        self._build_user_guide_section(layout)

        # ── 顶部系统特色功能区 ──────────────────────────────────────
        self._build_feature_section(layout)

        # ── 动态内容展示区 ──────────────────────────────────────────
        self._build_content_section(layout)

        # ── 底部分隔线 ──────────────────────────────────────────────
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: #E8E8E8;")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        # ── 底部选项卡（文件/记忆）───────────────────────────────────
        self._build_bottom_tabs(layout)

    def _build_user_guide_section(self, parent_layout: QVBoxLayout):
        """构建用户须知区"""
        self.user_guide_panel = UserGuidePanel()
        self.user_guide_panel.doc_requested.connect(self._on_doc_requested)
        parent_layout.addWidget(self.user_guide_panel)

    def _on_doc_requested(self, doc_type: str):
        """处理文档请求"""
        self.user_guide_panel.open_document(doc_type)

    def _build_feature_section(self, parent_layout: QVBoxLayout):
        """构建顶部系统特色功能区"""
        # 标题
        header = QLabel("🔮 系统特色")
        header.setStyleSheet("""
            color: #333333;
            font-size: 12px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
            padding: 4px 4px;
        """)
        parent_layout.addWidget(header)

        # 功能按钮网格
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("border: none; background: transparent;")

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        self.feature_buttons = {}
        features = [
            ("memory_palace", "🧠", "记忆宫殿", "长期记忆"),
            ("knowledge_graph", "🕸️", "知识图谱", "实体关系"),
            ("workflow", "📊", "工作流", "任务执行"),
            ("chain_of_thought", "🔮", "思维链", "推理过程"),
            ("skill_library", "🛠️", "技能库", "技能管理"),
            ("system_stats", "📈", "系统统计", "运行状态"),
            ("auto_deploy", "🚀", "自动化部署", "模型部署"),
            ("performance", "⚡", "性能监控", "资源分析"),
            ("message_queue", "📨", "消息队列", "任务管理"),
        ]

        for feature_id, icon, title, subtitle in features:
            btn = SystemFeatureButton(icon, title, subtitle)
            btn.clicked.connect(lambda checked, fid=feature_id: self._on_feature_click(fid))
            self.feature_buttons[feature_id] = btn
            container_layout.addWidget(btn)

        container_layout.addStretch()
        scroll.setWidget(container)
        parent_layout.addWidget(scroll, 1)

        # 初始化第一个为激活状态
        self._active_feature = "memory_palace"
        self.feature_buttons[self._active_feature].set_active(True)

    def _build_content_section(self, parent_layout: QVBoxLayout):
        """构建动态内容展示区"""
        self.content_stack = QStackedWidget()
        parent_layout.addWidget(self.content_stack, 2)

        # ── 知识库初始化面板 ───────────────────────────────────────
        self.kb_init_panel = KnowledgeBaseInitPanel()
        self.kb_init_panel.init_requested.connect(self._on_kb_init_requested)
        self.content_stack.addWidget(self.kb_init_panel)

        # ── 知识库视图面板 ─────────────────────────────────────────
        self.kb_view_panel = KnowledgeBaseViewPanel()
        self.kb_view_panel.search_requested.connect(self.kb_search_requested.emit)
        self.kb_view_panel.refresh_requested.connect(self._refresh_kb_view)
        self.content_stack.addWidget(self.kb_view_panel)

        # ── 各功能内容面板 ─────────────────────────────────────────
        self.memory_panel = MemoryPalacePanel()
        self.content_stack.addWidget(self.memory_panel)

        self.kg_panel = KnowledgeGraphPanel()
        self.content_stack.addWidget(self.kg_panel)

        self.workflow_panel = WorkflowPanel()
        self.content_stack.addWidget(self.workflow_panel)

        self.cot_panel = ChainOfThoughtPanel()
        self.content_stack.addWidget(self.cot_panel)

        self.skill_panel = SkillLibraryPanel()
        self.content_stack.addWidget(self.skill_panel)

        self.stats_panel = SystemStatsPanel()
        self.content_stack.addWidget(self.stats_panel)

        # ── 新增：系统功能面板 ─────────────────────────────────────
        self.deploy_panel = DeploymentPanel()
        self.content_stack.addWidget(self.deploy_panel)

        self.perf_panel = PerformanceMonitorPanel()
        self.content_stack.addWidget(self.perf_panel)

        self.queue_panel = MessageQueuePanel()
        self.content_stack.addWidget(self.queue_panel)

        self._feature_panels = {
            "memory_palace": self.memory_panel,
            "knowledge_graph": self.kg_panel,
            "workflow": self.workflow_panel,
            "chain_of_thought": self.cot_panel,
            "skill_library": self.skill_panel,
            "system_stats": self.stats_panel,
            "auto_deploy": self.deploy_panel,
            "performance": self.perf_panel,
            "message_queue": self.queue_panel,
        }

    def _build_bottom_tabs(self, parent_layout: QVBoxLayout):
        """构建底部文件/记忆选项卡"""
        self.tabs = QTabWidget()
        self.tabs.setObjectName("TabBar")
        self.tabs.tabBar().setObjectName("TabBar")
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #FFFFFF; }
            QTabBar::tab {
                background: transparent;
                color: #666666;
                padding: 8px 12px;
                border: none;
                border-bottom: 2px solid transparent;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QTabBar::tab:selected {
                color: #10B981;
                border-bottom-color: #10B981;
            }
            QTabBar::tab:hover { color: #333333; }
        """)
        parent_layout.addWidget(self.tabs, 1)

        # ── 文件选项卡 ──────────────────────────────────────────────
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)
        file_layout.setContentsMargins(4, 8, 4, 4)
        file_layout.setSpacing(4)

        # 工作目录路径
        path_layout = QHBoxLayout()
        self.path_lbl = QLabel("（未设置工作目录）")
        self.path_lbl.setStyleSheet("color: #555; font-size: 10px; padding: 0 4px;")
        self.path_lbl.setWordWrap(True)
        path_layout.addWidget(self.path_lbl)

        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedSize(24, 24)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #666;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover { color: #10B981; }
        """)
        self.refresh_btn.clicked.connect(self._refresh)
        path_layout.addWidget(self.refresh_btn)
        file_layout.addLayout(path_layout)

        # 文件树
        self.file_tree = QTreeWidget()
        self.file_tree.setObjectName("FileTree")
        self.file_tree.setHeaderHidden(True)
        self.file_tree.itemClicked.connect(self._on_file_clicked)
        file_layout.addWidget(self.file_tree, 1)

        self.tabs.addTab(file_tab, "📁 文件")

        # ── 记忆选项卡 ──────────────────────────────────────────────
        mem_tab = QWidget()
        mem_layout = QVBoxLayout(mem_tab)
        mem_layout.setContentsMargins(4, 8, 4, 4)

        self.memory_view = QTextEdit()
        self.memory_view.setObjectName("MemoryView")
        self.memory_view.setReadOnly(True)
        self.memory_view.setPlaceholderText("Agent 记忆将在此显示...\n(~/.hermes/memory/)")
        self.memory_view.setStyleSheet("""
            QTextEdit {
                background: #FFFFFF;
                border: none;
                color: #333333;
                font-size: 11px;
                font-family: "Microsoft YaHei", sans-serif;
            }
        """)
        mem_layout.addWidget(self.memory_view)
        self.tabs.addTab(mem_tab, "🧠 记忆")

        # ── 代理源选项卡 ──────────────────────────────────────────────
        if HAS_UNIFIED_PROXY:
            proxy_tab = QWidget()
            proxy_layout = QVBoxLayout(proxy_tab)
            proxy_layout.setContentsMargins(0, 8, 0, 4)
            self.proxy_panel = UnifiedProxyPanel()
            proxy_layout.addWidget(self.proxy_panel)
            self.tabs.addTab(proxy_tab, "🌐 代理源")

    def _check_knowledge_base(self):
        """检查知识库是否已初始化"""
        # 检查知识库存储路径
        kb_path = Path.home() / ".hermes" / "knowledge_base"
        if kb_path.exists() and any(kb_path.iterdir()):
            self._kb_initialized = True
            self.content_stack.setCurrentWidget(self.kb_view_panel)
            self._refresh_kb_view()
        else:
            self._kb_initialized = False
            self.content_stack.setCurrentWidget(self.kb_init_panel)

    def _on_kb_init_requested(self):
        """知识库初始化请求"""
        self.kb_init_requested.emit()
        # 模拟初始化过程
        self._simulate_kb_init()

    def _simulate_kb_init(self):
        """模拟知识库初始化"""
        # 创建知识库目录
        kb_path = Path.home() / ".hermes" / "knowledge_base"
        kb_path.mkdir(parents=True, exist_ok=True)

        # 创建配置
        config_path = kb_path / "config.json"
        import json
        config = {
            "initialized": True,
            "version": "1.0.0",
            "embedding_model": "BAAI/bge-small-zh",
            "chunk_size": 512,
        }
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

        # 更新状态
        self._kb_initialized = True
        self.content_stack.setCurrentWidget(self.kb_view_panel)
        self._refresh_kb_view()

        # 发送完成信号
        self.status_bar_msg("知识库初始化完成")

    def _refresh_kb_view(self):
        """刷新知识库视图"""
        if not self._kb_initialized:
            return

        # 模拟统计数据
        stats = {
            "documents": 0,
            "chunks": 0,
            "entities": 0,
            "relations": 0,
        }

        # 尝试读取真实数据
        try:
            kb_path = Path.home() / ".hermes" / "knowledge_base"
            if kb_path.exists():
                stats["documents"] = len(list(kb_path.glob("*.json")))
                chunks_path = kb_path / "chunks"
                if chunks_path.exists():
                    stats["chunks"] = len(list(chunks_path.glob("*.json")))
                entities_path = kb_path / "entities"
                if entities_path.exists():
                    stats["entities"] = len(list(entities_path.glob("*.json")))
        except Exception:
            pass

        self.kb_view_panel.update_stats(stats)

    def _on_feature_click(self, feature_id: str):
        """切换特色功能"""
        # 更新按钮状态
        for fid, btn in self.feature_buttons.items():
            btn.set_active(fid == feature_id)

        self._active_feature = feature_id
        self.feature_changed.emit(feature_id)

        # 切换内容面板
        if feature_id in self._feature_panels:
            self.content_stack.setCurrentWidget(self._feature_panels[feature_id])
        elif feature_id == "knowledge_base":
            if self._kb_initialized:
                self.content_stack.setCurrentWidget(self.kb_view_panel)
            else:
                self.content_stack.setCurrentWidget(self.kb_init_panel)

    def status_bar_msg(self, msg: str):
        """显示状态栏消息"""
        # 通过事件过滤器或信号传递
        pass

    # ── 公共接口 ─────────────────────────────────────────────────────────

    def set_workspace(self, path: str):
        """设置并刷新工作目录"""
        self._workspace_path = path
        self.path_lbl.setText(path or "（未设置）")
        self._refresh_tree()

    def refresh_memory(self):
        """读取 ~/.hermes/memory/MEMORY.md 并展示"""
        memory_file = Path.home() / ".hermes" / "memory" / "MEMORY.md"
        if not memory_file.exists():
            memory_file = Path.home() / ".hermes" / "MEMORY.md"
        if memory_file.exists():
            try:
                text = memory_file.read_text(encoding="utf-8")
                self.memory_view.setPlainText(text)
            except Exception as e:
                self.memory_view.setPlainText(f"读取失败: {e}")
        else:
            self.memory_view.setPlainText("未找到记忆文件\n~/.hermes/memory/MEMORY.md")

    def refresh(self):
        """刷新所有内容"""
        self._refresh()
        if self._kb_initialized:
            self._refresh_kb_view()

    def set_kb_initialized(self, initialized: bool):
        """设置知识库初始化状态"""
        self._kb_initialized = initialized
        if initialized:
            self.content_stack.setCurrentWidget(self.kb_view_panel)
            self._refresh_kb_view()
        else:
            self.content_stack.setCurrentWidget(self.kb_init_panel)

    def update_memory_stats(self, stats: Dict[str, Any]):
        """更新记忆统计"""
        self.memory_panel.update_memory_stats(stats)

    def update_kg_stats(self, entities: int, relations: int, triples: int):
        """更新知识图谱统计"""
        self.kg_panel.update_stats(entities, relations, triples)

    def set_recent_entities(self, entities: list):
        """设置最近实体"""
        self.kg_panel.set_recent_entities(entities)

    def set_active_tasks(self, tasks: list):
        """设置进行中的任务"""
        self.workflow_panel.set_active_tasks(tasks)

    def add_thought_chain(self, chain: Dict[str, Any]):
        """添加思维链"""
        self.cot_panel.add_thought_chain(chain)

    def update_skill_stats(self, total: int, active: int, evolving: int):
        """更新技能统计"""
        self.skill_panel.update_stats(total, active, evolving)

    def set_skills(self, skills: list):
        """设置技能列表"""
        self.skill_panel.set_skills(skills)

    def update_system_stats(self, stats: Dict[str, Any]):
        """更新系统统计"""
        self.stats_panel.update_stats(stats)

    # ── 内部方法 ────────────────────────────────────────────────────────

    def _refresh(self):
        self._refresh_tree()
        self.refresh_memory()

    def _refresh_tree(self):
        self.file_tree.clear()
        path = self._workspace_path
        if not path or not os.path.isdir(path):
            return
        root_item = QTreeWidgetItem(self.file_tree, [os.path.basename(path) or path])
        root_item.setData(0, Qt.ItemDataRole.UserRole, path)
        self._populate_tree(root_item, path, depth=0)
        root_item.setExpanded(True)

    def _populate_tree(self, parent_item, dir_path: str, depth: int):
        if depth > 3:
            return
        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.name in ("__pycache__", "node_modules", ".git"):
                continue
            icon = "📁 " if entry.is_dir() else "📄 "
            item = QTreeWidgetItem(parent_item, [icon + entry.name])
            item.setData(0, Qt.ItemDataRole.UserRole, entry.path)
            if entry.is_dir():
                self._populate_tree(item, entry.path, depth + 1)

    def _on_file_clicked(self, item: QTreeWidgetItem, column: int):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or os.path.isdir(path):
            return
        ext = os.path.splitext(path)[1].lower()
        text_exts = {
            ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml",
            ".md", ".txt", ".sh", ".bat", ".ps1", ".html", ".css",
            ".cfg", ".ini", ".env", ".csv",
        }
        if ext in text_exts:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(8000)
                # 显示在知识库面板的预览区
                if hasattr(self, 'kb_view_panel'):
                    self.kb_view_panel.set_content([{"title": os.path.basename(path), "summary": content[:200]}])
            except Exception as e:
                pass
        else:
            pass


# ── 自动化部署面板 ──────────────────────────────────────────────────────


class DeploymentPanel(QWidget):
    """自动化部署面板 - 监控 L0-L4 模型部署状态"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._init_backend()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        header = QLabel("🚀 自动化部署")
        header.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(header)

        # Ollama 服务状态
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame {
                background: #E8F5E9;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        status_layout = QHBoxLayout(status_frame)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #CCCCCC; font-size: 14px;")
        status_layout.addWidget(self.status_dot)

        self.status_label = QLabel("Ollama 未连接")
        self.status_label.setStyleSheet("""
            color: #666666;
            font-size: 12px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        status_layout.addWidget(self.status_label, 1)

        self.version_label = QLabel("")
        self.version_label.setStyleSheet("""
            color: #999999;
            font-size: 11px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        status_layout.addWidget(self.version_label)

        layout.addWidget(status_frame)

        # 模型层级状态
        tiers_label = QLabel("📦 模型层级")
        tiers_label.setStyleSheet("""
            color: #666666;
            font-size: 11px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(tiers_label)

        self.tier_list = QWidget()
        self.tier_list_layout = QVBoxLayout(self.tier_list)
        self.tier_list_layout.setContentsMargins(0, 0, 0, 0)
        self.tier_list_layout.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        scroll.setWidget(self.tier_list)
        layout.addWidget(scroll, 1)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.refresh_btn = QPushButton("↻ 刷新")
        self.refresh_btn.setFixedHeight(32)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                color: #666666;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #F5F5F5;
            }
        """)
        self.refresh_btn.clicked.connect(self._refresh_status)
        btn_layout.addWidget(self.refresh_btn)

        self.deploy_btn = QPushButton("➕ 部署")
        self.deploy_btn.setFixedHeight(32)
        self.deploy_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        btn_layout.addWidget(self.deploy_btn)

        layout.addLayout(btn_layout)

    def _init_backend(self):
        """初始化后端连接"""
        try:
            from core.deployment_monitor import DeploymentMonitor
            self._monitor = DeploymentMonitor()
            self._refresh_status()
        except ImportError:
            self._monitor = None

    def _refresh_status(self):
        """刷新部署状态"""
        if not self._monitor:
            return

        try:
            status = self._monitor.get_status()
            if status.ollama_running:
                self.status_dot.setStyleSheet("color: #10B981; font-size: 14px;")
                self.status_label.setText("Ollama 运行中")
                self.version_label.setText(f"v{status.ollama_version}")
            else:
                self.status_dot.setStyleSheet("color: #EF4444; font-size: 14px;")
                self.status_label.setText("Ollama 未运行")
                self.version_label.setText("")

            # 更新层级状态
            self._update_tier_list(status)
        except Exception:
            self.status_dot.setStyleSheet("color: #FFD700; font-size: 14px;")
            self.status_label.setText("检查中...")

    def _update_tier_list(self, status):
        """更新层级列表"""
        while self.tier_list_layout.count():
            item = self.tier_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tier_names = {
            "L0": ("路由模型", "#E3F2FD"),
            "L1": ("轻量推理", "#FFF3E0"),
            "L3": ("深度推理", "#E8F5E9"),
            "L4": ("生成模型", "#FCE4EC"),
        }

        for tier_id, tier_info in status.tier_status.items():
            tier_name, color = tier_names.get(tier_id, (tier_id, "#F5F5F5"))

            card = QWidget()
            card.setStyleSheet(f"""
                QWidget {{
                    background: {color};
                    border-radius: 6px;
                    padding: 10px;
                }}
            """)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(10)

            # 层级标签
            tier_label = QLabel(tier_id)
            tier_label.setStyleSheet("""
                color: #333333;
                font-size: 14px;
                font-weight: bold;
                font-family: "Microsoft YaHei", sans-serif;
            """)
            card_layout.addWidget(tier_label)

            # 信息
            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)

            name_label = QLabel(tier_name)
            name_label.setStyleSheet("""
                color: #333333;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            """)
            info_layout.addWidget(name_label)

            model_label = QLabel(tier_info.model_name or "未加载")
            model_label.setStyleSheet("""
                color: #666666;
                font-size: 10px;
                font-family: "Microsoft YaHei", sans-serif;
            """)
            info_layout.addWidget(model_label)

            card_layout.addLayout(info_layout, 1)

            # 状态
            status_icon = "✅" if tier_info.status.name == "READY" else "⏳"
            status_label = QLabel(status_icon)
            status_label.setStyleSheet("font-size: 16px;")
            card_layout.addWidget(status_label)

            self.tier_list_layout.addWidget(card)

    def update_status(self, running: bool, version: str = ""):
        """更新状态（外部调用）"""
        if running:
            self.status_dot.setStyleSheet("color: #10B981; font-size: 14px;")
            self.status_label.setText("Ollama 运行中")
            self.version_label.setText(f"v{version}" if version else "")
        else:
            self.status_dot.setStyleSheet("color: #EF4444; font-size: 14px;")
            self.status_label.setText("Ollama 未运行")


# ── 性能监控面板 ────────────────────────────────────────────────────────


class PerformanceMonitorPanel(QWidget):
    """性能监控面板 - 实时资源监控"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._init_backend()
        self._start_monitoring()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        header = QLabel("⚡ 性能监控")
        header.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(header)

        # 负载等级
        self.load_frame = QFrame()
        self.load_frame.setStyleSheet("""
            QFrame {
                background: #E8F5E9;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        load_layout = QHBoxLayout(self.load_frame)

        self.load_dot = QLabel("●")
        self.load_dot.setStyleSheet("color: #10B981; font-size: 16px;")
        load_layout.addWidget(self.load_dot)

        self.load_label = QLabel("负载: 空闲")
        self.load_label.setStyleSheet("""
            color: #333333;
            font-size: 14px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        load_layout.addWidget(self.load_label, 1)

        self.load_percent = QLabel("0%")
        self.load_percent.setStyleSheet("""
            color: #666666;
            font-size: 12px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        load_layout.addWidget(self.load_percent)

        layout.addWidget(self.load_frame)

        # 资源指标
        metrics_label = QLabel("📊 资源指标")
        metrics_label.setStyleSheet("""
            color: #666666;
            font-size: 11px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(metrics_label)

        # 指标卡片网格
        metrics_container = QWidget()
        metrics_layout = QHBoxLayout(metrics_container)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(8)

        self.cpu_card = self._create_metric_card("CPU", "0%", "#E3F2FD")
        self.mem_card = self._create_metric_card("内存", "0%", "#FFF3E0")
        self.disk_card = self._create_metric_card("磁盘", "0 MB/s", "#E8F5E9")

        metrics_layout.addWidget(self.cpu_card, 1)
        metrics_layout.addWidget(self.mem_card, 1)
        metrics_layout.addWidget(self.disk_card, 1)

        layout.addWidget(metrics_container)

        # 实时图表区域
        chart_label = QLabel("📈 实时趋势")
        chart_label.setStyleSheet("""
            color: #666666;
            font-size: 11px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(chart_label)

        self.chart_area = QFrame()
        self.chart_area.setStyleSheet("""
            QFrame {
                background: #F8FAFC;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
            }
        """)
        chart_layout = QVBoxLayout(self.chart_area)
        chart_layout.setContentsMargins(8, 8, 8, 8)

        self.chart_label = QLabel("CPU 使用率趋势\n(最近 60 秒)")
        self.chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_label.setStyleSheet("""
            color: #999999;
            font-size: 11px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        chart_layout.addWidget(self.chart_label)

        # 简单进度条模拟图表
        self.cpu_bar = QFrame()
        self.cpu_bar.setFixedHeight(20)
        self.cpu_bar.setStyleSheet("""
            QFrame {
                background: #F0F0F0;
                border-radius: 4px;
            }
        """)
        self.cpu_bar_inner = QFrame(self.cpu_bar)
        self.cpu_bar_inner.setFixedSize(0, 16)
        self.cpu_bar_inner.move(2, 2)
        self.cpu_bar_inner.setStyleSheet("""
            QFrame {
                background: #10B981;
                border-radius: 4px;
            }
        """)
        chart_layout.addWidget(self.cpu_bar)

        layout.addWidget(self.chart_area, 1)

        # 控制按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.pause_btn = QPushButton("⏸️ 暂停")
        self.pause_btn.setFixedHeight(28)
        self.pause_btn.setCheckable(True)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                color: #666666;
                font-size: 11px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:checked {
                background: #FFF3E0;
                border-color: #FFD700;
                color: #E65100;
            }
        """)
        self.pause_btn.clicked.connect(self._toggle_monitoring)
        btn_layout.addWidget(self.pause_btn)

        self.refresh_btn = QPushButton("↻ 刷新")
        self.refresh_btn.setFixedHeight(28)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                color: #666666;
                font-size: 11px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #F5F5F5;
            }
        """)
        self.refresh_btn.clicked.connect(self._refresh_now)
        btn_layout.addWidget(self.refresh_btn)

        layout.addLayout(btn_layout)

    def _create_metric_card(self, label: str, value: str, color: str) -> QWidget:
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background: {color};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        value_label = QLabel(value)
        value_label.setObjectName("metric_value")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet("""
            color: #333333;
            font-size: 16px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(value_label)

        label_text = QLabel(label)
        label_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_text.setStyleSheet("""
            color: #666666;
            font-size: 10px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(label_text)

        card._value_label = value_label
        return card

    def _init_backend(self):
        """初始化后端"""
        try:
            from core.resource_monitor import ResourceMonitor, LoadLevel
            self._monitor = ResourceMonitor()
            self._load_level = LoadLevel
        except ImportError:
            self._monitor = None
            self._load_level = None

        self._monitoring = True
        self._history = []

    def _start_monitoring(self):
        """启动监控定时器"""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_metrics)
        self._timer.start(2000)  # 每2秒更新

    def _toggle_monitoring(self):
        """切换监控状态"""
        self._monitoring = not self._monitoring
        if self._monitoring:
            self._timer.start()
            self.pause_btn.setText("⏸️ 暂停")
        else:
            self._timer.stop()
            self.pause_btn.setText("▶️ 继续")

    def _refresh_now(self):
        """立即刷新"""
        self._update_metrics()

    def _update_metrics(self):
        """更新指标"""
        if not self._monitoring:
            return

        try:
            if self._monitor:
                snapshot = self._monitor.get_current_snapshot()
                cpu = snapshot.cpu_percent
                mem = snapshot.memory_percent
                disk = snapshot.disk_read_mbps + snapshot.disk_write_mbps
            else:
                # 模拟数据
                import random
                cpu = random.uniform(10, 50)
                mem = random.uniform(30, 60)
                disk = random.uniform(0, 20)

            # 更新负载等级
            if self._load_level:
                level = self._load_level.from_cpu(cpu)
            else:
                level = None

            load_colors = {
                "idle": "#10B981",
                "light": "#10B981",
                "moderate": "#FFD700",
                "heavy": "#FF9800",
                "critical": "#EF4444",
            }
            load_names = {
                "idle": "空闲",
                "light": "轻度",
                "moderate": "中度",
                "heavy": "重度",
                "critical": "危险",
            }

            if level:
                level_name = level.value if hasattr(level, 'value') else str(level)
                color = load_colors.get(level_name, "#999999")
                name = load_names.get(level_name, level_name)
            else:
                color = "#999999"
                name = "未知"

            self.load_dot.setStyleSheet(f"color: {color}; font-size: 16px;")
            self.load_label.setText(f"负载: {name}")
            self.load_percent.setText(f"{cpu:.0f}%")

            # 更新指标卡片
            if hasattr(self.cpu_card, '_value_label'):
                self.cpu_card._value_label.setText(f"{cpu:.0f}%")
            if hasattr(self.mem_card, '_value_label'):
                self.mem_card._value_label.setText(f"{mem:.0f}%")
            if hasattr(self.disk_card, '_value_label'):
                self.disk_card._value_label.setText(f"{disk:.0f} MB/s")

            # 更新图表
            self._history.append(cpu)
            if len(self._history) > 30:
                self._history.pop(0)

            bar_width = int(cpu / 100 * (self.cpu_bar.width() - 4))
            self.cpu_bar_inner.resize(max(bar_width, 4), 16)

        except Exception:
            pass

    def resizeEvent(self, event):
        """窗口大小改变时更新图表"""
        super().resizeEvent(event)
        if self._history:
            cpu = self._history[-1] if self._history else 0
            bar_width = int(cpu / 100 * (self.cpu_bar.width() - 4))
            self.cpu_bar_inner.resize(max(bar_width, 4), 16)


# ── 消息队列面板 ────────────────────────────────────────────────────────


class MessageQueuePanel(QWidget):
    """消息队列面板 - 任务队列管理"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queues = []
        self._setup_ui()
        self._init_backend()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标题
        header = QLabel("📨 消息队列")
        header.setStyleSheet("""
            color: #333333;
            font-size: 13px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(header)

        # 队列统计
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background: #F8FAFC;
                border: 1px solid #E8E8E8;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setSpacing(16)

        self.total_card = self._create_stat_card("📦", "总数", "0")
        self.pending_card = self._create_stat_card("⏳", "等待", "0")
        self.running_card = self._create_stat_card("⚡", "运行", "0")
        self.completed_card = self._create_stat_card("✅", "完成", "0")

        stats_layout.addWidget(self.total_card)
        stats_layout.addWidget(self.pending_card)
        stats_layout.addWidget(self.running_card)
        stats_layout.addWidget(self.completed_card)

        layout.addWidget(stats_frame)

        # 任务列表
        task_label = QLabel("📋 任务列表")
        task_label.setStyleSheet("""
            color: #666666;
            font-size: 11px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(task_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        self.task_list = QWidget()
        self.task_list_layout = QVBoxLayout(self.task_list)
        self.task_list_layout.setContentsMargins(0, 0, 0, 0)
        self.task_list_layout.setSpacing(6)

        scroll.setWidget(self.task_list)
        layout.addWidget(scroll, 1)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.add_btn = QPushButton("➕ 添加")
        self.add_btn.setFixedHeight(32)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        btn_layout.addWidget(self.add_btn)

        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.setFixedHeight(32)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                color: #666666;
                font-size: 12px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #FFF3E0;
                border-color: #FFB74D;
            }
        """)
        self.clear_btn.clicked.connect(self._clear_completed)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

    def _create_stat_card(self, icon: str, label: str, value: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        value_label = QLabel(value)
        value_label.setObjectName("queue_stat_value")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet("""
            color: #333333;
            font-size: 18px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(value_label)

        label_text = QLabel(label)
        label_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_text.setStyleSheet("""
            color: #999999;
            font-size: 10px;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        layout.addWidget(label_text)

        widget._value_label = value_label
        return widget

    def _init_backend(self):
        """初始化后端"""
        try:
            from core.task_queue import TaskQueue, TaskState
            self._task_queue = TaskQueue()
            self._task_state = TaskState
        except ImportError:
            self._task_queue = None
            self._task_state = None

        self._refresh_tasks()

    def _refresh_tasks(self):
        """刷新任务列表"""
        # 更新统计
        total = len(self._queues)
        pending = sum(1 for q in self._queues if q.get("state") == "pending")
        running = sum(1 for q in self._queues if q.get("state") == "running")
        completed = sum(1 for q in self._queues if q.get("state") == "completed")

        if hasattr(self.total_card, '_value_label'):
            self.total_card._value_label.setText(str(total))
        if hasattr(self.pending_card, '_value_label'):
            self.pending_card._value_label.setText(str(pending))
        if hasattr(self.running_card, '_value_label'):
            self.running_card._value_label.setText(str(running))
        if hasattr(self.completed_card, '_value_label'):
            self.completed_card._value_label.setText(str(completed))

        # 更新任务列表
        while self.task_list_layout.count():
            item = self.task_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for task in self._queues[:10]:  # 最多显示10个
            self._add_task_item(task)

        if not self._queues:
            empty = QLabel("暂无队列任务")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("""
                color: #999999;
                font-size: 12px;
                padding: 20px;
            """)
            self.task_list_layout.addWidget(empty)

    def _add_task_item(self, task: Dict[str, Any]):
        """添加任务项"""
        item = QWidget()
        state = task.get("state", "pending")
        state_colors = {
            "pending": "#FFD700",
            "running": "#10B981",
            "completed": "#CCCCCC",
            "failed": "#EF4444",
        }
        state_icons = {
            "pending": "⏳",
            "running": "⚡",
            "completed": "✅",
            "failed": "❌",
        }
        color = state_colors.get(state, "#999999")
        icon = state_icons.get(state, "❓")

        item.setStyleSheet("""
            QWidget {
                background: #FFFFFF;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        layout = QHBoxLayout(item)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 状态图标
        status_icon = QLabel(icon)
        status_icon.setStyleSheet(f"font-size: 18px; color: {color};")
        layout.addWidget(status_icon)

        # 信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        title = QLabel(task.get("title", "未命名任务"))
        title.setStyleSheet("""
            color: #333333;
            font-size: 12px;
            font-weight: bold;
            font-family: "Microsoft YaHei", sans-serif;
        """)
        info_layout.addWidget(title)

        if task.get("description"):
            desc = QLabel(task.get("description", ""))
            desc.setStyleSheet("""
                color: #666666;
                font-size: 10px;
                font-family: "Microsoft YaHei", sans-serif;
            """)
            info_layout.addWidget(desc)

        layout.addLayout(info_layout, 1)

        # 优先级
        priority = task.get("priority", "normal")
        priority_colors = {
            "low": "#999999",
            "normal": "#10B981",
            "high": "#FF9800",
            "urgent": "#EF4444",
        }
        priority_label = QLabel({
            "low": "⚪",
            "normal": "🟢",
            "high": "🟠",
            "urgent": "🔴",
        }.get(priority, "🟢"))
        priority_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(priority_label)

        self.task_list_layout.addWidget(item)

    def _clear_completed(self):
        """清空已完成任务"""
        self._queues = [q for q in self._queues if q.get("state") != "completed"]
        self._refresh_tasks()

    def add_task(self, title: str, description: str = "", priority: str = "normal"):
        """添加任务"""
        self._queues.insert(0, {
            "title": title,
            "description": description,
            "priority": priority,
            "state": "pending",
        })
        self._refresh_tasks()

    def update_task_state(self, task_id: str, state: str):
        """更新任务状态"""
        for task in self._queues:
            if task.get("id") == task_id:
                task["state"] = state
                break
        self._refresh_tasks()


# ── 导出 ──────────────────────────────────────────────────────────────────

__all__ = [
    "WorkspacePanel",
    "UserGuidePanel",
    "SystemFeaturesPanel",
    "SystemFeatureButton",
    "KnowledgeBaseInitPanel",
    "KnowledgeBaseViewPanel",
    "MemoryPalacePanel",
    "KnowledgeGraphPanel",
    "WorkflowPanel",
    "ChainOfThoughtPanel",
    "SkillLibraryPanel",
    "SystemStatsPanel",
    "DeploymentPanel",
    "PerformanceMonitorPanel",
    "MessageQueuePanel",
]
