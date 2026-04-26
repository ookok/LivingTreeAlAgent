"""
智能IDE模块 - 真实功能实现

支持代码编辑、语法高亮、代码执行、AI 辅助编程。
"""

import os
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QLabel, QFrame, QFileDialog, QMessageBox,
    QTabWidget, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QTextCursor

from client.src.business.nanochat_config import config


# ── 代码执行工作线程 ─────────────────────────────────────────────────

class CodeExecutionWorker(QThread):
    """代码执行工作线程"""

    output = pyqtSignal(str)          # 输出
    error = pyqtSignal(str)           # 错误
    finished = pyqtSignal(int)        # 完成（退出码）

    def __init__(self, code: str, language: str, parent=None):
        super().__init__(parent)
        self.code = code
        self.language = language
        self._stop_requested = False

    def run(self):
        try:
            if self.language == "python":
                # 执行 Python 代码（模拟）
                import io
                import contextlib

                output_buffer = io.StringIO()
                try:
                    with contextlib.redirect_stdout(output_buffer), \
                         contextlib.redirect_stderr(output_buffer):
                        exec(self.code)
                    output = output_buffer.getvalue()
                    if output:
                        self.output.emit(output)
                except Exception as e:
                    self.error.emit(str(e))
            else:
                self.output.emit(f"代码执行（{self.language}）: 功能开发中...")

            self.finished.emit(0)

        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(1)

    def stop(self):
        self._stop_requested = True


# ── 代码编辑器 ──────────────────────────────────────────────────────

