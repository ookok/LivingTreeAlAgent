"""
语音消息组件 - Voice Message Widget
支持录音、播放、右键菜单（删除/转文字/重发）

功能:
1. 录音模式: 按住录制, 释放发送
2. 播放模式: 点击播放/暂停, 显示进度
3. 右键菜单: 删除/转文字/重发
"""

import os
import time
import uuid
import wave
import struct
import tempfile
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QSlider, QMenu, QFileDialog, QMessageBox,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QFrame
)
from PyQt6.QtCore import (
    Qt, QSize, QTimer, QUrl, QFileInfo,
    pyqtSignal, QRectF, QObject
)
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QAction
from PyQt6.QtMultimedia import (
    QMediaPlayer, QAudioOutput,
    QMediaDevices
)

# QAudioRecorder 可能不可用
try:
    from PyQt6.QtMultimedia import QAudioRecorder
except ImportError:
    QAudioRecorder = None

# 全局音频设备检查
_has_audio_input = False
try:
    _audio_devices = QMediaDevices.audioInputs()
    _has_audio_input = len(_audio_devices) > 0
except Exception:
    pass


# ============ 录音状态 ============

class RecordingState:
    """录音状态"""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"


# ============ 语音消息气泡组件 ============

class VoiceBubble(QFrame):
    """
    语音消息气泡 - 用于聊天界面显示

    支持:
    - 点击播放/暂停
    - 显示时长
    - 右键菜单 (删除/转文字/重发)
    - 发送失败时显示重发按钮
    """

    # 信号
    playClicked = pyqtSignal(str)          # msg_id - 请求播放
    pauseClicked = pyqtSignal(str)         # msg_id - 请求暂停
    deleteClicked = pyqtSignal(str)        # msg_id - 请求删除
    transcribeClicked = pyqtSignal(str)    # msg_id - 请求转文字
    resendClicked = pyqtSignal(str)        # msg_id - 请求重发

    def __init__(
        self,
        msg_id: str,
        duration: float,  # 秒
        file_path: str = "",
        is_outgoing: bool = True,
        status: str = "sent",  # sending/sent/failed
        parent=None
    ):
        super().__init__(parent)
        self.msg_id = msg_id
        self.duration = duration
        self.file_path = file_path
        self.is_outgoing = is_outgoing
        self.status = status
        self.is_playing = False
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # 播放/暂停按钮
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(36, 36)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                border: none;
                border-radius: 18px;
                font-size: 14px;
                color: white;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.3);
            }
        """)
        self.play_btn.clicked.connect(self._on_play_clicked)

        # 波形/进度显示区
        wave_layout = QVBoxLayout()
        wave_layout.setSpacing(2)

        # 波形显示
        self.wave_widget = WaveformWidget(self.duration)
        self.wave_widget.setFixedHeight(24)
        wave_layout.addWidget(self.wave_widget)

        # 时长标签
        duration_text = self._format_duration(self.duration)
        self.duration_label = QLabel(duration_text)
        self.duration_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 11px;")

        wave_layout.addWidget(self.duration_label)

        layout.addLayout(wave_layout)

        # 状态/操作按钮
        if self.status == "failed":
            self.resend_btn = QPushButton("↻")
            self.resend_btn.setFixedSize(24, 24)
            self.resend_btn.setToolTip("重发")
            self.resend_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    border: none;
                    border-radius: 12px;
                    font-size: 12px;
                    color: white;
                }
                QPushButton:hover { background-color: #dc2626; }
            """)
            self.resend_btn.clicked.connect(self._on_resend_clicked)
            layout.addWidget(self.resend_btn)
        elif self.status == "sending":
            self.sending_label = QLabel("⏳")
            self.sending_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 12px;")
            layout.addWidget(self.sending_label)

        # 设置气泡样式
        if self.is_outgoing:
            self.setStyleSheet("""
                QFrame {
                    background-color: #2563eb;
                    border-radius: 16px;
                    min-width: 180px;
                    max-width: 280px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #2d2d44;
                    border-radius: 16px;
                    min-width: 180px;
                    max-width: 280px;
                }
            """)

        # 右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _format_duration(self, seconds: float) -> str:
        """格式化时长"""
        if seconds < 60:
            return f"{int(seconds)}″"
        else:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}′{secs}″"

    def _on_play_clicked(self):
        """播放/暂停点击"""
        if self.is_playing:
            self.pauseClicked.emit(self.msg_id)
        else:
            self.playClicked.emit(self.msg_id)

    def _on_resend_clicked(self):
        """重发点击"""
        self.resendClicked.emit(self.msg_id)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu(self)

        # 播放/暂停
        if self.is_playing:
            play_action = QAction("⏸ 暂停", self)
        else:
            play_action = QAction("▶ 播放", self)
        play_action.triggered.connect(self._on_play_clicked)
        menu.addAction(play_action)

        menu.addSeparator()

        # 转文字
        transcribe_action = QAction("📝 转文字", self)
        transcribe_action.triggered.connect(self._on_transcribe)
        menu.addAction(transcribe_action)

        # 重发 (仅发送失败时)
        if self.status == "failed":
            resend_action = QAction("↻ 重发", self)
            resend_action.triggered.connect(self._on_resend_clicked)
            menu.addAction(resend_action)

        # 删除
        delete_action = QAction("🗑 删除", self)
        delete_action.triggered.connect(self._on_delete)
        menu.addAction(delete_action)

        menu.exec(self.mapToGlobal(pos))

    def _on_transcribe(self):
        """转文字"""
        self.transcribeClicked.emit(self.msg_id)

    def _on_delete(self):
        """删除"""
        self.deleteClicked.emit(self.msg_id)

    def set_playing(self, playing: bool):
        """设置播放状态"""
        self.is_playing = playing
        self.play_btn.setText("⏸" if playing else "▶")
        if playing:
            self.wave_widget.start_animation()
        else:
            self.wave_widget.stop_animation()

    def set_progress(self, progress: float):
        """设置播放进度 (0.0 - 1.0)"""
        self.wave_widget.set_progress(progress)


