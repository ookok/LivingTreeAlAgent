# -*- coding: utf-8 -*-
"""
智能写作面板 - Smart Writing Panel (R5 重构版)
==============================================

职责：
1. UI 展示（PyQt6）
2. 事件转发到 SmartWritingWorkflow
3. 结果展示

业务逻辑已委托给 core.smart_writing.unified_workflow.SmartWritingWorkflow

Author: Hermes Desktop Team
"""

import json
import logging
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 工作线程 - 业务逻辑分离
# =============================================================================

class WritingWorker(QThread):
    """写作工作线程 - 封装 SmartWritingWorkflow 调用"""
    
    progress = pyqtSignal(int, str, str)  # progress, stage, message
    score_updated = pyqtSignal(float)  # 评分更新
    content_ready = pyqtSignal(dict)  # 内容就绪
    issues_updated = pyqtSignal(list)  # 问题列表更新
    completed = pyqtSignal(dict)  # 完成
    error = pyqtSignal(str)
    
    def __init__(self, workflow, requirement, document_type, config, project_name=""):
        super().__init__()
        self.workflow = workflow
        self.requirement = requirement
        self.document_type = document_type
        self.project_name = project_name
        self.config = config
    
    def run(self):
        try:
            def progress_callback(stage, progress_pct, message):
                self.progress.emit(progress_pct, stage.value, message)
            
            result = self.workflow.execute(
                requirement=self.requirement,
                document_type=self.document_type,
                project_name=self.project_name,
                config=self.config,
                progress_callback=progress_callback,
            )
            
            # 发送结果
            self.score_updated.emit(result.review_score)
            self.content_ready.emit(result.final_content)
            self.issues_updated.emit(result.review_issues)
            self.completed.emit(result.to_dict())
            
        except Exception as e:
            logger.error(f"写作失败: {e}")
            self.error.emit(str(e))


# =============================================================================
# 虚拟会议对话框
# =============================================================================

class VirtualMeetingDialog(QDialog):
    """虚拟会议对话框"""
    
    def __init__(self, meeting_data: dict, parent=None):
        super().__init__(parent)
        self.meeting_data = meeting_data
        self.setWindowTitle("Virtual Meeting")
        self.setMinimumSize(600, 500)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel(f"Meeting: {self.meeting_data.get('meeting_id', '')}")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Participants
        participants_group = QGroupBox("Participants")
        participants_layout = QVBoxLayout(participants_group)
        for p in self.meeting_data.get("participants", []):
            participants_layout.addWidget(
                QLabel(f"  {p.get('role', '')}: {p.get('name', '')}")
            )
        layout.addWidget(participants_group)
        
        # Agenda
        agenda_group = QGroupBox("Agenda")
        agenda_layout = QVBoxLayout(agenda_group)
        for i, item in enumerate(self.meeting_data.get("agenda", []), 1):
            agenda_layout.addWidget(QLabel(f"  {i}. {item}"))
        layout.addWidget(agenda_group)
        
        # Transcript
        transcript_group = QGroupBox("Transcript")
        transcript_layout = QVBoxLayout(transcript_group)
        transcript_text = QTextEdit()
        transcript_text.setReadOnly(True)
        for entry in self.meeting_data.get("transcript", []):
            speaker = entry.get("speaker", "")
            content = entry.get("content", "")
            transcript_text.append(f"<b>[{speaker}]</b> {content}")
        transcript_layout.addWidget(transcript_text)
        layout.addWidget(transcript_group)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


# =============================================================================
# 智能写作面板 - R5 重构版
# =============================================================================

