"""
A2A 协议通信通道
Communication Channel for A2A Protocol

功能：
- Agent 发现与注册
- 消息路由
- 多协议传输支持（WebSocket/HTTP）
"""

import json
import time
import asyncio
import threading
from typing import Dict, Any, Optional, List, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from client.src.business.logger import get_logger

logger = get_logger('a2a_channel')


class TransportType(str, Enum):
    """传输类型"""
    WEBSOCKET = "websocket"
    HTTP = "http"
    STDIO = "stdio"
    IN_MEMORY = "in_memory"


@dataclass
class AgentEndpoint:
    """Agent 端点"""
    agent_id: str
    agent_name: str
    url: str
    transport: TransportType
    capabilities: List[str] = field(default_factory=list)
    is_local: bool = True
    last_seen: int = field(default_factory=lambda: int(time.time() * 1000))
    metadata: Dict[str, Any] = field(default_factory=dict)


class MessageRouter:
    """
    消息路由器
    根据目标 Agent ID 路由消息
    """
    
    def __init__(self):
        self._endpoints: Dict[str, AgentEndpoint] = {}
        self._local_agents: Set[str] = set()
        self._lock = threading.RLock()
    
    def register_endpoint(self, endpoint: AgentEndpoint):
        """注册端点"""
        with self._lock:
            self._endpoints[endpoint.agent_id] = endpoint
            if endpoint.is_local:
                self._local_agents.add(endpoint.agent_id)
            logger.debug(f"Endpoint registered: {endpoint.agent_id} -> {endpoint.url}")
    
    def unregister_endpoint(self, agent_id: str):
        """注销端点"""
        with self._lock:
            if agent_id in self._endpoints:
                del self._endpoints[agent_id]
                self._local_agents.discard(agent_id)
                logger.debug(f"Endpoint unregistered: {agent_id}")
    
    def get_endpoint(self, agent_id: str) -> Optional[AgentEndpoint]:
        """获取端点"""
        with self._lock:
            return self._endpoints.get(agent_id)
    
    def is_local_agent(self, agent_id: str) -> bool:
        """检查是否为本地 Agent"""
        with self._lock:
            return agent_id in self._local_agents
    
    def list_local_agents(self) -> List[AgentEndpoint]:
        """列出所有本地 Agent"""
        with self._lock:
            return [
                ep for agent_id, ep in self._endpoints.items()
                if agent_id in self._local_agents
            ]
    
    def find_agents_by_capability(self, capability: str) -> List[AgentEndpoint]:
        """根据能力查找 Agent"""
        with self._lock:
            return [
                ep for ep in self._endpoints.values()
                if capability in ep.capabilities
            ]


