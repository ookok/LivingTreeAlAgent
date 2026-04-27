"""
DeCommerce PyQt6 管理面板
DeCommerce Management Panel

7个标签页:
1. 卖家中心 - 发布/管理商品服务
2. 买家市场 - 发现和购买服务
3. 会话管理 - 实时会话控制
4. 订单管理 - 支付和佣金
5. AI能力 - 一键上架AI服务
6. 穿透网络 - Edge Relay管理
7. 存证审计 - 证据记录与导出
"""

from typing import Dict, Any, Optional
import asyncio
import json
import logging
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QLineEdit, QTextEdit,
    QTableWidget, QTableWidgetItem, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QGroupBox, QSplitter,
    QListWidget, QListWidgetItem, QProgressBar,
    QStatusBar, QMessageBox, QDialog, QFormLayout,
    QScrollArea, QFrame, QGridLayout, QTableView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QAbstractTableModel
from PyQt6.QtGui import QFont, QIcon, QColor

logger = logging.getLogger(__name__)


class DeCommercePanel(QWidget):
    """
    DeCommerce 管理面板

    集成卖家节点、买家客户端、支付守卫、Edge Relay、AI能力、存证系统
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 组件引用
        self.seller_node = None
        self.buyer_client = None
        self.payment_guard = None
        self.edge_relay = None
        self.audit_trail = None
        self.ai_registry = None
        self.crdt_order = None
        self.tracker_url = "http://localhost:8765"

        # 状态
        self._is_seller_mode = False
        self._is_buyer_mode = False

        # 初始化UI
        self.init_ui()

        # 定时器
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_status)
        self._update_timer.start(5000)

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题栏
        title_bar = self._create_title_bar()
        layout.addWidget(title_bar)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_seller_tab(), "卖家中心")
        self.tabs.addTab(self._create_buyer_tab(), "买家市场")
        self.tabs.addTab(self._create_session_tab(), "会话管理")
        self.tabs.addTab(self._create_order_tab(), "订单管理")
        self.tabs.addTab(self._create_ai_capabilities_tab(), "AI能力")
        self.tabs.addTab(self._create_relay_network_tab(), "穿透网络")
        self.tabs.addTab(self._create_audit_tab(), "存证审计")

        layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        layout.addWidget(self.status_bar)

    def _create_title_bar(self) -> QWidget:
        """创建标题栏"""
        bar = QWidget()
        layout = QHBoxLayout(bar)

        title = QLabel("P2P 去中心化电商 (DeCommerce)")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        layout.addStretch()

        self.connection_status = QLabel("未连接")
        self.connection_status.setStyleSheet("color: gray;")
        layout.addWidget(self.connection_status)

        return bar

    # ==================== 卖家中心 ====================

    def _create_seller_tab(self) -> QWidget:
        """卖家中心标签页"""
        tab = QScrollArea()
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 连接控制
        group = QGroupBox("卖家节点控制")
        group_layout = QHBoxLayout(group)

        self.seller_status_label = QLabel("离线")
        group_layout.addWidget(QLabel("状态:"))
        group_layout.addWidget(self.seller_status_label)

        self.seller_start_btn = QPushButton("启动卖家节点")
        self.seller_start_btn.clicked.connect(self._start_seller_node)
        group_layout.addWidget(self.seller_start_btn)

        self.seller_stop_btn = QPushButton("停止")
        self.seller_stop_btn.clicked.connect(self._stop_seller_node)
        self.seller_stop_btn.setEnabled(False)
        group_layout.addWidget(self.seller_stop_btn)

        layout.addWidget(group)

        # 发布服务
        publish_group = QGroupBox("发布新服务")
        publish_layout = QFormLayout(publish_group)

        self.publish_title = QLineEdit()
        self.publish_title.setPlaceholderText("服务标题")
        publish_layout.addRow("标题:", self.publish_title)

        self.publish_desc = QTextEdit()
        self.publish_desc.setPlaceholderText("服务描述...")
        self.publish_desc.setMaximumHeight(80)
        publish_layout.addRow("描述:", self.publish_desc)

        self.publish_price = QSpinBox()
        self.publish_price.setRange(0, 999999)
        self.publish_price.setValue(100)
        self.publish_price.setSuffix(" 分")
        publish_layout.addRow("价格:", self.publish_price)

        self.publish_type = QComboBox()
        self.publish_type.addItems([
            "物理商品 (图文)",
            "远程实景直播",
            "AI计算服务",
            "远程代操作",
            "知识咨询",
            "数字商品",
        ])
        publish_layout.addRow("类型:", self.publish_type)

        self.publish_ai_model = QComboBox()
        self.publish_ai_model.addItems([
            "qwen2.5:0.5b",
            "llama3:8b",
            "qwen2.5:7b",
            "codellama:7b",
        ])
        self.publish_ai_model.setEnabled(False)
        publish_layout.addRow("AI模型:", self.publish_ai_model)

        self.publish_btn = QPushButton("发布服务")
        self.publish_btn.clicked.connect(self._publish_service)
        self.publish_btn.setEnabled(False)
        publish_layout.addRow("", self.publish_btn)

        layout.addWidget(publish_group)

        # 我的服务列表
        list_group = QGroupBox("我的服务")
        list_layout = QVBoxLayout(list_group)

        self.seller_list = QTableWidget()
        self.seller_list.setColumnCount(6)
        self.seller_list.setHorizontalHeaderLabels(["ID", "标题", "类型", "价格", "状态", "订单数"])
        list_layout.addWidget(self.seller_list)

        list_btn_layout = QHBoxLayout()
        self.refresh_seller_list_btn = QPushButton("刷新")
        self.refresh_seller_list_btn.clicked.connect(self._refresh_seller_list)
        list_btn_layout.addWidget(self.refresh_seller_list_btn)

        self.unpublish_btn = QPushButton("下架")
        self.unpublish_btn.clicked.connect(self._unpublish_service)
        list_btn_layout.addWidget(self.unpublish_btn)

        list_layout.addLayout(list_btn_layout)

        layout.addWidget(list_group)

        layout.addStretch()
        tab.setWidget(widget)
        return tab

    # ==================== 买家市场 ====================

    def _create_buyer_tab(self) -> QWidget:
        """买家市场标签页"""
        tab = QScrollArea()
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 连接控制
        group = QGroupBox("买家客户端控制")
        group_layout = QHBoxLayout(group)

        self.buyer_status_label = QLabel("未连接")
        group_layout.addWidget(QLabel("状态:"))
        group_layout.addWidget(self.buyer_status_label)

        self.buyer_connect_btn = QPushButton("连接市场")
        self.buyer_connect_btn.clicked.connect(self._connect_buyer)
        group_layout.addWidget(self.buyer_connect_btn)

        self.buyer_refresh_btn = QPushButton("刷新目录")
        self.buyer_refresh_btn.clicked.connect(self._refresh_catalog)
        self.buyer_refresh_btn.setEnabled(False)
        group_layout.addWidget(self.buyer_refresh_btn)

        layout.addWidget(group)

        # 搜索
        search_group = QGroupBox("搜索服务")
        search_layout = QHBoxLayout(search_group)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索关键词...")
        self.search_input.returnPressed.connect(self._do_search)
        search_layout.addWidget(self.search_input)

        self.search_type = QComboBox()
        self.search_type.addItems(["全部", "远程直播", "AI计算", "远程协助", "知识咨询"])
        search_layout.addWidget(self.search_type)

        self.search_live_only = QCheckBox("仅实时可用")
        search_layout.addWidget(self.search_live_only)

        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self._do_search)
        search_layout.addWidget(search_btn)

        layout.addWidget(search_group)

        # 服务列表
        list_group = QGroupBox("服务目录")
        list_layout = QVBoxLayout(list_group)

        self.market_list = QTableWidget()
        self.market_list.setColumnCount(7)
        self.market_list.setHorizontalHeaderLabels(["ID", "卖家", "标题", "类型", "价格", "实时", "操作"])
        list_layout.addWidget(self.market_list)

        layout.addWidget(list_group)

        # 购买面板
        purchase_group = QGroupBox("购买服务")
        purchase_layout = QFormLayout(purchase_group)

        self.purchase_listing_id = QLineEdit()
        self.purchase_listing_id.setReadOnly(True)
        purchase_layout.addRow("服务ID:", self.purchase_listing_id)

        self.purchase_amount = QLabel("0 分")
        purchase_layout.addRow("金额:", self.purchase_amount)

        self.purchase_btn = QPushButton("立即购买")
        self.purchase_btn.clicked.connect(self._purchase_service)
        self.purchase_btn.setEnabled(False)
        purchase_layout.addRow("", self.purchase_btn)

        layout.addWidget(purchase_group)

        layout.addStretch()
        tab.setWidget(widget)
        return tab

    # ==================== 会话管理 ====================

    def _create_session_tab(self) -> QWidget:
        """会话管理标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 活跃会话
        group = QGroupBox("活跃会话")
        group_layout = QVBoxLayout(group)

        self.session_list = QTableWidget()
        self.session_list.setColumnCount(6)
        self.session_list.setHorizontalHeaderLabels(["会话ID", "商品", "买家", "状态", "时长", "操作"])
        group_layout.addWidget(self.session_list)

        btn_layout = QHBoxLayout()
        self.refresh_session_btn = QPushButton("刷新")
        self.refresh_session_btn.clicked.connect(self._refresh_sessions)
        btn_layout.addWidget(self.refresh_session_btn)

        self.end_session_btn = QPushButton("结束会话")
        self.end_session_btn.clicked.connect(self._end_session)
        btn_layout.addWidget(self.end_session_btn)

        group_layout.addLayout(btn_layout)
        layout.addWidget(group)

        # 会话详情
        detail_group = QGroupBox("会话详情")
        detail_layout = QVBoxLayout(detail_group)

        self.session_detail = QTextEdit()
        self.session_detail.setReadOnly(True)
        self.session_detail.setMaximumHeight(150)
        detail_layout.addWidget(self.session_detail)

        layout.addWidget(detail_group)

        # 心跳状态
        heartbeat_group = QGroupBox("心跳监控")
        heartbeat_layout = QFormLayout(heartbeat_group)

        self.heartbeat_seller = QLabel("-")
        self.heartbeat_buyer = QLabel("-")
        heartbeat_layout.addRow("卖家心跳:", self.heartbeat_seller)
        heartbeat_layout.addRow("买家心跳:", self.heartbeat_buyer)

        layout.addWidget(heartbeat_group)

        return tab

    # ==================== 订单管理 ====================

    def _create_order_tab(self) -> QWidget:
        """订单管理标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 统计
        stats_group = QGroupBox("订单统计")
        stats_layout = QFormLayout(stats_group)

        self.order_total = QLabel("0")
        self.order_frozen = QLabel("0")
        self.order_completed = QLabel("0")
        self.order_commission = QLabel("0 分")
        stats_layout.addRow("总订单:", self.order_total)
        stats_layout.addRow("冻结中:", self.order_frozen)
        stats_layout.addRow("已完成:", self.order_completed)
        stats_layout.addRow("总佣金:", self.order_commission)

        layout.addWidget(stats_group)

        # 订单列表
        list_group = QGroupBox("订单列表")
        list_layout = QVBoxLayout(list_group)

        self.order_list = QTableWidget()
        self.order_list.setColumnCount(7)
        self.order_list.setHorizontalHeaderLabels(["订单ID", "商品", "卖家", "买家", "金额", "佣金", "状态"])
        list_layout.addWidget(self.order_list)

        btn_layout = QHBoxLayout()
        self.refresh_order_btn = QPushButton("刷新")
        self.refresh_order_btn.clicked.connect(self._refresh_orders)
        btn_layout.addWidget(self.refresh_order_btn)

        self.refund_btn = QPushButton("退款")
        self.refund_btn.clicked.connect(self._refund_order)
        btn_layout.addWidget(self.refund_btn)

        list_layout.addLayout(btn_layout)

        layout.addWidget(list_group)

        return tab

    # ==================== 设置 ====================

    def _create_settings_tab(self) -> QWidget:
        """设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Tracker配置
        tracker_group = QGroupBox("Tracker服务器")
        tracker_layout = QFormLayout(tracker_group)

        self.tracker_url_input = QLineEdit()
        self.tracker_url_input.setText("http://localhost:8765")
        tracker_layout.addRow("服务器地址:", self.tracker_url_input)

        self.tracker_port = QSpinBox()
        self.tracker_port.setRange(1024, 65535)
        self.tracker_port.setValue(8765)
        tracker_layout.addRow("端口:", self.tracker_port)

        self.save_tracker_btn = QPushButton("保存")
        self.save_tracker_btn.clicked.connect(self._save_tracker_config)
        tracker_layout.addRow("", self.save_tracker_btn)

        layout.addWidget(tracker_group)

        # TURN配置
        turn_group = QGroupBox("TURN中继服务器")
        turn_layout = QFormLayout(turn_group)

        self.turn_url = QLineEdit()
        self.turn_url.setPlaceholderText("turn:your-server.com:3478")
        turn_layout.addRow("TURN URL:", self.turn_url)

        self.turn_user = QLineEdit()
        turn_layout.addRow("用户名:", self.turn_user)

        self.turn_credential = QLineEdit()
        self.turn_credential.setEchoMode(QLineEdit.EchoMode.Password)
        turn_layout.addRow("密码:", self.turn_credential)

        self.save_turn_btn = QPushButton("保存")
        self.save_turn_btn.clicked.connect(self._save_turn_config)
        turn_layout.addRow("", self.save_turn_btn)

        layout.addWidget(turn_group)

        # 佣金配置
        commission_group = QGroupBox("佣金设置")
        commission_layout = QFormLayout(commission_group)

        self.commission_rate = QDoubleSpinBox()
        self.commission_rate.setRange(0.0, 1.0)
        self.commission_rate.setSingleStep(0.01)
        self.commission_rate.setValue(0.05)
        self.commission_rate.setSuffix(" (5%)")
        commission_layout.addRow("佣金率:", self.commission_rate)

        self.min_commission = QSpinBox()
        self.min_commission.setRange(0, 1000)
        self.min_commission.setValue(1)
        self.min_commission.setSuffix(" 分")
        commission_layout.addRow("最低佣金:", self.min_commission)

        layout.addWidget(commission_group)

        # 本地服务端口
        port_group = QGroupBox("本地服务端口")
        port_layout = QFormLayout(port_group)

        self.local_port = QSpinBox()
        self.local_port.setRange(1024, 65535)
        self.local_port.setValue(8766)
        port_layout.addRow("HTTP端口:", self.local_port)

        layout.addWidget(port_group)

        layout.addStretch()

        return tab

    # ==================== AI能力 ====================

    def _create_ai_capabilities_tab(self) -> QWidget:
        """AI能力标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 工具栏
        toolbar = QHBoxLayout()

        self.discover_ai_btn = QPushButton("探测AI能力")
        self.discover_ai_btn.clicked.connect(self._discover_ai_capabilities)
        toolbar.addWidget(self.discover_ai_btn)

        self.publish_all_ai_btn = QPushButton("一键发布所有AI能力")
        self.publish_all_ai_btn.clicked.connect(self._publish_all_ai)
        toolbar.addWidget(self.publish_all_ai_btn)

        self.refresh_ai_btn = QPushButton("刷新")
        self.refresh_ai_btn.clicked.connect(self._refresh_ai_capabilities)
        toolbar.addWidget(self.refresh_ai_btn)

        layout.addLayout(toolbar)

        # 统计
        stats_group = QGroupBox("AI能力统计")
        stats_layout = QFormLayout(stats_group)

        self.ai_total_caps = QLabel("0")
        self.ai_available_caps = QLabel("0")
        self.ai_enabled_caps = QLabel("0")
        stats_layout.addRow("总能力数:", self.ai_total_caps)
        stats_layout.addRow("可用:", self.ai_available_caps)
        stats_layout.addRow("已启用:", self.ai_enabled_caps)

        layout.addWidget(stats_group)

        # 能力列表
        list_group = QGroupBox("AI能力列表")
        list_layout = QVBoxLayout(list_group)

        self.ai_cap_list = QTableWidget()
        self.ai_cap_list.setColumnCount(7)
        self.ai_cap_list.setHorizontalHeaderLabels(["能力ID", "类型", "模型", "后端", "显示名称", "可用", "启用"])
        list_layout.addWidget(self.ai_cap_list)

        btn_layout = QHBoxLayout()

        self.enable_ai_btn = QPushButton("启用")
        self.enable_ai_btn.clicked.connect(self._enable_ai_capability)
        btn_layout.addWidget(self.enable_ai_btn)

        self.disable_ai_btn = QPushButton("禁用")
        self.disable_ai_btn.clicked.connect(self._disable_ai_capability)
        btn_layout.addWidget(self.disable_ai_btn)

        self.publish_ai_btn = QPushButton("发布")
        self.publish_ai_btn.clicked.connect(self._publish_single_ai)
        btn_layout.addWidget(self.publish_ai_btn)

        list_layout.addLayout(btn_layout)

        layout.addWidget(list_group)

        return tab

    def _create_relay_network_tab(self) -> QWidget:
        """穿透网络标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 工具栏
        toolbar = QHBoxLayout()

        self.init_relay_btn = QPushButton("初始化Super Relay")
        self.init_relay_btn.clicked.connect(self._init_super_relay)
        toolbar.addWidget(self.init_relay_btn)

        self.add_edge_btn = QPushButton("添加Edge节点")
        self.add_edge_btn.clicked.connect(self._add_edge_relay)
        toolbar.addWidget(self.add_edge_btn)

        self.refresh_relay_btn = QPushButton("刷新")
        self.refresh_relay_btn.clicked.connect(self._refresh_relay_network)
        toolbar.addWidget(self.refresh_relay_btn)

        layout.addLayout(toolbar)

        # 网络统计
        stats_group = QGroupBox("网络统计")
        stats_layout = QFormLayout(stats_group)

        self.relay_total_nodes = QLabel("0")
        self.relay_healthy_nodes = QLabel("0")
        self.relay_total_sessions = QLabel("0")
        self.relay_active_sessions = QLabel("0")
        self.relay_utilization = QLabel("0%")

        stats_layout.addRow("总节点数:", self.relay_total_nodes)
        stats_layout.addRow("健康节点:", self.relay_healthy_nodes)
        stats_layout.addRow("总会话数:", self.relay_total_sessions)
        stats_layout.addRow("活跃会话:", self.relay_active_sessions)
        stats_layout.addRow("利用率:", self.relay_utilization)

        layout.addWidget(stats_group)

        # 节点列表
        list_group = QGroupBox("节点列表")
        list_layout = QVBoxLayout(list_group)

        self.relay_node_list = QTableWidget()
        self.relay_node_list.setColumnCount(6)
        self.relay_node_list.setHorizontalHeaderLabels(["节点ID", "类型", "区域", "状态", "延迟(ms)", "质量评分"])
        list_layout.addWidget(self.relay_node_list)

        layout.addWidget(list_group)

        return tab

    def _create_audit_tab(self) -> QWidget:
        """存证审计标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 工具栏
        toolbar = QHBoxLayout()

        self.start_audit_btn = QPushButton("开始审计")
        self.start_audit_btn.clicked.connect(self._start_audit)
        toolbar.addWidget(self.start_audit_btn)

        self.stop_audit_btn = QPushButton("停止审计")
        self.stop_audit_btn.clicked.connect(self._stop_audit)
        self.stop_audit_btn.setEnabled(False)
        toolbar.addWidget(self.stop_audit_btn)

        self.capture_screenshot_btn = QPushButton("截图")
        self.capture_screenshot_btn.clicked.connect(self._capture_screenshot)
        self.capture_screenshot_btn.setEnabled(False)
        toolbar.addWidget(self.capture_screenshot_btn)

        self.export_audit_btn = QPushButton("导出证据包")
        self.export_audit_btn.clicked.connect(self._export_audit_package)
        toolbar.addWidget(self.export_audit_btn)

        layout.addLayout(toolbar)

        # 统计
        stats_group = QGroupBox("存证统计")
        stats_layout = QFormLayout(stats_group)

        self.audit_total_sessions = QLabel("0")
        self.audit_sealed = QLabel("0")
        self.audit_total_slices = QLabel("0")
        self.audit_commands = QLabel("0")
        self.audit_storage = QLabel("0 KB")

        stats_layout.addRow("总会话数:", self.audit_total_sessions)
        stats_layout.addRow("已密封:", self.audit_sealed)
        stats_layout.addRow("证据切片:", self.audit_total_slices)
        stats_layout.addRow("命令日志:", self.audit_commands)
        stats_layout.addRow("存储大小:", self.audit_storage)

        layout.addWidget(stats_group)

        # 会话列表
        list_group = QGroupBox("审计会话")
        list_layout = QVBoxLayout(list_group)

        self.audit_session_list = QTableWidget()
        self.audit_session_list.setColumnCount(6)
        self.audit_session_list.setHorizontalHeaderLabels(["会话ID", "订单ID", "卖家", "买家", "状态", "密封校验"])
        list_layout.addWidget(self.audit_session_list)

        layout.addWidget(list_group)

        return tab

    # ==================== AI能力操作 ====================

    def _discover_ai_capabilities(self):
        """探测AI能力"""
        try:
            from client.src.business.decommerce import get_ai_capability_registry
            self.ai_registry = get_ai_capability_registry()
            asyncio.create_task(self.ai_registry.discover_capabilities())
            self.status_bar.showMessage("正在探测AI能力...")
            QTimer.singleShot(2000, self._refresh_ai_capabilities)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"探测AI能力失败: {e}")

    def _publish_all_ai(self):
        """一键发布所有AI能力"""
        if not self.seller_node or not self.ai_registry:
            QMessageBox.warning(self, "错误", "请先启动卖家节点并探测AI能力")
            return

        try:
            listings = self.ai_registry.publish_all_enabled(self.seller_node.seller_id)
            for listing_data in listings:
                asyncio.create_task(self.seller_node.publish_listing(**listing_data))
            QMessageBox.information(self, "成功", f"已发布 {len(listings)} 个AI服务")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"发布失败: {e}")

    def _refresh_ai_capabilities(self):
        """刷新AI能力列表"""
        if not self.ai_registry:
            return

        caps = self.ai_registry.get_capabilities()
        stats = self.ai_registry.get_stats()

        self.ai_total_caps.setText(str(stats.get("total_capabilities", 0)))
        self.ai_available_caps.setText(str(stats.get("available", 0)))
        self.ai_enabled_caps.setText(str(stats.get("enabled", 0)))

        self.ai_cap_list.setRowCount(len(caps))
        for i, cap in enumerate(caps):
            self.ai_cap_list.setItem(i, 0, QTableWidgetItem(cap.capability_id))
            self.ai_cap_list.setItem(i, 1, QTableWidgetItem(cap.capability_type.value))
            self.ai_cap_list.setItem(i, 2, QTableWidgetItem(cap.model_name))
            self.ai_cap_list.setItem(i, 3, QTableWidgetItem(cap.model_backend))
            self.ai_cap_list.setItem(i, 4, QTableWidgetItem(cap.display_name))

            avail_item = QTableWidgetItem("是" if cap.is_available else "否")
            avail_item.setBackground(QColor("green" if cap.is_available else "red"))
            self.ai_cap_list.setItem(i, 5, avail_item)

            enabled_item = QTableWidgetItem("是" if cap.is_enabled else "否")
            enabled_item.setBackground(QColor("green" if cap.is_enabled else "gray"))
            self.ai_cap_list.setItem(i, 6, enabled_item)

    def _enable_ai_capability(self):
        """启用AI能力"""
        if not self.ai_registry:
            return
        row = self.ai_cap_list.currentRow()
        if row >= 0:
            cap_id = self.ai_cap_list.item(row, 0).text()
            self.ai_registry.enable_capability(cap_id)
            self._refresh_ai_capabilities()

    def _disable_ai_capability(self):
        """禁用AI能力"""
        if not self.ai_registry:
            return
        row = self.ai_cap_list.currentRow()
        if row >= 0:
            cap_id = self.ai_cap_list.item(row, 0).text()
            self.ai_registry.disable_capability(cap_id)
            self._refresh_ai_capabilities()

    def _publish_single_ai(self):
        """发布单个AI能力"""
        if not self.seller_node or not self.ai_registry:
            return
        row = self.ai_cap_list.currentRow()
        if row >= 0:
            cap_id = self.ai_cap_list.item(row, 0).text()
            listing_data = self.ai_registry.create_listing_from_capability(cap_id, self.seller_node.seller_id)
            if listing_data:
                asyncio.create_task(self.seller_node.publish_listing(**listing_data))
                QMessageBox.information(self, "成功", f"已发布: {listing_data['title']}")

    # ==================== 穿透网络操作 ====================

    def _init_super_relay(self):
        """初始化Super Relay"""
        try:
            from client.src.business.decommerce import init_edge_relay_network
            self.edge_relay = init_edge_relay_network(
                super_relay_host=self.turn_url.text().replace("turn://", "").split(":")[0] or "localhost",
                super_relay_port=int(self.turn_url.text().replace("turn://", "").split(":")[1]) if ":" in self.turn_url.text() else 3478,
                turn_username=self.turn_user.text() or None,
                turn_credential=self.turn_credential.text() or None,
            )
            self.status_bar.showMessage("Super Relay已初始化")
            self._refresh_relay_network()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"初始化失败: {e}")

    def _add_edge_relay(self):
        """添加Edge节点"""
        if not self.edge_relay:
            QMessageBox.warning(self, "错误", "请先初始化Super Relay")
            return

        # 简单对话框获取节点信息
        host, ok = QLineEdit().text(), True
        if ok and host:
            self.edge_relay.register_edge_relay(
                host=host,
                region="default",
            )
            self._refresh_relay_network()

    def _refresh_relay_network(self):
        """刷新穿透网络"""
        if not self.edge_relay:
            return

        stats = self.edge_relay.get_network_stats()

        self.relay_total_nodes.setText(str(stats.get("total_nodes", 0)))
        self.relay_healthy_nodes.setText(str(stats.get("healthy_nodes", 0)))
        self.relay_total_sessions.setText(str(stats.get("total_sessions", 0)))
        self.relay_active_sessions.setText(str(stats.get("active_sessions", 0)))
        self.relay_utilization.setText(f"{stats.get('utilization_percent', 0):.1f}%")

        nodes = stats.get("edge_relays", [])
        self.relay_node_list.setRowCount(len(nodes))
        for i, node in enumerate(nodes):
            self.relay_node_list.setItem(i, 0, QTableWidgetItem(node.get("id", "")))
            self.relay_node_list.setItem(i, 1, QTableWidgetItem(node.get("node_type", "")))
            self.relay_node_list.setItem(i, 2, QTableWidgetItem(node.get("region", "")))
            self.relay_node_list.setItem(i, 3, QTableWidgetItem(node.get("status", "")))
            self.relay_node_list.setItem(i, 4, QTableWidgetItem(str(node.get("latency_ms", 0))))
            self.relay_node_list.setItem(i, 5, QTableWidgetItem(f"{node.get('quality_score', 0):.1f}"))

    # ==================== 存证审计操作 ====================

    def _start_audit(self):
        """开始审计"""
        try:
            from client.src.business.decommerce import get_audit_trail
            self.audit_trail = get_audit_trail()

            session_id = self.audit_trail.start_session(
                order_id="demo_order",
                listing_id="demo_listing",
                seller_id="demo_seller",
                buyer_id="demo_buyer",
            )

            self.start_audit_btn.setEnabled(False)
            self.stop_audit_btn.setEnabled(True)
            self.capture_screenshot_btn.setEnabled(True)
            self.status_bar.showMessage(f"审计已开始: {session_id}")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"开始审计失败: {e}")

    def _stop_audit(self):
        """停止审计"""
        if self.audit_trail:
            result = self.audit_trail.stop_session()
            if result:
                self.status_bar.showMessage(f"审计已停止, 密封校验: {result.get('seal_checksum', '')[:16]}")

        self.start_audit_btn.setEnabled(True)
        self.stop_audit_btn.setEnabled(False)
        self.capture_screenshot_btn.setEnabled(False)
        self._refresh_audit()

    def _capture_screenshot(self):
        """截图"""
        if self.audit_trail:
            asyncio.create_task(self.audit_trail.capture_screenshot(
                self.audit_trail._active_session.session_id if self.audit_trail._active_session else "unknown",
                "manual_capture"
            ))
            self.status_bar.showMessage("截图已保存")

    def _export_audit_package(self):
        """导出证据包"""
        if self.audit_trail:
            session_id = self.audit_trail._active_session.session_id if self.audit_trail._active_session else None
            if session_id:
                path = self.audit_trail.export_evidence_package(session_id)
                if path:
                    QMessageBox.information(self, "成功", f"证据包已导出到:\n{path}")

    def _refresh_audit(self):
        """刷新审计列表"""
        if not self.audit_trail:
            return

        stats = self.audit_trail.get_stats()

        self.audit_total_sessions.setText(str(stats.get("total_sessions", 0)))
        self.audit_sealed.setText(str(stats.get("sealed_sessions", 0)))
        self.audit_total_slices.setText(str(stats.get("total_slices", 0)))
        self.audit_commands.setText(str(stats.get("total_commands", 0)))

        # 获取所有会话
        sessions = []
        if hasattr(self.audit_trail, "_sessions"):
            sessions = list(self.audit_trail._sessions.values())

        self.audit_session_list.setRowCount(len(sessions))
        for i, session in enumerate(sessions):
            self.audit_session_list.setItem(i, 0, QTableWidgetItem(session.session_id))
            self.audit_session_list.setItem(i, 1, QTableWidgetItem(session.order_id))
            self.audit_session_list.setItem(i, 2, QTableWidgetItem(session.seller_id))
            self.audit_session_list.setItem(i, 3, QTableWidgetItem(session.buyer_id))
            self.audit_session_list.setItem(i, 4, QTableWidgetItem(session.status.value))

            seal_item = QTableWidgetItem(session.seal_checksum[:16] if session.seal_checksum else "未密封")
            if session.sealed:
                seal_item.setBackground(QColor("green"))
            self.audit_session_list.setItem(i, 5, seal_item)

    # ==================== 卖家操作 ====================

    def _start_seller_node(self):
        """启动卖家节点"""
        try:
            from client.src.business.decommerce import SellerNode

            self.seller_node = SellerNode(
                user_id="local_user",
                name="本地卖家",
                tracker_url=self.tracker_url_input.text(),
                http_port=self.local_port.value(),
            )

            # 异步启动
            asyncio.create_task(self._async_start_seller())

            self.seller_status_label.setText("启动中...")
            self.seller_start_btn.setEnabled(False)
            self.seller_stop_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.warning(self, "错误", f"启动卖家节点失败: {e}")

    async def _async_start_seller(self):
        """异步启动卖家节点"""
        try:
            await self.seller_node.initialize(
                cloud_turn_url=self.turn_url.text() or None,
                cloud_turn_user=self.turn_user.text() or None,
                cloud_turn_credential=self.turn_credential.text() or None,
            )
            self.seller_status_label.setText("在线")
            self.seller_status_label.setStyleSheet("color: green;")
            self.publish_btn.setEnabled(True)
            self._is_seller_mode = True
            self.status_bar.showMessage("卖家节点已启动")
        except Exception as e:
            self.seller_status_label.setText(f"错误: {e}")
            self.seller_start_btn.setEnabled(True)

    def _stop_seller_node(self):
        """停止卖家节点"""
        if self.seller_node:
            asyncio.create_task(self.seller_node.shutdown())
            self.seller_node = None

        self.seller_status_label.setText("离线")
        self.seller_status_label.setStyleSheet("color: gray;")
        self.seller_start_btn.setEnabled(True)
        self.seller_stop_btn.setEnabled(False)
        self.publish_btn.setEnabled(False)
        self._is_seller_mode = False

        self.status_bar.showMessage("卖家节点已停止")

    def _publish_service(self):
        """发布服务"""
        if not self.seller_node:
            QMessageBox.warning(self, "错误", "请先启动卖家节点")
            return

        try:
            from client.src.business.decommerce import ServiceType

            title = self.publish_title.text()
            desc = self.publish_desc.toPlainText()
            price = self.publish_price.value()

            type_map = {
                0: ServiceType.PHYSICAL_PRODUCT,
                1: ServiceType.REMOTE_LIVE_VIEW,
                2: ServiceType.AI_COMPUTING,
                3: ServiceType.REMOTE_ASSIST,
                4: ServiceType.KNOWLEDGE_CONSULT,
                5: ServiceType.DIGITAL_PRODUCT,
            }

            service_type = type_map.get(self.publish_type.currentIndex(), ServiceType.PHYSICAL_PRODUCT)

            # 如果是AI计算服务,设置模型
            ai_model = None
            if service_type == ServiceType.AI_COMPUTING:
                ai_model = self.publish_ai_model.currentText()

            # 异步发布
            asyncio.create_task(self._async_publish_service(
                title, desc, price, service_type, ai_model
            ))

        except Exception as e:
            QMessageBox.warning(self, "错误", f"发布失败: {e}")

    async def _async_publish_service(self, title, desc, price, service_type, ai_model):
        """异步发布服务"""
        try:
            listing = await self.seller_node.publish_listing(
                title=title,
                description=desc,
                price=price,
                service_type=service_type,
                ai_model=ai_model,
            )

            self.status_bar.showMessage(f"已发布服务: {listing.id}")
            self._refresh_seller_list()

        except Exception as e:
            QMessageBox.warning(self, "错误", f"发布失败: {e}")

    def _refresh_seller_list(self):
        """刷新卖家服务列表"""
        if not self.seller_node:
            return

        listings = self.seller_node.get_all_listings()

        self.seller_list.setRowCount(len(listings))
        for i, listing in enumerate(listings):
            self.seller_list.setItem(i, 0, QTableWidgetItem(listing.id))
            self.seller_list.setItem(i, 1, QTableWidgetItem(listing.title))
            self.seller_list.setItem(i, 2, QTableWidgetItem(listing.service_type.value))
            self.seller_list.setItem(i, 3, QTableWidgetItem(f"{listing.price}分"))
            self.seller_list.setItem(i, 4, QTableWidgetItem(listing.status.value))
            self.seller_list.setItem(i, 5, QTableWidgetItem(str(listing.order_count)))

    def _unpublish_service(self):
        """下架服务"""
        row = self.seller_list.currentRow()
        if row < 0:
            return

        listing_id = self.seller_list.item(row, 0).text()

        if self.seller_node:
            asyncio.create_task(self.seller_node.unpublish_listing(listing_id))

        self._refresh_seller_list()

    # ==================== 买家操作 ====================

    def _connect_buyer(self):
        """连接买家客户端"""
        try:
            from client.src.business.decommerce import BuyerClient

            self.buyer_client = BuyerClient(
                user_id="local_buyer",
                tracker_url=self.tracker_url_input.text(),
            )

            asyncio.create_task(self._async_connect_buyer())

        except Exception as e:
            QMessageBox.warning(self, "错误", f"连接失败: {e}")

    async def _async_connect_buyer(self):
        """异步连接买家"""
        try:
            success = await self.buyer_client.connect()
            if success:
                self.buyer_status_label.setText("已连接")
                self.buyer_status_label.setStyleSheet("color: green;")
                self.buyer_connect_btn.setEnabled(False)
                self.buyer_refresh_btn.setEnabled(True)
                self._is_buyer_mode = True
                await self._refresh_catalog()
            else:
                self.buyer_status_label.setText("连接失败")
        except Exception as e:
            self.buyer_status_label.setText(f"错误: {e}")

    def _refresh_catalog(self):
        """刷新目录"""
        if self.buyer_client:
            asyncio.create_task(self._async_refresh_catalog())

    async def _async_refresh_catalog(self):
        """异步刷新目录"""
        try:
            listings = await self.buyer_client.refresh_catalog()
            self._update_market_list(listings)
        except Exception as e:
            self.status_bar.showMessage(f"刷新失败: {e}")

    def _do_search(self):
        """搜索"""
        if not self.buyer_client:
            return

        query = self.search_input.text()
        live_only = self.search_live_only.isChecked()

        asyncio.create_task(self._async_search(query, live_only))

    async def _async_search(self, query, live_only):
        """异步搜索"""
        try:
            results = await self.buyer_client.search_listings(
                query=query,
                live_only=live_only,
            )
            self._update_market_list(results)
        except Exception as e:
            self.status_bar.showMessage(f"搜索失败: {e}")

    def _update_market_list(self, listings):
        """更新市场列表"""
        self.market_list.setRowCount(len(listings))

        for i, listing in enumerate(listings):
            self.market_list.setItem(i, 0, QTableWidgetItem(listing.id))
            self.market_list.setItem(i, 1, QTableWidgetItem(listing.seller_id[:8]))
            self.market_list.setItem(i, 2, QTableWidgetItem(listing.title))
            self.market_list.setItem(i, 3, QTableWidgetItem(listing.service_type.value))
            self.market_list.setItem(i, 4, QTableWidgetItem(f"{listing.price}分"))
            self.market_list.setItem(i, 5, QTableWidgetItem("是" if listing.is_live_available else "否"))

            # 购买按钮
            buy_btn = QPushButton("购买")
            buy_btn.clicked.connect(lambda checked, lid=listing.id, p=listing.price: self._select_for_purchase(lid, p))
            self.market_list.setCellWidget(i, 6, buy_btn)

    def _select_for_purchase(self, listing_id, price):
        """选择服务购买"""
        self.purchase_listing_id.setText(listing_id)
        self.purchase_amount.setText(f"{price} 分")
        self.purchase_btn.setEnabled(True)

    def _purchase_service(self):
        """购买服务"""
        if not self.buyer_client:
            return

        listing_id = self.purchase_listing_id.text()
        if not listing_id:
            return

        QMessageBox.information(self, "提示", f"正在连接服务 {listing_id}...")

    # ==================== 会话操作 ====================

    def _refresh_sessions(self):
        """刷新会话列表"""
        pass

    def _end_session(self):
        """结束会话"""
        pass

    # ==================== 订单操作 ====================

    def _refresh_orders(self):
        """刷新订单"""
        pass

    def _refund_order(self):
        """退款"""
        pass

    # ==================== 设置操作 ====================

    def _save_tracker_config(self):
        """保存Tracker配置"""
        self.tracker_url = self.tracker_url_input.text()
        self.status_bar.showMessage("Tracker配置已保存")

    def _save_turn_config(self):
        """保存TURN配置"""
        self.status_bar.showMessage("TURN配置已保存")

    # ==================== 定时更新 ====================

    def _update_status(self):
        """定时更新状态"""
        if self.seller_node:
            stats = self.seller_node.get_stats()
            self.seller_status_label.setText(f"在线 ({stats.get('active_sessions', 0)} 会话)")

        if self.buyer_client:
            stats = self.buyer_client.get_stats()
            self.buyer_status_label.setText(f"已连接 ({stats.get('discovered_listings', 0)} 服务)")

        # 更新AI能力统计
        if self.ai_registry:
            self._refresh_ai_capabilities()

        # 更新穿透网络统计
        if self.edge_relay:
            self._refresh_relay_network()

        # 更新审计统计
        if self.audit_trail:
            self._refresh_audit()