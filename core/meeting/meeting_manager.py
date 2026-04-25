"""
Meeting Manager - 会议管理器

统一管理会议全流程：
1. 会议录制
2. 语音转录
3. 说话人识别
4. AI 摘要生成
5. 导出与分享
"""

import os
import json
import shutil
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from enum import Enum
from pathlib import Path

from .transcriber import TranscriptionResult, TranscriptionSegment
from .summarizer import SummaryResult, MeetingSummarizer, SummaryTemplate
from .diarization import DiarizationResult, SpeakerDiarization
from .recorder import AudioRecorder, RecordingConfig


def _get_api_key(provider: str) -> str:
    """获取 API Key（兼容统一配置）"""
    try:
        from core.config.unified_config import get_config
        key = get_config().get_api_key(provider)
        if key:
            return key
    except Exception:
        pass
    return os.environ.get(f"{provider.upper()}_API_KEY", "")


class MeetingStatus(Enum):
    """会议状态"""
    IDLE = "idle"               # 空闲
    RECORDING = "recording"      # 录制中
    TRANSCRIBING = "transcribing"  # 转录中
    SUMMARIZING = "summarizing"   # 生成摘要中
    COMPLETED = "completed"       # 完成
    FAILED = "failed"            # 失败


class ExportFormat(Enum):
    """导出格式"""
    MARKDOWN = "markdown"
    PDF = "pdf"
    DOCX = "docx"
    JSON = "json"
    TXT = "txt"
    SRT = "srt"                 # 字幕格式


@dataclass
class Meeting:
    """会议数据"""
    meeting_id: str
    title: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    duration: float = 0.0        # 时长（秒）

    # 文件路径
    audio_path: Optional[str] = None
    transcription_path: Optional[str] = None
    summary_path: Optional[str] = None

    # 结果数据
    transcription: Optional[TranscriptionResult] = None
    diarization: Optional[DiarizationResult] = None
    summary: Optional[SummaryResult] = None

    # 元数据
    participants: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    status: MeetingStatus = MeetingStatus.IDLE
    error_message: Optional[str] = None

    # 配置
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "meeting_id": self.meeting_id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "duration": self.duration,
            "audio_path": self.audio_path,
            "transcription_path": self.transcription_path,
            "summary_path": self.summary_path,
            "participants": self.participants,
            "tags": self.tags,
            "status": self.status.value,
            "error_message": self.error_message,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Meeting":
        """从字典创建"""
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        data["status"] = MeetingStatus(data["status"])
        return cls(**data)


