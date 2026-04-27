"""
智能写作模块 - 真实功能实现

支持文章撰写、AI 辅助写作、模板管理、导出功能。
"""

import os
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QFrame, QComboBox,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QTextCursor

from client.src.business.nanochat_config import config


# ── AI 写作工作线程 ─────────────────────────────────────────────────────

class AIWritingWorker(QThread):
    """AI 写作辅助工作线程"""

    chunk_received = pyqtSignal(str)  # 收到一个文本块
    finished = pyqtSignal(str)         # 完成（完整响应）
    error = pyqtSignal(str)             # 错误

    def __init__(self, base_url: str, model: str, prompt: str, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.model = model
        self.prompt = prompt
        self._stop_requested = False

    def run(self):
        try:
            import requests
            import json

            url = f"{self.base_url}/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是专业的写作助手，帮助用户撰写高质量的文章。"},
                    {"role": "user", "content": self.prompt}
                ],
                "stream": True,
            }

            response = requests.post(url, json=payload, headers=headers, stream=True, timeout=120)
            response.raise_for_status()

            full_content = ""
            for line in response.iter_lines():
                if self._stop_requested:
                    break
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    full_content += content
                                    self.chunk_received.emit(content)
                        except json.JSONDecodeError:
                            continue

            self.finished.emit(full_content)

        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._stop_requested = True


# ── 主智能写作面板 ─────────────────────────────────────────────────────

