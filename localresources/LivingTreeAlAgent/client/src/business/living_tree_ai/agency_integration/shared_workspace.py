"""
共享工作空间模块

借鉴 OpenSpace 概念，为多 Agent 提供统一的共享工作空间
支持共享上下文、Agent 状态管理、消息总线
"""

import asyncio
import uuid
import time
import json
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading


class AgentState(Enum):
    """Agent 状态"""
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    BLOCKED = "blocked"
    COMPLETED = "completed"


@dataclass
class WorkspaceMessage:
    """工作空间消息"""
    msg_id: str
    sender_id: str
    sender_name: str
    msg_type: str
    content: Any
    timestamp: float
    room_id: Optional[str] = None
    reply_to: Optional[str] = None


@dataclass
class SharedContext:
    """共享上下文条目"""
    key: str
    value: Any
    owner_id: str
    created_at: float
    updated_at: float
    access_count: int = 0
    is_public: bool = True


class MessageBus:
    """消息总线"""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, callback: Callable):
        """订阅事件"""
        with self._lock:
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        """取消订阅"""
        with self._lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)

    async def publish(self, event_type: str, data: Any):
        """发布事件"""
        with self._lock:
            callbacks = self._subscribers.get(event_type, []).copy()

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                print(f"[MessageBus] 事件处理失败 {event_type}: {e}")


