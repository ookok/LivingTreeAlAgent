"""
写作助手 UI 面板
集成到 Hermes Desktop 的 PyQt6 写作功能
"""
import json
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QComboBox, QSpinBox, QGroupBox,
    QProgressBar, QTabWidget, QListWidget, QListWidgetItem,
    QCheckBox, QScrollArea, QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPalette

from ..core.writing_assistant import WritingAssistant
from ..core.unified_model_client import GenerationConfig


class WritingWorker(QThread):
    """写作任务工作线程"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # current, total

    def __init__(self, assistant: WritingAssistant, task: Dict):
        super().__init__()
        self.assistant = assistant
        self.task = task

    def run(self):
        try:
            task_type = self.task.get("type", "")
            params = self.task.get("params", {})

            if task_type == "generate":
                result = self.assistant.generate_text(**params)
            elif task_type == "outline":
                result = self.assistant.outline_chapter(**params)
            elif task_type == "polish":
                result = self.assistant.polish_text(**params)
            elif task_type == "expand":
                result = self.assistant.expand_scene(**params)
            elif task_type == "continue":
                result = self.assistant.continue_writing(**params)
            else:
                result = f"[错误] 未知任务类型: {task_type}"

            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class TaskItemWidget(QFrame):
    """任务卡片组件"""
    delete_clicked = pyqtSignal(int)

    def __init__(self, task_id: int, task_data: Dict):
        super().__init__()
        self.task_id = task_id
        self.task_data = task_data
        self.setup_ui()

    def setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            TaskItemWidget {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 8px;
                margin: 4px;
            }
            TaskItemWidget:hover {
                background: #e9ecef;
            }
        """)

        layout = QHBoxLayout()

        # 任务类型标签
        type_label = QLabel(self.task_data.get("type", "unknown").upper())
        type_label.setStyleSheet("""
            background: #007bff;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
        """)
        layout.addWidget(type_label)

        # 任务描述
        desc = self.task_data.get("params", {}).get("prompt", "")[:30]
        if not desc:
            desc = self.task_data.get("params", {}).get("text", "")[:30]
        desc_label = QLabel(f"{desc}...")
        desc_label.setStyleSheet("color: #6c757d;")
        layout.addWidget(desc_label, 1)

        # 删除按钮
        delete_btn = QPushButton("×")
        delete_btn.setFixedSize(24, 24)
        delete_btn.setStyleSheet("""
            QPushButton {
                background: #dc3545;
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #c82333;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.task_id))
        layout.addWidget(delete_btn)

        self.setLayout(layout)


class WritingAssistantPanel(QWidget):
    """
    写作助手面板
    支持本地/远程模型切换，多种写作任务
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.assistant: Optional[WritingAssistant] = None
        self.tasks: List[Dict] = []
        self.workers: List[WritingWorker] = []
        self.setup_ui()
        self.init_assistant()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # ===== 顶部设置栏 =====
        settings_bar = QGroupBox("⚙️ 模型设置")
        settings_layout = QHBoxLayout()

        # 模型切换
        self.use_local_cb = QCheckBox("使用本地模型")
        self.use_local_cb.setChecked(True)
        self.use_local_cb.stateChanged.connect(self.on_model_mode_changed)
        settings_layout.addWidget(self.use_local_cb)

        # 本地模型路径
        settings_layout.addWidget(QLabel("本地模型:"))
        self.local_model_path = QComboBox()
        self.local_model_path.setEditable(True)
        self.local_model_path.addItems([
            "自动检测",
            "deepseek-r1-7b.Q4_K_M.gguf",
            "qwen2.5-7b-instruct-q4_k_m.gguf",
        ])
        settings_layout.addWidget(self.local_model_path, 1)

        # 远程 API
        settings_layout.addWidget(QLabel("API:"))
        self.remote_api = QComboBox()
        self.remote_api.addItems([
            "DeepSeek (推荐)",
            "OpenAI",
            "OpenRouter",
            "自定义",
        ])
        self.remote_api.setEnabled(False)
        settings_layout.addWidget(self.remote_api)

        # 初始化按钮
        self.init_btn = QPushButton("🔄 初始化")
        self.init_btn.clicked.connect(self.init_assistant)
        settings_layout.addWidget(self.init_btn)

        settings_bar.setLayout(settings_layout)
        main_layout.addWidget(settings_bar)

        # ===== 写作工具标签页 =====
        self.tools_tabs = QTabWidget()

        # --- 生成页 ---
        gen_widget = QWidget()
        gen_layout = QVBoxLayout(gen_widget)

        gen_layout.addWidget(QLabel("📝 输入写作提示"))
        self.gen_prompt = QTextEdit()
        self.gen_prompt.setPlaceholderText("描述你想写的内容...")
        self.gen_prompt.setMaximumHeight(120)
        gen_layout.addWidget(self.gen_prompt)

        gen_options = QHBoxLayout()
        gen_options.addWidget(QLabel("风格:"))
        self.gen_style = QComboBox()
        self.gen_style.addItems(["novel-小说", "poetic-诗意", "simple-简洁"])
        gen_options.addWidget(self.gen_style)

        gen_options.addWidget(QLabel("长度:"))
        self.gen_max_tokens = QSpinBox()
        self.gen_max_tokens.setRange(256, 8192)
        self.gen_max_tokens.setValue(1024)
        self.gen_max_tokens.setSuffix(" tokens")
        gen_options.addWidget(self.gen_max_tokens)
        gen_options.addStretch()
        gen_layout.addLayout(gen_options)

        gen_btn = QPushButton("🎨 生成文本")
        gen_btn.clicked.connect(lambda: self.add_task("generate"))
        gen_layout.addWidget(gen_btn)
        gen_layout.addStretch()

        # --- 润色页 ---
        polish_widget = QWidget()
        polish_layout = QVBoxLayout(polish_widget)

        polish_layout.addWidget(QLabel("✏️ 输入待润色文本"))
        self.polish_text = QTextEdit()
        self.polish_text.setPlaceholderText("粘贴需要润色的文本...")
        polish_layout.addWidget(self.polish_text)

        polish_options = QHBoxLayout()
        polish_options.addWidget(QLabel("风格:"))
        self.polish_style = QComboBox()
        self.polish_style.addItems(["elegant-典雅", "concise-简洁", "dramatic-戏剧"])
        polish_options.addWidget(self.polish_style)
        polish_options.addStretch()
        polish_layout.addLayout(polish_options)

        polish_btn = QPushButton("✨ 润色文本")
        polish_btn.clicked.connect(lambda: self.add_task("polish"))
        polish_layout.addWidget(polish_btn)
        polish_layout.addStretch()

        # --- 大纲页 ---
        outline_widget = QWidget()
        outline_layout = QVBoxLayout(outline_widget)

        outline_layout.addWidget(QLabel("📋 前文摘要"))
        self.outline_summary = QTextEdit()
        self.outline_summary.setPlaceholderText("输入前文摘要...")
        self.outline_summary.setMaximumHeight(100)
        outline_layout.addWidget(self.outline_summary)

        outline_meta = QHBoxLayout()
        outline_meta.addWidget(QLabel("章节号:"))
        self.outline_chapter = QSpinBox()
        self.outline_chapter.setRange(1, 9999)
        outline_meta.addWidget(self.outline_chapter)

        outline_meta.addWidget(QLabel("主题:"))
        self.outline_theme = QComboBox()
        self.outline_theme.addItems(["", "冲突升级", "情感转折", "揭秘", "高潮", "结局"])
        outline_meta.addWidget(self.outline_theme, 1)
        outline_layout.addLayout(outline_meta)

        outline_btn = QPushButton("📑 生成大纲")
        outline_btn.clicked.connect(lambda: self.add_task("outline"))
        outline_layout.addWidget(outline_btn)
        outline_layout.addStretch()

        # --- 批量处理页 ---
        batch_widget = QWidget()
        batch_layout = QVBoxLayout(batch_widget)

        batch_layout.addWidget(QLabel("📋 任务列表"))
        self.task_list = QListWidget()
        self.task_list.setMinimumHeight(150)
        batch_layout.addWidget(self.task_list)

        batch_btns = QHBoxLayout()
        add_batch_btn = QPushButton("➕ 添加选中任务")
        add_batch_btn.clicked.connect(self.add_selected_task)
        batch_btns.addWidget(add_batch_btn)

        clear_btn = QPushButton("🗑 清空")
        clear_btn.clicked.connect(self.clear_tasks)
        batch_btns.addWidget(clear_btn)

        batch_btns.addStretch()
        batch_layout.addLayout(batch_btns)

        self.batch_run_btn = QPushButton("🚀 开始批量处理")
        self.batch_run_btn.clicked.connect(self.run_batch)
        self.batch_run_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                padding: 10px;
                border-radius: 6px;
                font-weight: bold;
            }
        """)
        batch_layout.addWidget(self.batch_run_btn)

        self.tools_tabs.addTab(gen_widget, "📝 生成")
        self.tools_tabs.addTab(polish_widget, "✏️ 润色")
        self.tools_tabs.addTab(outline_widget, "📑 大纲")
        self.tools_tabs.addTab(batch_widget, "📋 批量")
        main_layout.addWidget(self.tools_tabs)

        # ===== 输出区域 =====
        output_group = QGroupBox("📤 输出结果")
        output_layout = QVBoxLayout()

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', monospace;
                font-size: 13px;
            }
        """)
        output_layout.addWidget(self.output_text)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        output_layout.addWidget(self.progress_bar)

        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group, 1)

        # ===== 底部操作栏 =====
        bottom_bar = QHBoxLayout()

        bottom_bar.addWidget(QLabel("温度:"))
        self.temperature = QSpinBox()
        self.temperature.setRange(1, 100)
        self.temperature.setValue(70)
        self.temperature.setSuffix(" %")
        bottom_bar.addWidget(self.temperature)

        bottom_bar.addStretch()

        copy_btn = QPushButton("📋 复制结果")
        copy_btn.clicked.connect(self.copy_output)
        bottom_bar.addWidget(copy_btn)

        save_btn = QPushButton("💾 保存")
        save_btn.clicked.connect(self.save_output)
        bottom_bar.addWidget(save_btn)

        main_layout.addLayout(bottom_bar)

    def init_assistant(self):
        """初始化写作助手"""
        use_local = self.use_local_cb.isChecked()

        try:
            self.assistant = WritingAssistant(
                use_local=use_local,
                n_threads=12,
            )
            self.append_output("✅ 写作助手初始化成功")
            self.init_btn.setText("🔄 已连接")
            self.init_btn.setEnabled(False)
        except Exception as e:
            self.append_output(f"❌ 初始化失败: {e}")
            self.init_btn.setText("🔄 重试")

    def on_model_mode_changed(self, state):
        """模型模式切换"""
        self.local_model_path.setEnabled(state)
        self.remote_api.setEnabled(not state)

    def add_task(self, task_type: str):
        """添加任务"""
        if not self.assistant:
            self.append_output("❌ 请先初始化写作助手")
            return

        params = {}
        if task_type == "generate":
            prompt = self.gen_prompt.toPlainText().strip()
            if not prompt:
                self.append_output("❌ 请输入写作提示")
                return
            params = {
                "prompt": prompt,
                "style": self.gen_style.currentText().split("-")[0],
                "max_tokens": self.gen_max_tokens.value(),
            }
        elif task_type == "polish":
            text = self.polish_text.toPlainText().strip()
            if not text:
                self.append_output("❌ 请输入待润色文本")
                return
            params = {
                "text": text,
                "style": self.polish_style.currentText().split("-")[0],
            }
        elif task_type == "outline":
            summary = self.outline_summary.toPlainText().strip()
            if not summary:
                self.append_output("❌ 请输入前文摘要")
                return
            params = {
                "previous_summary": summary,
                "chapter_number": self.outline_chapter.value(),
                "theme": self.outline_theme.currentText(),
            }
        elif task_type == "continue":
            text = self.continue_text.toPlainText().strip()
            if not text:
                self.append_output("❌ 请输入续写文本")
                return
            params = {"previous_text": text}

        task = {"type": task_type, "params": params}
        self.tasks.append(task)

        # 更新批量列表
        self.update_task_list()
        self.append_output(f"➕ 已添加任务: {task_type}")

    def add_selected_task(self):
        """添加选中的任务类型"""
        current_tab = self.tools_tabs.currentIndex()
        task_types = ["generate", "polish", "outline", "continue"]
        self.add_task(task_types[current_tab])

    def update_task_list(self):
        """更新任务列表显示"""
        self.task_list.clear()
        for i, task in enumerate(self.tasks):
            item = QListWidgetItem(f"[{i+1}] {task['type']}")
            self.task_list.addItem(item)

    def clear_tasks(self):
        """清空任务列表"""
        self.tasks.clear()
        self.update_task_list()
        self.append_output("🗑 任务列表已清空")

    def run_batch(self):
        """执行批量任务"""
        if not self.assistant:
            self.append_output("❌ 请先初始化写作助手")
            return

        if not self.tasks:
            self.append_output("❌ 请先添加任务")
            return

        self.batch_run_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.tasks))
        self.progress_bar.setValue(0)
        self.append_output(f"🚀 开始批量处理 ({len(self.tasks)} 个任务)...")

        self.batch_index = 0
        self.batch_results = []
        self.run_next_batch_task()

    def run_next_batch_task(self):
        """执行下一个批量任务"""
        if self.batch_index >= len(self.tasks):
            self.batch_finished()
            return

        task = self.tasks[self.batch_index]
        self.append_output(f"\n--- 任务 {self.batch_index + 1}/{len(self.tasks)}: {task['type']} ---")

        worker = WritingWorker(self.assistant, task)
        worker.finished.connect(self.on_batch_task_finished)
        worker.error.connect(self.on_batch_task_error)
        self.workers.append(worker)
        worker.start()

    def on_batch_task_finished(self, result: str):
        """批量任务完成"""
        self.batch_results.append(result)
        self.progress_bar.setValue(self.batch_index + 1)
        self.batch_index += 1
        self.run_next_batch_task()

    def on_batch_task_error(self, error: str):
        """批量任务错误"""
        self.batch_results.append(f"[错误] {error}")
        self.batch_index += 1
        self.run_next_batch_task()

    def batch_finished(self):
        """批量处理完成"""
        self.progress_bar.setVisible(False)
        self.batch_run_btn.setEnabled(True)

        self.append_output("\n" + "=" * 50)
        self.append_output("📊 批量处理完成")
        self.append_output("=" * 50)

        for i, result in enumerate(self.batch_results):
            self.append_output(f"\n--- 结果 {i + 1} ---\n{result}")

        self.append_output(f"\n✅ 共处理 {len(self.batch_results)} 个任务")

    def append_output(self, text: str):
        """追加输出文本"""
        self.output_text.append(text)

    def copy_output(self):
        """复制输出"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.output_text.toPlainText())
        self.append_output("📋 已复制到剪贴板")

    def save_output(self):
        """保存输出"""
        from PyQt6.QtWidgets import QFileDialog
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存结果", "", "Text Files (*.txt);;All Files (*)"
        )
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self.output_text.toPlainText())
            self.append_output(f"💾 已保存到: {filepath}")


from PyQt6.QtWidgets import QApplication
