# -*- coding: utf-8 -*-
"""
P2P网络自举协议 UI 面板
P2P Network Bootstrap UI Panel

4层架构可视化：
- Phase 1: 节点即配置源
- Phase 2: 连接池与QoS
- Phase 3: Gossip协议
- Phase 4: WebRTC节点化

作者：Hermes Desktop V2.0
版本：1.0.0
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTabWidget, QTextEdit,
    QListWidget, QListWidgetItem, QComboBox, QSpinBox,
    QProgressBar, QGroupBox, QScrollArea, QFrame,
    QLineEdit, QCheckBox, QSlider, QStackedWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsLineItem, QDialog, QFormLayout, QProgressBar
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QSize,
    QRectF, QPointF, QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QColor, QBrush, QPen, QFont, QPainter,
    QIcon, QAction, QPixmap
)


class P2PBootstrapPanel(QWidget):
    """P2P网络自举协议主面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.p2p_engine = None
        self.current_node_id = f"node_{uuid.uuid4().hex[:8]}"
        self.init_ui()
        self.setup_timers()

    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("🌐 P2P网络自举协议 - 感染式网络")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self.status_label = QLabel("状态: 未连接")
        self.status_label.setStyleSheet("color: #888;")
        title_layout.addWidget(self.status_label)

        main_layout.addLayout(title_layout)

        # 创建标签页
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # 4个核心标签页 + 概览
        self.tab_overview = OverviewTab(self)
        self.tab_topology = TopologyTab(self)
        self.tab_connection = ConnectionTab(self)
        self.tab_gossip = GossipTab(self)
        self.tab_webrtc = WebRTCTab(self)

        self.tabs.addTab(self.tab_overview, "🏠 概览")
        self.tabs.addTab(self.tab_topology, "🕸️ 拓扑")
        self.tabs.addTab(self.tab_connection, "🔗 连接池")
        self.tabs.addTab(self.tab_gossip, "🦠 Gossip")
        self.tabs.addTab(self.tab_webrtc, "📡 WebRTC")

        main_layout.addWidget(self.tabs)

        self.setLayout(main_layout)

    def setup_timers(self):
        """设置定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(2000)  # 2秒更新

    def update_status(self):
        """更新状态"""
        if self.p2p_engine and self.p2p_engine.is_running:
            status = self.p2p_engine.get_network_status()
            self.tab_overview.refresh(status)
            self.tab_topology.refresh(status)
            self.tab_connection.refresh(status)
            self.tab_gossip.refresh(status)
            self.tab_webrtc.refresh(status)

            self.status_label.setText("状态: 运行中")
            self.status_label.setStyleSheet("color: #4CAF50;")
        else:
            self.status_label.setText("状态: 未连接")
            self.status_label.setStyleSheet("color: #888;")

    def set_engine(self, engine):
        """设置P2P引擎"""
        self.p2p_engine = engine

    async def start_network(self, bootstrap_url: str = None):
        """启动网络"""
        if self.p2p_engine:
            await self.p2p_engine.start()
            if bootstrap_url:
                await self.p2p_engine.connect_to_network(bootstrap_url)


class OverviewTab(QWidget):
    """概览标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 4层架构状态卡片
        phases_group = QGroupBox("📊 4层架构状态")
        phases_layout = QGridLayout()

        # Phase 1
        self.phase1_card = self.create_phase_card(
            "Phase 1",
            "节点即配置源",
            "nodes",
            "0"
        )
        phases_layout.addWidget(self.phase1_card, 0, 0)

        # Phase 2
        self.phase2_card = self.create_phase_card(
            "Phase 2",
            "连接池QoS",
            "connections",
            "0/0"
        )
        phases_layout.addWidget(self.phase2_card, 0, 1)

        # Phase 3
        self.phase3_card = self.create_phase_card(
            "Phase 3",
            "Gossip自愈",
            "gossip",
            "0"
        )
        phases_layout.addWidget(self.phase3_card, 1, 0)

        # Phase 4
        self.phase4_card = self.create_phase_card(
            "Phase 4",
            "WebRTC节点",
            "webrtc",
            "0"
        )
        phases_layout.addWidget(self.phase4_card, 1, 1)

        phases_group.setLayout(phases_layout)
        layout.addWidget(phases_group)

        # 网络拓扑可视化
        topology_group = QGroupBox("🕸️ 网络拓扑视图")
        topology_layout = QVBoxLayout()
        self.topology_view = NetworkTopologyView(self)
        self.topology_view.setMinimumHeight(250)
        topology_layout.addWidget(self.topology_view)
        topology_group.setLayout(topology_layout)
        layout.addWidget(topology_group, 1)

        # 统计信息
        stats_group = QGroupBox("📈 实时统计")
        stats_layout = QGridLayout()

        self.total_nodes_label = QLabel("总节点数: 0")
        self.alive_nodes_label = QLabel("活跃节点: 0")
        self.connections_label = QLabel("活动连接: 0")
        self.latency_label = QLabel("平均延迟: --")

        stats_layout.addWidget(self.total_nodes_label, 0, 0)
        stats_layout.addWidget(self.alive_nodes_label, 0, 1)
        stats_layout.addWidget(self.connections_label, 1, 0)
        stats_layout.addWidget(self.latency_label, 1, 1)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        self.setLayout(layout)

    def create_phase_card(self, title: str, subtitle: str, icon: str, value: str) -> QFrame:
        """创建阶段状态卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: rgba(40, 40, 80, 150);
                border-radius: 10px;
                border: 2px solid #555;
            }
        """)
        card.setFixedSize(200, 100)

        layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #4FC3F7;")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("color: #aaa;")

        value_label = QLabel(value)
        value_label.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        value_label.setStyleSheet("color: #FFD700;")

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(value_label)

        return card

    def refresh(self, status: Dict):
        """刷新显示"""
        if not status:
            return

        # 更新Phase卡片
        p1 = status.get("phase1_discovery", {})
        self.phase1_card.children()[2].setText(str(p1.get("alive_nodes", 0)))

        p2 = status.get("phase2_connection_pool", {})
        total = p2.get("total_connections", 0)
        connected = p2.get("connected", 0)
        self.phase2_card.children()[2].setText(f"{connected}/{total}")

        p3 = status.get("phase3_gossip", {})
        self.phase3_card.children()[2].setText(str(p3.get("total_peers", 0)))

        p4 = status.get("phase4_webrtc", {})
        nodes = p4.get("browser_nodes", {}).get("total", 0)
        self.phase4_card.children()[2].setText(str(nodes))

        # 更新统计
        self.total_nodes_label.setText(f"总节点数: {p1.get('total_known_nodes', 0)}")
        self.alive_nodes_label.setText(f"活跃节点: {p1.get('alive_nodes', 0)}")
        self.connections_label.setText(f"活动连接: {connected}")


