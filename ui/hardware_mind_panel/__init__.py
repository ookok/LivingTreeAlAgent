# -*- coding: utf-8 -*-
"""
🎨 通用硬件智能集成系统 UI 面板 - Hardware Mind Panel
=====================================================

8标签页设计:
- 🏠 总览: 系统状态、设备仪表盘
- 🔍 发现: 硬件检测、协议分析
- 📚 知识库: 手册管理、匹配状态
- ⚙️ 驱动: 驱动生成、安装状态
- 🎨 UI生成: 自动生成的界面预览
- 🧪 测试: 测试套件、验证结果
- 📊 设备: 统一设备管理、分组控制
- ⚙️ 设置: 系统配置

Author: Hermes Desktop Team
"""

import asyncio
import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QIcon, QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QScrollArea,
    QGroupBox, QFrame, QProgressBar, QStatusBar,
    QMenuBar, QMenu, QToolButton, QComboBox,
    QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QCardLayout, QStackedWidget, QSplitter,
    QProgressDialog, QMessageBox, QDialog,
    QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox,
    QTreeWidget, QTreeWidgetItem, QTabBar
)
from PyQt6.QtCharts import QChartView, QChart, QPieSeries, QBarSeries, QBarSet, QLineSeries
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

# 全局样式
PANEL_STYLE = """
/* Hardware Mind Panel 主题样式 */
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

QLabel#title {
    font-size: 18px;
    font-weight: bold;
    color: #2c3e50;
}

QLabel#subtitle {
    font-size: 14px;
    color: #7f8c8d;
}

QLabel#stat_value {
    font-size: 28px;
    font-weight: bold;
    color: #3498db;
}

QLabel#stat_label {
    font-size: 12px;
    color: #95a5a6;
}

QPushButton#primary {
    background-color: #3498db;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton#primary:hover {
    background-color: #2980b9;
}

QPushButton#success {
    background-color: #27ae60;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
}

QPushButton#danger {
    background-color: #e74c3c;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
}

QPushButton#warning {
    background-color: #f39c12;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
}

QGroupBox {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #3498db;
}

QTableWidget {
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    background: white;
    alternate-background-color: #f8f9fa;
}

QTableWidget::item {
    padding: 8px;
}

QTableWidget::item:selected {
    background-color: #3498db;
    color: white;
}

QHeaderView::section {
    background-color: #ecf0f1;
    padding: 8px;
    border: none;
    font-weight: bold;
}

QTabWidget::pane {
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    background: white;
}

QTabBar::tab {
    padding: 10px 20px;
    margin-right: 4px;
    background: #ecf0f1;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background: white;
    border-bottom: 2px solid #3498db;
}

QTabBar::tab:hover {
    background: #d5dbdb;
}

QProgressBar {
    border: none;
    border-radius: 4px;
    background: #ecf0f1;
    height: 20px;
    text-align: center;
}

QProgressBar::chunk {
    background: #3498db;
    border-radius: 4px;
}

QCard {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 16px;
}

QCard#device_card {
    border-left: 4px solid #3498db;
}

QCard#capability_card {
    border-left: 4px solid #27ae60;
}

QStatusBar {
    background: #ecf0f1;
    border-top: 1px solid #d5dbdb;
}

QTextEdit#log_viewer {
    background: #1e1e1e;
    color: #d4d4d4;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    border: none;
}

QListWidget#device_list {
    border: none;
    background: transparent;
}

QListWidget#device_list::item {
    padding: 12px;
    margin-bottom: 8px;
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
}

QListWidget#device_list::item:selected {
    border-left: 4px solid #3498db;
    background: #ebf5fb;
}
"""


