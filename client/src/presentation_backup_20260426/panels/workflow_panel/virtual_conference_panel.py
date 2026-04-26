"""
虚拟会议 UI 界面

提供虚拟会议、评审会、法庭、课堂等场景的用户界面
集成：实时字幕、同声传译、会议纪要、虚拟形象、数字分身
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QLineEdit, QListWidget,
    QListWidgetItem, QGroupBox, QFrame, QSplitter,
    QComboBox, QCheckBox, QSpinBox, QTabWidget,
    QProgressBar, QMessageBox, QSlider, QTextBrowser,
    QDialog, QDialogButtonBox, QFormLayout, QScrollArea
)
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon
from typing import Dict, Optional
import time


class ParticipantWidget(QWidget):
    """参与者组件"""

    def __init__(self, participant_data: Dict, parent=None):
        super().__init__(parent)
        self.participant_data = participant_data
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        avatar_label = QLabel("👤")
        avatar_label.setFont(QFont("Arial", 20))
        avatar_label.setFixedSize(40, 40)
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(avatar_label)

        info_layout = QVBoxLayout()

        name_label = QLabel(self.participant_data.get("name", "未知"))
        name_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        info_layout.addWidget(name_label)

        role_label = QLabel(self.participant_data.get("role", ""))
        role_label.setFont(QFont("Microsoft YaHei", 9))
        role_label.setStyleSheet("color: #666;")
        info_layout.addWidget(role_label)

        layout.addLayout(info_layout)

        status_layout = QVBoxLayout()
        status_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.speaking_indicator = QLabel("🔇")
        self.speaking_indicator.setFont(QFont("Arial", 14))
        status_layout.addWidget(self.speaking_indicator)

        self.mute_indicator = QLabel("")
        status_layout.addWidget(self.mute_indicator)

        layout.addLayout(status_layout)

        if self.participant_data.get("is_ai"):
            self.setStyleSheet("""
                QWidget {
                    background-color: #f0f8ff;
                    border: 1px solid #c0c0c0;
                    border-radius: 5px;
                }
            """)
        else:
            self.setStyleSheet("""
                QWidget {
                    background-color: #ffffff;
                    border: 1px solid #c0c0c0;
                    border-radius: 5px;
                }
            """)

    def update_status(self, is_speaking: bool, is_muted: bool):
        """更新状态"""
        if is_speaking:
            self.speaking_indicator.setText("🔊")
            self.speaking_indicator.setStyleSheet("color: green;")
        else:
            self.speaking_indicator.setText("🔇")
            self.speaking_indicator.setStyleSheet("color: #999;")

        if is_muted:
            self.mute_indicator.setText("已静音")
            self.mute_indicator.setStyleSheet("color: red; font-size: 10px;")
        else:
            self.mute_indicator.setText("")


class TwinCreationDialog(QDialog):
    """数字分身创建对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("创建数字分身")
        self.resize(500, 400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入分身名称")
        form_layout.addRow("分身名称:", self.name_edit)

        self.voice_combo = QComboBox()
        self.voice_combo.addItems([
            "默认语音 (中文女声)",
            "技术专家 (中文男声)",
            "政府官员 (中文男声)",
            "企业代表 (中文男声)"
        ])
        form_layout.addRow("选择音色:", self.voice_combo)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["中文", "英文", "日文", "韩文"])
        form_layout.addRow("语言:", self.lang_combo)

        self.record_btn = QPushButton("🎤 开始录音 (3秒)")
        self.record_btn.clicked.connect(self._toggle_recording)
        form_layout.addRow("录制声音:", self.record_btn)

        self.record_status = QLabel("")
        self.record_status.setStyleSheet("color: #666;")
        form_layout.addRow("录制状态:", self.record_status)

        layout.addLayout(form_layout)

        info_label = QLabel("💡 提示：录制您的声音后，系统将克隆您的音色作为数字分身的语音。")
        info_label.setStyleSheet("color: #888; font-size: 12px; padding: 10px;")
        layout.addWidget(info_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._is_recording = False
        self._audio_data = None

    def _toggle_recording(self):
        """切换录音状态"""
        if self._is_recording:
            self._is_recording = False
            self.record_btn.setText("🎤 开始录音 (3秒)")
            self.record_status.setText("录音已停止")
        else:
            self._is_recording = True
            self.record_btn.setText("⏹ 停止录音")
            self.record_status.setText("正在录音...")
            QTimer.singleShot(3000, self._on_recording_complete)

    def _on_recording_complete(self):
        """录音完成"""
        self._is_recording = False
        self.record_btn.setText("🎤 开始录音 (3秒)")
        self.record_status.setText("✅ 录音完成，声音已克隆")
        self._audio_data = b"mock_audio_data"

    def get_values(self) -> Dict:
        """获取输入值"""
        return {
            "name": self.name_edit.text(),
            "voice": self.voice_combo.currentIndex(),
            "language": self.lang_combo.currentText(),
            "audio_data": self._audio_data
        }


class TwinSelectionDialog(QDialog):
    """数字分身选择对话框"""

    def __init__(self, twins: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择数字分身参加会议")
        self.twins = twins
        self.selected_twin = None
        self.resize(400, 300)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("请选择要参加会议的数字分身:"))

        self.twin_list = QListWidget()
        for twin in self.twins:
            item = QListWidgetItem(f"🤖 {twin.get('name', '未知')}")
            item.setData(Qt.ItemDataRole.UserRole, twin)
            self.twin_list.addItem(item)

        if not self.twins:
            self.twin_list.addItem("（暂无数字分身，请先创建）")

        layout.addWidget(self.twin_list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        """确定选择"""
        current_item = self.twin_list.currentItem()
        if current_item:
            self.selected_twin = current_item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def get_selected_twin(self):
        """获取选中的分身"""
        return self.selected_twin


class CaptionsPanel(QWidget):
    """实时字幕面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("🗒️ 实时字幕"))
        header.addStretch()

        self.captions_display = QTextBrowser()
        self.captions_display.setMaximumHeight(150)
        self.captions_display.setPlaceholderText("会议字幕将在这里显示...")
        layout.addWidget(self.captions_display)

        controls = QHBoxLayout()

        controls.addWidget(QLabel("语言:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["中文", "英文", "日文", "韩文"])
        controls.addWidget(self.lang_combo)

        self.captions_btn = QPushButton("🎤 开始识别")
        self.captions_btn.clicked.connect(self._toggle_captions)
        controls.addWidget(self.captions_btn)

        controls.addStretch()

        layout.addLayout(controls)

        layout.addStretch()

        self._is_running = False

    def _toggle_captions(self):
        """切换字幕识别"""
        if self._is_running:
            self._is_running = False
            self.captions_btn.setText("🎤 开始识别")
            self.captions_display.append("<i>字幕识别已停止</i>")
        else:
            self._is_running = True
            self.captions_btn.setText("⏹ 停止识别")
            self.captions_display.append("<i>字幕识别已启动</i>")

    def add_caption(self, text: str, speaker: str = ""):
        """添加字幕"""
        if speaker:
            self.captions_display.append(f"<b>{speaker}:</b> {text}")
        else:
            self.captions_display.append(text)


class TranslationPanel(QWidget):
    """同声传译面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("🌐 同声传译"))
        header.addStretch()

        self.translation_display = QTextBrowser()
        self.translation_display.setMaximumHeight(150)
        self.translation_display.setPlaceholderText("翻译内容将在这里显示...")
        layout.addWidget(self.translation_display)

        controls = QHBoxLayout()

        controls.addWidget(QLabel("源语言:"))
        self.source_lang = QComboBox()
        self.source_lang.addItems(["中文", "英文", "日文", "韩文", "法文", "德文"])
        controls.addWidget(self.source_lang)

        controls.addWidget(QLabel("→"))
        controls.addWidget(QLabel("目标语言:"))
        self.target_lang = QComboBox()
        self.target_lang.addItems(["中文", "英文", "日文", "韩文", "法文", "德文"])
        controls.addWidget(self.target_lang)

        self.translate_btn = QPushButton("🔄 开启翻译")
        self.translate_btn.clicked.connect(self._toggle_translation)
        controls.addWidget(self.translate_btn)

        layout.addLayout(controls)

        layout.addStretch()

        self._is_running = False

    def _toggle_translation(self):
        """切换翻译"""
        if self._is_running:
            self._is_running = False
            self.translate_btn.setText("🔄 开启翻译")
            self.translation_display.append("<i>同声传译已关闭</i>")
        else:
            self._is_running = True
            self.translate_btn.setText("⏹ 关闭翻译")
            self.translation_display.append("<i>同声传译已开启</i>")

    def add_translation(self, original: str, translated: str, source_lang: str, target_lang: str):
        """添加翻译"""
        self.translation_display.append(f"<b>[{source_lang}→{target_lang}]</b> {translated}")


class SummaryPanel(QWidget):
    """会议纪要面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("📋 会议纪要"))
        header.addStretch()

        self.summary_display = QTextBrowser()
        layout.addWidget(self.summary_display)

        controls = QHBoxLayout()

        self.generate_btn = QPushButton("📝 生成纪要")
        self.generate_btn.clicked.connect(self._generate_summary)
        controls.addWidget(self.generate_btn)

        self.export_btn = QPushButton("💾 导出纪要")
        self.export_btn.clicked.connect(self._export_summary)
        controls.addWidget(self.export_btn)

        controls.addStretch()

        self.format_combo = QComboBox()
        self.format_combo.addItems(["Markdown", "HTML", "JSON"])
        controls.addWidget(self.format_combo)

        layout.addLayout(controls)

        self._summary_content = ""

    def _generate_summary(self):
        """生成纪要"""
        self.summary_display.append("<i>正在生成会议纪要...</i>")
        self._summary_content = """# 会议纪要

## 会议概要
本次会议围绕项目评审展开深入讨论。

## 关键决策
1. 确认项目整体方向
2. 通过下一阶段工作计划

## 待办事项
- [技术团队] 完善技术方案 (优先级: 高)
- [产品团队] 准备演示材料 (优先级: 中)

## 关键要点
1. 项目进展符合预期
2. 需要加强跨部门协作
"""
        self.summary_display.setMarkdown(self._summary_content)

    def _export_summary(self):
        """导出纪要"""
        if not self._summary_content:
            QMessageBox.warning(self, "提示", "请先生成会议纪要")
            return
        QMessageBox.information(self, "提示", "纪要已导出")


class AvatarPanel(QWidget):
    """虚拟形象面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("🤖 虚拟形象"))
        header.addStretch()

        self.avatar_display = QLabel("🤖")
        self.avatar_display.setFont(QFont("Arial", 60))
        self.avatar_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_display.setStyleSheet("""
            background-color: #f0f0f0;
            border-radius: 10px;
            padding: 20px;
        """)
        layout.addWidget(self.avatar_display)

        self.avatar_name = QLabel("虚拟形象")
        self.avatar_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.avatar_name)

        controls = QHBoxLayout()

        controls.addWidget(QLabel("表情:"))
        self.expression_combo = QComboBox()
        self.expression_combo.addItems(["😀 高兴", "😐 中性", "😢 悲伤", "🤔 思考", "🗣️ 说话"])
        controls.addWidget(self.expression_combo)

        self.avatar_btn = QPushButton("🎭 激活形象")
        self.avatar_btn.clicked.connect(self._toggle_avatar)
        controls.addWidget(self.avatar_btn)

        layout.addLayout(controls)

        self._is_active = False

    def _toggle_avatar(self):
        """切换虚拟形象"""
        if self._is_active:
            self._is_active = False
            self.avatar_btn.setText("🎭 激活形象")
            self.avatar_display.setStyleSheet("""
                background-color: #f0f0f0;
                border-radius: 10px;
                padding: 20px;
                opacity: 0.5;
            """)
        else:
            self._is_active = True
            self.avatar_btn.setText("⏹ 停用形象")
            self.avatar_display.setStyleSheet("""
                background-color: #e8f5e9;
                border-radius: 10px;
                padding: 20px;
                border: 2px solid #4caf50;
            """)


