# -*- coding: utf-8 -*-
"""
🎛️ 通用硬件智能集成系统 - Hardware Mind Panel
=============================================

核心理念: "硬件即插件，自动发现、自动学习、自动集成"

功能：
- 硬件设备检测与识别
- 设备指纹生成与管理
- 驱动匹配与下载
- 生命周期管理
- 协议解析

Author: Hermes Desktop Team
Version: 1.0.0
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QComboBox, QTabWidget, QGroupBox,
    QScrollArea, QFrame, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QStatusBar,
    QToolButton, QStackedWidget, QFormLayout, QSpinBox,
    QCheckBox, QMessageBox, QSplitter, QFileDialog,
    QInputDialog, QDialog, QProgressDialog
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor

import asyncio
import json
import time
import os
from datetime import datetime
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class HardwareMindPanel(QWidget):
    """
    通用硬件智能集成系统 - UI面板

    三层架构:
    - Layer 0: 物理层 (硬件检测、协议嗅探、指纹生成)
    - Layer 1: 知识层 (本地知识库、云端手册库、AI解析引擎)
    - Layer 2: 执行层 (驱动生成、配置生成、测试验证、UI生成)
    """

    # 信号定义
    device_discovered = pyqtSignal(dict)
    driver_installed = pyqtSignal(str, bool)
    lifecycle_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = None
        self.devices = {}
        self._init_ui()
        self._init_connections()

    def set_engine(self, engine):
        """设置Hardware Mind引擎"""
        self.engine = engine
        if engine:
            self._update_engine_status(True)
            self._start_auto_detection()
        else:
            self._update_engine_status(False)

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("🎛️ 通用硬件智能集成")
        self.setMinimumSize(1100, 750)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setSizes([350, 750])

        left_panel = self._create_device_panel()
        splitter.addWidget(left_panel)

        right_panel = self._create_detail_panel()
        splitter.addWidget(right_panel)

        main_layout.addWidget(splitter)

        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        main_layout.addWidget(self.status_bar)

        self._update_engine_status(False)

    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QFrame()
        toolbar.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 4, 8, 4)

        self.engine_status_label = QLabel("🔴 引擎未连接")
        layout.addWidget(self.engine_status_label)

        layout.addStretch()

        self.btn_scan = QPushButton("🔍 扫描设备")
        self.btn_scan.setEnabled(False)
        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_export = QPushButton("📤 导出")
        self.btn_settings = QPushButton("⚙️ 设置")

        layout.addWidget(self.btn_scan)
        layout.addWidget(self.btn_refresh)
        layout.addWidget(self.btn_export)
        layout.addWidget(self.btn_settings)

        return toolbar

    def _create_device_panel(self) -> QWidget:
        """创建设备列表面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QVBoxLayout(panel)

        title = QLabel("📱 已发现设备")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(title)

        self.device_search = QLineEdit()
        self.device_search.setPlaceholderText("搜索设备...")
        self.device_search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.device_search)

        self.device_list = QListWidget()
        self.device_list.itemClicked.connect(self._on_device_selected)
        layout.addWidget(self.device_list, 1)

        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("总计:"))
        self.device_count_label = QLabel("0")
        stats_layout.addWidget(self.device_count_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        filter_group = QGroupBox("设备类型过滤")
        filter_layout = QVBoxLayout(filter_group)

        self.filter_usb = QCheckBox("USB设备")
        self.filter_usb.setChecked(True)
        self.filter_usb.toggled.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_usb)

        self.filter_bluetooth = QCheckBox("蓝牙设备")
        self.filter_bluetooth.setChecked(True)
        self.filter_bluetooth.toggled.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_bluetooth)

        self.filter_wifi = QCheckBox("WiFi设备")
        self.filter_wifi.setChecked(True)
        self.filter_wifi.toggled.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_wifi)

        self.filter_serial = QCheckBox("串口设备")
        self.filter_serial.setChecked(True)
        self.filter_serial.toggled.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_serial)

        layout.addWidget(filter_group)

        return panel

    def _create_detail_panel(self) -> QWidget:
        """创建设备详情面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QVBoxLayout(panel)

        title = QLabel("📋 设备详情")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(title)

        self.detail_tabs = QTabWidget()

        overview_tab = self._create_overview_tab()
        self.detail_tabs.addTab(overview_tab, "📋 概览")

        fingerprint_tab = self._create_fingerprint_tab()
        self.detail_tabs.addTab(fingerprint_tab, "🔐 指纹信息")

        driver_tab = self._create_driver_tab()
        self.detail_tabs.addTab(driver_tab, "💾 驱动管理")

        lifecycle_tab = self._create_lifecycle_tab()
        self.detail_tabs.addTab(lifecycle_tab, "🔄 生命周期")

        protocol_tab = self._create_protocol_tab()
        self.detail_tabs.addTab(protocol_tab, "📡 协议分析")

        layout.addWidget(self.detail_tabs, 1)

        return panel

    def _create_overview_tab(self) -> QWidget:
        """创建概览选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info_group = QGroupBox("基本信息")
        info_layout = QGridLayout(info_group)

        info_layout.addWidget(QLabel("设备名称:"), 0, 0)
        self.info_name = QLabel("-")
        info_layout.addWidget(self.info_name, 0, 1)

        info_layout.addWidget(QLabel("设备类别:"), 0, 2)
        self.info_category = QLabel("-")
        info_layout.addWidget(self.info_category, 0, 3)

        info_layout.addWidget(QLabel("制造商:"), 1, 0)
        self.info_manufacturer = QLabel("-")
        info_layout.addWidget(self.info_manufacturer, 1, 1)

        info_layout.addWidget(QLabel("VID/PID:"), 1, 2)
        self.info_vidpid = QLabel("-")
        info_layout.addWidget(self.info_vidpid, 1, 3)

        info_layout.addWidget(QLabel("序列号:"), 2, 0)
        self.info_serial = QLabel("-")
        info_layout.addWidget(self.info_serial, 2, 1, 1, 3)

        info_layout.addWidget(QLabel("连接状态:"), 3, 0)
        self.info_connection = QLabel("-")
        info_layout.addWidget(self.info_connection, 3, 1)

        info_layout.addWidget(QLabel("最后活动:"), 3, 2)
        self.info_last_activity = QLabel("-")
        info_layout.addWidget(self.info_last_activity, 3, 3)

        layout.addWidget(info_group)

        lifecycle_group = QGroupBox("生命周期状态")
        lifecycle_layout = QHBoxLayout(lifecycle_group)

        self.lifecycle_stage = QLabel("未知")
        self.lifecycle_stage.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        lifecycle_layout.addWidget(self.lifecycle_stage)
        lifecycle_layout.addStretch()

        layout.addWidget(lifecycle_group)

        capability_group = QGroupBox("设备能力")
        capability_layout = QVBoxLayout(capability_group)
        self.capability_list = QListWidget()
        capability_layout.addWidget(self.capability_list)
        layout.addWidget(capability_group, 1)

        action_layout = QHBoxLayout()
        self.btn_connect = QPushButton("🔗 连接")
        self.btn_disconnect = QPushButton("🔌 断开")
        self.btn_identify = QPushButton("📍 定位设备")
        action_layout.addWidget(self.btn_connect)
        action_layout.addWidget(self.btn_disconnect)
        action_layout.addWidget(self.btn_identify)
        layout.addLayout(action_layout)

        return tab

    def _create_fingerprint_tab(self) -> QWidget:
        """创建指纹信息选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        fp_group = QGroupBox("硬件指纹")
        fp_layout = QGridLayout(fp_group)

        fp_layout.addWidget(QLabel("指纹ID:"), 0, 0)
        self.fp_id = QLabel("-")
        fp_layout.addWidget(self.fp_id, 0, 1)

        fp_layout.addWidget(QLabel("VID:"), 1, 0)
        self.fp_vid = QLabel("-")
        fp_layout.addWidget(self.fp_vid, 1, 1)

        fp_layout.addWidget(QLabel("PID:"), 1, 2)
        self.fp_pid = QLabel("-")
        fp_layout.addWidget(self.fp_pid, 1, 3)

        fp_layout.addWidget(QLabel("序列号:"), 2, 0)
        self.fp_serial = QLabel("-")
        fp_layout.addWidget(self.fp_serial, 2, 1, 1, 3)

        fp_layout.addWidget(QLabel("协议特征:"), 3, 0)
        self.fp_protocol = QLabel("-")
        fp_layout.addWidget(self.fp_protocol, 3, 1, 1, 3)

        fp_layout.addWidget(QLabel("匹配置信度:"), 4, 0)
        self.fp_confidence = QLabel("-")
        fp_layout.addWidget(self.fp_confidence, 4, 1)

        fp_layout.addWidget(QLabel("发现时间:"), 4, 2)
        self.fp_discovered = QLabel("-")
        fp_layout.addWidget(self.fp_discovered, 4, 3)

        layout.addWidget(fp_group)

        vis_group = QGroupBox("指纹可视化")
        vis_layout = QVBoxLayout(vis_group)
        self.fingerprint_display = QTextEdit()
        self.fingerprint_display.setReadOnly(True)
        self.fingerprint_display.setFont(QFont("Consolas", 8))
        self.fingerprint_display.setMaximumHeight(150)
        vis_layout.addWidget(self.fingerprint_display)
        layout.addWidget(vis_group)

        action_layout = QHBoxLayout()
        self.btn_copy_fingerprint = QPushButton("📋 复制指纹")
        self.btn_regenerate_fp = QPushButton("🔄 重新生成")
        action_layout.addWidget(self.btn_copy_fingerprint)
        action_layout.addWidget(self.btn_regenerate_fp)
        action_layout.addStretch()
        layout.addLayout(action_layout)

        layout.addStretch()
        return tab

    def _create_driver_tab(self) -> QWidget:
        """创建驱动管理选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        status_group = QGroupBox("驱动状态")
        status_layout = QGridLayout(status_group)

        status_layout.addWidget(QLabel("当前状态:"), 0, 0)
        self.driver_status = QLabel("未知")
        status_layout.addWidget(self.driver_status, 0, 1)

        status_layout.addWidget(QLabel("驱动版本:"), 0, 2)
        self.driver_version = QLabel("-")
        status_layout.addWidget(self.driver_version, 0, 3)

        status_layout.addWidget(QLabel("驱动路径:"), 1, 0)
        self.driver_path = QLabel("-")
        status_layout.addWidget(self.driver_path, 1, 1, 1, 3)

        layout.addWidget(status_group)

        available_group = QGroupBox("可用驱动")
        available_layout = QVBoxLayout(available_group)
        self.driver_list = QListWidget()
        available_layout.addWidget(self.driver_list)
        layout.addWidget(available_group, 1)

        driver_action_layout = QHBoxLayout()
        self.btn_install_driver = QPushButton("⬇️ 安装驱动")
        self.btn_update_driver = QPushButton("🔄 更新驱动")
        self.btn_uninstall_driver = QPushButton("🗑️ 卸载驱动")
        driver_action_layout.addWidget(self.btn_install_driver)
        driver_action_layout.addWidget(self.btn_update_driver)
        driver_action_layout.addWidget(self.btn_uninstall_driver)
        layout.addLayout(driver_action_layout)

        return tab

    def _create_lifecycle_tab(self) -> QWidget:
        """创建生命周期选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        stage_group = QGroupBox("当前阶段")
        stage_layout = QVBoxLayout(stage_group)

        self.lifecycle_display = QLabel("未知")
        self.lifecycle_display.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        self.lifecycle_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stage_layout.addWidget(self.lifecycle_display)

        self.lifecycle_description = QLabel("设备尚未被识别")
        self.lifecycle_description.setWordWrap(True)
        stage_layout.addWidget(self.lifecycle_description)

        layout.addWidget(stage_group)

        history_group = QGroupBox("生命周期历史")
        history_layout = QVBoxLayout(history_group)
        self.lifecycle_history = QListWidget()
        history_layout.addWidget(self.lifecycle_history)
        layout.addWidget(history_group, 1)

        transition_group = QGroupBox("阶段转换")
        transition_layout = QHBoxLayout(transition_group)

        self.btn_transition_prev = QPushButton("⬅️ 上一阶段")
        self.btn_transition_next = QPushButton("➡️ 下一阶段")
        transition_layout.addWidget(self.btn_transition_prev)
        transition_layout.addWidget(self.btn_transition_next)
        transition_layout.addStretch()
        layout.addWidget(transition_group)

        return tab

    def _create_protocol_tab(self) -> QWidget:
        """创建协议分析选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        proto_group = QGroupBox("协议信息")
        proto_layout = QGridLayout(proto_group)

        proto_layout.addWidget(QLabel("协议类型:"), 0, 0)
        self.proto_type = QLabel("-")
        proto_layout.addWidget(self.proto_type, 0, 1)

        proto_layout.addWidget(QLabel("版本:"), 0, 2)
        self.proto_version = QLabel("-")
        proto_layout.addWidget(self.proto_version, 0, 3)

        proto_layout.addWidget(QLabel("端点:"), 1, 0)
        self.proto_endpoint = QLabel("-")
        proto_layout.addWidget(self.proto_endpoint, 1, 1, 1, 3)

        layout.addWidget(proto_group)

        detail_group = QGroupBox("协议详情")
        detail_layout = QVBoxLayout(detail_group)
        self.protocol_detail = QTextEdit()
        self.protocol_detail.setReadOnly(True)
        self.protocol_detail.setFont(QFont("Consolas", 9))
        detail_layout.addWidget(self.protocol_detail)
        layout.addWidget(detail_group, 1)

        proto_action_layout = QHBoxLayout()
        self.btn_capture_proto = QPushButton("📡 捕获通信")
        self.btn_analyze_proto = QPushButton("🔍 分析协议")
        proto_action_layout.addWidget(self.btn_capture_proto)
        proto_action_layout.addWidget(self.btn_analyze_proto)
        proto_action_layout.addStretch()
        layout.addLayout(proto_action_layout)

        return tab

    def _init_connections(self):
        """初始化信号连接"""
        self.btn_scan.clicked.connect(self._on_scan_clicked)
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        self.btn_export.clicked.connect(self._on_export_clicked)
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        self.btn_disconnect.clicked.connect(self._on_disconnect_clicked)

    def _update_engine_status(self, connected: bool):
        """更新引擎状态"""
        if connected:
            self.engine_status_label.setText("🟢 引擎已连接")
            self.btn_scan.setEnabled(True)
            self.status_bar.showMessage("引擎就绪 - 准备扫描设备")
        else:
            self.engine_status_label.setText("🔴 引擎未连接")
            self.btn_scan.setEnabled(False)
            self.status_bar.showMessage("警告: Hardware Mind引擎未初始化")

    def _start_auto_detection(self):
        """启动自动检测"""
        if self.engine and hasattr(self.engine, 'start_detection'):
            self.status_bar.showMessage("正在启动设备检测...")
        self._simulate_device_discovery()

    def _simulate_device_discovery(self):
        """模拟设备发现"""
        mock_devices = [
            {
                'device_id': 'usb_001',
                'name': 'USB键盘',
                'category': 'USB_HID',
                'manufacturer': 'Logitech',
                'vid': '046D',
                'pid': 'C52B',
                'status': 'connected',
                'lifecycle': 'MATURITY'
            },
            {
                'device_id': 'usb_002',
                'name': 'USB鼠标',
                'category': 'USB_HID',
                'manufacturer': 'Razer',
                'vid': '1532',
                'pid': '0045',
                'status': 'connected',
                'lifecycle': 'GROWTH'
            },
            {
                'device_id': 'bt_001',
                'name': '蓝牙耳机',
                'category': 'BLUETOOTH',
                'manufacturer': 'Sony',
                'vid': '0D25',
                'pid': '3111',
                'status': 'connected',
                'lifecycle': 'MATURE'
            }
        ]

        for device in mock_devices:
            self._add_device(device)

        self.status_bar.showMessage(f"设备扫描完成 - 发现 {len(self.devices)} 个设备")

    def _add_device(self, device_info: dict):
        """添加设备到列表"""
        device_id = device_info.get('device_id')
        if device_id in self.devices:
            return

        self.devices[device_id] = device_info
        self._refresh_device_list()

    def _refresh_device_list(self):
        """刷新设备列表"""
        self.device_list.clear()
        search_text = self.device_search.text().lower()

        for device_id, device in self.devices.items():
            category = device.get('category', '')
            if not self._passes_filter(category):
                continue

            name = device.get('name', '').lower()
            manufacturer = device.get('manufacturer', '').lower()
            if search_text and search_text not in name and search_text not in manufacturer:
                continue

            icon = self._get_category_icon(category)
            status_icon = "🟢" if device.get('status') == 'connected' else "🔴"
            item = QListWidgetItem(f"{icon} {device.get('name', 'Unknown')} {status_icon}")
            item.setData(Qt.ItemDataRole.UserRole, device_id)
            self.device_list.addItem(item)

        self.device_count_label.setText(str(self.device_list.count()))

    def _get_category_icon(self, category: str) -> str:
        """获取类别图标"""
        icons = {
            'USB_HID': '⌨️',
            'USB_SERIAL': '🔌',
            'USB_MASS_STORAGE': '💾',
            'USB_VIDEO': '📷',
            'USB_AUDIO': '🔊',
            'BLUETOOTH': '📶',
            'WIFI': '📡',
            'SERIAL': '🔗',
        }
        return icons.get(category, '❓')

    def _passes_filter(self, category: str) -> bool:
        """检查设备是否通过过滤器"""
        if 'USB' in category:
            return self.filter_usb.isChecked()
        elif category == 'BLUETOOTH':
            return self.filter_bluetooth.isChecked()
        elif category == 'WIFI':
            return self.filter_wifi.isChecked()
        elif category == 'SERIAL':
            return self.filter_serial.isChecked()
        return True

    def _on_device_selected(self, item: QListWidgetItem):
        """设备列表项被选中"""
        device_id = item.data(Qt.ItemDataRole.UserRole)
        if device_id and device_id in self.devices:
            self._display_device_detail(self.devices[device_id])

    def _display_device_detail(self, device: dict):
        """显示设备详情"""
        self.info_name.setText(device.get('name', '-'))
        self.info_category.setText(device.get('category', '-'))
        self.info_manufacturer.setText(device.get('manufacturer', '-'))
        self.info_vidpid.setText(f"VID:{device.get('vid', '-')} / PID:{device.get('pid', '-')}")
        self.info_serial.setText(device.get('serial_number', device.get('vid', '-')))
        self.info_connection.setText(device.get('status', '-'))
        self.info_last_activity.setText(device.get('last_activity', '-'))

        lifecycle = device.get('lifecycle', 'UNKNOWN')
        self.lifecycle_stage.setText(lifecycle)
        self.lifecycle_display.setText(lifecycle)

        self.fp_id.setText(device.get('device_id', '-'))
        self.fp_vid.setText(device.get('vid', '-'))
        self.fp_pid.setText(device.get('pid', '-'))
        self.fp_serial.setText(device.get('serial_number', '-'))
        self.fp_confidence.setText(f"{device.get('confidence', 0) * 100:.1f}%")

        self.driver_status.setText(device.get('driver_status', '未安装'))

    def _on_search_changed(self, text: str):
        """搜索文本变化"""
        self._refresh_device_list()

    def _on_filter_changed(self):
        """过滤器变化"""
        self._refresh_device_list()

    def _on_scan_clicked(self):
        """扫描按钮点击"""
        self.status_bar.showMessage("正在扫描设备...")
        self._simulate_device_discovery()

    def _on_refresh_clicked(self):
        """刷新按钮点击"""
        self._refresh_device_list()
        self.status_bar.showMessage("已刷新设备列表")

    def _on_export_clicked(self):
        """导出按钮点击"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出设备信息", "", "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.devices, f, indent=2, ensure_ascii=False)
                self.status_bar.showMessage(f"已导出到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def _on_connect_clicked(self):
        """连接按钮点击"""
        self.status_bar.showMessage("正在连接设备...")

    def _on_disconnect_clicked(self):
        """断开按钮点击"""
        self.status_bar.showMessage("已断开设备连接")


def get_panel_info():
    """获取面板信息"""
    return {
        'name': '🎛️ 硬件智能',
        'class': HardwareMindPanel,
        'icon': '🎛️',
        'description': '通用硬件智能集成系统'
    }
