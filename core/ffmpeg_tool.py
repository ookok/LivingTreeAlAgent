"""
FFmpeg 工具封装 - 音视频录制、转码、推流引擎

提供统一的 FFmpeg 命令执行接口，支持：
- 文件转码
- WebRTC 流录制
- RTMP 推流
- 屏幕录制
"""

import asyncio
import json
import subprocess
import shlex
import time
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
import queue


class CodecType(Enum):
    """编解码器类型"""
    H264 = "libx264"
    H264_NVENC = "h264_nvenc"
    H265 = "libx265"
    VP8 = "libvpx"
    VP9 = "libvpx-vp9"
    COPY = "copy"
    AAC = "aac"
    OPUS = "libopus"
    MP3 = "libmp3lame"


class ContainerFormat(Enum):
    """容器格式"""
    MP4 = "mp4"
    WEBM = "webm"
    MKV = "mkv"
    FLV = "flv"
    TS = "ts"
    MOV = "mov"


@dataclass
class FFmpegPreset:
    """FFmpeg 转码预设"""
    name: str
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    video_bitrate: str = "1500k"
    audio_bitrate: str = "128k"
    preset: str = "veryfast"
    crf: int = 23
    extra_args: List[str] = field(default_factory=list)


# 常用预设
PRESET_BALANCED = FFmpegPreset(
    name="balanced",
    video_bitrate="2000k",
    crf=23
)

PRESET_HIGH_QUALITY = FFmpegPreset(
    name="high_quality",
    video_bitrate="5000k",
    crf=18,
    preset="slow"
)

PRESET_LOW_LATENCY = FFmpegPreset(
    name="low_latency",
    video_bitrate="1000k",
    crf=26,
    preset="ultrafast",
    extra_args=["-tune", "zerolatency"]
)

PRESET_SCREEN_CAPTURE = FFmpegPreset(
    name="screen_capture",
    video_codec="libx264",
    preset="ultrafast",
    crf=18,
    extra_args=["-pix_fmt", "yuv420p"]
)


@dataclass
class StreamInfo:
    """流信息"""
    index: int
    codec_type: str  # video/audio/data
    codec_name: str
    bitrate: Optional[str] = None
    resolution: Optional[str] = None
    fps: Optional[str] = None
    sample_rate: Optional[str] = None
    duration: Optional[str] = None


