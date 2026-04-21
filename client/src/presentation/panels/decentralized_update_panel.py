# decentralized_update_panel.py — P2P 去中心化更新系统 UI 面板

"""
P2P 去中心化更新系统 UI 面板
===========================

提供可视化的 P2P 更新管理界面
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QGridLayout, QFrame, QTextEdit,
    QScrollArea, QSizePolicy, QSpacerItem, QComboBox, QCheckBox
)
from PyQt6.QtGui import QFont, QColor, QPalette

import asyncio
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime

from core.decentralized_update.manager import (
    UpdateManager, UpdateSystemStatus, SystemState,
    get_update_manager, initialize_update_system
)
from core.decentralized_update.models import (
    NodeInfo, VersionInfo, UpdateTask, UpdateStage,
    NodeState, ReputationLevel, format_size, format_speed, format_duration
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 面板样式
# ═══════════════════════════════════════════════════════════════════════════════


PANEL_STYLE = """
/* 整体面板 */
QWidget#UpdatePanel {
    background-color: #1a1a2e;
    color: #e0e0e0;
}

/* 标题样式 */
.-panel-title {
    font-size: 18px;
    font-weight: bold;
    color: #00d4aa;
    padding: 10px;
}

/* 状态卡片 */
.status-card {
    background-color: #16213e;
    border-radius: 8px;
    padding: 15px;
    border: 1px solid #0f3460;
}

.status-card:hover {
    border: 1px solid #00d4aa;
}

/* 标签页 */
QTabWidget::pane {
    border: 1px solid #0f3460;
    background-color: #1a1a2e;
}

QTabBar::tab {
    background-color: #16213e;
    color: #a0a0a0;
    padding: 8px 20px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #0f3460;
    color: #00d4aa;
}

QTabBar::tab:hover {
    background-color: #1a3a5c;
}

/* 按钮 */
QPushButton {
    background-color: #0f3460;
    color: #e0e0e0;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #1a4a7a;
}

QPushButton:pressed {
    background-color: #00d4aa;
    color: #1a1a2e;
}

QPushButton:disabled {
    background-color: #2a2a3e;
    color: #606060;
}

QPushButton#primary {
    background-color: #00d4aa;
    color: #1a1a2e;
}

QPushButton#primary:hover {
    background-color: #00eebb;
}

/* 进度条 */
QProgressBar {
    border: 1px solid #0f3460;
    border-radius: 4px;
    background-color: #16213e;
    text-align: center;
    color: #e0e0e0;
    height: 20px;
}

QProgressBar::chunk {
    background-color: #00d4aa;
    border-radius: 3px;
}

/* 表格 */
QTableWidget {
    background-color: #16213e;
    alternate-background-color: #1a2a4e;
    border: 1px solid #0f3460;
    gridline-color: #0f3460;
    color: #e0e0e0;
}

QTableWidget::item {
    padding: 5px;
}

QTableWidget::item:selected {
    background-color: #0f3460;
}

/* 组框 */
QGroupBox {
    border: 1px solid #0f3460;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
    color: #00d4aa;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

/* 标签 */
QLabel {
    color: #e0e0e0;
}

QLabel#title {
    font-size: 16px;
    font-weight: bold;
    color: #00d4aa;
}

QLabel#subtitle {
    font-size: 13px;
    color: #a0a0a0;
}

QLabel#value {
    font-size: 24px;
    font-weight: bold;
    color: #ffffff;
}

QLabel#small_value {
    font-size: 14px;
    color: #00d4aa;
}

/* 输入框 */
QTextEdit {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 4px;
    color: #e0e0e0;
    padding: 5px;
}

/* 复选框 */
QCheckBox {
    color: #e0e0e0;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #0f3460;
    border-radius: 4px;
    background-color: #16213e;
}

QCheckBox::indicator:checked {
    background-color: #00d4aa;
    border-color: #00d4aa;
}

