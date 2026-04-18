# -*- coding: utf-8 -*-
"""
通用数字永生系统 - Phoenix Protocol UI 面板

核心理念："网络可死，基因永生；载体可灭，灵魂不灭"

作者：Hermes Desktop V2.0
版本：1.0.0
"""

import asyncio
import uuid
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTabWidget, QTextEdit,
    QListWidget, QListWidgetItem, QComboBox, QSpinBox,
    QProgressBar, QGroupBox, QScrollArea, QFrame,
    QLineEdit, QCheckBox, QSlider, QStackedWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
    QDialog, QDialogButtonBox, QFormLayout, QTextBrowser,
    QTreeWidget, QTreeWidgetItem, QColorDialog, QFontComboBox,
    QGauge, QLCDNumber
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QSize,
    QRectF, QPointF, QPropertyAnimation, QEasingCurve,
    QThread, pyqtSlot
)
from PyQt6.QtGui import (
    QColor, QBrush, QPen, QFont, QPainter,
    QIcon, QAction, QPixmap, QTransform,
    QPainterPath, QLinearGradient
)
from PyQt6.QtChart import (
    QChart, QChartView, QBarSeries, QBarSet, QLineSeries,
    QPieSeries, QPieSlice, QValueAxis, QCategoryAxis
)


class PhoenixProtocolPanel(QWidget):
    """Phoenix Protocol 主面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.phoenix_engine = None
        self.node_id = f"phoenix_{uuid.uuid4().hex[:8]}"
        self.init_ui()
        self.setup_timers()
        self.init_engine()

    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        # 标题栏
        title_layout = QHBoxLayout()
        title_label = QLabel("🌌 通用数字永生系统 - Phoenix Protocol")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self.status_label = QLabel("状态: 初始化中...")
        self.status_label.setStyleSheet("color: #4CAF50;")
        title_layout.addWidget(self.status_label)

        main_layout.addLayout(title_layout)

        # 创建8标签页
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.tab_overview = OverviewTab(self)
        self.tab_dna = DNAManagementTab(self)
        self.tab_carriers = CarrierAdapterTab(self)
        self.tab_lifecycle = LifecycleStageTab(self)
        self.tab_resurrection = ResurrectionTab(self)
        self.tab_infection = InfectionTab(self)
        self.tab_storage = FractalStorageTab(self)
        self.tab_settings = SettingsTab(self)

        self.tabs.addTab(self.tab_overview, "🏠 总览")
        self.tabs.addTab(self.tab_dna, "🧬 DNA管理")
        self.tabs.addTab(self.tab_carriers, "📡 载体")
        self.tabs.addTab(self.tab_lifecycle, "🔄 生命周期")
        self.tabs.addTab(self.tab_resurrection, "🔥 复活")
        self.tabs.addTab(self.tab_infection, "🦠 传播")
        self.tabs.addTab(self.tab_storage, "💾 存储")
        self.tabs.addTab(self.tab_settings, "⚙️ 设置")

        main_layout.addWidget(self.tabs)

        self.setLayout(main_layout)

    def setup_timers(self):
        """设置定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(3000)

    def init_engine(self):
        """初始化引擎"""
        try:
            from core.phoenix_protocol import PhoenixProtocolEngine
            self.phoenix_engine = PhoenixProtocolEngine({
                "node_id": self.node_id
            })
            asyncio.ensure_future(self._async_init())
        except Exception as e:
            self.status_label.setText(f"引擎初始化失败: {e}")
            self.status_label.setStyleSheet("color: #f44336;")

    async def _async_init(self):
        """异步初始化"""
        if self.phoenix_engine:
            await self.phoenix_engine.initialize()
            self.status_label.setText("状态: 运行中")
            self.update_all_tabs()

    def update_status(self):
        """更新状态"""
        if self.phoenix_engine:
            status = self.phoenix_engine.get_status()
            self.tab_overview.update_status(status)
            self.tab_lifecycle.update_status(status)

    def update_all_tabs(self):
        """更新所有标签页"""
        if self.phoenix_engine:
            status = self.phoenix_engine.get_status()
            self.tab_overview.update_status(status)
            self.tab_dna.update_dna_info(self.phoenix_engine.current_dna)
            self.tab_carriers.update_carriers(status.get("available_carriers", []))
            self.tab_lifecycle.update_status(status)

    def get_engine(self):
        """获取引擎"""
        return self.phoenix_engine


