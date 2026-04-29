"""
轻量级UI综合面板

集成网络探测、协议管理、质量监控、故障恢复、中继服务器配置
from __future__ import annotations
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QTextEdit, QGroupBox, QFormLayout,
    QProgressBar, QScrollArea, QFrame, QGridLayout,
    QHeaderView, QStatusBar, QToolButton, QMenu,
    QDialog, QDialogButtonBox, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QFont
from typing import Dict, List, Optional, Any
import asyncio
import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)


# 尝试导入核心模块
try:
    from ..models import ComponentType, LayoutType, ResponsiveBreakpoint
    from ..virtual_dom import VirtualDOM, VirtualNode
    from ..state_manager import StateManager, create_store
    from ..components import Button, Input, Select, Card, Modal, Progress, ListView, Table
    from ..performance import PerformanceMonitor, FPSCounter, MemoryOptimizer
    from ..layout import FlexLayout, GridLayout, ResponsiveLayout
    from ..network_probe import NetworkProbeManager, NATType, NetworkType
    from ..protocol_fallback import (
        ProtocolFallbackManager, ProtocolType, ConnectionState,
        FallbackLevel, RelayEndpoint
    )
    from ..quality_monitor import QualityMonitor, NetworkQuality
    from ..fast_recovery import FastRecoveryManager, FaultType, RecoveryAction
    from ..adaptive_connection import (
        AdaptiveConnectionPool, ConnectionLoadBalancer,
        ConnectionType, ConnectionStatus, RelayConfig
    )
    from ..relay_client import RelayClient, RelayServerManager, get_relay_manager, RelayState
    CORE_IMPORTED = True
except ImportError as e:
    logger.warning(f"Core modules not fully imported: {e}")
    CORE_IMPORTED = False


class RelayServerDialog(QDialog):
    """中继服务器配置对话框"""
    
    def __init__(self, parent=None, server_data: dict = None):
        super().__init__(parent)
        self.server_data = server_data or {}
        self.setup_ui()
        
        if server_data:
            self.load_server_data()
    
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("中继服务器配置")
        self.setMinimumWidth(500)
        
        layout = QFormLayout(self)
        
        # 基本信息
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("例如: 139.199.124.242")
        layout.addRow("主机地址 *:", self.host_input)
        
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(8888)
        layout.addRow("端口:", self.port_spin)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如: 腾讯云服务器")
        layout.addRow("名称:", self.name_input)
        
        self.region_combo = QComboBox()
        self.region_combo.addItems(["华北", "华东", "华南", "华西", "北美", "欧洲", "亚洲", "其他"])
        layout.addRow("区域:", self.region_combo)
        
        # 协议配置
        self.use_websocket = QCheckBox("使用 WebSocket")
        self.use_websocket.setChecked(True)
        layout.addRow("协议:", self.use_websocket)
        
        self.ssl_enabled = QCheckBox("启用 SSL/TLS")
        layout.addRow("加密:", self.ssl_enabled)
        
        # 连接参数
        self.connect_timeout = QDoubleSpinBox()
        self.connect_timeout.setRange(1, 60)
        self.connect_timeout.setValue(10)
        self.connect_timeout.setSuffix(" 秒")
        layout.addRow("连接超时:", self.connect_timeout)
        
        self.heartbeat_interval = QDoubleSpinBox()
        self.heartbeat_interval.setRange(5, 300)
        self.heartbeat_interval.setValue(30)
        self.heartbeat_interval.setSuffix(" 秒")
        layout.addRow("心跳间隔:", self.heartbeat_interval)
        
        # 认证
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("API密钥（可选）")
        layout.addRow("API密钥:", self.api_key_input)
        
        # 启用状态
        self.enabled_check = QCheckBox("启用此服务器")
        self.enabled_check.setChecked(True)
        layout.addRow("状态:", self.enabled_check)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def load_server_data(self):
        """加载服务器数据"""
        self.host_input.setText(self.server_data.get("host", ""))
        self.port_spin.setValue(self.server_data.get("port", 8888))
        self.name_input.setText(self.server_data.get("name", ""))
        
        region = self.server_data.get("region", "")
        if region:
            index = self.region_combo.findText(region)
            if index >= 0:
                self.region_combo.setCurrentIndex(index)
        
        self.use_websocket.setChecked(self.server_data.get("use_websocket", True))
        self.ssl_enabled.setChecked(self.server_data.get("ssl_enabled", False))
        self.connect_timeout.setValue(self.server_data.get("connect_timeout", 10))
        self.heartbeat_interval.setValue(self.server_data.get("heartbeat_interval", 30))
        self.api_key_input.setText(self.server_data.get("api_key", ""))
        self.enabled_check.setChecked(self.server_data.get("enabled", True))
    
    def get_server_data(self) -> dict:
        """获取服务器配置"""
        return {
            "host": self.host_input.text().strip(),
            "port": self.port_spin.value(),
            "name": self.name_input.text().strip(),
            "region": self.region_combo.currentText(),
            "use_websocket": self.use_websocket.isChecked(),
            "ssl_enabled": self.ssl_enabled.isChecked(),
            "connect_timeout": self.connect_timeout.value(),
            "heartbeat_interval": self.heartbeat_interval.value(),
            "api_key": self.api_key_input.text().strip(),
            "enabled": self.enabled_check.isChecked(),
        }


class RelayPanel(QWidget):
    """中继服务器管理面板"""
    
    # 信号
    server_added = pyqtSignal(dict)
    server_removed = pyqtSignal(str)
    connection_state_changed = pyqtSignal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._relay_manager = None
        self._relay_client = None
        self._servers: Dict[str, dict] = {}
        
        self.setup_ui()
        self.load_servers()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        self.add_btn = QPushButton("添加服务器")
        self.add_btn.clicked.connect(self.on_add_server)
        toolbar.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("编辑")
        self.edit_btn.clicked.connect(self.on_edit_server)
        self.edit_btn.setEnabled(False)
        toolbar.addWidget(self.edit_btn)
        
        self.remove_btn = QPushButton("删除")
        self.remove_btn.clicked.connect(self.on_remove_server)
        self.remove_btn.setEnabled(False)
        toolbar.addWidget(self.remove_btn)
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_stats)
        toolbar.addWidget(self.refresh_btn)
        
        toolbar.addStretch()
        
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.on_toggle_connection)
        self.connect_btn.setEnabled(False)
        toolbar.addWidget(self.connect_btn)
        
        layout.addLayout(toolbar)
        
        # 服务器列表
        self.server_table = QTableWidget()
        self.server_table.setColumnCount(9)
        self.server_table.setHorizontalHeaderLabels([
            "", "名称", "地址", "端口", "区域", "状态", "延迟(ms)", "质量", "连接数"
        ])
        self.server_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.server_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.server_table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.server_table)
        
        # 连接状态
        status_group = QGroupBox("连接状态")
        status_layout = QFormLayout(status_group)
        
        self.connection_status = QLabel("未连接")
        status_layout.addRow("状态:", self.connection_status)
        
        self.connection_time = QLabel("-")
        status_layout.addRow("已连接时间:", self.connection_time)
        
        self.messages_sent = QLabel("0")
        status_layout.addRow("已发送消息:", self.messages_sent)
        
        self.messages_recv = QLabel("0")
        status_layout.addRow("已接收消息:", self.messages_recv)
        
        self.online_peers = QLabel("0")
        status_layout.addRow("在线节点:", self.online_peers)
        
        layout.addWidget(status_group)
        
        # 日志
        log_group = QGroupBox("连接日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
    
    def load_servers(self):
        """加载服务器列表"""
        # 默认添加腾讯云服务器
        self._servers["139.199.124.242"] = {
            "id": "default",
            "host": "139.199.124.242",
            "port": 8888,
            "name": "腾讯云服务器",
            "region": "华南",
            "enabled": True,
            "use_websocket": True,
            "ssl_enabled": False,
            "api_key": "",
            "status": "离线",
            "latency": 0,
            "quality": 0,
            "connections": 0,
            "max_connections": 100,
        }
        
        self.update_server_table()
    
    def update_server_table(self):
        """更新服务器表格"""
        self.server_table.setRowCount(len(self._servers))
        
        for i, (host, server) in enumerate(self._servers.items()):
            # 选择框
            checkbox_item = QTableWidgetItem()
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            self.server_table.setItem(i, 0, checkbox_item)
            
            # 名称
            self.server_table.setItem(i, 1, QTableWidgetItem(server.get("name", host)))
            
            # 地址
            self.server_table.setItem(i, 2, QTableWidgetItem(server.get("host", "")))
            
            # 端口
            self.server_table.setItem(i, 3, QTableWidgetItem(str(server.get("port", 8888))))
            
            # 区域
            self.server_table.setItem(i, 4, QTableWidgetItem(server.get("region", "")))
            
            # 状态
            status_item = QTableWidgetItem(server.get("status", "离线"))
            if server.get("status") == "在线":
                status_item.setForeground(QColor(0, 150, 0))
            elif server.get("status") == "连接中":
                status_item.setForeground(QColor(200, 150, 0))
            else:
                status_item.setForeground(QColor(150, 150, 150))
            self.server_table.setItem(i, 5, status_item)
            
            # 延迟
            latency = server.get("latency", 0)
            self.server_table.setItem(i, 6, QTableWidgetItem(f"{latency:.0f}" if latency else "-"))
            
            # 质量
            quality = server.get("quality", 0)
            quality_item = QTableWidgetItem(f"{quality:.0f}%" if quality else "-")
            if quality >= 80:
                quality_item.setForeground(QColor(0, 150, 0))
            elif quality >= 50:
                quality_item.setForeground(QColor(200, 150, 0))
            else:
                quality_item.setForeground(QColor(200, 0, 0))
            self.server_table.setItem(i, 7, quality_item)
            
            # 连接数
            self.server_table.setItem(i, 8, QTableWidgetItem(
                f"{server.get('connections', 0)}/{server.get('max_connections', 100)}"
            ))
        
        # 调整列宽
        self.server_table.resizeColumnsToContents()
        self.server_table.setColumnWidth(0, 40)
    
    def on_selection_changed(self):
        """选择变化"""
        selected = len(self.server_table.selectedItems()) > 0
        self.edit_btn.setEnabled(selected)
        self.remove_btn.setEnabled(selected)
        self.connect_btn.setEnabled(selected)
    
    def on_add_server(self):
        """添加服务器"""
        dialog = RelayServerDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_server_data()
            if data["host"]:
                host = data["host"]
                self._servers[host] = {
                    "id": host,
                    **data,
                    "status": "离线",
                    "latency": 0,
                    "quality": 0,
                    "connections": 0,
                    "max_connections": 100,
                }
                self.update_server_table()
                self.server_added.emit(data)
                self.log(f"已添加服务器: {data['name']} ({host})")
    
    def on_edit_server(self):
        """编辑服务器"""
        row = self.server_table.currentRow()
        if row >= 0:
            host = self.server_table.item(row, 2).text()
            server = self._servers.get(host)
            if server:
                dialog = RelayServerDialog(self, server)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    data = dialog.get_server_data()
                    if data["host"]:
                        self._servers[data["host"]].update(data)
                        self.update_server_table()
                        self.log(f"已更新服务器: {data['name']}")
    
    def on_remove_server(self):
        """删除服务器"""
        row = self.server_table.currentRow()
        if row >= 0:
            host = self.server_table.item(row, 2).text()
            server = self._servers.get(host)
            if server:
                reply = QMessageBox.question(
                    self, "确认删除",
                    f"确定要删除服务器 {server.get('name', host)} 吗？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._servers.pop(host, None)
                    self.update_server_table()
                    self.server_removed.emit(host)
                    self.log(f"已删除服务器: {server.get('name', host)}")
    
    def on_toggle_connection(self):
        """切换连接状态"""
        if self._relay_client and self._relay_client.is_connected:
            # 断开连接
            self._relay_client.disconnect()
            self.connection_status.setText("已断开")
            self.connect_btn.setText("连接")
            self.log("已断开连接")
        else:
            # 连接
            row = self.server_table.currentRow()
            if row >= 0:
                host = self.server_table.item(row, 2).text()
                self.connect_to_server(host)
    
    def connect_to_server(self, host: str):
        """连接到服务器"""
        server = self._servers.get(host)
        if not server:
            return
        
        self.log(f"正在连接到 {server.get('name', host)}...")
        self.connection_status.setText("连接中...")
        
        # 模拟连接
        def simulate_connect():
            time.sleep(0.5)
            server["status"] = "在线"
            server["latency"] = 25
            server["quality"] = 95
            server["connections"] = 1
            
            self.update_server_table()
            self.connection_status.setText("已连接")
            self.connect_btn.setText("断开")
            self.log(f"已连接到 {server.get('name', host)}")
        
        thread = threading.Thread(target=simulate_connect)
        thread.start()
    
    def refresh_stats(self):
        """刷新统计"""
        self.log("正在刷新统计...")
        
        def simulate_refresh():
            for host, server in self._servers.items():
                if server.get("status") == "在线":
                    server["latency"] = 20 + int(time.time() % 30)
                    server["quality"] = 90 + int(time.time() % 10)
            
            time.sleep(0.3)
            self.update_server_table()
            self.log("统计已刷新")
        
        thread = threading.Thread(target=simulate_refresh)
        thread.start()
    
    def log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")


class NetworkProbePanel(QWidget):
    """网络探测面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 探测控制
        control = QHBoxLayout()
        
        self.probe_btn = QPushButton("开始探测")
        self.probe_btn.clicked.connect(self.start_probe)
        control.addWidget(self.probe_btn)
        
        self.auto_probe = QCheckBox("自动探测")
        control.addWidget(self.auto_probe)
        
        control.addStretch()
        
        layout.addLayout(control)
        
        # 探测结果
        result_group = QGroupBox("探测结果")
        result_layout = QFormLayout(result_group)
        
        self.nat_type = QLabel("-")
        result_layout.addRow("NAT类型:", self.nat_type)
        
        self.network_type = QLabel("-")
        result_layout.addRow("网络类型:", self.network_type)
        
        self.public_ip = QLabel("-")
        result_layout.addRow("公网IP:", self.public_ip)
        
        self.local_ip = QLabel("-")
        result_layout.addRow("本地IP:", self.local_ip)
        
        self.latency = QLabel("-")
        result_layout.addRow("延迟:", self.latency)
        
        self.bandwidth = QLabel("-")
        result_layout.addRow("带宽:", self.bandwidth)
        
        self.isp = QLabel("-")
        result_layout.addRow("运营商:", self.isp)
        
        layout.addWidget(result_group)
        
        # 推荐连接方式
        rec_group = QGroupBox("推荐连接方式")
        rec_layout = QVBoxLayout(rec_group)
        
        self.recommendation = QTextEdit()
        self.recommendation.setReadOnly(True)
        self.recommendation.setMaximumHeight(100)
        rec_layout.addWidget(self.recommendation)
        
        layout.addWidget(rec_group)
        
        layout.addStretch()
    
    def start_probe(self):
        """开始探测"""
        self.probe_btn.setEnabled(False)
        self.probe_btn.setText("探测中...")
        self.nat_type.setText("检测中...")
        
        def do_probe():
            time.sleep(1)
            
            # 模拟探测结果
            self.nat_type.setText("全锥型 (Full Cone)")
            self.network_type.setText("局域网")
            self.public_ip.setText("116.23.45.67")
            self.local_ip.setText("192.168.1.100")
            self.latency.setText("25 ms")
            self.bandwidth.setText("50 Mbps")
            self.isp.setText("中国电信")
            
            self.recommendation.setPlainText(
                "推荐连接方式:\n"
                "1. 局域网直连 (延迟 <10ms)\n"
                "2. P2P穿透 (延迟 <100ms)\n"
                "3. 中继服务器 (延迟 <300ms)"
            )
            
            self.probe_btn.setEnabled(True)
            self.probe_btn.setText("开始探测")
        
        thread = threading.Thread(target=do_probe)
        thread.start()


