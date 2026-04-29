"""
SelfEvolutionPanel - 自我进化控制面板（PyQt6）

提供可视化界面控制自我进化流程：
- 项目概览（文件数、代码行、类、工具等）
- 知识管理（查看、搜索、标记已应用）
- 进化计划（查看、审核动作）
- 执行控制（一键进化、手动/自动模式切换）
- 执行日志（实时显示进度和结果）
- 进化历史（查看历史会话和对比）

Author: LivingTreeAI
Date: 2026-04-29
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, QObject,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit,
    QProgressBar, QGroupBox, QFormLayout,
    QTabWidget, QTableWidget, QTableWidgetItem,
    QComboBox, QCheckBox, QSplitter,
    QMessageBox, QFileDialog, QHeaderView,
    QScrollArea, QTextBrowser,
)
from PyQt6.QtGui import QFont, QColor, QPalette, QTextCursor


class EvolutionWorkerSignals(QObject):
    """进化工作线程信号"""
    progress = pyqtSignal(str, float)  # (message, progress_0_to_1)
    log = pyqtSignal(str)  # log message
    finished = pyqtSignal(dict)  # session dict
    error = pyqtSignal(str)


class EvolutionWorker(QThread):
    """进化工作线程"""

    def __init__(
        self,
        orchestrator,
        goal: str = "",
        constraints: list = None,
        focus_areas: list = None,
        auto_approve: bool = False,
    ):
        super().__init__()
        self._orchestrator = orchestrator
        self._goal = goal
        self._constraints = constraints or []
        self._focus_areas = focus_areas or []
        self._auto_approve = auto_approve
        self.signals = EvolutionWorkerSignals()

    def run(self):
        """执行进化"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            def on_progress(msg, prog):
                self.signals.progress.emit(msg, prog)
                self.signals.log.emit(f"[{prog:.0%}] {msg}")

            self._orchestrator._on_progress = on_progress

            session = loop.run_until_complete(
                self._orchestrator.evolve(
                    goal=self._goal,
                    constraints=self._constraints,
                    focus_areas=self._focus_areas,
                )
            )

            self.signals.log.emit(f"进化完成: {session.session_id}")
            self.signals.finished.emit(session.to_dict())

        except Exception as e:
            self.signals.error.emit(str(e))
            self.signals.log.emit(f"错误: {e}")
        finally:
            loop.close()


class KnowledgeWorker(QThread):
    """知识摄入工作线程"""
    finished = pyqtSignal(dict)  # IngestionResult
    error = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, orchestrator, method: str, **kwargs):
        super().__init__()
        self._orchestrator = orchestrator
        self._method = method
        self._kwargs = kwargs

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            method_map = {
                "url": self._orchestrator.learn_from_url,
                "text": self._orchestrator.learn_from_text,
                "document": self._orchestrator.learn_from_document,
                "source_code": self._orchestrator.learn_from_source_code,
                "git_history": self._orchestrator.learn_from_git_history,
            }

            func = method_map.get(self._method)
            if func:
                self.log.emit(f"开始摄取知识 ({self._method})...")
                result = loop.run_until_complete(func(**self._kwargs))
                self.finished.emit({
                    "success": result.success,
                    "entries": result.entries_created,
                    "errors": result.errors,
                    "duration_ms": result.duration_ms,
                })
            else:
                self.error.emit(f"未知方法: {self._method}")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            loop.close()


