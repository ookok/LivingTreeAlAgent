"""
语音输入组件 - 支持语音录制和回放

功能特性：
1. 语音录制
2. 语音回放
3. 语音转文字
4. 实时音频可视化
5. 录音状态显示
"""

import wave
import pyaudio
import threading
import time
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QToolButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation
from PyQt6.QtGui import QColor


class VoiceRecorder:
    """语音录制器"""
    
    def __init__(self):
        self._audio = pyaudio.PyAudio()
        self._stream = None
        self._is_recording = False
        self._frames = []
        self._sample_rate = 16000
        self._channels = 1
        self._format = pyaudio.paInt16
        
        # 音频级别回调
        self.level_callback = None
    
    def start_recording(self):
        """开始录制"""
        self._frames = []
        self._is_recording = True
        
        self._stream = self._audio.open(
            format=self._format,
            channels=self._channels,
            rate=self._sample_rate,
            input=True,
            frames_per_buffer=1024,
            stream_callback=self._audio_callback
        )
        
        self._stream.start_stream()
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """音频回调"""
        if self._is_recording:
            self._frames.append(in_data)
            
            # 计算音频级别
            if self.level_callback:
                import numpy as np
                audio_data = np.frombuffer(in_data, dtype=np.int16)
                level = np.max(np.abs(audio_data)) / 32767.0
                self.level_callback(level)
        
        return (in_data, pyaudio.paContinue)
    
    def stop_recording(self) -> bytes:
        """停止录制并返回音频数据"""
        self._is_recording = False
        
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        
        # 合并帧
        return b''.join(self._frames)
    
    def save_to_file(self, filepath: str):
        """保存到WAV文件"""
        audio_data = self.stop_recording()
        
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(self._audio.get_sample_size(self._format))
            wf.setframerate(self._sample_rate)
            wf.writeframes(audio_data)
    
    def play_audio(self, audio_data: bytes):
        """播放音频"""
        stream = self._audio.open(
            format=self._format,
            channels=self._channels,
            rate=self._sample_rate,
            output=True
        )
        
        # 分块播放
        chunk_size = 1024
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            stream.write(chunk)
        
        stream.stop_stream()
        stream.close()
    
    def is_recording(self) -> bool:
        """是否正在录制"""
        return self._is_recording
    
    def close(self):
        """关闭音频设备"""
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        self._audio.terminate()


