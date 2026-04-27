"""
全学科智能写作助手 - PyQt 主面板

功能：
1. 多模态文件拖拽区
2. 意图识别状态显示
3. 学科自适应工作空间
4. 公式编辑器
5. 大纲编辑器
6. 文献管理面板
7. 实时预览
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QTextEdit, QLineEdit,
    QTabWidget, QFrame, QProgressBar,
    QComboBox, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QScrollArea, QSplitter, QCheckBox, QSpinBox,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox,
    QStatusBar, QToolBar, QMenuBar, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QAction, QIcon, QDragEnterEvent, QDropEvent

import re
from pathlib import Path
from datetime import datetime

# 导入写作模块
from writing.intent_detector import (
    IntentDetector, IntentResult, DocType, SubjectDomain, WritingFormat,
    AnalysisContext, get_intent_detector
)
from writing.latex_processor import LatexProcessor, ParsedFormula, get_latex_processor
from writing.outline_generator import OutlineGenerator, OutlineSection, OutlineStyle, get_outline_generator
from writing.citation_manager import CitationManager, Citation, CitationStyle, get_citation_manager
from writing.ai_writer import AIWriter, WritingContext, WritingResult, get_ai_writer


class DropZone(QFrame):
    """拖拽区域"""
    fileDropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        self.label = QLabel("📄 拖拽文件到此处\n支持 Word、PDF、Markdown、图片")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 10px;
                padding: 40px;
                color: #666;
                font-size: 14px;
            }
        """)

        layout.addWidget(self.label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.label.setStyleSheet("""
                QLabel {
                    border: 2px dashed #4CAF50;
                    border-radius: 10px;
                    padding: 40px;
                    color: #4CAF50;
                    font-size: 14px;
                }
            """)

    def dragLeaveEvent(self, event):
        self.label.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 10px;
                padding: 40px;
                color: #666;
                font-size: 14px;
            }
        """)

    def dropEvent(self: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self.fileDropped.emit(file_path)


class IntentCard(QFrame):
    """意图识别结果卡片"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
            }
        """)

        layout = QGridLayout(self)

        # 类型
        layout.addWidget(QLabel("📋 文档类型:"), 0, 0)
        self.doc_type_label = QLabel("未知")
        self.doc_type_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        layout.addWidget(self.doc_type_label, 0, 1)

        # 学科
        layout.addWidget(QLabel("🎯 学科领域:"), 1, 0)
        self.subject_label = QLabel("通用")
        self.subject_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        layout.addWidget(self.subject_label, 1, 1)

        # 格式
        layout.addWidget(QLabel("📝 推荐格式:"), 2, 0)
        self.format_label = QLabel("Markdown")
        self.format_label.setStyleSheet("font-weight: bold; color: #FF9800;")
        layout.addWidget(self.format_label, 2, 1)

        # 置信度
        layout.addWidget(QLabel("📊 置信度:"), 3, 0)
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setTextVisible(True)
        layout.addWidget(self.confidence_bar, 3, 1)

        # 语言
        layout.addWidget(QLabel("🌐 语言:"), 4, 0)
        self.lang_label = QLabel("中文")
        layout.addWidget(self.lang_label, 4, 1)

        # 技能包
        layout.addWidget(QLabel("🛠️ 建议技能:"), 5, 0)
        self.skills_label = QLabel("")
        layout.addWidget(self.skills_label, 5, 1, 1, 2)

    def update(self, result: IntentResult):
        """更新显示"""
        doc_type_map = {
            DocType.ACADEMIC_PAPER: "📄 学术论文",
            DocType.BUSINESS_REPORT: "📊 商业报告",
            DocType.BUSINESS_PLAN: "📈 商业计划书",
            DocType.NOVEL: "📖 小说/创意写作",
            DocType.TECHNICAL_DOC: "💻 技术文档",
            DocType.BLOG: "📝 博客文章",
            DocType.EMAIL: "📧 邮件",
            DocType.LEGAL: "⚖️ 法律文书",
            DocType.GENERAL: "📋 通用",
        }

        self.doc_type_label.setText(doc_type_map.get(result.doc_type, "未知"))
        self.subject_label.setText(result.subject.value)
        self.format_label.setText(result.suggested_format.value)
        self.confidence_bar.setValue(int(result.confidence * 100))
        self.lang_label.setText("🇨🇳 中文" if result.language == "zh" else "🇺🇸 英文")
        self.skills_label.setText(", ".join(result.suggested_skills) if result.suggested_skills else "无")

        # 颜色编码置信度
        if result.confidence >= 0.8:
            self.confidence_bar.setStyleSheet("QProgressBar::chunk { background: #4CAF50; }")
        elif result.confidence >= 0.5:
            self.confidence_bar.setStyleSheet("QProgressBar::chunk { background: #FF9800; }")
        else:
            self.confidence_bar.setStyleSheet("QProgressBar::chunk { background: #F44336; }")


class FormulaEditor(QFrame):
    """公式编辑器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.latex_processor = get_latex_processor()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 输入区域
        input_group = QGroupBox("LaTeX 公式输入")
        input_layout = QVBoxLayout()

        self.latex_input = QTextEdit()
        self.latex_input.setPlaceholderText("输入 LaTeX 公式，如：E = mc^2\n或输入自然语言描述，如：能量等于质量乘以光速的平方")
        self.latex_input.setMaximumHeight(100)
        input_layout.addWidget(self.latex_input)

        # 按钮行
        btn_layout = QHBoxLayout()
        self.parse_btn = QPushButton("🔍 解析")
        self.transform_btn = QPushButton("🔄 转换")
        self.render_btn = QPushButton("🖼️ 渲染")
        self.insert_btn = QPushButton("📋 插入文档")

        self.transform_combo = QComboBox()
        self.transform_combo.addItems(["偏导→全导", "全导→偏导", "添加绝对值", "添加上标", "添加下标"])

        btn_layout.addWidget(self.parse_btn)
        btn_layout.addWidget(self.transform_combo)
        btn_layout.addWidget(self.transform_btn)
        btn_layout.addWidget(self.render_btn)
        btn_layout.addWidget(self.insert_btn)
        btn_layout.addStretch()

        input_layout.addLayout(btn_layout)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 解析结果
        result_group = QGroupBox("解析结果")
        result_layout = QGridLayout()

        result_layout.addWidget(QLabel("标准化:"), 0, 0)
        self.standardized_label = QLabel("")
        result_layout.addWidget(self.standardized_label, 0, 1)

        result_layout.addWidget(QLabel("算子:"), 1, 0)
        self.operators_label = QLabel("")
        result_layout.addWidget(self.operators_label, 1, 1)

        result_layout.addWidget(QLabel("变量:"), 2, 0)
        self.variables_label = QLabel("")
        result_layout.addWidget(self.variables_label, 2, 1)

        result_layout.addWidget(QLabel("语义:"), 3, 0)
        self.semantic_label = QLabel("")
        result_layout.addWidget(self.semantic_label, 3, 1, 1, 2)

        result_group.setLayout(result_layout)
        layout.addWidget(result_group)

        # 预览
        preview_group = QGroupBox("预览")
        preview_layout = QVBoxLayout()
        self.preview_label = QLabel("")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 20px;
                font-size: 18px;
            }
        """)
        preview_layout.addWidget(self.preview_label)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # 信号
        self.parse_btn.clicked.connect(self._on_parse)
        self.transform_btn.clicked.connect(self._on_transform)
        self.render_btn.clicked.connect(self._on_render)

    def _on_parse(self):
        """解析公式"""
        latex = self.latex_input.toPlainText().strip()
        if not latex:
            return

        parsed = self.latex_processor.parse(latex)

        self.standardized_label.setText(parsed.latex)
        self.operators_label.setText(", ".join(parsed.operators) if parsed.operators else "无")
        self.variables_label.setText(", ".join(parsed.variables) if parsed.variables else "无")
        self.semantic_label.setText(parsed.semantic_description or "数学表达式")
        self.preview_label.setText(f"$${parsed.latex}$$")

    def _on_transform(self):
        """转换公式"""
        latex = self.latex_input.toPlainText().strip()
        if not latex:
            return

        instruction = self.transform_combo.currentText()
        new_latex = self.latex_processor.transform(latex, instruction)

        self.latex_input.setPlainText(new_latex)
        self._on_parse()

    def _on_render(self):
        """渲染公式"""
        latex = self.latex_input.toPlainText().strip()
        if not latex:
            return

        # 尝试渲染为图片
        try:
            img_data = self.latex_processor.render_to_image(latex)
            if img_data and len(img_data) > 100:
                # 可以显示图片
                pass
        except Exception as e:
            self.preview_label.setText(f"[渲染失败: {e}]")


class OutlineEditor(QFrame):
    """大纲编辑器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.outline_generator = get_outline_generator()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()

        self.topic_input = QLineEdit()
        self.topic_input.setPlaceholderText("输入主题...")
        toolbar.addWidget(self.topic_input)

        self.doc_type_combo = QComboBox()
        self.doc_type_combo.addItems([
            "学术论文", "商业计划书", "商业报告", "小说",
            "技术文档", "博客文章", "通用"
        ])
        toolbar.addWidget(QLabel("文档类型:"))
        toolbar.addWidget(self.doc_type_combo)

        self.generate_btn = QPushButton("🎯 生成大纲")
        toolbar.addWidget(self.generate_btn)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 大纲树
        self.outline_tree = QTreeWidget()
        self.outline_tree.setHeaderLabels(["章节", "描述", "预估字数"])
        self.outline_tree.setColumnWidth(0, 250)
        self.outline_tree.setAlternatingRowColors(True)
        layout.addWidget(self.outline_tree)

        # 按钮行
        btn_layout = QHBoxLayout()
        self.expand_btn = QPushButton("📂 展开全部")
        self.collapse_btn = QPushButton("📁 折叠全部")
        self.export_btn = QPushButton("💾 导出 Markdown")
        self.apply_btn = QPushButton("✨ 应用到写作")

        btn_layout.addWidget(self.expand_btn)
        btn_layout.addWidget(self.collapse_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

        # 信号
        self.generate_btn.clicked.connect(self._on_generate)
        self.expand_btn.clicked.connect(self.outline_tree.expandAll)
        self.collapse_btn.clicked.connect(self.outline_tree.collapseAll)
        self.export_btn.clicked.connect(self._on_export)
        self.apply_btn.clicked.connect(self._on_apply)

    def _on_generate(self):
        """生成大纲"""
        topic = self.topic_input.text().strip()
        if not topic:
            topic = "未命名主题"

        doc_type_map = {
            0: DocType.ACADEMIC_PAPER,
            1: DocType.BUSINESS_PLAN,
            2: DocType.BUSINESS_REPORT,
            3: DocType.NOVEL,
            4: DocType.TECHNICAL_DOC,
            5: DocType.BLOG,
            6: DocType.GENERAL,
        }

        doc_type = doc_type_map.get(self.doc_type_combo.currentIndex(), DocType.GENERAL)
        sections = self.outline_generator.generate(topic, doc_type)

        self._build_tree(sections)

    def _build_tree(self, sections: list[OutlineSection], parent=None):
        """构建大纲树"""
        self.outline_tree.clear()

        for section in sections:
            self._add_section_to_tree(section)

    def _add_section_to_tree(self, section: OutlineSection, parent_item=None):
        """添加章节到树"""
        item = QTreeWidgetItem()
        item.setText(0, section.title)
        item.setText(1, section.description[:50] if section.description else "")
        item.setText(2, f"{section.estimated_words}字" if section.estimated_words else "-")
        item.setData(0, Qt.ItemDataRole.UserRole, section)

        # 缩进
        item.setExpanded(section.is_expanded)

        if parent_item:
            parent_item.addChild(item)
        else:
            self.outline_tree.addTopLevelItem(item)

        for child in section.children:
            self._add_section_to_tree(child, item)

    def _on_export(self):
        """导出为 Markdown"""
        sections = self._get_current_sections()
        if not sections:
            return

        md = self.outline_generator.to_markdown(sections)

        path, _ = QFileDialog.getSaveFileName(
            self, "导出大纲", "", "Markdown (*.md);;所有文件 (*)"
        )
        if path:
            Path(path).write_text(md, encoding='utf-8')
            QMessageBox.information(self, "成功", f"已导出到: {path}")

    def _on_apply(self):
        """应用到写作"""
        sections = self._get_current_sections()
        if sections:
            # 发送信号
            self.outlineReady = pyqtSignal(list)
            self.outlineReady.emit(sections)

    def _get_current_sections(self) -> list[OutlineSection]:
        """获取当前大纲"""
        sections = []
        for i in range(self.outline_tree.topLevelItemCount()):
            item = self.outline_tree.topLevelItem(i)
            section = item.data(0, Qt.ItemDataRole.UserRole)
            if section:
                sections.append(section)
        return sections


class CitationPanel(QFrame):
    """文献管理面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.citation_manager = get_citation_manager()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 添加引用
        add_group = QGroupBox("添加引用")
        add_layout = QVBoxLayout()

        self.ref_input = QTextEdit()
        self.ref_input.setPlaceholderText('输入参考文献...\n格式：作者, "标题", 期刊, 年份, DOI')
        self.ref_input.setMaximumHeight(80)
        add_layout.addWidget(self.ref_input)

        btn_layout = QHBoxLayout()
        self.parse_btn = QPushButton("🔍 解析")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["IEEE", "APA", "Chicago", "GB/T 7714"])
        self.add_btn = QPushButton("➕ 添加")
        self.export_btn = QPushButton("📤 导出 BibTeX")

        btn_layout.addWidget(self.parse_btn)
        btn_layout.addWidget(QLabel("格式:"))
        btn_layout.addWidget(self.format_combo)
        btn_layout.addStretch()
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.export_btn)

        add_layout.addLayout(btn_layout)
        add_group.setLayout(add_layout)
        layout.addWidget(add_group)

        # 引用列表
        list_group = QGroupBox("引用列表")
        list_layout = QVBoxLayout()

        self.citation_list = QListWidget()
        list_layout.addWidget(self.citation_list)

        # 引用预览
        self.preview_edit = QTextEdit()
        self.preview_edit.setMaximumHeight(150)
        self.preview_edit.setPlaceholderText("选中引用查看预览...")
        list_layout.addWidget(self.preview_edit)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        # 信号
        self.parse_btn.clicked.connect(self._on_parse)
        self.add_btn.clicked.connect(self._on_add)
        self.export_btn.clicked.connect(self._on_export)
        self.citation_list.itemClicked.connect(self._on_item_clicked)

    def _on_parse(self):
        """解析引用"""
        ref_text = self.ref_input.toPlainText().strip()
        if not ref_text:
            return

        style_map = {
            0: CitationStyle.IEEE,
            1: CitationStyle.APA,
            2: CitationStyle.CHICAGO,
            3: CitationStyle.GB7714,
        }

        style = style_map.get(self.format_combo.currentIndex(), CitationStyle.IEEE)
        bibtex = self.citation_manager.parse_and_convert(ref_text, style)

        if bibtex:
            self.preview_edit.setPlainText(bibtex)
        else:
            self.preview_edit.setPlainText("[解析失败，请检查格式]")

    def _on_add(self):
        """添加引用"""
        bibtex = self.preview_edit.toPlainText()
        if not bibtex or bibtex.startswith("["):
            QMessageBox.warning(self, "错误", "请先解析有效的参考文献")
            return

        # 简单添加到列表
        item = QListWidgetItem(bibtex[:50] + "..." if len(bibtex) > 50 else bibtex)
        self.citation_list.addItem(item)

    def _on_export(self):
        """导出 BibTeX"""
        bibtex = self.citation_manager.generate_bibliography()

        path, _ = QFileDialog.getSaveFileName(
            self, "导出参考文献", "", "BibTeX (*.bib);;所有文件 (*)"
        )
        if path:
            Path(path).write_text(bibtex, encoding='utf-8')
            QMessageBox.information(self, "成功", f"已导出到: {path}")

    def _on_item_clicked(self, item):
        """列表项点击"""
        pass


class WritingWorkspace(QWidget):
    """
    全学科智能写作助手 - 主工作空间

    功能：
    - 多模态文件拖拽
    - 意图识别与自动切换
    - 公式编辑器
    - 大纲编辑器
    - 文献管理器
    - 实时预览
    """

    # 信号
    contentChanged = pyqtSignal(str)
    workspaceChanged = pyqtSignal(dict)

    def __init__(self, parent=None, agent=None):
        super().__init__(parent)
        self.agent = agent
        self.ai_writer = get_ai_writer(agent)
        self.intent_detector = get_intent_detector()

        self._setup_ui()
        self._setup_menu()

    def _setup_ui(self):
        """设置 UI"""
        main_layout = QVBoxLayout(self)

        # 顶部：意图识别卡片
        self.intent_card = IntentCard()
        main_layout.addWidget(self.intent_card)

        # 主区域：选项卡
        self.tabs = QTabWidget()

        # 选项卡1：拖拽 + 写作
        writing_tab = QWidget()
        writing_layout = QVBoxLayout(writing_tab)

        self.drop_zone = DropZone()
        self.drop_zone.fileDropped.connect(self._on_file_dropped)
        writing_layout.addWidget(self.drop_zone)

        # 写作区
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("在这里开始写作...\n拖入文件后，系统将自动识别意图并推荐格式和技能。")
        writing_layout.addWidget(self.editor)

        # 工具栏
        toolbar = QHBoxLayout()
        self.topic_btn = QPushButton("📋 生成大纲")
        self.citation_btn = QPushButton("📚 插入引用")
        self.formula_btn = QPushButton("🔢 插入公式")
        self.export_btn = QPushButton("💾 导出")

        toolbar.addWidget(self.topic_btn)
        toolbar.addWidget(self.citation_btn)
        toolbar.addWidget(self.formula_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.export_btn)

        writing_layout.addLayout(toolbar)

        self.tabs.addTab(writing_tab, "✏️ 写作")

        # 选项卡2：公式编辑器
        self.tabs.addTab(FormulaEditor(), "🔢 公式编辑器")

        # 选项卡3：大纲编辑器
        self.tabs.addTab(OutlineEditor(), "📋 大纲")

        # 选项卡4：文献管理
        self.tabs.addTab(CitationPanel(), "📚 参考文献")

        main_layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪 | 文档类型: 通用 | 格式: Markdown")
        main_layout.addWidget(self.status_bar)

    def _setup_menu(self):
        """设置菜单"""
        # 创建菜单栏（如果父窗口没有）

    def _on_file_dropped(self, file_path: str):
        """处理拖放的文件"""
        try:
            # 识别意图
            result = self.intent_detector.detect_from_file(file_path)

            # 更新卡片
            self.intent_card.update(result)

            # 更新上下文
            context = WritingContext(
                doc_type=result.doc_type,
                subject=result.subject,
                target_format=result.suggested_format,
                language=result.language,
            )
            self.ai_writer.set_context(context)

            # 更新状态栏
            self.status_bar.showMessage(
                f"已识别: {result.doc_type.value} | {result.subject.value} | "
                f"置信度: {result.confidence:.0%} | 格式: {result.suggested_format.value}"
            )

            # 显示检测到的公式
            if result.detected_equations:
                self.status_bar.showMessage(
                    self.status_bar.currentMessage() +
                    f" | 检测到 {len(result.detected_equations)} 个公式"
                )

            # 更新写作提示
            self.editor.setPlaceholderText(
                f"已识别为: {result.doc_type.value}\n"
                f"建议格式: {result.suggested_format.value}\n"
                f"建议技能: {', '.join(result.suggested_skills)}\n\n"
                "开始写作..."
            )

        except Exception as e:
            self.status_bar.showMessage(f"识别失败: {e}")

    def get_content(self) -> str:
        """获取内容"""
        return self.editor.toPlainText()

    def set_content(self, content: str):
        """设置内容"""
        self.editor.setPlainText(content)

    def export_document(self, path: str, format: str = "markdown"):
        """导出文档"""
        content = self.get_content()
        Path(path).write_text(content, encoding='utf-8')
        self.status_bar.showMessage(f"已导出: {path}")


# 便捷函数
def create_writing_panel(parent=None, agent=None) -> WritingWorkspace:
    """创建写作面板"""
    return WritingWorkspace(parent, agent)


# 验证导入
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    panel = WritingWorkspace()
    panel.resize(900, 700)
    panel.show()
    sys.exit(app.exec())