/* 滚动条 */
QScrollBar:vertical {
    background-color: #1a1a2e;
    width: 12px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #0f3460;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #1a4a7a;
}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# 状态卡片组件
# ═══════════════════════════════════════════════════════════════════════════════


class StatusCard(QFrame):
    """状态卡片"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("status_card")
        self.setMinimumHeight(80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #a0a0a0; font-size: 12px;")

        self.value_label = QLabel("--")
        self.value_label.setObjectName("value")
        self.value_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

        self.setStyleSheet(PANEL_STYLE)

    def set_value(self, value: str):
        self.value_label.setText(value)


# ═══════════════════════════════════════════════════════════════════════════════
# 网络拓扑图
# ═══════════════════════════════════════════════════════════════════════════════


class NetworkTopologyWidget(QWidget):
    """网络拓扑图（简化显示）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🌐 P2P 网络拓扑")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #00d4aa;")

        # 节点列表
        self.node_list = QTextEdit()
        self.node_list.setReadOnly(True)
        self.node_list.setMaximumHeight(150)
        self.node_list.setPlaceholderText("连接的节点将显示在这里...")

        layout.addWidget(title)
        layout.addWidget(self.node_list)

        self.setStyleSheet(PANEL_STYLE)

    def update_nodes(self, nodes: List[NodeInfo]):
        """更新节点列表"""
        if not nodes:
            self.node_list.setPlainText("暂无连接的节点")
            return

        text = ""
        for node in nodes[:10]:  # 最多显示10个
            status_icon = "🟢" if node.state == NodeState.ONLINE else "🔴"
            seed_icon = "⭐" if node.is_seed else ""
            text += f"{status_icon} {node.node_id[:12]}... {seed_icon} | "
            text += f"版本: {node.version} | "
            text += f"信誉: {node.reputation_score:.0f}\n"

        if len(nodes) > 10:
            text += f"\n... 还有 {len(nodes) - 10} 个节点"

        self.node_list.setPlainText(text)


# ═══════════════════════════════════════════════════════════════════════════════
# 主面板
# ═══════════════════════════════════════════════════════════════════════════════


