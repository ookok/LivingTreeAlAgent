# -*- coding: utf-8 -*-
"""
AI增强型项目生成面板
AI-Enhanced Project Generation Panel
====================================

功能：
- AI智能审核全流程可视化
- 数字分身辩论实时展示
- 虚拟会议评审界面
- 矛盾发现和深度辩论展示
- 专业审核意见自动生成
- 人性化操作界面

Author: Hermes Desktop Team
"""

import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QTextCharFormat
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
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
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


# =============================================================================
# AI增强审核工作线程
# =============================================================================

class AIReviewWorker(QThread):
    """AI增强审核工作线程"""
    progress_updated = pyqtSignal(int, str, str)
    stage_completed = pyqtSignal(str, dict)
    issue_found = pyqtSignal(dict)
    debate_round_updated = pyqtSignal(dict)
    meeting_started = pyqtSignal(dict)
    review_completed = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, engine, content, doc_type, config):
        super().__init__()
        self.engine = engine
        self.content = content
        self.doc_type = doc_type
        self.config = config
    
    def run(self):
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            def progress_callback(stage, progress_pct, message):
                self.progress_updated.emit(progress_pct, stage.value, message)
            
            result = loop.run_until_complete(
                self.engine.review_engine.run_full_review(
                    content=self.content,
                    doc_type=self.doc_type,
                    config=self.config,
                    progress_callback=progress_callback,
                )
            )
            
            loop.close()
            
            result_dict = {
                "review_id": result.review_id,
                "overall_score": result.overall_score,
                "conclusion": result.conclusion.value,
                "total_issues": result.total_issues,
                "issues": [
                    {
                        "issue_id": i.issue_id,
                        "section": i.section,
                        "type": i.issue_type,
                        "severity": i.severity.value,
                        "description": i.description,
                        "suggested_revision": i.suggested_revision,
                        "detected_by": i.detected_by,
                    }
                    for i in result.issues
                ],
                "conflicts": [
                    {
                        "conflict_id": c.conflict_id,
                        "type": c.conflict_type,
                        "severity": c.severity.value,
                        "explanation": c.explanation,
                    }
                    for c in result.conflicts
                ],
                "debate_records": [
                    {
                        "round": r.round_number,
                        "role": r.speaker_role.value,
                        "speaker": r.speaker_name,
                        "argument": r.argument,
                    }
                    for r in result.debate_records
                ],
                "debate_rounds": result.debate_rounds,
                "virtual_meetings": [
                    {
                        "meeting_id": m.meeting_id,
                        "type": m.meeting_type,
                        "participants": m.participants,
                        "summary": m.summary,
                        "conclusions": m.conclusions,
                    }
                    for m in result.virtual_meetings
                ],
                "professional_opinion": result.professional_opinion,
                "revision_suggestions": result.revision_suggestions,
                "knowledge_results": [
                    {
                        "query": k.query,
                        "source": k.source,
                        "summary": k.summary,
                    }
                    for k in result.knowledge_results
                ],
                "review_duration": result.review_duration,
            }
            
            self.review_completed.emit(result_dict)
            
        except Exception as e:
            logger.error(f"AI审核失败: {e}")
            self.error_occurred.emit(str(e))


# =============================================================================
# 虚拟电话/会议对话框
# =============================================================================

