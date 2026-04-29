# -*- coding: utf-8 -*-
"""
🏘️ 通用资产交易生态 UI 面板
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QGroupBox, QLineEdit, QTextEdit, QComboBox,
                             QSpinBox, QDoubleSpinBox, QCheckBox, QListWidget,
                             QStackedWidget, QFormLayout, QScrollArea,
                             QProgressBar, QBadge, QFrame)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor


class UniversalAssetPanel(QWidget):
    """通用资产交易生态面板"""

    TAB_LABELS = [
        ("🏠", "资产市场"),
        ("🚚", "交付路由"),
        ("💎", "信任网络"),
        ("💰", "积分金融"),
        ("🎁", "红包赠送"),
        ("🤝", "DAO治理"),
        ("🌱", "社会生态"),
        ("🌐", "跨社会桥")
    ]

    def __init__(self, ecosystem=None, parent=None):
        super().__init__(parent)
        self.ecosystem = ecosystem
        self.current_user = "user_default"
        self.init_ui()

        # 模拟数据刷新
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(30000)  # 每30秒刷新

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题栏
        header = self._create_header()
        layout.addWidget(header)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # 添加各标签页
        self.tab_market = self._create_market_tab()
        self.tab_delivery = self._create_delivery_tab()
        self.tab_trust = self._create_trust_tab()
        self.tab_credit = self._create_credit_tab()
        self.tab_gift = self._create_gift_tab()
        self.tab_dao = self._create_dao_tab()
        self.tab_society = self._create_society_tab()
        self.tab_bridge = self._create_bridge_tab()

        tabs = [self.tab_market, self.tab_delivery, self.tab_trust,
                self.tab_credit, self.tab_gift, self.tab_dao,
                self.tab_society, self.tab_bridge]

        for i, (emoji, title) in enumerate(self.TAB_LABELS):
            self.tabs.addTab(tabs[i], f"{emoji} {title}")

        layout.addWidget(self.tabs)

    def _create_header(self) -> QWidget:
        """创建标题栏"""
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        layout = QHBoxLayout(header)

        title = QLabel("🏘️ 通用资产交易生态")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        layout.addStretch()

        # 状态指示
        status = QLabel("● 系统正常")
        status.setStyleSheet("color: #4ade80; font-size: 14px;")
        layout.addWidget(status)

        return header

    def _create_market_tab(self) -> QWidget:
        """资产市场标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 筛选栏
        filter_bar = QHBoxLayout()

        filter_bar.addWidget(QLabel("资产类型:"))
        type_combo = QComboBox()
        type_combo.addItems(["全部", "数字资产", "实物商品", "专业服务", "房地产", "知识库"])
        filter_bar.addWidget(type_combo)

        filter_bar.addWidget(QLabel("排序:"))
        sort_combo = QComboBox()
        sort_combo.addItems(["综合推荐", "最新发布", "价格低→高", "价格高→低", "销量最高"])
        filter_bar.addWidget(sort_combo)

        search = QLineEdit()
        search.setPlaceholderText("搜索资产...")
        search.setMinimumWidth(200)
        filter_bar.addWidget(search)

        filter_bar.addStretch()

        layout.addLayout(filter_bar)

        # 资产列表
        self.asset_table = QTableWidget()
        self.asset_table.setColumnCount(6)
        self.asset_table.setHorizontalHeaderLabels([
            "资产名称", "类型", "卖家", "价格", "销量", "操作"
        ])
        self.asset_table.setRowCount(5)

        # 填充模拟数据
        sample_assets = [
            ["Qwen2.5-7B模型", "数字资产", "AI工作室", "5000", "128", "购买"],
            ["Python进阶教程", "知识库", "编程达人", "299", "562", "购买"],
            ["室内设计服务", "专业服务", "设计团队", "2000", "45", "购买"],
            ["二手MacBook Pro", "实物商品", "科技宅", "8500", "12", "购买"],
            ["朝阳区学区房", "房地产", "房产经纪", "面议", "3", "咨询"]
        ]

        for row, asset in enumerate(sample_assets):
            for col, value in enumerate(asset):
                item = QTableWidgetItem(value)
                if col == 5:
                    item.setForeground(QColor("#667eea"))
                self.asset_table.setItem(row, col, item)

        self.asset_table.cellClicked.connect(self.on_asset_clicked)
        layout.addWidget(self.asset_table)

        # 创建资产按钮
        create_btn = QPushButton("➕ 发布新资产")
        create_btn.setStyleSheet("""
            QPushButton {
                background: #667eea;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #5a6fd6;
            }
        """)
        create_btn.clicked.connect(self.on_create_asset)
        layout.addWidget(create_btn)

        return widget

    def _create_delivery_tab(self) -> QWidget:
        """交付路由标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 交付方式说明
        info = QLabel("""
        📦 资产交付智能路由器

        系统支持5种交付方式，自动匹配最佳路径：

        🟢 数字直接交付 - 模型、脚本等工作流，即时到达
        🔵 数字许可交付 - 许可证密钥，1小时内交付
        🟠 物理物流交付 - 实物商品，7天内送达
        🟡 服务预约交付 - 专业服务，30天内安排
        🟣 知识转移交付 - 知识库自动集成，24小时完成
        """)
        info.setStyleSheet("""
            QLabel {
                background: #f8fafc;
                padding: 15px;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
            }
        """)
        layout.addWidget(info)

        # 当前交付任务
        group = QGroupBox("📋 当前交付任务")
        group_layout = QVBoxLayout()

        self.delivery_table = QTableWidget()
        self.delivery_table.setColumnCount(5)
        self.delivery_table.setHorizontalHeaderLabels([
            "任务ID", "资产", "方式", "状态", "进度"
        ])
        self.delivery_table.setRowCount(3)

        for row in range(3):
            items = [
                f"task_{row:04d}", "Qwen模型", "数字直接",
                ["待处理", "配送中", "已完成"][row % 3], ""
            ]
            for col, value in enumerate(items):
                self.delivery_table.setItem(row, col, QTableWidgetItem(value))

            # 进度条
            progress = QProgressBar()
            progress.setValue([30, 65, 100][row % 3])
            self.delivery_table.setCellWidget(row, 4, progress)

        group_layout.addWidget(self.delivery_table)
        group.setLayout(group_layout)
        layout.addWidget(group)

        return widget

    def _create_trust_tab(self) -> QWidget:
        """信任网络标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 用户信任分
        trust_card = QWidget()
        trust_card.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #11998e, stop:1 #38ef7d);
                border-radius: 12px;
                padding: 20px;
            }
        """)
        trust_layout = QHBoxLayout(trust_card)

        trust_layout.addWidget(QLabel("🏆"))
        trust_title = QLabel("您的信任等级")
        trust_title.setStyleSheet("color: white; font-size: 16px;")
        trust_layout.addWidget(trust_title)

        trust_layout.addStretch()

        trust_level = QLabel("💎 钻石级")
        trust_level.setStyleSheet("color: white; font-size: 28px; font-weight: bold;")
        trust_layout.addWidget(trust_level)

        trust_score = QLabel("综合分: 92.5")
        trust_score.setStyleSheet("color: rgba(255,255,255,0.9);")
        trust_layout.addWidget(trust_score)

        layout.addWidget(trust_card)

        # 信任分详情
        group = QGroupBox("📊 信任分详情")
        group_layout = QFormLayout()

        scores = [
            ("交易信任", "90"),
            ("社交信任", "95"),
            ("资产质量", "88"),
            ("响应速度", "92"),
            ("争议解决", "98")
        ]

        for label, value in scores:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            bar = QProgressBar()
            bar.setValue(int(value))
            bar.setTextVisible(True)
            row.addWidget(bar)
            group_layout.addRow(row)

        group.setLayout(group_layout)
        layout.addWidget(group)

        # 徽章
        badges_group = QGroupBox("🎖️ 获得的徽章")
        badges_layout = QHBoxLayout()

        badges = ["交易达人", "社交之星", "品质保证", "知识导师", "DAO守护者"]
        for badge in badges:
            badge_label = QLabel(f"🏅 {badge}")
            badge_label.setStyleSheet("""
                QLabel {
                    background: #fef3c7;
                    padding: 8px 12px;
                    border-radius: 20px;
                    color: #92400e;
                }
            """)
            badges_layout.addWidget(badge_label)

        badges_layout.addStretch()
        badges_group.setLayout(badges_layout)
        layout.addWidget(badges_group)

        return widget

    def _create_credit_tab(self) -> QWidget:
        """积分金融标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 积分余额
        balance_card = QWidget()
        balance_card.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f093fb, stop:1 #f5576c);
                border-radius: 12px;
                padding: 20px;
            }
        """)
        balance_layout = QHBoxLayout(balance_card)

        balance_layout.addWidget(QLabel("💰"))
        balance_title = QLabel("积分余额")
        balance_title.setStyleSheet("color: white; font-size: 16px;")
        balance_layout.addWidget(balance_title)

        balance_layout.addStretch()

        balance_value = QLabel("12,888")
        balance_value.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")
        balance_layout.addWidget(balance_value)

        layout.addWidget(balance_card)

        # 积分操作
        operations = QGroupBox("⚡ 积分操作")
        operations_layout = QHBoxLayout()

        operations_layout.addWidget(QPushButton("💸 借贷"))
        operations_layout.addWidget(QPushButton("📤 转账"))
        operations_layout.addWidget(QPushButton("📥 收款"))
        operations_layout.addWidget(QPushButton("📜 历史"))

        operations.setLayout(operations_layout)
        layout.addWidget(operations)

        # 贷款合约
        loan_group = QGroupBox("📄 贷款合约")
        loan_layout = QVBoxLayout()

        self.loan_table = QTableWidget()
        self.loan_table.setColumnCount(5)
        self.loan_table.setHorizontalHeaderLabels([
            "合约ID", "金额", "利率", "状态", "到期日"
        ])
        self.loan_table.setRowCount(2)

        for row in range(2):
            items = [
                f"loan_{row:04d}", "5000", "5%", "正常", "2026-05-18"
            ]
            for col, value in enumerate(items):
                self.loan_table.setItem(row, col, QTableWidgetItem(value))

        loan_layout.addWidget(self.loan_table)
        loan_group.setLayout(loan_layout)
        layout.addWidget(loan_group)

        return widget

    def _create_gift_tab(self) -> QWidget:
        """红包赠送标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 发送红包
        gift_form = QGroupBox("🎁 发送积分红包")
        form_layout = QFormLayout()

        amount = QSpinBox()
        amount.setRange(100, 1000000)
        amount.setValue(1000)
        amount.setSuffix(" 积分")
        form_layout.addRow("红包金额:", amount)

        count = QSpinBox()
        count.setRange(1, 100)
        count.setValue(10)
        form_layout.addRow("红包个数:", count)

        message = QLineEdit()
        message.setPlaceholderText("祝福语（可选）")
        form_layout.addRow("祝福语:", message)

        send_btn = QPushButton("🎉 发送红包")
        send_btn.setStyleSheet("""
            QPushButton {
                background: #f59e0b;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #d97706;
            }
        """)
        form_layout.addRow("", send_btn)

        gift_form.setLayout(form_layout)
        layout.addWidget(gift_form)

        # 红包记录
        history_group = QGroupBox("📋 最近红包")
        history_layout = QVBoxLayout()

        history_table = QTableWidget()
        history_table.setColumnCount(4)
        history_table.setHorizontalHeaderLabels(["时间", "金额", "个数", "状态"])
        history_table.setRowCount(3)

        for row in range(3):
            items = [
                "2026-04-18 15:30", "500", "10", "已领完"
            ]
            for col, value in enumerate(items):
                history_table.setItem(row, col, QTableWidgetItem(value))

        history_layout.addWidget(history_table)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        return widget

    def _create_dao_tab(self) -> QWidget:
        """DAO治理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 社区资金池
        pool_card = QWidget()
        pool_card.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #4facfe, stop:1 #00f2fe);
                border-radius: 12px;
                padding: 20px;
            }
        """)
        pool_layout = QHBoxLayout(pool_card)

        pool_layout.addWidget(QLabel("🏛️"))
        pool_title = QLabel("AI创作者社区资金池")
        pool_title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        pool_layout.addWidget(pool_title)

        pool_layout.addStretch()

        treasury = QLabel("国库: 128,888 积分")
        treasury.setStyleSheet("color: white; font-size: 16px;")
        pool_layout.addWidget(treasury)

        layout.addWidget(pool_card)

        # 提案列表
        proposal_group = QGroupBox("📝 活跃提案")
        proposal_layout = QVBoxLayout()

        proposals = [
            {"title": "增加知识分享奖励预算", "progress": 75, "votes": "800/1000"},
            {"title": "新成员入会门槛调整", "progress": 45, "votes": "450/1000"},
            {"title": "社区徽章系统升级", "progress": 20, "votes": "200/1000"}
        ]

        for prop in proposals:
            prop_widget = QWidget()
            prop_widget.setStyleSheet("""
                QWidget {
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
            prop_layout = QHBoxLayout(prop_widget)

            prop_layout.addWidget(QLabel(prop["title"]))

            progress = QProgressBar()
            progress.setValue(prop["progress"])
            prop_layout.addWidget(progress)

            prop_layout.addWidget(QLabel(f"{prop['votes']}"))

            vote_btn = QPushButton("投票")
            vote_btn.setFixedWidth(60)
            prop_layout.addWidget(vote_btn)

            proposal_layout.addWidget(prop_widget)

        proposal_group.setLayout(proposal_layout)
        layout.addWidget(proposal_group)

        # 创建提案按钮
        create_prop_btn = QPushButton("📝 创建新提案")
        create_prop_btn.setStyleSheet("""
            QPushButton {
                background: #4facfe;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }
        """)
        layout.addWidget(create_prop_btn)

        return widget

    def _create_society_tab(self) -> QWidget:
        """社会生态标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 社会健康度
        health_card = QWidget()
        health_card.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #a18cd1, stop:1 #fbc2eb);
                border-radius: 12px;
                padding: 20px;
            }
        """)
        health_layout = QHBoxLayout(health_card)

        health_layout.addWidget(QLabel("🌱"))
        health_title = QLabel("社区健康度")
        health_title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        health_layout.addWidget(health_title)

        health_layout.addStretch()

        health_score = QLabel("85.5")
        health_score.setStyleSheet("color: white; font-size: 36px; font-weight: bold;")
        health_layout.addWidget(health_score)

        health_level = QLabel("优秀")
        health_level.setStyleSheet("color: rgba(255,255,255,0.9);")
        health_layout.addWidget(health_level)

        health_layout.addWidget(QLabel("阶段: 成熟期 →"))

        layout.addWidget(health_card)

        # 健康度指标
        metrics_group = QGroupBox("📊 健康度指标")
        metrics_layout = QFormLayout()

        metrics = [
            ("经济健康", 78),
            ("社会健康", 85),
            ("治理健康", 82),
            ("创新健康", 75),
            ("可持续健康", 80)
        ]

        for name, value in metrics:
            row = QHBoxLayout()
            row.addWidget(QLabel(name))
            bar = QProgressBar()
            bar.setValue(value)
            bar.setTextVisible(True)
            bar.setFormat(f"{value}")
            row.addWidget(bar)
            metrics_layout.addRow(row)

        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)

        # 发展阶段
        stage_group = QGroupBox("🚀 社会发展阶段")
        stage_layout = QHBoxLayout()

        stages = [
            ("形成期", "1-3月", False),
            ("成长期", "3-12月", False),
            ("成熟期", "1-3年", True),
            ("进化期", "3+年", False)
        ]

        for name, duration, active in stages:
            stage_widget = QWidget()
            stage_widget.setStyleSheet(f"""
                QWidget {{
                    background: {'#667eea' if active else '#e2e8f0'};
                    border-radius: 8px;
                    padding: 10px;
                    {'color: white;' if active else ''}
                }}
            """)
            stage_layout_inner = QVBoxLayout(stage_widget)
            stage_layout_inner.addWidget(QLabel(name))
            stage_layout_inner.addWidget(QLabel(duration))
            stage_layout.addWidget(stage_widget)

        stage_group.setLayout(stage_layout)
        layout.addWidget(stage_group)

        return widget

    def _create_bridge_tab(self) -> QWidget:
        """跨社会桥标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 说明
        info = QLabel("""
        🌐 跨社会互联

        连接不同社区，实现资源互通、文化交流与协同进化
        """)
        info.setStyleSheet("""
            QLabel {
                background: #f0f9ff;
                padding: 15px;
                border-radius: 8px;
                border: 1px solid #0ea5e9;
            }
        """)
        layout.addWidget(info)

        # 已连接的社会
        bridge_group = QGroupBox("🔗 已连接的社会")
        bridge_layout = QVBoxLayout()

        bridges = [
            {"name": "AI开发者社区", "members": "12.5K", "exchange_rate": "1:1", "daily_traffic": "888"},
            {"name": "创意设计师联盟", "members": "8.2K", "exchange_rate": "1:0.95", "daily_traffic": "456"},
            {"name": "区块链爱好者", "members": "5.1K", "exchange_rate": "1:1.1", "daily_traffic": "234"}
        ]

        for bridge in bridges:
            bridge_widget = QWidget()
            bridge_widget.setStyleSheet("""
                QWidget {
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 12px;
                }
            """)
            bridge_layout_inner = QHBoxLayout(bridge_widget)

            bridge_layout_inner.addWidget(QLabel(f"🌐 {bridge['name']}"))
            bridge_layout_inner.addWidget(QLabel(f"👥 {bridge['members']}"))
            bridge_layout_inner.addWidget(QLabel(f"💱 汇率: {bridge['exchange_rate']}"))
            bridge_layout_inner.addWidget(QLabel(f"📊 日交易: {bridge['daily_traffic']}"))

            trade_btn = QPushButton("跨社会交易")
            trade_btn.setFixedWidth(100)
            bridge_layout_inner.addWidget(trade_btn)

            bridge_layout.addWidget(bridge_widget)

        bridge_group.setLayout(bridge_layout)
        layout.addWidget(bridge_group)

        # 创建连接按钮
        connect_btn = QPushButton("🔗 创建新的社会连接")
        connect_btn.setStyleSheet("""
            QPushButton {
                background: #0ea5e9;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }
        """)
        layout.addWidget(connect_btn)

        return widget

    def on_asset_clicked(self, row, col):
        """资产表格点击"""
        if col == 5:  # 操作列
            asset_name = self.asset_table.item(row, 0).text()
            print(f"购买资产: {asset_name}")

    def on_create_asset(self):
        """创建资产"""
        print("打开创建资产表单")

    def refresh_data(self):
        """刷新数据"""
        print("刷新面板数据...")
