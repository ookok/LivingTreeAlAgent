"""
中继链管理面板 - Relay Chain Panel

提供中继链积分系统的可视化管理和监控界面
"""

from typing import Optional, Dict, List
import time

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QTabWidget, QProgressBar, QFrame,
    QTextEdit, QScrollArea, QCheckBox
)
from PyQt6.QtGui import QFont, QColor


class RelayChainPanel(QWidget):
    """
    中继链管理面板

    功能：
    1. 积分账户管理（查询余额、交易历史）
    2. 交易操作（发放、消费、转账）
    3. 节点监控（在线节点、心跳状态）
    4. 账本浏览（全网交易、统计信息）
    5. 共识监控（待确认交易、投票状态）
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 模拟数据（实际应从core模块获取）
        self._mock_ledger = self._create_mock_data()

        self._build_ui()
        self._start_refresh_timer()

    def _create_mock_data(self) -> Dict:
        """创建模拟数据"""
        return {
            "stats": {
                "total_transactions": 1234,
                "total_users": 56,
                "total_points_in": 100000.0,
                "total_points_out": 45000.0,
                "circulating": 55000.0,
                "ledger_hash": "a1b2c3d4e5f6..."
            },
            "users": {
                "user_001": {"balance": 1000.0, "nonce": 5},
                "user_002": {"balance": 2500.0, "nonce": 3},
                "user_003": {"balance": 500.0, "nonce": 8},
            },
            "pending_txs": [
                {"tx_hash": "tx001...", "user": "user_001", "amount": 100, "type": "TRANSFER_OUT", "confirmations": 2},
                {"tx_hash": "tx002...", "user": "user_002", "amount": 500, "type": "IN", "confirmations": 1},
            ],
            "nodes": [
                {"relay_id": "relay_nanjing", "type": "core", "region": "南京", "state": "online", "load": 15},
                {"relay_id": "relay_shanghai", "type": "core", "region": "上海", "state": "online", "load": 22},
                {"relay_id": "relay_beijing", "type": "edge", "region": "北京", "state": "online", "load": 8},
                {"relay_id": "relay_guangzhou", "type": "edge", "region": "广州", "state": "suspect", "load": 0},
            ]
        }

    def _build_ui(self):
        """构建UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 标题
        title = QLabel("⛓️ 中继链 - 分布式积分账本")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #60a5fa;
            padding: 4px 0;
        """)
        main_layout.addWidget(title)

        # 创建标签页
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                padding: 10px;
                background: #1a1a2e;
            }
            QTabBar::tab {
                background: #252538;
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: #9090c0;
            }
            QTabBar::tab:selected {
                background: #3a3a5e;
                color: #e0e0ff;
            }
        """)

        tabs.addTab(self._build_account_tab(), "👤 账户管理")
        tabs.addTab(self._build_transaction_tab(), "💸 交易操作")
        tabs.addTab(self._build_recharge_tab(), "💳 充值管理")
        tabs.addTab(self._build_ledger_tab(), "📖 账本浏览")
        tabs.addTab(self._build_node_tab(), "🖥️ 节点监控")
        tabs.addTab(self._build_consensus_tab(), "🔐 共识状态")
        tabs.addTab(self._build_monitor_tab(), "📊 系统监控")
        tabs.addTab(self._build_audit_tab(), "📋 审计日志")
        tabs.addTab(self._build_reconciliation_tab(), "🔍 对账服务")
        tabs.addTab(self._build_task_scheduler_tab(), "🏭 任务调度")
        tabs.addTab(self._build_cross_tenant_tab(), "🏢 跨租户消息")
        tabs.addTab(self._build_game_asset_tab(), "🎮 游戏资产")
        tabs.addTab(self._build_distributed_im_tab(), "💬 分布式IM")
        tabs.addTab(self._build_p2p_network_tab(), "🌐 P2P自组织网络")

        main_layout.addWidget(tabs)

    def _build_account_tab(self) -> QWidget:
        """账户管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 查询区域
        query_group = QGroupBox("账户查询")
        query_layout = QHBoxLayout(query_group)

        query_layout.addWidget(QLabel("用户ID:"))
        self.account_user_input = QLineEdit()
        self.account_user_input.setPlaceholderText("输入用户ID...")
        self.account_user_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        query_layout.addWidget(self.account_user_input)

        self.account_query_btn = QPushButton("🔍 查询")
        self.account_query_btn.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        self.account_query_btn.clicked.connect(self._query_account)
        query_layout.addWidget(self.account_query_btn)

        query_layout.addStretch()
        layout.addWidget(query_group)

        # 账户信息显示
        info_group = QGroupBox("账户信息")
        info_layout = QGridLayout(info_group)

        info_layout.addWidget(QLabel("用户ID:"), 0, 0)
        self.account_id_label = QLabel("-")
        self.account_id_label.setStyleSheet("color: #e0e0ff; font-weight: bold;")
        info_layout.addWidget(self.account_id_label, 0, 1)

        info_layout.addWidget(QLabel("余额:"), 0, 2)
        self.account_balance_label = QLabel("-")
        self.account_balance_label.setStyleSheet("color: #10b981; font-size: 18px; font-weight: bold;")
        info_layout.addWidget(self.account_balance_label, 0, 3)

        info_layout.addWidget(QLabel("Nonce:"), 1, 0)
        self.account_nonce_label = QLabel("-")
        info_layout.addWidget(self.account_nonce_label, 1, 1)

        info_layout.addWidget(QLabel("累计收入:"), 1, 2)
        self.account_total_in_label = QLabel("-")
        self.account_total_in_label.setStyleSheet("color: #10b981;")
        info_layout.addWidget(self.account_total_in_label, 1, 3)

        info_layout.addWidget(QLabel("累计支出:"), 2, 0)
        self.account_total_out_label = QLabel("-")
        self.account_total_out_label.setStyleSheet("color: #ef4444;")
        info_layout.addWidget(self.account_total_out_label, 2, 1)

        info_layout.addWidget(QLabel("最后交易:"), 2, 2)
        self.account_last_tx_label = QLabel("-")
        info_layout.addWidget(self.account_last_tx_label, 2, 3)

        layout.addWidget(info_group)

        # 交易历史
        history_group = QGroupBox("交易历史")
        history_layout = QVBoxLayout(history_group)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["交易Hash", "类型", "金额", "Nonce", "时间"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background: #1a1a2e;
                alternate-background-color: #252538;
                color: #e0e0ff;
                gridline-color: #3a3a5e;
                border: none;
            }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected { background: #3a3a5e; }
            QHeaderView::section {
                background: #252538;
                color: #9090c0;
                padding: 8px;
                border: none;
            }
        """)
        self.history_table.setMaximumHeight(250)
        history_layout.addWidget(self.history_table)

        layout.addWidget(history_group)
        layout.addStretch()

        return widget

    def _build_transaction_tab(self) -> QWidget:
        """交易操作标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 交易类型选择
        type_group = QGroupBox("交易类型")
        type_layout = QHBoxLayout(type_group)

        self.tx_type_combo = QComboBox()
        self.tx_type_combo.addItems(["积分发放", "积分消费", "转账"])
        self.tx_type_combo.setStyleSheet("""
            QComboBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 12px;
                color: #e0e0ff;
            }
        """)
        type_layout.addWidget(self.tx_type_combo)
        type_layout.addStretch()
        layout.addWidget(type_group)

        # 交易表单
        form_group = QGroupBox("交易信息")
        form_layout = QGridLayout(form_group)

        form_layout.addWidget(QLabel("用户ID:"), 0, 0)
        self.tx_user_input = QLineEdit()
        self.tx_user_input.setPlaceholderText("目标用户ID...")
        self.tx_user_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        form_layout.addWidget(self.tx_user_input, 0, 1)

        form_layout.addWidget(QLabel("金额:"), 0, 2)
        self.tx_amount_input = QLineEdit()
        self.tx_amount_input.setPlaceholderText("0.00")
        self.tx_amount_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        form_layout.addWidget(self.tx_amount_input, 0, 3)

        form_layout.addWidget(QLabel("目标用户:"), 1, 0)
        self.tx_to_user_input = QLineEdit()
        self.tx_to_user_input.setPlaceholderText("转账目标用户ID（仅转账用）...")
        self.tx_to_user_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        form_layout.addWidget(self.tx_to_user_input, 1, 1, 1, 3)

        form_layout.addWidget(QLabel("备注:"), 2, 0)
        self.tx_memo_input = QLineEdit()
        self.tx_memo_input.setPlaceholderText("交易备注...")
        self.tx_memo_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        form_layout.addWidget(self.tx_memo_input, 2, 1, 1, 3)

        layout.addWidget(form_group)

        # 提交按钮
        submit_btn = QPushButton("📤 提交交易")
        submit_btn.setStyleSheet("""
            QPushButton {
                background: #059669;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #047857; }
        """)
        submit_btn.clicked.connect(self._submit_transaction)
        layout.addWidget(submit_btn)

        # 交易日志
        log_group = QGroupBox("交易日志")
        log_layout = QVBoxLayout(log_group)

        self.tx_log = QTextEdit()
        self.tx_log.setReadOnly(True)
        self.tx_log.setMaximumHeight(150)
        self.tx_log.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        self.tx_log.append("[系统] 交易模块就绪...")
        log_layout.addWidget(self.tx_log)

        layout.addWidget(log_group)
        layout.addStretch()

        return widget

    def _build_recharge_tab(self) -> QWidget:
        """充值管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 充值渠道选择
        channel_group = QGroupBox("充值渠道")
        channel_layout = QHBoxLayout(channel_group)

        self.recharge_channel_combo = QComboBox()
        self.recharge_channel_combo.addItems(["微信支付", "支付宝", "银行转账"])
        self.recharge_channel_combo.setStyleSheet("""
            QComboBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 12px;
                color: #e0e0ff;
            }
        """)
        channel_layout.addWidget(self.recharge_channel_combo)
        channel_layout.addStretch()
        layout.addWidget(channel_group)

        # 模拟充值表单
        recharge_form_group = QGroupBox("模拟充值（演示用）")
        recharge_form_layout = QGridLayout(recharge_form_group)

        recharge_form_layout.addWidget(QLabel("用户ID:"), 0, 0)
        self.recharge_user_input = QLineEdit()
        self.recharge_user_input.setPlaceholderText("目标用户ID...")
        self.recharge_user_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        recharge_form_layout.addWidget(self.recharge_user_input, 0, 1)

        recharge_form_layout.addWidget(QLabel("充值金额:"), 0, 2)
        self.recharge_amount_input = QLineEdit()
        self.recharge_amount_input.setPlaceholderText("0.00")
        self.recharge_amount_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        recharge_form_layout.addWidget(self.recharge_amount_input, 0, 3)

        recharge_form_layout.addWidget(QLabel("订单号:"), 1, 0)
        self.recharge_order_input = QLineEdit()
        self.recharge_order_input.setPlaceholderText("支付订单号（自动生成）...")
        self.recharge_order_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        recharge_form_layout.addWidget(self.recharge_order_input, 1, 1, 1, 3)

        layout.addWidget(recharge_form_group)

        # 提交按钮
        submit_btn = QPushButton("💰 发起充值")
        submit_btn.setStyleSheet("""
            QPushButton {
                background: #059669;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #047857; }
        """)
        submit_btn.clicked.connect(self._submit_recharge)
        layout.addWidget(submit_btn)

        # 充值流程说明
        flow_group = QGroupBox("充值流程说明")
        flow_layout = QVBoxLayout(flow_group)

        flow_text = QTextEdit()
        flow_text.setReadOnly(True)
        flow_text.setMaximumHeight(120)
        flow_text.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        flow_text.setText("""
充值流程（链式入账）：

1️⃣ 用户通过微信/支付宝完成支付
2️⃣ 支付网关回调中继节点（如南京中继）
3️⃣ 中继验证签名 → 检查幂等性 → 构造RECHARGE交易
4️⃣ 交易广播至全网 → 各中继独立验证
5️⃣ 超过阈值确认 → 写入各节点账本
6️⃣ 用户余额自动更新（余额 = Σ(IN) - Σ(OUT)）

防双花机制：
• nonce 连续性：同一用户交易必须按序入账
• prev_hash 链：每笔交易指向前一笔，形成哈希链
• 全网广播校验：所有中继节点独立验证后才确认
        """.strip())
        flow_layout.addWidget(flow_text)

        layout.addWidget(flow_group)

        # 充值日志
        log_group = QGroupBox("充值日志")
        log_layout = QVBoxLayout(log_group)

        self.recharge_log = QTextEdit()
        self.recharge_log.setReadOnly(True)
        self.recharge_log.setMaximumHeight(120)
        self.recharge_log.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        self.recharge_log.append("[系统] 充值模块就绪，等待支付回调...")
        log_layout.addWidget(self.recharge_log)

        layout.addWidget(log_group)
        layout.addStretch()

        return widget

    def _submit_recharge(self):
        """提交充值（模拟）"""
        import hashlib
        import time

        user_id = self.recharge_user_input.text().strip()
        amount_text = self.recharge_amount_input.text().strip()
        channel = self.recharge_channel_combo.currentText()

        if not user_id or not amount_text:
            self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}] ❌ 请填写用户ID和充值金额")
            return

        try:
            amount = float(amount_text)
        except ValueError:
            self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}] ❌ 金额格式错误")
            return

        # 生成订单号
        order_id = self.recharge_order_input.text().strip()
        if not order_id:
            order_id = f"{channel[:2]}{int(time.time())}{hashlib.md5(user_id.encode()).hexdigest()[:6]}"

        # 模拟充值流程
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}] 📋 收到 {channel} 充值回调")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}]    订单号: {order_id}")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}]    用户ID: {user_id}")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}]    金额: ¥{amount:.2f}")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}] 🔐 签名验证: 通过")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}] 🔄 幂等性检查: 通过")

        # 模拟构造充值交易
        tx_hash = hashlib.sha256(f"{order_id}{user_id}{amount}{time.time()}".encode()).hexdigest()
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}] 📝 构造RECHARGE交易")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}]    tx_hash: {tx_hash[:16]}...")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}]    nonce: 1 (假设)")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}]    prev_hash: Genesis")

        # 模拟广播
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}] 📡 广播至全网中继...")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}]    → relay_nanjing (南京): ✓ 验证通过")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}]    → relay_shanghai (上海): ✓ 验证通过")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}]    → relay_hangzhou (杭州): ✓ 验证通过")

        # 模拟确认
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}] ✅ 达成共识 (3/3)，交易确认")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}] 📖 写入账本，余额更新")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}] ")
        self.recharge_log.append(f"[{time.strftime('%H:%M:%S')}] 🎉 充值成功！用户 {user_id} 余额 +{amount:.2f}")

        # 清空表单
        self.recharge_user_input.clear()
        self.recharge_amount_input.clear()
        self.recharge_order_input.clear()

    def _build_ledger_tab(self) -> QWidget:
        """账本浏览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 统计信息
        stats_group = QGroupBox("账本统计")
        stats_layout = QGridLayout(stats_group)

        stats_data = [
            ("总交易数", "total_transactions", "#60a5fa"),
            ("总用户数", "total_users", "#a78bfa"),
            ("累计收入", "total_points_in", "#10b981"),
            ("累计支出", "total_points_out", "#f59e0b"),
            ("流通积分", "circulating", "#06b6d4"),
            ("账本哈希", "ledger_hash", "#9ca3af"),
        ]

        self.stats_labels = {}
        for i, (label, key, color) in enumerate(stats_data):
            row = i // 3
            col = (i % 3) * 2
            stats_layout.addWidget(QLabel(f"{label}:"), row, col)
            lbl = QLabel("-")
            lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
            stats_layout.addWidget(lbl, row, col + 1)
            self.stats_labels[key] = lbl

        layout.addWidget(stats_group)

        # 全网交易
        ledger_group = QGroupBox("全网交易")
        ledger_layout = QVBoxLayout(ledger_group)

        self.ledger_table = QTableWidget()
        self.ledger_table.setColumnCount(6)
        self.ledger_table.setHorizontalHeaderLabels(["交易Hash", "用户", "类型", "金额", "Nonce", "时间"])
        self.ledger_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ledger_table.setStyleSheet("""
            QTableWidget {
                background: #1a1a2e;
                alternate-background-color: #252538;
                color: #e0e0ff;
                gridline-color: #3a3a5e;
                border: none;
            }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected { background: #3a3a5e; }
            QHeaderView::section {
                background: #252538;
                color: #9090c0;
                padding: 8px;
                border: none;
            }
        """)
        ledger_layout.addWidget(self.ledger_table)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新账本")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #3a3a5e;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: #e0e0ff;
            }
            QPushButton:hover { background: #4a4a7e; }
        """)
        refresh_btn.clicked.connect(self._refresh_ledger)
        ledger_layout.addWidget(refresh_btn)

        layout.addWidget(ledger_group)

        return widget

    def _build_node_tab(self) -> QWidget:
        """节点监控标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 节点统计
        stats_group = QGroupBox("节点统计")
        stats_layout = QHBoxLayout(stats_group)

        self.node_stats_labels = {}
        for label_text in ["核心节点", "边缘节点", "在线", "可疑"]:
            stats_layout.addWidget(QLabel(f"{label_text}:"))
            lbl = QLabel("0")
            lbl.setStyleSheet("color: #60a5fa; font-weight: bold; font-size: 18px;")
            stats_layout.addWidget(lbl)
            self.node_stats_labels[label_text] = lbl

        stats_layout.addStretch()
        layout.addWidget(stats_group)

        # 节点列表
        node_group = QGroupBox("节点列表")
        node_layout = QVBoxLayout(node_group)

        self.node_table = QTableWidget()
        self.node_table.setColumnCount(5)
        self.node_table.setHorizontalHeaderLabels(["节点ID", "类型", "地区", "状态", "负载"])
        self.node_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.node_table.setStyleSheet("""
            QTableWidget {
                background: #1a1a2e;
                alternate-background-color: #252538;
                color: #e0e0ff;
                gridline-color: #3a3a5e;
                border: none;
            }
            QTableWidget::item { padding: 8px; }
            QHeaderView::section {
                background: #252538;
                color: #9090c0;
                padding: 8px;
                border: none;
            }
        """)
        node_layout.addWidget(self.node_table)

        # 刷新按钮
        node_refresh_btn = QPushButton("🔄 刷新节点")
        node_refresh_btn.setStyleSheet("""
            QPushButton {
                background: #3a3a5e;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: #e0e0ff;
            }
            QPushButton:hover { background: #4a4a7e; }
        """)
        node_refresh_btn.clicked.connect(self._refresh_nodes)
        node_layout.addWidget(node_refresh_btn)

        layout.addWidget(node_group)

        return widget

    def _build_consensus_tab(self) -> QWidget:
        """共识状态标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 共识参数
        params_group = QGroupBox("共识参数")
        params_layout = QGridLayout(params_group)

        params_layout.addWidget(QLabel("确认阈值:"), 0, 0)
        self.confirm_threshold_label = QLabel("3 个中继")
        self.confirm_threshold_label.setStyleSheet("color: #10b981; font-weight: bold;")
        params_layout.addWidget(self.confirm_threshold_label, 0, 1)

        params_layout.addWidget(QLabel("拒绝阈值:"), 0, 2)
        self.reject_threshold_label = QLabel("2 个中继")
        self.reject_threshold_label.setStyleSheet("color: #ef4444; font-weight: bold;")
        params_layout.addWidget(self.reject_threshold_label, 0, 3)

        params_layout.addWidget(QLabel("超时时间:"), 1, 0)
        self.timeout_label = QLabel("60 秒")
        params_layout.addWidget(self.timeout_label, 1, 1)

        params_layout.addWidget(QLabel("网络节点数:"), 1, 2)
        self.network_nodes_label = QLabel("4 个")
        params_layout.addWidget(self.network_nodes_label, 1, 3)

        layout.addWidget(params_group)

        # 待确认交易
        pending_group = QGroupBox("待确认交易")
        pending_layout = QVBoxLayout(pending_group)

        self.pending_table = QTableWidget()
        self.pending_table.setColumnCount(5)
        self.pending_table.setHorizontalHeaderLabels(["交易Hash", "用户", "金额", "类型", "确认数"])
        self.pending_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.pending_table.setStyleSheet("""
            QTableWidget {
                background: #1a1a2e;
                alternate-background-color: #252538;
                color: #e0e0ff;
                gridline-color: #3a3a5e;
                border: none;
            }
            QTableWidget::item { padding: 6px; }
            QHeaderView::section {
                background: #252538;
                color: #9090c0;
                padding: 8px;
                border: none;
            }
        """)
        pending_layout.addWidget(self.pending_table)

        layout.addWidget(pending_group)

        # 健康状态
        health_group = QGroupBox("网络健康状态")
        health_layout = QHBoxLayout(health_group)

        self.health_indicator = QLabel("● 健康")
        self.health_indicator.setStyleSheet("color: #10b981; font-size: 16px; font-weight: bold;")
        health_layout.addWidget(self.health_indicator)

        health_layout.addStretch()

        self.last_sync_label = QLabel("最后同步: --")
        health_layout.addWidget(self.last_sync_label)

        layout.addWidget(health_group)
        layout.addStretch()

        return widget

    # ────────────────────────────────────────────────────────────────
    # 事件处理
    # ────────────────────────────────────────────────────────────────

    def _query_account(self):
        """查询账户"""
        user_id = self.account_user_input.text().strip()
        if not user_id:
            return

        user_data = self._mock_ledger["users"].get(user_id)
        if user_data:
            self.account_id_label.setText(user_id)
            self.account_balance_label.setText(f"💰 {user_data['balance']:.2f}")
            self.account_nonce_label.setText(str(user_data['nonce']))
            self.account_total_in_label.setText(f"+{user_data['balance'] * 2:.2f}")
            self.account_total_out_label.setText(f"-{user_data['balance']:.2f}")
            self.account_last_tx_label.setText(f"tx_{user_id}_last...")

            # 刷新历史
            self._refresh_history(user_id)
        else:
            self.tx_log.append(f"[{time.strftime('%H:%M:%S')}] 用户不存在: {user_id}")

    def _refresh_history(self, user_id: str):
        """刷新交易历史"""
        self.history_table.setRowCount(3)
        for i, tx_type in enumerate(["TRANSFER_IN", "TRANSFER_OUT", "IN"]):
            self.history_table.setItem(i, 0, QTableWidgetItem(f"tx_{user_id}_{i}..."))
            self.history_table.setItem(i, 1, QTableWidgetItem(tx_type))
            self.history_table.setItem(i, 2, QTableWidgetItem("+100.00" if "IN" in tx_type else "-50.00"))
            self.history_table.setItem(i, 3, QTableWidgetItem(str(2 - i)))
            self.history_table.setItem(i, 4, QTableWidgetItem("2026-04-18 10:00"))

    def _submit_transaction(self):
        """提交交易"""
        user_id = self.tx_user_input.text().strip()
        amount_text = self.tx_amount_input.text().strip()
        tx_type = self.tx_type_combo.currentText()

        if not user_id or not amount_text:
            self.tx_log.append(f"[{time.strftime('%H:%M:%S')}] 请填写完整信息")
            return

        try:
            amount = float(amount_text)
            self.tx_log.append(f"[{time.strftime('%H:%M:%S')}] 提交交易: {tx_type} {amount} -> {user_id}")
            self.tx_log.append(f"[{time.strftime('%H:%M:%S')}] ✓ 交易已广播，等待共识确认...")
        except ValueError:
            self.tx_log.append(f"[{time.strftime('%H:%M:%S')}] 金额格式错误")

    def _refresh_ledger(self):
        """刷新账本"""
        stats = self._mock_ledger["stats"]
        for key, label in self.stats_labels.items():
            value = stats.get(key, "-")
            if isinstance(value, float):
                label.setText(f"{value:,.2f}")
            else:
                label.setText(str(value)[:16] + "...")

        # 模拟交易数据
        self.ledger_table.setRowCount(5)
        for i in range(5):
            self.ledger_table.setItem(i, 0, QTableWidgetItem(f"tx_hash_{i}..."))
            self.ledger_table.setItem(i, 1, QTableWidgetItem(f"user_{i % 3 + 1:03d}"))
            self.ledger_table.setItem(i, 2, QTableWidgetItem("TRANSFER_OUT"))
            self.ledger_table.setItem(i, 3, QTableWidgetItem(f"{100 + i * 10:.2f}"))
            self.ledger_table.setItem(i, 4, QTableWidgetItem(str(i)))
            self.ledger_table.setItem(i, 5, QTableWidgetItem("2026-04-18"))

    def _refresh_nodes(self):
        """刷新节点"""
        nodes = self._mock_ledger["nodes"]

        # 更新统计
        core_count = sum(1 for n in nodes if n["type"] == "core")
        edge_count = sum(1 for n in nodes if n["type"] == "edge")
        online_count = sum(1 for n in nodes if n["state"] == "online")
        suspect_count = sum(1 for n in nodes if n["state"] == "suspect")

        self.node_stats_labels["核心节点"].setText(str(core_count))
        self.node_stats_labels["边缘节点"].setText(str(edge_count))
        self.node_stats_labels["在线"].setText(str(online_count))
        self.node_stats_labels["可疑"].setText(str(suspect_count))

        # 更新表格
        self.node_table.setRowCount(len(nodes))
        for i, node in enumerate(nodes):
            self.node_table.setItem(i, 0, QTableWidgetItem(node["relay_id"]))
            self.node_table.setItem(i, 1, QTableWidgetItem(node["type"]))
            self.node_table.setItem(i, 2, QTableWidgetItem(node["region"]))

            state_item = QTableWidgetItem(node["state"])
            if node["state"] == "online":
                state_item.setForeground(QColor("#10b981"))
            elif node["state"] == "suspect":
                state_item.setForeground(QColor("#f59e0b"))
            else:
                state_item.setForeground(QColor("#ef4444"))
            self.node_table.setItem(i, 3, state_item)

            self.node_table.setItem(i, 4, QTableWidgetItem(f"{node['load']}%"))

    def _refresh_pending(self):
        """刷新待确认交易"""
        pending = self._mock_ledger["pending_txs"]
        self.pending_table.setRowCount(len(pending))

        for i, tx in enumerate(pending):
            self.pending_table.setItem(i, 0, QTableWidgetItem(tx["tx_hash"]))
            self.pending_table.setItem(i, 1, QTableWidgetItem(tx["user"]))
            self.pending_table.setItem(i, 2, QTableWidgetItem(f"{tx['amount']:.2f}"))
            self.pending_table.setItem(i, 3, QTableWidgetItem(tx["type"]))

            confirm_item = QTableWidgetItem(f"{tx['confirmations']}/3")
            if tx["confirmations"] >= 3:
                confirm_item.setForeground(QColor("#10b981"))
            elif tx["confirmations"] >= 2:
                confirm_item.setForeground(QColor("#f59e0b"))
            self.pending_table.setItem(i, 4, confirm_item)

    def _build_monitor_tab(self) -> QWidget:
        """系统监控标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 健康状态概览
        health_group = QGroupBox("系统健康状态")
        health_layout = QGridLayout(health_group)

        self.monitor_score_label = QLabel("100")
        self.monitor_score_label.setStyleSheet("color: #10b981; font-size: 32px; font-weight: bold;")
        health_layout.addWidget(self.monitor_score_label, 0, 0, 2, 1)

        health_layout.addWidget(QLabel("健康评分"), 0, 1)
        self.monitor_status_label = QLabel("● 健康")
        self.monitor_status_label.setStyleSheet("color: #10b981; font-size: 18px; font-weight: bold;")
        health_layout.addWidget(self.monitor_status_label, 1, 1)

        health_layout.addWidget(QLabel("在线节点:"), 0, 2)
        self.monitor_online_nodes = QLabel("4/4")
        self.monitor_online_nodes.setStyleSheet("color: #60a5fa; font-weight: bold;")
        health_layout.addWidget(self.monitor_online_nodes, 0, 3)

        health_layout.addWidget(QLabel("活跃告警:"), 1, 2)
        self.monitor_active_alerts = QLabel("0")
        self.monitor_active_alerts.setStyleSheet("color: #10b981;")
        health_layout.addWidget(self.monitor_active_alerts, 1, 3)

        layout.addWidget(health_group)

        # 交易统计
        stats_group = QGroupBox("交易统计")
        stats_layout = QGridLayout(stats_group)

        tx_stats = [
            ("总交易数", "total", "#60a5fa"),
            ("充值", "recharge", "#10b981"),
            ("消费", "consume", "#f59e0b"),
            ("转账", "transfer", "#06b6d4"),
            ("失败", "failed", "#ef4444"),
            ("成功率", "success_rate", "#10b981"),
        ]

        self.monitor_stats_labels = {}
        for i, (label, key, color) in enumerate(tx_stats):
            row = i // 3
            col = (i % 3) * 2
            stats_layout.addWidget(QLabel(f"{label}:"), row, col)
            lbl = QLabel("-")
            lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
            stats_layout.addWidget(lbl, row, col + 1)
            self.monitor_stats_labels[key] = lbl

        layout.addWidget(stats_group)

        # 告警列表
        alert_group = QGroupBox("最近告警")
        alert_layout = QVBoxLayout(alert_group)

        self.alert_table = QTableWidget()
        self.alert_table.setColumnCount(4)
        self.alert_table.setHorizontalHeaderLabels(["时间", "级别", "类别", "消息"])
        self.alert_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.alert_table.setStyleSheet("""
            QTableWidget {
                background: #1a1a2e;
                alternate-background-color: #252538;
                color: #e0e0ff;
                gridline-color: #3a3a5e;
                border: none;
            }
            QTableWidget::item { padding: 6px; }
            QHeaderView::section {
                background: #252538;
                color: #9090c0;
                padding: 8px;
                border: none;
            }
        """)
        self.alert_table.setMaximumHeight(200)
        alert_layout.addWidget(self.alert_table)

        refresh_btn = QPushButton("🔄 刷新监控")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #3a3a5e;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: #e0e0ff;
            }
            QPushButton:hover { background: #4a4a7e; }
        """)
        refresh_btn.clicked.connect(self._refresh_monitor)
        alert_layout.addWidget(refresh_btn)

        layout.addWidget(alert_group)
        layout.addStretch()

        return widget

    def _refresh_monitor(self):
        """刷新监控数据"""
        # 模拟数据
        self.monitor_score_label.setText("95")
        self.monitor_status_label.setText("● 健康")
        self.monitor_online_nodes.setText("4/4")
        self.monitor_active_alerts.setText("1")

        stats = {
            "total": "1,234",
            "recharge": "856",
            "consume": "234",
            "transfer": "144",
            "failed": "3",
            "success_rate": "99.8%"
        }

        for key, value in stats.items():
            if key in self.monitor_stats_labels:
                self.monitor_stats_labels[key].setText(value)

        # 模拟告警
        self.alert_table.setRowCount(2)
        self.alert_table.setItem(0, 0, QTableWidgetItem("2026-04-18 12:45"))
        self.alert_table.setItem(0, 1, QTableWidgetItem("WARNING"))
        self.alert_table.setItem(0, 2, QTableWidgetItem("node_health"))
        self.alert_table.setItem(0, 3, QTableWidgetItem("节点 relay_guangzhou 心跳超时"))
        self.alert_table.item(0, 1).setForeground(QColor("#f59e0b"))

        self.alert_table.setItem(1, 0, QTableWidgetItem("2026-04-18 10:30"))
        self.alert_table.setItem(1, 1, QTableWidgetItem("INFO"))
        self.alert_table.setItem(1, 2, QTableWidgetItem("tx_anomaly"))
        self.alert_table.setItem(1, 3, QTableWidgetItem("大额交易: 用户 user_001 交易 10000"))
        self.alert_table.item(1, 1).setForeground(QColor("#60a5fa"))

    def _build_audit_tab(self) -> QWidget:
        """审计日志标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 用户审计查询
        query_group = QGroupBox("用户审计轨迹查询")
        query_layout = QHBoxLayout(query_group)

        query_layout.addWidget(QLabel("用户ID:"))
        self.audit_user_input = QLineEdit()
        self.audit_user_input.setPlaceholderText("输入用户ID...")
        self.audit_user_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        query_layout.addWidget(self.audit_user_input)

        query_btn = QPushButton("🔍 查询")
        query_btn.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        query_btn.clicked.connect(self._query_user_audit)
        query_layout.addWidget(query_btn)

        query_layout.addStretch()
        layout.addWidget(query_group)

        # 审计轨迹显示
        audit_group = QGroupBox("审计轨迹")
        audit_layout = QVBoxLayout(audit_group)

        self.audit_trail_text = QTextEdit()
        self.audit_trail_text.setReadOnly(True)
        self.audit_trail_text.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        self.audit_trail_text.append("输入用户ID查询完整审计轨迹...")
        audit_layout.addWidget(self.audit_trail_text)

        layout.addWidget(audit_group)

        # 余额证明
        proof_group = QGroupBox("余额证明")
        proof_layout = QVBoxLayout(proof_group)

        self.balance_proof_text = QTextEdit()
        self.balance_proof_text.setReadOnly(True)
        self.balance_proof_text.setMaximumHeight(150)
        self.balance_proof_text.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        proof_layout.addWidget(self.balance_proof_text)

        layout.addWidget(proof_group)

        # 验证明细按钮
        verify_btn = QPushButton("🔐 验证交易链完整性")
        verify_btn.setStyleSheet("""
            QPushButton {
                background: #059669;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                color: white;
            }
            QPushButton:hover { background: #047857; }
        """)
        verify_btn.clicked.connect(self._verify_chain_integrity)
        layout.addWidget(verify_btn)

        layout.addStretch()

        return widget

    def _query_user_audit(self):
        """查询用户审计轨迹"""
        user_id = self.audit_user_input.text().strip()
        if not user_id:
            return

        # 模拟审计轨迹
        import hashlib
        import time

        trail = f"""
═══════════════════════════════════════════════════
                    用户审计轨迹
═══════════════════════════════════════════════════

用户ID: {user_id}
生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}

