"""
P2P 搜索代理管理面板

PyQt6 实现，提供 P2P 搜索代理网络的图形化管理界面
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTableWidget,
    QTableWidgetItem, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QTabWidget, QProgressBar, QCheckBox,
    QListWidget, QListWidgetItem, QMessageBox
)
from PyQt6.QtGui import QColor, QFont

logger = logging.getLogger(__name__)


class P2PSearchProxyPanel(QWidget):
    """
    P2P 搜索代理管理面板

    功能：
    - 搜索请求测试
    - 节点能力监控
    - 路由策略配置
    - 统计信息展示
    """

    # 信号定义
    search_completed = pyqtSignal(dict)
    peer_updated = pyqtSignal(dict)
    stats_updated = pyqtSignal(dict)

    def __init__(self, proxy=None, parent=None):
        super().__init__(parent)
        self.proxy = proxy
        self._setup_ui()
        self._setup_timers()

    def set_proxy(self, proxy):
        """设置代理实例"""
        self.proxy = proxy
        if proxy:
            self._update_peers()
            self._update_stats()

    def _setup_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🌐 P2P 搜索代理网络")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Tab 页面
        tabs = QTabWidget()

        # Tab 1: 搜索测试
        tabs.addTab(self._create_search_tab(), "🔍 搜索测试")

        # Tab 2: 节点监控
        tabs.addTab(self._create_peers_tab(), "🖥️ 节点监控")

        # Tab 3: 路由策略
        tabs.addTab(self._create_routing_tab(), "🧭 路由策略")

        # Tab 4: 统计信息
        tabs.addTab(self._create_stats_tab(), "📊 统计信息")

        layout.addWidget(tabs)

    def _create_search_tab(self) -> QWidget:
        """创建搜索测试页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 搜索输入区
        input_group = QGroupBox("搜索请求")
        input_layout = QGridLayout()

        # 搜索引擎选择
        input_layout.addWidget(QLabel("搜索引擎:"), 0, 0)
        self.engine_combo = QComboBox()
        self.engine_combo.addItems([
            "duckduckgo", "google", "bing", "exa", "searxng"
        ])
        input_layout.addWidget(self.engine_combo, 0, 1)

        # 最大结果数
        input_layout.addWidget(QLabel("最大结果数:"), 0, 2)
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(1, 20)
        self.max_results_spin.setValue(5)
        input_layout.addWidget(self.max_results_spin, 0, 3)

        # P2P 强制模式
        self.force_p2p_check = QCheckBox("强制 P2P")
        input_layout.addWidget(self.force_p2p_check, 0, 4)

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索关键词...")
        self.search_input.returnPressed.connect(self._do_search)
        input_layout.addWidget(self.search_input, 1, 0, 1, 5)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 搜索按钮
        btn_layout = QHBoxLayout()
        self.search_btn = QPushButton("🔍 开始搜索")
        self.search_btn.clicked.connect(self._do_search)
        btn_layout.addWidget(self.search_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 搜索进度
        self.search_progress = QProgressBar()
        self.search_progress.setVisible(False)
        layout.addWidget(self.search_progress)

        # 结果显示
        result_group = QGroupBox("搜索结果")
        result_layout = QVBoxLayout()

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(300)
        result_layout.addWidget(self.result_text)

        result_group.setLayout(result_layout)
        layout.addWidget(result_group)

        # 路由信息
        self.route_info = QLabel("路由信息: 等待搜索...")
        layout.addWidget(self.route_info)

        layout.addStretch()
        return widget

    def _create_peers_tab(self) -> QWidget:
        """创建节点监控页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 节点列表
        self.peer_table = QTableWidget()
        self.peer_table.setColumnCount(6)
        self.peer_table.setHorizontalHeaderLabels([
            "节点ID", "外网", "搜索工具", "延迟(ms)", "成功率", "优先级"
        ])
        layout.addWidget(self.peer_table)

        # 刷新按钮
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 刷新节点")
        refresh_btn.clicked.connect(self._update_peers)
        btn_layout.addWidget(refresh_btn)

        # 注册节点
        register_btn = QPushButton("➕ 注册节点")
        register_btn.clicked.connect(self._register_peer_dialog)
        btn_layout.addWidget(register_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def _create_routing_tab(self) -> QWidget:
        """创建路由策略页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 能力广告配置
        capability_group = QGroupBox("节点能力广播")
        capability_layout = QGridLayout()

        self.advertise_external_check = QCheckBox("广告外网访问能力")
        capability_layout.addWidget(self.advertise_external_check, 0, 0)

        self.advertise_tools_check = QCheckBox("广告搜索工具能力")
        capability_layout.addWidget(self.advertise_tools_check, 0, 1)

        capability_group.setLayout(capability_layout)
        layout.addWidget(capability_group)

        # 路由策略配置
        routing_group = QGroupBox("路由策略")
        routing_layout = QGridLayout()

        routing_layout.addWidget(QLabel("优先模式:"), 0, 0)
        self.prefer_direct_combo = QComboBox()
        self.prefer_direct_combo.addItems(["直连优先", "P2P优先", "均衡模式"])
        routing_layout.addWidget(self.prefer_direct_combo, 0, 1)

        routing_layout.addWidget(QLabel("P2P超时(秒):"), 1, 0)
        self.p2p_timeout_spin = QSpinBox()
        self.p2p_timeout_spin.setRange(5, 60)
        self.p2p_timeout_spin.setValue(15)
        routing_layout.addWidget(self.p2p_timeout_spin, 1, 1)

        routing_layout.addWidget(QLabel("直连超时(秒):"), 1, 2)
        self.direct_timeout_spin = QSpinBox()
        self.direct_timeout_spin.setRange(3, 30)
        self.direct_timeout_spin.setValue(10)
        routing_layout.addWidget(self.direct_timeout_spin, 1, 3)

        routing_layout.addWidget(QLabel("最低节点优先级:"), 2, 0)
        self.min_priority_spin = QDoubleSpinBox()
        self.min_priority_spin.setRange(0, 20)
        self.min_priority_spin.setSingleStep(0.5)
        self.min_priority_spin.setValue(3.0)
        routing_layout.addWidget(self.min_priority_spin, 2, 1)

        routing_group.setLayout(routing_layout)
        layout.addWidget(routing_group)

        # 中继服务器配置
        relay_group = QGroupBox("中继服务器")
        relay_layout = QVBoxLayout()

        self.relay_list = QListWidget()
        self.relay_list.setMaximumHeight(100)
        relay_layout.addWidget(self.relay_list)

        relay_btn_layout = QHBoxLayout()
        add_relay_btn = QPushButton("➕ 添加服务器")
        add_relay_btn.clicked.connect(self._add_relay_server)
        relay_btn_layout.addWidget(add_relay_btn)

        remove_relay_btn = QPushButton("➖ 移除服务器")
        remove_relay_btn.clicked.connect(self._remove_relay_server)
        relay_btn_layout.addWidget(remove_relay_btn)

        relay_btn_layout.addStretch()
        relay_layout.addLayout(relay_btn_layout)

        relay_group.setLayout(relay_layout)
        layout.addWidget(relay_group)

        layout.addStretch()
        return widget

    def _create_stats_tab(self) -> QWidget:
        """创建统计信息页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 总体统计
        stats_group = QGroupBox("总体统计")
        stats_layout = QGridLayout()

        stats_layout.addWidget(QLabel("总请求数:"), 0, 0)
        self.total_requests_label = QLabel("0")
        stats_layout.addWidget(self.total_requests_label, 0, 1)

        stats_layout.addWidget(QLabel("直连成功:"), 0, 2)
        self.direct_success_label = QLabel("0")
        stats_layout.addWidget(self.direct_success_label, 0, 3)

        stats_layout.addWidget(QLabel("P2P成功:"), 1, 0)
        self.p2p_success_label = QLabel("0")
        stats_layout.addWidget(self.p2p_success_label, 1, 1)

        stats_layout.addWidget(QLabel("回退次数:"), 1, 2)
        self.fallback_label = QLabel("0")
        stats_layout.addWidget(self.fallback_label, 1, 3)

        stats_layout.addWidget(QLabel("错误次数:"), 2, 0)
        self.error_label = QLabel("0")
        stats_layout.addWidget(self.error_label, 2, 1)

        stats_layout.addWidget(QLabel("成功率:"), 2, 2)
        self.success_rate_label = QLabel("0%")
        stats_layout.addWidget(self.success_rate_label, 2, 3)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # 节点统计
        peer_stats_group = QGroupBox("节点统计")
        peer_stats_layout = QGridLayout()

        peer_stats_layout.addWidget(QLabel("在线节点数:"), 0, 0)
        self.online_peers_label = QLabel("0")
        peer_stats_layout.addWidget(self.online_peers_label, 0, 1)

        peer_stats_layout.addWidget(QLabel("缓存任务数:"), 0, 2)
        self.cache_size_label = QLabel("0")
        peer_stats_layout.addWidget(self.cache_size_label, 0, 3)

        peer_stats_group.setLayout(peer_stats_layout)
        layout.addWidget(peer_stats_group)

        # 日志
        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)

        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_layout.addWidget(clear_log_btn)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        layout.addStretch()
        return widget

    def _setup_timers(self):
        """设置定时器"""
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._update_peers)
        self._refresh_timer.timeout.connect(self._update_stats)
        self._refresh_timer.start(5000)  # 每5秒刷新

    # ==================== 搜索操作 ====================

    def _do_search(self):
        """执行搜索"""
        query = self.search_input.text().strip()
        if not query:
            return

        engine_str = self.engine_combo.currentText()
        max_results = self.max_results_spin.value()
        force_p2p = self.force_p2p_check.isChecked()

        self.search_btn.setEnabled(False)
        self.search_progress.setVisible(True)
        self.search_progress.setRange(0, 0)  # 不确定进度

        self._log(f"开始搜索: {query} (engine={engine_str}, p2p={force_p2p})")

        # 异步执行搜索
        asyncio.create_task(self._async_search(query, engine_str, max_results, force_p2p))

    async def _async_search(self, query: str, engine: str, max_results: int, force_p2p: bool):
        """异步搜索"""
        try:
            if self.proxy:
                from client.src.business.p2p_search_proxy import SearchEngineType

                engine_type = SearchEngineType(engine)
                task = await self.proxy.search(
                    query=query,
                    engine=engine_type,
                    max_results=max_results,
                    use_p2p=force_p2p
                )

                # 更新UI
                self.search_completed.emit({
                    "task": task,
                    "query": query
                })

                self._update_search_result(task)

        except Exception as e:
            self._log(f"搜索错误: {e}")
        finally:
            self.search_btn.setEnabled(True)
            self.search_progress.setVisible(False)

    def _update_search_result(self, task):
        """更新搜索结果"""
        # 路由信息
        route_text = f"路由类型: {task.route_type}"
        if task.target_node:
            route_text += f", 目标节点: {task.target_node[:12]}..."
        route_text += f", 延迟: {task.latency_ms:.0f}ms"
        self.route_info.setText(route_text)

        # 结果
        if task.status.value == "success":
            result_lines = [f"✅ 搜索成功 ({len(task.results)} 条结果)\n"]
            for i, r in enumerate(task.results[:5], 1):
                result_lines.append(f"{i}. {r.title}")
                result_lines.append(f"   {r.snippet[:100]}...")
                result_lines.append(f"   URL: {r.url}\n")
        else:
            result_lines = [f"❌ 搜索失败: {task.status.value}"]
            if task.error:
                result_lines.append(f"错误: {task.error}")

        self.result_text.setPlainText("\n".join(result_lines))
        self._update_stats()

    # ==================== 节点操作 ====================

    def _update_peers(self):
        """刷新节点列表"""
        if not self.proxy:
            return

        try:
            peers = self.proxy.capability_registry.get_all_peers()
            self.peer_table.setRowCount(len(peers))

            for row, peer in enumerate(peers):
                self.peer_table.setItem(row, 0, QTableWidgetItem(peer.node_id[:12]))
                self.peer_table.setItem(row, 1, QTableWidgetItem("✅" if peer.has_external_net() else "❌"))
                self.peer_table.setItem(row, 2, QTableWidgetItem("✅" if peer.has_search_tools() else "❌"))
                self.peer_table.setItem(row, 3, QTableWidgetItem(f"{peer.latency_ms:.0f}"))
                self.peer_table.setItem(row, 4, QTableWidgetItem(f"{peer.search_success_count}/{peer.search_success_count + peer.search_fail_count}"))
                self.peer_table.setItem(row, 5, QTableWidgetItem(f"{peer.get_priority():.2f}"))

            self.peer_updated.emit({"peers": peers})

        except Exception as e:
            self._log(f"刷新节点失败: {e}")

    def _register_peer_dialog(self):
        """注册节点对话框"""
        QMessageBox.information(
            self,
            "注册节点",
            "可以通过中继服务器广播来注册外部节点。\n"
            "确保外部节点已启用 '广告外网访问能力' 选项。"
        )

    # ==================== 路由配置 ====================

    def _add_relay_server(self):
        """添加中继服务器"""
        QMessageBox.information(
            self,
            "添加中继服务器",
            "请在路由策略配置中输入中继服务器地址，格式: host:port"
        )

    def _remove_relay_server(self):
        """移除选中的中继服务器"""
        current_row = self.relay_list.currentRow()
        if current_row >= 0:
            self.relay_list.takeItem(current_row)

    # ==================== 统计 ====================

    def _update_stats(self):
        """更新统计信息"""
        if not self.proxy:
            return

        try:
            stats = self.proxy.get_stats()

            self.total_requests_label.setText(str(stats.get("total_requests", 0)))
            self.direct_success_label.setText(str(stats.get("direct_success", 0)))
            self.p2p_success_label.setText(str(stats.get("p2p_success", 0)))
            self.fallback_label.setText(str(stats.get("fallback_count", 0)))
            self.error_label.setText(str(stats.get("error_count", 0)))
            self.success_rate_label.setText(f"{stats.get('success_rate', 0) * 100:.1f}%")

            self.online_peers_label.setText(str(stats.get("peer_count", 0)))
            self.cache_size_label.setText(str(stats.get("cache_size", 0)))

            self.stats_updated.emit(stats)

        except Exception as e:
            self._log(f"更新统计失败: {e}")

    # ==================== 工具 ====================

    def _log(self, message: str):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
