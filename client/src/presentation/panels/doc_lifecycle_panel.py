"""
文档审核与生命周期管理面板
DocLifecycle UI Panel - PyQt6集成面板
"""

import os
import webbrowser
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QTableWidget, QTableWidgetItem, QPushButton,
    QLabel, QLineEdit, QComboBox, QProgressBar, QTextEdit,
    QFileDialog, QListWidget, QListWidgetItem, QGroupBox,
    QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox,
    QTreeWidget, QTreeWidgetItem, QHeaderView,
    QMenu, QMessageBox, QDialog, QDialogButtonBox,
    QProgressDialog
)

from core.doc_lifecycle import (
    get_doc_lifecycle_system, ReviewLevel, ReviewStatus,
    FileActivity, ActivityLevel, CleanupRule, CleanupTask,
    ReportInfo, ReviewResult
)


class DocLifecyclePanel(QWidget):
    """文档审核与生命周期管理面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._system = get_doc_lifecycle_system()
        self._system.start()
        
        self._init_ui()
        self._init_signals()
        self._refresh_stats()
        
        # 定时刷新
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_queue_status)
        self._timer.start(2000)
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 1. 批量审核标签页
        self.tabs.addTab(self._create_review_tab(), "📋 批量审核")
        
        # 2. 报告管理标签页
        self.tabs.addTab(self._create_reports_tab(), "📊 报告管理")
        
        # 3. 文件分析标签页
        self.tabs.addTab(self._create_activity_tab(), "📁 文件分析")
        
        # 4. 清理管理标签页
        self.tabs.addTab(self._create_cleanup_tab(), "🧹 清理管理")
        
        # 5. 系统概览标签页
        self.tabs.addTab(self._create_overview_tab(), "📈 系统概览")
        
        layout.addWidget(self.tabs)
    
    def _create_review_tab(self) -> QWidget:
        """创建批量审核标签页"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # 左侧：文档列表
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # 工具栏
        toolbar = QHBoxLayout()
        self.btn_add_files = QPushButton("添加文件")
        self.btn_add_folder = QPushButton("添加文件夹")
        self.btn_start_review = QPushButton("开始审核")
        self.btn_start_review.setStyleSheet("background: #22c55e; color: white;")
        toolbar.addWidget(self.btn_add_files)
        toolbar.addWidget(self.btn_add_folder)
        toolbar.addWidget(self.btn_start_review)
        toolbar.addStretch()
        left_layout.addLayout(toolbar)
        
        # 文件列表
        self.review_file_list = QListWidget()
        self.review_file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        left_layout.addWidget(QLabel("待审核文档:"))
        left_layout.addWidget(self.review_file_list)
        
        # 审核设置
        settings_group = QGroupBox("审核设置")
        settings_layout = QFormLayout(settings_group)
        
        self.review_level_combo = QComboBox()
        self.review_level_combo.addItems(["快速审核", "标准审核", "深度审核", "专业审核"])
        self.review_level_combo.setCurrentIndex(1)
        settings_layout.addRow("审核级别:", self.review_level_combo)
        
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 10)
        self.priority_spin.setValue(5)
        settings_layout.addRow("优先级:", self.priority_spin)
        
        left_layout.addWidget(settings_group)
        
        # 右侧：任务状态
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        right_layout.addWidget(QLabel("审核进度:"))
        
        # 总进度
        progress_group = QGroupBox("总体进度")
        progress_layout = QVBoxLayout(progress_group)
        self.total_progress = QProgressBar()
        progress_layout.addWidget(self.total_progress)
        self.progress_label = QLabel("0 / 0")
        progress_layout.addWidget(self.progress_label)
        right_layout.addWidget(progress_group)
        
        # 任务列表
        right_layout.addWidget(QLabel("任务列表:"))
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(5)
        self.task_table.setHorizontalHeaderLabels(["任务ID", "文档", "状态", "进度", "操作"])
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.task_table.setMaximumHeight(300)
        right_layout.addWidget(self.task_table)
        
        # 实时日志
        right_layout.addWidget(QLabel("处理日志:"))
        self.review_log = QTextEdit()
        self.review_log.setMaximumHeight(150)
        self.review_log.setReadOnly(True)
        right_layout.addWidget(self.review_log)
        
        layout.addWidget(left_panel, 1)
        layout.addWidget(right_panel, 2)
        
        return widget
    
    def _create_reports_tab(self) -> QWidget:
        """创建报告管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 工具栏
        toolbar = QHBoxLayout()
        self.btn_refresh_reports = QPushButton("刷新")
        self.btn_view_report = QPushButton("查看报告")
        self.btn_download_report = QPushButton("下载")
        self.btn_generate_summary = QPushButton("生成汇总")
        self.btn_export_reports = QPushButton("导出")
        toolbar.addWidget(self.btn_refresh_reports)
        toolbar.addWidget(self.btn_view_report)
        toolbar.addWidget(self.btn_download_report)
        toolbar.addWidget(self.btn_generate_summary)
        toolbar.addWidget(self.btn_export_reports)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # 报告列表
        self.reports_table = QTableWidget()
        self.reports_table.setColumnCount(6)
        self.reports_table.setHorizontalHeaderLabels(["报告ID", "标题", "格式", "大小", "生成时间", "下载次数"])
        self.reports_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.reports_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.reports_table.itemDoubleClicked.connect(self._on_view_report)
        layout.addWidget(self.reports_table)
        
        # 报告预览
        preview_group = QGroupBox("报告预览")
        preview_layout = QVBoxLayout(preview_group)
        self.report_preview = QTextEdit()
        self.report_preview.setReadOnly(True)
        preview_layout.addWidget(self.report_preview)
        layout.addWidget(preview_group, 1)
        
        return widget
    
    def _create_activity_tab(self) -> QWidget:
        """创建文件分析标签页"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # 左侧：目录选择
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        left_layout.addWidget(QLabel("分析目录:"))
        path_layout = QHBoxLayout()
        self.activity_path = QLineEdit()
        self.activity_path.setText(str(Path.home()))
        path_layout.addWidget(self.activity_path)
        self.btn_browse_dir = QPushButton("浏览")
        path_layout.addWidget(self.btn_browse_dir)
        left_layout.addLayout(path_layout)
        
        self.btn_analyze = QPushButton("开始分析")
        self.btn_analyze.setStyleSheet("background: #3b82f6; color: white;")
        left_layout.addWidget(self.btn_analyze)
        
        # 活跃度分布
        activity_group = QGroupBox("活跃度分布")
        activity_layout = QVBoxLayout(activity_group)
        
        self.activity_stats = QFormLayout()
        self.high_count = QLabel("0")
        self.medium_high_count = QLabel("0")
        self.medium_count = QLabel("0")
        self.low_count = QLabel("0")
        self.inactive_count = QLabel("0")
        
        self.activity_stats.addRow("高活跃度 (80-100):", self.high_count)
        self.activity_stats.addRow("中高活跃度 (60-79):", self.medium_high_count)
        self.activity_stats.addRow("中活跃度 (40-59):", self.medium_count)
        self.activity_stats.addRow("低活跃度 (20-39):", self.low_count)
        self.activity_stats.addRow("非活跃 (0-19):", self.inactive_count)
        activity_layout.addLayout(self.activity_stats)
        left_layout.addWidget(activity_group)
        
        # 右侧：文件列表
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        right_layout.addWidget(QLabel("文件列表 (按活跃度排序):"))
        
        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(5)
        self.activity_table.setHorizontalHeaderLabels(["文件名", "活跃度", "评分", "类型", "大小"])
        self.activity_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.activity_table.setMaximumHeight(400)
        right_layout.addWidget(self.activity_table)
        
        # 建议
        suggestion_group = QGroupBox("清理建议")
        suggestion_layout = QVBoxLayout(suggestion_group)
        self.suggestion_text = QTextEdit()
        self.suggestion_text.setMaximumHeight(150)
        suggestion_layout.addWidget(self.suggestion_text)
        right_layout.addWidget(suggestion_group)
        
        layout.addWidget(left_panel, 1)
        layout.addWidget(right_panel, 2)
        
        return widget
    
    def _create_cleanup_tab(self) -> QWidget:
        """创建清理管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 规则管理
        rules_group = QGroupBox("清理规则")
        rules_layout = QVBoxLayout(rules_group)
        
        rules_toolbar = QHBoxLayout()
        self.btn_add_rule = QPushButton("添加规则")
        self.btn_edit_rule = QPushButton("编辑规则")
        self.btn_delete_rule = QPushButton("删除规则")
        self.btn_execute_cleanup = QPushButton("执行清理")
        self.btn_execute_cleanup.setStyleSheet("background: #ef4444; color: white;")
        rules_toolbar.addWidget(self.btn_add_rule)
        rules_toolbar.addWidget(self.btn_edit_rule)
        rules_toolbar.addWidget(self.btn_delete_rule)
        rules_toolbar.addStretch()
        rules_toolbar.addWidget(self.btn_execute_cleanup)
        rules_layout.addLayout(rules_toolbar)
        
        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(4)
        self.rules_table.setHorizontalHeaderLabels(["规则名称", "操作", "启用", "触发条件"])
        self.rules_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        rules_layout.addWidget(self.rules_table)
        
        layout.addWidget(rules_group)
        
        # 历史记录
        history_group = QGroupBox("清理历史")
        history_layout = QVBoxLayout(history_group)
        
        history_toolbar = QHBoxLayout()
        self.btn_refresh_history = QPushButton("刷新")
        self.btn_restore = QPushButton("恢复文件")
        history_toolbar.addWidget(self.btn_refresh_history)
        history_toolbar.addWidget(self.btn_restore)
        history_toolbar.addStretch()
        history_layout.addLayout(history_toolbar)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["时间", "文件", "操作", "状态", "释放空间"])
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        history_layout.addWidget(self.history_table)
        
        layout.addWidget(history_group, 1)
        
        return widget
    
    def _create_overview_tab(self) -> QWidget:
        """创建系统概览标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 统计卡片
        stats_layout = QHBoxLayout()
        
        self.doc_count_label = self._create_stat_card("📄", "文档总数", "0")
        self.task_count_label = self._create_stat_card("⏳", "待处理任务", "0")
        self.completed_count_label = self._create_stat_card("✅", "已完成任务", "0")
        self.failed_count_label = self._create_stat_card("❌", "失败任务", "0")
        self.avg_score_label = self._create_stat_card("📊", "平均质量分", "0")
        self.report_count_label = self._create_stat_card("📋", "报告总数", "0")
        
        stats_layout.addWidget(self.doc_count_label)
        stats_layout.addWidget(self.task_count_label)
        stats_layout.addWidget(self.completed_count_label)
        stats_layout.addWidget(self.failed_count_label)
        stats_layout.addWidget(self.avg_score_label)
        stats_layout.addWidget(self.report_count_label)
        
        layout.addLayout(stats_layout)
        
        # 队列状态
        queue_group = QGroupBox("任务队列状态")
        queue_layout = QVBoxLayout(queue_group)
        
        queue_info_layout = QFormLayout()
        self.queue_size_label = QLabel("0")
        self.running_count_label = QLabel("0")
        self.queued_count_label = QLabel("0")
        
        queue_info_layout.addRow("队列大小:", self.queue_size_label)
        queue_info_layout.addRow("运行中:", self.running_count_label)
        queue_info_layout.addRow("等待中:", self.queued_count_label)
        queue_layout.addLayout(queue_info_layout)
        
        layout.addWidget(queue_group)
        
        # 最近审核结果
        recent_group = QGroupBox("最近审核结果")
        recent_layout = QVBoxLayout(recent_group)
        
        self.recent_results_table = QTableWidget()
        self.recent_results_table.setColumnCount(5)
        self.recent_results_table.setHorizontalHeaderLabels(["文档", "质量分", "分类", "问题数", "建议数"])
        self.recent_results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        recent_layout.addWidget(self.recent_results_table)
        
        layout.addWidget(recent_group, 1)
        
        return widget
    
    def _create_stat_card(self, icon: str, title: str, value: str) -> QWidget:
        """创建统计卡片"""
        card = QWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel(f"<h1>{icon}</h1>")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_label)
        
        value_label = QLabel(f"<h2>{value}</h2>")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setObjectName("stat_value")
        card_layout.addWidget(value_label)
        
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #666; font-size: 12px;")
        card_layout.addWidget(title_label)
        
        card.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 8px;
                padding: 15px;
                border: 1px solid #e5e7eb;
            }
            QLabel#stat_value {
                color: #3b82f6;
            }
        """)
        
        return card
    
    def _init_signals(self):
        """初始化信号连接"""
        # 批量审核
        self.btn_add_files.clicked.connect(self._on_add_files)
        self.btn_add_folder.clicked.connect(self._on_add_folder)
        self.btn_start_review.clicked.connect(self._on_start_review)
        
        # 报告管理
        self.btn_refresh_reports.clicked.connect(self._refresh_reports)
        self.btn_view_report.clicked.connect(self._on_view_report)
        self.btn_download_report.clicked.connect(self._on_download_report)
        self.btn_generate_summary.clicked.connect(self._on_generate_summary)
        self.btn_export_reports.clicked.connect(self._on_export_reports)
        
        # 文件分析
        self.btn_browse_dir.clicked.connect(self._on_browse_dir)
        self.btn_analyze.clicked.connect(self._on_analyze_activity)
        
        # 清理管理
        self.btn_add_rule.clicked.connect(self._on_add_rule)
        self.btn_edit_rule.clicked.connect(self._on_edit_rule)
        self.btn_delete_rule.clicked.connect(self._on_delete_rule)
        self.btn_execute_cleanup.clicked.connect(self._on_execute_cleanup)
        self.btn_refresh_history.clicked.connect(self._refresh_history)
        self.btn_restore.clicked.connect(self._on_restore_file)
        
        # 信号
        self._system.on_task_completed(self._on_task_completed)
    
    # ==================== 批量审核 ====================
    
    def _on_add_files(self):
        """添加文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择文档", str(Path.home()),
            "文档文件 (*.txt *.md *.pdf *.doc *.docx *.xls *.xlsx *.csv *.json *.xml *.html *.py *.js *.java);;所有文件 (*.*)"
        )
        
        for file_path in files:
            self.review_file_list.addItem(file_path)
    
    def _on_add_folder(self):
        """添加文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹", str(Path.home()))
        
        if folder:
            path = Path(folder)
            for file_path in path.rglob('*'):
                if file_path.is_file():
                    self.review_file_list.addItem(str(file_path))
    
    def _on_start_review(self):
        """开始审核"""
        items = [self.review_file_list.item(i).text() for i in range(self.review_file_list.count())]
        
        if not items:
            QMessageBox.warning(self, "警告", "请先添加要审核的文档")
            return
        
        level_map = {
            0: ReviewLevel.QUICK,
            1: ReviewLevel.STANDARD,
            2: ReviewLevel.DEEP,
            3: ReviewLevel.PROFESSIONAL
        }
        
        review_level = level_map.get(self.review_level_combo.currentIndex(), ReviewLevel.STANDARD)
        priority = self.priority_spin.value()
        
        # 提交审核
        task_ids = self._system.submit_review(items, review_level, priority)
        
        self._refresh_task_table()
        self.review_log.append(f"已提交 {len(task_ids)} 个审核任务")
        
        # 清空列表
        self.review_file_list.clear()
    
    def _refresh_task_table(self):
        """刷新任务表"""
        status = self._system.get_queue_status()
        
        tasks = self._system._scheduler.get_all_tasks()
        
        self.task_table.setRowCount(len(tasks))
        
        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == ReviewStatus.COMPLETED)
        
        self.total_progress.setValue(int(completed / total * 100) if total > 0 else 0)
        self.progress_label.setText(f"{completed} / {total}")
        
        for i, task in enumerate(tasks):
            self.task_table.setItem(i, 0, QTableWidgetItem(task.task_id[:16]))
            self.task_table.setItem(i, 1, QTableWidgetItem(
                task.doc_info.file_name if task.doc_info else task.doc_id[:16]
            ))
            
            status_item = QTableWidgetItem(task.status.value)
            if task.status == ReviewStatus.COMPLETED:
                status_item.setBackground(Qt.GlobalColor.green)
            elif task.status == ReviewStatus.FAILED:
                status_item.setBackground(Qt.GlobalColor.red)
            elif task.status == ReviewStatus.PROCESSING:
                status_item.setBackground(Qt.GlobalColor.yellow)
            self.task_table.setItem(i, 2, status_item)
            
            progress_item = QTableWidgetItem(f"{task.progress * 100:.0f}%")
            self.task_table.setItem(i, 3, progress_item)
            
            # 操作按钮
            if task.status == ReviewStatus.QUEUED:
                cancel_btn = QPushButton("取消")
                cancel_btn.clicked.connect(lambda _, tid=task.task_id: self._on_cancel_task(tid))
                self.task_table.setCellWidget(i, 4, cancel_btn)
    
    def _on_cancel_task(self, task_id: str):
        """取消任务"""
        if self._system.cancel_task(task_id):
            self._refresh_task_table()
            self.review_log.append(f"已取消任务: {task_id[:16]}")
    
    def _on_task_completed(self, task):
        """任务完成回调"""
        self._refresh_task_table()
        self._refresh_stats()
        self.review_log.append(f"任务完成: {task.task_id[:16]}")
    
    # ==================== 报告管理 ====================
    
    def _refresh_reports(self):
        """刷新报告列表"""
        reports = self._system.get_reports()
        
        self.reports_table.setRowCount(len(reports))
        
        for i, report in enumerate(reports):
            self.reports_table.setItem(i, 0, QTableWidgetItem(report.report_id[:16]))
            self.reports_table.setItem(i, 1, QTableWidgetItem(report.title))
            self.reports_table.setItem(i, 2, QTableWidgetItem(report.report_format))
            self.reports_table.setItem(i, 3, QTableWidgetItem(self._format_size(report.file_size)))
            self.reports_table.setItem(i, 4, QTableWidgetItem(
                report.created_at.strftime("%Y-%m-%d %H:%M")
            ))
            self.reports_table.setItem(i, 5, QTableWidgetItem(str(report.download_count)))
    
    def _on_view_report(self):
        """查看报告"""
        row = self.reports_table.currentRow()
        if row < 0:
            return
        
        report_id = self.reports_table.item(row, 0).text()
        reports = self._system.get_reports()
        
        for report in reports:
            if report.report_id.startswith(report_id):
                if report.file_path:
                    webbrowser.open(f"file://{report.file_path}")
                break
    
    def _on_download_report(self):
        """下载报告"""
        row = self.reports_table.currentRow()
        if row < 0:
            return
        
        report_id = self.reports_table.item(row, 0).text()
        reports = self._system.get_reports()
        
        for report in reports:
            if report.report_id.startswith(report_id):
                save_path, _ = QFileDialog.getSaveFileName(
                    self, "保存报告", report.title,
                    f"报告文件 (*{report.report_format});;所有文件 (*.*)"
                )
                if save_path:
                    import shutil
                    shutil.copy(report.file_path, save_path)
                    QMessageBox.information(self, "成功", "报告已保存")
                break
    
    def _on_generate_summary(self):
        """生成汇总报告"""
        task_ids = [t.task_id for t in self._system._scheduler.get_all_tasks() 
                   if t.status == ReviewStatus.COMPLETED]
        
        if not task_ids:
            QMessageBox.warning(self, "警告", "没有已完成的任务")
            return
        
        report = self._system.generate_batch_summary(task_ids[:20])
        
        if report:
            self._refresh_reports()
            QMessageBox.information(self, "成功", "汇总报告已生成")
    
    def _on_export_reports(self):
        """导出报告"""
        selected_rows = set(index.row() for index in self.reports_table.selectedIndexes())
        
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请选择要导出的报告")
            return
        
        reports = self._system.get_reports()
        report_ids = [self.reports_table.item(row, 0).text() for row in selected_rows]
        
        export_path = self._system._report_gen.export_reports(report_ids)
        
        QMessageBox.information(self, "成功", f"已导出到: {export_path}")
    
    # ==================== 文件分析 ====================
    
    def _on_browse_dir(self):
        """浏览目录"""
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹", str(Path.home()))
        if folder:
            self.activity_path.setText(folder)
    
    def _on_analyze_activity(self):
        """分析活跃度"""
        directory = self.activity_path.text()
        
        if not directory or not Path(directory).exists():
            QMessageBox.warning(self, "警告", "请选择有效的目录")
            return
        
        # 显示进度
        progress = QProgressDialog("正在分析文件...", "取消", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        # 获取文件列表
        file_paths = [str(p) for p in Path(directory).rglob('*') if p.is_file()][:1000]
        
        # 批量评估
        activities = self._system.batch_evaluate_activity(file_paths)
        
        # 更新统计
        counts = {
            ActivityLevel.HIGH: 0,
            ActivityLevel.MEDIUM_HIGH: 0,
            ActivityLevel.MEDIUM: 0,
            ActivityLevel.LOW: 0,
            ActivityLevel.INACTIVE: 0
        }
        
        for activity in activities:
            counts[activity.activity_level] += 1
        
        self.high_count.setText(str(counts[ActivityLevel.HIGH]))
        self.medium_high_count.setText(str(counts[ActivityLevel.MEDIUM_HIGH]))
        self.medium_count.setText(str(counts[ActivityLevel.MEDIUM]))
        self.low_count.setText(str(counts[ActivityLevel.LOW]))
        self.inactive_count.setText(str(counts[ActivityLevel.INACTIVE]))
        
        # 更新表格
        self.activity_table.setRowCount(len(activities))
        
        sorted_activities = sorted(activities, key=lambda x: x.total_score)
        
        for i, activity in enumerate(sorted_activities[:100]):
            self.activity_table.setItem(i, 0, QTableWidgetItem(activity.file_name))
            
            level_item = QTableWidgetItem(activity.activity_level.value)
            if activity.activity_level == ActivityLevel.HIGH:
                level_item.setBackground(Qt.GlobalColor.green)
            elif activity.activity_level == ActivityLevel.LOW:
                level_item.setBackground(Qt.GlobalColor.red)
            elif activity.activity_level == ActivityLevel.INACTIVE:
                level_item.setBackground(Qt.GlobalColor.darkRed)
                level_item.setForeground(Qt.GlobalColor.white)
            self.activity_table.setItem(i, 1, level_item)
            
            self.activity_table.setItem(i, 2, QTableWidgetItem(f"{activity.total_score:.1f}"))
            self.activity_table.setItem(i, 3, QTableWidgetItem(activity.file_type.value))
            self.activity_table.setItem(i, 4, QTableWidgetItem(self._format_size(activity.file_size)))
        
        # 清理建议
        cleanup_candidates = [a for a in sorted_activities if a.total_score < 20]
        suggestion_text = f"发现 {len(cleanup_candidates)} 个可清理文件\n\n"
        suggestion_text += "建议清理操作:\n"
        suggestion_text += "- 删除评分低于10的非活跃文件\n"
        suggestion_text += "- 归档30天以上未访问的文件\n"
        suggestion_text += "- 清理临时文件"
        
        self.suggestion_text.setText(suggestion_text)
        
        progress.close()
    
    # ==================== 清理管理 ====================
    
    def _refresh_rules(self):
        """刷新规则列表"""
        rules = self._system.get_cleanup_rules()
        
        self.rules_table.setRowCount(len(rules))
        
        for i, rule in enumerate(rules):
            self.rules_table.setItem(i, 0, QTableWidgetItem(rule.name))
            self.rules_table.setItem(i, 1, QTableWidgetItem(rule.action))
            
            enabled_item = QTableWidgetItem("是" if rule.enabled else "否")
            enabled_item.setBackground(Qt.GlobalColor.green if rule.enabled else Qt.GlobalColor.red)
            self.rules_table.setItem(i, 2, enabled_item)
            
            condition = f"评分: {rule.min_activity_score}-{rule.max_activity_score}"
            if rule.min_file_age_days > 0:
                condition += f", 文件年龄: >{rule.min_file_age_days}天"
            self.rules_table.setItem(i, 3, QTableWidgetItem(condition))
    
    def _refresh_history(self):
        """刷新历史"""
        history = self._system.get_cleanup_history()
        
        self.history_table.setRowCount(len(history))
        
        for i, item in enumerate(history):
            from datetime import datetime
            exec_time = datetime.fromtimestamp((item["executed_at"] - 2440587.5) * 86400) if item["executed_at"] else datetime.now()
            
            self.history_table.setItem(i, 0, QTableWidgetItem(exec_time.strftime("%Y-%m-%d %H:%M")))
            self.history_table.setItem(i, 1, QTableWidgetItem(Path(item["file_path"]).name))
            self.history_table.setItem(i, 2, QTableWidgetItem(item["action"]))
            self.history_table.setItem(i, 3, QTableWidgetItem(item["status"]))
            self.history_table.setItem(i, 4, QTableWidgetItem(self._format_size(item["space_freed"] or 0)))
    
    def _on_add_rule(self):
        """添加规则"""
        QMessageBox.information(self, "提示", "规则编辑对话框 - 功能开发中")
    
    def _on_edit_rule(self):
        """编辑规则"""
        QMessageBox.information(self, "提示", "规则编辑对话框 - 功能开发中")
    
    def _on_delete_rule(self):
        """删除规则"""
        row = self.rules_table.currentRow()
        if row < 0:
            return
        
        rule_name = self.rules_table.item(row, 0).text()
        
        reply = QMessageBox.question(self, "确认", f"确定删除规则 '{rule_name}' 吗?")
        if reply == QMessageBox.StandardButton.Yes:
            rules = self._system.get_cleanup_rules()
            for rule in rules:
                if rule.name == rule_name:
                    self._system._cleanup_mgr.delete_rule(rule.rule_id)
                    break
            self._refresh_rules()
    
    def _on_execute_cleanup(self):
        """执行清理"""
        directory = self.activity_path.text()
        
        # 模拟清理（干运行）
        result = self._system.execute_cleanup([], dry_run=True)
        
        QMessageBox.information(
            self, "清理预览",
            f"将清理 {result['total']} 个文件\n"
            f"预计释放空间: {self._format_size(result.get('space_freed', 0))}"
        )
    
    def _on_restore_file(self):
        """恢复文件"""
        QMessageBox.information(self, "提示", "文件恢复功能 - 功能开发中")
    
    # ==================== 系统概览 ====================
    
    def _refresh_stats(self):
        """刷新统计"""
        stats = self._system.get_stats()
        
        # 更新统计卡片
        doc_count_card = self.doc_count_label.findChild(QLabel, "stat_value")
        if doc_count_card:
            doc_count_card.setText(str(stats.get("total_documents", 0)))
        
        # 更新概览标签
        for card, key in [
            (self.doc_count_label, "total_documents"),
            (self.task_count_label, "total_tasks"),
            (self.completed_count_label, "completed_tasks"),
            (self.failed_count_label, "failed_tasks"),
            (self.avg_score_label, "avg_quality_score"),
            (self.report_count_label, "total_reports")
        ]:
            value_label = card.findChild(QLabel, "stat_value")
            if value_label:
                value = stats.get(key, 0)
                if isinstance(value, float):
                    value_label.setText(f"{value:.1f}")
                else:
                    value_label.setText(str(value))
        
        # 更新队列状态
        queue_status = self._system.get_queue_status()
        self.queue_size_label.setText(str(queue_status.get("queue_size", 0)))
        self.running_count_label.setText(str(queue_status.get("running_count", 0)))
        self.queued_count_label.setText(str(queue_status.get("queued_count", 0)))
        
        # 最近结果
        results = self._system.get_results()
        
        self.recent_results_table.setRowCount(min(len(results), 10))
        
        for i, result in enumerate(results[:10]):
            self.recent_results_table.setItem(i, 0, QTableWidgetItem(result.doc_id[:16]))
            
            score_item = QTableWidgetItem(f"{result.quality_score:.1f}")
            if result.quality_score >= 80:
                score_item.setBackground(Qt.GlobalColor.green)
            elif result.quality_score < 60:
                score_item.setBackground(Qt.GlobalColor.red)
            self.recent_results_table.setItem(i, 1, score_item)
            
            self.recent_results_table.setItem(i, 2, QTableWidgetItem(result.category))
            self.recent_results_table.setItem(i, 3, QTableWidgetItem(str(len(result.issues))))
            self.recent_results_table.setItem(i, 4, QTableWidgetItem(str(len(result.suggestions))))
    
    def _refresh_queue_status(self):
        """定时刷新队列状态"""
        try:
            queue_status = self._system.get_queue_status()
            self.queue_size_label.setText(str(queue_status.get("queue_size", 0)))
            self.running_count_label.setText(str(queue_status.get("running_count", 0)))
            self.queued_count_label.setText(str(queue_status.get("queued_count", 0)))
            self._refresh_task_table()
        except:
            pass
    
    # ==================== 工具方法 ====================
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"
