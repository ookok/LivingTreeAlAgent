"""
实时流式对话系统

基于 WebSocket 的实时语音对话服务
"""

import asyncio
import json
import uuid
import base64
import websockets
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import traceback


class MessageType(Enum):
    """消息类型"""
    # 控制消息
    JOIN = "join"
    LEAVE = "leave"
    HEARTBEAT = "heartbeat"
    
    # 语音消息
    AUDIO = "audio"
    AUDIO_START = "audio_start"
    AUDIO_END = "audio_end"
    
    # 文本消息
    TEXT = "text"
    
    # 状态消息
    SPEAKING = "speaking"
    SILENCE = "silence"
    
    # 会议消息
    MEETING_START = "meeting_start"
    MEETING_END = "meeting_end"
    TOPIC_CHANGE = "topic_change"


@dataclass
class StreamMessage:
    """流消息"""
    type: MessageType
    sender_id: str
    sender_name: str
    content: Any = None
    timestamp: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Participant:
    """参与者"""
    id: str
    name: str
    is_ai: bool = False
    is_speaking: bool = False
    is_muted: bool = False
    is_deafened: bool = False
    audio_level: float = 0.0
    websocket = None


class WebSocketStreamServer:
    """WebSocket 流式对话服务器"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.participants: Dict[str, Participant] = {}
        self.rooms: Dict[str, Set[str]] = {}  # room_id -> set of participant_ids
        self.current_room: Optional[str] = None
        
        # 回调函数
        self.on_message: Optional[Callable] = None
        self.on_participant_join: Optional[Callable] = None
        self.on_participant_leave: Optional[Callable] = None
        
        # 服务器
        self.server = None
        self._running = False
    
    async def start(self):
        """启动服务器"""
        self._running = True
        
        self.server = await websockets.serve(
            self._handle_connection,
            self.host,
            self.port
        )
        
        print(f"[WebSocket] 服务器已启动: ws://{self.host}:{self.port}")
    
    async def stop(self):
        """停止服务器"""
        self._running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        print("[WebSocket] 服务器已停止")
    
    async def _handle_connection(self, websocket, path):
        """处理连接"""
        participant_id = str(uuid.uuid4())
        participant = Participant(
            id=participant_id,
            name=f"用户_{participant_id[:8]}",
            websocket=websocket
        )
        
        self.participants[participant_id] = participant
        
        print(f"[WebSocket] 新连接: {participant_id}")
        
        if self.on_participant_join:
            await self.on_participant_join(participant)
        
        try:
            async for message in websocket:
                await self._handle_message(websocket, participant, message)
                
        except websockets.exceptions.ConnectionClosed:
            pass
            
        finally:
            # 清理
            if participant_id in self.participants:
                del self.participants[participant_id]
            
            # 从所有房间移除
            for room_id in list(self.rooms.keys()):
                if participant_id in self.rooms[room_id]:
                    self.rooms[room_id].discard(participant_id)
            
            if self.on_participant_leave:
                await self.on_participant_leave(participant)
            
            print(f"[WebSocket] 连接关闭: {participant_id}")
    
    async def _handle_message(
        self,
        websocket,
        participant: Participant,
        message: str
    ):
        """处理消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == MessageType.JOIN.value:
                # 加入房间
                room_id = data.get("room_id", "default")
                participant.name = data.get("name", participant.name)
                participant.is_ai = data.get("is_ai", False)
                
                if room_id not in self.rooms:
                    self.rooms[room_id] = set()
                
                self.rooms[room_id].add(participant.id)
                self.current_room = room_id
                
                # 发送确认
                await self._send(websocket, {
                    "type": "joined",
                    "participant_id": participant.id,
                    "room_id": room_id
                })
                
                # 广播给房间内其他人
                await self._broadcast_to_room(
                    room_id,
                    {
                        "type": "participant_joined",
                        "participant_id": participant.id,
                        "name": participant.name,
                        "is_ai": participant.is_ai
                    },
                    exclude={participant.id}
                )
            
            elif msg_type == MessageType.LEAVE.value:
                # 离开房间
                if self.current_room:
                    self.rooms[self.current_room].discard(participant.id)
                    await self._broadcast_to_room(
                        self.current_room,
                        {
                            "type": "participant_left",
                            "participant_id": participant.id
                        }
                    )
            
            elif msg_type == MessageType.AUDIO.value:
                # 音频消息
                audio_data = data.get("audio")  # base64 encoded
                if audio_data and not participant.is_deafened:
                    # 广播音频给房间内其他人
                    await self._broadcast_to_room(
                        self.current_room,
                        {
                            "type": "audio",
                            "sender_id": participant.id,
                            "sender_name": participant.name,
                            "audio": audio_data
                        },
                        exclude={participant.id}
                    )
            
            elif msg_type == MessageType.AUDIO_START.value:
                # 开始发言
                participant.is_speaking = True
                await self._broadcast_to_room(
                    self.current_room,
                    {
                        "type": "speaking_start",
                        "participant_id": participant.id,
                        "name": participant.name
                    },
                    exclude={participant.id}
                )
            
            elif msg_type == MessageType.AUDIO_END.value:
                # 结束发言
                participant.is_speaking = False
                await self._broadcast_to_room(
                    self.current_room,
                    {
                        "type": "speaking_end",
                        "participant_id": participant.id
                    },
                    exclude={participant.id}
                )
            
            elif msg_type == MessageType.TEXT.value:
                # 文本消息
                text = data.get("text", "")
                if self.on_message:
                    response = await self.on_message(participant, text)
                    if response:
                        await self._broadcast_to_room(
                            self.current_room,
                            {
                                "type": "text",
                                "sender_id": participant.id,
                                "sender_name": participant.name,
                                "text": response
                            }
                        )
                else:
                    # 直接广播
                    await self._broadcast_to_room(
                        self.current_room,
                        {
                            "type": "text",
                            "sender_id": participant.id,
                            "sender_name": participant.name,
                            "text": text
                        },
                        exclude={participant.id}
                    )
            
            elif msg_type == MessageType.HEARTBEAT.value:
                # 心跳
                await self._send(websocket, {"type": "heartbeat_ack"})
            
            elif msg_type == MessageType.MEETING_START.value:
                # 会议开始
                await self._broadcast_to_room(
                    self.current_room,
                    {
                        "type": "meeting_started",
                        "initiator_id": participant.id
                    }
                )
            
            elif msg_type == MessageType.TOPIC_CHANGE.value:
                # 议题变更
                topic = data.get("topic")
                await self._broadcast_to_room(
                    self.current_room,
                    {
                        "type": "topic_changed",
                        "topic": topic,
                        "changed_by": participant.id
                    }
                )
            
        except json.JSONDecodeError:
            print(f"[WebSocket] 无效的 JSON 消息: {message[:100]}")
            
        except Exception as e:
            print(f"[WebSocket] 处理消息失败: {e}")
            traceback.print_exc()
    
    async def _send(self, websocket, message: dict):
        """发送消息"""
        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            print(f"[WebSocket] 发送消息失败: {e}")
    
    async def _broadcast_to_room(
        self,
        room_id: str,
        message: dict,
        exclude: Set[str] = None
    ):
        """广播消息到房间"""
        if room_id not in self.rooms:
            return
        
        exclude = exclude or set()
        message_str = json.dumps(message)
        
        for participant_id in self.rooms[room_id]:
            if participant_id in exclude:
                continue
            
            p = self.participants.get(participant_id)
            if p and p.websocket:
                try:
                    await p.websocket.send(message_str)
                except Exception as e:
                    print(f"[WebSocket] 广播消息失败: {e}")


