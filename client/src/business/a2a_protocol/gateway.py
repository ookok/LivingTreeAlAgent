"""
LivingTree A2A Gateway
A2A 协议网关 - 整合所有模块

功能：
- Agent 注册与发现
- 消息路由与转发
- 即时唤醒处理
- 会话管理
- 安全过滤
"""

import json
import time
import asyncio
import threading
from typing import Dict, Any, Optional, List, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import uuid

from business.logger import get_logger

from . import MessageType, TaskStatus, A2AMessage, Task, SessionContext, AgentCapability
from .security import SecurityFilter, ThreatLevel
from .session import SessionManager, A2ASession, SessionPersistence
from .channel import (
    MultiChannelRouter, 
    MessageRouter, 
    AgentEndpoint, 
    TransportType,
    InMemoryChannel
)

logger = get_logger('a2a_gateway')


@dataclass
class AgentInfo:
    """Agent 信息"""
    agent_id: str
    agent_name: str
    capabilities: AgentCapability
    is_online: bool = False
    last_heartbeat: int = field(default_factory=lambda: int(time.time() * 1000))
    message_handler: Optional[Callable] = None


class LivingTreeA2AGateway:
    """
    LivingTree A2A 网关
    统一的 Agent 通信中枢
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        hmac_secret: str,
        storage_dir: Optional[str] = None
    ):
        self._agent_id = agent_id
        self._agent_name = agent_name
        self._hmac_secret = hmac_secret
        
        # 核心组件
        self._security = SecurityFilter(hmac_secret)
        self._session_manager = SessionManager(
            persistence=SessionPersistence(storage_dir)
        )
        self._channel_router = MultiChannelRouter()
        
        # Agent 注册表
        self._agents: Dict[str, AgentInfo] = {}
        self._local_handlers: Dict[str, Callable] = {}
        
        # 消息队列
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        
        # 回调
        self._task_handlers: Dict[str, Callable] = {}
        self._on_agent_discovered: Optional[Callable] = None
        
        # 锁
        self._lock = threading.RLock()
        
        logger.info(f"A2A Gateway initialized: {agent_id} ({agent_name})")
    
    # ========== Agent 注册 ==========
    
    def register_agent(
        self,
        agent_id: str,
        agent_name: str,
        capabilities: List[str],
        message_handler: Optional[Callable] = None,
        is_local: bool = True
    ) -> bool:
        """注册 Agent"""
        with self._lock:
            if agent_id in self._agents:
                logger.warning(f"Agent already registered: {agent_id}")
                return False
            
            capability = AgentCapability(
                agent_id=agent_id,
                agent_name=agent_name,
                capabilities=capabilities,
                input_modes=["text", "json"],
                output_modes=["text", "json"]
            )
            
            url = f"in_memory://{agent_id}" if is_local else f"http://{agent_id}"
            
            self._agents[agent_id] = AgentInfo(
                agent_id=agent_id,
                agent_name=agent_name,
                capabilities=capability,
                is_online=True,
                message_handler=message_handler
            )
            
            self._channel_router.register_agent(
                agent_id=agent_id,
                agent_name=agent_name,
                url=url,
                transport=TransportType.IN_MEMORY if is_local else TransportType.WEBSOCKET,
                capabilities=capabilities,
                is_local=is_local
            )
            
            if is_local and message_handler:
                self._local_handlers[agent_id] = message_handler
            
            logger.info(f"Agent registered: {agent_id} ({agent_name})")
            return True
    
    def unregister_agent(self, agent_id: str) -> bool:
        """注销 Agent"""
        with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                self._local_handlers.pop(agent_id, None)
                self._channel_router._router.unregister_endpoint(agent_id)
                logger.info(f"Agent unregistered: {agent_id}")
                return True
            return False
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """获取 Agent 信息"""
        with self._lock:
            return self._agents.get(agent_id)
    
    def list_agents(self, online_only: bool = True) -> List[AgentInfo]:
        """列出 Agent"""
        with self._lock:
            agents = self._agents.values()
            if online_only:
                agents = [a for a in agents if a.is_online]
            return list(agents)
    
    def find_agents(self, capability: str) -> List[AgentInfo]:
        """根据能力查找 Agent"""
        with self._lock:
            return [
                a for a in self._agents.values()
                if capability in a.capabilities.capabilities and a.is_online
            ]
    
    # ========== 消息发送 ==========
    
    async def send_task(
        self,
        target_id: str,
        task: Task,
        session_context: Optional[SessionContext] = None
    ) -> bool:
        """发送任务请求"""
        message = A2AMessage(
            message_type=MessageType.TASK_REQUEST,
            sender_id=self._agent_id,
            sender_name=self._agent_name,
            target_id=target_id,
            task_id=task.task_id,
            payload={
                'task': task.to_dict(),
                'session_context': session_context.to_dict() if session_context else None
            }
        )
        message.add_hmac_signature(self._hmac_secret)
        
        # 安全过滤
        is_safe, error = self._security.filter_message(message.to_dict())
        if not is_safe:
            logger.warning(f"Message filtered: {error}")
            return False
        
        return await self._channel_router.send_message(
            self._agent_id,
            target_id,
            message.to_dict()
        )
    
    async def send_response(
        self,
        target_id: str,
        task_id: str,
        result: Dict[str, Any],
        status: TaskStatus = TaskStatus.COMPLETED
    ) -> bool:
        """发送任务响应"""
        message = A2AMessage(
            message_type=MessageType.TASK_RESPONSE,
            sender_id=self._agent_id,
            sender_name=self._agent_name,
            target_id=target_id,
            task_id=task_id,
            payload={
                'result': result,
                'status': status.value
            }
        )
        message.add_hmac_signature(self._hmac_secret)
        
        return await self._channel_router.send_message(
            self._agent_id,
            target_id,
            message.to_dict()
        )
    
    async def instant_wake(
        self,
        target_id: str,
        wake_data: Dict[str, Any]
    ) -> bool:
        """即时唤醒远程 Agent"""
        agent = self.get_agent(target_id)
        if not agent:
            logger.warning(f"Agent not found for instant wake: {target_id}")
            return False
        
        message = A2AMessage(
            message_type=MessageType.INSTANT_WAKE,
            sender_id=self._agent_id,
            sender_name=self._agent_name,
            target_id=target_id,
            payload={
                'wake_trigger': 'hmac_webhook',
                'wake_data': wake_data
            }
        )
        message.add_hmac_signature(self._hmac_secret)
        
        logger.info(f"Instant wake sent to: {target_id}")
        return await self._channel_router.send_message(
            self._agent_id,
            target_id,
            message.to_dict()
        )
    
    # ========== Webhook 处理 ==========
    
    async def handle_webhook(
        self,
        payload: Dict[str, Any],
        signature: str
    ) -> tuple[bool, str]:
        """处理传入的 Webhook 请求"""
        if not self._security.verify_instant_wake(payload, signature):
            return False, "Invalid signature"
        
        message_type = payload.get('message_type', MessageType.INSTANT_WAKE.value)
        
        if message_type == MessageType.INSTANT_WAKE.value:
            wake_data = payload.get('payload', {}).get('wake_data', {})
            await self._handle_instant_wake(wake_data)
            return True, "Wake processed"
        
        return False, "Unknown message type"
    
    async def _handle_instant_wake(self, wake_data: Dict[str, Any]):
        """处理即时唤醒"""
        trigger = wake_data.get('trigger')
        data = wake_data.get('data', {})
        
        logger.info(f"Instant wake triggered: {trigger}")
        
        if trigger == 'task_assigned':
            task_id = data.get('task_id')
            if task_id and 'task_handler' in self._local_handlers:
                await self._local_handlers['task_handler'](data)
    
    # ========== 消息处理 ==========
    
    async def process_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理接收到的消息"""
        try:
            a2a_message = A2AMessage.from_dict(message)
            
            # 验证 HMAC 签名
            if not a2a_message.verify_hmac_signature(self._hmac_secret):
                logger.warning(f"Invalid HMAC signature from {a2a_message.sender_id}")
                return self._create_error_response(a2a_message, "Invalid signature", 401)
            
            # 安全过滤
            is_safe, error = self._security.filter_message(message)
            if not is_safe:
                return self._create_error_response(a2a_message, f"Security: {error}", 403)
            
            # 根据消息类型处理
            if a2a_message.message_type == MessageType.TASK_REQUEST:
                return await self._handle_task_request(a2a_message)
            elif a2a_message.message_type == MessageType.TASK_RESPONSE:
                return await self._handle_task_response(a2a_message)
            elif a2a_message.message_type == MessageType.INSTANT_WAKE:
                return await self._handle_instant_wake_message(a2a_message)
            elif a2a_message.message_type == MessageType.SESSION_INJECT:
                return await self._handle_session_inject(a2a_message)
            elif a2a_message.message_type == MessageType.CAPABILITY_DISCOVERY:
                return self._handle_capability_discovery(a2a_message)
            elif a2a_message.message_type == MessageType.HEARTBEAT:
                return self._handle_heartbeat(a2a_message)
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return None
    
    async def _handle_task_request(self, message: A2AMessage) -> Dict[str, Any]:
        """处理任务请求"""
        payload = message.payload
        task_data = payload.get('task', {})
        task = Task.from_dict(task_data)
        
        session_data = payload.get('session_context')
        if session_data:
            session_context = SessionContext.from_dict(session_data)
            if message.session_id:
                self._session_manager.inject_session(
                    message.session_id,
                    session_context.injected_context,
                    message.sender_id
                )
        
        if task.task_type in self._task_handlers:
            handler = self._task_handlers[task.task_type]
            try:
                result = await handler(task)
                return await self.send_response(message.sender_id, task.task_id, result, TaskStatus.COMPLETED)
            except Exception as e:
                logger.error(f"Task handler error: {e}")
                return await self.send_response(message.sender_id, task.task_id, {'error': str(e)}, TaskStatus.FAILED)
        
        return await self.send_response(message.sender_id, task.task_id, {'error': 'No handler'}, TaskStatus.FAILED)
    
    async def _handle_task_response(self, message: A2AMessage) -> Dict[str, Any]:
        """处理任务响应"""
        payload = message.payload
        logger.info(f"Task response: task={message.task_id}, status={payload.get('status')}")
        return message.to_dict()
    
    async def _handle_instant_wake_message(self, message: A2AMessage) -> Optional[Dict[str, Any]]:
        """处理即时唤醒消息"""
        wake_data = message.payload.get('wake_data', {})
        logger.info(f"Instant wake from {message.sender_id}")
        await self._handle_instant_wake(wake_data)
        return None
    
    async def _handle_session_inject(self, message: A2AMessage) -> Dict[str, Any]:
        """处理会话注入"""
        session_data = message.payload.get('session_context', {})
        session_context = SessionContext.from_dict(session_data)
        
        if message.session_id:
            self._session_manager.inject_session(
                message.session_id,
                session_context.injected_context,
                message.sender_id
            )
            return {'status': 'injected', 'session_id': message.session_id}
        
        return {'status': 'error', 'message': 'No session_id'}
    
    def _handle_capability_discovery(self, message: A2AMessage) -> Dict[str, Any]:
        """处理能力发现"""
        return {
            'agent_id': self._agent_id,
            'agent_name': self._agent_name,
            'capabilities': [a.capabilities.to_dict() for a in self._agents.values()]
        }
    
    def _handle_heartbeat(self, message: A2AMessage) -> Dict[str, Any]:
        """处理心跳"""
        if message.sender_id in self._agents:
            self._agents[message.sender_id].last_heartbeat = int(time.time() * 1000)
        return {'status': 'ok', 'timestamp': int(time.time() * 1000)}
    
    def _create_error_response(self, request: A2AMessage, error_message: str, status_code: int = 400) -> Dict[str, Any]:
        """创建错误响应"""
        return A2AMessage(
            message_type=MessageType.ERROR,
            sender_id=self._agent_id,
            sender_name=self._agent_name,
            target_id=request.sender_id,
            task_id=request.task_id,
            payload={'error': error_message, 'status_code': status_code}
        ).to_dict()
    
    # ========== 会话管理 ==========
    
    def create_session(self, user_id: str, participants: List[str], initial_context: Optional[Dict[str, Any]] = None) -> A2ASession:
        """创建会话"""
        return self._session_manager.create_session(user_id=user_id, participants=participants, initial_context=initial_context)
    
    def get_session(self, session_id: str) -> Optional[A2ASession]:
        """获取会话"""
        return self._session_manager.get_session(session_id)
    
    # ========== 任务处理器 ==========
    
    def register_task_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._task_handlers[task_type] = handler
        logger.info(f"Task handler registered: {task_type}")
    
    # ========== 生命周期 ==========
    
    async def start(self):
        """启动网关"""
        self._running = True
        logger.info(f"A2A Gateway started: {self._agent_id}")
    
    async def stop(self):
        """停止网关"""
        self._running = False
        logger.info(f"A2A Gateway stopped: {self._agent_id}")


def create_a2a_gateway(agent_id: str, agent_name: str, hmac_secret: str, storage_dir: Optional[str] = None) -> LivingTreeA2AGateway:
    """创建 A2A 网关实例"""
    return LivingTreeA2AGateway(agent_id=agent_id, agent_name=agent_name, hmac_secret=hmac_secret, storage_dir=storage_dir)