class FFmpegTool:
    """
    FFmpeg 工具封装类

    提供同步/异步两种调用方式，自动检测 FFmpeg 路径，
    支持管道输入输出（用于直播流处理）
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, ffmpeg_path: str = None):
        if self._initialized:
            return

        self._initialized = True
        self._ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
        self._ffprobe_path = self._find_ffprobe()
        self._process_pool: Dict[str, subprocess.Popen] = {}
        self._probe_cache: Dict[str, List[StreamInfo]] = {}

    @staticmethod
    def _find_ffmpeg() -> str:
        """自动查找 FFmpeg 路径"""
        import shutil

        # 1. 先检查项目本地 bin 目录
        local_bin = Path(__file__).parent.parent / "bin" / "tools" / "ffmpeg"
        if os.name == 'nt':
            local_bin = local_bin.with_suffix('.exe')
        if local_bin.exists():
            return str(local_bin)

        # 2. 系统 PATH
        path = shutil.which("ffmpeg")
        if path:
            return path

        # 3. Windows 常见位置
        if os.name == 'nt':
            common_paths = [
                "C:/ffmpeg/bin/ffmpeg.exe",
                "C:/Program Files/ffmpeg/bin/ffmpeg.exe",
                "C:/Program Files (x86)/ffmpeg/bin/ffmpeg.exe",
            ]
            for p in common_paths:
                if Path(p).exists():
                    return p

        return "ffmpeg"  # 最后 fallback

    def _find_ffprobe(self) -> str:
        """自动查找 ffprobe 路径"""
        import shutil
from core.logger import get_logger
logger = get_logger('ffmpeg_tool')


        # 1. 项目本地 bin
        local_bin = Path(__file__).parent.parent / "bin" / "tools" / "ffprobe"
        if os.name == 'nt':
            local_bin = local_bin.with_suffix('.exe')
        if local_bin.exists():
            return str(local_bin)

        # 2. 系统 PATH
        path = shutil.which("ffprobe")
        if path:
            return path

        # 3. Windows 常见位置
        if os.name == 'nt':
            common_paths = [
                "C:/ffmpeg/bin/ffprobe.exe",
                "C:/Program Files/ffmpeg/bin/ffprobe.exe",
            ]
            for p in common_paths:
                if Path(p).exists():
                    return p

        return "ffprobe"

    @property
    def ffmpeg_path(self) -> str:
        return self._ffmpeg_path

    @property
    def available(self) -> bool:
        """FFmpeg 是否可用"""
        try:
            result = subprocess.run(
                [self._ffmpeg_path, "-version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def version_info(self) -> Dict[str, str]:
        """获取 FFmpeg 版本信息"""
        try:
            result = subprocess.run(
                [self._ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                first_line = result.stdout.split('\n')[0]
                return {"version": first_line, "path": self._ffmpeg_path}
        except Exception as e:
            return {"error": str(e)}
        return {"error": "FFmpeg not available"}

    def probe(self, input_path: str, use_cache: bool = True) -> List[StreamInfo]:
        """
        探测媒体文件信息

        Args:
            input_path: 输入文件路径
            use_cache: 是否使用缓存

        Returns:
            流信息列表
        """
        if use_cache and input_path in self._probe_cache:
            return self._probe_cache[input_path]

        try:
            cmd = [
                self._ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-show_format",
                input_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                return []

            data = json.loads(result.stdout)
            streams = []

            for idx, s in enumerate(data.get("streams", [])):
                stream = StreamInfo(
                    index=idx,
                    codec_type=s.get("codec_type", "unknown"),
                    codec_name=s.get("codec_name", "unknown"),
                    bitrate=s.get("bit_rate"),
                    resolution=s.get("width", 0) and f"{s.get('width', 0)}x{s.get('height', 0)}",
                    fps=s.get("r_frame_rate"),
                    sample_rate=s.get("sample_rate"),
                    duration=data.get("format", {}).get("duration")
                )
                streams.append(stream)

            if use_cache:
                self._probe_cache[input_path] = streams

            return streams

        except Exception as e:
            logger.info(f"Probe error: {e}")
            return []

    def exec_sync(
        self,
        args: List[str],
        timeout: int = 300,
        capture_output: bool = True
    ) -> Dict[str, Any]:
        """
        同步执行 FFmpeg 命令

        Args:
            args: FFmpeg 参数列表
            timeout: 超时秒数
            capture_output: 是否捕获输出

        Returns:
            {"returncode": int, "stdout": str, "stderr": str}
        """
        cmd = [self._ffmpeg_path] + args

        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                timeout=timeout
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout if capture_output else "",
                "stderr": result.stderr if capture_output else ""
            }
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "error": "timeout", "stdout": "", "stderr": ""}
        except Exception as e:
            return {"returncode": -1, "error": str(e), "stdout": "", "stderr": ""}

    async def exec_async(
        self,
        args: List[str],
        stdin_data: bytes = None,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        异步执行 FFmpeg 命令

        Args:
            args: FFmpeg 参数列表
            stdin_data: 标准输入数据（用于管道模式）
            timeout: 超时秒数

        Returns:
            {"returncode": int, "stderr": str}
        """
        cmd = [self._ffmpeg_path] + args

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=stdin_data),
                timeout=timeout
            )

            return {
                "returncode": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else ""
            }

        except asyncio.TimeoutExpired:
            process.kill()
            return {"returncode": -1, "error": "timeout", "stderr": ""}
        except Exception as e:
            return {"returncode": -1, "error": str(e), "stderr": ""}

    def convert(
        self,
        input_path: str,
        output_path: str,
        preset: FFmpegPreset = None,
        extra_args: List[str] = None,
        overwrite: bool = True
    ) -> Dict[str, Any]:
        """
        简单的文件转码

        Args:
            input_path: 输入文件
            output_path: 输出文件
            preset: 转码预设
            extra_args: 额外参数
            overwrite: 是否覆盖

        Returns:
            执行结果
        """
        preset = preset or PRESET_BALANCED

        args = ["-i", input_path]

        # 视频编码
        if preset.video_codec != "copy":
            args.extend(["-c:v", preset.video_codec])
            if preset.video_bitrate:
                args.extend(["-b:v", preset.video_bitrate])
            if preset.preset:
                args.extend(["-preset", preset.preset])
            if preset.crf:
                args.extend(["-crf", str(preset.crf)])
        else:
            args.extend(["-c:v", "copy"])

        # 音频编码
        if preset.audio_codec:
            args.extend(["-c:a", preset.audio_codec])
            if preset.audio_bitrate:
                args.extend(["-b:a", preset.audio_bitrate])

        # 额外参数
        if extra_args:
            args.extend(extra_args)

        # 覆盖
        if overwrite:
            args.append("-y")

        args.append(output_path)

        return self.exec_sync(args)

    def concat(
        self,
        input_files: List[str],
        output_path: str,
        format_type: str = "concat",
        copy_streams: bool = True
    ) -> Dict[str, Any]:
        """
        合并多个视频文件

        Args:
            input_files: 输入文件列表
            output_path: 输出文件
            format_type: concat 格式 ("concat" 或 "concat demuxer")
            copy_streams: 是否直接复制流（不重新编码）

        Returns:
            执行结果
        """
        if format_type == "concat":
            # 使用 concat 协议（文件需有相同的流）
            concat_str = "|".join(input_files)
            args = [
                "-i", f"concat:{concat_str}",
                "-c", "copy",
                "-y", output_path
            ]
        else:
            # 使用 concat demuxer（通用方式）
            concat_list = Path(output_path).parent / "concat_list.txt"
            with open(concat_list, "w", encoding="utf-8") as f:
                for fpath in input_files:
                    f.write(f"file '{fpath}'\n")

            args = [
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list)
            ]

            if copy_streams:
                args.extend(["-c", "copy"])
            else:
                args.extend(["-c:v", "libx264", "-c:a", "aac"])

            args.extend(["-y", output_path])

        result = self.exec_sync(args)

        # 清理临时文件
        if format_type != "concat":
            concat_list.unlink(missing_ok=True)

        return result

    def extract_audio(
        self,
        input_path: str,
        output_path: str = None,
        audio_codec: str = "libmp3lame",
        audio_bitrate: str = "192k",
        sample_rate: str = "44100"
    ) -> Dict[str, Any]:
        """
        提取音频轨道

        Args:
            input_path: 输入文件
            output_path: 输出文件（默认与输入同名但扩展名为 .mp3）
            audio_codec: 音频编码器
            audio_bitrate: 音频码率
            sample_rate: 采样率

        Returns:
            执行结果
        """
        if output_path is None:
            output_path = Path(input_path).with_suffix(".mp3").as_posix()

        args = [
            "-i", input_path,
            "-vn",  # 不要视频
            "-c:a", audio_codec,
            "-b:a", audio_bitrate,
            "-ar", sample_rate,
            "-y", output_path
        ]

        return self.exec_sync(args)

    def create_thumbnail(
        self,
        input_path: str,
        output_path: str = None,
        timestamp: str = "00:00:01",
        size: str = "320x240"
    ) -> Dict[str, Any]:
        """
        生成缩略图

        Args:
            input_path: 输入文件
            output_path: 输出文件
            timestamp: 截取时间点
            size: 输出尺寸

        Returns:
            执行结果
        """
        if output_path is None:
            output_path = str(Path(input_path).with_suffix(".jpg"))

        args = [
            "-ss", timestamp,
            "-i", input_path,
            "-vframes", "1",
            "-s", size,
            "-y", output_path
        ]

        return self.exec_sync(args)

    def get_duration(self, input_path: str) -> float:
        """获取视频时长（秒）"""
        streams = self.probe(input_path)
        for s in streams:
            if s.duration:
                try:
                    return float(s.duration)
                except ValueError:
                    pass
        return 0.0

    def get_resolution(self, input_path: str) -> tuple:
        """获取视频分辨率 (width, height)"""
        streams = self.probe(input_path)
        for s in streams:
            if s.codec_type == "video" and s.resolution:
                try:
                    w, h = s.resolution.split("x")
                    return int(w), int(h)
                except ValueError:
                    pass
        return 0, 0


