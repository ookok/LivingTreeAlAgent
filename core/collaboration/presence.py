# -*- coding: utf-8 -*-
"""
在线状态管理 - Presence Management
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable
import asyncio
import json


class PresenceStatus(Enum):
    """在线状态"""
    ONLINE = "online"        # 在线
    AWAY = "away"           # 离开
    BUSY = "busy"           # 忙碌
    DND = "dnd"             # 请勿打扰
    OFFLINE = "offline"     # 离线


@dataclass
class UserPresence:
    """用户在线状态"""
    user_id: str
    workspace_id: str = ""
    status: PresenceStatus = PresenceStatus.OFFLINE
    last_seen: datetime = field(default_factory=datetime.now)
    current_document: Optional[str] = None  # 当前编辑的文档
    cursor_position: Optional[Dict] = None   # 光标位置
    selection: Optional[Dict] = None         # 选中文本
    device: str = "desktop"  # desktop, mobile, web
    custom_status: str = ""  # 自定义状态文字
    
    def to_dict(self) -> Dict:
        """转字典"""
        return {
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "status": self.status.value,
            "last_seen": self.last_seen.isoformat(),
            "current_document": self.current_document,
            "cursor_position": self.cursor_position,
            "selection": self.selection,
            "device": self.device,
            "custom_status": self.custom_status
        }


class PresenceManager:
    """
    在线状态管理器
    
    管理用户的在线状态和实时同步
    """
    
    def __init__(self):
        self._presences: Dict[str, Dict[str, UserPresence]] = {}  # workspace_id -> {user_id -> presence}
        self._listeners: List[Callable] = []
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False
    
    # ── 状态管理 ──────────────────────────────────────────────────────────────
    
    def set_presence(
        self,
        user_id: str,
        workspace_id: str,
        status: PresenceStatus = PresenceStatus.ONLINE,
        **kwargs
    ) -> UserPresence:
        """设置用户状态"""
        if workspace_id not in self._presences:
            self._presences[workspace_id] = {}
        
        presence = self._presences[workspace_id].get(user_id)
        
        if presence:
            presence.status = status
            presence.last_seen = datetime.now()
            for key, value in kwargs.items():
                if hasattr(presence, key):
                    setattr(presence, key, value)
        else:
            presence = UserPresence(
                user_id=user_id,
                workspace_id=workspace_id,
                status=status,
                **kwargs
            )
            self._presences[workspace_id][user_id] = presence
        
        # 触发监听器
        self._notify_listeners(workspace_id, presence)
        
        return presence
    
    def get_presence(self, user_id: str, workspace_id: str) -> Optional[UserPresence]:
        """获取用户状态"""
        return self._presences.get(workspace_id, {}).get(user_id)
    
    def get_workspace_presences(self, workspace_id: str) -> List[UserPresence]:
        """获取工作空间的所有在线状态"""
        presences = self._presences.get(workspace_id, {})
        return list(presences.values())
    
    def get_online_users(self, workspace_id: str) -> List[str]:
        """获取在线用户列表"""
        presences = self._presences.get(workspace_id, {})
        return [
            user_id for user_id, p in presences.items()
            if p.status != PresenceStatus.OFFLINE
        ]
    
    # ── 光标同步 ──────────────────────────────────────────────────────────────
    
    def update_cursor(
        self,
        user_id: str,
        workspace_id: str,
        document_id: str,
        position: Dict,
        selection: Optional[Dict] = None
    ):
        """更新用户光标位置"""
        presence = self.set_presence(
            user_id=user_id,
            workspace_id=workspace_id,
            current_document=document_id,
            cursor_position=position,
            selection=selection
        )
        return presence
    
    # ── 监听器 ────────────────────────────────────────────────────────────────
    
    def add_listener(self, callback: Callable):
        """添加状态变化监听器"""
        self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable):
        """移除监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self, workspace_id: str, presence: UserPresence):
        """通知监听器"""
        event = {
            "type": "presence_update",
            "workspace_id": workspace_id,
            "presence": presence.to_dict()
        }
        
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                pass  # 日志记录
    
    # ── 心跳检测 ──────────────────────────────────────────────────────────────
    
    async def start_heartbeat(self, interval: int = 60):
        """启动心跳检测"""
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(interval))
    
    async def stop_heartbeat(self):
        """停止心跳检测"""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
    
    async def _heartbeat_loop(self, interval: int):
        """心跳循环"""
        while self._running:
            try:
                await asyncio.sleep(interval)
                self._check_idle_users()
            except asyncio.CancelledError:
                break
            except Exception:
                pass
    
    def _check_idle_users(self):
        """检查空闲用户"""
        now = datetime.now()
        idle_threshold = 300  # 5分钟无活动视为离开
        
        for workspace_id, presences in self._presences.items():
            for user_id, presence in presences.items():
                if presence.status == PresenceStatus.ONLINE:
                    elapsed = (now - presence.last_seen).total_seconds()
                    if elapsed > idle_threshold:
                        presence.status = PresenceStatus.AWAY
                        self._notify_listeners(workspace_id, presence)


# ── 全局实例 ──────────────────────────────────────────────────────────────────

_presence_manager: Optional[PresenceManager] = None


def get_presence_manager() -> PresenceManager:
    """获取在线状态管理器"""
    global _presence_manager
    if _presence_manager is None:
        _presence_manager = PresenceManager()
    return _presence_manager