class Panel(QWidget):
    """智能写作面板 - 真实功能"""

    content_changed = pyqtSignal(str)  # 内容变更
    export_requested = pyqtSignal(str, str)  # 格式, 内容

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file: Optional[str] = None
        self.worker: Optional[AIWritingWorker] = None
        self._setup_ui()
        self._setup_ai()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        title_bar = QFrame()
        title_bar.setFixedHeight(52)
        title_bar.setStyleSheet("background: #FFFFFF; border-bottom: 1px solid #E0E0E0;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)

        title_label = QLabel("✍️ 智能写作")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # 模板选择
        self.template_combo = QComboBox()
        self.template_combo.addItem("📝 空白文档", "blank")
        self.template_combo.addItem("📄 文章模板", "article")
        self.template_combo.addItem("📧 邮件模板", "email")
        self.template_combo.addItem("📊 报告模板", "report")
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        self.template_combo.setStyleSheet("padding: 6px 12px;")
        title_layout.addWidget(self.template_combo)

        # AI 辅助按钮
        self.ai_btn = QPushButton("🤖 AI 辅助")
        self.ai_btn.setFixedSize(120, 36)
        self.ai_btn.setStyleSheet("""
            QPushButton {
                background: #4B0082;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background: #5A0099; }
            QPushButton:disabled { background: #BDBDBD; }
        """)
        self.ai_btn.clicked.connect(self._request_ai_help)
        title_layout.addWidget(self.ai_btn)

        # 导出按钮
        self.export_btn = QPushButton("📤 导出")
        self.export_btn.setFixedSize(80, 36)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background: #FF9800;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background: #F57C00; }
        """)
        self.export_btn.clicked.connect(self._export_document)
        title_layout.addWidget(self.export_btn)

        layout.addWidget(title_bar)

        # 写作区域
        self.editor = QTextEdit()
        self.editor.setStyleSheet("""
            QTextEdit {
                background: #FFFFFF;
                color: #333333;
                border: none;
                padding: 24px 48px;
                font-size: 14px;
                line-height: 1.8;
            }
            QTextEdit:focus {
                border: none;
            }
        """)
        self.editor.setFont(QFont("Microsoft YaHei", 14))
        self.editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.editor, 1)

        # AI 辅助面板（底部）
        self.ai_panel = QFrame()
        self.ai_panel.setFixedHeight(0)  # 默认隐藏
        self.ai_panel.setStyleSheet("background: #F5F5F5; border-top: 1px solid #E0E0E0;")
        ai_layout = QVBoxLayout(self.ai_panel)
        ai_layout.setContentsMargins(16, 8, 16, 8)

        ai_title = QLabel("🤖 AI 辅助")
        ai_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #666;")
        ai_layout.addWidget(ai_title)

        self.ai_output = QTextEdit()
        self.ai_output.setReadOnly(True)
        self.ai_output.setMaximumHeight(80)
        self.ai_output.setStyleSheet("""
            QTextEdit {
                background: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
            }
        """)
        ai_layout.addWidget(self.ai_output)

        layout.addWidget(self.ai_panel)

        # 状态栏
        status_bar = QFrame()
        status_bar.setFixedHeight(28)
        status_bar.setStyleSheet("background: #F5F5F5; border-top: 1px solid #E0E0E0;")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(12, 0, 12, 0)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("font-size: 11px; color: #666;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.word_count_label = QLabel("字数: 0")
        self.word_count_label.setStyleSheet("font-size: 11px; color: #666;")
        status_layout.addWidget(self.word_count_label)

        layout.addWidget(status_bar)

    def _setup_ai(self):
        """设置 AI"""
        self.base_url = config.ollama.url
        self.model_name = "qwen3.5:4b"

    def _on_template_changed(self, text: str):
        """模板切换"""
        template_type = self.template_combo.currentData()
        templates = {
            "article": """# 文章标题

## 引言

在这里写引言...

## 正文

在这里写正文...

## 结论

在这里写结论...
""",
            "email": """主题: [邮件主题]

尊敬的 [收件人],

您好！

[邮件正文]

此致
[你的名字]
""",
            "report": """# 报告标题

## 摘要

[摘要内容]

## 背景

[背景介绍]

## 分析

[分析内容]

## 建议

[建议内容]

## 结论

[结论]
""",
        }

        if template_type in templates:
            self.editor.setPlainText(templates[template_type])
            self.status_label.setText(f"已加载模板: {text}")

    def _on_text_changed(self):
        """文本变更"""
        content = self.editor.toPlainText()
        word_count = len(content.replace(" ", "").replace("\n", ""))
        self.word_count_label.setText(f"字数: {word_count}")

        self.content_changed.emit(content)

    def _request_ai_help(self):
        """请求 AI 辅助"""
        content = self.editor.toPlainText().strip()
        if not content:
            self.status_label.setText("⚠️ 请先输入内容")
            return

        # 显示 AI 面板
        self.ai_panel.setFixedHeight(120)
        self.ai_output.clear()
        self.ai_output.append("🤖 AI 正在思考...")

        # 更新状态
        self.status_label.setText("🤖 AI 辅助中...")
        self.ai_btn.setEnabled(False)
        self.ai_btn.setText("思考中...")

        # 构建提示
        prompt = f"请帮我改进以下内容，使其更加专业和流畅：\n\n{content}"

        # 启动工作线程
        self.worker = AIWritingWorker(self.base_url, self.model_name, prompt)
        self.worker.chunk_received.connect(self._on_ai_chunk)
        self.worker.finished.connect(self._on_ai_finished)
        self.worker.error.connect(self._on_ai_error)
        self.worker.start()

    def _export_document(self):
        """导出文档"""
        content = self.editor.toPlainText()
        if not content.strip():
            QMessageBox.warning(self, "警告", "没有内容可导出！")
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "导出文档",
            "",
            "Markdown Files (*.md);;Text Files (*.txt);;HTML Files (*.html)"
        )

        if file_path:
            try:
                format_type = "md"
                if file_path.endswith(".txt"):
                    format_type = "txt"
                elif file_path.endswith(".html"):
                    format_type = "html"

                # 转换格式
                if format_type == "html":
                    export_content = f"<html><body>\n{content}\n</body></html>"
                else:
                    export_content = content

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(export_content)

                self.status_label.setText(f"✅ 已导出: {file_path}")
                self.export_requested.emit(format_type, content)

            except Exception as e:
                QMessageBox.warning(self, "警告", f"导出失败: {e}")

    @pyqtSlot(str)
    def _on_ai_chunk(self, chunk: str):
        """收到 AI 文本块"""
        self.ai_output.append(chunk)

    @pyqtSlot(str)
    def _on_ai_finished(self, full_content: str):
        """AI 完成"""
        self.status_label.setText("✅ AI 辅助完成")
        self.ai_btn.setEnabled(True)
        self.ai_btn.setText("🤖 AI 辅助")
        self.worker = None

    @pyqtSlot(str)
    def _on_ai_error(self, error_msg: str):
        """AI 错误"""
        self.ai_output.append(f"❌ 错误: {error_msg}")
        self.status_label.setText("❌ AI 辅助失败")
        self.ai_btn.setEnabled(True)
        self.ai_btn.setText("🤖 AI 辅助")
        self.worker = None

    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        super().closeEvent(event)
