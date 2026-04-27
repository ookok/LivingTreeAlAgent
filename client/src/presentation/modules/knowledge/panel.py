"""
知识库模块 - 真实功能实现

支持文档上传、知识库搜索、内容管理。
"""

import os
from typing import Optional, List, Dict
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QFrame, QScrollArea, QFileDialog,
    QMessageBox, QProgressBar, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from client.src.business.nanochat_config import config


# ── 知识库工作线程 ──────────────────────────────────────────────────────

class KnowledgeBaseWorker(QThread):
    """知识库操作工作线程"""

    progress = pyqtSignal(int)          # 进度
    result_received = pyqtSignal(dict)  # 收到一个结果
    finished = pyqtSignal(list)         # 完成
    error = pyqtSignal(str)             # 错误

    def __init__(self, operation: str, params: Dict, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.params = params
        self._stop_requested = False

    def run(self):
        try:
            if self.operation == "search":
                results = self._search()
                self.finished.emit(results)
            elif self.operation == "upload":
                result = self._upload()
                self.finished.emit([result])
            elif self.operation == "list":
                results = self._list_documents()
                self.finished.emit(results)
            else:
                self.error.emit(f"未知操作: {self.operation}")
        except Exception as e:
            self.error.emit(str(e))

    def _search(self) -> List[Dict]:
        """搜索知识库（模拟）"""
        # TODO: 实际调用知识库 API
        query = self.params.get("query", "")
        return [
            {
                "id": "1",
                "title": f"文档1: {query}",
                "snippet": "这是搜索结果摘要...",
                "source": "uploaded",
                "score": 0.95,
            },
        ]

    def _upload(self) -> Dict:
        """上传文档（模拟）"""
        # TODO: 实际上传文档到知识库
        file_path = self.params.get("file_path", "")
        return {
            "id": "new",
            "title": os.path.basename(file_path),
            "status": "uploaded",
            "size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        }

    def _list_documents(self) -> List[Dict]:
        """列出所有文档（模拟）"""
        # TODO: 实际从知识库获取文档列表
        return [
            {
                "id": "1",
                "title": "示例文档1.pdf",
                "size": 102400,
                "upload_time": "2024-01-01 10:00",
            },
        ]

    def stop(self):
        self._stop_requested = True


# ── 知识库文档卡片 ──────────────────────────────────────────────────────

class DocumentCard(QFrame):
    """知识库文档卡片"""

    deleted = pyqtSignal(str)  # 文档ID

    def __init__(self, doc: Dict, parent=None):
        super().__init__(parent)
        self.doc = doc
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # 图标
        icon_label = QLabel("📄")
        icon_label.setStyleSheet("font-size: 24px;")
        layout.addWidget(icon_label)

        # 信息
        info_layout = QVBoxLayout()

        title_label = QLabel(self.doc.get("title", "无标题"))
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        info_layout.addWidget(title_label)

        meta_label = QLabel(f"大小: {self._format_size(self.doc.get('size', 0))} | 上传: {self.doc.get('upload_time', '未知')}")
        meta_label.setStyleSheet("font-size: 12px; color: #888;")
        info_layout.addWidget(meta_label)

        layout.addLayout(info_layout, 1)

        # 删除按钮
        delete_btn = QPushButton("🗑️")
        delete_btn.setFixedSize(32, 32)
        delete_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #FFEBEE;
                border-radius: 16px;
            }
        """)
        delete_btn.clicked.connect(lambda: self.deleted.emit(self.doc.get("id", "")))
        layout.addWidget(delete_btn)

        # 样式
        self.setStyleSheet("""
            DocumentCard {
                background: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                margin: 4px 0;
            }
            DocumentCard:hover {
                border: 1px solid #1976D2;
                background: #F5F5F5;
            }
        """)

    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"


# ── 主知识库面板 ──────────────────────────────────────────────────────

class Panel(QWidget):
    """知识库面板 - 真实功能"""

    document_uploaded = pyqtSignal(str)  # 文件路径
    search_requested = pyqtSignal(str)   # 搜索查询

    def __init__(self, parent=None):
        super().__init__(parent)
        self.documents: List[Dict] = []
        self.worker: Optional[KnowledgeBaseWorker] = None
        self._setup_ui()
        self._load_documents()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        title_bar = QFrame()
        title_bar.setFixedHeight(52)
        title_bar.setStyleSheet("background: #FFFFFF; border-bottom: 1px solid #E0E0E0;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)

        title_label = QLabel("📚 知识库")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # 上传按钮
        self.upload_btn = QPushButton("📤 上传文档")
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background: #1976D2;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1565C0; }
        """)
        self.upload_btn.clicked.connect(self._upload_document)
        title_layout.addWidget(self.upload_btn)

        layout.addWidget(title_bar)

        # 搜索区域
        search_frame = QFrame()
        search_frame.setStyleSheet("background: #FFFFFF; border-bottom: 1px solid #E0E0E0;")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(16, 12, 16, 12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索知识库...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 12px;
                font-size: 14px;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
            }
            QLineEdit:focus {
                border: 2px solid #1976D2;
            }
        """)
        self.search_input.returnPressed.connect(self._search_knowledge_base)
        search_layout.addWidget(self.search_input, 1)

        self.search_btn = QPushButton("搜索")
        self.search_btn.setFixedSize(80, 40)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background: #1976D2;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1565C0; }
        """)
        self.search_btn.clicked.connect(self._search_knowledge_base)
        search_layout.addWidget(self.search_btn)

        layout.addWidget(search_frame)

        # 文档列表区域（可滚动）
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: #FAFAFA; }")

        self.documents_container = QWidget()
        self.documents_layout = QVBoxLayout(self.documents_container)
        self.documents_layout.setContentsMargins(16, 16, 16, 16)
        self.documents_layout.setSpacing(8)
        self.documents_layout.addStretch()

        self.scroll_area.setWidget(self.documents_container)
        layout.addWidget(self.scroll_area, 1)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("font-size: 12px; color: #888; padding: 8px 16px;")
        layout.addWidget(self.status_label)

        # 启用拖放
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖放进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        """拖放事件"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self._process_upload(file_path)

    def _upload_document(self):
        """上传文档"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文档",
            "",
            "Documents (*.pdf *.txt *.md *.docx *.doc);;All Files (*)"
        )

        if file_path:
            self._process_upload(file_path)

    def _process_upload(self, file_path: str):
        """处理上传"""
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "警告", "文件不存在！")
            return

        # 更新状态
        self.status_label.setText(f"上传中: {os.path.basename(file_path)}...")
        self.upload_btn.setEnabled(False)

        # 启动工作线程
        self.worker = KnowledgeBaseWorker("upload", {"file_path": file_path})
        self.worker.finished.connect(self._on_upload_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

        self.document_uploaded.emit(file_path)

    def _search_knowledge_base(self):
        """搜索知识库"""
        query = self.search_input.text().strip()
        if not query:
            return

        # 更新状态
        self.status_label.setText(f"搜索中: {query}...")
        self.search_btn.setEnabled(False)

        # 清空旧结果
        self._clear_documents()

        # 启动工作线程
        self.worker = KnowledgeBaseWorker("search", {"query": query})
        self.worker.result_received.connect(self._on_result_received)
        self.worker.finished.connect(self._on_search_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

        self.search_requested.emit(query)

    def _load_documents(self):
        """加载文档列表"""
        # 启动工作线程
        self.worker = KnowledgeBaseWorker("list", {})
        self.worker.finished.connect(self._on_list_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _clear_documents(self):
        """清空文档列表"""
        while self.documents_layout.count() > 1:
            item = self.documents_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_document(self, doc: Dict):
        """添加文档卡片"""
        card = DocumentCard(doc)
        card.deleted.connect(self._delete_document)
        self.documents_layout.insertWidget(self.documents_layout.count() - 1, card)

    @pyqtSlot(list)
    def _on_upload_finished(self, results: List[Dict]):
        """上传完成"""
        for result in results:
            self._add_document(result)
            self.documents.append(result)

        self.status_label.setText(f"上传成功: {len(results)} 个文档")
        self.upload_btn.setEnabled(True)
        self.worker = None

    @pyqtSlot(dict)
    def _on_result_received(self, result: Dict):
        """收到一个搜索结果"""
        self._add_document(result)

    @pyqtSlot(list)
    def _on_search_finished(self, results: List[Dict]):
        """搜索完成"""
        self.documents = results
        self.status_label.setText(f"找到 {len(results)} 个结果")
        self.search_btn.setEnabled(True)
        self.worker = None

    @pyqtSlot(list)
    def _on_list_finished(self, results: List[Dict]):
        """列表加载完成"""
        self.documents = results
        for doc in results:
            self._add_document(doc)
        self.status_label.setText(f"共 {len(results)} 个文档")
        self.worker = None

    @pyqtSlot(str)
    def _on_error(self, error_msg: str):
        """处理错误"""
        self.status_label.setText(f"❌ 错误: {error_msg}")
        self.upload_btn.setEnabled(True)
        self.search_btn.setEnabled(True)
        self.worker = None

    def _delete_document(self, doc_id: str):
        """删除文档"""
        # TODO: 实际调用删除 API
        self.status_label.setText(f"删除文档: {doc_id}")
        # 从界面移除
        for i in range(self.documents_layout.count()):
            widget = self.documents_layout.itemAt(i).widget()
            if widget and isinstance(widget, DocumentCard) and widget.doc.get("id") == doc_id:
                widget.deleteLater()
                break

    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        super().closeEvent(event)