class FFmpegRecorder:
    """
    FFmpeg 录制管理器

    管理 WebRTC 流的录制，支持：
    - 实时写入 chunk
    - 自动合并
    - 转码
    """

    def __init__(self, session_id: str, output_dir: str = None):
        self.session_id = session_id
        self.output_dir = Path(output_dir or "./recordings")
        self.chunk_dir = self.output_dir / session_id
        self.chunk_dir.mkdir(parents=True, exist_ok=True)

        self.chunks: List[Path] = []
        self.concat_list_path = self.chunk_dir / "concat_list.txt"
        self.final_path = self.output_dir / f"{session_id}_final.mp4"

        self._ffmpeg = FFmpegTool()
        self._is_recording = False
        self._merge_task = None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start(self):
        """开始录制"""
        self._is_recording = True
        # 清空之前的 concat list
        if self.concat_list_path.exists():
            self.concat_list_path.unlink()

    def write_chunk(self, data: bytes) -> Path:
        """
        写入一个 WebM chunk

        Args:
            data: chunk 数据

        Returns:
            写入的 chunk 文件路径
        """
        if not self._is_recording:
            self.start()

        ts = int(time.time() * 1000)
        chunk_path = self.chunk_dir / f"chunk_{ts}.webm"
        chunk_path.write_bytes(data)
        self.chunks.append(chunk_path)

        # 更新 concat list
        with open(self.concat_list_path, "a", encoding="utf-8") as f:
            f.write(f"file '{chunk_path.name}'\n")

        return chunk_path

    async def merge_chunks(self, delete_chunks: bool = True) -> Dict[str, Any]:
        """
        合并所有 chunks 为最终 MP4

        Args:
            delete_chunks: 合并后删除 chunk 文件

        Returns:
            执行结果
        """
        if not self.chunks:
            return {"returncode": -1, "error": "No chunks to merge"}

        # 使用 concat demuxer
        args = [
            "-f", "concat",
            "-safe", "0",
            "-i", str(self.concat_list_path),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-y",
            str(self.final_path)
        ]

        result = self._ffmpeg.exec_sync(args)

        if result["returncode"] == 0 and delete_chunks:
            # 删除 chunk 文件
            for chunk in self.chunks:
                chunk.unlink(missing_ok=True)
            self.concat_list_path.unlink(missing_ok=True)

        return result

    def stop(self) -> str:
        """
        停止录制

        Returns:
            最终文件路径（尚未合并）
        """
        self._is_recording = False
        return str(self.final_path)

    async def finalize(self) -> str:
        """
        完成录制并合并

        Returns:
            最终 MP4 文件路径
        """
        self.stop()
        result = await self.merge_chunks()
        if result["returncode"] == 0:
            return str(self.final_path)
        return ""


