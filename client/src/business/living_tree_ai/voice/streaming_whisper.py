"""
流式 Whisper 实时字幕模块

集成流式 Whisper 实现实时语音识别和字幕生成
"""

import asyncio
import tempfile
import numpy as np
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass
import queue
import threading


@dataclass
class CaptionSegment:
    """字幕片段"""
    start_time: float
    end_time: float
    text: str
    language: str = "zh"
    confidence: float = 1.0


@dataclass
class StreamRecognitionResult:
    """流式识别结果"""
    text: str
    language: str
    segments: List[CaptionSegment]
    is_final: bool
    timestamp: float


class StreamingWhisper:
    """流式 Whisper 识别器"""

    def __init__(
        self,
        model_size: str = "base",
        language: str = "zh",
        use_flash_attention: bool = True
    ):
        self.model_size = model_size
        self.language = language
        self.use_flash_attention = use_flash_attention
        self.model = None
        self.is_initialized = False
        self._buffer: List[np.ndarray] = []
        self._buffer_lock = threading.Lock()
        self._sample_rate = 16000

    async def initialize(self) -> bool:
        """
        初始化模型

        Returns:
            bool: 是否初始化成功
        """
        if self.is_initialized:
            return True

        try:
            import whisper
            self.model = whisper.load_model(self.model_size)
            self.is_initialized = True
            print(f"[StreamingWhisper] 模型加载成功: {self.model_size}")
            return True

        except ImportError:
            print("[StreamingWhisper] Whisper 未安装，请运行: pip install openai-whisper")
            return False

        except Exception as e:
            print(f"[StreamingWhisper] 模型加载失败: {e}")
            return False

    def load_model(self, model_size: str = "base"):
        """加载模型"""
        self.model_size = model_size
        return asyncio.run(self.initialize())

    def add_audio_chunk(self, audio_chunk: bytes):
        """
        添加音频块

        Args:
            audio_chunk: 音频数据（16-bit PCM）
        """
        audio_array = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0

        with self._buffer_lock:
            self._buffer.append(audio_array)

    def get_buffer_duration(self) -> float:
        """获取缓冲区时长（秒）"""
        with self._buffer_lock:
            if not self._buffer:
                return 0
            total_samples = sum(len(a) for a in self._buffer)
            return total_samples / self._sample_rate

    def clear_buffer(self):
        """清空缓冲区"""
        with self._buffer_lock:
            self._buffer.clear()

    async def recognize_streaming(
        self,
        min_duration: float = 0.5,
        max_duration: float = 30.0,
        callback: Optional[Callable[[StreamRecognitionResult], None]] = None
    ) -> Optional[StreamRecognitionResult]:
        """
        流式识别

        Args:
            min_duration: 最小识别时长
            max_duration: 最大识别时长
            callback: 识别回调

        Returns:
            Optional[StreamRecognitionResult]: 识别结果
        """
        if not self.is_initialized:
            await self.initialize()

        if not self.model:
            return None

        with self._buffer_lock:
            if not self._buffer:
                return None

            audio_data = np.concatenate(self._buffer)
            buffer_duration = len(audio_data) / self._sample_rate

            if buffer_duration < min_duration:
                return None

            if buffer_duration > max_duration:
                audio_data = audio_data[:int(max_duration * self._sample_rate)]

        try:
            result = self.model.transcribe(
                audio_data,
                language=self.language,
                task="transcribe",
                initial_prompt="以下是普通话的转录。",
                temperature=0.0,
                condition_on_previous_text=True
            )

            segments = []
            for seg in result.get("segments", []):
                segment = CaptionSegment(
                    start_time=seg.get("start", 0),
                    end_time=seg.get("end", 0),
                    text=seg.get("text", "").strip(),
                    language=self.language,
                    confidence=seg.get("confidence", 1.0)
                )
                segments.append(segment)

            stream_result = StreamRecognitionResult(
                text=result.get("text", "").strip(),
                language=self.language,
                segments=segments,
                is_final=True,
                timestamp=asyncio.get_event_loop().time()
            )

            if callback:
                callback(stream_result)

            return stream_result

        except Exception as e:
            print(f"[StreamingWhisper] 识别失败: {e}")
            return None

    async def recognize_once(
        self,
        audio_data: bytes,
        language: Optional[str] = None
    ) -> Optional[StreamRecognitionResult]:
        """
        单次识别

        Args:
            audio_data: 音频数据
            language: 语言

        Returns:
            Optional[StreamRecognitionResult]: 识别结果
        """
        if not self.is_initialized:
            await self.initialize()

        if not self.model:
            return None

        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            result = self.model.transcribe(
                audio_array,
                language=language or self.language,
                task="transcribe",
                temperature=0.0
            )

            segments = []
            for seg in result.get("segments", []):
                segment = CaptionSegment(
                    start_time=seg.get("start", 0),
                    end_time=seg.get("end", 0),
                    text=seg.get("text", "").strip(),
                    language=language or self.language,
                    confidence=seg.get("confidence", 1.0)
                )
                segments.append(segment)

            return StreamRecognitionResult(
                text=result.get("text", "").strip(),
                language=language or self.language,
                segments=segments,
                is_final=True,
                timestamp=asyncio.get_event_loop().time()
            )

        except Exception as e:
            print(f"[StreamingWhisper] 识别失败: {e}")
            return None