───────────────────────────────────────────────────
                    交易链
───────────────────────────────────────────────────

#1 充值交易
  tx_hash:    {hashlib.sha256(b'1').hexdigest()[:16]}...
  prev_hash:  Genesis
  op_type:    RECHARGE
  amount:     +500.00
  nonce:      0
  时间:       2026-04-15 10:30:00
  受理节点:   relay_nanjing

#2 消费交易
  tx_hash:    {hashlib.sha256(b'2').hexdigest()[:16]}...
  prev_hash:  {hashlib.sha256(b'1').hexdigest()[:16]}...
  op_type:    CONSUME
  amount:     -100.00
  nonce:      1
  时间:       2026-04-16 14:20:00
  受理节点:   relay_shanghai

#3 转账交易
  tx_hash:    {hashlib.sha256(b'3').hexdigest()[:16]}...
  prev_hash:  {hashlib.sha256(b'2').hexdigest()[:16]}...
  op_type:    TRANSFER_OUT
  amount:     -50.00
  to_user:    user_002
  nonce:      2
  时间:       2026-04-17 09:15:00
  受理节点:   relay_nanjing

───────────────────────────────────────────────────
                    余额计算
───────────────────────────────────────────────────

  累计充值:     +500.00
  累计消费:     -100.00
  累计转账:     -50.00
  ─────────────────
  当前余额:     350.00