class FFmpegPipeline:
    """
    FFmpeg 管道处理器

    用于处理直播流，支持：
    - stdin 管道输入
    - RTMP 推流
    - 实时转码
    """

    def __init__(self):
        self._ffmpeg = FFmpegTool()
        self._process: Optional[asyncio.subprocess.Popen] = None
        self._input_queue: queue.Queue = queue.Queue(maxsize=100)
        self._writer_task: Optional[asyncio.Task] = None

    async def start_push(
        self,
        rtmp_url: str,
        width: int = 1280,
        height: int = 720,
        video_bitrate: str = "1500k",
        audio_bitrate: str = "128k",
        input_format: str = "webm"
    ) -> Dict[str, Any]:
        """
        启动 RTMP 推流

        Args:
            rtmp_url: RTMP 服务器地址
            width: 视频宽度
            height: 视频高度
            video_bitrate: 视频码率
            audio_bitrate: 音频码率
            input_format: 输入格式 (webm/h264/rawvideo)

        Returns:
            启动结果
        """
        # 构建 FFmpeg 命令
        if input_format == "h264":
            # 输入已经是 H264 流
            args = [
                "-hwaccel", "cuda",  # 如果支持硬解码
                "-f", "h264",
                "-i", "-",  # stdin
                "-c:v", "copy",
                "-f", "flv",
                rtmp_url
            ]
        elif input_format == "webm":
            # 输入是 WebM (VP8/VP9)
            args = [
                "-f", "webm",
                "-i", "-",  # stdin
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-b:v", video_bitrate,
                "-vf", f"scale={width}:{height}",
                "-c:a", "aac",
                "-b:a", audio_bitrate,
                "-f", "flv",
                rtmp_url
            ]
        else:
            return {"returncode": -1, "error": f"Unknown input format: {input_format}"}

        try:
            self._process = await asyncio.create_subprocess_exec(
                self._ffmpeg.ffmpeg_path,
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )

            return {
                "returncode": 0,
                "pid": self._process.pid,
                "status": "ready"
            }

        except Exception as e:
            return {"returncode": -1, "error": str(e)}

    async def write_input(self, data: bytes):
        """
        写入输入数据

        Args:
            data: 输入数据
        """
        if self._process and self._process.stdin:
            self._process.stdin.write(data)
            await self._process.stdin.drain()

    async def stop(self):
        """停止推流"""
        if self._process:
            if self._process.stdin:
                self._process.stdin.close()
            self._process.terminate()
            await self._process.wait()
            self._process = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None


