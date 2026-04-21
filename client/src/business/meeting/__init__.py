"""
Meeting System - 智能会议系统 🎙️

基于 Meetily 理念设计的隐私优先 AI 会议助手：
- 本地语音转录（Whisper/Parakeet）
- 多 AI 提供商摘要生成（Ollama/Groq/Claude）
- 说话人识别（Diarization）
- 会议录制与导出

核心理念：
1. 隐私优先 - 所有数据本地处理
2. 灵活部署 - 支持本地/云端 AI
3. 多格式导出 - PDF/DOCX/TXT/JSON
"""

from .transcriber import TranscriptionEngine, TranscriptionResult
from .summarizer import MeetingSummarizer, SummaryResult
from .diarization import SpeakerDiarization, SpeakerSegment
from .meeting_manager import Meeting, MeetingManager
from .recorder import AudioRecorder, RecordingConfig

__all__ = [
    # 转录引擎
    "TranscriptionEngine",
    "TranscriptionResult",

    # 摘要生成
    "MeetingSummarizer",
    "SummaryResult",

    # 说话人识别
    "SpeakerDiarization",
    "SpeakerSegment",

    # 会议管理
    "Meeting",
    "MeetingManager",

    # 录音
    "AudioRecorder",
    "RecordingConfig",
]


# 支持的 AI 提供商
class AIProvider:
    """AI 提供商枚举"""
    OLLAMA = "ollama"           # 本地推荐
    GROQ = "groq"              # 实时推理
    OPENROUTER = "openrouter"   # 多模型聚合
    OPENAI = "openai"          # OpenAI API
    CLAUDE = "claude"          # Anthropic Claude
    CUSTOM = "custom"          # 自定义端点


# 支持的转录模型
class TranscriptionModel:
    """转录模型枚举"""
    WHISPER_BASE = "whisper-base"
    WHISPER_LARGE = "whisper-large"
    PARAKEET = "parakeet"      # NVIDIA 高精度


# 全局单例
_manager_instance = None


def get_meeting_manager() -> 'MeetingManager':
    """获取会议管理器单例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MeetingManager()
    return _manager_instance
