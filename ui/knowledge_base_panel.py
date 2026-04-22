"""
现代化 AI 知识库面板
===================

功能特性：
- AI 智能搜索（融合 RAG + 知识图谱推理）
- 快速查找与极速推理
- 知识聚合与智能分类
- 文档管理与标签系统
- 知识图谱可视化

Author: Hermes Desktop Team
Date: 2026-04-22
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSplitter, QTreeWidget, QTreeWidgetItem,
    QListWidget, QListWidgetItem, QTextEdit, QTabWidget,
    QGroupBox, QComboBox, QSpinBox, QFileDialog, QMessageBox,
    QScrollArea, QFrame, QStackedWidget, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtGui import QFont, QIcon, QColor, QTextCharFormat

logger = logging.getLogger(__name__)

# 样式常量
STYLE_SEARCH_INPUT = """
    QLineEdit {
        padding: 12px 16px;
        border: 2px solid #e0e0e0;
        border-radius: 8px;
        font-size: 14px;
        background: white;
    }
    QLineEdit:focus {
        border: 2px solid #1976D2;
    }
"""

STYLE_PRIMARY_BTN = """
    QPushButton {
        background: #1976D2;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton:hover {
        background: #1565C0;
    }
    QPushButton:pressed {
        background: #0D47A1;
    }
"""

STYLE_SECONDARY_BTN = """
    QPushButton {
        background: white;
        color: #1976D2;
        border: 2px solid #1976D2;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton:hover {
        background: #E3F2FD;
    }
"""

STYLE_CARD = """
    QFrame {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }
"""

STYLE_TREE = """
    QTreeWidget {
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        background: white;
    }
    QTreeWidget::item {
        padding: 8px;
    }
    QTreeWidget::item:selected {
        background: #E3F2FD;
        color: #1976D2;
    }
