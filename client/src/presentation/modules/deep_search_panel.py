"""
深度搜索模块面板
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QTextEdit, QScrollArea, QFrame,
    QListWidget, QListWidgetItem, QProgressBar,
    QCheckBox, QComboBox, QToolButton,
    QSizePolicy,
)
from PyQt6.QtGui import QFont


class DeepSearchPanel(QWidget):
    """深度搜索面板"""
    
    search_requested = pyqtSignal(str, dict)  # query, options
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_history = []
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            DeepSearchPanel {
                background: #0D0D0D;
            }
            QLabel {
                color: #FFFFFF;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton {
                background: #252525;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                padding: 8px 16px;
                font-family: "Microsoft YaHei", sans-serif;
            }
            QPushButton:hover {
                background: #333333;
            }
            QPushButton[active="true"] {
                background: #00D4AA;
                color: #0D0D0D;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 标题
        header = QLabel("🔍 深度搜索")
        header.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #00D4AA;
        """)
        layout.addWidget(header)
        
        # 搜索框
        search_layout = QHBoxLayout()
        search_layout.setSpacing(12)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索关键词...")
        self.search_input.setMinimumHeight(48)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #1A1A1A;
                border: 1px solid #333333;
                border-radius: 12px;
                padding: 0 20px;
                color: #FFFFFF;
                font-size: 15px;
            }
            QLineEdit:focus {
                border-color: #00D4AA;
            }
        """)
        self.search_input.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.search_input, 1)
        
        self.search_btn = QPushButton("🔍")
        self.search_btn.setFixedSize(48, 48)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background: #00D4AA;
                border: none;
                border-radius: 12px;
                font-size: 20px;
            }
            QPushButton:hover {
                background: #00E8BB;
            }
        """)
        self.search_btn.clicked.connect(self._on_search)
        search_layout.addWidget(self.search_btn)
        
        layout.addLayout(search_layout)
        
        # 数据源选择
        source_layout = QHBoxLayout()
        source_layout.setSpacing(8)
        
        self.source_btns = {}
        sources = [
            ("全部", "all", True),
            ("维基百科", "wiki", False),
            ("学术论文", "academic", False),
            ("行业报告", "report", False),
            ("全网", "web", False),
        ]
        
        for name, key, checked in sources:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(checked)
            btn.setProperty("active", "true" if checked else "false")
            btn.clicked.connect(lambda c, k=key: self._on_source_click(k))
            self.source_btns[key] = btn
            source_layout.addWidget(btn)
        
        source_layout.addStretch()
        layout.addLayout(source_layout)
        
        # 结果区域
        results_area = QHBoxLayout()
        results_area.setSpacing(16)
        
        # 搜索结果列表
        self.results_list = QListWidget()
        self.results_list.setStyleSheet("""
            QListWidget {
                background: #1A1A1A;
                border: none;
                border-radius: 12px;
                padding: 8px;
            }
            QListWidget::item {
                background: transparent;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 8px;
            }
            QListWidget::item:selected {
                background: #252525;
            }
            QListWidget::item:hover {
                background: #1F1F1F;
            }
        """)
        results_area.addWidget(self.results_list, 2)
        
        # 详情面板
        self.detail_panel = QFrame()
        self.detail_panel.setStyleSheet("""
            QFrame {
                background: #1A1A1A;
                border-radius: 12px;
            }
        """)
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(16, 16, 16, 16)
        
        self.detail_title = QLabel("选择搜索结果查看详情")
        self.detail_title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #FFFFFF;
        """)
        detail_layout.addWidget(self.detail_title)
        
        self.detail_content = QScrollArea()
        self.detail_content.setWidgetResizable(True)
        self.detail_content.setStyleSheet("border: none;")
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                color: #A0A0A0;
                font-size: 14px;
            }
        """)
        self.detail_content.setWidget(self.detail_text)
        detail_layout.addWidget(self.detail_content, 1)
        
        # 操作按钮
        action_layout = QHBoxLayout()
        open_btn = QPushButton("🌐 在浏览器打开")
        open_btn.clicked.connect(self._on_open_browser)
        copy_btn = QPushButton("📋 复制链接")
        copy_btn.clicked.connect(self._on_copy_link)
        action_layout.addWidget(open_btn)
        action_layout.addWidget(copy_btn)
        detail_layout.addLayout(action_layout)
        
        results_area.addWidget(self.detail_panel, 3)
        layout.addLayout(results_area, 1)
    
    def _on_search(self):
        query = self.search_input.text().strip()
        if query:
            self.search_requested.emit(query, {"source": self._current_source})
            self._show_loading()
    
    def _on_source_click(self, source: str):
        self._current_source = source
        for key, btn in self.source_btns.items():
            btn.setProperty("active", "true" if key == source else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
    
    def _show_loading(self):
        self.results_list.clear()
        item = QListWidgetItem("🔍 搜索中...")
        self.results_list.addItem(item)
    
    def show_results(self, results: list):
        """显示搜索结果"""
        self.results_list.clear()
        for r in results:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, r)
            self.results_list.addItem(item)
        self.results_list.itemClicked.connect(self._on_result_click)
    
    def _on_result_click(self, item: QListWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.detail_title.setText(data.get("title", ""))
            self.detail_text.setText(data.get("content", ""))
    
    def _on_open_browser(self):
        pass  # TODO: 实现
    
    def _on_copy_link(self):
        pass  # TODO: 实现
    
    def _current_source(self) -> str:
        for key, btn in self.source_btns.items():
            if btn.isChecked():
                return key
        return "all"


__all__ = ["DeepSearchPanel"]
