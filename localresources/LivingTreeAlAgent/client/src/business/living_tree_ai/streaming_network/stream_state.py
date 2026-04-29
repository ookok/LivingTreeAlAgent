"""
Stream State - 流状态同步
=========================

功能：
- 聊天消息同步
- 弹幕同步
- 点赞/情感同步
- 播放状态同步

Author: LivingTreeAI Community
"""

import asyncio
import time
import uuid
import json
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Any, List, Dict
from enum import Enum


class StreamStateType(Enum):
    """流状态类型"""
    CHAT = "chat"
    DANMAKU = "danmaku"
    LIKE = "like"
    PLAYBACK = "playback"
    PRESENCE = "presence"


@dataclass
class ChatMessage:
    """聊天消息"""
    msg_id: str
    stream_id: str
    sender_id: str
    sender_name: str
    text: str
    timestamp: float
    sequence: int

    def to_dict(self) -> dict:
        return {
            "type": StreamStateType.CHAT.value,
            "msg_id": self.msg_id,
            "stream_id": self.stream_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "text": self.text,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
        }


@dataclass
class DanmakuMessage:
    """弹幕消息"""
    danmaku_id: str
    stream_id: str
    sender_id: str
    text: str
    color: str = "#FFFFFF"
    position: str = "roll"  # roll/float/top
    timestamp: float
    sequence: int

    def to_dict(self) -> dict:
        return {
            "type": StreamStateType.DANMAKU.value,
            "danmaku_id": self.danmaku_id,
            "stream_id": self.stream_id,
            "sender_id": self.sender_id,
            "text": self.text,
            "color": self.color,
            "position": self.position,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
        }


@dataclass
class LikeEvent:
    """点赞事件"""
    event_id: str
    stream_id: str
    sender_id: str
    count: int = 1
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "type": StreamStateType.LIKE.value,
            "event_id": self.event_id,
            "stream_id": self.stream_id,
            "sender_id": self.sender_id,
            "count": self.count,
            "timestamp": self.timestamp,
        }


@dataclass
class StreamState:
    """流状态"""
    stream_id: str
    is_playing: bool = True
    current_position_ms: float = 0
    total_viewers: int = 0
    total_likes: int = 0
    last_update: float = field(default_factory=time.time)