# ============ 波形显示组件 ============

class WaveformWidget(QWidget):
    """简易波形显示组件"""

    def __init__(self, duration: float = 0, parent=None):
        super().__init__(parent)
        self.duration = duration
        self.progress = 0.0  # 0.0 - 1.0
        self.is_animating = False
        self.animation_pos = 0

        # 生成模拟波形数据
        self.waveform_data = self._generate_waveform(50)

        # 动画定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)

    def _generate_waveform(self, num_bars: int) -> list:
        """生成模拟波形数据"""
        import random
        random.seed(42)  # 固定种子保证一致外观
        return [0.3 + random.random() * 0.7 for _ in range(num_bars)]

    def _animate(self):
        """动画更新"""
        if self.is_animating:
            self.animation_pos = (self.animation_pos + 1) % 100
            self.update()

    def start_animation(self):
        """开始动画"""
        self.is_animating = True
        if not self.timer.isActive():
            self.timer.start(50)

    def stop_animation(self):
        """停止动画"""
        self.is_animating = False
        self.timer.stop()
        self.update()

    def set_progress(self, progress: float):
        """设置播放进度"""
        self.progress = max(0.0, min(1.0, progress))
        self.update()

    def paintEvent(self, event):
        """绘制波形"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.is_animating:
            # 录音中: 动态波形
            painter.fillRect(self.rect(), QColor(255, 255, 255, 100))
            # 绘制跳动的条形
            w = self.width()
            h = self.height()
            num_bars = len(self.waveform_data)
            bar_width = w / num_bars
            for i, amp in enumerate(self.waveform_data):
                # 添加动画偏移
                animated_amp = amp * (0.5 + 0.5 * abs((i - self.animation_pos / 100 * num_bars) % num_bars - num_bars / 2) / (num_bars / 2))
                bar_h = int(h * animated_amp)
                painter.fillRect(
                    int(i * bar_width),
                    (h - bar_h) // 2,
                    max(1, int(bar_width - 1)),
                    bar_h,
                    QColor(255, 255, 255, 180)
                )
        else:
            # 播放模式: 显示进度
            w = self.width()
            h = self.height()
            num_bars = len(self.waveform_data)
            bar_width = w / num_bars
            progress_x = int(w * self.progress)

            for i, amp in enumerate(self.waveform_data):
                bar_h = max(2, int(h * amp))
                x = int(i * bar_width)

                # 根据进度设置颜色
                if x < progress_x:
                    color = QColor(255, 255, 255, 220)  # 已播放
                else:
                    color = QColor(255, 255, 255, 80)   # 未播放

                painter.fillRect(
                    x,
                    (h - bar_h) // 2,
                    max(1, int(bar_width - 1)),
                    bar_h,
                    color
                )


# ============ 录音控制器 ============

class VoiceRecorder(QObject):
    """
    语音录音控制器

    使用 Qt 多媒体 API 录音, 支持:
    - 开始/停止录音
    - 暂停/恢复
    - 获取录音时长
    - 保存为 WAV 格式
    """

    recordingFinished = pyqtSignal(str)  # file_path - 录音完成
    recordingError = pyqtSignal(str)     # error_msg - 录音错误
    durationChanged = pyqtSignal(float)  # seconds - 时长变化

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = RecordingState.IDLE
        self.duration = 0
        self.output_path = ""
        self._recorder = None
        self._audio_output = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_duration_tick)
        self._setup_recorder()

    def _setup_recorder(self):
        """初始化录音机"""
        if not _has_audio_input:
            return

        try:
            self._recorder = QAudioRecorder(self)
            self._recorder.setAudioInput("")
            self._recorder.durationChanged.connect(self._on_duration_changed)
        except Exception as e:
            print(f"录音机初始化失败: {e}")

    def _on_duration_changed(self, ms):
        """录音时长变化"""
        self.duration = ms / 1000
        self.durationChanged.emit(self.duration)

    def _on_duration_tick(self):
        """定时更新时长"""
        if self.state == RecordingState.RECORDING:
            self.duration += 0.1
            self.durationChanged.emit(self.duration)

    def is_available(self) -> bool:
        """检查录音是否可用"""
        return _has_audio_input and self._recorder is not None

    def start_recording(self, output_dir: str = "") -> bool:
        """开始录音"""
        if not self.is_available():
            self.recordingError.emit("录音设备不可用")
            return False

        try:
            # 生成输出文件路径
            if not output_dir:
                output_dir = tempfile.gettempdir()
            filename = f"voice_{int(time.time())}_{uuid.uuid4().hex[:8]}.wav"
            self.output_path = os.path.join(output_dir, filename)

            # 配置录音机
            self._recorder.setOutputLocation(QUrl.fromLocalFile(self.output_path))
            self._recorder.record()

            self.state = RecordingState.RECORDING
            self.duration = 0
            self._timer.start(100)

            return True
        except Exception as e:
            self.recordingError.emit(f"开始录音失败: {e}")
            return False

    def stop_recording(self) -> str:
        """停止录音并返回文件路径"""
        if self.state == RecordingState.IDLE:
            return ""

        try:
            self._recorder.stop()
            self._timer.stop()
            self.state = RecordingState.IDLE

            if os.path.exists(self.output_path):
                self.recordingFinished.emit(self.output_path)
                return self.output_path
            else:
                self.recordingError.emit("录音文件未生成")
                return ""
        except Exception as e:
            self.recordingError.emit(f"停止录音失败: {e}")
            return ""

    def pause_recording(self):
        """暂停录音"""
        if self.state == RecordingState.RECORDING and self._recorder:
            self._recorder.pause()
            self._timer.stop()
            self.state = RecordingState.PAUSED

    def resume_recording(self):
        """恢复录音"""
        if self.state == RecordingState.PAUSED and self._recorder:
            self._recorder.record()
            self._timer.start(100)
            self.state = RecordingState.RECORDING


# ============ 语音播放器 ============

class VoicePlayer(QObject):
    """
    语音消息播放器

    使用 Qt 多媒体播放, 支持:
    - 播放/暂停
    - 进度控制
    - 播放完成通知
    """

    playbackFinished = pyqtSignal(str)   # msg_id - 播放完成
    playbackError = pyqtSignal(str, str)  # msg_id, error - 播放错误
    progressChanged = pyqtSignal(str, float)  # msg_id, progress (0.0-1.0)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        self._current_msg_id = ""
        self._is_playing = False
        self._duration = 0

        # 连接信号
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)

    def play(self, msg_id: str, file_path: str):
        """播放语音"""
        if not os.path.exists(file_path):
            self.playbackError.emit(msg_id, "文件不存在")
            return

        # 如果是同一文件, 恢复播放
        if self._current_msg_id == msg_id and self._player.playbackState() == QMediaPlayer.PausedState:
            self._player.play()
            return

        # 新文件
        self._current_msg_id = msg_id
        self._player.setSource(QUrl.fromLocalFile(file_path))
        self._player.play()

    def pause(self):
        """暂停播放"""
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()

    def resume(self):
        """恢复播放"""
        if self._player.playbackState() == QMediaPlayer.PausedState:
            self._player.play()

    def stop(self):
        """停止播放"""
        self._player.stop()
        self._current_msg_id = ""

    def seek(self, msg_id: str, progress: float):
        """跳转进度"""
        if self._current_msg_id == msg_id and self._duration > 0:
            position = int(progress * self._duration)
            self._player.setPosition(position)

    def _on_position_changed(self, position: int):
        """播放位置变化"""
        if self._duration > 0 and self._current_msg_id:
            progress = position / self._duration
            self.progressChanged.emit(self._current_msg_id, progress)

    def _on_duration_changed(self, duration: int):
        """时长变化"""
        self._duration = duration

    def _on_state_changed(self, state):
        """播放状态变化"""
        if state == QMediaPlayer.StoppedState and self._current_msg_id:
            self.playbackFinished.emit(self._current_msg_id)
            self._current_msg_id = ""


# ============ 录音按钮组件 ============

class RecordButton(QPushButton):
    """
    录音按钮

    支持:
    - 按住录音
    - 滑动取消
    - 显示录音时长
    """

    recordingStarted = pyqtSignal()
    recordingFinished = pyqtSignal(str)  # file_path
    recordingCancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recorder = VoiceRecorder(self)
        self.recorder.recordingFinished.connect(self._on_recording_finished)
        self.recorder.recordingError.connect(self._on_recording_error)

        self._is_recording = False
        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        self.setText("🎤")
        self.setFixedSize(40, 40)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 20px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.1);
                border-radius: 20px;
            }
            QPushButton:pressed {
                background-color: rgba(239,68,68,0.3);
            }
        """)
        self.setToolTip("按住录音")

    def mousePressEvent(self, event):
        """鼠标按下 - 开始录音"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.recorder.is_available():
                if self.recorder.start_recording():
                    self._is_recording = True
                    self.recordingStarted.emit()
                    self.setStyleSheet("""
                        QPushButton {
                            background-color: rgba(239,68,68,0.3);
                            border-radius: 20px;
                            font-size: 20px;
                        }
                    """)
                else:
                    QMessageBox.warning(self, "录音失败", "无法访问麦克风")
            else:
                QMessageBox.warning(self, "录音不可用", "系统没有检测到麦克风设备")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放 - 停止录音"""
        if event.button() == Qt.MouseButton.LeftButton and self._is_recording:
            self._is_recording = False
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    font-size: 20px;
                }
                QPushButton:hover {
                    background-color: rgba(255,255,255,0.1);
                    border-radius: 20px;
                }
            """)
            file_path = self.recorder.stop_recording()
            if file_path:
                self.recordingFinished.emit(file_path)
        super().mouseReleaseEvent(event)

    def _on_recording_finished(self, file_path: str):
        """录音完成"""
        pass

    def _on_recording_error(self, error: str):
        """录音错误"""
        self._is_recording = False
        QMessageBox.warning(self, "录音错误", error)


# ============ 录音指示器组件 ============

class RecordingIndicator(QWidget):
    """
    录音状态指示器

    显示:
    - 录音时长
    - 取消提示
    - 波形动画
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.duration = 0
        self._setup_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def _setup_ui(self):
        """设置 UI"""
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(239,68,68,0.9);
                border-radius: 16px;
                padding: 8px 16px;
            }
        """)
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # 红点闪烁
        self.dot_label = QLabel("●")
        self.dot_label.setStyleSheet("color: white; font-size: 12px;")
        layout.addWidget(self.dot_label)

        # 时长
        self.duration_label = QLabel("0:00")
        self.duration_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        layout.addWidget(self.duration_label)

        # 取消提示
        self.cancel_label = QLabel("↗ 取消")
        self.cancel_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 12px;")
        layout.addWidget(self.cancel_label)

    def start(self, duration: float = 0):
        """开始显示"""
        self.duration = duration
        self._update_display()
        self.show()
        self._timer.start(100)

        # 闪烁定时器
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.start(500)

    def stop(self):
        """停止显示"""
        self._timer.stop()
        if hasattr(self, '_blink_timer'):
            self._blink_timer.stop()
        self.hide()

    def _tick(self):
        """更新时长"""
        self.duration += 0.1
        self._update_display()

    def _blink(self):
        """闪烁红点"""
        current = self.dot_label.styleSheet()
        if "font-size: 12px" in current:
            self.dot_label.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 12px;")
        else:
            self.dot_label.setStyleSheet("color: white; font-size: 12px;")

    def _update_display(self):
        """更新时长显示"""
        mins = int(self.duration // 60)
        secs = int(self.duration % 60)
        self.duration_label.setText(f"{mins}:{secs:02d}")


# ============ 便捷函数 ============

def get_voice_duration(file_path: str) -> float:
    """获取语音文件时长"""
    try:
        with wave.open(file_path, 'rb') as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            return frames / float(rate)
    except Exception:
        return 0


def create_voice_message(
    msg_id: str,
    file_path: str,
    duration: float = 0,
    is_outgoing: bool = True,
    status: str = "sent"
) -> VoiceBubble:
    """
    创建语音消息气泡的便捷函数

    Args:
        msg_id: 消息ID
        file_path: 音频文件路径
        duration: 时长(秒), 如果为0则自动获取
        is_outgoing: 是否为发送的消息
        status: 状态 (sending/sent/failed)

    Returns:
        VoiceBubble 组件
    """
    if duration <= 0:
        duration = get_voice_duration(file_path)

    return VoiceBubble(
        msg_id=msg_id,
        duration=duration,
        file_path=file_path,
        is_outgoing=is_outgoing,
        status=status
    )