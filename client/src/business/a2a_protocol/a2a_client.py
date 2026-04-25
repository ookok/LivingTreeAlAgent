"""
A2A 客户端实现
用于向其他智能体发送请求

Author: LivingTreeAI Team
"""

import asyncio
import aiohttp
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
import logging

from . import MessageType, A2AMessage, Task, AgentInfo

logger = logging.getLogger(__name__)


class A2AHTTPClient:
    """
    A2A HTTP 客户端
    通过 HTTP 协议与其他智能体通信
    """
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.endpoints: Dict[str, str] = {}
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def add_endpoint(self, agent_id: str, endpoint: str):
        """添加智能体端点"""
        self.endpoints[agent_id] = endpoint
        logger.info(f"Endpoint added: {agent_id} -> {endpoint}")
    
    async def send_message(self, agent_id: str, message: A2AMessage) -> Optional[A2AMessage]:
        """发送消息"""
        if agent_id not in self.endpoints:
            logger.error(f"Unknown agent: {agent_id}")
            return None
        
        endpoint = self.endpoints[agent_id]
        
        try:
            async with self.session.post(
                f"{endpoint}/api/a2a/message",
                json=message.to_dict(),
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return A2AMessage.from_dict(data)
                else:
                    logger.error(f"Request failed: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Request error: {e}")
            return None
    
    async def send_task(self, agent_id: str, task: Task) -> Optional[str]:
        """发送任务并返回任务ID"""
        message = A2AMessage(
            method=MessageType.TASK_REQUEST,
            params={
                "task_type": task.task_type,
                "description": task.description,
                "params": task.params,
                "priority": task.priority
            }
        )
        
        response = await self.send_message(agent_id, message)
        if response and response.result:
            return response.result.get("task_id")
        return None
    
    async def cancel_task(self, agent_id: str, task_id: str) -> bool:
        """取消任务"""
        message = A2AMessage(
            method=MessageType.TASK_CANCEL,
            params={"task_id": task_id}
        )
        
        response = await self.send_message(agent_id, message)
        return response is not None and response.result is not None
    
    async def get_task_status(self, agent_id: str, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        endpoint = self.endpoints.get(agent_id)
        if not endpoint:
            return None
        
        try:
            async with self.session.get(
                f"{endpoint}/api/a2a/task/{task_id}",
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Get task status error: {e}")
            return None


class A2AWebSocketClient:
    """
    A2A WebSocket 客户端
    支持实时双向通信和流式响应
    """
    
    def __init__(self):
        self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self.connected = False
        self.callbacks: Dict[str, Callable] = {}
    
    async def connect(self, endpoint: str):
        """连接 WebSocket"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            self.websocket = await session.ws_connect(endpoint)
            self.connected = True
            logger.info(f"WebSocket connected: {endpoint}")
            
            # 启动接收循环
            asyncio.create_task(self._receive_loop())
    
    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info("WebSocket disconnected")
    
    async def _receive_loop(self):
        """接收消息循环"""
        while self.connected and self.websocket:
            msg = await self.websocket.receive()
            
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                message = A2AMessage.from_dict(data)
                
                # 调用回调
                if message.method:
                    callback = self.callbacks.get(message.method.value)
                    if callback:
                        await callback(message)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {msg.data}")
                break
    
    def register_callback(self, message_type: str, callback: Callable):
        """注册回调"""
        self.callbacks[message_type] = callback
    
    async def send(self, message: A2AMessage):
        """发送消息"""
        if self.websocket and self.connected:
            await self.websocket.send_str(json.dumps(message.to_dict()))
    
    async def subscribe_task(self, task_id: str):
        """订阅任务更新"""
        message = A2AMessage(
            method=MessageType.TASK_PROGRESS,
            params={"task_id": task_id, "action": "subscribe"}
        )
        await self.send(message)
    
    async def unsubscribe_task(self, task_id: str):
        """取消订阅"""
        message = A2AMessage(
            method=MessageType.TASK_PROGRESS,
            params={"task_id": task_id, "action": "unsubscribe"}
        )
        await self.send(message)


class A2AStreamClient:
    """
    A2A 流式客户端
    支持 Server-Sent Events 流式响应
    """
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def stream_task(self, agent_id: str, endpoint: str, 
                         task: Task) -> AsyncGenerator[Dict, None]:
        """
        流式执行任务
        
        Yields:
            Dict: 任务进度更新
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        async with self.session.post(
            f"{endpoint}/api/a2a/stream",
            json=task.to_dict()
        ) as response:
            async for line in response.content:
                if line:
                    data = json.loads(line.decode('utf-8'))
                    yield data


from typing import AsyncGenerator


__all__ = ['A2AHTTPClient', 'A2AWebSocketClient', 'A2AStreamClient']
