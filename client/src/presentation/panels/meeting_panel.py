"""
Meeting Panel - 会议面板UI 🎙️

提供可视化会议界面：
1. 会议录制控制
2. 转录进度
3. 摘要展示
4. 历史会议
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QLabel, QComboBox, QCheckBox, QProgressBar, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QFormLayout, QLineEdit, QListWidget, QListWidgetItem,
    QTextBrowser, QSplitter, QFrame, QStatusBar, QMessageBox,
    QDialog, QSpinBox, QDoubleSpinBox, QSlider, QFileDialog,
    QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QColor

import sys
import threading
from typing import Optional, Dict, Any
from datetime import datetime

# 导入核心模块
try:
    from core.meeting import (
        MeetingManager, Meeting, MeetingStatus,
        TranscriptionResult, SummaryResult,
        SummaryTemplate, ExportFormat
    )
    MODULE_AVAILABLE = True
except ImportError:
    MODULE_AVAILABLE = False


class MeetingPanel(QWidget):
    """
    会议面板

    提供完整的会议管理界面
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager: Optional[MeetingManager] = None
        self.current_meeting: Optional[Meeting] = None
        self._init_ui()
        self._init_manager()

    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("🎙️ 智能会议助手")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        main_layout.addWidget(title_label)

        # 创建分标签页面
        self.tabs = QTabWidget()

        # Tab 1: 录制控制
        self.tabs.addTab(self._create_record_tab(), "📍 录制")

        # Tab 2: 转录与摘要
        self.tabs.addTab(self._create_transcribe_tab(), "📝 转录摘要")

        # Tab 3: 历史会议
        self.tabs.addTab(self._create_history_tab(), "📋 历史")

        # Tab 4: 设置
        self.tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        main_layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)

    def _create_record_tab(self) -> QWidget:
        """创建录制标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 会议信息
        info_group = QGroupBox("会议信息")
        info_layout = QFormLayout()

        self.meeting_title = QLineEdit()
        self.meeting_title.setPlaceholderText("输入会议标题")
        info_layout.addRow("会议标题:", self.meeting_title)

        self.participants = QLineEdit()
        self.participants.setPlaceholderText("参与者（逗号分隔）")
        info_layout.addRow("参与者:", self.participants)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # 音频设置
        audio_group = QGroupBox("音频设置")
        audio_layout = QHBoxLayout()

        self.mic_enabled = QCheckBox("麦克风")
        self.mic_enabled.setChecked(True)
        audio_layout.addWidget(self.mic_enabled)

        self.system_audio_enabled = QCheckBox("系统音频")
        self.system_audio_enabled.setChecked(False)
        audio_layout.addWidget(self.system_audio_enabled)

        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)

        # 录制控制
        control_group = QGroupBox("录制控制")
        control_layout = QVBoxLayout()

        # 录音时长显示
        self.duration_label = QLabel("00:00:00")
        self.duration_label.setFont(QFont("Consolas", 24, QFont.Weight.Bold))
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        control_layout.addWidget(self.duration_label)

        # 波形指示器（简化版）
        self.waveform_label = QLabel("🔇")
        self.waveform_label.setFont(QFont("Arial", 32))
        self.waveform_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        control_layout.addWidget(self.waveform_label)

        # 按钮
        button_layout = QHBoxLayout()

        self.start_record_btn = QPushButton("⏺ 开始录制")
        self.start_record_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 10px;
            }
        """)
        self.start_record_btn.clicked.connect(self._on_start_recording)
        button_layout.addWidget(self.start_record_btn)

        self.stop_record_btn = QPushButton("⏹ 停止录制")
        self.stop_record_btn.setEnabled(False)
        self.stop_record_btn.clicked.connect(self._on_stop_recording)
        button_layout.addWidget(self.stop_record_btn)

        control_layout.addLayout(button_layout)
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # 快速操作
        quick_group = QGroupBox("快速操作")
        quick_layout = QHBoxLayout()

        self.import_audio_btn = QPushButton("📂 导入音频")
        self.import_audio_btn.clicked.connect(self._on_import_audio)
        quick_layout.addWidget(self.import_audio_btn)

        self.quick_record_btn = QPushButton("⚡ 快速录制 5分钟")
        self.quick_record_btn.clicked.connect(self._on_quick_record)
        quick_layout.addWidget(self.quick_record_btn)

        quick_group.setLayout(quick_layout)
        layout.addWidget(quick_group)

        layout.addStretch()

        return widget

    def _create_transcribe_tab(self) -> QWidget:
        """创建转录摘要标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 处理控制
        process_group = QGroupBox("处理选项")
        process_layout = QHBoxLayout()

        self.enable_diarization = QCheckBox("说话人识别")
        self.enable_diarization.setChecked(True)
        process_layout.addWidget(self.enable_diarization)

        self.enable_summary = QCheckBox("生成摘要")
        self.enable_summary.setChecked(True)
        process_layout.addWidget(self.enable_summary)

        self.summary_template_combo = QComboBox()
        self.summary_template_combo.addItems([
            "标准摘要",
            "详细报告",
            "会议纪要",
            "行动项清单",
            "要点列表"
        ])
        process_layout.addWidget(QLabel("摘要模板:"))
        process_layout.addWidget(self.summary_template_combo)

        process_group.setLayout(process_layout)
        layout.addWidget(process_group)

        # 进度条
        self.process_progress = QProgressBar()
        self.process_progress.setVisible(False)
        layout.addWidget(self.process_progress)

        # 进度状态
        self.process_status = QLabel("")
        layout.addWidget(self.process_status)

        # 处理按钮
        button_layout = QHBoxLayout()

        self.process_btn = QPushButton("🚀 开始处理")
        self.process_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
            }
        """)
        self.process_btn.clicked.connect(self._on_process)
        button_layout.addWidget(self.process_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

        # 转录预览
        transcript_group = QGroupBox("转录内容")
        transcript_layout = QVBoxLayout()

        self.transcript_output = QTextBrowser()
        self.transcript_output.setMinimumHeight(200)
        transcript_layout.addWidget(self.transcript_output)

        transcript_group.setLayout(transcript_layout)
        layout.addWidget(transcript_group)

        # 摘要预览
        summary_group = QGroupBox("摘要内容")
        summary_layout = QVBoxLayout()

        self.summary_output = QTextBrowser()
        self.summary_output.setMinimumHeight(150)
        summary_layout.addWidget(self.summary_output)

        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # 导出按钮
        export_layout = QHBoxLayout()

        self.export_md_btn = QPushButton("📄 导出 Markdown")
        self.export_md_btn.clicked.connect(lambda: self._on_export(ExportFormat.MARKDOWN))
        self.export_md_btn.setEnabled(False)
        export_layout.addWidget(self.export_md_btn)

        self.export_json_btn = QPushButton("📋 导出 JSON")
        self.export_json_btn.clicked.connect(lambda: self._on_export(ExportFormat.JSON))
        self.export_json_btn.setEnabled(False)
        export_layout.addWidget(self.export_json_btn)

        self.export_srt_btn = QPushButton("🎬 导出字幕")
        self.export_srt_btn.clicked.connect(lambda: self._on_export(ExportFormat.SRT))
        self.export_srt_btn.setEnabled(False)
        export_layout.addWidget(self.export_srt_btn)

        layout.addLayout(export_layout)

        return widget

    def _create_history_tab(self) -> QWidget:
        """创建历史标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 搜索栏
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索会议...")
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_input)

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self._load_meetings)
        search_layout.addWidget(self.refresh_btn)

        layout.addLayout(search_layout)

        # 会议列表
        self.meetings_table = QTableWidget()
        self.meetings_table.setColumnCount(5)
        self.meetings_table.setHorizontalHeaderLabels([
            "标题", "日期", "时长", "状态", "操作"
        ])
        self.meetings_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.meetings_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.meetings_table.itemClicked.connect(self._on_meeting_selected)
        layout.addWidget(self.meetings_table)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.open_btn = QPushButton("📂 打开")
        self.open_btn.clicked.connect(self._on_open_meeting)
        button_layout.addWidget(self.open_btn)

        self.delete_btn = QPushButton("🗑️ 删除")
        self.delete_btn.clicked.connect(self._on_delete_meeting)
        button_layout.addWidget(self.delete_btn)

        button_layout.addStretch()

        layout.addLayout(button_layout)

        # 加载历史
        self._load_meetings()

        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # AI 提供商设置
        ai_group = QGroupBox("AI 摘要设置")
        ai_layout = QFormLayout()

        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "Ollama (本地推荐)",
            "Groq (云端)",
            "OpenRouter (多模型)"
        ])
        ai_layout.addRow("AI 提供商:", self.provider_combo)

        self.ai_model = QLineEdit()
        self.ai_model.setPlaceholderText("模型名称")
        self.ai_model.setText("llama3.2")
        ai_layout.addRow("模型:", self.ai_model)

        self.test_ai_btn = QPushButton("🔗 测试连接")
        self.test_ai_btn.clicked.connect(self._on_test_ai)
        ai_layout.addRow("", self.test_ai_btn)

        ai_group.setLayout(ai_layout)
        layout.addWidget(ai_group)

        # 转录设置
        transcribe_group = QGroupBox("转录设置")
        transcribe_layout = QFormLayout()

        self.transcribe_model = QComboBox()
        self.transcribe_model.addItems([
            "base (快速)",
            "small (平衡)",
            "medium (高精度)",
            "large (最高精度)"
        ])
        transcribe_layout.addRow("模型大小:", self.transcribe_model)

        self.num_speakers = QSpinBox()
        self.num_speakers.setRange(1, 10)
        self.num_speakers.setValue(2)
        transcribe_layout.addRow("预估人数:", self.num_speakers)

        transcribe_group.setLayout(transcribe_layout)
        layout.addWidget(transcribe_group)

        # 存储设置
        storage_group = QGroupBox("存储设置")
        storage_layout = QFormLayout()

        self.storage_path = QLineEdit()
        self.storage_path.setReadOnly(True)
        storage_layout.addRow("存储目录:", self.storage_path)

        self.change_path_btn = QPushButton("📂 更改")
        self.change_path_btn.clicked.connect(self._on_change_storage)
        storage_layout.addRow("", self.change_path_btn)

        storage_group.setLayout(storage_layout)
        layout.addWidget(storage_group)

        # 保存按钮
        self.save_settings_btn = QPushButton("💾 保存设置")
        self.save_settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
            }
        """)
        self.save_settings_btn.clicked.connect(self._on_save_settings)
        layout.addWidget(self.save_settings_btn)

        layout.addStretch()

        return widget

    def _init_manager(self):
        """初始化管理器"""
        if MODULE_AVAILABLE:
            try:
                self.manager = MeetingManager()
                self._log("会议管理器初始化成功")
            except Exception as e:
                self._log(f"会议管理器初始化失败: {e}")

    @pyqtSlot()
    def _on_start_recording(self):
        """开始录制"""
        if not self.manager:
            self._show_error("会议模块未初始化")
            return

        title = self.meeting_title.text().strip()
        if not title:
            title = f"会议_{datetime.now().strftime('%Y%m%d_%H%M')}"

        participants = [
            p.strip() for p in self.participants.text().split(",")
            if p.strip()
        ]

        # 创建会议
        self.current_meeting = self.manager.create_meeting(
            title=title,
            participants=participants
        )

        # 开始录制
        success = self.manager.start_recording(
            meeting_id=self.current_meeting.meeting_id,
            include_system_audio=self.system_audio_enabled.isChecked()
        )

        if success:
            self.start_record_btn.setEnabled(False)
            self.stop_record_btn.setEnabled(True)
            self.status_bar.showMessage(f"正在录制: {title}")

            # 更新时长显示
            self._start_duration_timer()
            self.waveform_label.setText("🔴")
        else:
            self._show_error("无法开始录制，请检查麦克风权限")

    @pyqtSlot()
    def _on_stop_recording(self):
        """停止录制"""
        if not self.manager:
            return

        audio_path = self.manager.stop_recording(
            self.current_meeting.meeting_id if self.current_meeting else None
        )

        self.start_record_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(False)
        self._stop_duration_timer()

        if audio_path:
            self.status_bar.showMessage(f"录制完成: {audio_path}")
            self._log(f"音频文件: {audio_path}")

            # 切换到转录标签
            self.tabs.setCurrentIndex(1)
        else:
            self.status_bar.showMessage("录制停止")

    @pyqtSlot()
    def _on_import_audio(self):
        """导入音频文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择音频文件",
            "",
            "音频文件 (*.mp3 *.wav *.m4a *.ogg);;所有文件 (*.*)"
        )

        if file_path:
            # 创建会议并设置音频路径
            if self.manager:
                meeting = self.manager.create_meeting(
                    title=os.path.basename(file_path)
                )
                meeting.audio_path = file_path
                self.current_meeting = meeting
                self.status_bar.showMessage(f"已导入: {file_path}")
                self.tabs.setCurrentIndex(1)

    @pyqtSlot()
    def _on_quick_record(self):
        """快速录制5分钟"""
        self.meeting_title.setText(f"快速会议_{datetime.now().strftime('%H%M')}")
        self._on_start_recording()

        # 5分钟后自动停止
        QTimer.singleShot(5 * 60 * 1000, self._on_stop_recording)

    @pyqtSlot()
    def _on_process(self):
        """处理会议"""
        if not self.manager or not self.current_meeting:
            self._show_error("请先创建或导入会议")
            return

        self.process_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.process_progress.setVisible(True)
        self.process_progress.setValue(0)

        # 后台处理
        def process():
            try:
                # 转录
                self.process_status.setText("正在转录...")
                self.process_progress.setValue(10)

                self.manager.transcribe_meeting(
                    self.current_meeting.meeting_id
                )
                self.process_progress.setValue(40)

                # 说话人识别
                if self.enable_diarization.isChecked():
                    self.process_status.setText("正在识别说话人...")
                    self.manager.diarize_speakers(
                        self.current_meeting.meeting_id
                    )
                self.process_progress.setValue(60)

                # 生成摘要
                if self.enable_summary.isChecked():
                    self.process_status.setText("正在生成摘要...")
                    template_map = {
                        0: SummaryTemplate.STANDARD,
                        1: SummaryTemplate.DETAILED,
                        2: SummaryTemplate.MINUTES,
                        3: SummaryTemplate.ACTION_ITEMS,
                        4: SummaryTemplate.BULLET_POINTS,
                    }
                    self.manager.summarize_meeting(
                        self.current_meeting.meeting_id,
                        template=template_map.get(
                            self.summary_template_combo.currentIndex(),
                            SummaryTemplate.STANDARD
                        )
                    )
                self.process_progress.setValue(100)

                # 更新UI
                QTimer.singleShot(0, self._on_process_complete)

            except Exception as e:
                QTimer.singleShot(0, lambda: self._show_error(str(e)))

        thread = threading.Thread(target=process)
        thread.daemon = True
        thread.start()

    def _on_process_complete(self):
        """处理完成"""
        self.process_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.process_status.setText("处理完成!")

        # 更新显示
        if self.current_meeting.transcription:
            self._display_transcription(self.current_meeting.transcription)

        if self.current_meeting.summary:
            self._display_summary(self.current_meeting.summary)

        # 启用导出
        self.export_md_btn.setEnabled(True)
        self.export_json_btn.setEnabled(True)
        self.export_srt_btn.setEnabled(True)

        # 刷新历史
        self._load_meetings()

    @pyqtSlot()
    def _on_export(self, fmt: ExportFormat):
        """导出会议记录"""
        if not self.manager or not self.current_meeting:
            return

        export_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录"
        )

        if export_dir:
            result = self.manager.export_meeting(
                self.current_meeting.meeting_id,
                export_dir=export_dir,
                formats=[fmt]
            )

            if result:
                path = result.get(fmt.value)
                self.status_bar.showMessage(f"已导出: {path}")
                QMessageBox.information(self, "导出成功", f"文件已保存到:\n{path}")
            else:
                self._show_error("导出失败")

    def _display_transcription(self, transcription: TranscriptionResult):
        """显示转录内容"""
        lines = [f"# 转录内容\n\n"]
        lines.append(f"语言: {transcription.language}\n")
        lines.append(f"时长: {transcription.duration:.1f}秒\n\n")
        lines.append("---\n\n")

        for seg in transcription.segments:
            speaker = f"**[{seg.speaker}]** " if seg.speaker else ""
            time = f"[{self._format_time(seg.start_time)}] "
            lines.append(f"{time}{speaker}{seg.text}\n\n")

        self.transcript_output.setPlainText("".join(lines))

    def _display_summary(self, summary: SummaryResult):
        """显示摘要内容"""
        self.summary_output.setPlainText(summary.to_markdown())

    def _load_meetings(self):
        """加载会议列表"""
        if not self.manager:
            return

        meetings = self.manager.get_all_meetings()
        self.meetings_table.setRowCount(len(meetings))

        for i, meeting in enumerate(meetings):
            self.meetings_table.setItem(i, 0, QTableWidgetItem(meeting.title))
            self.meetings_table.setItem(
                i, 1,
                QTableWidgetItem(meeting.created_at.strftime("%Y-%m-%d %H:%M"))
            )
            self.meetings_table.setItem(
                i, 2,
                QTableWidgetItem(f"{meeting.duration / 60:.1f}分钟")
            )
            self.meetings_table.setItem(
                i, 3,
                QTableWidgetItem(meeting.status.value)
            )
            self.meetings_table.setItem(i, 4, QTableWidgetItem("查看"))

    @pyqtSlot()
    def _on_meeting_selected(self, item: QTableWidgetItem):
        """选中会议"""
        row = item.row()
        title = self.meetings_table.item(row, 0).text()

        # 查找会议
        if self.manager:
            for meeting in self.manager.get_all_meetings():
                if meeting.title == title:
                    self.current_meeting = meeting
                    break

    @pyqtSlot()
    def _on_open_meeting(self):
        """打开会议"""
        if not self.current_meeting:
            return

        # 加载数据
        if self.current_meeting.transcription_path:
            import json
            with open(self.current_meeting.transcription_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 重建转录结果
                from core.meeting import TranscriptionResult, TranscriptionSegment
                segments = [
                    TranscriptionSegment(
                        start_time=s["start"],
                        end_time=s["end"],
                        text=s["text"],
                        speaker=s.get("speaker")
                    )
                    for s in data.get("segments", [])
                ]
                self.current_meeting.transcription = TranscriptionResult(
                    meeting_id=data["meeting_id"],
                    full_text=data["full_text"],
                    segments=segments,
                    language=data.get("language", "zh"),
                    duration=data.get("duration", 0)
                )

        # 切换标签
        self.tabs.setCurrentIndex(1)

        # 更新显示
        if self.current_meeting.transcription:
            self._display_transcription(self.current_meeting.transcription)
        if self.current_meeting.summary:
            self._display_summary(self.current_meeting.summary)

    @pyqtSlot()
    def _on_delete_meeting(self):
        """删除会议"""
        if not self.current_meeting:
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除会议 '{self.current_meeting.title}' 吗？"
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.manager:
                self.manager.delete_meeting(self.current_meeting.meeting_id)
                self._load_meetings()
                self.current_meeting = None

    @pyqtSlot()
    def _on_search(self, text: str):
        """搜索会议"""
        for row in range(self.meetings_table.rowCount()):
            title_item = self.meetings_table.item(row, 0)
            if title_item:
                match = text.lower() in title_item.text().lower() if text else True
                self.meetings_table.setRowHidden(row, not match)

    @pyqtSlot()
    def _on_test_ai(self):
        """测试AI连接"""
        if not self.manager or not self.manager.summarizer:
            self._show_error("摘要生成器未初始化")
            return

        if self.manager.summarizer.test_connection():
            QMessageBox.information(self, "连接成功", "AI 服务连接正常!")
        else:
            self._show_error("无法连接到 AI 服务，请检查配置")

    @pyqtSlot()
    def _on_change_storage(self):
        """更改存储目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择存储目录"
        )
        if dir_path:
            self.storage_path.setText(dir_path)

    @pyqtSlot()
    def _on_save_settings(self):
        """保存设置"""
        QMessageBox.information(self, "设置", "设置已保存")
        self.status_bar.showMessage("设置已保存")

    def _start_duration_timer(self):
        """开始时长计时器"""
        self._duration_seconds = 0
        self._duration_timer = QTimer(self)
        self._duration_timer.timeout.connect(self._update_duration)
        self._duration_timer.start(1000)

    def _stop_duration_timer(self):
        """停止时长计时器"""
        if hasattr(self, '_duration_timer'):
            self._duration_timer.stop()

    def _update_duration(self):
        """更新时长显示"""
        self._duration_seconds += 1
        h, m, s = divmod(self._duration_seconds, 3600)
        m, s = divmod(m, 60)
        self.duration_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _format_time(self, seconds: float) -> str:
        """格式化时间"""
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def _log(self, message: str):
        """记录日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def _show_error(self, message: str):
        """显示错误"""
        QMessageBox.critical(self, "错误", message)


# 辅助导入
import os