class AudioVisualizer(QFrame):
    """音频可视化组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = 0.0
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        self.setStyleSheet("background-color: transparent;")
        self.setFixedHeight(40)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 创建条形
        self.bars = []
        for _ in range(20):
            bar = QFrame()
            bar.setStyleSheet("background-color: #2563eb;")
            bar.setFixedWidth(4)
            bar.setFixedHeight(4)
            self.bars.append(bar)
            layout.addWidget(bar)
        
        layout.addStretch()
    
    def set_level(self, level: float):
        """设置音频级别"""
        self._level = level
        
        # 更新条形高度
        for i, bar in enumerate(self.bars):
            threshold = (i + 1) / len(self.bars)
            if level >= threshold:
                height = int(40 * (level * 0.8 + 0.2))
            else:
                height = 4
            
            bar.setFixedHeight(height)
            
            # 设置颜色
            if level > 0.8:
                bar.setStyleSheet("background-color: #dc2626;")
            elif level > 0.5:
                bar.setStyleSheet("background-color: #f59e0b;")
            else:
                bar.setStyleSheet("background-color: #2563eb;")


class VoiceInputWidget(QWidget):
    """语音输入组件"""
    
    voice_finished = pyqtSignal(str)  # 语音转文字结果
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._recorder = VoiceRecorder()
        self._recorder.level_callback = self._on_audio_level
        self._audio_data = b''
        self._recording_time = 0
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_recording_time)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 录制按钮
        self.record_btn = QPushButton()
        self.record_btn.setFixedSize(40, 40)
        self.record_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                border: none;
                border-radius: 20px;
                font-size: 20px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
            QPushButton.recording {
                background-color: #dc2626;
            }
        """)
        self.record_btn.setText("🎤")
        self.record_btn.clicked.connect(self._toggle_recording)
        layout.addWidget(self.record_btn)
        
        # 可视化组件
        self.visualizer = AudioVisualizer()
        layout.addWidget(self.visualizer)
        
        # 录制时间
        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("font-size: 14px; color: #64748b;")
        layout.addWidget(self.time_label)
        
        # 回放按钮
        self.play_btn = QToolButton()
        self.play_btn.setText("▶️")
        self.play_btn.setStyleSheet("""
            QToolButton {
                color: #64748b;
                border: none;
                padding: 4px;
            }
            QToolButton:hover {
                color: #2563eb;
            }
            QToolButton:disabled {
                color: #9ca3af;
            }
        """)
        self.play_btn.clicked.connect(self._play_audio)
        self.play_btn.setEnabled(False)
        layout.addWidget(self.play_btn)
        
        # 清除按钮
        self.clear_btn = QToolButton()
        self.clear_btn.setText("🗑️")
        self.clear_btn.setStyleSheet("""
            QToolButton {
                color: #64748b;
                border: none;
                padding: 4px;
            }
            QToolButton:hover {
                color: #dc2626;
            }
            QToolButton:disabled {
                color: #9ca3af;
            }
        """)
        self.clear_btn.clicked.connect(self._clear_audio)
        self.clear_btn.setEnabled(False)
        layout.addWidget(self.clear_btn)
    
    def _toggle_recording(self):
        """切换录制状态"""
        if self._recorder.is_recording():
            self._stop_recording()
        else:
            self._start_recording()
    
    def _start_recording(self):
        """开始录制"""
        self._recording_time = 0
        self._timer.start(1000)
        
        self.record_btn.setText("⏹️")
        self.record_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                border: none;
                border-radius: 20px;
                font-size: 20px;
                animation: pulse 1s infinite;
            }
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.1); }
                100% { transform: scale(1); }
            }
        """)
        
        self.play_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        
        # 启动录制线程
        threading.Thread(target=self._recorder.start_recording, daemon=True).start()
        
        self.recording_started.emit()
    
    def _stop_recording(self):
        """停止录制"""
        self._timer.stop()
        
        # 停止录制并获取数据
        self._audio_data = self._recorder.stop_recording()
        
        self.record_btn.setText("🎤")
        self.record_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                border: none;
                border-radius: 20px;
                font-size: 20px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        
        # 重置可视化
        self.visualizer.set_level(0)
        
        # 启用回放和清除按钮
        self.play_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        
        # 模拟语音转文字（实际应调用STT服务）
        self._simulate_stt()
        
        self.recording_stopped.emit()
    
    def _update_recording_time(self):
        """更新录制时间"""
        self._recording_time += 1
        minutes = self._recording_time // 60
        seconds = self._recording_time % 60
        self.time_label.setText(f"{minutes:02d}:{seconds:02d}")
    
    def _on_audio_level(self, level: float):
        """处理音频级别回调"""
        self.visualizer.set_level(level)
    
    def _play_audio(self):
        """播放录音"""
        if self._audio_data:
            threading.Thread(target=self._recorder.play_audio, args=(self._audio_data,), daemon=True).start()
    
    def _clear_audio(self):
        """清除录音"""
        self._audio_data = b''
        self.time_label.setText("00:00")
        self.play_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
    
    def _simulate_stt(self):
        """模拟语音转文字"""
        # 实际应用中应调用语音识别API
        time.sleep(1)
        
        # 模拟结果
        text = "这是语音输入的文字内容"
        self.voice_finished.emit(text)
    
    def closeEvent(self, event):
        """关闭事件"""
        if self._recorder.is_recording():
            self._recorder.stop_recording()
        self._recorder.close()
        self._timer.stop()
        super().closeEvent(event)


class VoiceMessageBubble(QFrame):
    """语音消息气泡"""
    
    def __init__(self, audio_data: bytes, duration: int, is_sent: bool = False, parent=None):
        super().__init__(parent)
        self._audio_data = audio_data
        self._duration = duration
        self._is_sent = is_sent
        self._is_playing = False
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        if self._is_sent:
            self.setStyleSheet("""
                VoiceMessageBubble {
                    background: #E3F2FD;
                    border-radius: 12px;
                    margin-left: 40px;
                }
            """)
        else:
            self.setStyleSheet("""
                VoiceMessageBubble {
                    background: #F5F5F5;
                    border-radius: 12px;
                    margin-right: 40px;
                }
            """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # 播放按钮
        self.play_btn = QPushButton()
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                border: none;
                border-radius: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton.playing {
                background-color: #10b981;
            }
        """)
        self.play_btn.setText("▶")
        self.play_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self.play_btn)
        
        # 音频波形
        waveform = QFrame()
        waveform.setStyleSheet("background-color: #e2e8f0;")
        waveform.setFixedHeight(24)
        waveform.setFixedWidth(150)
        
        wave_layout = QHBoxLayout(waveform)
        wave_layout.setContentsMargins(4, 0, 4, 0)
        wave_layout.setSpacing(1)
        
        # 创建波形条
        for i in range(30):
            bar = QFrame()
            height = 8 + (i % 5) * 4
            bar.setFixedHeight(height)
            bar.setFixedWidth(3)
            bar.setStyleSheet("background-color: #2563eb;")
            wave_layout.addWidget(bar)
        
        layout.addWidget(waveform)
        
        # 时长
        duration_label = QLabel(f"{self._duration}''")
        duration_label.setStyleSheet("font-size: 12px; color: #64748b;")
        layout.addWidget(duration_label)
    
    def _toggle_play(self):
        """切换播放状态"""
        if self._is_playing:
            self._stop_play()
        else:
            self._start_play()
    
    def _start_play(self):
        """开始播放"""
        self._is_playing = True
        self.play_btn.setText("⏸")
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                border: none;
                border-radius: 16px;
                font-size: 14px;
            }
        """)
        
        # 模拟播放（实际应调用音频播放）
        QTimer.singleShot(self._duration * 1000, self._stop_play)
    
    def _stop_play(self):
        """停止播放"""
        self._is_playing = False
        self.play_btn.setText("▶")
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                border: none;
                border-radius: 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)