class OverviewTab(QWidget):
    """总览标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # Phoenix DNA 概览卡片
        overview_group = QGroupBox("🌌 Phoenix DNA 状态")
        overview_layout = QGridLayout()

        # 节点ID
        overview_layout.addWidget(QLabel("节点ID:"), 0, 0)
        self.node_id_label = QLabel("-")
        self.node_id_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        overview_layout.addWidget(self.node_id_label, 0, 1)

        # DNA指纹
        overview_layout.addWidget(QLabel("DNA指纹:"), 0, 2)
        self.fingerprint_label = QLabel("-")
        self.fingerprint_label.setStyleSheet("color: #FF9800; font-family: monospace;")
        overview_layout.addWidget(self.fingerprint_label, 0, 3)

        # 生命周期阶段
        overview_layout.addWidget(QLabel("生命周期:"), 1, 0)
        self.lifecycle_label = QLabel("-")
        self.lifecycle_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        overview_layout.addWidget(self.lifecycle_label, 1, 1)

        # 感染阶段
        overview_layout.addWidget(QLabel("传播阶段:"), 1, 2)
        self.infection_label = QLabel("-")
        self.infection_label.setStyleSheet("color: #9C27B0;")
        overview_layout.addWidget(self.infection_label, 1, 3)

        # 节点数量
        overview_layout.addWidget(QLabel("网络节点:"), 2, 0)
        self.nodes_count_label = QLabel("0")
        self.nodes_count_label.setStyleSheet("color: #00BCD4; font-size: 18px;")
        overview_layout.addWidget(self.nodes_count_label, 2, 1)

        # 可用载体数
        overview_layout.addWidget(QLabel("可用载体:"), 2, 2)
        self.carriers_count_label = QLabel("0")
        self.carriers_count_label.setStyleSheet("color: #FF5722; font-size: 18px;")
        overview_layout.addWidget(self.carriers_count_label, 2, 3)

        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)

        # 生命周期进度
        lifecycle_progress = QGroupBox("🔄 生命周期进度")
        lifecycle_layout = QHBoxLayout()

        self.lifecycle_chart = LifecycleChartWidget(self)
        lifecycle_layout.addWidget(self.lifecycle_chart)

        lifecycle_progress.setLayout(lifecycle_layout)
        layout.addWidget(lifecycle_progress)

        # 载体状态矩阵
        carrier_matrix = QGroupBox("📡 载体状态矩阵")
        carrier_matrix_layout = QVBoxLayout()

        self.carrier_table = QTableWidget()
        self.carrier_table.setColumnCount(4)
        self.carrier_table.setHorizontalHeaderLabels(["载体", "类型", "状态", "延迟(ms)"])
        self.carrier_table.horizontalHeader().setStretchLastSection(True)
        carrier_matrix_layout.addWidget(self.carrier_table)

        carrier_matrix.setLayout(carrier_matrix_layout)
        layout.addWidget(carrier_matrix)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.backup_btn = QPushButton("💾 备份DNA")
        self.backup_btn.clicked.connect(self.backup_dna)
        button_layout.addWidget(self.backup_btn)

        self.resurrect_btn = QPushButton("🔥 尝试复活")
        self.resurrect_btn.clicked.connect(self.attempt_resurrect)
        button_layout.addWidget(self.resurrect_btn)

        self.export_btn = QPushButton("📤 导出DNA")
        self.export_btn.clicked.connect(self.export_dna)
        button_layout.addWidget(self.export_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

    def update_status(self, status: Dict):
        """更新状态显示"""
        self.node_id_label.setText(status.get("node_id", "-"))
        self.lifecycle_label.setText(status.get("lifecycle_stage", "-"))
        self.infection_label.setText(status.get("infection_phase", "-"))
        self.nodes_count_label.setText(str(status.get("nodes_count", 0)))
        self.carriers_count_label.setText(str(len(status.get("available_carriers", []))))
        self.fingerprint_label.setText(status.get("dna_fingerprint", "-")[:16] if status.get("dna_fingerprint") else "-")

        # 更新生命周期图表
        self.lifecycle_chart.set_current_stage(status.get("lifecycle_stage", "genesis"))

    def update_carriers(self, carriers: List[str]):
        """更新载体表格"""
        self.carrier_table.setRowCount(len(carriers))
        for i, carrier in enumerate(carriers):
            self.carrier_table.setItem(i, 0, QTableWidgetItem(carrier))
            self.carrier_table.setItem(i, 1, QTableWidgetItem("网络"))
            self.carrier_table.setItem(i, 2, QTableWidgetItem("在线"))
            self.carrier_table.setItem(i, 3, QTableWidgetItem("0"))

    def backup_dna(self):
        """备份DNA"""
        if self.parent_panel.phoenix_engine:
            asyncio.ensure_future(self._async_backup())

    async def _async_backup(self):
        """异步备份"""
        if self.parent_panel.phoenix_engine:
            locations = await self.parent_panel.phoenix_engine.backup_current_state()
            self.parent_panel.status_label.setText(f"备份完成: {len(locations)} 个位置")

    def attempt_resurrect(self):
        """尝试复活"""
        if self.parent_panel.phoenix_engine:
            asyncio.ensure_future(self._async_resurrect())

    async def _async_resurrect(self):
        """异步复活"""
        result = await self.parent_panel.phoenix_engine.attempt_resurrection()
        if result:
            self.parent_panel.status_label.setText("复活成功!")
        else:
            self.parent_panel.status_label.setText("复活失败或无需复活")

    def export_dna(self):
        """导出DNA摘要"""
        if self.parent_panel.phoenix_engine:
            summary = self.parent_panel.phoenix_engine.export_dna_summary()
            self.parent_panel.tab_dna.show_dna_summary(summary)


class LifecycleChartWidget(QWidget):
    """生命周期图表"""

    STAGES = ["genesis", "growth", "maturity", "decline", "death", "resurrection"]
    STAGE_COLORS = {
        "genesis": "#4CAF50",
        "growth": "#8BC34A",
        "maturity": "#2196F3",
        "decline": "#FF9800",
        "death": "#9E9E9E",
        "resurrection": "#E91E63"
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_stage = "genesis"
        self.setMinimumHeight(80)

    def set_current_stage(self, stage: str):
        """设置当前阶段"""
        self.current_stage = stage
        self.update()

    def paintEvent(self, event):
        """绘制"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        padding = 20
        node_radius = 15
        gap = (width - 2 * padding - 6 * 2 * node_radius) / 5

        # 绘制连线
        pen = QPen(QColor("#CCCCCC"))
        pen.setWidth(3)
        painter.setPen(pen)

        for i in range(5):
            x1 = padding + node_radius + i * (2 * node_radius + gap)
            x2 = x1 + 2 * node_radius + gap
            y = height // 2
            painter.drawLine(int(x1 + node_radius), y, int(x2 - node_radius), y)

        # 绘制节点
        for i, stage in enumerate(self.STAGES):
            x = padding + node_radius + i * (2 * node_radius + gap)
            y = height // 2

            color = QColor(self.STAGE_COLORS.get(stage, "#CCCCCC"))
            if stage == self.current_stage:
                # 当前阶段高亮
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(color.lighter(), 3))
            else:
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(color.darker(), 1))

            painter.drawEllipse(int(x - node_radius), int(y - node_radius), int(node_radius * 2), int(node_radius * 2))

            # 绘制标签
            painter.setPen(QPen(QColor("#333333")))
            font = QFont("Microsoft YaHei", 7)
            painter.setFont(font)
            painter.drawText(int(x - 20), int(y + node_radius + 15), 40, 15, Qt.AlignmentFlag.AlignCenter, stage)