class VirtualMeetingDialog(QDialog):
    """虚拟会议对话框"""
    
    def __init__(self, meeting_data: Dict, parent=None):
        super().__init__(parent)
        self.meeting_data = meeting_data
        self.setWindowTitle("虚拟会议")
        self.setMinimumSize(600, 500)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        meeting_type = self.meeting_data.get("type", "review")
        meeting_id = self.meeting_data.get("meeting_id", "")
        
        title = QLabel(f"📞 虚拟会议 - {meeting_id}")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        participants_group = QGroupBox("参会人员")
        participants_layout = QVBoxLayout(participants_group)
        
        for p in self.meeting_data.get("participants", []):
            participant_label = QLabel(f"  {p.get('role', '')}: {p.get('name', '')}")
            participants_layout.addWidget(participant_label)
        
        layout.addWidget(participants_group)
        
        agenda_group = QGroupBox("议程")
        agenda_layout = QVBoxLayout(agenda_group)
        
        for i, item in enumerate(self.meeting_data.get("agenda", []), 1):
            agenda_label = QLabel(f"  {i}. {item}")
            agenda_layout.addWidget(agenda_label)
        
        layout.addWidget(agenda_group)
        
        transcript_group = QGroupBox("会议记录")
        transcript_layout = QVBoxLayout(transcript_group)
        
        self.transcript_text = QTextEdit()
        self.transcript_text.setReadOnly(True)
        
        for entry in self.meeting_data.get("transcript", []):
            speaker = entry.get("speaker", "")
            content = entry.get("content", "")
            self.transcript_text.append(f"<b>[{speaker}]</b> {content}")
        
        transcript_layout.addWidget(self.transcript_text)
        layout.addWidget(transcript_group)
        
        summary_group = QGroupBox("会议总结")
        summary_layout = QVBoxLayout(summary_group)
        
        summary_label = QLabel(self.meeting_data.get("summary", ""))
        summary_label.setWordWrap(True)
        summary_layout.addWidget(summary_label)
        
        conclusions = self.meeting_data.get("conclusions", [])
        if conclusions:
            conclusions_label = QLabel("\n".join(f"• {c}" for c in conclusions))
            conclusions_label.setWordWrap(True)
            summary_layout.addWidget(conclusions_label)
        
        layout.addWidget(summary_group)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


# =============================================================================
# AI增强型项目生成面板
# =============================================================================

