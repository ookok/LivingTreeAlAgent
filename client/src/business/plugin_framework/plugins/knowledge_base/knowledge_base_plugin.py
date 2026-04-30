"""
知识库插件

提供文档管理、检索、标注、关联功能
支持知识图谱可视化
"""

import uuid
from typing import Dict, List, Optional, Any
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QTextEdit, QLineEdit, QPushButton,
    QSplitter, QLabel, QMenu, QToolBar,
    QWidgetAction, QCompleter,
)
from PyQt6.QtGui import QAction, QIcon, QFont

from business.plugin_framework.base_plugin import (
    BasePlugin, PluginManifest, PluginType,
    ViewPreference, ViewMode
)
from business.plugin_framework.event_bus import Event


class DocumentItem:
    """文档项"""

    def __init__(
        self,
        doc_id: str,
        title: str,
        content: str = "",
        parent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        self.id = doc_id
        self.title = title
        self.content = content
        self.parent_id = parent_id
        self.tags = tags or []
        self.children: List['DocumentItem'] = []
        self.created_at = None
        self.updated_at = None

    def add_child(self, child: 'DocumentItem') -> None:
        self.children.append(child)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "parent_id": self.parent_id,
            "tags": self.tags,
            "children": [c.to_dict() for c in self.children],
        }