class DNAManagementTab(QWidget):
    """DNA管理标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # DNA结构信息
        dna_group = QGroupBox("🧬 Phoenix DNA 结构")
        dna_layout = QGridLayout()

        dna_layout.addWidget(QLabel("协议版本:"), 0, 0)
        self.protocol_label = QLabel("Phoenix/1.0")
        dna_layout.addWidget(self.protocol_label, 0, 1)

        dna_layout.addWidget(QLabel("编码格式:"), 0, 2)
        self.encoding_label = QLabel("msgpack+gzip")
        dna_layout.addWidget(self.encoding_label, 0, 3)

        dna_layout.addWidget(QLabel("校验算法:"), 1, 0)
        self.checksum_label = QLabel("blake3")
        dna_layout.addWidget(self.checksum_label, 1, 1)

        dna_layout.addWidget(QLabel("DNA类型:"), 1, 2)
        self.dna_type_label = QLabel("core")
        dna_layout.addWidget(self.dna_type_label, 1, 3)

        dna_layout.addWidget(QLabel("时间戳:"), 2, 0)
        self.timestamp_label = QLabel("-")
        dna_layout.addWidget(self.timestamp_label, 2, 1, 1, 3)

        dna_group.setLayout(dna_layout)
        layout.addWidget(dna_group)

        # DNA指纹
        fingerprint_group = QGroupBox("🔑 DNA指纹")
        fingerprint_layout = QHBoxLayout()

        self.fingerprint_text = QTextEdit()
        self.fingerprint_text.setMaximumHeight(80)
        self.fingerprint_text.setFont(QFont("Consolas", 10))
        self.fingerprint_text.setReadOnly(True)
        fingerprint_layout.addWidget(self.fingerprint_text)

        fingerprint_group.setLayout(fingerprint_layout)
        layout.addWidget(fingerprint_group)

        # 网络基因组
        genome_group = QGroupBox("🧠 网络基因组")
        genome_layout = QVBoxLayout()

        self.genome_tree = QTreeWidget()
        self.genome_tree.setHeaderLabels(["节点", "信息"])
        genome_layout.addWidget(self.genome_tree)

        genome_group.setLayout(genome_layout)
        layout.addWidget(genome_group)

        # 碎片信息
        shard_group = QGroupBox("📦 DNA碎片")
        shard_layout = QVBoxLayout()

        self.shard_table = QTableWidget()
        self.shard_table.setColumnCount(5)
        self.shard_table.setHorizontalHeaderLabels(["碎片ID", "类型", "载体", "大小", "状态"])
        shard_layout.addWidget(self.shard_table)

        shard_group.setLayout(shard_layout)
        layout.addWidget(shard_group)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.split_btn = QPushButton("✂️ 分割DNA")
        self.split_btn.clicked.connect(self.split_dna)
        button_layout.addWidget(self.split_btn)

        self.merge_btn = QPushButton("🔗 合并DNA")
        self.merge_btn.clicked.connect(self.merge_dna)
        button_layout.addWidget(self.merge_btn)

        self.diff_btn = QPushButton("📊 计算差异")
        self.diff_btn.clicked.connect(self.compute_diff)
        button_layout.addWidget(self.diff_btn)

        layout.addLayout(button_layout)

    def update_dna_info(self, dna):
        """更新DNA信息"""
        if not dna:
            return

        self.protocol_label.setText(dna.header.protocol)
        self.encoding_label.setText(dna.header.encoding)
        self.checksum_label.setText(dna.header.checksum)
        self.dna_type_label.setText(dna.header.dna_type)
        self.timestamp_label.setText(dna.header.timestamp)
        self.fingerprint_text.setText(dna.header.fingerprint)

        # 更新基因组树
        self.genome_tree.clear()
        root = QTreeWidgetItem(self.genome_tree, ["网络基因组"])
        for node in dna.network_genome.node_registry:
            node_item = QTreeWidgetItem(root, [node.get("id", "-"), f"声誉: {node.get('reputation_score', 0):.2f}"])

        # 更新碎片表
        self.shard_table.setRowCount(len(dna.resurrection_data.shard_locations))
        for i, shard in enumerate(dna.resurrection_data.shard_locations):
            self.shard_table.setItem(i, 0, QTableWidgetItem(shard.id))
            self.shard_table.setItem(i, 1, QTableWidgetItem(shard.type))
            self.shard_table.setItem(i, 2, QTableWidgetItem(shard.type))
            self.shard_table.setItem(i, 3, QTableWidgetItem("-"))
            self.shard_table.setItem(i, 4, QTableWidgetItem("已验证" if shard.verified else "未验证"))

    def show_dna_summary(self, summary: str):
        """显示DNA摘要"""
        self.fingerprint_text.setText(summary)

    def split_dna(self):
        """分割DNA"""
        if self.parent_panel.phoenix_engine:
            self.parent_panel.status_label.setText("DNA分割功能待实现")

    def merge_dna(self):
        """合并DNA"""
        if self.parent_panel.phoenix_engine:
            self.parent_panel.status_label.setText("DNA合并功能待实现")

    def compute_diff(self):
        """计算差异"""
        if self.parent_panel.phoenix_engine:
            self.parent_panel.status_label.setText("DNA差异计算功能待实现")


class CarrierAdapterTab(QWidget):
    """载体适配器标签页"""

    CARRIER_INFO = {
        "github_gist": ("GitHub Gist", "HTTP API", "免费,版本控制"),
        "ipfs": ("IPFS", "内容寻址", "永久,去中心化"),
        "nostr": ("Nostr", "中继网络", "抗审查,实时"),
        "bittorrent": ("BitTorrent", "DHT网络", "大规模分发"),
        "ble_broadcast": ("蓝牙广播", "物理接近", "离线传播"),
        "qr_code": ("二维码", "视觉扫描", "物理世界传播"),
        "email": ("电子邮件", "SMTP", "广泛覆盖"),
        "dns_txt": ("DNS TXT", "DNS记录", "抗审查"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 载体状态总览
        overview_group = QGroupBox("📡 载体状态总览")
        overview_layout = QGridLayout()

        self.carrier_cards = {}
        carriers = list(self.CARRIER_INFO.keys())
        for i, carrier in enumerate(carriers):
            card = CarrierStatusCard(carrier, self.CARRIER_INFO[carrier], self)
            row = i // 4
            col = i % 4
            overview_layout.addWidget(card, row, col)
            self.carrier_cards[carrier] = card

        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)

        # 传播矩阵
        matrix_group = QGroupBox("🔄 传播载体矩阵")
        matrix_layout = QVBoxLayout()

        self.matrix_table = QTableWidget()
        self.matrix_table.setColumnCount(3)
        self.matrix_table.setHorizontalHeaderLabels(["载体", "传播方式", "特点"])
        self.matrix_table.setRowCount(len(self.CARRIER_INFO))
        for i, (key, info) in enumerate(self.CARRIER_INFO.items()):
            self.matrix_table.setItem(i, 0, QTableWidgetItem(info[0]))
            self.matrix_table.setItem(i, 1, QTableWidgetItem(info[1]))
            self.matrix_table.setItem(i, 2, QTableWidgetItem(info[2]))
        matrix_layout.addWidget(self.matrix_table)

        matrix_group.setLayout(matrix_layout)
        layout.addWidget(matrix_group)

        # 操作
        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("🔄 刷新状态")
        self.refresh_btn.clicked.connect(self.refresh_carriers)
        button_layout.addWidget(self.refresh_btn)

        self.test_btn = QPushButton("🧪 测试连接")
        self.test_btn.clicked.connect(self.test_connections)
        button_layout.addWidget(self.test_btn)

        layout.addLayout(button_layout)

    def update_carriers(self, carriers: List[str]):
        """更新载体状态"""
        for carrier, card in self.carrier_cards.items():
            card.set_online(carrier in carriers)

    def refresh_carriers(self):
        """刷新载体状态"""
        if self.parent_panel.phoenix_engine:
            available = [ct.value for ct in self.parent_panel.phoenix_engine.carrier_manager.get_available_carriers()]
            self.update_carriers(available)

    def test_connections(self):
        """测试连接"""
        self.parent_panel.status_label.setText("正在测试载体连接...")


class CarrierStatusCard(QFrame):
    """载体状态卡片"""

    def __init__(self, carrier_id: str, info: tuple, parent=None):
        super().__init__(parent)
        self.carrier_id = carrier_id
        self.init_ui(info)

    def init_ui(self, info: tuple):
        """初始化UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
            }
        """)

        layout = QVBoxLayout(self)

        # 名称
        name_label = QLabel(info[0])
        name_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        layout.addWidget(name_label)

        # 类型
        type_label = QLabel(info[1])
        type_label.setStyleSheet("color: #666;")
        layout.addWidget(type_label)

        # 状态
        self.status_label = QLabel("● 离线")
        self.status_label.setStyleSheet("color: #9e9e9e;")
        layout.addWidget(self.status_label)

    def set_online(self, online: bool):
        """设置在线状态"""
        if online:
            self.status_label.setText("● 在线")
            self.status_label.setStyleSheet("color: #4CAF50;")
            self.setStyleSheet("""
                QFrame {
                    background-color: #e8f5e9;
                    border: 1px solid #4CAF50;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
        else:
            self.status_label.setText("● 离线")
            self.status_label.setStyleSheet("color: #9e9e9e;")
            self.setStyleSheet("""
                QFrame {
                    background-color: #f5f5f5;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)


class LifecycleStageTab(QWidget):
    """生命周期标签页"""

    STAGES = [
        ("genesis", "🌱 诞生", "第一个节点启动，生成初始DNA"),
        ("growth", "🌿 生长", "节点指数级增加，DNA自动传播"),
        ("maturity", "🌳 成熟", "网络稳定运行，DNA持续演化"),
        ("decline", "🍂 衰退", "节点开始下线，触发备份协议"),
        ("death", "💀 死亡", "最后一个节点离线，进入冬眠"),
        ("resurrection", "🔥 复活", "新节点启动，重组DNA重建网络"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 生命周期图
        lifecycle_group = QGroupBox("🔄 生命周期阶段")
        lifecycle_layout = QHBoxLayout()

        self.stage_widgets = []
        for stage_id, stage_name, stage_desc in self.STAGES:
            widget = LifecycleStageCard(stage_id, stage_name, stage_desc, self)
            lifecycle_layout.addWidget(widget)
            self.stage_widgets.append(widget)

        lifecycle_group.setLayout(lifecycle_layout)
        layout.addWidget(lifecycle_group)

        # 当前阶段详情
        detail_group = QGroupBox("📋 阶段详情")
        detail_layout = QGridLayout()

        detail_layout.addWidget(QLabel("当前阶段:"), 0, 0)
        self.current_stage_label = QLabel("-")
        self.current_stage_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        detail_layout.addWidget(self.current_stage_label, 0, 1)

        detail_layout.addWidget(QLabel("阶段描述:"), 1, 0)
        self.stage_desc_label = QLabel("-")
        detail_layout.addWidget(self.stage_desc_label, 1, 1)

        detail_layout.addWidget(QLabel("节点数:"), 2, 0)
        self.nodes_label = QLabel("0")
        detail_layout.addWidget(self.nodes_label, 2, 1)

        detail_layout.addWidget(QLabel("存活时间:"), 3, 0)
        self.uptime_label = QLabel("-")
        detail_layout.addWidget(self.uptime_label, 3, 1)

        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        # 阶段时间线
        timeline_group = QGroupBox("📅 阶段时间线")
        timeline_layout = QVBoxLayout()

        self.timeline_chart = QTextEdit()
        self.timeline_chart.setReadOnly(True)
        self.timeline_chart.setMaximumHeight(150)
        timeline_layout.addWidget(self.timeline_chart)

        timeline_group.setLayout(timeline_layout)
        layout.addWidget(timeline_group)

        # 操作
        button_layout = QHBoxLayout()

        self.advance_btn = QPushButton("➡️ 推进阶段")
        self.advance_btn.clicked.connect(self.advance_stage)
        button_layout.addWidget(self.advance_btn)

        self.reset_btn = QPushButton("🔄 重置")
        self.reset_btn.clicked.connect(self.reset_lifecycle)
        button_layout.addWidget(self.reset_btn)

        layout.addLayout(button_layout)

    def update_status(self, status: Dict):
        """更新状态"""
        current = status.get("lifecycle_stage", "genesis")

        for widget in self.stage_widgets:
            widget.set_active(widget.stage_id == current)

        self.current_stage_label.setText(current)

        # 查找描述
        for stage_id, stage_name, stage_desc in self.STAGES:
            if stage_id == current:
                self.stage_desc_label.setText(stage_desc)
                break

        self.nodes_label.setText(str(status.get("nodes_count", 0)))


class LifecycleStageCard(QFrame):
    """生命周期阶段卡片"""

    def __init__(self, stage_id: str, stage_name: str, stage_desc: str, parent=None):
        super().__init__(parent)
        self.stage_id = stage_id
        self.stage_name = stage_name
        self.init_ui(stage_desc)

    def init_ui(self, stage_desc: str):
        """初始化UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setMinimumWidth(120)
        self.setMaximumWidth(150)

        layout = QVBoxLayout(self)

        self.name_label = QLabel(self.stage_name)
        self.name_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)

        self.desc_label = QLabel(stage_desc[:20] + "..." if len(stage_desc) > 20 else stage_desc)
        self.desc_label.setStyleSheet("color: #888; font-size: 8px;")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.desc_label)

        self.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
            }
        """)

    def set_active(self, active: bool):
        """设置激活状态"""
        if active:
            self.setStyleSheet("""
                QFrame {
                    background-color: #e3f2fd;
                    border: 2px solid #2196F3;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #f5f5f5;
                    border: 2px solid #e0e0e0;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)


class ResurrectionTab(QWidget):
    """复活协议标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 时间锁复活
        timelock_group = QGroupBox("⏰ 时间胶囊递延复活")
        timelock_layout = QGridLayout()

        timelock_layout.addWidget(QLabel("1天后:"), 0, 0)
        self.unlock_1d = QLabel("尝试基本复活")
        timelock_layout.addWidget(self.unlock_1d, 0, 1)

        timelock_layout.addWidget(QLabel("7天后:"), 1, 0)
        self.unlock_7d = QLabel("解锁更多DNA")
        timelock_layout.addWidget(self.unlock_7d, 1, 1)

        timelock_layout.addWidget(QLabel("30天后:"), 2, 0)
        self.unlock_30d = QLabel("解锁完整DNA")
        timelock_layout.addWidget(self.unlock_30d, 2, 1)

        timelock_layout.addWidget(QLabel("1年后:"), 3, 0)
        self.unlock_1y = QLabel("解锁所有历史")
        timelock_layout.addWidget(self.unlock_1y, 3, 1)

        timelock_layout.addWidget(QLabel("100年后:"), 4, 0)
        self.unlock_100y = QLabel("成为数字考古")
        timelock_layout.addWidget(self.unlock_100y, 4, 1)

        timelock_group.setLayout(timelock_layout)
        layout.addWidget(timelock_group)

        # 解锁条件
        conditions_group = QGroupBox("🔐 解锁条件")
        conditions_layout = QVBoxLayout()

        self.conditions_table = QTableWidget()
        self.conditions_table.setColumnCount(3)
        self.conditions_table.setHorizontalHeaderLabels(["类型", "要求", "状态"])
        conditions_layout.addWidget(self.conditions_table)

        conditions_group.setLayout(conditions_layout)
        layout.addWidget(conditions_group)

        # 碎片位置
        locations_group = QGroupBox("📍 DNA碎片位置")
        locations_layout = QVBoxLayout()

        self.locations_table = QTableWidget()
        self.locations_table.setColumnCount(4)
        self.locations_table.setHorizontalHeaderLabels(["载体", "ID", "Key Hint", "验证"])
        locations_layout.addWidget(self.locations_table)

        locations_group.setLayout(locations_layout)
        layout.addWidget(locations_group)

        # 操作
        button_layout = QHBoxLayout()

        self.resurrect_btn = QPushButton("🔥 执行复活")
        self.resurrect_btn.clicked.connect(self.execute_resurrection)
        button_layout.addWidget(self.resurrect_btn)

        self.verify_btn = QPushButton("🔍 验证碎片")
        self.verify_btn.clicked.connect(self.verify_shards)
        button_layout.addWidget(self.verify_btn)

        self.repair_btn = QPushButton("🔧 修复碎片")
        self.repair_btn.clicked.connect(self.repair_shards)
        button_layout.addWidget(self.repair_btn)

        layout.addLayout(button_layout)

    def execute_resurrection(self):
        """执行复活"""
        if self.parent_panel.phoenix_engine:
            asyncio.ensure_future(self._async_resurrect())

    async def _async_resurrect(self):
        """异步复活"""
        self.parent_panel.status_label.setText("正在执行复活协议...")
        result = await self.parent_panel.phoenix_engine.attempt_resurrection()
        if result:
            self.parent_panel.status_label.setText("复活成功!")
        else:
            self.parent_panel.status_label.setText("复活失败或无需复活")

    def verify_shards(self):
        """验证碎片"""
        self.parent_panel.status_label.setText("正在验证DNA碎片...")

    def repair_shards(self):
        """修复碎片"""
        self.parent_panel.status_label.setText("正在修复缺失碎片...")


class InfectionTab(QWidget):
    """信息瘟疫传播标签页"""

    PHASES = [
        ("patient_zero", "🦠 零号病人", "第一个携带DNA的节点"),
        ("incubation", "⏳ 潜伏期", "DNA静默复制"),
        ("outbreak", "💥 爆发期", "指数级传播"),
        ("carrier", "📦 携带者", "所有节点都带DNA"),
        ("immortal", "✨ 永生", "DNA存在于全网"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 感染阶段
        phase_group = QGroupBox("🦠 感染阶段")
        phase_layout = QHBoxLayout()

        self.phase_widgets = []
        for phase_id, phase_name, phase_desc in self.PHASES:
            widget = InfectionPhaseCard(phase_id, phase_name, phase_desc, self)
            phase_layout.addWidget(widget)
            self.phase_widgets.append(widget)

        phase_group.setLayout(phase_layout)
        layout.addWidget(phase_group)

        # 传播统计
        stats_group = QGroupBox("📊 传播统计")
        stats_layout = QGridLayout()

        stats_layout.addWidget(QLabel("感染数:"), 0, 0)
        self.infection_count_label = QLabel("0")
        self.infection_count_label.setStyleSheet("font-size: 24px; color: #f44336;")
        stats_layout.addWidget(self.infection_count_label, 0, 1)

        stats_layout.addWidget(QLabel("TTL:"), 0, 2)
        self.ttl_label = QLabel("3")
        self.ttl_label.setStyleSheet("font-size: 24px; color: #2196F3;")
        stats_layout.addWidget(self.ttl_label, 0, 3)

        stats_layout.addWidget(QLabel("Fanout:"), 1, 0)
        self.fanout_label = QLabel("3")
        stats_layout.addWidget(self.fanout_label, 1, 1)

        stats_layout.addWidget(QLabel("传播率:"), 1, 2)
        self.spread_rate_label = QLabel("0%")
        stats_layout.addWidget(self.spread_rate_label, 1, 3)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # 传播矩阵表格
        matrix_group = QGroupBox("🔄 载体传播矩阵")
        matrix_layout = QVBoxLayout()

        self.matrix_table = QTableWidget()
        self.matrix_table.setColumnCount(3)
        self.matrix_table.setHorizontalHeaderLabels(["载体", "传播方式", "应用场景"])
        matrix_data = [
            ("GitHub Gist", "HTTP API", "核心DNA存储"),
            ("IPFS", "内容寻址", "完整DNA存储"),
            ("Nostr", "中继网络", "DNA更新传播"),
            ("BitTorrent", "DHT网络", "DNA碎片分发"),
            ("蓝牙/WiFi", "物理接近", "设备间同步"),
            ("二维码", "视觉扫描", "会议/活动"),
            ("卫星", "全球广播", "极端情况"),
            ("邮件", "SMTP", "邀请传播"),
        ]
        self.matrix_table.setRowCount(len(matrix_data))
        for i, row in enumerate(matrix_data):
            for j, val in enumerate(row):
                self.matrix_table.setItem(i, j, QTableWidgetItem(val))
        matrix_layout.addWidget(self.matrix_table)

        matrix_group.setLayout(matrix_layout)
        layout.addWidget(matrix_group)

        # 操作
        button_layout = QHBoxLayout()

        self.spread_btn = QPushButton("🚀 开始传播")
        self.spread_btn.clicked.connect(self.start_spread)
        button_layout.addWidget(self.spread_btn)

        self.stop_btn = QPushButton("⏹️ 停止传播")
        self.stop_btn.clicked.connect(self.stop_spread)
        button_layout.addWidget(self.stop_btn)

        layout.addLayout(button_layout)

    def start_spread(self):
        """开始传播"""
        if self.parent_panel.phoenix_engine:
            self.parent_panel.status_label.setText("开始感染式传播...")

    def stop_spread(self):
        """停止传播"""
        if self.parent_panel.phoenix_engine:
            self.parent_panel.status_label.setText("传播已停止")


class InfectionPhaseCard(QFrame):
    """感染阶段卡片"""

    def __init__(self, phase_id: str, phase_name: str, phase_desc: str, parent=None):
        super().__init__(parent)
        self.phase_id = phase_id
        self.init_ui(phase_name, phase_desc)

    def init_ui(self, phase_name: str, phase_desc: str):
        """初始化UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setMinimumWidth(100)

        layout = QVBoxLayout(self)

        self.name_label = QLabel(phase_name)
        self.name_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)

        self.desc_label = QLabel(phase_desc)
        self.desc_label.setStyleSheet("color: #888; font-size: 8px;")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.desc_label)

        self.set_inactive()

    def set_active(self):
        """设置为激活"""
        self.setStyleSheet("""
            QFrame {
                background-color: #ffebee;
                border: 2px solid #f44336;
                border-radius: 8px;
                padding: 8px;
            }
        """)

    def set_inactive(self):
        """设置为非激活"""
        self.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 8px;
            }
        """)


class FractalStorageTab(QWidget):
    """分形存储标签页"""

    TIERS = [
        (1, "💻 本地设备", "本地设备存储"),
        (2, "🌐 局域网P2P", "局域网P2P同步"),
        (3, "☁️ 互联网云", "互联网云存储"),
        (4, "⛓️ 区块链", "区块链永久存储"),
        (5, "📄 物理媒介", "物理媒介备份"),
        (6, "🛰️ 卫星广播", "卫星广播"),
        (7, "👥 社交网络", "社交网络传播"),
        (8, "📧 邮件列表", "邮件列表"),
        (9, "🔢 DHT网络", "分布式哈希表"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 9层存储架构
        storage_group = QGroupBox("💾 9层DNA存储架构")
        storage_layout = QVBoxLayout()

        self.tier_widgets = []
        for tier_num, tier_name, tier_desc in self.TIERS:
            widget = StorageTierCard(tier_num, tier_name, tier_desc, self)
            storage_layout.addWidget(widget)
            self.tier_widgets.append(widget)

        storage_group.setLayout(storage_layout)
        layout.addWidget(storage_group)

        # 存储状态
        status_group = QGroupBox("📊 存储状态")
        status_layout = QGridLayout()

        status_layout.addWidget(QLabel("总存储位置:"), 0, 0)
        self.total_locations_label = QLabel("0")
        status_layout.addWidget(self.total_locations_label, 0, 1)

        status_layout.addWidget(QLabel("已验证:"), 0, 2)
        self.verified_label = QLabel("0")
        status_layout.addWidget(self.verified_label, 0, 3)

        status_layout.addWidget(QLabel("待验证:"), 1, 0)
        self.pending_label = QLabel("0")
        status_layout.addWidget(self.pending_label, 1, 1)

        status_layout.addWidget(QLabel("冗余度:"), 1, 2)
        self.redundancy_label = QLabel("1x")
        status_layout.addWidget(self.redundancy_label, 1, 3)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 操作
        button_layout = QHBoxLayout()

        self.store_all_btn = QPushButton("💾 存储到所有层级")
        self.store_all_btn.clicked.connect(self.store_all_tiers)
        button_layout.addWidget(self.store_all_btn)

        self.verify_all_btn = QPushButton("🔍 验证所有位置")
        self.verify_all_btn.clicked.connect(self.verify_all)
        button_layout.addWidget(self.verify_all_btn)

        self.cleanup_btn = QPushButton("🧹 清理无效位置")
        self.cleanup_btn.clicked.connect(self.cleanup)
        button_layout.addWidget(self.cleanup_btn)

        layout.addLayout(button_layout)

    def store_all_tiers(self):
        """存储到所有层级"""
        if self.parent_panel.phoenix_engine:
            self.parent_panel.status_label.setText("正在存储到所有层级...")

    def verify_all(self):
        """验证所有"""
        self.parent_panel.status_label.setText("正在验证所有存储位置...")

    def cleanup(self):
        """清理"""
        self.parent_panel.status_label.setText("正在清理无效位置...")


class StorageTierCard(QFrame):
    """存储层级卡片"""

    def __init__(self, tier_num: int, tier_name: str, tier_desc: str, parent=None):
        super().__init__(parent)
        self.tier_num = tier_num
        self.init_ui(tier_name, tier_desc)

    def init_ui(self, tier_name: str, tier_desc: str):
        """初始化UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        layout = QHBoxLayout()

        # 层级号
        tier_label = QLabel(f"#{self.tier_num}")
        tier_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        tier_label.setStyleSheet("color: #666; min-width: 40px;")
        layout.addWidget(tier_label)

        # 名称和描述
        info_layout = QVBoxLayout()
        name_label = QLabel(tier_name)
        name_label.setFont(QFont("Microsoft YaHei", 10))
        info_layout.addWidget(name_label)

        desc_label = QLabel(tier_desc)
        desc_label.setStyleSheet("color: #888; font-size: 9px;")
        info_layout.addWidget(desc_label)
        layout.addLayout(info_layout)

        layout.addStretch()

        # 状态
        self.status_label = QLabel("○")
        self.status_label.setFont(QFont("Arial", 16))
        self.status_label.setStyleSheet("color: #9e9e9e;")
        layout.addWidget(self.status_label)

        self.setStyleSheet("""
            QFrame {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 8px;
            }
        """)

    def set_status(self, status: str, count: int = 0):
        """设置状态"""
        if status == "ok":
            self.status_label.setText("✓")
            self.status_label.setStyleSheet("color: #4CAF50;")
        elif status == "pending":
            self.status_label.setText(f"({count})")
            self.status_label.setStyleSheet("color: #FF9800;")
        else:
            self.status_label.setText("○")
            self.status_label.setStyleSheet("color: #9e9e9e;")


