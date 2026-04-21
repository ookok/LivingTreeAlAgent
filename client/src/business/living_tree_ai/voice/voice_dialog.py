"""
实时语音对话系统

实现用户与 Agent 的实时语音对话
"""

import asyncio
import json
import uuid
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import wave
import pyaudio
import numpy as np


class AudioFormat(Enum):
    """音频格式"""
    PCM_16BIT = 16
    SAMPLE_RATE = 16000
    CHANNELS = 1


@dataclass
class AudioChunk:
    """音频块"""
    data: bytes
    is_final: bool = False
    timestamp: float = 0


@dataclass
class Message:
    """对话消息"""
    id: str
    role: str  # user, assistant, system
    content: str
    audio_data: Optional[bytes] = None
    timestamp: float = 0


@dataclass
class ConversationContext:
    """对话上下文"""
    session_id: str
    messages: List[Message] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AudioDevice:
    """音频设备管理"""
    
    def __init__(self):
        self._pyaudio = None
        self._stream = None
        self._is_recording = False
        self._is_playing = False
    
    def _ensure_pyaudio(self):
        """确保 PyAudio 已初始化"""
        if self._pyaudio is None:
            try:
                self._pyaudio = pyaudio.PyAudio()
            except ImportError:
                print("PyAudio 未安装，请运行: pip install pyaudio")
                raise
    
    def start_recording(
        self,
        callback: Callable[[bytes], None],
        sample_rate: int = AudioFormat.SAMPLE_RATE.value,
        channels: int = AudioFormat.CHANNELS.value
    ):
        """
        开始录制
        
        Args:
            callback: 音频数据回调函数
            sample_rate: 采样率
            channels: 通道数
        """
        self._ensure_pyaudio()
        
        def _record_callback(in_data, frame_count, time_info, status):
            callback(in_data)
            return (in_data, pyaudio.paContinue)
        
        self._stream = self._pyaudio.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=sample_rate,
            input=True,
            stream_callback=_record_callback
        )
        
        self._is_recording = True
        self._stream.start_stream()
    
    def stop_recording(self):
        """停止录制"""
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        
        self._is_recording = False
    
    def play_audio(
        self,
        audio_data: bytes,
        sample_rate: int = AudioFormat.SAMPLE_RATE.value,
        channels: int = AudioFormat.CHANNELS.value
    ):
        """
        播放音频
        
        Args:
            audio_data: 音频数据
            sample_rate: 采样率
            channels: 通道数
        """
        self._ensure_pyaudio()
        
        # 写入临时文件
        import tempfile
        import os
        
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path = temp_file.name
        
        with wave.open(temp_path, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data)
        
        # 播放
        self._play_file(temp_path)
        
        # 清理
        try:
            os.unlink(temp_path)
        except:
            pass
    
    def _play_file(self, file_path: str):
        """播放音频文件"""
        self._ensure_pyaudio()
        
        with wave.open(file_path, 'rb') as wf:
            stream = self._pyaudio.open(
                format=self._pyaudio.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )
            
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
            
            stream.close()
    
    def is_recording(self) -> bool:
        """是否正在录制"""
        return self._is_recording
    
    def is_playing(self) -> bool:
        """是否正在播放"""
        return self._is_playing
    
    def close(self):
        """关闭音频设备"""
        self.stop_recording()
        
        if self._pyaudio:
            self._pyaudio.terminate()
            self._pyaudio = None


