"""
Kernel Monitor Panel - 内核监控面板

实时显示 Microkernel 状态、服务注册表、插件状态、事件总线统计。
"""

import time
from typing import Any, Dict, Optional

from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QThreadPool, QRunnable,
)
from PyQt6.QtGui import QFont, QColor, QPalette
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QProgressBar, QTextEdit, QGroupBox,
    QSplitter, QHeaderView, QMessageBox, QTreeWidget,
    QTreeWidgetItem, QStatusBar,
)

from .business.microkernel.kernel import get_kernel, Microkernel
from .business.microkernel.service_registry import get_service_registry
from .business.microkernel.performance_monitor import get_performance_monitor
from core.plugin_framework.event_bus import get_event_bus
from core.plugin_framework.plugin_manager import get_plugin_manager


# ─────────────────────────────────────────────────────────────
# 监控卡片（显示单个指标）
# ─────────────────────────────────────────────────────────────

class MetricCard(QGroupBox):
    """指标卡片"""

    def __init__(self, title: str, value: str = "N/A", unit: str = ""):
        super().__init__(title)
        self._value_label = QLabel(value)
        self._unit_label = QLabel(unit)
        self._trend_label = QLabel("")  # 趋势（↑ ↓ —）
        self._previous_value: Optional[float] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # 数值（大字体）
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        self._value_label.setFont(font)
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._value_label)

        # 单位和趋势
        bottom_layout = QHBoxLayout()
        self._unit_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._trend_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        bottom_layout.addWidget(self._unit_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self._trend_label)
        layout.addLayout(bottom_layout)

    def update_value(self, value: str, numeric_value: Optional[float] = None) -> None:
        """更新数值"""
        self._value_label.setText(value)

        # 计算趋势
        if numeric_value is not None and self._previous_value is not None:
            diff = numeric_value - self._previous_value
            if diff > 0:
                self._trend_label.setText("↑")
                self._trend_label.setStyleSheet("color: #4CAF50;")
            elif diff < 0:
                self._trend_label.setText("↓")
                self._trend_label.setStyleSheet("color: #F44336;")
            else:
                self._trend_label.setText("—")
                self._trend_label.setStyleSheet("color: #9E9E9E;")
        else:
            self._trend_label.setText("")

        self._previous_value = numeric_value


# ─────────────────────────────────────────────────────────────
# 内核状态卡片
# ─────────────────────────────────────────────────────────────

class KernelStatusCard(QGroupBox):
    """内核状态卡片"""

    def __init__(self):
        super().__init__("内核状态")
        self._status_label = QLabel("未知")
        self._uptime_label = QLabel("0s")
        self._plugin_count_label = QLabel("0")
        self._service_count_label = QLabel("0")
        self._ext_point_count_label = QLabel("0")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QGridLayout(self)

        # 状态
        layout.addWidget(QLabel("状态："), 0, 0)
        self._status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._status_label, 0, 1)

        # 运行时间
        layout.addWidget(QLabel("运行时间："), 1, 0)
        layout.addWidget(self._uptime_label, 1, 1)

        # 插件数
        layout.addWidget(QLabel("插件数："), 2, 0)
        layout.addWidget(self._plugin_count_label, 2, 1)

        # 服务数
        layout.addWidget(QLabel("服务数："), 3, 0)
        layout.addWidget(self._service_count_label, 3, 1)

        # 扩展点数
        layout.addWidget(QLabel("扩展点："), 4, 0)
        layout.addWidget(self._ext_point_count_label, 4, 1)

    def update_status(self, info: Any) -> None:
        """更新状态显示"""
        # 状态颜色
        state_colors = {
            "bootstrapping": "#FF9800",  # 橙色
            "running": "#4CAF50",        # 绿色
            "degraded": "#F44336",       # 红色
            "maintenance": "#FF9800",    # 橙色
            "shutting_down": "#9E9E9E",  # 灰色
            "stopped": "#9E9E9E",        # 灰色
        }
        color = state_colors.get(info.state.value, "#000000")
        self._status_label.setStyleSheet(
            f"font-weight: bold; color: {color};"
        )
        self._status_label.setText(info.state.value)

        # 运行时间
        uptime = int(info.uptime_seconds)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60
        self._uptime_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

        # 计数
        self._plugin_count_label.setText(str(info.plugin_count))
        self._service_count_label.setText(str(info.service_count))
        self._ext_point_count_label.setText(str(info.extension_point_count))


