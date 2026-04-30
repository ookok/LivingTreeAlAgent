"""
去中心化伪域名 - PyQt6 UI 面板 (生命之树版本)

功能:
- 域名管理 (注册/查看)
- DNS 解析测试
- Web 服务器状态
- 域名格式预览
- AI 智能命名
"""

import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QLineEdit, QTextEdit,
    QListWidget, QListWidgetItem, QFrame,
    QTabWidget, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QToolButton,
    QMenu, QDialog, QDialogButtonBox, QFormLayout,
    QComboBox, QCheckBox, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QAction, QIcon, QTextCursor


class DomainCard(QFrame):
    """域名卡片 (生命之树主题)"""

    def __init__(self, domain: str, domain_type: str, content_type: str,
                 suffix: str = "", parent=None):
        super().__init__(parent)
        self.domain = domain
        self.suffix = suffix
        self._setup_ui(domain_type, content_type)

    def _setup_ui(self, domain_type: str, content_type: str):
        self.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #C8E6C9;
                border-radius: 8px;
                padding: 12px;
            }
            QFrame:hover {
                border-color: #4CAF50;
                background: #F1F8E9;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 域名 (带 Emoji)
        domain_emoji = self._get_emoji_for_domain()
        domain_label = QLabel(f"{domain_emoji} {self.domain}")
        domain_label.setFont(QFont("", 11, QFont.Weight.Bold))
        domain_label.setStyleSheet("color: #1B5E20;")
        layout.addWidget(domain_label)

        # 类型标签
        type_layout = QHBoxLayout()
        type_layout.setSpacing(6)

        type_label = QLabel(f"类型: {domain_type}")
        type_label.setStyleSheet("color: #689F38; font-size: 11px;")
        type_layout.addWidget(type_label)

        type_layout.addStretch()

        # 后缀标签
        if self.suffix:
            suffix_label = QLabel(f"后缀: {self.suffix}")
            suffix_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
            type_layout.addWidget(suffix_label)

        content_label = QLabel(f"内容: {content_type}")
        content_label.setStyleSheet("color: #689F38; font-size: 11px;")
        type_layout.addWidget(content_label)

        layout.addLayout(type_layout)

    def _get_emoji_for_domain(self) -> str:
        """根据域名后缀获取 Emoji"""
        suffix_lower = self.suffix.lower() if self.suffix else ""
        if ".tree" in suffix_lower:
            return "🌳"
        elif ".leaf" in suffix_lower:
            return "🍃"
        elif ".root" in suffix_lower:
            return "🌱"
        elif ".wood" in suffix_lower:
            return "🌲"
        return "🌐"


class DNSResultWidget(QFrame):
    """DNS 解析结果组件 (生命之树主题)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: #F1F8E9;
                border: 1px solid #C8E6C9;
                border-radius: 6px;
                padding: 10px;
            }
        """)

        layout = QGridLayout(self)
        layout.setSpacing(8)

        # 状态
        self.status_label = QLabel("状态: --")
        self.status_label.setStyleSheet("font-weight: 500; color: #2E7D32;")
        layout.addWidget(self.status_label, 0, 0, 1, 2)

        # 节点 ID
        self.node_label = QLabel("节点ID: --")
        self.node_label.setStyleSheet("color: #558B2F;")
        layout.addWidget(self.node_label, 1, 0, 1, 2)

        # 地址
        self.address_label = QLabel("地址: --")
        self.address_label.setStyleSheet("color: #558B2F;")
        layout.addWidget(self.address_label, 2, 0, 1, 2)

        # 内容来源
        self.source_label = QLabel("来源: --")
        self.source_label.setStyleSheet("color: #689F38;")
        layout.addWidget(self.source_label, 3, 0, 1, 2)

        # 解析时间
        self.time_label = QLabel("耗时: --")
        self.time_label.setStyleSheet("color: #8BC34A; font-size: 11px;")
        layout.addWidget(self.time_label, 4, 0, 1, 2)

    def set_result(self, domain: str, status: str, node_id: str = "",
                   address: str = "", source: str = "", time_ms: float = 0):
        """设置解析结果"""
        status_colors = {
            "success": "#4CAF50",      # 绿色
            "not_found": "#E57373",    # 浅红
            "offline": "#FFB74D",      # 橙色 (落叶)
            "timeout": "#BA68C8",       # 紫色
            "invalid": "#90A4AE",       # 灰色
        }
        color = status_colors.get(status.lower(), "#7F8C8D")

        # 状态 Emoji
        status_emoji = {
            "success": "🌿",
            "not_found": "🔍",
            "offline": "🍂",
            "timeout": "⏱️",
            "invalid": "❌",
        }.get(status.lower(), "❓")

        self.status_label.setText(f"状态: <span style='color: {color}'>{status_emoji} {status.upper()}</span>")
        self.node_label.setText(f"节点ID: {node_id or 'N/A'}")
        self.address_label.setText(f"地址: {address or 'N/A'}")
        self.source_label.setText(f"来源: {source or 'N/A'}")
        self.time_label.setText(f"耗时: {time_ms:.2f} ms")


