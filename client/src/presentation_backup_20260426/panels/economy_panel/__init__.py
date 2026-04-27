"""
积分经济系统UI面板 (Credit Economy Panel)
=====================================

提供个人/企业双模式下的积分账户、技能市场、创意NFT、预测市场等功能界面
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QPushButton, QLabel, QStackedWidget, QListWidget,
                             QListWidgetItem, QTextEdit, QLineEdit, QComboBox,
                             QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
                             QFormLayout, QGroupBox, QSplitter, QProgressBar,
                             QDialog, QDialogButtonBox, QCheckBox, QFrame,
                             QScrollArea, QGridLayout, QCalendarWidget)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QDate, QTime
from PyQt6.QtGui import QFont, QIcon, QPainter, QPen, QColor, QBrush, QPalette
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime, timedelta
import uuid


class EconomyPanel(QWidget):
    """积分经济系统面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_user = "user_001"
        self.is_enterprise_mode = False
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        # 顶部标题栏
        header = self._create_header()
        main_layout.addLayout(header)

        # 模式切换标签
        self.mode_tabs = QTabWidget()
        self.mode_tabs.addTab(self._create_account_tab(), "💳 积分账户")
        self.mode_tabs.addTab(self._create_skill_market_tab(), "🎯 技能市场")
        self.mode_tabs.addTab(self._create_nft_market_tab(), "🎨 NFT市场")
        self.mode_tabs.addTab(self._create_prediction_tab(), "🔮 预测市场")
        self.mode_tabs.addTab(self._create_issuance_tab(), "💰 积分发放")
        self.mode_tabs.addTab(self._create_consumption_tab(), "💸 积分消耗")

        main_layout.addWidget(self.mode_tabs)

    def _create_header(self) -> QHBoxLayout:
        """创建顶部标题栏"""
        header = QHBoxLayout()

        title = QLabel("🪙 积分经济系统")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        header.addWidget(title)

        header.addStretch()

        # 模式切换
        mode_label = QLabel("模式:")
        header.addWidget(mode_label)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["👤 个人模式", "🏢 企业模式"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        header.addWidget(self.mode_combo)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_data)
        header.addWidget(refresh_btn)

        return header

    def _on_mode_changed(self, index):
        """模式切换"""
        self.is_enterprise_mode = (index == 1)
        self._refresh_data()

    def _refresh_data(self):
        """刷新数据"""
        pass

    # ============================================================
    # 积分账户标签页
    # ============================================================

    def _create_account_tab(self) -> QWidget:
        """创建积分账户标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 账户概览卡片
        overview = self._create_account_overview()
        layout.addWidget(overview)

        # 积分趋势图
        trend_group = QGroupBox("📈 积分趋势")
        trend_layout = QHBoxLayout()
        trend_layout.addWidget(QLabel("[趋势图表占位] 过去30天积分变化"))
        trend_group.setLayout(trend_layout)
        layout.addWidget(trend_group)

        # 最近交易
        tx_group = QGroupBox("📋 最近交易")
        tx_layout = QVBoxLayout()

        self.tx_table = QTableWidget(10, 5)
        self.tx_table.setHorizontalHeaderLabels(["时间", "类型", "金额", "余额", "状态"])
        self._populate_transactions()
        tx_layout.addWidget(self.tx_table)

        tx_group.setLayout(tx_layout)
        layout.addWidget(tx_group)

        layout.addStretch()
        return widget

    def _create_account_overview(self) -> QFrame:
        """创建账户概览卡片"""
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.StyledPanel)
        card_layout = QGridLayout(card)

        # 余额
        balance_label = QLabel("<span style='font-size: 32px;'>1,250</span> 积分")
        balance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(balance_label, 0, 0, 1, 2)

        # 统计数据
        stats = [
            ("今日获得", "+150", "green"),
            ("今日消耗", "-85", "red"),
            ("本月结余", "+2,150", "green"),
            ("信用评分", "850", "blue")
        ]

        for i, (label, value, color) in enumerate(stats):
            stat_frame = QFrame()
            stat_frame.setFrameStyle(QFrame.Shape.StyledPanel)
            stat_layout = QVBoxLayout(stat_frame)
            stat_layout.addWidget(QLabel(label))
            value_label = QLabel(f"<span style='color: {color}; font-size: 18px;'>{value}</span>")
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stat_layout.addWidget(value_label)
            card_layout.addWidget(stat_frame, 1, i)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QPushButton("📤 转账"))
        btn_layout.addWidget(QPushButton("💸 消费"))
        btn_layout.addWidget(QPushButton("📈 投资"))
        btn_layout.addWidget(QPushButton("🏦 储蓄"))
        card_layout.addLayout(btn_layout, 2, 0, 1, 4)

        return card

    def _populate_transactions(self):
        """填充交易记录"""
        txs = [
            ("2026-04-18 14:30", "发放", "+1000", "1,250", "已确认"),
            ("2026-04-18 12:15", "消费-AI服务", "-50", "250", "已确认"),
            ("2026-04-18 10:00", "转账-收到", "+200", "300", "已确认"),
            ("2026-04-17 18:20", "消费-存储", "-10", "100", "已确认"),
            ("2026-04-17 15:00", "消费-计算", "-30", "110", "已确认"),
            ("2026-04-17 12:00", "发放", "+1000", "140", "已确认"),
            ("2026-04-16 18:00", "消费-网络", "-5", "140", "已确认"),
            ("2026-04-16 15:30", "转账-发出", "-100", "145", "已确认"),
            ("2026-04-16 12:00", "发放", "+1000", "245", "已确认"),
            ("2026-04-15 18:00", "消费-存储", "-15", "245", "已确认"),
        ]

        for i, (time, tx_type, amount, balance, status) in enumerate(txs):
            self.tx_table.setItem(i, 0, QTableWidgetItem(time))
            self.tx_table.setItem(i, 1, QTableWidgetItem(tx_type))
            self.tx_table.setItem(i, 2, QTableWidgetItem(amount))
            self.tx_table.setItem(i, 3, QTableWidgetItem(balance))
            self.tx_table.setItem(i, 4, QTableWidgetItem(status))

    # ============================================================
    # 技能市场标签页
    # ============================================================

    def _create_skill_market_tab(self) -> QWidget:
        """创建技能市场标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 搜索和筛选
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍"))
        search_input = QLineEdit()
        search_input.setPlaceholderText("搜索技能...")
        search_layout.addWidget(search_input, 1)

        category_combo = QComboBox()
        category_combo.addItems(["全部分类", "编程开发", "设计创意", "写作咨询", "商务市场"])
        search_layout.addWidget(category_combo)

        sort_combo = QComboBox()
        sort_combo.addItems(["信誉排序", "价格排序", "销量排序"])
        search_layout.addWidget(sort_combo)

        layout.addLayout(search_layout)

        # 技能列表
        self.skill_list = QTableWidget(5, 5)
        self.skill_list.setHorizontalHeaderLabels(["技能", "卖家", "价格", "信誉", "操作"])
        self._populate_skill_list()
        layout.addWidget(self.skill_list)

        # 我的挂牌
        my_listing_group = QGroupBox("📦 我的挂牌")
        my_layout = QVBoxLayout()
        my_layout.addWidget(QPushButton("➕ 发布新技能"))
        my_layout.addWidget(QPushButton("📋 管理我的技能"))
        my_listing_group.setLayout(my_layout)
        layout.addWidget(my_listing_group)

        return widget

    def _populate_skill_list(self):
        """填充技能列表"""
        skills = [
            ("Python代码评审", "@tech_guru", "200积分", "★★★★☆ (4.2)", "购买"),
            ("React组件开发", "@frontend_pro", "500积分", "★★★★★ (4.8)", "购买"),
            ("UI/UX设计", "@design_master", "300积分", "★★★★☆ (4.5)", "购买"),
            ("技术写作", "@writer_tech", "150积分", "★★★★☆ (4.3)", "购买"),
            ("架构咨询", "@architect", "800积分", "★★★★★ (4.9)", "购买"),
        ]

        for i, (skill, seller, price, rep, action) in enumerate(skills):
            self.skill_list.setItem(i, 0, QTableWidgetItem(skill))
            self.skill_list.setItem(i, 1, QTableWidgetItem(seller))
            self.skill_list.setItem(i, 2, QTableWidgetItem(price))
            self.skill_list.setItem(i, 3, QTableWidgetItem(rep))
            self.skill_list.setItem(i, 4, QTableWidgetItem(action))

    # ============================================================
    # NFT市场标签页
    # ============================================================

    def _create_nft_market_tab(self) -> QWidget:
        """创建NFT市场标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # NFT概览
        nft_overview = QGroupBox("🎨 我的NFT资产")
        overview_layout = QHBoxLayout()

        nft_stats = [
            ("持有NFT", "3", "个"),
            ("NFT总价值", "5,200", "积分"),
            ("碎片化权益", "1,500", "积分"),
        ]

        for label, value, unit in nft_stats:
            stat_frame = QFrame()
            stat_frame.setFrameStyle(QFrame.Shape.StyledPanel)
            stat_layout = QVBoxLayout(stat_frame)
            stat_layout.addWidget(QLabel(label))
            stat_layout.addWidget(QLabel(f"<span style='font-size: 20px;'>{value}</span> {unit}"))
            overview_layout.addWidget(stat_frame)

        nft_overview.setLayout(overview_layout)
        layout.addWidget(nft_overview)

        # NFT展示
        nft_display = QGroupBox("📌 我的创意NFT")
        nft_layout = QGridLayout()

        for i in range(3):
            nft_card = self._create_nft_card(i)
            nft_layout.addWidget(nft_card, 0, i)

        nft_display.setLayout(nft_layout)
        layout.addWidget(nft_display)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QPushButton("🎨 铸造新NFT"))
        btn_layout.addWidget(QPushButton("📊 碎片化权益"))
        btn_layout.addWidget(QPushButton("🛒 出售NFT"))
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 市场浏览
        market_group = QGroupBox("🔍 浏览市场")
        market_layout = QVBoxLayout()
        market_layout.addWidget(QPushButton("查看全部NFT"))
        market_group.setLayout(market_layout)
        layout.addWidget(market_group)

        layout.addStretch()
        return widget

    def _create_nft_card(self, index: int) -> QFrame:
        """创建NFT卡片"""
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)

        layout.addWidget(QLabel(f"🎨 NFT #{index + 1}"))
        layout.addWidget(QLabel("创意标题"))
        layout.addWidget(QLabel("新颖度: 85%"))
        layout.addWidget(QPushButton("查看详情"))

        return card

    # ============================================================
    # 预测市场标签页
    # ============================================================

    def _create_prediction_tab(self) -> QWidget:
        """创建预测市场标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 我的预测资产
        pred_overview = QGroupBox("📊 我的预测资产")
        overview_layout = QHBoxLayout()

        overview_stats = [
            ("活跃预测", "3", "个"),
            ("持有份额", "850", "积分"),
            ("预计收益", "+320", "积分"),
        ]

        for label, value, unit in overview_stats:
            stat_frame = QFrame()
            stat_frame.setFrameStyle(QFrame.Shape.StyledPanel)
            stat_layout = QVBoxLayout(stat_frame)
            stat_layout.addWidget(QLabel(label))
            stat_layout.addWidget(QLabel(f"<span style='font-size: 18px;'>{value}</span> {unit}"))
            overview_layout.addWidget(stat_frame)

        pred_overview.setLayout(overview_layout)
        layout.addWidget(pred_overview)

        # 活跃预测市场
        market_group = QGroupBox("🔥 活跃预测市场")
        market_layout = QVBoxLayout()

        predictions = [
            {
                "event": "Hermes Desktop v2.0发布时间",
                "outcomes": [("4月底", 0.65), ("5月中", 0.25), ("6月后", 0.10)],
                "volume": "12,500积分"
            },
            {
                "event": "下一个集成功能",
                "outcomes": [("AR/VR", 0.35), ("IoT", 0.30), ("区块链", 0.25), ("其他", 0.10)],
                "volume": "8,200积分"
            }
        ]

        for pred in predictions:
            pred_card = self._create_prediction_card(pred)
            market_layout.addWidget(pred_card)

        market_group.setLayout(market_layout)
        layout.addWidget(market_group)

        # 操作
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QPushButton("🔮 创建预测"))
        btn_layout.addWidget(QPushButton("📈 我的份额"))
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        return widget

    def _create_prediction_card(self, pred: dict) -> QFrame:
        """创建预测卡片"""
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)

        layout.addWidget(QLabel(f"<b>{pred['event']}</b>"))

        for outcome, odds in pred["outcomes"]:
            layout.addWidget(QLabel(f"• {outcome}: {odds*100:.0f}%"))

        layout.addWidget(QLabel(f"总交易量: {pred['volume']}"))

        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton("买入"))
        btn_row.addWidget(QPushButton("卖出"))
        layout.addLayout(btn_row)

        return card

    # ============================================================
    # 积分发放标签页
    # ============================================================

    def _create_issuance_tab(self) -> QWidget:
        """创建积分发放标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 发放概览
        issuance_overview = QGroupBox("💰 积分发放概览")
        overview_layout = QVBoxLayout()

        stats_layout = QHBoxLayout()
        stats = [
            ("基础日发放", "1,000 积分"),
            ("贡献奖励", "+300 积分"),
            ("活跃奖励", "+200 积分"),
        ]

        for label, value in stats:
            stat_frame = QFrame()
            stat_frame.setFrameStyle(QFrame.Shape.StyledPanel)
            stat_layout = QVBoxLayout(stat_frame)
            stat_layout.addWidget(QLabel(label))
            stat_layout.addWidget(QLabel(f"<span style='font-size: 16px;'>{value}</span>"))
            stats_layout.addWidget(stat_frame)

        overview_layout.addLayout(stats_layout)

        total_frame = QFrame()
        total_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        total_layout = QVBoxLayout(total_frame)
        total_layout.addWidget(QLabel("预计今日可获得"))
        total_layout.addWidget(QLabel("<span style='font-size: 28px; color: green;'>1,500 积分</span>"))
        overview_layout.addWidget(total_frame)

        issuance_overview.setLayout(overview_layout)
        layout.addWidget(issuance_overview)

        # 贡献明细
        contribution_group = QGroupBox("📊 我的贡献明细")
        contrib_layout = QVBoxLayout()

        contributions = [
            ("节点在线时长", "95%", "+100"),
            ("数据分享量", "150条", "+75"),
            ("任务完成数", "12个", "+60"),
            ("内容创作", "3篇", "+45"),
            ("社区帮助", "8次", "+20"),
        ]

        contrib_table = QTableWidget(5, 3)
        contrib_table.setHorizontalHeaderLabels(["项目", "数值", "奖励"])
        for i, (item, value, reward) in enumerate(contributions):
            contrib_table.setItem(i, 0, QTableWidgetItem(item))
            contrib_table.setItem(i, 1, QTableWidgetItem(value))
            contrib_table.setItem(i, 2, QTableWidgetItem(reward))
        contrib_layout.addWidget(contrib_table)

        contribution_group.setLayout(contrib_layout)
        layout.addWidget(contribution_group)

        # 政策信息
        policy_group = QGroupBox("⚙️ 经济政策")
        policy_layout = QFormLayout()
        policy_layout.addRow("网络健康度:", QLabel("85%"))
        policy_layout.addRow("通胀率:", QLabel("1.02"))
        policy_layout.addRow("活跃节点:", QLabel("1,000"))
        policy_group.setLayout(policy_layout)
        layout.addWidget(policy_group)

        layout.addStretch()
        return widget

    # ============================================================
    # 积分消耗标签页
    # ============================================================

    def _create_consumption_tab(self) -> QWidget:
        """创建积分消耗标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 消耗概览
        consumption_overview = QGroupBox("💸 积分消耗概览")
        overview_layout = QVBoxLayout()

        # 智能建议
        suggestion = QLabel("""
        <div style='background: #E8F5E9; padding: 10px; border-radius: 5px;'>
        <b>💡 智能建议</b><br>
        • 当前余额充足，可进行技能学习投资<br>
        • 预计回报: 3x (技能收益权代币化)<br>
        • 建议储备: 500积分作为应急
        </div>
        """)
        overview_layout.addWidget(suggestion)

        # 消耗统计
        stats_layout = QHBoxLayout()
        stats = [
            ("计算服务", "50积分/次"),
            ("AI对话", "5积分/千token"),
            ("图像生成", "20积分/张"),
            ("代码生成", "30积分/百行"),
        ]

        for label, price in stats:
            stat_frame = QFrame()
            stat_frame.setFrameStyle(QFrame.Shape.StyledPanel)
            stat_layout = QVBoxLayout(stat_frame)
            stat_layout.addWidget(QLabel(label))
            stat_layout.addWidget(QLabel(f"<span style='font-size: 14px;'>{price}</span>"))
            stats_layout.addWidget(stat_frame)

        overview_layout.addLayout(stats_layout)
        consumption_overview.setLayout(overview_layout)
        layout.addWidget(consumption_overview)

        # 成本预估
        cost_group = QGroupBox("📊 任务成本预估")
        cost_layout = QVBoxLayout()

        cost_items = [
            ("Web开发任务", {"基础": "500", "AI增强": "650", "节省": "-15%"}),
            ("数据分析报告", {"基础": "300", "AI增强": "380", "节省": "-10%"}),
            ("设计原型", {"基础": "400", "AI增强": "500", "节省": "-12%"}),
        ]

        for task, costs in cost_items:
            task_frame = QFrame()
            task_frame.setFrameStyle(QFrame.Shape.StyledPanel)
            task_layout = QHBoxLayout(task_frame)
            task_layout.addWidget(QLabel(f"<b>{task}</b>"))
            task_layout.addWidget(QLabel(f"基础: {costs['基础']}"))
            task_layout.addWidget(QLabel(f"AI增强: {costs['AI增强']}"))
            task_layout.addWidget(QLabel(f"<span style='color: green;'>{costs['节省']}</span>"))
            cost_layout.addWidget(task_frame)

        cost_group.setLayout(cost_layout)
        layout.addWidget(cost_group)

        # 替代方案
        alt_group = QGroupBox("🔄 替代方案")
        alt_layout = QVBoxLayout()
        alt_layout.addWidget(QLabel("💡 选择轻量计算可节省50%积分"))
        alt_layout.addWidget(QPushButton("查看所有替代方案"))
        alt_group.setLayout(alt_layout)
        layout.addWidget(alt_group)

        layout.addStretch()
        return widget


def create_economy_panel() -> EconomyPanel:
    """创建经济面板"""
    return EconomyPanel()