class SelfEvolutionPanel(QWidget):
    """自我进化控制面板"""

    def __init__(self, project_root: str, parent=None):
        super().__init__(parent)
        self._project_root = project_root
        self._orchestrator = None
        self._worker = None
        self._init_orchestrator()
        self._setup_ui()
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_status)
        self._refresh_timer.start(5000)  # 5 秒刷新

    def _init_orchestrator(self):
        """初始化协调器"""
        try:
            from client.src.business.self_evolution.self_evolution_orchestrator import (
                SelfEvolutionOrchestrator,
            )
            self._orchestrator = SelfEvolutionOrchestrator(
                project_root=self._project_root,
            )
        except Exception as e:
            self._orchestrator = None
            print(f"初始化进化协调器失败: {e}")

    def _setup_ui(self):
        """构建 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 标题栏
        title_bar = QHBoxLayout()
        title = QLabel("🧬 自我进化中心")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        title_bar.addWidget(title)

        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet("color: #888; font-size: 13px;")
        title_bar.addStretch()
        title_bar.addWidget(self._status_label)
        layout.addLayout(title_bar)

        # 分割器
        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── 上部：控制区 ──
        control_widget = QWidget()
        control_layout = QHBoxLayout(control_widget)
        control_layout.setSpacing(12)

        # 左侧：进化控制
        evo_group = QGroupBox("🚀 进化控制")
        evo_layout = QVBoxLayout(evo_group)

        # 目标输入
        goal_layout = QHBoxLayout()
        goal_layout.addWidget(QLabel("进化目标:"))
        self._goal_input = QLineEdit()
        self._goal_input.setPlaceholderText("输入进化目标，留空则自动分析...")
        goal_layout.addWidget(self._goal_input)
        evo_layout.addLayout(goal_layout)

        # 按钮行
        btn_layout = QHBoxLayout()
        self._evolve_btn = QPushButton("▶ 一键进化")
        self._evolve_btn.setStyleSheet(
            "QPushButton { background: #4CAF50; color: white; padding: 8px 16px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background: #45a049; }"
            "QPushButton:disabled { background: #999; }"
        )
        self._evolve_btn.clicked.connect(self._start_evolution)
        btn_layout.addWidget(self._evolve_btn)

        self._auto_cb = QCheckBox("自动批准")
        self._auto_cb.setToolTip("自动批准所有进化动作（跳过审核）")
        btn_layout.addWidget(self._auto_cb)

        self._scan_btn = QPushButton("📊 仅扫描")
        self._scan_btn.clicked.connect(self._scan_only)
        btn_layout.addWidget(self._scan_btn)

        evo_layout.addLayout(btn_layout)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        evo_layout.addWidget(self._progress)

        control_layout.addWidget(evo_group, 2)

        # 右侧：知识摄入
        knowledge_group = QGroupBox("📚 知识学习")
        knowledge_layout = QVBoxLayout(knowledge_group)

        # 学习方式选择
        self._learn_type = QComboBox()
        self._learn_type.addItems(["URL", "文本输入", "文档文件", "源代码", "Git 历史"])
        self._learn_type.currentIndexChanged.connect(self._on_learn_type_changed)
        knowledge_layout.addWidget(self._learn_type)

        # URL 输入
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://...")
        knowledge_layout.addWidget(self._url_input)

        # 文本输入
        self._text_input = QTextEdit()
        self._text_input.setPlaceholderText("输入要学习的文本内容...")
        self._text_input.setMaximumHeight(80)
        self._text_input.hide()
        knowledge_layout.addWidget(self._text_input)

        # 文件选择
        self._file_input = QLineEdit()
        self._file_input.setPlaceholderText("选择文件路径...")
        self._file_input.hide()
        file_btn_layout = QHBoxLayout()
        file_btn_layout.addWidget(self._file_input)
        self._browse_btn = QPushButton("浏览")
        self._browse_btn.clicked.connect(self._browse_file)
        file_btn_layout.addWidget(self._browse_btn)
        knowledge_layout.addLayout(file_btn_layout)

        # 学习按钮
        self._learn_btn = QPushButton("📖 开始学习")
        self._learn_btn.setStyleSheet(
            "QPushButton { background: #2196F3; color: white; padding: 6px 12px; "
            "border-radius: 4px; }"
            "QPushButton:hover { background: #1976D2; }"
        )
        self._learn_btn.clicked.connect(self._start_learning)
        knowledge_layout.addWidget(self._learn_btn)

        control_layout.addWidget(knowledge_group, 1)
        splitter.addWidget(control_widget)

        # ── 下部：标签页 ──
        self._tabs = QTabWidget()
        splitter.addWidget(self._tabs)

        # 标签页 1: 项目概览
        self._overview_tab = self._create_overview_tab()
        self._tabs.addTab(self._overview_tab, "📊 项目概览")

        # 标签页 2: 知识库
        self._knowledge_tab = self._create_knowledge_tab()
        self._tabs.addTab(self._knowledge_tab, "📚 知识库")

        # 标签页 3: 进化计划
        self._plan_tab = self._create_plan_tab()
        self._tabs.addTab(self._plan_tab, "📋 进化计划")

        # 标签页 4: 执行日志
        self._log_tab = self._create_log_tab()
        self._tabs.addTab(self._log_tab, "📝 执行日志")

        # 标签页 5: 进化历史
        self._history_tab = self._create_history_tab()
        self._tabs.addTab(self._history_tab, "📜 历史")

        splitter.setSizes([200, 400])
        layout.addWidget(splitter)

    # ── 标签页创建 ─────────────────────────────────────────

    def _create_overview_tab(self) -> QWidget:
        """项目概览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 统计卡片
        stats_layout = QGridLayout()
        self._stat_labels = {}
        stat_items = [
            ("文件数", "total_files", "📄"),
            ("代码行", "total_lines", "📝"),
            ("类", "total_classes", "🏗"),
            ("函数", "total_functions", "⚡"),
            ("TODO", "todo_count", "📌"),
            ("FIXME", "fixme_count", "🐛"),
            ("工具", "tools", "🔧"),
            ("知识", "knowledge", "📚"),
        ]

        for i, (label, key, icon) in enumerate(stat_items):
            card = QGroupBox()
            card.setStyleSheet(
                "QGroupBox { font-weight: bold; border: 1px solid #ddd; "
                "border-radius: 8px; padding: 12px; }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)
            icon_label = QLabel(f"{icon} {label}")
            icon_label.setStyleSheet("color: #666; font-size: 12px;")
            value_label = QLabel("-")
            value_label.setStyleSheet("font-size: 20px; font-weight: bold;")
            card_layout.addWidget(icon_label)
            card_layout.addWidget(value_label)
            stats_layout.addWidget(card, i // 4, i % 4)
            self._stat_labels[key] = value_label

        layout.addLayout(stats_layout)

        # 模块摘要
        summary_group = QGroupBox("📋 模块摘要")
        summary_layout = QVBoxLayout(summary_group)
        self._summary_browser = QTextBrowser()
        self._summary_browser.setReadOnly(True)
        self._summary_browser.setFont(QFont("Consolas", 10))
        summary_layout.addWidget(self._summary_browser)
        layout.addWidget(summary_group)

        return widget

    def _create_knowledge_tab(self) -> QWidget:
        """知识库标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 搜索
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("🔍 搜索:"))
        self._kb_search = QLineEdit()
        self._kb_search.setPlaceholderText("搜索知识标题或标签...")
        self._kb_search.textChanged.connect(self._search_knowledge)
        search_layout.addWidget(self._kb_search)

        self._kb_filter = QComboBox()
        self._kb_filter.addItems(["全部", "未应用", "已应用"])
        self._kb_filter.currentIndexChanged.connect(self._refresh_knowledge)
        search_layout.addWidget(self._kb_filter)

        self._refresh_kb_btn = QPushButton("刷新")
        self._refresh_kb_btn.clicked.connect(self._refresh_knowledge)
        search_layout.addWidget(self._refresh_kb_btn)

        layout.addLayout(search_layout)

        # 知识表格
        self._kb_table = QTableWidget()
        self._kb_table.setColumnCount(5)
        self._kb_table.setHorizontalHeaderLabels(["类型", "标题", "摘要", "来源", "已应用"])
        self._kb_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._kb_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._kb_table)

        # 知识详情
        self._kb_detail = QTextEdit()
        self._kb_detail.setReadOnly(True)
        self._kb_detail.setMaximumHeight(120)
        self._kb_table.cellClicked.connect(self._show_knowledge_detail)
        layout.addWidget(self._kb_detail)

        return widget

    def _create_plan_tab(self) -> QWidget:
        """进化计划标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 计划信息
        self._plan_info = QLabel("暂无进化计划")
        self._plan_info.setStyleSheet("font-size: 14px; padding: 8px;")
        layout.addWidget(self._plan_info)

        # 动作表格
        self._plan_table = QTableWidget()
        self._plan_table.setColumnCount(6)
        self._plan_table.setHorizontalHeaderLabels([
            "优先级", "类型", "标题", "目标文件", "状态", "影响"
        ])
        self._plan_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._plan_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._plan_table)

        # 动作详情
        self._action_detail = QTextEdit()
        self._action_detail.setReadOnly(True)
        self._action_detail.setMaximumHeight(100)
        self._plan_table.cellClicked.connect(self._show_action_detail)
        layout.addWidget(self._action_detail)

        return widget

    def _create_log_tab(self) -> QWidget:
        """执行日志标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        toolbar = QHBoxLayout()
        clear_btn = QPushButton("清除日志")
        clear_btn.clicked.connect(lambda: self._log_browser.clear())
        toolbar.addStretch()
        toolbar.addWidget(clear_btn)
        layout.addLayout(toolbar)

        self._log_browser = QTextBrowser()
        self._log_browser.setFont(QFont("Consolas", 10))
        self._log_browser.setStyleSheet("background: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self._log_browser)

        return widget

    def _create_history_tab(self) -> QWidget:
        """进化历史标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self._history_table = QTableWidget()
        self._history_table.setColumnCount(5)
        self._history_table.setHorizontalHeaderLabels([
            "会话 ID", "时间", "动作数", "完成数", "状态"
        ])
        self._history_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._history_table.cellClicked.connect(self._show_history_detail)
        layout.addWidget(self._history_table)

        self._history_detail = QTextBrowser()
        self._history_detail.setMaximumHeight(150)
        layout.addWidget(self._history_detail)

        refresh_btn = QPushButton("刷新历史")
        refresh_btn.clicked.connect(self._refresh_history)
        layout.addWidget(refresh_btn)

        return widget

    # ── 事件处理 ───────────────────────────────────────────

    def _on_learn_type_changed(self, index: int):
        """学习类型切换"""
        self._url_input.hide()
        self._text_input.hide()
        self._file_input.hide()
        self._browse_btn.hide()

        if index == 0:  # URL
            self._url_input.show()
        elif index == 1:  # 文本
            self._text_input.show()
        elif index in (2, 3):  # 文档 / 源代码
            self._file_input.show()
            self._browse_btn.show()
        # index == 4: Git 历史（无需输入）

    def _browse_file(self):
        """浏览文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", str(Path(self._project_root)),
            "所有文件 (*.*);;Python 文件 (*.py);;文档 (*.md *.txt *.pdf);;代码 (*.py *.js *.ts)"
        )
        if path:
            self._file_input.setText(path)

    def _start_evolution(self):
        """启动进化"""
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "提示", "进化正在进行中...")
            return

        goal = self._goal_input.text().strip()
        auto_approve = self._auto_cb.isChecked()

        self._log("🚀 开始进化..." + (f" 目标: {goal}" if goal else " (自动分析)"))
        self._evolve_btn.setEnabled(False)
        self._progress.setValue(0)

        self._worker = EvolutionWorker(
            self._orchestrator,
            goal=goal,
            auto_approve=auto_approve,
        )
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.log.connect(self._log)
        self._worker.signals.finished.connect(self._on_evolution_finished)
        self._worker.signals.error.connect(self._on_evolution_error)
        self._worker.start()

    def _scan_only(self):
        """仅扫描项目"""
        self._log("📊 扫描项目结构...")

        def do_scan():
            try:
                from client.src.business.self_evolution.project_structure_scanner import ScanDepth
                result = self._orchestrator.scan_project(ScanDepth.MEDIUM)
                self._update_overview(result)
                self._log(f"扫描完成: {result.total_files} 文件, {result.total_lines} 行")
            except Exception as e:
                self._log(f"扫描失败: {e}")

        import threading
        threading.Thread(target=do_scan, daemon=True).start()

    def _start_learning(self):
        """开始学习"""
        index = self._learn_type.currentIndex()
        method_map = ["url", "text", "document", "source_code", "git_history"]

        if index == 0:
            url = self._url_input.text().strip()
            if not url:
                QMessageBox.warning(self, "提示", "请输入 URL")
                return
            kwargs = {"url": url}
        elif index == 1:
            text = self._text_input.toPlainText().strip()
            if not text:
                QMessageBox.warning(self, "提示", "请输入文本内容")
                return
            kwargs = {"text": text, "source_name": "panel_input"}
        elif index in (2, 3):
            path = self._file_input.text().strip()
            if not path or not Path(path).exists():
                QMessageBox.warning(self, "提示", "请选择有效文件")
                return
            kwargs = {"file_path": path}
        else:
            kwargs = {"max_commits": 50}

        self._learn_btn.setEnabled(False)
        worker = KnowledgeWorker(self._orchestrator, method_map[index], **kwargs)
        worker.log.connect(self._log)
        worker.finished.connect(self._on_learning_finished)
        worker.error.connect(self._on_learning_error)
        worker.start()
        self._current_learn_worker = worker

    # ── 信号处理 ───────────────────────────────────────────

    def _on_progress(self, message: str, progress: float):
        self._progress.setValue(int(progress * 100))

    def _on_evolution_finished(self, session_dict: dict):
        self._evolve_btn.setEnabled(True)
        self._progress.setValue(100)
        self._log(f"✅ 进化完成: {session_dict.get('completed_count', 0)}/{session_dict.get('total_files', 0)}")

        # 更新计划标签页
        self._update_plan_tab(session_dict)

        # 刷新概览
        QTimer.singleShot(1000, self._refresh_status)

    def _on_evolution_error(self, error_msg: str):
        self._evolve_btn.setEnabled(True)
        self._progress.setValue(0)
        self._log(f"❌ 进化失败: {error_msg}")

    def _on_learning_finished(self, result: dict):
        self._learn_btn.setEnabled(True)
        entries = result.get("entries", 0)
        self._log(f"✅ 学习完成: {entries} 条知识")
        self._refresh_knowledge()

    def _on_learning_error(self, error_msg: str):
        self._learn_btn.setEnabled(True)
        self._log(f"❌ 学习失败: {error_msg}")

    # ── UI 更新方法 ───────────────────────────────────────

    def _update_overview(self, scan_result):
        """更新项目概览"""
        self._stat_labels["total_files"].setText(str(scan_result.total_files))
        self._stat_labels["total_lines"].setText(f"{scan_result.total_lines:,}")
        self._stat_labels["total_classes"].setText(str(scan_result.total_classes))
        self._stat_labels["total_functions"].setText(str(scan_result.total_functions))
        self._stat_labels["todo_count"].setText(str(scan_result.todo_count))
        self._stat_labels["fixme_count"].setText(str(scan_result.fixme_count))
        self._stat_labels["tools"].setText(str(len(scan_result.registered_tools)))

        if self._orchestrator:
            kb_count = len(self._orchestrator._ingestion.list_entries())
            self._stat_labels["knowledge"].setText(str(kb_count))

        self._summary_browser.setPlainText(
            self._orchestrator.get_module_summary() if self._orchestrator else "无数据"
        )

    def _update_plan_tab(self, session_dict: dict):
        """更新计划标签页"""
        total = session_dict.get("action_count", 0)
        completed = session_dict.get("completed_count", 0)
        self._plan_info.setText(f"进化计划 | 动作: {total} | 已完成: {completed}")

        # TODO: 显示具体动作列表

    def _refresh_knowledge(self):
        """刷新知识库"""
        if not self._orchestrator:
            return

        entries = self._orchestrator._ingestion.list_entries(limit=100)

        filter_idx = self._kb_filter.currentIndex()
        if filter_idx == 1:
            entries = [e for e in entries if not e.applied]
        elif filter_idx == 2:
            entries = [e for e in entries if e.applied]

        search = self._kb_search.text().strip().lower()
        if search:
            entries = [
                e for e in entries
                if search in e.title.lower()
                or search in e.summary.lower()
                or any(search in t for t in e.tags)
            ]

        self._kb_table.setRowCount(len(entries))
        for i, entry in enumerate(entries):
            self._kb_table.setItem(i, 0, QTableWidgetItem(entry.knowledge_type.value))
            self._kb_table.setItem(i, 1, QTableWidgetItem(entry.title))
            self._kb_table.setItem(i, 2, QTableWidgetItem(entry.summary[:80]))
            self._kb_table.setItem(i, 3, QTableWidgetItem(entry.source_ref[:40]))

            applied_item = QTableWidgetItem("✅" if entry.applied else "⏳")
            applied_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._kb_table.setItem(i, 4, applied_item)

    def _show_knowledge_detail(self, row: int, col: int):
        """显示知识详情"""
        if not self._orchestrator:
            return
        entries = self._orchestrator._ingestion.list_entries(limit=100)
        if row < len(entries):
            entry = entries[row]
            self._kb_detail.setPlainText(
                f"标题: {entry.title}\n"
                f"类型: {entry.knowledge_type.value}\n"
                f"来源: {entry.source_ref}\n"
                f"标签: {', '.join(entry.tags)}\n"
                f"置信度: {entry.confidence}\n\n"
                f"内容:\n{entry.content}"
            )

    def _show_action_detail(self, row: int, col: int):
        """显示动作详情"""
        pass  # TODO

    def _search_knowledge(self, text: str):
        """搜索知识"""
        self._refresh_knowledge()

    def _refresh_history(self):
        """刷新历史"""
        if not self._orchestrator:
            return
        history = self._orchestrator.get_history()
        self._history_table.setRowCount(len(history))
        for i, session in enumerate(history):
            self._history_table.setItem(i, 0, QTableWidgetItem(session.get("session_id", "")))
            self._history_table.setItem(i, 1, QTableWidgetItem(session.get("started_at", "")))
            self._history_table.setItem(i, 2, QTableWidgetItem(str(session.get("action_count", 0))))
            self._history_table.setItem(i, 3, QTableWidgetItem(str(session.get("completed_count", 0))))
            self._history_table.setItem(i, 4, QTableWidgetItem(session.get("phase", "")))

    def _show_history_detail(self, row: int, col: int):
        """显示历史详情"""
        item = self._history_table.item(row, 0)
        if item and self._orchestrator:
            # 查找对应的日志
            logs = []
            if row < len(self._orchestrator.get_history()):
                session = self._orchestrator.get_history()[row]
                logs = session.get("logs", [])
                errors = session.get("errors", [])
            self._history_detail.setPlainText(
                "\n".join(logs) + ("\n\n错误:\n" + "\n".join(errors) if errors else "")
            )

    def _refresh_status(self):
        """刷新状态"""
        if not self._orchestrator:
            self._status_label.setText("❌ 未初始化")
            return
        status = self._orchestrator.get_status()
        unapplied = status.get("unapplied_knowledge", 0)
        sessions = status.get("session_count", 0)
        self._status_label.setText(
            f"📚 {unapplied} 条待应用知识 | 📜 {sessions} 次进化会话"
        )

    def _log(self, message: str):
        """写入日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_browser.append(f"<span style='color:#888'>[{timestamp}]</span> {message}")
        # 自动滚动到底部
        cursor = self._log_browser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log_browser.setTextCursor(cursor)