class WebSocketStreamClient:
    """WebSocket 流式对话客户端"""
    
    def __init__(self, server_url: str = "ws://localhost:8765"):
        self.server_url = server_url
        self.websocket = None
        self.participant_id: Optional[str] = None
        self.room_id: Optional[str] = None
        self.is_connected = False
        
        # 回调函数
        self.on_message: Optional[Callable] = None
        self.on_audio: Optional[Callable] = None
        self.on_participant_join: Optional[Callable] = None
        self.on_participant_leave: Optional[Callable] = None
        self.on_speaking: Optional[Callable] = None
    
    async def connect(
        self,
        name: str,
        room_id: str = "default",
        is_ai: bool = False
    ):
        """
        连接到服务器
        
        Args:
            name: 用户名
            room_id: 房间 ID
            is_ai: 是否是 AI
        """
        try:
            self.websocket = await websockets.connect(self.server_url)
            self.is_connected = True
            
            # 发送加入消息
            await self.send({
                "type": MessageType.JOIN.value,
                "name": name,
                "room_id": room_id,
                "is_ai": is_ai
            })
            
            # 启动接收循环
            asyncio.create_task(self._receive_loop())
            
        except Exception as e:
            print(f"[WebSocket Client] 连接失败: {e}")
            raise
    
    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            try:
                await self.send({
                    "type": MessageType.LEAVE.value
                })
                await self.websocket.close()
            except:
                pass
        
        self.is_connected = False
    
    async def send_audio(self, audio_data: bytes):
        """
        发送音频数据
        
        Args:
            audio_data: 音频数据（bytes）
        """
        if not self.is_connected:
            return
        
        # base64 编码
        audio_b64 = base64.b64encode(audio_data).decode()
        
        await self.send({
            "type": MessageType.AUDIO.value,
            "audio": audio_b64
        })
    
    async def send_audio_start(self):
        """发送开始发言"""
        await self.send({
            "type": MessageType.AUDIO_START.value
        })
    
    async def send_audio_end(self):
        """发送结束发言"""
        await self.send({
            "type": MessageType.AUDIO_END.value
        })
    
    async def send_text(self, text: str):
        """
        发送文本消息
        
        Args:
            text: 文本内容
        """
        await self.send({
            "type": MessageType.TEXT.value,
            "text": text
        })
    
    async def send_meeting_start(self):
        """发送会议开始"""
        await self.send({
            "type": MessageType.MEETING_START.value
        })
    
    async def send_topic_change(self, topic: str):
        """
        发送议题变更
        
        Args:
            topic: 新议题
        """
        await self.send({
            "type": MessageType.TOPIC_CHANGE.value,
            "topic": topic
        })
    
    async def send_heartbeat(self):
        """发送心跳"""
        await self.send({
            "type": MessageType.HEARTBEAT.value
        })
    
    async def send(self, message: dict):
        """发送消息"""
        if self.websocket:
            try:
                await self.websocket.send(json.dumps(message))
            except Exception as e:
                print(f"[WebSocket Client] 发送消息失败: {e}")
    
    async def _receive_loop(self):
        """接收消息循环"""
        try:
            async for message in self.websocket:
                await self._handle_message(message)
                
        except websockets.exceptions.ConnectionClosed:
            print("[WebSocket Client] 连接已关闭")
            
        finally:
            self.is_connected = False
    
    async def _handle_message(self, message: str):
        """处理消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "joined":
                self.participant_id = data.get("participant_id")
                self.room_id = data.get("room_id")
                print(f"[WebSocket Client] 已加入房间: {self.room_id}")
            
            elif msg_type == "audio":
                if self.on_audio:
                    audio_b64 = data.get("audio", "")
                    audio_data = base64.b64decode(audio_b64)
                    await self.on_audio(
                        data.get("sender_id"),
                        data.get("sender_name"),
                        audio_data
                    )
            
            elif msg_type == "text":
                if self.on_message:
                    await self.on_message(
                        data.get("sender_id"),
                        data.get("sender_name"),
                        data.get("text")
                    )
            
            elif msg_type == "participant_joined":
                if self.on_participant_join:
                    await self.on_participant_join(
                        data.get("participant_id"),
                        data.get("name"),
                        data.get("is_ai", False)
                    )
            
            elif msg_type == "participant_left":
                if self.on_participant_leave:
                    await self.on_participant_leave(data.get("participant_id"))
            
            elif msg_type == "speaking_start":
                if self.on_speaking:
                    await self.on_speaking(
                        data.get("participant_id"),
                        data.get("name"),
                        True
                    )
            
            elif msg_type == "speaking_end":
                if self.on_speaking:
                    await self.on_speaking(
                        data.get("participant_id"),
                        None,
                        False
                    )
            
            elif msg_type == "heartbeat_ack":
                pass  # 心跳响应
            
        except json.JSONDecodeError:
            print(f"[WebSocket Client] 无效的 JSON: {message[:100]}")
            
        except Exception as e:
            print(f"[WebSocket Client] 处理消息失败: {e}")


# 全局实例
_stream_server: Optional[WebSocketStreamServer] = None
_stream_clients: Dict[str, WebSocketStreamClient] = {}


def get_stream_server() -> WebSocketStreamServer:
    """获取流式服务器"""
    global _stream_server
    if _stream_server is None:
        _stream_server = WebSocketStreamServer()
    return _stream_server


def get_stream_client(client_id: str = "default") -> WebSocketStreamClient:
    """获取流式客户端"""
    global _stream_clients
    if client_id not in _stream_clients:
        _stream_clients[client_id] = WebSocketStreamClient()
    return _stream_clients[client_id]
