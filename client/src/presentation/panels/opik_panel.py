"""
📊 Opik Dashboard 面板
======================

提供 Opik Dashboard 的 UI 集成：
1. 嵌入 Opik Dashboard (QWebEngineView)
2. Traces 查看器
3. Metrics 监控
4. Alerts 管理
5. 配置管理

作者: LivingTreeAI Team
日期: 2026-04-29
版本: 1.0.0
"""

import json
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QUrl, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QSplitter,
    QTextEdit, QTabWidget, QComboBox, QProgressBar,
    QTextBrowser, QFileDialog, QGroupBox, QFormLayout,
    QLineEdit, QSpinBox, QCheckBox, QPlainTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QStatusBar,
    QMainWindow, QApplication
)
from PyQt6.QtGui import QFont, QTextCursor, QAction, QIcon

# 尝试导入 QWebEngineView（用于嵌入 Dashboard）
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
    QWebEngineView = None

from loguru import logger

# 导入 Opik 追踪和监控模块
try:
    from client.src.business.opik_tracer import (
        is_opik_enabled, start_trace, log_trace,
        OpikConfig, init_opik_for_livingtree, configure_opik
    )
    OPIK_TRACER_AVAILABLE = True
except ImportError:
    OPIK_TRACER_AVAILABLE = False

try:
    from client.src.business.opik_monitor import (
        get_monitor, MonitorConfig, AlertRule
    )
    OPIK_MONITOR_AVAILABLE = True
except ImportError:
    OPIK_MONITOR_AVAILABLE = False


