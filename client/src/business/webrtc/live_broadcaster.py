"""
直播推流模块

支持两种模式:
1. 录制模式: 将 WebSocket 收到的视频数据写入本地文件 (使用 FFmpeg 转码)
2. 推流模式: 通过 FFmpeg 推送到 RTMP 服务器

集成了:
- ffmpeg_tool.py: FFmpeg 核心工具
- ffmpeg_recorder.py: 录制管理
- ffmpeg_streamer.py: RTMP 推流
"""

import asyncio
import logging
import struct
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable, BinaryIO, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)

# 导入 FFmpeg 模块
try:
    from client.src.business.ffmpeg_tool import (
        FFmpegTool, FFmpegRecorder, FFmpegPipeline,
        get_ffmpeg, PRESET_BALANCED
    )
    from core.webrtc.ffmpeg_recorder import (
        RecordingManager, RecordingSession, RecordingState,
        get_recording_manager
    )
    from core.webrtc.ffmpeg_streamer import (
        RTMPStreamer, StreamSession, StreamState,
        PROFILES, get_rtmp_streamer
    )
    FFMPEG_AVAILABLE = True
except ImportError as e:
    logger.warning(f"FFmpeg 模块导入失败: {e}")
    FFMPEG_AVAILABLE = False


class StreamMode(Enum):
    RECORD = "record"  # 录制到本地
    PUSH = "push"  # 推流到 RTMP


@dataclass
class StreamConfig:
    """流配置"""
    mode: StreamMode = StreamMode.RECORD
    output_path: str = ""  # 录制输出路径或 RTMP URL
    chunk_duration_ms: int = 1000  # 每段录制时长
    max_file_size_mb: int = 100  # 单文件最大大小