class RealtimeCaptions:
    """实时字幕系统"""

    def __init__(self, whisper: Optional[StreamingWhisper] = None):
        self.whisper = whisper or StreamingWhisper()
        self._is_running = False
        self._caption_callback: Optional[Callable[[List[CaptionSegment]], None]] = None
        self._text_callback: Optional[Callable[[str], None]] = None
        self._current_segments: List[CaptionSegment] = []
        self._finalized_segments: List[CaptionSegment] = []
        self._recognition_task: Optional[asyncio.Task] = None

    async def start(
        self,
        caption_callback: Optional[Callable[[List[CaptionSegment]], None]] = None,
        text_callback: Optional[Callable[[str], None]] = None
    ):
        """
        启动字幕系统

        Args:
            caption_callback: 字幕片段回调
            text_callback: 文本更新回调
        """
        await self.whisper.initialize()

        self._caption_callback = caption_callback
        self._text_callback = text_callback
        self._is_running = True

        self._recognition_task = asyncio.create_task(self._recognition_loop())

    async def stop(self):
        """停止字幕系统"""
        self._is_running = False

        if self._recognition_task:
            self._recognition_task.cancel()
            try:
                await self._recognition_task
            except asyncio.CancelledError:
                pass

    def add_audio(self, audio_chunk: bytes):
        """添加音频"""
        self.whisper.add_audio_chunk(audio_chunk)

    async def _recognition_loop(self):
        """识别循环"""
        while self._is_running:
            try:
                await asyncio.sleep(0.3)

                if self.whisper.get_buffer_duration() < 0.5:
                    continue

                result = await self.whisper.recognize_streaming(
                    min_duration=0.5,
                    max_duration=30.0
                )

                if result and result.text:
                    self._current_segments = result.segments

                    if self._caption_callback:
                        self._caption_callback(self._current_segments)

                    if self._text_callback:
                        self._text_callback(result.text)

                    self.whisper.clear_buffer()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[RealtimeCaptions] 识别循环错误: {e}")

    def get_current_captions(self) -> List[CaptionSegment]:
        """获取当前字幕"""
        return self._current_segments.copy()

    def get_all_captions(self) -> List[CaptionSegment]:
        """获取所有字幕"""
        return self._finalized_segments + self._current_segments


class CaptionGenerator:
    """字幕生成器"""

    @staticmethod
    def generate_srt(captions: List[CaptionSegment], offset: float = 0) -> str:
        """
        生成 SRT 格式字幕

        Args:
            captions: 字幕片段
            offset: 时间偏移

        Returns:
            str: SRT 格式字符串
        """
        output = []
        for i, cap in enumerate(captions, 1):
            start = CaptionGenerator._format_srt_time(cap.start_time + offset)
            end = CaptionGenerator._format_srt_time(cap.end_time + offset)
            output.append(f"{i}\n{start} --> {end}\n{cap.text}\n")
        return "\n".join(output)

    @staticmethod
    def generate_vtt(captions: List[CaptionSegment], offset: float = 0) -> str:
        """
        生成 VTT 格式字幕

        Args:
            captions: 字幕片段
            offset: 时间偏移

        Returns:
            str: VTT 格式字符串
        """
        output = ["WEBVTT\n"]
        for cap in captions:
            start = CaptionGenerator._format_vtt_time(cap.start_time + offset)
            end = CaptionGenerator._format_vtt_time(cap.end_time + offset)
            output.append(f"{start} --> {end}\n{cap.text}\n")
        return "\n".join(output)

    @staticmethod
    def generate_ass(captions: List[CaptionSegment], offset: float = 0) -> str:
        """
        生成 ASS 格式字幕

        Args:
            captions: 字幕片段
            offset: 时间偏移

        Returns:
            str: ASS 格式字符串
        """
        output = [
            "[Script Info]",
            "Title: Generated Captions",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]

        for cap in captions:
            start = CaptionGenerator._format_ass_time(cap.start_time + offset)
            end = CaptionGenerator._format_ass_time(cap.end_time + offset)
            text = cap.text.replace("\\", "\\\\").replace("\n", "\\N")
            output.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

        return "\n".join(output)

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """格式化 SRT 时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def _format_vtt_time(seconds: float) -> str:
        """格式化 VTT 时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    @staticmethod
    def _format_ass_time(seconds: float) -> str:
        """格式化 ASS 时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


_global_whisper: Optional[StreamingWhisper] = None


def get_streaming_whisper(model_size: str = "base") -> StreamingWhisper:
    """获取流式 Whisper"""
    global _global_whisper
    if _global_whisper is None:
        _global_whisper = StreamingWhisper(model_size=model_size)
    return _global_whisper
