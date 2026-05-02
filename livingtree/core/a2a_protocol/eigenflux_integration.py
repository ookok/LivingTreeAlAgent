"""
EigenFlux 集成示例
==================
展示如何将 EigenFlux 信号机制与现有 A2A 协议集成

Author: LivingTree AI Agent
Date: 2026-04-29
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from a2a_protocol import (
    AgentInfo, AgentCapability, MessageType,
    AgentRegistry, A2AServer, A2AClient, Task,
)
from eigenflux import (
    SignalBus, SignalType, Subscriber, 
    A2AEigenFluxBridge, AgentSignalAdapter,
)


class LivingTreeEigenFluxGateway:
    """
    LivingTree EigenFlux 网关
    =========================
    将 EigenFlux 信号广播机制与现有 A2A 协议深度集成
    
    功能：
    1. Agent 注册时自动广播能力
    2. 任务创建时广播需求
    3. 知识发现时广播信号
    4. 智能订阅者匹配
    """
    
    def __init__(self):
        # 现有 A2A 组件
        self.registry = AgentRegistry()
        self.signal_bus = SignalBus("livingtree")
        self.eigenflux_bridge = A2AEigenFluxBridge(self.signal_bus)
        
        # Agent 适配器映射
        self.agent_adapters: Dict[str, AgentSignalAdapter] = {}
        
        # 设置信号总线钩子
        self.signal_bus.on_broadcast(self._on_signal_broadcast)
        self.signal_bus.on_delivered(self._on_signal_delivered)
        
        print("🌐 LivingTree EigenFlux Gateway 初始化完成")
    
    # ==================== Agent 管理 ====================
    
    def register_agent(self, agent_info: AgentInfo) -> bool:
        """
        注册 Agent（同时注册到 A2A 和 EigenFlux）
        """
        # A2A 注册
        self.registry.register(agent_info)
        
        # EigenFlux 适配器创建
        capabilities = [c.value for c in agent_info.capabilities]
        adapter = AgentSignalAdapter(
            agent_id=agent_info.agent_id,
            agent_name=agent_info.name,
            capabilities=capabilities,
            signal_bus=self.signal_bus,
        )
        self.agent_adapters[agent_info.agent_id] = adapter
        
        # 广播能力信号
        self.eigenflux_bridge.agent_registered(
            agent_id=agent_info.agent_id,
            capabilities=capabilities,
        )
        
        print(f"✅ Agent 注册成功: {agent_info.name} ({agent_info.agent_id})")
        return True
    
    def unregister_agent(self, agent_id: str) -> bool:
        """注销 Agent"""
        # A2A 注销
        self.registry.unregister(agent_id)
        
        # EigenFlux 注销
        if agent_id in self.agent_adapters:
            self.agent_adapters[agent_id].disconnect()
            del self.agent_adapters[agent_id]
        
        self.eigenflux_bridge.agent_unregistered(agent_id)
        
        print(f"🔴 Agent 注销: {agent_id}")
        return True
    
    def get_agent(self, agent_id: str):
        """获取 Agent 信息"""
        return self.registry.get_agent(agent_id)
    
    def find_agents_by_capability(self, capability: str) -> List[AgentInfo]:
        """查找具有特定能力的 Agent"""
        try:
            cap = AgentCapability(capability)
            return self.registry.find_agents_by_capability(cap)
        except ValueError:
            return []
    
    # ==================== 任务管理 ====================
    
    def create_task(self, task_type: str, description: str,
                    params: Dict = None, priority: int = 0,
                    sender_id: str = "system") -> str:
        """
        创建任务（自动广播到 EigenFlux）
        """
        import uuid
        task_id = str(uuid.uuid4())[:8]
        
        # 提取所需技能
        skills_required = []
        if params and "required_skills" in params:
            skills_required = params["required_skills"]
        
        # A2A 任务创建
        task = Task(
            task_id=task_id,
            task_type=task_type,
            description=description,
            params=params or {},
            priority=priority,
            status="pending",
        )
        
        # EigenFlux 广播
        self.eigenflux_bridge.task_created(
            task_id=task_id,
            task_type=task_type,
            skills_required=skills_required,
            sender_id=sender_id,
        )
        
        print(f"📋 任务创建: [{task_type}] {description[:50]}...")
        return task_id
    
    # ==================== 知识管理 ====================
    
    def broadcast_knowledge(self, agent_id: str, knowledge: Dict,
                           domain: str = "", keywords: List[str] = None):
        """广播知识信号"""
        if agent_id in self.agent_adapters:
            self.agent_adapters[agent_id].send_knowledge(
                knowledge=knowledge,
                domain=domain,
            )
        else:
            self.eigenflux_bridge.knowledge_discovered(
                agent_id=agent_id,
                knowledge=knowledge,
                domain=domain,
            )
        
        print(f"📚 知识广播: [{domain}] {knowledge.get('title', 'Untitled')}")
    
    def broadcast_need(self, agent_id: str, need: str,
                       required_skills: List[str] = None):
        """广播需求信号"""
        if agent_id in self.agent_adapters:
            self.agent_adapters[agent_id].send_need(
                need=need,
                required_skills=required_skills,
            )
        else:
            self.eigenflux_bridge.need_identified(
                agent_id=agent_id,
                need=need,
                required_skills=required_skills or [],
            )
        
        print(f"🔍 需求广播: {need[:50]}...")
    
    # ==================== 信号订阅 ====================
    
    def subscribe_to_signals(self, subscriber_id: str, interests: Set[str],
                            signal_types: Set[SignalType] = None,
                            callback: Callable = None):
        """订阅信号"""
        if signal_types is None:
            signal_types = {SignalType.KNOWLEDGE, SignalType.NEED, 
                          SignalType.CAPABILITY, SignalType.TASK}
        
        subscriber = Subscriber(
            subscriber_id=subscriber_id,
            interests=interests,
            capabilities=set(),  # 可根据需要设置
            signal_types={s.value for s in signal_types},
            callback=callback,
        )
        
        self.signal_bus.subscribe(subscriber)
        print(f"📡 订阅创建: {subscriber_id} (兴趣: {interests})")
    
    # ==================== 统计与调试 ====================
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "agents": {
                "registered": len(self.registry.agents),
                "adapters": len(self.agent_adapters),
            },
            "eigenflux": self.signal_bus.get_stats(),
        }
    
    def print_status(self):
        """打印状态"""
        stats = self.get_stats()
        print("\n" + "=" * 50)
        print("LivingTree EigenFlux Gateway 状态")
        print("=" * 50)
        print(f"注册 Agent 数量: {stats['agents']['registered']}")
        print(f"活跃适配器数量: {stats['agents']['adapters']}")
        print(f"活跃订阅者数量: {stats['eigenflux']['active_subscribers']}")
        print(f"信号发送总数: {stats['eigenflux']['signals_sent']}")
        print(f"信号传递总数: {stats['eigenflux']['signals_delivered']}")
        print(f"信号过滤总数: {stats['eigenflux']['signals_filtered']}")
        print("=" * 50)
    
    # ==================== 钩子回调 ====================
    
    def _on_signal_broadcast(self, signal):
        """信号广播回调"""
        print(f"📡 [广播] {signal.metadata.signal_type.value}: "
              f"from={signal.metadata.sender_id}")
    
    def _on_signal_delivered(self, signal, subscriber):
        """信号传递回调"""
        print(f"📬 [传递] {signal.metadata.signal_type.value} -> "
              f"{subscriber.subscriber_id}")


# ==================== 演示函数 ====================

def demo_basic():
    """基础演示"""
    print("\n" + "=" * 60)
    print("EigenFlux 基础演示")
    print("=" * 60)
    
    gateway = LivingTreeEigenFluxGateway()
    
    # 注册 Agent
    hermes = AgentInfo(
        agent_id="hermes_001",
        name="Hermes",
        capabilities=[AgentCapability.ORCHESTRATION, AgentCapability.PLANNING],
        description="智能中枢，负责协调其他 Agent",
    )
    gateway.register_agent(hermes)
    
    ei_agent = AgentInfo(
        agent_id="ei_001",
        name="EI Agent",
        capabilities=[AgentCapability.ANALYSIS, AgentCapability.CODE_REVIEW],
        description="自我进化 Agent",
    )
    gateway.register_agent(ei_agent)
    
    ide_agent = AgentInfo(
        agent_id="ide_001",
        name="IDE Agent",
        capabilities=[AgentCapability.CODE_GENERATION, AgentCapability.DEBUGGING],
        description="代码助手 Agent",
    )
    gateway.register_agent(ide_agent)
    
    # 创建订阅
    def on_signal_received(signal):
        print(f"   [收到信号] {signal.metadata.signal_id[:8]}...")
    
    gateway.subscribe_to_signals(
        subscriber_id="hermes_observer",
        interests={"代码生成", "架构设计", "AI"},
        callback=on_signal_received,
    )
    
    print()
    
    # 广播知识
    gateway.broadcast_knowledge(
        agent_id="hermes_001",
        knowledge={
            "title": "微服务架构最佳实践",
            "content": "关于微服务拆分的详细指南...",
            "author": "Hermes",
        },
        domain="架构设计",
    )
    
    # 广播需求
    gateway.broadcast_need(
        agent_id="ei_001",
        need="需要代码审查能力来提升进化质量",
        required_skills=["code_review"],
    )
    
    # 创建任务
    gateway.create_task(
        task_type="code_generation",
        description="实现一个新的 API 端点",
        params={"required_skills": ["code_generation"]},
        sender_id="hermes_001",
    )
    
    print()
    gateway.print_status()


def demo_signal_types():
    """信号类型演示"""
    print("\n" + "=" * 60)
    print("EigenFlux 信号类型演示")
    print("=" * 60)
    
    bus = SignalBus("demo")
    
    # 创建订阅者
    subscribers = [
        Subscriber(
            subscriber_id=f"agent_{i}",
            interests={"AI", "代码", "测试"},
            capabilities={"生成", "分析", "测试"},
            signal_types={s.value for s in SignalType},
        )
        for i in range(3)
    ]
    
    for sub in subscribers:
        bus.subscribe(sub)
    
    print(f"\n📡 已注册 {len(subscribers)} 个订阅者")
    
    # 广播不同类型的信号
    print("\n📤 广播测试:")
    
    count = bus.send_knowledge(
        sender_id="hermes",
        knowledge={"title": "LLM 最新进展", "content": "..."},
        domain="AI",
        keywords=["AI", "LLM", "深度学习"],
    )
    print(f"   KNOWLEDGE 信号 -> {count} 个订阅者")
    
    count = bus.send_need(
        sender_id="ei_agent",
        need="需要代码优化建议",
        required_skills=["code_review"],
    )
    print(f"   NEED 信号 -> {count} 个订阅者")
    
    count = bus.send_capability(
        sender_id="ide_agent",
        capabilities=["代码生成", "代码补全", "重构"],
    )
    print(f"   CAPABILITY 信号 -> {count} 个订阅者")
    
    count = bus.send_task(
        sender_id="hermes",
        task={"task_id": "001", "task_type": "代码审查"},
    )
    print(f"   TASK 信号 -> {count} 个订阅者")
    
    # 打印统计
    print("\n📊 统计信息:")
    stats = bus.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")


if __name__ == "__main__":
    demo_basic()
    print("\n")
    demo_signal_types()
