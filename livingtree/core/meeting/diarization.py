"""
Speaker Diarization - 说话人识别模块

识别音频中的不同说话人：
1. 说话人分割（Speaker Segmentation）
2. 说话人嵌入（Speaker Embedding）
3. 聚类（Clustering）

支持方案：
1. pyannote.audio - 开源方案
2. 简单能量检测 - 轻量级备选
"""

import os
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from enum import Enum

from .transcriber import TranscriptionSegment


class DiarizationEngine(Enum):
    """说话人识别引擎"""
    PYANNOTE = "pyannote"
    SIMPLE_ENERGY = "simple_energy"
    RESemblyzer = "resemblyzer"


@dataclass
class SpeakerSegment:
    """说话人片段"""
    start_time: float           # 开始时间
    end_time: float             # 结束时间
    speaker_id: str            # 说话人 ID
    speaker_name: Optional[str] = None  # 说话人名称（可自定义）
    confidence: float = 0.0     # 置信度
    embedding: Optional[np.ndarray] = None  # 说话人嵌入向量


@dataclass
class DiarizationResult:
    """说话人识别结果"""
    meeting_id: str
    segments: List[SpeakerSegment]  # 说话人片段
    num_speakers: int            # 检测到的说话人数量
    duration: float = 0.0        # 总时长
    engine: str = ""             # 使用的引擎
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SimpleEnergyDiarizer:
    """
    简单能量检测说话人分离

    基于能量和频率特征分离不同说话人
    轻量级方案，适合资源受限环境
    """

    def __init__(
        self,
        num_speakers: int = 2,
        energy_threshold: float = 0.02,
        min_speech_duration: float = 0.3
    ):
        self.num_speakers = num_speakers
        self.energy_threshold = energy_threshold
        self.min_speech_duration = min_speech_duration

    def diarize(self, audio_path: str) -> DiarizationResult:
        """
        执行说话人识别

        Args:
            audio_path: 音频文件路径

        Returns:
            DiarizationResult: 说话人识别结果
        """
        import struct
        import wave

        # 读取音频
        with wave.open(audio_path, 'rb') as wf:
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            audio_data = wf.readframes(n_frames)

        # 转换为 numpy 数组
        audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # 计算能量
        frame_length = int(sample_rate * 0.025)  # 25ms 帧
        hop_length = int(sample_rate * 0.010)   # 10ms 跳跃

        energy = []
        for i in range(0, len(audio) - frame_length, hop_length):
            frame = audio[i:i + frame_length]
            energy.append(np.sqrt(np.mean(frame ** 2)))

        energy = np.array(energy)

        # 简单二值化
        speech = energy > self.energy_threshold

        # 找语音段
        speech_segments = self._find_segments(speech, hop_length / sample_rate)

        # 分配说话人（基于能量变化）
        speaker_segments = self._assign_speakers(
            speech_segments,
            energy,
            hop_length / sample_rate
        )

        return DiarizationResult(
            meeting_id=os.path.splitext(os.path.basename(audio_path))[0],
            segments=speaker_segments,
            num_speakers=self.num_speakers,
            duration=len(audio) / sample_rate,
            engine=DiarizationEngine.SIMPLE_ENERGY.value,
        )

    def _find_segments(self, binary: np.ndarray, hop_duration: float) -> List[Tuple[float, float]]:
        """找语音段"""
        segments = []
        in_speech = False
        start = 0.0

        for i, is_speech in enumerate(binary):
            time = i * hop_duration
            if is_speech and not in_speech:
                start = time
                in_speech = True
            elif not is_speech and in_speech:
                duration = time - start
                if duration >= self.min_speech_duration:
                    segments.append((start, time))
                in_speech = False

        if in_speech:
            segments.append((start, len(binary) * hop_duration))

        return segments

    def _assign_speakers(
        self,
        segments: List[Tuple[float, float]],
        energy: np.ndarray,
        hop_duration: float
    ) -> List[SpeakerSegment]:
        """分配说话人"""
        speaker_segments = []
        speaker_energies = {i: [] for i in range(self.num_speakers)}

        for start, end in segments:
            # 计算该段的平均能量
            start_idx = int(start / hop_duration)
            end_idx = int(end / hop_duration)
            avg_energy = np.mean(energy[start_idx:end_idx]) if end_idx > start_idx else 0

            # 分配给能量最接近的说话人
            speaker_id = min(
                range(self.num_speakers),
                key=lambda s: abs(np.mean(speaker_energies[s]) - avg_energy)
                if speaker_energies[s] else avg_energy
            )

            speaker_energies[speaker_id].append(avg_energy)

            speaker_segments.append(SpeakerSegment(
                start_time=start,
                end_time=end,
                speaker_id=f"SPEAKER_{speaker_id:02d}",
                confidence=0.6  # 简化实现
            ))

        return speaker_segments


