"""
WebRTC SFU - 选择性转发单元
===========================

功能：
- WebRTC 连接管理
- 媒体流转发
- 多用户会话

Author: LivingTreeAI Community
"""

import asyncio
import time
import uuid
import json
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any, List, Dict, Set
from enum import Enum


class ConnectionState(Enum):
    """连接状态"""
    NEW = "new"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    CLOSED = "closed"


class MediaType(Enum):
    """媒体类型"""
    VIDEO = "video"
    AUDIO = "audio"
    SCREEN = "screen"


@dataclass
class MediaTrack:
    """媒体轨道"""
    track_id: str
    media_type: MediaType
    stream_id: str
    label: str = ""
    enabled: bool = True
    muted: bool = False


@dataclass
class StreamSession:
    """流会话"""
    session_id: str
    stream_id: str
    publisher_id: str
    created_at: float
    is_live: bool = True
    viewer_count: int = 0
    max_viewers: int = 1000
    bitrate: int = 2000  # kbps
    fps: int = 30

    # 参与者
    participants: Dict[str, "Participant"] = field(default_factory=dict)

    # 媒体轨道
    video_track: Optional[MediaTrack] = None
    audio_track: Optional[MediaTrack] = None


@dataclass
class Participant:
    """会话参与者"""
    node_id: str
    session_id: str
    is_publisher: bool = False
    connection_state: ConnectionState = ConnectionState.NEW
    joined_at: float = field(default_factory=time.time)

    # 媒体轨道
    tracks: List[MediaTrack] = field(default_factory=list)

    # 连接信息
    latency_ms: float = 0
    bandwidth_kbps: int = 0