# ─────────────────────────────────────────────────────────────
# 服务注册表表格
# ─────────────────────────────────────────────────────────────

class ServiceTable(QTableWidget):
    """服务注册表表格"""

    def __init__(self):
        super().__init__()
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["服务 ID", "接口", "版本", "插件", "优先级"])
        self.horizontalHeader().setStretchLastSection(True)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def update_services(self, services: list) -> None:
        """更新服务列表"""
        self.setRowCount(len(services))

        for row, svc in enumerate(services):
            self.setItem(row, 0, QTableWidgetItem(svc.id))
            self.setItem(row, 1, QTableWidgetItem(svc.interface))
            self.setItem(row, 2, QTableWidgetItem(svc.version))
            self.setItem(row, 3, QTableWidgetItem(svc.plugin_id))
            self.setItem(row, 4, QTableWidgetItem(str(svc.priority)))

            # 根据作用域设置背景色
            if svc.scope.value == "singleton":
                color = QColor(200, 230, 200)  # 浅绿
            elif svc.scope.value == "prototype":
                color = QColor(200, 200, 230)  # 浅蓝
            else:
                color = QColor(230, 230, 200)  # 浅黄

            for col in range(5):
                item = self.item(row, col)
                if item:
                    item.setBackground(color)


# ─────────────────────────────────────────────────────────────
# 插件状态表格
# ─────────────────────────────────────────────────────────────

class PluginTable(QTableWidget):
    """插件状态表格"""

    plugin_selected = pyqtSignal(str)  # plugin_id

    def __init__(self):
        super().__init__()
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["插件 ID", "名称", "版本", "状态", "优先级"])
        self.horizontalHeader().setStretchLastSection(True)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cellClicked.connect(self._on_cell_clicked)

    def update_plugins(self, plugins: Dict[str, Any]) -> None:
        """更新插件列表"""
        self.setRowCount(len(plugins))

        state_colors = {
            "registered": QColor(220, 220, 220),   # 灰色
            "loaded": QColor(200, 220, 255),      # 浅蓝
            "active": QColor(200, 255, 200),      # 浅绿
            "inactive": QColor(255, 255, 200),    # 浅黄
            "error": QColor(255, 200, 200),       # 浅红
        }

        for row, (pid, info) in enumerate(plugins.items()):
            self.setItem(row, 0, QTableWidgetItem(pid))
            self.setItem(row, 1, QTableWidgetItem(info.manifest.name))
            self.setItem(row, 2, QTableWidgetItem(info.manifest.version))
            self.setItem(row, 3, QTableWidgetItem(info.state.value))
            self.setItem(row, 4, QTableWidgetItem(str(info.manifest.priority)))

            # 状态颜色
            color = state_colors.get(info.state.value, QColor(255, 255, 255))
            for col in range(5):
                item = self.item(row, col)
                if item:
                    item.setBackground(color)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        item = self.item(row, 0)
        if item:
            self.plugin_selected.emit(item.text())


# ─────────────────────────────────────────────────────────────
# 事件总线统计
# ─────────────────────────────────────────────────────────────

