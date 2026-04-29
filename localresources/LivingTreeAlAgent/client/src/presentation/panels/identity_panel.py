"""
IdentityPanel - 身份管理与同步状态面板
=====================================

用户界面功能：
1. 身份创建与恢复（助记词）
2. 保险箱解锁/锁定
3. 设备列表与在线状态
4. 同步状态与手动同步
5. 备份管理与恢复
6. 私有服务器配置

Author: Hermes Desktop AI Assistant
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

# PyQt6 导入
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
        QGroupBox, QFrame, QScrollArea, QProgressBar, QTabWidget,
        QComboBox, QCheckBox, QSpinBox, QTableWidget, QTableWidgetItem,
        QHeaderView, QAbstractItemView, QSizePolicy, QDialog, QMessageBox,
        QSplitter, QStatusBar, QToolButton, QMenu, QProgressDialog
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QStringListModel
    from PyQt6.QtGui import QIcon, QFont, QColor, QPalette, QAction, QPainter, QPen
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    print("PyQt6 not available, IdentityPanel UI will not be loaded")

logger = logging.getLogger(__name__)


class IdentityPanel(QWidget if PYQT6_AVAILABLE else object):
    """
    身份管理面板

    主要功能：
    1. 身份创建与恢复（助记词）
    2. 保险箱解锁/锁定
    3. 设备列表与在线状态
    4. 同步状态与手动同步
    5. 备份管理与恢复
    6. 私有服务器配置
    """

    # 信号定义
    identity_created = pyqtSignal(str, str)  # mnemonic, device_id
    identity_recovered = pyqtSignal(str)      # device_id
    vault_unlocked = pyqtSignal()
    vault_locked = pyqtSignal()
    sync_started = pyqtSignal()
    sync_completed = pyqtSignal(dict)
    backup_started = pyqtSignal()
    backup_completed = pyqtSignal(dict)
    connection_changed = pyqtSignal(str, str)  # old_state, new_state

    def __init__(self, parent=None):
        super().__init__(parent)

        # 状态
        self._vault_unlocked = False
        self._device_id = ""
        self._mnemonic = ""
        self._relay_manager = None
        self._connection_manager = None
        self._health_monitor = None

        # 初始化UI
        if PYQT6_AVAILABLE:
            self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 标题
        title = QLabel("🔐 身份与同步管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        main_layout.addWidget(title)

        # 创建标签页
        tabs = QTabWidget()
        tabs.addTab(self._create_identity_tab(), "👤 身份")
        tabs.addTab(self._create_devices_tab(), "📱 设备")
        tabs.addTab(self._create_sync_tab(), "🔄 同步")
        tabs.addTab(self._create_backup_tab(), "☁️ 备份")
        tabs.addTab(self._create_relay_tab(), "🌐 中继")

        main_layout.addWidget(tabs)

        # 状态栏
        self._status_bar = QStatusBar()
        self._status_label = QLabel("未连接")
        self._status_bar.addPermanentWidget(self._status_label)
        main_layout.addWidget(self._status_bar)

    def _create_identity_tab(self) -> QWidget:
        """创建身份标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 保险箱状态
        vault_group = QGroupBox("🔐 身份保险箱")
        vault_layout = QVBoxLayout()

        # 状态显示
        self._vault_status_label = QLabel("🔒 已锁定")
        self._vault_status_label.setStyleSheet(
            "padding: 10px; background: #f8f9fa; border-radius: 5px; font-size: 14px;"
        )
        vault_layout.addWidget(self._vault_status_label)

        # 设备ID
        self._device_id_label = QLabel("设备ID: 未设置")
        vault_layout.addWidget(self._device_id_label)

        # 按钮组
        btn_layout = QHBoxLayout()

        self._unlock_btn = QPushButton("🔓 解锁保险箱")
        self._unlock_btn.clicked.connect(self._on_unlock_clicked)
        btn_layout.addWidget(self._unlock_btn)

        self._lock_btn = QPushButton("🔒 锁定保险箱")
        self._lock_btn.clicked.connect(self._on_lock_clicked)
        self._lock_btn.setEnabled(False)
        btn_layout.addWidget(self._lock_btn)

        vault_layout.addLayout(btn_layout)
        vault_group.setLayout(vault_layout)
        layout.addWidget(vault_group)

        # 创建身份
        create_group = QGroupBox("✨ 创建新身份")
        create_layout = QVBoxLayout()

        desc = QLabel("创建新的数字身份，生成助记词用于恢复。")
        desc.setStyleSheet("color: #666;")
        create_layout.addWidget(desc)

        pwd_layout = QHBoxLayout()
        pwd_layout.addWidget(QLabel("保险箱密码:"))
        self._create_password = QLineEdit()
        self._create_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._create_password.setPlaceholderText("设置保险箱密码")
        pwd_layout.addWidget(self._create_password)
        create_layout.addLayout(pwd_layout)

        confirm_layout = QHBoxLayout()
        confirm_layout.addWidget(QLabel("确认密码:"))
        self._confirm_password = QLineEdit()
        self._confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_password.setPlaceholderText("再次输入密码")
        confirm_layout.addWidget(self._confirm_password)
        create_layout.addLayout(confirm_layout)

        self._create_identity_btn = QPushButton("🚀 创建身份")
        self._create_identity_btn.clicked.connect(self._on_create_identity)
        create_layout.addWidget(self._create_identity_btn)

        # 助记词显示区（创建后）
        self._mnemonic_display = QTextEdit()
        self._mnemonic_display.setPlaceholderText("助记词将显示在这里...")
        self._mnemonic_display.setMaximumHeight(100)
        self._mnemonic_display.setVisible(False)
        create_layout.addWidget(self._mnemonic_display)

        self._copy_mnemonic_btn = QPushButton("📋 复制助记词")
        self._copy_mnemonic_btn.setVisible(False)
        self._copy_mnemonic_btn.clicked.connect(self._on_copy_mnemonic)
        create_layout.addWidget(self._copy_mnemonic_btn)

        create_group.setLayout(create_layout)
        layout.addWidget(create_group)

        # 恢复身份
        recover_group = QGroupBox("🔁 恢复身份")
        recover_layout = QVBoxLayout()

        desc2 = QLabel("使用助记词恢复已有身份。")
        desc2.setStyleSheet("color: #666;")
        recover_layout.addWidget(desc2)

        recover_pwd_layout = QHBoxLayout()
        recover_pwd_layout.addWidget(QLabel("保险箱密码:"))
        self._recover_password = QLineEdit()
        self._recover_password.setEchoMode(QLineEdit.EchoMode.Password)
        recover_pwd_layout.addWidget(self._recover_password)
        recover_layout.addLayout(recover_pwd_layout)

        self._recover_mnemonic = QTextEdit()
        self._recover_mnemonic.setPlaceholderText("输入助记词（12或24个单词，用空格分隔）...")
        self._recover_mnemonic.setMaximumHeight(80)
        recover_layout.addWidget(self._recover_mnemonic)

        self._recover_btn = QPushButton("🔄 恢复身份")
        self._recover_btn.clicked.connect(self._on_recover_identity)
        recover_layout.addWidget(self._recover_btn)

        recover_group.setLayout(recover_layout)
        layout.addWidget(recover_group)

        layout.addStretch()
        return widget

    def _create_devices_tab(self) -> QWidget:
        """创建设备标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 当前设备
        current_group = QGroupBox("📱 当前设备")
        current_layout = QVBoxLayout()

        self._current_device_label = QLabel("设备ID: 未设置")
        current_layout.addWidget(self._current_device_label)

        self._device_status_label = QLabel("状态: 离线")
        current_layout.addWidget(self._device_status_label)

        current_group.setLayout(current_layout)
        layout.addWidget(current_group)

        # 在线设备列表
        devices_group = QGroupBox("🌐 在线设备")
        devices_layout = QVBoxLayout()

        self._devices_list = QListWidget()
        self._devices_list.setAlternatingRowColors(True)
        devices_layout.addWidget(self._devices_list)

        refresh_btn = QPushButton("🔍 刷新设备列表")
        refresh_btn.clicked.connect(self._on_refresh_devices)
        devices_layout.addWidget(refresh_btn)

        devices_group.setLayout(devices_layout)
        layout.addWidget(devices_group)

        return widget

    def _create_sync_tab(self) -> QWidget:
        """创建同步标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 连接状态
        status_group = QGroupBox("📡 连接状态")
        status_layout = QVBoxLayout()

        self._connection_state_label = QLabel("状态: 初始化中...")
        status_layout.addWidget(self._connection_state_label)

        self._current_path_label = QLabel("当前路径: 无")
        status_layout.addWidget(self._current_path_label)

        # 阶段进度
        self._stage_progress = QProgressBar()
        self._stage_progress.setRange(0, 100)
        self._stage_progress.setValue(0)
        status_layout.addWidget(self._stage_progress)

        self._stage_label = QLabel("阶段: -")
        status_layout.addWidget(self._stage_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # 同步状态
        sync_group = QGroupBox("🔄 同步状态")
        sync_layout = QVBoxLayout()

        self._last_sync_label = QLabel("上次同步: 从未")
        sync_layout.addWidget(self._last_sync_label)

        self._pending_ops_label = QLabel("待同步操作: 0")
        sync_layout.addWidget(self._pending_ops_label)

        sync_btn_layout = QHBoxLayout()

        self._sync_now_btn = QPushButton("🔄 立即同步")
        self._sync_now_btn.clicked.connect(self._on_sync_now)
        sync_btn_layout.addWidget(self._sync_now_btn)

        self._force_reconnect_btn = QPushButton("🔁 重新连接")
        self._force_reconnect_btn.clicked.connect(self._on_force_reconnect)
        sync_btn_layout.addWidget(self._force_reconnect_btn)

        sync_layout.addLayout(sync_btn_layout)

        sync_group.setLayout(sync_layout)
        layout.addWidget(sync_group)

        # 同步历史
        history_group = QGroupBox("📜 同步历史")
        history_layout = QVBoxLayout()

        self._sync_history_list = QListWidget()
        history_layout.addWidget(self._sync_history_list)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        return widget

    def _create_backup_tab(self) -> QWidget:
        """创建备份标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 备份概览
        overview_group = QGroupBox("☁️ 云端备份")
        overview_layout = QVBoxLayout()

        # 配额显示
        quota_layout = QHBoxLayout()
        quota_layout.addWidget(QLabel("存储配额:"))

        self._quota_bar = QProgressBar()
        quota_layout.addWidget(self._quota_bar)

        self._quota_label = QLabel("0 / 0 GB")
        quota_layout.addWidget(self._quota_label)

        overview_layout.addLayout(quota_layout)

        # 云盘选择
        cloud_layout = QHBoxLayout()
        cloud_layout.addWidget(QLabel("云盘:"))

        self._cloud_selector = QComboBox()
        self._cloud_selector.addItems([
            "阿里云 OSS (40GB)",
            "腾讯云 COS (50GB)",
            "Google Drive (15GB)",
            "OneDrive (5GB)",
            "Dropbox (2GB)"
        ])
        cloud_layout.addWidget(self._cloud_selector)

        overview_layout.addLayout(cloud_layout)

        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)

        # 备份操作
        action_group = QGroupBox("🛠️ 备份操作")
        action_layout = QVBoxLayout()

        self._create_backup_btn = QPushButton("💾 创建备份")
        self._create_backup_btn.clicked.connect(self._on_create_backup)
        action_layout.addWidget(self._create_backup_btn)

        self._restore_backup_btn = QPushButton("📥 恢复备份")
        self._restore_backup_btn.clicked.connect(self._on_restore_backup)
        action_layout.addWidget(self._restore_backup_btn)

        # 定时备份设置
        schedule_layout = QHBoxLayout()
        schedule_layout.addWidget(QLabel("自动备份:"))

        self._schedule_selector = QComboBox()
        self._schedule_selector.addItems(["关闭", "每天", "每周", "每月"])
        schedule_layout.addWidget(self._schedule_selector)

        action_layout.addLayout(schedule_layout)

        action_group.setLayout(action_layout)
        layout.addWidget(action_group)

        # 备份列表
        list_group = QGroupBox("📋 备份历史")
        list_layout = QVBoxLayout()

        self._backup_list = QTableWidget()
        self._backup_list.setColumnCount(5)
        self._backup_list.setHorizontalHeaderLabels(["ID", "时间", "云盘", "大小", "状态"])
        self._backup_list.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._backup_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._backup_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        list_layout.addWidget(self._backup_list)

        refresh_backup_btn = QPushButton("🔄 刷新列表")
        refresh_backup_btn.clicked.connect(self._on_refresh_backups)
        list_layout.addWidget(refresh_backup_btn)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        return widget

    def _create_relay_tab(self) -> QWidget:
        """创建中继标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 私有服务器配置
        private_group = QGroupBox("🖥️ 私有服务器配置")
        private_layout = QVBoxLayout()

        desc = QLabel("配置您自己的服务器以获得更好的连接体验（可选）")
        desc.setStyleSheet("color: #666;")
        private_layout.addWidget(desc)

        domain_layout = QHBoxLayout()
        domain_layout.addWidget(QLabel("域名:"))
        self._relay_domain = QLineEdit()
        self._relay_domain.setPlaceholderText("your-server.com")
        domain_layout.addWidget(self._relay_domain)
        private_layout.addLayout(domain_layout)

        ports_layout = QHBoxLayout()
        ports_layout.addWidget(QLabel("信令端口:"))
        self._signaling_port = QSpinBox()
        self._signaling_port.setRange(1, 65535)
        self._signaling_port.setValue(8081)
        ports_layout.addWidget(self._signaling_port)

        ports_layout.addWidget(QLabel("TURN端口:"))
        self._turn_port = QSpinBox()
        self._turn_port.setRange(1, 65535)
        self._turn_port.setValue(8082)
        ports_layout.addWidget(self._turn_port)
        private_layout.addLayout(ports_layout)

        auth_layout = QHBoxLayout()
        auth_layout.addWidget(QLabel("用户名:"))
        self._relay_username = QLineEdit()
        auth_layout.addWidget(self._relay_username)
        auth_layout.addWidget(QLabel("密码:"))
        self._relay_password = QLineEdit()
        self._relay_password.setEchoMode(QLineEdit.EchoMode.Password)
        auth_layout.addWidget(self._relay_password)
        private_layout.addLayout(auth_layout)

        btn_layout = QHBoxLayout()
        self._save_relay_btn = QPushButton("💾 保存配置")
        self._save_relay_btn.clicked.connect(self._on_save_relay_config)
        btn_layout.addWidget(self._save_relay_btn)

        self._test_relay_btn = QPushButton("🧪 测试连接")
        self._test_relay_btn.clicked.connect(self._on_test_relay)
        btn_layout.addWidget(self._test_relay_btn)

        self._disable_private_btn = QPushButton("❌ 禁用私有服务器")
        self._disable_private_btn.clicked.connect(self._on_disable_private)
        btn_layout.addWidget(self._disable_private_btn)

        private_layout.addLayout(btn_layout)
        private_group.setLayout(private_layout)
        layout.addWidget(private_group)

        # 公共端点状态
        public_group = QGroupBox("🌍 公共端点状态")
        public_layout = QVBoxLayout()

        self._relay_health_table = QTableWidget()
        self._relay_health_table.setColumnCount(5)
        self._relay_health_table.setHorizontalHeaderLabels(["端点", "类型", "延迟", "成功率", "状态"])
        self._relay_health_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._relay_health_table.setAlternatingRowColors(True)
        self._relay_health_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        public_layout.addWidget(self._relay_health_table)

        refresh_relay_btn = QPushButton("🔄 刷新状态")
        refresh_relay_btn.clicked.connect(self._on_refresh_relay_status)
        public_layout.addWidget(refresh_relay_btn)

        public_group.setLayout(public_layout)
        layout.addWidget(public_group)

        return widget

    # ============================================================
    # 事件处理
    # ============================================================

    def _on_unlock_clicked(self):
        """解锁保险箱"""
        password = self._create_password.text() if self._create_password.text() else ""
        if not password:
            QMessageBox.warning(self, "警告", "请输入保险箱密码")
            return

        try:
            from core.identity_vault import get_vault_manager
            vault = get_vault_manager()

            if vault.unlock(password):
                self._vault_unlocked = True
                self._vault_status_label.setText("🔓 已解锁")
                self._vault_status_label.setStyleSheet(
                    "padding: 10px; background: #d4edda; border-radius: 5px; font-size: 14px;"
                )
                self._unlock_btn.setEnabled(False)
                self._lock_btn.setEnabled(True)
                self.vault_unlocked.emit()
                QMessageBox.information(self, "成功", "保险箱已解锁！")
            else:
                QMessageBox.warning(self, "失败", "密码错误")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"解锁失败: {str(e)}")

    def _on_lock_clicked(self):
        """锁定保险箱"""
        try:
            from core.identity_vault import get_vault_manager
            vault = get_vault_manager()
            vault.lock()

            self._vault_unlocked = False
            self._vault_status_label.setText("🔒 已锁定")
            self._vault_status_label.setStyleSheet(
                "padding: 10px; background: #f8f9fa; border-radius: 5px; font-size: 14px;"
            )
            self._unlock_btn.setEnabled(True)
            self._lock_btn.setEnabled(False)
            self.vault_locked.emit()

        except Exception as e:
            logger.error(f"Lock failed: {e}")

    def _on_create_identity(self):
        """创建身份"""
        password = self._create_password.text()
        confirm = self._confirm_password.text()

        if not password:
            QMessageBox.warning(self, "警告", "请输入密码")
            return

        if password != confirm:
            QMessageBox.warning(self, "警告", "两次密码不一致")
            return

        if len(password) < 8:
            QMessageBox.warning(self, "警告", "密码长度至少8位")
            return

        try:
            from core.identity_vault import get_vault_manager

            # 显示进度
            progress = QProgressDialog("正在创建身份...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            vault = get_vault_manager()
            mnemonic, device_id = vault.create_identity(password)

            self._mnemonic = mnemonic
            self._device_id = device_id

            # 显示助记词
            self._mnemonic_display.setPlainText(mnemonic)
            self._mnemonic_display.setVisible(True)
            self._copy_mnemonic_btn.setVisible(True)

            self._device_id_label.setText(f"设备ID: {device_id}")

            self.identity_created.emit(mnemonic, device_id)

            progress.close()
            QMessageBox.information(
                self,
                "🎉 身份创建成功",
                f"设备ID: {device_id}\n\n"
                "⚠️ 请立即抄写助记词并妥善保管！\n"
                "助记词是恢复身份的唯一方式，一旦丢失将无法恢复。"
            )

        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建身份失败: {str(e)}")

    def _on_copy_mnemonic(self):
        """复制助记词"""
        from PyQt6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self._mnemonic)
        QMessageBox.information(self, "已复制", "助记词已复制到剪贴板")

    def _on_recover_identity(self):
        """恢复身份"""
        mnemonic = self._recover_mnemonic.toPlainText().strip()
        password = self._recover_password.text()

        if not mnemonic or not password:
            QMessageBox.warning(self, "警告", "请输入助记词和密码")
            return

        try:
            from core.identity_vault import get_vault_manager

            vault = get_vault_manager()
            device_id = vault.recover_identity(mnemonic, password)

            self._device_id = device_id
            self._device_id_label.setText(f"设备ID: {device_id}")

            self.identity_recovered.emit(device_id)

            QMessageBox.information(self, "成功", f"身份已恢复！\n设备ID: {device_id}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"恢复身份失败: {str(e)}")

    def _on_refresh_devices(self):
        """刷新设备列表"""
        try:
            from core.identity_vault import get_state_db

            db = get_state_db()
            devices = db.get_devices()

            self._devices_list.clear()
            for device in devices:
                item = QListWidgetItem(
                    f"📱 {device['device_id']} - "
                    f"{'在线' if device.get('is_online') else '离线'}"
                )
                self._devices_list.addItem(item)

        except Exception as e:
            logger.error(f"Refresh devices failed: {e}")

    def _on_sync_now(self):
        """立即同步"""
        try:
            self.sync_started.emit()
            self._sync_now_btn.setEnabled(False)

            from core.identity_vault import get_data_butler
            butler = get_data_butler()
            result = butler.sync_all()

            self.sync_completed.emit(result)
            self._last_sync_label.setText(f"上次同步: {time.strftime('%H:%M:%S')}")

        except Exception as e:
            logger.error(f"Sync failed: {e}")
        finally:
            self._sync_now_btn.setEnabled(True)

    def _on_force_reconnect(self):
        """强制重新连接"""
        try:
            from core.relay_router import get_connection_manager
            cm = get_connection_manager()
            cm.force_reconnect()
            QMessageBox.information(self, "已触发", "正在尝试重新连接...")

        except Exception as e:
            logger.error(f"Reconnect failed: {e}")

    def _on_create_backup(self):
        """创建备份"""
        try:
            self.backup_started.emit()

            from core.identity_vault import get_data_butler
            butler = get_data_butler()

            cloud_names = ["aliyun_oss", "tencent_cos", "google_drive", "onedrive", "dropbox"]
            selected_cloud = cloud_names[self._cloud_selector.currentIndex()]

            result = butler.create_backup(categories=["state", "content", "config"])

            if result.get("success"):
                self.backup_completed.emit(result)
                QMessageBox.information(self, "成功", f"备份已创建！\nID: {result.get('backup_id')}")
            else:
                QMessageBox.warning(self, "失败", result.get("error", "未知错误"))

        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建备份失败: {str(e)}")

    def _on_restore_backup(self):
        """恢复备份"""
        selected = self._backup_list.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "警告", "请选择要恢复的备份")
            return

        backup_id = self._backup_list.item(selected, 0).text()

        reply = QMessageBox.question(
            self,
            "确认恢复",
            f"确定要恢复备份 {backup_id} 吗？这将覆盖当前数据。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                from core.identity_vault import get_data_butler
                butler = get_data_butler()
                result = butler.restore_backup(backup_id)

                if result.get("success"):
                    QMessageBox.information(self, "成功", "备份已恢复！")
                else:
                    QMessageBox.warning(self, "失败", result.get("error", "未知错误"))

            except Exception as e:
                QMessageBox.critical(self, "错误", f"恢复失败: {str(e)}")

    def _on_refresh_backups(self):
        """刷新备份列表"""
        try:
            from core.identity_vault import get_data_butler
            butler = get_data_butler()
            backups = butler.list_backups()

            self._backup_list.setRowCount(len(backups))
            for i, backup in enumerate(backups):
                self._backup_list.setItem(i, 0, QTableWidgetItem(backup.get("backup_id", "")))
                self._backup_list.setItem(i, 1, QTableWidgetItem(
                    time.strftime("%Y-%m-%d %H:%M", time.localtime(backup.get("timestamp", 0)))
                ))
                self._backup_list.setItem(i, 2, QTableWidgetItem(backup.get("provider", "")))
                self._backup_list.setItem(i, 3, QTableWidgetItem(
                    f"{backup.get('size', 0) / 1024 / 1024:.2f} MB"
                ))
                self._backup_list.setItem(i, 4, QTableWidgetItem(backup.get("status", "")))

        except Exception as e:
            logger.error(f"Refresh backups failed: {e}")

    def _on_save_relay_config(self):
        """保存中继配置"""
        domain = self._relay_domain.text()
        signaling_port = self._signaling_port.value()
        turn_port = self._turn_port.value()
        username = self._relay_username.text()
        password = self._relay_password.text()

        if not domain:
            QMessageBox.warning(self, "警告", "请输入服务器域名")
            return

        try:
            from core.relay_router import get_relay_config
            config = get_relay_config()
            config.configure_private_server(
                domain=domain,
                signaling_port=signaling_port,
                turn_port=turn_port,
                username=username,
                password=password
            )

            QMessageBox.information(self, "成功", "中继配置已保存！")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")

    def _on_test_relay(self):
        """测试中继连接"""
        self._test_relay_btn.setEnabled(False)
        self._test_relay_btn.setText("测试中...")

        try:
            from core.relay_router import get_health_monitor
            monitor = get_health_monitor()
            results = monitor.check_all_relays()

            # 更新表格
            self._relay_health_table.setRowCount(len(results))
            for i, (name, health) in enumerate(results.items()):
                self._relay_health_table.setItem(i, 0, QTableWidgetItem(name))
                self._relay_health_table.setItem(i, 1, QTableWidgetItem(
                    health.name.replace("_", " ").title()
                ))
                self._relay_health_table.setItem(i, 2, QTableWidgetItem(
                    f"{health.latency_ms:.0f} ms" if health.latency_ms else "N/A"
                ))
                self._relay_health_table.setItem(i, 3, QTableWidgetItem(
                    f"{health.success_rate * 100:.1f}%"
                ))

                status_item = QTableWidgetItem(health.status.value)
                if health.status.value == "healthy":
                    status_item.setBackground(QColor("#d4edda"))
                elif health.status.value == "degraded":
                    status_item.setBackground(QColor("#fff3cd"))
                else:
                    status_item.setBackground(QColor("#f8d7da"))
                self._relay_health_table.setItem(i, 4, status_item)

            QMessageBox.information(self, "完成", "连接测试完成！")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"测试失败: {str(e)}")

        finally:
            self._test_relay_btn.setEnabled(True)
            self._test_relay_btn.setText("🧪 测试连接")

    def _on_disable_private(self):
        """禁用私有服务器"""
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要禁用私有服务器吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                from core.relay_router import get_relay_config
                config = get_relay_config()
                config.disable_private_server()

                self._relay_domain.clear()
                self._relay_username.clear()
                self._relay_password.clear()

                QMessageBox.information(self, "成功", "私有服务器已禁用")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"操作失败: {str(e)}")

    def _on_refresh_relay_status(self):
        """刷新中继状态"""
        self._on_test_relay()

    # ============================================================
    # 公共接口
    # ============================================================

    def is_vault_unlocked(self) -> bool:
        """检查保险箱是否已解锁"""
        return self._vault_unlocked

    def get_device_id(self) -> str:
        """获取设备ID"""
        return self._device_id

    def update_connection_status(self, state: str, path: str, stage: str, progress: int):
        """更新连接状态"""
        self._connection_state_label.setText(f"状态: {state}")
        self._current_path_label.setText(f"当前路径: {path}")
        self._stage_label.setText(f"阶段: {stage}")
        self._stage_progress.setValue(progress)

    def update_sync_status(self, last_sync: float, pending_ops: int):
        """更新同步状态"""
        if last_sync > 0:
            self._last_sync_label.setText(f"上次同步: {time.strftime('%H:%M:%S', time.localtime(last_sync))}")
        else:
            self._last_sync_label.setText("上次同步: 从未")

        self._pending_ops_label.setText(f"待同步操作: {pending_ops}")

    def add_sync_history(self, message: str):
        """添加同步历史"""
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        self._sync_history_list.insertItem(0, f"[{timestamp}] {message}")
