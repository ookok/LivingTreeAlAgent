"""
FFmpeg 录制管理 - WebRTC 流录制与转码

功能：
- 接收前端 MediaRecorder 发来的 WebM chunk
- 实时写入文件
- 自动合并为最终 MP4
- 支持录制暂停/恢复
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
import queue
import uuid

from client.src.business.ffmpeg_tool import FFmpegTool, FFmpegRecorder, PRESET_BALANCED


class RecordingState(Enum):
    """录制状态"""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    MERGING = "merging"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class RecordingSession:
    """录制会话"""
    session_id: str
    room_id: str
    start_time: float
    chunks: List[Path] = field(default_factory=list)
    state: RecordingState = RecordingState.IDLE
    duration: float = 0.0
    final_path: Optional[str] = None
    error: Optional[str] = None

    @property
    def is_active(self) -> bool:
        return self.state in (RecordingState.RECORDING, RecordingState.PAUSED)


class RecordingManager:
    """
    录制管理器

    管理多个并发录制会话，处理来自 WebSocket 的 chunk 数据流
    """

    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir or "./recordings")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._sessions: Dict[str, RecordingSession] = {}
        self._recorders: Dict[str, FFmpegRecorder] = {}
        self._ffmpeg = FFmpegTool()

        # 事件回调
        self._on_chunk_received: Optional[Callable] = None
        self._on_recording_complete: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

        self._lock = threading.Lock()

    def set_callbacks(
        self,
        on_chunk: Callable = None,
        on_complete: Callable = None,
        on_error: Callable = None
    ):
        """设置事件回调"""
        self._on_chunk_received = on_chunk
        self._on_recording_complete = on_complete
        self._on_error = on_error

    def create_session(self, room_id: str) -> RecordingSession:
        """
        创建录制会话

        Args:
            room_id: 房间 ID

        Returns:
            录制会话对象
        """
        session_id = f"rec_{room_id}_{int(time.time() * 1000)}"

        session = RecordingSession(
            session_id=session_id,
            room_id=room_id,
            start_time=time.time()
        )

        recorder = FFmpegRecorder(
            session_id=session_id,
            output_dir=str(self.output_dir)
        )

        with self._lock:
            self._sessions[session_id] = session
            self._recorders[session_id] = recorder

        session.state = RecordingState.IDLE
        return session

    async def start_recording(self, session_id: str) -> bool:
        """
        开始录制

        Args:
            session_id: 会话 ID

        Returns:
            是否成功
        """
        with self._lock:
            if session_id not in self._sessions:
                return False

            session = self._sessions[session_id]
            recorder = self._recorders[session_id]

        try:
            recorder.start()
            session.state = RecordingState.RECORDING
            return True
        except Exception as e:
            session.state = RecordingState.ERROR
            session.error = str(e)
            if self._on_error:
                await self._on_error(session_id, str(e))
            return False

    async def pause_recording(self, session_id: str) -> bool:
        """暂停录制"""
        with self._lock:
            if session_id not in self._sessions:
                return False
            session = self._sessions[session_id]

        if session.state == RecordingState.RECORDING:
            session.state = RecordingState.PAUSED
            return True
        return False

    async def resume_recording(self, session_id: str) -> bool:
        """恢复录制"""
        with self._lock:
            if session_id not in self._sessions:
                return False
            session = self._sessions[session_id]

        if session.state == RecordingState.PAUSED:
            session.state = RecordingState.RECORDING
            return True
        return False

    async def write_chunk(self, session_id: str, chunk_data: bytes) -> Optional[Path]:
        """
        写入一个 chunk

        Args:
            session_id: 会话 ID
            chunk_data: chunk 数据

        Returns:
            写入的文件路径
        """
        with self._lock:
            if session_id not in self._sessions:
                return None
            session = self._sessions[session_id]
            recorder = self._recorders[session_id]

        try:
            # 自动开始（如果还没开始）
            if session.state == RecordingState.IDLE:
                recorder.start()
                session.state = RecordingState.RECORDING

            if session.state != RecordingState.RECORDING:
                return None

            chunk_path = recorder.write_chunk(chunk_data)

            # 更新时长
            session.duration = time.time() - session.start_time

            if self._on_chunk_received:
                await self._on_chunk_received(session_id, chunk_path)

            return chunk_path

        except Exception as e:
            session.state = RecordingState.ERROR
            session.error = str(e)
            if self._on_error:
                await self._on_error(session_id, str(e))
            return None

    async def stop_recording(self, session_id: str) -> Optional[str]:
        """
        停止录制

        Args:
            session_id: 会话 ID

        Returns:
            最终文件路径（尚未合并）
        """
        with self._lock:
            if session_id not in self._sessions:
                return None
            session = self._sessions[session_id]
            recorder = self._recorders[session_id]

        session.state = RecordingState.MERGING
        final_path = recorder.stop()
        session.final_path = final_path

        return final_path

    async def finalize_recording(self, session_id: str) -> Optional[str]:
        """
        完成录制（合并 chunks）

        Args:
            session_id: 会话 ID

        Returns:
            最终 MP4 文件路径
        """
        with self._lock:
            if session_id not in self._sessions:
                return None
            session = self._sessions[session_id]
            recorder = self._recorders[session_id]

        try:
            result = await recorder.merge_chunks()

            if result["returncode"] == 0:
                session.state = RecordingState.COMPLETED
                session.final_path = str(recorder.final_path)

                if self._on_recording_complete:
                    await self._on_recording_complete(
                        session_id,
                        session.final_path,
                        session.duration
                    )

                return session.final_path
            else:
                session.state = RecordingState.ERROR
                session.error = result.get("stderr", "Unknown error")
                return None

        except Exception as e:
            session.state = RecordingState.ERROR
            session.error = str(e)
            if self._on_error:
                await self._on_error(session_id, str(e))
            return None

    async def cancel_recording(self, session_id: str) -> bool:
        """
        取消录制（删除所有文件）

        Args:
            session_id: 会话 ID

        Returns:
            是否成功
        """
        with self._lock:
            if session_id not in self._sessions:
                return False

            session = self._sessions[session_id]
            recorder = self._recorders.get(session.session_id)

        try:
            # 删除 chunk 文件
            if recorder:
                for chunk in recorder.chunks:
                    chunk.unlink(missing_ok=True)

                # 删除 concat list
                if recorder.concat_list_path.exists():
                    recorder.concat_list_path.unlink()

            session.state = RecordingState.IDLE
            session.chunks.clear()

            return True

        except Exception as e:
            if self._on_error:
                await self._on_error(session_id, str(e))
            return False

    def get_session(self, session_id: str) -> Optional[RecordingSession]:
        """获取会话信息"""
        with self._lock:
            return self._sessions.get(session_id)

    def get_all_sessions(self) -> List[RecordingSession]:
        """获取所有会话"""
        with self._lock:
            return list(self._sessions.values())

    def get_active_sessions(self) -> List[RecordingSession]:
        """获取活跃会话"""
        with self._lock:
            return [s for s in self._sessions.values() if s.is_active]

    def get_recordings_by_room(self, room_id: str) -> List[RecordingSession]:
        """获取某个房间的录制"""
        with self._lock:
            return [s for s in self._sessions.values() if s.room_id == room_id]

    def cleanup_old_recordings(self, max_age_hours: int = 24):
        """
        清理旧录制文件

        Args:
            max_age_hours: 最长保留时间（小时）
        """
        cutoff = time.time() - max_age_hours * 3600

        for session in self._sessions.values():
            if session.start_time < cutoff:
                # 删除文件
                if session.final_path:
                    Path(session.final_path).unlink(missing_ok=True)

                # 删除 chunks
                recorder = self._recorders.get(session.session_id)
                if recorder:
                    for chunk in recorder.chunks:
                        chunk.unlink(missing_ok=True)


class LiveRecordingHandler:
    """
    直播录制处理器

    处理来自 WebSocket 的直播流数据
    """

    def __init__(self, manager: RecordingManager = None):
        self.manager = manager or RecordingManager()
        self._ws_connections: Dict[str, asyncio.Queue] = {}
        self._processing_tasks: Dict[str, asyncio.Task] = {}

    async def handle_binary_message(
        self,
        session_id: str,
        data: bytes
    ) -> bool:
        """
        处理二进制消息（chunk 数据）

        Args:
            session_id: 会话 ID
            data: chunk 数据

        Returns:
            是否成功
        """
        chunk_path = await self.manager.write_chunk(session_id, data)
        return chunk_path is not None

    async def handle_control_message(
        self,
        session_id: str,
        action: str,
        params: dict = None
    ) -> dict:
        """
        处理控制消息

        Args:
            session_id: 会话 ID
            action: 操作类型 (start/stop/pause/resume/finalize)
            params: 额外参数

        Returns:
            处理结果
        """
        params = params or {}

        if action == "start":
            success = await self.manager.start_recording(session_id)
            return {"success": success, "session_id": session_id}

        elif action == "stop":
            final_path = await self.manager.stop_recording(session_id)
            return {"success": final_path is not None, "final_path": final_path}

        elif action == "finalize":
            final_path = await self.manager.finalize_recording(session_id)
            return {"success": final_path is not None, "final_path": final_path}

        elif action == "pause":
            success = await self.manager.pause_recording(session_id)
            return {"success": success}

        elif action == "resume":
            success = await self.manager.resume_recording(session_id)
            return {"success": success}

        elif action == "cancel":
            success = await self.manager.cancel_recording(session_id)
            return {"success": success}

        elif action == "status":
            session = self.manager.get_session(session_id)
            if session:
                return {
                    "success": True,
                    "session_id": session_id,
                    "state": session.state.value,
                    "duration": session.duration,
                    "chunks": len(session.chunks)
                }
            return {"success": False, "error": "Session not found"}

        return {"success": False, "error": f"Unknown action: {action}"}


# 全局录制管理器
_recording_manager: Optional[RecordingManager] = None


def get_recording_manager() -> RecordingManager:
    """获取录制管理器单例"""
    global _recording_manager
    if _recording_manager is None:
        _recording_manager = RecordingManager()
    return _recording_manager
