"""
MOSS-TTS 声音克隆模块

集成 MOSS-TTS 的声音克隆功能，支持自定义声音生成
"""

import os
import asyncio
import tempfile
import uuid
from typing import Optional, Dict, List, BinaryIO
from dataclasses import dataclass
import numpy as np


@dataclass
class VoiceProfile:
    """声音配置"""
    voice_id: str
    name: str
    reference_audio_path: Optional[str] = None
    embedding: Optional[np.ndarray] = None
    created_at: float = 0


class MossTTSCloner:
    """MOSS-TTS 声音克隆器"""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model = None
        self.is_initialized = False
        self.voice_profiles: Dict[str, VoiceProfile] = {}

    async def initialize(self) -> bool:
        """
        初始化 MOSS-TTS 模型

        Returns:
            bool: 是否初始化成功
        """
        if self.is_initialized:
            return True

        try:
            import torch
            from .moss_tts_model import MossTTSModel

            self.model = MossTTSModel(model_path=self.model_path)
            await self.model.load()
            self.is_initialized = True
            print("[MOSS-TTS] 模型初始化成功")
            return True

        except ImportError as e:
            print(f"[MOSS-TTS] 缺少依赖: {e}")
            print("[MOSS-TTS] 请安装: pip install torch torchaudio")
            return False

        except Exception as e:
            print(f"[MOSS-TTS] 初始化失败: {e}")
            return False

    async def clone_voice(
        self,
        reference_audio_path: str,
        voice_name: str,
        language: str = "zh"
    ) -> Optional[str]:
        """
        克隆声音

        Args:
            reference_audio_path: 参考音频路径（3-10秒）
            voice_name: 声音名称
            language: 语言

        Returns:
            Optional[str]: 声音 ID
        """
        if not self.is_initialized:
            await self.initialize()

        if not self.model:
            print("[MOSS-TTS] 模型未初始化")
            return None

        if not os.path.exists(reference_audio_path):
            print(f"[MOSS-TTS] 参考音频不存在: {reference_audio_path}")
            return None

        import wave
        with wave.open(reference_audio_path, 'rb') as f:
            duration = f.getnframes() / f.getframerate()

        if duration < 3 or duration > 10:
            print(f"[MOSS-TTS] 参考音频时长需要在 3-10 秒之间，当前: {duration:.1f}秒")
            return None

        try:
            voice_id = str(uuid.uuid4())

            embedding = await self.model.extract_embedding(reference_audio_path)

            profile = VoiceProfile(
                voice_id=voice_id,
                name=voice_name,
                reference_audio_path=reference_audio_path,
                embedding=embedding,
                created_at=asyncio.get_event_loop().time()
            )

            self.voice_profiles[voice_id] = profile
            print(f"[MOSS-TTS] 声音克隆成功: {voice_name} ({voice_id})")
            return voice_id

        except Exception as e:
            print(f"[MOSS-TTS] 声音克隆失败: {e}")
            return None

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        output_path: Optional[str] = None,
        speed: float = 1.0,
        pitch: float = 1.0
    ) -> Optional[bytes]:
        """
        使用指定声音合成语音

        Args:
            text: 文本内容
            voice_id: 声音 ID
            output_path: 输出文件路径
            speed: 语速
            pitch: 音调

        Returns:
            Optional[bytes]: 音频数据
        """
        if not self.is_initialized:
            await self.initialize()

        if not self.model:
            return None

        if voice_id and voice_id not in self.voice_profiles:
            print(f"[MOSS-TTS] 声音不存在: {voice_id}")
            return None

        try:
            embedding = None
            if voice_id:
                profile = self.voice_profiles[voice_id]
                embedding = profile.embedding

            audio_data = await self.model.synthesize(
                text=text,
                embedding=embedding,
                speed=speed,
                pitch=pitch
            )

            if output_path and audio_data:
                import wave
                with wave.open(output_path, 'wb') as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(24000)
                    f.writeframes(audio_data)

            return audio_data

        except Exception as e:
            print(f"[MOSS-TTS] 语音合成失败: {e}")
            return None

    async def synthesize_streaming(
        self,
        text: str,
        voice_id: Optional[str] = None,
        callback=None,
        chunk_size: int = 2048
    ):
        """
        流式合成语音

        Args:
            text: 文本内容
            voice_id: 声音 ID
            callback: 音频块回调函数
            chunk_size: 块大小
        """
        if not self.is_initialized:
            await self.initialize()

        if not self.model:
            return

        try:
            embedding = None
            if voice_id and voice_id in self.voice_profiles:
                embedding = self.voice_profiles[voice_id].embedding

            async for audio_chunk in self.model.synthesize_streaming(
                text=text,
                embedding=embedding,
                chunk_size=chunk_size
            ):
                if callback:
                    callback(audio_chunk)

        except Exception as e:
            print(f"[MOSS-TTS] 流式合成失败: {e}")

    def list_voices(self) -> List[Dict]:
        """列出所有声音"""
        return [
            {
                "voice_id": vid,
                "name": profile.name,
                "reference_audio": profile.reference_audio_path
            }
            for vid, profile in self.voice_profiles.items()
        ]

    def delete_voice(self, voice_id: str) -> bool:
        """删除声音"""
        if voice_id in self.voice_profiles:
            del self.voice_profiles[voice_id]
            return True
        return False


class MossTTSFallback:
    """MOSS-TTS 回退实现（使用 edge-tts）"""

    def __init__(self):
        self.current_voice = "zh-CN-XiaoxiaoNeural"
        self.voice_map = {
            "default": "zh-CN-XiaoxiaoNeural",
            "male": "zh-CN-YunxiNeural",
            "female": "zh-CN-XiaoxiaoNeural",
            "young": "zh-CN-XiaoxiaoNeural",
            "older": "zh-CN-YunyangNeural"
        }

    async def initialize(self) -> bool:
        """初始化"""
        try:
            import edge_tts
            return True
        except ImportError:
            print("[MOSS-TTS Fallback] edge-tts 未安装")
            return False

    async def clone_voice(
        self,
        reference_audio_path: str,
        voice_name: str,
        language: str = "zh"
    ) -> Optional[str]:
        """克隆声音（模拟）"""
        voice_id = str(uuid.uuid4())
        self.current_voice = self.voice_map.get(voice_name, "zh-CN-XiaoxiaoNeural")
        return voice_id

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        output_path: Optional[str] = None,
        speed: float = 1.0,
        pitch: float = 1.0
    ) -> Optional[bytes]:
        """合成语音"""
        try:
            from edge_tts import Communicate

            voice = self.current_voice
            rate_str = f"{int((speed - 1) * 100)}%"
            pitch_str = f"{int((pitch - 1) * 50)}Hz"

            communicate = Communicate(text=text, voice=voice)

            if output_path:
                await communicate.save(output_path)
                with open(output_path, 'rb') as f:
                    return f.read()
            else:
                return await communicate.read()

        except Exception as e:
            print(f"[MOSS-TTS Fallback] 合成失败: {e}")
            return None

    def list_voices(self) -> List[Dict]:
        """列出声音"""
        return [{"voice_id": k, "name": v} for k, v in self.voice_map.items()]


_global_cloner: Optional[MossTTSCloner] = None


def get_moss_tts_cloner() -> MossTTSCloner:
    """获取 MOSS-TTS 克隆器"""
    global _global_cloner
    if _global_cloner is None:
        _global_cloner = MossTTSCloner()
    return _global_cloner