class AIEnhancedGenerationPanel(QWidget):
    """AI增强型项目生成面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = None
        self.worker = None
        self._init_engine()
        self._setup_ui()
        self._review_result = None
    
    def _init_engine(self):
        """初始化AI增强引擎"""
        try:
            from core.smart_writing.ai_enhanced_generation import (
                get_ai_enhanced_project_engine,
                AIEnhancedGenerationConfig,
                AvatarRole,
            )
            self.engine = get_ai_enhanced_project_engine()
            self.AIEnhancedGenerationConfig = AIEnhancedGenerationConfig
            self.AvatarRole = AvatarRole
        except Exception as e:
            logger.warning(f"AI增强引擎加载失败: {e}")
            self.engine = None
    
    def _setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        tab_widget = QTabWidget()
        
        tab_widget.addTab(self._create_generation_tab(), "📝 文档生成")
        tab_widget.addTab(self._create_review_tab(), "🔍 智能审核")
        tab_widget.addTab(self._create_debate_tab(), "⚔️ 分身辩论")
        tab_widget.addTab(self._create_meeting_tab(), "📞 虚拟会议")
        tab_widget.addTab(self._create_report_tab(), "📊 审核报告")
        
        main_layout.addWidget(tab_widget)
    
    def _create_generation_tab(self) -> QWidget:
        """创建生成标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        scroll_layout.addWidget(self._create_input_group())
        scroll_layout.addWidget(self._create_ai_config_group())
        scroll_layout.addWidget(self._create_debate_config_group())
        scroll_layout.addWidget(self._create_knowledge_source_group())
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        layout.addWidget(self._create_action_buttons())
        
        return widget
    
    def _create_input_group(self) -> QGroupBox:
        """创建输入配置组"""
        group = QGroupBox("项目信息输入")
        layout = QFormLayout(group)
        
        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("请输入项目全称")
        layout.addRow("项目名称:", self.project_name_edit)
        
        self.doc_type_combo = QComboBox()
        self.doc_type_combo.addItems([
            "feasibility_report",
            "project_proposal",
            "eia_report",
            "environmental_emergency",
            "acceptance_monitoring",
            "pollution_permit",
            "pollution_survey",
            "safety_assessment",
            "financial_analysis",
            "legal_opinion",
            "compliance_report",
        ])
        layout.addRow("文档类型:", self.doc_type_combo)
        
        self.project_desc_edit = QPlainTextEdit()
        self.project_desc_edit.setPlaceholderText("项目描述（用于AI理解上下文）")
        self.project_desc_edit.setMaximumHeight(100)
        layout.addRow("项目描述:", self.project_desc_edit)
        
        return group
    
    def _create_ai_config_group(self) -> QGroupBox:
        """创建AI配置组"""
        group = QGroupBox("AI Agent配置")
        layout = QVBoxLayout(group)
        
        self.enable_ai_agent_cb = QCheckBox("启用AI Agent全方位辅助")
        self.enable_ai_agent_cb.setChecked(True)
        layout.addWidget(self.enable_ai_agent_cb)
        
        self.enable_smart_review_cb = QCheckBox("启用智能审核系统")
        self.enable_smart_review_cb.setChecked(True)
        layout.addWidget(self.enable_smart_review_cb)
        
        self.enable_conflict_cb = QCheckBox("启用矛盾自动检测")
        self.enable_conflict_cb.setChecked(True)
        layout.addWidget(self.enable_conflict_cb)
        
        self.enable_debate_cb = QCheckBox("启用数字分身辩论")
        self.enable_debate_cb.setChecked(True)
        layout.addWidget(self.enable_debate_cb)
        
        self.enable_virtual_review_cb = QCheckBox("启用虚拟会议评审")
        self.enable_virtual_review_cb.setChecked(True)
        layout.addWidget(self.enable_virtual_review_cb)
        
        self.enable_auto_revision_cb = QCheckBox("启用自动修改建议")
        self.enable_auto_revision_cb.setChecked(False)
        layout.addWidget(self.enable_auto_revision_cb)
        
        self.enable_virtual_phone_cb = QCheckBox("启用虚拟电话通知")
        self.enable_virtual_phone_cb.setChecked(False)
        layout.addWidget(self.enable_virtual_phone_cb)
        
        return group
    
    def _create_debate_config_group(self) -> QGroupBox:
        """创建辩论配置组"""
        group = QGroupBox("辩论配置")
        layout = QFormLayout(group)
        
        self.debate_rounds_spin = QSpinBox()
        self.debate_rounds_spin.setRange(1, 10)
        self.debate_rounds_spin.setValue(3)
        layout.addRow("辩论轮数:", self.debate_rounds_spin)
        
        self.debate_roles_list = QListWidget()
        self.debate_roles_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        
        debate_roles = [
            ("辩护专家", "defender"),
            ("质疑专家", "prosecutor"),
            ("环境专家", "expert_env"),
            ("安全专家", "expert_safety"),
            ("财务专家", "expert_finance"),
            ("法律专家", "expert_legal"),
            ("技术专家", "expert_tech"),
            ("政府代表", "government"),
        ]
        
        for name, role_id in debate_roles:
            item = QListWidgetItem(f"{name}")
            item.setData(Qt.ItemDataRole.UserRole, role_id)
            if role_id in ["defender", "prosecutor", "expert_env", "expert_safety"]:
                item.setSelected(True)
            self.debate_roles_list.addItem(item)
        
        layout.addRow("辩论参与者:", self.debate_roles_list)
        
        return group
    
    def _create_knowledge_source_group(self) -> QGroupBox:
        """创建知识源配置组"""
        group = QGroupBox("知识数据源")
        layout = QVBoxLayout(group)
        
        self.use_kb_cb = QCheckBox("使用本地知识库")
        self.use_kb_cb.setChecked(True)
        layout.addWidget(self.use_kb_cb)
        
        self.use_deep_search_cb = QCheckBox("使用深度搜索")
        self.use_deep_search_cb.setChecked(True)
        layout.addWidget(self.use_deep_search_cb)
        
        self.use_local_data_cb = QCheckBox("使用本地项目数据")
        self.use_local_data_cb.setChecked(True)
        layout.addWidget(self.use_local_data_cb)
        
        self.use_online_api_cb = QCheckBox("使用在线API数据")
        self.use_online_api_cb.setChecked(True)
        layout.addWidget(self.use_online_api_cb)
        
        return group
    
    def _create_action_buttons(self) -> QWidget:
        """创建操作按钮"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 10)
        
        self.start_btn = QPushButton("🚀 AI增强生成")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setMinimumHeight(45)
        self.start_btn.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        self.start_btn.clicked.connect(self._start_ai_generation)
        layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(45)
        self.stop_btn.clicked.connect(self._stop_ai_generation)
        layout.addWidget(self.stop_btn)
        
        return widget
    
    def _create_review_tab(self) -> QWidget:
        """创建审核标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.review_progress_label = QLabel("就绪")
        self.review_progress_label.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self.review_progress_label)
        
        self.review_progress_bar = QProgressBar()
        self.review_progress_bar.setMinimum(0)
        self.review_progress_bar.setMaximum(100)
        layout.addWidget(self.review_progress_bar)
        
        score_layout = QHBoxLayout()
        
        score_group = QGroupBox("综合评分")
        score_layout_inner = QVBoxLayout(score_group)
        
        self.score_label = QLabel("0 / 100")
        self.score_label.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout_inner.addWidget(self.score_label)
        
        self.conclusion_label = QLabel("待审核")
        self.conclusion_label.setFont(QFont("Microsoft YaHei", 12))
        self.conclusion_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score_layout_inner.addWidget(self.conclusion_label)
        
        score_layout.addWidget(score_group)
        layout.addLayout(score_layout)
        
        issues_group = QGroupBox("发现的问题")
        issues_layout = QVBoxLayout(issues_group)
        
        self.issues_tree = QTreeWidget()
        self.issues_tree.setHeaderLabels(["严重程度", "章节", "问题描述", "检测者"])
        self.issues_tree.setColumnWidth(0, 80)
        self.issues_tree.setColumnWidth(1, 120)
        self.issues_tree.setColumnWidth(2, 350)
        self.issues_tree.setColumnWidth(3, 100)
        issues_layout.addWidget(self.issues_tree)
        
        layout.addWidget(issues_group)
        
        conflicts_group = QGroupBox("数据矛盾")
        conflicts_layout = QVBoxLayout(conflicts_group)
        
        self.conflicts_tree = QTreeWidget()
        self.conflicts_tree.setHeaderLabels(["严重程度", "类型", "矛盾说明"])
        self.conflicts_tree.setColumnWidth(0, 80)
        self.conflicts_tree.setColumnWidth(1, 100)
        self.conflicts_tree.setColumnWidth(2, 400)
        conflicts_layout.addWidget(self.conflicts_tree)
        
        layout.addWidget(conflicts_group)
        
        return widget
    
    def _create_debate_tab(self) -> QWidget:
        """创建辩论标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.debate_round_label = QLabel("辩论轮数: 0")
        self.debate_round_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(self.debate_round_label)
        
        debate_group = QGroupBox("辩论记录")
        debate_layout = QVBoxLayout(debate_group)
        
        self.debate_text = QTextEdit()
        self.debate_text.setReadOnly(True)
        self.debate_text.setFont(QFont("Microsoft YaHei", 10))
        debate_layout.addWidget(self.debate_text)
        
        layout.addWidget(debate_group)
        
        return widget
    
    def _create_meeting_tab(self) -> QWidget:
        """创建虚拟会议标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        meetings_group = QGroupBox("虚拟会议记录")
        meetings_layout = QVBoxLayout(meetings_group)
        
        self.meetings_list = QListWidget()
        self.meetings_list.itemDoubleClicked.connect(self._show_meeting_detail)
        meetings_layout.addWidget(self.meetings_list)
        
        layout.addWidget(meetings_group)
        
        meeting_summary_group = QGroupBox("会议总结")
        meeting_summary_layout = QVBoxLayout(meeting_summary_group)
        
        self.meeting_summary_text = QTextEdit()
        self.meeting_summary_text.setReadOnly(True)
        meeting_summary_layout.addWidget(self.meeting_summary_text)
        
        layout.addWidget(meeting_summary_group)
        
        return widget
    
    def _create_report_tab(self) -> QWidget:
        """创建审核报告标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        opinion_group = QGroupBox("专业审核意见")
        opinion_layout = QVBoxLayout(opinion_group)
        
        self.opinion_text = QTextEdit()
        self.opinion_text.setReadOnly(True)
        self.opinion_text.setFont(QFont("Microsoft YaHei", 10))
        opinion_layout.addWidget(self.opinion_text)
        
        layout.addWidget(opinion_group)
        
        suggestions_group = QGroupBox("修改建议")
        suggestions_layout = QVBoxLayout(suggestions_group)
        
        self.suggestions_list = QListWidget()
        suggestions_layout.addWidget(self.suggestions_list)
        
        export_btn = QPushButton("导出审核报告")
        export_btn.clicked.connect(self._export_review_report)
        suggestions_layout.addWidget(export_btn)
        
        layout.addWidget(suggestions_group)
        
        return widget
    
    def _start_ai_generation(self):
        """开始AI增强生成"""
        project_name = self.project_name_edit.text().strip()
        if not project_name:
            QMessageBox.warning(self, "错误", "请输入项目名称")
            return
        
        if not self.engine:
            QMessageBox.warning(self, "错误", "AI增强引擎未加载")
            return
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        try:
            self._clear_review_ui()
            
            selected_roles = []
            for i in range(self.debate_roles_list.count()):
                item = self.debate_roles_list.item(i)
                if item.isSelected():
                    role_id = item.data(Qt.ItemDataRole.UserRole)
                    try:
                        selected_roles.append(self.AvatarRole(role_id))
                    except ValueError:
                        pass
            
            config = self.AIEnhancedGenerationConfig(
                enable_ai_agent=self.enable_ai_agent_cb.isChecked(),
                enable_smart_review=self.enable_smart_review_cb.isChecked(),
                enable_conflict_detection=self.enable_conflict_cb.isChecked(),
                enable_avatar_debate=self.enable_debate_cb.isChecked(),
                enable_virtual_review=self.enable_virtual_review_cb.isChecked(),
                enable_auto_revision=self.enable_auto_revision_cb.isChecked(),
                enable_virtual_phone=self.enable_virtual_phone_cb.isChecked(),
                use_knowledge_base=self.use_kb_cb.isChecked(),
                use_deep_search=self.use_deep_search_cb.isChecked(),
                use_local_data=self.use_local_data_cb.isChecked(),
                use_online_api=self.use_online_api_cb.isChecked(),
                debate_rounds=self.debate_rounds_spin.value(),
                debate_participants=selected_roles,
            )
            
            content = self._build_sample_content(project_name)
            doc_type = self.doc_type_combo.currentText()
            
            self.worker = AIReviewWorker(self.engine, content, doc_type, config)
            self.worker.progress_updated.connect(self._on_progress_updated)
            self.worker.issue_found.connect(self._on_issue_found)
            self.worker.debate_round_updated.connect(self._on_debate_updated)
            self.worker.meeting_started.connect(self._on_meeting_started)
            self.worker.review_completed.connect(self._on_review_completed)
            self.worker.error_occurred.connect(self._on_error_occurred)
            self.worker.start()
            
        except Exception as e:
            logger.error(f"启动AI审核失败: {e}")
            QMessageBox.critical(self, "错误", f"启动失败:\n{e}")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
    
    def _stop_ai_generation(self):
        """停止AI审核"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.review_progress_label.setText("已停止")
    
    def _build_sample_content(self, project_name: str) -> Dict:
        """构建示例内容"""
        return {
            "cover": {
                "title": project_name,
                "subtitle": self.doc_type_combo.currentText(),
            },
            "sections": [
                {
                    "title": "一、项目总论",
                    "content": "本项目旨在...",
                },
                {
                    "title": "二、市场分析",
                    "content": "市场需求分析显示...",
                },
                {
                    "title": "三、技术方案",
                    "content": "采用先进技术方案...",
                },
                {
                    "title": "四、环境影响评价",
                    "content": "环境影响较小...",
                },
            ],
        }
    
    def _clear_review_ui(self):
        """清空审核UI"""
        self.issues_tree.clear()
        self.conflicts_tree.clear()
        self.debate_text.clear()
        self.meetings_list.clear()
        self.meeting_summary_text.clear()
        self.opinion_text.clear()
        self.suggestions_list.clear()
        self.score_label.setText("0 / 100")
        self.conclusion_label.setText("审核中...")
        self.review_progress_bar.setValue(0)
        self.review_progress_label.setText("正在审核...")
    
    def _on_progress_updated(self, progress: int, stage: str, message: str):
        """进度更新"""
        self.review_progress_bar.setValue(progress)
        self.review_progress_label.setText(message)
        logger.info(f"AI审核进度: {progress}% - {message}")
    
    def _on_issue_found(self, issue: Dict):
        """发现问题"""
        severity = issue.get("severity", "info")
        severity_colors = {
            "critical": "#FF0000",
            "major": "#FF8C00",
            "moderate": "#FFD700",
            "minor": "#87CEEB",
            "info": "#00FF00",
        }
        color = severity_colors.get(severity, "#000000")
        
        item = QTreeWidgetItem([
            severity.upper(),
            issue.get("section", ""),
            issue.get("description", ""),
            issue.get("detected_by", ""),
        ])
        item.setForeground(0, QColor(color))
        self.issues_tree.addTopLevelItem(item)
    
    def _on_debate_updated(self, debate_data: Dict):
        """辩论更新"""
        round_num = debate_data.get("round", 0)
        role = debate_data.get("role", "")
        speaker = debate_data.get("speaker", "")
        argument = debate_data.get("argument", "")
        
        self.debate_round_label.setText(f"辩论轮数: {round_num}")
        
        self.debate_text.append(f"<hr>")
        self.debate_text.append(f"<b>[第{round_num}轮 - {speaker}]</b>")
        self.debate_text.append(f"{argument}")
        self.debate_text.append("")
    
    def _on_meeting_started(self, meeting_data: Dict):
        """会议开始"""
        meeting_id = meeting_data.get("meeting_id", "")
        meeting_type = meeting_data.get("type", "")
        participants = meeting_data.get("participants", [])
        participant_names = ", ".join(p.get("name", "") for p in participants)
        
        item = QListWidgetItem(f"📞 {meeting_type}: {meeting_id}")
        item.setToolTip(f"参与者: {participant_names}")
        self.meetings_list.addItem(item)
        
        self.meeting_summary_text.append(f"<b>会议ID:</b> {meeting_id}")
        self.meeting_summary_text.append(f"<b>类型:</b> {meeting_type}")
        self.meeting_summary_text.append(f"<b>参与者:</b> {participant_names}")
        self.meeting_summary_text.append("")
    
    def _on_review_completed(self, result: Dict):
        """审核完成"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        self._review_result = result
        
        score = result.get("overall_score", 0)
        self.score_label.setText(f"{score:.1f} / 100")
        
        conclusion = result.get("conclusion", "unknown")
        conclusion_texts = {
            "pass": "✅ 通过",
            "pass_with_revisions": "⚠️ 有条件通过",
            "revise_and_resubmit": "📝 修改后重审",
            "reject": "❌ 驳回",
        }
        self.conclusion_label.setText(conclusion_texts.get(conclusion, conclusion))
        
        for issue in result.get("issues", []):
            self._on_issue_found(issue)
        
        for conflict in result.get("conflicts", []):
            item = QTreeWidgetItem([
                conflict.get("severity", "").upper(),
                conflict.get("type", ""),
                conflict.get("explanation", ""),
            ])
            self.conflicts_tree.addTopLevelItem(item)
        
        for debate_record in result.get("debate_records", []):
            self._on_debate_updated(debate_record)
        
        for meeting in result.get("virtual_meetings", []):
            self._on_meeting_started(meeting)
        
        opinion = result.get("professional_opinion", "")
        self.opinion_text.setPlainText(opinion)
        
        for suggestion in result.get("revision_suggestions", []):
            self.suggestions_list.addItem(suggestion)
        
        duration = result.get("review_duration", 0)
        QMessageBox.information(
            self,
            "审核完成",
            f"AI审核完成！\n\n"
            f"综合评分: {score:.1f}/100\n"
            f"审核结论: {conclusion_texts.get(conclusion, conclusion)}\n"
            f"发现问题: {result.get('total_issues', 0)}个\n"
            f"数据矛盾: {len(result.get('conflicts', []))}个\n"
            f"辩论轮数: {result.get('debate_rounds', 0)}轮\n"
            f"虚拟会议: {len(result.get('virtual_meetings', []))}场\n"
            f"审核耗时: {duration:.1f}秒"
        )
    
    def _on_error_occurred(self, error: str):
        """错误处理"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "错误", f"AI审核失败:\n{error}")
    
    def _show_meeting_detail(self, item: QListWidgetItem):
        """显示会议详情"""
        for i in range(self.meetings_list.count()):
            if self.meetings_list.item(i) == item:
                if self._review_result:
                    meetings = self._review_result.get("virtual_meetings", [])
                    if i < len(meetings):
                        dialog = VirtualMeetingDialog(meetings[i], self)
                        dialog.exec()
                break
    
    def _export_review_report(self):
        """导出审核报告"""
        if not self._review_result:
            QMessageBox.information(self, "提示", "没有审核结果可导出")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出审核报告", "", "JSON文件 (*.json);;文本文件 (*.txt)"
        )
        
        if file_path:
            try:
                if file_path.endswith(".json"):
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(self._review_result, f, ensure_ascii=False, indent=2)
                else:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(self._review_result.get("professional_opinion", ""))
                        f.write("\n\n=== 修改建议 ===\n")
                        for s in self._review_result.get("revision_suggestions", []):
                            f.write(f"• {s}\n")
                
                QMessageBox.information(self, "成功", f"审核报告已导出到:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败:\n{e}")


# =============================================================================
# 导出
# =============================================================================

def create_ai_enhanced_generation_panel() -> AIEnhancedGenerationPanel:
    """创建AI增强型项目生成面板"""
    return AIEnhancedGenerationPanel()
