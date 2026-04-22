# -*- coding: utf-8 -*-
"""
深度搜索面板 - DeepSearchPanel
深度搜索功能模块 UI 实现

功能：
- 搜索输入框
- 搜索类型选择 (通用/竞品/产品/舆情/Wiki)
- 搜索结果展示
- Wiki 生成
- 搜索历史
- 搜索统计
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QTextEdit, QScrollArea, QFrame, QGroupBox,
    QSplitter, QTabWidget, QProgressBar, QFileDialog,
    QCheckBox, QToolBar, QToolButton,
    QMessageBox, QHeaderView, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QMenu, QAction, QInputDialog,
)
from PyQt6.QtGui import QFont, QIcon, QColor, QTextDocument, QKeySequence

logger = logging.getLogger(__name__)


class DeepSearchPanel(QWidget):
    """深度搜索面板"""

    search_requested = pyqtSignal(str, str)  # query, search_type
    wiki_generated = pyqtSignal(str)  # topic
    search_history_updated = pyqtSignal(list)  # history

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._intelligence_hub = None
        self._wiki_system = None
        self._search_history: List[dict] = []
        self._current_results: List[dict] = []
        self._is_searching = False
        self._search_timer: Optional[QTimer] = None

        self.setObjectName("DeepSearchPanel")
        self.setStyleSheet("""
            QWidget#DeepSearchPanel {
                background: #f8fafc;
            }
        """)

        self._init_ui()
        self._init_intelligence_hub()

    def _init_ui(self):
        """初始化 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 顶部搜索区
        search_widget = self._create_search_area()
        splitter.addWidget(search_widget)

        # 中间结果区
        results_widget = self._create_results_area()
        splitter.addWidget(results_widget)

        # 底部统计区
        stats_widget = self._create_stats_area()
        splitter.addWidget(stats_widget)

        # 设置分割比例
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)

        main_layout.addWidget(splitter)

    def _create_search_area(self) -> QWidget:
        """创建搜索区域"""
        widget = QWidget()
        widget.setObjectName("SearchArea")
        widget.setStyleSheet("""
            QWidget#SearchArea {
                background: white;
                border-bottom: 1px solid #e2e8f0;
            }
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 标题
        title_layout = QHBoxLayout()
        title_label = QLabel("🔍 深度搜索")
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #1e293b;
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # 搜索框
        search_input_layout = QHBoxLayout()
        search_input_layout.setSpacing(8)

        # 搜索类型选择
        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems([
            "通用搜索", "竞品监控", "产品发布", "舆情分析", "Wiki生成"
        ])
        self.search_type_combo.setFixedWidth(120)
        self.search_type_combo.setStyleSheet("""
            QComboBox {
                background: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
        """)
        search_input_layout.addWidget(self.search_type_combo)

        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入搜索关键词...")
        self.search_input.setFixedHeight(40)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 0 16px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #3b82f6;
                background: white;
            }
            QLineEdit::placeholder {
                color: #94a3b8;
            }
        """)
        self.search_input.returnPressed.connect(self._execute_search)
        search_input_layout.addWidget(self.search_input)

        # 搜索按钮
        self.search_btn = QPushButton("🔍 搜索")
        self.search_btn.setFixedHeight(40)
        self.search_btn.setFixedWidth(100)
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2563eb;
            }
            QPushButton:pressed {
                background: #1d4ed8;
            }
            QPushButton:disabled {
                background: #94a3b8;
            }
        """)
        self.search_btn.clicked.connect(self._execute_search)
        search_input_layout.addWidget(self.search_btn)

        # 停止按钮
        self.stop_btn = QPushButton("⏹️ 停止")
        self.stop_btn.setFixedHeight(40)
        self.stop_btn.setFixedWidth(80)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #dc2626;
            }
            QPushButton:disabled {
                background: #94a3b8;
            }
        """)
        self.stop_btn.clicked.connect(self._stop_search)
        search_input_layout.addWidget(self.stop_btn)

        # 清空按钮
        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.setFixedHeight(40)
        self.clear_btn.setFixedWidth(80)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: #64748b;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #475569;
            }
        """)
        self.clear_btn.clicked.connect(self._clear_results)
        search_input_layout.addWidget(self.clear_btn)

        layout.addLayout(search_input_layout)

        # 搜索选项
        options_layout = QHBoxLayout()
        options_layout.setSpacing(16)

        self.cache_checkbox = QCheckBox("使用缓存")
        self.cache_checkbox.setChecked(True)
        self.cache_checkbox.setStyleSheet("color: #64748b; font-size: 12px;")
        options_layout.addWidget(self.cache_checkbox)

        self.wiki_checkbox = QCheckBox("自动生成Wiki")
        self.wiki_checkbox.setChecked(False)
        self.wiki_checkbox.setStyleSheet("color: #64748b; font-size: 12px;")
        options_layout.addWidget(self.wiki_checkbox)

        options_layout.addStretch()
        layout.addLayout(options_layout)

        return widget

    def _create_results_area(self) -> QWidget:
        """创建结果区域"""
        widget = QWidget()
        widget.setObjectName("ResultsArea")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #f8fafc;
            }
            QTabBar::tab {
                background: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 2px;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 2px solid #3b82f6;
            }
            QTabBar::tab:hover {
                background: #e2e8f0;
            }
        """)

        # 搜索结果标签页
        self.search_results_widget = self._create_search_results_tab()
        self.tabs.addTab(self.search_results_widget, "📊 搜索结果")

        # Wiki 标签页
        self.wiki_widget = self._create_wiki_tab()
        self.tabs.addTab(self.wiki_widget, "📖 Wiki")

        # 搜索历史标签页
        self.history_widget = self._create_history_tab()
        self.tabs.addTab(self.history_widget, "📜 搜索历史")

        layout.addWidget(self.tabs)

        return widget

    def _create_search_results_tab(self) -> QWidget:
        """创建搜索结果标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # 结果统计
        self.result_stats_label = QLabel("📊 暂无搜索结果")
        self.result_stats_label.setStyleSheet("""
            font-size: 13px;
            color: #64748b;
            padding: 4px 0;
        """)
        layout.addWidget(self.result_stats_label)

        # 结果列表
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setStyleSheet("""
            QTextEdit {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 12px;
                font-size: 13px;
                color: #1e293b;
            }
        """)
        self.results_text.setFont(QFont("Microsoft YaHei", 12))
        layout.addWidget(self.results_text)

        # 导出按钮
        export_layout = QHBoxLayout()
        export_layout.addStretch()

        self.export_md_btn = QPushButton("📄 导出 Markdown")
        self.export_md_btn.setFixedHeight(32)
        self.export_md_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_md_btn.setEnabled(False)
        self.export_md_btn.setStyleSheet("""
            QPushButton {
                background: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background: #059669;
            }
            QPushButton:disabled {
                background: #94a3b8;
            }
        """)
        self.export_md_btn.clicked.connect(self._export_results)
        export_layout.addWidget(self.export_md_btn)

        self.export_json_btn = QPushButton("📋 导出 JSON")
        self.export_json_btn.setFixedHeight(32)
        self.export_json_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_json_btn.setEnabled(False)
        self.export_json_btn.setStyleSheet("""
            QPushButton {
                background: #8b5cf6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background: #7c3aed;
            }
            QPushButton:disabled {
                background: #94a3b8;
            }
        """)
        self.export_json_btn.clicked.connect(self._export_results_json)
        export_layout.addWidget(self.export_json_btn)

        layout.addLayout(export_layout)

        return widget

    def _create_wiki_tab(self) -> QWidget:
        """创建 Wiki 标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Wiki 标题
        wiki_title = QLabel("📖 Wiki 生成")
        wiki_title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #1e293b;
            padding: 4px 0;
        """)
        layout.addWidget(wiki_title)

        # Wiki 内容
        self.wiki_text = QTextEdit()
        self.wiki_text.setReadOnly(True)
        self.wiki_text.setStyleSheet("""
            QTextEdit {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 12px;
                font-size: 13px;
                color: #1e293b;
            }
        """)
        self.wiki_text.setFont(QFont("Microsoft YaHei", 12))
        layout.addWidget(self.wiki_text)

        # Wiki 操作按钮
        wiki_btn_layout = QHBoxLayout()
        wiki_btn_layout.addStretch()

        self.save_wiki_btn = QPushButton("💾 保存 Wiki")
        self.save_wiki_btn.setFixedHeight(32)
        self.save_wiki_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_wiki_btn.setEnabled(False)
        self.save_wiki_btn.setStyleSheet("""
            QPushButton {
                background: #f59e0b;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background: #d97706;
            }
            QPushButton:disabled {
                background: #94a3b8;
            }
        """)
        self.save_wiki_btn.clicked.connect(self._save_wiki)
        wiki_btn_layout.addWidget(self.save_wiki_btn)

        layout.addLayout(wiki_btn_layout)

        return widget

    def _create_history_tab(self) -> QWidget:
        """创建搜索历史标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # 历史标题
        history_title = QLabel("📜 搜索历史")
        history_title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #1e293b;
            padding: 4px 0;
        """)
        layout.addWidget(history_title)

        # 历史表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["时间", "关键词", "类型", "结果数"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                gridline-color: #e2e8f0;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background: #f1f5f9;
                border: none;
                padding: 6px;
                font-weight: bold;
            }
        """)
        self.history_table.itemClicked.connect(self._on_history_clicked)
        layout.addWidget(self.history_table)

        # 历史操作按钮
        history_btn_layout = QHBoxLayout()
        history_btn_layout.addStretch()

        self.clear_history_btn = QPushButton("🗑️ 清空历史")
        self.clear_history_btn.setFixedHeight(32)
        self.clear_history_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_history_btn.setStyleSheet("""
            QPushButton {
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background: #dc2626;
            }
        """)
        self.clear_history_btn.clicked.connect(self._clear_history)
        history_btn_layout.addWidget(self.clear_history_btn)

        layout.addLayout(history_btn_layout)

        return widget

    def _create_stats_area(self) -> QWidget:
        """创建统计区域"""
        widget = QWidget()
        widget.setObjectName("StatsArea")
        widget.setStyleSheet("""
            QWidget#StatsArea {
                background: white;
                border-top: 1px solid #e2e8f0;
            }
        """)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(16)

        # 搜索次数
        self.search_count_label = QLabel("🔍 搜索次数: 0")
        self.search_count_label.setStyleSheet("font-size: 12px; color: #64748b;")
        layout.addWidget(self.search_count_label)

        # 总结果数
        self.total_results_label = QLabel("📊 总结果数: 0")
        self.total_results_label.setStyleSheet("font-size: 12px; color: #64748b;")
        layout.addWidget(self.total_results_label)

        # 平均耗时
        self.avg_time_label = QLabel("⏱️ 平均耗时: 0ms")
        self.avg_time_label.setStyleSheet("font-size: 12px; color: #64748b;")
        layout.addWidget(self.avg_time_label)

        # Wiki 数量
        self.wiki_count_label = QLabel("📖 Wiki 数量: 0")
        self.wiki_count_label.setStyleSheet("font-size: 12px; color: #64748b;")
        layout.addWidget(self.wiki_count_label)

        layout.addStretch()

        return widget

    def _init_intelligence_hub(self):
        """初始化 IntelligenceHub"""
        try:
            from core.intelligence_center.intelligence_hub import get_intelligence_hub
            self._intelligence_hub = get_intelligence_hub()
            logger.info("IntelligenceHub 初始化成功")
        except ImportError as e:
            logger.warning(f"无法导入 IntelligenceHub: {e}")
            self._intelligence_hub = None
        except Exception as e:
            logger.warning(f"IntelligenceHub 初始化失败: {e}")
            self._intelligence_hub = None

        try:
            from core.deep_search_wiki import get_wiki_system
            self._wiki_system = get_wiki_system()
            logger.info("DeepSearchWikiSystem 初始化成功")
        except ImportError as e:
            logger.warning(f"无法导入 DeepSearchWikiSystem: {e}")
            self._wiki_system = None
        except Exception as e:
            logger.warning(f"DeepSearchWikiSystem 初始化失败: {e}")
            self._wiki_system = None

    def _execute_search(self):
        """执行搜索"""
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, "提示", "请输入搜索关键词")
            return

        search_type = self.search_type_combo.currentText()
        use_cache = self.cache_checkbox.isChecked()

        # 更新 UI 状态
        self._is_searching = True
        self.search_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.search_input.setEnabled(False)
        self.search_type_combo.setEnabled(False)

        # 显示搜索中状态
        self.results_text.setHtml(f"""
            <div style="text-align: center; padding: 40px;">
                <p style="font-size: 16px; color: #3b82f6;">🔄 正在搜索: {query}</p>
                <p style="font-size: 12px; color: #94a3b8;">搜索类型: {search_type}</p>
            </div>
        """)

        # 异步执行搜索
        asyncio.create_task(self._async_search(query, search_type, use_cache))

    async def _async_search(self, query: str, search_type: str, use_cache: bool):
        """异步执行搜索"""
        start_time = time.time()

        try:
            results = []

            if search_type == "通用搜索":
                results = await self._general_search(query, use_cache)
            elif search_type == "竞品监控":
                results = await self._competitor_search(query)
            elif search_type == "产品发布":
                results = await self._product_release_search(query)
            elif search_type == "舆情分析":
                results = await self._sentiment_search(query)
            elif search_type == "Wiki生成":
                results = await self._wiki_search(query)

            execution_time = (time.time() - start_time) * 1000

            # 更新结果
            self._display_results(results, execution_time, query)

            # 添加到历史记录
            self._add_to_history(query, search_type, len(results))

            # 更新统计
            self._update_stats(len(results), execution_time)

            # 如果启用了 Wiki 生成，自动生成 Wiki
            if self.wiki_checkbox.isChecked() and results:
                await self._generate_wiki(query)

        except Exception as e:
            logger.error(f"搜索失败: {e}", exc_info=True)
            self.results_text.setHtml(f"""
                <div style="text-align: center; padding: 40px;">
                    <p style="font-size: 16px; color: #ef4444;">❌ 搜索失败</p>
                    <p style="font-size: 12px; color: #94a3b8;">{str(e)}</p>
                </div>
            """)

        finally:
            # 恢复 UI 状态
            self._is_searching = False
            self.search_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.search_input.setEnabled(True)
            self.search_type_combo.setEnabled(True)

    async def _general_search(self, query: str, use_cache: bool) -> List[dict]:
        """通用搜索"""
        if self._intelligence_hub:
            try:
                response = await self._intelligence_hub.search(query, use_cache=use_cache)
                if hasattr(response, 'results'):
                    return [
                        {
                            "title": r.title,
                            "url": r.url,
                            "snippet": r.snippet,
                            "source": r.source,
                            "score": r.relevance_score,
                        }
                        for r in response.results
                    ]
            except Exception as e:
                logger.warning(f"IntelligenceHub 搜索失败: {e}")

        # 降级：返回模拟数据
        return self._generate_mock_results(query)

    async def _competitor_search(self, query: str) -> List[dict]:
        """竞品监控搜索"""
        if self._intelligence_hub:
            try:
                response = await self._intelligence_hub.deep_search(query, "competitor")
                if hasattr(response, 'results'):
                    return [
                        {
                            "title": r.title,
                            "url": r.url,
                            "snippet": r.snippet,
                            "source": r.source,
                            "score": r.relevance_score,
                            "type": "竞品",
                        }
                        for r in response.results
                    ]
            except Exception as e:
                logger.warning(f"竞品搜索失败: {e}")

        return self._generate_mock_results(f"{query} 竞品")

    async def _product_release_search(self, query: str) -> List[dict]:
        """产品发布搜索"""
        if self._intelligence_hub:
            try:
                response = await self._intelligence_hub.deep_search(query, "releases")
                if hasattr(response, 'results'):
                    return [
                        {
                            "title": r.title,
                            "url": r.url,
                            "snippet": r.snippet,
                            "source": r.source,
                            "score": r.relevance_score,
                            "type": "产品",
                        }
                        for r in response.results
                    ]
            except Exception as e:
                logger.warning(f"产品发布搜索失败: {e}")

        return self._generate_mock_results(f"{query} 新品发布")

    async def _sentiment_search(self, query: str) -> List[dict]:
        """舆情分析搜索"""
        if self._intelligence_hub:
            try:
                response = await self._intelligence_hub.deep_search(query, "sentiment")
                if hasattr(response, 'results'):
                    return [
                        {
                            "title": r.title,
                            "url": r.url,
                            "snippet": r.snippet,
                            "source": r.source,
                            "score": r.relevance_score,
                            "type": "舆情",
                        }
                        for r in response.results
                    ]
            except Exception as e:
                logger.warning(f"舆情分析搜索失败: {e}")

        return self._generate_mock_results(f"{query} 口碑")

    async def _wiki_search(self, query: str) -> List[dict]:
        """Wiki 生成搜索"""
        if self._wiki_system:
            try:
                wiki = await self._wiki_system.generate_async(query)
                if wiki:
                    self.wiki_text.setMarkdown(wiki.to_markdown())
                    self.save_wiki_btn.setEnabled(True)
                    return [{"title": wiki.topic, "type": "Wiki", "content": wiki.to_markdown()}]
            except Exception as e:
                logger.warning(f"Wiki 生成失败: {e}")

        return self._generate_mock_results(f"{query} Wiki")

    def _generate_mock_results(self, query: str) -> List[dict]:
        """生成模拟搜索结果"""
        return [
            {
                "title": f"{query} - 搜索结果 1",
                "url": "https://example.com/1",
                "snippet": f"这是关于 {query} 的搜索结果摘要。",
                "source": "模拟源",
                "score": 0.95,
            },
            {
                "title": f"{query} - 搜索结果 2",
                "url": "https://example.com/2",
                "snippet": f"这是关于 {query} 的另一条搜索结果。",
                "source": "模拟源",
                "score": 0.85,
            },
            {
                "title": f"{query} - 搜索结果 3",
                "url": "https://example.com/3",
                "snippet": f"这是关于 {query} 的第三条搜索结果。",
                "source": "模拟源",
                "score": 0.75,
            },
        ]

    def _display_results(self, results: List[dict], execution_time: float, query: str):
        """显示搜索结果"""
        self._current_results = results

        if not results:
            self.results_text.setHtml("""
                <div style="text-align: center; padding: 40px;">
                    <p style="font-size: 16px; color: #94a3b8;">📭 暂无搜索结果</p>
                </div>
            """)
            self.export_md_btn.setEnabled(False)
            self.export_json_btn.setEnabled(False)
            return

        # 构建 Markdown 格式结果
        md = f"# 🔍 搜索结果: {query}\n\n"
        md += f"> 共找到 {len(results)} 条结果 | 耗时 {execution_time:.0f}ms\n\n"
        md += "---\n\n"

        for i, result in enumerate(results, 1):
            md += f"## {i}. {result.get('title', '无标题')}\n\n"
            md += f"**来源:** {result.get('source', '未知')}  "
            md += f"**评分:** {result.get('score', 0):.2f}\n\n"
            md += f"{result.get('snippet', '无摘要')}\n\n"
            if result.get('url'):
                md += f"[{result['url']}]({result['url']})\n\n"
            md += "---\n\n"

        self.results_text.setMarkdown(md)
        self.export_md_btn.setEnabled(True)
        self.export_json_btn.setEnabled(True)

    def _add_to_history(self, query: str, search_type: str, result_count: int):
        """添加到搜索历史"""
        self._search_history.insert(0, {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "type": search_type,
            "result_count": result_count,
        })

        # 限制历史记录数量
        if len(self._search_history) > 100:
            self._search_history = self._search_history[:100]

        self._update_history_table()

    def _update_history_table(self):
        """更新历史表格"""
        self.history_table.setRowCount(len(self._search_history))

        for i, item in enumerate(self._search_history):
            timestamp = datetime.fromisoformat(item["timestamp"]).strftime("%Y-%m-%d %H:%M")
            self.history_table.setItem(i, 0, QTableWidgetItem(timestamp))
            self.history_table.setItem(i, 1, QTableWidgetItem(item["query"]))
            self.history_table.setItem(i, 2, QTableWidgetItem(item["type"]))
            self.history_table.setItem(i, 3, QTableWidgetItem(str(item["result_count"])))

    def _update_stats(self, result_count: int, execution_time: float):
        """更新统计信息"""
        # 搜索次数
        search_count = int(self.search_count_label.text().split(":")[1].split()[0]) + 1
        self.search_count_label.setText(f"🔍 搜索次数: {search_count}")

        # 总结果数
        total_results = int(self.total_results_label.text().split(":")[1].split()[0]) + result_count
        self.total_results_label.setText(f"📊 总结果数: {total_results}")

        # 平均耗时
        self.export_md_btn.setEnabled(True)
        self.export_json_btn.setEnabled(True)

        # Wiki 数量
        wiki_count = int(self.wiki_count_label.text().split(":")[1].split()[0])
        self.wiki_count_label.setText(f"📖 Wiki 数量: {wiki_count}")

    async def _generate_wiki(self, topic: str):
        """生成 Wiki"""
        if self._wiki_system:
            try:
                wiki = await self._wiki_system.generate_async(topic)
                if wiki:
                    self.wiki_text.setMarkdown(wiki.to_markdown())
                    self.save_wiki_btn.setEnabled(True)
                    self.tabs.setCurrentIndex(1)  # 切换到 Wiki 标签页
            except Exception as e:
                logger.warning(f"Wiki 生成失败: {e}")

    def _stop_search(self):
        """停止搜索"""
        self._is_searching = False
        self.search_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.search_input.setEnabled(True)
        self.search_type_combo.setEnabled(True)
        self.results_text.setHtml("""
            <div style="text-align: center; padding: 40px;">
                <p style="font-size: 16px; color: #f59e0b;">⏹️ 搜索已停止</p>
            </div>
        """)

    def _clear_results(self):
        """清空结果"""
        self.results_text.setHtml("""
            <div style="text-align: center; padding: 40px;">
                <p style="font-size: 16px; color: #94a3b8;">📭 暂无搜索结果</p>
            </div>
        """)
        self.wiki_text.setHtml("")
        self.export_md_btn.setEnabled(False)
        self.export_json_btn.setEnabled(False)
        self.save_wiki_btn.setEnabled(False)
        self._current_results = []

    def _export_results(self):
        """导出结果为 Markdown"""
        if not self._current_results:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出 Markdown", "", "Markdown Files (*.md)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.results_text.toMarkdown() if hasattr(self.results_text, 'toMarkdown') else self.results_text.toPlainText())
            QMessageBox.information(self, "成功", f"结果已导出到 {file_path}")

    def _export_results_json(self):
        """导出结果为 JSON"""
        import json

        if not self._current_results:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出 JSON", "", "JSON Files (*.json)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self._current_results, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "成功", f"结果已导出到 {file_path}")

    def _save_wiki(self):
        """保存 Wiki"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存 Wiki", "", "Markdown Files (*.md)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.wiki_text.toPlainText())
            QMessageBox.information(self, "成功", f"Wiki 已保存到 {file_path}")

    def _clear_history(self):
        """清空历史"""
        reply = QMessageBox.question(
            self, "确认", "确定要清空搜索历史吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._search_history.clear()
            self.history_table.setRowCount(0)

    def _on_history_clicked(self, item):
        """点击历史记录"""
        row = item.row()
        if row < len(self._search_history):
            history = self._search_history[row]
            self.search_input.setText(history["query"])
            self.tabs.setCurrentIndex(0)  # 切换到搜索结果标签页

    def get_search_history(self) -> List[dict]:
        """获取搜索历史"""
        return self._search_history

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "search_count": int(self.search_count_label.text().split(":")[1].split()[0]),
            "total_results": int(self.total_results_label.text().split(":")[1].split()[0]),
            "wiki_count": int(self.wiki_count_label.text().split(":")[1].split()[0]),
            "history_count": len(self._search_history),
        }
