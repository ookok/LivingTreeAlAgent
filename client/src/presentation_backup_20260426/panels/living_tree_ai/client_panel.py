"""
LivingTreeAI Client Panel - 生命之树客户端控制面板
================================================

功能：
- 节点状态监控
- 任务管理
- 知识库浏览
- 贡献查询
- 网络连接

Author: LivingTreeAI Community
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime


class LivingTreeAIClientPanel:
    """
    生命之树AI客户端面板

    提供PyQt6界面组件
    """

    def __init__(self, node, network, knowledge_share, incentive):
        self.node = node
        self.network = network
        self.knowledge_share = knowledge_share
        self.incentive = incentive

        # UI组件引用
        self.ui_components: Dict = {}

    def setup_ui(self, parent_widget):
        """设置UI组件"""
        from PyQt6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
            QLabel, QPushButton, QTableWidget, QTabWidget,
            QGroupBox, QProgressBar, QTextEdit, QListWidget,
            QComboBox, QSpinBox
        )
        from PyQt6.QtCore import Qt, QTimer

        # 主容器
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # 标签页
        tabs = QTabWidget()

        # 1. 状态页
        tabs.addTab(self._create_status_tab(), "📊 状态")
        # 2. 任务页
        tabs.addTab(self._create_tasks_tab(), "📋 任务")
        # 3. 知识页
        tabs.addTab(self._create_knowledge_tab(), "📚 知识")
        # 4. 贡献页
        tabs.addTab(self._create_contribution_tab(), "🏆 贡献")
        # 5. 网络页
        tabs.addTab(self._create_network_tab(), "🌐 网络")
        # 6. 设置页
        tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        layout.addWidget(tabs)

        return main_widget

    def _create_status_tab(self) -> QWidget:
        """创建状态页面"""
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QGroupBox, QLabel

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 节点信息组
        status_group = QGroupBox("节点信息")
        status_layout = QGridLayout()

        # 获取节点状态
        status = self.node.get_status()

        status_layout.addWidget(QLabel("节点ID:"), 0, 0)
        status_layout.addWidget(QLabel(status.get("node_id", "N/A")), 0, 1)

        status_layout.addWidget(QLabel("状态:"), 1, 0)
        status_layout.addWidget(QLabel(status.get("status", "unknown")), 1, 1)

        status_layout.addWidget(QLabel("类型:"), 2, 0)
        status_layout.addWidget(QLabel(status.get("node_type", "N/A")), 2, 1)

        status_layout.addWidget(QLabel("特化:"), 3, 0)
        status_layout.addWidget(QLabel(status.get("specialization", "N/A")), 3, 1)

        status_layout.addWidget(QLabel("在线时长:"), 4, 0)
        status_layout.addWidget(QLabel(f"{status.get('online_hours', 0):.2f} 小时"), 4, 1)

        status_layout.addWidget(QLabel("已完成任务:"), 5, 0)
        status_layout.addWidget(QLabel(str(status.get("task_completed", 0))), 5, 1)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 硬件信息组
        hw_group = QGroupBox("硬件配置")
        hw_layout = QGridLayout()

        hw = status.get("hardware", {})
        hw_layout.addWidget(QLabel("CPU:"), 0, 0)
        hw_layout.addWidget(QLabel(f"{hw.get('cpu_cores', 0)}核"), 0, 1)

        hw_layout.addWidget(QLabel("频率:"), 1, 0)
        hw_layout.addWidget(QLabel(f"{hw.get('cpu_freq_mhz', 0):.0f} MHz"), 1, 1)

        hw_layout.addWidget(QLabel("内存:"), 2, 0)
        hw_layout.addWidget(QLabel(f"{hw.get('memory_total_gb', 0):.1f} GB"), 2, 1)

        hw_layout.addWidget(QLabel("可用:"), 3, 0)
        hw_layout.addWidget(QLabel(f"{hw.get('memory_available_gb', 0):.1f} GB"), 3, 1)

        hw_group.setLayout(hw_layout)
        layout.addWidget(hw_group)

        # 信誉信息
        rep = self.incentive.get_reputation(self.node.node_id)
        if rep:
            rep_group = QGroupBox("信誉")
            rep_layout = QGridLayout()
            rep_layout.addWidget(QLabel("等级:"), 0, 0)
            rep_layout.addWidget(QLabel(f"Lv.{rep.level} {rep.title}"), 0, 1)
            rep_layout.addWidget(QLabel("积分:"), 1, 0)
            rep_layout.addWidget(QLabel(f"{rep.total_points:.1f}"), 1, 1)
            rep_layout.addWidget(QLabel("评分:"), 2, 0)
            rep_layout.addWidget(QLabel(f"{rep.reputation_score:.1f}/100"), 2, 1)
            rep_group.setLayout(rep_layout)
            layout.addWidget(rep_group)

        layout.addStretch()
        return widget

    def _create_tasks_tab(self) -> QWidget:
        """创建任务页面"""
        from PyQt6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
            QTableWidget, QGroupBox, QComboBox, QLabel
        )

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QHBoxLayout()

        self.refresh_tasks_btn = QPushButton("🔄 刷新")
        self.submit_task_btn = QPushButton("➕ 提交任务")
        self.pause_all_btn = QPushButton("⏸ 暂停全部")
        self.cancel_all_btn = QPushButton("🚫 取消全部")

        toolbar.addWidget(self.refresh_tasks_btn)
        toolbar.addWidget(self.submit_task_btn)
        toolbar.addWidget(self.pause_all_btn)
        toolbar.addWidget(self.cancel_all_btn)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 任务表格
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(5)
        self.task_table.setHorizontalHeaderLabels(["任务ID", "类型", "状态", "进度", "操作"])
        layout.addWidget(self.task_table)

        # 统计
        stats_group = QGroupBox("任务统计")
        stats_layout = QHBoxLayout()

        self.stats_labels = {
            "pending": QLabel("等待: 0"),
            "running": QLabel("进行中: 0"),
            "completed": QLabel("已完成: 0"),
            "failed": QLabel("失败: 0"),
        }

        for lbl in self.stats_labels.values():
            stats_layout.addWidget(lbl)
        stats_layout.addStretch()

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        return widget

    def _create_knowledge_tab(self) -> QWidget:
        """创建知识页面"""
        from PyQt6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
            QTableWidget, QLineEdit, QComboBox, QGroupBox, QLabel
        )

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 搜索栏
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索知识...")
        search_layout.addWidget(self.search_input)

        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems(["全部", "事实", "推理模式", "技能", "元知识"])
        search_layout.addWidget(self.search_type_combo)

        self.search_btn = QPushButton("🔍 搜索")
        self.share_btn = QPushButton("📤 分享知识")
        search_layout.addWidget(self.search_btn)
        search_layout.addWidget(self.share_btn)

        layout.addLayout(search_layout)

        # 知识表格
        self.knowledge_table = QTableWidget()
        self.knowledge_table.setColumnCount(5)
        self.knowledge_table.setHorizontalHeaderLabels(["ID", "标题", "类型", "可信度", "使用次数"])
        layout.addWidget(self.knowledge_table)

        # 统计
        stats_group = QGroupBox("知识库统计")
        stats_layout = QHBoxLayout()

        self.knowledge_stats = QLabel("总计: 0 条知识")
        stats_layout.addWidget(self.knowledge_stats)
        stats_layout.addStretch()

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        return widget

    def _create_contribution_tab(self) -> QWidget:
        """创建贡献页面"""
        from PyQt6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
            QLabel, QProgressBar, QPushButton, QTableWidget
        )

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 我的贡献
        my_group = QGroupBox("我的贡献")
        my_layout = QVBoxLayout()

        # 等级进度
        level_layout = QHBoxLayout()
        level_layout.addWidget(QLabel("等级:"))
        self.level_label = QLabel("Lv.1 新手")
        level_layout.addWidget(self.level_label)
        level_layout.addStretch()

        self.level_progress = QProgressBar()
        self.level_progress.setMaximum(100)
        self.level_progress.setValue(0)
        level_layout.addWidget(self.level_progress)

        my_layout.addLayout(level_layout)

        # 统计
        stats_layout = QGridLayout()
        stats_layout.addWidget(QLabel("总积分:"), 0, 0)
        self.total_points_label = QLabel("0")
        stats_layout.addWidget(self.total_points_label, 0, 1)

        stats_layout.addWidget(QLabel("完成任务:"), 1, 0)
        self.tasks_done_label = QLabel("0")
        stats_layout.addWidget(self.tasks_done_label, 1, 1)

        stats_layout.addWidget(QLabel("分享知识:"), 2, 0)
        self.knowledge_shared_label = QLabel("0")
        stats_layout.addWidget(self.knowledge_shared_label, 2, 1)

        stats_layout.addWidget(QLabel("在线时长:"), 3, 0)
        self.online_hours_label = QLabel("0小时")
        stats_layout.addWidget(self.online_hours_label, 3, 1)

        my_layout.addLayout(stats_layout)

        # 勋章
        self.badges_layout = QHBoxLayout()
        self.badges_label = QLabel("🏅 暂无勋章")
        self.badges_layout.addWidget(self.badges_label)
        self.badges_layout.addStretch()
        my_layout.addLayout(self.badges_layout)

        my_group.setLayout(my_layout)
        layout.addWidget(my_group)

        # 排行榜
        rank_group = QGroupBox("贡献排行榜")
        rank_layout = QVBoxLayout()

        self.rank_table = QTableWidget()
        self.rank_table.setColumnCount(4)
        self.rank_table.setHorizontalHeaderLabels(["排名", "节点", "等级", "积分"])
        rank_layout.addWidget(self.rank_table)

        rank_group.setLayout(rank_layout)
        layout.addWidget(rank_group)

        return widget

    def _create_network_tab(self) -> QWidget:
        """创建网络页面"""
        from PyQt6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
            QTableWidget, QPushButton, QLabel
        )

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 连接统计
        conn_group = QGroupBox("连接统计")
        conn_layout = QHBoxLayout()

        self.peer_count_label = QLabel("连接节点: 0")
        self.network_status_label = QLabel("网络状态: 未连接")

        conn_layout.addWidget(self.peer_count_label)
        conn_layout.addWidget(self.network_status_label)
        conn_layout.addStretch()

        self.refresh_network_btn = QPushButton("🔄 刷新")
        self.discover_btn = QPushButton("🔍 发现节点")
        conn_layout.addWidget(self.refresh_network_btn)
        conn_layout.addWidget(self.discover_btn)

        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # 节点列表
        peers_group = QGroupBox("已连接节点")
        peers_layout = QVBoxLayout()

        self.peers_table = QTableWidget()
        self.peers_table.setColumnCount(5)
        self.peers_table.setHorizontalHeaderLabels(["节点ID", "地址", "延迟", "类型", "状态"])
        peers_layout.addWidget(self.peers_table)

        peers_group.setLayout(peers_layout)
        layout.addWidget(peers_group)

        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建设置页面"""
        from PyQt6.QtWidgets import (
            QWidget, QVBoxLayout, QFormLayout, QGroupBox,
            QLineEdit, QSpinBox, QComboBox, QCheckBox, QPushButton
        )

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 节点设置
        node_group = QGroupBox("节点设置")
        node_layout = QFormLayout()

        self.node_type_combo = QComboBox()
        self.node_type_combo.addItems(["通用节点", "专业节点", "协调节点", "存储节点"])
        node_layout.addRow("节点类型:", self.node_type_combo)

        self.specialization_input = QLineEdit()
        self.specialization_input.setPlaceholderText("如: 编程, 数学, 写作...")
        node_layout.addRow("专业领域:", self.specialization_input)

        self.auto_start_check = QCheckBox()
        self.auto_start_check.setChecked(True)
        node_layout.addRow("开机启动:", self.auto_start_check)

        node_group.setLayout(node_layout)
        layout.addWidget(node_group)

        # 网络设置
        net_group = QGroupBox("网络设置")
        net_layout = QFormLayout()

        self.max_peers_spin = QSpinBox()
        self.max_peers_spin.setRange(1, 100)
        self.max_peers_spin.setValue(20)
        net_layout.addRow("最大连接数:", self.max_peers_spin)

        self.bandwidth_limit_spin = QSpinBox()
        self.bandwidth_limit_spin.setRange(1, 100)
        self.bandwidth_limit_spin.setValue(10)
        net_layout.addRow("带宽限制(Mbps):", self.bandwidth_limit_spin)

        self.relay_enabled_check = QCheckBox()
        self.relay_enabled_check.setChecked(True)
        net_layout.addRow("启用中继:", self.relay_enabled_check)

        net_group.setLayout(net_layout)
        layout.addWidget(net_group)

        # 保存按钮
        self.save_settings_btn = QPushButton("💾 保存设置")
        layout.addWidget(self.save_settings_btn)

        layout.addStretch()
        return widget

    def update_status(self):
        """更新状态显示"""
        status = self.node.get_status()

        # 更新统计数据
        running_tasks = status.get("running_tasks", 0)
        queue_size = status.get("queue_size", 0)
        completed = status.get("task_completed", 0)

        # 更新标签
        self.stats_labels["pending"].setText(f"等待: {queue_size}")
        self.stats_labels["running"].setText(f"进行中: {running_tasks}")
        self.stats_labels["completed"].setText(f"已完成: {completed}")

    def update_reputation(self):
        """更新信誉显示"""
        rep = self.incentive.get_reputation(self.node.node_id)
        if not rep:
            return

        self.level_label.setText(f"Lv.{rep.level} {rep.title}")
        self.total_points_label.setText(f"{rep.total_points:.1f}")
        self.tasks_done_label.setText(str(rep.tasks_completed))
        self.knowledge_shared_label.setText(str(rep.knowledge_shared))
        self.online_hours_label.setText(f"{rep.online_hours:.1f}小时")

        badges_text = "🏅 " + ", ".join(rep.badges) if rep.badges else "🏅 暂无勋章"
        self.badges_label.setText(badges_text)

    def update_network(self):
        """更新网络状态"""
        peers = self.network.get_peers()
        self.peer_count_label.setText(f"连接节点: {len(peers)}")

        # 更新节点表格
        self.peers_table.setRowCount(len(peers))
        for i, peer in enumerate(peers):
            self.peers_table.setItem(i, 0, QTableWidgetItem(peer["node_id"]))
            self.peers_table.setItem(i, 1, QTableWidgetItem(peer["address"]))
            self.peers_table.setItem(i, 2, QTableWidgetItem(f"{peer.get('latency_ms', 0):.0f}ms"))
            self.peers_table.setItem(i, 3, QTableWidgetItem("通用"))
            self.peers_table.setItem(i, 4, QTableWidgetItem("在线"))


# PyQt6导入（仅类型标注）
from PyQt6.QtWidgets import QTableWidgetItem