class KnowledgeBasePlugin(BasePlugin):
    """
    知识库插件

    提供：
    - 文档树管理
    - 全文搜索
    - 标签系统
    - 知识图谱
    """

    # 信号定义
    document_selected = pyqtSignal(str)  # doc_id
    search_results_ready = pyqtSignal(list)  # results

    def __init__(self, manifest: PluginManifest, framework):
        super().__init__(manifest, framework)
        self._documents: Dict[str, DocumentItem] = {}
        self._root_items: List[DocumentItem] = []
        self._current_doc_id: Optional[str] = None
        self._search_index: Dict[str, str] = {}  # doc_id -> searchable_text

        # 注册事件处理
        self.register_event_handler("file_opened", self._on_file_opened)
        self.register_event_handler("text_selected", self._on_text_selected)

    def on_init(self) -> None:
        """初始化"""
        self.log_info("知识库插件初始化")

        # 加载示例数据
        self._load_sample_data()

    def on_create_widget(self) -> QWidget:
        """创建主Widget"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        # 创建主分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：文档树
        left_panel = self._create_tree_panel()
        splitter.addWidget(left_panel)

        # 中间：内容编辑器
        center_panel = self._create_editor_panel()
        splitter.addWidget(center_panel)

        # 右侧：属性面板
        right_panel = self._create_properties_panel()
        splitter.addWidget(right_panel)

        # 设置初始比例
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)

        layout.addWidget(splitter)

        return widget

    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QToolBar()
        toolbar.setMovable(False)

        # 搜索框
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索文档...")
        self._search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_input)

        toolbar.addSeparator()

        # 操作按钮
        add_btn = QPushButton("新建")
        add_btn.clicked.connect(self._on_new_document)
        toolbar.addWidget(add_btn)

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save)
        toolbar.addWidget(save_btn)

        return toolbar

    def _create_tree_panel(self) -> QWidget:
        """创建文档树面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        # 标签过滤
        self._tag_filter = QLineEdit()
        self._tag_filter.setPlaceholderText("标签过滤...")
        layout.addWidget(self._tag_filter)

        # 文档树
        self._doc_tree = QTreeWidget()
        self._doc_tree.setHeaderLabel("文档")
        self._doc_tree.itemClicked.connect(self._on_tree_item_clicked)
        self._doc_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._doc_tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        layout.addWidget(self._doc_tree)

        return widget

    def _create_editor_panel(self) -> QWidget:
        """创建编辑器面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        # 标题编辑
        title_layout = QHBoxLayout()
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("文档标题")
        self._title_edit.textChanged.connect(self._on_title_changed)
        title_layout.addWidget(QLabel("标题:"))
        title_layout.addWidget(self._title_edit)
        layout.addLayout(title_layout)

        # 内容编辑器
        self._content_edit = QTextEdit()
        self._content_edit.setPlaceholderText("输入文档内容...")
        self._content_edit.textChanged.connect(self._on_content_changed)
        layout.addWidget(self._content_edit)

        return widget

    def _create_properties_panel(self) -> QWidget:
        """创建属性面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        # 标签管理
        layout.addWidget(QLabel("标签"))
        self._tags_list = QListWidget()
        layout.addWidget(self._tags_list)

        tag_layout = QHBoxLayout()
        self._tag_input = QLineEdit()
        self._tag_input.setPlaceholderText("添加标签...")
        add_tag_btn = QPushButton("+")
        add_tag_btn.clicked.connect(self._on_add_tag)
        tag_layout.addWidget(self._tag_input)
        tag_layout.addWidget(add_tag_btn)
        layout.addLayout(tag_layout)

        layout.addStretch()

        return widget

    def _load_sample_data(self) -> None:
        """加载示例数据"""
        # 创建示例文档
        root1 = DocumentItem(
            doc_id=str(uuid.uuid4()),
            title="技术文档",
            content="这是技术文档的根节点",
            tags=["技术", "开发"]
        )

        child1 = DocumentItem(
            doc_id=str(uuid.uuid4()),
            title="Python指南",
            content="Python编程语言指南...",
            parent_id=root1.id,
            tags=["Python", "编程"]
        )
        root1.add_child(child1)

        child2 = DocumentItem(
            doc_id=str(uuid.uuid4()),
            title="JavaScript指南",
            content="JavaScript编程指南...",
            parent_id=root1.id,
            tags=["JavaScript", "Web"]
        )
        root1.add_child(child2)

        root2 = DocumentItem(
            doc_id=str(uuid.uuid4()),
            title="产品文档",
            content="产品相关文档",
            tags=["产品", "设计"]
        )

        self._root_items = [root1, root2]
        self._rebuild_tree()

        # 更新搜索索引
        self._update_search_index()

    def _rebuild_tree(self) -> None:
        """重建文档树"""
        self._doc_tree.clear()

        for root in self._root_items:
            self._add_tree_item(root, None)

    def _add_tree_item(self, doc: DocumentItem, parent: QTreeWidgetItem) -> QTreeWidgetItem:
        """添加树节点"""
        item = QTreeWidgetItem(parent)
        item.setText(0, doc.title)
        item.setData(0, Qt.ItemDataRole.UserRole, doc.id)

        # 添加标签图标
        if doc.tags:
            item.setToolTip(0, ", ".join(doc.tags))

        for child in doc.children:
            self._add_tree_item(child, item)

        if parent is None:
            self._doc_tree.addTopLevelItem(item)

        return item

    def _find_document(self, doc_id: str) -> Optional[DocumentItem]:
        """查找文档"""
        for root in self._root_items:
            if root.id == doc_id:
                return root
            found = self._search_document_tree(root, doc_id)
            if found:
                return found
        return None

    def _search_document_tree(self, doc: DocumentItem, doc_id: str) -> Optional[DocumentItem]:
        """搜索文档树"""
        for child in doc.children:
            if child.id == doc_id:
                return child
            found = self._search_document_tree(child, doc_id)
            if found:
                return found
        return None

    def _update_search_index(self) -> None:
        """更新搜索索引"""
        self._search_index.clear()
        for root in self._root_items:
            self._index_document(root)

    def _index_document(self, doc: DocumentItem) -> None:
        """索引文档"""
        searchable = f"{doc.title} {doc.content} {' '.join(doc.tags)}"
        self._search_index[doc.id] = searchable.lower()
        for child in doc.children:
            self._index_document(child)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """树节点点击"""
        doc_id = item.data(0, Qt.ItemDataRole.UserRole)
        if doc_id:
            self._load_document(doc_id)

    def _on_tree_context_menu(self, pos) -> None:
        """树上下文菜单"""
        menu = QMenu()
        menu.addAction("新建子文档", self._on_new_child_document)
        menu.addAction("删除", self._on_delete_document)
        menu.exec(self._doc_tree.mapToGlobal(pos))

    def _load_document(self, doc_id: str) -> None:
        """加载文档"""
        doc = self._find_document(doc_id)
        if doc:
            self._current_doc_id = doc_id
            self._title_edit.setText(doc.title)
            self._content_edit.setPlainText(doc.content)

            # 更新标签
            self._tags_list.clear()
            for tag in doc.tags:
                self._tags_list.addItem(tag)

            self.document_selected.emit(doc_id)

    def _on_new_document(self) -> None:
        """新建文档"""
        new_doc = DocumentItem(
            doc_id=str(uuid.uuid4()),
            title="新文档",
            content="",
            tags=[]
        )
        self._root_items.append(new_doc)
        self._rebuild_tree()
        self._update_search_index()
        self._load_document(new_doc.id)

    def _on_new_child_document(self) -> None:
        """新建子文档"""
        if not self._current_doc_id:
            return

        parent = self._find_document(self._current_doc_id)
        if parent:
            new_doc = DocumentItem(
                doc_id=str(uuid.uuid4()),
                title="新子文档",
                content="",
                parent_id=parent.id,
                tags=[]
            )
            parent.add_child(new_doc)
            self._rebuild_tree()
            self._update_search_index()
            self._load_document(new_doc.id)

    def _on_delete_document(self) -> None:
        """删除文档"""
        if not self._current_doc_id:
            return

        # 从根节点移除
        for i, root in enumerate(self._root_items):
            if root.id == self._current_doc_id:
                self._root_items.pop(i)
                break
            if self._remove_from_tree(root, self._current_doc_id):
                break

        self._current_doc_id = None
        self._title_edit.clear()
        self._content_edit.clear()
        self._tags_list.clear()
        self._rebuild_tree()
        self._update_search_index()

    def _remove_from_tree(self, doc: DocumentItem, doc_id: str) -> bool:
        """从树中移除文档"""
        for child in doc.children:
            if child.id == doc_id:
                doc.children.remove(child)
                return True
            if self._remove_from_tree(child, doc_id):
                return True
        return False

    def _on_title_changed(self, text: str) -> None:
        """标题更改"""
        if self._current_doc_id:
            doc = self._find_document(self._current_doc_id)
            if doc:
                doc.title = text
                self._rebuild_tree()
                self._update_search_index()

    def _on_content_changed(self) -> None:
        """内容更改"""
        if self._current_doc_id:
            doc = self._find_document(self._current_doc_id)
            if doc:
                doc.content = self._content_edit.toPlainText()
                self._update_search_index()

    def _on_add_tag(self) -> None:
        """添加标签"""
        if not self._current_doc_id:
            return

        tag = self._tag_input.text().strip()
        if not tag:
            return

        doc = self._find_document(self._current_doc_id)
        if doc and tag not in doc.tags:
            doc.tags.append(tag)
            self._tags_list.addItem(tag)
            self._tag_input.clear()
            self._rebuild_tree()
            self._update_search_index()

    def _on_search(self, text: str) -> None:
        """搜索"""
        if not text.strip():
            self._rebuild_tree()
            return

        query = text.lower()
        results = []

        for doc_id, searchable in self._search_index.items():
            if query in searchable:
                doc = self._find_document(doc_id)
                if doc:
                    results.append(doc.to_dict())

        self.search_results_ready.emit(results)

        # 临时过滤树
        self._doc_tree.clear()
        for doc_id, searchable in self._search_index.items():
            if query in searchable:
                doc = self._find_document(doc_id)
                if doc:
                    self._add_tree_item(doc, None)

    def _on_file_opened(self, data: Dict[str, Any]) -> None:
        """处理文件打开事件"""
        path = data.get("path")
        if path:
            # 可以从文件中导入内容
            self.log_info(f"从文件创建文档: {path}")

    def _on_text_selected(self, data: Dict[str, Any]) -> None:
        """处理文本选中事件"""
        text = data.get("text")
        if text:
            # 可以用选中的文本创建笔记
            self.log_info(f"选中文本: {text[:50]}...")

    def on_activate(self) -> None:
        """激活"""
        self.log_info("知识库插件激活")

    def on_deactivate(self) -> None:
        """停用"""
        # 保存当前状态
        self._state["current_doc"] = self._current_doc_id
        self.log_info("知识库插件停用")

    def on_save_state(self) -> Dict[str, Any]:
        """保存状态"""
        return {
            "documents": [root.to_dict() for root in self._root_items],
            "current_doc": self._current_doc_id,
        }

    def on_load_state(self, state: Dict[str, Any]) -> None:
        """加载状态"""
        if "documents" in state:
            # 重建文档树
            self._root_items = []
            for doc_data in state["documents"]:
                self._root_items.append(self._rebuild_from_dict(doc_data))
            self._rebuild_tree()
            self._update_search_index()

        if "current_doc" in state:
            self._current_doc_id = state["current_doc"]
            if self._current_doc_id:
                self._load_document(self._current_doc_id)

    def _rebuild_from_dict(self, data: Dict[str, Any]) -> DocumentItem:
        """从字典重建文档"""
        doc = DocumentItem(
            doc_id=data["id"],
            title=data["title"],
            content=data.get("content", ""),
            parent_id=data.get("parent_id"),
            tags=data.get("tags", []),
        )
        for child_data in data.get("children", []):
            child = self._rebuild_from_dict(child_data)
            doc.add_child(child)
        return doc


# 插件清单
MANIFEST = PluginManifest(
    id="knowledge_base",
    name="知识库",
    version="1.0.0",
    author="Hermes Team",
    description="文档管理、检索、标注、关联，支持知识图谱可视化",
    plugin_type=PluginType.KNOWLEDGE,
    view_preference=ViewPreference(
        preferred_mode=ViewMode.TABBED,
        dock_area="left",
        default_width=300,
        default_height=500,
        min_width=200,
        min_height=150,
    ),
    icon=":/icons/knowledge.svg",
    lazy_load=True,
)
