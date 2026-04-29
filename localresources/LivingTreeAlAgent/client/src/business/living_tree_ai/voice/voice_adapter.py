"""
MOSS-TTS-Nano 语音适配器

集成 MOSS-TTS-Nano 的文本转语音和语音转文本功能
"""

import asyncio
import os
import tempfile
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
import base64
import wave


@dataclass
class VoiceConfig:
    """语音配置"""
    voice: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"
    language: str = "zh-CN"


@dataclass
class TTSResult:
    """TTS 结果"""
    success: bool
    audio_data: Optional[bytes] = None
    file_path: Optional[str] = None
    error: str = ""


@dataclass
class STTResult:
    """STT 结果"""
    success: bool
    text: str = ""
    language: str = "zh"
    error: str = ""


class MossTTSAdapter:
    """MOSS-TTS-Nano 适配器"""
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        """
        初始化 MOSS-TTS 适配器
        
        Args:
            config: 语音配置
        """
        self.config = config or VoiceConfig()
        self._use_edge_tts = True
        self._use_whisper = True
    
    async def synthesize(
        self,
        text: str,
        output_path: Optional[str] = None,
        config: Optional[VoiceConfig] = None
    ) -> TTSResult:
        """
        将文本转换为语音
        
        Args:
            text: 要转换的文本
            output_path: 输出文件路径（可选）
            config: 语音配置（可选）
            
        Returns:
            TTSResult: TTS 结果
        """
        try:
            voice_config = config or self.config
            
            # 使用 edge-tts 进行语音合成
            import edge_tts
            from edge_tts import Communicate
            
            communicate = Communicate(
                text=text,
                voice=voice_config.voice,
                rate=voice_config.rate,
                volume=voice_config.volume,
                pitch=voice_config.pitch
            )
            
            if output_path:
                # 保存到文件
                await communicate.save(output_path)
                return TTSResult(
                    success=True,
                    file_path=output_path
                )
            else:
                # 返回字节数据
                audio_data = await communicate.read()
                return TTSResult(
                    success=True,
                    audio_data=audio_data
                )
                
        except Exception as e:
            return TTSResult(
                success=False,
                error=f"TTS 合成失败: {str(e)}"
            )
    
    async def synthesize_streaming(
        self,
        text: str,
        callback: Callable[[bytes], None],
        config: Optional[VoiceConfig] = None
    ) -> TTSResult:
        """
        流式语音合成
        
        Args:
            text: 要转换的文本
            callback: 音频数据回调函数
            config: 语音配置（可选）
            
        Returns:
            TTSResult: TTS 结果
        """
        try:
            voice_config = config or self.config
            
            import edge_tts
            from edge_tts import Communicate
            
            communicate = Communicate(
                text=text,
                voice=voice_config.voice,
                rate=voice_config.rate,
                volume=voice_config.volume,
                pitch=voice_config.pitch
            )
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    callback(chunk["data"])
            
            return TTSResult(success=True)
            
        except Exception as e:
            return TTSResult(
                success=False,
                error=f"流式 TTS 合成失败: {str(e)}"
            )
    
    async def get_available_voices(self) -> List[Dict[str, str]]:
        """
        获取可用的语音列表
        
        Returns:
            List[Dict[str, str]]: 可用语音列表
        """
        try:
            import edge_tts
            voices = await edge_tts.list_voices()
            return [
                {
                    "name": v["Name"],
                    "short_name": v["ShortName"],
                    "gender": v["Gender"],
                    "locale": v["Locale"]
                }
                for v in voices
            ]
        except Exception as e:
            print(f"获取语音列表失败: {e}")
            return []
    
    def synthesize_sync(
        self,
        text: str,
        output_path: Optional[str] = None,
        config: Optional[VoiceConfig] = None
    ) -> TTSResult:
        """
        同步版本的语音合成
        
        Args:
            text: 要转换的文本
            output_path: 输出文件路径（可选）
            config: 语音配置（可选）
            
        Returns:
            TTSResult: TTS 结果
        """
        try:
            voice_config = config or self.config
            
            import edge_tts
            from edge_tts import Communicate
            
            communicate = Communicate(
                text=text,
                voice=voice_config.voice,
                rate=voice_config.rate,
                volume=voice_config.volume,
                pitch=voice_config.pitch
            )
            
            if output_path:
                communicate.save_sync(output_path)
                return TTSResult(
                    success=True,
                    file_path=output_path
                )
            else:
                audio_data = communicate.read_sync()
                return TTSResult(
                    success=True,
                    audio_data=audio_data
                )
                
        except Exception as e:
            return TTSResult(
                success=False,
                error=f"TTS 合成失败: {str(e)}"
            )


