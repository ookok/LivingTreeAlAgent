#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试集成组件
==============

功能：
1. 运行 pytest 测试
2. 显示测试结果（通过/失败/错误）
3. 显示测试覆盖率
4. 测试历史记录
5. 一键运行所有测试/单个测试文件/单个测试函数

Author: LivingTreeAI Agent
Date: 2026-04-26
"""

import os
import sys
import subprocess
import json
from typing import Optional, List, Dict
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QTextEdit,
    QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QBrush


# ── 测试运行工作线程 ─────────────────────────────────────────────

class TestRunnerWorker(QThread):
    """测试运行工作线程"""
    
    test_result = pyqtSignal(dict)  # 测试结果
    test_finished = pyqtSignal(int, int, int)  # 通过数, 失败数, 错误数
    test_error = pyqtSignal(str)  # 错误信息
    output_received = pyqtSignal(str)  # 输出信息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.test_path: str = ""  # 测试路径（文件或目录）
        self.run_coverage: bool = False
        self.verbose: bool = True
        self.stop_requested: bool = False
    
    def run(self):
        """运行测试"""
        try:
            # 构建 pytest 命令
            cmd = [sys.executable, "-m", "pytest", self.test_path]
            
            if self.verbose:
                cmd.append("-v")
            
            if self.run_coverage:
                cmd.extend(["--cov", "--cov-report=term-missing"])
            
            # 添加 JSON 报告（用于解析结果）
            cmd.append("--json-report")
            cmd.append("--json-report-file=test_result.json")
            
            self.output_received.emit(f"运行命令: {' '.join(cmd)}\n")
            self.output_received.emit(f"测试路径: {self.test_path}\n")
            self.output_received.emit("-" * 60 + "\n")
            
            # 运行测试
            process = subprocess.Popen(
                cmd,
                cwd=os.getcwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # 实时读取输出
            passed = 0
            failed = 0
            errors = 0
            
            while True:
                if self.stop_requested:
                    process.terminate()
                    break
                
                line = process.stdout.readline()
                if not line:
                    break
                
                # 发送输出
                self.output_received.emit(line)
                
                # 统计结果
                if "PASSED" in line:
                    passed += 1
                elif "FAILED" in line:
                    failed += 1
                elif "ERROR" in line:
                    errors += 1
            
            process.wait()
            
            self.test_finished.emit(passed, failed, errors)
            
        except Exception as e:
            self.test_error.emit(str(e))
    
    def stop(self):
        """停止测试"""
        self.stop_requested = True


# ── 测试集成面板 ─────────────────────────────────────────────

class TestIntegrationPanel(QWidget):
    """
    测试集成面板
    
    功能：
    - 测试文件浏览器
    - 运行测试按钮
    - 测试结果展示
    - 测试输出
    
    Signals:
        test_file_selected(str): 测试文件被选中
    """
    
    test_file_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.test_path: str = ""
        self.worker: Optional[TestRunnerWorker] = None
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 标题
        title_label = QLabel("🧪 测试集成")
        title_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #FFFFFF; padding: 4px 0;"
        )
        layout.addWidget(title_label)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.run_all_btn = QPushButton("▶️ 运行所有测试")
        self.run_all_btn.setFixedSize(120, 32)
        self.run_all_btn.setStyleSheet("""
            QPushButton {
                background: #0E639C;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #1177BB; }
            QPushButton:disabled { background: #555555; }
        """)
        toolbar_layout.addWidget(self.run_all_btn)
        
        self.run_file_btn = QPushButton("▶️ 运行选中文件")
        self.run_file_btn.setFixedSize(120, 32)
        self.run_file_btn.setEnabled(False)
        self.run_file_btn.setStyleSheet("""
            QPushButton {
                background: #0E639C;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #1177BB; }
            QPushButton:disabled { background: #555555; }
        """)
        toolbar_layout.addWidget(self.run_file_btn)
        
        self.coverage_check = QPushButton("📊 覆盖率")
        self.coverage_check.setCheckable(True)
        self.coverage_check.setFixedSize(80, 32)
        self.coverage_check.setStyleSheet("""
            QPushButton {
                background: #3E3E42;
                color: #D4D4D4;
                border: 1px solid #555555;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:checked {
                background: #0E639C;
                color: white;
                border: 1px solid #0E639C;
            }
            QPushButton:hover { background: #4A4A4E; }
        """)
        toolbar_layout.addWidget(self.coverage_check)
        
        toolbar_layout.addStretch()
        
        self.stop_btn = QPushButton("⏹️ 停止")
        self.stop_btn.setFixedSize(80, 32)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #C42B1C;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #E51400; }
            QPushButton:disabled { background: #555555; }
        """)
        toolbar_layout.addWidget(self.stop_btn)
        
        layout.addLayout(toolbar_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #3E3E42;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #0E639C;
                border-radius: 2px;
            }
        """)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0)  # 不确定模式
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # 分割视图（测试结果树 + 输出）
        split_layout = QHBoxLayout()
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(8)
        
        # 测试结果树
        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["测试", "状态", "耗时"])
        self.result_tree.setColumnWidth(0, 300)
        self.result_tree.setColumnWidth(1, 80)
        self.result_tree.setColumnWidth(2, 80)
        self.result_tree.setStyleSheet("""
            QTreeWidget {
                background: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #3E3E42;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 2px 4px;
            }
            QTreeWidget::item:selected {
                background: #094771;
                color: #FFFFFF;
            }
        """)
        split_layout.addWidget(self.result_tree, 1)
        
        # 测试输出
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #3E3E42;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        split_layout.addWidget(self.output_text, 1)
        
        layout.addLayout(split_layout, 1)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(
            "color: #D4D4D4; font-size: 11px; padding: 4px 0;"
        )
        layout.addWidget(self.status_label)
    
    def _connect_signals(self):
        """连接信号"""
        self.run_all_btn.clicked.connect(self._run_all_tests)
        self.run_file_btn.clicked.connect(self._run_selected_file)
        self.stop_btn.clicked.connect(self._stop_tests)
        self.result_tree.itemDoubleClicked.connect(self._on_test_double_clicked)
    
    def set_test_path(self, path: str):
        """
        设置测试路径
        
        Args:
            path: 测试路径（文件或目录）
        """
        self.test_path = path
    
    def _run_all_tests(self):
        """运行所有测试"""
        if not self.test_path:
            # 默认使用项目根目录
            self.test_path = os.getcwd()
        
        self._start_test_run(self.test_path)
    
    def _run_selected_file(self):
        """运行选中的测试文件"""
        # TODO: 从测试结果树获取选中的测试文件
        selected_items = self.result_tree.selectedItems()
        if selected_items:
            file_path = selected_items[0].data(0, Qt.ItemDataRole.UserRole)
            if file_path:
                self._start_test_run(file_path)
    
    def _start_test_run(self, test_path: str):
        """
        开始运行测试
        
        Args:
            test_path: 测试路径
        """
        # 清空结果
        self.result_tree.clear()
        self.output_text.clear()
        
        # 更新状态
        self.status_label.setText(f"测试运行中: {test_path}")
        self.progress_bar.show()
        
        # 禁用按钮
        self.run_all_btn.setEnabled(False)
        self.run_file_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # 启动工作线程
        self.worker = TestRunnerWorker()
        self.worker.test_path = test_path
        self.worker.run_coverage = self.coverage_check.isChecked()
        self.worker.test_result.connect(self._on_test_result)
        self.worker.test_finished.connect(self._on_test_finished)
        self.worker.test_error.connect(self._on_test_error)
        self.worker.output_received.connect(self._on_output_received)
        self.worker.start()
    
    def _stop_tests(self):
        """停止测试"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
            self._on_test_finished(0, 0, 0)
    
    def _on_test_result(self, result: dict):
        """
        处理测试结果
        
        Args:
            result: 测试结果字典
        """
        # TODO: 解析 JSON 报告
        pass
    
    def _on_test_finished(self, passed: int, failed: int, errors: int):
        """
        测试完成
        
        Args:
            passed: 通过数
            failed: 失败数
            errors: 错误数
        """
        # 更新状态
        total = passed + failed + errors
        status = f"测试完成: {total} 个测试, "
        status += f"✅ {passed} 通过, "
        status += f"❌ {failed} 失败, "
        status += f"⚠️ {errors} 错误"
        self.status_label.setText(status)
        
        # 隐藏进度条
        self.progress_bar.hide()
        
        # 启用按钮
        self.run_all_btn.setEnabled(True)
        self.run_file_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # 显示结果摘要
        self.output_text.append(f"\n{'=' * 60}")
        self.output_text.append(status)
        self.output_text.append(f"{'=' * 60}")
        
        self.worker = None
    
    def _on_test_error(self, error_msg: str):
        """
        测试错误
        
        Args:
            error_msg: 错误信息
        """
        self.status_label.setText(f"测试错误: {error_msg}")
        self.output_text.append(f"\n错误: {error_msg}\n")
        
        # 隐藏进度条
        self.progress_bar.hide()
        
        # 启用按钮
        self.run_all_btn.setEnabled(True)
        self.run_file_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        self.worker = None
    
    def _on_output_received(self, output: str):
        """
        接收测试输出
        
        Args:
            output: 输出文本
        """
        self.output_text.append(output.rstrip())
    
    def _on_test_double_clicked(self, item: QTreeWidgetItem, column: int):
        """
        处理测试双击
        
        Args:
            item: 被点击的项
            column: 被点击的列
        """
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if file_path and os.path.isfile(file_path):
            self.test_file_selected.emit(file_path)


# ── 测试 ─────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("测试集成测试")
    window.setGeometry(100, 100, 1000, 700)
    
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    
    layout = QVBoxLayout(central_widget)
    
    test_panel = TestIntegrationPanel()
    test_panel.set_test_path(os.getcwd())
    test_panel.test_file_selected.connect(
        lambda p: print(f"选中测试文件: {p}")
    )
    
    layout.addWidget(test_panel)
    
    window.show()
    sys.exit(app.exec())
