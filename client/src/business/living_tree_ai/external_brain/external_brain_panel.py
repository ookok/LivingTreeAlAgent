"""
ExternalBrainPanel - 外脑调用系统 PyQt6 UI面板
=============================================

功能：
1. 网络诊断面板 - 显示各服务可达性
2. 通道状态面板 - 显示四层通道状态
3. 代理配置面板 - 用户手动配置代理
4. 离线队列面板 - 显示和管理离线任务

Author: LivingTreeAI Community
from __future__ import annotations
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QTextEdit, QGroupBox, QLineEdit,
    QCheckBox, QSpinBox, QComboBox, QProgressBar,
    QBadge, QFrame, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QPalette

from ..channel_manager import (
    ChannelManager, ChannelType, ChannelStatus, ChannelResult,
    UserProxyConfig, APIKeyConfig, LocalLLMConfig,
    get_channel_manager,
)
from ..network_diagnosis import (
    NetworkDiagnoser, DiagnosisReport, ServiceStatus,
    get_network_diagnoser,
)
from ..offline_queue import (
    OfflineQueue, OfflineTask, TaskStatus,
    get_offline_queue,
)


class NetworkStatusWidget(QWidget):
    """网络状态指示器"""

    status_changed = pyqtSignal(str, str)  # service_name, status

    def __init__(self, diagnoser: NetworkDiagnoser, parent=None):
        super().__init__(parent)
        self._diagnoser = diagnoser
        self._init_ui()
        self._setup_timer()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题
        title = QLabel("🌐 网络状态")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        layout.addWidget(title)

        # 状态显示
        self._status_label = QLabel("检测中...")
        self._status_label.setStyleSheet("color: #888; padding: 5px;")
        layout.addWidget(self._status_label)

        # 详细结果
        self._result_widget = QTextEdit()
        self._result_widget.setReadOnly(True)
        self._result_widget.setMaximumHeight(200)
        self._result_widget.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 4px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self._result_widget)

        # 刷新按钮
        btn_layout = QHBoxLayout()
        self._refresh_btn = QPushButton("🔄 刷新诊断")
        self._refresh_btn.clicked.connect(self._on_refresh)
        btn_layout.addWidget(self._refresh_btn)

        self._auto_refresh_cb = QCheckBox("自动刷新")
        self._auto_refresh_cb.setChecked(True)
        btn_layout.addWidget(self._auto_refresh_cb)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

    def _setup_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._auto_refresh)
        self._timer.start(60000)  # 每分钟自动刷新

    def _on_refresh(self):
        """手动刷新诊断"""
        self._status_label.setText("🔄 诊断中...")
        self._refresh_btn.setEnabled(False)

        # 异步执行诊断
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        report = loop.run_until_complete(self._diagnoser.diagnose())
        loop.close()

        self._update_display(report)
        self._refresh_btn.setEnabled(True)
        self._status_label.setText(f"✅ 诊断完成 ({report.timestamp.strftime('%H:%M:%S')})")

    def _auto_refresh(self):
        """自动刷新"""
        if self._auto_refresh_cb.isChecked():
            self._on_refresh()

    def _update_display(self, report: DiagnosisReport):
        """更新显示"""
        self._result_widget.setPlainText(report.to_display_string())


class ChannelStatusWidget(QWidget):
    """通道状态面板"""

    def __init__(self, channel_manager: ChannelManager, parent=None):
        super().__init__(parent)
        self._manager = channel_manager
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("📡 外脑通道状态")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        layout.addWidget(title)

        # 通道表格
        self._table = QTableWidget(5, 4)
        self._table.setHorizontalHeaderLabels(["通道", "状态", "延迟", "错误次数"])
        self._table.setMaximumHeight(180)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        channels = [
            (ChannelType.DIRECT, "0️⃣ 本地直连"),
            (ChannelType.USER_PROXY, "1️⃣ 用户代理"),
            (ChannelType.API_FALLBACK, "2️⃣ 官方API"),
            (ChannelType.LOCAL_LLM, "3️⃣ 本地LLM"),
            (ChannelType.OFFLINE_QUEUE, "4️⃣ 离线队列"),
        ]

        for i, (ch_type, name) in enumerate(channels):
            self._table.setItem(i, 0, QTableWidgetItem(name))
            self._table.setItem(i, 1, QTableWidgetItem("未知"))
            self._table.setItem(i, 2, QTableWidgetItem("-"))
            self._table.setItem(i, 3, QTableWidgetItem("0"))

        self._table.setColumnWidth(0, 120)
        self._table.setColumnWidth(1, 80)
        self._table.setColumnWidth(2, 80)
        layout.addWidget(self._table)

        # 刷新按钮
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 刷新状态")
        refresh_btn.clicked.connect(self._refresh)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._refresh()

    def _refresh(self):
        """刷新通道状态"""
        stats = self._manager.get_channel_stats()

        channel_map = [
            (ChannelType.DIRECT, 0),
            (ChannelType.USER_PROXY, 1),
            (ChannelType.API_FALLBACK, 2),
            (ChannelType.LOCAL_LLM, 3),
            (ChannelType.OFFLINE_QUEUE, 4),
        ]

        for ch_type, row in channel_map:
            stat = stats.get(ch_type.value, {})
            status = stat.get("status", "unknown")
            latency = stat.get("latency_ms", 0)
            errors = stat.get("error_count", 0)

            status_item = self._table.item(row, 1)
            status_item.setText(self._get_status_text(status))
            status_item.setForeground(self._get_status_color(status))

            latency_item = self._table.item(row, 2)
            latency_item.setText(f"{latency:.0f}ms" if latency > 0 else "-")

            error_item = self._table.item(row, 3)
            error_item.setText(str(errors))

    def _get_status_text(self, status: str) -> str:
        status_map = {
            "available": "✅ 可用",
            "unavailable": "❌ 不可用",
            "skipped": "⏭️ 跳过",
            "error": "⚠️ 错误",
            "timeout": "⏱️ 超时",
        }
        return status_map.get(status, status)

    def _get_status_color(self, status: str) -> QColor:
        color_map = {
            "available": QColor("#4ec9b0"),
            "unavailable": QColor("#f14c4c"),
            "skipped": QColor("#888888"),
            "error": QColor("#ce9178"),
            "timeout": QColor("#dcdcaa"),
        }
        return color_map.get(status, QColor("#d4d4d4"))


class ProxyConfigWidget(QWidget):
    """代理配置面板"""

    config_changed = pyqtSignal()

    def __init__(self, channel_manager: ChannelManager, parent=None):
        super().__init__(parent)
        self._manager = channel_manager
        self._init_ui()
        self._load_config()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 说明
        note = QLabel("⚠️ 此功能需自行准备代理服务，本软件不提供任何代理节点")
        note.setStyleSheet("color: #ce9178; font-size: 12px; padding: 5px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        # 启用复选框
        self._enable_cb = QCheckBox("启用手动代理")
        self._enable_cb.stateChanged.connect(self._on_enable_changed)
        layout.addWidget(self._enable_cb)

        # 代理配置组
        config_group = QGroupBox("代理设置")
        config_layout = QGridLayout()

        # 代理类型
        config_layout.addWidget(QLabel("代理类型:"), 0, 0)
        self._type_combo = QComboBox()
        self._type_combo.addItems(["http", "socks5"])
        config_layout.addWidget(self._type_combo, 0, 1)

        # 代理地址
        config_layout.addWidget(QLabel("代理地址:"), 1, 0)
        self._host_edit = QLineEdit()
        self._host_edit.setPlaceholderText("例如: 192.168.1.100")
        config_layout.addWidget(self._host_edit, 1, 1)

        # 代理端口
        config_layout.addWidget(QLabel("端口:"), 2, 0)
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setPlaceholderText("例如: 7890")
        config_layout.addWidget(self._port_spin, 2, 1)

        # 用户名（可选）
        config_layout.addWidget(QLabel("用户名(可选):"), 3, 0)
        self._user_edit = QLineEdit()
        self._user_edit.setPlaceholderText("可选")
        config_layout.addWidget(self._user_edit, 3, 1)

        # 密码（可选）
        config_layout.addWidget(QLabel("密码(可选):"), 4, 0)
        self._pass_edit = QLineEdit()
        self._pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_edit.setPlaceholderText("可选")
        config_layout.addWidget(self._pass_edit, 4, 1)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("💾 保存配置")
        save_btn.clicked.connect(self._save_config)
        btn_layout.addWidget(save_btn)

        test_btn = QPushButton("🧪 测试连通性")
        test_btn.clicked.connect(self._test_connection)
        btn_layout.addWidget(test_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 状态标签
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("padding: 5px;")
        layout.addWidget(self._status_label)

        layout.addStretch()

        self._set_enabled(False)

    def _load_config(self):
        """加载配置"""
        proxy = self._manager.get_user_proxy()
        self._enable_cb.setChecked(proxy.enabled)
        self._type_combo.setCurrentText(proxy.proxy_type)
        self._host_edit.setText(proxy.proxy_host)
        self._port_spin.setValue(proxy.proxy_port or 8080)
        self._user_edit.setText(proxy.proxy_user)
        self._pass_edit.setText(proxy.proxy_pass)
        self._set_enabled(proxy.enabled)

    def _save_config(self):
        """保存配置"""
        config = UserProxyConfig(
            enabled=self._enable_cb.isChecked(),
            proxy_type=self._type_combo.currentText(),
            proxy_host=self._host_edit.text().strip(),
            proxy_port=self._port_spin.value(),
            proxy_user=self._user_edit.text().strip(),
            proxy_pass=self._pass_edit.text(),
        )

        self._manager.set_user_proxy(config)
        self._status_label.setText("✅ 配置已保存")
        self._status_label.setStyleSheet("color: #4ec9b0; padding: 5px;")
        self.config_changed.emit()

    def _test_connection(self):
        """测试连通性"""
        self._status_label.setText("🔄 测试中...")
        self._status_label.setStyleSheet("color: #dcdcaa; padding: 5px;")

        # 简化实现：使用网络诊断器测试
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def do_test():
            diagnoser = get_network_diagnoser()
            # 测试通用可达性
            report = await diagnoser.diagnose()
            return report

        report = loop.run_until_complete(do_test())
        loop.close()

        available = report.get_available_services()
        if available:
            self._status_label.setText(f"✅ 网络正常 (可用服务: {len(available)})")
            self._status_label.setStyleSheet("color: #4ec9b0; padding: 5px;")
        else:
            self._status_label.setText("❌ 网络受限，请检查代理配置")
            self._status_label.setStyleSheet("color: #f14c4c; padding: 5px;")

    def _on_enable_changed(self, state):
        """启用状态改变"""
        self._set_enabled(state == Qt.CheckState.Checked.value)

    def _set_enabled(self, enabled: bool):
        """设置控件启用状态"""
        self._type_combo.setEnabled(enabled)
        self._host_edit.setEnabled(enabled)
        self._port_spin.setEnabled(enabled)
        self._user_edit.setEnabled(enabled)
        self._pass_edit.setEnabled(enabled)


class OfflineQueueWidget(QWidget):
    """离线队列面板"""

    def __init__(self, offline_queue: OfflineQueue, parent=None):
        super().__init__(parent)
        self._queue = offline_queue
        self._init_ui()
        self._setup_timer()
        self._load_tasks()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题和计数
        header_layout = QHBoxLayout()
        title = QLabel("📋 离线任务队列")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        header_layout.addWidget(title)

        self._count_label = QLabel("(0 个任务)")
        self._count_label.setStyleSheet("color: #888;")
        header_layout.addWidget(self._count_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # 任务表格
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["任务ID", "名称", "状态", "重试", "创建时间"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setMaximumHeight(250)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setColumnWidth(0, 80)
        self._table.setColumnWidth(1, 150)
        self._table.setColumnWidth(2, 80)
        self._table.setColumnWidth(3, 50)
        self._table.setColumnWidth(4, 120)
        layout.addWidget(self._table)

        # 按钮
        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._load_tasks)
        btn_layout.addWidget(refresh_btn)

        retry_btn = QPushButton("🔁 重试选中")
        retry_btn.clicked.connect(self._retry_selected)
        btn_layout.addWidget(retry_btn)

        delete_btn = QPushButton("🗑️ 删除选中")
        delete_btn.clicked.connect(self._delete_selected)
        btn_layout.addWidget(delete_btn)

        clear_completed_btn = QPushButton("✨ 清除已完成")
        clear_completed_btn.clicked.connect(self._clear_completed)
        btn_layout.addWidget(clear_completed_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _setup_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._load_tasks)
        self._timer.start(30000)  # 每30秒刷新

    def _load_tasks(self):
        """加载任务列表"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def do_load():
            return await self._queue.get_all_tasks()

        tasks = loop.run_until_complete(do_load())
        loop.close()

        self._table.setRowCount(len(tasks))

        for i, task in enumerate(tasks):
            self._table.setItem(i, 0, QTableWidgetItem(task.task_id[:8]))
            self._table.setItem(i, 1, QTableWidgetItem(task.task_name))
            self._table.setItem(i, 2, QTableWidgetItem(self._get_status_text(task.status)))
            self._table.setItem(i, 3, QTableWidgetItem(f"{task.retry_count}/{task.max_retries}"))
            self._table.setItem(i, 4, QTableWidgetItem(task.created_at.strftime("%H:%M:%S")))

        self._count_label.setText(f"({len(tasks)} 个任务)")

    def _get_status_text(self, status: TaskStatus) -> str:
        status_map = {
            TaskStatus.PENDING: "⏳ 待处理",
            TaskStatus.QUEUED: "📋 已入队",
            TaskStatus.RETRYING: "🔁 重试中",
            TaskStatus.COMPLETED: "✅ 完成",
            TaskStatus.FAILED: "❌ 失败",
            TaskStatus.CANCELLED: "🚫 取消",
        }
        return status_map.get(status, str(status.value))

    def _retry_selected(self):
        """重试选中的任务"""
        selected = self._table.currentRow()
        if selected < 0:
            return

        task_id_item = self._table.item(selected, 0)
        if not task_id_item:
            return

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def do_retry():
            return await self._queue.retry_task(task_id_item.text())

        success = loop.run_until_complete(do_retry())
        loop.close()

        if success:
            self._load_tasks()

    def _delete_selected(self):
        """删除选中的任务"""
        selected = self._table.currentRow()
        if selected < 0:
            return

        task_id_item = self._table.item(selected, 0)
        if not task_id_item:
            return

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def do_delete():
            await self._queue.delete_task(task_id_item.text())

        loop.run_until_complete(do_delete())
        loop.close()

        self._load_tasks()

    def _clear_completed(self):
        """清除已完成的任务"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def do_clear():
            await self._queue.clear_completed()

        loop.run_until_complete(do_clear())
        loop.close()

        self._load_tasks()


class ExternalBrainPanel(QWidget):
    """
    外脑调用系统综合面板

    整合网络诊断、通道状态、代理配置、离线队列四个模块
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 获取单例
        self._channel_manager = get_channel_manager()
        self._diagnoser = get_network_diagnoser()
        self._offline_queue = get_offline_queue()

        # 关联组件
        self._channel_manager.set_diagnoser(self._diagnoser)
        self._channel_manager.set_offline_queue(self._offline_queue)

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🌿 外脑调用系统 - 多通道回退")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        title.setStyleSheet("padding: 10px; background: #2d2d30; border-radius: 4px;")
        layout.addWidget(title)

        # 创建标签页
        tabs = QTabWidget()

        # 网络诊断页
        tabs.addTab(NetworkStatusWidget(self._diagnoser), "🌐 网络诊断")

        # 通道状态页
        tabs.addTab(ChannelStatusWidget(self._channel_manager), "📡 通道状态")

        # 代理配置页
        tabs.addTab(ProxyConfigWidget(self._channel_manager), "⚙️ 代理配置")

        # 离线队列页
        tabs.addTab(OfflineQueueWidget(self._offline_queue), "📋 离线队列")

        layout.addWidget(tabs)

        # 底部信息
        footer = QLabel(
            "🛡️ 安全合规: 绝不内置代理 · 用户知情授权 · 数据本地处理"
        )
        footer.setStyleSheet("""
            color: #608b4e;
            font-size: 11px;
            padding: 8px;
            border-top: 1px solid #333;
            margin-top: 5px;
        """)
        layout.addWidget(footer)


# ==================== 集成到主窗口 ====================

def create_external_brain_panel() -> QWidget:
    """创建外脑调用系统面板"""
    return ExternalBrainPanel()