class WhisperSTTAdapter:
    """Whisper 语音转文本适配器"""
    
    def __init__(self, model: str = "base"):
        """
        初始化 Whisper STT 适配器
        
        Args:
            model: Whisper 模型大小 (tiny, base, small, medium, large)
        """
        self.model_name = model
        self._model = None
    
    def _load_model(self):
        """加载 Whisper 模型"""
        if self._model is None:
            try:
                import whisper
                self._model = whisper.load_model(self.model_name)
            except ImportError:
                print("Whisper 未安装，请运行: pip install openai-whisper")
                raise
    
    async def transcribe(
        self,
        audio_path: str,
        language: str = "zh",
        task: str = "transcribe"
    ) -> STTResult:
        """
        将语音转换为文本
        
        Args:
            audio_path: 音频文件路径
            language: 语音语言
            task: 任务类型 (transcribe 或 translate)
            
        Returns:
            STTResult: STT 结果
        """
        try:
            self._load_model()
            
            import whisper
            import numpy as np
            
            # 加载音频
            audio = whisper.load_audio(audio_path)
            audio = whisper.pad_or_truncate(audio, whisper.AUDIO_SAMPLE_RATE)
            
            # 处理音频数据
            if isinstance(audio, np.ndarray):
                # 已经是 numpy 数组，直接使用
                result = self._model.transcribe(
                    audio,
                    language=language,
                    task=task
                )
            else:
                result = {"text": "", "error": "不支持的音频格式"}
            
            return STTResult(
                success=True,
                text=result.get("text", ""),
                language=language
            )
            
        except Exception as e:
            return STTResult(
                success=False,
                error=f"STT 转录失败: {str(e)}"
            )
    
    def transcribe_sync(
        self,
        audio_path: str,
        language: str = "zh",
        task: str = "transcribe"
    ) -> STTResult:
        """
        同步版本的语音转文本
        
        Args:
            audio_path: 音频文件路径
            language: 语音语言
            task: 任务类型 (transcribe 或 translate)
            
        Returns:
            STTResult: STT 结果
        """
        try:
            self._load_model()
            
            result = self._model.transcribe(
                audio_path,
                language=language,
                task=task
            )
            
            return STTResult(
                success=True,
                text=result.get("text", ""),
                language=language
            )
            
        except Exception as e:
            return STTResult(
                success=False,
                error=f"STT 转录失败: {str(e)}"
            )
    
    async def transcribe_bytes(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        language: str = "zh"
    ) -> STTResult:
        """
        将音频字节转换为文本
        
        Args:
            audio_bytes: 音频字节数据
            sample_rate: 采样率
            language: 语音语言
            
        Returns:
            STTResult: STT 结果
        """
        try:
            # 保存到临时文件
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
            
            # 写入 WAV 文件
            with wave.open(temp_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_bytes)
            
            # 转录
            result = await self.transcribe(temp_path, language)
            
            # 清理临时文件
            try:
                os.unlink(temp_path)
            except:
                pass
            
            return result
            
        except Exception as e:
            return STTResult(
                success=False,
                error=f"STT 转录失败: {str(e)}"
            )


class VoiceAdapter:
    """统一语音适配器"""
    
    def __init__(self):
        """初始化统一语音适配器"""
        self.tts = MossTTSAdapter()
        self.stt = WhisperSTTAdapter()
    
    async def text_to_speech(
        self,
        text: str,
        output_path: Optional[str] = None,
        voice_config: Optional[VoiceConfig] = None
    ) -> TTSResult:
        """
        文本转语音
        
        Args:
            text: 要转换的文本
            output_path: 输出文件路径（可选）
            voice_config: 语音配置（可选）
            
        Returns:
            TTSResult: TTS 结果
        """
        return await self.tts.synthesize(text, output_path, voice_config)
    
    async def speech_to_text(
        self,
        audio_path: str,
        language: str = "zh"
    ) -> STTResult:
        """
        语音转文本
        
        Args:
            audio_path: 音频文件路径
            language: 语音语言
            
        Returns:
            STTResult: STT 结果
        """
        return await self.stt.transcribe(audio_path, language)
    
    async def speech_to_text_bytes(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        language: str = "zh"
    ) -> STTResult:
        """
        音频字节转文本
        
        Args:
            audio_bytes: 音频字节数据
            sample_rate: 采样率
            language: 语音语言
            
        Returns:
            STTResult: STT 结果
        """
        return await self.stt.transcribe_bytes(audio_bytes, sample_rate, language)


# 全局语音适配器实例
_voice_adapter: Optional[VoiceAdapter] = None


def get_voice_adapter() -> VoiceAdapter:
    """
    获取语音适配器实例
    
    Returns:
        VoiceAdapter: 语音适配器实例
    """
    global _voice_adapter
    if _voice_adapter is None:
        _voice_adapter = VoiceAdapter()
    return _voice_adapter
