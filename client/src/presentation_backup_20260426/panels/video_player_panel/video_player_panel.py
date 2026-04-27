# -*- coding: utf-8 -*-
"""
视频播放器面板
基于 LibVLC 的 PyQt6 视频播放器界面
"""

import os
import logging
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QFrame, QFileDialog,
    QGroupBox, QListWidget, QListWidgetItem, QToolBar,
    QDial, QSizePolicy, QStyle, QStyleOptionSlider,
    QAbstractItemView, QMenuBar, QMenu
)
from PyQt6.QtCore import Qt, QTimer, QUrl, QSize, pyqtSignal, QPoint
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor, QContextMenuEvent
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

logger = logging.getLogger(__name__)

# 尝试导入 VLC
try:
    import vlc
    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False
    logger.warning("python-vlc 未安装，请运行: pip install python-vlc")


class VideoPlayerPanel(QWidget):
    """
    视频播放器面板

    功能：
    - 本地/网络视频播放
    - 播放控制（播放/暂停/停止/跳转）
    - 音量控制
    - 播放列表管理
    - 字幕加载
    - 全屏切换
    - 截图功能
    """

    # 信号定义
    media_loaded = pyqtSignal(str)       # 媒体加载完成
    playback_state_changed = pyqtSignal(str)  # 播放状态变化
    position_changed = pyqtSignal(float, float)  # 位置变化 (当前, 总时长)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = None
        self._playlist = None
        self._subtitle_manager = None
        self._is_fullscreen = False
        self._volume = 100
        self._is_muted = False

        self._setup_ui()
        self._init_player()
        self._init_timers()

    def _setup_ui(self):
        """设置 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建菜单栏
        self._create_menu_bar()

        # 创建视频显示区域
        self._create_video_area()

        # 创建控制栏
        self._create_control_bar()

        # 创建播放列表区域
        self._create_playlist_area()

        # 布局
        main_layout.addWidget(self.video_container)
        main_layout.addWidget(self.controls_frame)
        main_layout.addWidget(self.playlist_widget)

        # 设置拉伸因子：视频区域优先拉伸
        main_layout.setStretch(0, 3)
        main_layout.setStretch(1, 0)
        main_layout.setStretch(2, 1)

        self.setMinimumSize(640, 480)

    def _create_menu_bar(self):
        """创建菜单栏"""
        self.menu_bar = QMenuBar()

        # 文件菜单
        file_menu = self.menu_bar.addMenu("文件")

        self.action_open_file = QAction("打开本地视频...", self)
        self.action_open_file.triggered.connect(self._on_open_file)
        file_menu.addAction(self.action_open_file)

        self.action_open_url = QAction("打开网络地址...", self)
        self.action_open_url.triggered.connect(self._on_open_url)
        file_menu.addAction(self.action_open_url)

        file_menu.addSeparator()

        self.action_load_subtitle = QAction("加载字幕...", self)
        self.action_load_subtitle.triggered.connect(self._on_load_subtitle)
        file_menu.addAction(self.action_load_subtitle)

        file_menu.addSeparator()

        self.action_screenshot = QAction("截图", self)
        self.action_screenshot.triggered.connect(self._on_screenshot)
        file_menu.addAction(self.action_screenshot)

        # 播放菜单
        play_menu = self.menu_bar.addMenu("播放")

        self.action_play_pause = QAction("播放/暂停", self)
        self.action_play_pause.triggered.connect(self._on_play_pause)
        play_menu.addAction(self.action_play_pause)

        self.action_stop = QAction("停止", self)
        self.action_stop.triggered.connect(self._on_stop)
        play_menu.addAction(self.action_stop)

        play_menu.addSeparator()

        self.action_prev = QAction("上一个", self)
        self.action_prev.triggered.connect(self._on_prev)
        play_menu.addAction(self.action_prev)

        self.action_next = QAction("下一个", self)
        self.action_next.triggered.connect(self._on_next)
        play_menu.addAction(self.action_next)

        # 视图菜单
        view_menu = self.menu_bar.addMenu("视图")

        self.action_fullscreen = QAction("全屏", self)
        self.action_fullscreen.triggered.connect(self._on_toggle_fullscreen)
        view_menu.addAction(self.action_fullscreen)

        # 音频菜单
        audio_menu = self.menu_bar.addMenu("音频")

        self.action_mute = QAction("静音", self)
        self.action_mute.triggered.connect(self._on_toggle_mute)
        audio_menu.addAction(self.action_mute)

    def _create_video_area(self):
        """创建视频显示区域"""
        self.video_container = QFrame()
        self.video_container.setStyleSheet("background-color: #000000;")
        self.video_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.video_layout = QVBoxLayout(self.video_container)
        self.video_layout.setContentsMargins(0, 0, 0, 0)

        # 占位符标签
        self.video_placeholder = QLabel("拖放视频文件到此处\n或点击「打开本地视频」", self.video_container)
        self.video_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_placeholder.setStyleSheet("""
            color: #888888;
            font-size: 16px;
            background-color: #000000;
        """)
        self.video_layout.addWidget(self.video_placeholder)

        # 视频播放标签
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setVisible(False)
        self.video_layout.addWidget(self.video_label)

    def _create_control_bar(self):
        """创建播放控制栏"""
        self.controls_frame = QFrame()
        self.controls_frame.setMaximumHeight(120)
        controls_layout = QVBoxLayout(self.controls_frame)

        # 进度条
        progress_layout = QHBoxLayout()

        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setMinimumWidth(120)
        progress_layout.addWidget(self.time_label)

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setValue(0)
        self.progress_slider.sliderMoved.connect(self._on_seek)
        self.progress_slider.sliderPressed.connect(self._on_seek_start)
        progress_layout.addWidget(self.progress_slider)

        controls_layout.addLayout(progress_layout)

        # 播放控制按钮
        buttons_layout = QHBoxLayout()

        # 音量控制
        volume_layout = QHBoxLayout()

        self.volume_btn = QPushButton("🔊")
        self.volume_btn.setMaximumWidth(40)
        self.volume_btn.clicked.connect(self._on_toggle_mute)
        volume_layout.addWidget(self.volume_btn)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        volume_layout.addWidget(self.volume_slider)

        buttons_layout.addLayout(volume_layout)

        buttons_layout.addStretch()

        # 播放按钮
        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setMaximumWidth(50)
        self.btn_prev.clicked.connect(self._on_prev)
        buttons_layout.addWidget(self.btn_prev)

        self.btn_play_pause = QPushButton("▶")
        self.btn_play_pause.setMaximumWidth(60)
        self.btn_play_pause.setMinimumHeight(40)
        self.btn_play_pause.clicked.connect(self._on_play_pause)
        buttons_layout.addWidget(self.btn_play_pause)

        self.btn_stop = QPushButton("⏹")
        self.btn_stop.setMaximumWidth(50)
        self.btn_stop.clicked.connect(self._on_stop)
        buttons_layout.addWidget(self.btn_stop)

        self.btn_next = QPushButton("⏭")
        self.btn_next.setMaximumWidth(50)
        self.btn_next.clicked.connect(self._on_next)
        buttons_layout.addWidget(self.btn_next)

        buttons_layout.addStretch()

        # 全屏按钮
        self.btn_fullscreen = QPushButton("⛶")
        self.btn_fullscreen.setMaximumWidth(50)
        self.btn_fullscreen.clicked.connect(self._on_toggle_fullscreen)
        buttons_layout.addWidget(self.btn_fullscreen)

        controls_layout.addLayout(buttons_layout)

    def _create_playlist_area(self):
        """创建播放列表区域"""
        self.playlist_widget = QFrame()
        playlist_layout = QVBoxLayout(self.playlist_widget)

        # 标题栏
        header_layout = QHBoxLayout()
        title = QLabel("播放列表")
        title.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.btn_add = QPushButton("+ 添加")
        self.btn_add.setMaximumWidth(80)
        self.btn_add.clicked.connect(self._on_add_to_playlist)
        header_layout.addWidget(self.btn_add)

        self.btn_clear = QPushButton("清空")
        self.btn_clear.setMaximumWidth(60)
        self.btn_clear.clicked.connect(self._on_clear_playlist)
        header_layout.addWidget(self.btn_clear)

        playlist_layout.addLayout(header_layout)

        # 列表
        self.playlist_list = QListWidget()
        self.playlist_list.itemDoubleClicked.connect(self._on_playlist_item_double_click)
        playlist_layout.addWidget(self.playlist_list)

    def _init_player(self):
        """初始化播放器"""
        if VLC_AVAILABLE:
            try:
                from client.src.business.video_player import VideoPlayer, Playlist, SubtitleManager

                self._player = VideoPlayer()
                self._playlist = Playlist()
                self._subtitle_manager = SubtitleManager()

                # 绑定 VLC 到 Qt 窗口
                self._bind_vlc_to_qt()

                logger.info("VLC 播放器初始化成功")
            except Exception as e:
                logger.error(f"VLC 播放器初始化失败: {e}")
                self._player = None
        else:
            logger.warning("VLC 不可用，使用 Qt 多媒体回退")
            self._init_qt_player()

    def _init_qt_player(self):
        """初始化 Qt 多媒体播放器（备选方案）"""
        self._media_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._media_player.setAudioOutput(self._audio_output)

        self._video_widget = QVideoWidget()
        self._media_player.setVideoOutput(self._video_widget)

        # 信号连接
        self._media_player.positionChanged.connect(self._on_position_changed)
        self._media_player.durationChanged.connect(self._on_duration_changed)
        self._media_player.playbackStateChanged.connect(self._on_playback_state_changed)

    def _init_timers(self):
        """初始化定时器"""
        # 进度更新定时器
        self._update_timer = QTimer()
        self._update_timer.setInterval(200)
        self._update_timer.timeout.connect(self._update_progress)
        self._update_timer.start()

    def _bind_vlc_to_qt(self):
        """绑定 VLC 到 Qt 窗口"""
        if not self._player or not hasattr(self, '_media_player'):
            return

        # 获取窗口句柄
        try:
            import ctypes
            ctypes.windll.user32.SetParent(self.winId(), None)
        except Exception:
            pass

    # 播放控制

    def load_media(self, url: str):
        """
        加载媒体

        Args:
            url: 媒体 URL 或文件路径
        """
        if not url:
            return

        logger.info(f"加载媒体: {url}")

        if VLC_AVAILABLE and self._player:
            self._player.load(url)
            self._player.play()
            self.video_placeholder.setVisible(False)
        elif hasattr(self, '_media_player'):
            # Qt 多媒体回退
            self._media_player.setSource(QUrl.fromUserInput(url))
            self._media_player.play()
            self.video_placeholder.setVisible(False)

        self.media_loaded.emit(url)

    def play(self):
        """播放"""
        if VLC_AVAILABLE and self._player:
            self._player.play()
        elif hasattr(self, '_media_player'):
            self._media_player.play()

    def pause(self):
        """暂停"""
        if VLC_AVAILABLE and self._player:
            self._player.pause()
        elif hasattr(self, '_media_player'):
            self._media_player.pause()

    def stop(self):
        """停止"""
        if VLC_AVAILABLE and self._player:
            self._player.stop()
        elif hasattr(self, '_media_player'):
            self._media_player.stop()

    def seek(self, position: float):
        """
        跳转

        Args:
            position: 位置 (0.0 - 1.0)
        """
        if VLC_AVAILABLE and self._player:
            self._player.seek(position)
        elif hasattr(self, '_media_player'):
            duration = self._media_player.duration()
            self._media_player.setPosition(int(position * duration))

    def set_volume(self, volume: int):
        """
        设置音量

        Args:
            volume: 音量 0-100
        """
        volume = max(0, min(100, volume))
        self._volume = volume

        if VLC_AVAILABLE and self._player:
            self._player.set_volume(volume)
        elif hasattr(self, '_audio_output'):
            self._audio_output.setVolume(volume / 100.0)

        # 更新按钮图标
        if volume == 0:
            self.volume_btn.setText("🔇")
        elif volume < 50:
            self.volume_btn.setText("🔉")
        else:
            self.volume_btn.setText("🔊")

    def toggle_play_pause(self):
        """切换播放/暂停"""
        if VLC_AVAILABLE and self._player:
            if self._player.is_playing():
                self.pause()
            else:
                self.play()
        elif hasattr(self, '_media_player'):
            if self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.pause()
            else:
                self.play()

    # 事件处理

    def _on_open_file(self):
        """打开本地文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频文件",
            "",
            "视频文件 (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg);;所有文件 (*.*)"
        )

        if file_path:
            self.load_media(file_path)
            self._add_to_playlist(file_path, os.path.basename(file_path))

    def _on_open_url(self):
        """打开网络地址"""
        from PyQt6.QtWidgets import QInputDialog
        url, ok = QInputDialog.getText(self, "打开网络地址", "请输入视频 URL:")
        if ok and url:
            self.load_media(url)
            self._add_to_playlist(url, url)

    def _on_load_subtitle(self):
        """加载字幕文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择字幕文件",
            "",
            "字幕文件 (*.srt *.ass *.ssa *.sub *.vtt);;所有文件 (*.*)"
        )

        if file_path and self._subtitle_manager:
            track = self._subtitle_manager.load_subtitle(file_path)
            if track and VLC_AVAILABLE and self._player:
                self._player.load_external_subtitle(file_path)

    def _on_screenshot(self):
        """截图"""
        if VLC_AVAILABLE and self._player:
            from datetime import datetime
            import tempfile

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_path = os.path.join(tempfile.gettempdir(), f"screenshot_{timestamp}.png")

            path, _ = QFileDialog.getSaveFileName(
                self,
                "保存截图",
                default_path,
                "PNG 图片 (*.png)"
            )

            if path:
                if self._player.take_snapshot(path):
                    logger.info(f"截图已保存: {path}")
                else:
                    logger.error("截图失败")

    def _on_play_pause(self):
        """播放/暂停按钮点击"""
        self.toggle_play_pause()

    def _on_stop(self):
        """停止按钮点击"""
        self.stop()

    def _on_prev(self):
        """上一个按钮点击"""
        if self._playlist:
            item = self._playlist.play_previous()
            if item:
                self.load_media(item.url)

    def _on_next(self):
        """下一个按钮点击"""
        if self._playlist:
            item = self._playlist.play_next()
            if item:
                self.load_media(item.url)

    def _on_seek(self, value: int):
        """进度条拖动"""
        position = value / 1000.0
        self.seek(position)

    def _on_seek_start(self):
        """进度条开始拖动"""
        # 暂停更新定时器
        self._update_timer.stop()

    def _on_volume_changed(self, value: int):
        """音量改变"""
        self.set_volume(value)

    def _on_toggle_mute(self):
        """静音切换"""
        self._is_muted = not self._is_muted

        if VLC_AVAILABLE and self._player:
            self._player.set_mute(self._is_muted)
        elif hasattr(self, '_audio_output'):
            self._audio_output.setMuted(self._is_muted)

        self.volume_btn.setText("🔇" if self._is_muted else "🔊")

    def _on_toggle_fullscreen(self):
        """全屏切换"""
        self._is_fullscreen = not self._is_fullscreen

        if self._is_fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()

    def _on_position_changed(self, position: int):
        """播放位置改变（Qt 多媒体）"""
        duration = self._media_player.duration()
        if duration > 0:
            self._update_time_label(position, duration)
            self.position_changed.emit(position, duration)

    def _on_duration_changed(self, duration: int):
        """时长改变"""
        pass

    def _on_playback_state_changed(self, state):
        """播放状态改变"""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play_pause.setText("⏸")
            self.playback_state_changed.emit("playing")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.btn_play_pause.setText("▶")
            self.playback_state_changed.emit("paused")
        else:
            self.btn_play_pause.setText("▶")
            self.playback_state_changed.emit("stopped")

    # 播放列表

    def _add_to_playlist(self, url: str, title: str):
        """添加到播放列表"""
        if self._playlist:
            self._playlist.add(url, title)
            self._refresh_playlist_ui()

    def _on_playlist_item_double_click(self, item: QListWidgetItem):
        """播放列表项双击"""
        index = self.playlist_list.row(item)
        if self._playlist:
            playlist_item = self._playlist.play(index)
            if playlist_item:
                self.load_media(playlist_item.url)

    def _on_add_to_playlist(self):
        """添加按钮点击"""
        self._on_open_file()

    def _on_clear_playlist(self):
        """清空按钮点击"""
        if self._playlist:
            self._playlist.clear()
            self._refresh_playlist_ui()

    def _refresh_playlist_ui(self):
        """刷新播放列表 UI"""
        self.playlist_list.clear()

        if self._playlist:
            for item in self._playlist.get_items():
                list_item = QListWidgetItem(item.title)
                list_item.setData(Qt.ItemDataRole.UserRole, item.url)
                self.playlist_list.addItem(list_item)

    # 进度更新

    def _update_progress(self):
        """更新进度"""
        if VLC_AVAILABLE and self._player:
            pos = self._player.get_position()
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(int(pos.position * 1000))
            self.progress_slider.blockSignals(False)

            self._update_time_label(pos.time, pos.duration)
        elif hasattr(self, '_media_player') and not self._update_timer.isNull():
            # Qt 多媒体模式
            position = self._media_player.position()
            duration = self._media_player.duration()

            if duration > 0:
                self.progress_slider.blockSignals(True)
                self.progress_slider.setValue(int(position / duration * 1000))
                self.progress_slider.blockSignals(False)

                self._update_time_label(position, duration)

    def _update_time_label(self, current_ms: float, duration_ms: float):
        """更新时间标签"""
        current = self._format_time(current_ms / 1000.0)
        total = self._format_time(duration_ms / 1000.0)
        self.time_label.setText(f"{current} / {total}")

    @staticmethod
    def _format_time(seconds: float) -> str:
        """格式化时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    # 拖放支持

    def dragEnterEvent(self, event):
        """拖放进入"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """拖放放下"""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path and os.path.exists(file_path):
                if os.path.isfile(file_path):
                    self.load_media(file_path)
                    self._add_to_playlist(file_path, os.path.basename(file_path))

    # 公共 API

    def get_player(self):
        """获取播放器对象"""
        if VLC_AVAILABLE:
            return self._player
        return getattr(self, '_media_player', None)

    def get_playlist(self):
        """获取播放列表对象"""
        return self._playlist

    def get_subtitle_manager(self):
        """获取字幕管理器"""
        return self._subtitle_manager

    def is_playing(self) -> bool:
        """是否正在播放"""
        if VLC_AVAILABLE and self._player:
            return self._player.is_playing()
        elif hasattr(self, '_media_player'):
            return self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        return False

    def release(self):
        """释放播放器资源"""
        if VLC_AVAILABLE and self._player:
            self._player.release()

        if hasattr(self, '_media_player'):
            self._media_player.stop()

        self._update_timer.stop()
