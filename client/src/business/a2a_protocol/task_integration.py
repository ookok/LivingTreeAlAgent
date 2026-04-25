"""
A2A 任务集成模块
A2A Protocol Integration for LivingTreeAI Task System

功能：
- Agent 注册与发现
- 任务转换 (TaskNode <-> A2A Task)
- 上下文传递 (TaskContext <-> SessionContext)
- 消息路由
"""

import json
import time
import asyncio
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

from core.logger import get_logger

logger = get_logger('a2a_integration')


# ========== 任务类型映射 ==========

class AgentType(str, Enum):
    """Agent 类型枚举"""
    PLANNER = "planner"           # 任务规划
    CODER = "coder"              # 代码生成
    REVIEWER = "reviewer"        # 代码审查
    RESEARCHER = "researcher"    # 研究分析
    WRITER = "writer"            # 文档写作
    ORCHESTRATOR = "orchestrator"  # 任务编排
    GENERAL = "general"          # 通用


# ========== 任务转换器 ==========

class TaskConverter:
    """
    任务类型转换器
    TaskNode <-> A2A Task
    """
    
    @staticmethod
    def from_task_node(node, task_context=None) -> 'A2ATask':
        """从 TaskNode 转换为 A2A Task"""
        from client.src.business.a2a_protocol import Task, TaskStatus as A2ATaskStatus
        
        # 状态映射
        status_map = {
            "pending": A2ATaskStatus.PENDING,
            "running": A2ATaskStatus.IN_PROGRESS,
            "completed": A2ATaskStatus.COMPLETED,
            "failed": A2ATaskStatus.FAILED,
            "waiting_approval": A2ATaskStatus.PENDING,
        }
        
        a2a_status = status_map.get(node.status.value, A2ATaskStatus.PENDING)
        
        # 输入数据
        input_data = {
            "prompt": node.prompt,
            "context_snapshot": node.context_snapshot,
            "tools_allowed": node.tools_allowed,
            "depth": node.depth,
            "complexity_score": node.complexity_score,
            "priority": node.priority.value if hasattr(node, 'priority') else 1,
        }
        
        # 添加上下文
        if task_context:
            input_data["variables"] = task_context.variables
            input_data["file_paths"] = task_context.file_paths
            input_data["results"] = task_context.results
        
        return A2ATask(
            task_id=node.task_id,
            task_type=node.prompt[:50] if node.prompt else "unnamed",
            description=node.prompt,
            status=a2a_status,
            input_data=input_data,
            context_id=task_context.root_task_id if task_context else None,
            parent_task_id=node.parent_id,
        )
    
    @staticmethod
    def to_task_node(a2a_task, depth: int = 0) -> 'TaskNode':
        """从 A2A Task 转换为 TaskNode"""
        from core.task_router import TaskNode, TaskStatus as RouterTaskStatus
        
        input_data = a2a_task.input_data
        
        node = TaskNode(
            task_id=a2a_task.task_id,
            prompt=input_data.get("prompt", a2a_task.description),
            context_snapshot=input_data.get("context_snapshot", {}),
            tools_allowed=input_data.get("tools_allowed", []),
            depth=depth,
            status=RouterTaskStatus.PENDING,
        )
        
        if input_data.get("parent_task_id"):
            node.parent_id = input_data["parent_task_id"]
        
        return node
    
    @staticmethod
    def from_task_context(context) -> 'SessionContext':
        """从 TaskContext 转换为 SessionContext"""
        from client.src.business.a2a_protocol import SessionContext
        
        return SessionContext(
            user_id=context.root_task_id or "default",
            context_id=context.root_task_id,
            conversation_history=[],
            user_preferences=context.variables,
            injected_context={
                "file_paths": context.file_paths,
                "results": context.results,
                "errors": context.errors,
            }
        )
    
    @staticmethod
    def to_task_context(session: 'SessionContext', root_task_id: str = "") -> 'TaskContext':
        """从 SessionContext 转换为 TaskContext"""
        from core.task_execution_engine import TaskContext
        
        ctx = TaskContext(
            root_task_id=root_task_id or session.context_id or "",
            original_task=session.user_preferences.get("original_task", ""),
        )
        
        # 恢复变量
        for key, value in session.user_preferences.items():
            ctx.set_var(key, value)
        
        # 恢复注入的上下文
        injected = session.injected_context
        if isinstance(injected, dict):
            ctx.file_paths = injected.get("file_paths", {})
            ctx.results = injected.get("results", {})
            ctx.errors = injected.get("errors", [])
        
        return ctx


# ========== Agent 适配器 ==========

@dataclass
class AgentAdapter:
    """Agent 适配器 - 桥接现有 Agent 与 A2A 协议"""
    agent_id: str
    agent_name: str
    agent_type: AgentType
    capabilities: List[str]
    handler: Callable  # async def handle_task(a2a_task) -> result
    is_local: bool = True
    is_busy: bool = False
    current_task_id: Optional[str] = None
    last_heartbeat: int = field(default_factory=lambda: int(time.time() * 1000))
    
    def to_endpoint(self) -> 'AgentEndpoint':
        """转换为 A2A 端点"""
        from client.src.business.a2a_protocol.channel import AgentEndpoint, TransportType
        
        return AgentEndpoint(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            url=f"in_memory://{self.agent_id}",
            transport=TransportType.IN_MEMORY if self.is_local else TransportType.WEBSOCKET,
            capabilities=self.capabilities,
            is_local=self.is_local,
        )


