"""
数字分身模块

实现用户语音克隆和数字分身管理
支持语音问答和会议参与
"""

import asyncio
import os
import uuid
import tempfile
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np


class TwinStatus(Enum):
    """分身状态"""
    IDLE = "idle"
    LISTENING = "listening"
    SPEAKING = "speaking"
    THINKING = "thinking"


@dataclass
class VoiceCloneProfile:
    """语音克隆配置"""
    profile_id: str
    name: str
    reference_audio_path: Optional[str] = None
    voice_id: Optional[str] = None
    language: str = "zh"
    created_at: float = 0
    is_default: bool = False


@dataclass
class DigitalTwin:
    """数字分身"""
    twin_id: str
    user_id: str
    name: str
    avatar_id: Optional[str] = None
    voice_profile: Optional[VoiceCloneProfile] = None
    status: TwinStatus = TwinStatus.IDLE
    current_text: str = ""
    is_active: bool = False
    llm_handler: Optional[Callable] = None


@dataclass
class QASession:
    """问答会话"""
    session_id: str
    twin_id: str
    user_id: str
    question: str = ""
    answer: str = ""
    audio_data: Optional[bytes] = None
    created_at: float = 0


class VoiceCloner:
    """语音克隆器"""

    def __init__(self):
        self.profiles: Dict[str, VoiceCloneProfile] = {}
        self._is_initialized = False

    async def initialize(self) -> bool:
        """初始化"""
        if self._is_initialized:
            return True

        try:
            from .moss_tts_clone import get_moss_tts_cloner
            self._moss_cloner = get_moss_tts_cloner()
            self._is_initialized = True
            return True
        except Exception as e:
            print(f"[VoiceCloner] 初始化失败: {e}")
            return False

    async def clone_from_audio(
        self,
        audio_path: str,
        name: str,
        language: str = "zh"
    ) -> Optional[VoiceCloneProfile]:
        """
        从音频克隆声音

        Args:
            audio_path: 参考音频路径
            name: 配置名称
            language: 语言

        Returns:
            Optional[VoiceCloneProfile]: 语音配置
        """
        if not os.path.exists(audio_path):
            print(f"[VoiceCloner] 音频文件不存在: {audio_path}")
            return None

        try:
            profile_id = str(uuid.uuid4())

            await self._moss_cloner.initialize()

            voice_id = await self._moss_cloner.clone_voice(
                reference_audio_path=audio_path,
                voice_name=name,
                language=language
            )

            profile = VoiceCloneProfile(
                profile_id=profile_id,
                name=name,
                reference_audio_path=audio_path,
                voice_id=voice_id,
                language=language
            )

            self.profiles[profile_id] = profile
            print(f"[VoiceCloner] 声音克隆成功: {name}")

            return profile

        except Exception as e:
            print(f"[VoiceCloner] 克隆失败: {e}")
            return None

    async def clone_from_recording(
        self,
        audio_data: bytes,
        name: str,
        sample_rate: int = 16000,
        language: str = "zh"
    ) -> Optional[VoiceCloneProfile]:
        """
        从录音克隆声音

        Args:
            audio_data: 音频数据
            name: 配置名称
            sample_rate: 采样率
            language: 语言

        Returns:
            Optional[VoiceCloneProfile]: 语音配置
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            import wave
            with wave.open(temp_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)

            return await self.clone_from_audio(temp_path, name, language)

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def create_profile(
        self,
        name: str,
        voice_id: str,
        language: str = "zh",
        reference_audio_path: Optional[str] = None
    ) -> VoiceCloneProfile:
        """
        创建语音配置（不使用克隆）

        Args:
            name: 配置名称
            voice_id: 语音 ID
            language: 语言
            reference_audio_path: 参考音频路径

        Returns:
            VoiceCloneProfile: 语音配置
        """
        profile_id = str(uuid.uuid4())

        profile = VoiceCloneProfile(
            profile_id=profile_id,
            name=name,
            voice_id=voice_id,
            language=language,
            reference_audio_path=reference_audio_path
        )

        self.profiles[profile_id] = profile
        return profile

    def get_profile(self, profile_id: str) -> Optional[VoiceCloneProfile]:
        """获取语音配置"""
        return self.profiles.get(profile_id)

    def list_profiles(self) -> List[VoiceCloneProfile]:
        """列出所有配置"""
        return list(self.profiles.values())

    def delete_profile(self, profile_id: str) -> bool:
        """删除配置"""
        if profile_id in self.profiles:
            del self.profiles[profile_id]
            return True
        return False


class DigitalTwinManager:
    """数字分身管理器"""

    def __init__(self):
        self.twins: Dict[str, DigitalTwin] = {}
        self.voice_cloner = VoiceCloner()
        self._is_initialized = False

    async def initialize(self) -> bool:
        """初始化"""
        if self._is_initialized:
            return True

        await self.voice_cloner.initialize()
        self._is_initialized = True
        return True

    async def create_twin(
        self,
        user_id: str,
        name: str,
        voice_profile: Optional[VoiceCloneProfile] = None,
        llm_handler: Optional[Callable] = None
    ) -> str:
        """
        创建数字分身

        Args:
            user_id: 用户 ID
            name: 分身名称
            voice_profile: 语音配置
            llm_handler: LLM 处理函数

        Returns:
            str: 分身 ID
        """
        await self.initialize()

        twin_id = str(uuid.uuid4())

        twin = DigitalTwin(
            twin_id=twin_id,
            user_id=user_id,
            name=name,
            voice_profile=voice_profile,
            llm_handler=llm_handler
        )

        self.twins[twin_id] = twin
        print(f"[TwinManager] 创建数字分身: {name} ({twin_id})")

        return twin_id

    async def create_twin_from_voice(
        self,
        user_id: str,
        name: str,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: str = "zh"
    ) -> Optional[str]:
        """
        从语音创建数字分身（克隆音色）

        Args:
            user_id: 用户 ID
            name: 分身名称
            audio_data: 音频数据
            sample_rate: 采样率
            language: 语言

        Returns:
            Optional[str]: 分身 ID
        """
        voice_profile = await self.voice_cloner.clone_from_recording(
            audio_data=audio_data,
            name=name,
            sample_rate=sample_rate,
            language=language
        )

        if not voice_profile:
            return None

        return await self.create_twin(
            user_id=user_id,
            name=name,
            voice_profile=voice_profile
        )

    def get_twin(self, twin_id: str) -> Optional[DigitalTwin]:
        """获取分身"""
        return self.twins.get(twin_id)

    def get_user_twins(self, user_id: str) -> List[DigitalTwin]:
        """获取用户的所有分身"""
        return [t for t in self.twins.values() if t.user_id == user_id]

    def list_twins(self) -> List[DigitalTwin]:
        """列出所有分身"""
        return list(self.twins.values())

    async def activate_twin(self, twin_id: str) -> bool:
        """激活分身"""
        twin = self.get_twin(twin_id)
        if not twin:
            return False

        twin.is_active = True
        twin.status = TwinStatus.IDLE
        print(f"[TwinManager] 激活分身: {twin.name}")
        return True

    async def deactivate_twin(self, twin_id: str) -> bool:
        """停用分身"""
        twin = self.get_twin(twin_id)
        if not twin:
            return False

        twin.is_active = False
        twin.status = TwinStatus.IDLE
        print(f"[TwinManager] 停用分身: {twin.name}")
        return True

    def set_twin_voice(self, twin_id: str, voice_profile: VoiceCloneProfile) -> bool:
        """设置分身语音"""
        twin = self.get_twin(twin_id)
        if not twin:
            return False

        twin.voice_profile = voice_profile
        return True

    def delete_twin(self, twin_id: str) -> bool:
        """删除分身"""
        if twin_id in self.twins:
            del self.twins[twin_id]
            return True
        return False


class TwinQAHandler:
    """数字分身问答处理器"""

    def __init__(self, twin_manager: DigitalTwinManager):
        self.twin_manager = twin_manager
        self.sessions: Dict[str, QASession] = {}
        self._tts_handler: Optional[Callable] = None
        self._stt_handler: Optional[Callable] = None

    def set_handlers(
        self,
        tts_handler: Callable,
        stt_handler: Callable
    ):
        """设置 TTS/STT 处理函数"""
        self._tts_handler = tts_handler
        self._stt_handler = stt_handler

    async def process_voice_question(
        self,
        twin_id: str,
        audio_data: bytes,
        sample_rate: int = 16000
    ) -> Optional[bytes]:
        """
        处理语音提问

        Args:
            twin_id: 分身 ID
            audio_data: 音频数据
            sample_rate: 采样率

        Returns:
            Optional[bytes]: 回答音频数据
        """
        twin = self.twin_manager.get_twin(twin_id)
        if not twin:
            return None

        twin.status = TwinStatus.THINKING

        try:
            if self._stt_handler:
                question = await self._stt_handler(audio_data, sample_rate)
            else:
                question = "请问有什么可以帮助您的？"

            twin.current_text = question

            if twin.llm_handler:
                answer = await twin.llm_handler(question)
            else:
                answer = f"这是一个测试回复。您的问题是：{question[:20]}..."

            twin.current_text = answer
            twin.status = TwinStatus.SPEAKING

            if self._tts_handler and twin.voice_profile:
                audio_answer = await self._tts_handler(
                    text=answer,
                    voice_id=twin.voice_profile.voice_id
                )
            else:
                audio_answer = None

            twin.status = TwinStatus.IDLE
            return audio_answer

        except Exception as e:
            print(f"[TwinQA] 处理失败: {e}")
            twin.status = TwinStatus.IDLE
            return None

    async def process_text_question(
        self,
        twin_id: str,
        question: str
    ) -> Optional[str]:
        """
        处理文本提问

        Args:
            twin_id: 分身 ID
            question: 问题

        Returns:
            Optional[str]: 回答文本
        """
        twin = self.twin_manager.get_twin(twin_id)
        if not twin:
            return None

        twin.status = TwinStatus.THINKING
        twin.current_text = question

        try:
            if twin.llm_handler:
                answer = await twin.llm_handler(question)
            else:
                answer = f"这是一个测试回复。您的问题是：{question}"

            twin.current_text = answer
            twin.status = TwinStatus.IDLE

            return answer

        except Exception as e:
            print(f"[TwinQA] 处理失败: {e}")
            twin.status = TwinStatus.IDLE
            return None


class TwinConferenceBridge:
    """数字分身会议桥接器"""

    def __init__(self, twin_manager: DigitalTwinManager):
        self.twin_manager = twin_manager
        self._conference_handler: Optional[Any] = None

    def set_conference_handler(self, handler: Any):
        """设置会议处理器"""
        self._conference_handler = handler

    async def twin_join_meeting(
        self,
        twin_id: str,
        meeting_id: str,
        role: str = "participant"
    ) -> bool:
        """
        分身加入会议

        Args:
            twin_id: 分身 ID
            meeting_id: 会议 ID
            role: 角色

        Returns:
            bool: 是否成功
        """
        twin = self.twin_manager.get_twin(twin_id)
        if not twin:
            return False

        await self.twin_manager.activate_twin(twin_id)

        if self._conference_handler:
            try:
                await self._conference_handler.add_twin_to_meeting(twin, meeting_id, role)
                return True
            except Exception as e:
                print(f"[TwinConference] 加入会议失败: {e}")
                return False

        return True

    async def twin_leave_meeting(
        self,
        twin_id: str,
        meeting_id: str
    ) -> bool:
        """
        分身离开会议

        Args:
            twin_id: 分身 ID
            meeting_id: 会议 ID

        Returns:
            bool: 是否成功
        """
        twin = self.twin_manager.get_twin(twin_id)
        if not twin:
            return False

        await self.twin_manager.deactivate_twin(twin_id)

        if self._conference_handler:
            try:
                await self._conference_handler.remove_twin_from_meeting(twin_id, meeting_id)
            except:
                pass

        return True

    async def twin_speak_in_meeting(
        self,
        twin_id: str,
        text: str
    ) -> Optional[bytes]:
        """
        分身在会议中发言

        Args:
            twin_id: 分身 ID
            text: 发言内容

        Returns:
            Optional[bytes]: 语音数据
        """
        twin = self.twin_manager.get_twin(twin_id)
        if not twin or not twin.is_active:
            return None

        twin.status = TwinStatus.SPEAKING
        twin.current_text = text

        audio_data = None
        if twin.voice_profile and self._conference_handler:
            try:
                from .moss_tts_clone import get_moss_tts_cloner
                cloner = get_moss_tts_cloner()
                audio_data = await cloner.synthesize(
                    text=text,
                    voice_id=twin.voice_profile.voice_id
                )
            except Exception as e:
                print(f"[TwinConference] 语音合成失败: {e}")

        twin.status = TwinStatus.IDLE
        return audio_data


_global_twin_manager: Optional[DigitalTwinManager] = None


def get_twin_manager() -> DigitalTwinManager:
    """获取数字分身管理器"""
    global _global_twin_manager
    if _global_twin_manager is None:
        _global_twin_manager = DigitalTwinManager()
    return _global_twin_manager


_global_qa_handler: Optional[TwinQAHandler] = None


def get_qa_handler() -> TwinQAHandler:
    """获取问答处理器"""
    global _global_qa_handler
    if _global_qa_handler is None:
        _global_qa_handler = TwinQAHandler(get_twin_manager())
    return _global_qa_handler


_global_conference_bridge: Optional[TwinConferenceBridge] = None


def get_conference_bridge() -> TwinConferenceBridge:
    """获取会议桥接器"""
    global _global_conference_bridge
    if _global_conference_bridge is None:
        _global_conference_bridge = TwinConferenceBridge(get_twin_manager())
    return _global_conference_bridge
