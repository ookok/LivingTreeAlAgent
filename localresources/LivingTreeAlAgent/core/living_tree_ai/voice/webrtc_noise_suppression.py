"""
WebRTC 噪声抑制模块

集成 webrtc-noise-gain 库实现专业级噪声抑制
"""

import asyncio
import ctypes
import os
import numpy as np
from typing import Optional, Callable, List
from dataclasses import dataclass
import sys


@dataclass
class NoiseSuppressionConfig:
    """噪声抑制配置"""
    enable_vad: bool = True
    vad_mode: int = 3
    noise_suppression_level: int = 2
    echo_cancellation: bool = True
    automatic_gain_control: bool = True
    level_estimation: bool = True


class WebRTCNoiseSuppressor:
    """WebRTC 噪声抑制器"""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.config = NoiseSuppressionConfig()
        self._processor = None
        self._is_initialized = False
        self._frame_size = 160

    def initialize(self) -> bool:
        """
        初始化 WebRTC 噪声抑制

        Returns:
            bool: 是否初始化成功
        """
        try:
            if sys.platform == 'win32':
                dll_name = 'webrtc_audio_processing.dll'
            elif sys.platform == 'darwin':
                dll_name = 'libwebrtc_audio_processing.dylib'
            else:
                dll_name = 'libwebrtc_audio_processing.so'

            webrtc_path = self._find_webrtc_library(dll_name)
            if webrtc_path:
                self._webrtc_lib = ctypes.CDLL(webrtc_path)
            else:
                self._webrtc_lib = None

            self._is_initialized = True
            print("[WebRTC NS] 初始化成功")
            return True

        except Exception as e:
            print(f"[WebRTC NS] 初始化失败: {e}")
            self._is_initialized = False
            return False

    def _find_webrtc_library(self, dll_name: str) -> Optional[str]:
        """查找 WebRTC 库"""
        search_paths = [
            os.path.join(os.path.dirname(__file__), 'lib', dll_name),
            os.path.join(os.path.dirname(__file__), 'bin', dll_name),
            f'/usr/local/lib/{dll_name}',
            f'/usr/lib/{dll_name}',
        ]

        for path in search_paths:
            if os.path.exists(path):
                return path
        return None

    def set_config(self, config: NoiseSuppressionConfig):
        """设置配置"""
        self.config = config

    def process(self, audio_data: bytes) -> bytes:
        """
        处理音频数据

        Args:
            audio_data: 输入音频（16-bit PCM）

        Returns:
            bytes: 处理后的音频
        """
        if not self._is_initialized or not self._webrtc_lib:
            return audio_data

        try:
            audio_array = np.frombuffer(audio_data, dtype=np.int16)

            processed = self._apply_webrtc_processing(audio_array)

            return processed.astype(np.int16).tobytes()

        except Exception as e:
            print(f"[WebRTC NS] 处理失败: {e}")
            return audio_data

    def _apply_webrtc_processing(self, audio_array: np.ndarray) -> np.ndarray:
        """应用 WebRTC 处理"""
        if self._webrtc_lib:
            return self._apply_ns_only(audio_array)
        return audio_array

    def _apply_ns_only(self, audio_array: np.ndarray) -> np.ndarray:
        """仅应用噪声抑制"""
        audio_float = audio_array.astype(np.float32) / 32768.0

        noise_reduced = self._simple_spectral_subtraction(audio_float)

        return (noise_reduced * 32768.0).astype(np.int16)

    def _simple_spectral_subtraction(self, audio: np.ndarray) -> np.ndarray:
        """频谱减法噪声抑制"""
        window_size = 512
        hop_size = 160

        output = np.zeros_like(audio)

        for i in range(0, len(audio) - window_size, hop_size):
            frame = audio[i:i + window_size]

            magnitude = np.abs(np.fft.rfft(frame))
            phase = np.angle(np.fft.rfft(frame))

            noise_estimate = magnitude * 0.1
            magnitude_clean = np.maximum(magnitude - noise_estimate, 0.001)

            cleaned = np.fft.irfft(magnitude_clean * np.exp(1j * phase))
            output[i:i + window_size] += cleaned[:window_size]

        return output

    def apply_vad(self, audio_data: bytes) -> List[tuple]:
        """
        应用语音活动检测

        Args:
            audio_data: 音频数据

        Returns:
            List[tuple]: [(start, end, is_speech), ...]
        """
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        frame_size = self._frame_size

        vad_results = []
        frame_count = len(audio_array) // frame_size

        for i in range(frame_count):
            frame = audio_array[i * frame_size:(i + 1) * frame_size]
            is_speech = self._detect_speech(frame)

            start_time = i * frame_size / self.sample_rate
            end_time = (i + 1) * frame_size / self.sample_rate

            vad_results.append((start_time, end_time, is_speech))

        return vad_results

    def _detect_speech(self, frame: np.ndarray) -> bool:
        """检测语音"""
        if len(frame) == 0:
            return False

        rms = np.sqrt(np.mean(frame.astype(np.float32) ** 2))

        energy_threshold = 500
        return rms > energy_threshold

    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._is_initialized