class SmartWritingPanel(QWidget):
    """
    智能写作面板（R5 重构版）
    
    特点：
    1. UI 简化 - 只负责展示和交互
    2. 业务委托 - 核心逻辑在 SmartWritingWorkflow
    3. 易于测试 - 工作线程独立测试
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker: Optional[WritingWorker] = None
        self._workflow = None
        self._review_result = None
        self._setup_workflow()
        self._setup_ui()
    
    def _setup_workflow(self):
        """初始化业务引擎（延迟加载）"""
        try:
            from core.smart_writing.unified_workflow import (
                SmartWritingWorkflow,
                WritingConfig,
            )
            self._workflow = SmartWritingWorkflow()
            self._writing_config_class = WritingConfig
        except ImportError as e:
            logger.warning(f"SmartWritingWorkflow 加载失败: {e}")
            self._workflow = None
    
    def _setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab widget
        tab_widget = QTabWidget()
        tab_widget.addTab(self._create_input_tab(), "Input")
        tab_widget.addTab(self._create_review_tab(), "Review")
        tab_widget.addTab(self._create_issues_tab(), "Issues")
        tab_widget.addTab(self._create_report_tab(), "Report")
        
        main_layout.addWidget(tab_widget)
    
    def _create_input_tab(self) -> QWidget:
        """创建输入标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Project info
        scroll_layout.addWidget(self._create_project_group())
        
        # AI config
        scroll_layout.addWidget(self._create_ai_config_group())
        
        # Debate config
        scroll_layout.addWidget(self._create_debate_config_group())
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Action buttons
        layout.addWidget(self._create_action_buttons())
        
        return widget
    
    def _create_project_group(self) -> QGroupBox:
        """创建项目信息组"""
        group = QGroupBox("Project Information")
        layout = QVBoxLayout(group)
        
        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("Project name")
        layout.addWidget(QLabel("Project Name:"))
        layout.addWidget(self.project_name_edit)
        
        self.doc_type_combo = QComboBox()
        self.doc_type_combo.addItems([
            "general",
            "feasibility_report",
            "eia_report",
            "safety_assessment",
            "financial_analysis",
        ])
        layout.addWidget(QLabel("Document Type:"))
        layout.addWidget(self.doc_type_combo)
        
        self.requirement_edit = QPlainTextEdit()
        self.requirement_edit.setPlaceholderText("Enter your writing requirement...")
        self.requirement_edit.setMaximumHeight(120)
        layout.addWidget(QLabel("Requirement:"))
        layout.addWidget(self.requirement_edit)
        
        return group
    
    def _create_ai_config_group(self) -> QGroupBox:
        """创建AI配置组"""
        group = QGroupBox("AI Configuration")
        layout = QVBoxLayout(group)
        
        self.enable_review_cb = QCheckBox("Enable AI Review")
        self.enable_review_cb.setChecked(True)
        layout.addWidget(self.enable_review_cb)
        
        self.enable_debate_cb = QCheckBox("Enable Debate")
        self.enable_debate_cb.setChecked(True)
        layout.addWidget(self.enable_debate_cb)
        
        self.enable_meeting_cb = QCheckBox("Enable Virtual Meeting")
        self.enable_meeting_cb.setChecked(False)
        layout.addWidget(self.enable_meeting_cb)
        
        return group
    
    def _create_debate_config_group(self) -> QGroupBox:
        """创建辩论配置组"""
        group = QGroupBox("Debate Configuration")
        layout = QFormLayout(group)
        
        self.debate_rounds_spin = QSpinBox()
        self.debate_rounds_spin.setRange(1, 10)
        self.debate_rounds_spin.setValue(3)
        layout.addRow("Debate Rounds:", self.debate_rounds_spin)
        
        return group
    
    def _create_action_buttons(self) -> QWidget:
        """创建操作按钮"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 10)
        
        self.start_btn = QPushButton("Start Writing")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self.start_btn.clicked.connect(self._on_start)
        layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.clicked.connect(self._on_stop)
        layout.addWidget(self.stop_btn)
        
        return widget
    
    def _create_review_tab(self) -> QWidget:
        """创建审核标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Progress
        self.review_progress_label = QLabel("Ready")
        layout.addWidget(self.review_progress_label)
        
        self.review_progress_bar = QProgressBar()
        self.review_progress_bar.setMinimum(0)
        self.review_progress_bar.setMaximum(100)
        layout.addWidget(self.review_progress_bar)
        
        # Score
        score_group = QGroupBox("Review Score")
        score_layout = QVBoxLayout(score_group)
        
        self.score_label = QLabel("0 / 100")
        self.score_label.setFont(QFont("Microsoft YaHei", 24, QFont.Bold))
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(self.score_label)
        
        self.conclusion_label = QLabel("Pending")
        self.conclusion_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout.addWidget(self.conclusion_label)
        
        layout.addWidget(score_group)
        
        # Content preview
        content_group = QGroupBox("Content Preview")
        content_layout = QVBoxLayout(content_group)
        
        self.content_preview = QTextEdit()
        self.content_preview.setReadOnly(True)
        content_layout.addWidget(self.content_preview)
        
        layout.addWidget(content_group)
        
        return widget
    
    def _create_issues_tab(self) -> QWidget:
        """创建问题标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.issues_tree = QTreeWidget()
        self.issues_tree.setHeaderLabels(["Severity", "Section", "Description"])
        self.issues_tree.setColumnWidth(0, 80)
        self.issues_tree.setColumnWidth(1, 120)
        self.issues_tree.setColumnWidth(2, 350)
        layout.addWidget(self.issues_tree)
        
        return widget
    
    def _create_report_tab(self) -> QWidget:
        """创建报告标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Opinion
        opinion_group = QGroupBox("Professional Opinion")
        opinion_layout = QVBoxLayout(opinion_group)
        
        self.opinion_text = QTextEdit()
        self.opinion_text.setReadOnly(True)
        opinion_layout.addWidget(self.opinion_text)
        
        layout.addWidget(opinion_group)
        
        # Export button
        export_btn = QPushButton("Export Report")
        export_btn.clicked.connect(self._on_export)
        layout.addWidget(export_btn)
        
        return widget
    
    # ── 事件处理 ─────────────────────────────────────────────────────────
    
    def _on_start(self):
        """开始写作"""
        requirement = self.requirement_edit.toPlainText().strip()
        if not requirement:
            QMessageBox.warning(self, "Error", "Please enter a requirement")
            return
        
        if not self._workflow:
            QMessageBox.warning(self, "Error", "SmartWritingWorkflow not available")
            return
        
        # Build config
        config = self._writing_config_class(
            enable_ai_review=self.enable_review_cb.isChecked(),
            enable_debate=self.enable_debate_cb.isChecked(),
            enable_virtual_meeting=self.enable_meeting_cb.isChecked(),
            debate_rounds=self.debate_rounds_spin.value(),
        )
        
        # Update UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._clear_results()
        
        # Start worker
        self.worker = WritingWorker(
            workflow=self._workflow,
            requirement=requirement,
            document_type=self.doc_type_combo.currentText(),
            project_name=self.project_name_edit.text(),
            config=config,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.score_updated.connect(self._on_score_updated)
        self.worker.content_ready.connect(self._on_content_ready)
        self.worker.issues_updated.connect(self._on_issues_updated)
        self.worker.completed.connect(self._on_completed)
        self.worker.error.connect(self._on_error)
        self.worker.start()
    
    def _on_stop(self):
        """停止写作"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self._on_finished()
            self.review_progress_label.setText("Stopped")
    
    def _on_finished(self):
        """结束"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
    
    def _on_progress(self, progress: int, stage: str, message: str):
        """进度更新"""
        self.review_progress_bar.setValue(progress)
        self.review_progress_label.setText(message)
    
    def _on_score_updated(self, score: float):
        """评分更新"""
        self.score_label.setText(f"{score:.1f} / 100")
        
        if score >= 90:
            self.conclusion_label.setText("Excellent")
        elif score >= 75:
            self.conclusion_label.setText("Good")
        elif score >= 60:
            self.conclusion_label.setText("Needs Improvement")
        else:
            self.conclusion_label.setText("Poor")
    
    def _on_content_ready(self, content: dict):
        """内容就绪"""
        if content:
            # Format and display
            lines = []
            cover = content.get("cover", {})
            if cover.get("title"):
                lines.append(f"# {cover['title']}")
                lines.append("")
            
            for section in content.get("sections", [])[:10]:
                title = section.get("title", "")
                lines.append(f"## {title}")
                lines.append("")
            
            self.content_preview.setPlainText("\n".join(lines))
    
    def _on_issues_updated(self, issues: list):
        """问题更新"""
        self.issues_tree.clear()
        
        severity_colors = {
            "critical": "#FF0000",
            "major": "#FF8C00",
            "moderate": "#FFD700",
            "minor": "#87CEEB",
        }
        
        for issue in issues:
            severity = issue.get("severity", "info")
            item = QTreeWidgetItem([
                severity.upper(),
                issue.get("section", ""),
                issue.get("description", ""),
            ])
            color = severity_colors.get(severity, "#000000")
            item.setForeground(0, QColor(color))
            self.issues_tree.addTopLevelItem(item)
    
    def _on_completed(self, result: dict):
        """完成"""
        self._review_result = result
        self._on_finished()
        
        # Show summary
        QMessageBox.information(
            self,
            "Completed",
            f"Writing completed!\n\n"
            f"Score: {result.get('review_score', 0):.1f}\n"
            f"Issues: {result.get('issues_count', 0)}\n"
            f"Confidence: {result.get('confidence', 0):.2f}"
        )
    
    def _on_error(self, error: str):
        """错误"""
        self._on_finished()
        QMessageBox.critical(self, "Error", f"Writing failed:\n{error}")
    
    def _on_export(self):
        """导出报告"""
        if not self._review_result:
            QMessageBox.information(self, "Info", "No result to export")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Report", "", "JSON (*.json);;Text (*.txt)"
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    if file_path.endswith(".json"):
                        json.dump(self._review_result, f, ensure_ascii=False, indent=2)
                    else:
                        f.write(json.dumps(self._review_result, ensure_ascii=False, indent=2))
                QMessageBox.information(self, "Success", f"Report exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed:\n{e}")
    
    def _clear_results(self):
        """清空结果"""
        self.issues_tree.clear()
        self.content_preview.clear()
        self.opinion_text.clear()
        self.score_label.setText("0 / 100")
        self.conclusion_label.setText("Pending")
        self.review_progress_bar.setValue(0)


# =============================================================================
# Factory
# =============================================================================

def create_smart_writing_panel() -> SmartWritingPanel:
    """创建智能写作面板"""
    return SmartWritingPanel()
