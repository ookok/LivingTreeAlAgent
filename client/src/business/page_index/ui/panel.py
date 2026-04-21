"""
PageIndex 管理面板 - PyQt6 实现
"""

import asyncio
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..hermes_tool import PageIndexTool, get_pageindex_tool


class BuildIndexThread(QThread):
    """异步构建索引线程"""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str, int)

    def __init__(self, tool: PageIndexTool, file_path: str, doc_key: str):
        super().__init__()
        self.tool = tool
        self.file_path = file_path
        self.doc_key = doc_key

    def run(self):
        try:
            self.progress.emit("正在加载文档...", 10)
            result = self.tool.build_index(self.file_path, self.doc_key)
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit({"success": False, "error": str(e)})


class QueryThread(QThread):
    """异步查询线程"""
    finished = pyqtSignal(dict)

    def __init__(self, tool: PageIndexTool, question: str, doc_key: str):
        super().__init__()
        self.tool = tool
        self.question = question
        self.doc_key = doc_key

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self.tool.query_and_answer(self.question, self.doc_key)
            )
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit({"success": False, "error": str(e)})


class PageIndexPanel(QWidget):
    """
    PageIndex 管理面板

    功能:
    1. 索引管理 - 上传文档、构建索引
    2. 文档浏览 - 查看已索引的文档
    3. 智能查询 - 基于索引的精确查询
    4. 结果展示 - 显示答案和引用来源
    """

    def __init__(self):
        super().__init__()
        self.tool = get_pageindex_tool()
        self.current_doc_key = "default"
        self.build_thread = None
        self.query_thread = None

        self.init_ui()

    def init_ui(self):
        """初始化 UI"""
        main_layout = QVBoxLayout(self)

        # 标题栏
        title_bar = QHBoxLayout()
        title_label = QLabel("🧠 PageIndex 智能文档索引")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_bar.addWidget(title_label)
        title_bar.addStretch()

        # 统计信息
        self.stats_label = QLabel("📊 文档: 0 | Chunks: 0 | 查询: 0")
        self.stats_label.setStyleSheet("color: #666;")
        title_bar.addWidget(self.stats_label)

        main_layout.addLayout(title_bar)

        # Tab 页
        tabs = QTabWidget()
        tabs.addTab(self._create_index_tab(), "📤 索引管理")
        tabs.addTab(self._create_browse_tab(), "📚 文档浏览")
        tabs.addTab(self._create_query_tab(), "🔍 智能查询")
        tabs.addTab(self._create_result_tab(), "📋 查询结果")

        main_layout.addWidget(tabs)

        self.update_stats()

    def _create_index_tab(self) -> QWidget:
        """创建索引管理页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 文件选择
        file_group = QGroupBox("📁 文档上传")
        file_layout = QHBoxLayout()

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择 PDF/HTML/TXT 文件...")
        self.file_path_edit.setReadOnly(True)
        file_layout.addWidget(self.file_path_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_btn)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # 索引配置
        config_group = QGroupBox("⚙️ 索引配置")
        config_layout = QHBoxLayout()

        config_layout.addWidget(QLabel("文档名称:"))
        self.doc_key_edit = QLineEdit()
        self.doc_key_edit.setPlaceholderText("default")
        config_layout.addWidget(self.doc_key_edit)

        config_layout.addWidget(QLabel("Chunk大小:"))
        self.chunk_size_combo = QComboBox()
        self.chunk_size_combo.addItems(["300", "500", "800", "1000"])
        self.chunk_size_combo.setCurrentText("500")
        config_layout.addWidget(self.chunk_size_combo)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # 构建按钮
        btn_layout = QHBoxLayout()

        self.build_btn = QPushButton("🚀 构建索引")
        self.build_btn.setEnabled(False)
        self.build_btn.clicked.connect(self.build_index)
        btn_layout.addWidget(self.build_btn)

        self.build_progress = QProgressBar()
        self.build_progress.setVisible(False)
        btn_layout.addWidget(self.build_progress)

        layout.addLayout(btn_layout)

        # 构建日志
        log_group = QGroupBox("📝 构建日志")
        self.build_log = QTextEdit()
        self.build_log.setReadOnly(True)
        self.build_log.setMaximumHeight(150)
        log_group.setLayout(QVBoxLayout())
        log_group.layout().addWidget(self.build_log)

        layout.addWidget(log_group)
        layout.addStretch()

        return widget

    def _create_browse_tab(self) -> QWidget:
        """创建文档浏览页"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # 文档列表
        self.doc_list = QListWidget()
        self.doc_list.itemClicked.connect(self.on_doc_selected)
        layout.addWidget(self.doc_list, 1)

        # 文档详情
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)

        detail_layout.addWidget(QLabel("<b>文档详情</b>"))

        self.doc_detail = QTextEdit()
        self.doc_detail.setReadOnly(True)
        detail_layout.addWidget(self.doc_detail)

        # 删除按钮
        delete_btn = QPushButton("🗑️ 删除索引")
        delete_btn.clicked.connect(self.delete_selected_doc)
        detail_layout.addWidget(delete_btn)

        layout.addWidget(detail_widget, 2)

        # 加载已有文档
        self.refresh_doc_list()

        return widget

    def _create_query_tab(self) -> QWidget:
        """创建查询页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 文档选择
        query_doc_layout = QHBoxLayout()
        query_doc_layout.addWidget(QLabel("文档:"))
        self.query_doc_combo = QComboBox()
        self.query_doc_combo.addItem("default", "default")
        query_doc_layout.addWidget(self.query_doc_combo, 1)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.refresh_doc_list)
        query_doc_layout.addWidget(refresh_btn)

        layout.addLayout(query_doc_layout)

        # 查询输入
        query_group = QGroupBox("💬 智能问答")
        query_layout = QVBoxLayout()

        self.question_edit = QTextEdit()
        self.question_edit.setPlaceholderText(
            "输入问题，例如：\n"
            "- 这个文档的主要内容包括什么？\n"
            "- 如何安装和配置？\n"
            "- 第5章讲了哪些内容？"
        )
        self.question_edit.setMaximumHeight(100)
        query_layout.addWidget(self.question_edit)

        query_btn_layout = QHBoxLayout()

        self.query_btn = QPushButton("🔍 查询")
        self.query_btn.clicked.connect(self.execute_query)
        query_btn_layout.addWidget(self.query_btn)

        self.query_progress = QProgressBar()
        self.query_progress.setVisible(False)
        query_btn_layout.addWidget(self.query_progress)

        query_layout.addLayout(query_btn_layout)
        query_group.setLayout(query_layout)

        layout.addWidget(query_group)

        # 快捷问题
        quick_group = QGroupBox("⚡ 快捷问题")
        quick_layout = QHBoxLayout()

        quick_questions = [
            ("主要概述", "这篇文档的主要内容和结构是什么？"),
            ("核心要点", "文档的核心要点有哪些？"),
            ("使用方法", "如何使用这个系统？"),
            ("常见问题", "有哪些常见问题和解决方案？"),
        ]

        for label, question in quick_questions:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, q=question: self.set_question(q))
            quick_layout.addWidget(btn)

        quick_group.setLayout(quick_layout)
        layout.addWidget(quick_group)

        layout.addStretch()

        return widget

    def _create_result_tab(self) -> QWidget:
        """创建结果页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 答案展示
        answer_group = QGroupBox("🤖 生成答案")
        answer_layout = QVBoxLayout()

        self.answer_text = QTextEdit()
        self.answer_text.setReadOnly(True)
        answer_layout.addWidget(self.answer_text)

        answer_group.setLayout(answer_layout)
        layout.addWidget(answer_group, 1)

        # 引用来源
        citation_group = QGroupBox("📌 引用来源")
        citation_layout = QVBoxLayout()

        self.citation_list = QListWidget()
        citation_layout.addWidget(self.citation_list)

        citation_group.setLayout(citation_layout)
        layout.addWidget(citation_group)

        # 元信息
        self.meta_label = QLabel("⏱️ 查询时间: -")
        layout.addWidget(self.meta_label)

        return widget

    # ========== 事件处理 ==========

    def browse_file(self):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文档",
            "",
            "支持的文件 (*.pdf *.html *.htm *.txt *.md);;所有文件 (*.*)"
        )

        if file_path:
            self.file_path_edit.setText(file_path)
            self.doc_key_edit.setText(Path(file_path).stem)
            self.build_btn.setEnabled(True)

    def build_index(self):
        """构建索引"""
        file_path = self.file_path_edit.text()
        doc_key = self.doc_key_edit.text() or Path(file_path).stem

        if not file_path:
            return

        self.build_btn.setEnabled(False)
        self.build_progress.setVisible(True)
        self.build_progress.setRange(0, 0)  # 不确定进度

        self.build_log.append(f"🚀 开始构建索引: {doc_key}")
        self.build_log.append(f"📄 文件: {file_path}")

        self.build_thread = BuildIndexThread(self.tool, file_path, doc_key)
        self.build_thread.progress.connect(
            lambda msg, _: self.build_log.append(f"  {msg}")
        )
        self.build_thread.finished.connect(self.on_build_finished)
        self.build_thread.start()

    def on_build_finished(self, result: dict):
        """索引构建完成"""
        self.build_progress.setVisible(False)
        self.build_btn.setEnabled(True)

        if result.get("success"):
            self.build_log.append(f"✅ 构建成功！")
            self.build_log.append(f"   文档ID: {result.get('doc_id')}")
            self.build_log.append(f"   Chunk数: {result.get('total_chunks')}")
            self.build_log.append(f"   树高度: {result.get('tree_height')}")
            self.refresh_doc_list()
        else:
            self.build_log.append(f"❌ 构建失败: {result.get('error')}")

        self.update_stats()

    def refresh_doc_list(self):
        """刷新文档列表"""
        self.doc_list.clear()
        self.query_doc_combo.clear()

        docs = self.tool.list_documents()
        for doc in docs:
            item = QListWidgetItem()
            item.setText(f"📄 {doc['title']} ({doc['total_chunks']} chunks)")
            item.setData(Qt.ItemDataRole.UserRole, doc["doc_id"])
            self.doc_list.addItem(item)

            self.query_doc_combo.addItem(
                doc["title"],
                doc["doc_id"]
            )

        self.update_stats()

    def on_doc_selected(self, item: QListWidgetItem):
        """文档选中"""
        doc_id = item.data(Qt.ItemDataRole.UserRole)
        docs = self.tool.list_documents()

        for doc in docs:
            if doc["doc_id"] == doc_id:
                detail = f"""<b>📄 {doc['title']}</b>

<b>文件:</b> {doc['file_path']}
<b>类型:</b> {doc['doc_type']}
<b>页数:</b> {doc['total_pages']}
<b>Chunks:</b> {doc['total_chunks']}
<b>树高度:</b> {doc['tree_height']}
<b>创建时间:</b> {doc.get('created_at', 'N/A')}
"""
                self.doc_detail.setHtml(detail)
                break

    def delete_selected_doc(self):
        """删除选中的文档"""
        current_item = self.doc_list.currentItem()
        if not current_item:
            return

        doc_id = current_item.data(Qt.ItemDataRole.UserRole)
        self.tool.builder.delete_index(doc_id)
        self.refresh_doc_list()

    def set_question(self, question: str):
        """设置问题"""
        self.question_edit.setText(question)

    def execute_query(self):
        """执行查询"""
        question = self.question_edit.toPlainText().strip()
        if not question:
            return

        doc_key = self.query_doc_combo.currentData()
        if not doc_key:
            self.answer_text.setHtml(
                "<b>❌ 请先选择或构建索引文档</b>"
            )
            return

        self.query_btn.setEnabled(False)
        self.query_progress.setVisible(True)
        self.query_progress.setRange(0, 0)

        self.query_thread = QueryThread(self.tool, question, doc_key)
        self.query_thread.finished.connect(self.on_query_finished)
        self.query_thread.start()

    def on_query_finished(self, result: dict):
        """查询完成"""
        self.query_btn.setEnabled(True)
        self.query_progress.setVisible(False)

        if result.get("success"):
            # 显示答案
            self.answer_text.setHtml(
                f"<b>🤖 答案:</b><br><br>{result.get('answer', 'N/A')}"
            )

            # 显示引用
            self.citation_list.clear()
            for citation in result.get("citations", []):
                self.citation_list.addItem(f"📖 {citation}")

            # 元信息
            self.meta_label.setText(
                f"⏱️ 查询时间: {result.get('response_time_ms', 0):.2f}ms | "
                f"候选数: {len(result.get('candidates', []))}"
            )
        else:
            self.answer_text.setHtml(
                f"<b>❌ 查询失败:</b> {result.get('error', 'Unknown error')}"
            )

    def update_stats(self):
        """更新统计"""
        stats = self.tool.get_stats()
        self.stats_label.setText(
            f"📊 文档: {stats['total_documents']} | "
            f"Chunks: {stats['total_chunks']} | "
            f"查询: {stats['query_count']}"
        )
