# -*- coding: utf-8 -*-
"""
🐍 Python智能日志分析与自动修复系统 - Python Mind Panel
========================================================

核心理念: "从错误中学习，从日志中洞察，自动诊断，智能修复"

功能：
- 日志输入与分析
- 错误模式识别
- 根因分析
- 修复建议生成
- 代码补丁应用

Author: Hermes Desktop Team
Version: 1.0.0
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QListWidget,
    QListWidgetItem, QComboBox, QTabWidget, QGroupBox,
    QScrollArea, QFrame, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QStatusBar, QMenuBar, QMenu,
    QToolButton, QStackedWidget, QFormLayout, QSpinBox,
    QCheckBox, QMessageBox, QSplitter, QFileDialog,
    QInputDialog, QDialog, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QIcon, QAction, QColor, QPalette

import asyncio
import json
import time
import os
import traceback
from datetime import datetime
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class PythonMindPanel(QWidget):
    """
    Python智能日志分析与自动修复系统 - UI面板

    三层架构:
    - Log Ingestion Layer: 实时日志收集、结构化解析、上下文关联
    - Intelligent Analysis Layer: 错误模式识别、根因分析、代码关联
    - Auto-Fix Generation Layer: 代码补丁生成、配置优化、测试用例生成
    """

    # 信号定义
    log_received = pyqtSignal(str)  # 新日志接收
    analysis_completed = pyqtSignal(dict)  # 分析完成
    fix_applied = pyqtSignal(str, bool)  # 修复应用结果 (fix_id, success)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = None
        self._init_ui()
        self._init_connections()

    def set_engine(self, engine):
        """设置Python Mind引擎"""
        self.engine = engine
        if engine:
            self._update_engine_status(True)

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("🐍 Python智能日志分析")
        self.setMinimumSize(1000, 700)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # ===== 顶部工具栏 =====
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)

        # ===== 主工作区 =====
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setSizes([400, 600])

        # 左侧：日志输入与分析
        left_panel = self._create_log_panel()
        splitter.addWidget(left_panel)

        # 右侧：结果展示
        right_panel = self._create_result_panel()
        splitter.addWidget(right_panel)

        main_layout.addWidget(splitter)

        # ===== 底部状态栏 =====
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        main_layout.addWidget(self.status_bar)

        # 引擎状态
        self._update_engine_status(False)

    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QFrame()
        toolbar.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 4, 8, 4)

        # 引擎状态标签
        self.engine_status_label = QLabel("🔴 引擎未连接")
        layout.addWidget(self.engine_status_label)

        layout.addStretch()

        # 按钮
        self.btn_analyze = QPushButton("🔍 分析日志")
        self.btn_analyze.setEnabled(False)
        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_export = QPushButton("📤 导出报告")
        self.btn_settings = QPushButton("⚙️ 设置")

        layout.addWidget(self.btn_analyze)
        layout.addWidget(self.btn_clear)
        layout.addWidget(self.btn_export)
        layout.addWidget(self.btn_settings)

        return toolbar

    def _create_log_panel(self) -> QWidget:
        """创建日志输入面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QVBoxLayout(panel)

        # 标题
        title = QLabel("📝 日志输入与分析")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(title)

        # 日志输入选项卡
        self.log_tabs = QTabWidget()

        # 手动输入
        manual_tab = QWidget()
        manual_layout = QVBoxLayout(manual_tab)
        self.log_input = QTextEdit()
        self.log_input.setPlaceholderText("在此粘贴日志内容...\n支持：\n- Python traceback\n- 错误输出\n- 日志文件内容")
        self.log_input.setFont(QFont("Consolas", 9))
        manual_layout.addWidget(self.log_input)
        self.log_tabs.addTab(manual_tab, "✍️ 手动输入")

        # 文件导入
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)
        file_layout.addWidget(QLabel("选择日志文件:"))
        file_btn_layout = QHBoxLayout()
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("选择日志文件路径...")
        btn_browse = QPushButton("📂 浏览...")
        file_btn_layout.addWidget(self.file_path_input)
        file_btn_layout.addWidget(btn_browse)
        file_layout.addLayout(file_btn_layout)
        self.btn_load_file = QPushButton("📥 加载文件")
        file_layout.addWidget(self.btn_load_file)
        file_layout.addStretch()
        self.log_tabs.addTab(file_tab, "📁 文件导入")

        # 实时监控
        monitor_tab = QWidget()
        monitor_layout = QVBoxLayout(monitor_tab)
        monitor_layout.addWidget(QLabel("实时监控 (读取指定目录的日志文件):"))
        self.monitor_path = QLineEdit()
        self.monitor_path.setPlaceholderText("日志目录路径...")
        self.monitor_path.setText(os.path.expanduser("~/AppData/Local/hermes-desktop/logs"))
        monitor_layout.addWidget(self.monitor_path)
        self.btn_start_monitor = QPushButton("▶️ 开始监控")
        self.btn_stop_monitor = QPushButton("⏹️ 停止监控")
        self.btn_stop_monitor.setEnabled(False)
        monitor_btn_layout = QHBoxLayout()
        monitor_btn_layout.addWidget(self.btn_start_monitor)
        monitor_btn_layout.addWidget(self.btn_stop_monitor)
        monitor_layout.addLayout(monitor_btn_layout)
        monitor_layout.addStretch()
        self.log_tabs.addTab(monitor_tab, "📡 实时监控")

        layout.addWidget(self.log_tabs, 1)

        # 分析选项
        options_group = QGroupBox("分析选项")
        options_layout = QHBoxLayout(options_group)

        self.auto_fix_check = QCheckBox("自动生成修复")
        self.auto_fix_check.setChecked(True)
        options_layout.addWidget(self.auto_fix_check)

        self.deep_analysis_check = QCheckBox("深度分析")
        self.deep_analysis_check.setChecked(False)
        options_layout.addWidget(self.deep_analysis_check)

        options_layout.addStretch()
        layout.addWidget(options_group)

        return panel

    def _create_result_panel(self) -> QWidget:
        """创建结果展示面板"""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        layout = QVBoxLayout(panel)

        # 标题
        title = QLabel("📊 分析结果")
        title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(title)

        # 结果选项卡
        self.result_tabs = QTabWidget()

        # 概览
        overview_tab = self._create_overview_tab()
        self.result_tabs.addTab(overview_tab, "📋 概览")

        # 错误详情
        error_tab = self._create_error_tab()
        self.result_tabs.addTab(error_tab, "❌ 错误详情")

        # 修复建议
        fix_tab = self._create_fix_tab()
        self.result_tabs.addTab(fix_tab, "🔧 修复建议")

        # 代码预览
        code_tab = self._create_code_tab()
        self.result_tabs.addTab(code_tab, "💻 代码预览")

        layout.addWidget(self.result_tabs, 1)

        return panel

    def _create_overview_tab(self) -> QWidget:
        """创建概览选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 统计信息
        stats_group = QGroupBox("统计信息")
        stats_layout = QGridLayout(stats_group)

        stats_layout.addWidget(QLabel("错误总数:"), 0, 0)
        self.stat_error_count = QLabel("0")
        stats_layout.addWidget(self.stat_error_count, 0, 1)

        stats_layout.addWidget(QLabel("警告总数:"), 0, 2)
        self.stat_warning_count = QLabel("0")
        stats_layout.addWidget(self.stat_warning_count, 0, 3)

        stats_layout.addWidget(QLabel("信息总数:"), 1, 0)
        self.stat_info_count = QLabel("0")
        stats_layout.addWidget(self.stat_info_count, 1, 1)

        stats_layout.addWidget(QLabel("分析耗时:"), 1, 2)
        self.stat_duration = QLabel("0ms")
        stats_layout.addWidget(self.stat_duration, 1, 3)

        layout.addWidget(stats_group)

        # 错误类型分布
        type_group = QGroupBox("错误类型分布")
        type_layout = QVBoxLayout(type_group)
        self.error_type_list = QListWidget()
        type_layout.addWidget(self.error_type_list)
        layout.addWidget(type_group)

        # 严重性分布
        severity_group = QGroupBox("严重性分布")
        severity_layout = QGridLayout(severity_group)

        severity_layout.addWidget(QLabel("🔴 阻断:"), 0, 0)
        self.severity_blocker = QLabel("0")
        severity_layout.addWidget(self.severity_blocker, 0, 1)

        severity_layout.addWidget(QLabel("🟠 严重:"), 0, 2)
        self.severity_critical = QLabel("0")
        severity_layout.addWidget(self.severity_critical, 0, 3)

        severity_layout.addWidget(QLabel("🟡 主要:"), 1, 0)
        self.severity_major = QLabel("0")
        severity_layout.addWidget(self.severity_major, 1, 1)

        severity_layout.addWidget(QLabel("🔵 次要:"), 1, 2)
        self.severity_minor = QLabel("0")
        severity_layout.addWidget(self.severity_minor, 1, 3)

        layout.addWidget(severity_group)
        layout.addStretch()

        return tab

    def _create_error_tab(self) -> QWidget:
        """创建错误详情选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 错误列表
        self.error_list = QListWidget()
        self.error_list.itemClicked.connect(self._on_error_selected)
        layout.addWidget(self.error_list)

        # 错误详情
        detail_group = QGroupBox("错误详情")
        detail_layout = QVBoxLayout(detail_group)

        self.error_detail = QTextEdit()
        self.error_detail.setReadOnly(True)
        self.error_detail.setFont(QFont("Consolas", 9))
        detail_layout.addWidget(self.error_detail)

        layout.addWidget(detail_group)
        return tab

    def _create_fix_tab(self) -> QWidget:
        """创建修复建议选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 修复列表
        self.fix_list = QListWidget()
        self.fix_list.itemClicked.connect(self._on_fix_selected)
        layout.addWidget(self.fix_list)

        # 修复详情和应用
        action_group = QGroupBox("修复操作")
        action_layout = QVBoxLayout(action_group)

        self.fix_detail = QTextEdit()
        self.fix_detail.setReadOnly(True)
        self.fix_detail.setFont(QFont("Consolas", 9))
        action_layout.addWidget(self.fix_detail)

        fix_btn_layout = QHBoxLayout()
        self.btn_apply_fix = QPushButton("✅ 应用修复")
        self.btn_apply_fix.setEnabled(False)
        self.btn_copy_fix = QPushButton("📋 复制代码")
        fix_btn_layout.addWidget(self.btn_apply_fix)
        fix_btn_layout.addWidget(self.btn_copy_fix)
        fix_btn_layout.addStretch()
        action_layout.addLayout(fix_btn_layout)

        layout.addWidget(action_group)
        return tab

    def _create_code_tab(self) -> QWidget:
        """创建代码预览选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 文件选择
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("文件:"))
        self.code_file_combo = QComboBox()
        file_layout.addWidget(self.code_file_combo, 1)
        layout.addLayout(file_layout)

        # 代码显示
        self.code_preview = QTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setFont(QFont("Consolas", 10))
        layout.addWidget(self.code_preview, 1)

        # 操作按钮
        code_btn_layout = QHBoxLayout()
        self.btn_apply_patch = QPushButton("🔄 应用补丁")
        self.btn_revert_patch = QPushButton("↩️ 撤销补丁")
        self.btn_test_code = QPushButton("🧪 测试代码")
        code_btn_layout.addWidget(self.btn_apply_patch)
        code_btn_layout.addWidget(self.btn_revert_patch)
        code_btn_layout.addWidget(self.btn_test_code)
        code_btn_layout.addStretch()
        layout.addLayout(code_btn_layout)

        return tab

    def _init_connections(self):
        """初始化信号连接"""
        self.btn_analyze.clicked.connect(self._on_analyze_clicked)
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        self.btn_export.clicked.connect(self._on_export_clicked)

    def _update_engine_status(self, connected: bool):
        """更新引擎状态"""
        if connected:
            self.engine_status_label.setText("🟢 引擎已连接")
            self.btn_analyze.setEnabled(True)
            self.status_bar.showMessage("引擎就绪")
        else:
            self.engine_status_label.setText("🔴 引擎未连接")
            self.btn_analyze.setEnabled(False)
            self.status_bar.showMessage("警告: Python Mind引擎未初始化")

    def _on_analyze_clicked(self):
        """分析按钮点击"""
        current_tab = self.log_tabs.currentIndex()

        if current_tab == 0:  # 手动输入
            log_content = self.log_input.toPlainText()
        elif current_tab == 1:  # 文件导入
            log_content = self._load_log_file()
        else:  # 实时监控
            self.status_bar.showMessage("监控模式下，日志会自动分析")
            return

        if not log_content.strip():
            QMessageBox.warning(self, "警告", "请输入日志内容")
            return

        self._analyze_logs(log_content)

    def _load_log_file(self) -> str:
        """加载日志文件"""
        file_path = self.file_path_input.text()
        if not file_path:
            QMessageBox.warning(self, "警告", "请选择日志文件路径")
            return ""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取文件失败: {str(e)}")
            return ""

    def _analyze_logs(self, log_content: str):
        """分析日志"""
        self.status_bar.showMessage("分析中...")
        self.btn_analyze.setEnabled(False)

        try:
            if self.engine:
                # 使用引擎分析
                result = self.engine.analyze_log(log_content)
            else:
                # 简单本地分析
                result = self._simple_analysis(log_content)

            self._display_analysis_result(result)
            self.status_bar.showMessage(f"分析完成 - 发现 {len(result.get('errors', []))} 个错误")

        except Exception as e:
            self.status_bar.showMessage(f"分析失败: {str(e)}")
            logger.error(f"分析失败: {traceback.format_exc()}")

        finally:
            self.btn_analyze.setEnabled(True)

    def _simple_analysis(self, log_content: str) -> dict:
        """简单的本地日志分析"""
        errors = []
        warnings = []
        info_count = 0

        lines = log_content.split('\n')
        for line in lines:
            if 'ERROR' in line or 'Traceback' in line:
                errors.append({'message': line, 'type': 'error'})
            elif 'WARNING' in line:
                warnings.append({'message': line, 'type': 'warning'})
            elif 'INFO' in line:
                info_count += 1

        return {
            'errors': errors,
            'warnings': warnings,
            'info_count': info_count,
            'duration': 100
        }

    def _display_analysis_result(self, result: dict):
        """显示分析结果"""
        errors = result.get('errors', [])
        warnings = result.get('warnings', [])
        info_count = result.get('info_count', 0)

        # 更新统计
        self.stat_error_count.setText(str(len(errors)))
        self.stat_warning_count.setText(str(len(warnings)))
        self.stat_info_count.setText(str(info_count))
        self.stat_duration.setText(f"{result.get('duration', 0)}ms")

        # 更新错误列表
        self.error_list.clear()
        for err in errors[:50]:  # 最多显示50个
            item = QListWidgetItem(f"❌ {err.get('message', 'Unknown')[:60]}")
            self.error_list.addItem(item)

        # 更新错误类型分布
        self.error_type_list.clear()
        type_counts = {}
        for err in errors:
            err_type = err.get('type', 'unknown')
            type_counts[err_type] = type_counts.get(err_type, 0) + 1

        for err_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            self.error_type_list.addItem(f"{err_type}: {count}个")

    def _on_error_selected(self, item: QListWidgetItem):
        """错误列表项被选中"""
        self.error_detail.setText(item.text())

    def _on_fix_selected(self, item: QListWidgetItem):
        """修复建议被选中"""
        self.btn_apply_fix.setEnabled(True)
        self.fix_detail.setText(item.text())

    def _on_clear_clicked(self):
        """清空按钮点击"""
        self.log_input.clear()
        self.error_list.clear()
        self.error_detail.clear()
        self.fix_list.clear()
        self.fix_detail.clear()
        self.code_preview.clear()
        self.status_bar.showMessage("已清空")

    def _on_export_clicked(self):
        """导出报告"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出分析报告", "", "JSON Files (*.json);;Text Files (*.txt)"
        )
        if file_path:
            try:
                report = {
                    'timestamp': datetime.now().isoformat(),
                    'error_count': int(self.stat_error_count.text()),
                    'warning_count': int(self.stat_warning_count.text()),
                    'info_count': int(self.stat_info_count.text())
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                self.status_bar.showMessage(f"报告已导出: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")


# ==================== 面板注册 ====================

def get_panel_info():
    """获取面板信息"""
    return {
        'name': '🐍 Python日志',
        'class': PythonMindPanel,
        'icon': '🐍',
        'description': 'Python智能日志分析与自动修复'
    }
