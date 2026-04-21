"""
Wiki 编译器管理面板 - PyQt6 UI
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QTextEdit, QLineEdit,
    QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter,
    QGroupBox, QFrame, QScrollArea,
    QProgressBar, QStatusBar, QMenuBar, QMenu,
    QDialog, QDialogButtonBox, QComboBox, QCheckBox,
    QSpinBox, QDoubleSpinBox, QTabBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QAction, QIcon, QTextCursor
from PyQt6.QtWidgets import QApplication
from typing import Dict, Any, Optional
import time


class WikiPageCard(QFrame):
    """Wiki页面卡片"""

    def __init__(self, page_data: Dict, parent=None):
        super().__init__(parent)
        self.page_data = page_data
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 标题行
        title_layout = QHBoxLayout()
        title_label = QLabel(self.page_data.get("title", "Untitled"))
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)

        # 类型标签
        page_type = self.page_data.get("page_type", "concept")
        type_label = QLabel(f"[{page_type}]")
        type_label.setStyleSheet("color: #666; font-size: 10px;")
        title_layout.addWidget(type_label)
        title_layout.addStretch()

        # 版本号
        version = self.page_data.get("version", 1)
        version_label = QLabel(f"v{version}")
        version_label.setStyleSheet("color: #888; font-size: 9px;")
        title_layout.addWidget(version_label)

        layout.addLayout(title_layout)

        # 摘要
        summary = self.page_data.get("compiled_truth", {}).get("summary", "")
        if summary:
            summary_label = QLabel(summary[:100] + "..." if len(summary) > 100 else summary)
            summary_label.setWordWrap(True)
            summary_label.setStyleSheet("color: #444; background: #f5f5f5; padding: 8px; border-radius: 4px;")
            layout.addWidget(summary_label)

        # 标签
        tags = self.page_data.get("tags", [])
        if tags:
            tags_layout = QHBoxLayout()
            for tag in tags[:5]:
                tag_label = QLabel(f"#{tag}")
                tag_label.setStyleSheet("color: #0066cc; font-size: 10px;")
                tags_layout.addWidget(tag_label)
            tags_layout.addStretch()
            layout.addLayout(tags_layout)

        # 元信息行
        meta_layout = QHBoxLayout()

        # 证据数量
        evidence_count = len(self.page_data.get("evidence_timeline", []))
        evidence_label = QLabel(f"📅 {evidence_count}条证据")
        evidence_label.setStyleSheet("color: #888; font-size: 10px;")
        meta_layout.addWidget(evidence_label)

        # 置信度
        confidence = self.page_data.get("compiled_truth", {}).get("confidence", 1.0)
        confidence_label = QLabel(f"🎯 {confidence:.0%}")
        confidence_label.setStyleSheet("color: #888; font-size: 10px;")
        meta_layout.addWidget(confidence_label)

        # 最后更新
        last_modified = self.page_data.get("last_modified", time.time())
        time_str = time.strftime("%Y-%m-%d", time.localtime(last_modified))
        time_label = QLabel(f"🕐 {time_str}")
        time_label.setStyleSheet("color: #888; font-size: 10px;")
        meta_layout.addWidget(time_label)

        meta_layout.addStretch()
        layout.addLayout(meta_layout)

        # 设置样式
        self.setStyleSheet("""
            WikiPageCard {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            WikiPageCard:hover {
                border-color: #0066cc;
                background: #fafcff;
            }
        """)


class CompoundingInsightsPanel(QWidget):
    """复利洞察面板"""

    def __init__(self, compounder, parent=None):
        super().__init__(parent)
        self.compounder = compounder
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🧠 复利效应洞察")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 概览卡片
        self.overview_card = QFrame()
        self.overview_card.setStyleSheet("background: #f0f4ff; border-radius: 8px; padding: 12px;")
        overview_layout = QVBoxLayout(self.overview_card)

        self.overview_label = QLabel("加载中...")
        overview_layout.addWidget(self.overview_label)
        layout.addWidget(self.overview_card)

        # 顶级上下文
        contexts_group = QGroupBox("活跃上下文 (Top 5)")
        contexts_layout = QVBoxLayout(contexts_group)

        self.contexts_list = QListWidget()
        contexts_layout.addWidget(self.contexts_list)
        layout.addWidget(contexts_group)

        # 全局洞察
        insights_group = QGroupBox("全局洞察")
        insights_layout = QVBoxLayout(insights_group)

        self.insights_list = QListWidget()
        insights_layout.addWidget(self.insights_list)
        layout.addWidget(insights_group)

        layout.addStretch()

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(refresh_btn)

    def _refresh(self):
        """刷新数据"""
        insights = self.compounder.get_compounding_insights()

        # 更新概览
        overview_text = f"""
        <b>总来源数:</b> {insights.get('source_count', 0)} |
        <b>活跃上下文:</b> {insights.get('active_contexts', 0)} |
        <b>命中率:</b> {insights.get('hit_rate', 0):.1%} |
        <b>平均置信度提升:</b> +{insights.get('avg_confidence_boost', 0):.2f}
        """
        self.overview_label.setText(overview_text)

        # 更新上下文列表
        self.contexts_list.clear()
        for ctx in insights.get("top_contexts", []):
            item_text = f"<b>{ctx['topic']}</b> - 来源:{ctx['source_count']} 置信度:{ctx['confidence']:.0%}"
            self.contexts_list.addItem(item_text)

        # 更新全局洞察
        self.insights_list.clear()
        for insight in insights.get("global_insights", []):
            self.insights_list.addItem(f"• {insight[:60]}...")


class CacheStatsPanel(QWidget):
    """缓存统计面板"""

    def __init__(self, cache, parent=None):
        super().__init__(parent)
        self.cache = cache
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("📦 编译器式缓存")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 统计表格
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(2)
        self.stats_table.setRowCount(12)
        self.stats_table.setHorizontalHeaderLabels(["指标", "数值"])
        self.stats_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.stats_table.verticalHeader().setVisible(False)
        layout.addWidget(self.stats_table)

        # 预编译片段
        chunks_group = QGroupBox("顶级预编译片段 (复利得分)")
        chunks_layout = QVBoxLayout(chunks_group)

        self.chunks_list = QListWidget()
        chunks_layout.addWidget(self.chunks_list)
        layout.addWidget(chunks_group)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(refresh_btn)

    def _refresh(self):
        """刷新数据"""
        stats = self.cache.get_stats()
        compounding = self.cache.get_compounding_insights()

        # 更新统计表格
        row = 0
        for key, value in stats.items():
            if isinstance(value, float):
                self.stats_table.setItem(row, 0, QTableWidgetItem(str(key)))
                self.stats_table.setItem(row, 1, QTableWidgetItem(f"{value:.4f}" if value < 1 else f"{value:.0f}"))
            else:
                self.stats_table.setItem(row, 0, QTableWidgetItem(str(key)))
                self.stats_table.setItem(row, 1, QTableWidgetItem(str(value)))
            row += 1

        # 更新预编译片段
        self.chunks_list.clear()
        for chunk in compounding.get("top_chunks", []):
            item_text = f"<b>{chunk['compounding_score']:.1f}分</b> - {chunk['content']} (使用{chunk['usage_count']}次)"
            self.chunks_list.addItem(item_text)


class WikiBrowserPanel(QWidget):
    """Wiki浏览器面板"""

    pageSelected = pyqtSignal(str)  # page_id

    def __init__(self, compiler, parent=None):
        super().__init__(parent)
        self.compiler = compiler
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 搜索栏
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索 Wiki 页面...")
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_input)

        refresh_btn = QPushButton("🔄")
        refresh_btn.clicked.connect(self._refresh)
        search_layout.addWidget(refresh_btn)

        layout.addLayout(search_layout)

        # 过滤器
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("类型:"))

        self.type_filter = QComboBox()
        self.type_filter.addItems(["全部", "source", "entity", "concept", "topic", "comparison"])
        self.type_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.type_filter)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # 页面列表
        self.pages_list = QListWidget()
        self.pages_list.itemClicked.connect(self._on_page_clicked)
        layout.addWidget(self.pages_list)

    def _refresh(self):
        """刷新页面列表"""
        self.pages_list.clear()

        page_type = self.type_filter.currentText()
        if page_type == "全部":
            pages = self.compiler.get_all_pages()
        else:
            from .models import WikiPageType
            pages = self.compiler.get_all_pages(WikiPageType(page_type))

        for page in pages:
            item = QListWidgetItem()
            page_data = page.to_dict()
            page_data["compiled_truth"] = page.compiled_truth.to_dict()

            card = WikiPageCard(page_data)
            item.setSizeHint(card.sizeHint())
            self.pages_list.addItem(item)
            self.pages_list.setItemWidget(item, card)

    def _on_search(self, text: str):
        """搜索"""
        if not text:
            self._refresh()
            return

        results = self.compiler.search_pages(text)
        self.pages_list.clear()

        for page in results[:20]:
            item = QListWidgetItem()
            page_data = page.to_dict()
            page_data["compiled_truth"] = page.compiled_truth.to_dict()

            card = WikiPageCard(page_data)
            item.setSizeHint(card.sizeHint())
            self.pages_list.addItem(item)
            self.pages_list.setItemWidget(item, card)

    def _on_filter_changed(self, text: str):
        """过滤器变更"""
        self._refresh()

    def _on_page_clicked(self, item: QListWidgetItem):
        """页面点击"""
        widget = self.pages_list.itemWidget(item)
        if widget:
            self.pageSelected.emit(widget.page_data.get("id", ""))


class IngestPanel(QWidget):
    """摄入面板"""

    ingestRequested = pyqtSignal(dict)  # {content, title, type, tags}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("📥 摄入新原材料")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 标题输入
        layout.addWidget(QLabel("标题:"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("输入材料标题...")
        layout.addWidget(self.title_input)

        # 类型选择
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["article", "paper", "pdf", "webpage", "code", "conversation", "api_response"])
        type_layout.addWidget(self.type_combo)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        # 内容输入
        layout.addWidget(QLabel("内容:"))
        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("输入或粘贴原材料内容...")
        self.content_input.setMinimumHeight(200)
        layout.addWidget(self.content_input)

        # 标签
        layout.addWidget(QLabel("标签 (逗号分隔):"))
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("技术, Python, AI ...")
        layout.addWidget(self.tags_input)

        # 来源URL
        layout.addWidget(QLabel("来源URL (可选):"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://...")
        layout.addWidget(self.url_input)

        # 按钮
        btn_layout = QHBoxLayout()
        ingest_btn = QPushButton("🚀 开始摄入")
        ingest_btn.setStyleSheet("""
            QPushButton {
                background: #0066cc;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #0055aa;
            }
        """)
        ingest_btn.clicked.connect(self._on_ingest)
        btn_layout.addWidget(ingest_btn)

        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666; padding: 8px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _on_ingest(self):
        """开始摄入"""
        title = self.title_input.text().strip()
        content = self.content_input.toPlainText().strip()

        if not title or not content:
            self.status_label.setText("⚠️ 标题和内容不能为空")
            return

        tags = [t.strip() for t in self.tags_input.text().split(",") if t.strip()]

        self.ingestRequested.emit({
            "title": title,
            "content": content,
            "material_type": self.type_combo.currentText(),
            "tags": tags,
            "source_url": self.url_input.text().strip()
        })

        self.status_label.setText(f"✅ 已提交摄入请求: {title}")

    def _on_clear(self):
        """清空"""
        self.title_input.clear()
        self.content_input.clear()
        self.tags_input.clear()
        self.url_input.clear()
        self.status_label.clear()


class QueryPanel(QWidget):
    """查询面板"""

    def __init__(self, compiler, parent=None):
        super().__init__(parent)
        self.compiler = compiler
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🔍 Wiki 查询")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 查询输入
        self.query_input = QTextEdit()
        self.query_input.setPlaceholderText("输入你的问题...")
        self.query_input.setMaximumHeight(100)
        layout.addWidget(self.query_input)

        # 选项
        options_layout = QHBoxLayout()
        self.use_cache_cb = QCheckBox("使用缓存")
        self.use_cache_cb.setChecked(True)
        options_layout.addWidget(self.use_cache_cb)

        self.use_compounding_cb = QCheckBox("使用复利上下文")
        self.use_compounding_cb.setChecked(True)
        options_layout.addWidget(self.use_compounding_cb)

        options_layout.addStretch()
        layout.addLayout(options_layout)

        # 查询按钮
        query_btn = QPushButton("🔍 查询")
        query_btn.setStyleSheet("""
            QPushButton {
                background: #00aa55;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #008844;
            }
        """)
        query_btn.clicked.connect(self._on_query)
        layout.addWidget(query_btn)

        # 结果区域
        result_group = QGroupBox("查询结果")
        result_layout = QVBoxLayout(result_group)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        result_layout.addWidget(self.result_text)

        layout.addWidget(result_group)

        # 引用页面
        refs_group = QGroupBox("引用的页面")
        refs_layout = QVBoxLayout(refs_group)

        self.refs_list = QListWidget()
        refs_layout.addWidget(self.refs_list)
        layout.addWidget(refs_group)

    def _on_query(self):
        """执行查询"""
        query = self.query_input.toPlainText().strip()
        if not query:
            return

        use_cache = self.use_cache_cb.isChecked()
        use_compounding = self.use_compounding_cb.isChecked()

        answer = self.compiler.query(
            query_text=query,
            use_cache=use_cache,
            use_compounding=use_compounding
        )

        # 显示结果
        result_text = f"""
<h3>答案 (置信度: {answer.confidence:.0%})</h3>
<hr>
{answer.answer}
"""
        if answer.reasoning_chain:
            result_text += "<h4>推理链:</h4><ul>"
            for step in answer.reasoning_chain:
                result_text += f"<li>{step}</li>"
            result_text += "</ul>"

        self.result_text.setHtml(result_text)

        # 显示引用
        self.refs_list.clear()
        for page_id in answer.referenced_pages:
            page = self.compiler.get_page(page_id)
            if page:
                self.refs_list.addItem(f"📄 {page.title} ({page.page_type.value})")


class WikiCompilerPanel(QWidget):
    """
    Wiki 编译器管理面板 - 主面板
    """

    def __init__(self, compiler=None, parent=None):
        super().__init__(parent)
        self.compiler = compiler
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 标签页
        self.tabs = QTabWidget()

        # Wiki 浏览器
        self.browser_tab = WikiBrowserPanel(self.compiler)
        self.tabs.addTab(self.browser_tab, "📚 Wiki 浏览器")

        # 查询
        self.query_tab = QueryPanel(self.compiler)
        self.tabs.addTab(self.query_tab, "🔍 查询")

        # 摄入
        self.ingest_tab = IngestPanel()
        self.tabs.addTab(self.ingest_tab, "📥 摄入")

        # 缓存统计
        self.cache_tab = CacheStatsPanel(self.compiler.cache)
        self.tabs.addTab(self.cache_tab, "📦 缓存")

        # 复利洞察
        self.compounding_tab = CompoundingInsightsPanel(self.compiler.compounder)
        self.tabs.addTab(self.compounding_tab, "🧠 复利")

        # Check 结果
        self.check_tab = QWidget()
        self._init_check_tab()
        self.tabs.addTab(self.check_tab, "✅ 检查")

        layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        self._update_status()
        layout.addWidget(self.status_bar)

        # 定时刷新
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_status)
        self.timer.start(5000)

    def _init_check_tab(self):
        """初始化检查标签页"""
        layout = QVBoxLayout(self.check_tab)

        # 标题
        title = QLabel("✅ Wiki 一致性检查")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # 检查按钮
        check_btn = QPushButton("🔍 运行检查")
        check_btn.clicked.connect(self._run_check)
        layout.addWidget(check_btn)

        # 结果表格
        self.check_table = QTableWidget()
        self.check_table.setColumnCount(3)
        self.check_table.setHorizontalHeaderLabels(["类型", "详情", "建议"])
        self.check_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.check_table)

        # 建议列表
        suggestions_group = QGroupBox("建议")
        suggestions_layout = QVBoxLayout(suggestions_group)

        self.suggestions_list = QListWidget()
        suggestions_layout.addWidget(self.suggestions_list)
        layout.addWidget(suggestions_group)

    def _run_check(self):
        """运行检查"""
        result = self.compiler.check()

        # 更新表格
        self.check_table.setRowCount(0)

        for item in result.contradictions:
            self._add_check_row("⚠️ 矛盾", f"{item['title']}", "检查页面内容是否过时")
        for item in result.outdated_pages:
            self._add_check_row("⏰ 过时", f"{item['title']} ({item['days_ago']}天)", "考虑更新内容")
        for item in result.orphan_pages:
            self._add_check_row("🔗 孤立", f"{item['title']}", "添加相关链接")
        for item in result.missing_links[:10]:
            self._add_check_row("📎 缺失链接", f"{item['from_title']} → {item['to_title']}", item['suggestion'])

        # 更新建议
        self.suggestions_list.clear()
        for suggestion in result.suggestions:
            self.suggestions_list.addItem(suggestion)

    def _add_check_row(self, type_: str, detail: str, suggestion: str):
        """添加检查结果行"""
        row = self.check_table.rowCount()
        self.check_table.insertRow(row)
        self.check_table.setItem(row, 0, QTableWidgetItem(type_))
        self.check_table.setItem(row, 1, QTableWidgetItem(detail))
        self.check_table.setItem(row, 2, QTableWidgetItem(suggestion))

    def _update_status(self):
        """更新状态栏"""
        if not self.compiler:
            return

        stats = self.compiler.get_stats()
        status_text = (
            f"📚 页面: {stats['wiki_pages']} | "
            f"📦 缓存命中: {stats['cache_stats'].get('cache_hit_rate', 0):.1%} | "
            f"🧠 复利率: {stats['compounding_stats'].get('hit_rate', 0):.1%} | "
            f"⏱️ 平均查询: {stats['avg_query_time']:.3f}s"
        )
        self.status_bar.showMessage(status_text)

    def refresh(self):
        """刷新面板"""
        self.browser_tab._refresh()
        self.cache_tab._refresh()
        self.compounding_tab._refresh()
        self._update_status()
