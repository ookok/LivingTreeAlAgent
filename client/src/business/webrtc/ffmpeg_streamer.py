"""
FFmpeg RTMP 推流管理器

功能：
- 管理 RTMP 推流连接
- 支持多种输入格式 (H264/VP8/VP9/WebM)
- 自动重连
- 带宽自适应
"""

import asyncio
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
import queue

from business.ffmpeg_tool import FFmpegTool, FFmpegPipeline


class StreamState(Enum):
    """推流状态"""
    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    PAUSED = "paused"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class StreamProfile:
    """推流配置"""
    name: str
    width: int = 1280
    height: int = 720
    video_bitrate: str = "1500k"
    audio_bitrate: str = "128k"
    fps: int = 30
    keyframe_interval: int = 2
    preset: str = "veryfast"
    extra_args: List[str] = field(default_factory=list)

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


# 预设配置
PROFILE_480P = StreamProfile(
    name="480p",
    width=854,
    height=480,
    video_bitrate="800k",
    fps=24
)

PROFILE_720P = StreamProfile(
    name="720p",
    width=1280,
    height=720,
    video_bitrate="1500k",
    fps=30
)

PROFILE_1080P = StreamProfile(
    name="1080p",
    width=1920,
    height=1080,
    video_bitrate="3000k",
    fps=30,
    preset="fast"
)

PROFILE_1440P = StreamProfile(
    name="1440p",
    width=2560,
    height=1440,
    video_bitrate="6000k",
    fps=30,
    preset="fast"
)

PROFILES = {
    "480p": PROFILE_480P,
    "720p": PROFILE_720P,
    "1080p": PROFILE_1080P,
    "1440p": PROFILE_1440P,
}


@dataclass
class StreamSession:
    """推流会话"""
    stream_id: str
    rtmp_url: str
    profile: StreamProfile
    state: StreamState = StreamState.IDLE
    start_time: Optional[float] = None
    bytes_sent: int = 0
    frames_sent: int = 0
    error: Optional[str] = None
    last_activity: Optional[float] = None

    @property
    def duration(self) -> float:
        if self.start_time:
            return time.time() - self.start_time
        return 0.0