class SharedWorkspace:
    """
    多 Agent 共享工作空间

    借鉴 OpenSpace 概念，提供统一的共享工作空间
    """

    def __init__(self, workspace_id: Optional[str] = None):
        self.workspace_id = workspace_id or str(uuid.uuid4())
        self.shared_context: Dict[str, SharedContext] = {}
        self.agent_states: Dict[str, AgentState] = {}
        self.agent_info: Dict[str, Dict] = {}
        self.message_bus = MessageBus()
        self._lock = threading.RLock()
        self._rooms: Dict[str, Set[str]] = defaultdict(set)
        self._history: List[WorkspaceMessage] = []
        self._max_history = 1000

    def register_agent(
        self,
        agent_id: str,
        agent_name: str,
        role: str = "",
        capabilities: Optional[List[str]] = None
    ) -> bool:
        """
        注册 Agent

        Args:
            agent_id: Agent ID
            agent_name: Agent 名称
            role: 角色
            capabilities: 能力列表

        Returns:
            bool: 是否成功
        """
        with self._lock:
            if agent_id in self.agent_info:
                return False

            self.agent_info[agent_id] = {
                "name": agent_name,
                "role": role,
                "capabilities": capabilities or [],
                "registered_at": time.time()
            }
            self.agent_states[agent_id] = AgentState.IDLE

            asyncio.create_task(
                self.message_bus.publish("agent_registered", {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "role": role
                })
            )

            return True

    def unregister_agent(self, agent_id: str) -> bool:
        """注销 Agent"""
        with self._lock:
            if agent_id not in self.agent_info:
                return False

            del self.agent_info[agent_id]
            del self.agent_states[agent_id]

            for room_id in self._rooms:
                self._rooms[room_id].discard(agent_id)

            asyncio.create_task(
                self.message_bus.publish("agent_unregistered", {
                    "agent_id": agent_id
                })
            )

            return True

    def set_agent_state(self, agent_id: str, state: AgentState) -> bool:
        """设置 Agent 状态"""
        with self._lock:
            if agent_id not in self.agent_states:
                return False

            old_state = self.agent_states[agent_id]
            self.agent_states[agent_id] = state

            asyncio.create_task(
                self.message_bus.publish("agent_state_changed", {
                    "agent_id": agent_id,
                    "old_state": old_state.value,
                    "new_state": state.value
                })
            )

            return True

    def get_agent_state(self, agent_id: str) -> Optional[AgentState]:
        """获取 Agent 状态"""
        return self.agent_states.get(agent_id)

    def get_active_agents(self) -> List[str]:
        """获取活跃的 Agent"""
        with self._lock:
            return [
                agent_id for agent_id, state in self.agent_states.items()
                if state == AgentState.WORKING
            ]

    def set_context(
        self,
        key: str,
        value: Any,
        owner_id: str,
        is_public: bool = True
    ):
        """
        设置共享上下文

        Args:
            key: 上下文键
            value: 上下文值
            owner_id: 拥有者 ID
            is_public: 是否公开
        """
        with self._lock:
            now = time.time()

            if key in self.shared_context:
                context = self.shared_context[key]
                context.value = value
                context.updated_at = now
                context.access_count += 1
            else:
                self.shared_context[key] = SharedContext(
                    key=key,
                    value=value,
                    owner_id=owner_id,
                    created_at=now,
                    updated_at=now
                )

            asyncio.create_task(
                self.message_bus.publish("context_updated", {
                    "key": key,
                    "owner_id": owner_id,
                    "is_public": is_public
                })
            )

    def get_context(self, key: str, requester_id: Optional[str] = None) -> Optional[Any]:
        """
        获取共享上下文

        Args:
            key: 上下文键
            requester_id: 请求者 ID

        Returns:
            Optional[Any]: 上下文值
        """
        with self._lock:
            context = self.shared_context.get(key)
            if not context:
                return None

            if not context.is_public and context.owner_id != requester_id:
                return None

            context.access_count += 1
            return context.value

    def delete_context(self, key: str, requester_id: str) -> bool:
        """删除共享上下文"""
        with self._lock:
            context = self.shared_context.get(key)
            if not context:
                return False

            if context.owner_id != requester_id:
                return False

            del self.shared_context[key]
            return True

    def list_context_keys(
        self,
        requester_id: Optional[str] = None,
        owner_id: Optional[str] = None
    ) -> List[str]:
        """列出上下文键"""
        with self._lock:
            keys = []
            for key, context in self.shared_context.items():
                if not context.is_public and context.owner_id != requester_id:
                    continue
                if owner_id and context.owner_id != owner_id:
                    continue
                keys.append(key)
            return keys

    async def send_message(
        self,
        sender_id: str,
        sender_name: str,
        msg_type: str,
        content: Any,
        room_id: Optional[str] = None,
        recipient_id: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> str:
        """
        发送消息

        Args:
            sender_id: 发送者 ID
            sender_name: 发送者名称
            msg_type: 消息类型
            content: 消息内容
            room_id: 房间 ID（可选）
            recipient_id: 接收者 ID（可选）
            reply_to: 回复的消息 ID（可选）

        Returns:
            str: 消息 ID
        """
        msg_id = str(uuid.uuid4())

        message = WorkspaceMessage(
            msg_id=msg_id,
            sender_id=sender_id,
            sender_name=sender_name,
            msg_type=msg_type,
            content=content,
            timestamp=time.time(),
            room_id=room_id,
            reply_to=reply_to
        )

        with self._lock:
            self._history.append(message)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        await self.message_bus.publish("message_sent", message)

        if room_id:
            await self.message_bus.publish(f"room_{room_id}_message", message)

        if recipient_id:
            await self.message_bus.publish(f"agent_{recipient_id}_message", message)

        return msg_id

    def get_messages(
        self,
        agent_id: Optional[str] = None,
        room_id: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100
    ) -> List[WorkspaceMessage]:
        """获取消息"""
        with self._lock:
            messages = self._history.copy()

        if agent_id:
            messages = [m for m in messages if m.sender_id == agent_id or m.recipient_id == agent_id]

        if room_id:
            messages = [m for m in messages if m.room_id == room_id]

        if since:
            messages = [m for m in messages if m.timestamp >= since]

        return messages[-limit:]

    def join_room(self, agent_id: str, room_id: str):
        """加入房间"""
        with self._lock:
            self._rooms[room_id].add(agent_id)

        asyncio.create_task(
            self.message_bus.publish("room_joined", {
                "agent_id": agent_id,
                "room_id": room_id
            })
        )

    def leave_room(self, agent_id: str, room_id: str):
        """离开房间"""
        with self._lock:
            self._rooms[room_id].discard(agent_id)

        asyncio.create_task(
            self.message_bus.publish("room_left", {
                "agent_id": agent_id,
                "room_id": room_id
            })
        )

    def get_room_members(self, room_id: str) -> Set[str]:
        """获取房间成员"""
        with self._lock:
            return self._rooms.get(room_id, set()).copy()

    def get_workspace_snapshot(self) -> Dict:
        """获取工作空间快照"""
        with self._lock:
            return {
                "workspace_id": self.workspace_id,
                "agent_count": len(self.agent_info),
                "active_agents": len(self.get_active_agents()),
                "context_count": len(self.shared_context),
                "message_count": len(self._history),
                "rooms": list(self._rooms.keys()),
                "agents": {
                    agent_id: {
                        "name": info["name"],
                        "role": info["role"],
                        "state": self.agent_states.get(agent_id, AgentState.IDLE).value
                    }
                    for agent_id, info in self.agent_info.items()
                }
            }


class WorkspaceManager:
    """工作空间管理器"""

    def __init__(self):
        self.workspaces: Dict[str, SharedWorkspace] = {}
        self._default_workspace: Optional[SharedWorkspace] = None

    def create_workspace(self, workspace_id: Optional[str] = None) -> SharedWorkspace:
        """创建工作空间"""
        workspace = SharedWorkspace(workspace_id)
        self.workspaces[workspace.workspace_id] = workspace

        if self._default_workspace is None:
            self._default_workspace = workspace

        return workspace

    def get_workspace(self, workspace_id: str) -> Optional[SharedWorkspace]:
        """获取工作空间"""
        return self.workspaces.get(workspace_id)

    def get_default_workspace(self) -> Optional[SharedWorkspace]:
        """获取默认工作空间"""
        return self._default_workspace

    def delete_workspace(self, workspace_id: str) -> bool:
        """删除工作空间"""
        if workspace_id not in self.workspaces:
            return False

        del self.workspaces[workspace_id]

        if self._default_workspace and self._default_workspace.workspace_id == workspace_id:
            self._default_workspace = next(iter(self.workspaces.values()), None)

        return True

    def list_workspaces(self) -> List[Dict]:
        """列出所有工作空间"""
        return [
            ws.get_workspace_snapshot()
            for ws in self.workspaces.values()
        ]


_global_manager: Optional[WorkspaceManager] = None


def get_workspace_manager() -> WorkspaceManager:
    """获取工作空间管理器"""
    global _global_manager
    if _global_manager is None:
        _global_manager = WorkspaceManager()
    return _global_manager


def get_default_workspace() -> SharedWorkspace:
    """获取默认工作空间"""
    manager = get_workspace_manager()
    ws = manager.get_default_workspace()
    if ws is None:
        ws = manager.create_workspace("default")
    return ws
