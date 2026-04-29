"""
Audio Recorder - 会议录音器

支持多种音频源：
1. 默认麦克风
2. 系统音频
3. 混合录制（麦克风 + 系统音频）

平台支持：
- Windows: WASAPI / DirectSound
- macOS: CoreAudio
- Linux: PulseAudio / ALSA
"""

import os
import queue
import threading
import struct
from dataclasses import dataclass, field
from typing import Optional, Callable, List
from datetime import datetime
from enum import Enum
import wave
import tempfile

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class AudioSource(Enum):
    """音频源"""
    MICROPHONE = "microphone"
    SYSTEM_AUDIO = "system"
    MIXED = "mixed"


@dataclass
class RecordingConfig:
    """录音配置"""
    audio_source: str = "default"
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    include_system_audio: bool = False
    output_dir: str = ""
    file_format: str = "wav"

    # 音频处理
    enable_vad: bool = True           # 语音活动检测
    vad_aggressiveness: int = 3       # VAD 激进程度 (0-3)
    noise_reduction: bool = True       # 降噪

    # 质量设置
    bit_depth: int = 16               # 位深度
    codec: str = "pcm"                # 编解码器


class AudioRecorder:
    """
    会议录音器

    支持多平台音频录制
    """

    def __init__(self, config: RecordingConfig):
        self.config = config
        self._is_recording = False
        self._recording_thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._output_path: Optional[str] = None
        self._recording_start_time: Optional[datetime] = None
        self._frames: List[bytes] = []

    def start(self, meeting_id: str) -> Optional[str]:
        """
        开始录音

        Args:
            meeting_id: 会议 ID（用于生成文件名）

        Returns:
            音频文件路径
        """
        if self._is_recording:
            return None

        # 生成输出路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"meeting_{meeting_id}_{timestamp}.{self.config.file_format}"
        self._output_path = os.path.join(
            self.config.output_dir or tempfile.gettempdir(),
            filename
        )
        os.makedirs(os.path.dirname(self._output_path) or ".", exist_ok=True)

        # 清空帧缓冲区
        self._frames = []

        # 启动录音线程
        self._is_recording = True
        self._recording_start_time = datetime.now()
        self._recording_thread = threading.Thread(
            target=self._recording_loop,
            daemon=True
        )
        self._recording_thread.start()

        return self._output_path

    def stop(self) -> Optional[str]:
        """
        停止录音

        Returns:
            音频文件路径
        """
        if not self._is_recording:
            return None

        self._is_recording = False

        if self._recording_thread:
            self._recording_thread.join(timeout=5)

        # 保存文件
        if self._frames:
            self._save_wav_file()

        return self._output_path

    def _recording_loop(self):
        """录音循环"""
        try:
            import pyaudio

            audio = pyaudio.PyAudio()

            # 选择输入流
            if self.config.audio_source == "default":
                input_device_index = None
            else:
                input_device_index = self._get_device_index(
                    audio,
                    self.config.audio_source
                )

            # 打开流
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=self.config.channels,
                rate=self.config.sample_rate,
                input=True,
                input_device_index=input_device_index,
                frames_per_buffer=self.config.chunk_size
            )

            while self._is_recording:
                try:
                    data = stream.read(
                        self.config.chunk_size,
                        exception_on_overflow=False
                    )
                    self._frames.append(data)

                except Exception as e:
                    print(f"Recording error: {e}")
                    break

            # 关闭流
            stream.stop_stream()
            stream.close()
            audio.terminate()

        except ImportError:
            self._simulate_recording()
        except Exception as e:
            print(f"Recording initialization error: {e}")

    def _simulate_recording(self):
        """模拟录音（当没有 PyAudio 时）"""
        import time

        chunk_duration = self.config.chunk_size / self.config.sample_rate

        while self._is_recording:
            # 生成静音帧
            if NUMPY_AVAILABLE:
                silence = np.zeros(
                    self.config.chunk_size,
                    dtype=np.int16
                ).tobytes()
            else:
                silence = b'\x00\x00' * self.config.chunk_size

            self._frames.append(silence)
            time.sleep(chunk_duration)

    def _save_wav_file(self):
        """保存 WAV 文件"""
        if not self._frames or not self._output_path:
            return

        # 写入 WAV
        with wave.open(self._output_path, 'wb') as wf:
            wf.setnchannels(self.config.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.config.sample_rate)
            wf.writeframes(b''.join(self._frames))

    def _get_device_index(self, audio, device_name: str) -> Optional[int]:
        """获取设备索引"""
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            if device_name.lower() in info["name"].lower():
                return i
        return None

    @property
    def is_recording(self) -> bool:
        """是否正在录音"""
        return self._is_recording

    @property
    def recording_duration(self) -> float:
        """录音时长（秒）"""
        if not self._recording_start_time:
            return 0.0
        if self._is_recording:
            return (datetime.now() - self._recording_start_time).total_seconds()
        return 0.0


class SystemAudioRecorder:
    """
    系统音频录制器

    捕获系统播放的音频（需要平台特定实现）
    """

    def __init__(self, config: RecordingConfig):
        self.config = config
        self._is_recording = False
        self._frames: List[bytes] = []

    def start(self, output_path: str) -> bool:
        """开始录制系统音频"""
        if self._is_recording:
            return False

        self._is_recording = True
        # 实现需要平台特定代码
        return True

    def stop(self) -> Optional[str]:
        """停止录制"""
        self._is_recording = False
        return self._output_path if hasattr(self, '_output_path') else None


