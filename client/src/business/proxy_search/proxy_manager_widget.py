# -*- coding: utf-8 -*-
"""
代理源管理 PyQt6 组件
"""

from typing import List, Dict, Optional, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QLineEdit, QComboBox, QLabel,
    QGroupBox, QTabWidget, QTextEdit, QSplitter,
    QMessageBox, QToolButton, QMenu, QStatusBar,
    QProgressBar, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QAction, QIcon, QColor

from .config import (
    get_config, add_source, remove_source, enable_source,
    ProxySource, get_allowed_domains, ProxySearchConfig
)
from .url_router import get_router, URLRouteResult
from .monitor import get_monitor, get_status_summary, ProxyMonitor, HealthStatus


class ProxySourceTable(QTableWidget):
    """代理源表格"""

    source_toggled = pyqtSignal(str, bool)  # name, enabled
    source_deleted = pyqtSignal(str)  # name
    source_refresh = pyqtSignal(str)  # name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels([
            "启用", "名称", "URL", "协议", "优先级"
        ])

        # 表头设置
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 50)
        self.setColumnWidth(3, 70)
        self.setColumnWidth(4, 70)

        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def load_sources(self, sources: List[ProxySource]):
        """加载代理源"""
        self.setRowCount(0)
        for source in sources:
            self._add_source_row(source)

    def _add_source_row(self, source: ProxySource):
        """添加代理源行"""
        row = self.rowCount()
        self.insertRow(row)

        # 启用复选框
        checkbox = QCheckBox()
        checkbox.setChecked(source.enabled)
        checkbox.stateChanged.connect(
            lambda state, s=source: self.source_toggled.emit(s.name, bool(state))
        )
        self.setCellWidget(row, 0, checkbox)

        # 名称
        name_item = QTableWidgetItem(source.name)
        name_item.setData(Qt.ItemDataRole.UserRole, source.name)
        self.setItem(row, 1, name_item)

        # URL
        url_item = QTableWidgetItem(source.url)
        url_item.setToolTip(source.url)
        self.setItem(row, 2, url_item)

        # 协议
        protocol_item = QTableWidgetItem(source.protocol.upper())
        self.setItem(row, 3, protocol_item)

        # 优先级
        priority_item = QTableWidgetItem(str(source.priority))
        self.setItem(row, 4, priority_item)