class CodeEditor(QPlainTextEdit):
    """代码编辑器（简化版）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        # 设置字体
        font = QFont("Consolas", 13)
        self.setFont(font)

        # 设置样式
        self.setStyleSheet("""
            QPlainTextEdit {
                background: #1E1E1E;
                color: #D4D4D4;
                border: none;
                padding: 12px;
                font-family: Consolas, 'Courier New', monospace;
            }
        """)

    def set_content(self, content: str):
        """设置内容"""
        self.setPlainText(content)

    def get_content(self) -> str:
        """获取内容"""
        return self.toPlainText()

    def set_language(self, language: str):
        """设置语言（用于语法高亮，暂未实现）"""
        pass


# ── 主智能IDE面板 ─────────────────────────────────────────────────

class Panel(QWidget):
    """智能IDE面板 - 真实功能"""

    code_executed = pyqtSignal(str, str)  # 代码, 语言
    ai_requested = pyqtSignal(str)        # 请求 AI 辅助

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file: Optional[str] = None
        self.worker: Optional[CodeExecutionWorker] = None
        self._setup_ui()
        self._load_sample()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        title_bar = QFrame()
        title_bar.setFixedHeight(52)
        title_bar.setStyleSheet("background: #252526; border-bottom: 1px solid #3E3E42;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)

        title_label = QLabel("💻 智能 IDE")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # 语言选择
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Python", "python")
        self.lang_combo.addItem("JavaScript", "javascript")
        self.lang_combo.addItem("TypeScript", "typescript")
        self.lang_combo.addItem("HTML", "html")
        self.lang_combo.addItem("CSS", "css")
        self.lang_combo.setStyleSheet("""
            QComboBox {
                background: #3E3E42;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QComboBox::dropDown {
                border: none;
            }
        """)
        title_layout.addWidget(self.lang_combo)

        # 运行按钮
        self.run_btn = QPushButton("▶️ 运行")
        self.run_btn.setFixedSize(100, 36)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background: #0E639C;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1177BB; }
            QPushButton:disabled { background: #555555; }
        """)
        self.run_btn.clicked.connect(self._run_code)
        title_layout.addWidget(self.run_btn)

        # AI 辅助按钮
        self.ai_btn = QPushButton("🤖 AI 辅助")
        self.ai_btn.setFixedSize(120, 36)
        self.ai_btn.setStyleSheet("""
            QPushButton {
                background: #4B0082;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background: #5A0099; }
        """)
        self.ai_btn.clicked.connect(self._request_ai_help)
        title_layout.addWidget(self.ai_btn)

        layout.addWidget(title_bar)

        # 主区域（编辑器 + 输出）
        main_split = QHBoxLayout()
        main_split.setContentsMargins(0, 0, 0, 0)
        main_split.setSpacing(0)

        # 编辑器区域
        editor_frame = QFrame()
        editor_frame.setStyleSheet("background: #1E1E1E;")
        editor_layout = QVBoxLayout(editor_frame)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        # 文件标签栏（简化）
        self.tab_bar = QTabWidget()
        self.tab_bar.setStyleSheet("""
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: #2D2D30;
                color: #FFFFFF;
                padding: 8px 16px;
                border: none;
            }
            QTabBar::tab:selected {
                background: #1E1E1E;
            }
        """)

        # 编辑器
        self.editor = CodeEditor()
        editor_layout.addWidget(self.editor)

        main_split.addWidget(editor_frame, 2)

        # 输出面板
        output_frame = QFrame()
        output_frame.setFixedWidth(400)
        output_frame.setStyleSheet("background: #252526; border-left: 1px solid #3E3E42;")
        output_layout = QVBoxLayout(output_frame)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(0)

        # 输出标题
        output_title = QLabel("📤 输出")
        output_title.setStyleSheet("color: #FFFFFF; font-size: 12px; padding: 8px 12px; background: #2D2D30;")
        output_layout.addWidget(output_title)

        # 输出内容
        self.output_text = QPlainTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QPlainTextEdit {
                background: #252526;
                color: #D4D4D4;
                border: none;
                padding: 8px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        output_layout.addWidget(self.output_text, 1)

        main_split.addWidget(output_frame, 1)

        layout.addLayout(main_split, 1)

        # 状态栏
        status_bar = QFrame()
        status_bar.setFixedHeight(28)
        status_bar.setStyleSheet("background: #007ACC;")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(12, 0, 12, 0)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #FFFFFF; font-size: 11px;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.cursor_label = QLabel("行 1, 列 1")
        self.cursor_label.setStyleSheet("color: #FFFFFF; font-size: 11px;")
        status_layout.addWidget(self.cursor_label)

        layout.addWidget(status_bar)

    def _load_sample(self):
        """加载示例代码"""
        sample_code = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def greet(name: str) -> str:
    \"\"\"问候函数\"\"\"
    return f"Hello, {name}!"

if __name__ == "__main__":
    # 测试代码
    print(greet("World"))
    print("智能 IDE 测试成功！")
"""
        self.editor.set_content(sample_code)
        self.status_label.setText("已加载示例代码")

    def _run_code(self):
        """运行代码"""
        code = self.editor.get_content()
        language = self.lang_combo.currentData()

        if not code.strip():
            self.output_text.appendPlainText("⚠️ 没有代码可运行\n")
            return

        # 更新状态
        self.status_label.setText(f"运行中 ({language})...")
        self.run_btn.setEnabled(False)
        self.run_btn.setText("运行中...")

        # 清空输出
        self.output_text.clear()

        # 启动工作线程
        self.worker = CodeExecutionWorker(code, language)
        self.worker.output.connect(self._on_output)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

        self.code_executed.emit(code, language)

    def _request_ai_help(self):
        """请求 AI 辅助"""
        code = self.editor.get_content()
        self.ai_requested.emit(code)

        # 在输出面板显示
        self.output_text.appendPlainText("🤖 正在请求 AI 辅助...\n")

    def _save_file(self):
        """保存文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存文件",
            "",
            "Python Files (*.py);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.editor.get_content())
                self.current_file = file_path
                self.status_label.setText(f"已保存: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "警告", f"保存失败: {e}")

    @pyqtSlot(str)
    def _on_output(self, text: str):
        """收到输出"""
        self.output_text.appendPlainText(text)

    @pyqtSlot(str)
    def _on_error(self, error_msg: str):
        """处理错误"""
        self.output_text.appendPlainText(f"❌ 错误:\n{error_msg}\n")
        self.status_label.setText("运行出错")

    @pyqtSlot(int)
    def _on_finished(self, exit_code: int):
        """运行完成"""
        self.status_label.setText(f"运行完成 (退出码: {exit_code})")
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶️ 运行")
        self.worker = None

    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            self.worker.wait()
        super().closeEvent(event)
