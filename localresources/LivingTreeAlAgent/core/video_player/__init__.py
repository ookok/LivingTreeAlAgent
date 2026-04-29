# -*- coding: utf-8 -*-
"""
视频播放器核心模块
基于 LibVLC (python-vlc) 实现，支持本地和网络视频播放

Screenbox 集成说明:
- Screenbox 本身是 UWP 应用，不提供 API/SDK
- 本模块使用与 Screenbox 相同的底层引擎 (LibVLC)
- 提供等同的播放能力：本地视频、网络流、字幕等
"""

from .player import VideoPlayer, PlaybackState, MediaType
from .playlist import Playlist, PlaylistItem
from .subtitles import SubtitleManager, SubtitleTrack

__all__ = [
    "VideoPlayer",
    "PlaybackState",
    "MediaType",
    "Playlist",
    "PlaylistItem",
    "SubtitleManager",
    "SubtitleTrack",
]


def get_video_player() -> VideoPlayer:
    """获取全局视频播放器实例（单例模式）"""
    from .player import _global_player
    return _global_player


def release_video_player():
    """释放全局视频播放器实例"""
    from .player import _global_player
    if _global_player:
        _global_player.release()