class StreamStateSync:
    """
    流状态同步

    功能：
    1. 聊天/弹幕广播
    2. 播放状态同步
    3. 计数聚合
    """

    def __init__(
        self,
        node_id: str,
        send_func: Optional[Callable[[str, dict], Awaitable]] = None,
        sync_protocol: Optional[Any] = None,
    ):
        self.node_id = node_id

        # 状态存储
        self.states: Dict[str, StreamState] = {}
        self.chat_history: Dict[str, List[ChatMessage]] = {}
        self.danmaku_history: Dict[str, List[DanmakuMessage]] = {}

        # 聚合计数
        self.like_counters: Dict[str, int] = {}

        # 网络函数
        self._send_func = send_func
        self._sync = sync_protocol

        # 序列号
        self.sequences: Dict[str, int] = {}

        # 回调
        self._on_chat_received: Optional[Callable] = None
        self._on_danmaku_received: Optional[Callable] = None
        self._on_like_received: Optional[Callable] = None
        self._on_playback_changed: Optional[Callable] = None

    def _next_sequence(self, stream_id: str) -> int:
        """获取下一个序列号"""
        seq = self.sequences.get(stream_id, 0) + 1
        self.sequences[stream_id] = seq
        return seq

    # ========== 聊天 ==========

    async def send_chat(
        self,
        stream_id: str,
        text: str,
        sender_name: str = "",
    ) -> ChatMessage:
        """发送聊天消息"""
        msg = ChatMessage(
            msg_id=str(uuid.uuid4())[:16],
            stream_id=stream_id,
            sender_id=self.node_id,
            sender_name=sender_name or self.node_id,
            text=text,
            timestamp=self._sync.get_synchronized_time_ms() if self._sync else time.time() * 1000,
            sequence=self._next_sequence(stream_id),
        )

        # 本地存储
        if stream_id not in self.chat_history:
            self.chat_history[stream_id] = []
        self.chat_history[stream_id].append(msg)

        # 广播
        await self._broadcast_state_update(stream_id, msg.to_dict())

        return msg

    async def receive_chat(self, data: dict):
        """接收聊天消息"""
        msg = ChatMessage(
            msg_id=data["msg_id"],
            stream_id=data["stream_id"],
            sender_id=data["sender_id"],
            sender_name=data["sender_name"],
            text=data["text"],
            timestamp=data["timestamp"],
            sequence=data["sequence"],
        )

        # 存储
        if msg.stream_id not in self.chat_history:
            self.chat_history[msg.stream_id] = []
        self.chat_history[msg.stream_id].append(msg)

        # 回调
        if self._on_chat_received:
            await self._on_chat_received(msg)

    # ========== 弹幕 ==========

    async def send_danmaku(
        self,
        stream_id: str,
        text: str,
        color: str = "#FFFFFF",
        position: str = "roll",
    ) -> DanmakuMessage:
        """发送弹幕"""
        danmaku = DanmakuMessage(
            danmaku_id=str(uuid.uuid4())[:16],
            stream_id=stream_id,
            sender_id=self.node_id,
            text=text,
            color=color,
            position=position,
            timestamp=self._sync.get_synchronized_time_ms() if self._sync else time.time() * 1000,
            sequence=self._next_sequence(stream_id),
        )

        # 本地存储
        if stream_id not in self.danmaku_history:
            self.danmaku_history[stream_id] = []
        self.danmaku_history[stream_id].append(danmaku)

        # 广播
        await self._broadcast_state_update(stream_id, danmaku.to_dict())

        return danmaku

    async def receive_danmaku(self, data: dict):
        """接收弹幕"""
        danmaku = DanmakuMessage(
            danmaku_id=data["danmaku_id"],
            stream_id=data["stream_id"],
            sender_id=data["sender_id"],
            text=data["text"],
            color=data.get("color", "#FFFFFF"),
            position=data.get("position", "roll"),
            timestamp=data["timestamp"],
            sequence=data["sequence"],
        )

        if self._on_danmaku_received:
            await self._on_danmaku_received(danmaku)

    # ========== 点赞 ==========

    async def send_like(
        self,
        stream_id: str,
        count: int = 1,
    ) -> LikeEvent:
        """发送点赞"""
        event = LikeEvent(
            event_id=str(uuid.uuid4())[:16],
            stream_id=stream_id,
            sender_id=self.node_id,
            count=count,
            timestamp=self._sync.get_synchronized_time_ms() if self._sync else time.time() * 1000,
        )

        # 本地聚合
        self.like_counters[stream_id] = self.like_counters.get(stream_id, 0) + count

        # 更新状态
        state = self._get_or_create_state(stream_id)
        state.total_likes += count
        state.last_update = time.time()

        # 广播
        await self._broadcast_state_update(stream_id, event.to_dict())

        return event

    async def receive_like(self, data: dict):
        """接收点赞"""
        stream_id = data["stream_id"]
        count = data.get("count", 1)

        # 聚合
        self.like_counters[stream_id] = self.like_counters.get(stream_id, 0) + count

        # 更新状态
        state = self.states.get(stream_id)
        if state:
            state.total_likes += count
            state.last_update = time.time()

        if self._on_like_received:
            await self._on_like_received(data)

    # ========== 播放状态 ==========

    async def update_playback_state(
        self,
        stream_id: str,
        is_playing: bool,
        position_ms: float,
    ):
        """更新播放状态"""
        state = self._get_or_create_state(stream_id)
        state.is_playing = is_playing
        state.current_position_ms = position_ms
        state.last_update = time.time()

        # 广播
        await self._broadcast_state_update(stream_id, {
            "type": StreamStateType.PLAYBACK.value,
            "is_playing": is_playing,
            "position_ms": position_ms,
            "timestamp": state.last_update,
        })

    async def handle_playback_update(self, data: dict):
        """处理播放状态更新"""
        stream_id = data.get("stream_id")
        if not stream_id:
            return

        state = self._get_or_create_state(stream_id)
        state.is_playing = data.get("is_playing", True)
        state.current_position_ms = data.get("position_ms", 0)
        state.last_update = data.get("timestamp", time.time())

        if self._on_playback_changed:
            await self._on_playback_changed(state)

    # ========== 广播 ==========

    async def _broadcast_state_update(self, stream_id: str, update: dict):
        """广播状态更新"""
        if not self._send_func:
            return

        update["stream_id"] = stream_id
        update["sender"] = self.node_id

        # 根据类型选择传输策略
        state_type = update.get("type")

        if state_type in [StreamStateType.CHAT.value, StreamStateType.DANMAKU.value]:
            # 可靠传输
            await self._reliable_broadcast(stream_id, update)
        elif state_type == StreamStateType.LIKE.value:
            # 尽力传输
            await self._best_effort_broadcast(stream_id, update)
        elif state_type == StreamStateType.PLAYBACK.value:
            # 强一致传输
            await self._strong_consistent_broadcast(stream_id, update)

    async def _reliable_broadcast(self, stream_id: str, update: dict):
        """可靠广播"""
        # 简化实现：发送给所有已知节点
        peers = self._get_peer_list(stream_id)
        for peer in peers:
            try:
                await self._send_func(peer, {
                    "type": "state_update",
                    "stream_id": stream_id,
                    "update": update,
                })
            except Exception:
                pass

    async def _best_effort_broadcast(self, stream_id: str, update: dict):
        """尽力广播"""
        # 简化实现：只发送给父节点和中继节点
        peers = self._get_relay_peers(stream_id)
        for peer in peers:
            try:
                await self._send_func(peer, {
                    "type": "state_update",
                    "stream_id": stream_id,
                    "update": update,
                })
            except Exception:
                pass

    async def _strong_consistent_broadcast(self, stream_id: str, update: dict):
        """强一致广播"""
        # 使用主时钟源确认
        peers = self._get_peer_list(stream_id)
        acks = []

        for peer in peers:
            try:
                response = await self._send_func(peer, {
                    "type": "state_update_strong",
                    "stream_id": stream_id,
                    "update": update,
                })
                if response and response.get("ack"):
                    acks.append(peer)
            except Exception:
                pass

    def _get_peer_list(self, stream_id: str) -> List[str]:
        """获取对等节点列表（简化）"""
        return []

    def _get_relay_peers(self, stream_id: str) -> List[str]:
        """获取中继节点列表（简化）"""
        return []

    def _get_or_create_state(self, stream_id: str) -> StreamState:
        """获取或创建流状态"""
        if stream_id not in self.states:
            self.states[stream_id] = StreamState(stream_id=stream_id)
        return self.states[stream_id]

    # ========== 回调设置 ==========

    def set_chat_received_callback(self, callback: Callable):
        self._on_chat_received = callback

    def set_danmaku_received_callback(self, callback: Callable):
        self._on_danmaku_received = callback

    def set_like_received_callback(self, callback: Callable):
        self._on_like_received = callback

    def set_playback_changed_callback(self, callback: Callable):
        self._on_playback_changed = callback

    # ========== 统计 ==========

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            "active_streams": len(self.states),
            "chat_messages": sum(len(h) for h in self.chat_history.values()),
            "danmaku_messages": sum(len(h) for h in self.danmaku_history.values()),
            "like_counters": self.like_counters,
        }


# 全局单例
_state_instance: Optional[StreamStateSync] = None


def get_stream_state_sync(node_id: str = "local") -> StreamStateSync:
    """获取流状态同步单例"""
    global _state_instance
    if _state_instance is None:
        _state_instance = StreamStateSync(node_id)
    return _state_instance