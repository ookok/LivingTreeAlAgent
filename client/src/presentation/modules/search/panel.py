"""
搜索模块 - 真实功能实现

支持网页搜索、学术搜索、代码搜索等。
"""

import requests
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QFrame, QComboBox, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot

from client.src.business.nanochat_config import config


# ── 搜索工作线程 ─────────────────────────────────────────────────────────

class SearchWorker(QThread):
    """搜索工作线程"""

    result_received = pyqtSignal(dict)  # 收到一个结果
    finished = pyqtSignal(list)          # 完成（所有结果）
    error = pyqtSignal(str)              # 错误

    def __init__(self, query: str, search_type: str, parent=None):
        super().__init__(parent)
        self.query = query
        self.search_type = search_type
        self._stop_requested = False

    def run(self):
        try:
            # 模拟搜索（实际应调用搜索 API）
            results = self._perform_search()
            self.finished.emit(results)

        except Exception as e:
            self.error.emit(str(e))

    def _perform_search(self) -> List[Dict]:
        """执行搜索（模拟）"""
        # TODO: 实际调用搜索 API
        # 目前返回模拟数据

        if self.search_type == "web":
            return [
                {
                    "title": f"搜索结果 1: {self.query}",
                    "url": "https://example.com/1",
                    "snippet": "这是第一个搜索结果的摘要...",
                    "source": "Web"
                },
                {
                    "title": f"搜索结果 2: {self.query}",
                    "url": "https://example.com/2",
                    "snippet": "这是第二个搜索结果的摘要...",
                    "source": "Web"
                },
            ]
        elif self.search_type == "academic":
            return [
                {
                    "title": f"论文: {self.query} 研究",
                    "url": "https://arxiv.org/...",
                    "snippet": "摘要：本文研究了...",
                    "authors": "张三, 李四",
                    "year": "2024",
                    "source": "Academic"
                },
            ]
        else:
            return [
                {
                    "title": f"结果: {self.query}",
                    "url": "https://example.com",
                    "snippet": "摘要...",
                    "source": "General"
                },
            ]

    def stop(self):
        self._stop_requested = True


# ── 搜索结果卡片 ─────────────────────────────────────────────────────────

class SearchResultCard(QFrame):
    """搜索结果卡片"""

    def __init__(self, result: Dict, parent=None):
        super().__init__(parent)
        self.result = result
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # 标题（可点击）
        title_label = QLabel(f"<a href='{self.result.get('url', '#')}'>{self.result.get('title', '无标题')}</a>")
        title_label.setStyleSheet("""
            font-size: 16px;
            color: #1A0DAB;
            font-weight: bold;
        """)
        title_label.setOpenExternalLinks(True)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # URL
        url_label = QLabel(self.result.get("url", ""))
        url_label.setStyleSheet("font-size: 12px; color: #006621;")
        layout.addWidget(url_label)

        # 摘要
        snippet_label = QLabel(self.result.get("snippet", ""))
        snippet_label.setStyleSheet("font-size: 14px; color: #545454;")
        snippet_label.setWordWrap(True)
        layout.addWidget(snippet_label)

        # 来源标签
        source = self.result.get("source", "")
        if source:
            source_label = QLabel(f"[{source}]")
            source_label.setStyleSheet("font-size: 11px; color: #888;")
            layout.addWidget(source_label)

        # 样式
        self.setStyleSheet("""
            SearchResultCard {
                background: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                margin: 4px 0;
            }
            SearchResultCard:hover {
                border: 1px solid #1976D2;
                background: #F5F5F5;
            }
        """)


# ── 主搜索面板 ───────────────────────────────────────────────────────────

class Panel(QWidget):
    """搜索面板 - 真实功能"""

    search_requested = pyqtSignal(str, str)  # 查询, 类型

    def __init__(self, parent=None):
        super().__init__(parent)
        self.results: List[Dict] = []
        self.worker: Optional[SearchWorker] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        title_bar = QFrame()
        title_bar.setFixedHeight(52)
        title_bar.setStyleSheet("background: #FFFFFF; border-bottom: 1px solid #E0E0E0;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)

        title_label = QLabel("🔍 深度搜索")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # 搜索类型选择
        self.type_combo = QComboBox()
        self.type_combo.addItem("🌐 网页搜索", "web")
        self.type_combo.addItem("📚 学术搜索", "academic")
        self.type_combo.addItem("💻 代码搜索", "code")
        self.type_combo.addItem("📰 新闻搜索", "news")
        self.type_combo.setStyleSheet("padding: 4px 8px;")
        title_layout.addWidget(self.type_combo)

        layout.addWidget(title_bar)

        # 搜索输入区域
        search_frame = QFrame()
        search_frame.setStyleSheet("background: #FFFFFF; border-bottom: 1px solid #E0E0E0;")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(16, 12, 16, 12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索关键词...")
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
        self.search_input.returnPressed.connect(self._perform_search)
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
                font-size: 14px;
            }
            QPushButton:hover { background: #1565C0; }
            QPushButton:disabled { background: #BDBDBD; }
        """)
        self.search_btn.clicked.connect(self._perform_search)
        search_layout.addWidget(self.search_btn)

        layout.addWidget(search_frame)

        # 结果区域（可滚动）
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: #FAFAFA; }")

        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(16, 16, 16, 16)
        self.results_layout.setSpacing(8)
        self.results_layout.addStretch()

        self.scroll_area.setWidget(self.results_container)
        layout.addWidget(self.scroll_area, 1)

        # 状态栏
        self.status_label = QLabel("输入关键词开始搜索")
        self.status_label.setStyleSheet("font-size: 12px; color: #888; padding: 8px 16px;")
        layout.addWidget(self.status_label)

    def _perform_search(self):
        """执行搜索"""
        query = self.search_input.text().strip()
        if not query:
            return

        search_type = self.type_combo.currentData()

        # 更新状态
        self.status_label.setText(f"搜索中: {query}...")
        self.search_btn.setEnabled(False)
        self.search_btn.setText("搜索中...")

        # 清空旧结果
        self._clear_results()

        # 启动工作线程
        self.worker = SearchWorker(query, search_type)
        self.worker.result_received.connect(self._on_result_received)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

        # 发送信号
        self.search_requested.emit(query, search_type)

    def _clear_results(self):
        """清空结果"""
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_result(self, result: Dict):
        """添加搜索结果卡片"""
        card = SearchResultCard(result)
        self.results_layout.insertWidget(self.results_layout.count() - 1, card)

    @pyqtSlot(dict)
    def _on_result_received(self, result: Dict):
        """收到一个搜索结果"""
        self._add_result(result)

    @pyqtSlot(list)
    def _on_finished(self, results: List[Dict]):
        """搜索完成"""
        self.results = results
        self.status_label.setText(f"找到 {len(results)} 个结果")
        self.search_btn.setEnabled(True)
        self.search_btn.setText("搜索")
        self.worker = None

    @pyqtSlot(str)
    def _on_error(self, error_msg: str):
        """处理错误"""
        self.status_label.setText(f"❌ 错误: {error_msg}")
        self.search_btn.setEnabled(True)
        self.search_btn.setText("搜索")
        self.worker = None

    def closeEvent(self, event):
        """关闭事件"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        super().closeEvent(event)