class DecentralizedUpdatePanel(QWidget):
    """
    P2P 去中心化更新系统面板

    功能：
    1. 系统状态概览
    2. 版本检查与下载
    3. P2P 网络管理
    4. 信誉排行
    5. 分发统计
    """

    # 信号
    status_updated = pyqtSignal(dict)
    update_available = pyqtSignal(str)  # version

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UpdatePanel")

        self.update_manager: Optional[UpdateManager] = None
        self._refresh_timer: Optional[QTimer] = None

        self._init_ui()
        self._init_manager()

    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        # ═══════════════════════════════════════════════════════════════════════
        # 标题栏
        # ═══════════════════════════════════════════════════════════════════════

        title_layout = QHBoxLayout()

        title = QLabel("🌐 P2P 去中心化更新系统")
        title.setObjectName("title")

        self.status_indicator = QLabel("● 初始化中")
        self.status_indicator.setStyleSheet("color: #ffaa00; font-size: 12px;")

        title_layout.addWidget(title)
        title_layout.addStretch()
        title_layout.addWidget(self.status_indicator)

        main_layout.addLayout(title_layout)

        # ═══════════════════════════════════════════════════════════════════
        # 状态卡片区
        # ═══════════════════════════════════════════════════════════════════

        cards_layout = QHBoxLayout()

        self.current_version_card = StatusCard("当前版本")
        self.current_version_card.set_value("v1.0.0")

        self.latest_version_card = StatusCard("最新版本")
        self.latest_version_card.set_value("--")

        self.network_card = StatusCard("网络节点")
        self.network_card.set_value("0")

        self.peer_card = StatusCard("活跃连接")
        self.peer_card.set_value("0")

        self.download_speed_card = StatusCard("下载速度")
        self.download_speed_card.set_value("--")

        cards_layout.addWidget(self.current_version_card)
        cards_layout.addWidget(self.latest_version_card)
        cards_layout.addWidget(self.network_card)
        cards_layout.addWidget(self.peer_card)
        cards_layout.addWidget(self.download_speed_card)

        main_layout.addLayout(cards_layout)

        # ═══════════════════════════════════════════════════════════════════
        # 进度区域
        # ═══════════════════════════════════════════════════════════════════

        progress_group = QGroupBox("📥 更新进度")

        progress_layout = QGridLayout()

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")

        # 进度标签
        self.progress_label = QLabel("准备就绪")

        # 按钮
        self.check_btn = QPushButton("🔍 检查更新")
        self.check_btn.clicked.connect(self._on_check_updates)

        self.download_btn = QPushButton("⬇️ 下载更新")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._on_download)
        self.download_btn.setObjectName("primary")

        self.pause_btn = QPushButton("⏸️ 暂停")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._on_pause)

        self.apply_btn = QPushButton("✅ 应用更新")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._on_apply)

        progress_layout.addWidget(self.progress_label, 0, 0, 1, 4)
        progress_layout.addWidget(self.progress_bar, 1, 0, 1, 4)
        progress_layout.addWidget(self.check_btn, 2, 0)
        progress_layout.addWidget(self.download_btn, 2, 1)
        progress_layout.addWidget(self.pause_btn, 2, 2)
        progress_layout.addWidget(self.apply_btn, 2, 3)

        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)

        # ═══════════════════════════════════════════════════════════════════
        # 标签页
        # ═══════════════════════════════════════════════════════════════════

        tabs = QTabWidget()

        # 网络拓扑页
        network_tab = QWidget()
        network_layout = QVBoxLayout(network_tab)
        self.network_widget = NetworkTopologyWidget()
        network_layout.addWidget(self.network_widget)
        network_layout.addStretch()
        tabs.addTab(network_tab, "🌐 网络拓扑")

        # 信誉排行页
        reputation_tab = QWidget()
        reputation_layout = QVBoxLayout(reputation_tab)
        self.reputation_table = self._create_reputation_table()
        reputation_layout.addWidget(self.reputation_table)
        tabs.addTab(reputation_tab, "⭐ 信誉排行")

        # 分发统计页
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setPlaceholderText("统计数据将显示在这里...")
        stats_layout.addWidget(self.stats_text)
        tabs.addTab(stats_tab, "📊 分发统计")

        # 日志页
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("系统日志...")
        log_layout.addWidget(self.log_text)
        tabs.addTab(log_tab, "📝 日志")

        main_layout.addWidget(tabs, 1)

        # ═══════════════════════════════════════════════════════════════════
        # 底部设置
        # ═══════════════════════════════════════════════════════════════════

        settings_layout = QHBoxLayout()

        settings_layout.addWidget(QLabel("更新策略:"))

        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["自动更新", "手动更新", "定时更新", "仅通知"])
        self.strategy_combo.setCurrentText("仅通知")
        settings_layout.addWidget(self.strategy_combo)

        settings_layout.addStretch()

        self.auto_checkbox = QCheckBox("自动检查更新")
        self.auto_checkbox.setChecked(True)
        settings_layout.addWidget(self.auto_checkbox)

        main_layout.addLayout(settings_layout)

        self.setStyleSheet(PANEL_STYLE)

    def _create_reputation_table(self) -> QTableWidget:
        """创建信誉表"""
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["节点ID", "版本", "信誉分", "等级", "分发成功"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        return table

    def _init_manager(self):
        """初始化更新管理器"""
        try:
            self.update_manager = get_update_manager()

            # 设置回调
            self.update_manager.on_status_change = self._on_status_change
            self.update_manager.on_update_available = self._on_update_available
            self.update_manager.on_download_progress = self._on_download_progress

            # 更新UI
            self.current_version_card.set_value(f"v{self.update_manager.config.current_version}")
            self.status_indicator.setText("● 就绪")
            self.status_indicator.setStyleSheet("color: #00d4aa; font-size: 12px;")

            self._log("更新系统已初始化")

        except Exception as e:
            self._log(f"初始化失败: {e}")
            logger.error(f"Update manager init failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 事件处理
    # ═══════════════════════════════════════════════════════════════════════════

    async def _on_check_updates(self):
        """检查更新"""
        self._log("正在检查更新...")
        self.check_btn.setEnabled(False)

        try:
            latest = await self.update_manager.check_for_updates()

            if latest:
                self.latest_version_card.set_value(f"v{latest.version}")
                self.download_btn.setEnabled(True)
                self._log(f"发现新版本: v{latest.version} ({format_size(latest.full_size)})")
            else:
                self.latest_version_card.set_value("已是最新")
                self._log("当前已是最新版本")

        except Exception as e:
            self._log(f"检查更新失败: {e}")

        finally:
            self.check_btn.setEnabled(True)

    async def _on_download(self):
        """开始下载"""
        version = self.update_manager.status.latest_version
        if not version:
            return

        self._log("开始下载更新...")
        self.download_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)

        try:
            version_info = self.update_manager.version_cache.get(version)
            if version_info:
                task = await self.update_manager.download_update(version_info)

                if task:
                    self._log(f"下载任务已创建: {task.task_id}")
                else:
                    self._log("下载任务创建失败")

        except Exception as e:
            self._log(f"下载失败: {e}")
            self.download_btn.setEnabled(True)

    def _on_pause(self):
        """暂停下载"""
        task = self.update_manager.status.active_task
        if task:
            asyncio.create_task(self.update_manager.pause_update(task.task_id))
            self._log("已暂停下载")
            self.pause_btn.setText("▶️ 继续")
            self.pause_btn.clicked.disconnect()
            self.pause_btn.clicked.connect(self._on_resume)

    def _on_resume(self):
        """继续下载"""
        task = self.update_manager.status.active_task
        if task:
            asyncio.create_task(self.update_manager.resume_update(task.task_id))
            self._log("继续下载")
            self.pause_btn.setText("⏸️ 暂停")
            self.pause_btn.clicked.disconnect()
            self.pause_btn.clicked.connect(self._on_pause)

    async def _on_apply(self):
        """应用更新"""
        task = self.update_manager.status.active_task
        if not task:
            return

        self._log("正在应用更新...")
        self.apply_btn.setEnabled(False)

        try:
            success = await self.update_manager.apply_update(task.task_id)

            if success:
                self._log("更新应用成功！")
                self.current_version_card.set_value(f"v{task.to_version}")
                self.progress_bar.setValue(100)
                self.progress_label.setText("更新完成")
            else:
                self._log("更新应用失败")

        except Exception as e:
            self._log(f"应用更新失败: {e}")

    async def _on_status_change(self, state: SystemState):
        """状态变化回调"""
        state_names = {
            SystemState.IDLE: "● 就绪",
            SystemState.CHECKING: "◐ 检查中",
            SystemState.DOWNLOADING: "▼ 下载中",
            SystemState.VERIFYING: "◑ 验证中",
            SystemState.APPLYING: "◕ 应用中",
            SystemState.ERROR: "✕ 错误"
        }

        colors = {
            SystemState.IDLE: "#00d4aa",
            SystemState.CHECKING: "#ffaa00",
            SystemState.DOWNLOADING: "#00aaff",
            SystemState.VERIFYING: "#ffaa00",
            SystemState.APPLYING: "#00aaff",
            SystemState.ERROR: "#ff4444"
        }

        self.status_indicator.setText(state_names.get(state, "● 就绪"))
        self.status_indicator.setStyleSheet(f"color: {colors.get(state, '#00d4aa')}; font-size: 12px;")

    async def _on_update_available(self, version: VersionInfo):
        """发现新版本回调"""
        self.update_available.emit(version.version)
        self._log(f"发现新版本: v{version.version}")

    async def _on_download_progress(self, task: UpdateTask):
        """下载进度回调"""
        progress = int(task.progress * 100)
        self.progress_bar.setValue(progress)

        remaining = format_duration(task.remaining_time) if task.remaining_time > 0 else "计算中"
        self.progress_label.setText(
            f"下载进度: {progress}% | "
            f"速度: {format_speed(task.speed_bps)} | "
            f"剩余时间: {remaining}"
        )

        if task.stage == UpdateStage.COMPLETED:
            self.apply_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self._log("下载完成！可以应用更新了。")

    # ═══════════════════════════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════════════════════════

    def _log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        logger.info(message)

    def _update_reputation_table(self, nodes: List[NodeInfo]):
        """更新信誉表"""
        self.reputation_table.setRowCount(0)

        sorted_nodes = sorted(nodes, key=lambda n: n.reputation_score, reverse=True)

        for i, node in enumerate(sorted_nodes[:20]):  # 最多20行
            self.reputation_table.insertRow(i)
            self.reputation_table.setItem(i, 0, QTableWidgetItem(node.node_id[:16] + "..."))
            self.reputation_table.setItem(i, 1, QTableWidgetItem(node.version))
            self.reputation_table.setItem(i, 2, QTableWidgetItem(f"{node.reputation_score:.1f}"))
            self.reputation_table.setItem(i, 3, QTableWidgetItem(node.reputation_level.name))
            self.reputation_table.setItem(i, 4, QTableWidgetItem(str(node.successful_distributes)))

    def _update_stats(self):
        """更新统计信息"""
        if not self.update_manager:
            return

        stats = self.update_manager.get_stats()

        stats_text = f"""
=== P2P 更新系统统计 ===

📊 状态
   系统状态: {stats.get('state', 'N/A')}
   活跃任务: {stats.get('active_tasks', 0)}

🌐 网络
   连接的peers: {stats.get('connected_peers', 0)}
   活跃连接: {stats.get('active_tasks', 0)}

📥 下载
   进度: {stats.get('download_progress', 0) * 100:.1f}%
   速度: {stats.get('download_speed', 'N/A')}
   剩余时间: {stats.get('remaining_time', 'N/A')}

⭐ 信誉
   我的信誉: {stats.get('reputation', 'N/A')}
"""

        self.stats_text.setPlainText(stats_text)

    # ═══════════════════════════════════════════════════════════════════════════
    # 生命周期
    # ═══════════════════════════════════════════════════════════════════════════

    def showEvent(self, event):
        """显示面板"""
        super().showEvent(event)

        # 启动刷新定时器
        if not self._refresh_timer:
            self._refresh_timer = QTimer()
            self._refresh_timer.timeout.connect(self._refresh)
            self._refresh_timer.start(2000)  # 每2秒刷新

    def hideEvent(self, event):
        """隐藏面板"""
        super().hideEvent(event)

        if self._refresh_timer:
            self._refresh_timer.stop()

    def _refresh(self):
        """刷新UI"""
        if not self.update_manager:
            return

        try:
            # 更新节点数
            if self.update_manager.dht_node:
                nodes = self.update_manager.dht_node.get_closest_nodes(
                    self.update_manager.dht_node.node_id
                )
                self.network_card.set_value(str(len(nodes)))
                self.network_widget.update_nodes(nodes)
                self._update_reputation_table(nodes)

            # 更新活跃连接
            if self.update_manager.distribution:
                self.peer_card.set_value(str(self.update_manager.distribution.connection_manager.connection_count))

            # 更新统计
            self._update_stats()

        except Exception as e:
            logger.error(f"Refresh error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 面板创建函数
# ═══════════════════════════════════════════════════════════════════════════════


def create_decentralized_update_panel() -> DecentralizedUpdatePanel:
    """创建面板"""
    return DecentralizedUpdatePanel()