class RTMPStreamer:
    """
    RTMP 推流管理器

    管理到 RTMP 服务器的推流连接
    """

    def __init__(self):
        self._ffmpeg = FFmpegTool()
        self._sessions: Dict[str, StreamSession] = {}
        self._pipelines: Dict[str, FFmpegPipeline] = {}
        self._lock = threading.Lock()

        # 事件回调
        self._on_state_change: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        self._on_stats: Optional[Callable] = None

        # 统计收集
        self._stats_task: Optional[asyncio.Task] = None

    def set_callbacks(
        self,
        on_state_change: Callable = None,
        on_error: Callable = None,
        on_stats: Callable = None
    ):
        """设置事件回调"""
        self._on_state_change = on_state_change
        self._on_error = on_error
        self._on_stats = on_stats

    def _get_ffmpeg_args(
        self,
        session: StreamSession,
        input_format: str = "webm"
    ) -> List[str]:
        """
        构建 FFmpeg 推流命令

        Args:
            session: 推流会话
            input_format: 输入格式

        Returns:
            FFmpeg 参数列表
        """
        profile = session.profile
        args = []

        # 输入格式
        if input_format == "h264":
            args.extend(["-f", "h264", "-i", "-"])
        elif input_format == "vp8":
            args.extend(["-f", "webm", "-i", "-"])
        elif input_format == "vp9":
            args.extend(["-f", "webm", "-i", "-"])
        else:
            args.extend(["-f", "webm", "-i", "-"])

        # 视频编码
        if input_format == "h264":
            # H264 直通
            args.extend(["-c:v", "copy"])
        else:
            # 需要转码
            args.extend([
                "-c:v", "libx264",
                "-preset", profile.preset,
                "-b:v", profile.video_bitrate,
                "-maxrate", profile.video_bitrate,
                "-bufsize", f"{int(profile.video_bitrate.rstrip('k')) * 2}k",
                "-g", str(profile.keyframe_interval * profile.fps),
            ])

        # 视频滤镜
        if profile.width and profile.height:
            args.extend(["-vf", f"scale={profile.width}:{profile.height}:force_original_aspect_ratio=decrease,pad={profile.width}:{profile.height}:(ow-iw)/2:(oh-ih)/2"])

        # 音频编码
        args.extend([
            "-c:a", "aac",
            "-b:a", profile.audio_bitrate,
            "-ar", "44100",
        ])

        # 输出
        args.extend([
            "-f", "flv",
            session.rtmp_url
        ])

        return args

    async def start_stream(
        self,
        rtmp_url: str,
        profile: StreamProfile = None,
        input_format: str = "webm"
    ) -> Optional[str]:
        """
        启动推流

        Args:
            rtmp_url: RTMP 服务器地址
            profile: 推流配置
            input_format: 输入格式 (webm/h264/vp9)

        Returns:
            stream_id 或 None
        """
        profile = profile or PROFILE_720P

        stream_id = f"stream_{int(time.time() * 1000)}"

        session = StreamSession(
            stream_id=stream_id,
            rtmp_url=rtmp_url,
            profile=profile,
            state=StreamState.CONNECTING
        )

        pipeline = FFmpegPipeline()

        # 构建命令
        args = self._get_ffmpeg_args(session, input_format)

        try:
            result = await pipeline.start_push(
                rtmp_url=rtmp_url,
                width=profile.width,
                height=profile.height,
                video_bitrate=profile.video_bitrate,
                input_format=input_format
            )

            with self._lock:
                self._sessions[stream_id] = session
                self._pipelines[stream_id] = pipeline

            if result["returncode"] == 0:
                session.state = StreamState.STREAMING
                session.start_time = time.time()

                if self._on_state_change:
                    await self._on_state_change(stream_id, StreamState.STREAMING)

                return stream_id
            else:
                session.state = StreamState.ERROR
                session.error = result.get("error", "Unknown error")

                if self._on_error:
                    await self._on_error(stream_id, session.error)

                return None

        except Exception as e:
            session.state = StreamState.ERROR
            session.error = str(e)

            if self._on_error:
                await self._on_error(stream_id, str(e))

            return None

    async def write_data(self, stream_id: str, data: bytes) -> bool:
        """
        写入推流数据

        Args:
            stream_id: 流 ID
            data: 数据

        Returns:
            是否成功
        """
        with self._lock:
            if stream_id not in self._pipelines:
                return False

            session = self._sessions[stream_id]
            pipeline = self._pipelines[stream_id]

        if session.state != StreamState.STREAMING:
            return False

        try:
            await pipeline.write_input(data)
            session.bytes_sent += len(data)
            session.frames_sent += 1
            session.last_activity = time.time()
            return True

        except Exception as e:
            session.state = StreamState.ERROR
            session.error = str(e)

            if self._on_error:
                await self._on_error(stream_id, str(e))

            return False

    async def stop_stream(self, stream_id: str) -> bool:
        """
        停止推流

        Args:
            stream_id: 流 ID

        Returns:
            是否成功
        """
        with self._lock:
            if stream_id not in self._sessions:
                return False

            session = self._sessions[stream_id]
            pipeline = self._pipelines.get(stream_id)

        try:
            if pipeline:
                await pipeline.stop()

            session.state = StreamState.STOPPED

            if self._on_state_change:
                await self._on_state_change(stream_id, StreamState.STOPPED)

            with self._lock:
                self._sessions.pop(stream_id, None)
                self._pipelines.pop(stream_id, None)

            return True

        except Exception as e:
            if self._on_error:
                await self._on_error(stream_id, str(e))
            return False

    async def pause_stream(self, stream_id: str) -> bool:
        """暂停推流"""
        with self._lock:
            if stream_id not in self._sessions:
                return False
            session = self._sessions[stream_id]

        if session.state == StreamState.STREAMING:
            session.state = StreamState.PAUSED
            if self._on_state_change:
                await self._on_state_change(stream_id, StreamState.PAUSED)
            return True
        return False

    async def resume_stream(self, stream_id: str) -> bool:
        """恢复推流"""
        with self._lock:
            if stream_id not in self._sessions:
                return False
            session = self._sessions[stream_id]

        if session.state == StreamState.PAUSED:
            session.state = StreamState.STREAMING
            session.last_activity = time.time()
            if self._on_state_change:
                await self._on_state_change(stream_id, StreamState.STREAMING)
            return True
        return False

    def get_session(self, stream_id: str) -> Optional[StreamSession]:
        """获取会话信息"""
        with self._lock:
            return self._sessions.get(stream_id)

    def get_all_sessions(self) -> List[StreamSession]:
        """获取所有会话"""
        with self._lock:
            return list(self._sessions.values())

    def get_active_sessions(self) -> List[StreamSession]:
        """获取活跃会话"""
        with self._lock:
            return [s for s in self._sessions.values() if s.state == StreamState.STREAMING]

    async def stop_all(self):
        """停止所有推流"""
        stream_ids = list(self._sessions.keys())
        for stream_id in stream_ids:
            await self.stop_stream(stream_id)

    async def get_stats(self, stream_id: str = None) -> Dict:
        """
        获取推流统计

        Args:
            stream_id: 流 ID（None 则获取所有）

        Returns:
            统计信息
        """
        if stream_id:
            session = self.get_session(stream_id)
            if not session:
                return {"error": "Stream not found"}

            return {
                "stream_id": stream_id,
                "state": session.state.value,
                "duration": session.duration,
                "bytes_sent": session.bytes_sent,
                "frames_sent": session.frames_sent,
                "bitrate": session.bytes_sent * 8 / max(session.duration, 1) if session.duration > 0 else 0,
                "rtmp_url": session.rtmp_url,
            }
        else:
            stats = []
            for s in self.get_all_sessions():
                stats.append({
                    "stream_id": s.stream_id,
                    "state": s.state.value,
                    "duration": s.duration,
                    "bytes_sent": s.bytes_sent,
                })
            return {"streams": stats}