class MixedAudioRecorder:
    """
    混合音频录制器

    同时录制麦克风和系统音频，并进行混合
    """

    def __init__(
        self,
        config: RecordingConfig,
        mic_gain: float = 1.0,
        system_gain: float = 1.0
    ):
        self.config = config
        self.mic_gain = mic_gain
        self.system_gain = system_gain
        self._mic_recorder = AudioRecorder(config)
        self._system_recorder = SystemAudioRecorder(config)

    def start(self, output_path: str) -> bool:
        """开始混合录制"""
        mic_ok = self._mic_recorder.start(output_path.replace(".wav", "_mic.wav"))
        system_ok = self._system_recorder.start(output_path.replace(".wav", "_system.wav"))
        return mic_ok or system_ok

    def stop(self) -> Optional[str]:
        """停止混合录制"""
        mic_path = self._mic_recorder.stop()
        system_path = self._system_recorder.stop()

        # 混合音频
        if mic_path and system_path:
            return self._mix_audio(mic_path, system_path)

        return mic_path or system_path

    def _mix_audio(self, mic_path: str, system_path: str) -> str:
        """混合两个音频文件"""
        if not NUMPY_AVAILABLE:
            return mic_path

        try:
            # 读取两个音频
            with wave.open(mic_path, 'rb') as mic_wav:
                mic_frames = mic_wav.readframes(mic_wav.getnframes())
                mic_params = mic_wav.getparams()

            with wave.open(system_path, 'rb') as sys_wav:
                sys_frames = sys_wav.readframes(sys_wav.getnframes())

            # 转换为 numpy
            mic_data = np.frombuffer(mic_frames, dtype=np.int16).astype(np.float32)
            sys_data = np.frombuffer(sys_frames, dtype=np.int16).astype(np.float32)

            # 对齐长度
            min_len = min(len(mic_data), len(sys_data))
            mic_data = mic_data[:min_len]
            sys_data = sys_data[:min_len]

            # 混合
            mixed = (mic_data * self.mic_gain + sys_data * self.system_gain)
            mixed = np.clip(mixed, -32768, 32767).astype(np.int16)

            # 保存
            output_path = mic_path.replace("_mic.wav", "_mixed.wav")
            with wave.open(output_path, 'wb') as out_wav:
                out_wav.setparams(mic_params)
                out_wav.writeframes(mixed.tobytes())

            # 清理临时文件
            os.remove(mic_path)
            os.remove(system_path)

            return output_path

        except Exception as e:
            print(f"Mix audio error: {e}")
            return mic_path


class VoiceActivityDetector:
    """
    语音活动检测器 (VAD)

    用于检测语音和静音
    """

    def __init__(
        self,
        aggressiveness: int = 3,  # 0-3
        sample_rate: int = 16000
    ):
        self.aggressiveness = aggressiveness
        self.sample_rate = sample_rate

    def is_speech(self, audio_chunk: bytes) -> bool:
        """
        检测音频块是否包含语音

        Args:
            audio_chunk: 原始音频数据

        Returns:
            bool: 是否包含语音
        """
        if not NUMPY_AVAILABLE:
            return True

        # 转换为 numpy
        audio = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)

        # 计算能量
        energy = np.sqrt(np.mean(audio ** 2))

        # 简单阈值判断
        threshold = 0.02 * (4 - self.aggressiveness)  # 激进程度越高，阈值越低

        return energy > threshold

    def find_speech_segments(
        self,
        audio_path: str,
        min_speech_duration: float = 0.1,
        min_silence_duration: float = 0.1
    ) -> List[tuple]:
        """
        找音频中的语音段落

        Args:
            audio_path: 音频文件路径
            min_speech_duration: 最小语音时长（秒）
            min_silence_duration: 最小静音时长（秒）

        Returns:
            [(start, end), ...] 语音段落
        """
        if not NUMPY_AVAILABLE:
            return [(0.0, float('inf'))]

        # 读取音频
        with wave.open(audio_path, 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            sample_rate = wf.getframerate()

        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32)

        # 分帧
        frame_length = int(sample_rate * 0.025)  # 25ms
        hop_length = int(sample_rate * 0.010)   # 10ms

        speech_flags = []
        for i in range(0, len(audio) - frame_length, hop_length):
            frame = audio[i:i + frame_length]
            speech_flags.append(self.is_speech(frame.tobytes()))

        # 找连续语音段
        segments = []
        in_speech = False
        start = 0.0

        for i, is_speech in enumerate(speech_flags):
            time = i * hop_length / sample_rate

            if is_speech and not in_speech:
                start = time
                in_speech = True
            elif not is_speech and in_speech:
                duration = time - start
                if duration >= min_speech_duration:
                    segments.append((start, time))
                in_speech = False

        if in_speech:
            duration = (len(speech_flags) * hop_length / sample_rate) - start
            if duration >= min_speech_duration:
                segments.append((start, len(speech_flags) * hop_length / sample_rate))

        return segments
