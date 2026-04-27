"""
语音配置和对话界面

提供语音对话和会议的用户界面
"""

from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QLineEdit, QComboBox,
    QListWidget, QListWidgetItem, QGroupBox,
    QFrame, QSplitter, QMessageBox, QCheckBox,
    QSpinBox, QSlider, QTabWidget
)
from PyQt6.QtGui import QFont


class VoiceConfigPanel(QWidget):
    """语音配置面板"""
    
    config_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        
        # TTS 配置
        tts_group = QGroupBox("文本转语音 (TTS) 配置")
        tts_layout = QVBoxLayout()
        
        # 语音选择
        voice_layout = QHBoxLayout()
        voice_layout.addWidget(QLabel("语音:"))
        self.voice_combo = QComboBox()
        self.voice_combo.addItems([
            "zh-CN-XiaoxiaoNeural (女声-晓晓)",
            "zh-CN-YunxiNeural (男声-云希)",
            "zh-CN-YunyangNeural (男声-云扬)",
            "zh-CN-XiaoyiNeural (女声-晓伊)",
            "en-US-JennyNeural (女声-Jenny)",
            "en-US-GuyNeural (男声-Guy)"
        ])
        voice_layout.addWidget(self.voice_combo)
        tts_layout.addLayout(voice_layout)
        
        # 语速
        rate_layout = QHBoxLayout()
        rate_layout.addWidget(QLabel("语速:"))
        self.rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.rate_slider.setRange(-100, 100)
        self.rate_slider.setValue(0)
        self.rate_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.rate_slider.setTickInterval(10)
        rate_layout.addWidget(self.rate_slider)
        self.rate_value = QLabel("0%")
        rate_layout.addWidget(self.rate_value)
        tts_layout.addLayout(rate_layout)
        
        # 音调
        pitch_layout = QHBoxLayout()
        pitch_layout.addWidget(QLabel("音调:"))
        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setRange(-50, 50)
        self.pitch_slider.setValue(0)
        self.pitch_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.pitch_slider.setTickInterval(10)
        pitch_layout.addWidget(self.pitch_slider)
        self.pitch_value = QLabel("0Hz")
        pitch_layout.addWidget(self.pitch_value)
        tts_layout.addLayout(pitch_layout)
        
        tts_group.setLayout(tts_layout)
        layout.addWidget(tts_group)
        
        # STT 配置
        stt_group = QGroupBox("语音转文本 (STT) 配置")
        stt_layout = QVBoxLayout()
        
        # 模型选择
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("模型:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "tiny (最快，最低精度)",
            "base (快速，低精度)",
            "small (中等，中等精度)",
            "medium (较慢，高精度)",
            "large (最慢，最高精度)"
        ])
        model_layout.addWidget(self.model_combo)
        stt_layout.addLayout(model_layout)
        
        # 语言选择
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("语言:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems([
            "zh (中文)",
            "en (英文)",
            "ja (日文)",
            "ko (韩文)",
            "auto (自动检测)"
        ])
        lang_layout.addWidget(self.lang_combo)
        stt_layout.addLayout(lang_layout)
        
        stt_group.setLayout(stt_layout)
        layout.addWidget(stt_group)
        
        # 音频设备配置
        device_group = QGroupBox("音频设备")
        device_layout = QVBoxLayout()
        
        self.enable_audio_check = QCheckBox("启用音频输入/输出")
        self.enable_audio_check.setChecked(True)
        device_layout.addWidget(self.enable_audio_check)
        
        device_group.setLayout(device_layout)
        layout.addWidget(device_group)
        
        # 测试按钮
        test_layout = QHBoxLayout()
        
        test_tts_btn = QPushButton("测试 TTS")
        test_tts_btn.clicked.connect(self._test_tts)
        test_layout.addWidget(test_tts_btn)
        
        test_stt_btn = QPushButton("测试 STT")
        test_stt_btn.clicked.connect(self._test_stt)
        test_layout.addWidget(test_stt_btn)
        
        layout.addLayout(test_layout)
        layout.addStretch()
        
        # 信号连接
        self.rate_slider.valueChanged.connect(lambda v: self.rate_value.setText(f"{v}%"))
        self.pitch_slider.valueChanged.connect(lambda v: self.pitch_value.setText(f"{v}Hz"))
    
    def _test_tts(self):
        """测试 TTS"""
        try:
            from core.living_tree_ai.voice.voice_adapter import MossTTSAdapter, VoiceConfig
            
            voice_map = {
                "zh-CN-XiaoxiaoNeural (女声-晓晓)": "zh-CN-XiaoxiaoNeural",
                "zh-CN-YunxiNeural (男声-云希)": "zh-CN-YunxiNeural",
                "zh-CN-YunyangNeural (男声-云扬)": "zh-CN-YunyangNeural",
                "zh-CN-XiaoyiNeural (女声-晓伊)": "zh-CN-XiaoyiNeural",
                "en-US-JennyNeural (女声-Jenny)": "en-US-JennyNeural",
                "en-US-GuyNeural (男声-Guy)": "en-US-GuyNeural"
            }
            
            voice_name = self.voice_combo.currentText()
            voice = voice_map.get(voice_name, "zh-CN-XiaoxiaoNeural")
            rate = f"{self.rate_slider.value()}%"
            pitch = f"{self.pitch_slider.value()}Hz"
            
            config = VoiceConfig(voice=voice, rate=rate, pitch=pitch)
            adapter = MossTTSAdapter(config)
            
            import asyncio
            result = asyncio.run(adapter.synthesize("你好，这是一个测试。"))
            
            if result.success:
                QMessageBox.information(self, "成功", "TTS 测试成功！")
            else:
                QMessageBox.warning(self, "失败", f"TTS 测试失败: {result.error}")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"TTS 测试失败: {e}")
    
    def _test_stt(self):
        """测试 STT"""
        QMessageBox.information(self, "提示", "请在后续版本中使用语音对话界面进行 STT 测试")


