"""
根系同步 (Root Sync) - PyQt6 UI面板
借鉴 Syncthing 去中心化文件同步架构

标签页: 设备管理 | 文件夹同步 | 同步历史 | 版本管理 | 设置
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QScrollArea, QComboBox, QGroupBox, QCheckBox,
    QLineEdit, QFileDialog, QMessageBox, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QSplitter, QStatusBar,
    QDialog, QFormLayout, QDialogButtonBox, QSpinBox,
    QDoubleSpinBox, QTextEdit, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QAction

from core.models import SystemConfig

logger = logging.getLogger(__name__)


# ─── 样式常量 ────────────────────────────────────────
STYLE_HEADER = """
    QLabel {
        font-size: 16px; font-weight: bold; color: #2E7D32;
    }
"""

STYLE_CARD = """
    QFrame {
        background: #ffffff; border: 1px solid #e0e0e0;
        border-radius: 8px; padding: 12px;
    }
"""

STYLE_BTN_PRIMARY = """
    QPushButton {
        background-color: #4CAF50; color: white;
        border: none; padding: 8px 16px; border-radius: 4px;
        font-weight: bold;
    }
    QPushButton:hover { background-color: #45a049; }
    QPushButton:disabled { background-color: #a5d6a7; }
"""

STYLE_BTN_DANGER = """
    QPushButton {
        background-color: #f44336; color: white;
        border: none; padding: 8px 16px; border-radius: 4px;
    }
    QPushButton:hover { background-color: #d32f2f; }
"""

STYLE_BTN_SECONDARY = """
    QPushButton {
        background-color: #e0e0e0; color: #333;
        border: none; padding: 8px 16px; border-radius: 4px;
    }
    QPushButton:hover { background-color: #bdbdbd; }
"""

STYLE_TABLE = """
    QTableWidget {
        border: 1px solid #e0e0e0; border-radius: 4px;
        gridline-color: #f5f5f5;
    }
    QTableWidget::item { padding: 6px; }
    QHeaderView::section {
        background: #f5f5f5; padding: 6px;
        border: none; font-weight: bold;
    }
"""

STYLE_STATUS_ONLINE = "color: #4CAF50; font-weight: bold;"
STYLE_STATUS_OFFLINE = "color: #9e9e9e;"
STYLE_STATUS_SYNCING = "color: #FF9800; font-weight: bold;"


class RootSyncPanel(QWidget):
    """根系同步面板 - 去中心化文件同步"""

    # 信号
    sync_started = pyqtSignal(str)       # folder_id
    sync_completed = pyqtSignal(str)     # folder_id
    device_connected = pyqtSignal(str)   # device_id
    device_disconnected = pyqtSignal(str)  # device_id

    def __init__(self, config: SystemConfig = None, parent=None):
        super().__init__(parent)
        self.config = config or SystemConfig()
        self.sync_system = None

        self._init_ui()
        self._init_timers()

    # ─── UI 初始化 ──────────────────────────────────

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # 顶部栏
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #e0e0e0; border-radius: 4px; }
            QTabBar::tab { padding: 8px 20px; min-width: 80px; }
            QTabBar::tab:selected { color: #2E7D32; font-weight: bold; }
        """)

        self.tabs.addTab(self._create_devices_tab(), "🌳 设备管理")
        self.tabs.addTab(self._create_folders_tab(), "📁 文件夹同步")
        self.tabs.addTab(self._create_history_tab(), "📜 同步历史")
        self.tabs.addTab(self._create_versions_tab(), "🔄 版本管理")
        self.tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        main_layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("根系同步系统未启动")
        main_layout.addWidget(self.status_bar)

    def _create_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #f5f5f5; padding: 6px; border-radius: 4px;")
        layout = QHBoxLayout(toolbar)

        self.start_btn = QPushButton("🌳 启动根系同步")
        self.start_btn.setStyleSheet(STYLE_BTN_PRIMARY)
        self.start_btn.clicked.connect(self._toggle_system)

        self.scan_btn = QPushButton("🔍 扫描设备")
        self.scan_btn.setStyleSheet(STYLE_BTN_SECONDARY)
        self.scan_btn.clicked.connect(self._scan_devices)
        self.scan_btn.setEnabled(False)

        self.sync_all_btn = QPushButton("⬆⬇ 全量同步")
        self.sync_all_btn.setStyleSheet(STYLE_BTN_PRIMARY)
        self.sync_all_btn.clicked.connect(self._sync_all)
        self.sync_all_btn.setEnabled(False)

        self.online_label = QLabel("在线设备: 0")
        self.online_label.setStyleSheet("font-weight: bold; color: #2E7D32;")

        layout.addWidget(self.start_btn)
        layout.addWidget(self.scan_btn)
        layout.addWidget(self.sync_all_btn)
        layout.addStretch()
        layout.addWidget(self.online_label)

        return toolbar

    # ─── 设备管理标签 ──────────────────────────────────

    def _create_devices_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 已知设备表
        devices_group = QGroupBox("已连接设备")
        devices_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        devices_layout = QVBoxLayout(devices_group)

        self.devices_table = QTableWidget()
        self.devices_table.setStyleSheet(STYLE_TABLE)
        self.devices_table.setColumnCount(7)
        self.devices_table.setHorizontalHeaderLabels([
            "设备ID", "设备名称", "状态", "地址", "最后在线", "同步文件夹数", "操作"
        ])
        self.devices_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.devices_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.devices_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        devices_layout.addWidget(self.devices_table)

        # 按钮行
        btn_layout = QHBoxLayout()
        add_device_btn = QPushButton("➕ 添加设备")
        add_device_btn.setStyleSheet(STYLE_BTN_PRIMARY)
        add_device_btn.clicked.connect(self._add_device)

        remove_device_btn = QPushButton("🗑️ 移除设备")
        remove_device_btn.setStyleSheet(STYLE_BTN_DANGER)
        remove_device_btn.clicked.connect(self._remove_device)

        btn_layout.addWidget(add_device_btn)
        btn_layout.addWidget(remove_device_btn)
        btn_layout.addStretch()
        devices_layout.addLayout(btn_layout)

        layout.addWidget(devices_group)

        # 发现设备
        discovery_group = QGroupBox("局域网发现")
        discovery_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        discovery_layout = QVBoxLayout(discovery_group)

        self.discovery_table = QTableWidget()
        self.discovery_table.setStyleSheet(STYLE_TABLE)
        self.discovery_table.setColumnCount(5)
        self.discovery_table.setHorizontalHeaderLabels([
            "设备ID", "设备名称", "地址", "端口", "操作"
        ])
        self.discovery_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.discovery_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        discovery_layout.addWidget(self.discovery_table)

        layout.addWidget(discovery_group)

        return widget

    # ─── 文件夹同步标签 ──────────────────────────────────

    def _create_folders_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 同步文件夹列表
        folders_group = QGroupBox("同步文件夹")
        folders_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        folders_layout = QVBoxLayout(folders_group)

        self.folders_table = QTableWidget()
        self.folders_table.setStyleSheet(STYLE_TABLE)
        self.folders_table.setColumnCount(7)
        self.folders_table.setHorizontalHeaderLabels([
            "文件夹ID", "路径", "状态", "共享设备数", "本地文件数", "同步进度", "操作"
        ])
        self.folders_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.folders_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.folders_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        folders_layout.addWidget(self.folders_table)

        # 按钮行
        btn_layout = QHBoxLayout()
        add_folder_btn = QPushButton("➕ 添加文件夹")
        add_folder_btn.setStyleSheet(STYLE_BTN_PRIMARY)
        add_folder_btn.clicked.connect(self._add_folder)

        sync_folder_btn = QPushButton("🔄 立即同步")
        sync_folder_btn.setStyleSheet(STYLE_BTN_SECONDARY)
        sync_folder_btn.clicked.connect(self._sync_selected_folder)

        btn_layout.addWidget(add_folder_btn)
        btn_layout.addWidget(sync_folder_btn)
        btn_layout.addStretch()
        folders_layout.addLayout(btn_layout)

        layout.addWidget(folders_group)

        # 文件差异视图
        diff_group = QGroupBox("文件差异")
        diff_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        diff_layout = QVBoxLayout(diff_group)

        self.diff_tree = QTreeWidget()
        self.diff_tree.setHeaderLabels(["文件路径", "本地状态", "远程状态", "操作"])
        self.diff_tree.setStyleSheet(STYLE_TABLE)
        diff_layout.addWidget(self.diff_tree)

        layout.addWidget(diff_group)

        return widget

    # ─── 同步历史标签 ──────────────────────────────────

    def _create_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 过滤栏
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("类型:"))

        self.history_type_filter = QComboBox()
        self.history_type_filter.addItems(["全部", "上传", "下载", "冲突", "删除"])
        filter_layout.addWidget(self.history_type_filter)

        filter_layout.addWidget(QLabel("时间范围:"))
        self.history_time_filter = QComboBox()
        self.history_time_filter.addItems(["全部", "今天", "最近7天", "最近30天"])
        filter_layout.addWidget(self.history_time_filter)

        filter_layout.addStretch()
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet(STYLE_BTN_SECONDARY)
        refresh_btn.clicked.connect(self._refresh_history)
        filter_layout.addWidget(refresh_btn)

        layout.addLayout(filter_layout)

        # 历史表
        self.history_table = QTableWidget()
        self.history_table.setStyleSheet(STYLE_TABLE)
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            "时间", "类型", "文件路径", "方向", "大小", "耗时", "状态"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.history_table)

        # 统计信息
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background: #f5f5f5; border-radius: 4px; padding: 8px;")
        stats_layout = QHBoxLayout(stats_frame)

        self.stat_total = QLabel("总同步: 0")
        self.stat_conflicts = QLabel("冲突: 0")
        self.stat_errors = QLabel("错误: 0")
        self.stat_data = QLabel("数据量: 0 MB")

        for lbl in [self.stat_total, self.stat_conflicts, self.stat_errors, self.stat_data]:
            lbl.setStyleSheet("font-weight: bold;")
            stats_layout.addWidget(lbl)

        layout.addWidget(stats_frame)

        return widget

    # ─── 版本管理标签 ──────────────────────────────────

    def _create_versions_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 版本策略
        strategy_group = QGroupBox("版本策略")
        strategy_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        strategy_layout = QFormLayout(strategy_group)

        self.version_type_combo = QComboBox()
        self.version_type_combo.addItems([
            "简单版本 (.sync-xxxx)", "暂存版本 (.stversions/)",
            "按时间归档", "仅保留最新"
        ])
        strategy_layout.addRow("版本策略:", self.version_type_combo)

        self.max_versions_spin = QSpinBox()
        self.max_versions_spin.setRange(1, 100)
        self.max_versions_spin.setValue(5)
        strategy_layout.addRow("最大版本数:", self.max_versions_spin)

        self.cleanup_days_spin = QSpinBox()
        self.cleanup_days_spin.setRange(1, 365)
        self.cleanup_days_spin.setValue(30)
        strategy_layout.addRow("清理天数:", self.cleanup_days_spin)

        save_strategy_btn = QPushButton("💾 保存策略")
        save_strategy_btn.setStyleSheet(STYLE_BTN_PRIMARY)
        save_strategy_btn.clicked.connect(self._save_version_strategy)
        strategy_layout.addRow(save_strategy_btn)

        layout.addWidget(strategy_group)

        # 版本列表
        versions_group = QGroupBox("文件版本")
        versions_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        versions_layout = QVBoxLayout(versions_group)

        self.versions_table = QTableWidget()
        self.versions_table.setStyleSheet(STYLE_TABLE)
        self.versions_table.setColumnCount(6)
        self.versions_table.setHorizontalHeaderLabels([
            "文件路径", "版本号", "修改时间", "大小", "来源设备", "操作"
        ])
        self.versions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.versions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.versions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        versions_layout.addWidget(self.versions_table)

        layout.addWidget(versions_group)

        return widget

    # ─── 设置标签 ──────────────────────────────────

    def _create_settings_tab(self) -> QWidget:
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # 连接设置
        conn_group = QGroupBox("连接设置")
        conn_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        conn_layout = QFormLayout(conn_group)

        self.listen_addr = QLineEdit("0.0.0.0:22000")
        conn_layout.addRow("监听地址:", self.listen_addr)

        self.global_discovery = QCheckBox("启用全局发现服务器")
        self.global_discovery.setChecked(True)
        conn_layout.addRow(self.global_discovery)

        self.local_discovery = QCheckBox("启用局域网发现")
        self.local_discovery.setChecked(True)
        conn_layout.addRow(self.local_discovery)

        self.relay_enabled = QCheckBox("启用中继服务器")
        self.relay_enabled.setChecked(True)
        conn_layout.addRow(self.relay_enabled)

        scroll_layout.addWidget(conn_group)

        # 同步设置
        sync_group = QGroupBox("同步设置")
        sync_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        sync_layout = QFormLayout(sync_group)

        self.rescan_interval = QSpinBox()
        self.rescan_interval.setRange(10, 86400)
        self.rescan_interval.setValue(60)
        self.rescan_interval.setSuffix(" 秒")
        sync_layout.addRow("重扫间隔:", self.rescan_interval)

        self.max_concurrent = QSpinBox()
        self.max_concurrent.setRange(1, 32)
        self.max_concurrent.setValue(4)
        sync_layout.addRow("最大并发同步:", self.max_concurrent)

        self.conflict_strategy = QComboBox()
        self.conflict_strategy.addItems([
            "保留双方 (推荐)", "最新优先", "最大优先", "手动解决"
        ])
        sync_layout.addRow("冲突策略:", self.conflict_strategy)

        scroll_layout.addWidget(sync_group)

        # 性能设置
        perf_group = QGroupBox("性能设置")
        perf_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        perf_layout = QFormLayout(perf_group)

        self.chunk_size = QComboBox()
        self.chunk_size.addItems([
            "128 KB", "256 KB", "512 KB (推荐)", "1 MB", "2 MB"
        ])
        self.chunk_size.setCurrentIndex(2)
        perf_layout.addRow("块大小:", self.chunk_size)

        self.send_rate = QSpinBox()
        self.send_rate.setRange(0, 100000)
        self.send_rate.setValue(0)
        self.send_rate.setSuffix(" KB/s (0=不限)")
        perf_layout.addRow("发送限速:", self.send_rate)

        self.recv_rate = QSpinBox()
        self.recv_rate.setRange(0, 100000)
        self.recv_rate.setValue(0)
        self.recv_rate.setSuffix(" KB/s (0=不限)")
        perf_layout.addRow("接收限速:", self.recv_rate)

        self.compression = QCheckBox("启用压缩传输")
        self.compression.setChecked(True)
        perf_layout.addRow(self.compression)

        scroll_layout.addWidget(perf_group)

        # 安全设置
        sec_group = QGroupBox("安全设置")
        sec_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        sec_layout = QFormLayout(sec_group)

        self.tls_enabled = QCheckBox("启用 TLS 加密")
        self.tls_enabled.setChecked(True)
        sec_layout.addRow(self.tls_enabled)

        self.cert_display = QLineEdit()
        self.cert_display.setReadOnly(True)
        self.cert_display.setPlaceholderText("点击生成设备证书...")
        sec_layout.addRow("设备证书:", self.cert_display)

        gen_cert_btn = QPushButton("🔑 生成新证书")
        gen_cert_btn.setStyleSheet(STYLE_BTN_SECONDARY)
        gen_cert_btn.clicked.connect(self._generate_cert)
        sec_layout.addRow(gen_cert_btn)

        scroll_layout.addWidget(sec_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)

        # 保存按钮
        save_btn = QPushButton("💾 保存所有设置")
        save_btn.setStyleSheet(STYLE_BTN_PRIMARY)
        save_btn.clicked.connect(self._save_settings)

        outer_layout = QVBoxLayout(widget)
        outer_layout.addWidget(scroll)
        outer_layout.addWidget(save_btn)

        return widget

    # ─── 定时器 ──────────────────────────────────

    def _init_timers(self):
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_status)
        self.refresh_timer.setInterval(3000)

    # ─── 系统控制 ──────────────────────────────────

    def _toggle_system(self):
        if self.sync_system is None:
            self._start_system()
        else:
            self._stop_system()

    def _start_system(self):
        try:
            from core.root_sync import RootSyncSystem, FolderConfig
            self.sync_system = RootSyncSystem(storage_dir=str(self.config.get("storage_dir", "~/.hermes/root_sync")))
            
            # TODO 1: 从数据库加载配置并启动
            async def _init_async():
                try:
                    # 初始化设备（加载或生成证书）
                    device_id, cert, key = await self.sync_system.initialize_device("LivingTree-AI")
                    self._device_id = device_id
                    self.cert_display.setText(device_id)
                    
                    # 加载已保存的文件夹配置
                    saved_folders = self.config.get("sync_folders", [])
                    for folder_data in saved_folders:
                        config = FolderConfig(
                            folder_id=folder_data.get("id", ""),
                            path=folder_data.get("path", ""),
                            label=folder_data.get("label", ""),
                        )
                        await self.sync_system.add_folder(config)
                    
                    # 启动同步系统
                    await self.sync_system.start()
                except Exception as e:
                    logger.error(f"根系同步初始化失败: {e}")
            
            # 在新线程中运行异步初始化
            loop = asyncio.new_event_loop()
            threading.Thread(target=lambda: asyncio.run_coroutine_threadsafe(_init_async(), loop).result(), daemon=True).start()
            loop.close()

            self.start_btn.setText("⏹ 停止根系同步")
            self.start_btn.setStyleSheet(STYLE_BTN_DANGER)
            self.scan_btn.setEnabled(True)
            self.sync_all_btn.setEnabled(True)
            self.status_bar.showMessage("🌳 根系同步系统已启动")
            self.refresh_timer.start()
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"根系同步系统启动失败:\n{str(e)}")

    def _stop_system(self):
        if self.sync_system:
            # TODO 2: 优雅关闭
            async def _stop_async():
                try:
                    await self.sync_system.stop()
                except Exception as e:
                    logger.error(f"根系同步停止失败: {e}")
            
            loop = asyncio.new_event_loop()
            threading.Thread(target=lambda: asyncio.run_coroutine_threadsafe(_stop_async(), loop).result(), daemon=True).start()
            loop.close()
            self.sync_system = None

        self.start_btn.setText("🌳 启动根系同步")
        self.start_btn.setStyleSheet(STYLE_BTN_PRIMARY)
        self.scan_btn.setEnabled(False)
        self.sync_all_btn.setEnabled(False)
        self.status_bar.showMessage("根系同步系统已停止")
        self.refresh_timer.stop()

    # ─── 设备管理 ──────────────────────────────────

    def _scan_devices(self):
        """扫描局域网设备"""
        if not self.sync_system:
            return

        self.status_bar.showMessage("🔍 正在扫描局域网设备...")
        # TODO 3: 调用 sync_system 扫描
        try:
            from core.root_sync import GlobalDiscovery
            discovery = GlobalDiscovery()
            loop = asyncio.new_event_loop()
            discovered = loop.run_until_complete(discovery.scan())
            loop.close()
            
            self.discovery_table.setRowCount(len(discovered))
            for i, device in enumerate(discovered):
                self.discovery_table.setItem(i, 0, QTableWidgetItem(device.device_id))
                self.discovery_table.setItem(i, 1, QTableWidgetItem(device.device_name))
                self.discovery_table.setItem(i, 2, QTableWidgetItem(device.address))
                self.discovery_table.setItem(i, 3, QTableWidgetItem(str(device.port)))
                connect_btn = QPushButton("连接")
                connect_btn.clicked.connect(lambda checked, d=device: self._connect_device(d))
                self.discovery_table.setCellWidget(i, 4, connect_btn)
            
            self.status_bar.showMessage(f"🔍 扫描完成，发现 {len(discovered)} 台设备")
        except Exception as e:
            self.status_bar.showMessage(f"❌ 扫描失败: {str(e)}")

    def _add_device(self):
        """添加设备对话框"""
        dialog = AddDeviceDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            device_id = dialog.device_id_input.text().strip()
            device_name = dialog.device_name_input.text().strip()
            address = dialog.address_input.text().strip()

            if not device_id:
                QMessageBox.warning(self, "错误", "设备ID不能为空")
                return

            if self.sync_system:
                # TODO 4: 调用 sync_system 添加设备
                from core.root_sync import DeviceInfo
                device_info = DeviceInfo(
                    device_id=device_id,
                    device_name=device_name or device_id,
                    addresses=[address] if address else [],
                    auto_connect=dialog.auto_connect.isChecked(),
                )
                async def _add_async():
                    try:
                        await self.sync_system.add_device(device_info)
                        if dialog.auto_connect and address:
                            await self.sync_system.connect_device(device_id, [address])
                    except Exception as e:
                        logger.error(f"添加设备失败: {e}")
                        self.status_bar.showMessage(f"❌ 添加设备失败: {str(e)}")
                
                loop = asyncio.new_event_loop()
                threading.Thread(target=lambda: asyncio.run_coroutine_threadsafe(_add_async(), loop).result(), daemon=True).start()
                loop.close()
                
                self.status_bar.showMessage(f"✅ 已添加设备: {device_name}")
                self._refresh_devices()

    def _remove_device(self):
        """移除选中设备"""
        row = self.devices_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择要移除的设备")
            return

        device_id = self.devices_table.item(row, 0).text()
        reply = QMessageBox.question(
            self, "确认移除",
            f"确定要移除设备 {device_id} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # TODO 5: 调用 sync_system 移除设备
            if self.sync_system:
                async def _remove_async():
                    try:
                        await self.sync_system.remove_folder(device_id)
                    except Exception as e:
                        logger.error(f"移除设备失败: {e}")
                        self.status_bar.showMessage(f"❌ 移除设备失败: {str(e)}")
                
                loop = asyncio.new_event_loop()
                threading.Thread(target=lambda: asyncio.run_coroutine_threadsafe(_remove_async(), loop).result(), daemon=True).start()
                loop.close()
            
            self.status_bar.showMessage(f"🗑️ 已移除设备: {device_id}")
            self._refresh_devices()

    # ─── 文件夹同步 ──────────────────────────────────

    def _add_folder(self):
        """添加同步文件夹"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择同步文件夹")
        if not folder_path:
            return

        dialog = AddFolderDialog(folder_path, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            folder_id = dialog.folder_id_input.text().strip()
            if self.sync_system:
                # TODO 6: 调用 sync_system 添加文件夹
                from core.root_sync import FolderConfig
                config = FolderConfig(
                    folder_id=folder_id,
                    path=folder_path,
                    label=dialog.folder_id_input.placeholderText(),
                    rescan_interval_sec=dialog.rescan_interval.value(),
                    ignore_patterns=[p.strip() for p in dialog.ignore_patterns.text().split(",") if p.strip()],
                    watch_changes=dialog.watch_changes.isChecked(),
                )
                async def _add_async():
                    try:
                        await self.sync_system.add_folder(config)
                    except Exception as e:
                        logger.error(f"添加文件夹失败: {e}")
                        self.status_bar.showMessage(f"❌ 添加文件夹失败: {str(e)}")
                
                loop = asyncio.new_event_loop()
                threading.Thread(target=lambda: asyncio.run_coroutine_threadsafe(_add_async(), loop).result(), daemon=True).start()
                loop.close()
                
                self.status_bar.showMessage(f"📁 已添加同步文件夹: {folder_path}")
                self._refresh_folders()

    def _sync_selected_folder(self):
        """同步选中文件夹"""
        row = self.folders_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择要同步的文件夹")
            return

        folder_id = self.folders_table.item(row, 0).text()
        if self.sync_system:
            # TODO 7: 调用 sync_system 同步
            async def _sync_async():
                try:
                    await self.sync_system.sync_folder(folder_id)
                except Exception as e:
                    logger.error(f"同步文件夹失败: {e}")
                    self.status_bar.showMessage(f"❌ 同步失败: {str(e)}")
            
            loop = asyncio.new_event_loop()
            threading.Thread(target=lambda: asyncio.run_coroutine_threadsafe(_sync_async(), loop).result(), daemon=True).start()
            loop.close()
            
            self.status_bar.showMessage(f"🔄 正在同步文件夹: {folder_id}")
            self.sync_started.emit(folder_id)

    def _sync_all(self):
        """全量同步所有文件夹"""
        if not self.sync_system:
            return

        self.status_bar.showMessage("⬆⬇ 正在执行全量同步...")
        # TODO 8: 调用 sync_system 全量同步
        async def _sync_all_async():
            try:
                # 获取所有文件夹状态
                if self.sync_system._engine:
                    for folder_id in list(self.sync_system._engine.folders.keys()):
                        await self.sync_system.force_sync(folder_id)
                    self.status_bar.showMessage("⬆⬇ 全量同步完成")
                else:
                    self.status_bar.showMessage("⚠️ 同步引擎未就绪")
            except Exception as e:
                logger.error(f"全量同步失败: {e}")
                self.status_bar.showMessage(f"❌ 全量同步失败: {str(e)}")
        
        loop = asyncio.new_event_loop()
        threading.Thread(target=lambda: asyncio.run_coroutine_threadsafe(_sync_all_async(), loop).result(), daemon=True).start()
        loop.close()

    # ─── 版本管理 ──────────────────────────────────

    def _save_version_strategy(self):
        """保存版本策略"""
        self.status_bar.showMessage("💾 版本策略已保存")

    # ─── 设置 ──────────────────────────────────

    def _generate_cert(self):
        """生成设备证书"""
        if self.sync_system:
            # TODO 9: 调用 device_registry 生成证书
            async def _gen_cert_async():
                try:
                    device_id, cert, key = await self.sync_system.initialize_device("LivingTree-AI-New")
                    self.cert_display.setText(device_id)
                    self.status_bar.showMessage(f"🔑 设备证书已生成: {device_id}")
                except Exception as e:
                    logger.error(f"生成证书失败: {e}")
                    self.status_bar.showMessage(f"❌ 生成证书失败: {str(e)}")
            
            loop = asyncio.new_event_loop()
            threading.Thread(target=lambda: asyncio.run_coroutine_threadsafe(_gen_cert_async(), loop).result(), daemon=True).start()
            loop.close()

    def _save_settings(self):
        """保存所有设置"""
        self.status_bar.showMessage("💾 所有设置已保存")

    # ─── 刷新 ──────────────────────────────────

    def _refresh_status(self):
        """定时刷新状态"""
        if not self.sync_system:
            return
        self._refresh_devices()
        self._refresh_folders()

    def _refresh_devices(self):
        """刷新设备列表"""
        if not self.sync_system:
            return
        
        self.devices_table.setRowCount(0)
        # TODO 10: 从 sync_system 获取设备列表
        try:
            connected_devices = self.sync_system.get_connected_devices()
            self.devices_table.setRowCount(len(connected_devices))
            for i, device_id in enumerate(connected_devices):
                self.devices_table.setItem(i, 0, QTableWidgetItem(device_id))
                self.devices_table.setItem(i, 1, QTableWidgetItem(f"设备-{device_id[:8]}"))
                self.devices_table.setItem(i, 2, QTableWidgetItem("在线"))
                self.devices_table.setItem(i, 2, QTableWidgetItem("").__class__(self.devices_table.item(i, 2).text()))
                self.devices_table.item(i, 2).setStyleSheet(STYLE_STATUS_ONLINE)
                self.devices_table.setItem(i, 3, QTableWidgetItem("192.168.1.x"))
                self.devices_table.setItem(i, 4, QTableWidgetItem("刚刚"))
                self.devices_table.setItem(i, 5, QTableWidgetItem("0"))
                disconnect_btn = QPushButton("断开")
                disconnect_btn.setStyleSheet(STYLE_BTN_DANGER)
                self.devices_table.setCellWidget(i, 6, disconnect_btn)
            
            self.online_label.setText(f"在线设备: {len(connected_devices)}")
        except Exception as e:
            logger.error(f"刷新设备列表失败: {e}")

    def _refresh_folders(self):
        """刷新文件夹列表"""
        if not self.sync_system or not self.sync_system._engine:
            return
        
        self.folders_table.setRowCount(0)
        # TODO 11: 从 sync_system 获取文件夹列表
        try:
            folders = self.sync_system._engine.folders
            self.folders_table.setRowCount(len(folders))
            for i, (folder_id, folder) in enumerate(folders.items()):
                self.folders_table.setItem(i, 0, QTableWidgetItem(folder_id))
                self.folders_table.setItem(i, 1, QTableWidgetItem(folder.path))
                self.folders_table.setItem(i, 2, QTableWidgetItem("同步中"))
                self.folders_table.setItem(i, 2, QTableWidgetItem("").__class__(self.folders_table.item(i, 2).text()))
                self.folders_table.item(i, 2).setStyleSheet(STYLE_STATUS_SYNCING)
                self.folders_table.setItem(i, 3, QTableWidgetItem("0"))
                self.folders_table.setItem(i, 4, QTableWidgetItem("0"))
                self.folders_table.setItem(i, 5, QTableWidgetItem("100%"))
                sync_btn = QPushButton("同步")
                sync_btn.setStyleSheet(STYLE_BTN_SECONDARY)
                self.folders_table.setCellWidget(i, 6, sync_btn)
        except Exception as e:
            logger.error(f"刷新文件夹列表失败: {e}")

    def _refresh_history(self):
        """刷新同步历史"""
        # TODO 12: 从数据库获取同步历史
        # 由于同步历史需要从数据库查询，这里先显示模拟数据
        self.history_table.setRowCount(0)
        
        # 显示模拟数据（实际应该从数据库查询）
        mock_history = [
            ("2026-04-22 10:30:00", "上传", "/docs/file1.txt", "↑", "2.5 KB", "0.5s", "成功"),
            ("2026-04-22 10:25:00", "下载", "/docs/file2.txt", "↓", "1.2 MB", "1.2s", "成功"),
            ("2026-04-22 10:20:00", "冲突", "/docs/file3.txt", "↔", "500 B", "0.1s", "冲突"),
        ]
        
        self.history_table.setRowCount(len(mock_history))
        for i, (time, type_, path, direction, size, duration, status) in enumerate(mock_history):
            self.history_table.setItem(i, 0, QTableWidgetItem(time))
            self.history_table.setItem(i, 1, QTableWidgetItem(type_))
            self.history_table.setItem(i, 2, QTableWidgetItem(path))
            self.history_table.setItem(i, 3, QTableWidgetItem(direction))
            self.history_table.setItem(i, 4, QTableWidgetItem(size))
            self.history_table.setItem(i, 5, QTableWidgetItem(duration))
            self.history_table.setItem(i, 6, QTableWidgetItem(status))
            if status == "成功":
                self.history_table.item(i, 6).setStyleSheet("color: #4CAF50;")
            elif status == "冲突":
                self.history_table.item(i, 6).setStyleSheet("color: #FF9800;")
            else:
                self.history_table.item(i, 6).setStyleSheet("color: #f44336;")
        
        # 更新统计信息
        self.stat_total.setText(f"总同步: {len(mock_history)}")
        self.stat_conflicts.setText(f"冲突: {sum(1 for h in mock_history if h[1] == '冲突')}")
        self.stat_errors.setText(f"错误: {sum(1 for h in mock_history if h[6] == '失败')}")
        self.stat_data.setText(f"数据量: {sum(int(h[4].split()[0]) for h in mock_history if h[4].split()[1] == 'KB')} KB")

    # ─── 外部接口 ──────────────────────────────────

    def set_sync_system(self, sync_system):
        """设置同步系统实例"""
        self.sync_system = sync_system
        if sync_system:
            self._start_system()


class AddDeviceDialog(QDialog):
    """添加设备对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加设备")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.device_id_input = QLineEdit()
        self.device_id_input.setPlaceholderText("例: LT-AI-7A3B9C1D")
        layout.addRow("设备ID *:", self.device_id_input)

        self.device_name_input = QLineEdit()
        self.device_name_input.setPlaceholderText("例: 办公室笔记本")
        layout.addRow("设备名称:", self.device_name_input)

        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("例: 192.168.1.100:22000")
        layout.addRow("地址:", self.address_input)

        self.auto_connect = QCheckBox("自动连接")
        self.auto_connect.setChecked(True)
        layout.addRow(self.auto_connect)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class AddFolderDialog(QDialog):
    """添加同步文件夹对话框"""

    def __init__(self, folder_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加同步文件夹")
        self.setMinimumWidth(450)

        layout = QFormLayout(self)

        self.folder_id_input = QLineEdit()
        self.folder_id_input.setPlaceholderText("例: work-docs")
        layout.addRow("文件夹ID *:", self.folder_id_input)

        self.path_input = QLineEdit(folder_path)
        self.path_input.setReadOnly(True)
        layout.addRow("路径:", self.path_input)

        self.shared_devices = QTextEdit()
        self.shared_devices.setPlaceholderText("每行一个设备ID，留空则共享给所有设备")
        self.shared_devices.setMaximumHeight(80)
        layout.addRow("共享设备:", self.shared_devices)

        self.rescan_interval = QSpinBox()
        self.rescan_interval.setRange(10, 86400)
        self.rescan_interval.setValue(60)
        self.rescan_interval.setSuffix(" 秒")
        layout.addRow("扫描间隔:", self.rescan_interval)

        self.ignore_patterns = QLineEdit()
        self.ignore_patterns.setPlaceholderText("例: *.tmp, .git/*, node_modules/*")
        layout.addRow("忽略规则:", self.ignore_patterns)

        self.watch_changes = QCheckBox("监听文件变化 (实时同步)")
        self.watch_changes.setChecked(True)
        layout.addRow(self.watch_changes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
