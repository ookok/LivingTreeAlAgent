"""
Transcription Engine - 语音转录引擎

支持多种本地转录方案：
1. Whisper (OpenAI) - 通用型
2. Parakeet (NVIDIA) - 高精度
3. Faster Whisper - 优化性能版

特性：
- 实时流式转录
- 多语言支持
- 说话人识别（需配合 diarization 模块）
- GPU 加速
"""

import os
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any
from datetime import datetime
from enum import Enum
import json
import tempfile


class TranscriptionModel(Enum):
    """转录模型"""
    WHISPER_BASE = "base"
    WHISPER_SMALL = "small"
    WHISPER_MEDIUM = "medium"
    WHISPER_LARGE = "large"
    PARAKEET_NEMO = "parakeet-nemo"  # NVIDIA NeMo
    FASTER_WHISPER = "faster-whisper"


class TranscriptionEngine(Enum):
    """转录引擎"""
    WHISPER_CPP = "whisper.cpp"
    WHISPER_PYTHON = "whisper-python"
    FASTER_WHISPER = "faster-whisper"
    PARAKEET = "parakeet"


@dataclass
class TranscriptionSegment:
    """转录片段"""
    start_time: float           # 开始时间（秒）
    end_time: float             # 结束时间（秒）
    text: str                   # 转录文本
    speaker: Optional[str] = None  # 说话人（如果有）
    confidence: float = 0.0     # 置信度