class LiveBroadcaster:
    """
    直播推流处理器

    接收 WebSocket 二进制数据（MediaRecorder 切片）
    支持本地录制和 RTMP 推流

    增强版: 集成 FFmpeg 模块，支持高质量转码和 RTMP 推流
    """

    def __init__(self, config: Optional[StreamConfig] = None):
        self.config = config or StreamConfig()
        self._is_streaming = False
        self._writer: Optional[asyncio.StreamWriter] = None
        self._current_file: Optional[BinaryIO] = None
        self._chunk_count = 0
        self._bytes_written = 0
        self._start_time = 0
        self._ffmpeg_process: Optional[asyncio.subprocess.Process] = None

        # FFmpeg 集成
        self._ffmpeg_recorder: Optional[FFmpegRecorder] = None
        self._ffmpeg_pipeline: Optional[FFmpegPipeline] = None
        self._ffmpeg_tool: Optional[FFmpegTool] = None
        self._session_id: Optional[str] = None

        # 回调钩子
        self.on_chunk_received: Optional[Callable[[bytes, float], None]] = None
        self.on_stream_started: Optional[Callable[[], None]] = None
        self.on_stream_stopped: Optional[Callable[[dict], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None

        # 初始化 FFmpeg
        if FFMPEG_AVAILABLE:
            try:
                self._ffmpeg_tool = get_ffmpeg()
            except Exception as e:
                logger.warning(f"FFmpeg 初始化失败: {e}")

    @property
    def is_streaming(self) -> bool:
        return self._is_streaming

    async def start_stream(self, output_path: str = ""):
        """开始推流/录制"""
        if self._is_streaming:
            logger.warning("流已经在运行中")
            return

        output = output_path or self.config.output_path
        if not output:
            # 默认路径
            output = str(Path.home() / "Videos" / f"hermes_live_{int(time.time())}.webm")

        self.config.output_path = output
        self._is_streaming = True
        self._chunk_count = 0
        self._bytes_written = 0
        self._start_time = time.time()

        if self.config.mode == StreamMode.PUSH:
            await self._start_ffmpeg_push(output)
        else:
            self._current_file = open(output, 'wb')

        logger.info(f"开始{self.config.mode.value}: {output}")

        if self.on_stream_started:
            self.on_stream_started()

    async def stop_stream(self):
        """停止推流/录制"""
        if not self._is_streaming:
            return

        self._is_streaming = False

        if self.config.mode == StreamMode.PUSH:
            await self._stop_ffmpeg_push()
        else:
            self._close_current_file()

        stats = {
            "duration_sec": time.time() - self._start_time,
            "chunks": self._chunk_count,
            "bytes": self._bytes_written,
            "output": self.config.output_path
        }

        logger.info(f"流结束: {stats}")

        if self.on_stream_stopped:
            self.on_stream_stopped(stats)

    async def feed_data(self, data: bytes, timestamp: float = 0):
        """
        接收 MediaRecorder 切片数据

        Args:
            data: WebM/Opus 格式的二进制数据
            timestamp: 时间戳（毫秒）
        """
        if not self._is_streaming:
            return

        try:
            if self.config.mode == StreamMode.PUSH:
                await self._feed_ffmpeg(data)
            else:
                self._write_to_file(data)

            self._chunk_count += 1

            if self.on_chunk_received:
                self.on_chunk_received(data, timestamp)

        except Exception as e:
            logger.error(f"处理数据失败: {e}")
            if self.on_error:
                self.on_error(e)

    def _write_to_file(self, data: bytes):
        """写入本地文件"""
        if self._current_file is None:
            return

        # WebM 容器处理: 添加 EBML 头部或直接写入
        self._current_file.write(data)
        self._bytes_written += len(data)

        # 检查文件大小
        file_size_mb = self._bytes_written / (1024 * 1024)
        if file_size_mb >= self.config.max_file_size_mb:
            self._rotate_file()

    def _rotate_file(self):
        """轮转文件"""
        self._close_current_file()
        self._chunk_count = 0
        self._bytes_written = 0

        # 生成新文件名
        base, ext = self.config.output_path.rsplit('.', 1)
        self.config.output_path = f"{base}_{int(time.time())}.{ext}"
        self._current_file = open(self.config.output_path, 'wb')
        logger.info(f"文件轮转: {self.config.output_path}")

    def _close_current_file(self):
        """关闭当前文件"""
        if self._current_file:
            try:
                self._current_file.close()
            except Exception:
                pass
            self._current_file = None

    async def _start_ffmpeg_push(self, rtmp_url: str):
        """启动 ffmpeg 推流"""
        try:
            # ffmpeg 命令: 接收 WebM 流，推送到 RTMP
            cmd = [
                "ffmpeg",
                "-i", "pipe:0",  # 从 stdin 读取
                "-c:v", "copy",  # 复制视频流（不转码）
                "-c:a", "aac",   # 转码音频为 AAC（RTMP 常用）
                "-f", "flv",     # FLV 容器（RTMP 必需）
                "-flvflags", "no_duration_filesize",
                rtmp_url
            ]

            self._ffmpeg_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )

            logger.info(f"FFmpeg 推流进程启动 (PID: {self._ffmpeg_process.pid})")

        except FileNotFoundError:
            logger.error("ffmpeg 未找到，无法推流")
            # 回退到录制模式
            self.config.mode = StreamMode.RECORD
            self._current_file = open(self.config.output_path.replace('.webm', '_nofmpeg.webm'), 'wb')

    async def _feed_ffmpeg(self, data: bytes):
        """发送数据给 ffmpeg"""
        if self._ffmpeg_process and self._ffmpeg_process.stdin:
            try:
                self._ffmpeg_process.stdin.write(data)
                await self._ffmpeg_process.stdin.drain()
                self._bytes_written += len(data)
            except Exception as e:
                logger.error(f"FFmpeg 写入失败: {e}")
                if self._ffmpeg_process.stdin:
                    await self._ffmpeg_process.stdin.close()
                self._ffmpeg_process.terminate()

    async def _stop_ffmpeg_push(self):
        """停止 ffmpeg 推流"""
        if self._ffmpeg_process:
            try:
                if self._ffmpeg_process.stdin:
                    self._ffmpeg_process.stdin.close()
                await asyncio.wait_for(self._ffmpeg_process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._ffmpeg_process.terminate()
            except Exception as e:
                logger.error(f"停止 FFmpeg 失败: {e}")
            self._ffmpeg_process = None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "is_streaming": self._is_streaming,
            "mode": self.config.mode.value,
            "output": self.config.output_path,
            "duration_sec": time.time() - self._start_time if self._is_streaming else 0,
            "chunks": self._chunk_count,
            "bytes": self._bytes_written,
            "file_size_mb": self._bytes_written / (1024 * 1024) if self._bytes_written > 0 else 0
        }

        # FFmpeg 统计
        if FFMPEG_AVAILABLE and self._ffmpeg_tool:
            stats["ffmpeg"] = {
                "available": self._ffmpeg_tool.available,
                "version": self._ffmpeg_tool.version_info().get("version", "unknown")
            }

        return stats

    def get_ffmpeg_info(self) -> Dict[str, Any]:
        """获取 FFmpeg 详细信息"""
        if not FFMPEG_AVAILABLE or not self._ffmpeg_tool:
            return {"available": False, "error": "FFmpeg not available"}

        return {
            "available": self._ffmpeg_tool.available,
            "path": self._ffmpeg_tool.ffmpeg_path,
            "version": self._ffmpeg_tool.version_info().get("version", "unknown"),
            "probe_cache_size": len(self._ffmpeg_tool._probe_cache)
        }


class StreamRouter:
    """
    直播路由 - 处理多房间直播分发

    支持:
    - 单人直播给多人
    - 多人连麦直播

    增强版: 集成 FFmpeg 录制和 RTMP 推流
    """

    def __init__(self):
        self._broadcasters: Dict[str, LiveBroadcaster] = {}
        self._subscribers: Dict[str, set] = {}
        self._recording_manager: Optional[RecordingManager] = None
        self._rtmp_streamer: Optional[RTMPStreamer] = None

        # 初始化 FFmpeg 组件
        if FFMPEG_AVAILABLE:
            try:
                self._recording_manager = get_recording_manager()
                self._rtmp_streamer = get_rtmp_streamer()
            except Exception as e:
                logger.warning(f"FFmpeg StreamRouter 初始化失败: {e}")  # room_id -> set of ws_ids

    def start_broadcast(self, room_id: str, config: StreamConfig) -> LiveBroadcaster:
        """为房间启动直播"""
        broadcaster = LiveBroadcaster(config)
        self._broadcasters[room_id] = broadcaster
        self._subscribers[room_id] = set()
        return broadcaster

    def stop_broadcast(self, room_id: str):
        """停止房间直播"""
        if room_id in self._broadcasters:
            asyncio.create_task(self._broadcasters[room_id].stop_stream())
            del self._broadcasters[room_id]
            del self._subscribers[room_id]

    def subscribe(self, room_id: str, ws_id: str):
        """订阅房间直播"""
        if room_id in self._subscribers:
            self._subscribers[room_id].add(ws_id)

    def unsubscribe(self, room_id: str, ws_id: str):
        """取消订阅"""
        if room_id in self._subscribers:
            self._subscribers[room_id].discard(ws_id)

    def get_broadcaster(self, room_id: str) -> Optional[LiveBroadcaster]:
        return self._broadcasters.get(room_id)

    def is_live(self, room_id: str) -> bool:
        return room_id in self._broadcasters and self._broadcasters[room_id].is_streaming


# 单例
_broadcaster_instance: Optional[StreamRouter] = None


def get_stream_router() -> StreamRouter:
    global _broadcaster_instance
    if _broadcaster_instance is None:
        _broadcaster_instance = StreamRouter()
    return _broadcaster_instance