class VoiceDialogPanel(QWidget):
    """语音对话面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dialog_system = None
        self.session_id = None
        self._is_recording = False
        self._setup_ui()
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel("🎤 语音对话")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 会话信息
        session_layout = QHBoxLayout()
        session_layout.addWidget(QLabel("会话 ID:"))
        self.session_label = QLabel("未创建")
        session_layout.addWidget(self.session_label)
        
        new_session_btn = QPushButton("新建会话")
        new_session_btn.clicked.connect(self._create_session)
        session_layout.addWidget(new_session_btn)
        
        layout.addLayout(session_layout)
        
        # 对话历史
        history_group = QGroupBox("对话历史")
        history_layout = QVBoxLayout()
        
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        history_layout.addWidget(self.history_text)
        
        history_group.setLayout(history_layout)
        layout.addWidget(history_group, stretch=1)
        
        # 文本输入
        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入文本消息...")
        self.input_edit.returnPressed.connect(self._send_text)
        input_layout.addWidget(self.input_edit)
        
        send_btn = QPushButton("发送")
        send_btn.clicked.connect(self._send_text)
        input_layout.addWidget(send_btn)
        
        layout.addLayout(input_layout)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        
        self.record_btn = QPushButton("🎙️ 开始录音")
        self.record_btn.setCheckable(True)
        self.record_btn.clicked.connect(self._toggle_recording)
        control_layout.addWidget(self.record_btn)
        
        self.play_btn = QPushButton("🔊 播放回复")
        self.play_btn.clicked.connect(self._play_last_response)
        control_layout.addWidget(self.play_btn)
        
        layout.addLayout(control_layout)
        
        # 状态
        self.status_label = QLabel("状态: 就绪")
        layout.addWidget(self.status_label)
    
    def _create_session(self):
        """创建新会话"""
        try:
            from core.living_tree_ai.voice.voice_dialog import get_voice_dialog_system
            
            self.dialog_system = get_voice_dialog_system()
            self.session_id = self.dialog_system.create_session()
            
            self.session_label.setText(self.session_id[:8] + "...")
            self.history_text.clear()
            self.status_label.setText("状态: 会话已创建")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建会话失败: {e}")
    
    def _send_text(self):
        """发送文本消息"""
        if not self.session_id:
            QMessageBox.warning(self, "警告", "请先创建会话")
            return
        
        text = self.input_edit.text().strip()
        if not text:
            return
        
        try:
            import asyncio
            
            # 处理输入
            async def process():
                return await self.dialog_system.process_text_input(self.session_id, text)
            
            response = asyncio.run(process())
            
            if response:
                # 更新历史
                self.history_text.append(f"<b>用户:</b> {text}")
                self.history_text.append(f"<b>助手:</b> {response}")
                self.input_edit.clear()
                self.status_label.setText("状态: 已收到回复")
            else:
                self.status_label.setText("状态: 处理失败")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发送失败: {e}")
    
    def _toggle_recording(self):
        """切换录音状态"""
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()
    
    def _start_recording(self):
        """开始录音"""
        self._is_recording = True
        self.record_btn.setText("🔴 停止录音")
        self.status_label.setText("状态: 正在录音...")
        
        # 注意：实际录音功能需要集成音频设备
        QMessageBox.information(self, "提示", "录音功能需要音频设备支持")
    
    def _stop_recording(self):
        """停止录音"""
        self._is_recording = False
        self.record_btn.setText("🎙️ 开始录音")
        self.status_label.setText("状态: 录音已停止")
    
    def _play_last_response(self):
        """播放最后回复"""
        QMessageBox.information(self, "提示", "播放功能需要音频设备支持")


class VoiceConferencePanel(QWidget):
    """语音会议面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.conference_system = None
        self.current_room = None
        self._setup_ui()
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel("📞 语音会议")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # 房间管理
        room_layout = QHBoxLayout()
        
        room_layout.addWidget(QLabel("房间 ID:"))
        self.room_input = QLineEdit()
        self.room_input.setPlaceholderText("输入房间 ID...")
        room_layout.addWidget(self.room_input)
        
        create_room_btn = QPushButton("创建房间")
        create_room_btn.clicked.connect(self._create_room)
        room_layout.addWidget(create_room_btn)
        
        join_room_btn = QPushButton("加入房间")
        join_room_btn.clicked.connect(self._join_room)
        room_layout.addWidget(join_room_btn)
        
        leave_room_btn = QPushButton("离开房间")
        leave_room_btn.clicked.connect(self._leave_room)
        room_layout.addWidget(leave_room_btn)
        
        layout.addLayout(room_layout)
        
        # 房间信息
        info_group = QGroupBox("房间信息")
        info_layout = QVBoxLayout()
        
        self.room_info_text = QTextEdit()
        self.room_info_text.setReadOnly(True)
        self.room_info_text.setMaximumHeight(100)
        info_layout.addWidget(self.room_info_text)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # 参与者列表
        participant_group = QGroupBox("参与者")
        participant_layout = QVBoxLayout()
        
        self.participant_list = QListWidget()
        participant_layout.addWidget(self.participant_list)
        
        participant_group.setLayout(participant_layout)
        layout.addWidget(participant_group, stretch=1)
        
        # 会议控制
        control_layout = QHBoxLayout()
        
        self.mute_btn = QPushButton("🔇 静音")
        self.mute_btn.setCheckable(True)
        self.mute_btn.clicked.connect(self._toggle_mute)
        control_layout.addWidget(self.mute_btn)
        
        self.deafen_btn = QPushButton("🔊 关闭声音")
        self.deafen_btn.setCheckable(True)
        self.deafen_btn.clicked.connect(self._toggle_deafen)
        control_layout.addWidget(self.deafen_btn)
        
        layout.addLayout(control_layout)
        
        # 状态
        self.status_label = QLabel("状态: 未加入房间")
        layout.addWidget(self.status_label)
    
    def _create_room(self):
        """创建房间"""
        room_id = self.room_input.text().strip()
        if not room_id:
            QMessageBox.warning(self, "警告", "请输入房间 ID")
            return
        
        try:
            from core.living_tree_ai.voice.voice_dialog import get_voice_conference_system
            
            self.conference_system = get_voice_conference_system()
            success = self.conference_system.create_room(room_id)
            
            if success:
                self.current_room = room_id
                self.room_info_text.setText(f"房间已创建: {room_id}")
                self.status_label.setText(f"状态: 已在房间 {room_id}")
                QMessageBox.information(self, "成功", f"房间 {room_id} 已创建")
            else:
                QMessageBox.warning(self, "失败", "房间已存在")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建房间失败: {e}")
    
    def _join_room(self):
        """加入房间"""
        room_id = self.room_input.text().strip()
        if not room_id:
            QMessageBox.warning(self, "警告", "请输入房间 ID")
            return
        
        try:
            from core.living_tree_ai.voice.voice_dialog import get_voice_conference_system
            
            self.conference_system = get_voice_conference_system()
            success = self.conference_system.add_participant(
                room_id,
                f"user_{id(self)}",
                f"用户 {id(self) % 1000}"
            )
            
            if success:
                self.current_room = room_id
                self._update_room_info()
                self.status_label.setText(f"状态: 已加入房间 {room_id}")
                QMessageBox.information(self, "成功", f"已加入房间 {room_id}")
            else:
                QMessageBox.warning(self, "失败", "无法加入房间")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加入房间失败: {e}")
    
    def _leave_room(self):
        """离开房间"""
        if not self.current_room:
            return
        
        try:
            self.conference_system.remove_participant(
                self.current_room,
                f"user_{id(self)}"
            )
            
            self.current_room = None
            self.participant_list.clear()
            self.room_info_text.clear()
            self.status_label.setText("状态: 已离开房间")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"离开房间失败: {e}")
    
    def _update_room_info(self):
        """更新房间信息"""
        if not self.current_room or not self.conference_system:
            return
        
        info = self.conference_system.get_room_info(self.current_room)
        if info:
            self.room_info_text.setText(
                f"房间: {info['room_id']}\n"
                f"参与人数: {info['participant_count']}/{info['max_participants']}"
            )
            
            self.participant_list.clear()
            for p in info['participants']:
                self.participant_list.addItem(f"{p['name']} (ID: {p['id'][:8]}...)")
    
    def _toggle_mute(self):
        """切换静音"""
        if self.mute_btn.isChecked():
            self.mute_btn.setText("🔇 已静音")
            self.status_label.setText("状态: 已静音")
        else:
            self.mute_btn.setText("🔇 静音")
            self.status_label.setText("状态: 正常")
    
    def _toggle_deafen(self):
        """切换关闭声音"""
        if self.deafen_btn.isChecked():
            self.deafen_btn.setText("🔇 已关声音")
            self.status_label.setText("状态: 已关闭声音")
        else:
            self.deafen_btn.setText("🔊 关闭声音")
            self.status_label.setText("状态: 正常")


class VoiceMainPanel(QWidget):
    """语音主面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)
        
        # 创建标签页
        tabs = QTabWidget()
        
        # 语音配置
        config_tab = VoiceConfigPanel()
        tabs.addTab(config_tab, "⚙️ 配置")
        
        # 语音对话
        dialog_tab = VoiceDialogPanel()
        tabs.addTab(dialog_tab, "🎤 对话")
        
        # 语音会议
        conference_tab = VoiceConferencePanel()
        tabs.addTab(conference_tab, "📞 会议")
        
        layout.addWidget(tabs)
        
        self.setLayout(layout)


class VoiceDialog(QWidget):
    """语音对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("语音功能")
        self.resize(500, 600)
        
        layout = QVBoxLayout(self)
        self.voice_panel = VoiceMainPanel()
        layout.addWidget(self.voice_panel)
        
        self.setLayout(layout)