# ========== A2A 任务管理器 ==========

class A2ATaskManager:
    """
    A2A 任务管理器
    整合 LivingTreeAI 任务系统与 A2A 协议
    """
    
    def __init__(self, gateway, hmac_secret: str = ""):
        """
        Args:
            gateway: A2A 网关实例
            hmac_secret: HMAC 密钥
        """
        self._gateway = gateway
        self._hmac_secret = hmac_secret
        
        # Agent 注册表
        self._agents: Dict[str, AgentAdapter] = {}
        
        # 任务映射
        self._task_mapping: Dict[str, str] = {}  # a2a_task_id -> node_id
        
        # 回调
        self._task_callbacks: Dict[str, Callable] = {}
        
        # 锁
        self._lock = threading.RLock()
        
        # 注册默认处理器
        self._register_default_handlers()
        
        logger.info("A2A Task Manager initialized")
    
    def _register_default_handlers(self):
        """注册默认任务处理器"""
        # 注册到网关
        self._gateway.register_task_handler("code_generation", self._handle_code_generation)
        self._gateway.register_task_handler("code_review", self._handle_code_review)
        self._gateway.register_task_handler("planning", self._handle_planning)
        self._gateway.register_task_handler("research", self._handle_research)
        self._gateway.register_task_handler("writing", self._handle_writing)
    
    # ========== Agent 管理 ==========
    
    def register_agent(
        self,
        agent_id: str,
        agent_name: str,
        agent_type: AgentType,
        capabilities: List[str],
        handler: Callable,
        is_local: bool = True
    ) -> bool:
        """
        注册 Agent
        
        Args:
            agent_id: Agent ID
            agent_name: Agent 名称
            agent_type: Agent 类型
            capabilities: 能力列表
            handler: 任务处理函数
            is_local: 是否本地
        """
        with self._lock:
            adapter = AgentAdapter(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_type=agent_type,
                capabilities=capabilities,
                handler=handler,
                is_local=is_local,
            )
            
            self._agents[agent_id] = adapter
            
            # 注册到 A2A 网关
            self._gateway.register_agent(
                agent_id=agent_id,
                agent_name=agent_name,
                capabilities=capabilities,
                message_handler=None,
                is_local=is_local,
            )
            
            logger.info(f"Agent registered: {agent_id} ({agent_type.value})")
            return True
    
    def unregister_agent(self, agent_id: str) -> bool:
        """注销 Agent"""
        with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                self._gateway.unregister_agent(agent_id)
                logger.info(f"Agent unregistered: {agent_id}")
                return True
            return False
    
    def get_agent(self, agent_id: str) -> Optional[AgentAdapter]:
        """获取 Agent"""
        with self._lock:
            return self._agents.get(agent_id)
    
    def find_agents(self, capability: str, agent_type: Optional[AgentType] = None) -> List[AgentAdapter]:
        """查找 Agent"""
        with self._lock:
            result = [
                a for a in self._agents.values()
                if capability in a.capabilities and not a.is_busy
            ]
            
            if agent_type:
                result = [a for a in result if a.agent_type == agent_type]
            
            return result
    
    def get_available_agents(self) -> List[AgentAdapter]:
        """获取空闲 Agent"""
        with self._lock:
            return [a for a in self._agents.values() if not a.is_busy]
    
    # ========== 任务分发 ==========
    
    async def dispatch_task(
        self,
        node,
        task_context=None,
        preferred_agents: Optional[List[str]] = None
    ) -> str:
        """
        分发任务到 A2A 网络
        
        Args:
            node: TaskNode 任务节点
            task_context: 任务上下文
            preferred_agents: 优先选择的 Agent ID 列表
        
        Returns:
            a2a_task_id
        """
        from client.src.business.a2a_protocol import Task, SessionContext
        
        # 转换为 A2A Task
        a2a_task = TaskConverter.from_task_node(node, task_context)
        
        # 创建会话上下文
        session_context = TaskConverter.from_task_context(task_context) if task_context else None
        
        # 选择目标 Agent
        target_id = self._select_target_agent(node, preferred_agents)
        
        if not target_id:
            logger.warning(f"No available agent for task: {node.task_id}")
            return ""
        
        # 更新 Agent 状态
        agent = self._agents.get(target_id)
        if agent:
            agent.is_busy = True
            agent.current_task_id = a2a_task.task_id
        
        # 记录映射
        self._task_mapping[a2a_task.task_id] = node.task_id
        
        # 发送到 A2A 网络
        success = await self._gateway.send_task(
            target_id=target_id,
            task=a2a_task,
            session_context=session_context,
        )
        
        if success:
            logger.info(f"Task dispatched: {node.task_id} -> {target_id}")
        else:
            logger.error(f"Failed to dispatch task: {node.task_id}")
            if agent:
                agent.is_busy = False
        
        return a2a_task.task_id if success else ""
    
    def _select_target_agent(
        self,
        node,
        preferred_agents: Optional[List[str]] = None
    ) -> Optional[str]:
        """选择目标 Agent"""
        # 优先使用指定的 Agent
        if preferred_agents:
            for agent_id in preferred_agents:
                agent = self._agents.get(agent_id)
                if agent and not agent.is_busy:
                    return agent_id
        
        # 根据能力选择
        capabilities = []
        if hasattr(node, 'tools_allowed') and node.tools_allowed:
            capabilities = node.tools_allowed
        elif hasattr(node, 'prompt') and node.prompt:
            # 简单关键词匹配
            prompt_lower = node.prompt.lower()
            if any(k in prompt_lower for k in ['code', 'function', 'class', 'implement']):
                capabilities.append('code_generation')
            if any(k in prompt_lower for k in ['review', 'check', 'analyze']):
                capabilities.append('code_review')
            if any(k in prompt_lower for k in ['plan', 'design', 'architecture']):
                capabilities.append('planning')
        
        # 查找匹配的空闲 Agent
        for cap in capabilities:
            agents = self.find_agents(cap)
            if agents:
                return agents[0].agent_id
        
        # 返回任意空闲 Agent
        available = self.get_available_agents()
        if available:
            return available[0].agent_id
        
        return None
    
    # ========== 任务回调处理 ==========
    
    async def _handle_code_generation(self, task) -> Dict[str, Any]:
        """处理代码生成任务"""
        logger.info(f"Code generation task: {task.task_id}")
        return {"status": "handled", "type": "code_generation"}
    
    async def _handle_code_review(self, task) -> Dict[str, Any]:
        """处理代码审查任务"""
        logger.info(f"Code review task: {task.task_id}")
        return {"status": "handled", "type": "code_review"}
    
    async def _handle_planning(self, task) -> Dict[str, Any]:
        """处理规划任务"""
        logger.info(f"Planning task: {task.task_id}")
        return {"status": "handled", "type": "planning"}
    
    async def _handle_research(self, task) -> Dict[str, Any]:
        """处理研究任务"""
        logger.info(f"Research task: {task.task_id}")
        return {"status": "handled", "type": "research"}
    
    async def _handle_writing(self, task) -> Dict[str, Any]:
        """处理写作任务"""
        logger.info(f"Writing task: {task.task_id}")
        return {"status": "handled", "type": "writing"}
    
    # ========== 即时唤醒 ==========
    
    async def wake_agent(
        self,
        agent_id: str,
        trigger: str,
        data: Dict[str, Any]
    ) -> bool:
        """唤醒指定 Agent"""
        return await self._gateway.instant_wake(agent_id, {
            "trigger": trigger,
            "data": data
        })
    
    # ========== 会话管理 ==========
    
    def create_session(
        self,
        user_id: str,
        participants: List[str],
        initial_context: Optional[Dict[str, Any]] = None
    ):
        """创建 A2A 会话"""
        return self._gateway.create_session(user_id, participants, initial_context)
    
    def inject_context(
        self,
        session_id: str,
        context: Dict[str, Any],
        agent_id: str
    ) -> bool:
        """注入会话上下文"""
        return self._gateway._session_manager.inject_session(session_id, context, agent_id)
    
    # ========== 状态管理 ==========
    
    def update_agent_status(self, agent_id: str, is_busy: bool, task_id: str = None):
        """更新 Agent 状态"""
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].is_busy = is_busy
                self._agents[agent_id].current_task_id = task_id
                self._agents[agent_id].last_heartbeat = int(time.time() * 1000)
    
    def get_task_mapping(self, a2a_task_id: str) -> Optional[str]:
        """获取任务映射"""
        return self._task_mapping.get(a2a_task_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = len(self._agents)
            busy = sum(1 for a in self._agents.values() if a.is_busy)
            return {
                "total_agents": total,
                "busy_agents": busy,
                "available_agents": total - busy,
                "pending_tasks": len(self._task_mapping),
                "by_type": {
                    atype.value: len([
                        a for a in self._agents.values()
                        if a.agent_type == atype
                    ])
                    for atype in AgentType
                }
            }


# ========== 便捷工厂函数 ==========

def create_a2a_task_manager(
    agent_id: str = "livingtree",
    agent_name: str = "LivingTree",
    hmac_secret: str = "",
    storage_dir: str = None
) -> A2ATaskManager:
    """
    创建 A2A 任务管理器
    
    Args:
        agent_id: 当前 Agent ID
        agent_name: 当前 Agent 名称
        hmac_secret: HMAC 密钥
        storage_dir: 会话存储目录
    
    Returns:
        A2ATaskManager 实例
    """
    from client.src.business.a2a_protocol.gateway import create_a2a_gateway
    
    gateway = create_a2a_gateway(
        agent_id=agent_id,
        agent_name=agent_name,
        hmac_secret=hmac_secret,
        storage_dir=storage_dir,
    )
    
    return A2ATaskManager(gateway, hmac_secret)
