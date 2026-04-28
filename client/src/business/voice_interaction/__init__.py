"""
语音交互模块

支持语音输入和输出：
1. 语音识别（SpeechRecognition）
   - Whisper / Deepgram / Google
   - 实时监听
   - 多种语言支持

2. 语音合成（SpeechSynthesis）
   - ElevenLabs / edge-tts / Google
   - 多种语音选择
   - 直接播放支持

可集成到 PyQt6 桌面应用中。
"""

from .speech_recognition import (
    SpeechRecognition,
    RecognitionEngine,
    RecognitionResult
)

from .speech_synthesis import (
    SpeechSynthesis,
    SynthesisEngine,
    SynthesisResult,
    VoiceGender
)

__all__ = [
    # 语音识别
    "SpeechRecognition",
    "RecognitionEngine",
    "RecognitionResult",
    
    # 语音合成
    "SpeechSynthesis",
    "SynthesisEngine",
    "SynthesisResult",
    "VoiceGender"
]