class WebRTCSFU:
    """
    WebRTC 选择性转发单元 (SFU)

    功能：
    1. 会话管理
    2. WebRTC 连接建立
    3. 媒体流转发
    4. 参与者管理
    """

    # 配置
    DEFAULT_BITRATE = 2000  # kbps
    MAX_BITRATE = 8000
    MIN_BITRATE = 500
    MAX_VIEWERS_PER_SESSION = 1000

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
        get_media_func: Optional[Callable[[str], Any]] = None,
    ):
        self.node_id = node_id

        # 会话管理
        self.sessions: Dict[str, StreamSession] = {}
        self.node_sessions: Dict[str, str] = {}  # node_id -> session_id

        # 连接管理
        self.peer_connections: Dict[str, Any] = {}  # 简化实现
        self.data_channels: Dict[str, Any] = {}

        # 网络函数
        self._send_func = send_func
        self._get_media = get_media_func

        # 回调
        self._on_participant_joined: Optional[Callable] = None
        self._on_participant_left: Optional[Callable] = None
        self._on_stream_started: Optional[Callable] = None
        self._on_stream_stopped: Optional[Callable] = None

    # ========== 会话管理 ==========

    async def create_session(
        self,
        stream_id: str,
        publisher_id: str,
        bitrate: int = DEFAULT_BITRATE,
        fps: int = 30,
    ) -> StreamSession:
        """
        创建流会话（主播端调用）

        Args:
            stream_id: 流ID
            publisher_id: 主播节点ID
            bitrate: 码率 (kbps)
            fps: 帧率

        Returns:
            StreamSession
        """
        session_id = f"session_{stream_id}_{int(time.time())}"

        session = StreamSession(
            session_id=session_id,
            stream_id=stream_id,
            publisher_id=publisher_id,
            created_at=time.time(),
            bitrate=bitrate,
            fps=fps,
        )

        self.sessions[session_id] = session
        self.node_sessions[publisher_id] = session_id

        return session

    async def join_session(
        self,
        session_id: str,
        node_id: str,
        is_publisher: bool = False,
    ) -> Optional[Participant]:
        """
        加入会话（观众端调用）

        Args:
            session_id: 会话ID
            node_id: 节点ID
            is_publisher: 是否为发布者

        Returns:
            Participant 或 None
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        if session.viewer_count >= session.max_viewers:
            return None

        participant = Participant(
            node_id=node_id,
            session_id=session_id,
            is_publisher=is_publisher,
            connection_state=ConnectionState.CONNECTING,
        )

        session.participants[node_id] = participant
        self.node_sessions[node_id] = session_id

        if is_publisher:
            session.is_live = True

        session.viewer_count += 1

        # 回调
        if self._on_participant_joined:
            await self._on_participant_joined(session, participant)

        return participant

    async def leave_session(self, node_id: str):
        """离开会话"""
        session_id = self.node_sessions.get(node_id)
        if not session_id:
            return

        session = self.sessions.get(session_id)
        if session:
            participant = session.participants.pop(node_id, None)
            if participant:
                session.viewer_count -= 1

            # 如果主播离开，结束直播
            if participant and participant.is_publisher:
                session.is_live = False
                if self._on_stream_stopped:
                    await self._on_stream_stopped(session)

        del self.node_sessions[node_id]

    async def end_session(self, session_id: str):
        """结束会话"""
        session = self.sessions.pop(session_id, None)
        if session:
            for node_id in list(session.participants.keys()):
                if node_id in self.node_sessions:
                    del self.node_sessions[node_id]

            if self._on_stream_stopped:
                await self._on_stream_stopped(session)

    def get_session(self, session_id: str) -> Optional[StreamSession]:
        """获取会话"""
        return self.sessions.get(session_id)

    def get_node_session(self, node_id: str) -> Optional[StreamSession]:
        """获取节点参与的会话"""
        session_id = self.node_sessions.get(node_id)
        if session_id:
            return self.sessions.get(session_id)
        return None

    # ========== 连接管理 ==========

    async def create_offer(self, target_node: str, session_id: str) -> str:
        """
        创建 WebRTC Offer

        Returns:
            SDP offer 字符串
        """
        # 简化实现：生成模拟SDP
        offer = {
            "type": "offer",
            "sdp": f"v=0\r\no=- {self.node_id} 1234567890 IN IP4 127.0.0.1\r\n",
            "session_id": session_id,
            "target": target_node,
        }
        return json.dumps(offer)

    async def handle_offer(self, offer_data: str, from_node: str) -> str:
        """
        处理 WebRTC Offer，返回 Answer

        Args:
            offer_data: SDP Offer
            from_node: 发送者

        Returns:
            SDP Answer
        """
        offer = json.loads(offer_data)

        # 创建 Answer
        answer = {
            "type": "answer",
            "sdp": f"v=0\r\no=- {self.node_id} 9876543210 IN IP4 127.0.0.1\r\n",
            "session_id": offer.get("session_id"),
            "target": from_node,
        }

        return json.dumps(answer)

    async def handle_answer(self, answer_data: str):
        """处理 WebRTC Answer"""
        answer = json.loads(answer_data)
        # 更新连接状态
        target = answer.get("target")

    async def add_ice_candidate(self, candidate_data: dict):
        """添加 ICE 候选"""
        # 简化实现
        pass

    # ========== 媒体控制 ==========

    async def publish_track(
        self,
        node_id: str,
        media_type: MediaType,
        track_id: str,
    ):
        """发布媒体轨道"""
        session = self.get_node_session(node_id)
        if not session:
            return

        track = MediaTrack(
            track_id=track_id,
            media_type=media_type,
            stream_id=session.stream_id,
        )

        if media_type == MediaType.VIDEO:
            session.video_track = track
        elif media_type == MediaType.AUDIO:
            session.audio_track = track

        # 通知其他参与者
        await self._broadcast_track_added(session, node_id, track)

    async def unpublish_track(self, node_id: str, media_type: MediaType):
        """取消发布媒体轨道"""
        session = self.get_node_session(node_id)
        if not session:
            return

        if media_type == MediaType.VIDEO:
            session.video_track = None
        elif media_type == MediaType.AUDIO:
            session.audio_track = None

        await self._broadcast_track_removed(session, node_id, media_type)

    async def mute_track(self, node_id: str, media_type: MediaType, muted: bool):
        """静音/取消静音"""
        session = self.get_node_session(node_id)
        if not session:
            return

        track = None
        if media_type == MediaType.VIDEO and session.video_track:
            track = session.video_track
        elif media_type == MediaType.AUDIO and session.audio_track:
            track = session.audio_track

        if track:
            track.muted = muted

    async def _broadcast_track_added(
        self,
        session: StreamSession,
        node_id: str,
        track: MediaTrack,
    ):
        """广播新轨道"""
        for participant in session.participants.values():
            if participant.node_id != node_id:
                await self._send_func(participant.node_id, {
                    "type": "track_added",
                    "session_id": session.session_id,
                    "node_id": node_id,
                    "track": {
                        "track_id": track.track_id,
                        "media_type": track.media_type.value,
                    },
                })

    async def _broadcast_track_removed(
        self,
        session: StreamSession,
        node_id: str,
        media_type: MediaType,
    ):
        """广播轨道移除"""
        for participant in session.participants.values():
            if participant.node_id != node_id:
                await self._send_func(participant.node_id, {
                    "type": "track_removed",
                    "session_id": session.session_id,
                    "node_id": node_id,
                    "media_type": media_type.value,
                })

    # ========== 码率控制 ==========

    async def set_bitrate(self, session_id: str, bitrate: int):
        """设置码率"""
        session = self.sessions.get(session_id)
        if session:
            session.bitrate = max(self.MIN_BITRATE, min(bitrate, self.MAX_BITRATE))

    async def request_bitrate_decrease(self, session_id: str, factor: float = 0.8):
        """请求降低码率"""
        session = self.sessions.get(session_id)
        if session:
            new_bitrate = int(session.bitrate * factor)
            session.bitrate = max(self.MIN_BITRATE, new_bitrate)
            return session.bitrate
        return None

    async def request_bitrate_increase(self, session_id: str, factor: float = 1.2):
        """请求提高码率"""
        session = self.sessions.get(session_id)
        if session:
            new_bitrate = int(session.bitrate * factor)
            session.bitrate = min(self.MAX_BITRATE, new_bitrate)
            return session.bitrate
        return None

    # ========== 回调设置 ==========

    def set_participant_joined_callback(self, callback: Callable):
        self._on_participant_joined = callback

    def set_participant_left_callback(self, callback: Callable):
        self._on_participant_left = callback

    def set_stream_started_callback(self, callback: Callable):
        self._on_stream_started = callback

    def set_stream_stopped_callback(self, callback: Callable):
        self._on_stream_stopped = callback

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "active_sessions": len(self.sessions),
            "total_participants": sum(
                len(s.participants) for s in self.sessions.values()
            ),
            "sessions": {
                sid: {
                    "publisher": s.publisher_id,
                    "viewers": s.viewer_count,
                    "is_live": s.is_live,
                    "bitrate": s.bitrate,
                }
                for sid, s in self.sessions.items()
            },
        }


# 全局单例
_webrtc_sfu_instance: Optional[WebRTCSFU] = None


def get_webrtc_sfu(node_id: str = "local") -> WebRTCSFU:
    """获取 WebRTC SFU 单例"""
    global _webrtc_sfu_instance
    if _webrtc_sfu_instance is None:
        _webrtc_sfu_instance = WebRTCSFU(node_id)
    return _webrtc_sfu_instance