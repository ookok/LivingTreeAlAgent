"""
WebRTC 信令服务器
提供 HTTP + WebSocket 双通道，处理 Offer/Answer/ICE 候选交换
"""

import asyncio
import json
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Callable
from aiohttp import web, WSMsgType
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Room:
    """WebRTC 房间"""
    id: str
    name: str
    participants: Dict[str, 'Participant'] = field(default_factory=dict)
    created_at: float = 0
    is_live: bool = False  # 是否开启直播模式

    def add_participant(self, peer_id: str, ws: web.WebSocketResponse, name: str = ""):
        self.participants[peer_id] = Participant(peer_id, ws, name)

    def remove_participant(self, peer_id: str):
        if peer_id in self.participants:
            del self.participants[peer_id]

    def broadcast(self, message: dict, exclude: Optional[str] = None):
        """广播消息给房间内除指定用户外的所有人"""
        for pid, p in self.participants.items():
            if pid != exclude and not p.ws.closed:
                asyncio.create_task(p.ws.send_json(message))


@dataclass
class Participant:
    """房间参与者"""
    id: str
    ws: web.WebSocketResponse
    name: str = ""
    is_audio_enabled: bool = True
    is_video_enabled: bool = True


class SignalingServer:
    """
    WebRTC 信令服务器

    处理流程:
    1. 用户加入房间 → 创建 Room（若不存在）
    2. 用户发布 Offer/Answer → 转发给房间内其他人
    3. 用户发布 ICE Candidate → 转发给房间内其他人
    4. 用户离开 → 通知房间内其他人
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.rooms: Dict[str, Room] = {}
        self.participants: Dict[str, Room] = {}  # peer_id -> room
        self._setup_routes()
        self.runner: Optional[web.AppRunner] = None

        # 回调钩子
        self.on_room_created: Optional[Callable] = None
        self.on_participant_joined: Optional[Callable] = None
        self.on_participant_left: Optional[Callable] = None

    def _setup_routes(self):
        """配置路由"""
        self.app.router.add_get('/ws/{room_id}/{peer_id}', self.websocket_handler)
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_get('/rooms', self.list_rooms_handler)
        self.app.router.add_post('/rooms', self.create_room_handler)
        self.app.router.add_static('/assets', str(Path(__file__).parent.parent.parent / 'assets' / 'webrtc'),
                                   show_index=True)

    async def start(self):
        """启动信令服务器"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        logger.info(f"WebRTC 信令服务器启动: ws://{self.host}:{self.port}/ws/<room_id>/<peer_id>")

    async def stop(self):
        """停止信令服务器"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("WebRTC 信令服务器已停止")

    async def health_handler(self, request):
        """健康检查"""
        return web.json_response({
            "status": "ok",
            "rooms": len(self.rooms),
            "participants": sum(len(r.participants) for r in self.rooms.values())
        })

    async def list_rooms_handler(self, request):
        """列出所有房间"""
        rooms_data = []
        for room_id, room in self.rooms.items():
            rooms_data.append({
                "id": room_id,
                "name": room.name,
                "participants": len(room.participants),
                "is_live": room.is_live,
                "created_at": room.created_at
            })
        return web.json_response({"rooms": rooms_data})

    async def create_room_handler(self, request):
        """创建房间"""
        data = await request.json()
        room_name = data.get('name', f"Room-{uuid.uuid4().hex[:6]}")
        room_id = data.get('room_id', uuid.uuid4().hex[:8])

        if room_id in self.rooms:
            return web.json_response({"error": "Room already exists"}, status=400)

        import time
        self.rooms[room_id] = Room(id=room_id, name=room_name, created_at=time.time())

        if self.on_room_created:
            await self.on_room_created(room_id, room_name)

        logger.info(f"创建房间: {room_name} ({room_id})")
        return web.json_response({"room_id": room_id, "name": room_name})

    async def websocket_handler(self, request):
        """
        WebSocket 信令处理

        消息类型:
        - join: 加入房间
        - offer: 发送 Offer SDP
        - answer: 发送 Answer SDP
        - ice_candidate: 发送 ICE 候选
        - leave: 离开房间
        - chat: 聊天室消息
        - live_start: 开始直播
        - live_stop: 停止直播
        """
        room_id = request.match_info['room_id']
        peer_id = request.match_info['peer_id']

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        room = self.rooms.get(room_id)
        if not room:
            await ws.send_json({"type": "error", "message": "Room not found"})
            await ws.close()
            return ws

        # 加入房间
        room.add_participant(peer_id, ws)
        self.participants[peer_id] = room

        # 广播用户加入
        room.broadcast({
            "type": "user_joined",
            "peer_id": peer_id,
            "participants": list(room.participants.keys())
        }, exclude=peer_id)

        if self.on_participant_joined:
            await self.on_participant_joined(room_id, peer_id)

        logger.info(f"用户 {peer_id} 加入房间 {room_id}")

        # 发送当前房间参与者列表
        await ws.send_json({
            "type": "room_info",
            "room_id": room_id,
            "participants": list(room.participants.keys()),
            "is_live": room.is_live
        })

        # 消息处理循环
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await self._handle_message(room, peer_id, ws, data)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from {peer_id}")
            elif msg.type == WSMsgType.ERROR:
                logger.error(f"WebSocket error for {peer_id}")

        # 用户断开 - 清理
        room.remove_participant(peer_id)
        if peer_id in self.participants:
            del self.participants[peer_id]

        room.broadcast({
            "type": "user_left",
            "peer_id": peer_id,
            "participants": list(room.participants.keys())
        })

        if self.on_participant_left:
            await self.on_participant_left(room_id, peer_id)

        logger.info(f"用户 {peer_id} 离开房间 {room_id}")

        # 如果房间空了，可以选择关闭
        if not room.participants:
            # 保持房间一段时间后自动删除
            await asyncio.sleep(300)  # 5分钟
            if not room.participants and room_id in self.rooms:
                del self.rooms[room_id]
                logger.info(f"房间 {room_id} 已空，已删除")

        return ws

    async def _handle_message(self, room: Room, peer_id: str, ws: web.WebSocketResponse, data: dict):
        """处理信令消息"""
        msg_type = data.get('type')

        if msg_type == 'offer':
            # 转发 Offer 给房间内其他人
            target_peer = data.get('target_peer')
            if target_peer and target_peer in room.participants:
                await room.participants[target_peer].ws.send_json({
                    "type": "offer",
                    "from_peer": peer_id,
                    "sdp": data.get('sdp'),
                    "sdpMid": data.get('sdpMid'),
                    "sdpMLineIndex": data.get('sdpMLineIndex')
                })

        elif msg_type == 'answer':
            # 转发 Answer 给指定用户
            target_peer = data.get('target_peer')
            if target_peer and target_peer in room.participants:
                await room.participants[target_peer].ws.send_json({
                    "type": "answer",
                    "from_peer": peer_id,
                    "sdp": data.get('sdp'),
                    "sdpMid": data.get('sdpMid'),
                    "sdpMLineIndex": data.get('sdpMLineIndex')
                })

        elif msg_type == 'ice_candidate':
            # 转发 ICE 候选给房间内其他人
            target_peer = data.get('target_peer')
            if target_peer and target_peer in room.participants:
                await room.participants[target_peer].ws.send_json({
                    "type": "ice_candidate",
                    "from_peer": peer_id,
                    "candidate": data.get('candidate')
                })

        elif msg_type == 'chat':
            # 聊天室消息广播
            room.broadcast({
                "type": "chat",
                "from_peer": peer_id,
                "message": data.get('message', ''),
                "timestamp": data.get('timestamp')
            })

        elif msg_type == 'live_start':
            # 开始直播
            room.is_live = True
            room.broadcast({
                "type": "live_started",
                "by_peer": peer_id
            })
            logger.info(f"房间 {room.id} 开始直播")

        elif msg_type == 'live_stop':
            # 停止直播
            room.is_live = False
            room.broadcast({
                "type": "live_stopped",
                "by_peer": peer_id
            })
            logger.info(f"房间 {room.id} 停止直播")

        elif msg_type == 'toggle_audio':
            # 切换音频
            room.broadcast({
                "type": "audio_toggled",
                "peer_id": peer_id,
                "enabled": data.get('enabled', True)
            }, exclude=peer_id)

        elif msg_type == 'toggle_video':
            # 切换视频
            room.broadcast({
                "type": "video_toggled",
                "peer_id": peer_id,
                "enabled": data.get('enabled', True)
            }, exclude=peer_id)

    def get_room_info(self, room_id: str) -> Optional[dict]:
        """获取房间信息"""
        room = self.rooms.get(room_id)
        if not room:
            return None
        return {
            "id": room.id,
            "name": room.name,
            "participants": len(room.participants),
            "is_live": room.is_live
        }


# 单例模式
_server_instance: Optional[SignalingServer] = None


def get_signaling_server(host: str = "0.0.0.0", port: int = 8080) -> SignalingServer:
    """获取信令服务器单例"""
    global _server_instance
    if _server_instance is None:
        _server_instance = SignalingServer(host, port)
    return _server_instance


async def start_signaling_server(host: str = "0.0.0.0", port: int = 8080):
    """启动信令服务器"""
    server = get_signaling_server(host, port)
    await server.start()
    return server


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_signaling_server())
