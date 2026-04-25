"""
全学科智能写作助手 Tab
AI Writing Assistant Tab

集成到主界面的写作助手，作为独立的 Tab 页面使用。
支持：
- 学科自适应写作
- 多种文档格式
- 任务分解写作
- 实时预览
"""

import os
import json
import re
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QPushButton, QLabel, QComboBox, QLineEdit,
    QTabWidget, QListWidget, QListWidgetItem, QGroupBox,
    QScrollArea, QProgressBar, QCheckBox, QSpinBox,
    QFileDialog, QMessageBox, QToolBar, QTextBrowser
)
from PyQt6.QtGui import QFont, QAction, QIcon, QTextCursor

from writing.ai_writer import AIWriter, WritingContext, WritingMode, DocType, SubjectDomain, WritingFormat
from writing.outline_generator import OutlineGenerator
from client.src.business.task_decomposer import TaskDecomposer, ChainOfThoughtExecutor, DecomposedTask


@dataclass
class WritingProject:
    """写作项目"""
    id: str
    title: str
    doc_type: str
    subject: str
    content: str = ""
    outline: list = None
    created_at: str = ""
    updated_at: str = ""


class WritingWorker(QThread):
    """写作后台工作线程"""
    
    finished_signal = pyqtSignal(str)  # 完成信号
    progress_signal = pyqtSignal(str, int, int)  # 进度信号 (step_title, current, total)
    error_signal = pyqtSignal(str)  # 错误信号
    
    def __init__(self, task: DecomposedTask, executor: ChainOfThoughtExecutor):
        super().__init__()
        self.task = task
        self.executor = executor
    
    def run(self):
        """执行任务"""
        try:
            # 设置进度回调
            def progress_callback(step, current, total):
                self.progress_signal.emit(step.title, current, total)
            
            self.executor.progress_callback = progress_callback
            
            # 执行
            result = self.executor.execute(self.task)
            
            # 生成最终结果
            from client.src.business.task_decomposer import format_task_result
            output = format_task_result(result)
            
            self.finished_signal.emit(output)
            
        except Exception as e:
            self.error_signal.emit(str(e))


