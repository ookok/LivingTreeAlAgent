# -*- coding: utf-8 -*-
"""
🎨 Python智能日志分析系统 UI 面板 - Python Mind Panel
=====================================================

8标签页设计:
- 🏠 总览: 系统状态、分析仪表盘
- 🔍 分析: 错误分析、根因分析
- 🛠️ 修复: 修复建议、代码补丁
- 📝 测试: 测试用例生成
- 📊 模式: 错误模式库
- 📜 历史: 分析历史、报告
- 💾 知识库: 修复经验库
- ⚙️ 设置: 系统配置

Author: Hermes Desktop Team
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QScrollArea,
    QGroupBox, QFrame, QProgressBar, QStatusBar,
    QMenuBar, QMenu, QTextEdit, QListWidget, QListWidgetItem,
    QSplitter, QComboBox, QLineEdit, QSpinBox, QCheckBox,
    QFormLayout, QTreeWidget, QTreeWidgetItem, QProgressDialog,
    QMessageBox, QDialog, QFileDialog, QMainWindow,
    QSyntaxHighlighter, QPlainTextEdit
)
from PyQt6.QtCharts import QChartView, QChart, QPieSeries, QBarSeries, QBarSet, QLineSeries
from PyQt6.QtWebEngineWidgets import QWebEngineView

# 全局样式
PANEL_STYLE = """
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

QLabel#title {
    font-size: 18px;
    font-weight: bold;
    color: #2c3e50;
}

QGroupBox {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px;
    font-weight: bold;
    background: white;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #e74c3c;
}

QTableWidget {
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    background: white;
}

QTabWidget::pane {
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    background: white;
    padding: 8px;
}

QTextEdit#log_viewer {
    background: #1e1e1e;
    color: #d4d4d4;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    border: none;
    padding: 8px;
}

QTextEdit#code_editor {
    background: #f8f9fa;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    border: 1px solid #e0e0e0;
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

QStatusBar {
    background: #ecf0f1;
    border-top: 1px solid #d5dbdb;
}

QListWidget#analysis_list {
    border: none;
    background: transparent;
}

QListWidget#analysis_list::item {
    padding: 12px;
    margin-bottom: 8px;
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
}

