"""
A2A 协议核心模块
Agent-to-Agent 通信协议，实现多智能体协作

协议特点：
- JSON-RPC 2.0 通信格式
- 支持任务委托、状态同步、结果返回
- 内置错误处理和重试机制
- 支持流式响应 (Server-Sent Events)

Author: LivingTreeAI Team
"""

import asyncio
import json
import uuid
import time
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """消息类型"""
    # 任务相关
    TASK_REQUEST = "task_request"          # 任务请求
    TASK_RESPONSE = "task_response"        # 任务响应
    TASK_CANCEL = "task_cancel"            # 取消任务
    TASK_PROGRESS = "task_progress"        # 任务进度
    
    # 协作相关
    HAND_SHAKE = "handshake"               # 握手
    HEART_BEAT = "heartbeat"               # 心跳
    STATE_SYNC = "state_sync"              # 状态同步
    
    # 错误相关
    ERROR = "error"                         # 错误消息
    

class AgentCapability(Enum):
    """智能体能力"""
    CODE_GENERATION = "code_generation"    # 代码生成
    CODE_REVIEW = "code_review"            # 代码审查
    TESTING = "testing"                    # 测试
    DEBUGGING = "debugging"                # 调试
    DEPLOYMENT = "deployment"              # 部署
    ANALYSIS = "analysis"                  # 分析
    PLANNING = "planning"                  # 规划
    ORCHESTRATION = "orchestration"        # 编排


@dataclass
class AgentInfo:
    """智能体信息"""
    agent_id: str
    name: str
    capabilities: List[AgentCapability]
    status: str = "online"  # online, busy, offline
    description: str = ""
    version: str = "1.0.0"
    endpoint: str = ""  # A2A 端点
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "capabilities": [c.value for c in self.capabilities],
            "status": self.status,
            "description": self.description,
            "version": self.version,
            "endpoint": self.endpoint,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentInfo':
        return cls(
            agent_id=data["agent_id"],
            name=data["name"],
            capabilities=[AgentCapability(c) for c in data["capabilities"]],
            status=data.get("status", "online"),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            endpoint=data.get("endpoint", ""),
            metadata=data.get("metadata", {})
        )


@dataclass
class A2AMessage:
    """A2A 消息格式 (JSON-RPC 2.0)"""
    jsonrpc: str = "2.0"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    method: Optional[MessageType] = None
    params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        msg = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.method:
            msg["method"] = self.method.value
            msg["params"] = self.params
        if self.result is not None:
            msg["result"] = self.result
        if self.error:
            msg["error"] = self.error
        return msg
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'A2AMessage':
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id", str(uuid.uuid4())),
            method=MessageType(data["method"]) if "method" in data else None,
            params=data.get("params", {}),
            result=data.get("result"),
            error=data.get("error")
        )


