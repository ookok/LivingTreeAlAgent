# -*- coding: utf-8 -*-
"""
同步服务器 - Sync Server
=========================

功能：
1. WebSocket 服务端
2. 用户认证
3. 数据存储
4. 冲突检测

Author: Hermes Desktop Team
"""

from __future__ import annotations
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass, field

from .data_types import SyncRecord, SyncStatus, SyncDataType

logger = logging.getLogger(__name__)


@dataclass
class UserSession:
    """用户会话"""
    user_id: str
    device_id: str
    websocket: Any
    last_active: datetime = field(default_factory=datetime.now)
    subscribed_types: Set[SyncDataType] = field(default_factory=set)


class SyncServer:
    """
    同步服务器
    
    管理多个客户端连接和数据同步
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self._server = None
        self._sessions: Dict[str, UserSession] = {}
        self._user_devices: Dict[str, Set[str]] = {}  # user_id -> device_ids
        self._data_store: Dict[str, SyncRecord] = {}  # 全局数据存储
        self._running = False
        self._api_key = ""  # 可设置的 API Key
    
    async def start(self):
        """启动服务器"""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port
        )
        
        addr = self._server.sockets[0].getsockname()
        logger.info(f"Sync server started on {addr}")
        
        self._running = True
        
        async with self._server:
            await self._server.serve_forever()
    
    async def stop(self):
        """停止服务器"""
        self._running = False
        if self._server:
            self._server.close()
        logger.info("Sync server stopped")
    
    async def _handle_client(self, ws, path):
        """处理客户端连接"""
        session_id = str(uuid.uuid4())
        session = None
        
        try:
            # 等待认证
            auth_msg = await ws.recv()
            auth_data = json.loads(auth_msg)
            
            if auth_data.get('type') != 'auth':
                await ws.send(json.dumps({"type": "error", "message": "Auth required"}))
                return
            
            user_id = auth_data.get('user_id', '')
            device_id = auth_data.get('device_id', '')
            
            if not user_id:
                await ws.send(json.dumps({"type": "error", "message": "User ID required"}))
                return
            
            # 创建会话
            session = UserSession(
                user_id=user_id,
                device_id=device_id,
                websocket=ws
            )
            self._sessions[session_id] = session
            
            # 跟踪用户设备
            if user_id not in self._user_devices:
                self._user_devices[user_id] = set()
            self._user_devices[user_id].add(device_id)
            
            logger.info(f"Client connected: {user_id}/{device_id}")
            
            # 发送认证成功
            await ws.send(json.dumps({
                "type": "auth_success",
                "session_id": session_id
            }))
            
            # 处理消息循环
            async for msg in ws:
                await self._handle_message(session, msg)
                
        except Exception as e:
            logger.error(f"Client error: {e}")
        
        finally:
            # 清理会话
            if session:
                if session.user_id in self._user_devices:
                    self._user_devices[session.user_id].discard(session.device_id)
                del self._sessions[session_id]
                logger.info(f"Client disconnected: {session.user_id}")
    
    async def _handle_message(self, session: UserSession, msg: str):
        """处理客户端消息"""
        try:
            data = json.loads(msg)
            msg_type = data.get('type')
            
            if msg_type == 'sync_batch':
                await self._handle_sync_batch(session, data)
            
            elif msg_type == 'fetch_updates':
                await self._handle_fetch_updates(session, data)
            
            elif msg_type == 'subscribe':
                await self._handle_subscribe(session, data)
            
            elif msg_type == 'ping':
                await session.websocket.send(json.dumps({"type": "pong"}))
            
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        
        except Exception as e:
            logger.error(f"Message handling error: {e}")
            await session.websocket.send(json.dumps({
                "type": "error",
                "message": str(e)
            }))
    
    async def _handle_sync_batch(self, session: UserSession, data: Dict):
        """处理批量同步"""
        records = data.get('records', [])
        results = []
        
        for record_data in records:
            record = SyncRecord.from_dict(record_data)
            record.user_id = session.user_id
            record.device_id = session.device_id
            
            # 检查冲突
            existing = self._data_store.get(record.id)
            
            if existing and existing.device_id != session.device_id:
                # 不同设备，可能冲突
                if existing.version >= record.version and existing.checksum != record.checksum:
                    # 冲突！
                    results.append({
                        "id": record.id,
                        "status": "conflict",
                        "remote_data": existing.to_dict()
                    })
                    continue
            
            # 存储记录
            record.status = SyncStatus.SYNCED
            record.synced_at = datetime.now()
            self._data_store[record.id] = record
            
            results.append({
                "id": record.id,
                "status": "synced",
                "version": record.version
            })
        
        # 发送响应
        await session.websocket.send(json.dumps({
            "type": "sync_response",
            "results": results
        }))
        
        # 广播更新给其他设备
        await self._broadcast_updates(session.user_id, session.device_id, records)
    
    async def _handle_fetch_updates(self, session: UserSession, data: Dict):
        """处理获取更新请求"""
        last_sync = data.get('last_sync')
        
        if last_sync:
            last_sync_dt = datetime.fromisoformat(last_sync)
            records = [
                r.to_dict() for r in self._data_store.values()
                if r.user_id == session.user_id and r.updated_at > last_sync_dt
            ]
        else:
            # 全量同步
            records = [
                r.to_dict() for r in self._data_store.values()
                if r.user_id == session.user_id
            ]
        
        await session.websocket.send(json.dumps({
            "type": "updates",
            "records": records
        }))
    
    async def _handle_subscribe(self, session: UserSession, data: Dict):
        """处理订阅请求"""
        types = data.get('types', [])
        
        for type_str in types:
            try:
                session.subscribed_types.add(SyncDataType(type_str))
            except ValueError:
                pass
        
        await session.websocket.send(json.dumps({
            "type": "subscribed",
            "types": [t.value for t in session.subscribed_types]
        }))
    
    async def _broadcast_updates(self, user_id: str, exclude_device: str, records: List[Dict]):
        """广播更新给同一用户的其他设备"""
        user_device_ids = self._user_devices.get(user_id, set()) - {exclude_device}
        
        for session in self._sessions.values():
            if session.user_id == user_id and session.device_id in user_device_ids:
                try:
                    await session.websocket.send(json.dumps({
                        "type": "remote_update",
                        "records": records
                    }))
                except Exception as e:
                    logger.error(f"Broadcast error: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取服务器统计"""
        return {
            "total_sessions": len(self._sessions),
            "total_users": len(self._user_devices),
            "total_records": len(self._data_store),
            "running": self._running
        }


# ── 启动脚本 ──────────────────────────────────────────────────────────────────

async def run_server(host: str = "0.0.0.0", port: int = 8765):
    """运行同步服务器"""
    server = SyncServer(host=host, port=port)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        await server.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_server())