"""


class KnowledgeBasePanel(QWidget):
    """现代化 AI 知识库面板"""

    # 信号定义
    search_completed = pyqtSignal(list)
    document_selected = pyqtSignal(str)
    knowledge_aggregated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_state()
        self._init_ui()
        self._load_sample_data()

    def _init_state(self):
        """初始化状态"""
        # 知识库数据
        self.documents: Dict[str, Dict] = {}
        self.tags: Dict[str, List[str]] = {}  # doc_id -> tags
        self.search_history: List[Dict] = []
        self.recent_documents: List[str] = []

        # AI 模块（延迟加载）
        self.fusion_rag = None
        self.knowledge_graph_manager = None
        self.embedding_model = None

        # UI 状态
        self.current_view = "search"  # search, browse, aggregate, graph
        self.selected_doc_id: Optional[str] = None

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 顶部搜索区
        self._setup_search_area(layout)

        # 主内容区（使用分割器）
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)

        # 左侧面板
        left_panel = self._create_left_panel()
        main_splitter.addWidget(left_panel)

        # 右侧面板
        right_panel = self._create_right_panel()
        main_splitter.addWidget(right_panel)

        layout.addWidget(main_splitter)

        # 底部状态栏
        self._setup_status_bar(layout)

    def _setup_search_area(self, parent_layout: QVBoxLayout):
        """设置顶部搜索区"""
        search_frame = QFrame()
        search_frame.setStyleSheet(STYLE_CARD)
        search_layout = QVBoxLayout(search_frame)
        search_layout.setContentsMargins(16, 16, 16, 16)
        search_layout.setSpacing(12)

        # 标题
        title_label = QLabel("📚 AI 知识库")
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        search_layout.addWidget(title_label)

        # 搜索框
        search_input_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入关键词进行 AI 智能搜索...")
        self.search_input.setStyleSheet(STYLE_SEARCH_INPUT)
        self.search_input.returnPressed.connect(self._on_ai_search)
        search_input_layout.addWidget(self.search_input)

        # 搜索按钮
        self.search_btn = QPushButton("🔍 AI 搜索")
        self.search_btn.setStyleSheet(STYLE_PRIMARY_BTN)
        self.search_btn.setMinimumWidth(120)
        self.search_btn.clicked.connect(self._on_ai_search)
        search_input_layout.addWidget(self.search_btn)

        search_layout.addLayout(search_input_layout)

        # 搜索选项
        options_layout = QHBoxLayout()
        options_layout.setSpacing(16)

        # 搜索类型
        QLabel("搜索类型:").setStyleSheet("font-size: 13px;")
        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems(["智能搜索", "语义搜索", "关键词搜索", "图谱推理"])
        self.search_type_combo.setStyleSheet("""
            QComboBox {
                padding: 6px;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        options_layout.addWidget(QLabel("搜索类型:"))
        options_layout.addWidget(self.search_type_combo)

        # 返回结果数
        options_layout.addWidget(QLabel("结果数:"))
        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(1, 50)
        self.top_k_spin.setValue(10)
        self.top_k_spin.setStyleSheet("""
            QSpinBox {
                padding: 6px;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
        """)
        options_layout.addWidget(self.top_k_spin)

        options_layout.addStretch()
        search_layout.addLayout(options_layout)

        parent_layout.addWidget(search_frame)

    def _create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        # 功能选项卡
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
            }
            QTabBar::tab {
                padding: 8px 12px;
                border: 1px solid #e0e0e0;
                border-radius: 4px 4px 0 0;
                background: #f5f5f5;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom-color: white;
            }
        """)

        # 文档树标签
        self.doc_tree_tab = self._create_doc_tree_tab()
        self.tab_widget.addTab(self.doc_tree_tab, "📁 文档")

        # 标签云标签
        self.tag_cloud_tab = self._create_tag_cloud_tab()
        self.tab_widget.addTab(self.tag_cloud_tab, "🏷️ 标签")

        # 最近文档标签
        self.recent_tab = self._create_recent_tab()
        self.tab_widget.addTab(self.recent_tab, "🕒 最近")

        left_layout.addWidget(self.tab_widget)

        return left_widget

    def _create_doc_tree_tab(self) -> QWidget:
        """创建文档树标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 工具栏
        toolbar_layout = QHBoxLayout()
        add_doc_btn = QPushButton("➕ 添加文档")
        add_doc_btn.setStyleSheet(STYLE_PRIMARY_BTN)
        add_doc_btn.clicked.connect(self._on_add_document)
        toolbar_layout.addWidget(add_doc_btn)

        add_folder_btn = QPushButton("📁 新建文件夹")
        add_folder_btn.setStyleSheet(STYLE_SECONDARY_BTN)
        add_folder_btn.clicked.connect(self._on_add_folder)
        toolbar_layout.addWidget(add_folder_btn)

        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        # 文档树
        self.doc_tree = QTreeWidget()
        self.doc_tree.setHeaderLabels(["名称", "类型", "更新时间"])
        self.doc_tree.setStyleSheet(STYLE_TREE)
        self.doc_tree.setColumnWidth(0, 200)
        self.doc_tree.setColumnWidth(1, 80)
        self.doc_tree.itemClicked.connect(self._on_doc_selected)
        layout.addWidget(self.doc_tree)

        return widget

    def _create_tag_cloud_tab(self) -> QWidget:
        """创建标签云标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 标签列表
        self.tag_list = QListWidget()
        self.tag_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background: #E3F2FD;
                color: #1976D2;
            }
        """)
        self.tag_list.itemClicked.connect(self._on_tag_clicked)
        layout.addWidget(self.tag_list)

        # 添加标签按钮
        add_tag_btn = QPushButton("➕ 新建标签")
        add_tag_btn.setStyleSheet(STYLE_SECONDARY_BTN)
        add_tag_btn.clicked.connect(self._on_add_tag)
        layout.addWidget(add_tag_btn)

        return widget

    def _create_recent_tab(self) -> QWidget:
        """创建最近文档标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.recent_list = QListWidget()
        self.recent_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background: #E3F2FD;
                color: #1976D2;
            }
        """)
        self.recent_list.itemClicked.connect(self._on_recent_clicked)
        layout.addWidget(self.recent_list)

        return widget

    def _create_right_panel(self) -> QWidget:
        """创建右侧面板"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # 内容堆栈（用于切换不同视图）
        self.content_stack = QStackedWidget()

        # 搜索结果视图
        self.search_results_view = self._create_search_results_view()
        self.content_stack.addWidget(self.search_results_view)

        # 知识聚合视图
        self.aggregate_view = self._create_aggregate_view()
        self.content_stack.addWidget(self.aggregate_view)

        # 知识图谱视图
        self.graph_view = self._create_graph_view()
        self.content_stack.addWidget(self.graph_view)

        right_layout.addWidget(self.content_stack)

        return right_widget

    def _create_search_results_view(self) -> QWidget:
        """创建搜索结果视图"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 搜索统计
        stats_layout = QHBoxLayout()
        self.results_count_label = QLabel("找到 0 条结果")
        self.results_count_label.setStyleSheet("font-size: 13px; color: #666;")
        stats_layout.addWidget(self.results_count_label)

        self.search_time_label = QLabel("耗时: 0ms")
        self.search_time_label.setStyleSheet("font-size: 13px; color: #666;")
        stats_layout.addWidget(self.search_time_label)

        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # 结果列表
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["标题", "类型", "相关度", "更新时间"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background: white;
                gridline-color: #f0f0f0;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background: #E3F2FD;
                color: #1976D2;
            }
            QHeaderView::section {
                background: #f5f5f5;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        self.results_table.cellClicked.connect(self._on_result_selected)
        layout.addWidget(self.results_table)

        # 文档详情区
        self.doc_detail_group = QGroupBox("📄 文档详情")
        self.doc_detail_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 12px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
        """)
        detail_layout = QVBoxLayout()

        self.doc_title_label = QLabel("选择文档查看详情")
        self.doc_title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        detail_layout.addWidget(self.doc_title_label)

        self.doc_content_edit = QTextEdit()
        self.doc_content_edit.setReadOnly(True)
        self.doc_content_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 12px;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        detail_layout.addWidget(self.doc_content_edit)

        self.doc_detail_group.setLayout(detail_layout)
        layout.addWidget(self.doc_detail_group)

        return widget

    def _create_aggregate_view(self) -> QWidget:
        """创建知识聚合视图"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 聚合标题
        title_label = QLabel("🔗 知识聚合")
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 聚合类型选择
        agg_type_layout = QHBoxLayout()
        agg_type_layout.addWidget(QLabel("聚合方式:"))
        self.agg_type_combo = QComboBox()
        self.agg_type_combo.addItems(["智能聚合", "主题聚合", "时间聚合", "标签聚合"])
        agg_type_layout.addWidget(self.agg_type_combo)
        agg_type_layout.addStretch()
        layout.addLayout(agg_type_layout)

        # 聚合结果区
        self.agg_results_scroll = QScrollArea()
        self.agg_results_scroll.setWidgetResizable(True)
        self.agg_results_content = QWidget()
        self.agg_results_layout = QVBoxLayout(self.agg_results_content)
        self.agg_results_layout.setSpacing(12)
        self.agg_results_layout.addStretch()
        self.agg_results_scroll.setWidget(self.agg_results_content)
        layout.addWidget(self.agg_results_scroll)

        return widget

    def _create_graph_view(self) -> QWidget:
        """创建知识图谱视图"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 图谱标题
        title_label = QLabel("🌐 知识图谱")
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 图谱占位区（后续可集成 pygraphviz 或 networkx）
        self.graph_placeholder = QLabel("知识图谱可视化功能开发中...")
        self.graph_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.graph_placeholder.setStyleSheet("""
            QLabel {
                background: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 8px;
                padding: 40px;
                font-size: 16px;
                color: #999;
            }
        """)
        layout.addWidget(self.graph_placeholder)

        return widget

    def _setup_status_bar(self, parent_layout: QVBoxLayout):
        """设置底部状态栏"""
        status_frame = QFrame()
        status_frame.setStyleSheet("background: #f5f5f5; border-radius: 6px;")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(12, 8, 12, 8)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("font-size: 12px; color: #666;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.doc_count_label = QLabel("文档: 0")
        status_layout.addWidget(self.doc_count_label)

        self.tag_count_label = QLabel("标签: 0")
        status_layout.addWidget(self.tag_count_label)

        parent_layout.addWidget(status_frame)

    # ─── 事件处理 ──────────────────────────────────

    def _on_ai_search(self):
        """执行 AI 智能搜索"""
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, "提示", "请输入搜索关键词")
            return

        # 切换到搜索结果视图
        self.content_stack.setCurrentWidget(self.search_results_view)

        # 显示搜索中状态
        self._set_status(f"🔍 正在搜索: {query}...")

        # 记录搜索历史
        self.search_history.append({
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "type": self.search_type_combo.currentText(),
        })

        # 异步执行搜索
        start_time = time.time()
        results = self._perform_ai_search(query)
        elapsed_ms = int((time.time() - start_time) * 1000)

        # 更新 UI
        self._update_search_results(results, elapsed_ms)
        self._set_status(f"✅ 搜索完成: {len(results)} 条结果，耗时 {elapsed_ms}ms")

    def _perform_ai_search(self, query: str) -> List[Dict]:
        """执行 AI 搜索（融合 RAG + 知识图谱推理）"""
        results = []
        search_type = self.search_type_combo.currentText()
        top_k = self.top_k_spin.value()

        try:
            # 1. 向量语义搜索（如果 fusion_rag 可用）
            if self.fusion_rag:
                vector_results = self.fusion_rag.hybrid_search(query, top_k=top_k)
                results.extend(vector_results)

            # 2. 知识图谱推理搜索
            if self.knowledge_graph_manager:
                kg_results = self._search_knowledge_graph(query, top_k)
                results.extend(kg_results)

            # 3. 如果 AI 模块不可用，使用本地搜索
            if not results:
                results = self._local_search(query, top_k)

        except Exception as e:
            logger.error(f"AI 搜索失败: {e}")
            results = self._local_search(query, top_k)

        return results[:top_k]

    def _local_search(self, query: str, top_k: int) -> List[Dict]:
        """本地搜索（降级方案）"""
        results = []
        query_lower = query.lower()

        for doc_id, doc in self.documents.items():
            score = 0.0

            # 标题匹配
            if query_lower in doc.get("title", "").lower():
                score += 10.0

            # 内容匹配
            content = doc.get("content", "").lower()
            if query_lower in content:
                score += 5.0
                # 根据出现次数加分
                score += content.count(query_lower) * 0.5

            # 标签匹配
            doc_tags = self.tags.get(doc_id, [])
            if any(query_lower in tag.lower() for tag in doc_tags):
                score += 3.0

            if score > 0:
                results.append({
                    "doc_id": doc_id,
                    "title": doc.get("title", ""),
                    "type": doc.get("type", "文档"),
                    "score": score,
                    "updated_at": doc.get("updated_at", ""),
                    "content": doc.get("content", ""),
                    "tags": doc_tags,
                })

        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _search_knowledge_graph(self, query: str, top_k: int) -> List[Dict]:
        """知识图谱推理搜索"""
        results = []
        try:
            # 在知识图谱中搜索相关实体
            if self.knowledge_graph_manager.current_kg:
                kg = self.knowledge_graph_manager.current_kg

                # 搜索匹配的实体
                entities = kg.search_entities_by_name(query)
                for entity in entities[:top_k]:
                    results.append({
                        "doc_id": f"kg_entity_{entity.id}",
                        "title": f"实体: {entity.name}",
                        "type": "知识图谱实体",
                        "score": 8.0,
                        "updated_at": "",
                        "content": f"实体描述: {entity.description or '无'}",
                        "tags": [entity.entity_type.value],
                    })

        except Exception as e:
            logger.error(f"知识图谱搜索失败: {e}")

        return results

    def _update_search_results(self, results: List[Dict], elapsed_ms: int):
        """更新搜索结果 UI"""
        self.results_table.setRowCount(0)

        for i, result in enumerate(results):
            self.results_table.insertRow(i)

            # 标题
            title_item = QTableWidgetItem(result.get("title", ""))
            self.results_table.setItem(i, 0, title_item)

            # 类型
            type_item = QTableWidgetItem(result.get("type", ""))
            self.results_table.setItem(i, 1, type_item)

            # 相关度
            score = result.get("score", 0)
            score_text = f"{score:.1f}"
            score_item = QTableWidgetItem(score_text)
            # 根据分数设置颜色
            if score >= 8.0:
                score_item.setForeground(QColor("#4CAF50"))
            elif score >= 5.0:
                score_item.setForeground(QColor("#FF9800"))
            else:
                score_item.setForeground(QColor("#999999"))
            self.results_table.setItem(i, 2, score_item)

            # 更新时间
            updated_item = QTableWidgetItem(result.get("updated_at", ""))
            self.results_table.setItem(i, 3, updated_item)

        # 更新统计
        self.results_count_label.setText(f"找到 {len(results)} 条结果")
        self.search_time_label.setText(f"耗时: {elapsed_ms}ms")

        # 发送信号
        self.search_completed.emit(results)

    def _on_result_selected(self, row: int, col: int):
        """选择搜索结果"""
        doc_id = self.results_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if not doc_id:
            # 尝试从文档列表查找
            title = self.results_table.item(row, 0).text()
            for d_id, doc in self.documents.items():
                if doc.get("title") == title:
                    doc_id = d_id
                    break

        if doc_id and doc_id in self.documents:
            self._display_document(doc_id)
            self.document_selected.emit(doc_id)

    def _on_doc_selected(self, item: QTreeWidgetItem, column: int):
        """选择文档树中的文档"""
        doc_id = item.data(0, Qt.ItemDataRole.UserRole)
        if doc_id and doc_id in self.documents:
            self._display_document(doc_id)
            self.document_selected.emit(doc_id)

    def _on_tag_clicked(self, item: QListWidgetItem):
        """点击标签"""
        tag = item.text()
        if tag:
            self.search_input.setText(f"tag:{tag}")
            self._on_ai_search()

    def _on_recent_clicked(self, item: QListWidgetItem):
        """点击最近文档"""
        doc_id = item.data(Qt.ItemDataRole.UserRole)
        if doc_id and doc_id in self.documents:
            self._display_document(doc_id)

    def _on_add_document(self):
        """添加文档"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文档",
            "",
            "文本文档 (*.txt *.md);;所有文件 (*)"
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                doc_id = f"doc_{int(time.time())}"
                self.documents[doc_id] = {
                    "title": Path(file_path).stem,
                    "content": content,
                    "type": "文本",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "source": file_path,
                }

                self._refresh_doc_tree()
                self._update_status_counts()
                self._set_status(f"✅ 已添加文档: {Path(file_path).name}")
            except Exception as e:
                logger.error(f"添加文档失败: {e}")
                QMessageBox.critical(self, "错误", f"添加文档失败:\n{str(e)}")

    def _on_add_folder(self):
        """添加文件夹"""
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder_path:
            self._set_status(f"📁 正在扫描文件夹: {folder_path}")
            # TODO: 实现递归扫描文件夹
            QMessageBox.information(self, "提示", "文件夹扫描功能开发中...")

    def _on_add_tag(self):
        """添加标签"""
        from PyQt6.QtWidgets import QInputDialog

        tag, ok = QInputDialog.getText(self, "新建标签", "标签名称:")
        if ok and tag:
            self._add_tag_to_system(tag)
            self._refresh_tag_list()

    # ─── UI 辅助方法 ──────────────────────────────────

    def _display_document(self, doc_id: str):
        """显示文档详情"""
        if doc_id not in self.documents:
            return

        doc = self.documents[doc_id]
        self.selected_doc_id = doc_id

        # 更新详情区
        self.doc_title_label.setText(doc.get("title", "无标题"))
        self.doc_content_edit.setPlainText(doc.get("content", ""))

        # 切换到搜索结果视图（查看详情）
        self.content_stack.setCurrentWidget(self.search_results_view)

        # 添加到最近文档
        if doc_id not in self.recent_documents:
            self.recent_documents.insert(0, doc_id)
            self.recent_documents = self.recent_documents[:20]  # 保留最近 20 个
            self._refresh_recent_list()

    def _refresh_doc_tree(self):
        """刷新文档树"""
        self.doc_tree.clear()

        # 按类型分组
        type_groups: Dict[str, List[str]] = {}
        for doc_id, doc in self.documents.items():
            doc_type = doc.get("type", "其他")
            if doc_type not in type_groups:
                type_groups[doc_type] = []
            type_groups[doc_type].append(doc_id)

        # 添加节点
        for doc_type, doc_ids in type_groups.items():
            type_item = QTreeWidgetItem([f"📁 {doc_type}", doc_type, ""])
            type_item.setExpanded(True)

            for doc_id in doc_ids:
                doc = self.documents[doc_id]
                doc_item = QTreeWidgetItem([
                    doc.get("title", ""),
                    doc.get("type", ""),
                    doc.get("updated_at", ""),
                ])
                doc_item.setData(0, Qt.ItemDataRole.UserRole, doc_id)
                type_item.addChild(doc_item)

            self.doc_tree.addTopLevelItem(type_item)

    def _refresh_tag_list(self):
        """刷新标签列表"""
        self.tag_list.clear()

        # 统计标签频率
        tag_counts: Dict[str, int] = {}
        for doc_id, tags in self.tags.items():
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # 按频率排序
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        for tag, count in sorted_tags:
            item = QListWidgetItem(f"{tag} ({count})")
            item.setData(Qt.ItemDataRole.UserRole, tag)
            self.tag_list.addItem(item)

        # 更新状态栏
        self.tag_count_label.setText(f"标签: {len(tag_counts)}")

    def _refresh_recent_list(self):
        """刷新最近文档列表"""
        self.recent_list.clear()

        for doc_id in self.recent_documents[:10]:
            if doc_id in self.documents:
                doc = self.documents[doc_id]
                item = QListWidgetItem(f"📄 {doc.get('title', '')}")
                item.setData(Qt.ItemDataRole.UserRole, doc_id)
                self.recent_list.addItem(item)

    def _update_status_counts(self):
        """更新状态栏计数"""
        self.doc_count_label.setText(f"文档: {len(self.documents)}")
        self._refresh_tag_list()

    def _set_status(self, message: str):
        """设置状态栏消息"""
        self.status_label.setText(message)

    def _add_tag_to_system(self, tag: str):
        """添加标签到系统"""
        if self.selected_doc_id:
            if self.selected_doc_id not in self.tags:
                self.tags[self.selected_doc_id] = []
            if tag not in self.tags[self.selected_doc_id]:
                self.tags[self.selected_doc_id].append(tag)
                self._refresh_tag_list()

    # ─── 示例数据 ──────────────────────────────────

    def _load_sample_data(self):
        """加载示例数据"""
        sample_docs = [
            {
                "title": "AI 知识库系统设计文档",
                "content": "本文档介绍了 AI 知识库系统的整体架构设计...\n\n1. 系统概述\n2. 功能模块\n3. 技术选型\n4. 部署方案",
                "type": "技术文档",
                "tags": ["AI", "知识库", "系统设计"],
            },
            {
                "title": "融合 RAG 检索技术指南",
                "content": "融合 RAG（Retrieval-Augmented Generation）是一种结合向量检索和生成模型的技术...\n\n核心组件：\n- 向量索引\n- BM25 关键词检索\n- 重排序模型",
                "type": "技术文档",
                "tags": ["RAG", "检索", "AI"],
            },
            {
                "title": "知识图谱构建教程",
                "content": "知识图谱（Knowledge Graph）是一种结构化的知识表示形式...\n\n构建步骤：\n1. 实体识别\n2. 关系抽取\n3. 知识融合\n4. 存储与查询",
                "type": "教程",
                "tags": ["知识图谱", "NLP", "教程"],
            },
            {
                "title": "企业数字化转型报告",
                "content": "企业数字化转型是当今企业发展的重要趋势...\n\n关键领域：\n- 业务流程数字化\n- 数据驱动决策\n- AI 赋能",
                "type": "报告",
                "tags": ["数字化", "企业", "报告"],
            },
            {
                "title": "Python 异步编程最佳实践",
                "content": "异步编程是现代 Python 开发的重要技能...\n\n核心概念：\n- asyncio\n- async/await\n- 事件循环\n- 并发控制",
                "type": "教程",
                "tags": ["Python", "异步编程", "教程"],
            },
        ]

        for doc_data in sample_docs:
            doc_id = f"doc_{int(time.time())}_{len(self.documents)}"
            self.documents[doc_id] = {
                "title": doc_data["title"],
                "content": doc_data["content"],
                "type": doc_data["type"],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            self.tags[doc_id] = doc_data.get("tags", [])

        # 刷新 UI
        self._refresh_doc_tree()
        self._refresh_tag_list()
        self._refresh_recent_list()
        self._update_status_counts()

    # ─── AI 模块初始化 ──────────────────────────────────

    def init_ai_modules(self):
        """初始化 AI 模块（延迟加载）"""
        try:
            # 初始化 Fusion RAG
            from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
            self.fusion_rag = KnowledgeBaseLayer(
                embedding_model="BAAI/bge-small-zh",
                top_k=10,
                chunk_size=512,
                chunk_overlap=64,
            )

            # 初始化知识图谱管理器
            from core.knowledge_graph.knowledge_graph_manager import KnowledgeGraphManager
            self.knowledge_graph_manager = KnowledgeGraphManager()
            self.knowledge_graph_manager.create_empty_graph("knowledge_base_graph")

            # 导入现有文档到 Fusion RAG
            self._sync_documents_to_rag()

            self._set_status("✅ AI 模块初始化成功")
        except ImportError as e:
            logger.warning(f"AI 模块导入失败: {e}")
            self._set_status("⚠️ AI 模块不可用，使用本地搜索")
        except Exception as e:
            logger.error(f"AI 模块初始化失败: {e}")
            self._set_status(f"❌ AI 模块初始化失败: {e}")

    def _sync_documents_to_rag(self):
        """同步文档到 Fusion RAG"""
        if not self.fusion_rag:
            return

        for doc_id, doc in self.documents.items():
            try:
                self.fusion_rag.add_document({
                    "id": doc_id,
                    "title": doc.get("title", ""),
                    "content": doc.get("content", ""),
                    "metadata": {
                        "type": doc.get("type", ""),
                        "tags": self.tags.get(doc_id, []),
                        "created_at": doc.get("created_at", ""),
                    }
                })
            except Exception as e:
                logger.warning(f"同步文档到 RAG 失败: {doc_id}, 错误: {e}")
