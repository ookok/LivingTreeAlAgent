# -*- coding: utf-8 -*-
"""
视频播放器核心引擎
基于 LibVLC (python-vlc) 实现高性能视频播放
"""

import os
import time
import logging
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any, Union
from dataclasses import dataclass, field
from threading import Thread, Lock
import urllib.parse

logger = logging.getLogger(__name__)

# 尝试导入 VLC
try:
    import vlc
    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False
    logger.warning("python-vlc 未安装，视频播放器功能受限")


class MediaType(Enum):
    """媒体类型"""
    UNKNOWN = "unknown"
    FILE = "file"           # 本地文件
    NETWORK = "network"     # 网络流 (RTMP, HTTP, HTTPS)
    DISC = "disc"           # 光盘
    ASF = "asf"             # ASF 流
    DVB = "dvb"             # 数字视频广播


class PlaybackState(Enum):
    """播放状态"""
    IDLE = "idle"
    LOADING = "loading"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    ENDED = "ended"
    ERROR = "error"


@dataclass
class MediaInfo:
    """媒体信息"""
    title: str = ""
    artist: str = ""
    album: str = ""
    genre: str = ""
    year: int = 0
    duration: float = 0.0  # 秒
    width: int = 0
    height: int = 0
    fps: float = 0.0
    video_codec: str = ""
    audio_codec: str = ""
    audio_channels: int = 0
    sample_rate: int = 0
    bitrate: int = 0


@dataclass
class PlaybackPosition:
    """播放位置"""
    time: float = 0.0       # 毫秒
    position: float = 0.0   # 0.0-1.0
    duration: float = 0.0    # 秒


@dataclass
class PlayerConfig:
    """播放器配置"""
    # 视频设置
    fullscreen: bool = False
    fit_to_window: bool = True
    deinterlace: bool = False
    post_process: str = ""  # 视频后处理模块

    # 音频设置
    volume: int = 100        # 0-100
    mute: bool = False
    audio_track: int = -1    # -1 = 自动
    audio_delay: float = 0.0 # 毫秒

    # 字幕设置
    subtitle_track: int = -1
    subtitle_delay: float = 0.0
    subtitle_encoding: str = "UTF-8"

    # 网络设置
    network_caching: int = 300  # 毫秒
    live_caching: int = 300
    http_reconnect: bool = True
    http_continuous: bool = True

    # 高级设置
    avcodec_threads: int = 0   # 0 = 自动
    hardware_acceleration: str = "any"  # any/disable/automatic


# 全局播放器实例
_global_player: Optional["VideoPlayer"] = None
_player_lock = Lock()


