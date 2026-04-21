# -*- coding: utf-8 -*-
"""
Markdown转Word文档系统 - PyQt6 UI面板
======================================

功能：
- 文件选择与配置
- 转换进度显示
- 知识库集成
- 模板管理

作者：Hermes Desktop Team
版本：1.0.0
"""

import os
import sys
from typing import Optional, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QPushButton, QLabel, QLineEdit,
    QTextEdit, QListWidget, QListWidgetItem,
    QFileDialog, QProgressBar, QComboBox, QCheckBox,
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QDialog, QDialogButtonBox,
    QStatusBar, QToolBar, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QIcon, QFont

from core.md_to_doc import (
    ConversionConfig, Task, TaskStatus, TargetFormat,
    TaskType, StyleTemplate, get_default_template, get_builtin_templates,
    ImageConfig, LinkConfig, CodeConfig, TableConfig,
    PageConfig, HeaderFooterConfig, TOCConfig,
    ImageMode, LinkMode, CodeHighlight
)
from core.md_to_doc.converter import ConversionEngine, get_conversion_engine, quick_convert
from core.md_to_doc.knowledge_base import (
    KnowledgeBaseManager, get_knowledge_base_manager,
    create_local_source, create_git_source
)
from core.md_to_doc.models import SourceType, SourceConfig


class ConversionThread(QThread):
    """转换线程"""
    progress_updated = pyqtSignal(float, str)
    conversion_completed = pyqtSignal(bool, str)

    def __init__(self, engine: ConversionEngine, task: Task):
        super().__init__()
        self.engine = engine
        self.task = task

    def run(self):
        try:
            def progress_callback(progress):
                self.progress_updated.emit(progress.overall_progress, progress.current_step_name)

            self.engine.add_progress_callback(progress_callback)
            result = self.engine.convert(self.task)

            if result.success:
                self.conversion_completed.emit(True, result.output_file or "转换成功")
            else:
                self.conversion_completed.emit(False, result.error.message if result.error else "转换失败")

        except Exception as e:
            self.conversion_completed.emit(False, str(e))