QListWidget#analysis_list::item:selected {
    border-left: 4px solid #e74c3c;
    background: #fdf2f2;
}
"""


class PythonMindPanel(QWidget):
    """Python智能日志分析系统主面板"""

    # 信号定义
    analysis_started = pyqtSignal()
    analysis_completed = pyqtSignal(dict)
    fix_applied = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 引用外部engine (由main_window设置)
        self.python_mind_engine = None

        # 内部状态
        self.current_analysis: Optional[Dict] = None
        self.current_report: Optional[Dict] = None
        self.analysis_history: List[Dict] = []

        # 初始化UI
        self._init_ui()

        # 模拟数据
        self._init_mock_data()

        # 更新定时器
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_dashboard)
        self._update_timer.start(5000)

    def set_engine(self, engine):
        """设置Python Mind引擎"""
        self.python_mind_engine = engine

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

        self.tab_overview = self._create_overview_tab()
        self.tab_analysis = self._create_analysis_tab()
        self.tab_fixes = self._create_fixes_tab()
        self.tab_tests = self._create_tests_tab()
        self.tab_patterns = self._create_patterns_tab()
        self.tab_history = self._create_history_tab()
        self.tab_knowledge = self._create_knowledge_tab()
        self.tab_settings = self._create_settings_tab()

        self.tabs.addTab(self.tab_overview, "🏠 总览")
        self.tabs.addTab(self.tab_analysis, "🔍 分析")
        self.tabs.addTab(self.tab_fixes, "🛠️ 修复")
        self.tabs.addTab(self.tab_tests, "📝 测试")
        self.tabs.addTab(self.tab_patterns, "📊 模式")
        self.tabs.addTab(self.tab_history, "📜 历史")
        self.tabs.addTab(self.tab_knowledge, "💾 知识库")
        self.tabs.addTab(self.tab_settings, "⚙️ 设置")

        main_layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = self._create_status_bar()
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)

    def _create_header(self) -> QWidget:
        """创建标题栏"""
        header = QFrame()
        header.setStyleSheet("""
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            padding: 16px;
        """)
        header_layout = QHBoxLayout()

        # 标题
        title_container = QVBoxLayout()
        title_label = QLabel("🐍 Python智能日志分析系统")
        title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")

        subtitle_label = QLabel("Python Mind - 从错误中学习，从日志中洞察，自动诊断，智能修复")
        subtitle_label.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.8);")

        title_container.addWidget(title_label)
        title_container.addWidget(subtitle_label)

        # 控制按钮
        btn_container = QHBoxLayout()

        self.btn_analyze = QPushButton("🔍 开始分析")
        self.btn_analyze.setStyleSheet("""
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
        self.btn_analyze.clicked.connect(self._start_analysis)

        self.btn_generate_report = QPushButton("📄 生成报告")
        self.btn_generate_report.setStyleSheet("""
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
        self.btn_generate_report.clicked.connect(self._generate_report)

        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_clear.setStyleSheet("""
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
        self.btn_clear.clicked.connect(self._clear_history)

        btn_container.addWidget(self.btn_analyze)
        btn_container.addWidget(self.btn_generate_report)
        btn_container.addWidget(self.btn_clear)

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

        self.analysis_count_label = QLabel("分析: 0")
        status_bar.addPermanentWidget(self.analysis_count_label)

        status_bar.addPermanentWidget(QLabel(" | "))

        self.pattern_count_label = QLabel("模式: 0")
        status_bar.addPermanentWidget(self.pattern_count_label)

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

        self.stat_analyzed = self._create_stat_card("已分析错误", "0", "#e74c3c")
        self.stat_patterns = self._create_stat_card("匹配模式", "0", "#3498db")
        self.stat_fixes = self._create_stat_card("生成修复", "0", "#27ae60")
        self.stat_reports = self._create_stat_card("生成报告", "0", "#9b59b6")

        stats_row.addWidget(self.stat_analyzed)
        stats_row.addWidget(self.stat_patterns)
        stats_row.addWidget(self.stat_fixes)
        stats_row.addWidget(self.stat_reports)
        layout.addLayout(stats_row)

        # 错误分布图表
        chart_row = QHBoxLayout()

        error_dist_chart = self._create_error_distribution_chart()
        chart_row.addWidget(error_dist_chart, 1)

        severity_chart = self._create_severity_chart()
        chart_row.addWidget(severity_chart, 1)

        layout.addLayout(chart_row)

        # 最近分析列表
        recent_group = QGroupBox("📋 最近分析")
        recent_layout = QVBoxLayout()

        self.recent_analysis_list = QListWidget()
        self.recent_analysis_list.setObjectName("analysis_list")
        self.recent_analysis_list.itemClicked.connect(self._on_analysis_selected)

        recent_layout.addWidget(self.recent_analysis_list)
        recent_group.setLayout(recent_layout)
        layout.addWidget(recent_group)

        layout.addStretch()
        container.setLayout(layout)
        tab.setWidget(container)

        return tab

    def _create_stat_card(self, title: str, value: str, color: str) -> QFrame:
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

        value_label = QLabel(value)
        value_label.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {color};")

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")

        layout.addWidget(value_label)
        layout.addWidget(title_label)
        layout.addStretch()

        card.setLayout(layout)
        return card

    def _create_error_distribution_chart(self) -> QFrame:
        """创建错误分布图表"""
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; }")

        layout = QVBoxLayout()
        title = QLabel("📊 错误类型分布")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        layout.addWidget(title)

        self.error_dist_chart = QChartView()
        self.error_dist_chart.setMinimumHeight(200)
        layout.addWidget(self.error_dist_chart)

        container.setLayout(layout)
        return container

    def _create_severity_chart(self) -> QFrame:
        """创建严重性图表"""
        container = QFrame()
        container.setStyleSheet("QFrame { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; }")

        layout = QVBoxLayout()
        title = QLabel("🔴 严重性分布")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        layout.addWidget(title)

        self.severity_chart = QChartView()
        self.severity_chart.setMinimumHeight(200)
        layout.addWidget(self.severity_chart)

        container.setLayout(layout)
        return container

    def _create_analysis_tab(self) -> QWidget:
        """创建分析标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        # 控制栏
        control_bar = QHBoxLayout()

        self.btn_run_analysis = QPushButton("🚀 运行分析")
        self.btn_run_analysis.setObjectName("primary")
        self.btn_run_analysis.clicked.connect(self._run_analysis)

        self.btn_paste_error = QPushButton("📋 粘贴错误")
        self.btn_paste_error.clicked.connect(self._paste_error)

        self.btn_export_analysis = QPushButton("📤 导出分析")
        self.btn_export_analysis.clicked.connect(self._export_analysis)

        control_bar.addWidget(self.btn_run_analysis)
        control_bar.addWidget(self.btn_paste_error)
        control_bar.addWidget(self.btn_export_analysis)
        control_bar.addStretch()

        layout.addLayout(control_bar)

        # 分析结果区域
        splitter = QSplitter()

        # 左侧: 错误输入
        left_widget = QWidget()
        left_layout = QVBoxLayout()

        input_group = QGroupBox("📝 错误日志输入")
        input_layout = QVBoxLayout()

        self.error_input = QTextEdit()
        self.error_input.setObjectName("log_viewer")
        self.error_input.setPlaceholderText("在此粘贴错误日志或traceback...")
        self.error_input.setMinimumHeight(200)
        input_layout.addWidget(self.error_input)

        input_group.setLayout(input_layout)
        left_layout.addWidget(input_group)

        # 分析进度
        self.analysis_progress = QProgressBar()
        self.analysis_progress.setRange(0, 100)
        self.analysis_progress.setValue(0)
        left_layout.addWidget(self.analysis_progress)

        left_widget.setLayout(left_layout)

        # 右侧: 分析结果
        right_widget = QWidget()
        right_layout = QVBoxLayout()

        result_group = QGroupBox("📊 分析结果")
        result_layout = QVBoxLayout()

        self.analysis_result_text = QTextEdit()
        self.analysis_result_text.setReadOnly(True)
        self.analysis_result_text.setMinimumHeight(200)
        result_layout.addWidget(self.analysis_result_text)

        result_group.setLayout(result_layout)
        right_layout.addWidget(result_group)

        # 根因分析
        root_cause_group = QGroupBox("🔬 根因分析")
        root_cause_layout = QVBoxLayout()

        self.root_cause_text = QTextEdit()
        self.root_cause_text.setReadOnly(True)
        self.root_cause_text.setMaximumHeight(150)
        root_cause_layout.addWidget(self.root_cause_text)

        root_cause_group.setLayout(root_cause_layout)
        right_layout.addWidget(root_cause_group)

        right_widget.setLayout(right_layout)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        tab.setLayout(layout)
        return tab

    def _create_fixes_tab(self) -> QWidget:
        """创建修复标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        # 工具栏
        toolbar = QHBoxLayout()

        self.btn_generate_fixes = QPushButton("⚡ 生成修复")
        self.btn_generate_fixes.setObjectName("primary")
        self.btn_generate_fixes.clicked.connect(self._generate_fixes)

        self.btn_apply_fix = QPushButton("✅ 应用修复")
        self.btn_apply_fix.setEnabled(False)

        self.btn_copy_fix = QPushButton("📋 复制修复")
        self.btn_copy_fix.clicked.connect(self._copy_fix)

        toolbar.addWidget(self.btn_generate_fixes)
        toolbar.addWidget(self.btn_apply_fix)
        toolbar.addWidget(self.btn_copy_fix)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 修复列表
        fixes_group = QGroupBox("🛠️ 修复建议列表")
        fixes_layout = QVBoxLayout()

        self.fixes_table = QTableWidget()
        self.fixes_table.setColumnCount(5)
        self.fixes_table.setHorizontalHeaderLabels(["修复ID", "标题", "类型", "置信度", "操作"])
        self.fixes_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        fixes_layout.addWidget(self.fixes_table)

        fixes_group.setLayout(fixes_layout)
        layout.addWidget(fixes_group)

        # 代码对比
        code_group = QGroupBox("💻 代码对比")
        code_layout = QGridLayout()

        # 原始代码
        original_label = QLabel("原始代码")
        original_label.setStyleSheet("font-weight: bold; color: #e74c3c;")
        code_layout.addWidget(original_label, 0, 0)

        self.original_code = QTextEdit()
        self.original_code.setObjectName("code_editor")
        self.original_code.setReadOnly(True)
        code_layout.addWidget(self.original_code, 1, 0)

        # 修复代码
        fixed_label = QLabel("修复代码")
        fixed_label.setStyleSheet("font-weight: bold; color: #27ae60;")
        code_layout.addWidget(fixed_label, 0, 1)

        self.fixed_code = QTextEdit()
        self.fixed_code.setObjectName("code_editor")
        code_layout.addWidget(self.fixed_code, 1, 1)

        code_group.setLayout(code_layout)
        layout.addWidget(code_group)

        tab.setLayout(layout)
        return tab

    def _create_tests_tab(self) -> QWidget:
        """创建测试标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        # 控制栏
        control_bar = QHBoxLayout()

        self.btn_generate_tests = QPushButton("🧪 生成测试")
        self.btn_generate_tests.setObjectName("primary")
        self.btn_generate_tests.clicked.connect(self._generate_tests)

        self.btn_run_tests = QPushButton("▶️ 运行测试")
        self.btn_run_tests.setEnabled(False)

        self.btn_save_tests = QPushButton("💾 保存测试")

        control_bar.addWidget(self.btn_generate_tests)
        control_bar.addWidget(self.btn_run_tests)
        control_bar.addWidget(self.btn_save_tests)
        control_bar.addStretch()

        layout.addLayout(control_bar)

        # 测试列表
        tests_group = QGroupBox("📝 生成的测试用例")
        tests_layout = QVBoxLayout()

        self.tests_table = QTableWidget()
        self.tests_table.setColumnCount(4)
        self.tests_table.setHorizontalHeaderLabels(["测试ID", "测试名称", "类型", "状态"])
        self.tests_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tests_layout.addWidget(self.tests_table)

        tests_group.setLayout(tests_layout)
        layout.addWidget(tests_group)

        # 测试代码预览
        test_code_group = QGroupBox("📄 测试代码")
        test_code_layout = QVBoxLayout()

        self.test_code_view = QTextEdit()
        self.test_code_view.setObjectName("code_editor")
        test_code_view_label = QLabel("选择一个测试查看代码")
        test_code_view_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        test_code_view_label.setStyleSheet("color: #95a5a6; padding: 50px;")
        self.test_code_view_layout = QVBoxLayout()
        self.test_code_view_layout.addWidget(test_code_view_label)
        test_code_view_container = QWidget()
        test_code_view_container.setLayout(self.test_code_view_layout)
        test_code_layout.addWidget(self.test_code_view)

        test_code_group.setLayout(test_code_layout)
        layout.addWidget(test_code_group)

        tab.setLayout(layout)
        return tab

    def _create_patterns_tab(self) -> QWidget:
        """创建模式标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        # 搜索栏
        search_bar = QHBoxLayout()

        self.pattern_search = QLineEdit()
        self.pattern_search.setPlaceholderText("🔍 搜索错误模式...")
        self.pattern_search.textChanged.connect(self._filter_patterns)

        category_filter = QComboBox()
        category_filter.addItems(["全部", "语法错误", "导入错误", "类型错误", "IO错误", "其他"))

        search_bar.addWidget(self.pattern_search, 1)
        search_bar.addWidget(category_filter)
        layout.addLayout(search_bar)

        # 模式列表
        patterns_group = QGroupBox("📊 错误模式库")
        patterns_layout = QVBoxLayout()

        self.patterns_table = QTableWidget()
        self.patterns_table.setColumnCount(6)
        self.patterns_table.setHorizontalHeaderLabels(["模式ID", "名称", "类别", "严重性", "匹配次数", "示例"])
        self.patterns_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        patterns_layout.addWidget(self.patterns_table)

        patterns_group.setLayout(patterns_layout)
        layout.addWidget(patterns_group)

        # 模式详情
        pattern_detail_group = QGroupBox("📖 模式详情")
        pattern_detail_layout = QVBoxLayout()

        self.pattern_detail_text = QTextEdit()
        self.pattern_detail_text.setReadOnly True
        pattern_detail_layout.addWidget(self.pattern_detail_text)

        pattern_detail_group.setLayout(pattern_detail_layout)
        layout.addWidget(pattern_detail_group)

        tab.setLayout(layout)
        return tab

    def _create_history_tab(self) -> QWidget:
        """创建历史标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        # 工具栏
        toolbar = QHBoxLayout()

        self.btn_view_report = QPushButton("📄 查看报告")
        self.btn_view_report.clicked.connect(self._view_report)

        self.btn_delete_history = QPushButton("🗑️ 删除")
        self.btn_delete_history.clicked.connect(self._delete_history)

        self.btn_export_all = QPushButton("📤 导出全部")
        self.btn_export_all.clicked.connect(self._export_all_reports)

        toolbar.addWidget(self.btn_view_report)
        toolbar.addWidget(self.btn_delete_history)
        toolbar.addWidget(self.btn_export_all)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 历史列表
        history_group = QGroupBox("📜 分析历史")
        history_layout = QVBoxLayout()

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(["报告ID", "时间", "错误类型", "严重性", "修复数", "状态"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        history_layout.addWidget(self.history_table)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        # 报告预览
        report_preview_group = QGroupBox("📋 报告预览")
        report_preview_layout = QVBoxLayout()

        self.report_preview = QTextEdit()
        self.report_preview.setReadOnly True
        report_preview_layout.addWidget(self.report_preview)

        report_preview_group.setLayout(report_preview_layout)
        layout.addWidget(report_preview_group)

        tab.setLayout(layout)
        return tab

    def _create_knowledge_tab(self) -> QWidget:
        """创建知识库标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        # 搜索栏
        search_bar = QHBoxLayout()

        self.knowledge_search = QLineEdit()
        self.knowledge_search.setPlaceholderText("🔍 搜索知识库...")

        self.btn_add_knowledge = QPushButton("➕ 添加知识")
        self.btn_add_knowledge.clicked.connect(self._add_knowledge)

        search_bar.addWidget(self.knowledge_search, 1)
        search_bar.addWidget(self.btn_add_knowledge)
        layout.addLayout(search_bar)

        # 知识分类
        categories = QHBoxLayout()

        category_buttons = [
            ("🔧 常见错误", 15),
            ("💡 最佳实践", 8),
            ("📚 修复手册", 12),
            ("⚠️ 注意事项", 6)
        ]

        for name, count in category_buttons:
            btn = QPushButton(f"{name} ({count})")
            btn.setStyleSheet("""
                QPushButton {
                    background: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 4px;
                    padding: 10px 16px;
                }
                QPushButton:hover {
                    border-color: #e74c3c;
                }
            """)
            categories.addWidget(btn)

        categories.addStretch()
        layout.addLayout(categories)

        # 知识列表
        knowledge_group = QGroupBox("💾 修复经验库")
        knowledge_layout = QVBoxLayout()

        self.knowledge_tree = QTreeWidget()
        self.knowledge_tree.setHeaderLabels(["知识条目", "类型", "使用次数"])
        knowledge_layout.addWidget(self.knowledge_tree)

        knowledge_group.setLayout(knowledge_layout)
        layout.addWidget(knowledge_group)

        # 知识详情
        knowledge_detail_group = QGroupBox("📖 知识详情")
        knowledge_detail_layout = QVBoxLayout()

        self.knowledge_detail = QTextEdit()
        self.knowledge_detail.setReadOnly True
        knowledge_detail_layout.addWidget(self.knowledge_detail)

        knowledge_detail_group.setLayout(knowledge_detail_layout)
        layout.addWidget(knowledge_detail_group)

        tab.setLayout(layout)
        return tab

    def _create_settings_tab(self) -> QWidget:
        """创建设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout()

        # 分析设置
        analysis_group = QGroupBox("🔍 分析设置")
        analysis_layout = QFormLayout()

        self.setting_auto_analyze = QCheckBox("自动分析新错误")
        self.setting_auto_analyze.setChecked(True)

        self.setting_deep_analysis = QCheckBox("启用深度分析")

        self.setting_ml_enabled = QCheckBox("启用机器学习分类")

        self.setting_max_history = QSpinBox()
        self.setting_max_history.setRange(10, 1000)
        self.setting_max_history.setValue(100)

        analysis_layout.addRow("自动分析:", self.setting_auto_analyze)
        analysis_layout.addRow("深度分析:", self.setting_deep_analysis)
        analysis_layout.addRow("ML分类:", self.setting_ml_enabled)
        analysis_layout.addRow("最大历史:", self.setting_max_history)

        analysis_group.setLayout(analysis_layout)
        layout.addWidget(analysis_group)

        # 修复设置
        fix_group = QGroupBox("🛠️ 修复设置")
        fix_layout = QFormLayout()

        self.setting_auto_fix = QCheckBox("自动生成修复建议")
        self.setting_auto_fix.setChecked(True)

        self.setting_confidence_threshold = QSpinBox()
        self.setting_confidence_threshold.setRange(50, 100)
        self.setting_confidence_threshold.setValue(70)
        self.setting_confidence_threshold.setSuffix(" %")

        self.setting_safe_mode = QCheckBox("安全模式 (手动确认)")
        self.setting_safe_mode.setChecked(True)

        fix_layout.addRow("自动生成:", self.setting_auto_fix)
        fix_layout.addRow("置信度阈值:", self.setting_confidence_threshold)
        fix_layout.addRow("安全模式:", self.setting_safe_mode)

        fix_group.setLayout(fix_layout)
        layout.addWidget(fix_group)

        # 报告设置
        report_group = QGroupBox("📄 报告设置")
        report_layout = QFormLayout()

        self.setting_auto_report = QCheckBox("自动生成Markdown报告")
        self.setting_auto_report.setChecked(True)

        self.setting_include_code = QCheckBox("包含代码上下文")

        self.setting_include_tests = QCheckBox("包含测试用例")

        report_format = QComboBox()
        report_format.addItems(["Markdown", "HTML", "JSON", "PDF"])

        report_layout.addRow("自动报告:", self.setting_auto_report)
        report_layout.addRow("包含代码:", self.setting_include_code)
        report_layout.addRow("包含测试:", self.setting_include_tests)
        report_layout.addRow("报告格式:", report_format)

        report_group.setLayout(report_layout)
        layout.addWidget(report_group)

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

    def _init_mock_data(self):
        """初始化模拟数据"""
        # 模拟错误模式
        self.mock_patterns = [
            {"id": "syntax_error", "name": "语法错误", "category": "语法", "severity": "BLOCKER", "count": 12},
            {"id": "import_error", "name": "导入错误", "category": "导入", "severity": "CRITICAL", "count": 8},
            {"id": "type_error", "name": "类型错误", "category": "类型", "severity": "MAJOR", "count": 15},
            {"id": "key_error", "name": "键错误", "category": "数据", "severity": "MINOR", "count": 6},
            {"id": "attribute_error", "name": "属性错误", "category": "属性", "severity": "MAJOR", "count": 9},
            {"id": "io_error", "name": "IO错误", "category": "IO", "severity": "MAJOR", "count": 4},
        ]

        # 模拟分析历史
        self.mock_history = [
            {
                "id": "rpt_001",
                "timestamp": "2026-04-19 01:25:00",
                "error_type": "ImportError",
                "severity": "CRITICAL",
                "fixes": 3,
                "status": "已完成"
            },
            {
                "id": "rpt_002",
                "timestamp": "2026-04-19 01:20:00",
                "error_type": "TypeError",
                "severity": "MAJOR",
                "fixes": 2,
                "status": "已完成"
            },
            {
                "id": "rpt_003",
                "timestamp": "2026-04-19 01:15:00",
                "error_type": "KeyError",
                "severity": "MINOR",
                "fixes": 1,
                "status": "已完成"
            }
        ]

        self._update_patterns_table()
        self._update_history_table()
        self._update_charts()

    def _update_patterns_table(self):
        """更新模式表格"""
        self.patterns_table.setRowCount(0)

        for pattern in self.mock_patterns:
            row = self.patterns_table.rowCount()
            self.patterns_table.insertRow(row)

            self.patterns_table.setItem(row, 0, QTableWidgetItem(pattern["id"]))
            self.patterns_table.setItem(row, 1, QTableWidgetItem(pattern["name"]))
            self.patterns_table.setItem(row, 2, QTableWidgetItem(pattern["category"]))

            severity_item = QTableWidgetItem(pattern["severity"])
            if pattern["severity"] == "BLOCKER":
                severity_item.setForeground(QColor("#e74c3c"))
            elif pattern["severity"] == "CRITICAL":
                severity_item.setForeground(QColor("#f39c12"))
            self.patterns_table.setItem(row, 3, severity_item)

            self.patterns_table.setItem(row, 4, QTableWidgetItem(str(pattern["count"])))
            self.patterns_table.setItem(row, 5, QTableWidgetItem("None"))

    def _update_history_table(self):
        """更新历史表格"""
        self.history_table.setRowCount(0)

        for hist in self.mock_history:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)

            self.history_table.setItem(row, 0, QTableWidgetItem(hist["id"]))
            self.history_table.setItem(row, 1, QTableWidgetItem(hist["timestamp"]))
            self.history_table.setItem(row, 2, QTableWidgetItem(hist["error_type"]))

            status_item = QTableWidgetItem(hist["severity"])
            if hist["severity"] == "CRITICAL":
                status_item.setForeground(QColor("#e74c3c"))
            elif hist["severity"] == "MAJOR":
                status_item.setForeground(QColor("#f39c12"))
            self.history_table.setItem(row, 3, status_item)

            self.history_table.setItem(row, 4, QTableWidgetItem(str(hist["fixes"])))
            self.history_table.setItem(row, 5, QTableWidgetItem(hist["status"]))

    def _update_charts(self):
        """更新图表"""
        # 错误分布饼图
        series = QPieSeries()
        for pattern in self.mock_patterns[:4]:
            series.append(pattern["name"], pattern["count"])

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Top 4 错误类型")
        self.error_dist_chart.setChart(chart)

        # 严重性柱状图
        bar_set = QBarSet("错误数量")
        severities = ["BLOCKER", "CRITICAL", "MAJOR", "MINOR"]
        counts = []
        for sev in severities:
            count = sum(p["count"] for p in self.mock_patterns if p["severity"] == sev)
            counts.append(count)

        bar_set.append(counts)

        bar_series = QBarSeries()
        bar_series.append(bar_set)

        severity_chart = QChart()
        severity_chart.addSeries(bar_series)
        severity_chart.setTitle("严重性分布")
        self.severity_chart.setChart(severity_chart)

    def _start_analysis(self):
        """开始分析"""
        self.status_label.setText("🟡 正在分析...")
        QTimer.singleShot(1000, lambda: self.status_label.setText("🟢 分析完成"))

    def _run_analysis(self):
        """运行分析"""
        error_text = self.error_input.toPlainText()

        if not error_text.strip():
            QMessageBox.warning(self, "警告", "请输入错误日志")
            return

        self.status_label.setText("🟡 分析中...")

        # 模拟分析过程
        self.analysis_progress.setValue(0)
        for i in range(1, 101, 10):
            self.analysis_progress.setValue(i)
            QTimer.singleShot(i * 20, lambda v=i: self.analysis_progress.setValue(v))

        # 显示分析结果
        self.analysis_result_text.setHtml("""
        <h2>🔍 分析结果</h2>
        <table border='1' cellpadding='8'>
            <tr><td><b>错误类型</b></td><td>TypeError</td></tr>
            <tr><td><b>严重性</b></td><td style='color: orange;'>MAJOR</td></tr>
            <tr><td><b>匹配模式</b></td><td>type_error, concatenation_error</td></tr>
            <tr><td><b>置信度</b></td><td>85%</td></tr>
            <tr><td><b>建议</b></td><td>使用 str() 转换非字符串类型</td></tr>
        </table>
        """)

        self.root_cause_text.setHtml("""
        <h3>🔬 根因分析</h3>
        <ul>
            <li>错误消息: unsupported operand type(s) for +: 'str' and 'int'</li>
            <li>可能原因:
                <ul>
                    <li>对字符串和整数使用 + 操作符</li>
                    <li>类型推断与实际类型不匹配</li>
                </ul>
            </li>
            <li>建议: 在操作前进行类型检查或转换</li>
        </ul>
        """)

        # 更新表格
        self.fixes_table.setRowCount(0)
        fixes = [
            ("fix_001", "使用str()转换", "code", "85%", "应用"),
            ("fix_002", "使用f-string格式化", "code", "80%", "应用"),
        ]
        for fix in fixes:
            row = self.fixes_table.rowCount()
            self.fixes_table.insertRow(row)
            for i, val in enumerate(fix):
                self.fixes_table.setItem(row, i, QTableWidgetItem(val))

        self.btn_apply_fix.setEnabled(True)
        self.status_label.setText("🟢 分析完成")

    def _paste_error(self):
        """粘贴错误"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.error_input.setPlainText(text)

    def _generate_report(self):
        """生成报告"""
        if not self.current_report:
            QMessageBox.information(self, "提示", "请先运行分析")
            return

        report_content = """# 🐍 Python智能错误分析报告

## 执行摘要

| 项目 | 值 |
|------|-----|
| 严重性 | MAJOR |
| 错误类型 | TypeError |
| 匹配模式 | 2个 |
| 修复建议 | 2条 |
| 置信度 | 85% |

## 错误详情

错误信息: `unsupported operand type(s) for +: 'str' and 'int'`

## 修复建议

1. 使用 `str()` 转换非字符串类型
2. 使用 f-string 格式化

---
*报告由 Python Mind 自动生成*
"""
        self.report_preview.setPlainText(report_content)
        QMessageBox.information(self, "成功", "报告已生成")

    def _clear_history(self):
        """清空历史"""
        reply = QMessageBox.question(self, "确认", "确定要清空所有历史记录吗?")
        if reply == QMessageBox.StandardButton.Yes:
            self.mock_history.clear()
            self._update_history_table()
            self.status_label.setText("🟢 历史已清空")

    def _export_analysis(self):
        """导出分析"""
        path, _ = QFileDialog.getSaveFileName(self, "导出分析", "", "JSON Files (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({"analysis": "data"}, f, ensure_ascii=False)
            QMessageBox.information(self, "成功", f"已导出到 {path}")

    def _on_analysis_selected(self, item: QListWidgetItem):
        """分析项被选中"""
        pass

    def _generate_fixes(self):
        """生成修复"""
        self.fixes_table.setRowCount(0)
        fixes = [
            ("fix_001", "类型转换修复", "code", "90%", "应用"),
            ("fix_002", "边界检查修复", "code", "85%", "应用"),
            ("fix_003", "空值检查修复", "code", "88%", "应用"),
        ]
        for fix in fixes:
            row = self.fixes_table.rowCount()
            self.fixes_table.insertRow(row)
            for i, val in enumerate(fix):
                self.fixes_table.setItem(row, i, QTableWidgetItem(val))

        self.original_code.setPlainText("# 原始代码\nvalue = 'string' + 123")
        self.fixed_code.setPlainText("# 修复后\nvalue = 'string' + str(123)")

    def _copy_fix(self):
        """复制修复"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.fixed_code.toPlainText())
        self.status_label.setText("🟢 已复制到剪贴板")

    def _generate_tests(self):
        """生成测试"""
        self.tests_table.setRowCount(0)
        tests = [
            ("test_001", "测试类型转换", "unit", "待运行"),
            ("test_002", "测试边界条件", "boundary", "待运行"),
            ("test_003", "测试回归", "regression", "待运行"),
        ]
        for test in tests:
            row = self.tests_table.rowCount()
            self.tests_table.insertRow(row)
            for i, val in enumerate(test):
                self.tests_table.setItem(row, i, QTableWidgetItem(val))

        self.test_code_view.setPlainText('''def test_type_conversion():
    """测试类型转换"""
    # 测试整数转字符串
    assert str(123) == "123"
    # 测试字符串连接
    assert "hello" + str(123) == "hello123"''')

    def _filter_patterns(self, text: str):
        """筛选模式"""
        for i in range(self.patterns_table.rowCount()):
            item = self.patterns_table.item(i, 1)
            if item:
                match = text.lower() in item.text().lower() if text else True
                self.patterns_table.setRowHidden(i, not match)

    def _view_report(self):
        """查看报告"""
        self._generate_report()

    def _delete_history(self):
        """删除历史"""
        self._clear_history()

    def _export_all_reports(self):
        """导出所有报告"""
        path, _ = QFileDialog.getSaveFileName(self, "导出全部报告", "", "Markdown Files (*.md)")
        if path:
            QMessageBox.information(self, "成功", f"已导出到 {path}")

    def _add_knowledge(self):
        """添加知识"""
        QMessageBox.information(self, "提示", "添加知识功能开发中")

    def _update_dashboard(self):
        """更新仪表盘"""
        # 更新统计数据
        total = len(self.mock_history)
        self.stat_analyzed.findChild(QLabel).setText(str(total + 5))
        self.stat_patterns.findChild(QLabel).setText(str(len(self.mock_patterns)))
        self.stat_fixes.findChild(QLabel).setText(str(total * 2))
        self.stat_reports.findChild(QLabel).setText(str(total))

        # 更新最近分析列表
        self.recent_analysis_list.clear()
        for hist in self.mock_history[:5]:
            item = QListWidgetItem(
                f"📋 {hist['error_type']} - {hist['timestamp']} ({hist['severity']})"
            )
            self.recent_analysis_list.addItem(item)

        # 更新计数
        self.analysis_count_label.setText(f"分析: {total + 5}")
        self.pattern_count_label.setText(f"模式: {len(self.mock_patterns)}")