@dataclass
class TranscriptionResult:
    """转录结果"""
    meeting_id: str
    full_text: str              # 完整转录文本
    segments: List[TranscriptionSegment]  # 分段
    language: str = "zh"        # 检测到的语言
    duration: float = 0.0        # 总时长
    model_used: str = ""        # 使用的模型
    engine: str = ""            # 使用的引擎
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_srt(self) -> str:
        """导出为 SRT 格式"""
        lines = []
        for i, seg in enumerate(self.segments, 1):
            start = self._format_timestamp(seg.start_time)
            end = self._format_timestamp(seg.end_time)
            speaker = f"[{seg.speaker}] " if seg.speaker else ""
            lines.extend([
                str(i),
                f"{start} --> {end}",
                f"{speaker}{seg.text}",
                ""
            ])
        return "\n".join(lines)

    def to_vtt(self) -> str:
        """导出为 VTT 格式"""
        lines = ["WEBVTT", ""]
        for seg in self.segments:
            start = self._format_timestamp(seg.start_time, sep=".")
            end = self._format_timestamp(seg.end_time, sep=".")
            speaker = f"<v {seg.speaker}>" if seg.speaker else ""
            lines.extend([
                f"{start} --> {end}",
                f"{speaker}{seg.text}",
                ""
            ])
        return "\n".join(lines)

    def to_json(self) -> str:
        """导出为 JSON 格式"""
        data = {
            "meeting_id": self.meeting_id,
            "full_text": self.full_text,
            "segments": [
                {
                    "start": s.start_time,
                    "end": s.end_time,
                    "text": s.text,
                    "speaker": s.speaker,
                    "confidence": s.confidence,
                }
                for s in self.segments
            ],
            "language": self.language,
            "duration": self.duration,
            "model": self.model_used,
            "timestamp": self.timestamp.isoformat(),
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _format_timestamp(self, seconds: float, sep: str = ",") -> str:
        """格式化时间戳"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{ms:03d}"


class LocalTranscriber:
    """
    本地转录器

    使用 Whisper.cpp 或 Faster Whisper 进行本地转录
    """

    def __init__(
        self,
        model: TranscriptionModel = TranscriptionModel.WHISPER_BASE,
        engine: TranscriptionEngine = TranscriptionEngine.WHISPER_CPP,
        model_dir: Optional[str] = None
    ):
        self.model = model
        self.engine = engine
        self.model_dir = model_dir or self._get_default_model_dir()
        self._ensure_model_downloaded()

    def _get_default_model_dir(self) -> str:
        """获取默认模型目录"""
        base = os.path.expanduser("~/.workbuddy/models")
        return os.path.join(base, "whisper")

    def _ensure_model_downloaded(self):
        """确保模型已下载"""
        model_path = os.path.join(self.model_dir, f"{self.model.value}.bin")
        if not os.path.exists(model_path):
            # 首次使用需要下载模型
            print(f"模型 {self.model.value} 尚未下载，首次使用将自动下载...")

    def transcribe_file(
        self,
        audio_path: str,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> TranscriptionResult:
        """
        转录音频文件

        Args:
            audio_path: 音频文件路径
            language: 语言（None 则自动检测）
            progress_callback: 进度回调

        Returns:
            TranscriptionResult: 转录结果
        """
        if self.engine == TranscriptionEngine.WHISPER_CPP:
            return self._transcribe_whisper_cpp(audio_path, language, progress_callback)
        elif self.engine == TranscriptionEngine.FASTER_WHISPER:
            return self._transcribe_faster_whisper(audio_path, language, progress_callback)
        else:
            return self._transcribe_whisper_python(audio_path, language, progress_callback)

    def _transcribe_whisper_cpp(
        self,
        audio_path: str,
        language: Optional[str],
        progress_callback: Optional[Callable]
    ) -> TranscriptionResult:
        """使用 whisper.cpp 转录"""
        model_path = os.path.join(self.model_dir, f"{self.model.value}.bin")

        # 构建命令
        cmd = [
            "whisper.cpp/main",
            "-m", model_path,
            "-f", audio_path,
            "--output-json",
        ]

        if language:
            cmd.extend(["-l", language])

        # 执行转录
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            # 解析输出
            output = json.loads(result.stdout)

            # 构建结果
            segments = []
            for seg in output.get("transcription", []):
                segments.append(TranscriptionSegment(
                    start_time=seg.get("t0", 0) / 100.0,
                    end_time=seg.get("t1", 0) / 100.0,
                    text=seg.get("text", "").strip(),
                    confidence=seg.get("probability", 0.0),
                ))

            return TranscriptionResult(
                meeting_id=os.path.splitext(os.path.basename(audio_path))[0],
                full_text=" ".join(s.text for s in segments),
                segments=segments,
                language=output.get("language", "zh"),
                duration=segments[-1].end_time if segments else 0.0,
                model_used=self.model.value,
                engine=self.engine.value,
            )

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"转录失败: {e.stderr}")

    def _transcribe_faster_whisper(
        self,
        audio_path: str,
        language: Optional[str],
        progress_callback: Optional[Callable]
    ) -> TranscriptionResult:
        """使用 Faster Whisper 转录"""
        try:
            from faster_whisper import WhisperModel

            # 加载模型
            model_size = self.model.value.replace("whisper-", "")
            model = WhisperModel(
                model_size,
                device="cuda" if self._has_gpu() else "cpu",
                download_root=self.model_dir
            )

            # 转录
            segments, info = model.transcribe(
                audio_path,
                language=language,
                beam_size=5,
                vad_filter=True,
            )

            # 构建结果
            seg_list = []
            full_texts = []

            for seg in segments:
                seg_list.append(TranscriptionSegment(
                    start_time=seg.start,
                    end_time=seg.end,
                    text=seg.text.strip(),
                    confidence=seg.avg_logprob,
                ))
                full_texts.append(seg.text)

                if progress_callback:
                    progress_callback(seg.end / info.duration)

            return TranscriptionResult(
                meeting_id=os.path.splitext(os.path.basename(audio_path))[0],
                full_text=" ".join(full_texts),
                segments=seg_list,
                language=info.language,
                duration=info.duration,
                model_used=self.model.value,
                engine=self.engine.value,
            )

        except ImportError:
            raise RuntimeError("请安装 faster-whisper: pip install faster-whisper")

    def _transcribe_whisper_python(
        self,
        audio_path: str,
        language: Optional[str],
        progress_callback: Optional[Callable]
    ) -> TranscriptionResult:
        """使用 whisper Python 包转录"""
        try:
            import whisper
            import numpy as np

            # 加载模型
            model = whisper.load_model(self.model.value)

            # 转录
            result = model.transcribe(
                audio_path,
                language=language,
                fp16=self._has_gpu(),
            )

            # 构建结果
            segments = []
            for seg in result.get("segments", []):
                segments.append(TranscriptionSegment(
                    start_time=seg["start"],
                    end_time=seg["end"],
                    text=seg["text"].strip(),
                    confidence=seg.get("avg_logprob", 0.0),
                ))

            return TranscriptionResult(
                meeting_id=os.path.splitext(os.path.basename(audio_path))[0],
                full_text=result["text"].strip(),
                segments=segments,
                language=result.get("language", "zh"),
                duration=segments[-1].end_time if segments else 0.0,
                model_used=self.model.value,
                engine=self.engine.value,
            )

        except ImportError:
            raise RuntimeError("请安装 openai-whisper: pip install openai-whisper")

    def _has_gpu(self) -> bool:
        """检测是否有 GPU"""
        try:
            import torch
            return torch.cuda.is_available() or torch.backends.mps.is_available()
        except ImportError:
            return False


class StreamingTranscriber:
    """
    流式转录器

    支持实时转录（用于直播、会议监控等场景）
    """

    def __init__(
        self,
        model: TranscriptionModel = TranscriptionModel.WHISPER_BASE,
        sample_rate: int = 16000
    ):
        self.model = model
        self.sample_rate = sample_rate
        self._buffer = bytearray()
        self._is_running = False

    def start(self, callback: Callable[[TranscriptionSegment], None]):
        """开始流式转录"""
        self._is_running = True
        # 实现需要结合音频捕获模块

    def stop(self):
        """停止流式转录"""
        self._is_running = False
        self._buffer.clear()

    def process_audio_chunk(self, audio_data: bytes) -> Optional[TranscriptionSegment]:
        """处理音频数据块"""
        self._buffer.extend(audio_data)
        # 当累积足够音频时进行转录
        min_samples = self.sample_rate * 1  # 至少1秒
        if len(self._buffer) >= min_samples * 2:  # 16-bit audio
            # 执行转录
            pass


# 便捷函数
def quick_transcribe(
    audio_path: str,
    model: str = "base",
    engine: str = "faster-whisper"
) -> TranscriptionResult:
    """
    快速转录

    Args:
        audio_path: 音频文件路径
        model: 模型大小 (base/small/medium/large)
        engine: 引擎 (whisper-cpp/faster-whisper/whisper-python)

    Returns:
        TranscriptionResult: 转录结果
    """
    model_map = {
        "base": TranscriptionModel.WHISPER_BASE,
        "small": TranscriptionModel.WHISPER_SMALL,
        "medium": TranscriptionModel.WHISPER_MEDIUM,
        "large": TranscriptionModel.WHISPER_LARGE,
    }

    engine_map = {
        "whisper-cpp": TranscriptionEngine.WHISPER_CPP,
        "faster-whisper": TranscriptionEngine.FASTER_WHISPER,
        "whisper-python": TranscriptionEngine.WHISPER_PYTHON,
    }

    transcriber = LocalTranscriber(
        model=model_map.get(model, TranscriptionModel.WHISPER_BASE),
        engine=engine_map.get(engine, TranscriptionEngine.FASTER_WHISPER),
    )

    return transcriber.transcribe_file(audio_path)