class NetworkTopologyView(QGraphicsView):
    """网络拓扑可视化视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background-color: #1a1a2e;")

        # 节点位置
        self.nodes = {}

    def refresh_topology(self, nodes: List[Dict]):
        """刷新拓扑"""
        self.scene.clear()
        self.nodes.clear()

        if not nodes:
            return

        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(self.width(), self.height()) / 3

        # 绘制中心节点
        self._draw_center_node(center_x, center_y)

        # 绘制周围节点
        for i, node in enumerate(nodes[:12]):  # 最多12个节点
            angle = (2 * 3.14159 * i) / min(len(nodes), 12)
            x = center_x + radius * abs(1 - i % 2 * 0.3) * (1 if i % 2 == 0 else -1) * abs(1 - i % 2) * (1 if i % 4 < 2 else -1) * 0.7 + radius * 0.5 * (1 if i % 4 < 2 else -1)
            y = center_y + radius * abs(1 - i % 2 * 0.3) * (1 if i % 4 < 2 else -1) * abs(1 - i % 2) * (1 if i % 4 < 2 else -1) * 0.7 + radius * 0.5 * (1 if i % 4 < 2 else -1)

            self._draw_node(x, y, node)

    def _draw_center_node(self, x: float, y: float):
        """绘制中心节点"""
        # 光环
        glow = QGraphicsEllipseItem(x - 40, y - 40, 80, 80)
        glow.setBrush(QBrush(QColor(100, 200, 255, 50)))
        glow.setPen(Qt.NoPen)
        self.scene.addItem(glow)

        # 节点
        node = QGraphicsEllipseItem(x - 25, y - 25, 50, 50)
        node.setBrush(QBrush(QColor(100, 200, 255)))
        node.setPen(QPen(QColor(255, 255, 255), 2))
        self.scene.addItem(node)

        # 标签
        label = self.scene.addText("我")
        label.setPos(x - 10, y - 10)
        label.setDefaultTextColor(QColor(255, 255, 255))

    def _draw_node(self, x: float, y: float, node: Dict):
        """绘制普通节点"""
        role = node.get("role", "peer")

        # 颜色根据角色
        colors = {
            "peer": QColor(150, 150, 200),
            "relay": QColor(200, 150, 100),
            "bootstrap": QColor(255, 200, 100),
            "webrtc": QColor(100, 200, 150)
        }

        color = colors.get(role, colors["peer"])

        # 节点
        node_item = QGraphicsEllipseItem(x - 15, y - 15, 30, 30)
        node_item.setBrush(QBrush(color))
        node_item.setPen(QPen(QColor(255, 255, 255), 1))
        self.scene.addItem(node_item)

        # 标签
        node_id = node.get("node_id", "unknown")[:6]
        label = self.scene.addText(node_id)
        label.setPos(x - 20, y + 20)
        label.setDefaultTextColor(QColor(200, 200, 200))
        label.setScale(0.7)


class TopologyTab(QWidget):
    """拓扑标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)

        # 左侧：节点列表
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)

        list_group = QGroupBox("📍 已知节点")
        list_layout = QVBoxLayout()
        self.node_list = QListWidget()
        list_layout.addWidget(self.node_list)
        list_group.setLayout(list_layout)
        left_layout.addWidget(list_group, 1)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新拓扑")
        refresh_btn.clicked.connect(self.on_refresh)
        left_layout.addWidget(refresh_btn)

        layout.addWidget(left_panel, 1)

        # 右侧：节点详情
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        detail_group = QGroupBox("🔍 节点详情")
        detail_layout = QFormLayout()
        self.detail_node_id = QLabel("-")
        self.detail_url = QLabel("-")
        self.detail_role = QLabel("-")
        self.detail_status = QLabel("-")
        self.detail_latency = QLabel("-")
        self.detail_weight = QLabel("-")
        detail_layout.addRow("节点ID:", self.detail_node_id)
        detail_layout.addRow("URL:", self.detail_url)
        detail_layout.addRow("角色:", self.detail_role)
        detail_layout.addRow("状态:", self.detail_status)
        detail_layout.addRow("延迟:", self.detail_latency)
        detail_layout.addRow("权重:", self.detail_weight)
        detail_group.setLayout(detail_layout)
        right_layout.addWidget(detail_group)

        # 操作按钮
        action_group = QGroupBox("⚡ 操作")
        action_layout = QVBoxLayout()
        connect_btn = QPushButton("🔗 连接到节点")
        disconnect_btn = QPushButton("断开连接")
        action_layout.addWidget(connect_btn)
        action_layout.addWidget(disconnect_btn)
        action_group.setLayout(action_layout)
        right_layout.addWidget(action_group)

        layout.addWidget(right_panel, 1)

        self.setLayout(layout)

    def on_refresh(self):
        """刷新"""
        if self.parent_panel.p2p_engine:
            topology = self.parent_panel.p2p_engine.get_topology()
            nodes = topology.get("nodes", [])
            self.parent_panel.tab_overview.topology_view.refresh_topology(nodes)

    def refresh(self, status: Dict):
        """刷新显示"""
        if not status:
            return

        self.node_list.clear()

        # Phase 1数据
        p1 = status.get("phase1_discovery", {})
        alive = p1.get("alive_nodes", 0)

        # 添加模拟节点
        for i in range(min(alive, 10)):
            self.node_list.addItem(f"节点 {i+1} - 延迟: {50+i*10}ms")