class WhiteListTable(QTableWidget):
    """白名单域名表格"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["分类", "域名", "描述"])
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def load_whitelist(self, whitelist: Dict[str, List[str]]):
        """加载白名单"""
        self.setRowCount(0)

        descriptions = {
            "搜索引擎": "Google, Bing, 学术搜索等",
            "编程问答": "StackOverflow, GitHub, Reddit等",
            "开发文档": "官方文档, API参考",
            "AI/机器学习": "HuggingFace, ArXiv等",
            "知识库": "Wikipedia, Wiki等",
            "视频类（禁止）": "YouTube, Bilibili等（禁止使用代理）",
        }

        for category, domains in whitelist.items():
            for domain in domains:
                self._add_domain_row(category, domain, descriptions.get(category, ""))

    def _add_domain_row(self, category: str, domain: str, desc: str):
        """添加域名行"""
        row = self.rowCount()
        self.insertRow(row)

        self.setItem(row, 0, QTableWidgetItem(category))
        self.setItem(row, 1, QTableWidgetItem(domain))
        self.setItem(row, 2, QTableWidgetItem(desc))


class ProxyManagerWidget(QWidget):
    """
    代理管理主组件

    功能：
    1. 管理代理源（添加、删除、启用/禁用）
    2. 查看白名单
    3. 查看健康状态
    4. 定时监测控制
    """

    # 信号
    proxy_status_changed = pyqtSignal(bool)  # 代理启用状态变化
    health_report_updated = pyqtSignal(dict)  # 健康报告更新

    def __init__(self, parent=None):
        super().__init__(parent)
        self._monitor = get_monitor()
        self._init_ui()
        self._load_config()
        self._setup_timer()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 顶部控制栏
        control_bar = self._create_control_bar()
        layout.addLayout(control_bar)

        # 主内容区（标签页）
        tabs = QTabWidget()

        # 代理源标签页
        tabs.addTab(self._create_sources_tab(), "代理源")

        # 白名单标签页
        tabs.addTab(self._create_whitelist_tab(), "白名单")

        # 监测标签页
        tabs.addTab(self._create_monitor_tab(), "健康监测")

        # URL测试标签页
        tabs.addTab(self._create_url_test_tab(), "URL测试")

        layout.addWidget(tabs, 1)

        # 状态栏
        self._status_bar = QStatusBar()
        layout.addWidget(self._status_bar)
        self._update_status_bar()

    def _create_control_bar(self) -> QHBoxLayout:
        """创建控制栏"""
        bar = QHBoxLayout()

        # 代理开关
        self._proxy_switch = QCheckBox("启用代理")
        self._proxy_switch.stateChanged.connect(self._on_proxy_toggled)
        bar.addWidget(self._proxy_switch)

        # 代理模式
        bar.addWidget(QLabel("模式:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["智能路由", "总是代理", "从不代理"])
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        bar.addWidget(self._mode_combo)

        bar.addStretch()

        # 刷新按钮
        self._refresh_btn = QPushButton("刷新代理池")
        self._refresh_btn.clicked.connect(self._on_refresh_pool)
        bar.addWidget(self._refresh_btn)

        # 添加源按钮
        self._add_btn = QPushButton("添加代理源")
        self._add_btn.clicked.connect(self._on_add_source)
        bar.addWidget(self._add_btn)

        return bar

    def _create_sources_tab(self) -> QWidget:
        """创建代理源标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 表格
        self._source_table = ProxySourceTable()
        self._source_table.source_toggled.connect(self._on_source_toggled)
        self._source_table.source_deleted.connect(self._on_source_deleted)
        layout.addWidget(self._source_table, 1)

        return widget

    def _create_whitelist_tab(self) -> QWidget:
        """创建白名单标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 说明
        info = QLabel(
            "白名单控制哪些网站允许使用代理访问。视频类网站被禁止。\n"
            "在智能路由模式下，只有白名单中的网站才会通过代理访问。"
        )
        info.setStyleSheet("color: gray; padding: 5px;")
        layout.addWidget(info)

        # 表格
        self._whitelist_table = WhiteListTable()
        layout.addWidget(self._whitelist_table, 1)

        return widget

    def _create_monitor_tab(self) -> QWidget:
        """创建监测标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 健康状态
        status_group = QGroupBox("当前状态")
        status_layout = QHBoxLayout()

        self._health_label = QLabel("未检测")
        status_layout.addWidget(QLabel("健康状态:"))
        status_layout.addWidget(self._health_label)
        status_layout.addStretch()

        self._proxy_count_label = QLabel("0/0")
        status_layout.addWidget(QLabel("可用代理:"))
        status_layout.addWidget(self._proxy_count_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 监测控制
        control_group = QGroupBox("监测控制")
        control_layout = QHBoxLayout()

        self._monitor_switch = QCheckBox("启用定时监测")
        self._monitor_switch.stateChanged.connect(self._on_monitor_toggled)
        control_layout.addWidget(self._monitor_switch)

        control_layout.addWidget(QLabel("间隔(秒):"))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(60, 3600)
        self._interval_spin.setValue(300)
        self._interval_spin.valueChanged.connect(self._on_interval_changed)
        control_layout.addWidget(self._interval_spin)

        control_layout.addWidget(QLabel("断网阈值:"))
        self._threshold_spin = QSpinBox()
        self._threshold_spin.setRange(3, 20)
        self._threshold_spin.setValue(5)
        control_layout.addWidget(self._threshold_spin)

        control_layout.addStretch()

        self._disconnect_btn = QPushButton("立即断网")
        self._disconnect_btn.clicked.connect(self._on_manual_disconnect)
        self._disconnect_btn.setStyleSheet("background-color: #ff4444; color: white;")
        control_layout.addWidget(self._disconnect_btn)

        self._reconnect_btn = QPushButton("重新连接")
        self._reconnect_btn.clicked.connect(self._on_reconnect)
        control_layout.addWidget(self._reconnect_btn)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # 健康报告
        report_group = QGroupBox("健康报告")
        report_layout = QVBoxLayout()

        self._report_text = QTextEdit()
        self._report_text.setReadOnly(True)
        self._report_text.setMaximumHeight(150)
        report_layout.addWidget(self._report_text)

        report_group.setLayout(report_layout)
        layout.addWidget(report_group, 1)

        return widget

    def _create_url_test_tab(self) -> QWidget:
        """创建URL测试标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 输入
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("URL/查询:"))
        self._test_input = QLineEdit()
        self._test_input.setPlaceholderText("输入URL或搜索查询进行测试...")
        self._test_input.returnPressed.connect(self._on_test_url)
        input_layout.addWidget(self._test_input, 1)

        self._test_btn = QPushButton("测试")
        self._test_btn.clicked.connect(self._on_test_url)
        input_layout.addWidget(self._test_btn)

        layout.addLayout(input_layout)

        # 结果
        result_group = QGroupBox("路由结果")
        result_layout = QVBoxLayout()

        self._result_text = QTextEdit()
        self._result_text.setReadOnly(True)
        result_layout.addWidget(self._result_text)

        result_group.setLayout(result_layout)
        layout.addWidget(result_group, 1)

        return widget

    def _load_config(self):
        """加载配置"""
        config = get_config()

        # 代理开关
        self._proxy_switch.setChecked(config.enable_proxy)

        # 代理模式
        mode_map = {"smart": 0, "always": 1, "never": 2}
        self._mode_combo.setCurrentIndex(mode_map.get(config.proxy_mode, 0))

        # 代理源
        self._source_table.load_sources(config.sources)

        # 白名单
        self._whitelist_table.load_whitelist(get_allowed_domains())

        # 监测
        self._interval_spin.setValue(self._monitor.interval)

    def _setup_timer(self):
        """设置定时器"""
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_status)
        self._update_timer.start(5000)  # 每5秒更新

    def _update_status(self):
        """更新状态"""
        summary = get_status_summary()
        self._update_status_bar()
        self._health_label.setText(summary.get("health_status", "未知"))
        self._proxy_count_label.setText(
            f"{summary.get('healthy_proxies', 0)}/{summary.get('total_proxies', 0)}"
        )

    def _update_status_bar(self):
        """更新状态栏"""
        summary = get_status_summary()

        status_text = "🟢 在线" if summary["online"] else "🔴 断网"
        status_text += f" | 代理: {'可用' if summary['proxy_available'] else '不可用'}"
        status_text += f" | 可用代理: {summary['healthy_proxies']}/{summary['total_proxies']}"

        self._status_bar.showMessage(status_text)

    def _on_proxy_toggled(self, state: bool):
        """代理开关变化"""
        config = get_config()
        config.enable_proxy = state
        self._update_status_bar()
        self.proxy_status_changed.emit(state)

    def _on_mode_changed(self, mode_text: str):
        """代理模式变化"""
        config = get_config()
        mode_map = {"智能路由": "smart", "总是代理": "always", "从不代理": "never"}
        config.proxy_mode = mode_map.get(mode_text, "smart")

    def _on_source_toggled(self, name: str, enabled: bool):
        """代理源启用/禁用"""
        enable_source(name, enabled)
        self._load_config()

    def _on_source_deleted(self, name: str):
        """删除代理源"""
        reply = QMessageBox.question(
            self, "确认删除", f"确定删除代理源 '{name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            remove_source(name)
            self._load_config()

    def _on_add_source(self):
        """添加代理源"""
        # 简单的输入对话框
        from PyQt6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "添加代理源", "名称:")
        if not ok or not name:
            return

        url, ok = QInputDialog.getText(self, "添加代理源", "URL:")
        if not ok or not url:
            return

        add_source(name, url)
        self._load_config()
        QMessageBox.information(self, "成功", f"已添加代理源: {name}")

    def _on_refresh_pool(self):
        """刷新代理池"""
        from .proxy_pool import get_proxy_pool
        import asyncio

        async def refresh():
            pool = get_proxy_pool()
            count = await pool.refresh()
            return count

        def done(future):
            try:
                count = future.result()
                self._status_bar.showMessage(f"代理池刷新完成，获取 {count} 个代理")
                self._update_status()
            except Exception as e:
                self._status_bar.showMessage(f"刷新失败: {e}")

        asyncio.create_task(refresh()).add_done_callback(done)
        self._status_bar.showMessage("正在刷新代理池...")

    def _on_monitor_toggled(self, state: bool):
        """监测开关变化"""
        import asyncio
        config = get_config()

        if state:
            config.enable_monitoring = True
            asyncio.create_task(self._monitor.start())
        else:
            config.enable_monitoring = False
            asyncio.create_task(self._monitor.stop())

    def _on_interval_changed(self, value: int):
        """监测间隔变化"""
        self._monitor.interval = value

    async def _on_manual_disconnect(self):
        """手动断网"""
        await self._monitor.manual_disconnect("用户手动断网")
        self._update_status()
        QMessageBox.warning(self, "已断网", "代理已关闭，网络访问将直接连接")

    async def _on_reconnect(self):
        """重新连接"""
        await self._monitor.reconnect()
        self._update_status()
        QMessageBox.information(self, "已连接", "代理已启用")

    def _on_test_url(self):
        """测试URL路由"""
        url = self._test_input.text()
        if not url:
            return

        router = get_router()
        result = router.route(url)

        info = router.get_access_info(url)

        output = f"""URL类型: {result.url_type.value}
最终URL: {result.final_url}
使用代理: {'是' if result.use_proxy else '否'}
原因: {result.reason}
分类: {result.category}
允许访问: {'是' if result.url_type.value != 'blocked' else '否'}
"""

        self._result_text.setPlainText(output)