class MarkdownToDocPanel(QWidget):
    """Markdown转Word文档面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = get_conversion_engine()
        self.kb_manager = get_knowledge_base_manager()
        self.current_task: Optional[Task] = None
        self.conversion_thread: Optional[ConversionThread] = None
        self.file_list: List[str] = []

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 创建标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_conversion_tab(), "📄 转换")
        self.tabs.addTab(self._create_knowledge_tab(), "📚 知识库")
        self.tabs.addTab(self._create_template_tab(), "🎨 模板")
        self.tabs.addTab(self._create_history_tab(), "📋 历史")
        self.tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        layout.addWidget(self.status_bar)

    def _create_conversion_tab(self) -> QWidget:
        """创建转换标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QToolBar()
        self.btn_select_file = QPushButton("📂 选择文件")
        self.btn_select_folder = QPushButton("📁 选择文件夹")
        self.btn_clear = QPushButton("🗑️ 清空")
        self.btn_start = QPushButton("🚀 开始转换")
        self.btn_start.setEnabled(False)

        toolbar.addWidget(self.btn_select_file)
        toolbar.addWidget(self.btn_select_folder)
        toolbar.addWidget(self.btn_clear)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_start)

        self.btn_select_file.clicked.connect(self._on_select_files)
        self.btn_select_folder.clicked.connect(self._on_select_folder)
        self.btn_clear.clicked.connect(self._on_clear)
        self.btn_start.clicked.connect(self._on_start_conversion)

        layout.addWidget(toolbar)

        # 左侧：文件列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        left_layout.addWidget(QLabel("待转换文件列表:"))

        self.file_list_widget = QListWidget()
        self.file_list_widget.setAlternatingRowColors(True)
        left_layout.addWidget(self.file_list_widget)

        # 右侧：配置
        right_widget = self._create_config_widget()

        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        # 进度条
        progress_group = QGroupBox("转换进度")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("等待开始...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)

        self.step_list_widget = QListWidget()
        self.step_list_widget.setMaximumHeight(100)
        progress_layout.addWidget(self.step_list_widget)

        layout.addWidget(progress_group)

        return widget

    def _create_config_widget(self) -> QWidget:
        """创建配置面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 目标格式
        format_group = QGroupBox("输出格式")
        format_layout = QFormLayout(format_group)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["Word文档 (.docx)", "PDF文档 (.pdf)",
                                     "HTML网页 (.html)", "纯文本 (.txt)"])
        self.format_combo.setCurrentIndex(0)
        format_layout.addRow("目标格式:", self.format_combo)

        # 输出目录
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("默认与源文件同目录")
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self._on_browse_output)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.output_path_edit)
        path_layout.addWidget(btn_browse)
        format_layout.addRow("输出目录:", path_layout)

        layout.addWidget(format_group)

        # 样式模板
        style_group = QGroupBox("样式模板")
        style_layout = QFormLayout(style_group)

        self.template_combo = QComboBox()
        for template in get_builtin_templates():
            self.template_combo.addItem(template.template_name, template.template_id)
        self.template_combo.setCurrentIndex(0)
        style_layout.addRow("模板:", self.template_combo)

        layout.addWidget(style_group)

        # 转换选项
        options_group = QGroupBox("转换选项")
        options_layout = QVBoxLayout(options_group)

        self.checkbox_toc = QCheckBox("生成目录")
        self.checkbox_toc.setChecked(True)
        options_layout.addWidget(self.checkbox_toc)

        self.checkbox_code = QCheckBox("保留代码高亮")
        self.checkbox_code.setChecked(True)
        options_layout.addWidget(self.checkbox_code)

        self.checkbox_table = QCheckBox("保留表格格式")
        self.checkbox_table.setChecked(True)
        options_layout.addWidget(self.checkbox_table)

        self.checkbox_image = QCheckBox("嵌入图片")
        self.checkbox_image.setChecked(True)
        options_layout.addWidget(self.checkbox_image)

        layout.addWidget(options_group)

        layout.addStretch()

        return widget

    def _create_knowledge_tab(self) -> QWidget:
        """创建知识库标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QToolBar()
        btn_add_local = QPushButton("📂 添加本地文件夹")
        btn_add_git = QPushButton("🔗 添加Git仓库")
        btn_refresh = QPushButton("🔄 刷新")
        btn_export = QPushButton("📤 导出")

        toolbar.addWidget(btn_add_local)
        toolbar.addWidget(btn_add_git)
        toolbar.addStretch()
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_export)

        btn_add_local.clicked.connect(self._on_add_local_folder)
        btn_refresh.clicked.connect(self._on_refresh_knowledge)
        btn_export.clicked.connect(self._on_export_from_knowledge)

        layout.addWidget(toolbar)

        # 知识源列表
        self.knowledge_list = QTableWidget()
        self.knowledge_list.setColumnCount(4)
        self.knowledge_list.setHorizontalHeaderLabels(["名称", "类型", "文档数", "状态"])
        self.knowledge_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.knowledge_list.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.knowledge_list)

        # 文档列表
        doc_group = QGroupBox("文档列表")
        doc_layout = QVBoxLayout(doc_group)

        self.doc_list = QListWidget()
        self.doc_list.setAlternatingRowColors(True)
        doc_layout.addWidget(self.doc_list)

        layout.addWidget(doc_group)

        return widget

    def _create_template_tab(self) -> QWidget:
        """创建模板标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QToolBar()
        btn_preview = QPushButton("👁️ 预览")
        btn_import = QPushButton("📥 导入")
        btn_export = QPushButton("📤 导出")

        toolbar.addWidget(btn_preview)
        toolbar.addWidget(btn_import)
        toolbar.addWidget(btn_export)

        btn_preview.clicked.connect(self._on_preview_template)
        btn_import.clicked.connect(self._on_import_template)
        btn_export.clicked.connect(self._on_export_template)

        layout.addWidget(toolbar)

        # 模板列表
        self.template_list = QListWidget()
        self.template_list.setAlternatingRowColors(True)

        for template in get_builtin_templates():
            item = QListWidgetItem(f"📄 {template.template_name}")
            item.setData(Qt.ItemDataRole.UserRole, template.template_id)
            item.setToolTip(template.template_description)
            self.template_list.addItem(item)

        layout.addWidget(self.template_list)

        # 模板预览
        preview_group = QGroupBox("模板预览")
        preview_layout = QVBoxLayout(preview_group)

        self.template_preview = QTextEdit()
        self.template_preview.setReadOnly(True)
        self.template_preview.setMaximumHeight(200)
        preview_layout.addWidget(self.template_preview)

        layout.addWidget(preview_group)

        return widget

    def _create_history_tab(self) -> QWidget:
        """创建历史标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QToolBar()
        btn_clear = QPushButton("🗑️ 清空历史")
        btn_open = QPushButton("📂 打开文件")
        btn_retry = QPushButton("🔄 重新转换")

        toolbar.addWidget(btn_clear)
        toolbar.addWidget(btn_open)
        toolbar.addWidget(btn_retry)
        toolbar.addStretch()

        btn_clear.clicked.connect(self._on_clear_history)
        btn_open.clicked.connect(self._on_open_file)
        btn_retry.clicked.connect(self._on_retry_conversion)

        layout.addWidget(toolbar)

        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["时间", "文件名", "状态", "大小", "耗时"])
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.history_table)

        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 页面设置
        page_group = QGroupBox("页面设置")
        page_layout = QFormLayout(page_group)

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["A4", "A3", "Letter", "Legal"])
        page_layout.addRow("纸张大小:", self.page_size_combo)

        self.orientation_combo = QComboBox()
        self.orientation_combo.addItems(["纵向", "横向"])
        page_layout.addRow("方向:", self.orientation_combo)

        self.margin_top = QDoubleSpinBox()
        self.margin_top.setRange(0.5, 10)
        self.margin_top.setValue(2.54)
        self.margin_top.setSuffix(" cm")
        page_layout.addRow("上边距:", self.margin_top)

        self.margin_bottom = QDoubleSpinBox()
        self.margin_bottom.setRange(0.5, 10)
        self.margin_bottom.setValue(2.54)
        self.margin_bottom.setSuffix(" cm")
        page_layout.addRow("下边距:", self.margin_bottom)

        layout.addWidget(page_group)

        # 图片设置
        image_group = QGroupBox("图片设置")
        image_layout = QFormLayout(image_group)

        self.image_mode_combo = QComboBox()
        self.image_mode_combo.addItems(["嵌入文档", "链接引用", "下载到本地"])
        image_layout.addRow("处理模式:", self.image_mode_combo)

        self.max_width = QSpinBox()
        self.max_width.setRange(100, 2000)
        self.max_width.setValue(600)
        self.max_width.setSuffix(" px")
        image_layout.addRow("最大宽度:", self.max_width)

        layout.addWidget(image_group)

        # 代码设置
        code_group = QGroupBox("代码设置")
        code_layout = QFormLayout(code_group)

        self.highlight_combo = QComboBox()
        self.highlight_combo.addItems(["无高亮", "纯文本", "彩色高亮"])
        code_layout.addRow("高亮模式:", self.highlight_combo)

        self.line_numbers = QCheckBox("显示行号")
        self.line_numbers.setChecked(True)
        code_layout.addRow("", self.line_numbers)

        layout.addWidget(code_group)

        layout.addStretch()

        return widget

    # =========================================================================
    # 事件处理
    # =========================================================================

    def _on_select_files(self):
        """选择文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择Markdown文件",
            "",
            "Markdown文件 (*.md *.markdown);;所有文件 (*.*)"
        )

        if files:
            self.file_list.extend(files)
            self._update_file_list()
            self.btn_start.setEnabled(len(self.file_list) > 0)

    def _on_select_folder(self):
        """选择文件夹"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择包含Markdown文件的文件夹",
            ""
        )

        if folder:
            # 扫描文件夹中的Markdown文件
            for root, _, files in os.walk(folder):
                for file in files:
                    if file.endswith('.md') or file.endswith('.markdown'):
                        self.file_list.append(os.path.join(root, file))

            self._update_file_list()
            self.btn_start.setEnabled(len(self.file_list) > 0)

    def _on_clear(self):
        """清空列表"""
        self.file_list.clear()
        self._update_file_list()
        self.btn_start.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("等待开始...")
        self.step_list_widget.clear()

    def _on_update_file_list(self):
        """更新文件列表"""
        self.file_list_widget.clear()
        for file in self.file_list:
            self.file_list_widget.addItem(os.path.basename(file))

    def _on_browse_output(self):
        """浏览输出目录"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            ""
        )

        if folder:
            self.output_path_edit.setText(folder)

    def _on_start_conversion(self):
        """开始转换"""
        if not self.file_list:
            QMessageBox.warning(self, "提示", "请先选择要转换的文件")
            return

        # 获取配置
        config = self._get_current_config()

        # 创建任务
        output_path = self.output_path_edit.text() or None
        self.current_task = self.engine.create_task(
            source_files=self.file_list.copy(),
            target_format=TargetFormat.DOCX,
            output_path=output_path,
            config=config,
        )

        # 清除旧进度
        self.step_list_widget.clear()
        for step in self.current_task.progress.steps:
            self.step_list_widget.addItem(f"⏳ {step.step_name}")

        # 开始转换线程
        self.conversion_thread = ConversionThread(self.engine, self.current_task)
        self.conversion_thread.progress_updated.connect(self._on_progress_updated)
        self.conversion_thread.conversion_completed.connect(self._on_conversion_completed)
        self.conversion_thread.start()

        self.btn_start.setEnabled(False)
        self.status_bar.showMessage("转换中...")

    def _on_progress_updated(self, progress: float, step_name: str):
        """进度更新"""
        self.progress_bar.setValue(int(progress * 100))
        self.progress_label.setText(f"正在执行: {step_name} ({int(progress * 100)}%)")

        # 更新步骤列表
        if self.current_task:
            for i, step in enumerate(self.current_task.progress.steps):
                if step.step_name == step_name:
                    icon = "✅" if step.status.value == "completed" else "🔄"
                    self.step_list_widget.item(i).setText(f"{icon} {step.step_name}")

    def _on_conversion_completed(self, success: bool, message: str):
        """转换完成"""
        self.progress_bar.setValue(100 if success else 0)
        self.progress_label.setText(message)

        if success:
            self.status_bar.showMessage("转换完成")
            QMessageBox.information(self, "转换成功", f"文件已生成: {message}")
        else:
            self.status_bar.showMessage("转换失败")
            QMessageBox.warning(self, "转换失败", message)

        self.btn_start.setEnabled(True)

    def _on_add_local_folder(self):
        """添加本地文件夹"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择文件夹",
            ""
        )

        if folder:
            source = create_local_source(folder)
            if self.kb_manager.register_source(source):
                self._refresh_knowledge_list()
                self.status_bar.showMessage(f"已添加知识源: {source.source_name}")
            else:
                QMessageBox.warning(self, "添加失败", "无法连接到此知识源")

    def _on_refresh_knowledge(self):
        """刷新知识库"""
        self._refresh_knowledge_list()
        self.status_bar.showMessage("已刷新知识库")

    def _on_export_from_knowledge(self):
        """从知识库导出"""
        if not self.file_list:
            QMessageBox.warning(self, "提示", "请先从知识库选择文档")
            return

        self._on_start_conversion()

    def _on_preview_template(self):
        """预览模板"""
        current_item = self.template_list.currentItem()
        if current_item:
            template_id = current_item.data(Qt.ItemDataRole.UserRole)
            self.template_preview.setPlainText(
                f"模板ID: {template_id}\n\n"
                "模板配置预览:\n"
                "- 标题样式: 黑体\n"
                "- 正文字体: 宋体\n"
                "- 代码字体: Consolas\n"
                "- 行间距: 1.5倍\n"
            )

    def _on_import_template(self):
        """导入模板"""
        QMessageBox.information(self, "导入模板", "请选择模板文件(.json)")

    def _on_export_template(self):
        """导出模板"""
        QMessageBox.information(self, "导出模板", "请选择导出位置")

    def _on_clear_history(self):
        """清空历史"""
        self.history_table.setRowCount(0)
        self.status_bar.showMessage("历史记录已清空")

    def _on_open_file(self):
        """打开文件"""
        row = self.history_table.currentRow()
        if row >= 0:
            file_path = self.history_table.item(row, 1).text()
            if os.path.exists(file_path):
                os.startfile(file_path)

    def _on_retry_conversion(self):
        """重新转换"""
        row = self.history_table.currentRow()
        if row >= 0:
            file_path = self.history_table.item(row, 1).text()
            if os.path.exists(file_path):
                self.file_list = [file_path]
                self._update_file_list()
                self.btn_start.setEnabled(True)
                self.tabs.setCurrentIndex(0)

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _update_file_list(self):
        """更新文件列表"""
        self.file_list_widget.clear()
        for file in self.file_list:
            item = os.path.basename(file)
            self.file_list_widget.addItem(item)

    def _refresh_knowledge_list(self):
        """刷新知识源列表"""
        self.knowledge_list.setRowCount(0)
        for source in self.kb_manager.list_sources():
            row = self.knowledge_list.rowCount()
            self.knowledge_list.insertRow(row)
            self.knowledge_list.setItem(row, 0, QTableWidgetItem(source.source_name))
            self.knowledge_list.setItem(row, 1, QTableWidgetItem(source.source_type.value))
            self.knowledge_list.setItem(row, 2, QTableWidgetItem(str(source.config.folder_path)))
            self.knowledge_list.setItem(row, 3, QTableWidgetItem("已连接" if source.is_connected else "未连接"))

    def _get_current_config(self) -> ConversionConfig:
        """获取当前配置"""
        config = ConversionConfig()

        # 格式
        format_map = {
            0: TargetFormat.DOCX,
            1: TargetFormat.PDF,
            2: TargetFormat.HTML,
            3: TargetFormat.TXT,
        }
        config.target_format = format_map.get(self.format_combo.currentIndex(), TargetFormat.DOCX)

        # 目录
        config.toc.generate_toc = self.checkbox_toc.isChecked()

        # 页面
        config.page.page_size = self.page_size_combo.currentText()
        config.page.orientation = "landscape" if self.orientation_combo.currentIndex() == 1 else "portrait"
        config.page.margin_top = self.margin_top.value()
        config.page.margin_bottom = self.margin_bottom.value()

        # 图片
        image_mode_map = {
            0: ImageMode.EMBED,
            1: ImageMode.LINK,
            2: ImageMode.DOWNLOAD,
        }
        config.image.mode = image_mode_map.get(self.image_mode_combo.currentIndex(), ImageMode.EMBED)
        config.image.max_width = self.max_width.value()

        # 代码
        highlight_map = {
            0: CodeHighlight.NONE,
            1: CodeHighlight.PLAIN,
            2: CodeHighlight.COLORED,
        }
        config.code.highlight = highlight_map.get(self.highlight_combo.currentIndex(), CodeHighlight.COLORED)
        config.code.line_numbers = self.line_numbers.isChecked()

        return config


# ============================================================================
# 便捷函数
# ============================================================================

def show_md_to_doc_panel(parent=None) -> MarkdownToDocPanel:
    """显示转换面板"""
    panel = MarkdownToDocPanel(parent)
    panel.show()
    return panel