@dataclass
class Task:
    """任务"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = ""
    description: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # 0-9, 9最高
    status: str = "pending"  # pending, running, completed, failed, cancelled
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    progress: float = 0.0  # 0.0 - 1.0
    subtasks: List['Task'] = field(default_factory=list)
    assigned_agent: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "params": self.params,
            "priority": self.priority,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
            "subtasks": [s.to_dict() for s in self.subtasks],
            "assigned_agent": self.assigned_agent
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Task':
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            description=data["description"],
            params=data.get("params", {}),
            priority=data.get("priority", 0),
            status=data.get("status", "pending"),
            result=data.get("result"),
            error=data.get("error"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            progress=data.get("progress", 0.0),
            subtasks=[cls.from_dict(s) for s in data.get("subtasks", [])],
            assigned_agent=data.get("assigned_agent")
        )
    
    def get_duration(self) -> float:
        """获取任务持续时间"""
        end = self.completed_at or time.time()
        start = self.started_at or self.created_at
        return end - start


class A2AProtocol:
    """
    A2A 协议处理器
    
    支持：
    - 消息编解码
    - 任务委托
    - 状态同步
    - 心跳检测
    """
    
    def __init__(self, agent_info: AgentInfo):
        self.agent_info = agent_info
        self.tasks: Dict[str, Task] = {}
        self.pending_messages: List[A2AMessage] = []
        self.message_handlers: Dict[MessageType, Callable] = {}
        self._setup_default_handlers()
    
    def _setup_default_handlers(self):
        """设置默认处理器"""
        self.register_handler(MessageType.TASK_REQUEST, self._handle_task_request)
        self.register_handler(MessageType.TASK_CANCEL, self._handle_task_cancel)
        self.register_handler(MessageType.HEART_BEAT, self._handle_heartbeat)
        self.register_handler(MessageType.STATE_SYNC, self._handle_state_sync)
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器"""
        self.message_handlers[msg_type] = handler
    
    async def send_message(self, message: A2AMessage, endpoint: str) -> Optional[A2AMessage]:
        """发送消息（需子类实现具体传输）"""
        raise NotImplementedError
    
    async def receive_message(self, data: Dict) -> A2AMessage:
        """接收并处理消息"""
        message = A2AMessage.from_dict(data)
        
        if message.method and message.method in self.message_handlers:
            handler = self.message_handlers[message.method]
            result = await handler(message)
            return result
        else:
            return A2AMessage(
                id=message.id,
                error={"code": -32601, "message": "Method not found"}
            )
    
    async def create_task(self, task_type: str, description: str, 
                         params: Dict = None, priority: int = 0) -> Task:
        """创建任务"""
        task = Task(
            task_type=task_type,
            description=description,
            params=params or {},
            priority=priority
        )
        self.tasks[task.task_id] = task
        logger.info(f"Task created: {task.task_id} - {description}")
        return task
    
    async def _handle_task_request(self, message: A2AMessage) -> A2AMessage:
        """处理任务请求"""
        params = message.params
        task = await self.create_task(
            task_type=params.get("task_type"),
            description=params.get("description"),
            params=params.get("params", {}),
            priority=params.get("priority", 0)
        )
        return A2AMessage(
            id=message.id,
            result={"task_id": task.task_id, "status": "accepted"}
        )
    
    async def _handle_task_cancel(self, message: A2AMessage) -> A2AMessage:
        """处理任务取消"""
        task_id = message.params.get("task_id")
        if task_id in self.tasks:
            self.tasks[task_id].status = "cancelled"
            self.tasks[task_id].updated_at = time.time()
            return A2AMessage(
                id=message.id,
                result={"task_id": task_id, "status": "cancelled"}
            )
        return A2AMessage(
            id=message.id,
            error={"code": -32001, "message": "Task not found"}
        )
    
    async def _handle_heartbeat(self, message: A2AMessage) -> A2AMessage:
        """处理心跳"""
        return A2AMessage(
            id=message.id,
            result={
                "agent_id": self.agent_info.agent_id,
                "status": self.agent_info.status,
                "active_tasks": len([t for t in self.tasks.values() if t.status == "running"])
            }
        )
    
    async def _handle_state_sync(self, message: A2AMessage) -> A2AMessage:
        """处理状态同步"""
        return A2AMessage(
            id=message.id,
            result={
                "agent_info": self.agent_info.to_dict(),
                "tasks": [t.to_dict() for t in self.tasks.values()]
            }
        )