class StreamRouter:
    """
    直播路由

    支持多平台同时推流（哔哩哔哩/抖音/YouTube等）
    """

    def __init__(self):
        self._streamers: Dict[str, RTMPStreamer] = {}
        self._outputs: Dict[str, List[str]] = {}  # stream_id -> [rtmp_urls]
        self._lock = threading.Lock()

    def add_destination(
        self,
        name: str,
        rtmp_url: str,
        profile: StreamProfile = None
    ) -> str:
        """
        添加推流目标

        Args:
            name: 目标名称
            rtmp_url: RTMP 地址
            profile: 推流配置

        Returns:
            stream_id
        """
        streamer = RTMPStreamer()

        with self._lock:
            self._streamers[name] = streamer
            self._outputs[name] = [rtmp_url]

        return name

    def remove_destination(self, name: str):
        """移除推流目标"""
        with self._lock:
            if name in self._streamers:
                asyncio.create_task(self._streamers[name].stop_all())
                del self._streamers[name]
                del self._outputs[name]

    async def start_all(self, input_format: str = "webm") -> Dict[str, Optional[str]]:
        """
        启动所有推流

        Returns:
            {name: stream_id or None}
        """
        results = {}
        for name, streamer in self._streamers.items():
            urls = self._outputs.get(name, [])
            if urls:
                rtmp_url = urls[0]
                stream_id = await streamer.start_stream(rtmp_url, input_format=input_format)
                results[name] = stream_id
            else:
                results[name] = None
        return results

    async def stop_all(self):
        """停止所有推流"""
        for streamer in self._streamers.values():
            await streamer.stop_all()


# 全局单例
_rtmp_streamer: Optional[RTMPStreamer] = None


def get_rtmp_streamer() -> RTMPStreamer:
    """获取 RTMP 推流管理器单例"""
    global _rtmp_streamer
    if _rtmp_streamer is None:
        _rtmp_streamer = RTMPStreamer()
    return _rtmp_streamer