class PyAnnoteDiarizer:
    """
    PyAnnote 说话人识别

    使用开源 pyannote.audio 库进行精确说话人识别
    需要模型文件
    """

    def __init__(
        self,
        model_name: str = "pyannote/speaker-diarization-3.0",
        auth_token: Optional[str] = None
    ):
        self.model_name = model_name
        self.auth_token = auth_token or os.environ.get("HF_TOKEN")
        self._model = None

    def _load_model(self):
        """加载模型"""
        if self._model is None:
            try:
                from pyannote.audio import Pipeline
                self._model = Pipeline.from_pretrained(
                    self.model_name,
                    use_auth_token=self.auth_token
                )
            except ImportError:
                raise RuntimeError("请安装 pyannote.audio: pip install pyannote.audio")

    def diarize(self, audio_path: str) -> DiarizationResult:
        """
        执行说话人识别

        Args:
            audio_path: 音频文件路径

        Returns:
            DiarizationResult: 说话人识别结果
        """
        self._load_model()

        try:
            # 执行说话人识别
            from pyannote.core import Segment

            diarization = self._model(audio_path)

            # 转换结果
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append(SpeakerSegment(
                    start_time=turn.start,
                    end_time=turn.end,
                    speaker_id=speaker,
                    confidence=0.9  # pyannote 不直接提供置信度
                ))

            # 统计说话人数量
            speakers = set(s.segments[0].speaker_id for s in [diarization] if hasattr(s, 'speaker'))

            return DiarizationResult(
                meeting_id=os.path.splitext(os.path.basename(audio_path))[0],
                segments=segments,
                num_speakers=len(set(s.speaker_id for s in segments)),
                duration=segments[-1].end_time if segments else 0.0,
                engine=DiarizationEngine.PYANNOTE.value,
            )

        except Exception as e:
            raise RuntimeError(f"PyAnnote 说话人识别失败: {e}")


class ResemblyzerDiarizer:
    """
    Resemblyzer 说话人识别

    使用 Resemblyzer 进行说话人嵌入和聚类
    """

    def __init__(self, num_speakers: int = 2):
        self.num_speakers = num_speakers
        self._encoder = None

    def _load_encoder(self):
        """加载编码器"""
        if self._encoder is None:
            try:
                from resemblyzer import VoiceEncoder
                self._encoder = VoiceEncoder()
            except ImportError:
                raise RuntimeError("请安装 resemblyzer: pip install resemblyzer")

    def diarize(self, audio_path: str) -> DiarizationResult:
        """执行说话人识别"""
        self._load_encoder()

        from resemblyzer import Audio
        from scipy.cluster.hierarchy import fcluster, linkage

        # 加载音频
        audio = Audio.from_file(audio_path)

        # 获取语音段落
        speech_time = audio.speech_times

        # 为每个语音段计算嵌入
        embeddings = []
        times = []
        for start, end in speech_time:
            embed = self._encoder.embed_utterance(audio.subsegment(start, end))
            embeddings.append(embed)
            times.append((start + end) / 2)

        if not embeddings:
            return DiarizationResult(
                meeting_id=os.path.splitext(os.path.basename(audio_path))[0],
                segments=[],
                num_speakers=0,
                duration=audio.duration,
                engine=DiarizationEngine.RESemblyzer.value,
            )

        # 聚类
        embeddings = np.array(embeddings)
        linkage_matrix = linkage(embeddings, method='ward')
        speaker_labels = fcluster(linkage_matrix, self.num_speakers, criterion='maxclust')

        # 构建结果
        segments = []
        for (start, end), label in zip(speech_time, speaker_labels):
            segments.append(SpeakerSegment(
                start_time=start,
                end_time=end,
                speaker_id=f"SPEAKER_{label:02d}",
                confidence=0.75,
                embedding=embeddings[label - 1] if label <= len(embeddings) else None
            ))

        return DiarizationResult(
            meeting_id=os.path.splitext(os.path.basename(audio_path))[0],
            segments=segments,
            num_speakers=self.num_speakers,
            duration=audio.duration,
            engine=DiarizationEngine.RESemblyzer.value,
        )