class DomainPanel(QWidget):
    """
    去中心化伪域名管理面板 (生命之树版本)

    功能:
    - 查看我的域名
    - DNS 解析测试
    - Web 服务器状态
    - 域名格式预览
    - AI 智能命名
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.domain_hub = None
        self._setup_ui()
        self._init_hub()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # 标题
        title_layout = QHBoxLayout()
        title = QLabel("🌳 生命之树伪域名系统")
        title.setFont(QFont("", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #1B5E20;")
        title_layout.addWidget(title)

        # 副标题
        subtitle = QLabel("根系相连，智慧生长")
        subtitle.setStyleSheet("color: #689F38; font-size: 12px;")
        title_layout.addWidget(subtitle)
        title_layout.addStretch()

        layout.addLayout(title_layout)

        # 标签页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #C8E6C9;
                border-radius: 8px;
                padding: 10px;
                background: white;
            }
            QTabBar::tab {
                padding: 8px 16px;
                margin-right: 5px;
                border-radius: 6px;
                color: #558B2F;
            }
            QTabBar::tab:selected {
                background: #4CAF50;
                color: white;
            }
        """)

        # 1. 我的域名
        tabs.addTab(self._create_my_domains_tab(), "🌿 我的域名")
        # 2. DNS 测试
        tabs.addTab(self._create_dns_test_tab(), "🔍 DNS 测试")
        # 3. 服务器状态
        tabs.addTab(self._create_server_tab(), "🌱 服务器状态")
        # 4. 域名格式
        tabs.addTab(self._create_format_tab(), "📝 域名格式")
        # 5. AI 命名
        tabs.addTab(self._create_ai_naming_tab(), "🤖 AI 命名")

        layout.addWidget(tabs)

        # 状态栏
        self.status_label = QLabel("🌳 生命之树 | 初始化中...")
        self.status_label.setStyleSheet("""
            background: #F1F8E9;
            border-top: 1px solid #C8E6C9;
            padding: 8px 15px;
            color: #689F38;
            font-size: 12px;
        """)
        layout.addWidget(self.status_label)

    def _create_my_domains_tab(self) -> QWidget:
        """创建我的域名标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 说明
        info_label = QLabel("您拥有的伪域名, 可用于访问您的博客、论坛、邮箱等服务")
        info_label.setStyleSheet("color: #7F8C8D; font-size: 12px; padding: 5px 0;")
        layout.addWidget(info_label)

        # 域名列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        self.domains_container = QWidget()
        self.domains_layout = QVBoxLayout(self.domains_container)
        self.domains_layout.setSpacing(10)
        self.domains_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.domains_container)
        layout.addWidget(scroll)

        # 添加按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #F8F9FA;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #E8F4FD;
                border-color: #4A90D9;
            }
        """)
        refresh_btn.clicked.connect(self._refresh_domains)
        btn_layout.addWidget(refresh_btn)

        layout.addLayout(btn_layout)

        return widget

    def _create_dns_test_tab(self) -> QWidget:
        """创建 DNS 测试标签页 (生命之树版本)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 输入
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

        self.dns_input = QLineEdit()
        self.dns_input.setPlaceholderText("输入伪域名, 如: blog.8848993321.tree")
        self.dns_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #C8E6C9;
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
        """)
        self.dns_input.returnPressed.connect(self._test_dns)
        input_layout.addWidget(self.dns_input)

        test_btn = QPushButton("🔍 解析")
        test_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #388E3C;
            }
        """)
        test_btn.clicked.connect(self._test_dns)
        input_layout.addWidget(test_btn)

        layout.addLayout(input_layout)

        # 预设域名
        preset_label = QLabel("预设测试 (.tree 家族):")
        preset_label.setStyleSheet("color: #689F38; font-size: 11px;")
        layout.addWidget(preset_label)

        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(8)

        # 生命之树预设域名
        presets = [
            ("🌳", "blog.8848993321.tree"),
            ("🌲", "forum.8855.wood"),
            ("🍃", "@8848993321.leaf"),
            ("🌱", "registry.living.root"),
        ]

        for emoji, preset in presets:
            btn = QPushButton(f"{emoji} {preset}")
            btn.setStyleSheet("""
                QPushButton {
                    background: #E8F5E9;
                    color: #4CAF50;
                    border: 1px solid #C8E6C9;
                    border-radius: 4px;
                    padding: 5px 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #C8E6C9;
                }
            """)
            btn.clicked.connect(lambda checked, p=preset: self.dns_input.setText(p))
            preset_layout.addWidget(btn)

        preset_layout.addStretch()
        layout.addLayout(preset_layout)

        # 结果
        result_label = QLabel("解析结果:")
        result_label.setStyleSheet("font-weight: 500; color: #2E7D32;")
        layout.addWidget(result_label)

        self.dns_result = DNSResultWidget()
        layout.addWidget(self.dns_result)

        layout.addStretch()

        return widget

    def _create_server_tab(self) -> QWidget:
        """创建服务器状态标签页 (生命之树版本)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Web 服务器状态
        server_group = QGroupBox("🌱 Web 服务器")
        server_group.setStyleSheet("""
            QGroupBox {
                font-weight: 500;
                border: 1px solid #C8E6C9;
                border-radius: 8px;
                padding: 15px;
                margin-top: 10px;
                color: #2E7D32;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        server_layout = QGridLayout(server_group)
        server_layout.setSpacing(10)

        self.server_status_label = QLabel("状态: 运行中")
        self.server_status_label.setStyleSheet("font-weight: 500; color: #4CAF50;")
        server_layout.addWidget(self.server_status_label, 0, 0, 1, 2)

        server_layout.addWidget(QLabel("监听地址:"), 1, 0)
        self.server_address_label = QLabel("127.0.0.1:8080")
        self.server_address_label.setStyleSheet("color: #558B2F;")
        server_layout.addWidget(self.server_address_label, 1, 1)

        server_layout.addWidget(QLabel("访问 URL:"), 2, 0)
        self.server_url_label = QLabel("http://127.0.0.1:8080")
        self.server_url_label.setStyleSheet("color: #4CAF50;")
        server_layout.addWidget(self.server_url_label, 2, 1)

        layout.addWidget(server_group)

        # 统计
        stats_group = QGroupBox("📊 统计信息")
        stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: 500;
                border: 1px solid #C8E6C9;
                border-radius: 8px;
                padding: 15px;
                margin-top: 10px;
                color: #2E7D32;
            }
        """)

        stats_layout = QGridLayout(stats_group)
        stats_layout.setSpacing(10)

        stats_layout.addWidget(QLabel("🌳 总请求数:"), 0, 0)
        self.total_requests_label = QLabel("0")
        self.total_requests_label.setStyleSheet("color: #558B2F;")
        stats_layout.addWidget(self.total_requests_label, 0, 1)

        stats_layout.addWidget(QLabel("🍃 本地服务:"), 1, 0)
        self.local_served_label = QLabel("0")
        self.local_served_label.setStyleSheet("color: #558B2F;")
        stats_layout.addWidget(self.local_served_label, 1, 1)

        stats_layout.addWidget(QLabel("🌲 远程请求:"), 2, 0)
        self.remote_requests_label = QLabel("0")
        self.remote_requests_label.setStyleSheet("color: #558B2F;")
        stats_layout.addWidget(self.remote_requests_label, 2, 1)

        layout.addWidget(stats_group)

        # 按钮
        btn_layout = QHBoxLayout()

        start_btn = QPushButton("▶️ 启动服务")
        start_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background: #388E3C;
            }
        """)
        start_btn.clicked.connect(self._start_server)
        btn_layout.addWidget(start_btn)

        stop_btn = QPushButton("⏹️ 停止服务")
        stop_btn.setStyleSheet("""
            QPushButton {
                background: #E57373;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background: #D32F2F;
            }
        """)
        stop_btn.clicked.connect(self._stop_server)
        btn_layout.addWidget(stop_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

        return widget

    def _create_format_tab(self) -> QWidget:
        """创建域名格式标签页 (生命之树版本)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 说明
        info = QLabel("🌳 生命之树伪域名格式说明:")
        info.setStyleSheet("font-weight: 500; color: #2E7D32;")
        layout.addWidget(info)

        # 顶级域名说明
        tld_info = QLabel("顶级域名 (.tree 家族):")
        tld_info.setStyleSheet("font-weight: 500; color: #558B2F; margin-top: 5px;")
        layout.addWidget(tld_info)

        tld_layout = QHBoxLayout()
        tld_layout.setSpacing(10)

        tld_data = [
            ("🌳 .tree", "主命名空间，个人主页/商店"),
            ("🍃 .leaf", "轻量服务，邮箱/便签"),
            ("🌱 .root", "核心系统，路由/注册表"),
            ("🌲 .wood", "社区，论坛/协作空间"),
        ]
        for tld_emoji, tld_desc in tld_data:
            tld_label = QLabel(f"{tld_emoji} {tld_desc}")
            tld_label.setStyleSheet("background: #E8F5E9; padding: 5px 10px; border-radius: 4px; color: #4CAF50; font-size: 11px;")
            tld_layout.addWidget(tld_label)
        tld_layout.addStretch()

        layout.addLayout(tld_layout)

        # 格式卡片
        formats = [
            ("🌳 个人域", "{name}.{node-id}.tree", "shop.8848993321.tree", "个人主页或商店"),
            ("📝 博客", "blog.{node-id}.tree", "blog.8848993321.tree", "个人博客文章"),
            ("🌲 论坛", "forum.{node-id}.wood", "forum.8855.wood", "去中心化社区"),
            ("🍃 邮箱", "@{node-id}.leaf", "@8848993321.leaf", "分布式邮箱服务"),
            ("📌 便签", "note.{node-id}.leaf", "note.8848993321.leaf", "轻量便签服务"),
            ("🌱 系统", "{service}.living.root", "registry.living.root", "核心系统服务"),
            ("🌰 话题", "topic.seed{hash}.tree", "topic.seed12345.tree", "话题频道"),
        ]

        for icon, format_str, example, desc in formats:
            card = self._create_format_card(icon, format_str, example, desc)
            layout.addWidget(card)

        layout.addStretch()

        return widget

    def _create_format_card(self, icon: str, format_str: str,
                           example: str, desc: str) -> QFrame:
        """创建格式卡片 (生命之树主题)"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #F1F8E9;
                border: 1px solid #C8E6C9;
                border-radius: 6px;
                padding: 12px;
            }
        """)

        layout = QGridLayout(card)
        layout.setSpacing(8)

        # 图标和名称
        name_label = QLabel(f"{icon} {format_str}")
        name_label.setFont(QFont("", 10, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #2E7D32;")
        layout.addWidget(name_label, 0, 0, 1, 2)

        # 示例
        example_label = QLabel(f"示例: {example}")
        example_label.setStyleSheet("color: #4CAF50; font-size: 12px;")
        layout.addWidget(example_label, 1, 0, 1, 2)

        # 描述
        desc_label = QLabel(desc)
        desc_label.setStyleSheet("color: #689F38; font-size: 11px;")
        layout.addWidget(desc_label, 2, 0, 1, 2)

        return card

    def _create_ai_naming_tab(self) -> QWidget:
        """创建 AI 命名标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 说明
        info = QLabel("🤖 AI 智能域名生成")
        info.setStyleSheet("font-weight: 500; color: #2E7D32; font-size: 13px;")
        layout.addWidget(info)

        info2 = QLabel("输入您的业务或想法, AI 将为您生成富有诗意的域名")
        info2.setStyleSheet("color: #689F38; font-size: 12px;")
        layout.addWidget(info2)

        # 输入
        input_layout = QVBoxLayout()
        input_layout.setSpacing(8)

        name_label = QLabel("您的业务/想法:")
        name_label.setStyleSheet("color: #558B2F; font-weight: 500;")
        input_layout.addWidget(name_label)

        self.ai_name_input = QLineEdit()
        self.ai_name_input.setPlaceholderText("例如: 在线书店、AI编程助手、程序员社区")
        self.ai_name_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #C8E6C9;
                border-radius: 6px;
                padding: 10px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
        """)
        input_layout.addWidget(self.ai_name_input)

        layout.addLayout(input_layout)

        # 生成按钮
        generate_btn = QPushButton("🌿 AI 生成域名建议")
        generate_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #388E3C;
            }
        """)
        generate_btn.clicked.connect(self._generate_ai_names)
        layout.addWidget(generate_btn)

        # 结果
        result_label = QLabel("生成结果:")
        result_label.setStyleSheet("font-weight: 500; color: #2E7D32; margin-top: 10px;")
        layout.addWidget(result_label)

        self.ai_result_list = QVBoxLayout()
        self.ai_result_list.setSpacing(8)
        layout.addLayout(self.ai_result_list)

        # 预设场景
        preset_label = QLabel("快速体验:")
        preset_label.setStyleSheet("color: #689F38; font-size: 11px; margin-top: 15px;")
        layout.addWidget(preset_label)

        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(8)

        presets = [
            ("📚 书店", "在线书店"),
            ("💻 编程", "AI编程助手"),
            ("🎮 游戏", "游戏社区"),
            ("✍️ 写作", "创意写作平台"),
        ]

        for emoji, text in presets:
            btn = QPushButton(f"{emoji} {text}")
            btn.setStyleSheet("""
                QPushButton {
                    background: #E8F5E9;
                    color: #4CAF50;
                    border: 1px solid #C8E6C9;
                    border-radius: 4px;
                    padding: 5px 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #C8E6C9;
                }
            """)
            btn.clicked.connect(lambda checked, t=text: self.ai_name_input.setText(t))
            preset_layout.addWidget(btn)

        preset_layout.addStretch()
        layout.addLayout(preset_layout)

        layout.addStretch()

        return widget

    def _generate_ai_names(self):
        """生成 AI 域名建议"""
        idea = self.ai_name_input.text().strip()
        if not idea:
            return

        # 清除现有结果
        while self.ai_result_list.count():
            child = self.ai_result_list.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 预设的域名建议 (基于关键词生成)
        suggestions = self._generate_suggestions(idea)

        for suggestion in suggestions:
            card = self._create_suggestion_card(suggestion)
            self.ai_result_list.addWidget(card)

    def _generate_suggestions(self, idea: str) -> list:
        """根据想法生成域名建议"""
        import hashlib

        # 基于输入生成一致的建议
        idea_hash = int(hashlib.md5(idea.encode()).hexdigest()[:8], 16)

        # 智能关键词映射
        keywords_map = {
            "书店": [("📚", "book", "bookstore"), ("📖", "read", "reading")],
            "编程": [("💻", "code", "coding"), ("🤖", "ai", "ai-coding")],
            "游戏": [("🎮", "game", "gaming"), ("🎯", "play", "playground")],
            "写作": [("✍️", "write", "writing"), ("📝", "note", "notes")],
            "AI": [("🤖", "ai", "smart"), ("🧠", "mind", "brain")],
            "社区": [("🌲", "forum", "community"), ("🏘️", "talk", "talks")],
            "在线": [("🌐", "online", "net"), ("☁️", "cloud", "cloudy")],
        }

        # 匹配关键词
        matched = []
        for key, values in keywords_map.items():
            if key in idea:
                matched.extend(values)

        if not matched:
            matched = [(idea[:2], idea.lower().replace(" ", ""), idea.lower().replace(" ", ""))]

        suggestions = []
        node_id = "8848993321"  # 默认节点 ID

        for i, (emoji, eng, cn) in enumerate(matched[:3]):
            suggestions.append({
                "emoji": emoji,
                "domain": f"{eng}.{node_id[:4]}.tree",
                "description": f"{emoji} {cn.title()} - {eng}.{node_id[:4]}.tree",
                "suffix": ".tree"
            })

        # 添加 .leaf 和 .wood 选项
        if len(suggestions) >= 1:
            suggestions.append({
                "emoji": "🍃",
                "domain": f"note.{node_id[:4]}.leaf",
                "description": f"🍃 便签服务 - note.{node_id[:4]}.leaf",
                "suffix": ".leaf"
            })

        if len(suggestions) >= 2:
            suggestions.append({
                "emoji": "🌲",
                "domain": f"talk.{node_id[:4]}.wood",
                "description": f"🌲 社区论坛 - talk.{node_id[:4]}.wood",
                "suffix": ".wood"
            })

        return suggestions

    def _create_suggestion_card(self, suggestion: dict) -> QFrame:
        """创建建议卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #F1F8E9;
                border: 1px solid #C8E6C9;
                border-radius: 6px;
                padding: 12px;
            }
        """)

        layout = QHBoxLayout(card)
        layout.setSpacing(12)

        # Emoji
        emoji_label = QLabel(suggestion["emoji"])
        emoji_label.setFont(QFont("", 20))
        layout.addWidget(emoji_label)

        # 域名和描述
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        domain_label = QLabel(suggestion["domain"])
        domain_label.setFont(QFont("", 11, QFont.Weight.Bold))
        domain_label.setStyleSheet("color: #2E7D32;")
        text_layout.addWidget(domain_label)

        desc_label = QLabel(suggestion["description"])
        desc_label.setStyleSheet("color: #689F38; font-size: 11px;")
        text_layout.addWidget(desc_label)

        layout.addLayout(text_layout)
        layout.addStretch()

        # 使用按钮
        use_btn = QPushButton("使用")
        use_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #388E3C;
            }
        """)
        use_btn.clicked.connect(lambda: self._use_suggestion(suggestion))
        layout.addWidget(use_btn)

        return card

    def _use_suggestion(self, suggestion: dict):
        """使用建议的域名"""
        self.dns_input.setText(suggestion["domain"])
        self.status_label.setText(f"🌳 已选择域名: {suggestion['domain']}")

    async def _init_hub(self):
        """初始化中枢"""
        try:
            from .business.pseudodomain import get_pseudodomain_hub_async
            self.domain_hub = await get_pseudodomain_hub_async()

            # 注册回调
            self.domain_hub.add_ui_callback("domain_resolved", self._on_domain_resolved)

            # 刷新域名
            self._refresh_domains()

            # 更新状态
            self.status_label.setText("🌳 生命之树 | 已就绪")
            self._update_stats()

        except Exception as e:
            self.status_label.setText(f"🌳 生命之树 | 初始化失败: {e}")

    @pyqtSlot()
    def _refresh_domains(self):
        """刷新域名列表"""
        if not self.domain_hub:
            return

        # 清空现有
        while self.domains_layout.count():
            child = self.domains_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 添加域名
        domains = self.domain_hub.get_my_domains()
        for domain_reg in domains:
            suffix = domain_reg.tree_suffix.value if hasattr(domain_reg, 'tree_suffix') and domain_reg.tree_suffix else ""
            card = DomainCard(
                domain=domain_reg.domain,
                domain_type=domain_reg.domain_type.value,
                content_type=domain_reg.content_type,
                suffix=suffix
            )
            self.domains_layout.addWidget(card)

        if not domains:
            empty_label = QLabel("暂无域名, 请先配置节点 ID")
            empty_label.setStyleSheet("color: #689F38; padding: 20px; text-align: center;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.domains_layout.addWidget(empty_label)

    @pyqtSlot()
    def _test_dns(self):
        """测试 DNS 解析"""
        domain = self.dns_input.text().strip()
        if not domain:
            return

        if not self.domain_hub:
            self.dns_result.set_result(domain, "error", time_ms=0)
            return

        # 异步解析
        asyncio.create_task(self._async_test_dns(domain))

    async def _async_test_dns(self, domain: str):
        """异步 DNS 测试"""
        result = await self.domain_hub.resolve(domain)

        # 更新 UI
        self.dns_result.set_result(
            domain=result.original_domain,
            status=result.status.value,
            node_id=result.node_id or "",
            address=result.node_address or "",
            source=result.content_source.value if result.content_source else "",
            time_ms=result.resolution_time
        )

    @pyqtSlot(str, object)
    def _on_domain_resolved(self, domain: str, resolution):
        """域名解析完成回调"""
        pass

    @pyqtSlot()
    def _start_server(self):
        """启动服务器"""
        if self.domain_hub:
            asyncio.create_task(self.domain_hub.web_server.start())
            self.server_status_label.setText("状态: <span style='color: #4CAF50;'>🌿 运行中</span>")
            self.status_label.setText("🌳 Web 服务器已启动")

    @pyqtSlot()
    def _stop_server(self):
        """停止服务器"""
        if self.domain_hub:
            asyncio.create_task(self.domain_hub.web_server.stop())
            self.server_status_label.setText("状态: <span style='color: #E57373;'>🍂 已停止</span>")
            self.status_label.setText("🌳 Web 服务器已停止")

    def _update_stats(self):
        """更新统计"""
        if not self.domain_hub:
            return

        stats = self.domain_hub.get_stats()
        self.total_requests_label.setText(str(stats.get("total_requests", 0)))
        self.local_served_label.setText(str(stats.get("local_served", 0)))
        self.remote_requests_label.setText(str(stats.get("remote_requests", 0)))
        self.server_address_label.setText(f"127.0.0.1:{self.domain_hub.config.web_server_port}")
        self.server_url_label.setText(self.domain_hub.get_web_server_url())
