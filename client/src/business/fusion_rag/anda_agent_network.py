"""
Anda 代理网络设计借鉴模块
============================

借鉴 Anda 框架的可组合代理网络设计理念，实现：
1. 代理网络架构
2. 自主记忆机制
3. 跨行业代理协作
4. 动态任务分配

作者: LivingTreeAI Team
日期: 2026-04-30
版本: 1.0.0
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from loguru import logger


class AgentRole(Enum):
    """代理角色"""
    ANALYZER = "analyzer"           # 分析代理
    REASONER = "reasoner"           # 推理代理
    RETRIEVER = "retriever"         # 检索代理
    WRITER = "writer"               # 写作代理
    EXECUTOR = "executor"           # 执行代理
    COORDINATOR = "coordinator"     # 协调代理
    SPECIALIST = "specialist"       # 专家代理


class AgentStatus(Enum):
    """代理状态"""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


@dataclass
class AgentInfo:
    """代理信息"""
    id: str
    name: str
    role: AgentRole
    status: AgentStatus = AgentStatus.IDLE
    capabilities: List[str] = field(default_factory=list)
    expertise: List[str] = field(default_factory=list)
    memory_keys: List[str] = field(default_factory=list)
    success_rate: float = 1.0
    avg_latency: float = 0.0
    last_active: float = 0.0


@dataclass
class TaskRequest:
    """任务请求"""
    id: str
    type: str
    payload: Dict[str, Any]
    required_capabilities: List[str] = field(default_factory=list)
    priority: int = 0
    max_retries: int = 3


@dataclass
class NetworkMessage:
    """网络消息"""
    sender_id: str
    receiver_id: str
    message_type: str
    payload: Dict[str, Any]
    timestamp: float = 0.0


class AndaAgentNetwork:
    """
    Anda 风格的代理网络
    
    借鉴 Anda 框架的核心设计理念：
    1. 可组合性 - 代理可以组合形成更复杂的能力
    2. 自主记忆 - 支持永久记忆机制
    3. 跨行业连接 - 支持不同领域代理协作
    4. 动态路由 - 智能任务分配
    """
    
    def __init__(self):
        """初始化代理网络"""
        self._agents: Dict[str, AgentInfo] = {}
        self._agents_by_role: Dict[AgentRole, List[str]] = defaultdict(list)
        self._network_graph: Dict[str, List[str]] = {}  # 代理连接图
        self._memory_store: Dict[str, Any] = {}  # 共享记忆存储
        self._task_queue: List[TaskRequest] = []
        
        # 初始化内置代理
        self._initialize_default_agents()
        
        logger.info("[AndaAgentNetwork] 初始化完成")
    
    def _initialize_default_agents(self):
        """初始化默认代理"""
        default_agents = [
            AgentInfo(
                id="agent-analyzer-001",
                name="文档分析代理",
                role=AgentRole.ANALYZER,
                capabilities=["document_analysis", "content_extraction", "summary"],
                expertise=["pdf", "document", "research"]
            ),
            AgentInfo(
                id="agent-reasoner-001",
                name="推理代理",
                role=AgentRole.REASONER,
                capabilities=["reasoning", "logic", "inference"],
                expertise=["complex_query", "multi_step"]
            ),
            AgentInfo(
                id="agent-retriever-001",
                name="检索代理",
                role=AgentRole.RETRIEVER,
                capabilities=["search", "knowledge_retrieval", "information_gathering"],
                expertise=["database", "web_search", "document"]
            ),
            AgentInfo(
                id="agent-writer-001",
                name="写作代理",
                role=AgentRole.WRITER,
                capabilities=["content_generation", "writing", "summarization"],
                expertise=["report", "article", "documentation"]
            ),
            AgentInfo(
                id="agent-executor-001",
                name="执行代理",
                role=AgentRole.EXECUTOR,
                capabilities=["code_execution", "tool_use", "action"],
                expertise=["python", "cli", "automation"]
            ),
            AgentInfo(
                id="agent-coordinator-001",
                name="协调代理",
                role=AgentRole.COORDINATOR,
                capabilities=["task_coordination", "workflow", "orchestration"],
                expertise=["multi_agent", "complex_task"]
            )
        ]
        
        for agent in default_agents:
            self.register_agent(agent)
    
    def register_agent(self, agent_info: AgentInfo):
        """注册代理"""
        self._agents[agent_info.id] = agent_info
        self._agents_by_role[agent_info.role].append(agent_info.id)
        
        # 初始化网络连接
        if agent_info.id not in self._network_graph:
            self._network_graph[agent_info.id] = []
        
        logger.info(f"[AndaAgentNetwork] 代理注册成功: {agent_info.name} ({agent_info.role.value})")
    
    def connect_agents(self, agent_id1: str, agent_id2: str):
        """建立代理间连接"""
        if agent_id1 in self._network_graph and agent_id2 not in self._network_graph[agent_id1]:
            self._network_graph[agent_id1].append(agent_id2)
        
        if agent_id2 in self._network_graph and agent_id1 not in self._network_graph[agent_id2]:
            self._network_graph[agent_id2].append(agent_id1)
        
        logger.info(f"[AndaAgentNetwork] 建立连接: {agent_id1} <-> {agent_id2}")
    
    def select_agent(self, task: TaskRequest) -> Optional[str]:
        """
        根据任务选择最佳代理
        
        Args:
            task: 任务请求
            
        Returns:
            最佳代理ID
        """
        candidates = []
        
        # 根据能力需求筛选
        for agent_id, agent_info in self._agents.items():
            if agent_info.status != AgentStatus.IDLE:
                continue
            
            # 检查能力匹配
            if task.required_capabilities:
                has_capabilities = all(
                    cap in agent_info.capabilities
                    for cap in task.required_capabilities
                )
                if not has_capabilities:
                    continue
            
            # 计算匹配度
            score = self._calculate_match_score(agent_info, task)
            candidates.append((agent_id, score))
        
        # 按优先级排序
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        if candidates:
            best_agent = candidates[0][0]
            logger.info(f"[AndaAgentNetwork] 选择代理: {best_agent}")
            return best_agent
        
        return None
    
    def _calculate_match_score(self, agent_info: AgentInfo, task: TaskRequest) -> float:
        """计算代理匹配度"""
        score = 0.0
        
        # 能力匹配
        if task.required_capabilities:
            matched_caps = sum(
                1 for cap in task.required_capabilities
                if cap in agent_info.capabilities
            )
            score += (matched_caps / len(task.required_capabilities)) * 0.5
        
        # 专业知识匹配
        for expertise in agent_info.expertise:
            if expertise.lower() in str(task.payload).lower():
                score += 0.1
        
        # 成功率加成
        score += agent_info.success_rate * 0.3
        
        # 优先级加成
        score += task.priority * 0.01
        
        return score
    
    async def dispatch_task(self, task: TaskRequest) -> Dict[str, Any]:
        """
        分发任务到代理
        
        Args:
            task: 任务请求
            
        Returns:
            执行结果
        """
        import time
        
        # 选择代理
        agent_id = self.select_agent(task)
        if not agent_id:
            return {"success": False, "error": "没有找到合适的代理"}
        
        agent_info = self._agents[agent_id]
        agent_info.status = AgentStatus.BUSY
        agent_info.last_active = time.time()
        
        try:
            # 执行任务
            result = await self._execute_task(agent_info, task)
            
            # 更新代理统计
            self._update_agent_stats(agent_id, result["latency"], result["success"])
            
            return result
            
        finally:
            agent_info.status = AgentStatus.IDLE
    
    async def _execute_task(self, agent_info: AgentInfo, task: TaskRequest) -> Dict[str, Any]:
        """执行任务"""
        import time
        start_time = time.time()
        
        # 模拟代理执行
        await asyncio.sleep(0.3)
        
        latency = time.time() - start_time
        
        # 根据代理角色生成响应
        responses = {
            AgentRole.ANALYZER: f"文档分析完成: {task.payload.get('query', '')}",
            AgentRole.REASONER: f"推理完成，结论已生成",
            AgentRole.RETRIEVER: f"检索完成，找到相关信息",
            AgentRole.WRITER: f"内容生成完成",
            AgentRole.EXECUTOR: f"执行完成",
            AgentRole.COORDINATOR: f"任务协调完成",
            AgentRole.SPECIALIST: f"专业分析完成"
        }
        
        return {
            "success": True,
            "agent_id": agent_info.id,
            "agent_name": agent_info.name,
            "response": responses.get(agent_info.role, "任务完成"),
            "latency": latency,
            "task_id": task.id
        }
    
    def _update_agent_stats(self, agent_id: str, latency: float, success: bool):
        """更新代理统计"""
        agent_info = self._agents.get(agent_id)
        if not agent_info:
            return
        
        # 更新成功率（滑动窗口）
        if success:
            agent_info.success_rate = min(1.0, agent_info.success_rate * 0.9 + 0.1)
        else:
            agent_info.success_rate = max(0.0, agent_info.success_rate * 0.9 - 0.1)
        
        # 更新平均延迟
        agent_info.avg_latency = (agent_info.avg_latency * 0.9 + latency * 0.1)
    
    async def send_message(self, sender_id: str, receiver_id: str, message_type: str, payload: Dict[str, Any]):
        """发送网络消息"""
        message = NetworkMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            payload=payload,
            timestamp=time.time()
        )
        
        # 处理消息
        await self._process_message(message)
    
    async def _process_message(self, message: NetworkMessage):
        """处理网络消息"""
        logger.info(f"[AndaAgentNetwork] 消息: {message.sender_id} -> {message.receiver_id}")
        
        # 消息类型处理
        if message.message_type == "memory_request":
            await self._handle_memory_request(message)
        elif message.message_type == "task_delegation":
            await self._handle_task_delegation(message)
        elif message.message_type == "status_update":
            await self._handle_status_update(message)
    
    async def _handle_memory_request(self, message: NetworkMessage):
        """处理记忆请求"""
        memory_key = message.payload.get("key")
        if memory_key in self._memory_store:
            # 回复记忆内容
            pass
    
    async def _handle_task_delegation(self, message: NetworkMessage):
        """处理任务委托"""
        task_data = message.payload.get("task")
        if task_data:
            task = TaskRequest(
                id=task_data.get("id", ""),
                type=task_data.get("type", ""),
                payload=task_data.get("payload", {}),
                required_capabilities=task_data.get("capabilities", []),
                priority=task_data.get("priority", 0)
            )
            await self.dispatch_task(task)
    
    async def _handle_status_update(self, message: NetworkMessage):
        """处理状态更新"""
        status = message.payload.get("status")
        if message.receiver_id in self._agents:
            self._agents[message.receiver_id].status = AgentStatus(status)
    
    def store_memory(self, key: str, value: Any):
        """存储共享记忆"""
        self._memory_store[key] = value
        logger.info(f"[AndaAgentNetwork] 存储记忆: {key}")
    
    def retrieve_memory(self, key: str) -> Optional[Any]:
        """检索共享记忆"""
        return self._memory_store.get(key)
    
    def get_network_status(self) -> Dict[str, Any]:
        """获取网络状态"""
        status = {
            "agents": [],
            "connections": [],
            "memory_count": len(self._memory_store),
            "task_queue_length": len(self._task_queue)
        }
        
        for agent_id, agent_info in self._agents.items():
            status["agents"].append({
                "id": agent_id,
                "name": agent_info.name,
                "role": agent_info.role.value,
                "status": agent_info.status.value,
                "success_rate": agent_info.success_rate,
                "avg_latency": round(agent_info.avg_latency, 2)
            })
        
        for agent_id, connections in self._network_graph.items():
            for target_id in connections:
                if agent_id < target_id:  # 避免重复
                    status["connections"].append({
                        "from": agent_id,
                        "to": target_id
                    })
        
        return status


# 单例模式
_network_instance = None

def get_anda_agent_network() -> AndaAgentNetwork:
    """获取全局 Anda 代理网络实例"""
    global _network_instance
    if _network_instance is None:
        _network_instance = AndaAgentNetwork()
    return _network_instance


# 便捷函数
async def create_and_dispatch_task(task_type: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    创建并分发任务（便捷函数）
    
    Args:
        task_type: 任务类型
        payload: 任务内容
        **kwargs: 其他参数
        
    Returns:
        执行结果
    """
    import uuid
    
    network = get_anda_agent_network()
    
    task = TaskRequest(
        id=str(uuid.uuid4()),
        type=task_type,
        payload=payload,
        required_capabilities=kwargs.get("capabilities", []),
        priority=kwargs.get("priority", 0)
    )
    
    return await network.dispatch_task(task)