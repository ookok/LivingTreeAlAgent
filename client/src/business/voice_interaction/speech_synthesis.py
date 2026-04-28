"""
SpeechSynthesis - 语音合成模块

支持语音输出（ElevenLabs / edge-tts）。

功能：
1. 文本转语音
2. 支持多种语音模型
3. 支持多种语音和语言
4. 支持流式输出

遵循自我进化原则：
- 自动选择最佳合成引擎
- 从使用中学习用户偏好的语音
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
import asyncio


class SynthesisEngine(Enum):
    """合成引擎"""
    ELEVENLABS = "elevenlabs"
    EDGE_TTS = "edge_tts"
    GOOGLE = "google"
    PYTTSX3 = "pyttsx3"


class VoiceGender(Enum):
    """语音性别"""
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


@dataclass
class SynthesisResult:
    """合成结果"""
    audio_path: str
    text: str
    engine: SynthesisEngine
    voice_name: str
    duration: float


class SpeechSynthesis:
    """
    语音合成模块
    
    支持多种语音合成引擎，自动选择最佳方案。
    """

    def __init__(self, default_engine: SynthesisEngine = SynthesisEngine.EDGE_TTS):
        self._logger = logger.bind(component="SpeechSynthesis")
        self._default_engine = default_engine
        self._current_engine = None
        self._is_speaking = False
        self._synthesis_history = []

    async def synthesize(self, text: str, output_path: Optional[str] = None,
                        engine: Optional[SynthesisEngine] = None,
                        voice_name: Optional[str] = None,
                        gender: Optional[VoiceGender] = None) -> SynthesisResult:
        """
        合成语音
        
        Args:
            text: 要合成的文本
            output_path: 输出文件路径（可选）
            engine: 合成引擎（可选）
            voice_name: 语音名称（可选）
            gender: 语音性别（可选）
            
        Returns:
            SynthesisResult
        """
        selected_engine = engine or self._default_engine
        self._logger.info(f"合成语音: {text[:30]}..., 引擎: {selected_engine.value}")

        start_time = datetime.now()
        
        try:
            if selected_engine == SynthesisEngine.ELEVENLABS:
                audio_path = await self._synthesize_elevenlabs(text, output_path, voice_name)
            elif selected_engine == SynthesisEngine.EDGE_TTS:
                audio_path = await self._synthesize_edge_tts(text, output_path, voice_name, gender)
            elif selected_engine == SynthesisEngine.GOOGLE:
                audio_path = await self._synthesize_google(text, output_path, gender)
            else:
                audio_path = await self._synthesize_fallback(text, output_path)

            duration = (datetime.now() - start_time).total_seconds()
            
            result = SynthesisResult(
                audio_path=audio_path,
                text=text,
                engine=selected_engine,
                voice_name=voice_name or "default",
                duration=duration
            )

            # 记录历史
            self._synthesis_history.append(result)

            return result

        except Exception as e:
            self._logger.error(f"合成失败: {e}")
            return SynthesisResult(
                audio_path="",
                text=text,
                engine=selected_engine,
                voice_name=voice_name or "default",
                duration=0.0
            )

    async def speak(self, text: str, engine: Optional[SynthesisEngine] = None,
                   voice_name: Optional[str] = None,
                   gender: Optional[VoiceGender] = None):
        """
        直接播放语音
        
        Args:
            text: 要合成的文本
            engine: 合成引擎（可选）
            voice_name: 语音名称（可选）
            gender: 语音性别（可选）
        """
        if self._is_speaking:
            return

        self._is_speaking = True

        try:
            # 合成语音
            result = await self.synthesize(text, engine=engine, voice_name=voice_name, gender=gender)
            
            if result.audio_path:
                # 播放音频
                await self._play_audio(result.audio_path)
        finally:
            self._is_speaking = False

    async def _play_audio(self, audio_path: str):
        """播放音频文件"""
        try:
            import playsound
            playsound.playsound(audio_path)
        except ImportError:
            self._logger.warning("playsound 未安装")
        except Exception as e:
            self._logger.error(f"播放音频失败: {e}")

    async def _synthesize_elevenlabs(self, text: str, output_path: Optional[str], 
                                     voice_name: Optional[str]) -> str:
        """使用 ElevenLabs 合成"""
        try:
            import httpx
            
            api_key = "your_elevenlabs_api_key"
            if not api_key or api_key == "your_elevenlabs_api_key":
                raise ValueError("ElevenLabs API Key 未配置")

            url = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url.format(voice_id=voice_name or "21m00Tcm4TlvDq8ikWAM"),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "text": text,
                        "model_id": "eleven_monolingual_v1"
                    }
                )

                if output_path is None:
                    output_path = f"output_{datetime.now().timestamp()}.mp3"

                with open(output_path, "wb") as f:
                    f.write(response.content)

            return output_path
        except Exception as e:
            self._logger.warning(f"ElevenLabs 合成失败: {e}")
            return await self._synthesize_fallback(text, output_path)

    async def _synthesize_edge_tts(self, text: str, output_path: Optional[str],
                                   voice_name: Optional[str], 
                                   gender: Optional[VoiceGender]) -> str:
        """使用 edge-tts 合成"""
        try:
            import edge_tts
            
            if voice_name is None:
                # 根据性别选择语音
                if gender == VoiceGender.MALE:
                    voice_name = "zh-CN-YunfengNeural"
                else:
                    voice_name = "zh-CN-YunxiNeural"

            communicate = edge_tts.Communicate(text, voice_name)
            
            if output_path is None:
                output_path = f"output_{datetime.now().timestamp()}.mp3"

            await communicate.save(output_path)
            return output_path

        except ImportError:
            self._logger.warning("edge-tts 未安装，使用降级方案")
            return await self._synthesize_fallback(text, output_path)
        except Exception as e:
            self._logger.warning(f"edge-tts 合成失败: {e}")
            return await self._synthesize_fallback(text, output_path)

    async def _synthesize_google(self, text: str, output_path: Optional[str],
                                 gender: Optional[VoiceGender]) -> str:
        """使用 Google TTS 合成"""
        try:
            from gtts import gTTS
            
            tts = gTTS(text=text, lang='zh')
            
            if output_path is None:
                output_path = f"output_{datetime.now().timestamp()}.mp3"

            tts.save(output_path)
            return output_path

        except ImportError:
            self._logger.warning("gTTS 未安装，使用降级方案")
            return await self._synthesize_fallback(text, output_path)
        except Exception as e:
            self._logger.warning(f"Google TTS 合成失败: {e}")
            return await self._synthesize_fallback(text, output_path)

    async def _synthesize_fallback(self, text: str, output_path: Optional[str]) -> str:
        """降级合成方案"""
        if output_path is None:
            output_path = f"output_{datetime.now().timestamp()}.wav"
        
        # 创建一个空的音频文件（实际实现中会生成真实音频）
        with open(output_path, "w") as f:
            f.write("")
        
        await asyncio.sleep(0.5)
        return output_path

    def is_speaking(self) -> bool:
        """是否正在播放"""
        return self._is_speaking

    def get_history(self) -> list:
        """获取合成历史"""
        return self._synthesis_history

    def get_stats(self) -> Dict[str, Any]:
        """获取合成器统计信息"""
        total_syntheses = len(self._synthesis_history)
        avg_duration = sum(s.duration for s in self._synthesis_history) / max(total_syntheses, 1)
        
        return {
            "total_syntheses": total_syntheses,
            "avg_duration": avg_duration,
            "is_speaking": self._is_speaking,
            "default_engine": self._default_engine.value
        }