# 全局单例
_ffmpeg_tool: Optional[FFmpegTool] = None


def get_ffmpeg() -> FFmpegTool:
    """获取 FFmpeg 工具单例"""
    global _ffmpeg_tool
    if _ffmpeg_tool is None:
        _ffmpeg_tool = FFmpegTool()
    return _ffmpeg_tool


async def ffmpeg_exec(args_str: str) -> Dict[str, Any]:
    """
    执行 FFmpeg 命令的便捷函数

    Args:
        args_str: FFmpeg 参数字符串，如 "-i input.mp4 -c copy output.mp4"

    Returns:
        执行结果
    """
    ffmpeg = get_ffmpeg()
    args = shlex.split(args_str) if isinstance(args_str, str) else args_str
    return await ffmpeg.exec_async(args)


# 便捷命令函数
def convert_file(input_path: str, output_path: str, quality: str = "balanced") -> Dict[str, Any]:
    """转换文件格式"""
    ffmpeg = get_ffmpeg()

    preset_map = {
        "low": FFmpegPreset("low", video_bitrate="500k", crf=28),
        "balanced": PRESET_BALANCED,
        "high": PRESET_HIGH_QUALITY,
    }

    preset = preset_map.get(quality, PRESET_BALANCED)
    return ffmpeg.convert(input_path, output_path, preset)


def merge_files(input_files: List[str], output_path: str) -> Dict[str, Any]:
    """合并视频文件"""
    ffmpeg = get_ffmpeg()
    return ffmpeg.concat(input_files, output_path)


def extract_audio_track(input_path: str, output_path: str = None) -> Dict[str, Any]:
    """提取音频"""
    ffmpeg = get_ffmpeg()
    return ffmpeg.extract_audio(input_path, output_path)


def generate_thumbnail(input_path: str, output_path: str = None, timestamp: str = "00:00:01") -> Dict[str, Any]:
    """生成缩略图"""
    ffmpeg = get_ffmpeg()
    return ffmpeg.create_thumbnail(input_path, output_path, timestamp)