class VoiceDialogSystem:
    """语音对话系统"""
    
    def __init__(self):
        self.sessions: Dict[str, ConversationContext] = {}
        self.audio_device = AudioDevice()
        self.tts_adapter = None
        self.stt_adapter = None
        self.agent_handler: Optional[Callable] = None
        self._running = False
    
    def set_tts_adapter(self, adapter):
        """设置 TTS 适配器"""
        self.tts_adapter = adapter
    
    def set_stt_adapter(self, adapter):
        """设置 STT 适配器"""
        self.stt_adapter = adapter
    
    def set_agent_handler(self, handler: Callable):
        """
        设置 Agent 处理函数
        
        Args:
            handler: Agent 处理函数，接收 (session_id, user_text) 返回 assistant_text
        """
        self.agent_handler = handler
    
    def create_session(self, session_id: Optional[str] = None) -> str:
        """
        创建对话会话
        
        Args:
            session_id: 会话 ID（可选）
            
        Returns:
            str: 会话 ID
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        self.sessions[session_id] = ConversationContext(
            session_id=session_id
        )
        
        return session_id
    
    def close_session(self, session_id: str):
        """
        关闭对话会话
        
        Args:
            session_id: 会话 ID
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    async def process_voice_input(
        self,
        session_id: str,
        audio_data: bytes
    ) -> Optional[str]:
        """
        处理语音输入
        
        Args:
            session_id: 会话 ID
            audio_data: 音频数据
            
        Returns:
            Optional[str]: 助手回复文本
        """
        if session_id not in self.sessions:
            return None
        
        # 语音转文本
        if self.stt_adapter:
            stt_result = await self.stt_adapter.speech_to_text_bytes(audio_data)
            if not stt_result.success:
                return None
            
            user_text = stt_result.text
        else:
            return None
        
        # 添加用户消息
        context = self.sessions[session_id]
        context.messages.append(Message(
            id=str(uuid.uuid4()),
            role="user",
            content=user_text
        ))
        
        # 调用 Agent
        if self.agent_handler:
            assistant_text = await self.agent_handler(session_id, user_text)
        else:
            assistant_text = "抱歉，Agent 处理函数未设置"
        
        # 添加助手消息
        context.messages.append(Message(
            id=str(uuid.uuid4()),
            role="assistant",
            content=assistant_text
        ))
        
        return assistant_text
    
    async def process_text_input(
        self,
        session_id: str,
        user_text: str
    ) -> Optional[str]:
        """
        处理文本输入
        
        Args:
            session_id: 会话 ID
            user_text: 用户文本
            
        Returns:
            Optional[str]: 助手回复文本
        """
        if session_id not in self.sessions:
            return None
        
        # 添加用户消息
        context = self.sessions[session_id]
        context.messages.append(Message(
            id=str(uuid.uuid4()),
            role="user",
            content=user_text
        ))
        
        # 调用 Agent
        if self.agent_handler:
            assistant_text = await self.agent_handler(session_id, user_text)
        else:
            assistant_text = "抱歉，Agent 处理函数未设置"
        
        # 添加助手消息
        context.messages.append(Message(
            id=str(uuid.uuid4()),
            role="assistant",
            content=assistant_text
        ))
        
        return assistant_text
    
    async def text_to_speech(self, text: str) -> Optional[bytes]:
        """
        文本转语音
        
        Args:
            text: 要转换的文本
            
        Returns:
            Optional[bytes]: 音频数据
        """
        if self.tts_adapter:
            result = await self.tts_adapter.text_to_speech(text)
            if result.success:
                return result.audio_data
        return None
    
    def get_session_history(self, session_id: str) -> List[Message]:
        """
        获取会话历史
        
        Args:
            session_id: 会话 ID
            
        Returns:
            List[Message]: 消息列表
        """
        if session_id in self.sessions:
            return self.sessions[session_id].messages
        return []
    
    def clear_session_history(self, session_id: str):
        """
        清除会话历史
        
        Args:
            session_id: 会话 ID
        """
        if session_id in self.sessions:
            self.sessions[session_id].messages.clear()