class ProtocolPanel(QWidget):
    """协议管理面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 协议表格
        self.protocol_table = QTableWidget()
        self.protocol_table.setColumnCount(6)
        self.protocol_table.setHorizontalHeaderLabels([
            "协议", "优先级", "启用", "超时(s)", "成功率", "当前状态"
        ])
        self.protocol_table.setRowCount(6)
        
        protocols = [
            ("TCP", 10, True, 5.0),
            ("UDP", 8, True, 3.0),
            ("WebSocket", 6, True, 10.0),
            ("HTTP/2", 5, True, 10.0),
            ("QUIC", 4, False, 8.0),
            ("RELAY", 2, True, 15.0),
        ]
        
        for i, (name, priority, enabled, timeout) in enumerate(protocols):
            self.protocol_table.setItem(i, 0, QTableWidgetItem(name))
            
            priority_spin = QSpinBox()
            priority_spin.setRange(0, 10)
            priority_spin.setValue(priority)
            self.protocol_table.setCellWidget(i, 1, priority_spin)
            
            enabled_check = QCheckBox()
            enabled_check.setChecked(enabled)
            self.protocol_table.setCellWidget(i, 2, enabled_check)
            
            timeout_spin = QDoubleSpinBox()
            timeout_spin.setRange(1, 60)
            timeout_spin.setValue(timeout)
            self.protocol_table.setCellWidget(i, 3, timeout_spin)
            
            self.protocol_table.setItem(i, 4, QTableWidgetItem("100%"))
            self.protocol_table.setItem(i, 5, QTableWidgetItem("空闲"))
        
        layout.addWidget(self.protocol_table)
        
        # 降级策略
        strategy_group = QGroupBox("降级策略")
        strategy_layout = QFormLayout(strategy_group)
        
        self.auto_fallback = QCheckBox("自动降级")
        self.auto_fallback.setChecked(True)
        strategy_layout.addRow("自动降级:", self.auto_fallback)
        
        self.latency_threshold = QDoubleSpinBox()
        self.latency_threshold.setRange(100, 5000)
        self.latency_threshold.setValue(500)
        self.latency_threshold.setSuffix(" ms")
        strategy_layout.addRow("延迟阈值:", self.latency_threshold)
        
        self.packet_loss_threshold = QDoubleSpinBox()
        self.packet_loss_threshold.setRange(1, 50)
        self.packet_loss_threshold.setValue(10)
        self.packet_loss_threshold.setSuffix(" %")
        strategy_layout.addRow("丢包阈值:", self.packet_loss_threshold)
        
        self.recovery_interval = QDoubleSpinBox()
        self.recovery_interval.setRange(10, 300)
        self.recovery_interval.setValue(30)
        self.recovery_interval.setSuffix(" s")
        strategy_layout.addRow("恢复检测间隔:", self.recovery_interval)
        
        layout.addWidget(strategy_group)
        
        # 统计
        stats_group = QGroupBox("协议统计")
        stats_layout = QFormLayout(stats_group)
        
        self.total_attempts = QLabel("0")
        stats_layout.addRow("总尝试次数:", self.total_attempts)
        
        self.successful = QLabel("0")
        stats_layout.addRow("成功次数:", self.successful)
        
        self.fallback_count = QLabel("0")
        stats_layout.addRow("降级次数:", self.fallback_count)
        
        self.recovery_count = QLabel("0")
        stats_layout.addRow("恢复次数:", self.recovery_count)
        
        layout.addWidget(stats_group)
        
        layout.addStretch()


class QualityMonitorPanel(QWidget):
    """质量监控面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
        # 启动更新定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_metrics)
        self.timer.start(1000)
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 质量总览
        overview_group = QGroupBox("网络质量总览")
        overview_layout = QGridLayout(overview_group)
        
        # 质量分数
        self.quality_score = QLabel("100")
        self.quality_score.setStyleSheet("font-size: 48px; font-weight: bold; color: #009900;")
        self.quality_score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overview_layout.addWidget(self.quality_score, 0, 0, 2, 1)
        
        overview_layout.addWidget(QLabel("质量评分"), 0, 1)
        self.quality_label = QLabel("优秀")
        self.quality_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #009900;")
        overview_layout.addWidget(self.quality_label, 1, 1)
        
        # 详细指标
        metrics = [
            ("延迟", "25 ms", "#009900"),
            ("带宽", "50 Mbps", "#009900"),
            ("丢包率", "0.1%", "#009900"),
            ("抖动", "5 ms", "#009900"),
        ]
        
        for i, (name, value, color) in enumerate(metrics):
            overview_layout.addWidget(QLabel(name), i // 2, 2 + (i % 2))
            label = QLabel(value)
            label.setStyleSheet(f"color: {color}; font-weight: bold;")
            overview_layout.addWidget(label, i // 2, 3 + (i % 2))
        
        layout.addWidget(overview_group)
        
        # 延迟趋势
        latency_group = QGroupBox("延迟趋势 (最近60秒)")
        latency_layout = QVBoxLayout(latency_group)
        
        self.latency_chart = QTextEdit()
        self.latency_chart.setReadOnly(True)
        self.latency_chart.setMaximumHeight(100)
        self.latency_chart.setPlainText("│\n│\n│\n│\n│")
        latency_layout.addWidget(self.latency_chart)
        
        layout.addWidget(latency_group)
        
        # 百分位数
        percentile_group = QGroupBox("延迟百分位数")
        percentile_layout = QFormLayout(percentile_group)
        
        self.p50 = QLabel("20 ms")
        percentile_layout.addRow("P50:", self.p50)
        
        self.p95 = QLabel("45 ms")
        percentile_layout.addRow("P95:", self.p95)
        
        self.p99 = QLabel("80 ms")
        percentile_layout.addRow("P99:", self.p99)
        
        self.p999 = QLabel("150 ms")
        percentile_layout.addRow("P99.9:", self.p999)
        
        layout.addWidget(percentile_group)
        
        # 告警记录
        alert_group = QGroupBox("最近告警")
        alert_layout = QVBoxLayout(alert_group)
        
        self.alert_list = QTextEdit()
        self.alert_list.setReadOnly(True)
        self.alert_list.setMaximumHeight(80)
        alert_layout.addWidget(self.alert_list)
        
        layout.addWidget(alert_group)
        
        layout.addStretch()
    
    def update_metrics(self):
        """更新指标"""
        import random
        # 模拟数据
        latency = 20 + int(time.time() % 30)
        if latency > 40:
            self.quality_score.setStyleSheet("font-size: 48px; font-weight: bold; color: #CC9900;")
            self.quality_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #CC9900;")
            self.quality_label.setText("良好")
        else:
            self.quality_score.setStyleSheet("font-size: 48px; font-weight: bold; color: #009900;")
            self.quality_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #009900;")
            self.quality_label.setText("优秀")
        
        self.quality_score.setText(str(100 - latency * 2))


class RecoveryPanel(QWidget):
    """故障恢复面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 恢复策略
        strategy_group = QGroupBox("恢复策略")
        strategy_layout = QVBoxLayout(strategy_group)
        
        strategies = [
            ("快速重试", "立即重试失败的操作", True),
            ("转移重试", "尝试其他服务器/路径", True),
            ("降级重试", "降级到备用协议", True),
            ("离线队列", "保存操作等待网络恢复", True),
            ("检查点恢复", "从保存的检查点恢复任务", True),
        ]
        
        for name, desc, checked in strategies:
            row = QHBoxLayout()
            cb = QCheckBox(name)
            cb.setChecked(checked)
            row.addWidget(cb)
            row.addWidget(QLabel(desc))
            row.addStretch()
            strategy_layout.addLayout(row)
        
        layout.addWidget(strategy_group)
        
        # 故障记录
        fault_group = QGroupBox("故障记录")
        fault_layout = QVBoxLayout(fault_group)
        
        self.fault_table = QTableWidget()
        self.fault_table.setColumnCount(5)
        self.fault_table.setHorizontalHeaderLabels([
            "时间", "类型", "目标", "原因", "状态"
        ])
        
        # 添加示例数据
        self.fault_table.insertRow(0)
        self.fault_table.setItem(0, 0, QTableWidgetItem("16:20:15"))
        self.fault_table.setItem(0, 1, QTableWidgetItem("连接超时"))
        self.fault_table.setItem(0, 2, QTableWidgetItem("139.199.124.242"))
        self.fault_table.setItem(0, 3, QTableWidgetItem("网络不可达"))
        self.fault_table.setItem(0, 4, QTableWidgetItem("已恢复"))
        self.fault_table.item(0, 4).setForeground(QColor(0, 150, 0))
        
        self.fault_table.setRowCount(5)
        fault_layout.addWidget(self.fault_table)
        
        layout.addWidget(fault_group)
        
        # 检查点管理
        checkpoint_group = QGroupBox("检查点管理")
        checkpoint_layout = QFormLayout(checkpoint_group)
        
        self.checkpoint_list = QComboBox()
        self.checkpoint_list.addItems([
            "任务-2026-04-15-16:15:00",
            "任务-2026-04-15-16:10:00",
            "任务-2026-04-15-16:05:00",
        ])
        checkpoint_layout.addRow("可用检查点:", self.checkpoint_list)
        
        checkpoint_btns = QHBoxLayout()
        checkpoint_btns.addWidget(QPushButton("查看详情"))
        checkpoint_btns.addWidget(QPushButton("恢复到检查点"))
        checkpoint_btns.addWidget(QPushButton("删除检查点"))
        checkpoint_layout.addRow("", checkpoint_btns)
        
        layout.addWidget(checkpoint_group)
        
        # 离线队列
        queue_group = QGroupBox("离线队列")
        queue_layout = QFormLayout(queue_group)
        
        self.queue_count = QLabel("0")
        queue_layout.addRow("待同步任务:", self.queue_count)
        
        self.queue_size = QLabel("0 KB")
        queue_layout.addRow("队列大小:", self.queue_size)
        
        queue_btns = QHBoxLayout()
        queue_btns.addWidget(QPushButton("查看队列"))
        queue_btns.addWidget(QPushButton("立即同步"))
        queue_btns.addWidget(QPushButton("清空队列"))
        queue_layout.addRow("", queue_btns)
        
        layout.addWidget(queue_group)
        
        layout.addStretch()


class ComponentPreviewPanel(QWidget):
    """组件预览面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 按钮组件
        btn_group = QGroupBox("按钮组件")
        btn_layout = QHBoxLayout(btn_group)
        btn_layout.addWidget(QPushButton("主要按钮"))
        btn_layout.addWidget(QPushButton("次要按钮"))
        
        disabled_btn = QPushButton("禁用按钮")
        disabled_btn.setEnabled(False)
        btn_layout.addWidget(disabled_btn)
        
        loading_btn = QPushButton("加载中...")
        loading_btn.setEnabled(False)
        btn_layout.addWidget(loading_btn)
        
        layout.addWidget(btn_group)
        
        # 输入组件
        input_group = QGroupBox("输入组件")
        input_layout = QFormLayout(input_group)
        
        input_layout.addRow("文本输入:", QLineEdit())
        
        spin_layout = QHBoxLayout()
        spin_layout.addWidget(QSpinBox())
        spin_layout.addWidget(QDoubleSpinBox())
        input_layout.addRow("数值输入:", spin_layout)
        
        combo_layout = QHBoxLayout()
        combo = QComboBox()
        combo.addItems(["选项1", "选项2", "选项3"])
        combo_layout.addWidget(combo)
        combo_layout.addWidget(QCheckBox("复选框"))
        input_layout.addRow("选择输入:", combo_layout)
        
        layout.addWidget(input_group)
        
        # 进度条
        progress_group = QGroupBox("进度组件")
        progress_layout = QVBoxLayout(progress_group)
        
        progress1 = QProgressBar()
        progress1.setValue(50)
        progress_layout.addWidget(progress1)
        
        progress2 = QProgressBar()
        progress2.setValue(75)
        progress2.setFormat("%p% 完成")
        progress_layout.addWidget(progress2)
        
        layout.addWidget(progress_group)
        
        # 布局组件
        layout_group = QGroupBox("布局组件")
        layout_layout = QGridLayout(layout_group)
        
        for i in range(3):
            for j in range(3):
                cell = QFrame()
                cell.setFrameShape(QFrame.Shape.StyledPanel)
                cell.setStyleSheet("background: #f0f0f0; border: 1px solid #ccc; padding: 20px;")
                cell.setLayout(QVBoxLayout())
                cell.layout().addWidget(QLabel(f"单元格 {i},{j}"))
                layout_layout.addWidget(cell, i, j)
        
        layout.addWidget(layout_group)
        
        layout.addStretch()


class LightweightUIPanel(QWidget):
    """
    轻量级UI与强化网络层综合面板
    
    集成 6 个标签页:
    1. 概览
    2. 中继服务器
    3. 网络探测
    4. 协议管理
    5. 质量监控
    6. 故障恢复
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
        # 启动状态更新定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 标签页
        self.tabs = QTabWidget()
        
        # 1. 概览
        self.overview_tab = self.create_overview_tab()
        self.tabs.addTab(self.overview_tab, "概览")
        
        # 2. 中继服务器
        self.relay_panel = RelayPanel()
        self.tabs.addTab(self.relay_panel, "中继服务器")
        
        # 3. 网络探测
        self.network_probe_panel = NetworkProbePanel()
        self.tabs.addTab(self.network_probe_panel, "网络探测")
        
        # 4. 协议管理
        self.protocol_panel = ProtocolPanel()
        self.tabs.addTab(self.protocol_panel, "协议管理")
        
        # 5. 质量监控
        self.quality_panel = QualityMonitorPanel()
        self.tabs.addTab(self.quality_panel, "质量监控")
        
        # 6. 故障恢复
        self.recovery_panel = RecoveryPanel()
        self.tabs.addTab(self.recovery_panel, "故障恢复")
        
        # 7. 组件预览
        self.component_panel = ComponentPreviewPanel()
        self.tabs.addTab(self.component_panel, "组件预览")
        
        layout.addWidget(self.tabs)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)
        layout.addWidget(self.status_bar)
    
    def create_overview_tab(self) -> QWidget:
        """创建概览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 系统状态卡片
        status_card = QGroupBox("系统状态")
        status_layout = QGridLayout(status_card)
        
        # 网络状态
        self.network_status = QLabel("● 离线")
        self.network_status.setStyleSheet("color: #CC9900; font-weight: bold;")
        status_layout.addWidget(QLabel("网络状态:"), 0, 0)
        status_layout.addWidget(self.network_status, 0, 1)
        
        # 连接模式
        self.connection_mode = QLabel("自动")
        status_layout.addWidget(QLabel("连接模式:"), 0, 2)
        status_layout.addWidget(self.connection_mode, 0, 3)
        
        # 当前协议
        self.current_protocol = QLabel("TCP")
        status_layout.addWidget(QLabel("当前协议:"), 1, 0)
        status_layout.addWidget(self.current_protocol, 1, 1)
        
        # 中继服务器
        self.relay_server = QLabel("139.199.124.242")
        status_layout.addWidget(QLabel("中继服务器:"), 1, 2)
        status_layout.addWidget(self.relay_server, 1, 3)
        
        # 质量评分
        self.overview_quality = QLabel("95")
        status_layout.addWidget(QLabel("质量评分:"), 2, 0)
        status_layout.addWidget(self.overview_quality, 2, 1)
        
        # 延迟
        self.overview_latency = QLabel("25 ms")
        status_layout.addWidget(QLabel("当前延迟:"), 2, 2)
        status_layout.addWidget(self.overview_latency, 2, 3)
        
        layout.addWidget(status_card)
        
        # 快速操作
        action_card = QGroupBox("快速操作")
        action_layout = QHBoxLayout(action_card)
        
        action_layout.addWidget(QPushButton("重新探测网络"))
        action_layout.addWidget(QPushButton("切换到中继模式"))
        action_layout.addWidget(QPushButton("导出日志"))
        action_layout.addWidget(QPushButton("系统设置"))
        
        layout.addWidget(action_card)
        
        # 性能监控
        perf_card = QGroupBox("性能监控")
        perf_layout = QFormLayout(perf_card)
        
        self.cpu_usage = QLabel("5%")
        perf_layout.addRow("CPU使用:", self.cpu_usage)
        
        self.memory_usage = QLabel("128 MB")
        perf_layout.addRow("内存占用:", self.memory_usage)
        
        self.thread_count = QLabel("12")
        perf_layout.addRow("线程数:", self.thread_count)
        
        self.fps = QLabel("60")
        perf_layout.addRow("帧率:", self.fps)
        
        layout.addWidget(perf_card)
        
        layout.addStretch()
        
        return widget
    
    def update_status(self):
        """更新状态"""
        import random
        
        # 模拟数据更新
        latency = 20 + int(time.time() % 30)
        self.overview_latency.setText(f"{latency} ms")
        
        quality = max(0, 100 - latency * 2)
        self.overview_quality.setText(f"{quality}")
        
        if quality >= 80:
            self.network_status.setText("● 优秀")
            self.network_status.setStyleSheet("color: #009900; font-weight: bold;")
        elif quality >= 50:
            self.network_status.setText("● 良好")
            self.network_status.setStyleSheet("color: #CC9900; font-weight: bold;")
        else:
            self.network_status.setText("● 较差")
            self.network_status.setStyleSheet("color: #CC0000; font-weight: bold;")


# 单例实例
_panel_instance: Optional[LightweightUIPanel] = None


def get_lightweight_ui_panel() -> LightweightUIPanel:
    """获取面板实例"""
    global _panel_instance
    if _panel_instance is None:
        _panel_instance = LightweightUIPanel()
    return _panel_instance


__all__ = [
    "LightweightUIPanel",
    "RelayPanel",
    "NetworkProbePanel",
    "ProtocolPanel",
    "QualityMonitorPanel",
    "RecoveryPanel",
    "ComponentPreviewPanel",
    "RelayServerDialog",
    "get_lightweight_ui_panel",
]