class ConnectionTab(QWidget):
    """连接池标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 连接池状态
        pool_group = QGroupBox("🔗 连接池状态")
        pool_layout = QGridLayout()

        self.pool_total = QLabel("总连接: 0")
        self.pool_connected = QLabel("已连接: 0")
        self.pool_primary = QLabel("主连接: -")
        self.pool_failover = QLabel("故障转移: 0")
        pool_layout.addWidget(self.pool_total, 0, 0)
        pool_layout.addWidget(self.pool_connected, 0, 1)
        pool_layout.addWidget(self.pool_primary, 1, 0)
        pool_layout.addWidget(self.pool_failover, 1, 1)
        pool_group.setLayout(pool_layout)
        layout.addWidget(pool_group)

        # 连接列表
        conn_group = QGroupBox("📡 活动连接")
        conn_layout = QVBoxLayout()
        self.conn_table = QTableWidget()
        self.conn_table.setColumnCount(5)
        self.conn_table.setHorizontalHeaderLabels(["节点", "状态", "质量", "延迟", "主连接"])
        conn_layout.addWidget(self.conn_table)
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group, 1)

        # QoS路由
        qos_group = QGroupBox("🎯 QoS路由")
        qos_layout = QFormLayout()
        self.qos_mode = QLabel("自动")
        self.qos_threshold = QLabel("200ms")
        qos_layout.addRow("路由模式:", self.qos_mode)
        qos_layout.addRow("延迟阈值:", self.qos_threshold)
        qos_group.setLayout(qos_layout)
        layout.addWidget(qos_group)

        self.setLayout(layout)

    def refresh(self, status: Dict):
        """刷新显示"""
        if not status:
            return

        p2 = status.get("phase2_connection_pool", {})

        self.pool_total.setText(f"总连接: {p2.get('total_connections', 0)}")
        self.pool_connected.setText(f"已连接: {p2.get('connected', 0)}")
        self.pool_primary.setText(f"主连接: {p2.get('primary_node', '-')}")
        self.pool_failover.setText(f"故障转移: {p2.get('total_failovers', 0)}")

        # 更新连接表格
        connections = p2.get("connections", {})
        self.conn_table.setRowCount(len(connections))

        for i, (node_id, conn_info) in enumerate(connections.items()):
            self.conn_table.setItem(i, 0, QTableWidgetItem(node_id[:8]))
            self.conn_table.setItem(i, 1, QTableWidgetItem(conn_info.get("status", "-")))
            self.conn_table.setItem(i, 2, QTableWidgetItem(conn_info.get("quality", "-")))
            self.conn_table.setItem(i, 3, QTableWidgetItem(f"{conn_info.get('latency_ms', 0):.1f}ms"))
            self.conn_table.setItem(i, 4, QTableWidgetItem("✓" if conn_info.get("is_primary") else ""))


class GossipTab(QWidget):
    """Gossip协议标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # Gossip状态
        gossip_group = QGroupBox("🦠 Gossip协议状态")
        gossip_layout = QGridLayout()

        self.gossip_peers = QLabel("对等体: 0")
        self.gossip_healthy = QLabel("健康: 0")
        self.gossip_events = QLabel("事件历史: 0")
        self.gossip_sent = QLabel("已发送: 0")
        self.gossip_received = QLabel("已接收: 0")
        gossip_layout.addWidget(self.gossip_peers, 0, 0)
        gossip_layout.addWidget(self.gossip_healthy, 0, 1)
        gossip_layout.addWidget(self.gossip_events, 1, 0)
        gossip_layout.addWidget(self.gossip_sent, 1, 1)
        gossip_layout.addWidget(self.gossip_received, 2, 0)
        gossip_group.setLayout(gossip_layout)
        layout.addWidget(gossip_group)

        # 事件流
        event_group = QGroupBox("📨 最近事件")
        event_layout = QVBoxLayout()
        self.event_list = QListWidget()
        self.event_list.setMaximumHeight(150)
        event_layout.addWidget(self.event_list)
        event_group.setLayout(event_layout)
        layout.addWidget(event_group)

        # 自愈状态
        healing_group = QGroupBox("🔧 自愈管理")
        healing_layout = QFormLayout()
        self.healing_timeout = QLabel("120秒")
        self.healing_interval = QLabel("30秒")
        healing_layout.addRow("节点超时:", self.healing_timeout)
        healing_layout.addRow("健康检查:", self.healing_interval)
        healing_group.setLayout(healing_layout)
        layout.addWidget(healing_group)

        self.setLayout(layout)

    def refresh(self, status: Dict):
        """刷新显示"""
        if not status:
            return

        p3 = status.get("phase3_gossip", {})

        self.gossip_peers.setText(f"对等体: {p3.get('total_peers', 0)}")
        self.gossip_healthy.setText(f"健康: {p3.get('healthy_peers', 0)}")
        self.gossip_events.setText(f"事件历史: {p3.get('events_in_history', 0)}")
        self.gossip_sent.setText(f"已发送: {p3.get('events_sent', 0)}")
        self.gossip_received.setText(f"已接收: {p3.get('events_received', 0)}")