class MeetingManager:
    """
    会议管理器

    核心功能：
    1. 创建和管理会议
    2. 录制音频
    3. 转录
    4. 说话人识别
    5. 生成摘要
    6. 导出会议记录
    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        transcription_model: str = "base",
        summarizer_provider: str = "ollama",
        summarizer_model: str = "llama3.2",
        diarization_num_speakers: int = 2
    ):
        """
        初始化会议管理器

        Args:
            storage_dir: 会议文件存储目录
            transcription_model: 转录模型大小
            summarizer_provider: 摘要生成提供商
            summarizer_model: 摘要模型
            diarization_num_speakers: 预估说话人数量
        """
        self.storage_dir = storage_dir or os.path.join(
            os.path.expanduser("~"),
            ".workbuddy",
            "meetings"
        )
        os.makedirs(self.storage_dir, exist_ok=True)

        # 创建子目录
        self.audio_dir = os.path.join(self.storage_dir, "audio")
        self.transcription_dir = os.path.join(self.storage_dir, "transcriptions")
        self.summary_dir = os.path.join(self.storage_dir, "summaries")

        for d in [self.audio_dir, self.transcription_dir, self.summary_dir]:
            os.makedirs(d, exist_ok=True)

        # 初始化组件
        self.transcription_model = transcription_model
        self.diarization_num_speakers = diarization_num_speakers

        # 初始化摘要生成器
        self._init_summarizer(summarizer_provider, summarizer_model)

        # 会议记录
        self._meetings: Dict[str, Meeting] = {}
        self._current_meeting: Optional[Meeting] = None
        self._recorder: Optional[AudioRecorder] = None

        # 回调
        self._callbacks: Dict[str, List[Callable]] = {
            "status_changed": [],
            "progress": [],
            "completed": [],
        }

    def _init_summarizer(self, provider: str, model: str):
        """初始化摘要生成器"""
        try:
            if provider == "ollama":
                self.summarizer = MeetingSummarizer.create_ollama(model=model)
            elif provider == "groq":
                api_key = _get_api_key("groq")
                self.summarizer = MeetingSummarizer.create_groq(api_key=api_key, model=model)
            elif provider == "openrouter":
                api_key = _get_api_key("openrouter")
                self.summarizer = MeetingSummarizer.create_openrouter(api_key=api_key, model=model)
            else:
                self.summarizer = MeetingSummarizer.create_ollama(model=model)
        except Exception as e:
            print(f"警告: 初始化摘要生成器失败: {e}")
            self.summarizer = None

    def create_meeting(
        self,
        title: str,
        participants: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        **config
    ) -> Meeting:
        """
        创建会议

        Args:
            title: 会议标题
            participants: 参与者列表
            tags: 标签
            **config: 其他配置

        Returns:
            Meeting: 创建的会议
        """
        import uuid
        meeting_id = uuid.uuid4().hex[:12]

        meeting = Meeting(
            meeting_id=meeting_id,
            title=title,
            participants=participants or [],
            tags=tags or [],
            config=config,
        )

        self._meetings[meeting_id] = meeting
        self._current_meeting = meeting

        # 保存会议元数据
        self._save_meeting_metadata(meeting)

        return meeting

    def start_recording(
        self,
        meeting_id: Optional[str] = None,
        audio_source: str = "default",
        include_system_audio: bool = False
    ) -> bool:
        """
        开始录制

        Args:
            meeting_id: 会议 ID（如果不指定则使用当前会议）
            audio_source: 音频源
            include_system_audio: 是否包含系统音频

        Returns:
            bool: 是否成功
        """
        meeting = self._get_meeting(meeting_id)
        if not meeting:
            return False

        # 创建录音器
        config = RecordingConfig(
            audio_source=audio_source,
            include_system_audio=include_system_audio,
            output_dir=self.audio_dir,
        )
        self._recorder = AudioRecorder(config)

        # 开始录制
        audio_path = self._recorder.start(meeting.meeting_id)
        if audio_path:
            meeting.audio_path = audio_path
            meeting.status = MeetingStatus.RECORDING
            self._notify_status_changed(meeting)
            return True

        return False

    def stop_recording(self, meeting_id: Optional[str] = None) -> Optional[str]:
        """
        停止录制

        Args:
            meeting_id: 会议 ID

        Returns:
            音频文件路径
        """
        meeting = self._get_meeting(meeting_id)
        if not meeting or not self._recorder:
            return None

        audio_path = self._recorder.stop()
        meeting.audio_path = audio_path
        meeting.status = MeetingStatus.IDLE

        return audio_path

    def transcribe_meeting(
        self,
        meeting_id: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Optional[TranscriptionResult]:
        """
        转录会议

        Args:
            meeting_id: 会议 ID
            progress_callback: 进度回调

        Returns:
            TranscriptionResult: 转录结果
        """
        meeting = self._get_meeting(meeting_id)
        if not meeting or not meeting.audio_path:
            return None

        meeting.status = MeetingStatus.TRANSCRIBING
        self._notify_status_changed(meeting)

        try:
            from .transcriber import quick_transcribe

            # 执行转录
            result = quick_transcribe(
                audio_path=meeting.audio_path,
                model=self.transcription_model,
            )
            result.meeting_id = meeting.meeting_id

            meeting.transcription = result
            meeting.transcription_path = os.path.join(
                self.transcription_dir,
                f"{meeting.meeting_id}.json"
            )

            # 保存转录结果
            with open(meeting.transcription_path, "w", encoding="utf-8") as f:
                f.write(result.to_json())

            meeting.status = MeetingStatus.IDLE
            self._notify_status_changed(meeting)

            return result

        except Exception as e:
            meeting.status = MeetingStatus.FAILED
            meeting.error_message = str(e)
            return None

    def diarize_speakers(
        self,
        meeting_id: Optional[str] = None
    ) -> Optional[DiarizationResult]:
        """
        执行说话人识别

        Args:
            meeting_id: 会议 ID

        Returns:
            DiarizationResult: 说话人识别结果
        """
        meeting = self._get_meeting(meeting_id)
        if not meeting or not meeting.audio_path:
            return None

        try:
            diarizer = SpeakerDiarization(num_speakers=self.diarization_num_speakers)
            result = diarizer.diarize(meeting.audio_path)
            result.meeting_id = meeting.meeting_id

            meeting.diarization = result

            # 合并说话人到转录
            if meeting.transcription:
                meeting.transcription.segments = diarizer.merge_with_transcription(
                    result,
                    meeting.transcription.segments
                )

            return result

        except Exception as e:
            meeting.error_message = str(e)
            return None

    def summarize_meeting(
        self,
        meeting_id: Optional[str] = None,
        template: SummaryTemplate = SummaryTemplate.STANDARD,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Optional[SummaryResult]:
        """
        生成会议摘要

        Args:
            meeting_id: 会议 ID
            template: 摘要模板
            progress_callback: 进度回调

        Returns:
            SummaryResult: 摘要结果
        """
        meeting = self._get_meeting(meeting_id)
        if not meeting or not meeting.transcription:
            return None

        if not self.summarizer:
            raise RuntimeError("摘要生成器未初始化")

        meeting.status = MeetingStatus.SUMMARIZING
        self._notify_status_changed(meeting)

        try:
            result = self.summarizer.summarize(
                transcription=meeting.transcription,
                template=template
            )
            result.meeting_id = meeting.meeting_id

            meeting.summary = result
            meeting.summary_path = os.path.join(
                self.summary_dir,
                f"{meeting.meeting_id}.md"
            )

            # 保存摘要
            with open(meeting.summary_path, "w", encoding="utf-8") as f:
                f.write(result.to_markdown())

            meeting.status = MeetingStatus.COMPLETED
            self._notify_status_changed(meeting)

            return result

        except Exception as e:
            meeting.status = MeetingStatus.FAILED
            meeting.error_message = str(e)
            return None

    def process_full_pipeline(
        self,
        meeting_id: Optional[str] = None,
        include_diarization: bool = True,
        include_summary: bool = True,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Optional[Meeting]:
        """
        执行完整处理流程

        Args:
            meeting_id: 会议 ID
            include_diarization: 是否包含说话人识别
            include_summary: 是否生成摘要
            progress_callback: 进度回调 (stage, progress)

        Returns:
            Meeting: 处理完成的会议
        """
        meeting = self._get_meeting(meeting_id)
        if not meeting:
            return None

        # 1. 转录
        if progress_callback:
            progress_callback("transcribing", 0)
        self.transcribe_meeting(meeting_id)
        if progress_callback:
            progress_callback("transcribing", 1.0)

        # 2. 说话人识别
        if include_diarization:
            if progress_callback:
                progress_callback("diarizing", 0)
            self.diarize_speakers(meeting_id)
            if progress_callback:
                progress_callback("diarizing", 1.0)

        # 3. 摘要生成
        if include_summary and self.summarizer:
            if progress_callback:
                progress_callback("summarizing", 0)
            self.summarize_meeting(meeting_id)
            if progress_callback:
                progress_callback("summarizing", 1.0)

        meeting.status = MeetingStatus.COMPLETED
        meeting.updated_at = datetime.now()
        self._notify_completed(meeting)

        return meeting

    def export_meeting(
        self,
        meeting_id: str,
        export_dir: Optional[str] = None,
        formats: Optional[List[ExportFormat]] = None
    ) -> Dict[str, str]:
        """
        导出会议记录

        Args:
            meeting_id: 会议 ID
            export_dir: 导出目录
            formats: 导出格式列表

        Returns:
            {format: file_path} 导出文件路径
        """
        meeting = self._get_meeting(meeting_id)
        if not meeting:
            return {}

        formats = formats or [ExportFormat.MARKDOWN, ExportFormat.JSON]
        export_dir = export_dir or os.path.join(self.storage_dir, "exports")
        os.makedirs(export_dir, exist_ok=True)

        exported = {}
        base_name = f"{meeting.title}_{meeting.meeting_id}"

        for fmt in formats:
            try:
                if fmt == ExportFormat.MARKDOWN:
                    path = self._export_markdown(meeting, export_dir, base_name)
                elif fmt == ExportFormat.JSON:
                    path = self._export_json(meeting, export_dir, base_name)
                elif fmt == ExportFormat.TXT:
                    path = self._export_txt(meeting, export_dir, base_name)
                elif fmt == ExportFormat.SRT:
                    path = self._export_srt(meeting, export_dir, base_name)
                else:
                    continue

                exported[fmt.value] = path

            except Exception as e:
                print(f"导出 {fmt} 失败: {e}")

        return exported

    def _export_markdown(self, meeting: Meeting, export_dir: str, base_name: str) -> str:
        """导出 Markdown"""
        lines = [
            f"# {meeting.title}",
            "",
            f"**日期**: {meeting.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"**时长**: {meeting.duration / 60:.1f} 分钟",
            "",
        ]

        if meeting.participants:
            lines.append(f"**参与者**: {', '.join(meeting.participants)}")
            lines.append("")

        lines.append("---")
        lines.append("")

        # 转录内容
        if meeting.transcription:
            lines.append("## 转录记录")
            lines.append("")

            for seg in meeting.transcription.segments:
                speaker = f"**[{seg.speaker}]** " if seg.speaker else ""
                time = f"[{self._format_time(seg.start_time)}] "
                lines.append(f"{time}{speaker}{seg.text}")

            lines.append("")

        # 摘要
        if meeting.summary:
            lines.append("## 摘要")
            lines.append("")
            lines.append(meeting.summary.to_markdown())

        path = os.path.join(export_dir, f"{base_name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return path

    def _export_json(self, meeting: Meeting, export_dir: str, base_name: str) -> str:
        """导出 JSON"""
        data = meeting.to_dict()

        if meeting.transcription:
            data["transcription"] = {
                "full_text": meeting.transcription.full_text,
                "language": meeting.transcription.language,
                "segments": [
                    {
                        "start": s.start_time,
                        "end": s.end_time,
                        "text": s.text,
                        "speaker": s.speaker,
                    }
                    for s in meeting.transcription.segments
                ],
            }

        if meeting.summary:
            data["summary"] = {
                "title": meeting.summary.title,
                "summary": meeting.summary.summary,
                "key_points": meeting.summary.key_points,
                "action_items": [
                    {
                        "task": a.task,
                        "assignee": a.assignee,
                        "deadline": a.deadline,
                    }
                    for a in meeting.summary.action_items
                ],
            }

        path = os.path.join(export_dir, f"{base_name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return path

    def _export_txt(self, meeting: Meeting, export_dir: str, base_name: str) -> str:
        """导出 TXT"""
        lines = [
            meeting.title,
            "=" * len(meeting.title),
            "",
            f"日期: {meeting.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"时长: {meeting.duration / 60:.1f} 分钟",
            "",
        ]

        if meeting.transcription:
            lines.append("-" * 40)
            lines.append("转录记录")
            lines.append("-" * 40)
            for seg in meeting.transcription.segments:
                lines.append(seg.text)

        path = os.path.join(export_dir, f"{base_name}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return path

    def _export_srt(self, meeting: Meeting, export_dir: str, base_name: str) -> str:
        """导出 SRT 字幕"""
        if not meeting.transcription:
            raise ValueError("没有转录数据")

        path = os.path.join(export_dir, f"{base_name}.srt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(meeting.transcription.to_srt())

        return path

    def _format_time(self, seconds: float) -> str:
        """格式化时间"""
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def _get_meeting(self, meeting_id: Optional[str]) -> Optional[Meeting]:
        """获取会议"""
        if meeting_id:
            return self._meetings.get(meeting_id)
        return self._current_meeting

    def _save_meeting_metadata(self, meeting: Meeting):
        """保存会议元数据"""
        metadata_path = os.path.join(self.storage_dir, "meetings.json")

        # 读取现有数据
        meetings_data = {}
        if os.path.exists(metadata_path):
            with open(metadata_path, "r", encoding="utf-8") as f:
                meetings_data = json.load(f)

        # 更新
        meetings_data[meeting.meeting_id] = meeting.to_dict()

        # 写入
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(meetings_data, f, ensure_ascii=False, indent=2)

    def _notify_status_changed(self, meeting: Meeting):
        """通知状态变更"""
        for callback in self._callbacks["status_changed"]:
            try:
                callback(meeting)
            except Exception as e:
                print(f"Callback error: {e}")

    def _notify_completed(self, meeting: Meeting):
        """通知完成"""
        for callback in self._callbacks["completed"]:
            try:
                callback(meeting)
            except Exception as e:
                print(f"Callback error: {e}")

    def register_callback(
        self,
        event: str,
        callback: Callable
    ):
        """注册回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    # ========== 便捷方法 ==========

    def quick_record(
        self,
        title: str,
        duration_seconds: int = 0
    ) -> Meeting:
        """
        快速录制会议

        Args:
            title: 会议标题
            duration_seconds: 录制时长（0 表示手动停止）

        Returns:
            Meeting: 创建的会议
        """
        meeting = self.create_meeting(title=title)
        self.start_recording(meeting.meeting_id)

        if duration_seconds > 0:
            import time
            time.sleep(duration_seconds)
            self.stop_recording(meeting.meeting_id)

        return meeting

    def get_all_meetings(self) -> List[Meeting]:
        """获取所有会议"""
        return list(self._meetings.values())

    def get_meeting(self, meeting_id: str) -> Optional[Meeting]:
        """获取会议"""
        return self._meetings.get(meeting_id)

    def delete_meeting(self, meeting_id: str) -> bool:
        """删除会议"""
        meeting = self._meetings.get(meeting_id)
        if not meeting:
            return False

        # 删除文件
        for path in [meeting.audio_path, meeting.transcription_path, meeting.summary_path]:
            if path and os.path.exists(path):
                os.remove(path)

        # 删除记录
        del self._meetings[meeting_id]
        self._save_meeting_metadata(meeting)

        return True
