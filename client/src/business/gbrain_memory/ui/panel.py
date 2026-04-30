"""
GBrain 记忆系统 PyQt6 管理面板

提供可视化界面来管理记忆页面
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QTextEdit, QListWidget, QListWidgetItem, QTabWidget,
    QComboBox, QGroupBox, QScrollArea, QFrame, QDialog, QDialogButtonBox,
    QMessageBox, QToolButton, QMenu, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QAction

from client.src.business.gbrain_memory.agent_loop import BrainAgentLoop
from client.src.business.gbrain_memory.models import (
    BrainPage, MemoryCategory, CATEGORY_STRUCTURE, EvidenceSource
)


class BrainPageCard(QFrame):
    """记忆页面卡片"""

    clicked = pyqtSignal(str)  # page_id
    delete_requested = pyqtSignal(str)

    def __init__(self, page: BrainPage, parent=None):
        super().__init__(parent)
        self.page = page
        self._setup_ui()
        self._load_content()

    def _setup_ui(self):
        """设置 UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet("""
            BrainPageCard {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
                margin: 5px;
            }
            BrainPageCard:hover {
                background-color: #e9ecef;
                border: 1px solid #adb5bd;
            }
        """)

        layout = QVBoxLayout(self)

        # 标题行
        header = QHBoxLayout()

        self.category_label = QLabel()
        self.category_label.setStyleSheet("""
            QLabel {
                background-color: #007bff;
                color: white;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 10px;
            }
        """)

        self.title_label = QLabel()
        self.title_label.setFont(QFont("微软雅黑", 11, QFont.Weight.Bold))

        header.addWidget(self.category_label)
        header.addWidget(self.title_label, 1)
        header.addStretch()

        # 删除按钮
        self.delete_btn = QToolButton()
        self.delete_btn.setText("🗑️")
        self.delete_btn.setStyleSheet("border: none;")
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.page.id))

        header.addWidget(self.delete_btn)

        layout.addLayout(header)

        # 摘要
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setMaximumHeight(60)
        self.summary_label.setStyleSheet("color: #495057; font-size: 12px;")

        layout.addWidget(self.summary_label)

        # 元信息行
        meta = QHBoxLayout()

        self.timeline_count = QLabel(f"📅 {len(self.page.timeline)} 条记录")
        self.timeline_count.setStyleSheet("color: #6c757d; font-size: 11px;")

        self.last_modified = QLabel(f"🕐 {self._format_time(self.page.last_modified)}")
        self.last_modified.setStyleSheet("color: #6c757d; font-size: 11px;")

        meta.addWidget(self.timeline_count)
        meta.addWidget(self.last_modified)
        meta.addStretch()

        layout.addLayout(meta)

        # 标签
        if self.page.tags:
            tags_layout = QHBoxLayout()
            for tag in self.page.tags[:3]:
                tag_label = QLabel(f"#{tag}")
                tag_label.setStyleSheet("""
                    QLabel {
                        background-color: #e9ecef;
                        color: #495057;
                        padding: 1px 6px;
                        border-radius: 3px;
                        font-size: 10px;
                    }
                """)
                tags_layout.addWidget(tag_label)
            tags_layout.addStretch()
            layout.addLayout(tags_layout)

        # 点击事件
        self.mousePressEvent = lambda e: self.clicked.emit(self.page.id)

    def _load_content(self):
        """加载内容"""
        self.category_label.setText(self.page.category.value)
        self.title_label.setText(self.page.title or self.page.id)
        self.summary_label.setText(
            self.page.compiled_truth.summary[:100] + "..."
            if self.page.compiled_truth.summary and len(self.page.compiled_truth.summary) > 100
            else self.page.compiled_truth.summary or "（无摘要）"
        )

    def _format_time(self, timestamp: float) -> str:
        """格式化时间"""
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


