"""
文档 QA 界面

提供独立的文档问答界面
"""

from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QLabel,
    QFileDialog, QMessageBox, QSplitter, QProgressBar,
    QGroupBox, QFrame
)
from PyQt6.QtGui import QFont


class DocumentQaWorker(QThread):
    """文档 QA 工作线程"""
    
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, multi_doc_qa, question):
        super().__init__()
        self.multi_doc_qa = multi_doc_qa
        self.question = question
    
    def run(self):
        try:
            self.progress.emit("正在检索相关文档...")
            result = self.multi_doc_qa.query(self.question)
            
            if result:
                self.finished.emit({
                    "answer": result.answer,
                    "sources": result.sources,
                    "confidence": result.confidence,
                    "processing_time": result.processing_time,
                    "documents": [
                        {
                            "id": d.id,
                            "name": d.name,
                            "type": d.type
                        }
                        for d in result.documents
                    ]
                })
            else:
                self.error.emit("问答执行失败")
        except Exception as e:
            self.error.emit(str(e))


class DocumentQaPanel(QWidget):
    """文档 QA 面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.multi_doc_qa = None
        self.worker = None
        self._setup_ui()
        self._init_qa_system()
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # 左侧：文档列表
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        # 右侧：问答区域
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割比例
        splitter.setSizes([250, 550])
    
    def _create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        
        # 标题
        title = QLabel("📚 文档集合")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 文档列表
        self.document_list = QListWidget()
        self.document_list.setAlternatingRowColors(True)
        layout.addWidget(self.document_list)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        add_button = QPushButton("添加文档")
        add_button.clicked.connect(self._add_document)
        button_layout.addWidget(add_button)
        
        remove_button = QPushButton("移除")
        remove_button.clicked.connect(self._remove_document)
        button_layout.addWidget(remove_button)
        
        layout.addLayout(button_layout)
        
        # 统计信息
        self.stats_label = QLabel("文档数量: 0\n总块数: 0")
        self.stats_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.stats_label)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """创建右侧面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        
        # 问答标题
        title = QLabel("💬 文档问答")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 问题输入区域
        question_group = QGroupBox("问题")
        question_layout = QVBoxLayout()
        
        self.question_input = QTextEdit()
        self.question_input.setPlaceholderText("输入您的问题...")
        self.question_input.setMaximumHeight(80)
        question_layout.addWidget(self.question_input)
        
        self.ask_button = QPushButton("提问")
        self.ask_button.clicked.connect(self._ask_question)
        self.ask_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        question_layout.addWidget(self.ask_button)
        
        question_group.setLayout(question_layout)
        layout.addWidget(question_group)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 回答区域
        answer_group = QGroupBox("回答")
        answer_layout = QVBoxLayout()
        
        self.answer_text = QTextEdit()
        self.answer_text.setReadOnly(True)
        self.answer_text.setPlaceholderText("回答将在此处显示...")
        answer_layout.addWidget(self.answer_text)
        
        answer_group.setLayout(answer_layout)
        layout.addWidget(answer_group)
        
        # 来源区域
        sources_group = QGroupBox("参考来源")
        sources_layout = QVBoxLayout()
        
        self.sources_text = QTextEdit()
        self.sources_text.setReadOnly(True)
        self.sources_text.setMaximumHeight(120)
        self.sources_text.setPlaceholderText("参考来源将在此处显示...")
        sources_layout.addWidget(self.sources_text)
        
        sources_group.setLayout(sources_layout)
        layout.addWidget(sources_group)
        
        return panel
    
    def _init_qa_system(self):
        """初始化 QA 系统"""
        try:
            from core.living_tree_ai.knowledge.multi_document_qa import MultiDocumentQA
            from core.living_tree_ai.config.config_manager import get_config_manager
            
            config = get_config_manager()
            
            self.multi_doc_qa = MultiDocumentQA(
                embedding_model=config.document_qa.embedding_model,
                llm_model=config.document_qa.llm_model,
                temperature=config.document_qa.temperature,
                top_k=config.document_qa.top_k,
                chunk_size=config.document_qa.chunk_size,
                chunk_overlap=config.document_qa.chunk_overlap
            )
            
            self._update_stats()
            
        except Exception as e:
            QMessageBox.warning(self, "警告", f"初始化 QA 系统失败: {e}")
    
    def _add_document(self):
        """添加文档"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择文档",
            "",
            "支持的文档 (*.pdf *.docx *.xlsx *.txt);;PDF 文件 (*.pdf);;Word 文档 (*.docx);;Excel 文件 (*.xlsx);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if file_paths:
            self._load_documents(file_paths)
    
    def _load_documents(self, file_paths: list):
        """加载文档"""
        if not self.multi_doc_qa:
            self._init_qa_system()
        
        success_count = 0
        for path in file_paths:
            if self.multi_doc_qa.load_document(path):
                success_count += 1
        
        if success_count > 0:
            self._update_document_list()
            self._update_stats()
            QMessageBox.information(self, "成功", f"成功加载 {success_count} 个文档")
        else:
            QMessageBox.warning(self, "警告", "无法加载文档")
    
    def _remove_document(self):
        """移除文档"""
        current_item = self.document_list.currentItem()
        if not current_item:
            return
        
        doc_name = current_item.text()
        
        # 找到并移除文档
        for doc in self.multi_doc_qa.documents:
            if doc.name == doc_name:
                self.multi_doc_qa.remove_document(doc.id)
                break
        
        self._update_document_list()
        self._update_stats()
    
    def _update_document_list(self):
        """更新文档列表"""
        self.document_list.clear()
        
        if self.multi_doc_qa:
            for doc in self.multi_doc_qa.documents:
                item = QListWidgetItem(f"{doc.name} ({doc.type})")
                self.document_list.addItem(item)
    
    def _update_stats(self):
        """更新统计信息"""
        if self.multi_doc_qa:
            stats = self.multi_doc_qa.get_stats()
            self.stats_label.setText(
                f"文档数量: {stats['document_count']}\n总块数: {stats['total_chunks']}"
            )
    
    def _ask_question(self):
        """提问"""
        if not self.multi_doc_qa:
            QMessageBox.warning(self, "警告", "请先加载文档")
            return
        
        question = self.question_input.toPlainText().strip()
        if not question:
            QMessageBox.warning(self, "警告", "请输入问题")
            return
        
        # 检查是否有文档
        if not self.multi_doc_qa.documents:
            QMessageBox.warning(self, "警告", "请先添加文档")
            return
        
        # 禁用按钮
        self.ask_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 不确定进度
        
        # 启动工作线程
        self.worker = DocumentQaWorker(self.multi_doc_qa, question)
        self.worker.finished.connect(self._on_query_finished)
        self.worker.progress.connect(self._on_progress)
        self.worker.error.connect(self._on_error)
        self.worker.start()
    
    def _on_query_finished(self, result: dict):
        """查询完成"""
        self.ask_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        # 显示回答
        self.answer_text.setPlainText(result["answer"])
        
        # 显示来源
        sources_text = ""
        for i, source in enumerate(result["sources"], 1):
            sources_text += f"\n【来源 {i}】\n"
            sources_text += f"{source['content'][:300]}...\n"
            sources_text += f"(来自: {source['metadata'].get('source', '未知')})\n"
        
        self.sources_text.setPlainText(sources_text.strip())
        
        # 显示统计
        docs = result.get("documents", [])
        stats_text = f"涉及文档: {len(docs)} 个"
        stats_text += f"\n置信度: {result['confidence']:.2f}"
        stats_text += f"\n处理时间: {result['processing_time']:.2f} 秒"
        
        QMessageBox.information(self, "查询完成", stats_text)
    
    def _on_progress(self, message: str):
        """进度更新"""
        self.progress_bar.setFormat(message)
    
    def _on_error(self, error: str):
        """错误处理"""
        self.ask_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "错误", f"查询失败: {error}")


class DocumentQaDialog(QWidget):
    """文档 QA 对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("文档问答")
        self.resize(900, 600)
        
        layout = QVBoxLayout(self)
        self.qa_panel = DocumentQaPanel()
        layout.addWidget(self.qa_panel)
        
        self.setLayout(layout)