class AgentRegistry:
    """
    智能体注册表
    管理所有已知智能体的信息
    """
    
    def __init__(self):
        self.agents: Dict[str, AgentInfo] = {}
        self.discovery_enabled = True
    
    def register(self, agent: AgentInfo):
        """注册智能体"""
        self.agents[agent.agent_id] = agent
        logger.info(f"Agent registered: {agent.name} ({agent.agent_id})")
    
    def unregister(self, agent_id: str):
        """注销智能体"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info(f"Agent unregistered: {agent_id}")
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """获取智能体"""
        return self.agents.get(agent_id)
    
    def find_agents_by_capability(self, capability: AgentCapability) -> List[AgentInfo]:
        """按能力查找智能体"""
        return [
            agent for agent in self.agents.values()
            if agent.status == "online" and capability in agent.capabilities
        ]
    
    def get_all_agents(self) -> List[AgentInfo]:
        """获取所有智能体"""
        return list(self.agents.values())


class TaskOrchestrator:
    """
    任务编排器
    负责任务分解、分配、执行调度
    """
    
    def __init__(self, registry: AgentRegistry, protocol: A2AProtocol):
        self.registry = registry
        self.protocol = protocol
        self.task_queue: List[Task] = []
        self.running_tasks: Dict[str, Task] = {}
    
    async def decompose_task(self, task: Task) -> List[Task]:
        """任务分解（简单实现）"""
        # 实际使用时可用 LLM 分解
        return [task]
    
    async def assign_task(self, task: Task, agent: AgentInfo) -> bool:
        """分配任务"""
        if agent.status != "online":
            logger.warning(f"Agent {agent.agent_id} is not online")
            return False
        
        # 发送任务请求
        message = A2AMessage(
            method=MessageType.TASK_REQUEST,
            params={
                "task_type": task.task_type,
                "description": task.description,
                "params": task.params,
                "priority": task.priority
            }
        )
        
        # 实际发送逻辑需子类实现
        task.assigned_agent = agent.agent_id
        self.running_tasks[task.task_id] = task
        
        return True
    
    async def execute_workflow(self, workflow: List[Dict]) -> List[Any]:
        """执行工作流"""
        results = []
        for step in workflow:
            task = await self.protocol.create_task(
                task_type=step.get("type"),
                description=step.get("description"),
                params=step.get("params", {}),
                priority=step.get("priority", 0)
            )
            
            # 查找合适的智能体
            agents = self.registry.find_agents_by_capability(
                AgentCapability(step.get("capability", "code_generation"))
            )
            
            if agents:
                await self.assign_task(task, agents[0])
                results.append({"task_id": task.task_id, "status": "assigned"})
            else:
                results.append({"error": "No available agent"})
        
        return results
    
    def get_task_status(self, task_id: str) -> Optional[str]:
        """获取任务状态"""
        task = self.running_tasks.get(task_id) or self.protocol.tasks.get(task_id)
        return task.status if task else None
    
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return list(self.protocol.tasks.values())


class A2AServer:
    """
    A2A 服务器
    提供 HTTP + WebSocket 接口接收外部 Agent 请求

    HTTP 端点：
    - POST /a2a/message        — 发送 JSON-RPC 消息
    - GET  /a2a/status         — 获取服务器状态
    - GET  /a2a/agents         — 获取已注册智能体列表
    - GET  /a2a/tasks          — 获取任务列表
    - WebSocket /a2a/ws        — 双向实时通信
    """

    def __init__(self, agent_info: AgentInfo, host: str = "0.0.0.0", port: int = 8080):
        self.agent_info = agent_info
        self.protocol = A2AProtocol(agent_info)
        self.registry = AgentRegistry()
        self.orchestrator = TaskOrchestrator(self.registry, self.protocol)
        self.host = host
        self.port = port
        self._running = False
        self._app = None       # aiohttp web.Application
        self._runner = None    # aiohttp web.AppRunner
        self._site = None      # aiohttp web.TCPSite
        self._ws_clients: set = set()  # WebSocket 连接集合

    async def start(self):
        """启动 HTTP + WebSocket 服务器"""
        from aiohttp import web

        self._app = web.Application()
        self._app.router.add_post('/a2a/message', self._handle_http_message)
        self._app.router.add_get('/a2a/status', self._handle_status)
        self._app.router.add_get('/a2a/agents', self._handle_agents)
        self._app.router.add_get('/a2a/tasks', self._handle_tasks)
        self._app.router.add_get('/a2a/ws', self._handle_websocket)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        self._running = True
        self.agent_info.status = "online"
        logger.info(f"A2A Server started on http://{self.host}:{self.port}")
        logger.info(f"  HTTP:  http://{self.host}:{self.port}/a2a/message")
        logger.info(f"  WS:    ws://{self.host}:{self.port}/a2a/ws")
        logger.info(f"  Agent: {self.agent_info.name} ({self.agent_info.agent_id})")

    async def stop(self):
        """停止服务器"""
        self._running = False
        self.agent_info.status = "offline"

        # 关闭所有 WebSocket 连接
        for ws in list(self._ws_clients):
            try:
                await ws.close()
            except Exception:
                pass
        self._ws_clients.clear()

        if self._runner:
            await self._runner.cleanup()
            self._runner = None

        logger.info("A2A Server stopped")

    def is_running(self) -> bool:
        """检查服务器状态"""
        return self._running

    # ── HTTP 处理器 ──────────────────────────────────────────────────

    async def _handle_http_message(self, request) -> 'web.Response':
        """处理 HTTP JSON-RPC 消息"""
        from aiohttp import web
        try:
            data = await request.json()
        except Exception:
            return web.json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error: invalid JSON"}
            })

        # 处理消息
        response_msg = await self.protocol.receive_message(data)
        return web.json_response(response_msg.to_dict())

    async def _handle_status(self, request) -> 'web.Response':
        """获取服务器状态"""
        from aiohttp import web
        return web.json_response({
            "agent_id": self.agent_info.agent_id,
            "name": self.agent_info.name,
            "status": self.agent_info.status,
            "version": self.agent_info.version,
            "capabilities": [c.value for c in self.agent_info.capabilities],
            "running": self._running,
            "active_tasks": len([t for t in self.protocol.tasks.values() if t.status == "running"]),
            "total_tasks": len(self.protocol.tasks),
            "registered_agents": len(self.registry.agents),
            "ws_clients": len(self._ws_clients),
        })

    async def _handle_agents(self, request) -> 'web.Response':
        """获取已注册智能体列表"""
        from aiohttp import web
        return web.json_response({
            "agents": [a.to_dict() for a in self.registry.get_all_agents()]
        })

    async def _handle_tasks(self, request) -> 'web.Response':
        """获取任务列表"""
        from aiohttp import web
        return web.json_response({
            "tasks": [t.to_dict() for t in self.protocol.tasks.values()]
        })

    # ── WebSocket 处理器 ─────────────────────────────────────────────

    async def _handle_websocket(self, request) -> 'web.Response':
        """处理 WebSocket 连接"""
        from aiohttp import web as aiohttp_web

        ws = aiohttp_web.WebSocketResponse()
        await ws.prepare(request)
        self._ws_clients.add(ws)
        logger.info(f"WebSocket client connected: {request.remote}")

        try:
            async for msg in ws:
                if msg.type == aiohttp_web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        response_msg = await self.protocol.receive_message(data)
                        await ws.send_json(response_msg.to_dict())
                    except json.JSONDecodeError:
                        await ws.send_json({
                            "jsonrpc": "2.0",
                            "error": {"code": -32700, "message": "Parse error"}
                        })
                elif msg.type == aiohttp_web.WSMsgType.ERROR:
                    logger.warning(f"WebSocket error: {ws.exception()}")
        finally:
            self._ws_clients.discard(ws)
            logger.info(f"WebSocket client disconnected: {request.remote}")

        return ws


class A2AClient:
    """
    A2A 客户端
    用于向其他智能体发送 HTTP/WebSocket 请求

    支持两种通信模式：
    - HTTP: POST/GET 请求（简单、无状态）
    - WebSocket: 双向实时通信（持续连接）
    """

    def __init__(self, agent_info: AgentInfo, timeout: float = 30.0):
        self.agent_info = agent_info
        self.protocol = A2AProtocol(agent_info)
        self.endpoints: Dict[str, str] = {}  # agent_id -> endpoint (http://host:port)
        self.timeout = timeout
        self._session = None  # aiohttp ClientSession

    def add_endpoint(self, agent_id: str, endpoint: str):
        """添加端点（完整 URL，如 http://localhost:8081）"""
        self.endpoints[agent_id] = endpoint.rstrip("/")

    async def _get_session(self):
        """获取/创建 aiohttp 会话"""
        if self._session is None or self._session.closed:
            import aiohttp
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"Content-Type": "application/json"},
            )
        return self._session

    async def close(self):
        """关闭客户端"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def send_task_request(self, agent_id: str, task: Task) -> Optional[A2AMessage]:
        """发送任务请求到目标 Agent"""
        if agent_id not in self.endpoints:
            logger.error(f"Unknown agent: {agent_id}")
            return None

        message = A2AMessage(
            method=MessageType.TASK_REQUEST,
            params={
                "task_type": task.task_type,
                "description": task.description,
                "params": task.params,
                "priority": task.priority,
            }
        )

        return await self._send_http(agent_id, message)

    async def get_agent_status(self, agent_id: str) -> Optional[Dict]:
        """获取目标 Agent 的状态"""
        if agent_id not in self.endpoints:
            logger.error(f"Unknown agent: {agent_id}")
            return None

        session = await self._get_session()
        url = f"{self.endpoints[agent_id]}/a2a/status"

        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"Status request failed: HTTP {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Status request error: {e}")
            return None

    async def cancel_task(self, agent_id: str, task_id: str) -> bool:
        """取消目标 Agent 上的任务"""
        if agent_id not in self.endpoints:
            logger.error(f"Unknown agent: {agent_id}")
            return False

        message = A2AMessage(
            method=MessageType.TASK_CANCEL,
            params={"task_id": task_id},
        )

        response = await self._send_http(agent_id, message)
        if response and response.result:
            return response.result.get("status") == "cancelled"
        return False

    async def send_message(self, message: A2AMessage, endpoint: str) -> Optional[A2AMessage]:
        """发送通用 JSON-RPC 消息到指定端点"""
        session = await self._get_session()
        url = f"{endpoint.rstrip('/')}/a2a/message"

        try:
            async with session.post(url, json=message.to_dict()) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return A2AMessage.from_dict(data)
                else:
                    error_text = await resp.text()
                    logger.error(f"Message send failed: HTTP {resp.status} - {error_text[:200]}")
                    return None
        except Exception as e:
            logger.error(f"Message send error: {e}")
            return None

    async def _send_http(self, agent_id: str, message: A2AMessage) -> Optional[A2AMessage]:
        """通过 HTTP 发送消息"""
        return await self.send_message(message, self.endpoints[agent_id])


__all__ = [
    'MessageType',
    'AgentCapability',
    'AgentInfo',
    'A2AMessage',
    'Task',
    'A2AProtocol',
    'AgentRegistry',
    'TaskOrchestrator',
    'A2AServer',
    'A2AClient'
]