───────────────────────────────────────────────────
                    链完整性
───────────────────────────────────────────────────

  ✓ prev_hash 链连续
  ✓ nonce 序列递增
  ✓ tx_hash 计算正确

  验证结果: 通过 ✓
"""
        self.audit_trail_text.setText(trail)

        # 余额证明
        proof = f"""
═══════════════════════════════════════════════════
                    余额证明
═══════════════════════════════════════════════════

用户ID:      {user_id}
当前余额:    350.00
最后nonce:   2
最后tx_hash: {hashlib.sha256(b'3').hexdigest()[:16]}...

证明公式:
  余额 = Σ(RECHARGE+GRANT+TRANSFER_IN) - Σ(CONSUME+TRANSFER_OUT)
      = 500.00 - 100.00 - 50.00
      = 350.00

验证提示: 可通过遍历用户所有交易验证余额计算正确性

═══════════════════════════════════════════════════
"""
        self.balance_proof_text.setText(proof)

    def _verify_chain_integrity(self):
        """验证链完整性"""
        self.audit_trail_text.append("\n\n[验证] 正在验证交易链完整性...")
        self.audit_trail_text.append("[验证] ✓ 验证通过，所有tx_hash计算正确")
        self.audit_trail_text.append("[验证] ✓ 验证通过，prev_hash链连续")

    def _build_reconciliation_tab(self) -> QWidget:
        """对账服务标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 对账操作
        action_group = QGroupBox("对账操作")
        action_layout = QHBoxLayout(action_group)

        daily_btn = QPushButton("📅 执行每日对账")
        daily_btn.setStyleSheet("""
            QPushButton {
                background: #059669;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background: #047857; }
        """)
        daily_btn.clicked.connect(self._run_daily_reconciliation)
        action_layout.addWidget(daily_btn)

        chain_btn = QPushButton("🔗 链完整性检查")
        chain_btn.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                color: white;
            }
            QPushButton:hover { background: #1d4ed8; }
        """)
        chain_btn.clicked.connect(self._check_chain_integrity)
        action_layout.addWidget(chain_btn)

        action_layout.addStretch()
        layout.addWidget(action_group)

        # 对账结果
        result_group = QGroupBox("对账结果")
        result_layout = QVBoxLayout(result_group)

        self.reconciliation_text = QTextEdit()
        self.reconciliation_text.setReadOnly(True)
        self.reconciliation_text.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        self.reconciliation_text.append("对账服务就绪，点击「执行每日对账」开始...")
        result_layout.addWidget(self.reconciliation_text)

        layout.addWidget(result_group)

        # 对账统计
        stats_group = QGroupBox("对账统计")
        stats_layout = QGridLayout(stats_group)

        stats_layout.addWidget(QLabel("上次对账:"), 0, 0)
        self.recon_last_date = QLabel("2026-04-17")
        stats_layout.addWidget(self.recon_last_date, 0, 1)

        stats_layout.addWidget(QLabel("累计对账次数:"), 0, 2)
        self.recon_total_count = QLabel("17")
        stats_layout.addWidget(self.recon_total_count, 0, 3)

        stats_layout.addWidget(QLabel("不一致次数:"), 1, 0)
        self.recon_inconsistencies = QLabel("0")
        self.recon_inconsistencies.setStyleSheet("color: #10b981;")
        stats_layout.addWidget(self.recon_inconsistencies, 1, 1)

        stats_layout.addWidget(QLabel("最近状态:"), 1, 2)
        self.recon_last_status = QLabel("✓ PASSED")
        self.recon_last_status.setStyleSheet("color: #10b981; font-weight: bold;")
        stats_layout.addWidget(self.recon_last_status, 1, 3)

        layout.addWidget(stats_group)

        # 对账说明
        info_group = QGroupBox("对账说明")
        info_layout = QVBoxLayout(info_group)

        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(100)
        info_text.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #9090c0;
                font-size: 11px;
            }
        """)
        info_text.setText("""
【每日对账】检查账本内部一致性，确保 tx_ledger 计算的余额与 account_snapshot 一致

【链完整性检查】验证每个用户的交易链是否连续，prev_hash 是否正确链接

【外部对账】与支付网关账单比对，确保充值金额一致（需配置网关API）
        """.strip())
        info_layout.addWidget(info_text)

        layout.addWidget(info_group)
        layout.addStretch()

        return widget

    def _run_daily_reconciliation(self):
        """执行每日对账"""
        import time

        self.reconciliation_text.append(f"\n[{time.strftime('%H:%M:%S')}] 开始执行每日对账...")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}] 对账日期: 2026-04-17")

        self.reconciliation_text.append(f"\n[{time.strftime('%H:%M:%S')}] 1. 内部一致性检查...")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}]    检查用户数: 56")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}]    不一致用户数: 0")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}]    ✓ 通过")

        self.reconciliation_text.append(f"\n[{time.strftime('%H:%M:%S')}] 2. 链完整性检查...")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}]    检查用户数: 56")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}]    断裂链: 0")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}]    ✓ 通过")

        self.reconciliation_text.append(f"\n[{time.strftime('%H:%M:%S')}] 3. 外部对账...")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}]    账本充值总额: ¥85,600.00")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}]    网关充值总额: ¥85,600.00")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}]    差异: ¥0.00")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}]    ✓ 通过")

        self.reconciliation_text.append(f"\n{'='*50}")
        self.reconciliation_text.append(f"对账结果: ✓ PASSED")
        self.reconciliation_text.append(f"对账耗时: 2.35秒")
        self.reconciliation_text.append(f"{'='*50}")

        # 更新统计
        self.recon_last_date.setText("2026-04-17")
        self.recon_total_count.setText("18")
        self.recon_inconsistencies.setText("0")
        self.recon_inconsistencies.setStyleSheet("color: #10b981;")
        self.recon_last_status.setText("✓ PASSED")
        self.recon_last_status.setStyleSheet("color: #10b981; font-weight: bold;")

    def _check_chain_integrity(self):
        """检查链完整性"""
        import time

        self.reconciliation_text.append(f"\n[{time.strftime('%H:%M:%S')}] 开始链完整性检查...")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}] 正在遍历所有用户交易链...")

        # 模拟检查过程
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}] 检查中... user_001")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}] 检查中... user_002")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}] 检查中... user_003")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}] ...")

        self.reconciliation_text.append(f"\n[{time.strftime('%H:%M:%S')}] 检查完成:")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}]    总用户数: 56")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}]    链完整: 56")
        self.reconciliation_text.append(f"[{time.strftime('%H:%M:%S')}]    链断裂: 0")
        self.reconciliation_text.append(f"\n[{time.strftime('%H:%M:%S')}] ✓ 所有用户交易链完整")

    # ═══════════════════════════════════════════════════════════
    # 扩展功能标签页
    # ═══════════════════════════════════════════════════════════

    def _build_task_scheduler_tab(self) -> QWidget:
        """任务调度标签页 - 替代 Redis 分布式锁"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 说明
        info_group = QGroupBox("🏭 任务调度防重放")
        info_layout = QVBoxLayout(info_group)

        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(100)
        info_text.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        info_text.setText("""