class SettingsTab(QWidget):
    """设置标签页"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_panel = parent
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 网络设置
        network_group = QGroupBox("🌐 网络设置")
        network_layout = QGridLayout()

        network_layout.addWidget(QLabel("节点ID:"), 0, 0)
        self.node_id_edit = QLineEdit()
        network_layout.addWidget(self.node_id_edit, 0, 1, 1, 2)

        network_layout.addWidget(QLabel("TTL:"), 1, 0)
        self.ttl_spin = QSpinBox()
        self.ttl_spin.setRange(1, 10)
        self.ttl_spin.setValue(3)
        network_layout.addWidget(self.ttl_spin, 1, 1)

        network_layout.addWidget(QLabel("Fanout:"), 1, 2)
        self.fanout_spin = QSpinBox()
        self.fanout_spin.setRange(1, 10)
        self.fanout_spin.setValue(3)
        network_layout.addWidget(self.fanout_spin, 1, 3)

        network_group.setLayout(network_layout)
        layout.addWidget(network_group)

        # 存储设置
        storage_group = QGroupBox("💾 存储设置")
        storage_layout = QGridLayout()

        storage_layout.addWidget(QLabel("编码格式:"), 0, 0)
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["msgpack+gzip", "json+gzip", "msgpack", "json"])
        storage_layout.addWidget(self.encoding_combo, 0, 1)

        storage_layout.addWidget(QLabel("校验算法:"), 0, 2)
        self.checksum_combo = QComboBox()
        self.checksum_combo.addItems(["blake3", "sha3-256", "sha256"])
        storage_layout.addWidget(self.checksum_combo, 0, 3)

        storage_layout.addWidget(QLabel("碎片大小:"), 1, 0)
        self.shard_size_spin = QSpinBox()
        self.shard_size_spin.setRange(1024, 65536)
        self.shard_size_spin.setSingleStep(1024)
        self.shard_size_spin.setValue(4096)
        storage_layout.addWidget(self.shard_size_spin, 1, 1)

        storage_group.setLayout(storage_layout)
        layout.addWidget(storage_group)

        # 载体配置
        carrier_group = QGroupBox("📡 载体配置")
        carrier_layout = QVBoxLayout()

        self.carrier_checks = {}
        carriers = [
            ("github_gist", "GitHub Gist"),
            ("ipfs", "IPFS"),
            ("nostr", "Nostr"),
            ("bittorrent", "BitTorrent"),
            ("qr_code", "二维码"),
            ("email", "邮件"),
        ]
        for carrier_id, carrier_name in carriers:
            check = QCheckBox(carrier_name)
            check.setChecked(True)
            carrier_layout.addWidget(check)
            self.carrier_checks[carrier_id] = check

        carrier_group.setLayout(carrier_layout)
        layout.addWidget(carrier_group)

        # 按钮
        button_layout = QHBoxLayout()

        self.save_btn = QPushButton("💾 保存设置")
        self.save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_btn)

        self.reset_btn = QPushButton("🔄 重置默认")
        self.reset_btn.clicked.connect(self.reset_settings)
        button_layout.addWidget(self.reset_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

    def save_settings(self):
        """保存设置"""
        self.parent_panel.status_label.setText("设置已保存")

    def reset_settings(self):
        """重置设置"""
        self.ttl_spin.setValue(3)
        self.fanout_spin.setValue(3)
        self.encoding_combo.setCurrentIndex(0)
        self.checksum_combo.setCurrentIndex(0)
        self.shard_size_spin.setValue(4096)
        self.parent_panel.status_label.setText("设置已重置")


# ==================== 导出 ====================

__all__ = ['PhoenixProtocolPanel']