class VideoPlayer:
    """
    基于 LibVLC 的视频播放器

    支持:
    - 本地视频文件播放
    - 网络流媒体 (HTTP, HTTPS, RTMP, MMS 等)
    - 字幕加载 (SRT, SSA, 内嵌)
    - 多音轨切换
    - 播放控制 (播放/暂停/停止/跳转)
    - 播放列表管理
    """

    def __init__(self, instance_options: Optional[List[str]] = None):
        """
        初始化视频播放器

        Args:
            instance_options: VLC 实例选项列表
        """
        if not VLC_AVAILABLE:
            raise RuntimeError("python-vlc 未安装，请运行: pip install python-vlc")

        self._instance: Optional[vlc.Instance] = None
        self._player: Optional[vlc.MediaPlayer] = None
        self._media: Optional[vlc.Media] = None
        self._config = PlayerConfig()
        self._state = PlaybackState.IDLE
        self._current_url: str = ""
        self._media_info = MediaInfo()
        self._event_callbacks: Dict[str, List[Callable]] = {}
        self._lock = Lock()

        # 初始化 VLC
        self._init_vlc(instance_options)

    def _init_vlc(self, options: Optional[List[str]] = None):
        """初始化 VLC 实例和播放器"""
        # 构建 VLC 选项
        default_options = [
            "--file-cache=300",           # 文件缓存 300ms
            "--network-caching=300",     # 网络缓存 300ms
            "--live-caching=300",        # 直播缓存 300ms
            "--clock-jitter=0",
            "--clock-synchro=0",
        ]

        # 添加硬件加速选项
        if self._config.hardware_acceleration == "any":
            default_options.append("--hwdec=any")
        elif self._config.hardware_acceleration == "automatic":
            default_options.append("--hwdec=auto")
        elif self._config.hardware_acceleration == "disable":
            default_options.append("--hwdec=disable")

        # 添加网络选项
        if self._config.http_reconnect:
            default_options.append("--http-reconnect")
        if self._config.http_continuous:
            default_options.append("--http-continuous")

        if options:
            default_options.extend(options)

        try:
            self._instance = vlc.Instance(default_options)
            self._player = self._instance.media_player_new()
            self._register_events()
            logger.info("VLC 播放器初始化成功")
        except Exception as e:
            logger.error(f"VLC 播放器初始化失败: {e}")
            raise

    def _register_events(self):
        """注册 VLC 事件回调"""
        if not self._player:
            return

        events = {
            vlc.EventType.MediaPlayerPlaying: self._on_playing,
            vlc.EventType.MediaPlayerPaused: self._on_paused,
            vlc.EventType.MediaPlayerStopped: self._on_stopped,
            vlc.EventType.MediaPlayerEndReached: self._on_end,
            vlc.EventType.MediaPlayerError: self._on_error,
            vlc.EventType.MediaPlayerPositionChanged: self._on_position_changed,
            vlc.EventType.MediaPlayerTimeChanged: self._on_time_changed,
            vlc.EventType.MediaPlayerLengthChanged: self._on_length_changed,
        }

        for event, callback in events.items():
            self._player.event_manager().event_attach(event, callback)

    def _create_media(self, url: str, media_type: MediaType = MediaType.UNKNOWN) -> vlc.Media:
        """
        创建 VLC 媒体对象

        Args:
            url: 媒体 URL 或文件路径
            media_type: 媒体类型

        Returns:
            vlc.Media 对象
        """
        # 根据媒体类型设置选项
        options = []

        if media_type == MediaType.NETWORK or self._is_network_url(url):
            options.append("network-caching=300")
            options.append("live-caching=300")
            options.append("http-reconnect")
            options.append("http-continuous")
        elif media_type == MediaType.DISC:
            options.append("disc-caching=300")
        else:
            options.append("file-caching=300")

        # 设置字幕编码
        if self._config.subtitle_encoding:
            options.append(f"sub-encoding={self._config.subtitle_encoding}")

        # 创建媒体
        if media_type == MediaType.FILE or (media_type == MediaType.UNKNOWN and not self._is_network_url(url)):
            # 本地文件
            media = self._instance.media_new(url, *options)
        else:
            # 网络流
            media = self._instance.media_new(url, *options)

        return media

    @staticmethod
    def _is_network_url(url: str) -> bool:
        """判断是否为网络 URL"""
        if not url:
            return False
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme in ("http", "https", "rtmp", "rtmps", "mms", "mmsh", "rtsp")

    def _emit(self, event: str, *args):
        """触发事件回调"""
        with self._lock:
            callbacks = self._event_callbacks.get(event, [])
        for callback in callbacks:
            try:
                callback(*args)
            except Exception as e:
                logger.error(f"事件回调错误 {event}: {e}")

    # 事件回调
    def _on_playing(self, event):
        self._state = PlaybackState.PLAYING
        self._emit("playing")

    def _on_paused(self, event):
        self._state = PlaybackState.PAUSED
        self._emit("paused")

    def _on_stopped(self, event):
        self._state = PlaybackState.STOPPED
        self._emit("stopped")

    def _on_end(self, event):
        self._state = PlaybackState.ENDED
        self._emit("ended")

    def _on_error(self, event):
        self._state = PlaybackState.ERROR
        self._emit("error")

    def _on_position_changed(self, event):
        if self._player:
            position = self._player.get_position()
            self._emit("position_changed", position)

    def _on_time_changed(self, event):
        if self._player:
            time_ms = self._player.get_time()
            self._emit("time_changed", time_ms / 1000.0)

    def _on_length_changed(self, event):
        if self._player:
            length_ms = self._player.get_length()
            self._emit("length_changed", length_ms / 1000.0)

    # 公共 API

    def load(self, url: str, media_type: MediaType = MediaType.UNKNOWN) -> bool:
        """
        加载媒体

        Args:
            url: 媒体 URL 或文件路径
            media_type: 媒体类型（自动检测可传 UNKNOWN）

        Returns:
            是否加载成功
        """
        with self._lock:
            try:
                self._state = PlaybackState.LOADING
                self._current_url = url

                # 创建媒体
                if media_type == MediaType.UNKNOWN:
                    if self._is_network_url(url):
                        actual_type = MediaType.NETWORK
                    else:
                        actual_type = MediaType.FILE
                else:
                    actual_type = media_type

                self._media = self._create_media(url, actual_type)
                self._player.set_media(self._media)

                # 更新媒体信息
                self._update_media_info()

                self._emit("loaded", url)
                logger.info(f"媒体加载成功: {url}")
                return True

            except Exception as e:
                logger.error(f"媒体加载失败: {e}")
                self._state = PlaybackState.ERROR
                return False

    def play(self) -> bool:
        """开始/恢复播放"""
        with self._lock:
            if not self._player:
                return False

            try:
                # 如果没有加载媒体，先尝试从当前 URL 加载
                if self._state == PlaybackState.IDLE and self._current_url:
                    self.load(self._current_url)

                result = self._player.play()
                if result == 0:
                    self._state = PlaybackState.PLAYING
                    self._emit("play")
                    logger.debug("播放开始")
                    return True
                else:
                    logger.error(f"播放失败，返回码: {result}")
                    return False
            except Exception as e:
                logger.error(f"播放异常: {e}")
                return False

    def pause(self):
        """暂停播放"""
        with self._lock:
            if self._player and self._state == PlaybackState.PLAYING:
                self._player.pause()
                self._state = PlaybackState.PAUSED
                self._emit("pause")

    def stop(self):
        """停止播放"""
        with self._lock:
            if self._player:
                self._player.stop()
                self._state = PlaybackState.STOPPED
                self._emit("stop")

    def toggle_play_pause(self):
        """切换播放/暂停"""
        if self._state == PlaybackState.PLAYING:
            self.pause()
        elif self._state in (PlaybackState.PAUSED, PlaybackState.STOPPED, PlaybackState.ENDED):
            self.play()

    def seek(self, position: float) -> bool:
        """
        跳转到指定位置

        Args:
            position: 位置，0.0-1.0（百分比）或 秒（当 use_seconds=True）

        Returns:
            是否成功
        """
        with self._lock:
            if not self._player:
                return False

            try:
                if 0.0 <= position <= 1.0:
                    # 百分比位置
                    return self._player.set_position(position) == 0
                else:
                    # 秒数位置
                    duration = self._player.get_length() / 1000.0
                    if duration > 0:
                        pos = position / duration
                        return self._player.set_position(min(1.0, max(0.0, pos))) == 0
                    return False
            except Exception as e:
                logger.error(f"跳转失败: {e}")
                return False

    def seek_time(self, time_ms: int, relative: bool = False) -> bool:
        """
        跳转到指定时间

        Args:
            time_ms: 时间（毫秒）
            relative: 是否相对跳转

        Returns:
            是否成功
        """
        with self._lock:
            if not self._player:
                return False

            try:
                if relative:
                    current = self._player.get_time()
                    new_time = current + time_ms
                else:
                    new_time = time_ms

                return self._player.set_time(int(new_time)) == 0
            except Exception as e:
                logger.error(f"时间跳转失败: {e}")
                return False

    def set_volume(self, volume: int) -> bool:
        """
        设置音量

        Args:
            volume: 音量 0-100

        Returns:
            是否成功
        """
        with self._lock:
            if not self._player:
                return False

            volume = max(0, min(100, volume))
            self._config.volume = volume
            return self._player.audio_set_volume(volume) == 0

    def get_volume(self) -> int:
        """获取当前音量"""
        if self._player:
            return self._player.audio_get_volume()
        return self._config.volume

    def set_mute(self, mute: bool):
        """设置静音"""
        with self._lock:
            self._config.mute = mute
            if self._player:
                self._player.audio_set_mute(mute)

    def is_muted(self) -> bool:
        """是否静音"""
        if self._player:
            return self._player.audio_get_mute()
        return self._config.mute

    def toggle_mute(self):
        """切换静音状态"""
        current = self.is_muted()
        self.set_mute(not current)

    def set_fullscreen(self, fullscreen: bool):
        """设置全屏模式"""
        self._config.fullscreen = fullscreen
        if self._player:
            self._player.set_fullscreen(fullscreen)

    def is_fullscreen(self) -> bool:
        """是否全屏"""
        if self._player:
            return self._player.get_fullscreen()
        return self._config.fullscreen

    def toggle_fullscreen(self):
        """切换全屏模式"""
        current = self.is_fullscreen()
        self.set_fullscreen(not current)

    # 音轨和字幕

    def get_audio_tracks(self) -> List[Dict[str, Any]]:
        """获取可用音轨列表"""
        if not self._player:
            return []

        tracks = []
        try:
            audio_tracks = self._player.audio_get_track_description()
            current = self._player.audio_get_track()

            for track_id, name in audio_tracks:
                if track_id != -1:  # -1 通常是 "Disable"
                    tracks.append({
                        "id": track_id,
                        "name": name,
                        "active": track_id == current
                    })
        except Exception as e:
            logger.error(f"获取音轨失败: {e}")

        return tracks

    def set_audio_track(self, track_id: int) -> bool:
        """
        设置音轨

        Args:
            track_id: 音轨 ID，-1 表示禁用

        Returns:
            是否成功
        """
        if not self._player:
            return False

        try:
            result = self._player.audio_set_track(track_id)
            if result == 0:
                self._config.audio_track = track_id
                self._emit("audio_track_changed", track_id)
                return True
            return False
        except Exception as e:
            logger.error(f"设置音轨失败: {e}")
            return False

    def get_subtitle_tracks(self) -> List[Dict[str, Any]]:
        """获取可用字幕轨道列表"""
        if not self._player:
            return []

        tracks = []
        try:
            subtitle_tracks = self._player.video_get_spu_description()
            current = self._player.video_get_spu()

            for track_id, name in subtitle_tracks:
                if track_id != -1:
                    tracks.append({
                        "id": track_id,
                        "name": name,
                        "active": track_id == current
                    })
        except Exception as e:
            logger.error(f"获取字幕轨道失败: {e}")

        return tracks

    def set_subtitle_track(self, track_id: int) -> bool:
        """
        设置字幕轨道

        Args:
            track_id: 字幕轨道 ID，-1 表示禁用

        Returns:
            是否成功
        """
        if not self._player:
            return False

        try:
            result = self._player.video_set_spu(track_id)
            if result >= 0:
                self._config.subtitle_track = track_id
                self._emit("subtitle_track_changed", track_id)
                return True
            return False
        except Exception as e:
            logger.error(f"设置字幕轨道失败: {e}")
            return False

    def load_external_subtitle(self, path: str) -> bool:
        """
        加载外部字幕文件

        Args:
            path: 字幕文件路径 (SRT, SSA, SUB 等)

        Returns:
            是否成功
        """
        if not self._player or not os.path.exists(path):
            return False

        try:
            return self._player.add_slave(vlc.MediaSlaveType.subtitle, path, True) == 0
        except Exception as e:
            logger.error(f"加载字幕失败: {e}")
            return False

    def set_subtitle_delay(self, delay_ms: float):
        """设置字幕延迟（毫秒）"""
        self._config.subtitle_delay = delay_ms
        if self._player:
            self._player.video_set_spu_delay(int(delay_ms * 1000))

    # 播放信息

    def get_state(self) -> PlaybackState:
        """获取当前播放状态"""
        return self._state

    def is_playing(self) -> bool:
        """是否正在播放"""
        return self._state == PlaybackState.PLAYING

    def is_paused(self) -> bool:
        """是否暂停"""
        return self._state == PlaybackState.PAUSED

    def get_position(self) -> PlaybackPosition:
        """获取当前播放位置"""
        if not self._player:
            return PlaybackPosition()

        time_ms = self._player.get_time()
        duration = self._player.get_length() / 1000.0
        position = self._player.get_position()

        return PlaybackPosition(
            time=time_ms / 1000.0,
            position=position,
            duration=duration
        )

    def get_duration(self) -> float:
        """获取媒体时长（秒）"""
        if self._player:
            return self._player.get_length() / 1000.0
        return 0.0

    def get_current_url(self) -> str:
        """获取当前媒体 URL"""
        return self._current_url

    def get_media_info(self) -> MediaInfo:
        """获取媒体信息"""
        return self._media_info

    def _update_media_info(self):
        """更新媒体信息"""
        if not self._media:
            return

        try:
            # 解析媒体元数据
            meta = self._media.get_meta(vlc.Meta.Title)
            if meta:
                self._media_info.title = meta

            meta = self._media.get_meta(vlc.Meta.Artist)
            if meta:
                self._media_info.artist = meta

            meta = self._media.get_meta(vlc.Meta.Album)
            if meta:
                self._media_info.album = meta

            # 获取时长
            if self._media.get_duration() > 0:
                self._media_info.duration = self._media.get_duration() / 1000.0

            # 解析轨道信息
            if self._player:
                # 视频信息
                self._media_info.width = self._player.video_get_width()
                self._media_info.height = self._player.video_get_height()

                # FPS 和码率
                try:
                    tracks = self._media.tracks_get()
                    for track in tracks:
                        if track.type == vlc.TrackType.video:
                            self._media_info.fps = track.video.fps
                            self._media_info.bitrate = track.video.bitrate
                            codec = bytes(track.video.codec).decode('utf-8')
                            self._media_info.video_codec = codec
                        elif track.type == vlc.TrackType.audio:
                            codec = bytes(track.audio.codec).decode('utf-8')
                            self._media_info.audio_codec = codec
                            self._media_info.audio_channels = track.audio.channels
                            self._media_info.sample_rate = track.audio.sample_rate
                except Exception as e:
                    logger.debug(f"获取轨道信息失败: {e}")

        except Exception as e:
            logger.error(f"更新媒体信息失败: {e}")

    # 事件注册

    def on(self, event: str, callback: Callable):
        """
        注册事件回调

        Args:
            event: 事件名 (playing, paused, stopped, ended, error,
                    position_changed, time_changed, length_changed,
                    loaded, play, pause, stop, audio_track_changed,
                    subtitle_track_changed)
            callback: 回调函数
        """
        with self._lock:
            if event not in self._event_callbacks:
                self._event_callbacks[event] = []
            if callback not in self._event_callbacks[event]:
                self._event_callbacks[event].append(callback)

    def off(self, event: str, callback: Callable = None):
        """
        注销事件回调

        Args:
            event: 事件名
            callback: 回调函数，None 表示注销所有该事件的回调
        """
        with self._lock:
            if callback is None:
                self._event_callbacks[event] = []
            elif event in self._event_callbacks:
                if callback in self._event_callbacks[event]:
                    self._event_callbacks[event].remove(callback)

    # 窗口绑定

    def set_window(self, hwnd: int):
        """
        设置播放窗口句柄

        Args:
            hwnd: 窗口句柄（Windows 下为 HWND）
        """
        if self._player:
            self._player.set_hwnd(hwnd)

    def set_x_window(self, xid: int):
        """
        设置 X Window 句柄（Linux）

        Args:
            xid: X Window ID
        """
        if self._player:
            self._player.set_xwindow(xid)

    def set_nsobject(self, drawable: int):
        """
        设置 NSObject 句柄（macOS）

        Args:
            drawable: NSObject
        """
        if self._player:
            self._player.set_nsobject(drawable)

    # 截图

    def take_snapshot(self, path: str, width: int = 0, height: int = 0) -> bool:
        """
        截取当前画面

        Args:
            path: 保存路径（PNG 格式）
            width: 截图宽度，0 表示原始宽度
            height: 截图高度，0 表示原始高度

        Returns:
            是否成功
        """
        if not self._player:
            return False

        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(path), exist_ok=True)
            return self._player.video_take_snapshot(0, path, width, height) == 0
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return False

    # 播放列表支持

    def play_next(self) -> bool:
        """播放下一个（需要外部播放列表支持）"""
        self._emit("play_next")
        return True

    def play_previous(self) -> bool:
        """播放上一个（需要外部播放列表支持）"""
        self._emit("play_previous")
        return True

    # 配置

    def get_config(self) -> PlayerConfig:
        """获取播放器配置"""
        return self._config

    def update_config(self, **kwargs):
        """更新播放器配置"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

    def release(self):
        """释放播放器资源"""
        with self._lock:
            if self._player:
                self._player.stop()
                self._player.release()
                self._player = None

            if self._instance:
                self._instance.release()
                self._instance = None

            self._state = PlaybackState.IDLE
            self._event_callbacks.clear()
            logger.info("播放器资源已释放")


# 全局播放器实例管理

_global_player: Optional["VideoPlayer"] = None


def _create_global_player() -> VideoPlayer:
    """创建全局播放器实例"""
    global _global_player
    with _player_lock:
        if _global_player is None:
            _global_player = VideoPlayer()
        return _global_player