class HardwareMindPanel(QWidget):
    """硬件智能集成系统主面板"""

    # 信号定义
    device_discovered = pyqtSignal(dict)
    driver_ready = pyqtSignal(str, dict)
    test_completed = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 引用外部engine (由main_window设置)
        self.phoenix_engine = None

        # 内部状态
        self.is_scanning = False
        self.devices: List[Dict] = []
        self.selected_device: Optional[Dict] = None

        # 初始化UI
        self._init_ui()

        # 模拟数据更新定时器
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_dashboard)
        self._update_timer.start(3000)

    def set_engine(self, engine):
        """设置硬件引擎"""
        self.phoenix_engine = engine

    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 顶部标题栏
        header = self._create_header()
        main_layout.addWidget(header)

        # 主标签页
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # 创建8个标签页
        self.tab_overview = self._create_overview_tab()
        self.tab_discovery = self._create_discovery_tab()
        self.tab_knowledge = self._create_knowledge_tab()
        self.tab_drivers = self._create_drivers_tab()
        self.tab_ui_gen = self._create_ui_gen_tab()
        self.tab_testing = self._create_testing_tab()
        self.tab_devices = self._create_devices_tab()
        self.tab_settings = self._create_settings_tab()

        self.tabs.addTab(self.tab_overview, "🏠 总览")
        self.tabs.addTab(self.tab_discovery, "🔍 发现")
        self.tabs.addTab(self.tab_knowledge, "📚 知识库")
        self.tabs.addTab(self.tab_drivers, "⚙️ 驱动")
        self.tabs.addTab(self.tab_ui_gen, "🎨 UI生成")
        self.tabs.addTab(self.tab_testing, "🧪 测试")
        self.tabs.addTab(self.tab_devices, "📊 设备")
        self.tabs.addTab(self.tab_settings, "⚙️ 设置")

        main_layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = self._create_status_bar()
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)

    def _create_header(self) -> QWidget:
        """创建标题栏"""
        header = QFrame()
        header.setStyleSheet("background: linear-gradient(135deg, #3498db 0%, #2c3e50 100%); padding: 16px;")
        header_layout = QHBoxLayout()

        # 标题
        title_container = QVBoxLayout()
        title_label = QLabel("🎛️ 硬件智能集成系统")
        title_label.setObjectName("title")
        title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")

        subtitle_label = QLabel("Hardware Mind - 自动发现、自动学习、自动集成")
        subtitle_label.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.8);")

        title_container.addWidget(title_label)
        title_container.addWidget(subtitle_label)

        # 控制按钮
        btn_container = QHBoxLayout()

        self.btn_scan = QPushButton("🔍 开始扫描")
        self.btn_scan.setObjectName("primary")
        self.btn_scan.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                color: white;
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.3);
            }
        """)
        self.btn_scan.clicked.connect(self._toggle_scan)

        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                color: white;
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 4px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.3);
            }
        """)
        self.btn_refresh.clicked.connect(self._refresh_data)

        btn_container.addWidget(self.btn_scan)
        btn_container.addWidget(self.btn_refresh)

        header_layout.addLayout(title_container)
        header_layout.addStretch()
        header_layout.addLayout(btn_container)

        header.setLayout(header_layout)
        return header

    def _create_status_bar(self) -> QStatusBar:
        """创建状态栏"""
        status_bar = QStatusBar()

        self.status_label = QLabel("🟢 系统就绪")
        status_bar.addWidget(self.status_label)

        status_bar.addPermanentWidget(QLabel(" | "))

        self.device_count_label = QLabel("设备: 0")
        status_bar.addPermanentWidget(self.device_count_label)

        status_bar.addPermanentWidget(QLabel(" | "))

        self.driver_count_label = QLabel("驱动: 0")
        status_bar.addPermanentWidget(self.driver_count_label)

        return status_bar

    def _create_overview_tab(self) -> QWidget:
        """创建总览标签页"""
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)

        # 统计卡片行
        stats_row = QHBoxLayout()

        self.stat_devices = self._create_stat_card("发现设备", "0", "device_icon", "#3498db")
        self.stat_manuals = self._create_stat_card("匹配手册", "0", "manual_icon", "#27ae60")
        self.stat_drivers = self._create_stat_card("生成驱动", "0", "driver_icon", "#f39c12")
        self.stat_tests = self._create_stat_card("测试通过", "0", "test_icon", "#9b59b6")

        stats_row.addWidget(self.stat_devices)
        stats_row.addWidget(self.stat_manuals)
        stats_row.addWidget(self.stat_drivers)
        stats_row.addWidget(self.stat_tests)
        layout.addLayout(stats_row)

        # 图表区域
        charts_row = QHBoxLayout()

        # 设备类型分布饼图
        chart_container = self._create_device_category_chart()
        charts_row.addWidget(chart_container, 1)

        # 生命周期状态
        lifecycle_container = self._create_lifecycle_status()
        charts_row.addWidget(lifecycle_container, 1)

        layout.addLayout(charts_row)

        # 最近设备列表
        recent_group = QGroupBox("最近发现的设备")
        recent_layout = QVBoxLayout()

        self.recent_device_list = QListWidget()
        self.recent_device_list.setObjectName("device_list")
        self.recent_device_list.itemClicked.connect(self._on_device_selected)

        recent_layout.addWidget(self.recent_device_list)
        recent_group.setLayout(recent_layout)
        layout.addWidget(recent_group)

        # 协议分布
        protocol_group = QGroupBox("协议分布")
        protocol_layout = QHBoxLayout()

        self.protocol_bars = QChartView()
        protocol_layout.addWidget(self.protocol_bars)
        protocol_group.setLayout(protocol_layout)
        layout.addWidget(protocol_group)

        layout.addStretch()
        container.setLayout(layout)
        tab.setWidget(container)

        return tab

    def _create_stat_card(self, title: str, value: str, icon: str, color: str) -> QFrame:
        """创建统计卡片"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 16px;
                border-left: 4px solid {color};
            }}
        """)
        layout = QVBoxLayout()

        icon_label = QLabel(f"<span style='font-size: 24px;'>{icon}</span>")
        value_label = QLabel(value)
        value_label.setObjectName("stat_value")
        value_label.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {color};")
        title_label = QLabel(title)
        title_label.setObjectName("stat_label")
        title_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")

        layout.addWidget(icon_label)
        layout.addWidget(value_label)
        layout.addWidget(title_label)
        layout.addStretch()

        card.setLayout(layout)
        return card

    def _create_device_category_chart(self) -> QFrame:
        """创建设备类型分布图"""
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; }")

        layout = QVBoxLayout()
        title = QLabel("📊 设备类型分布")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        layout.addWidget(title)

        # 模拟饼图
        self.category_chart = QChartView()
        self.category_chart.setMinimumHeight(200)
        layout.addWidget(self.category_chart)

        container.setLayout(layout)
        return container

    def _create_lifecycle_status(self) -> QFrame:
        """创建生命周期状态"""
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; }")

        layout = QVBoxLayout()
        title = QLabel("🔄 设备生命周期")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        layout.addWidget(title)

        # 生命周期流程
        lifecycle_flow = QHBoxLayout()

        stages = ["诞生", "生长", "成熟", "衰退", "死亡", "复活"]
        colors = ["#3498db", "#2ecc71", "#27ae60", "#f39c12", "#e74c3c", "#9b59b6"]

        for i, (stage, color) in enumerate(zip(stages, colors)):
            stage_frame = QFrame()
            stage_frame.setStyleSheet(f"""
                QFrame {{
                    background: {color};
                    border-radius: 4px;
                    padding: 8px;
                }}
            """)
            stage_layout = QVBoxLayout()
            stage_label = QLabel(stage)
            stage_label.setStyleSheet("color: white; font-weight: bold;")
            count_label = QLabel("0")
            count_label.setStyleSheet("color: white; font-size: 18px;")
            stage_layout.addWidget(stage_label)
            stage_layout.addWidget(count_label)
            stage_frame.setLayout(stage_layout)
            lifecycle_flow.addWidget(stage_frame)

            if i < len(stages) - 1:
                arrow = QLabel("→")
                arrow.setStyleSheet("color: #bdc3c7; font-size: 18px;")
                lifecycle_flow.addWidget(arrow)

        layout.addLayout(lifecycle_flow)

        container.setLayout(layout)
        return container

    def _create_discovery_tab(self) -> QWidget:
        """创建发现标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        # 控制栏
        control_bar = QHBoxLayout()

        self.btn_start_discovery = QPushButton("🚀 开始发现")
        self.btn_start_discovery.setObjectName("primary")
        self.btn_start_discovery.clicked.connect(self._start_discovery)

        self.btn_stop_discovery = QPushButton("🛑 停止")
        self.btn_stop_discovery.setEnabled(False)
        self.btn_stop_discovery.clicked.connect(self._stop_discovery)

        self.scan_progress = QProgressBar()
        self.scan_progress.setRange(0, 100)

        protocol_filter = QComboBox()
        protocol_filter.addItems(["全部协议", "USB", "蓝牙", "WiFi", "串口"])

        control_bar.addWidget(self.btn_start_discovery)
        control_bar.addWidget(self.btn_stop_discovery)
        control_bar.addWidget(self.scan_progress)
        control_bar.addWidget(protocol_filter)
        control_bar.addStretch()

        layout.addLayout(control_bar)

        # 协议检测面板
        protocols_group = QGroupBox("🔬 多协议检测状态")
        protocols_layout = QGridLayout()

        self.protocol_status = {}
        protocols = [
            ("USB", "🔌"),
            ("蓝牙", "📡"),
            ("WiFi", "📶"),
            ("串口", "🔧"),
            ("NFC", "📱"),
            ("I2C", "💾")
        ]

        for i, (name, icon) in enumerate(protocols):
            frame = self._create_protocol_card(name, icon)
            protocols_layout.addWidget(frame, i // 3, i % 3)
            self.protocol_status[name] = frame

        protocols_group.setLayout(protocols_layout)
        layout.addWidget(protocols_group)

        # 发现的设备列表
        devices_group = QGroupBox("📋 发现的设备")
        devices_layout = QVBoxLayout()

        self.discovery_table = QTableWidget()
        self.discovery_table.setColumnCount(6)
        self.discovery_table.setHorizontalHeaderLabels(["设备ID", "名称", "类型", "协议", "VID:PID", "状态"])
        self.discovery_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.discovery_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.discovery_table.itemClicked.connect(self._on_discovery_table_clicked)

        devices_layout.addWidget(self.discovery_table)
        devices_group.setLayout(devices_layout)
        layout.addWidget(devices_group)

        # 设备详情
        detail_group = QGroupBox("🔎 设备详情")
        detail_layout = QGridLayout()

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(150)
        detail_layout.addWidget(self.detail_text, 0, 0, 1, 2)

        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        tab.setLayout(layout)
        return tab

    def _create_protocol_card(self, name: str, icon: str) -> QFrame:
        """创建协议状态卡片"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        layout = QVBoxLayout()

        header = QHBoxLayout()
        icon_label = QLabel(f"<span style='font-size: 24px;'>{icon}</span>")
        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(icon_label)
        header.addWidget(name_label)
        header.addStretch()

        status_label = QLabel("⬤ 待机")
        status_label.setObjectName(f"status_{name}")
        status_label.setStyleSheet("color: #95a5a6;")

        devices_label = QLabel("发现 0 个设备")
        devices_label.setObjectName(f"count_{name}")

        layout.addLayout(header)
        layout.addWidget(status_label)
        layout.addWidget(devices_label)

        frame.setLayout(layout)
        return frame

    def _create_knowledge_tab(self) -> QWidget:
        """创建知识库标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        # 搜索栏
        search_bar = QHBoxLayout()

        search_input = QLineEdit()
        search_input.setPlaceholderText("🔍 搜索设备手册...")
        search_input.setStyleSheet("padding: 10px; border-radius: 4px; border: 1px solid #e0e0e0;")

        source_filter = QComboBox()
        source_filter.addItems(["全部来源", "官方", "社区", "AI生成"])

        search_bar.addWidget(search_input, 1)
        search_bar.addWidget(source_filter)
        layout.addLayout(search_bar)

        # 手册分类
        manual_types = QHBoxLayout()

        manual_type_buttons = [
            ("📦 USB设备", 0),
            ("📡 蓝牙设备", 0),
            ("🌐 网络设备", 0),
            ("🔧 串口设备", 0)
        ]

        for name, count in manual_type_buttons:
            btn = QPushButton(f"{name} ({count})")
            btn.setStyleSheet("""
                QPushButton {
                    background: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 4px;
                    padding: 10px 16px;
                }
                QPushButton:hover {
                    border-color: #3498db;
                }
            """)
            manual_types.addWidget(btn)

        manual_types.addStretch()
        layout.addLayout(manual_types)

        # 手册列表
        manuals_group = QGroupBox("📚 手册库")
        manuals_layout = QVBoxLayout()

        self.manual_table = QTableWidget()
        self.manual_table.setColumnCount(6)
        self.manual_table.setHorizontalHeaderLabels([
            "手册ID", "设备名称", "制造商", "来源", "验证状态", "可信度"
        ])
        self.manual_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        manuals_layout.addWidget(self.manual_table)

        manuals_group.setLayout(manuals_layout)
        layout.addWidget(manuals_group)

        # 手册详情预览
        preview_group = QGroupBox("📖 手册预览")
        preview_layout = QVBoxLayout()

        self.manual_preview = QTextEdit()
        self.manual_preview.setReadOnly(True)
        preview_layout.addWidget(self.manual_preview)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        tab.setLayout(layout)
        return tab

    def _create_drivers_tab(self) -> QWidget:
        """创建驱动标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        # 工具栏
        toolbar = QHBoxLayout()

        self.btn_generate_all = QPushButton("⚡ 生成所有驱动")
        self.btn_generate_all.setObjectName("primary")
        self.btn_generate_all.clicked.connect(self._generate_all_drivers)

        self.btn_install = QPushButton("📦 安装驱动")
        self.btn_install.setEnabled(False)

        self.btn_update = QPushButton("🔄 更新驱动")

        toolbar.addWidget(self.btn_generate_all)
        toolbar.addWidget(self.btn_install)
        toolbar.addWidget(self.btn_update)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 驱动列表
        drivers_group = QGroupBox("⚙️ 驱动管理")
        drivers_layout = QVBoxLayout()

        self.drivers_table = QTableWidget()
        self.drivers_table.setColumnCount(7)
        self.drivers_table.setHorizontalHeaderLabels([
            "驱动ID", "设备", "平台", "版本", "状态", "安装日期", "操作"
        ])
        self.drivers_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        drivers_layout.addWidget(self.drivers_table)

        drivers_group.setLayout(drivers_layout)
        layout.addWidget(drivers_group)

        # 代码预览
        code_group = QGroupBox("💻 生成的驱动代码")
        code_layout = QVBoxLayout()

        self.driver_code_view = QTextEdit()
        self.driver_code_view.setObjectName("log_viewer")
        self.driver_code_view.setReadOnly(True)
        code_layout.addWidget(self.driver_code_view)

        code_group.setLayout(code_layout)
        layout.addWidget(code_group)

        tab.setLayout(layout)
        return tab

    def _create_ui_gen_tab(self) -> QWidget:
        """创建UI生成标签页"""
        tab = QWidget()
        layout = QHBoxLayout()

        # 左侧: 设备列表
        left_panel = QFrame()
        left_panel.setMaximumWidth(300)
        left_panel.setStyleSheet("background: #f8f9fa; padding: 8px;")
        left_layout = QVBoxLayout()

        title = QLabel("📱 可视化设备列表")
        title.setStyleSheet("font-weight: bold; padding: 8px;")
        left_layout.addWidget(title)

        self.ui_device_list = QListWidget()
        self.ui_device_list.itemClicked.connect(self._on_ui_device_selected)
        left_layout.addWidget(self.ui_device_list)

        left_panel.setLayout(left_layout)
        layout.addWidget(left_panel)

        # 右侧: 生成的UI预览
        right_panel = QFrame()
        right_layout = QVBoxLayout()

        preview_title = QLabel("🎨 自动生成的UI界面")
        preview_title.setStyleSheet("font-weight: bold; padding: 8px;")
        right_layout.addWidget(preview_title)

        self.ui_preview = QFrame()
        self.ui_preview.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px dashed #bdc3c7;
                border-radius: 8px;
                min-height: 400px;
            }
        """)
        self.ui_preview_layout = QVBoxLayout()
        self.ui_preview.setLayout(self.ui_preview_layout)

        placeholder = QLabel("👈 从左侧选择一个设备以预览生成的UI")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #95a5a6; font-size: 14px; padding: 100px;")
        self.ui_preview_layout.addWidget(placeholder)

        right_layout.addWidget(self.ui_preview)
        right_panel.setLayout(right_layout)
        layout.addWidget(right_panel, 1)

        tab.setLayout(layout)
        return tab

    def _create_testing_tab(self) -> QWidget:
        """创建测试标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        # 控制栏
        control_bar = QHBoxLayout()

        self.btn_run_all_tests = QPushButton("▶️ 运行所有测试")
        self.btn_run_all_tests.setObjectName("primary")
        self.btn_run_all_tests.clicked.connect(self._run_all_tests)

        self.btn_run_selected = QPushButton("✅ 运行选中")
        self.btn_stop_tests = QPushButton("⏹ 停止")
        self.btn_stop_tests.setEnabled(False)

        test_filter = QComboBox()
        test_filter.addItems(["全部类型", "连接测试", "功能测试", "边界测试", "压力测试"])

        control_bar.addWidget(self.btn_run_all_tests)
        control_bar.addWidget(self.btn_run_selected)
        control_bar.addWidget(self.btn_stop_tests)
        control_bar.addWidget(test_filter)
        control_bar.addStretch()

        layout.addLayout(control_bar)

        # 测试套件
        splitter = QSplitter()

        # 左侧: 测试列表
        left_widget = QWidget()
        left_layout = QVBoxLayout()

        test_list_group = QGroupBox("📋 测试套件")
        test_list_layout = QVBoxLayout()

        self.test_table = QTableWidget()
        self.test_table.setColumnCount(4)
        self.test_table.setHorizontalHeaderLabels(["测试ID", "测试名称", "类型", "状态"])
        self.test_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        test_list_layout.addWidget(self.test_table)

        test_list_group.setLayout(test_list_layout)
        left_layout.addWidget(test_list_group)
        left_widget.setLayout(left_layout)

        # 右侧: 测试详情和结果
        right_widget = QWidget()
        right_layout = QVBoxLayout()

        # 测试结果
        results_group = QGroupBox("📊 测试结果统计")
        results_layout = QHBoxLayout()

        self.result_passed = QLabel("✅ 通过: 0")
        self.result_passed.setStyleSheet("color: #27ae60; font-size: 16px; font-weight: bold;")
        self.result_failed = QLabel("❌ 失败: 0")
        self.result_failed.setStyleSheet("color: #e74c3c; font-size: 16px; font-weight: bold;")
        self.result_skipped = QLabel("⏭ 跳过: 0")
        self.result_skipped.setStyleSheet("color: #95a5a6; font-size: 16px;")

        results_layout.addWidget(self.result_passed)
        results_layout.addWidget(self.result_failed)
        results_layout.addWidget(self.result_skipped)
        results_layout.addStretch()

        results_group.setLayout(results_layout)
        right_layout.addWidget(results_group)

        # 日志输出
        log_group = QGroupBox("📝 测试日志")
        log_layout = QVBoxLayout()

        self.test_log = QTextEdit()
        self.test_log.setObjectName("log_viewer")
        self.test_log.setReadOnly(True)
        self.test_log.setMaximumHeight(200)
        log_layout.addWidget(self.test_log)

        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)

        right_widget.setLayout(right_layout)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        tab.setLayout(layout)
        return tab

    def _create_devices_tab(self) -> QWidget:
        """创建设备标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        # 工具栏
        toolbar = QHBoxLayout()

        self.btn_add_group = QPushButton("📁 新建分组")
        self.btn_export = QPushButton("📤 导出配置")
        self.btn_import = QPushButton("📥 导入配置")
        self.btn_backup = QPushButton("💾 备份全部")

        toolbar.addWidget(self.btn_add_group)
        toolbar.addWidget(self.btn_export)
        toolbar.addWidget(self.btn_import)
        toolbar.addWidget(self.btn_backup)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 设备管理表格
        devices_group = QGroupBox("📦 统一设备管理器")
        devices_layout = QVBoxLayout()

        self.devices_table = QTableWidget()
        self.devices_table.setColumnCount(8)
        self.devices_table.setHorizontalHeaderLabels([
            "设备ID", "设备名称", "类别", "协议", "生命周期", "驱动状态", "在线状态", "操作"
        ])
        self.devices_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        devices_layout.addWidget(self.devices_table)

        devices_group.setLayout(devices_layout)
        layout.addWidget(devices_group)

        # 分组管理
        groups_group = QGroupBox("🏷️ 设备分组")
        groups_layout = QHBoxLayout()

        self.groups_tree = QTreeWidget()
        self.groups_tree.setHeaderLabels(["分组名称", "设备数"])
        groups_layout.addWidget(self.groups_tree)

        group_buttons = QVBoxLayout()
        group_buttons.addWidget(QPushButton("➕ 添加分组"))
        group_buttons.addWidget(QPushButton("✏️ 编辑"))
        group_buttons.addWidget(QPushButton("🗑️ 删除"))
        group_buttons.addStretch()

        groups_layout.addLayout(group_buttons)
        groups_group.setLayout(groups_layout)
        layout.addWidget(groups_group)

        tab.setLayout(layout)
        return tab

    def _create_settings_tab(self) -> QWidget:
        """创建设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        # 基本设置
        basic_group = QGroupBox("🔧 基本设置")
        basic_layout = QFormLayout()

        self.setting_auto_scan = QCheckBox("启动时自动扫描")
        self.setting_auto_scan.setChecked(True)
        self.setting_scan_interval = QSpinBox()
        self.setting_scan_interval.setRange(1, 60)
        self.setting_scan_interval.setValue(10)
        self.setting_scan_interval.setSuffix(" 秒")

        self.setting_auto_install = QCheckBox("自动安装驱动")
        self.setting_auto_install.setChecked(True)

        self.setting_auto_ui = QCheckBox("自动生成UI")
        self.setting_auto_ui.setChecked(True)

        basic_layout.addRow("自动扫描:", self.setting_auto_scan)
        basic_layout.addRow("扫描间隔:", self.setting_scan_interval)
        basic_layout.addRow("自动安装:", self.setting_auto_install)
        basic_layout.addRow("自动UI:", self.setting_auto_ui)

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # 协议设置
        protocol_group = QGroupBox("🔌 协议设置")
        protocol_layout = QFormLayout()

        self.setting_usb_enabled = QCheckBox("启用USB检测")
        self.setting_usb_enabled.setChecked(True)
        self.setting_bt_enabled = QCheckBox("启用蓝牙检测")
        self.setting_bt_enabled.setChecked(True)
        self.setting_wifi_enabled = QCheckBox("启用WiFi检测")
        self.setting_wifi_enabled.setChecked(True)
        self.setting_serial_enabled = QCheckBox("启用串口检测")
        self.setting_serial_enabled.setChecked(True)

        protocol_layout.addRow("USB:", self.setting_usb_enabled)
        protocol_layout.addRow("蓝牙:", self.setting_bt_enabled)
        protocol_layout.addRow("WiFi:", self.setting_wifi_enabled)
        protocol_layout.addRow("串口:", self.setting_serial_enabled)

        protocol_group.setLayout(protocol_layout)
        layout.addWidget(protocol_group)

        # 知识库设置
        knowledge_group = QGroupBox("📚 知识库设置")
        knowledge_layout = QFormLayout()

        self.setting_cloud_manual = QCheckBox("启用云端手册查询")
        self.setting_community = QCheckBox("启用社区手册")
        self.setting_ai_gen = QCheckBox("启用AI手册生成")

        knowledge_layout.addRow("云端手册:", self.setting_cloud_manual)
        knowledge_layout.addRow("社区贡献:", self.setting_community)
        knowledge_layout.addRow("AI生成:", self.setting_ai_gen)

        knowledge_group.setLayout(knowledge_layout)
        layout.addWidget(knowledge_group)

        # 测试设置
        test_group = QGroupBox("🧪 测试设置")
        test_layout = QFormLayout()

        self.setting_auto_test = QCheckBox("自动运行测试")
        self.setting_auto_test.setChecked(True)

        self.setting_test_timeout = QSpinBox()
        self.setting_test_timeout.setRange(1, 60)
        self.setting_test_timeout.setValue(30)
        self.setting_test_timeout.setSuffix(" 秒")

        test_layout.addRow("自动测试:", self.setting_auto_test)
        test_layout.addRow("超时时间:", self.setting_test_timeout)

        test_group.setLayout(test_layout)
        layout.addWidget(test_group)

        # 保存按钮
        save_layout = QHBoxLayout()
        save_layout.addStretch()

        btn_save = QPushButton("💾 保存设置")
        btn_save.setObjectName("primary")
        btn_reset = QPushButton("🔄 恢复默认")

        save_layout.addWidget(btn_reset)
        save_layout.addWidget(btn_save)

        layout.addLayout(save_layout)
        layout.addStretch()

        tab.setLayout(layout)
        return tab

    # ============================================================
    # 事件处理方法
    # ============================================================

    def _toggle_scan(self):
        """切换扫描状态"""
        if self.is_scanning:
            self._stop_discovery()
        else:
            self._start_discovery()

    def _start_discovery(self):
        """开始发现"""
        self.is_scanning = True
        self.btn_scan.setText("⏹ 停止扫描")
        self.btn_start_discovery.setEnabled(False)
        self.btn_stop_discovery.setEnabled(True)
        self.status_label.setText("🟡 正在扫描...")

        # 模拟扫描进度
        self._scan_progress_value = 0
        self._scan_timer = QTimer()
        self._scan_timer.timeout.connect(self._update_scan_progress)
        self._scan_timer.start(100)

    def _stop_discovery(self):
        """停止发现"""
        self.is_scanning = False
        self.btn_scan.setText("🔍 开始扫描")
        self.btn_start_discovery.setEnabled(True)
        self.btn_stop_discovery.setEnabled(False)
        self.status_label.setText("🟢 扫描已停止")

        if hasattr(self, '_scan_timer'):
            self._scan_timer.stop()

    def _update_scan_progress(self):
        """更新扫描进度"""
        self._scan_progress_value += 1
        if self._scan_progress_value > 100:
            self._scan_progress_value = 0

        self.scan_progress.setValue(self._scan_progress_value)

        # 模拟更新协议状态
        protocols = list(self.protocol_status.keys())
        active_index = (self._scan_progress_value // 20) % len(protocols)

        for i, name in enumerate(protocols):
            card = self.protocol_status[name]
            status_label = card.findChild(QLabel, f"status_{name}")
            count_label = card.findChild(QLabel, f"count_{name}")

            if i <= active_index:
                status_label.setText("● 扫描中")
                status_label.setStyleSheet("color: #f39c12;")
                count_label.setText(f"发现 {i + 1} 个设备")
            else:
                status_label.setText("⬤ 待机")
                status_label.setStyleSheet("color: #95a5a6;")

        # 模拟发现设备
        if self._scan_progress_value % 30 == 0:
            self._add_mock_device()

    def _add_mock_device(self):
        """添加模拟设备"""
        mock_devices = [
            {"id": "usb_046d_c52b", "name": "Logitech USB Receiver", "type": "USB HID", "protocol": "USB", "vid_pid": "046D:C52B"},
            {"id": "usb_0bda_5652", "name": "USB Camera", "type": "Video", "protocol": "USB", "vid_pid": "0BDA:5652"},
            {"id": "bt_001a7dda", "name": "JBL Flip 5", "type": "Bluetooth Audio", "protocol": "BT", "vid_pid": "N/A"},
            {"id": "wifi_192168", "name": "Smart Plug", "type": "IoT Device", "protocol": "MQTT", "vid_pid": "N/A"},
            {"id": "serial_com3", "name": "CP2102 USB-UART", "type": "USB Serial", "protocol": "Serial", "vid_pid": "10C4:EA60"},
        ]

        device = mock_devices[len(self.devices) % len(mock_devices)]
        self.devices.append(device)

        # 更新发现表格
        row = self.discovery_table.rowCount()
        self.discovery_table.insertRow(row)
        self.discovery_table.setItem(row, 0, QTableWidgetItem(device["id"]))
        self.discovery_table.setItem(row, 1, QTableWidgetItem(device["name"]))
        self.discovery_table.setItem(row, 2, QTableWidgetItem(device["type"]))
        self.discovery_table.setItem(row, 3, QTableWidgetItem(device["protocol"]))
        self.discovery_table.setItem(row, 4, QTableWidgetItem(device["vid_pid"]))
        self.discovery_table.setItem(row, 5, QTableWidgetItem("已发现"))

        # 更新设备计数
        self.device_count_label.setText(f"设备: {len(self.devices)}")

    def _on_device_selected(self, item: QListWidgetItem):
        """设备列表项被选中"""
        # 获取设备信息
        device_info = item.data(Qt.ItemDataRole.UserRole)
        if device_info:
            self.selected_device = device_info
            self.detail_text.setText(json.dumps(device_info, indent=2, ensure_ascii=False))

    def _on_discovery_table_clicked(self, item: QTableWidgetItem):
        """发现表格被点击"""
        row = item.row()
        device_id = self.discovery_table.item(row, 0).text()
        device_name = self.discovery_table.item(row, 1).text()
        device_type = self.discovery_table.item(row, 2).text()
        device_protocol = self.discovery_table.item(row, 3).text()
        device_vid_pid = self.discovery_table.item(row, 4).text()

        self.detail_text.setText(f"""设备详情:
================================
设备ID: {device_id}
名称: {device_name}
类型: {device_type}
协议: {device_protocol}
VID:PID: {device_vid_pid}

状态: 已连接
生命周期: 成熟期
驱动状态: 已安装
""")

        # 启用安装按钮
        self.btn_install.setEnabled(True)

    def _on_ui_device_selected(self, item: QListWidgetItem):
        """UI设备列表项被选中"""
        # 清除之前的预览
        for i in reversed(range(self.ui_preview_layout.count())):
            widget = self.ui_preview_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # 添加占位符（实际会根据设备生成UI组件）
        placeholder = QLabel("🎨 UI组件预览")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #3498db; font-size: 18px; padding: 20px;")
        self.ui_preview_layout.addWidget(placeholder)

        # 添加模拟UI组件
        components = [
            ("开关控制", "toggle"),
            ("亮度调节", "slider"),
            ("状态显示", "display"),
            ("操作按钮", "button")
        ]

        for name, comp_type in components:
            frame = QFrame()
            frame.setStyleSheet("""
                QFrame {
                    background: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    padding: 16px;
                    margin: 8px;
                }
            """)
            layout = QHBoxLayout()

            label = QLabel(name)
            label.setStyleSheet("font-weight: bold;")

            if comp_type == "toggle":
                toggle = QPushButton("开")
                toggle.setStyleSheet("""
                    QPushButton {
                        background: #27ae60;
                        color: white;
                        border: none;
                        border-radius: 12px;
                        padding: 6px 16px;
                    }
                """)
                layout.addWidget(label)
                layout.addWidget(toggle)
            elif comp_type == "slider":
                slider = QSlider()
                slider.setOrientation(Qt.Orientation.Horizontal)
                layout.addWidget(label)
                layout.addWidget(slider, 1)
            elif comp_type == "display":
                value = QLabel("数值: 42")
                value.setStyleSheet("color: #3498db; font-size: 16px;")
                layout.addWidget(label)
                layout.addWidget(value)
            else:
                btn = QPushButton("执行")
                btn.setObjectName("primary")
                layout.addWidget(label)
                layout.addWidget(btn)

            frame.setLayout(layout)
            self.ui_preview_layout.addWidget(frame)

    def _refresh_data(self):
        """刷新数据"""
        self.status_label.setText("🟢 正在刷新...")
        QTimer.singleShot(500, lambda: self.status_label.setText("🟢 系统就绪"))
        self._update_dashboard()

    def _update_dashboard(self):
        """更新仪表盘"""
        # 更新统计数据
        self.stat_devices.findChild(QLabel, "stat_value").setText(str(len(self.devices)))
        self.stat_manuals.findChild(QLabel, "stat_value").setText(str(min(len(self.devices), 5)))
        self.stat_drivers.findChild(QLabel, "stat_value").setText(str(min(len(self.devices), 3)))
        self.stat_tests.findChild(QLabel, "stat_value").setText("90%")

        # 更新最近设备列表
        self.recent_device_list.clear()
        for device in self.devices[-5:]:
            item = QListWidgetItem(f"📱 {device['name']} ({device['type']})")
            item.setData(Qt.ItemDataRole.UserRole, device)
            self.recent_device_list.addItem(item)

        # 更新设备管理表格
        self._update_devices_table()

        # 更新UI设备列表
        self.ui_device_list.clear()
        for device in self.devices:
            self.ui_device_list.addItem(f"📱 {device['name']}")

    def _update_devices_table(self):
        """更新设备管理表格"""
        self.devices_table.setRowCount(0)

        for device in self.devices:
            row = self.devices_table.rowCount()
            self.devices_table.insertRow(row)

            lifecycle = ["诞生", "生长", "成熟", "衰退", "死亡", "复活"][row % 6]
            status = ["待匹配", "已匹配", "已安装", "运行中"][row % 4]

            self.devices_table.setItem(row, 0, QTableWidgetItem(device["id"]))
            self.devices_table.setItem(row, 1, QTableWidgetItem(device["name"]))
            self.devices_table.setItem(row, 2, QTableWidgetItem(device["type"]))
            self.devices_table.setItem(row, 3, QTableWidgetItem(device["protocol"]))
            self.devices_table.setItem(row, 4, QTableWidgetItem(lifecycle))
            self.devices_table.setItem(row, 5, QTableWidgetItem(status))
            self.devices_table.setItem(row, 6, QTableWidgetItem("🟢 在线"))

            btn_view = QPushButton("查看")
            btn_view.setStyleSheet("""
                QPushButton {
                    background: #3498db;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                }
            """)
            self.devices_table.setCellWidget(row, 7, btn_view)

    def _generate_all_drivers(self):
        """生成所有驱动"""
        self.status_label.setText("🟡 正在生成驱动...")

        # 模拟生成过程
        self.driver_code_view.clear()
        sample_code = '''// 自动生成的驱动代码
// 设备: Logitech USB Receiver
// 生成时间: {time}

#include <usbhelper.h>
#include <hidapi.h>

class LogitechReceiverDriver {{
private:
    hid_device* handle;

public:
    int initialize() {{
        handle = hid_open(0x046D, 0xC52B, NULL);
        return handle ? 0 : -1;
    }}

    int send_data(uint8_t* data, size_t len) {{
        return hid_write(handle, data, len);
    }}

    int read_data(uint8_t* buf, size_t len) {{
        return hid_read(handle, buf, len);
    }}
}};
'''.format(time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        self.driver_code_view.setPlainText(sample_code)

        # 更新驱动表格
        self.drivers_table.setRowCount(0)
        for device in self.devices[:3]:
            row = self.drivers_table.rowCount()
            self.drivers_table.insertRow(row)
            self.drivers_table.setItem(row, 0, QTableWidgetItem(f"driver_{device['id']}"))
            self.drivers_table.setItem(row, 1, QTableWidgetItem(device["name"]))
            self.drivers_table.setItem(row, 2, QTableWidgetItem("Windows"))
            self.drivers_table.setItem(row, 3, QTableWidgetItem("1.0.0"))
            self.drivers_table.setItem(row, 4, QTableWidgetItem("已生成"))
            self.drivers_table.setItem(row, 5, QTableWidgetItem(datetime.now().strftime("%Y-%m-%d")))
            self.drivers_table.setItem(row, 6, QTableWidgetItem("查看 | 安装"))

        self.driver_count_label.setText(f"驱动: {min(len(self.devices), 3)}")
        self.status_label.setText("🟢 驱动生成完成")

    def _run_all_tests(self):
        """运行所有测试"""
        self.test_log.clear()
        self.test_log.append("▶️ 开始运行测试套件...\n")

        # 模拟测试结果
        test_cases = [
            ("conn_usb_001", "USB连接测试", "connection"),
            ("cap_hid_001", "HID输入测试", "capability"),
            ("cap_video_001", "视频流测试", "capability"),
            ("bound_baud_001", "波特率边界测试", "boundary"),
            ("stress_001", "压力测试", "stress"),
        ]

        self.test_table.setRowCount(0)
        passed = 0
        failed = 0

        for test_id, name, test_type in test_cases:
            row = self.test_table.rowCount()
            self.test_table.insertRow(row)
            self.test_table.setItem(row, 0, QTableWidgetItem(test_id))
            self.test_table.setItem(row, 1, QTableWidgetItem(name))
            self.test_table.setItem(row, 2, QTableWidgetItem(test_type))

            # 模拟测试结果
            import random
            result = "passed" if random.random() > 0.2 else "failed"
            status_item = QTableWidgetItem("✅ 通过" if result == "passed" else "❌ 失败")
            status_item.setForeground(Qt.GlobalColor.green if result == "passed" else Qt.GlobalColor.red)
            self.test_table.setItem(row, 3, status_item)

            if result == "passed":
                passed += 1
            else:
                failed += 1

            self.test_log.append(f"{'✅' if result == 'passed' else '❌'} {name}: {result}")

        self.result_passed.setText(f"✅ 通过: {passed}")
        self.result_failed.setText(f"❌ 失败: {failed}")
        self.result_skipped.setText(f"⏭ 跳过: 0")

        self.test_log.append(f"\n📊 测试完成: {passed}/{len(test_cases)} 通过")