"""
知识库模块面板
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QTextEdit, QScrollArea, QFrame,
    QListWidget, QListWidgetItem,
    QComboBox, QTabWidget,
    QSplitter,
)
from PyQt6.QtGui import QFont


class KnowledgeBasePanel(QWidget):
    """知识库面板"""
    
    search_requested = pyqtSignal(str)  # query
    add_knowledge_requested = pyqtSignal()
    delete_knowledge_requested = pyqtSignal(str)  # knowledge_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_category = "all"
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            KnowledgeBasePanel {
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
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 标题栏
        header_layout = QHBoxLayout()
        
        title = QLabel("📚 知识库")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #00D4AA;
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # 操作按钮
        add_btn = QPushButton("➕ 添加知识")
        add_btn.setStyleSheet("""
            QPushButton {
                background: #00D4AA;
                color: #0D0D0D;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #00E8BB;
            }
        """)
        add_btn.clicked.connect(self.add_knowledge_requested.emit)
        header_layout.addWidget(add_btn)
        
        sync_btn = QPushButton("🔄 同步")
        sync_btn.clicked.connect(self._on_sync)
        header_layout.addWidget(sync_btn)
        
        export_btn = QPushButton("📤 导出")
        export_btn.clicked.connect(self._on_export)
        header_layout.addWidget(export_btn)
        
        layout.addLayout(header_layout)
        
        # 分类选择
        category_layout = QHBoxLayout()
        category_layout.setSpacing(8)
        
        categories = ["全部", "文档", "代码", "数据", "图片"]
        self.category_btns = {}
        for cat in categories:
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.setChecked(cat == "全部")
            btn.clicked.connect(lambda c, c2=cat: self._on_category_change(c2))
            self.category_btns[cat] = btn
            category_layout.addWidget(btn)
        
        category_layout.addStretch()
        
        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索知识...")
        self.search_input.setMaximumWidth(300)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #1A1A1A;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 8px 16px;
                color: #FFFFFF;
            }
        """)
        self.search_input.textChanged.connect(self._on_search)
        category_layout.addWidget(self.search_input)
        
        layout.addLayout(category_layout)
        
        # 主内容区
        content = QSplitter(Qt.Orientation.Horizontal)
        
        # 知识列表
        self.knowledge_list = QListWidget()
        self.knowledge_list.setStyleSheet("""
            QListWidget {
                background: #1A1A1A;
                border: none;
                border-radius: 12px;
            }
            QListWidget::item {
                background: transparent;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 4px;
            }
            QListWidget::item:selected {
                background: #252525;
            }
        """)
        self.knowledge_list.itemClicked.connect(self._on_item_click)
        content.addWidget(self.knowledge_list)
        
        # 详情面板
        self.detail_panel = self._create_detail_panel()
        content.addWidget(self.detail_panel)
        
        content.setStretchFactor(0, 1)
        content.setStretchFactor(1, 2)
        
        layout.addWidget(content, 1)
    
    def _create_detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: #1A1A1A;
                border-radius: 12px;
            }
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # 标题
        self.detail_title = QLabel("选择知识条目查看详情")
        self.detail_title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
        """)
        layout.addWidget(self.detail_title)
        
        # 元信息
        meta_layout = QHBoxLayout()
        
        self.detail_tags = QLabel("标签: -")
        self.detail_tags.setStyleSheet("color: #888888; font-size: 13px;")
        meta_layout.addWidget(self.detail_tags)
        
        self.detail_date = QLabel("创建: -")
        self.detail_date.setStyleSheet("color: #888888; font-size: 13px;")
        meta_layout.addWidget(self.detail_date)
        
        meta_layout.addStretch()
        layout.addLayout(meta_layout)
        
        # 内容
        self.detail_content = QScrollArea()
        self.detail_content.setWidgetResizable(True)
        self.detail_content.setStyleSheet("border: none;")
        
        content_text = QTextEdit()
        content_text.setReadOnly(True)
        content_text.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                color: #A0A0A0;
                font-size: 14px;
            }
        """)
        self.detail_content.setWidget(content_text)
        layout.addWidget(self.detail_content, 1)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        edit_btn = QPushButton("✏️ 编辑")
        edit_btn.clicked.connect(self._on_edit)
        btn_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("🗑️ 删除")
        delete_btn.setStyleSheet("""
            QPushButton {
                background: #FF5252;
                color: #FFFFFF;
            }
            QPushButton:hover {
                background: #FF6B6B;
            }
        """)
        delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(delete_btn)
        
        btn_layout.addStretch()
        
        copy_btn = QPushButton("📋 复制")
        copy_btn.clicked.connect(self._on_copy)
        btn_layout.addWidget(copy_btn)
        
        layout.addLayout(btn_layout)
        
        return panel
    
    def _on_category_change(self, category: str):
        self._current_category = category
        for cat, btn in self.category_btns.items():
            btn.setChecked(cat == category)
    
    def _on_search(self, query: str):
        self.search_requested.emit(query)
    
    def _on_sync(self):
        pass  # TODO: 同步知识库
    
    def _on_export(self):
        pass  # TODO: 导出知识库
    
    def _on_item_click(self, item: QListWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.detail_title.setText(data.get("title", ""))
            self.detail_tags.setText(f"标签: {', '.join(data.get('tags', []))}")
            self.detail_date.setText(f"创建: {data.get('created_at', '-')}")
    
    def _on_edit(self):
        pass  # TODO: 编辑知识
    
    def _on_delete(self):
        pass  # TODO: 删除知识
    
    def _on_copy(self):
        pass  # TODO: 复制内容
    
    def show_knowledge_list(self, items: list):
        """显示知识列表"""
        self.knowledge_list.clear()
        for item in items:
            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.knowledge_list.addItem(list_item)


__all__ = ["KnowledgeBasePanel"]