class Channel(ABC):
    """
    通信通道抽象基类
    """
    
    @abstractmethod
    async def send(self, endpoint: AgentEndpoint, message: Dict[str, Any]) -> bool:
        """发送消息"""
        pass
    
    @abstractmethod
    async def receive(self, agent_id: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """接收消息"""
        pass
    
    @abstractmethod
    async def close(self):
        """关闭通道"""
        pass


class InMemoryChannel(Channel):
    """
    内存通道
    用于本地 Agent 之间的通信
    """
    
    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._lock = threading.Lock()
        self._running = True
    
    def get_queue(self, agent_id: str) -> asyncio.Queue:
        """获取 Agent 的消息队列"""
        with self._lock:
            if agent_id not in self._queues:
                self._queues[agent_id] = asyncio.Queue()
            return self._queues[agent_id]
    
    async def send(self, endpoint: AgentEndpoint, message: Dict[str, Any]) -> bool:
        """发送消息到本地队列"""
        if not endpoint.is_local:
            logger.warning(f"Cannot use InMemoryChannel for remote agent: {endpoint.agent_id}")
            return False
        
        try:
            queue = self.get_queue(endpoint.agent_id)
            await queue.put(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {endpoint.agent_id}: {e}")
            return False
    
    async def receive(self, agent_id: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """从本地队列接收消息"""
        try:
            queue = self.get_queue(agent_id)
            if timeout:
                message = await asyncio.wait_for(queue.get(), timeout=timeout)
            else:
                message = await queue.get()
            return message
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Failed to receive message for {agent_id}: {e}")
            return None
    
    async def close(self):
        """关闭通道"""
        self._running = False
        with self._lock:
            self._queues.clear()


class WebSocketChannel(Channel):
    """
    WebSocket 通道
    用于远程 Agent 之间的通信
    """
    
    def __init__(self, client_factory: Optional[Callable] = None):
        """
        Args:
            client_factory: WebSocket 客户端工厂函数
        """
        self._client_factory = client_factory
        self._clients: Dict[str, Any] = {}  # agent_id -> websocket
        self._lock = threading.Lock()
        self._running = True
    
    def _get_or_create_client(self, endpoint: AgentEndpoint) -> Optional[Any]:
        """获取或创建 WebSocket 客户端"""
        with self._lock:
            if endpoint.agent_id in self._clients:
                return self._clients[endpoint.agent_id]
            
            if self._client_factory:
                try:
                    client = self._client_factory(endpoint.url)
                    self._clients[endpoint.agent_id] = client
                    return client
                except Exception as e:
                    logger.error(f"Failed to create client for {endpoint.agent_id}: {e}")
                    return None
            return None
    
    async def send(self, endpoint: AgentEndpoint, message: Dict[str, Any]) -> bool:
        """通过 WebSocket 发送消息"""
        try:
            client = self._get_or_create_client(endpoint)
            if not client:
                return False
            
            await client.send(json.dumps(message))
            return True
            
        except Exception as e:
            logger.error(f"WebSocket send failed to {endpoint.agent_id}: {e}")
            return False
    
    async def receive(self, agent_id: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """通过 WebSocket 接收消息"""
        client = self._clients.get(agent_id)
        if not client:
            logger.warning(f"No WebSocket connection for {agent_id}")
            return None

        try:
            if timeout:
                # 带超时的接收
                msg = await asyncio.wait_for(client.recv(), timeout=timeout)
            else:
                msg = await client.recv()

            if isinstance(msg, bytes):
                return json.loads(msg.decode("utf-8"))
            elif isinstance(msg, str):
                return json.loads(msg)
            else:
                return None
        except asyncio.TimeoutError:
            logger.debug(f"WebSocket receive timeout for {agent_id}")
            return None
        except Exception as e:
            logger.error(f"WebSocket receive failed for {agent_id}: {e}")
            # 连接可能断开，清理
            with self._lock:
                self._clients.pop(agent_id, None)
            return None
    
    async def close(self):
        """关闭所有 WebSocket 连接"""
        self._running = False
        with self._lock:
            for client in self._clients.values():
                try:
                    await client.close()
                except Exception:
                    pass
            self._clients.clear()


class MultiChannelRouter:
    """
    多通道路由器
    自动选择合适的通道进行通信
    """
    
    def __init__(self):
        self._router = MessageRouter()
        self._channels: Dict[TransportType, Channel] = {}
        self._lock = threading.Lock()
        
        # 默认添加内存通道
        self._channels[TransportType.IN_MEMORY] = InMemoryChannel()
    
    def register_channel(self, transport: TransportType, channel: Channel):
        """注册通道"""
        with self._lock:
            self._channels[transport] = channel
            logger.info(f"Channel registered: {transport.value}")
    
    def register_agent(
        self,
        agent_id: str,
        agent_name: str,
        url: str,
        transport: TransportType = TransportType.IN_MEMORY,
        capabilities: Optional[List[str]] = None,
        is_local: bool = True
    ):
        """注册 Agent"""
        endpoint = AgentEndpoint(
            agent_id=agent_id,
            agent_name=agent_name,
            url=url,
            transport=transport,
            capabilities=capabilities or [],
            is_local=is_local
        )
        self._router.register_endpoint(endpoint)
    
    async def send_message(
        self,
        source_id: str,
        target_id: str,
        message: Dict[str, Any]
    ) -> bool:
        """发送消息"""
        endpoint = self._router.get_endpoint(target_id)
        if not endpoint:
            logger.warning(f"Unknown target agent: {target_id}")
            return False
        
        channel = self._channels.get(endpoint.transport)
        if not channel:
            logger.error(f"No channel for transport: {endpoint.transport}")
            return False
        
        return await channel.send(endpoint, message)
    
    def is_local(self, agent_id: str) -> bool:
        """检查是否为本地 Agent"""
        return self._router.is_local_agent(agent_id)
    
    def find_by_capability(self, capability: str) -> List[AgentEndpoint]:
        """根据能力查找 Agent"""
        return self._router.find_agents_by_capability(capability)