class DigitalTwinPanel(QWidget):
    """数字分身面板"""

    twin_created = pyqtSignal(dict)
    twin_selected = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.twins = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("🎭 我的数字分身"))
        header.addStretch()

        self.create_twin_btn = QPushButton("➕ 创建分身")
        self.create_twin_btn.clicked.connect(self._on_create_twin)
        header.addWidget(self.create_twin_btn)

        layout.addLayout(header)

        self.twin_list = QListWidget()
        layout.addWidget(self.twin_list)

        controls = QHBoxLayout()

        self.select_twin_btn = QPushButton("✓ 选择参加会议")
        self.select_twin_btn.clicked.connect(self._on_select_twin)
        controls.addWidget(self.select_twin_btn)

        self.delete_twin_btn = QPushButton("🗑️ 删除")
        self.delete_twin_btn.clicked.connect(self._on_delete_twin)
        controls.addWidget(self.delete_twin_btn)

        layout.addLayout(controls)

        info_label = QLabel("💡 您可以创建多个数字分身，每个分身可以有不同的声音和角色。")
        info_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(info_label)

    def add_twin(self, twin_data: Dict):
        """添加分身"""
        self.twins.append(twin_data)
        self._update_list()

    def _update_list(self):
        """更新列表"""
        self.twin_list.clear()
        for twin in self.twins:
            icon = "🎭" if twin.get("is_digital_twin") else "👤"
            item = QListWidgetItem(f"{icon} {twin.get('name', '未知')}")
            item.setData(Qt.ItemDataRole.UserRole, twin)
            self.twin_list.addItem(item)

    def _on_create_twin(self):
        """创建分身"""
        dialog = TwinCreationDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.get_values()
            if values.get("name"):
                twin_data = {
                    "twin_id": f"twin_{len(self.twins)}",
                    "name": values["name"],
                    "voice": values["voice"],
                    "language": values["language"],
                    "is_digital_twin": True
                }
                self.add_twin(twin_data)
                self.twin_created.emit(twin_data)
                QMessageBox.information(self, "成功", f"数字分身「{values['name']}」创建成功！")
            else:
                QMessageBox.warning(self, "警告", "请输入分身名称")

    def _on_select_twin(self):
        """选择分身"""
        current_item = self.twin_list.currentItem()
        if current_item:
            twin = current_item.data(Qt.ItemDataRole.UserRole)
            self.twin_selected.emit(twin)
            QMessageBox.information(self, "提示", f"已选择数字分身「{twin.get('name')}」参加会议")
        else:
            QMessageBox.warning(self, "提示", "请先选择一个数字分身")

    def _on_delete_twin(self):
        """删除分身"""
        current_item = self.twin_list.currentItem()
        if current_item:
            twin = current_item.data(Qt.ItemDataRole.UserRole)
            reply = QMessageBox.question(
                self, "确认", f"确定要删除数字分身「{twin.get('name')}」吗？"
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.twins = [t for t in self.twins if t.get("twin_id") != twin.get("twin_id")]
                self._update_list()


class VirtualConferencePanel(QWidget):
    """虚拟会议面板"""

    meeting_started = pyqtSignal()
    meeting_ended = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.conference_system = None
        self.is_recording = False
        self.current_twin = None
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)

        title = QLabel("🏛️ 虚拟会议系统 - 增强版")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.tab_widget = QTabWidget()

        main_tab = QWidget()
        main_layout = QVBoxLayout(main_tab)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        left_panel = self._create_control_panel()
        splitter.addWidget(left_panel)

        center_panel = self._create_content_panel()
        splitter.addWidget(center_panel)

        right_panel = self._create_participants_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([200, 400, 200])

        self.tab_widget.addTab(main_tab, "📹 会议")

        self.captions_panel = CaptionsPanel()
        self.tab_widget.addTab(self.captions_panel, "🗒️ 实时字幕")

        self.translation_panel = TranslationPanel()
        self.tab_widget.addTab(self.translation_panel, "🌐 同声传译")

        self.summary_panel = SummaryPanel()
        self.tab_widget.addTab(self.summary_panel, "📋 会议纪要")

        self.avatar_panel = AvatarPanel()
        self.tab_widget.addTab(self.avatar_panel, "🤖 虚拟形象")

        self.twin_panel = DigitalTwinPanel()
        self.twin_panel.twin_created.connect(self._on_twin_created)
        self.twin_panel.twin_selected.connect(self._on_twin_selected)
        self.tab_widget.addTab(self.twin_panel, "🎭 数字分身")

        layout.addWidget(self.tab_widget)

        status_layout = QHBoxLayout()

        self.status_label = QLabel("状态: 未开始")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.twin_status = QLabel("")
        self.twin_status.setStyleSheet("color: #4caf50;")
        status_layout.addWidget(self.twin_status)

        self.recording_indicator = QLabel("")
        status_layout.addWidget(self.recording_indicator)

        self.audio_level = QProgressBar()
        self.audio_level.setMaximumWidth(100)
        self.audio_level.setRange(0, 100)
        self.audio_level.setValue(0)
        status_layout.addWidget(QLabel("音量:"))
        status_layout.addWidget(self.audio_level)

        layout.addLayout(status_layout)

    def _create_control_panel(self) -> QWidget:
        """创建控制面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)

        scenario_group = QGroupBox("会议场景")
        scenario_layout = QVBoxLayout()

        self.scenario_combo = QComboBox()
        self.scenario_combo.addItems([
            "评审会",
            "政府会议",
            "虚拟法庭",
            "虚拟课堂",
            "商务谈判",
            "新闻发布会"
        ])
        scenario_layout.addWidget(self.scenario_combo)

        quick_create_btn = QPushButton("🎯 快速创建评审会")
        quick_create_btn.clicked.connect(self._quick_create_review_meeting)
        scenario_layout.addWidget(quick_create_btn)

        scenario_group.setLayout(scenario_layout)
        layout.addWidget(scenario_group)

        control_group = QGroupBox("会议控制")
        control_layout = QVBoxLayout()

        self.start_btn = QPushButton("▶️ 开始会议")
        self.start_btn.clicked.connect(self._start_meeting)
        self.start_btn.setEnabled(False)
        control_layout.addWidget(self.start_btn)

        self.end_btn = QPushButton("⏹️ 结束会议")
        self.end_btn.clicked.connect(self._end_meeting)
        self.end_btn.setEnabled(False)
        control_layout.addWidget(self.end_btn)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        topic_group = QGroupBox("议题控制")
        topic_layout = QVBoxLayout()

        self.topic_list = QListWidget()
        topic_layout.addWidget(self.topic_list)

        topic_btn_layout = QHBoxLayout()

        prev_topic_btn = QPushButton("◀ 上一个")
        prev_topic_btn.clicked.connect(self._prev_topic)
        topic_btn_layout.addWidget(prev_topic_btn)

        next_topic_btn = QPushButton("下一个 ▶")
        next_topic_btn.clicked.connect(self._next_topic)
        topic_btn_layout.addWidget(next_topic_btn)

        topic_layout.addLayout(topic_btn_layout)

        topic_group.setLayout(topic_layout)
        layout.addWidget(topic_group)

        record_group = QGroupBox("会议录音")
        record_layout = QVBoxLayout()

        self.record_btn = QPushButton("⏺ 开始录音")
        self.record_btn.clicked.connect(self._toggle_recording)
        record_layout.addWidget(self.record_btn)

        self.transcribe_btn = QPushButton("📝 转录会议")
        self.transcribe_btn.clicked.connect(self._transcribe_meeting)
        record_layout.addWidget(self.transcribe_btn)

        record_group.setLayout(record_layout)
        layout.addWidget(record_group)

        layout.addStretch()

        return panel

    def _create_content_panel(self) -> QWidget:
        """创建内容面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)

        topic_label = QLabel("当前议题:")
        topic_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(topic_label)

        self.current_topic_label = QLabel("无")
        self.current_topic_label.setFont(QFont("Microsoft YaHei", 12))
        self.current_topic_label.setStyleSheet("color: #0066cc; padding: 5px;")
        layout.addWidget(self.current_topic_label)

        content_group = QGroupBox("会议内容")
        content_layout = QVBoxLayout()

        self.content_text = QTextEdit()
        self.content_text.setReadOnly(True)
        content_layout.addWidget(self.content_text)

        content_group.setLayout(content_layout)
        layout.addWidget(content_group, stretch=1)

        input_group = QGroupBox("发言")
        input_layout = QVBoxLayout()

        self.input_text = QLineEdit()
        self.input_text.setPlaceholderText("输入发言内容...")
        input_layout.addWidget(self.input_text)

        input_btn_layout = QHBoxLayout()

        speak_btn = QPushButton("🗣️ 发言")
        speak_btn.clicked.connect(self._send_speech)
        input_btn_layout.addWidget(speak_btn)

        ai_speak_btn = QPushButton("🤖 AI 发言")
        ai_speak_btn.clicked.connect(self._ai_speak)
        input_btn_layout.addWidget(ai_speak_btn)

        input_layout.addLayout(input_btn_layout)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        return panel

    def _create_participants_panel(self) -> QWidget:
        """创建参与者面板"""
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)

        title = QLabel("👥 参与者")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        self.participant_list = QListWidget()
        layout.addWidget(self.participant_list)

        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("筛选:"))

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "专家", "政府", "企业", "员工", "AI", "分身"])
        filter_layout.addWidget(self.filter_combo)

        layout.addLayout(filter_layout)

        add_btn = QPushButton("➕ 添加参与者")
        add_btn.clicked.connect(self._add_participant)
        layout.addWidget(add_btn)

        quick_add_group = QGroupBox("快捷添加角色")
        quick_add_layout = QVBoxLayout()

        add_expert_btn = QPushButton("👔 添加专家")
        add_expert_btn.clicked.connect(lambda: self._quick_add_role("expert"))
        quick_add_layout.addWidget(add_expert_btn)

        add_gov_btn = QPushButton("🏛️ 添加政府代表")
        add_gov_btn.clicked.connect(lambda: self._quick_add_role("government"))
        quick_add_layout.addWidget(add_gov_btn)

        add_ent_btn = QPushButton("🏢 添加企业代表")
        add_ent_btn.clicked.connect(lambda: self._quick_add_role("enterprise"))
        quick_add_layout.addWidget(add_ent_btn)

        add_emp_btn = QPushButton("👷 添加员工代表")
        add_emp_btn.clicked.connect(lambda: self._quick_add_role("employee"))
        quick_add_layout.addWidget(add_emp_btn)

        quick_add_group.setLayout(quick_add_layout)
        layout.addWidget(quick_add_group)

        return panel

    def _on_twin_created(self, twin_data: Dict):
        """数字分身创建事件"""
        self.content_text.append(f"【系统】数字分身「{twin_data.get('name')}」创建成功！\n")

    def _on_twin_selected(self, twin_data: Dict):
        """数字分身选择事件"""
        self.current_twin = twin_data
        self.twin_status.setText(f"🎭 当前分身: {twin_data.get('name', '')}")

        if self.conference_system:
            from core.living_tree_ai.voice.virtual_conference import RoleProfile, RoleType
            role = RoleProfile(
                name=twin_data.get("name", ""),
                title="数字分身",
                role_type=RoleType.EXPERT,
                voice="custom"
            )
            self.conference_system.add_digital_twin(
                twin_id=twin_data.get("twin_id", ""),
                name=twin_data.get("name", ""),
                role=role,
                voice_profile=twin_data
            )
            self._update_participant_list()
            self.content_text.append(f"【系统】数字分身「{twin_data.get('name')}」已加入会议\n")

    def _quick_create_review_meeting(self):
        """快速创建评审会"""
        try:
            from core.living_tree_ai.voice.virtual_conference import (
                ReviewMeetingScenario, RoleType
            )

            async def llm_handler(prompt):
                return f"AI 思考: {prompt[:50]}...\n\n这是基于评审会的回复。"

            self.conference_system = ReviewMeetingScenario.create_review_meeting(
                llm_handler=llm_handler,
                include_roles=["chairman", "expert1", "expert2", "government", "enterprise", "employee"]
            )

            self._update_participant_list()
            self._update_topic_list()

            self.start_btn.setEnabled(True)
            self.status_label.setText("状态: 评审会已创建")
            self.content_text.append("【系统】评审会已创建完成。\n")
            self.content_text.append("💡 提示: 您可以在「数字分身」标签页创建您的AI分身，代替您参加会议。\n")

            QMessageBox.information(self, "成功", "评审会已创建！")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建评审会失败: {e}")

    def _start_meeting(self):
        """开始会议"""
        if not self.conference_system:
            return

        try:
            import asyncio
            asyncio.run(self.conference_system.start_meeting(
                "虚拟评审会",
                "对项目报告进行评审和质询"
            ))

            self.start_btn.setEnabled(False)
            self.end_btn.setEnabled(True)
            self.status_label.setText("状态: 会议进行中")
            self.content_text.append("【系统】会议已开始。\n")

            if self.current_twin:
                self.content_text.append(f"【系统】数字分身「{self.current_twin.get('name')}」正在代表您参加会议。\n")

            self.meeting_started.emit()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"开始会议失败: {e}")

    def _end_meeting(self):
        """结束会议"""
        if not self.conference_system:
            return

        try:
            import asyncio
            asyncio.run(self.conference_system.end_meeting())

            self.start_btn.setEnabled(True)
            self.end_btn.setEnabled(False)
            self.status_label.setText("状态: 会议已结束")
            self.content_text.append("【系统】会议已结束。\n")

            summary = self.conference_system.get_meeting_summary()
            self.content_text.append(f"\n【会议总结】\n{summary}\n")

            self.meeting_ended.emit()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"结束会议失败: {e}")

    def _prev_topic(self):
        """上一个议题"""
        if not self.conference_system:
            return

        current = self.conference_system.current_topic_index
        if current > 0:
            self.conference_system.set_current_topic(current - 1)
            self._update_current_topic()

    def _next_topic(self):
        """下一个议题"""
        if not self.conference_system:
            return

        current = self.conference_system.current_topic_index
        if current < len(self.conference_system.topics) - 1:
            self.conference_system.set_current_topic(current + 1)
            self._update_current_topic()

    def _update_current_topic(self):
        """更新当前议题显示"""
        if not self.conference_system:
            return

        if self.conference_system.topics:
            topic = self.conference_system.topics[self.conference_system.current_topic_index]
            self.current_topic_label.setText(f"{topic.title}")
            self.content_text.append(f"\n【议题变更】{topic.title}\n{topic.description}\n")

    def _toggle_recording(self):
        """切换录音状态"""
        if self.is_recording:
            self.is_recording = False
            self.record_btn.setText("⏺ 开始录音")
            self.recording_indicator.setText("")
            self.content_text.append("【系统】录音已停止。\n")
        else:
            self.is_recording = True
            self.record_btn.setText("⏹ 停止录音")
            self.recording_indicator.setText("🔴 录音中")
            self.recording_indicator.setStyleSheet("color: red; font-weight: bold;")
            self.content_text.append("【系统】开始录音。\n")

    def _transcribe_meeting(self):
        """转录会议"""
        QMessageBox.information(self, "提示", "会议转录功能将在会议结束后可用。")

    def _send_speech(self):
        """发送发言"""
        text = self.input_text.text().strip()
        if not text:
            return

        speaker = "你"
        if self.current_twin:
            speaker = self.current_twin.get("name", "你的分身")

        self.content_text.append(f"<b>{speaker}:</b> {text}\n")
        self.captions_panel.add_caption(text, speaker)
        self.input_text.clear()

    def _ai_speak(self):
        """AI 发言"""
        text = self.input_text.text().strip()
        if not text:
            return

        self.content_text.append(f"<b>专家:</b> 关于「{text}」，我认为...\n这是基于专业角度的分析。\n")
        self.captions_panel.add_caption(f"关于「{text}」，我认为...", "专家")
        self.input_text.clear()

    def _add_participant(self):
        """添加参与者"""
        QMessageBox.information(self, "提示", "请使用快捷添加按钮快速添加角色。")

    def _quick_add_role(self, role_type: str):
        """快速添加角色"""
        role_names = {
            "expert": ("专家", "技术专家"),
            "government": ("政府代表", "发改委处长"),
            "enterprise": ("企业代表", "总经理"),
            "employee": ("员工代表", "部门经理")
        }

        name, title = role_names.get(role_type, ("未知", "未知"))

        self.content_text.append(f"【系统】已添加 {name}（{title}）到会议。\n")

        self._update_participant_list()

    def _update_participant_list(self):
        """更新参与者列表"""
        self.participant_list.clear()

        if not self.conference_system:
            return

        for participant in self.conference_system.participants.values():
            icon = "🤖" if participant.is_digital_twin else "👤"
            item = QListWidgetItem(f"{icon} {participant.name} - {participant.role.title}")
            self.participant_list.addItem(item)

    def _update_topic_list(self):
        """更新议题列表"""
        self.topic_list.clear()

        if not self.conference_system:
            return

        for topic in self.conference_system.topics:
            self.topic_list.addItem(f"📋 {topic.title}")


class VirtualConferenceDialog(QWidget):
    """虚拟会议对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("虚拟会议系统 - 增强版")
        self.resize(1400, 800)

        layout = QVBoxLayout(self)
        self.conference_panel = VirtualConferencePanel()
        layout.addWidget(self.conference_panel)

        self.setLayout(layout)