class WritingTab(QWidget):
    """
    智能写作助手 Tab
    
    集成到主窗口，作为独立的写作工作区。
    """
    
    # 信号
    status_changed = pyqtSignal(str)
    
    def __init__(self, parent=None, hermes_agent=None):
        """
        初始化写作 Tab
        
        Args:
            parent: 父窗口
            hermes_agent: Hermes Agent 实例
        """
        super().__init__(parent)
        
        self.agent = hermes_agent
        self.ai_writer = AIWriter(agent=hermes_agent)
        self.task_decomposer = TaskDecomposer()
        self.chain_executor = ChainOfThoughtExecutor(
            llm_callable=self._call_ai,
            progress_callback=None
        )
        
        self._current_project: Optional[WritingProject] = None
        self._current_task: Optional[DecomposedTask] = None
        self._worker: Optional[WritingWorker] = None
        
        self._setup_ui()
        self._setup_toolbar()
        self._load_projects()
    
    def set_agent(self, agent):
        """设置 Agent"""
        self.agent = agent
        self.ai_writer.set_agent(agent)
    
    def _setup_toolbar(self):
        """设置工具栏"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFixedHeight(36)
        
        # 新建项目
        new_act = QAction("📄 新建", self)
        new_act.triggered.connect(self._new_project)
        toolbar.addAction(new_act)
        
        toolbar.addSeparator()
        
        # 保存
        save_act = QAction("💾 保存", self)
        save_act.triggered.connect(self._save_project)
        toolbar.addAction(save_act)
        
        # 导出
        export_act = QAction("📤 导出", self)
        export_act.triggered.connect(self._export_project)
        toolbar.addAction(export_act)
        
        toolbar.addSeparator()
        
        # 任务分解
        decompose_act = QAction("🔍 任务分解", self)
        decompose_act.triggered.connect(self._decompose_task)
        toolbar.addAction(decompose_act)
        
        # 自动写作
        write_act = QAction("✨ 智能写作", self)
        write_act.triggered.connect(self._start_writing)
        toolbar.addAction(write_act)
        
        toolbar.addWidget(QLabel())
        
        # 切换视图
        self.view_combo = QComboBox()
        self.view_combo.addItems(["编辑器", "预览", "分步视图"])
        self.view_combo.currentTextChanged.connect(self._switch_view)
        toolbar.addWidget(self.view_combo)
        
        self.layout().addWidget(toolbar)
    
    def _setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 顶部工具栏占位
        self._toolbar_placeholder = QWidget()
        main_layout.addWidget(self._toolbar_placeholder)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：项目列表 + 设置
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        # 右侧：编辑/预览区
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 900])
        
        main_layout.addWidget(splitter)
        
        # 状态栏
        self._status_bar = QLabel("就绪")
        self._status_bar.setStyleSheet(
            "background:#1e1e1e;border-top:1px solid #333;padding:4px 12px;color:#888;"
        )
        main_layout.addWidget(self._status_bar)
        
        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background: #2a2a2a;
                border: none;
            }
            QProgressBar::chunk {
                background: #3b82f6;
            }
        """)
        main_layout.addWidget(self._progress_bar)
    
    def _create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 项目列表
        list_group = QGroupBox("📁 项目列表")
        list_layout = QVBoxLayout(list_group)
        
        self._project_list = QListWidget()
        self._project_list.itemClicked.connect(self._on_project_selected)
        list_layout.addWidget(self._project_list)
        
        list_btn_layout = QHBoxLayout()
        add_btn = QPushButton("+ 新建")
        add_btn.clicked.connect(self._new_project)
        del_btn = QPushButton("- 删除")
        del_btn.clicked.connect(self._delete_project)
        list_btn_layout.addWidget(add_btn)
        list_btn_layout.addWidget(del_btn)
        list_layout.addLayout(list_btn_layout)
        
        layout.addWidget(list_group)
        
        # 写作设置
        settings_group = QGroupBox("⚙️ 写作设置")
        settings_layout = QVBoxLayout(settings_group)
        
        # 文档类型
        settings_layout.addWidget(QLabel("文档类型"))
        self._doc_type_combo = QComboBox()
        self._doc_type_combo.addItems([
            "通用文档", "学术论文", "技术报告", "商业计划书",
            "市场分析", "项目方案", "培训教材", "新闻稿"
        ])
        settings_layout.addWidget(self._doc_type_combo)
        
        # 学科领域
        settings_layout.addWidget(QLabel("学科领域"))
        self._subject_combo = QComboBox()
        self._subject_combo.addItems([
            "通用", "计算机/AI", "商业管理", "金融经济",
            "法律合规", "教育", "医疗健康", "工程技术"
        ])
        settings_layout.addWidget(self._subject_combo)
        
        # 输出格式
        settings_layout.addWidget(QLabel("输出格式"))
        self._format_combo = QComboBox()
        self._format_combo.addItems(["Markdown", "LaTeX", "纯文本", "HTML"])
        settings_layout.addWidget(self._format_combo)
        
        # 链式思考
        self._chain_thought_check = QCheckBox("启用任务分解（链式思考）")
        self._chain_thought_check.setChecked(True)
        settings_layout.addWidget(self._chain_thought_check)
        
        # 最大步数
        settings_layout.addWidget(QLabel("任务分解步数"))
        self._max_steps_spin = QSpinBox()
        self._max_steps_spin.setRange(2, 8)
        self._max_steps_spin.setValue(4)
        settings_layout.addWidget(self._max_steps_spin)
        
        layout.addWidget(settings_group)
        
        # 大纲
        outline_group = QGroupBox("📋 大纲")
        outline_layout = QVBoxLayout(outline_group)
        
        self._outline_list = QListWidget()
        self._outline_list.setMaximumHeight(150)
        outline_layout.addWidget(self._outline_list)
        
        outline_btn_layout = QHBoxLayout()
        gen_outline_btn = QPushButton("生成大纲")
        gen_outline_btn.clicked.connect(self._generate_outline)
        clear_outline_btn = QPushButton("清空")
        clear_outline_btn.clicked.connect(lambda: self._outline_list.clear())
        outline_btn_layout.addWidget(gen_outline_btn)
        outline_btn_layout.addWidget(clear_outline_btn)
        outline_layout.addLayout(outline_btn_layout)
        
        layout.addWidget(outline_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_right_panel(self) -> QWidget:
        """创建右侧面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 标题输入
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("标题:"))
        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("输入文章标题...")
        self._title_input.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_layout.addWidget(self._title_input)
        layout.addLayout(title_layout)
        
        # Tab 切换
        self._content_tabs = QTabWidget()
        
        # 编辑器
        self._editor = QTextEdit()
        self._editor.setFont(QFont("Consolas", 11))
        self._editor.setPlaceholderText("在此输入内容，或点击「智能写作」让AI帮你创作...\n\n快捷指令：\n- /outline - 生成大纲\n- /expand - 续写\n- /polish - 润色\n- /summary - 总结")
        self._editor.textChanged.connect(self._on_content_changed)
        self._content_tabs.addTab(self._editor, "✏️ 编辑器")
        
        # 预览
        self._preview = QTextBrowser()
        self._preview.setOpenExternalLinks(True)
        self._content_tabs.addTab(self._preview, "👁️ 预览")
        
        # 任务分步视图
        self._steps_view = self._create_steps_view()
        self._content_tabs.addTab(self._steps_view, "🔍 分步视图")
        
        layout.addWidget(self._content_tabs)
        
        # 底部操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self._decompose_btn = QPushButton("🔍 任务分解")
        self._decompose_btn.clicked.connect(self._decompose_task)
        btn_layout.addWidget(self._decompose_btn)
        
        self._write_btn = QPushButton("✨ 智能写作")
        self._write_btn.clicked.connect(self._start_writing)
        btn_layout.addWidget(self._write_btn)
        
        self._continue_btn = QPushButton("📝 继续写作")
        self._continue_btn.clicked.connect(self._continue_writing)
        btn_layout.addWidget(self._continue_btn)
        
        self._polish_btn = QPushButton("🎨 润色")
        self._polish_btn.clicked.connect(self._polish_text)
        btn_layout.addWidget(self._polish_btn)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def _create_steps_view(self) -> QWidget:
        """创建任务分步视图"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 步骤列表
        self._steps_list = QListWidget()
        self._steps_list.itemClicked.connect(self._on_step_selected)
        layout.addWidget(self._steps_list)
        
        # 步骤详情
        detail_layout = QVBoxLayout()
        detail_layout.addWidget(QLabel("步骤详情"))
        
        self._step_detail = QTextBrowser()
        self._step_detail.setMaximumHeight(200)
        layout.addWidget(self._step_detail)
        
        return widget
    
    def _set_status(self, msg: str):
        """设置状态"""
        self._status_bar.setText(msg)
        self.status_changed.emit(msg)
    
    def _load_projects(self):
        """加载项目列表"""
        self._project_list.clear()
        
        # TODO: 从文件/数据库加载项目
        # 暂时添加示例
        example_projects = [
            WritingProject("1", "AI技术发展趋势分析", "技术报告", "计算机/AI"),
            WritingProject("2", "企业数字化转型方案", "商业计划书", "商业管理"),
        ]
        
        for p in example_projects:
            item = QListWidgetItem(f"📄 {p.title}")
            item.setData(Qt.ItemDataRole.UserRole, p)
            self._project_list.addItem(item)
    
    def _new_project(self):
        """新建项目"""
        self._current_project = WritingProject(
            id="new",
            title="未命名文档",
            doc_type=self._doc_type_combo.currentText(),
            subject=self._subject_combo.currentText()
        )
        
        self._title_input.setText("")
        self._editor.clear()
        self._outline_list.clear()
        self._steps_list.clear()
        self._step_detail.clear()
        
        self._set_status("新建项目")
    
    def _save_project(self):
        """保存项目"""
        if self._current_project:
            self._current_project.title = self._title_input.text()
            self._current_project.content = self._editor.toPlainText()
            self._current_project.updated_at = "2024-01-01"  # TODO: 实际时间
            
            # TODO: 保存到数据库/文件
            
            self._set_status("✅ 项目已保存")
            self._show_toast("项目已保存", "success")
    
    def _export_project(self):
        """导出项目"""
        content = self._editor.toPlainText()
        if not content:
            self._show_toast("没有内容可导出", "warning")
            return
        
        # 选择格式
        fmt = self._format_combo.currentText().lower()
        ext_map = {"markdown": "md", "latex": "tex", "纯文本": "txt", "html": "html"}
        ext = ext_map.get(fmt, "md")
        
        # 选择路径
        title = self._title_input.text() or "document"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出文档",
            str(Path.home() / f"{title}.{ext}"),
            f"文档 (*.{ext});;所有文件 (*)"
        )
        
        if path:
            try:
                Path(path).write_text(content, encoding="utf-8")
                self._show_toast(f"已导出到: {path}", "success")
            except Exception as e:
                self._show_toast(f"导出失败: {e}", "error")
    
    def _on_project_selected(self, item: QListWidgetItem):
        """项目选中"""
        project = item.data(Qt.ItemDataRole.UserRole)
        if project:
            self._current_project = project
            self._title_input.setText(project.title)
            self._editor.setPlainText(project.content)
            self._set_status(f"已加载: {project.title}")
    
    def _delete_project(self):
        """删除项目"""
        current = self._project_list.currentItem()
        if current:
            reply = QMessageBox.question(
                self, "确认删除",
                "确定要删除这个项目吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                row = self._project_list.row(current)
                self._project_list.takeItem(row)
                self._show_toast("项目已删除", "info")
    
    def _generate_outline(self):
        """生成大纲"""
        title = self._title_input.text()
        if not title:
            self._show_toast("请先输入标题", "warning")
            return
        
        self._set_status("正在生成大纲...")
        
        # 使用大纲生成器
        doc_type_map = {
            "通用文档": DocType.GENERAL,
            "学术论文": DocType.TECHNICAL_REPORT,
            "技术报告": DocType.TECHNICAL_REPORT,
            "商业计划书": DocType.BUSINESS_PLAN,
        }
        
        doc_type = doc_type_map.get(
            self._doc_type_combo.currentText(), 
            DocType.GENERAL
        )
        
        outline = self.ai_writer.generate_outline(title, doc_type)
        
        # 显示大纲
        self._outline_list.clear()
        for i, item in enumerate(outline, 1):
            self._outline_list.addItem(f"{i}. {item}")
        
        self._set_status("大纲已生成")
    
    def _decompose_task(self):
        """任务分解"""
        question = self._editor.toPlainText() or self._title_input.text()
        
        if not question:
            self._show_toast("请输入内容后再进行任务分解", "warning")
            return
        
        self._set_status("正在进行任务分解...")
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        
        # 分解任务
        max_steps = self._max_steps_spin.value()
        self._current_task = self.task_decomposer.decompose(
            question, 
            max_steps=max_steps
        )
        
        # 显示步骤
        self._steps_list.clear()
        for step in self._current_task.steps:
            status_icon = "⏳" if step.status.value == "pending" else "✅"
            item = QListWidgetItem(f"{status_icon} {step.step_id}. {step.title}")
            item.setData(Qt.ItemDataRole.UserRole, step)
            self._steps_list.addItem(item)
        
        # 切换到分步视图
        self._content_tabs.setCurrentIndex(2)
        
        self._set_status(f"任务已分解为 {len(self._current_task.steps)} 个步骤")
        self._progress_bar.setVisible(False)
        
        self._show_toast("任务分解完成，点击「智能写作」开始执行", "success")
    
    def _start_writing(self):
        """开始智能写作"""
        question = self._editor.toPlainText() or self._title_input.text()
        
        if not question:
            self._show_toast("请输入内容后再开始写作", "warning")
            return
        
        self._set_status("正在进行智能写作...")
        self._write_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        
        if self._chain_thought_check.isChecked() and self._current_task:
            # 使用任务分解模式
            self._run_chain_thought()
        else:
            # 直接生成
            self._run_direct_writing()
    
    def _run_chain_thought(self):
        """运行链式思考写作"""
        if not self._current_task:
            self._decompose_task()
        
        # 创建工作线程
        self._worker = WritingWorker(self._current_task, self.chain_executor)
        self._worker.progress_signal.connect(self._on_step_progress)
        self._worker.finished_signal.connect(self._on_writing_finished)
        self._worker.error_signal.connect(self._on_writing_error)
        self._worker.start()
    
    def _run_direct_writing(self):
        """直接写作"""
        title = self._title_input.text()
        content = self._call_ai(
            f"请为「{title}」写一篇完整的文章。\n\n"
            f"类型: {self._doc_type_combo.currentText()}\n"
            f"学科: {self._subject_combo.currentText()}\n"
            f"格式: {self._format_combo.currentText()}"
        )
        
        self._editor.setPlainText(content)
        self._update_preview(content)
        self._write_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._set_status("写作完成")
        self._show_toast("写作完成", "success")
    
    def _on_step_progress(self, step_title: str, current: int, total: int):
        """步骤进度更新"""
        progress = int(current / total * 100)
        self._progress_bar.setValue(progress)
        self._set_status(f"正在执行: {step_title} ({current}/{total})")
        
        # 更新步骤列表
        for i in range(self._steps_list.count()):
            item = self._steps_list.item(i)
            step = item.data(Qt.ItemDataRole.UserRole)
            if step and step.title == step_title:
                item.setText(f"🔄 {step.step_id}. {step_title}")
                break
    
    def _on_writing_finished(self, result: str):
        """写作完成"""
        self._editor.setPlainText(result)
        self._update_preview(result)
        
        # 更新步骤状态
        for i in range(self._steps_list.count()):
            item = self._steps_list.item(i)
            step = item.data(Qt.ItemDataRole.UserRole)
            if step:
                item.setText(f"✅ {step.step_id}. {step.title}")
        
        self._write_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._set_status("✅ 智能写作完成")
        self._show_toast("智能写作完成", "success")
    
    def _on_writing_error(self, error: str):
        """写作错误"""
        self._write_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._set_status(f"❌ 错误: {error}")
        self._show_toast(f"写作出错: {error}", "error")
    
    def _continue_writing(self):
        """继续写作"""
        current = self._editor.toPlainText()
        
        if not current:
            self._show_toast("请先输入一些内容", "warning")
            return
        
        self._set_status("正在续写...")
        
        result = self.ai_writer.continue_writing(
            current,
            "继续以上内容，保持相同的风格和格式"
        )
        
        if result.success:
            self._editor.setPlainText(result.content)
            self._update_preview(result.content)
            self._show_toast("续写完成", "success")
        else:
            self._show_toast(result.errors[0] if result.errors else "续写失败", "error")
        
        self._set_status("就绪")
    
    def _polish_text(self):
        """润色文本"""
        current = self._editor.toPlainText()
        
        if not current:
            self._show_toast("请先输入一些内容", "warning")
            return
        
        self._set_status("正在润色...")
        
        result = self.ai_writer.revise_text(
            current,
            "润色以下文本，使其更加流畅、专业"
        )
        
        if result.success:
            self._editor.setPlainText(result.content)
            self._update_preview(result.content)
            self._show_toast("润色完成", "success")
        else:
            self._show_toast(result.errors[0] if result.errors else "润色失败", "error")
        
        self._set_status("就绪")
    
    def _on_step_selected(self, item: QListWidgetItem):
        """步骤选中"""
        step = item.data(Qt.ItemDataRole.UserRole)
        if step:
            detail = f"**{step.title}**\n\n"
            detail += f"描述: {step.description}\n\n"
            detail += f"状态: {step.status.value}\n\n"
            
            if step.output_data:
                detail += f"**输出**:\n{step.output_data}"
            
            self._step_detail.setMarkdown(detail)
    
    def _on_content_changed(self):
        """内容变化"""
        content = self._editor.toPlainText()
        self._update_preview(content)
    
    def _update_preview(self, content: str):
        """更新预览"""
        # 简单的 Markdown 渲染
        import markdown
        html = markdown.markdown(content)
        
        # 添加样式
        styled_html = f"""
        <html>
        <head>
        <style>
            body {{ 
                font-family: 'Segoe UI', sans-serif;
                padding: 20px;
                line-height: 1.6;
            }}
            h1 {{ color: #1a1a1a; border-bottom: 2px solid #3b82f6; }}
            h2 {{ color: #333; }}
            code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }}
            pre {{ background: #f5f5f5; padding: 15px; border-radius: 8px; overflow-x: auto; }}
        </style>
        </head>
        <body>{html}</body>
        </html>
        """
        
        self._preview.setHtml(styled_html)
    
    def _switch_view(self, view_name: str):
        """切换视图"""
        if view_name == "预览":
            self._update_preview(self._editor.toPlainText())
    
    def _call_ai(self, prompt: str) -> str:
        """调用 AI"""
        if self.agent:
            try:
                # 简单实现，实际应使用 agent.send_message
                return f"[AI 生成内容]\n\n{prompt}"
            except Exception as e:
                return f"[AI 调用失败: {e}]"
        else:
            return "[请先连接 AI Agent]"
    
    def _show_toast(self, message: str, toast_type: str = "info"):
        """显示通知"""
        from ui.toast_notification import show_toast, ToastType
        
        type_map = {
            "success": ToastType.SUCCESS,
            "warning": ToastType.WARNING,
            "error": ToastType.ERROR,
            "info": ToastType.INFO,
        }
        
        show_toast(message, type_map.get(toast_type, ToastType.INFO))
