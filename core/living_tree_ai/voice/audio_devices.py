"""
增强音频设备管理器

支持完整的音频录制、播放和流式处理
"""

import asyncio
import wave
import io
import threading
from typing import Optional, Callable, List
from dataclasses import dataclass
import queue
import numpy as np


@dataclass
class AudioDeviceInfo:
    """音频设备信息"""
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_sample_rate: float


class AudioDeviceManager:
    """音频设备管理器"""
    
    def __init__(self):
        self._pyaudio = None
        self._input_devices: List[AudioDeviceInfo] = []
        self._output_devices: List[AudioDeviceInfo] = []
        self._current_input_device: Optional[int] = None
        self._current_output_device: Optional[int] = None
        self._is_recording = False
        self._is_playing = False
        self._recording_stream = None
        self._playback_stream = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._recording_callback: Optional[Callable] = None
        self._noise_reduction_enabled = False
        self._noise_gate_threshold = 500  # 噪声门阈值
    
    def initialize(self):
        """初始化音频设备"""
        try:
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()
            self._enumerate_devices()
        except ImportError:
            print("PyAudio 未安装，请运行: pip install pyaudio")
            raise
    
    def _enumerate_devices(self):
        """枚举音频设备"""
        if not self._pyaudio:
            return
        
        self._input_devices.clear()
        self._output_devices.clear()
        
        for i in range(self._pyaudio.get_device_count()):
            try:
                info = self._pyaudio.get_device_info_by_index(i)
                device_info = AudioDeviceInfo(
                    index=i,
                    name=info['name'],
                    max_input_channels=int(info['maxInputChannels']),
                    max_output_channels=int(info['maxOutputChannels']),
                    default_sample_rate=info['defaultSampleRate']
                )
                
                if device_info.max_input_channels > 0:
                    self._input_devices.append(device_info)
                
                if device_info.max_output_channels > 0:
                    self._output_devices.append(device_info)
                    
            except Exception as e:
                print(f"枚举设备 {i} 失败: {e}")
    
    def get_input_devices(self) -> List[AudioDeviceInfo]:
        """获取输入设备列表"""
        return self._input_devices.copy()
    
    def get_output_devices(self) -> List[AudioDeviceInfo]:
        """获取输出设备列表"""
        return self._output_devices.copy()
    
    def set_input_device(self, device_index: int) -> bool:
        """设置输入设备"""
        for device in self._input_devices:
            if device.index == device_index:
                self._current_input_device = device_index
                return True
        return False
    
    def set_output_device(self, device_index: int) -> bool:
        """设置输出设备"""
        for device in self._output_devices:
            if device.index == device_index:
                self._current_output_device = device_index
                return True
        return False
    
    def set_noise_reduction(self, enabled: bool):
        """设置噪声抑制"""
        self._noise_reduction_enabled = enabled
    
    def _apply_noise_gate(self, audio_data: bytes) -> bytes:
        """应用噪声门"""
        if not self._noise_reduction_enabled:
            return audio_data
        
        # 将字节转换为 numpy 数组
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # 计算 RMS
        rms = np.sqrt(np.mean(audio_array.astype(np.float32)**2))
        
        # 如果低于阈值，静音
        if rms < self._noise_gate_threshold:
            return bytes(np.zeros(len(audio_array), dtype=np.int16))
        
        return audio_data
    
    def _apply_noise_reduction(self, audio_data: bytes) -> bytes:
        """应用噪声抑制算法"""
        if not self._noise_reduction_enabled:
            return audio_data
        
        # 简化的噪声抑制实现
        # 实际应用中可以使用 WebRTC 的噪声抑制库
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        
        # 简单的移动平均滤波
        window_size = 5
        smoothed = np.convolve(audio_array, np.ones(window_size)/window_size, mode='same')
        
        return smoothed.astype(np.int16).tobytes()
    
    def start_recording(
        self,
        callback: Callable[[bytes], None],
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
        format_type: int = 16  # 16-bit PCM
    ):
        """
        开始录制
        
        Args:
            callback: 音频数据回调函数
            sample_rate: 采样率
            channels: 通道数
            chunk_size: 块大小
            format_type: 格式类型
        """
        if not self._pyaudio:
            self.initialize()
        
        if self._is_recording:
            return
        
        device_index = self._current_input_device
        if device_index is None and self._input_devices:
            device_index = self._input_devices[0].index
        
        format_map = {
            8: pyaudio.paInt8,
            16: pyaudio.paInt16,
            24: pyaudio.paInt24,
            32: pyaudio.paInt32
        }
        
        self._recording_callback = callback
        
        def callback_wrapper(in_data, frame_count, time_info, status):
            # 应用噪声处理
            processed_data = self._apply_noise_reduction(in_data)
            processed_data = self._apply_noise_gate(processed_data)
            
            # 调用回调
            if self._recording_callback:
                self._recording_callback(processed_data)
            
            return (in_data, pyaudio.paContinue)
        
        try:
            self._recording_stream = self._pyaudio.open(
                format=format_map.get(format_type, pyaudio.paInt16),
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=device_index,
                stream_callback=callback_wrapper,
                frames_per_buffer=chunk_size
            )
            
            self._is_recording = True
            self._recording_stream.start_stream()
            
        except Exception as e:
            print(f"开始录制失败: {e}")
            raise
    
    def stop_recording(self):
        """停止录制"""
        if self._recording_stream:
            self._recording_stream.stop_stream()
            self._recording_stream.close()
            self._recording_stream = None
        
        self._is_recording = False
        self._recording_callback = None
    
    def play_audio(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
        wait: bool = True
    ):
        """
        播放音频
        
        Args:
            audio_data: 音频数据
            sample_rate: 采样率
            channels: 通道数
            wait: 是否等待播放完成
        """
        if not self._pyaudio:
            self.initialize()
        
        device_index = self._current_output_device
        if device_index is None and self._output_devices:
            device_index = self._output_devices[0].index
        
        try:
            # 打开播放流
            stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                output=True,
                output_device_index=device_index
            )
            
            # 播放
            stream.write(audio_data)
            
            # 等待播放完成
            if wait:
                stream.close()
            
        except Exception as e:
            print(f"播放音频失败: {e}")
            raise
    
    async def play_audio_async(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        channels: int = 1
    ):
        """异步播放音频"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self.play_audio,
            audio_data,
            sample_rate,
            channels,
            True
        )
    
    def is_recording(self) -> bool:
        """是否正在录制"""
        return self._is_recording
    
    def is_playing(self) -> bool:
        """是否正在播放"""
        return self._is_playing
    
    def close(self):
        """关闭设备"""
        self.stop_recording()
        
        if self._pyaudio:
            self._pyaudio.terminate()
            self._pyaudio = None


class AudioStreamer:
    """音频流管理器"""
    
    def __init__(self, device_manager: AudioDeviceManager):
        self.device_manager = device_manager
        self._streaming = False
        self._audio_chunks: List[bytes] = []
        self._stream_callback: Optional[Callable] = None
    
    async def start_streaming(
        self,
        on_audio_chunk: Callable[[bytes], None]
    ):
        """
        开始流式传输
        
        Args:
            on_audio_chunk: 音频块回调
        """
        self._streaming = True
        self._stream_callback = on_audio_chunk
        
        def callback(audio_data: bytes):
            if self._streaming and self._stream_callback:
                self._stream_callback(audio_data)
        
        self.device_manager.start_recording(callback)
    
    def stop_streaming(self):
        """停止流式传输"""
        self._streaming = False
        self._stream_callback = None
        self.device_manager.stop_recording()
    
    async def send_audio(self, audio_data: bytes):
        """发送音频数据"""
        if self._stream_callback:
            self._stream_callback(audio_data)
    
    def is_streaming(self) -> bool:
        """是否正在流式传输"""
        return self._streaming


class MeetingRecorder:
    """会议录音器"""
    
    def __init__(self, device_manager: AudioDeviceManager):
        self.device_manager = device_manager
        self._is_recording = False
        self._audio_segments: List[bytes] = []
        self._start_time: Optional[float] = None
        self._segment_count = 0
        self._output_path: Optional[str] = None
    
    def start_recording(self, output_path: str = "meeting_recording.wav"):
        """
        开始录音
        
        Args:
            output_path: 输出文件路径
        """
        if self._is_recording:
            return
        
        self._output_path = output_path
        self._audio_segments.clear()
        self._segment_count = 0
        self._start_time = None
        
        def on_audio(audio_data: bytes):
            if not self._start_time:
                import time
                self._start_time = time.time()
            self._audio_segments.append(audio_data)
        
        self.device_manager.start_recording(on_audio)
        self._is_recording = True
    
    def stop_recording(self) -> Optional[str]:
        """
        停止录音
        
        Returns:
            Optional[str]: 输出文件路径
        """
        if not self._is_recording:
            return None
        
        self.device_manager.stop_recording()
        self._is_recording = False
        
        if not self._audio_segments:
            return None
        
        # 保存为 WAV 文件
        if self._output_path:
            self._save_wav(self._output_path)
            return self._output_path
        
        return None
    
    def _save_wav(self, path: str):
        """保存为 WAV 文件"""
        if not self._audio_segments:
            return
        
        import wave
        
        # 合并所有片段
        total_data = b''.join(self._audio_segments)
        
        # 写入 WAV 文件
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(16000)
            wf.writeframes(total_data)
    
    def get_audio_segments(self) -> List[bytes]:
        """获取音频片段"""
        return self._audio_segments.copy()
    
    def get_recording_duration(self) -> float:
        """获取录音时长（秒）"""
        if not self._start_time:
            return 0
        
        import time
        return time.time() - self._start_time
    
    def is_recording(self) -> bool:
        """是否正在录音"""
        return self._is_recording


# 全局实例
_audio_device_manager: Optional[AudioDeviceManager] = None


def get_audio_device_manager() -> AudioDeviceManager:
    """获取音频设备管理器"""
    global _audio_device_manager
    if _audio_device_manager is None:
        _audio_device_manager = AudioDeviceManager()
    return _audio_device_manager
