"""
Bilingual Document Panel - 双语对照文档面板
==========================================

PyQt6 实现的双语文档处理界面。
"""

from typing import Optional, List
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
        QTextEdit, QFileDialog, QComboBox, QProgressBar, QListWidget,
        QListWidgetItem, QGroupBox, QFormLayout, QCheckBox, QSpinBox,
        QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
        QMessageBox, QApplication, QStyle
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
    from PyQt6.QtGui import QFont, QIcon, QAction
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    # Mock classes for when PyQt6 is not available
    class QWidget: pass
    class Qt: pass
    class pyqtSignal: pass


from ..core.bilingual_doc import (
    DocumentParser, BilingualDetector, BilingualDecision,
    BilingualNeed, DocumentManager, BilingualDocument,
    RenderFormat, RenderLayout
)


class TranslationWorker(QThread):
    """翻译工作线程"""
    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(BilingualDocument)  # type: ignore
    error = pyqtSignal(str)  # type: ignore

    def __init__(self, manager: DocumentManager, file_path: str,
                 source_lang: str, target_lang: str,
                 force_bilingual: bool = False):
        super().__init__()
        self.manager = manager
        self.file_path = file_path
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.force_bilingual = force_bilingual

    def run(self):
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            doc = loop.run_until_complete(
                self.manager.process_document(
                    self.file_path,
                    source_lang=self.source_lang,
                    target_lang=self.target_lang,
                    force_bilingual=self.force_bilingual,
                    progress=lambda current, total, msg: self.progress.emit(current, total, msg)
                )
            )
            loop.close()
            self.finished.emit(doc)
        except Exception as e:
            self.error.emit(str(e))