class SpeakerDiarization:
    """
    说话人识别统一接口
    """

    ENGINES = {
        DiarizationEngine.PYANNOTE: PyAnnoteDiarizer,
        DiarizationEngine.SIMPLE_ENERGY: SimpleEnergyDiarizer,
        DiarizationEngine.RESemblyzer: ResemblyzerDiarizer,
    }

    def __init__(
        self,
        engine: str = "simple_energy",
        num_speakers: int = 2,
        **kwargs
    ):
        """
        初始化说话人识别

        Args:
            engine: 引擎名称 (pyannote/simple_energy/resemblyzer)
            num_speakers: 预估说话人数量
            **kwargs: 引擎特定参数
        """
        engine_enum = DiarizationEngine(engine)
        diarizer_class = self.ENGINES.get(engine_enum)

        if not diarizer_class:
            raise ValueError(f"不支持的引擎: {engine}")

        if engine_enum == DiarizationEngine.PYANNOTE:
            self._diarizer = diarizer_class(**kwargs)
        elif engine_enum == DiarizationEngine.SIMPLE_ENERGY:
            self._diarizer = diarizer_class(num_speakers=num_speakers)
        else:
            self._diarizer = diarizer_class(num_speakers=num_speakers)

        self.engine = engine_enum.value

    def diarize(self, audio_path: str) -> DiarizationResult:
        """执行说话人识别"""
        return self._diarizer.diarize(audio_path)

    def merge_with_transcription(
        self,
        diarization_result: DiarizationResult,
        transcription_segments: List[TranscriptionSegment]
    ) -> List[TranscriptionSegment]:
        """
        将说话人识别结果与转录结果合并

        Args:
            diarization_result: 说话人识别结果
            transcription_segments: 转录片段

        Returns:
            带说话人的转录片段
        """
        merged = []

        for seg in transcription_segments:
            # 找到对应的说话人
            speaker = self._find_speaker_for_time(
                diarization_result.segments,
                seg.start_time
            )

            merged.append(TranscriptionSegment(
                start_time=seg.start_time,
                end_time=seg.end_time,
                text=seg.text,
                speaker=speaker,
                confidence=seg.confidence
            ))

        return merged

    def _find_speaker_for_time(
        self,
        speaker_segments: List[SpeakerSegment],
        time: float
    ) -> Optional[str]:
        """根据时间找说话人"""
        for spk_seg in speaker_segments:
            if spk_seg.start_time <= time < spk_seg.end_time:
                return spk_seg.speaker_id
        return None

    def assign_speaker_names(
        self,
        result: DiarizationResult,
        name_mapping: Dict[str, str]
    ) -> DiarizationResult:
        """
        为说话人分配名称

        Args:
            result: 说话人识别结果
            name_mapping: {speaker_id: name} 映射

        Returns:
            更新后的结果
        """
        for segment in result.segments:
            if segment.speaker_id in name_mapping:
                segment.speaker_name = name_mapping[segment.speaker_id]

        return result

    @classmethod
    def quick_diarize(cls, audio_path: str, num_speakers: int = 2) -> DiarizationResult:
        """
        快速说话人识别

        自动选择可用的最佳引擎
        """
        # 优先尝试 pyannote
        try:
            diarizer = cls(engine="pyannote", num_speakers=num_speakers)
            return diarizer.diarize(audio_path)
        except Exception:
            pass

        # 降级到简单方案
        diarizer = cls(engine="simple_energy", num_speakers=num_speakers)
        return diarizer.diarize(audio_path)