class EventBusStats(QGroupBox):
    """事件总线统计"""

    def __init__(self):
        super().__init__("事件总线")
        self._event_count_label = QLabel("0")
        self._listener_count_label = QLabel("0")
        self._top_events_label = QLabel("无")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # 事件总数
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("事件总数："))
        self._event_count_label.setStyleSheet("font-weight: bold;")
        h1.addWidget(self._event_count_label)
        h1.addStretch()
        layout.addLayout(h1)

        # 监听器总数
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("监听器总数："))
        self._listener_count_label.setStyleSheet("font-weight: bold;")
        h2.addWidget(self._listener_count_label)
        h2.addStretch()
        layout.addLayout(h2)

        # 热门事件
        layout.addWidget(QLabel("热门事件："))
        self._top_events_label.setWordWrap(True)
        layout.addWidget(self._top_events_label)

    def update_stats(self, stats: Dict[str, Any]) -> None:
        """更新统计"""
        self._event_count_label.setText(str(stats.get("event_count", 0)))
        self._listener_count_label.setText(str(stats.get("listener_count", 0)))

        # 显示前 5 个热门事件
        top_events = stats.get("top_events", [])
        if top_events:
            text = "\n".join(
                f"  {e['event_type']}: {e['count']} 次"
                for e in top_events[:5]
            )
            self._top_events_label.setText(text)
        else:
            self._top_events_label.setText("无")


# ─────────────────────────────────────────────────────────────
# 主监控面板
# ─────────────────────────────────────────────────────────────