class BilingualDocPanel(QWidget if PYQT6_AVAILABLE else object):
    """双语对照文档面板"""

    # Tab titles
    TAB_TRANSLATE = "📄 文档翻译"
    TAB_HISTORY = "📋 历史记录"
    TAB_SETTINGS = "⚙️ 设置"

    def __init__(self, parent=None):
        if not PYQT6_AVAILABLE:
            raise ImportError("PyQt6 is required for this panel")

        super().__init__(parent)
        self.manager = DocumentManager()
        self.current_document: Optional[BilingualDocument] = None
        self.worker: Optional[TranslationWorker] = None

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 创建标签页
        tabs = QTabWidget()
        tabs.addTab(self._create_translate_tab(), self.TAB_TRANSLATE)
        tabs.addTab(self._create_history_tab(), self.TAB_HISTORY)
        tabs.addTab(self._create_settings_tab(), self.TAB_SETTINGS)

        layout.addWidget(tabs)

    def _create_translate_tab(self) -> QWidget:
        """创建翻译标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 文件选择区
        file_group = QGroupBox("📁 选择文档")
        file_layout = QHBoxLayout()

        self.file_path_label = QLabel("未选择文件")
        self.file_path_label.setStyleSheet("color: #666; padding: 5px;")

        self.select_file_btn = QPushButton("选择文件")
        self.select_file_btn.clicked.connect(self._select_file)

        file_layout.addWidget(QLabel("文件:"))
        file_layout.addWidget(self.file_path_label, 1)
        file_layout.addWidget(self.select_file_btn)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # 翻译设置区
        settings_group = QGroupBox("🔧 翻译设置")
        settings_layout = QFormLayout()

        # 语言设置
        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItems([
            "自动检测 (Auto)", "英文 (EN)", "中文 (ZH)",
            "日文 (JA)", "韩文 (KO)", "法文 (FR)",
            "德文 (DE)", "西班牙文 (ES)"
        ])
        self.source_lang_combo.setCurrentText("自动检测 (Auto)")

        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems([
            "中文 (ZH)", "英文 (EN)", "日文 (JA)",
            "韩文 (KO)", "法文 (FR)", "德文 (DE)"
        ])

        settings_layout.addRow("源语言:", self.source_lang_combo)
        settings_layout.addRow("目标语言:", self.target_lang_combo)

        # 布局设置
        self.layout_combo = QComboBox()
        self.layout_combo.addItems([
            "左右对照 (Side by Side)",
            "上下对照 (Top Bottom)",
            "交替段落 (Interleaved)",
            "仅译文 (Translation Only)"
        ])

        settings_layout.addRow("布局:", self.layout_combo)

        # 强制双语
        self.force_bilingual_cb = QCheckBox("强制双语对照")
        settings_layout.addRow("", self.force_bilingual_cb)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # 智能检测结果显示
        self.detection_group = QGroupBox("🔍 智能检测结果")
        detection_layout = QVBoxLayout()

        self.detection_label = QLabel("等待分析...")
        self.detection_label.setWordWrap(True)

        detection_layout.addWidget(self.detection_label)
        self.detection_group.setLayout(detection_layout)
        layout.addWidget(self.detection_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_label = QLabel()
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_label)

        # 按钮区
        btn_layout = QHBoxLayout()

        self.analyze_btn = QPushButton("🔍 分析文档")
        self.analyze_btn.clicked.connect(self._analyze_document)
        self.analyze_btn.setEnabled(False)

        self.translate_btn = QPushButton("🚀 开始翻译")
        self.translate_btn.clicked.connect(self._start_translation)
        self.translate_btn.setEnabled(False)

        self.export_btn = QPushButton("💾 导出")
        self.export_btn.clicked.connect(self._export_document)
        self.export_btn.setEnabled(False)

        btn_layout.addWidget(self.analyze_btn)
        btn_layout.addWidget(self.translate_btn)
        btn_layout.addWidget(self.export_btn)

        layout.addLayout(btn_layout)

        # 预览区
        preview_group = QGroupBox("📝 预览")
        preview_layout = QVBoxLayout()

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("翻译结果将显示在这里...")

        preview_layout.addWidget(self.preview_text)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, 1)  # stretch

        return widget

    def _create_history_tab(self) -> QWidget:
        """创建历史记录标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self._refresh_history)

        self.clear_history_btn = QPushButton("🗑️ 清空")
        self.clear_history_btn.clicked.connect(self._clear_history)

        toolbar_layout.addWidget(self.refresh_btn)
        toolbar_layout.addWidget(self.clear_history_btn)
        toolbar_layout.addStretch()

        layout.addLayout(toolbar_layout)

        # 历史列表
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self._open_history_item)
        layout.addWidget(self.history_list)

        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 翻译引擎设置
        engine_group = QGroupBox("🔧 翻译引擎")
        engine_layout = QFormLayout()

        self.engine_combo = QComboBox()
        self.engine_combo.addItems([
            "Ollama (本地推荐)",
            "OpenAI GPT",
            "Google Translate",
            "模拟翻译 (测试用)"
        ])
        engine_layout.addRow("引擎:", self.engine_combo)

        self.model_name = QComboBox()
        self.model_name.addItems([
            "llama3.2", "qwen2.5", "deepseek-v2",
            "gpt-3.5-turbo", "gpt-4"
        ])
        engine_layout.addRow("模型:", self.model_name)

        self.api_url = QTextEdit()
        self.api_url.setMaximumHeight(60)
        self.api_url.setPlaceholderText("http://localhost:11434")
        engine_layout.addRow("API URL:", self.api_url)

        self.api_key = QTextEdit()
        self.api_key.setMaximumHeight(60)
        self.api_key.setPlaceholderText("API Key (可选)")
        engine_layout.addRow("API Key:", self.api_key)

        engine_group.setLayout(engine_layout)
        layout.addWidget(engine_group)

        # 输出设置
        output_group = QGroupBox("📤 输出设置")
        output_layout = QFormLayout()

        self.output_dir = QTextEdit()
        self.output_dir.setMaximumHeight(60)
        self.output_dir.setPlaceholderText("./bilingual_docs")
        output_layout.addRow("输出目录:", self.output_dir)

        self.default_format = QComboBox()
        self.default_format.addItems(["Markdown", "HTML", "JSON"])
        output_layout.addRow("默认格式:", self.default_format)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        layout.addStretch()

        return widget

    def _select_file(self):
        """选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文档",
            "",
            "支持格式 (*.pdf *.docx *.md *.txt);;PDF (*.pdf);;Word (*.docx);;Markdown (*.md);;文本 (*.txt);;所有文件 (*.*)"
        )

        if file_path:
            self.file_path_label.setText(file_path)
            self.file_path_label.setStyleSheet("color: #333; padding: 5px;")
            self.analyze_btn.setEnabled(True)
            self.current_file = file_path

    def _analyze_document(self):
        """分析文档"""
        if not hasattr(self, 'current_file'):
            return

        try:
            parser = DocumentParser()
            doc = parser.parse(self.current_file)

            detector = BilingualDetector()
            decision = detector.analyze(doc.raw_text, self.current_file)

            self._update_detection_display(decision)
            self.current_decision = decision
            self.translate_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.warning(self, "分析失败", f"无法分析文档:\n{str(e)}")

    def _update_detection_display(self, decision: BilingualDecision):
        """更新检测结果显示"""
        need_emoji = {
            BilingualNeed.REQUIRED: "🔴 必须",
            BilingualNeed.RECOMMENDED: "🟡 建议",
            BilingualNeed.OPTIONAL: "🟢 可选",
            BilingualNeed.NOT_NEEDED: "⚪ 不需要"
        }

        emoji = need_emoji.get(decision.need_level, "⚪")
        need_text = decision.need_level.value.replace("_", " ").title()

        reasons_html = "<br>".join(f"• {r}" for r in decision.reasons)

        html = f"""
        <div style='margin: 10px;'>
            <h3 style='color: #2196F3;'>{emoji} 双语需求: {need_text}</h3>
            <p><b>置信度:</b> {decision.confidence:.0%}</p>
            <p><b>源语言:</b> {decision.source_lang.value.upper()}</p>
            <p><b>目标语言:</b> {decision.target_lang.value.upper()}</p>
            <p><b>判断理由:</b></p>
            <ul>{reasons_html}</ul>
        """

        if decision.content_profile:
            cp = decision.content_profile
            html += f"""
            <p><b>内容分析:</b></p>
            <ul>
                <li>类型: {cp.content_type.value.replace('_', ' ').title()}</li>
                <li>技术难度: {'⭐' * int(cp.technical_level * 5)} ({cp.technical_level:.0%})</li>
                <li>术语密度: {'🔤' * int(cp.terminology_density * 5)} ({cp.terminology_density:.0%})</li>
                <li>目标读者: {cp.estimated_reader_level}</li>
            </ul>
            """

        if decision.alternative_suggestions:
            html += "<p><b>建议:</b></p><ul>"
            for s in decision.alternative_suggestions:
                html += f"<li>{s}</li>"
            html += "</ul>"

        html += "</div>"

        self.detection_label.setText(html)

    def _start_translation(self):
        """开始翻译"""
        if not hasattr(self, 'current_file'):
            return

        # 获取设置
        source_text = self.source_lang_combo.currentText()
        if "自动" in source_text:
            source_lang = "auto"
        else:
            source_lang = source_text.split("(")[-1].replace(")", "").lower().strip()

        target_text = self.target_lang_combo.currentText()
        target_lang = target_text.split("(")[-1].replace(")", "").lower().strip()

        # 开始翻译
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.translate_btn.setEnabled(False)
        self.analyze_btn.setEnabled(False)

        self.worker = TranslationWorker(
            self.manager,
            self.current_file,
            source_lang,
            target_lang,
            self.force_bilingual_cb.isChecked()
        )

        self.worker.progress.connect(self._on_translation_progress)
        self.worker.finished.connect(self._on_translation_finished)
        self.worker.error.connect(self._on_translation_error)

        self.worker.start()

    def _on_translation_progress(self, current: int, total: int, message: str):
        """翻译进度更新"""
        if total > 0:
            value = int(current / total * 100)
            self.progress_bar.setValue(value)
        self.progress_label.setText(message)

    def _on_translation_finished(self, doc: BilingualDocument):
        """翻译完成"""
        self.current_document = doc
        self.progress_bar.setVisible(False)
        self.progress_label.setText("翻译完成!")
        self.translate_btn.setEnabled(True)
        self.analyze_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        # 更新预览
        self._update_preview(doc)

        QMessageBox.information(self, "翻译完成", "文档翻译已完成!\n点击「导出」保存结果。")

    def _on_translation_error(self, error: str):
        """翻译错误"""
        self.progress_bar.setVisible(False)
        self.translate_btn.setEnabled(True)
        self.analyze_btn.setEnabled(True)
        self.progress_label.setText("翻译失败")

        QMessageBox.critical(self, "翻译失败", f"翻译过程中出错:\n{error}")

    def _update_preview(self, doc: BilingualDocument):
        """更新预览"""
        if not doc.bilingual_segments:
            return

        # 根据布局设置选择预览格式
        layout_text = self.layout_combo.currentText()

        if "左右" in layout_text:
            preview = self._generate_side_by_side_preview(doc)
        elif "上下" in layout_text:
            preview = self._generate_top_bottom_preview(doc)
        elif "交替" in layout_text:
            preview = self._generate_interleaved_preview(doc)
        else:
            preview = self._generate_translation_only_preview(doc)

        self.preview_text.setPlainText(preview)

    def _generate_side_by_side_preview(self, doc: BilingualDocument) -> str:
        """生成左右对照预览"""
        lines = ["=" * 60]
        lines.append("双语对照预览 (Side by Side)")
        lines.append("=" * 60)
        lines.append("")

        for i, seg in enumerate(doc.bilingual_segments[:20]):  # 只显示前20段
            lines.append(f"【段落 {i + 1}】")
            lines.append(f"原文: {seg.original[:100]}..." if len(seg.original) > 100 else f"原文: {seg.original}")
            lines.append(f"译文: {seg.translation[:100]}..." if len(seg.translation) > 100 else f"译文: {seg.translation}")
            lines.append("-" * 40)

        if len(doc.bilingual_segments) > 20:
            lines.append(f"\n... 共 {len(doc.bilingual_segments)} 段，以上显示前20段")

        return "\n".join(lines)

    def _generate_top_bottom_preview(self, doc: BilingualDocument) -> str:
        """生成上下对照预览"""
        lines = ["=" * 60]
        lines.append("双语对照预览 (Top Bottom)")
        lines.append("=" * 60)
        lines.append("\n【原文】\n")

        for i, seg in enumerate(doc.bilingual_segments[:10]):
            lines.append(seg.original)

        lines.append("\n【译文】\n")
        for i, seg in enumerate(doc.bilingual_segments[:10]):
            lines.append(seg.translation)

        return "\n".join(lines)

    def _generate_interleaved_preview(self, doc: BilingualDocument) -> str:
        """生成交替段落预览"""
        lines = ["=" * 60]
        lines.append("双语对照预览 (Interleaved)")
        lines.append("=" * 60)

        for i, seg in enumerate(doc.bilingual_segments[:15]):
            lines.append(f"\n【段落 {i + 1}】")
            lines.append(f"原文: {seg.original[:80]}..." if len(seg.original) > 80 else f"原文: {seg.original}")
            lines.append(f"译文: {seg.translation[:80]}..." if len(seg.translation) > 80 else f"译文: {seg.translation}")

        return "\n".join(lines)

    def _generate_translation_only_preview(self, doc: BilingualDocument) -> str:
        """生成仅译文预览"""
        lines = ["=" * 60]
        lines.append("译文预览 (Translation Only)")
        lines.append("=" * 60)

        for i, seg in enumerate(doc.bilingual_segments[:20]):
            lines.append(f"\n【段落 {i + 1}】")
            lines.append(seg.translation[:150] + "..." if len(seg.translation) > 150 else seg.translation)

        return "\n".join(lines)

    def _export_document(self):
        """导出文档"""
        if not self.current_document:
            return

        # 获取选择的格式和布局
        format_text = self.default_format.currentText().lower()
        format_map = {
            "markdown": RenderFormat.MARKDOWN,
            "html": RenderFormat.HTML,
            "json": RenderFormat.JSON
        }
        output_format = format_map.get(format_text, RenderFormat.MARKDOWN)

        layout_text = self.layout_combo.currentText()
        if "左右" in layout_text:
            layout = RenderLayout.SIDE_BY_SIDE
        elif "上下" in layout_text:
            layout = RenderLayout.TOP_BOTTOM
        elif "交替" in layout_text:
            layout = RenderLayout.INTERLEAVED
        else:
            layout = RenderLayout.TRANSLATION_ONLY

        # 选择保存位置
        default_name = Path(self.current_document.source_file).stem + "_bilingual"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存双语文档",
            default_name,
            f"{format_text.upper()} (.{output_format.value});;所有文件 (*.*)"
        )

        if file_path:
            try:
                output_path = self.manager.export_document(
                    self.current_document,
                    output_format=output_format,
                    layout=layout,
                    output_path=file_path
                )

                QMessageBox.information(
                    self, "导出成功",
                    f"文档已保存至:\n{output_path}"
                )

                # 添加到历史
                self._add_to_history(self.current_document)

            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出文档时出错:\n{str(e)}")

    def _add_to_history(self, doc: BilingualDocument):
        """添加到历史记录"""
        item = QListWidgetItem()
        file_name = Path(doc.source_file).name
        text = f"{file_name} - {doc.source_lang.upper()} → {doc.target_lang.upper()} ({len(doc.bilingual_segments)}段)"
        item.setText(text)
        item.setData(Qt.ItemDataRole.UserRole, doc.document_id)
        self.history_list.insertItem(0, item)

    def _refresh_history(self):
        """刷新历史记录"""
        self.history_list.clear()
        for doc in self.manager.list_documents():
            self._add_to_history(doc)

    def _clear_history(self):
        """清空历史记录"""
        reply = QMessageBox.question(
            self, "确认清空",
            "确定要清空所有历史记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.history_list.clear()

    def _open_history_item(self, item: QListWidgetItem):
        """打开历史记录项"""
        doc_id = item.data(Qt.ItemDataRole.UserRole)
        doc = self.manager.get_document(doc_id)

        if doc:
            self.current_document = doc
            self._update_preview(doc)
            self.export_btn.setEnabled(True)
            QMessageBox.information(self, "历史记录", f"已加载: {Path(doc.source_file).name}")
        else:
            QMessageBox.warning(self, "历史记录", "无法找到该文档")