class PageDetailDialog(QDialog):
    """页面详情对话框"""

    def __init__(self, page: BrainPage, parent=None):
        super().__init__(parent)
        self.page = page
        self.setWindowTitle(f"记忆页面: {page.title or page.id}")
        self.setMinimumSize(700, 500)
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)

        # 分类和标签
        info_layout = QHBoxLayout()

        info_layout.addWidget(QLabel(f"**分类**: {self.page.category.value}"))
        info_layout.addWidget(QLabel(f"**ID**: {self.page.id}"))

        if self.page.tags:
            tags = ", ".join(f"#{t}" for t in self.page.tags)
            info_layout.addWidget(QLabel(f"**标签**: {tags}"))

        info_layout.addStretch()
        layout.addLayout(info_layout)

        # 标签页
        tabs = QTabWidget()

        # === COMPILED TRUTH ===
        truth_tab = QWidget()
        truth_layout = QVBoxLayout(truth_tab)

        truth_layout.addWidget(QLabel("**摘要**"))
        summary = QTextEdit()
        summary.setReadOnly(True)
        summary.setPlainText(self.page.compiled_truth.summary or "（无）")
        truth_layout.addWidget(summary)

        truth_layout.addWidget(QLabel("**关键点**"))
        key_points = QTextEdit()
        key_points.setReadOnly(True)
        key_points.setPlainText("\n".join(f"- {p}" for p in self.page.compiled_truth.key_points) or "（无）")
        truth_layout.addWidget(key_points)

        tabs.addTab(truth_tab, "📝 COMPILED TRUTH")

        # === TIMELINE ===
        timeline_tab = QWidget()
        timeline_layout = QVBoxLayout(timeline_tab)

        timeline_list = QListWidget()
        for entry in reversed(self.page.timeline[-20:]):  # 最近20条
            from datetime import datetime
            ts = datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d %H:%M")
            item_text = f"**{ts}** [{entry.source_type.value}]\n来源: {entry.source}\n{entry.content}"
            timeline_list.addItem(item_text)

        timeline_layout.addWidget(timeline_list)
        tabs.addTab(timeline_tab, "📅 TIMELINE")

        # === RAW ===
        raw_tab = QWidget()
        raw_layout = QVBoxLayout(raw_tab)

        raw_text = QTextEdit()
        raw_text.setReadOnly(True)
        raw_text.setPlainText(self.page.to_markdown())
        raw_layout.addWidget(raw_text)

        tabs.addTab(raw_tab, "📄 RAW")
        layout.addWidget(tabs)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class GBrainPanel(QWidget):
    """
    GBrain 记忆系统管理面板

    功能：
    1. 自然语言创建记忆
    2. 分类浏览
    3. 搜索
    4. 页面管理
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.brain_agent = None
        self.current_category = None
        self._setup_ui()
        self._init_brain()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)

        # === 顶部：标题和统计 ===
        header = QHBoxLayout()

        title = QLabel("🧠 GBrain 记忆系统")
        title.setFont(QFont("微软雅黑", 14, QFont.Weight.Bold))
        header.addWidget(title)

        header.addStretch()

        self.stats_label = QLabel("加载中...")
        self.stats_label.setStyleSheet("color: #6c757d;")
        header.addWidget(self.stats_label)

        layout.addLayout(header)

        # === 搜索栏 ===
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索记忆...")
        self.search_input.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.search_input, 1)

        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self._on_search)
        search_layout.addWidget(search_btn)

        layout.addLayout(search_layout)

        # === 主内容区 ===
        content = QHBoxLayout()

        # 左侧：分类列表
        sidebar = QVBoxLayout()
        sidebar.setSpacing(2)

        sidebar.addWidget(QLabel("**分类**"))
        sidebar.addWidget(QLabel())

        self.category_list = QListWidget()
        self.category_list.currentItemChanged.connect(self._on_category_changed)
        sidebar.addWidget(self.category_list, 1)

        layout.addLayout(sidebar, 1)

        # 右侧：页面列表
        main = QVBoxLayout()

        # 操作按钮
        actions = QHBoxLayout()

        new_btn = QPushButton("➕ 新建记忆")
        new_btn.clicked.connect(self._on_new_page)
        actions.addWidget(new_btn)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh)
        actions.addWidget(refresh_btn)

        export_btn = QPushButton("📤 导出")
        export_btn.clicked.connect(self._on_export)
        actions.addWidget(export_btn)

        main.addLayout(actions)

        # 页面列表
        self.page_list = QListWidget()
        self.page_list.itemClicked.connect(self._on_page_clicked)
        main.addWidget(self.page_list, 1)

        layout.addLayout(main, 4)

        # === 状态栏 ===
        self.status_bar = QLabel("就绪")
        self.status_bar.setStyleSheet("color: #6c757d; padding: 5px;")
        layout.addWidget(self.status_bar)

    def _init_brain(self):
        """初始化大脑"""
        try:
            self.brain_agent = BrainAgentLoop()
            self._populate_categories()
            self._refresh()
        except Exception as e:
            self.status_bar.setText(f"初始化失败: {str(e)}")

    def _populate_categories(self):
        """填充分类列表"""
        self.category_list.clear()

        # 全部
        item = QListWidgetItem("📚 全部")
        item.setData(Qt.ItemDataRole.UserRole, None)
        self.category_list.addItem(item)

        # 按分类
        for cat in MemoryCategory:
            icon = self._get_category_icon(cat)
            item = QListWidgetItem(f"{icon} {cat.value}")
            item.setData(Qt.ItemDataRole.UserRole, cat)
            self.category_list.addItem(item)

    def _get_category_icon(self, category: MemoryCategory) -> str:
        """获取分类图标"""
        icons = {
            MemoryCategory.ORIGINALS: "💡",
            MemoryCategory.PEOPLE: "👤",
            MemoryCategory.COMPANIES: "🏢",
            MemoryCategory.PROJECTS: "📁",
            MemoryCategory.MEETINGS: "📅",
            MemoryCategory.IDEAS: "🎨",
            MemoryCategory.CONCEPTS: "📖",
            MemoryCategory.FACTS: "✅",
            MemoryCategory.PREFERENCES: "⚙️",
            MemoryCategory.CONVERSATIONS: "💬",
            MemoryCategory.DOCUMENTS: "📄",
            MemoryCategory.UNCLASSIFIED: "📦",
        }
        return icons.get(category, "📦")

    def _refresh(self):
        """刷新页面列表"""
        if not self.brain_agent:
            return

        self.page_list.clear()

        # 获取页面
        if self.current_category:
            pages = self.brain_agent.page_manager.get_pages_by_category(self.current_category)
        else:
            pages = self.brain_agent.page_manager.get_all_pages(limit=100)

        # 添加卡片
        for page in pages:
            item = QListWidgetItem()
            card = BrainPageCard(page)
            card.clicked.connect(self._on_page_clicked_by_id)
            card.delete_requested.connect(self._on_delete_page)
            self.page_list.addItem(item)
            self.page_list.setItemWidget(item, card)
            item.setSizeHint(QSize(0, card.sizeHint().height()))

        # 更新统计
        self._update_stats()

    def _update_stats(self):
        """更新统计信息"""
        if not self.brain_agent:
            return

        stats = self.brain_agent.get_stats()
        page_count = stats["page_count"]
        total = sum(page_count.values())

        self.stats_label.setText(f"共 {total} 页记忆")

    def _on_category_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """分类切换"""
        if current:
            self.current_category = current.data(Qt.ItemDataRole.UserRole)
            self._refresh()

    def _on_search(self):
        """搜索"""
        if not self.brain_agent:
            return

        query = self.search_input.text().strip()
        if not query:
            self.current_category = None
            self._refresh()
            return

        # 执行搜索
        from client.src.business.gbrain_memory.models import MemoryQuery

        keywords = query.split()
        search_results = self.brain_agent.search_engine.search(
            MemoryQuery(keywords=keywords, limit=50)
        )

        self.page_list.clear()

        for result in search_results:
            page = result.page
            item = QListWidgetItem()
            card = BrainPageCard(page)
            card.clicked.connect(self._on_page_clicked_by_id)
            card.delete_requested.connect(self._on_delete_page)
            self.page_list.addItem(item)
            self.page_list.setItemWidget(item, card)
            item.setSizeHint(QSize(0, card.sizeHint().height()))

        self.status_bar.setText(f"找到 {len(search_results)} 条结果")

    def _on_page_clicked(self, item: QListWidgetItem):
        """页面点击"""
        widget = self.page_list.itemWidget(item)
        if widget and isinstance(widget, BrainPageCard):
            self._show_page_detail(widget.page)

    def _on_page_clicked_by_id(self, page_id: str):
        """通过 ID 点击页面"""
        if not self.brain_agent:
            return

        page = self.brain_agent.page_manager.get_page(page_id)
        if page:
            self._show_page_detail(page)

    def _show_page_detail(self, page: BrainPage):
        """显示页面详情"""
        dialog = PageDetailDialog(page, self)
        dialog.exec()

    def _on_new_page(self):
        """新建页面"""
        dialog = NewPageDialog(self)
        if dialog.exec():
            title = dialog.title_input.text().strip()
            content = dialog.content_input.toPlainText().strip()
            category = dialog.category_combo.currentData()
            tags_text = dialog.tags_input.text().strip()

            if not title or not content:
                QMessageBox.warning(self, "警告", "标题和内容不能为空")
                return

            tags = [t.strip() for t in tags_text.split(",") if t.strip()] if tags_text else []

            page = self.brain_agent.remember(
                content=content,
                title=title,
                category=category or MemoryCategory.UNCLASSIFIED,
                tags=tags
            )

            self._refresh()
            self.status_bar.setText(f"✅ 已创建记忆: {page.title}")

    def _on_delete_page(self, page_id: str):
        """删除页面"""
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除这个记忆页面吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.brain_agent.page_manager.delete_page(page_id)
            self._refresh()
            self.status_bar.setText("🗑️ 已删除")

    def _on_export(self):
        """导出"""
        if not self.brain_agent:
            return

        from client.src.business.gbrain_memory.sync import SyncManager
        sync = SyncManager()
        result = sync.export_all()

        QMessageBox.information(self, "导出完成", f"已导出到:\n{result}")


class NewPageDialog(QDialog):
    """新建页面对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建记忆")
        self.setMinimumSize(500, 400)
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)

        # 标题
        layout.addWidget(QLabel("**标题**"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("输入记忆标题...")
        layout.addWidget(self.title_input)

        # 分类
        layout.addWidget(QLabel("**分类**"))
        self.category_combo = QComboBox()
        for cat in MemoryCategory:
            self.category_combo.addItem(cat.value, cat)
        layout.addWidget(self.category_combo)

        # 标签
        layout.addWidget(QLabel("**标签**（逗号分隔）"))
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("例如: 重要, 工作, 项目A")
        layout.addWidget(self.tags_input)

        # 内容
        layout.addWidget(QLabel("**内容**"))
        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("输入记忆内容...")
        layout.addWidget(self.content_input, 1)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
