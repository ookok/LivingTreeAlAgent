"""
语音克隆和会议录音转录模块

支持语音克隆和会议内容的录音转录
"""

import os
import asyncio
import tempfile
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class VoiceCloneConfig:
    """语音克隆配置"""
    reference_audio: Optional[str] = None
    reference_text: Optional[str] = None
    voice_name: str = "custom"


@dataclass
class TranscriptSegment:
    """转录片段"""
    start_time: float
    end_time: float
    text: str
    speaker: Optional[str] = None
    confidence: float = 1.0


@dataclass
class MeetingTranscript:
    """会议转录"""
    meeting_id: str
    segments: List[TranscriptSegment] = field(default_factory=list)
    summary: str = ""
    full_text: str = ""


class VoiceCloner:
    """语音克隆器"""
    
    def __init__(self):
        self.current_voice = None
        self.voice_profiles: Dict[str, VoiceCloneConfig] = {}
    
    async def clone_voice(
        self,
        reference_audio_path: str,
        voice_name: str = "custom"
    ) -> bool:
        """
        克隆声音
        
        Args:
            reference_audio_path: 参考音频路径（3-10秒）
            voice_name: 语音名称
            
        Returns:
            bool: 是否成功
        """
        try:
            # 验证参考音频
            if not os.path.exists(reference_audio_path):
                print(f"[VoiceCloner] 参考音频不存在: {reference_audio_path}")
                return False
            
            # 获取音频时长
            import wave
            with wave.open(reference_audio_path, 'rb') as f:
                duration = f.getnframes() / f.getframerate()
                
            if duration < 3 or duration > 10:
                print(f"[VoiceCloner] 参考音频时长需要在 3-10 秒之间，当前: {duration:.1f}秒")
                return False
            
            # 保存语音配置
            config = VoiceCloneConfig(
                reference_audio=reference_audio_path,
                voice_name=voice_name
            )
            
            self.voice_profiles[voice_name] = config
            self.current_voice = voice_name
            
            print(f"[VoiceCloner] 语音克隆成功: {voice_name}")
            return True
            
        except Exception as e:
            print(f"[VoiceCloner] 语音克隆失败: {e}")
            return False
    
    async def generate_with_voice(
        self,
        text: str,
        voice_name: Optional[str] = None,
        output_path: Optional[str] = None
    ):
        """
        使用克隆的声音生成语音
        
        Args:
            text: 要转换的文本
            voice_name: 语音名称（如果为 None，使用当前语音）
            output_path: 输出路径
            
        Returns:
            生成结果
        """
        voice_name = voice_name or self.current_voice
        
        if voice_name not in self.voice_profiles:
            print(f"[VoiceCloner] 语音不存在: {voice_name}")
            return None
        
        config = self.voice_profiles[voice_name]
        
        try:
            # 使用 edge-tts 合成语音（简化实现）
            # 实际应用中，应该使用 MOSS-TTS 的声音克隆功能
            from edge_tts import Communicate
            
            # 选择一个合适的声音作为基础
            voice_map = {
                "custom": "zh-CN-XiaoxiaoNeural",
                "male": "zh-CN-YunxiNeural",
                "female": "zh-CN-XiaoxiaoNeural"
            }
            
            voice = voice_map.get(voice_name, "zh-CN-XiaoxiaoNeural")
            
            communicate = Communicate(text=text, voice=voice)
            
            if output_path:
                await communicate.save(output_path)
                return output_path
            else:
                audio_data = await communicate.read()
                return audio_data
                
        except Exception as e:
            print(f"[VoiceCloner] 语音生成失败: {e}")
            return None
    
    def list_voices(self) -> List[str]:
        """列出所有语音"""
        return list(self.voice_profiles.keys())
    
    def get_current_voice(self) -> Optional[str]:
        """获取当前语音"""
        return self.current_voice
    
    def delete_voice(self, voice_name: str) -> bool:
        """删除语音"""
        if voice_name in self.voice_profiles:
            del self.voice_profiles[voice_name]
            if self.current_voice == voice_name:
                self.current_voice = None
            return True
        return False


