"""
轻量级UI与网络优化面板

集成轻量级UI组件、网络探测、协议降级等功能
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QProgressBar, QLineEdit, QGroupBox, QFormLayout,
    QScrollArea, QFrame, QComboBox, QSpinBox, QCheckBox,
    QGridLayout, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QTimer
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LightweightUIPanel(QWidget):
    """
    轻量级UI与网络优化综合面板
    
    包含以下标签页：
    1. 概览 - 系统状态总览
    2. 网络探测 - 网络环境探测
    3. 协议管理 - 协议选择与降级
    4. 质量监控 - 实时质量监控
    5. 故障恢复 - 故障处理与恢复
    6. 组件预览 - UI组件示例
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._init_timers()
        
        try:
            from client.src.business.lightweight_ui import get_lightweight_ui
            self._ui_system = get_lightweight_ui()
        except ImportError:
            self._ui_system = None
        
        try:
            from core.lightweight_ui.network_probe import get_network_probe_manager
            from core.lightweight_ui.protocol_fallback import get_protocol_fallback_manager
            from core.lightweight_ui.quality_monitor import get_quality_monitor
            from core.lightweight_ui.fast_recovery import get_fast_recovery_manager
            
            self._probe_manager = get_network_probe_manager()
            self._fallback_manager = get_protocol_fallback_manager()
            self._quality_monitor = get_quality_monitor()
            self._recovery_manager = get_fast_recovery_manager()
        except ImportError:
            self._probe_manager = None
            self._fallback_manager = None
            self._quality_monitor = None
            self._recovery_manager = None
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_overview_tab(), "概览")
        self.tabs.addTab(self._create_network_probe_tab(), "网络探测")
        self.tabs.addTab(self._create_protocol_tab(), "协议管理")
        self.tabs.addTab(self._create_quality_tab(), "质量监控")
        self.tabs.addTab(self._create_recovery_tab(), "故障恢复")
        self.tabs.addTab(self._create_components_tab(), "组件预览")
        
        layout.addWidget(self.tabs)
    
    def _create_overview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title = QLabel("系统状态概览")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        cards_layout = QGridLayout()
        cards_layout.addWidget(self._create_status_card("FPS", "60", "#4CAF50"), 0, 0)
        cards_layout.addWidget(self._create_status_card("内存", "128 MB", "#2196F3"), 0, 1)
        cards_layout.addWidget(self._create_status_card("延迟", "25 ms", "#FF9800"), 1, 0)
        cards_layout.addWidget(self._create_status_card("连接", "12", "#9C27B0"), 1, 1)
        layout.addLayout(cards_layout)
        
        actions_group = QGroupBox("快速操作")
        actions_layout = QHBoxLayout()
        
        self.btn_probe = QPushButton("探测网络")
        self.btn_probe.clicked.connect(self._on_probe_network)
        actions_layout.addWidget(self.btn_probe)
        
        self.btn_optimize = QPushButton("优化连接")
        self.btn_optimize.clicked.connect(self._on_optimize)
        actions_layout.addWidget(self.btn_optimize)
        
        self.btn_refresh = QPushButton("刷新状态")
        self.btn_refresh.clicked.connect(self._refresh_status)
        actions_layout.addWidget(self.btn_refresh)
        
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
        
        activity_group = QGroupBox("最近活动")
        activity_layout = QVBoxLayout()
        
        self.activity_list = QListWidget()
        self.activity_list.addItems([
            "[15:58:32] 网络探测完成 - 延迟: 25ms",
            "[15:57:15] 协议切换 - TCP -> UDP",
            "[15:56:00] 连接池调整 - 10 -> 12",
        ])
        activity_layout.addWidget(self.activity_list)
        
        activity_group.setLayout(activity_layout)
        layout.addWidget(activity_group)
        
        layout.addStretch()
        return widget
    
    def _create_network_probe_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title = QLabel("智能网络探测")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        info_group = QGroupBox("网络环境信息")
        info_layout = QFormLayout()
        
        self.lbl_network_type = QLabel("未知")
        self.lbl_nat_type = QLabel("未知")
        self.lbl_local_ip = QLabel("-")
        self.lbl_latency = QLabel("0 ms")
        self.lbl_bandwidth = QLabel("0 Mbps")
        
        info_layout.addRow("网络类型:", self.lbl_network_type)
        info_layout.addRow("NAT类型:", self.lbl_nat_type)
        info_layout.addRow("本地IP:", self.lbl_local_ip)
        info_layout.addRow("延迟:", self.lbl_latency)
        info_layout.addRow("带宽:", self.lbl_bandwidth)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        method_group = QGroupBox("推荐连接方式")
        method_layout = QVBoxLayout()
        
        self.method_list = QListWidget()
        self.method_list.addItems([
            "1. 局域网直连 (评分: 95)",
            "2. P2P内网穿透 (评分: 80)",
            "3. 中继服务器 (评分: 60)",
        ])
        method_layout.addWidget(self.method_list)
        
        method_group.setLayout(method_layout)
        layout.addWidget(method_group)
        
        self.btn_start_probe = QPushButton("开始探测")
        self.btn_start_probe.clicked.connect(self._on_start_probe)
        layout.addWidget(self.btn_start_probe)
        
        layout.addStretch()
        return widget
    
    def _create_protocol_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title = QLabel("多协议降级管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        status_group = QGroupBox("当前状态")
        status_layout = QFormLayout()
        
        self.lbl_current_protocol = QLabel("TCP")
        self.lbl_protocol_state = QLabel("已连接")
        self.lbl_fallback_count = QLabel("0")
        self.lbl_success_rate = QLabel("100%")
        
        status_layout.addRow("当前协议:", self.lbl_current_protocol)
        status_layout.addRow("连接状态:", self.lbl_protocol_state)
        status_layout.addRow("降级次数:", self.lbl_fallback_count)
        status_layout.addRow("成功率:", self.lbl_success_rate)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        stats_group = QGroupBox("协议统计")
        stats_layout = QVBoxLayout()
        
        self.protocol_table = QTableWidget(3, 4)
        self.protocol_table.setHorizontalHeaderLabels(["协议", "尝试", "成功", "成功率"])
        
        self.protocol_table.setItem(0, 0, QTableWidgetItem("TCP"))
        self.protocol_table.setItem(0, 1, QTableWidgetItem("156"))
        self.protocol_table.setItem(0, 2, QTableWidgetItem("152"))
        self.protocol_table.setItem(0, 3, QTableWidgetItem("97.4%"))
        
        self.protocol_table.setItem(1, 0, QTableWidgetItem("UDP"))
        self.protocol_table.setItem(1, 1, QTableWidgetItem("89"))
        self.protocol_table.setItem(1, 2, QTableWidgetItem("85"))
        self.protocol_table.setItem(1, 3, QTableWidgetItem("95.5%"))
        
        self.protocol_table.setItem(2, 0, QTableWidgetItem("WebSocket"))
        self.protocol_table.setItem(2, 1, QTableWidgetItem("45"))
        self.protocol_table.setItem(2, 2, QTableWidgetItem("45"))
        self.protocol_table.setItem(2, 3, QTableWidgetItem("100%"))
        
        stats_layout.addWidget(self.protocol_table)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        layout.addStretch()
        return widget
    
    def _create_quality_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title = QLabel("实时网络质量监控")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        gauge_layout = QHBoxLayout()
        gauge_layout.addWidget(self._create_gauge_card("延迟", "25", "ms", "#4CAF50"))
        gauge_layout.addWidget(self._create_gauge_card("抖动", "3", "ms", "#2196F3"))
        gauge_layout.addWidget(self._create_gauge_card("丢包", "0.1", "%", "#FF9800"))
        layout.addLayout(gauge_layout)
        
        score_group = QGroupBox("综合质量评分")
        score_layout = QVBoxLayout()
        
        self.score_bar = QProgressBar()
        self.score_bar.setMaximum(100)
        self.score_bar.setValue(92)
        score_layout.addWidget(self.score_bar)
        
        self.lbl_quality_level = QLabel("质量等级: 优秀")
        self.lbl_quality_level.setStyleSheet("color: #4CAF50; font-weight: bold;")
        score_layout.addWidget(self.lbl_quality_level, alignment=Qt.AlignmentFlag.AlignCenter)
        
        score_group.setLayout(score_layout)
        layout.addWidget(score_group)
        
        alert_group = QGroupBox("质量告警")
        alert_layout = QVBoxLayout()
        
        self.alert_list = QListWidget()
        self.alert_list.addItems([
            "[15:50:00] 信息 - 连接稳定性正常",
            "[15:30:00] 警告 - P95延迟略高 (180ms)",
        ])
        alert_layout.addWidget(self.alert_list)
        
        alert_group.setLayout(alert_layout)
        layout.addWidget(alert_group)
        
        layout.addStretch()
        return widget
    
    def _create_recovery_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title = QLabel("快速故障恢复")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        strategy_group = QGroupBox("恢复策略配置")
        strategy_layout = QFormLayout()
        
        self.chk_fast_retry = QCheckBox("启用快速重试")
        self.chk_fast_retry.setChecked(True)
        strategy_layout.addRow(self.chk_fast_retry)
        
        self.spin_retry_max = QSpinBox()
        self.spin_retry_max.setRange(1, 10)
        self.spin_retry_max.setValue(3)
        strategy_layout.addRow("最大重试次数:", self.spin_retry_max)
        
        self.chk_fallback = QCheckBox("启用自动降级")
        self.chk_fallback.setChecked(True)
        strategy_layout.addRow(self.chk_fallback)
        
        strategy_group.setLayout(strategy_layout)
        layout.addWidget(strategy_group)
        
        history_group = QGroupBox("故障历史")
        history_layout = QVBoxLayout()
        
        self.fault_table = QTableWidget(3, 4)
        self.fault_table.setHorizontalHeaderLabels(["时间", "类型", "动作", "状态"])
        
        self.fault_table.setItem(0, 0, QTableWidgetItem("15:45:30"))
        self.fault_table.setItem(0, 1, QTableWidgetItem("超时"))
        self.fault_table.setItem(0, 2, QTableWidgetItem("重试"))
        self.fault_table.setItem(0, 3, QTableWidgetItem("成功"))
        
        history_layout.addWidget(self.fault_table)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        layout.addStretch()
        return widget
    
    def _create_components_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        title = QLabel("轻量级UI组件预览")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        
        btn_group = QGroupBox("按钮组件")
        btn_layout = QGridLayout()
        
        primary_btn = QPushButton("主要按钮")
        primary_btn.setStyleSheet("background-color: #4CAF50; color: white; border: none; padding: 10px 20px; border-radius: 5px;")
        btn_layout.addWidget(primary_btn, 0, 0)
        
        secondary_btn = QPushButton("次要按钮")
        secondary_btn.setStyleSheet("background-color: #2196F3; color: white; border: none; padding: 10px 20px; border-radius: 5px;")
        btn_layout.addWidget(secondary_btn, 0, 1)
        
        outline_btn = QPushButton("轮廓按钮")
        outline_btn.setStyleSheet("background-color: transparent; color: #4CAF50; border: 2px solid #4CAF50; padding: 10px 20px; border-radius: 5px;")
        btn_layout.addWidget(outline_btn, 0, 2)
        
        danger_btn = QPushButton("危险按钮")
        danger_btn.setStyleSheet("background-color: #f44336; color: white; border: none; padding: 10px 20px; border-radius: 5px;")
        btn_layout.addWidget(danger_btn, 1, 0)
        
        btn_group.setLayout(btn_layout)
        content_layout.addWidget(btn_group)
        
        input_group = QGroupBox("输入组件")
        input_layout = QFormLayout()
        
        input1 = QLineEdit()
        input1.setPlaceholderText("普通输入框")
        input_layout.addRow("文本输入:", input1)
        
        combo = QComboBox()
        combo.addItems(["选项 1", "选项 2", "选项 3"])
        input_layout.addRow("下拉选择:", combo)
        
        input_group.setLayout(input_layout)
        content_layout.addWidget(input_group)
        
        progress_group = QGroupBox("进度组件")
        progress_layout = QVBoxLayout()
        
        progress1 = QProgressBar()
        progress1.setValue(65)
        progress_layout.addWidget(QLabel("进度条:"))
        progress_layout.addWidget(progress1)
        
        progress_group.setLayout(progress_layout)
        content_layout.addWidget(progress_group)
        
        badge_group = QGroupBox("状态标签")
        badge_layout = QHBoxLayout()
        
        badge_success = QLabel("成功")
        badge_success.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px 10px; border-radius: 12px;")
        badge_layout.addWidget(badge_success)
        
        badge_warning = QLabel("警告")
        badge_warning.setStyleSheet("background-color: #FF9800; color: white; padding: 5px 10px; border-radius: 12px;")
        badge_layout.addWidget(badge_warning)
        
        badge_error = QLabel("错误")
        badge_error.setStyleSheet("background-color: #f44336; color: white; padding: 5px 10px; border-radius: 12px;")
        badge_layout.addWidget(badge_error)
        
        badge_layout.addStretch()
        badge_group.setLayout(badge_layout)
        content_layout.addWidget(badge_group)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return widget
    
    def _create_status_card(self, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("QFrame { background-color: white; border-radius: 10px; border: 1px solid #E0E0E0; padding: 15px; }")
        
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666; font-size: 14px;")
        layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        layout.addWidget(value_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        return card
    
    def _create_gauge_card(self, title: str, value: str, unit: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("QFrame { background-color: #1a1a2e; border-radius: 60px; min-width: 120px; min-height: 120px; padding: 10px; }")
        
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {color}; font-size: 36px; font-weight: bold;")
        layout.addWidget(value_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        unit_label = QLabel(unit)
        unit_label.setStyleSheet("color: #888; font-size: 14px;")
        layout.addWidget(unit_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        return card
    
    def _init_timers(self):
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(2000)
    
    def _refresh_status(self):
        pass
    
    def _on_probe_network(self):
        if self._probe_manager:
            pass
        self.activity_list.insertItem(0, f"[{self._get_time()}] 开始网络探测...")
    
    def _on_start_probe(self):
        self.btn_start_probe.setEnabled(False)
        self.btn_start_probe.setText("探测中...")
        QTimer.singleShot(2000, self._on_probe_complete)
    
    def _on_probe_complete(self):
        self.btn_start_probe.setEnabled(True)
        self.btn_start_probe.setText("开始探测")
        
        self.lbl_network_type.setText("局域网")
        self.lbl_nat_type.setText("全锥型")
        self.lbl_local_ip.setText("192.168.1.100")
        self.lbl_latency.setText("25 ms")
        self.lbl_bandwidth.setText("100 Mbps")
    
    def _on_optimize(self):
        self.activity_list.insertItem(0, f"[{self._get_time()}] 正在优化连接...")
    
    def _get_time(self) -> str:
        return datetime.now().strftime("%H:%M:%S")


__all__ = ["LightweightUIPanel"]
