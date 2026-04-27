"""
EIWizard 多媒体消息支持（视频、音频）
=====================================
P2 功能：添加更多消息类型 - 支持视频、音频消息
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSlider, QHBoxLayout
from PySide6.QtCore import Qt, Signal, Slot, QUrl, QTimer, QTime
from PySide6.QtGui import QIcon, QFont, QDesktopServices
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class VideoBubble(QWidget):
    """视频消息气泡（P2 新增）"""
    
    def __init__(self, video_path: str, role: str = 'user', parent=None):
        """
        初始化视频气泡
        
        Args:
            video_path: 视频文件路径
            role: 'user' 或 'assitant'
            parent: 父组件
        """
        super().__init__(parent)
        self.video_path = video_path
        self.role = role
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 创建视频图标和名称标签
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 10px;
                background-color: white;
            }
            QWidget:hover {
                background-color: #f5f5f5;
            }
        """)
        container.mousePressEvent = self._open_video
        
        container_layout = QVBoxLayout(container)
        
        # 视频图标
        icon_label = QLabel("🎬")
        icon_label.setStyleSheet("font-size: 32px;")
        container_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)
        
        # 视频名称
        filename = Path(self.video_path).name
        name_label = QLabel(filename)
        name_label.setStyleSheet("""
            font-size: 12px;
            color: #333333;
            padding: 5px;
        """)
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(200)
        container_layout.addWidget(name_label)
        
        # 视频时长（可选，需要解析视频文件）
        # duration_label = QLabel("00:00")
        # container_layout.addWidget(duration_label)
        
        if self.role == 'user':
            # 用户消息：右侧
            layout.addStretch()
            layout.addWidget(container)
        else:
            # 助手消息：左侧
            layout.addWidget(container)
            layout.addStretch()
        
        self.setLayout(layout)
    
    def _open_video(self, event):
        """点击视频打开"""
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.video_path))


class AudioBubble(QWidget):
    """音频消息气泡（P2 新增）"""
    
    def __init__(self, audio_path: str, role: str = 'user', parent=None):
        """
        初始化音频气泡
        
        Args:
            audio_path: 音频文件路径
            role: 'user' 或 'assitant'
            parent: 父组件
        """
        super().__init__(parent)
        self.audio_path = audio_path
        self.role = role
        self.is_playing = False
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 创建音频播放组件
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 10px;
                background-color: white;
            }
            QWidget:hover {
                background-color: #f5f5f5;
            }
        """)
        
        container_layout = QHBoxLayout(container)
        
        # 播放/暂停按钮
        self.play_btn = QLabel("▶️")
        self.play_btn.setStyleSheet("font-size: 24px; cursor: pointer;")
        self.play_btn.mousePressEvent = self._toggle_play
        container_layout.addWidget(self.play_btn)
        
        # 音频信息
        info_layout = QVBoxLayout()
        
        # 音频名称
        filename = Path(self.audio_path).name
        name_label = QLabel(filename)
        name_label.setStyleSheet("font-size: 12px; color: #333333;")
        info_layout.addWidget(name_label)
        
        # 播放进度条（简化，不实现真正进度条）
        self.progress_label = QLabel("点击播放")
        self.progress_label.setStyleSheet("font-size: 10px; color: #666666;")
        info_layout.addWidget(self.progress_label)
        
        container_layout.addLayout(info_layout)
        
        if self.role == 'user':
            # 用户消息：右侧
            layout.addStretch()
            layout.addWidget(container)
        else:
            # 助手消息：左侧
            layout.addWidget(container)
            layout.addStretch()
        
        self.setLayout(layout)
    
    def _toggle_play(self, event):
        """切换播放/暂停状态"""
        if self.is_playing:
            # 暂停
            self.is_playing = False
            self.play_btn.setText("▶️")
            self.progress_label.setText("已暂停")
            # TODO: 暂停音频播放
        else:
            # 播放
            self.is_playing = True
            self.play_btn.setText("⏸️")
            self.progress_label.setText("正在播放...")
            # TODO: 开始音频播放（使用 QMediaPlayer）
            # 模拟播放 5 秒后自动暂停
            QTimer.singleShot(5000, self._on_playback_finished)
    
    def _on_playback_finished(self):
        """播放完成"""
        self.is_playing = False
        self.play_btn.setText("▶️")
        self.progress_label.setText("播放完成")
    
    def _open_audio(self, event):
        """点击音频打开文件"""
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.audio_path))


class MediaMessageHandler:
    """多媒体消息处理器（工具类，可集成到 EIWizardChat）"""
    
    @staticmethod
    def is_video_file(file_path: str) -> bool:
        """判断是否为视频文件"""
        video_exts = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']
        return Path(file_path).suffix.lower() in video_exts
    
    @staticmethod
    def is_audio_file(file_path: str) -> bool:
        """判断是否为音频文件"""
        audio_exts = ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.wma', '.m4a']
        return Path(file_path).suffix.lower() in audio_exts
    
    @staticmethod
    def create_media_bubble(file_path: str, role: str = 'user') -> QWidget:
        """
        根据文件类型创建对应的媒体气泡
        
        Args:
            file_path: 文件路径
            role: 'user' 或 'assitant'
            
        Returns:
            媒体气泡组件
        """
        if MediaMessageHandler.is_video_file(file_path):
            return VideoBubble(file_path, role)
        elif MediaMessageHandler.is_audio_file(file_path):
            return AudioBubble(file_path, role)
        else:
            return None
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """格式化时长（秒 → MM:SS）"""
        return QTime(0, 0, 0).addSecs(seconds).toString("mm:ss")