class WebRTCTab(QWidget):
    """WebRTC标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # WebRTC状态
        webrtc_group = QGroupBox("📡 WebRTC网络")
        webrtc_layout = QGridLayout()

        self.webrtc_gateway = QLabel("网关: -")
        self.webrtc_browser_nodes = QLabel("浏览器节点: 0")
        self.webrtc_relayed = QLabel("已中继: 0")
        webrtc_layout.addWidget(self.webrtc_gateway, 0, 0)
        webrtc_layout.addWidget(self.webrtc_browser_nodes, 0, 1)
        webrtc_layout.addWidget(self.webrtc_relayed, 1, 0)
        webrtc_group.setLayout(webrtc_layout)
        layout.addWidget(webrtc_group)

        # 信令服务器
        signaling_group = QGroupBox("📡 信令服务器")
        signaling_layout = QFormLayout()
        self.signaling_server = QLabel("-")
        self.signaling_peers = QLabel("已注册对等体: 0")
        signaling_layout.addRow("服务器:", self.signaling_server)
        signaling_layout.addRow("状态:", self.signaling_peers)
        signaling_group.setLayout(signaling_layout)
        layout.addWidget(signaling_group)

        # 浏览器节点列表
        browser_group = QGroupBox("🌐 浏览器节点")
        browser_layout = QVBoxLayout()
        self.browser_list = QListWidget()
        browser_layout.addWidget(self.browser_list)
        browser_group.setLayout(browser_layout)
        layout.addWidget(browser_list, 1)

        self.setLayout(layout)

    def refresh(self, status: Dict):
        """刷新显示"""
        if not status:
            return

        p4 = status.get("phase4_webrtc", {})
        browser_nodes = p4.get("browser_nodes", {})

        self.webrtc_browser_nodes.setText(f"浏览器节点: {browser_nodes.get('total', 0)}")


# ==================== 便捷函数 ====================

def create_p2p_bootstrap_panel(parent=None) -> P2PBootstrapPanel:
    """创建P2P自举协议面板"""
    panel = P2PBootstrapPanel(parent)
    return panel