class KernelMonitorPanel(QWidget):
    """
    内核监控面板

    实时显示：
    1. 内核状态
    2. 服务注册表
    3. 插件状态
    4. 事件总线统计
    5. 系统资源使用
    """

    # 信号
    plugin_activate_requested = pyqtSignal(str)   # plugin_id
    plugin_deactivate_requested = pyqtSignal(str) # plugin_id
    plugin_reload_requested = pyqtSignal(str)     # plugin_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._update_interval = 1000  # 1 秒
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_all)
        self._setup_ui()
        self._start_monitoring()

    def _setup_ui(self) -> None:
        """构建 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # 标题
        title = QLabel("内核监控面板")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        main_layout.addWidget(title)

        # 顶部指标卡片
        cards_layout = QHBoxLayout()

        self._kernel_card = KernelStatusCard()
        cards_layout.addWidget(self._kernel_card)

        self._event_stats = EventBusStats()
        cards_layout.addWidget(self._event_stats)

        # 性能卡片（实时指标）
        self._perf_cards = self._create_perf_cards()
        cards_layout.addWidget(self._perf_cards)

        main_layout.addLayout(cards_layout)

        # Tab 页：服务 / 插件 / 日志
        self._tabs = QTabWidget()

        # Tab 1：服务注册表
        self._service_table = ServiceTable()
        self._tabs.addTab(self._service_table, "服务注册表")

        # Tab 2：插件状态
        plugin_widget = QWidget()
        plugin_layout = QVBoxLayout(plugin_widget)
        plugin_layout.setContentsMargins(0, 0, 0, 0)

        self._plugin_table = PluginTable()
        self._plugin_table.plugin_selected.connect(self._on_plugin_selected)
        plugin_layout.addWidget(self._plugin_table)

        # 插件操作按钮
        btn_layout = QHBoxLayout()
        self._btn_activate = QPushButton("激活")
        self._btn_deactivate = QPushButton("停用")
        self._btn_reload = QPushButton("重载")
        self._btn_activate.clicked.connect(self._activate_selected)
        self._btn_deactivate.clicked.connect(self._deactivate_selected)
        self._btn_reload.clicked.connect(self._reload_selected)
        btn_layout.addWidget(self._btn_activate)
        btn_layout.addWidget(self._btn_deactivate)
        btn_layout.addWidget(self._btn_reload)
        btn_layout.addStretch()
        plugin_layout.addLayout(btn_layout)

        self._tabs.addTab(plugin_widget, "插件状态")

        # Tab 3：系统日志（简化）
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(1000)  # 最多 1000 行
        self._tabs.addTab(self._log_view, "系统日志")

        # Tab 4：性能监控
        self._perf_tab = QWidget()
        perf_layout = QVBoxLayout(self._perf_tab)
        perf_layout.setContentsMargins(8, 8, 8, 8)

        # 性能指标网格
        perf_grid = QGridLayout()
        self._perf_labels: Dict[str, QLabel] = {}

        metrics = [
            ("CPU 使用率", "cpu_percent", "%"),
            ("内存使用率", "memory_percent", "%"),
            ("内存使用", "memory_used_mb", "MB"),
            ("事件总数", "event_count", ""),
            ("缓存命中率", "cache_hit_rate", ""),
            ("活跃插件", "active_plugins", ""),
        ]

        for i, (label_text, key, unit) in enumerate(metrics):
            row, col = divmod(i, 3)
            group = QGroupBox(label_text)
            value_label = QLabel("0")
            font = QFont()
            font.setPointSize(18)
            font.setBold(True)
            value_label.setFont(font)
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            group_layout = QVBoxLayout(group)
            group_layout.addWidget(value_label)

            self._perf_labels[key] = value_label
            perf_grid.addWidget(group, row, col)

        perf_layout.addLayout(perf_grid)
        perf_layout.addStretch()
        self._tabs.addTab(self._perf_tab, "性能监控")

        # Tab 5：告警
        self._alert_list = QTextEdit()
        self._alert_list.setReadOnly(True)
        self._tabs.addTab(self._alert_list, "告警")

        main_layout.addWidget(self._tabs)

        # 状态栏
        self._status_bar = QStatusBar()
        self._status_bar.showMessage("监控中...")
        main_layout.addWidget(self._status_bar)

    def _create_perf_cards(self) -> QWidget:
        """创建性能卡片组件"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # CPU
        self._cpu_card = self._create_mini_card("CPU", "%")
        layout.addWidget(self._cpu_card)

        # 内存
        self._mem_card = self._create_mini_card("内存", "%")
        layout.addWidget(self._mem_card)

        # 缓存命中率
        self._cache_card = self._create_mini_card("缓存命中", "")
        layout.addWidget(self._cache_card)

        return widget

    def _create_mini_card(self, title: str, unit: str) -> QGroupBox:
        """创建迷你指标卡片"""
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        value_label = QLabel("0")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        value_label.setFont(font)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)

        # 存储引用
        setattr(self, f"_{title.lower()}_value", value_label)
        return group

    def _start_monitoring(self) -> None:
        """启动监控定时器"""
        self._timer.start(self._update_interval)
        self._log("监控已启动")

    def _update_all(self) -> None:
        """更新所有监控数据"""
        try:
            # 1. 更新内核状态
            kernel = get_kernel()
            if kernel:
                info = kernel.get_info()
                self._kernel_card.update_status(info)

            # 2. 更新服务注册表
            registry = get_service_registry()
            if registry:
                services = registry.list_services()
                self._service_table.update_services(services)

            # 3. 更新插件状态
            pm = get_plugin_manager()
            if pm:
                plugins = pm.get_all_plugins()
                self._plugin_table.update_plugins(plugins)

            # 4. 更新事件总线统计
            eb = get_event_bus()
            if eb:
                stats = eb.get_stats()
                self._event_stats.update_stats(stats)

            # 5. 更新性能 Tab 数据
            monitor = get_performance_monitor()
            if monitor:
                metrics = monitor.get_current_metrics()
                self._update_perf_labels(metrics)
                self._update_alerts(monitor)

            self._status_bar.showMessage(
                f"最后更新：{time.strftime('%H:%M:%S')}"
            )

        except Exception as e:
            self._log(f"更新失败：{e}")

    def _update_perf_labels(self, metrics: dict) -> None:
        """更新性能卡片和性能Tab的显示"""
        # 更新顶部迷你卡片
        cpu = metrics.get("system.cpu_percent", 0.0)
        self._cpu_card.findChild(QLabel).setText(f"{cpu:.1f}")
        mem = metrics.get("system.memory_percent", 0.0)
        self._mem_card.findChild(QLabel).setText(f"{mem:.1f}")
        cache = metrics.get("app.cache_hit_rate", 0.0)
        self._cache_card.findChild(QLabel).setText(f"{cache:.0%}")

        # 更新性能Tab中的详细指标
        mapping = {
            "cpu_percent": "system.cpu_percent",
            "memory_percent": "system.memory_percent",
            "memory_used_mb": "system.memory_used_mb",
            "event_count": "app.event_count",
            "cache_hit_rate": "app.cache_hit_rate",
            "active_plugins": "app.active_plugins",
        }
        for key, metric_name in mapping.items():
            label = self._perf_labels.get(key)
            if label:
                val = metrics.get(metric_name, 0)
                if isinstance(val, float):
                    if metric_name.endswith("rate"):
                        label.setText(f"{val:.1%}")
                    elif metric_name.endswith("mb"):
                        label.setText(f"{val:.0f}")
                    else:
                        label.setText(f"{val:.1f}")
                else:
                    label.setText(str(int(val)))

    def _update_alerts(self, monitor) -> None:
        """更新告警Tab"""
        # 获取最近的告警（通过PerformanceMonitor的history）
        stats = monitor.get_stats() if hasattr(monitor, 'get_stats') else {}
        # 此处可以扩展为从monitor获取真实告警历史
        pass

    def _on_plugin_selected(self, plugin_id: str) -> None:
        """插件被选中"""
        self._log(f"选中插件：{plugin_id}")
        self._selected_plugin_id = plugin_id

    def _activate_selected(self) -> None:
        """激活选中的插件"""
        if not hasattr(self, '_selected_plugin_id'):
            return
        pid = self._selected_plugin_id
        pm = get_plugin_manager()
        if pm:
            success = pm.activate_plugin(pid)
            if success:
                self._log(f"已激活插件：{pid}")
            else:
                self._log(f"激活插件失败：{pid}")

    def _deactivate_selected(self) -> None:
        """停用选中的插件"""
        if not hasattr(self, '_selected_plugin_id'):
            return
        pid = self._selected_plugin_id
        pm = get_plugin_manager()
        if pm:
            success = pm.deactivate_plugin(pid)
            if success:
                self._log(f"已停用插件：{pid}")
            else:
                self._log(f"停用插件失败：{pid}")

    def _reload_selected(self) -> None:
        """重载选中的插件"""
        if not hasattr(self, '_selected_plugin_id'):
            return
        pid = self._selected_plugin_id
        pm = get_plugin_manager()
        if pm:
            success = pm.reload_plugin(pid)
            if success:
                self._log(f"已重载插件：{pid}")
            else:
                self._log(f"重载插件失败：{pid}")

    def _log(self, message: str) -> None:
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        self._log_view.append(f"[{timestamp}] {message}")

    def set_update_interval(self, ms: int) -> None:
        """设置更新间隔（毫秒）"""
        self._update_interval = ms
        self._timer.setInterval(ms)

    def stop_monitoring(self) -> None:
        """停止监控"""
        self._timer.stop()
        self._log("监控已停止")

    def start_monitoring(self) -> None:
        """启动监控"""
        self._timer.start(self._update_interval)
        self._log("监控已恢复")

    def closeEvent(self, event) -> None:
        """关闭事件"""
        self.stop_monitoring()
        super().closeEvent(event)


# ─────────────────────────────────────────────────────────────
# 独立窗口版本
# ─────────────────────────────────────────────────────────────

class KernelMonitorWindow(QWidget):
    """独立窗口版内核监控面板"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("内核监控面板 - LivingTreeAI")
        self.setMinimumSize(900, 600)
        self._panel = KernelMonitorPanel()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._panel)

    def closeEvent(self, event) -> None:
        self._panel.stop_monitoring()
        super().closeEvent(event)


if __name__ == "__main__":
    # 独立运行测试
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = KernelMonitorWindow()
    window.show()
    sys.exit(app.exec())