# ─── Opik Dashboard 面板主界面 ─────────────────────────────────────
class OpikDashboardPanel(QWidget):
    """
    Opik Dashboard 面板

    功能标签页：
    1. Dashboard (嵌入 Opik Web UI)
    2. Traces (追踪记录查看)
    3. Metrics (指标监控)
    4. Alerts (告警管理)
    5. 配置 (Opik 连接配置)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 状态
        self._opik_url: str = "http://localhost:5173"
        self._dashboard_loaded: bool = False

        # UI 组件
        self.web_view: Optional[QWebEngineView] = None
        self.traces_table: Optional[QTableWidget] = None
        self.metrics_table: Optional[QTableWidget] = None
        self.alerts_table: Optional[QTableWidget] = None
        self.config_url: Optional[QLineEdit] = None
        self.status_label: Optional[QLabel] = None

        self._init_ui()
        self._init_connections()
        self._check_opik_status()

        logger.info("[OpikDashboardPanel] 初始化完成")

    # ─── 初始化 ─────────────────────────────────────────────────────

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题栏
        title_bar = self._create_title_bar()
        layout.addWidget(title_bar)

        # 主内容区（标签页）
        tabs = QTabWidget()

        # 标签页1: Dashboard (嵌入 Web UI)
        dashboard_tab = self._create_dashboard_tab()
        tabs.addTab(dashboard_tab, "📊 Dashboard")

        # 标签页2: Traces
        traces_tab = self._create_traces_tab()
        tabs.addTab(traces_tab, "🔍 Traces")

        # 标签页3: Metrics
        metrics_tab = self._create_metrics_tab()
        tabs.addTab(metrics_tab, "📈 Metrics")

        # 标签页4: Alerts
        alerts_tab = self._create_alerts_tab()
        tabs.addTab(alerts_tab, "🚨 Alerts")

        # 标签页5: 配置
        config_tab = self._create_config_tab()
        tabs.addTab(config_tab, "⚙️ 配置")

        layout.addWidget(tabs)

        # 状态栏
        status_bar = self._create_status_bar()
        layout.addWidget(status_bar)

    def _create_title_bar(self) -> QWidget:
        """创建标题栏"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        title = QLabel("📊 Opik Dashboard")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # 连接状态指示器
        self.status_label = QLabel("⚪ 未连接")
        self.status_label.setStyleSheet("font-size: 12px; padding: 4px 8px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._on_refresh_dashboard)
        layout.addWidget(refresh_btn)

        # 外部打开按钮
        open_external_btn = QPushButton("🔗 外部打开")
        open_external_btn.clicked.connect(self._on_open_external)
        layout.addWidget(open_external_btn)

        return widget

    def _create_dashboard_tab(self) -> QWidget:
        """创建 Dashboard 嵌入标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        if WEBENGINE_AVAILABLE:
            # 使用 QWebEngineView 嵌入 Dashboard
            self.web_view = QWebEngineView()
            self.web_view.setMinimumHeight(600)

            # 配置 WebEngine 设置
            settings = self.web_view.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)

            # 加载 Dashboard
            self.web_view.load(QUrl(self._opik_url))

            # 连接信号
            self.web_view.loadFinished.connect(self._on_load_finished)
            self.web_view.loadStarted.connect(self._on_load_started)

            layout.addWidget(self.web_view)

            # 加载状态标签
            self.load_status_label = QLabel("⏳ 正在加载 Dashboard...")
            self.load_status_label.setStyleSheet("padding: 8px; color: #666;")
            layout.addWidget(self.load_status_label)

        else:
            # 如果 QWebEngineView 不可用，显示提示
            hint = QLabel(
                "⚠️ QWebEngineView 不可用\n"
                "请安装 PyQt6-WebEngine:\n"
                "pip install PyQt6-WebEngine\n\n"
                f"或者直接在浏览器访问: {self._opik_url}"
            )
            hint.setStyleSheet("font-size: 14px; padding: 20px; color: #666;")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(hint)

            # 提供手动打开链接的按钮
            open_btn = QPushButton(f"🔗 打开 {self._opik_url}")
            open_btn.clicked.connect(lambda: webbrowser.open(self._opik_url))
            layout.addWidget(open_btn)

        return widget

    def _create_traces_tab(self) -> QWidget:
        """创建 Traces 查看标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 控制栏
        control_bar = QHBoxLayout()

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新 Traces")
        refresh_btn.clicked.connect(self._on_refresh_traces)
        control_bar.addWidget(refresh_btn)

        control_bar.addStretch()

        # 提示标签
        hint = QLabel("提示: Traces 数据来自 Opik SDK，需要先在配置标签页启用追踪")
        hint.setStyleSheet("font-size: 11px; color: #888;")
        control_bar.addWidget(hint)

        layout.addLayout(control_bar)

        # Traces 表格
        self.traces_table = QTableWidget()
        self.traces_table.setColumnCount(6)
        self.traces_table.setHorizontalHeaderLabels([
            "ID", "名称", "类型", "开始时间", "延迟(秒)", "状态"
        ])
        self.traces_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.traces_table)

        # 详情区
        detail_group = QGroupBox("📝 Trace 详情")
        detail_layout = QVBoxLayout(detail_group)

        self.trace_detail = QPlainTextEdit()
        self.trace_detail.setReadOnly(True)
        self.trace_detail.setMaximumHeight(200)
        detail_layout.addWidget(self.trace_detail)

        layout.addWidget(detail_group)

        return widget

    def _create_metrics_tab(self) -> QWidget:
        """创建 Metrics 监控标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 控制栏
        control_bar = QHBoxLayout()

        refresh_btn = QPushButton("🔄 刷新指标")
        refresh_btn.clicked.connect(self._on_refresh_metrics)
        control_bar.addWidget(refresh_btn)

        control_bar.addStretch()

        layout.addLayout(control_bar)

        # Metrics 表格
        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(5)
        self.metrics_table.setHorizontalHeaderLabels([
            "指标名称", "当前值", "平均值", "最大值", "最小值"
        ])
        self.metrics_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.metrics_table)

        # 监控器统计（如果可用）
        if OPIK_MONITOR_AVAILABLE:
            monitor_group = QGroupBox("📊 监控器统计")
            monitor_layout = QVBoxLayout(monitor_group)

            self.monitor_stats = QTextBrowser()
            self.monitor_stats.setMaximumHeight(200)
            monitor_layout.addWidget(self.monitor_stats)

            layout.addWidget(monitor_group)

        return widget

    def _create_alerts_tab(self) -> QWidget:
        """创建 Alerts 管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 控制栏
        control_bar = QHBoxLayout()

        refresh_btn = QPushButton("🔄 刷新告警")
        refresh_btn.clicked.connect(self._on_refresh_alerts)
        control_bar.addWidget(refresh_btn)

        add_btn = QPushButton("➕ 添加告警规则")
        add_btn.clicked.connect(self._on_add_alert_rule)
        control_bar.addWidget(add_btn)

        control_bar.addStretch()

        layout.addLayout(control_bar)

        # Alerts 表格
        self.alerts_table = QTableWidget()
        self.alerts_table.setColumnCount(5)
        self.alerts_table.setHorizontalHeaderLabels([
            "规则名称", "指标", "条件", "阈值", "状态"
        ])
        self.alerts_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.alerts_table)

        # 告警日志
        log_group = QGroupBox("📋 告警日志")
        log_layout = QVBoxLayout(log_group)

        self.alert_log = QTextBrowser()
        self.alert_log.setMaximumHeight(200)
        log_layout.addWidget(self.alert_log)

        layout.addWidget(log_group)

        return widget

    def _create_config_tab(self) -> QWidget:
        """创建配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Opik 连接配置
        conn_group = QGroupBox("🔌 Opik 连接配置")
        conn_form = QFormLayout(conn_group)

        # Dashboard URL
        self.config_url = QLineEdit(self._opik_url)
        conn_form.addRow("Dashboard URL:", self.config_url)

        # 使用本地模式
        self.config_use_local = QCheckBox("使用本地部署")
        self.config_use_local.setChecked(True)
        self.config_use_local.stateChanged.connect(self._on_toggle_local_mode)
        conn_form.addRow("", self.config_use_local)

        # API Key (云端模式)
        self.config_api_key = QLineEdit()
        self.config_api_key.setPlaceholderText("仅云端模式需要")
        conn_form.addRow("API Key:", self.config_api_key)

        # Workspace (云端模式)
        self.config_workspace = QLineEdit()
        self.config_workspace.setPlaceholderText("仅云端模式需要")
        conn_form.addRow("Workspace:", self.config_workspace)

        # 项目名
        self.config_project = QLineEdit("livingtree-ai")
        conn_form.addRow("项目名:", self.config_project)

        layout.addWidget(conn_group)

        # 追踪选项
        trace_group = QGroupBox("📡 追踪选项")
        trace_layout = QVBoxLayout(trace_group)

        self.trace_llm = QCheckBox("追踪 LLM 调用")
        self.trace_llm.setChecked(True)
        trace_layout.addWidget(self.trace_llm)

        self.trace_tool = QCheckBox("追踪 Tool 调用")
        self.trace_tool.setChecked(True)
        trace_layout.addWidget(self.trace_tool)

        self.trace_agent = QCheckBox("追踪 Agent 调用")
        self.trace_agent.setChecked(True)
        trace_layout.addWidget(self.trace_agent)

        layout.addWidget(trace_group)

        # 监控选项
        monitor_group = QGroupBox("📊 监控选项")
        monitor_layout = QVBoxLayout(monitor_group)

        self.monitor_token = QCheckBox("监控 Token 使用")
        self.monitor_token.setChecked(True)
        monitor_layout.addWidget(self.monitor_token)

        self.monitor_cost = QCheckBox("监控成本")
        self.monitor_cost.setChecked(True)
        monitor_layout.addWidget(self.monitor_cost)

        self.monitor_latency = QCheckBox("监控延迟")
        self.monitor_latency.setChecked(True)
        monitor_layout.addWidget(self.monitor_latency)

        layout.addWidget(monitor_group)

        # 操作按钮
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ 应用配置")
        apply_btn.clicked.connect(self._on_apply_config)
        btn_layout.addWidget(apply_btn)

        test_btn = QPushButton("🧪 测试连接")
        test_btn.clicked.connect(self._on_test_connection)
        btn_layout.addWidget(test_btn)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        layout.addStretch()

        return widget

    def _create_status_bar(self) -> QWidget:
        """创建状态栏"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 状态标签
        self.status_bar_label = QLabel("就绪")
        self.status_bar_label.setStyleSheet("font-size: 11px; color: #666;")
        layout.addWidget(self.status_bar_label)

        layout.addStretch()

        # Opik Logo (文字版)
        logo = QLabel("Powered by Opik")
        logo.setStyleSheet("font-size: 10px; color: #888;")
        layout.addWidget(logo)

        return widget

    def _init_connections(self):
        """初始化信号连接"""
        pass

    # ─── Dashboard 相关槽函数 ─────────────────────────────────────────

    def _on_load_started(self):
        """开始加载 Dashboard"""
        self.load_status_label.setText("⏳ 正在加载 Dashboard...")
        self.load_status_label.setStyleSheet("padding: 8px; color: #666;")

    def _on_load_finished(self, success: bool):
        """加载完成"""
        if success:
            self.load_status_label.setText("✅ Dashboard 加载成功")
            self.load_status_label.setStyleSheet("padding: 8px; color: green;")
            self._dashboard_loaded = True
            self._update_status_label("🟢 已连接", "green")
        else:
            self.load_status_label.setText("❌ Dashboard 加载失败")
            self.load_status_label.setStyleSheet("padding: 8px; color: red;")
            self._dashboard_loaded = False
            self._update_status_label("🔴 连接失败", "red")

    def _on_refresh_dashboard(self):
        """刷新 Dashboard"""
        if self.web_view:
            self.web_view.reload()

    def _on_open_external(self):
        """在外部浏览器打开 Dashboard"""
        webbrowser.open(self._opik_url)

    # ─── Traces 相关槽函数 ─────────────────────────────────────────────

    def _on_refresh_traces(self):
        """刷新 Traces 数据"""
        self._log("🔄 刷新 Traces 数据...")

        # 这里应该从 Opik API 获取 traces 数据
        # 由于 Opik Python SDK 的限制，这里先显示提示
        self.traces_table.setRowCount(1)
        self.traces_table.setItem(0, 0, QTableWidgetItem("N/A"))
        self.traces_table.setItem(0, 1, QTableWidgetItem("需要通过 Opik Python SDK 获取"))
        self.traces_table.setItem(0, 2, QTableWidgetItem("N/A"))
        self.traces_table.setItem(0, 3, QTableWidgetItem("N/A"))
        self.traces_table.setItem(0, 4, QTableWidgetItem("N/A"))
        self.traces_table.setItem(0, 5, QTableWidgetItem("N/A"))

        self.trace_detail.setPlainText(
            "提示: 要通过 Python SDK 获取 Traces 数据，请使用:\n"
            "from opik import Opik\n"
            "client = Opik()\n"
            "traces = client.traces()\n"
            "\n"
            "或者直接在 Dashboard 网页界面查看。"
        )

        self._log("✅ Traces 数据刷新完成（提示模式）")

    # ─── Metrics 相关槽函数 ─────────────────────────────────────────────

    def _on_refresh_metrics(self):
        """刷新 Metrics 数据"""
        self._log("📈 刷新 Metrics 数据...")

        # 显示基础指标
        metrics_data = [
            ("LLM 调用次数", "N/A", "N/A", "N/A", "N/A"),
            ("平均延迟", "N/A", "N/A", "N/A", "N/A"),
            ("Token 使用量", "N/A", "N/A", "N/A", "N/A"),
            ("错误率", "N/A", "N/A", "N/A", "N/A"),
        ]

        self.metrics_table.setRowCount(len(metrics_data))
        for i, (name, current, avg, max_val, min_val) in enumerate(metrics_data):
            self.metrics_table.setItem(i, 0, QTableWidgetItem(name))
            self.metrics_table.setItem(i, 1, QTableWidgetItem(current))
            self.metrics_table.setItem(i, 2, QTableWidgetItem(avg))
            self.metrics_table.setItem(i, 3, QTableWidgetItem(max_val))
            self.metrics_table.setItem(i, 4, QTableWidgetItem(min_val))

        # 更新监控器统计
        if OPIK_MONITOR_AVAILABLE:
            try:
                monitor = get_monitor()
                stats = monitor.get_statistics()

                stats_text = f"""
                <h4>📊 监控器统计</h4>
                <p><b>总 Tool 调用次数:</b> {stats.get('total_tool_calls', 0)}</p>
                <p><b>总告警次数:</b> {stats.get('total_alerts', 0)}</p>
                <p><b>告警规则数:</b> {stats.get('alert_rules_count', 0)}</p>
                """

                self.monitor_stats.setHtml(stats_text)
            except Exception as e:
                self._log(f"❌ 获取监控器统计失败: {e}")

        self._log("✅ Metrics 数据刷新完成")

    # ─── Alerts 相关槽函数 ─────────────────────────────────────────────

    def _on_refresh_alerts(self):
        """刷新 Alerts 数据"""
        self._log("🚨 刷新 Alerts 数据...")

        if OPIK_MONITOR_AVAILABLE:
            try:
                monitor = get_monitor()
                alert_rules = monitor.alert_rules

                self.alerts_table.setRowCount(len(alert_rules))

                for i, rule in enumerate(alert_rules):
                    self.alerts_table.setItem(i, 0, QTableWidgetItem(rule.name))
                    self.alerts_table.setItem(i, 1, QTableWidgetItem(rule.metric_name))
                    self.alerts_table.setItem(i, 2, QTableWidgetItem(f"{rule.condition} {rule.threshold}"))
                    self.alerts_table.setItem(i, 3, QTableWidgetItem(str(rule.threshold)))
                    self.alerts_table.setItem(i, 4, QTableWidgetItem("启用" if rule.enabled else "禁用"))

                self._log(f"✅ Alerts 数据刷新完成，规则数: {len(alert_rules)}")

            except Exception as e:
                self._log(f"❌ 刷新 Alerts 失败: {e}")
        else:
            self.alerts_table.setRowCount(1)
            self.alerts_table.setItem(0, 0, QTableWidgetItem("监控器模块不可用"))
            self.alerts_table.setItem(0, 1, QTableWidgetItem("N/A"))
            self.alerts_table.setItem(0, 2, QTableWidgetItem("N/A"))
            self.alerts_table.setItem(0, 3, QTableWidgetItem("N/A"))
            self.alerts_table.setItem(0, 4, QTableWidgetItem("N/A"))

    def _on_add_alert_rule(self):
        """添加告警规则"""
        self._log("⚠️ 添加告警规则功能待实现")
        QMessageBox.information(self, "提示", "添加告警规则功能正在开发中...")

    # ─── 配置相关槽函数 ─────────────────────────────────────────────

    def _on_toggle_local_mode(self, state):
        """切换本地/云端模式"""
        is_local = state == Qt.CheckState.Checked.value
        self.config_api_key.setEnabled(not is_local)
        self.config_workspace.setEnabled(not is_local)

    def _on_apply_config(self):
        """应用配置"""
        self._log("⚙️ 应用 Opik 配置...")

        if not OPIK_TRACER_AVAILABLE:
            QMessageBox.warning(self, "警告", "Opik 追踪模块不可用，请检查安装")
            return

        try:
            # 读取配置
            use_local = self.config_use_local.isChecked()
            api_key = self.config_api_key.text() if not use_local else None
            workspace = self.config_workspace.text() if not use_local else None
            project_name = self.config_project.text()

            # 创建配置对象
            config = OpikConfig(
                enabled=True,
                use_local=use_local,
                api_key=api_key,
                workspace=workspace,
                project_name=project_name,
                trace_llm_calls=self.trace_llm.isChecked(),
                trace_tool_calls=self.trace_tool.isChecked(),
                trace_agent_calls=self.trace_agent.isChecked(),
                monitor_token_usage=self.monitor_token.isChecked(),
                monitor_cost=self.monitor_cost.isChecked(),
                monitor_latency=self.monitor_latency.isChecked(),
            )

            # 初始化 Opik
            success = init_opik_for_livingtree(config)

            if success:
                QMessageBox.information(self, "成功", "✅ Opik 配置应用成功！")
                self._log("✅ Opik 配置应用成功")
                self._check_opik_status()
            else:
                QMessageBox.warning(self, "警告", "Opik 配置应用失败，请检查日志")
                self._log("❌ Opik 配置应用失败")

        except Exception as e:
            self._log(f"❌ 应用配置失败: {e}")
            QMessageBox.critical(self, "错误", f"应用配置失败: {e}")

    def _on_test_connection(self):
        """测试 Opik 连接"""
        self._log("🧪 测试 Opik 连接...")

        if WEBENGINE_AVAILABLE and self.web_view:
            # 重新加载 Dashboard
            self.web_view.load(QUrl(self.config_url.text()))

        # 检查 Opik 是否启用
        if OPIK_TRACER_AVAILABLE:
            enabled = is_opik_enabled()
            if enabled:
                QMessageBox.information(self, "成功", "✅ Opik 已启用且可用")
                self._log("✅ Opik 连接测试通过")
            else:
                QMessageBox.warning(self, "警告", "Opik 已安装但未启用，请在配置中应用")
                self._log("⚠️ Opik 已安装但未启用")
        else:
            QMessageBox.warning(self, "警告", "Opik SDK 未安装，请运行: pip install opik")
            self._log("❌ Opik SDK 未安装")

    # ─── 辅助方法 ─────────────────────────────────────────────────────

    def _check_opik_status(self):
        """检查 Opik 状态"""
        if OPIK_TRACER_AVAILABLE and is_opik_enabled():
            self._update_status_label("🟢 已连接", "green")
        else:
            self._update_status_label("🔴 未连接", "red")

    def _update_status_label(self, text: str, color: str):
        """更新状态标签"""
        if self.status_label:
            self.status_label.setText(text)
            self.status_label.setStyleSheet(f"font-size: 12px; padding: 4px 8px; color: {color};")

        if self.status_bar_label:
            self.status_bar_label.setText(text)

    def _log(self, message: str):
        """输出日志（在状态栏显示）"""
        if self.status_bar_label:
            self.status_bar_label.setText(message)

        logger.info(f"[OpikDashboardPanel] {message}")


# ─── 延迟加载函数 ─────────────────────────────────────────────────────
def _create_opik_panel() -> type:
    """
    创建 Opik Dashboard 面板的延迟加载函数

    Returns:
        OpikDashboardPanel 类
    """
    try:
        return OpikDashboardPanel
    except Exception as e:
        logger.error(f"[_create_opik_panel] 导入失败: {e}")
        return None


if __name__ == "__main__":
    # 测试 Opik Dashboard 面板
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    panel = OpikDashboardPanel()
    panel.show()

    sys.exit(app.exec())