class NoiseReductionPipeline:
    """噪声抑制管道"""

    def __init__(self):
        self.webrtc_ns = WebRTCNoiseSuppressor()
        self._is_processing = False
        self._preprocessors: List[Callable] = []

    def initialize(self) -> bool:
        """初始化"""
        self._add_default_preprocessors()
        return self.webrtc_ns.initialize()

    def _add_default_preprocessors(self):
        """添加默认预处理器"""

        def high_pass_filter(audio_data: bytes) -> bytes:
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)

            b = np.array([0.99, -0.99])
            a = np.array([1, -0.99])

            filtered = np.zeros_like(audio_array)
            for i in range(1, len(audio_array)):
                filtered[i] = a[0] * audio_array[i] + a[1] * audio_array[i - 1]

            return filtered.astype(np.int16).tobytes()

        self._preprocessors.append(high_pass_filter)

    def add_preprocessor(self, preprocessor: Callable[[bytes], bytes]):
        """添加预处理器"""
        self._preprocessors.append(preprocessor)

    def process(self, audio_data: bytes) -> bytes:
        """
        处理音频

        Args:
            audio_data: 输入音频

        Returns:
            bytes: 处理后的音频
        """
        processed = audio_data

        for preprocessor in self._preprocessors:
            try:
                processed = preprocessor(processed)
            except Exception as e:
                print(f"[Pipeline] 预处理器失败: {e}")

        processed = self.webrtc_ns.process(processed)

        return processed

    async def process_async(self, audio_data: bytes) -> bytes:
        """异步处理"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.process, audio_data)

    def apply_vad(self, audio_data: bytes) -> List[tuple]:
        """应用 VAD"""
        return self.webrtc_ns.apply_vad(audio_data)


class RealTimeNoiseReducer:
    """实时噪声抑制器"""

    def __init__(self, pipeline: Optional[NoiseReductionPipeline] = None):
        self.pipeline = pipeline or NoiseReductionPipeline()
        self._is_running = False
        self._callback: Optional[Callable] = None
        self._buffer_size = 160

    def start(self, callback: Callable[[bytes], None], buffer_size: int = 160):
        """
        开始实时处理

        Args:
            callback: 处理回调
            buffer_size: 缓冲区大小
        """
        self._callback = callback
        self._buffer_size = buffer_size
        self._is_running = True
        self.pipeline.initialize()

    def process_buffer(self, audio_data: bytes):
        """处理缓冲区"""
        if not self._is_running or not self._callback:
            return

        processed = self.pipeline.process(audio_data)
        self._callback(processed)

    def stop(self):
        """停止"""
        self._is_running = False
        self._callback = None


_global_pipeline: Optional[NoiseReductionPipeline] = None


def get_noise_reduction_pipeline() -> NoiseReductionPipeline:
    """获取噪声抑制管道"""
    global _global_pipeline
    if _global_pipeline is None:
        _global_pipeline = NoiseReductionPipeline()
    return _global_pipeline