class VoiceConferenceSystem:
    """语音会议系统"""
    
    def __init__(self):
        self.rooms: Dict[str, "ConferenceRoom"] = {}
        self.participants: Dict[str, str] = {}  # participant_id -> room_id
    
    def create_room(self, room_id: str, max_participants: int = 10) -> bool:
        """
        创建会议房间
        
        Args:
            room_id: 房间 ID
            max_participants: 最大参与人数
            
        Returns:
            bool: 是否创建成功
        """
        if room_id in self.rooms:
            return False
        
        self.rooms[room_id] = ConferenceRoom(
            room_id=room_id,
            max_participants=max_participants
        )
        return True
    
    def close_room(self, room_id: str):
        """
        关闭会议房间
        
        Args:
            room_id: 房间 ID
        """
        if room_id in self.rooms:
            # 移除所有参与者
            room = self.rooms[room_id]
            for participant_id in list(room.participants.keys()):
                self.remove_participant(room_id, participant_id)
            
            del self.rooms[room_id]
    
    def add_participant(
        self,
        room_id: str,
        participant_id: str,
        participant_name: str
    ) -> bool:
        """
        添加参与者
        
        Args:
            room_id: 房间 ID
            participant_id: 参与者 ID
            participant_name: 参与者名称
            
        Returns:
            bool: 是否添加成功
        """
        if room_id not in self.rooms:
            return False
        
        room = self.rooms[room_id]
        if len(room.participants) >= room.max_participants:
            return False
        
        if participant_id in room.participants:
            return False
        
        room.add_participant(participant_id, participant_name)
        self.participants[participant_id] = room_id
        return True
    
    def remove_participant(self, room_id: str, participant_id: str) -> bool:
        """
        移除参与者
        
        Args:
            room_id: 房间 ID
            participant_id: 参与者 ID
            
        Returns:
            bool: 是否移除成功
        """
        if room_id not in self.rooms:
            return False
        
        room = self.rooms[room_id]
        room.remove_participant(participant_id)
        
        if participant_id in self.participants:
            del self.participants[participant_id]
        
        return True
    
    def broadcast(
        self,
        room_id: str,
        sender_id: str,
        message: Dict[str, Any]
    ) -> List[str]:
        """
        广播消息给房间内所有参与者
        
        Args:
            room_id: 房间 ID
            sender_id: 发送者 ID
            message: 消息内容
            
        Returns:
            List[str]: 接收到消息的参与者 ID 列表
        """
        if room_id not in self.rooms:
            return []
        
        room = self.rooms[room_id]
        return room.broadcast(sender_id, message)
    
    def get_room_info(self, room_id: str) -> Optional[Dict[str, Any]]:
        """
        获取房间信息
        
        Args:
            room_id: 房间 ID
            
        Returns:
            Optional[Dict[str, Any]]: 房间信息
        """
        if room_id not in self.rooms:
            return None
        
        room = self.rooms[room_id]
        return room.get_info()


class ConferenceRoom:
    """会议房间"""
    
    def __init__(self, room_id: str, max_participants: int = 10):
        self.room_id = room_id
        self.max_participants = max_participants
        self.participants: Dict[str, Dict[str, Any]] = {}
        self.message_handlers: List[Callable] = []
    
    def add_participant(self, participant_id: str, participant_name: str):
        """添加参与者"""
        self.participants[participant_id] = {
            "id": participant_id,
            "name": participant_name,
            "joined_at": asyncio.get_event_loop().time()
        }
    
    def remove_participant(self, participant_id: str):
        """移除参与者"""
        if participant_id in self.participants:
            del self.participants[participant_id]
    
    def broadcast(
        self,
        sender_id: str,
        message: Dict[str, Any]
    ) -> List[str]:
        """
        广播消息
        
        Args:
            sender_id: 发送者 ID
            message: 消息内容
            
        Returns:
            List[str]: 接收到消息的参与者 ID 列表
        """
        received_by = []
        
        for handler in self.message_handlers:
            try:
                handler(sender_id, message)
            except:
                pass
        
        return received_by
    
    def add_message_handler(self, handler: Callable):
        """添加消息处理器"""
        self.message_handlers.append(handler)
    
    def get_info(self) -> Dict[str, Any]:
        """获取房间信息"""
        return {
            "room_id": self.room_id,
            "max_participants": self.max_participants,
            "participants": list(self.participants.values()),
            "participant_count": len(self.participants)
        }


# 全局实例
_voice_dialog_system: Optional[VoiceDialogSystem] = None
_voice_conference_system: Optional[VoiceConferenceSystem] = None


def get_voice_dialog_system() -> VoiceDialogSystem:
    """获取语音对话系统"""
    global _voice_dialog_system
    if _voice_dialog_system is None:
        _voice_dialog_system = VoiceDialogSystem()
    return _voice_dialog_system


def get_voice_conference_system() -> VoiceConferenceSystem:
    """获取语音会议系统"""
    global _voice_conference_system
    if _voice_conference_system is None:
        _voice_conference_system = VoiceConferenceSystem()
    return _voice_conference_system
