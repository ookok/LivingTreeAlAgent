"""
LivingTreeAI Server Panel - 生命之树服务器管理面板
================================================

功能：
- 网络全局视图
- 节点管理
- 任务调度
- 联邦学习控制
- 系统监控

Author: LivingTreeAI Community
"""

from typing import Dict, List, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QGroupBox,
    QLabel, QPushButton, QProgressBar, QTextEdit,
    QComboBox, QSpinBox, QLineEdit, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer


class LivingTreeAIServerPanel:
    """
    生命之树AI服务器管理面板

    提供PyQt6界面组件
    """

    def __init__(self, coordinator_node, network, fl_system, incentive_system):
        self.coordinator = coordinator_node
        self.network = network
        self.fl_system = fl_system
        self.incentive = incentive_system

        # 自动刷新定时器
        self.refresh_timer: Optional[QTimer] = None

    def setup_ui(self) -> QWidget:
        """设置UI组件"""
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # 标签页
        tabs = QTabWidget()

        tabs.addTab(self._create_overview_tab(), "📊 总览")
        tabs.addTab(self._create_nodes_tab(), "🖥️ 节点管理")
        tabs.addTab(self._create_tasks_tab(), "📋 任务调度")
        tabs.addTab(self._create_federated_tab(), "🤖 联邦学习")
        tabs.addTab(self._create_knowledge_tab(), "📚 知识管理")
        tabs.addTab(self._create_reputation_tab(), "🏆 信誉系统")
        tabs.addTab(self._create_network_tab(), "🌐 网络拓扑")

        layout.addWidget(tabs)

        return main_widget

    def start_auto_refresh(self, interval_ms: int = 5000):
        """启动自动刷新"""
        if self.refresh_timer is None:
            self.refresh_timer = QTimer()
            self.refresh_timer.timeout.connect(self.refresh_all)
            self.refresh_timer.start(interval_ms)

    def stop_auto_refresh(self):
        """停止自动刷新"""
        if self.refresh_timer:
            self.refresh_timer.stop()
            self.refresh_timer = None

    def refresh_all(self):
        """刷新所有数据"""
        self.update_overview()
        self.update_nodes_table()
        self.update_tasks_table()
        self.update_fl_status()
        self.update_reputation_leaderboard()

    def _create_overview_tab(self) -> QWidget:
        """创建总览页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 标题
        title = QLabel("🌾 平民AI集群 - 管理中心")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # 统计卡片
        cards_layout = QGridLayout()

        # 网络规模
        net_group = QGroupBox("网络规模")
        net_layout = QVBoxLayout()
        self.total_nodes_label = QLabel("0")
        self.total_nodes_label.setStyleSheet("font-size: 32px; font-weight: bold;")
        net_layout.addWidget(self.total_nodes_label)
        net_layout.addWidget(QLabel("在线节点"))
        net_group.setLayout(net_layout)
        cards_layout.addWidget(net_group, 0, 0)

        # 任务统计
        task_group = QGroupBox("任务状态")
        task_layout = QVBoxLayout()
        self.active_tasks_label = QLabel("0")
        self.active_tasks_label.setStyleSheet("font-size: 32px; font-weight: bold; color: blue;")
        task_layout.addWidget(self.active_tasks_label)
        task_layout.addWidget(QLabel("活跃任务"))
        task_group.setLayout(task_layout)
        cards_layout.addWidget(task_group, 0, 1)

        # 知识库
        know_group = QGroupBox("知识库")
        know_layout = QVBoxLayout()
        self.total_knowledge_label = QLabel("0")
        self.total_knowledge_label.setStyleSheet("font-size: 32px; font-weight: bold; color: green;")
        know_layout.addWidget(self.total_knowledge_label)
        know_layout.addWidget(QLabel("知识条目"))
        know_group.setLayout(know_layout)
        cards_layout.addWidget(know_group, 0, 2)

        # 联邦学习轮次
        fl_group = QGroupBox("联邦学习")
        fl_layout = QVBoxLayout()
        self.fl_rounds_label = QLabel("0")
        self.fl_rounds_label.setStyleSheet("font-size: 32px; font-weight: bold; color: purple;")
        fl_layout.addWidget(self.fl_rounds_label)
        fl_layout.addWidget(QLabel("完成轮次"))
        fl_group.setLayout(fl_layout)
        cards_layout.addWidget(fl_group, 0, 3)

        layout.addLayout(cards_layout)

        # 实时活动日志
        log_group = QGroupBox("实时活动")
        log_layout = QVBoxLayout()
        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setMaximumHeight(200)
        log_layout.addWidget(self.activity_log)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # 性能指标
        perf_group = QGroupBox("系统性能")
        perf_layout = QGridLayout()

        perf_layout.addWidget(QLabel("CPU使用率:"), 0, 0)
        self.cpu_usage_bar = QProgressBar()
        perf_layout.addWidget(self.cpu_usage_bar, 0, 1)

        perf_layout.addWidget(QLabel("内存使用率:"), 1, 0)
        self.memory_usage_bar = QProgressBar()
        perf_layout.addWidget(self.memory_usage_bar, 1, 1)

        perf_layout.addWidget(QLabel("网络带宽:"), 2, 0)
        self.bandwidth_bar = QProgressBar()
        perf_layout.addWidget(self.bandwidth_bar, 2, 1)

        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)

        layout.addStretch()
        return widget

    def _create_nodes_tab(self) -> QWidget:
        """创建节点管理页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QHBoxLayout()

        self.refresh_nodes_btn = QPushButton("🔄 刷新")
        self.view_node_btn = QPushButton("👁️ 查看详情")
        self.kick_node_btn = QPushButton("🚫 踢出节点")
        self.ban_node_btn = QPushButton("⛔ 封禁节点")
        self.send_msg_btn = QPushButton("📤 发送消息")

        toolbar.addWidget(self.refresh_nodes_btn)
        toolbar.addWidget(self.view_node_btn)
        toolbar.addWidget(self.kick_node_btn)
        toolbar.addWidget(self.ban_node_btn)
        toolbar.addWidget(self.send_msg_btn)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 筛选
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选:"))
        self.node_filter_combo = QComboBox()
        self.node_filter_combo.addItems(["全部", "通用节点", "专业节点", "协调节点", "存储节点"])
        filter_layout.addWidget(self.node_filter_combo)

        filter_layout.addWidget(QLabel("状态:"))
        self.node_status_filter = QComboBox()
        self.node_status_filter.addItems(["全部", "在线", "离线", "忙碌", "暂停"])
        filter_layout.addWidget(self.node_status_filter)

        filter_layout.addWidget(QLabel("搜索:"))
        self.node_search_input = QLineEdit()
        self.node_search_input.setPlaceholderText("节点ID...")
        filter_layout.addWidget(self.node_search_input)

        layout.addLayout(filter_layout)

        # 节点表格
        self.nodes_table = QTableWidget()
        self.nodes_table.setColumnCount(9)
        self.nodes_table.setHorizontalHeaderLabels([
            "节点ID", "类型", "状态", "信誉", "在线时长", "完成任务", "知识分享", "延迟", "操作"
        ])
        self.nodes_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.nodes_table)

        # 分页
        page_layout = QHBoxLayout()
        page_layout.addWidget(QLabel("每页:"))
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setRange(10, 100)
        self.page_size_spin.setValue(20)
        page_layout.addWidget(self.page_size_spin)
        page_layout.addStretch()
        self.page_label = QLabel("第 1/1 页")
        page_layout.addWidget(self.page_label)

        prev_btn = QPushButton("◀ 上一页")
        next_btn = QPushButton("下一页 ▶")
        page_layout.addWidget(prev_btn)
        page_layout.addWidget(next_btn)

        layout.addLayout(page_layout)

        return widget

    def _create_tasks_tab(self) -> QWidget:
        """创建任务调度页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QHBoxLayout()

        self.create_task_btn = QPushButton("➕ 创建任务")
        self.distribute_task_btn = QPushButton("📢 分发任务")
        self.cancel_task_btn = QPushButton("🚫 取消任务")
        self.retry_task_btn = QPushButton("↻ 重试")

        toolbar.addWidget(self.create_task_btn)
        toolbar.addWidget(self.distribute_task_btn)
        toolbar.addWidget(self.cancel_task_btn)
        toolbar.addWidget(self.retry_task_btn)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 任务类型选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("任务类型:"))
        self.task_type_combo = QComboBox()
        self.task_type_combo.addItems([
            "推理任务", "训练任务", "存储任务", "协调任务", "混合任务"
        ])
        type_layout.addWidget(self.task_type_combo)

        type_layout.addWidget(QLabel("优先级:"))
        self.task_priority_combo = QComboBox()
        self.task_priority_combo.addItems(["低", "普通", "高", "紧急"])
        type_layout.addWidget(self.task_priority_combo)

        type_layout.addStretch()

        layout.addLayout(type_layout)

        # 任务表格
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(8)
        self.tasks_table.setHorizontalHeaderLabels([
            "任务ID", "类型", "状态", "进度", "创建时间", "执行节点", "剩余时间", "操作"
        ])
        layout.addWidget(self.tasks_table)

        # 任务统计
        stats_group = QGroupBox("任务统计")
        stats_layout = QGridLayout()

        self.task_stats_labels = {
            "pending": QLabel("等待: 0"),
            "running": QLabel("进行中: 0"),
            "completed": QLabel("已完成: 0"),
            "failed": QLabel("失败: 0"),
        }

        row = 0
        for i, (key, lbl) in enumerate(self.task_stats_labels.items()):
            col = i % 4
            if i > 0 and col == 0:
                row += 1
            stats_layout.addWidget(lbl, row, col)

        stats_layout.addWidget(QLabel("成功率:"), row + 1, 0)
        self.success_rate_label = QLabel("0%")
        stats_layout.addWidget(self.success_rate_label, row + 1, 1)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        return widget

    def _create_federated_tab(self) -> QWidget:
        """创建联邦学习页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 控制面板
        control_group = QGroupBox("联邦学习控制")
        control_layout = QGridLayout()

        # 轮次设置
        control_layout.addWidget(QLabel("总轮次:"), 0, 0)
        self.fl_total_rounds_spin = QSpinBox()
        self.fl_total_rounds_spin.setRange(1, 1000)
        self.fl_total_rounds_spin.setValue(10)
        control_layout.addWidget(self.fl_total_rounds_spin, 0, 1)

        # 参与节点数
        control_layout.addWidget(QLabel("每轮参与节点:"), 0, 2)
        self.fl_nodes_per_round_spin = QSpinBox()
        self.fl_nodes_per_round_spin.setRange(2, 100)
        self.fl_nodes_per_round_spin.setValue(5)
        control_layout.addWidget(self.fl_nodes_per_round_spin, 0, 3)

        # 本地轮次
        control_layout.addWidget(QLabel("本地训练轮次:"), 1, 0)
        self.fl_local_epochs_spin = QSpinBox()
        self.fl_local_epochs_spin.setRange(1, 100)
        self.fl_local_epochs_spin.setValue(5)
        control_layout.addWidget(self.fl_local_epochs_spin, 1, 1)

        # 聚合策略
        control_layout.addWidget(QLabel("聚合策略:"), 1, 2)
        self.fl_strategy_combo = QComboBox()
        self.fl_strategy_combo.addItems(["FedAvg", "FedProx", "SCAFFOLD"])
        control_layout.addWidget(self.fl_strategy_combo, 1, 3)

        # 按钮
        self.fl_start_btn = QPushButton("▶ 开始训练")
        self.fl_pause_btn = QPushButton("⏸ 暂停")
        self.fl_stop_btn = QPushButton("⏹ 停止")
        self.fl_export_btn = QPushButton("📤 导出模型")

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.fl_start_btn)
        btn_layout.addWidget(self.fl_pause_btn)
        btn_layout.addWidget(self.fl_stop_btn)
        btn_layout.addWidget(self.fl_export_btn)
        btn_layout.addStretch()

        control_layout.addLayout(btn_layout, 2, 0, 1, 4)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # 当前状态
        status_group = QGroupBox("训练状态")
        status_layout = QGridLayout()

        status_layout.addWidget(QLabel("当前轮次:"), 0, 0)
        self.fl_current_round_label = QLabel("0 / 0")
        status_layout.addWidget(self.fl_current_round_label, 0, 1)

        status_layout.addWidget(QLabel("阶段:"), 0, 2)
        self.fl_phase_label = QLabel("空闲")
        status_layout.addWidget(self.fl_phase_label, 0, 3)

        status_layout.addWidget(QLabel("参与节点:"), 1, 0)
        self.fl_participants_label = QLabel("0")
        status_layout.addWidget(self.fl_participants_label, 1, 1)

        status_layout.addWidget(QLabel("平均损失:"), 1, 2)
        self.fl_loss_label = QLabel("0.0000")
        status_layout.addWidget(self.fl_loss_label, 1, 3)

        status_layout.addWidget(QLabel("平均准确率:"), 2, 0)
        self.fl_accuracy_label = QLabel("0.00%")
        status_layout.addWidget(self.fl_accuracy_label, 2, 1)

        status_layout.addWidget(QLabel("耗时:"), 2, 2)
        self.fl_duration_label = QLabel("0s")
        status_layout.addWidget(self.fl_duration_label, 2, 3)

        # 进度条
        status_layout.addWidget(QLabel("整体进度:"), 3, 0)
        self.fl_progress_bar = QProgressBar()
        status_layout.addWidget(self.fl_progress_bar, 3, 1, 1, 3)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 历史记录
        history_group = QGroupBox("训练历史")
        history_layout = QVBoxLayout()

        self.fl_history_table = QTableWidget()
        self.fl_history_table.setColumnCount(6)
        self.fl_history_table.setHorizontalHeaderLabels([
            "轮次", "参与节点", "平均损失", "平均准确率", "耗时", "状态"
        ])
        history_layout.addWidget(self.fl_history_table)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        return widget

    def _create_knowledge_tab(self) -> QWidget:
        """创建知识管理页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QHBoxLayout()

        self.knowledge_refresh_btn = QPushButton("🔄 刷新")
        self.knowledge_share_btn = QPushButton("📤 分享知识")
        self.knowledge_sync_btn = QPushButton("🔄 同步")
        self.knowledge_export_btn = QPushButton("📥 导出")
        self.knowledge_import_btn = QPushButton("📤 导入")

        toolbar.addWidget(self.knowledge_refresh_btn)
        toolbar.addWidget(self.knowledge_share_btn)
        toolbar.addWidget(self.knowledge_sync_btn)
        toolbar.addWidget(self.knowledge_export_btn)
        toolbar.addWidget(self.knowledge_import_btn)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 筛选
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("类型:"))
        self.knowledge_type_filter = QComboBox()
        self.knowledge_type_filter.addItems(["全部", "事实", "推理模式", "技能", "元知识"])
        filter_layout.addWidget(self.knowledge_type_filter)

        filter_layout.addWidget(QLabel("领域:"))
        self.knowledge_domain_input = QLineEdit()
        self.knowledge_domain_input.setPlaceholderText("搜索领域...")
        filter_layout.addWidget(self.knowledge_domain_input)

        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        # 知识表格
        self.knowledge_table = QTableWidget()
        self.knowledge_table.setColumnCount(8)
        self.knowledge_table.setHorizontalHeaderLabels([
            "ID", "标题", "类型", "领域", "来源节点", "可信度", "使用次数", "更新时间"
        ])
        layout.addWidget(self.knowledge_table)

        # 统计
        stats_group = QGroupBox("知识库统计")
        stats_layout = QGridLayout()

        stats_layout.addWidget(QLabel("总条目:"), 0, 0)
        self.knowledge_total_label = QLabel("0")
        stats_layout.addWidget(self.knowledge_total_label, 0, 1)

        stats_layout.addWidget(QLabel("今日新增:"), 0, 2)
        self.knowledge_today_label = QLabel("0")
        stats_layout.addWidget(self.knowledge_today_label, 0, 3)

        stats_layout.addWidget(QLabel("知识类型分布:"), 1, 0)
        self.knowledge_dist_label = QLabel("N/A")
        stats_layout.addWidget(self.knowledge_dist_label, 1, 1, 1, 3)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        return widget

    def _create_reputation_tab(self) -> QWidget:
        """创建信誉系统页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 排行榜
        rank_group = QGroupBox("贡献排行榜 TOP 100")
        rank_layout = QVBoxLayout()

        self.reputation_table = QTableWidget()
        self.reputation_table.setColumnCount(8)
        self.reputation_table.setHorizontalHeaderLabels([
            "排名", "节点ID", "等级", "称号", "总积分", "信誉评分", "完成任务", "勋章"
        ])
        rank_layout.addWidget(self.reputation_table)

        rank_group.setLayout(rank_layout)
        layout.addWidget(rank_group)

        # 勋章管理
        badge_group = QGroupBox("勋章管理")
        badge_layout = QGridLayout()

        badge_layout.addWidget(QLabel("已颁发勋章:"), 0, 0)
        self.total_badges_label = QLabel("0")
        badge_layout.addWidget(self.total_badges_label, 0, 1)

        badge_layout.addWidget(QLabel("本周新增:"), 0, 2)
        self.new_badges_week_label = QLabel("0")
        badge_layout.addWidget(self.new_badges_week_label, 0, 3)

        badge_layout.addWidget(QLabel("最常见勋章:"), 1, 0)
        self.common_badge_label = QLabel("N/A")
        badge_layout.addWidget(self.common_badge_label, 1, 1, 1, 3)

        badge_group.setLayout(badge_layout)
        layout.addWidget(badge_group)

        return widget

    def _create_network_tab(self) -> QWidget:
        """创建网络拓扑页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 控制
        control_layout = QHBoxLayout()

        self.network_refresh_btn = QPushButton("🔄 刷新拓扑")
        self.network_stats_btn = QPushButton("📊 网络统计")
        self.network_optimize_btn = QPushButton("⚡ 优化路由")

        control_layout.addWidget(self.network_refresh_btn)
        control_layout.addWidget(self.network_stats_btn)
        control_layout.addWidget(self.network_optimize_btn)
        control_layout.addStretch()

        layout.addLayout(control_layout)

        # 拓扑可视化区域（占位）
        topo_group = QGroupBox("网络拓扑")
        topo_layout = QVBoxLayout()

        self.topo_canvas = QLabel("网络拓扑可视化区域")
        self.topo_canvas.setMinimumHeight(300)
        self.topo_canvas.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        self.topo_canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        topo_layout.addWidget(self.topo_canvas)

        topo_group.setLayout(topo_layout)
        layout.addWidget(topo_group)

        # 连接详情
        details_group = QGroupBox("连接详情")
        details_layout = QGridLayout()

        details_layout.addWidget(QLabel("总连接数:"), 0, 0)
        self.total_connections_label = QLabel("0")
        details_layout.addWidget(self.total_connections_label, 0, 1)

        details_layout.addWidget(QLabel("平均延迟:"), 0, 2)
        self.avg_latency_label = QLabel("0ms")
        details_layout.addWidget(self.avg_latency_label, 0, 3)

        details_layout.addWidget(QLabel("带宽利用率:"), 1, 0)
        self.bandwidth_usage_label = QLabel("0%")
        details_layout.addWidget(self.bandwidth_usage_label, 1, 1)

        details_layout.addWidget(QLabel("丢包率:"), 1, 2)
        self.packet_loss_label = QLabel("0%")
        details_layout.addWidget(self.packet_loss_label, 1, 3)

        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

        return widget

    # ==================== 更新方法 ====================

    def update_overview(self):
        """更新总览数据"""
        # 获取网络统计
        network_stats = self.network.get_network_stats()

        self.total_nodes_label.setText(str(network_stats.get("peer_count", 0)))

        # 更新活动日志
        self.activity_log.append(f"[{self._current_time()}] 系统正常")

    def update_nodes_table(self):
        """更新节点表格"""
        peers = self.network.get_peers()

        self.nodes_table.setRowCount(len(peers))
        for i, peer in enumerate(peers):
            self.nodes_table.setItem(i, 0, QTableWidgetItem(peer["node_id"]))
            self.nodes_table.setItem(i, 1, QTableWidgetItem("通用"))
            self.nodes_table.setItem(i, 2, QTableWidgetItem("在线"))
            self.nodes_table.setItem(i, 3, QTableWidgetItem("50.0"))
            self.nodes_table.setItem(i, 4, QTableWidgetItem("0h"))
            self.nodes_table.setItem(i, 5, QTableWidgetItem("0"))
            self.nodes_table.setItem(i, 6, QTableWidgetItem("0"))
            self.nodes_table.setItem(i, 7, QTableWidgetItem(f"{peer.get('latency_ms', 0):.0f}ms"))
            self.nodes_table.setItem(i, 8, QTableWidgetItem("[操作]"))

    def update_tasks_table(self):
        """更新任务表格"""
        # 占位实现
        pass

    def update_fl_status(self):
        """更新联邦学习状态"""
        stats = self.fl_system.get_stats()

        self.fl_rounds_label.setText(str(stats["total_rounds"]))

        if stats.get("round_history"):
            last = stats["round_history"][-1]
            self.fl_current_round_label.setText(f"{last['round']} / {stats['total_rounds']}")
            self.fl_loss_label.setText(f"{last['avg_loss']:.4f}")
            self.fl_accuracy_label.setText(f"{last['avg_accuracy']:.2f}%")

    def update_reputation_leaderboard(self):
        """更新信誉排行榜"""
        leaderboard = self.incentive.get_leaderboard(100)

        self.reputation_table.setRowCount(len(leaderboard))
        for i, entry in enumerate(leaderboard):
            self.reputation_table.setItem(i, 0, QTableWidgetItem(f"#{entry['rank']}"))
            self.reputation_table.setItem(i, 1, QTableWidgetItem(entry["node_id"]))
            self.reputation_table.setItem(i, 2, QTableWidgetItem(f"Lv.{entry['level']}"))
            self.reputation_table.setItem(i, 3, QTableWidgetItem(entry["title"]))
            self.reputation_table.setItem(i, 4, QTableWidgetItem(f"{entry['total_points']:.0f}"))
            self.reputation_table.setItem(i, 5, QTableWidgetItem(f"{entry['reputation_score']:.1f}"))
            self.reputation_table.setItem(i, 6, QTableWidgetItem(str(entry["tasks_completed"])))
            self.reputation_table.setItem(i, 7, QTableWidgetItem(", ".join(entry.get("badges", []))))

    def _current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
