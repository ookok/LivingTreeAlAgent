"""
🌲 知识林地面板 (Knowledge Grove Panel)
========================================

行业化智库 × 伪域名阅览厅 × 可迁徙知识包

四个标签页：
1. 🏛️ 林区导航 - 按行业浏览知识
2. 📚 知识条目 - 列表/搜索/管理
3. 🔍 Wiki预览 - 伪域名路由渲染
4. 📦 导入导出 - LTKG包管理
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QLineEdit, QTextEdit,
    QListWidget, QListWidgetItem, QFrame, QComboBox,
    QProgressBar, QFileDialog, QMessageBox, QScrollArea,
    QSizePolicy, QSpacerItem, QGridLayout, QGroupBox,
    QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor

from pathlib import Path
from datetime import datetime


class IndustryCard(QFrame):
    """行业林区卡片"""

    clicked = pyqtSignal(str)  # industry_id

    def __init__(self, industry_data: dict, parent=None):
        super().__init__(parent)
        self.industry_id = industry_data.get('id', '')
        self._build_ui(industry_data)

    def _build_ui(self, data: dict):
        self.setObjectName("industry-card")
        self.setFixedSize(180, 140)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # 图标
        icon_label = QLabel(data.get('icon', '🌲'))
        icon_label.setObjectName("card-icon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 36px;")

        # 名称
        name_label = QLabel(data.get('name', '未知林区').replace('🌲 ', ''))
        name_label.setObjectName("card-name")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-weight: 600; font-size: 14px; color: #2a6d39;")

        # 描述
        count_label = QLabel(f"{data.get('entry_count', 0)} 条知识")
        count_label.setObjectName("card-count")
        count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_label.setStyleSheet("font-size: 12px; color: #6b6b6b;")

        layout.addWidget(icon_label)
        layout.addWidget(name_label)
        layout.addWidget(count_label)

        # 样式
        self.setStyleSheet("""
            #industry-card {
                background: white;
                border-radius: 12px;
                border: 2px solid transparent;
            }
            #industry-card:hover {
                border-color: #4a9d5b;
                background: #f8fff8;
            }
        """)

    def mousePressEvent(self, event):
        self.clicked.emit(self.industry_id)
        super().mousePressEvent(event)


class EntryListItem(QFrame):
    """知识条目列表项"""

    def __init__(self, entry_data: dict, parent=None):
        super().__init__(parent)
        self.entry_id = entry_data.get('id', '')
        self._build_ui(entry_data)

    def _build_ui(self, data: dict):
        self.setObjectName("entry-item")
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # 标题行
        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)

        title = QLabel(data.get('title', '无标题'))
        title.setObjectName("entry-title")
        title.setStyleSheet("font-weight: 600; font-size: 14px; color: #2a6d39;")

        # 标签
        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(4)
        for tag in (data.get('tags', []) or [])[:3]:
            tag_label = QLabel(tag)
            tag_label.setObjectName("tag-label")
            tag_label.setStyleSheet("""
                background: #2a6d39;
                color: white;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 10px;
            """)
            tags_layout.addWidget(tag_label)
        tags_layout.addStretch()

        title_layout.addWidget(title)
        title_layout.addLayout(tags_layout)

        # 摘要
        summary = QLabel(data.get('summary', '')[:100] + ('...' if len(data.get('summary', '')) > 100 else ''))
        summary.setObjectName("entry-summary")
        summary.setStyleSheet("font-size: 12px; color: #6b6b6b;")
        summary.setWordWrap(True)

        # 元数据行
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(12)

        industry = data.get('industries', [''])[0] if data.get('industries') else 'general'
        meta_layout.addWidget(QLabel(f"🏷️ {industry}"))
        meta_layout.addWidget(QLabel(f"📅 {data.get('created_at', '')[:10]}"))
        meta_layout.addWidget(QLabel(f"📖 {data.get('usage_count', 0)}次"))
        meta_layout.addStretch()

        layout.addLayout(title_layout)
        layout.addWidget(summary)
        layout.addLayout(meta_layout)

        self.setStyleSheet("""
            #entry-item {
                background: white;
                border-radius: 8px;
                border-left: 4px solid #2a6d39;
            }
            #entry-item:hover {
                background: #fafaf5;
            }
        """)


class KnowledgeGrovePanel(QWidget):
    """
    知识林地面板

    四个标签：
    - 🏛️ 林区导航
    - 📚 知识条目
    - 🔍 Wiki预览
    - 📦 导入导出
    """

    # 信号
    entry_selected = pyqtSignal(dict)  # 选择知识条目
    wiki_route_requested = pyqtSignal(str)  # 请求Wiki路由

    def __init__(self, grove, parent=None):
        super().__init__(parent)
        self.grove = grove
        self._build_ui()

    def _build_ui(self):
        """构建UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setObjectName("grove-tabs")

        # 1. 林区导航
        self.tab_navigation = self._create_navigation_tab()
        self.tabs.addTab(self.tab_navigation, "🏛️ 林区导航")

        # 2. 知识条目
        self.tab_entries = self._create_entries_tab()
        self.tabs.addTab(self.tab_entries, "📚 知识条目")

        # 3. Wiki预览
        self.tab_wiki = self._create_wiki_tab()
        self.tabs.addTab(self.tab_wiki, "🔍 Wiki预览")

        # 4. 导入导出
        self.tab_import_export = self._create_import_export_tab()
        self.tabs.addTab(self.tab_import_export, "📦 导入导出")

        main_layout.addWidget(self.tabs)

        # 样式
        self.setStyleSheet("""
            #grove-tabs::pane {
                border: none;
            }
            QTabBar::tab {
                padding: 10px 20px;
                font-size: 13px;
            }
        """)

    # ==================== 林区导航 ====================

    def _create_navigation_tab(self) -> QWidget:
        """创建林区导航标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        # 标题
        header = QLabel("🏛️ 选择林区开始浏览")
        header.setStyleSheet("font-size: 18px; font-weight: 600; color: #2a6d39;")
        layout.addWidget(header)

        # 统计信息
        stats = self.grove.get_stats()
        stats_label = QLabel(f"📚 {stats.get('total_entries', 0)} 条知识  |  🏛️ {len(stats.get('by_industry', {}))} 个林区")
        stats_label.setStyleSheet("color: #6b6b6b; font-size: 13px;")
        layout.addWidget(stats_label)

        layout.addSpacing(12)

        # 行业卡片区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(16)

        industries = self.grove.list_industries()
        for i, ind in enumerate(industries):
            if ind.id == "general":
                continue
            card = IndustryCard({
                'id': ind.id,
                'name': ind.name,
                'icon': ind.icon,
                'entry_count': stats.get('by_industry', {}).get(ind.id, 0)
            })
            card.clicked.connect(lambda rid=ind.id: self._on_industry_clicked(rid))
            grid.addWidget(card, i // 4, i % 4)

        # 添加通用林区
        general_card = IndustryCard({
            'id': 'general',
            'name': '🌐 通用林区',
            'icon': '🌐',
            'entry_count': stats.get('by_industry', {}).get('general', 0)
        })
        general_card.clicked.connect(lambda rid='general': self._on_industry_clicked(rid))
        grid.addWidget(general_card, (len(industries)) // 4, (len(industries)) % 4)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        return widget

    def _on_industry_clicked(self, industry_id: str):
        """行业卡片点击"""
        self.tabs.setCurrentIndex(1)  # 切换到知识条目页
        self._refresh_entries(industry=industry_id)

    # ==================== 知识条目 ====================

    def _create_entries_tab(self) -> QWidget:
        """创建知识条目标签页"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 左侧：列表
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)

        # 搜索栏
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索知识...")
        self.search_input.setObjectName("search-input")
        self.search_input.textChanged.connect(self._on_search_changed)

        self.industry_filter = QComboBox()
        self.industry_filter.setObjectName("industry-filter")
        self.industry_filter.addItem("🌐 全部林区", "all")
        for ind in self.grove.list_industries():
            self.industry_filter.addItem(f"{ind.icon} {ind.name}", ind.id)
        self.industry_filter.currentIndexChanged.connect(self._on_filter_changed)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.industry_filter)

        # 列表
        self.entry_list = QListWidget()
        self.entry_list.setObjectName("entry-list")
        self.entry_list.itemClicked.connect(self._on_entry_clicked)

        left_layout.addLayout(search_layout)
        left_layout.addWidget(self.entry_list)

        # 右侧：详情预览
        self.entry_detail = QWidget()
        self.entry_detail.setMaximumWidth(400)
        detail_layout = QVBoxLayout(self.entry_detail)

        self.detail_title = QLabel("选择知识条目查看详情")
        self.detail_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #2a6d39;")
        self.detail_title.setWordWrap(True)

        self.detail_content = QTextEdit()
        self.detail_content.setObjectName("detail-content")
        self.detail_content.setReadOnly(True)

        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_content)

        layout.addWidget(left_panel, 1)
        layout.addWidget(self.entry_detail)

        # 初始加载
        self._refresh_entries()

        return widget

    def _refresh_entries(self, industry: str = None, keyword: str = None):
        """刷新知识条目列表"""
        self.entry_list.clear()

        if keyword:
            entries = self.grove.search_entries(keyword, industry=industry)
        elif industry and industry != 'all':
            entries = self.grove.list_entries(industry=industry)
        else:
            entries = self.grove.list_entries()

        for entry in entries:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, entry.to_dict())
            entry_widget = EntryListItem(entry.to_dict())
            item.setSizeHint(entry_widget.sizeHint())
            self.entry_list.addItem(item)
            self.entry_list.setItemWidget(item, entry_widget)

    def _on_search_changed(self, text: str):
        """搜索文本变化"""
        industry = self.industry_filter.currentData()
        self._refresh_entries(industry=industry, keyword=text or None)

    def _on_filter_changed(self, index: int):
        """行业过滤变化"""
        keyword = self.search_input.text()
        industry = self.industry_filter.currentData()
        self._refresh_entries(industry=industry if industry != 'all' else None, keyword=keyword or None)

    def _on_entry_clicked(self, item: QListWidgetItem):
        """条目点击"""
        data = item.data(Qt.ItemDataRole.UserRole)
        self.detail_title.setText(data.get('title', '无标题'))

        # 格式化内容
        content = f"""
<h3 style="color:#2a6d39;">📌 {data.get('summary', '')}</h3>
<hr/>
<p><b>行业：</b>{', '.join(data.get('industries', []))}</p>
<p><b>标签：</b>{', '.join(data.get('tags', []))}</p>
<p><b>类型：</b>{data.get('knowledge_type', '')}</p>
<p><b>来源：</b>{data.get('source_url', '无')}</p>
<hr/>
<h4>正文：</h4>
<pre style="font-family: inherit; white-space: pre-wrap;">{data.get('content_md', '')[:500]}...</pre>
        """
        self.detail_content.setHtml(content)

        self.entry_selected.emit(data)

    # ==================== Wiki预览 ====================

    def _create_wiki_tab(self) -> QWidget:
        """创建Wiki预览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)

        # 路由输入
        route_layout = QHBoxLayout()

        route_label = QLabel("🌐 伪域名路由：")
        route_label.setStyleSheet("font-weight: 600;")

        self.route_input = QLineEdit()
        self.route_input.setObjectName("route-input")
        self.route_input.setText("wiki.root.tree")
        self.route_input.setPlaceholderText("wiki.root.tree / wiki.electronics.root.tree / wiki.view/industry/slug")

        self.route_go_btn = QPushButton("访问")
        self.route_go_btn.setObjectName("route-go-btn")
        self.route_go_btn.clicked.connect(self._on_wiki_route)

        route_layout.addWidget(route_label)
        route_layout.addWidget(self.route_input, 1)
        route_layout.addWidget(self.route_go_btn)

        # 常用快捷链接
        shortcuts_layout = QHBoxLayout()
        shortcuts_layout.setSpacing(8)

        shortcuts_label = QLabel("快捷访问：")
        for route, name in [
            ("wiki.root.tree", "🏠 首页"),
            ("wiki.electronics.root.tree", "💻 电子"),
            ("wiki.software.root.tree", "📝 软件"),
            ("wiki.ai_ml.root.tree", "🤖 AI/ML"),
        ]:
            btn = QPushButton(name)
            btn.setObjectName(f"shortcut-{route}")
            btn.clicked.connect(lambda checked, r=route: self._navigate_to_route(r))
            shortcuts_layout.addWidget(btn)
        shortcuts_layout.addStretch()

        # Wiki内容预览（HTML）
        self.wiki_preview = QTextEdit()
        self.wiki_preview.setObjectName("wiki-preview")
        self.wiki_preview.setReadOnly(True)

        # 底部提示
        tips = QLabel("💡 提示：在装配园播种知识后，知识会自动出现在对应的林区Wiki中")
        tips.setStyleSheet("color: #6b6b6b; font-size: 12px; padding: 8px; background: #f8f8f8; border-radius: 4px;")

        layout.addLayout(route_layout)
        layout.addLayout(shortcuts_layout)
        layout.addWidget(self.wiki_preview, 1)
        layout.addWidget(tips)

        # 初始加载首页
        self._load_wiki_page("wiki.root.tree")

        return widget

    def _navigate_to_route(self, route: str):
        """导航到路由"""
        self.route_input.setText(route)
        self._on_wiki_route()

    def _on_wiki_route(self):
        """Wiki路由访问"""
        route = self.route_input.text().strip()
        self._load_wiki_page(route)

    def _load_wiki_page(self, route: str):
        """加载Wiki页面"""
        from .wiki_renderer import WikiRenderer

        renderer = WikiRenderer(self.grove)
        route_type, industry, entry_slug = renderer.parse_route(route)

        if route_type == "index":
            html = renderer.render_index()
        elif route_type == "industry":
            html = renderer.render_industry(industry)
        elif route_type == "entry":
            html = renderer.render_entry(entry_slug)
        else:
            html = renderer.render_error("无效的路由")

        self.wiki_preview.setHtml(html)
        self.wiki_route_requested.emit(route)

    # ==================== 导入导出 ====================

    def _create_import_export_tab(self) -> QWidget:
        """创建导入导出标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 导出区域
        export_group = QGroupBox("📤 导出知识包")
        export_layout = QVBoxLayout(export_group)

        export_desc = QLabel("将知识导出为 .ltkg 包，可在不同节点间分享")
        export_desc.setStyleSheet("color: #6b6b6b;")
        export_layout.addWidget(export_desc)

        # 导出选项
        export_options = QHBoxLayout()
        export_options.setSpacing(16)

        self.export_industry = QComboBox()
        self.export_industry.addItem("🌐 全部知识", "all")
        for ind in self.grove.list_industries():
            self.export_industry.addItem(f"{ind.icon} {ind.name}", ind.id)

        self.export_include_attachments = QCheckBox("包含附件")
        self.export_include_attachments.setChecked(True)

        self.export_desc_input = QLineEdit()
        self.export_desc_input.setPlaceholderText("包描述（可选）")

        export_btn = QPushButton("📦 导出 LTKG 包")
        export_btn.setObjectName("export-btn")
        export_btn.clicked.connect(self._on_export)

        export_options.addWidget(QLabel("范围："))
        export_options.addWidget(self.export_industry)
        export_options.addWidget(self.export_include_attachments)
        export_options.addWidget(self.export_desc_input, 1)
        export_options.addWidget(export_btn)

        export_layout.addLayout(export_options)

        # 导入区域
        import_group = QGroupBox("📥 导入知识包")
        import_layout = QVBoxLayout(import_group)

        import_desc = QLabel("从 .ltkg 包导入知识，支持跳过/合并/覆盖策略")
        import_desc.setStyleSheet("color: #6b6b6b;")
        import_layout.addWidget(import_desc)

        # 导入选项
        import_options = QHBoxLayout()
        import_options.setSpacing(16)

        self.import_file_btn = QPushButton("📂 选择文件...")
        self.import_file_btn.setObjectName("import-file-btn")
        self.import_file_btn.clicked.connect(self._on_select_import_file)

        self.import_file_label = QLabel("未选择文件")
        self.import_file_label.setStyleSheet("color: #6b6b6b;")

        self.import_strategy = QComboBox()
        self.import_strategy.addItem("跳过已存在", "skip_existing")
        self.import_strategy.addItem("合并更新", "merge")
        self.import_strategy.addItem("全部覆盖", "replace")

        import_btn = QPushButton("📥 开始导入")
        import_btn.setObjectName("import-btn")
        import_btn.clicked.connect(self._on_import)

        import_options.addWidget(self.import_file_btn)
        import_options.addWidget(self.import_file_label, 1)
        import_options.addWidget(QLabel("策略："))
        import_options.addWidget(self.import_strategy)
        import_options.addWidget(import_btn)

        import_layout.addLayout(import_options)

        # 进度条
        self.import_progress = QProgressBar()
        self.import_progress.setObjectName("import-progress")
        self.import_progress.hide()

        import_layout.addWidget(self.import_progress)

        # 统计
        stats_group = QGroupBox("📊 知识库统计")
        stats_layout = QGridLayout(stats_group)

        stats = self.grove.get_stats()
        stats_layout.addWidget(QLabel("总条目："), 0, 0)
        stats_layout.addWidget(QLabel(f"<b>{stats.get('total_entries', 0)}</b>"), 0, 1)

        stats_layout.addWidget(QLabel("总查阅："), 0, 2)
        stats_layout.addWidget(QLabel(f"<b>{stats.get('total_usage', 0)}</b>"), 0, 3)

        stats_layout.addWidget(QLabel("按类型："), 1, 0)
        type_str = ", ".join(f"{k}: {v}" for k, v in stats.get('by_type', {}).items())
        stats_layout.addWidget(QLabel(type_str or "无"), 1, 1, 1, 3)

        layout.addWidget(export_group)
        layout.addWidget(import_group)
        layout.addWidget(stats_group)
        layout.addStretch()

        return widget

    def _on_select_import_file(self):
        """选择导入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择LTKG包",
            str(self.grove.archives_dir),
            "LTKG包 (*.ltkg);;所有文件 (*)"
        )
        if file_path:
            self.import_file_label.setText(Path(file_path).name)
            self._selected_import_file = file_path

    def _on_export(self):
        """导出知识包"""
        from .ltkg_handler import get_ltkg_handler

        output_dir = self.grove.archives_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"knowledge_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ltkg"
        output_path = output_dir / filename

        handler = get_ltkg_handler(self.grove)

        industry = self.export_industry.currentData()
        entry_ids = None if industry == "all" else [e.id for e in self.grove.list_entries(industry=industry)]

        result = handler.export_package(
            output_path=output_path,
            entry_ids=entry_ids,
            include_attachments=self.export_include_attachments.isChecked(),
            description=self.export_desc_input.text()
        )

        if result.success:
            QMessageBox.information(self, "导出成功", result.message)
        else:
            QMessageBox.warning(self, "导出失败", result.message)

    def _on_import(self):
        """导入知识包"""
        if not getattr(self, '_selected_import_file', None):
            QMessageBox.warning(self, "请先选择文件", "请选择一个 .ltkg 包文件")
            return

        from .ltkg_handler import get_ltkg_handler, ImportStrategy

        handler = get_ltkg_handler(self.grove)

        strategy_map = {
            "skip_existing": ImportStrategy.SKIP_EXISTING,
            "merge": ImportStrategy.MERGE,
            "replace": ImportStrategy.REPLACE,
        }
        strategy = strategy_map.get(self.import_strategy.currentData(), ImportStrategy.SKIP_EXISTING)

        self.import_progress.show()
        self.import_progress.setValue(0)

        def progress_callback(current, total, message):
            percent = int(current / total * 100) if total > 0 else 0
            self.import_progress.setValue(percent)

        result = handler.import_package(
            self._selected_import_file,
            strategy=strategy,
            progress_callback=progress_callback
        )

        self.import_progress.hide()

        QMessageBox.information(self, "导入完成", result.summary())
        self._refresh_entries()  # 刷新列表