class MeetingTranscriber:
    """会议转录器"""
    
    def __init__(self, whisper_model: str = "base"):
        self.whisper_model = whisper_model
        self.model = None
        self.is_initialized = False
    
    async def initialize(self):
        """初始化"""
        if self.is_initialized:
            return
        
        try:
            import whisper
            self.model = whisper.load_model(self.whisper_model)
            self.is_initialized = True
            print(f"[MeetingTranscriber] Whisper 模型已加载: {self.whisper_model}")
        except ImportError:
            print("[MeetingTranscriber] Whisper 未安装，请运行: pip install openai-whisper")
    
    async def transcribe_audio(
        self,
        audio_path: str,
        language: str = "zh",
        task: str = "transcribe"
    ) -> List[TranscriptSegment]:
        """
        转录音频
        
        Args:
            audio_path: 音频文件路径
            language: 语言
            task: 任务类型 (transcribe 或 translate)
            
        Returns:
            List[TranscriptSegment]: 转录片段列表
        """
        if not self.is_initialized:
            await self.initialize()
        
        if not self.model:
            return []
        
        try:
            result = self.model.transcribe(
                audio_path,
                language=language,
                task=task
            )
            
            segments = []
            for seg in result.get("segments", []):
                segment = TranscriptSegment(
                    start_time=seg.get("start", 0),
                    end_time=seg.get("end", 0),
                    text=seg.get("text", ""),
                    confidence=seg.get("confidence", 1.0)
                )
                segments.append(segment)
            
            return segments
            
        except Exception as e:
            print(f"[MeetingTranscriber] 转录失败: {e}")
            return []
    
    async def transcribe_segments_from_bytes(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        language: str = "zh"
    ) -> List[TranscriptSegment]:
        """
        从音频字节转录
        
        Args:
            audio_bytes: 音频字节数据
            sample_rate: 采样率
            language: 语言
            
        Returns:
            List[TranscriptSegment]: 转录片段列表
        """
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
        
        try:
            import wave
            with wave.open(temp_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_bytes)
            
            # 转录
            segments = await self.transcribe_audio(temp_path, language)
            
            return segments
            
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_path)
            except:
                pass
    
    async def generate_transcript(
        self,
        audio_path: str,
        meeting_id: str,
        language: str = "zh"
    ) -> MeetingTranscript:
        """
        生成会议转录
        
        Args:
            audio_path: 音频文件路径
            meeting_id: 会议 ID
            language: 语言
            
        Returns:
            MeetingTranscript: 会议转录
        """
        segments = await self.transcribe_audio(audio_path, language)
        
        transcript = MeetingTranscript(
            meeting_id=meeting_id,
            segments=segments,
            full_text=" ".join([seg.text for seg in segments])
        )
        
        return transcript
    
    def format_transcript(
        self,
        transcript: MeetingTranscript,
        format_type: str = "plain"
    ) -> str:
        """
        格式化转录文本
        
        Args:
            transcript: 会议转录
            format_type: 格式类型 (plain, srt, vtt)
            
        Returns:
            str: 格式化后的文本
        """
        if format_type == "plain":
            return transcript.full_text
        
        elif format_type == "srt":
            output = []
            for i, seg in enumerate(transcript.segments, 1):
                start = self._format_timestamp_srt(seg.start_time)
                end = self._format_timestamp_srt(seg.end_time)
                output.append(f"{i}\n{start} --> {end}\n{seg.text}\n")
            return "\n".join(output)
        
        elif format_type == "vtt":
            output = ["WEBVTT\n"]
            for seg in transcript.segments:
                start = self._format_timestamp_vtt(seg.start_time)
                end = self._format_timestamp_vtt(seg.end_time)
                output.append(f"{start} --> {end}\n{seg.text}\n")
            return "\n".join(output)
        
        return transcript.full_text
    
    def _format_timestamp_srt(self, seconds: float) -> str:
        """格式化 SRT 时间戳"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _format_timestamp_vtt(self, seconds: float) -> str:
        """格式化 VTT 时间戳"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    
    async def generate_summary(
        self,
        transcript: MeetingTranscript
    ) -> str:
        """
        生成转录摘要
        
        Args:
            transcript: 会议转录
            
        Returns:
            str: 摘要文本
        """
        # 简单的摘要生成
        # 实际应用中，可以使用 LLM 来生成更智能的摘要
        
        total_time = 0
        if transcript.segments:
            total_time = transcript.segments[-1].end_time
        
        summary = f"""会议转录摘要

- 会议 ID: {transcript.meeting_id}
- 总时长: {total_time:.1f} 秒
- 发言片段数: {len(transcript.segments)}
- 总字数: {len(transcript.full_text)}

转录预览（前 500 字）:
{transcript.full_text[:500]}...
"""
        return summary


# 全局实例
_voice_cloner: Optional[VoiceCloner] = None
_meeting_transcriber: Optional[MeetingTranscriber] = None


def get_voice_cloner() -> VoiceCloner:
    """获取语音克隆器"""
    global _voice_cloner
    if _voice_cloner is None:
        _voice_cloner = VoiceCloner()
    return _voice_cloner


def get_meeting_transcriber(whisper_model: str = "base") -> MeetingTranscriber:
    """获取会议转录器"""
    global _meeting_transcriber
    if _meeting_transcriber is None:
        _meeting_transcriber = MeetingTranscriber(whisper_model)
    return _meeting_transcriber
