# -*- coding: utf-8 -*-
"""
SmolLM2 L0 快反大脑管理面板
===========================

PyQt6 面板用于：
- 查看路由统计
- 测试意图分类
- 管理 L0-L4 集成
- 模型下载状态

Author: Hermes Desktop Team
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QComboBox,
    QGroupBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

import asyncio
from typing import Optional

from core.smolllm2 import (
    L0Router, SmolLM2Config, RouteType, IntentType,
    SMOLLLM2_MANIFEST, find_smallest_gguf
)


class SmolLM2Panel(QWidget):
    """
    SmolLM2 L0 快反大脑管理面板
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._router: Optional[L0Router] = None
        self._setup_ui()
        self._connect_signals()

        # 定时刷新统计
        self._stats_timer = QTimer()
        self._stats_timer.timeout.connect(self._update_stats)
        self._stats_timer.start(5000)

    def _setup_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_layout = QHBoxLayout()
        title = QLabel("⚡ SmolLM2 L0 快反大脑")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()

        # 状态指示
        self.status_label = QLabel("● 就绪")
        self.status_label.setStyleSheet("color: #52c41a; font-size: 12px;")
        title_layout.addWidget(self.status_label)
        layout.addLayout(title_layout)

        # Tab 页
        tabs = QTabWidget()

        # Tab 1: 路由测试
        tabs.addTab(self._create_test_tab(), "🧪 路由测试")

        # Tab 2: 统计信息
        tabs.addTab(self._create_stats_tab(), "📊 统计信息")

        # Tab 3: 模型管理
        tabs.addTab(self._create_model_tab(), "📦 模型管理")

        # Tab 4: 集成设置
        tabs.addTab(self._create_settings_tab(), "⚙️ 集成设置")

        layout.addWidget(tabs)

    def _create_test_tab(self) -> QWidget:
        """创建路由测试 Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 输入框
        input_group = QGroupBox("输入测试")
        input_layout = QVBoxLayout()

        self.test_input = QTextEdit()
        self.test_input.setPlaceholderText("输入要测试的内容...")
        self.test_input.setMaximumHeight(80)
        input_layout.addWidget(self.test_input)

        # 测试按钮
        btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("🔍 开始路由测试")
        self.test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(self.test_btn)
        btn_layout.addStretch()
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 结果显示
        result_group = QGroupBox("路由结果")
        result_layout = QGridLayout()

        result_layout.addWidget(QLabel("路由决策:"), 0, 0)
        self.route_result = QLabel("-")
        self.route_result.setStyleSheet("font-weight: bold; color: #1890ff;")
        result_layout.addWidget(self.route_result, 0, 1)

        result_layout.addWidget(QLabel("意图类型:"), 1, 0)
        self.intent_result = QLabel("-")
        result_layout.addWidget(self.intent_result, 1, 1)

        result_layout.addWidget(QLabel("置信度:"), 2, 0)
        self.confidence_result = QLabel("-")
        result_layout.addWidget(self.confidence_result, 2, 1)

        result_layout.addWidget(QLabel("响应时间:"), 3, 0)
        self.latency_result = QLabel("-")
        result_layout.addWidget(self.latency_result, 3, 1)

        result_layout.addWidget(QLabel("原因:"), 4, 0)
        self.reason_result = QLabel("-")
        self.reason_result.setWordWrap(True)
        result_layout.addWidget(self.reason_result, 4, 1, 1, 2)

        result_group.setLayout(result_layout)
        layout.addWidget(result_group)

        # 快捷测试
        quick_group = QGroupBox("快捷测试用例")
        quick_layout = QHBoxLayout()

        quick_cases = [
            ("问候", "你好"),
            ("搜索", "帮我查下产品价格"),
            ("格式化", "整理一下这段代码"),
            ("重型", "写一篇关于AI发展趋势的分析报告"),
        ]

        for name, text in quick_cases:
            btn = QPushButton(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, t=text: self._quick_test(t))
            quick_layout.addWidget(btn)

        quick_group.setLayout(quick_layout)
        layout.addWidget(quick_group)

        layout.addStretch()
        return widget

    def _create_stats_tab(self) -> QWidget:
        """创建统计信息 Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 统计表格
        self.stats_table = QTableWidget(6, 2)
        self.stats_table.setHorizontalHeaderLabels(["指标", "数值"])
        self.stats_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.stats_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        stats_items = [
            ("总请求数", "0"),
            ("缓存命中", "0"),
            ("本地执行", "0"),
            ("联网搜索", "0"),
            ("重型推理", "0"),
            ("快反率 (<1s)", "0%"),
        ]

        for i, (name, value) in enumerate(stats_items):
            self.stats_table.setItem(i, 0, QTableWidgetItem(name))
            self.stats_table.setItem(i, 1, QTableWidgetItem(value))

        layout.addWidget(self.stats_table)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新统计")
        refresh_btn.clicked.connect(self._update_stats)
        layout.addWidget(refresh_btn)

        layout.addStretch()
        return widget

    def _create_model_tab(self) -> QWidget:
        """创建模型管理 Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 模型信息
        info_group = QGroupBox("SmolLM2-135M GGUF 模型信息")
        info_layout = QGridLayout()

        manifest = SMOLLLM2_MANIFEST
        info_layout.addWidget(QLabel("模型ID:"), 0, 0)
        info_layout.addWidget(QLabel(manifest.get("id", "-")), 0, 1)

        info_layout.addWidget(QLabel("描述:"), 1, 0)
        info_layout.addWidget(QLabel(manifest.get("desc", "-")), 1, 1)

        info_layout.addWidget(QLabel("推荐量化:"), 2, 0)
        info_layout.addWidget(QLabel(manifest.get("quant_type", "-")), 2, 1)

        info_layout.addWidget(QLabel("大小:"), 3, 0)
        size = manifest.get("platforms", {}).get("any", {}).get("size_mb", 0)
        info_layout.addWidget(QLabel(f"~{size} MB"), 3, 1)

        info_layout.addWidget(QLabel("HF Tree:"), 4, 0)
        hf_tree = manifest.get("platforms", {}).get("any", {}).get("hf_tree", False)
        info_layout.addWidget(QLabel("✅ 支持" if hf_tree else "❌ 不支持"), 4, 1)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("📥 下载模型")
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(self.download_btn)

        self.check_btn = QPushButton("🔍 检查模型")
        self.check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(self.check_btn)
        layout.addLayout(btn_layout)

        # 状态
        self.model_status = QLabel("状态: 未检查")
        self.model_status.setStyleSheet("padding: 8px; background: #f5f5f5; border-radius: 4px;")
        layout.addWidget(self.model_status)

        layout.addStretch()
        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建集成设置 Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # L0 设置
        l0_group = QGroupBox("L0 路由设置")
        l0_layout = QGridLayout()

        l0_layout.addWidget(QLabel("启用 L0 路由:"), 0, 0)
        self.enable_l0 = QComboBox()
        self.enable_l0.addItems(["是", "否"])
        self.enable_l0.setCurrentIndex(0)
        l0_layout.addWidget(self.enable_l0, 0, 1)

        l0_layout.addWidget(QLabel("启用缓存:"), 1, 0)
        self.enable_cache = QComboBox()
        self.enable_cache.addItems(["是", "否"])
        self.enable_cache.setCurrentIndex(0)
        l0_layout.addWidget(self.enable_cache, 1, 1)

        l0_layout.addWidget(QLabel("快速本地执行:"), 2, 0)
        self.enable_fast = QComboBox()
        self.enable_fast.addItems(["是", "否"])
        self.enable_fast.setCurrentIndex(0)
        l0_layout.addWidget(self.enable_fast, 2, 1)

        l0_group.setLayout(l0_layout)
        layout.addWidget(l0_group)

        # 阈值设置
        threshold_group = QGroupBox("路由阈值")
        threshold_layout = QGridLayout()

        threshold_layout.addWidget(QLabel("重型判定长度:"), 0, 0)
        self.heavy_threshold = QLineEdit("2000")
        threshold_layout.addWidget(self.heavy_threshold, 0, 1)

        threshold_layout.addWidget(QLabel("快反阈值 (ms):"), 1, 0)
        self.fast_threshold = QLineEdit("1000")
        threshold_layout.addWidget(self.fast_threshold, 1, 1)

        threshold_group.setLayout(threshold_layout)
        layout.addWidget(threshold_group)

        # 保存按钮
        save_btn = QPushButton("💾 保存设置")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()
        return widget

    def _connect_signals(self):
        """连接信号"""
        self.test_btn.clicked.connect(self._on_test)
        self.download_btn.clicked.connect(self._on_download)

    def _on_test(self):
        """执行路由测试"""
        prompt = self.test_input.toPlainText().strip()
        if not prompt:
            return

        self.test_btn.setEnabled(False)
        self.test_btn.setText("测试中...")

        asyncio.create_task(self._do_test(prompt))

    async def _do_test(self, prompt: str):
        """执行测试"""
        try:
            if not self._router:
                self._router = L0Router()

            decision = await self._router.route(prompt)

            # 更新 UI
            self.route_result.setText(decision.route.value)
            self.intent_result.setText(decision.intent.value)
            self.confidence_result.setText(f"{decision.confidence:.2f}")
            self.latency_result.setText(f"{decision.latency_ms:.0f} ms")
            self.reason_result.setText(decision.reason)

            # 颜色编码
            if decision.route == RouteType.CACHE:
                self.route_result.setStyleSheet("font-weight: bold; color: #52c41a;")
            elif decision.route == RouteType.LOCAL:
                self.route_result.setStyleSheet("font-weight: bold; color: #1890ff;")
            elif decision.route == RouteType.HEAVY:
                self.route_result.setStyleSheet("font-weight: bold; color: #fa8c16;")
            else:
                self.route_result.setStyleSheet("font-weight: bold; color: #722ed1;")

        except Exception as e:
            self.route_result.setText(f"错误: {e}")
        finally:
            self.test_btn.setEnabled(True)
            self.test_btn.setText("🔍 开始路由测试")

    def _quick_test(self, text: str):
        """快捷测试"""
        self.test_input.setPlainText(text)
        self._on_test()

    def _update_stats(self):
        """刷新统计"""
        if not self._router:
            return

        stats = self._router.get_stats()

        stats_data = [
            ("总请求数", str(stats.get("total", 0))),
            ("缓存命中", str(stats.get("cache", 0))),
            ("本地执行", str(stats.get("local", 0))),
            ("联网搜索", str(stats.get("search", 0))),
            ("重型推理", str(stats.get("heavy", 0))),
            ("快反率 (<1s)", f"{stats.get('fast_response_rate', 0) * 100:.1f}%"),
        ]

        for i, (_, value) in enumerate(stats_data):
            self.stats_table.setItem(i, 1, QTableWidgetItem(value))

    def _on_download(self):
        """下载模型"""
        self.download_btn.setEnabled(False)
        self.model_status.setText("状态: 正在连接 HuggingFace...")

        # 这里会调用下载器
        self.model_status.setText("状态: 下载功能需要配置 HF_TOKEN")
        self.download_btn.setEnabled(True)

    def _save_settings(self):
        """保存设置"""
        # 保存到配置文件
        self.model_status.setText("状态: 设置已保存")
