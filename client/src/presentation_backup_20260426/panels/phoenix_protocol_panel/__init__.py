# -*- coding: utf-8 -*-
"""
🌌 通用数字永生系统 - Phoenix Protocol Panel
=============================================

核心理念: "网络可死，基因永生；载体可灭，灵魂不灭"

Author: Hermes Desktop Team
Version: 1.0.0
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QComboBox, QTabWidget, QGroupBox,
    QFrame, QStatusBar, QCheckBox, QMessageBox,
    QSplitter, QFileDialog, QInputDialog, QSpinBox,
    QDateTimeEdit, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QDateTime
from PyQt6.QtGui import QFont

import hashlib
from datetime import datetime
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class PhoenixProtocolPanel(QWidget):
    """
    通用数字永生系统 - UI面板

    核心理念: "网络可死，基因永生；载体可灭，灵魂不灭"
    """

    dna_created = pyqtSignal(str)
    resurrection_triggered = pyqtSignal(str)
    carrier_updated = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.phoenix_engine = None
        self.dna_records = []
        self.carriers = {}
        self._init_ui()
        self._init_connections()
        self._load_mock_data()

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("🌌 Phoenix Protocol - 数字永生系统")
        self.setMinimumSize(1200, 800)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)

        overview_cards = self._create_overview_cards()
        main_layout.addWidget(overview_cards)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setSizes([400, 800])

        left_panel = self._create_dna_list_panel()
        splitter.addWidget(left_panel)

        right_panel = self._create_detail_panel()
        splitter.addWidget(right_panel)

        main_layout.addWidget(splitter, 1)

        self.status_bar = QStatusBar()
        self.status_bar.showMessage("系统就绪")
        main_layout.addWidget(self.status_bar)

    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QFrame()
        toolbar.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 4, 8, 4)

        title = QLabel("🌌 Phoenix Protocol")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addStretch()

        self.btn_create_dna = QPushButton("🧬 创建DNA")
        self.btn_import_dna = QPushButton("📥 导入DNA")
        self.btn_export_dna = QPushButton("📤 导出DNA")
        self.btn_settings = QPushButton("⚙️ 设置")

        layout.addWidget(self.btn_create_dna)
        layout.addWidget(self.btn_import_dna)
        layout.addWidget(self.btn_export_dna)
        layout.addWidget(self.btn_settings)

        return toolbar

    def _create_overview_cards(self) -> QWidget:
        """创建概览卡片"""
        cards = QFrame()
        cards.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QHBoxLayout(cards)
        layout.setSpacing(16)

        self.dna_count_card = self._make_stat_card("🧬", "DNA记录", "0", "#4CAF50")
        layout.addWidget(self.dna_count_card)

        self.carrier_count_card = self._make_stat_card("📦", "存储载体", "0", "#2196F3")
        layout.addWidget(self.carrier_count_card)

        self.capsule_count_card = self._make_stat_card("⏰", "时间胶囊", "0", "#FF9800")
        layout.addWidget(self.capsule_count_card)

        self.health_card = self._make_stat_card("❤️", "系统健康", "100%", "#E91E63")
        layout.addWidget(self.health_card)

        return cards

    def _make_stat_card(self, icon: str, title: str, value: str, color: str) -> QFrame:
        """创建统计卡片"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {color}22;
                border: 2px solid {color};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(4)

        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Microsoft YaHei", 20))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 9))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        self._stat_values = getattr(self, '_stat_values', {})
        value_label = QLabel(value)
        value_label.setObjectName(f"stat_{title}")
        value_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)

        return card

    def _create_dna_list_panel(self) -> QWidget:
        """创建DNA列表面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QVBoxLayout(panel)

        title = QLabel("🧬 DNA记录")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(title)

        self.dna_search = QLineEdit()
        self.dna_search.setPlaceholderText("搜索DNA...")
        self.dna_search.textChanged.connect(self._on_dna_search)
        layout.addWidget(self.dna_search)

        self.dna_list = QListWidget()
        self.dna_list.itemClicked.connect(self._on_dna_selected)
        layout.addWidget(self.dna_list, 1)

        filter_group = QGroupBox("DNA类型")
        filter_layout = QVBoxLayout(filter_group)

        self.filter_core = QCheckBox("核心DNA (1KB)")
        self.filter_core.setChecked(True)
        self.filter_core.toggled.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_core)

        self.filter_extended = QCheckBox("扩展DNA (10KB)")
        self.filter_extended.setChecked(True)
        self.filter_extended.toggled.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_extended)

        self.filter_full = QCheckBox("完整DNA (100KB)")
        self.filter_full.setChecked(True)
        self.filter_full.toggled.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_full)

        layout.addWidget(filter_group)

        return panel

    def _create_detail_panel(self) -> QWidget:
        """创建详情面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QVBoxLayout(panel)

        title = QLabel("📋 详细信息")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(title)

        self.detail_tabs = QTabWidget()

        overview_tab = self._create_dna_overview_tab()
        self.detail_tabs.addTab(overview_tab, "🧬 DNA概览")

        carrier_tab = self._create_carrier_tab()
        self.detail_tabs.addTab(carrier_tab, "📦 载体管理")

        capsule_tab = self._create_capsule_tab()
        self.detail_tabs.addTab(capsule_tab, "⏰ 时间胶囊")

        resurrection_tab = self._create_resurrection_tab()
        self.detail_tabs.addTab(resurrection_tab, "🔄 复活协议")

        network_tab = self._create_network_tab()
        self.detail_tabs.addTab(network_tab, "🌐 传播网络")

        layout.addWidget(self.detail_tabs, 1)

        return panel

    def _create_dna_overview_tab(self) -> QWidget:
        """创建DNA概览选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info_group = QGroupBox("DNA基本信息")
        info_layout = QGridLayout(info_group)

        info_layout.addWidget(QLabel("DNA ID:"), 0, 0)
        self.dna_id = QLabel("-")
        info_layout.addWidget(self.dna_id, 0, 1)

        info_layout.addWidget(QLabel("DNA类型:"), 0, 2)
        self.dna_type = QLabel("-")
        info_layout.addWidget(self.dna_type, 0, 3)

        info_layout.addWidget(QLabel("编码格式:"), 1, 0)
        self.dna_encoding = QLabel("-")
        info_layout.addWidget(self.dna_encoding, 1, 1)

        info_layout.addWidget(QLabel("大小:"), 1, 2)
        self.dna_size = QLabel("-")
        info_layout.addWidget(self.dna_size, 1, 3)

        info_layout.addWidget(QLabel("创建时间:"), 2, 0)
        self.dna_created_at = QLabel("-")
        info_layout.addWidget(self.dna_created_at, 2, 1, 1, 3)

        info_layout.addWidget(QLabel("校验和:"), 3, 0)
        self.dna_checksum = QLabel("-")
        self.dna_checksum.setFont(QFont("Consolas", 8))
        info_layout.addWidget(self.dna_checksum, 3, 1, 1, 3)

        layout.addWidget(info_group)

        vis_group = QGroupBox("DNA可视化")
        vis_layout = QVBoxLayout(vis_group)
        self.dna_visualization = QTextEdit()
        self.dna_visualization.setReadOnly(True)
        self.dna_visualization.setFont(QFont("Consolas", 8))
        self.dna_visualization.setMaximumHeight(200)
        vis_layout.addWidget(self.dna_visualization)
        layout.addWidget(vis_group)

        action_layout = QHBoxLayout()
        self.btn_copy_dna = QPushButton("📋 复制DNA")
        self.btn_backup_dna = QPushButton("💾 备份DNA")
        self.btn_delete_dna = QPushButton("🗑️ 删除DNA")
        action_layout.addWidget(self.btn_copy_dna)
        action_layout.addWidget(self.btn_backup_dna)
        action_layout.addWidget(self.btn_delete_dna)
        layout.addLayout(action_layout)

        layout.addStretch()
        return tab

    def _create_carrier_tab(self) -> QWidget:
        """创建载体管理选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        carrier_group = QGroupBox("活跃载体")
        carrier_layout = QVBoxLayout(carrier_group)
        self.carrier_list = QListWidget()
        carrier_layout.addWidget(self.carrier_list)
        layout.addWidget(carrier_group, 1)

        detail_group = QGroupBox("载体详情")
        detail_layout = QGridLayout(detail_group)

        detail_layout.addWidget(QLabel("载体类型:"), 0, 0)
        self.carrier_type = QLabel("-")
        detail_layout.addWidget(self.carrier_type, 0, 1)

        detail_layout.addWidget(QLabel("状态:"), 0, 2)
        self.carrier_status = QLabel("-")
        detail_layout.addWidget(self.carrier_status, 0, 3)

        detail_layout.addWidget(QLabel("存储位置:"), 1, 0)
        self.carrier_location = QLabel("-")
        detail_layout.addWidget(self.carrier_location, 1, 1, 1, 3)

        layout.addWidget(detail_group)

        carrier_action = QHBoxLayout()
        self.btn_add_carrier = QPushButton("➕ 添加载体")
        self.btn_verify_carrier = QPushButton("✅ 验证载体")
        self.btn_remove_carrier = QPushButton("➖ 移除载体")
        carrier_action.addWidget(self.btn_add_carrier)
        carrier_action.addWidget(self.btn_verify_carrier)
        carrier_action.addWidget(self.btn_remove_carrier)
        layout.addLayout(carrier_action)

        return tab

    def _create_capsule_tab(self) -> QWidget:
        """创建时间胶囊选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        create_group = QGroupBox("创建时间胶囊")
        create_layout = QGridLayout(create_group)

        create_layout.addWidget(QLabel("解锁时间:"), 0, 0)
        self.capsule_unlock_time = QDateTimeEdit()
        self.capsule_unlock_time.setDateTime(QDateTime.currentDateTime().addDays(30))
        create_layout.addWidget(self.capsule_unlock_time, 0, 1, 1, 2)

        create_layout.addWidget(QLabel("内容描述:"), 1, 0)
        self.capsule_description = QLineEdit()
        self.capsule_description.setPlaceholderText("描述时间胶囊内容...")
        create_layout.addWidget(self.capsule_description, 1, 1, 1, 2)

        self.btn_create_capsule = QPushButton("🕐 创建时间胶囊")
        create_layout.addWidget(self.btn_create_capsule, 2, 0, 1, 3)

        layout.addWidget(create_group)

        capsule_list_group = QGroupBox("时间胶囊列表")
        capsule_list_layout = QVBoxLayout(capsule_list_group)
        self.capsule_list = QListWidget()
        capsule_list_layout.addWidget(self.capsule_list)
        layout.addWidget(capsule_list_group, 1)

        return tab

    def _create_resurrection_tab(self) -> QWidget:
        """创建复活协议选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        condition_group = QGroupBox("复活条件")
        condition_layout = QGridLayout(condition_group)

        condition_layout.addWidget(QLabel("触发条件:"), 0, 0)
        self.resurrection_trigger = QComboBox()
        self.resurrection_trigger.addItems([
            "时间锁定", "多重签名", "法定人数", "继承人密钥", "社区投票"
        ])
        condition_layout.addWidget(self.resurrection_trigger, 0, 1, 1, 2)

        condition_layout.addWidget(QLabel("解锁延迟:"), 1, 0)
        self.resurrection_delay = QSpinBox()
        self.resurrection_delay.setRange(1, 365)
        self.resurrection_delay.setValue(30)
        condition_layout.addWidget(self.resurrection_delay, 1, 1)
        condition_layout.addWidget(QLabel("天"), 1, 2)

        condition_layout.addWidget(QLabel("必要签名者:"), 2, 0)
        self.resurrection_signers = QSpinBox()
        self.resurrection_signers.setRange(1, 10)
        self.resurrection_signers.setValue(3)
        condition_layout.addWidget(self.resurrection_signers, 2, 1)

        layout.addWidget(condition_group)

        history_group = QGroupBox("复活历史")
        history_layout = QVBoxLayout(history_group)
        self.resurrection_history = QListWidget()
        history_layout.addWidget(self.resurrection_history)
        layout.addWidget(history_group, 1)

        res_action = QHBoxLayout()
        self.btn_init_resurrection = QPushButton("🔄 初始化复活")
        self.btn_cancel_resurrection = QPushButton("❌ 取消复活")
        res_action.addWidget(self.btn_init_resurrection)
        res_action.addWidget(self.btn_cancel_resurrection)
        layout.addLayout(res_action)

        return tab

    def _create_network_tab(self) -> QWidget:
        """创建传播网络选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        stats_group = QGroupBox("网络统计")
        stats_layout = QGridLayout(stats_group)

        stats_layout.addWidget(QLabel("活跃节点:"), 0, 0)
        self.network_nodes = QLabel("0")
        stats_layout.addWidget(self.network_nodes, 0, 1)

        stats_layout.addWidget(QLabel("传播深度:"), 0, 2)
        self.network_depth = QLabel("0")
        stats_layout.addWidget(self.network_depth, 0, 3)

        stats_layout.addWidget(QLabel("感染阶段:"), 1, 0)
        self.network_phase = QLabel("-")
        stats_layout.addWidget(self.network_phase, 1, 1, 1, 3)

        layout.addWidget(stats_group)

        node_group = QGroupBox("节点列表")
        node_layout = QVBoxLayout(node_group)
        self.node_list = QListWidget()
        node_layout.addWidget(self.node_list)
        layout.addWidget(node_group, 1)

        node_action = QHBoxLayout()
        self.btn_add_node = QPushButton("➕ 添加节点")
        self.btn_refresh_network = QPushButton("🔄 刷新网络")
        node_action.addWidget(self.btn_add_node)
        node_action.addWidget(self.btn_refresh_network)
        layout.addLayout(node_action)

        return tab

    def _init_connections(self):
        """初始化信号连接"""
        self.btn_create_dna.clicked.connect(self._on_create_dna)
        self.btn_import_dna.clicked.connect(self._on_import_dna)
        self.btn_export_dna.clicked.connect(self._on_export_dna)
        self.btn_copy_dna.clicked.connect(self._on_copy_dna)
        self.btn_delete_dna.clicked.connect(self._on_delete_dna)

    def _load_mock_data(self):
        """加载模拟数据"""
        self.dna_records = [
            {
                'id': 'dna_001',
                'type': 'CORE',
                'encoding': 'msgpack+gzip',
                'size': '1.2 KB',
                'created_at': '2026-04-15 10:30:00',
                'checksum': 'blake3:a1b2c3d4...',
                'data': 'ATGCGATCGATCG...' * 10
            },
            {
                'id': 'dna_002',
                'type': 'EXTENDED',
                'encoding': 'msgpack+gzip',
                'size': '12.5 KB',
                'created_at': '2026-04-18 14:20:00',
                'checksum': 'blake3:e5f6g7h8...',
                'data': 'ATGCGATCGATCG...' * 100
            },
            {
                'id': 'dna_003',
                'type': 'FULL',
                'encoding': 'msgpack+gzip',
                'size': '98.7 KB',
                'created_at': '2026-04-19 08:00:00',
                'checksum': 'blake3:i9j0k1l2...',
                'data': 'ATGCGATCGATCG...' * 800
            }
        ]

        self.carriers = {
            'github_gist': {'status': 'active', 'count': 3},
            'ipfs': {'status': 'active', 'count': 5},
            'arweave': {'status': 'inactive', 'count': 2}
        }

        self._refresh_dna_list()
        self._update_stats()

    def _refresh_dna_list(self):
        """刷新DNA列表"""
        self.dna_list.clear()

        search_text = self.dna_search.text().lower()

        for dna in self.dna_records:
            dna_type = dna.get('type', '').lower()
            if dna_type == 'core' and not self.filter_core.isChecked():
                continue
            if dna_type == 'extended' and not self.filter_extended.isChecked():
                continue
            if dna_type == 'full' and not self.filter_full.isChecked():
                continue

            if search_text and search_text not in dna.get('id', '').lower():
                continue

            icon = '🔹' if dna_type == 'core' else ('🔷' if dna_type == 'extended' else '🟣')
            item = QListWidgetItem(f"{icon} {dna.get('id')} ({dna.get('type')})")
            item.setData(Qt.ItemDataRole.UserRole, dna.get('id'))
            self.dna_list.addItem(item)

    def _update_stats(self):
        """更新统计信息"""
        # 更新DNA数量
        dna_count_label = self.dna_count_card.findChild(QLabel, "stat_DNA记录")
        if dna_count_label:
            dna_count_label.setText(str(len(self.dna_records)))

        # 更新载体数量
        carrier_count_label = self.carrier_count_card.findChild(QLabel, "stat_存储载体")
        if carrier_count_label:
            carrier_count_label.setText(str(len(self.carriers)))

    def _on_dna_search(self, text: str):
        """DNA搜索"""
        self._refresh_dna_list()

    def _on_filter_changed(self):
        """过滤器变化"""
        self._refresh_dna_list()

    def _on_dna_selected(self, item: QListWidgetItem):
        """DNA被选中"""
        dna_id = item.data(Qt.ItemDataRole.UserRole)
        for dna in self.dna_records:
            if dna.get('id') == dna_id:
                self._display_dna_detail(dna)
                break

    def _display_dna_detail(self, dna: dict):
        """显示DNA详情"""
        self.dna_id.setText(dna.get('id', '-'))
        self.dna_type.setText(dna.get('type', '-'))
        self.dna_encoding.setText(dna.get('encoding', '-'))
        self.dna_size.setText(dna.get('size', '-'))
        self.dna_created_at.setText(dna.get('created_at', '-'))
        self.dna_checksum.setText(dna.get('checksum', '-'))

        data = dna.get('data', '')
        vis_lines = []
        for i in range(0, min(len(data), 500), 50):
            chunk = data[i:i+50]
            hex_view = ' '.join(f'{ord(c):02X}' for c in chunk[:25])
            ascii_view = ''.join(c if 32 <= ord(c) < 127 else '.' for c in chunk[:25])
            vis_lines.append(f"{i:08X}  {hex_view:<75}  {ascii_view}")

        self.dna_visualization.setText('\n'.join(vis_lines) if vis_lines else "No data")

    def _on_create_dna(self):
        """创建DNA"""
        dlg = QInputDialog(self)
        dlg.setWindowTitle("创建DNA")
        dlg.setLabelText("输入DNA数据:")
        dlg.setTextValue("")
        dlg.setInputMode(QInputDialog.InputMode.TextInput)

        if dlg.exec():
            data = dlg.textValue()
            if data:
                new_dna = {
                    'id': f"dna_{len(self.dna_records) + 1:03d}",
                    'type': 'CORE',
                    'encoding': 'msgpack+gzip',
                    'size': f'{len(data) / 1024:.1f} KB',
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'checksum': hashlib.blake2b(data.encode()).hexdigest()[:16],
                    'data': data
                }
                self.dna_records.append(new_dna)
                self._refresh_dna_list()
                self._update_stats()
                self.status_bar.showMessage(f"DNA {new_dna['id']} 创建成功")

    def _on_import_dna(self):
        """导入DNA"""
        file_path, _ = QFileDialog.getOpenName(
            self, "导入DNA", "", "DNA Files (*.dna *.json);;All Files (*.*)"
        )
        if file_path:
            self.status_bar.showMessage(f"从 {file_path} 导入DNA...")

    def _on_export_dna(self):
        """导出DNA"""
        current_item = self.dna_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "警告", "请先选择要导出的DNA")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出DNA", "", "DNA Files (*.dna);;JSON Files (*.json)"
        )
        if file_path:
            self.status_bar.showMessage(f"已导出到 {file_path}")

    def _on_copy_dna(self):
        """复制DNA"""
        current_item = self.dna_list.currentItem()
        if current_item:
            dna_id = current_item.data(Qt.ItemDataRole.UserRole)
            for dna in self.dna_records:
                if dna.get('id') == dna_id:
                    QApplication.clipboard().setText(dna.get('data', ''))
                    self.status_bar.showMessage(f"DNA {dna_id} 已复制到剪贴板")
                    break

    def _on_delete_dna(self):
        """删除DNA"""
        current_item = self.dna_list.currentItem()
        if current_item:
            dna_id = current_item.data(Qt.ItemDataRole.UserRole)
            reply = QMessageBox.question(
                self, "确认", f"确定要删除DNA {dna_id} 吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.dna_records = [d for d in self.dna_records if d.get('id') != dna_id]
                self._refresh_dna_list()
                self._update_stats()
                self.status_bar.showMessage(f"DNA {dna_id} 已删除")


def get_panel_info():
    """获取面板信息"""
    return {
        'name': '🌌 数字永生',
        'class': PhoenixProtocolPanel,
        'icon': '🌌',
        'description': '通用数字永生系统 - Phoenix Protocol'
    }