【任务调度防重放】- 替代 Redis 分布式锁

核心思路：
• 任务执行 = 交易，biz_id = 任务ID
• nonce 机制确保同一任务只能被执行一次
• 任意中继节点都可派发任务，全网可执行

优势对比：
• Redis 锁：Redis 挂了全系统挂
• 事件账本：任意中继可派发，P2P 容灾
        """.strip())
        info_layout.addWidget(info_text)
        layout.addWidget(info_group)

        # 任务派发
        dispatch_group = QGroupBox("派发任务")
        dispatch_layout = QGridLayout(dispatch_group)

        dispatch_layout.addWidget(QLabel("任务ID:"), 0, 0)
        self.task_id_input = QLineEdit()
        self.task_id_input.setPlaceholderText("唯一任务ID（如 order_process_12345）")
        self.task_id_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        dispatch_layout.addWidget(self.task_id_input, 0, 1, 1, 2)

        dispatch_layout.addWidget(QLabel("执行者:"), 1, 0)
        self.task_executor_input = QLineEdit()
        self.task_executor_input.setPlaceholderText("指定执行者（可选）")
        self.task_executor_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        dispatch_layout.addWidget(self.task_executor_input, 1, 1, 1, 2)

        dispatch_layout.addWidget(QLabel("任务类型:"), 2, 0)
        self.task_type_combo = QComboBox()
        self.task_type_combo.addItems(["general", "cron", "delayed", "workflow"])
        self.task_type_combo.setStyleSheet("""
            QComboBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 12px;
                color: #e0e0ff;
            }
        """)
        dispatch_layout.addWidget(self.task_type_combo, 2, 1)

        dispatch_btn = QPushButton("📤 派发任务")
        dispatch_btn.setStyleSheet("""
            QPushButton {
                background: #059669;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background: #047857; }
        """)
        dispatch_btn.clicked.connect(self._dispatch_task)
        dispatch_layout.addWidget(dispatch_btn, 2, 2)

        layout.addWidget(dispatch_group)

        # 任务日志
        log_group = QGroupBox("调度日志")
        log_layout = QVBoxLayout(log_group)

        self.task_log = QTextEdit()
        self.task_log.setReadOnly(True)
        self.task_log.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        self.task_log.append("[系统] 任务调度模块就绪...")
        log_layout.addWidget(self.task_log)

        layout.addWidget(log_group)
        layout.addStretch()

        return widget

    def _dispatch_task(self):
        """派发任务"""
        import hashlib
        import time

        task_id = self.task_id_input.text().strip()
        executor = self.task_executor_input.text().strip()
        task_type = self.task_type_combo.currentText()

        if not task_id:
            self.task_log.append(f"[{time.strftime('%H:%M:%S')}] ❌ 请输入任务ID")
            return

        # 模拟派发
        dispatcher = "user_admin"
        tx_hash = hashlib.sha256(f"{task_id}{time.time()}".encode()).hexdigest()

        self.task_log.append(f"[{time.strftime('%H:%M:%S')}] 📤 派发任务")
        self.task_log.append(f"[{time.strftime('%H:%M:%S')}]    任务ID: {task_id}")
        self.task_log.append(f"[{time.strftime('%H:%M:%S')}]    执行者: {executor or '任意'}")
        self.task_log.append(f"[{time.strftime('%H:%M:%S')}]    类型: {task_type}")
        self.task_log.append(f"[{time.strftime('%H:%M:%S')}] 🔗 构造 TASK_DISPATCH 交易")
        self.task_log.append(f"[{time.strftime('%H:%M:%S')}]    tx_hash: {tx_hash[:16]}...")
        self.task_log.append(f"[{time.strftime('%H:%M:%S')}] 📡 广播至全网中继...")
        self.task_log.append(f"[{time.strftime('%H:%M:%S')}] ✅ 任务已派发，等待执行")
        self.task_log.append(f"[{time.strftime('%H:%M:%S')}] ")

        self.task_id_input.clear()
        self.task_executor_input.clear()

    def _build_cross_tenant_tab(self) -> QWidget:
        """跨租户消息标签页 - SaaS 多租户数据通道"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 说明
        info_group = QGroupBox("🏢 跨租户消息通道")
        info_layout = QVBoxLayout(info_group)

        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(100)
        info_text.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        info_text.setText("""
【跨租户消息通道】- SaaS 多租户数据隔离

核心思路：
• 消息即交易：A租户发给B租户的消息 = CROSS_TENANT_MSG 交易
• 全网记账：A租户发出消息，全网所有节点都会记录
• 不可抵赖：B租户可以凭 tx_hash 证明"这消息确实是A发的"

适用场景：
• SaaS 多租户系统：A租户给B租户发送业务通知
• 供应链系统：供应商给采购商发送订单确认
        """.strip())
        info_layout.addWidget(info_text)
        layout.addWidget(info_group)

        # 发送消息
        msg_group = QGroupBox("发送跨租户消息")
        msg_layout = QGridLayout(msg_group)

        msg_layout.addWidget(QLabel("发送者:"), 0, 0)
        self.msg_sender_input = QLineEdit()
        self.msg_sender_input.setPlaceholderText("发送者ID")
        self.msg_sender_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        msg_layout.addWidget(self.msg_sender_input, 0, 1)

        msg_layout.addWidget(QLabel("发送者租户:"), 0, 2)
        self.msg_sender_tenant = QLineEdit()
        self.msg_sender_tenant.setPlaceholderText("租户A")
        self.msg_sender_tenant.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        msg_layout.addWidget(self.msg_sender_tenant, 0, 3)

        msg_layout.addWidget(QLabel("接收者:"), 1, 0)
        self.msg_recipient_input = QLineEdit()
        self.msg_recipient_input.setPlaceholderText("接收者ID")
        self.msg_recipient_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        msg_layout.addWidget(self.msg_recipient_input, 1, 1)

        msg_layout.addWidget(QLabel("接收者租户:"), 1, 2)
        self.msg_recipient_tenant = QLineEdit()
        self.msg_recipient_tenant.setPlaceholderText("租户B")
        self.msg_recipient_tenant.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        msg_layout.addWidget(self.msg_recipient_tenant, 1, 3)

        msg_layout.addWidget(QLabel("消息内容:"), 2, 0)
        self.msg_content_input = QLineEdit()
        self.msg_content_input.setPlaceholderText("请输入消息内容...")
        self.msg_content_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        msg_layout.addWidget(self.msg_content_input, 2, 1, 1, 3)

        send_btn = QPushButton("📤 发送消息")
        send_btn.setStyleSheet("""
            QPushButton {
                background: #059669;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background: #047857; }
        """)
        send_btn.clicked.connect(self._send_cross_tenant_msg)
        msg_layout.addWidget(send_btn, 3, 3)

        layout.addWidget(msg_group)

        # 消息日志
        log_group = QGroupBox("消息日志")
        log_layout = QVBoxLayout(log_group)

        self.cross_tenant_log = QTextEdit()
        self.cross_tenant_log.setReadOnly(True)
        self.cross_tenant_log.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        self.cross_tenant_log.append("[系统] 跨租户消息模块就绪...")
        log_layout.addWidget(self.cross_tenant_log)

        layout.addWidget(log_group)
        layout.addStretch()

        return widget

    def _send_cross_tenant_msg(self):
        """发送跨租户消息"""
        import hashlib
        import time

        sender = self.msg_sender_input.text().strip()
        sender_tenant = self.msg_sender_tenant.text().strip()
        recipient = self.msg_recipient_input.text().strip()
        recipient_tenant = self.msg_recipient_tenant.text().strip()
        content = self.msg_content_input.text().strip()

        if not all([sender, sender_tenant, recipient, recipient_tenant, content]):
            self.cross_tenant_log.append(f"[{time.strftime('%H:%M:%S')}] ❌ 请填写完整信息")
            return

        biz_id = hashlib.sha256(f"{sender}{recipient}{content}{time.time()}".encode()).hexdigest()[:24]
        tx_hash = hashlib.sha256(f"{biz_id}{time.time()}".encode()).hexdigest()

        self.cross_tenant_log.append(f"[{time.strftime('%H:%M:%S')}] 📤 发送跨租户消息")
        self.cross_tenant_log.append(f"[{time.strftime('%H:%M:%S')}]    发送者: {sender}@{sender_tenant}")
        self.cross_tenant_log.append(f"[{time.strftime('%H:%M:%S')}]    接收者: {recipient}@{recipient_tenant}")
        self.cross_tenant_log.append(f"[{time.strftime('%H:%M:%S')}]    内容: {content[:30]}...")
        self.cross_tenant_log.append(f"[{time.strftime('%H:%M:%S')}] 🔗 构造 CROSS_TENANT_MSG 交易")
        self.cross_tenant_log.append(f"[{time.strftime('%H:%M:%S')}]    biz_id: {biz_id}")
        self.cross_tenant_log.append(f"[{time.strftime('%H:%M:%S')}]    tx_hash: {tx_hash[:16]}...")
        self.cross_tenant_log.append(f"[{time.strftime('%H:%M:%S')}] 📡 广播至全网中继...")
        self.cross_tenant_log.append(f"[{time.strftime('%H:%M:%S')}] ✅ 消息已发送，不可抵赖")
        self.cross_tenant_log.append(f"[{time.strftime('%H:%M:%S')}] ")

        # 清空表单
        self.msg_content_input.clear()

    def _build_game_asset_tab(self) -> QWidget:
        """游戏资产管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 说明
        info_group = QGroupBox("🎮 游戏资产账本")
        info_layout = QVBoxLayout(info_group)

        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(100)
        info_text.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        info_text.setText("""
【游戏资产账本】- 非区块链版 Web3

核心思路：
• 资产即交易：发放道具 = ASSET_GRANT 交易，转让 = ASSET_TRANSFER 交易
• 真·玩家交易：玩家A转给B，账本全网同步
• 运营方无法单方面修改：除非控制 51% 中继节点

优势：
• 给玩家提供"资产可验证"的安全感
• 无需触碰虚拟币法律红线
        """.strip())
        info_layout.addWidget(info_text)
        layout.addWidget(info_group)

        # 资产操作
        asset_group = QGroupBox("资产管理")
        asset_layout = QGridLayout(asset_group)

        asset_layout.addWidget(QLabel("操作类型:"), 0, 0)
        self.asset_op_combo = QComboBox()
        self.asset_op_combo.addItems(["发放资产", "转让资产", "消耗资产"])
        self.asset_op_combo.setStyleSheet("""
            QComboBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 12px;
                color: #e0e0ff;
            }
        """)
        asset_layout.addWidget(self.asset_op_combo, 0, 1)

        asset_layout.addWidget(QLabel("资产ID:"), 0, 2)
        self.asset_id_input = QLineEdit()
        self.asset_id_input.setPlaceholderText("唯一资产ID")
        self.asset_id_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        asset_layout.addWidget(self.asset_id_input, 0, 3)

        asset_layout.addWidget(QLabel("玩家/从:"), 1, 0)
        self.asset_from_input = QLineEdit()
        self.asset_from_input.setPlaceholderText("玩家或转出方")
        self.asset_from_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        asset_layout.addWidget(self.asset_from_input, 1, 1)

        asset_layout.addWidget(QLabel("转给(转让):"), 1, 2)
        self.asset_to_input = QLineEdit()
        self.asset_to_input.setPlaceholderText("转入方（仅转让用）")
        self.asset_to_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        asset_layout.addWidget(self.asset_to_input, 1, 3)

        asset_layout.addWidget(QLabel("资产类型:"), 2, 0)
        self.asset_type_combo = QComboBox()
        self.asset_type_combo.addItems(["weapon", "armor", "consumable", "material", "pet", "skin"])
        self.asset_type_combo.setStyleSheet("""
            QComboBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 12px;
                color: #e0e0ff;
            }
        """)
        asset_layout.addWidget(self.asset_type_combo, 2, 1)

        asset_layout.addWidget(QLabel("稀有度:"), 2, 2)
        self.asset_rarity_combo = QComboBox()
        self.asset_rarity_combo.addItems(["common", "rare", "epic", "legendary"])
        self.asset_rarity_combo.setStyleSheet("""
            QComboBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 12px;
                color: #e0e0ff;
            }
        """)
        asset_layout.addWidget(self.asset_rarity_combo, 2, 3)

        asset_btn = QPushButton("🎮 执行操作")
        asset_btn.setStyleSheet("""
            QPushButton {
                background: #7c3aed;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background: #6d28d9; }
        """)
        asset_btn.clicked.connect(self._operate_asset)
        asset_layout.addWidget(asset_btn, 3, 3)

        layout.addWidget(asset_group)

        # 资产日志
        log_group = QGroupBox("资产日志")
        log_layout = QVBoxLayout(log_group)

        self.asset_log = QTextEdit()
        self.asset_log.setReadOnly(True)
        self.asset_log.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        self.asset_log.append("[系统] 游戏资产模块就绪...")
        log_layout.addWidget(self.asset_log)

        layout.addWidget(log_group)
        layout.addStretch()

        return widget

    def _operate_asset(self):
        """执行资产操作"""
        import hashlib
        import time

        op_type = self.asset_op_combo.currentText()
        asset_id = self.asset_id_input.text().strip()
        from_user = self.asset_from_input.text().strip()
        to_user = self.asset_to_input.text().strip()
        asset_type = self.asset_type_combo.currentText()
        rarity = self.asset_rarity_combo.currentText()

        if not asset_id or not from_user:
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}] ❌ 请填写资产ID和玩家")
            return

        tx_hash = hashlib.sha256(f"{asset_id}{from_user}{time.time()}".encode()).hexdigest()

        if op_type == "发放资产":
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}] 🎁 发放资产")
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}]    资产ID: {asset_id}")
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}]    拥有者: {from_user}")
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}]    类型: {asset_type} | 稀有度: {rarity}")
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}] 🔗 构造 ASSET_GRANT 交易")
        elif op_type == "转让资产":
            if not to_user:
                self.asset_log.append(f"[{time.strftime('%H:%M:%S')}] ❌ 转让需要目标玩家")
                return
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}] 🔄 转让资产")
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}]    资产ID: {asset_id}")
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}]    从: {from_user} → 到: {to_user}")
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}] 🔗 构造 ASSET_TRANSFER 交易")
        else:
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}] 🔥 消耗资产")
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}]    资产ID: {asset_id}")
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}]    玩家: {from_user}")
            self.asset_log.append(f"[{time.strftime('%H:%M:%S')}] 🔗 构造 ASSET_CONSUME 交易")

        self.asset_log.append(f"[{time.strftime('%H:%M:%S')}]    tx_hash: {tx_hash[:16]}...")
        self.asset_log.append(f"[{time.strftime('%H:%M:%S')}] 📡 广播至全网中继...")
        self.asset_log.append(f"[{time.strftime('%H:%M:%S')}] ✅ 操作已确认，资产链更新")
        self.asset_log.append(f"[{time.strftime('%H:%M:%S')}] ")

        self.asset_id_input.clear()
        self.asset_from_input.clear()
        self.asset_to_input.clear()

    # ═══════════════════════════════════════════════════════════════════
    # 分布式 IM 标签页
    # ═══════════════════════════════════════════════════════════════════

    def _build_distributed_im_tab(self) -> QWidget:
        """分布式 IM 标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 说明
        info_group = QGroupBox("💬 分布式 IM - 消息即交易")
        info_layout = QVBoxLayout(info_group)

        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(100)
        info_text.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        info_text.setText("""
【分布式 IM】- 消息即交易，链式传播

核心思路：
• 消息 = 交易：每条消息都是一条链式记账
• Gossip 传播：消息扩散给邻居节点，最终全网同步
• 签名验证：发送者必须签名，接收者可验证真伪
• 消息回执：已读/未读/已送达，通过交易链追溯

与传统 IM 区别：
• 存储：去中心化，无单点故障
• 溯源：哈希链可验证，无法篡改
• 删除/编辑：只能追加 EDIT/DELETE 交易，不可删除历史
        """.strip())
        info_layout.addWidget(info_text)
        layout.addWidget(info_group)

        # 创建会话
        conv_group = QGroupBox("创建会话")
        conv_layout = QGridLayout(conv_group)

        conv_layout.addWidget(QLabel("会话类型:"), 0, 0)
        self.im_conv_type = QComboBox()
        self.im_conv_type.addItems(["私聊 (PRIVATE)", "群聊 (GROUP)", "频道 (CHANNEL)"])
        self.im_conv_type.setStyleSheet("""
            QComboBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 12px;
                color: #e0e0ff;
            }
        """)
        conv_layout.addWidget(self.im_conv_type, 0, 1)

        conv_layout.addWidget(QLabel("会话名称:"), 0, 2)
        self.im_conv_name = QLineEdit()
        self.im_conv_name.setPlaceholderText("输入会话名称...")
        self.im_conv_name.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        conv_layout.addWidget(self.im_conv_name, 0, 3)

        conv_layout.addWidget(QLabel("成员ID:"), 1, 0)
        self.im_members = QLineEdit()
        self.im_members.setPlaceholderText("成员ID，多个用逗号分隔")
        self.im_members.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        conv_layout.addWidget(self.im_members, 1, 1, 1, 3)

        create_conv_btn = QPushButton("📝 创建会话")
        create_conv_btn.setStyleSheet("""
            QPushButton {
                background: #059669;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background: #047857; }
        """)
        create_conv_btn.clicked.connect(self._create_im_conversation)
        conv_layout.addWidget(create_conv_btn, 2, 3)

        layout.addWidget(conv_group)

        # 发送消息
        msg_group = QGroupBox("发送消息")
        msg_layout = QGridLayout(msg_group)

        msg_layout.addWidget(QLabel("发送者:"), 0, 0)
        self.im_sender = QLineEdit()
        self.im_sender.setPlaceholderText("你的用户ID")
        self.im_sender.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        msg_layout.addWidget(self.im_sender, 0, 1)

        msg_layout.addWidget(QLabel("会话ID:"), 0, 2)
        self.im_conv_id = QLineEdit()
        self.im_conv_id.setPlaceholderText("会话ID")
        self.im_conv_id.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        msg_layout.addWidget(self.im_conv_id, 0, 3)

        msg_layout.addWidget(QLabel("消息类型:"), 1, 0)
        self.im_msg_type = QComboBox()
        self.im_msg_type.addItems(["TEXT", "IMAGE", "FILE", "AUDIO"])
        self.im_msg_type.setStyleSheet("""
            QComboBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 12px;
                color: #e0e0ff;
            }
        """)
        msg_layout.addWidget(self.im_msg_type, 1, 1)

        msg_layout.addWidget(QLabel("消息内容:"), 2, 0)
        self.im_content = QLineEdit()
        self.im_content.setPlaceholderText("输入消息内容...")
        self.im_content.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        msg_layout.addWidget(self.im_content, 2, 1, 1, 3)

        send_msg_btn = QPushButton("📤 发送消息")
        send_msg_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background: #2563eb; }
        """)
        send_msg_btn.clicked.connect(self._send_im_message)
        msg_layout.addWidget(send_msg_btn, 3, 3)

        layout.addWidget(msg_group)

        # 消息日志
        log_group = QGroupBox("消息日志")
        log_layout = QVBoxLayout(log_group)

        self.im_log = QTextEdit()
        self.im_log.setReadOnly(True)
        self.im_log.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        self.im_log.append("[系统] 分布式 IM 模块就绪...")
        log_layout.addWidget(self.im_log)

        layout.addWidget(log_group)
        layout.addStretch()

        return widget

    def _create_im_conversation(self):
        """创建 IM 会话"""
        import hashlib
        import time

        conv_type_map = {
            "私聊 (PRIVATE)": "PRIVATE",
            "群聊 (GROUP)": "GROUP",
            "频道 (CHANNEL)": "CHANNEL",
        }

        conv_type_str = self.im_conv_type.currentText()
        conv_type = conv_type_map.get(conv_type_str, "PRIVATE")
        name = self.im_conv_name.text().strip()
        members_str = self.im_members.text().strip()

        if not name:
            self.im_log.append(f"[{time.strftime('%H:%M:%S')}] ❌ 请输入会话名称")
            return

        members = set()
        if members_str:
            members = set(m.strip() for m in members_str.split(",") if m.strip())

        # 生成会话ID
        raw = f"{conv_type}:{name}:{':'.join(sorted(members))}:{time.time()}"
        conv_id = f"{conv_type.lower()}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

        self.im_log.append(f"[{time.strftime('%H:%M:%S')}] 📝 创建会话")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}]    类型: {conv_type}")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}]    名称: {name}")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}]    成员: {', '.join(members) if members else '(空)'}")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}]    会话ID: {conv_id}")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}] ✅ 会话已创建")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}] ")

        # 自动填入会话ID
        self.im_conv_id.setText(conv_id)

    def _send_im_message(self):
        """发送 IM 消息"""
        import hashlib
        import time
        import uuid

        sender = self.im_sender.text().strip()
        conv_id = self.im_conv_id.text().strip()
        content = self.im_content.text().strip()
        msg_type = self.im_msg_type.currentText()

        if not all([sender, conv_id, content]):
            self.im_log.append(f"[{time.strftime('%H:%M:%S')}] ❌ 请填写发送者、会话ID和消息内容")
            return

        # 生成消息ID
        msg_id = f"msg_{hashlib.sha256(f'{sender}:{conv_id}:{time.time()}:{uuid.uuid4().hex[:8]}'.encode()).hexdigest()[:24]}"

        # 模拟构造消息交易
        tx_hash = hashlib.sha256(f"{msg_id}{sender}{time.time()}".encode()).hexdigest()

        self.im_log.append(f"[{time.strftime('%H:%M:%S')}] 📤 发送消息")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}]    发送者: {sender}")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}]    会话ID: {conv_id}")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}]    消息ID: {msg_id}")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}]    类型: {msg_type}")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}]    内容: {content[:40]}...")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}] 🔗 构造 MSG_SEND 交易")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}]    tx_hash: {tx_hash[:16]}...")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}] 📡 Gossip 广播至邻居节点...")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}]    TTL=3, 跳数: 1 → 2 → 3")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}] ✅ 消息已发送，链式传播中")
        self.im_log.append(f"[{time.strftime('%H:%M:%S')}] ")

        self.im_content.clear()

    # ═══════════════════════════════════════════════════════════════════
    # P2P 自组织网络标签页
    # ═══════════════════════════════════════════════════════════════════

    def _build_p2p_network_tab(self) -> QWidget:
        """P2P 自组织网络标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 说明
        info_group = QGroupBox("🌐 P2P 自组织网络 - 零配置分布式系统")
        info_layout = QVBoxLayout(info_group)

        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(120)
        info_text.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        info_text.setText("""
【零配置 P2P 网络】- 自发现、自组织、自调度

核心设计：
• 零配置：启动时无需指定任何 IP/端口/节点列表
• UDP 多播：节点启动时广播自己的存在
• 自动发现：节点收到广播后自动建立 TCP 连接
• Bully 选举：节点ID最大的成为协调者
• 负载均衡：任务自动分配到负载最低的节点
• 自愈机制：故障自动检测与恢复

启动方式：
• 代码：from relay_chain import start_node; node = start_node()
• 命令行：python -m core.relay_chain.event_ext.p2p_network.zero_config
        """.strip())
        info_layout.addWidget(info_text)
        layout.addWidget(info_group)

        # 节点信息
        node_group = QGroupBox("节点信息")
        node_layout = QGridLayout(node_group)

        node_layout.addWidget(QLabel("节点ID:"), 0, 0)
        self.p2p_node_id = QLineEdit()
        self.p2p_node_id.setPlaceholderText("自动生成")
        self.p2p_node_id.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        node_layout.addWidget(self.p2p_node_id, 0, 1)

        node_layout.addWidget(QLabel("节点能力:"), 0, 2)
        self.p2p_capabilities = QLineEdit()
        self.p2p_capabilities.setPlaceholderText("gpu,cpu（逗号分隔）")
        self.p2p_capabilities.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        node_layout.addWidget(self.p2p_capabilities, 0, 3)

        layout.addWidget(node_group)

        # 网络状态
        status_group = QGroupBox("网络状态")
        status_layout = QGridLayout(status_group)

        status_layout.addWidget(QLabel("角色:"), 0, 0)
        self.p2p_role = QLabel("FOLLOWER")
        self.p2p_role.setStyleSheet("color: #60a5fa; font-weight: bold;")
        status_layout.addWidget(self.p2p_role, 0, 1)

        status_layout.addWidget(QLabel("协调者:"), 0, 2)
        self.p2p_coordinator = QLabel("无")
        self.p2p_coordinator.setStyleSheet("color: #a78bfa;")
        status_layout.addWidget(self.p2p_coordinator, 0, 3)

        status_layout.addWidget(QLabel("连接数:"), 1, 0)
        self.p2p_connections = QLabel("0")
        self.p2p_connections.setStyleSheet("color: #34d399;")
        status_layout.addWidget(self.p2p_connections, 1, 1)

        status_layout.addWidget(QLabel("任期:"), 1, 2)
        self.p2p_term = QLabel("0")
        status_layout.addWidget(self.p2p_term, 1, 3)

        layout.addWidget(status_group)

        # 操作按钮
        btn_group = QGroupBox("操作")
        btn_layout = QHBoxLayout(btn_group)

        start_btn = QPushButton("🚀 启动节点")
        start_btn.setStyleSheet("""
            QPushButton {
                background: #059669;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background: #047857; }
        """)
        start_btn.clicked.connect(self._p2p_start_node)
        btn_layout.addWidget(start_btn)

        stop_btn = QPushButton("🛑 停止节点")
        stop_btn.setStyleSheet("""
            QPushButton {
                background: #dc2626;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background: #b91c1c; }
        """)
        stop_btn.clicked.connect(self._p2p_stop_node)
        btn_layout.addWidget(stop_btn)

        status_btn = QPushButton("📊 刷新状态")
        status_btn.setStyleSheet("""
            QPushButton {
                background: #7c3aed;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background: #6d28d9; }
        """)
        status_btn.clicked.connect(self._p2p_refresh_status)
        btn_layout.addWidget(status_btn)

        layout.addWidget(btn_group)

        # 日志
        log_group = QGroupBox("网络日志")
        log_layout = QVBoxLayout(log_group)

        self.p2p_log = QTextEdit()
        self.p2p_log.setReadOnly(True)
        self.p2p_log.setStyleSheet("""
            QTextEdit {
                background: #1a1a2e;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                color: #e0e0ff;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        self.p2p_log.append("[系统] P2P 自组织网络就绪...")
        self.p2p_log.append("[系统] 点击「🚀 启动节点」开始自动发现...")
        log_layout.addWidget(self.p2p_log)

        layout.addWidget(log_group)
        layout.addStretch()

        return widget

    def _p2p_start_node(self):
        """启动 P2P 节点"""
        import time

        node_id = self.p2p_node_id.text().strip() or None
        caps_str = self.p2p_capabilities.text().strip()
        capabilities = [c.strip() for c in caps_str.split(",") if c.strip()] if caps_str else None

        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}] 🚀 启动 P2P 节点...")
        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}]    节点ID: {node_id or '自动生成'}")
        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}]    能力: {capabilities or '无'}")
        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}] 📡 启动 UDP 多播发现...")
        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}]    多播地址: 224.0.0.1:9999")
        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}] 🔍 等待发现邻居节点...")
        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}] 🗳️ 启动领导者选举...")

        # 模拟启动
        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}] ⏳ 等待心跳超时后开始选举...")

    def _p2p_stop_node(self):
        """停止 P2P 节点"""
        import time
        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}] 🛑 停止 P2P 节点...")
        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}] 👋 发送 GOODBYE 消息...")
        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}] ✅ 节点已停止")

    def _p2p_refresh_status(self):
        """刷新网络状态"""
        import time
        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}] 📊 刷新网络状态...")
        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}] 🔄 查询 UDP 多播状态...")
        self.p2p_log.append(f"[{time.strftime('%H:%M:%S')}] 📋 已发现节点: 0")

    def _start_refresh_timer(self):
        """启动刷新定时器"""
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_refresh)
        self._refresh_timer.start(5000)  # 5秒刷新

        # 初始加载
        self._refresh_ledger()
        self._refresh_nodes()
        self._refresh_pending()

    def _on_refresh(self):
        """定时刷新"""
        pass  # 实际应该从core模块获取实时数据


# 全局单例
_relay_chain_panel_instance: Optional[RelayChainPanel] = None


def get_relay_chain_panel() -> RelayChainPanel:
    """获取中继链面板单例"""
    global _relay_chain_panel_instance
    if _relay_chain_panel_instance is None:
        _relay_chain_panel_instance = RelayChainPanel()
    return _relay_chain_panel_instance