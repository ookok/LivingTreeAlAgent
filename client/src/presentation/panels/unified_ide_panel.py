"""
统一IDE面板 - 整合原有IDE服务和现代化UI设计

结合:
1. ide_service.py - IDE服务层（代码执行、代码生成、代码分析）
2. 新设计的现代化组件
"""

import os
import sys
import subprocess
import tempfile
import asyncio
from typing import Optional, List, Dict, Any, Callable
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTabWidget, QTextEdit, QPushButton, QProgressBar,
    QComboBox, QToolBar, QSplitter, QFrame
)
from PyQt6.QtGui import QFont, QIcon

# 导入业务逻辑
from client.src.business.ide_service import get_ide_service, IDEService, ExecutionStatus


class UnifiedIDEPanel(QWidget):
    """
    统一IDE面板 - 整合代码编辑、执行、分析功能
    
    信号:
        code_executed(result)
        code_generated(result)
        code_analyzed(result)
    """
    
    code_executed = pyqtSignal(dict)
    code_generated = pyqtSignal(dict)
    code_analyzed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UnifiedIDEPanel")
        
        # 业务逻辑层
        self._ide_service = get_ide_service()
        
        # UI状态
        self._current_file = None
        self._execution_history = []
        
        self._build_ui()
    
    def _build_ui(self):
        """构建现代化IDE UI"""
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 工具栏
        toolbar = QToolBar()
        toolbar.setStyleSheet("""
            QToolBar {
                background: #1e293b;
                border-bottom: 1px solid #334155;
            }
            QToolButton {
                color: #cbd5e1;
            }
            QToolButton:hover {
                background: #334155;
            }
        """)
        
        # 新建文件
        new_btn = QPushButton("新建")
        new_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)
        new_btn.clicked.connect(self._on_new_file)
        toolbar.addWidget(new_btn)
        
        toolbar.addSeparator()
        
        # 语言选择
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["Python", "JavaScript", "TypeScript", "HTML", "CSS", "JSON", "YAML"])
        self._lang_combo.setStyleSheet("""
            QComboBox {
                background: #0f172a;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 12px;
            }
        """)
        toolbar.addWidget(QLabel("语言:"))
        toolbar.addWidget(self._lang_combo)
        
        toolbar.addSeparator()
        
        # 运行按钮
        self._run_btn = QPushButton("▶ 运行")
        self._run_btn.setStyleSheet("""
            QPushButton {
                background: #10b981;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #059669;
            }
            QPushButton:disabled {
                background: #64748b;
            }
        """)
        self._run_btn.clicked.connect(self._on_run_code)
        toolbar.addWidget(self._run_btn)
        
        # 生成按钮
        self._generate_btn = QPushButton("✨ 生成")
        self._generate_btn.setStyleSheet("""
            QPushButton {
                background: #8b5cf6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #7c3aed;
            }
        """)
        self._generate_btn.clicked.connect(self._on_generate_code)
        toolbar.addWidget(self._generate_btn)
        
        # 分析按钮
        self._analyze_btn = QPushButton("🔍 分析")
        self._analyze_btn.setStyleSheet("""
            QPushButton {
                background: #f59e0b;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 16px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #d97706;
            }
        """)
        self._analyze_btn.clicked.connect(self._on_analyze_code)
        toolbar.addWidget(self._analyze_btn)
        
        toolbar.addStretch()
        
        # 执行状态
        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet("color: #10b981; font-size: 12px;")
        toolbar.addWidget(self._status_label)
        
        layout.addWidget(toolbar)
        
        # 主内容区 - 编辑器 + 输出
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: #334155;
                height: 2px;
            }
        """)
        
        # 代码编辑器区域
        editor_area = QWidget()
        editor_layout = QVBoxLayout(editor_area)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标签页
        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet("""
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background: #0f172a;
                color: #64748b;
                padding: 8px 16px;
                margin-right: 4px;
                border-radius: 4px 4px 0 0;
            }
            QTabBar::tab:selected {
                background: #1e293b;
                color: #f1f5f9;
            }
        """)
        
        # 创建初始标签页
        self._add_new_file("untitled.py", "")
        
        editor_layout.addWidget(self._tab_widget)
        splitter.addWidget(editor_area)
        
        # 输出区域
        output_area = QWidget()
        output_layout = QVBoxLayout(output_area)
        output_layout.setContentsMargins(0, 0, 0, 0)
        
        # 输出标签
        output_header = QHBoxLayout()
        output_header.addWidget(QLabel("输出"))
        clear_btn = QPushButton("清空")
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #f1f5f9;
            }
        """)
        clear_btn.clicked.connect(self._clear_output)
        output_header.addWidget(clear_btn)
        output_header.addStretch()
        output_layout.addLayout(output_header)
        
        # 输出内容
        self._output_edit = QTextEdit()
        self._output_edit.setReadOnly(True)
        self._output_edit.setStyleSheet("""
            QTextEdit {
                background: #0f172a;
                color: #9ca3af;
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 12px;
                border: none;
            }
        """)
        output_layout.addWidget(self._output_edit)
        
        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 2px;
                height: 2px;
                background: #334155;
            }
            QProgressBar::chunk {
                background: #3b82f6;
            }
        """)
        output_layout.addWidget(self._progress_bar)
        
        splitter.addWidget(output_area)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
    
    def _add_new_file(self, filename: str, content: str = ""):
        """添加新文件标签页"""
        editor = QTextEdit()
        editor.setFont(QFont("JetBrains Mono", 13))
        editor.setStyleSheet("""
            QTextEdit {
                background: #1e293b;
                color: #e2e8f0;
                border: none;
                padding: 8px;
            }
            QTextEdit:focus {
                outline: none;
            }
        """)
        editor.setPlainText(content)
        self._tab_widget.addTab(editor, filename)
        return editor
    
    def _on_new_file(self):
        """新建文件"""
        count = self._tab_widget.count() + 1
        self._add_new_file(f"untitled_{count}.py")
    
    def _on_run_code(self):
        """运行代码"""
        current_widget = self._tab_widget.currentWidget()
        if not isinstance(current_widget, QTextEdit):
            return
        
        code = current_widget.toPlainText()
        if not code.strip():
            self._append_output("请先输入代码\n", "warning")
            return
        
        language = self._lang_combo.currentText().lower()
        
        self._status_label.setText("运行中...")
        self._status_label.setStyleSheet("color: #f59e0b; font-size: 12px;")
        self._run_btn.setEnabled(False)
        
        self._clear_output()
        
        callbacks = {
            "on_output_line": lambda line: self._append_output(line, "output"),
            "on_error_line": lambda line: self._append_output(line, "error"),
            "on_finished": self._on_execution_finished
        }
        
        asyncio.create_task(self._execute_code_async(code, language, callbacks))
    
    async def _execute_code_async(self, code: str, language: str, callbacks: Dict[str, Callable]):
        """异步执行代码"""
        result = await asyncio.to_thread(
            self._ide_service.execute_code,
            code, language, callbacks
        )
        if "on_finished" in callbacks:
            callbacks["on_finished"](result)
    
    def _on_execution_finished(self, result):
        """代码执行完成"""
        self._status_label.setText("就绪")
        self._status_label.setStyleSheet("color: #10b981; font-size: 12px;")
        self._run_btn.setEnabled(True)
        
        if result.status == ExecutionStatus.SUCCESS:
            self._append_output(f"\n执行完成 (耗时: {result.execution_time_ms:.2f}ms)\n", "success")
        elif result.status == ExecutionStatus.ERROR:
            self._append_output(f"\n执行失败: {result.error}\n", "error")
        elif result.status == ExecutionStatus.TIMEOUT:
            self._append_output(f"\n执行超时\n", "error")
        
        self.code_executed.emit({
            "status": result.status.value,
            "output": result.output,
            "error": result.error,
            "execution_time_ms": result.execution_time_ms
        })
    
    def _on_generate_code(self):
        """生成代码"""
        intent, ok = self._show_input_dialog("代码生成", "描述你想要生成的代码:")
        if not ok or not intent.strip():
            return
        
        language = self._lang_combo.currentText().lower()
        
        self._status_label.setText("生成中...")
        self._status_label.setStyleSheet("color: #8b5cf6; font-size: 12px;")
        self._generate_btn.setEnabled(False)
        
        asyncio.create_task(self._generate_code_async(intent, language))
    
    async def _generate_code_async(self, intent: str, language: str):
        """异步生成代码"""
        result = await asyncio.to_thread(
            self._ide_service.generate_code,
            intent, language
        )
        
        self._status_label.setText("就绪")
        self._status_label.setStyleSheet("color: #10b981; font-size: 12px;")
        self._generate_btn.setEnabled(True)
        
        if result.success:
            current_widget = self._tab_widget.currentWidget()
            if isinstance(current_widget, QTextEdit):
                current_widget.setPlainText(result.code)
            self._append_output(f"代码生成成功！\n", "success")
        else:
            self._append_output(f"代码生成失败: {result.error}\n", "error")
        
        self.code_generated.emit({
            "success": result.success,
            "code": result.code,
            "language": result.language,
            "confidence": result.confidence,
            "error": result.error
        })
    
    def _on_analyze_code(self):
        """分析代码"""
        current_widget = self._tab_widget.currentWidget()
        if not isinstance(current_widget, QTextEdit):
            return
        
        code = current_widget.toPlainText()
        if not code.strip():
            self._append_output("请先输入代码\n", "warning")
            return
        
        language = self._lang_combo.currentText().lower()
        
        self._status_label.setText("分析中...")
        self._status_label.setStyleSheet("color: #f59e0b; font-size: 12px;")
        self._analyze_btn.setEnabled(False)
        
        asyncio.create_task(self._analyze_code_async(code, language))
    
    async def _analyze_code_async(self, code: str, language: str):
        """异步分析代码"""
        analysis = await asyncio.to_thread(
            self._ide_service.analyze_code,
            code, language
        )
        
        self._status_label.setText("就绪")
        self._status_label.setStyleSheet("color: #10b981; font-size: 12px;")
        self._analyze_btn.setEnabled(True)
        
        self._clear_output()
        
        if analysis.syntax_valid:
            self._append_output("✅ 语法检查通过\n", "success")
        else:
            self._append_output("❌ 语法检查失败\n", "error")
            for error in analysis.errors:
                self._append_output(f"  - {error}\n", "error")
        
        self._append_output(f"代码行数: {analysis.line_count}\n", "info")
        
        if analysis.warnings:
            self._append_output("\n警告:\n", "warning")
            for warning in analysis.warnings:
                self._append_output(f"  - {warning}\n", "warning")
        
        if analysis.suggestions:
            self._append_output("\n建议:\n", "info")
            for suggestion in analysis.suggestions:
                self._append_output(f"  - {suggestion}\n", "info")
        
        self.code_analyzed.emit({
            "syntax_valid": analysis.syntax_valid,
            "errors": analysis.errors,
            "warnings": analysis.warnings,
            "suggestions": analysis.suggestions,
            "line_count": analysis.line_count,
            "complexity": analysis.complexity
        })
    
    def _append_output(self, text: str, type: str = "output"):
        """追加输出"""
        colors = {
            "output": "#9ca3af",
            "error": "#ef4444",
            "success": "#10b981",
            "warning": "#f59e0b",
            "info": "#64748b"
        }
        
        color = colors.get(type, "#9ca3af")
        current = self._output_edit.toHtml()
        self._output_edit.setHtml(current + f"<span style='color: {color};'>{text}</span>")
        
        scroll_bar = self._output_edit.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())
    
    def _clear_output(self):
        """清空输出"""
        self._output_edit.clear()
    
    def _show_input_dialog(self, title: str, label: str) -> tuple:
        """显示输入对话框"""
        from ..components.modern_dialogs import ModernDialog
        
        dialog = ModernDialog(self)
        dialog.setWindowTitle(title)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        
        layout.addWidget(QLabel(label))
        
        input_edit = QTextEdit()
        input_edit.setFixedHeight(100)
        input_edit.setStyleSheet("""
            QTextEdit {
                background: #1e293b;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        layout.addWidget(input_edit)
        
        buttons_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
            }
        """)
        ok_btn.clicked.connect(dialog.accept)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #334155;
                color: #f1f5f9;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
            }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        
        buttons_layout.addWidget(ok_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
        
        dialog.setFixedSize(400, 220)
        
        result = dialog.exec()
        return input_edit.toPlainText(), result == ModernDialog.DialogCode.Accepted
    
    def set_code(self, code: str, filename: str = None):
        """设置代码内容"""
        if filename:
            index = self._tab_widget.count()
            self._add_new_file(filename, code)
            self._tab_widget.setCurrentIndex(index)
        else:
            current_widget = self._tab_widget.currentWidget()
            if isinstance(current_widget, QTextEdit):
                current_widget.setPlainText(code)
    
    def get_code(self) -> str:
        """获取当前代码"""
        current_widget = self._tab_widget.currentWidget()
        if isinstance(current_widget, QTextEdit):
            return current_widget.toPlainText()
        return ""
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._ide_service.get_stats()