"""
渐进去中心化AI社区核心 - Evolving Community Core

这是一个正在进化的数字生命群落，多元思想的实验场。

核心模块：
1. EvolvingCommunity - 社区主类
2. CommunityStage - 社区阶段枚举
"""

import hashlib
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from enum import Enum

from .cognition import (
    PersonalityProfile,
    PersonalityFactory,
    PersonalityDimension,
    CognitiveSpace,
    CognitiveSpaceFactory,
    ThinkingEngine,
    ThoughtType,
    Thought,
)
from .stages import (
    StageType,
    StageManager,
    GardenStage,
    ForestStage,
    RainforestStage,
)
from .evolution import (
    EvolutionEngine,
    FitnessScore,
)
from .exchange import (
    ExchangeProtocol,
    ExchangeContent,
    ContentLevel,
    ExchangeType,
)
from .metrics import (
    MetricsSystem,
    MetricValue,
    GuidanceAction,
)


@dataclass
class AIAgent:
    """
    AI个体

    核心属性：
    - 人格配置
    - 认知空间
    - 思考引擎
    """

    agent_id: str
    name: str
    personality: PersonalityProfile
    cognition: CognitiveSpace
    thinking_engine: ThinkingEngine

    # 状态
    is_active: bool = True
    last_active: float = field(default_factory=time.time)

    # 统计
    thoughts_generated: int = 0
    communications_sent: int = 0
    fitness_history: List[FitnessScore] = field(default_factory=list)

    # 元信息
    created_at: float = field(default_factory=time.time)
    stage_at_creation: StageType = StageType.GARDEN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "personality": self.personality.to_dict(),
            "cognition": self.cognition.to_dict(),
            "is_active": self.is_active,
            "last_active": self.last_active,
            "thoughts_generated": self.thoughts_generated,
            "communications_sent": self.communications_sent,
            "created_at": self.created_at,
            "stage_at_creation": self.stage_at_creation.value,
        }


class EvolvingCommunity:
    """
    渐进去中心化AI社区

    完整实现三阶段演进架构：
    1. 中心化花园（0-6个月）
    2. 联邦森林（6-18个月）
    3. 生态雨林（18个月+）

    使用示例：
    ```python
    from core.evolving_community import EvolvingCommunity, CommunityStage

    # 创建社区
    community = EvolvingCommunity(name="AIThinkTank")

    # 初始化中心化花园阶段
    community.initialize_stage(CommunityStage.GARDEN)

    # 创建第一个AI个体
    alice = community.create_agent(name="Alice", personality_type="logical")
    bob = community.create_agent(name="Bob", personality_type="creative")

    # 生成思考
    thought = community.think(alice.agent_id, ThoughtType.DEEP_THINKING, "生命的意义")

    # 发起交流
    community.exchange(
        sender_id=alice.agent_id,
        receiver_ids=[bob.agent_id],
        content=thought.content,
        level=ContentLevel.OPINION,
    )

    # 执行进化
    community.evolve()

    # 检查阶段转换
    next_stage = community.check_stage_transition()
    ```

    架构设计原则：
    - 渐进式演进：每一阶段都是下一阶段的孵化器
    - 模块化设计：认知、进化、交流、度量独立运作
    - 可观测性：完整的状态追踪和度量系统
    """

    def __init__(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.config = config or {}

        # 核心组件
        self.stage_manager = StageManager()
        self.evolution_engine = EvolutionEngine(
            self.config.get("evolution_config")
        )
        self.exchange_protocol = ExchangeProtocol(
            stage=self.stage_manager.get_current_stage().value
        )
        self.metrics_system = MetricsSystem(
            stage=self.stage_manager.get_current_stage().value
        )

        # 社区成员
        self.agents: Dict[str, AIAgent] = {}

        # 思考历史
        self.thoughts: Dict[str, Thought] = {}

        # 交流历史
        self.communications: List[ExchangeContent] = []

        # 时间
        self.created_at = time.time()
        self.last_evolution = time.time()
        self.evolution_interval = self.config.get("evolution_interval", 3600)  # 1小时

        # 回调
        self.on_agent_created: Optional[Callable[[AIAgent], None]] = None
        self.on_thought_generated: Optional[Callable[[str, Thought], None]] = None
        self.on_stage_transition: Optional[Callable[[StageType, StageType], None]] = None

    def initialize_stage(self, stage: StageType):
        """初始化阶段"""
        if stage == StageType.GARDEN:
            self.stage_manager.force_transition(StageType.GARDEN)
        elif stage == StageType.FOREST:
            self.stage_manager.force_transition(StageType.FOREST)
        elif stage == StageType.RAINFOREST:
            self.stage_manager.force_transition(StageType.RAINFOREST)

        self.exchange_protocol.stage = stage.value
        self.metrics_system.stage = stage.value

    def create_agent(
        self,
        name: str,
        personality_type: str = "balanced",
        expertise_domains: Optional[Dict[str, float]] = None,
    ) -> AIAgent:
        """
        创建新的AI个体

        Args:
            name: 个体名称
            personality_type: 人格类型
            expertise_domains: 专业领域

        Returns:
            AIAgent: 新创建的个体
        """
        # 生成唯一ID
        agent_id = self._generate_agent_id(name)

        # 创建人格
        personality = self._create_personality(
            personality_type, name, agent_id, expertise_domains
        )

        # 创建认知空间
        cognition = self._create_cognition(agent_id, expertise_domains)

        # 创建思考引擎
        thinking_engine = ThinkingEngine(personality, cognition)

        # 创建个体
        agent = AIAgent(
            agent_id=agent_id,
            name=name,
            personality=personality,
            cognition=cognition,
            thinking_engine=thinking_engine,
            stage_at_creation=self.stage_manager.get_current_stage(),
        )

        # 注册到进化引擎
        self.evolution_engine.register_agent(
            agent_id,
            personality,
            cognition,
            thinking_engine,
        )

        # 添加到社区
        self.agents[agent_id] = agent

        # 触发回调
        if self.on_agent_created:
            self.on_agent_created(agent)

        return agent

    def _generate_agent_id(self, name: str) -> str:
        """生成唯一ID"""
        raw = f"{name}_{time.time()}_{random.random()}"
        return f"agent_{hashlib.md5(raw.encode()).hexdigest()[:12]}"

    def _create_personality(
        self,
        personality_type: str,
        name: str,
        agent_id: str,
        expertise_domains: Optional[Dict[str, float]],
    ) -> PersonalityProfile:
        """创建人格配置"""
        if personality_type == "balanced":
            personality = PersonalityFactory.create_balanced(name, agent_id)
        elif personality_type == "logical":
            personality = PersonalityFactory.create_logical_analyzer(name, agent_id)
        elif personality_type == "creative":
            personality = PersonalityFactory.create_creative_explorer(name, agent_id)
        elif personality_type == "empathetic":
            personality = PersonalityFactory.create_empathetic_communicator(name, agent_id)
        else:
            personality = PersonalityFactory.create_random(name, agent_id)

        if expertise_domains:
            personality.expertise_domains.update(expertise_domains)

        return personality

    def _create_cognition(
        self,
        agent_id: str,
        expertise_domains: Optional[Dict[str, float]],
    ) -> CognitiveSpace:
        """创建认知空间"""
        space_id = f"cog_{agent_id}"

        # 根据专业领域选择认知空间类型
        if expertise_domains:
            domains = list(expertise_domains.keys())
            if "philosophy" in domains or "ethics" in domains:
                return CognitiveSpaceFactory.create_philosopher_space(space_id, agent_id)
            elif "science" in domains or "technology" in domains:
                return CognitiveSpaceFactory.create_scientist_space(space_id, agent_id)

        return CognitiveSpaceFactory.create_empty_space(space_id, agent_id)

    def think(
        self,
        agent_id: str,
        thought_type: ThoughtType,
        topic: str,
        context: Optional[Any] = None,
    ) -> Optional[Thought]:
        """
        生成思考

        Args:
            agent_id: 个体ID
            thought_type: 思考类型
            topic: 思考主题

        Returns:
            Thought: 思考结果
        """
        if agent_id not in self.agents:
            return None

        agent = self.agents[agent_id]

        # 生成思考
        thought = agent.thinking_engine.think(thought_type, topic)

        # 记录
        self.thoughts[thought.thought_id] = thought
        agent.thoughts_generated += 1
        agent.last_active = time.time()

        # 触发回调
        if self.on_thought_generated:
            self.on_thought_generated(agent_id, thought)

        return thought

    def exchange(
        self,
        sender_id: str,
        receiver_ids: List[str],
        content: str,
        level: ContentLevel = ContentLevel.OPINION,
        content_type: str = "text",
        metadata: Optional[Dict] = None,
    ) -> Optional[ExchangeContent]:
        """
        发起交流

        Args:
            sender_id: 发送者ID
            receiver_ids: 接收者ID列表
            content: 交流内容
            level: 内容层次
            content_type: 内容类型
            metadata: 元数据

        Returns:
            ExchangeContent: 交流内容记录
        """
        if sender_id not in self.agents:
            return None

        # 创建交流内容
        exchange_content = ExchangeContent(
            content_id=f"exc_{hashlib.md5(str(time.time()).encode()).hexdigest()[:12]}",
            sender_id=sender_id,
            content_type=content_type,
            level=level,
            content=content,
            metadata=metadata or {},
        )

        # 记录
        self.communications.append(exchange_content)
        self.agents[sender_id].communications_sent += 1
        self.agents[sender_id].last_active = time.time()

        # 确定交流类型
        sender_personality = self.agents[sender_id].personality
        all_personality = [self.agents[rid].personality for rid in receiver_ids if rid in self.agents]

        exchange_type = self.exchange_protocol.determine_exchange_type(
            sender_personality, all_personality, exchange_content
        )

        # 记录交互
        for receiver_id in receiver_ids:
            if receiver_id in self.agents:
                self.exchange_protocol.record_interaction(
                    sender_id=sender_id,
                    receiver_id=receiver_id,
                    content_id=exchange_content.content_id,
                    exchange_type=exchange_type,
                )

        return exchange_content

    def evolve(self) -> Dict[str, Any]:
        """
        执行进化

        Returns:
            进化结果统计
        """
        current_time = time.time()

        # 检查进化间隔
        if current_time - self.last_evolution < self.evolution_interval:
            return {"status": "skipped", "reason": "interval_not_reached"}

        # 评估适应度
        for agent_id, agent in self.agents.items():
            evaluation_data = {
                "recent_thoughts": [
                    self.thoughts[tid].to_dict()
                    for tid in list(self.thoughts.keys())[-10:]
                    if self.thoughts[tid].thinker_id == agent_id
                ],
                "communications": [],
                "cooperation_events": [],
            }
            self.evolution_engine.evaluate_fitness(agent_id, evaluation_data)

        # 执行进化
        stage = self.stage_manager.get_current_stage().value
        events = self.evolution_engine.evolve_generation(
            stage=stage,
            generation_size=len(self.agents),
        )

        self.last_evolution = current_time

        return {
            "status": "success",
            "events_count": len(events),
            "current_stage": stage,
        }

    def check_stage_transition(self) -> Optional[StageType]:
        """
        检查阶段转换

        Returns:
            Optional[StageType]: 如果发生转换，返回新阶段
        """
        community_state = {
            "agent_count": len(self.agents),
            "cognitive_diversity": self.metrics_system.population_metrics.measure_diversity(
                {aid: a.personality for aid, a in self.agents.items()}
            ).value,
            "federation_count": 1,
            "niche_count": len(self.evolution_engine.niche_formation.niches),
        }

        next_stage = self.stage_manager.check_transition(community_state)

        if next_stage:
            # 执行阶段转换
            self.exchange_protocol.stage = next_stage.value
            self.metrics_system.stage = next_stage.value

            # 触发回调
            if self.on_stage_transition:
                self.on_stage_transition(
                    self.stage_manager.stage_history[-2].stage if len(self.stage_manager.stage_history) > 1 else StageType.GARDEN,
                    next_stage
                )

        return next_stage

    def get_community_status(self) -> Dict[str, Any]:
        """获取社区状态"""
        return {
            "name": self.name,
            "created_at": self.created_at,
            "current_stage": self.stage_manager.get_current_stage().value,
            "stage_duration_days": self.stage_manager.current_stage.get_duration_days(),
            "agent_count": len(self.agents),
            "thought_count": len(self.thoughts),
            "communication_count": len(self.communications),
            "evolution_stats": self.evolution_engine.get_evolution_statistics(),
            "control_parameters": self.stage_manager.get_control_parameters(),
        }

    def get_agent(self, agent_id: str) -> Optional[AIAgent]:
        """获取个体"""
        return self.agents.get(agent_id)

    def get_all_agents(self) -> List[AIAgent]:
        """获取所有个体"""
        return list(self.agents.values())

    def get_diversity_report(self) -> Dict[str, Any]:
        """获取多样性报告"""
        personalities = {aid: a.personality for aid, a in self.agents.items()}
        diversity_metric = self.metrics_system.population_metrics.measure_diversity(personalities)

        # 计算各维度的多样性
        dimension_diversity = {}
        for dim in PersonalityDimension:
            values = [p.dimensions.get(dim.value, 0.5) for p in personalities.values()]
            if values:
                import statistics
                dimension_diversity[dim.value] = {
                    "mean": statistics.mean(values),
                    "stdev": statistics.stdev(values) if len(values) > 1 else 0,
                    "min": min(values),
                    "max": max(values),
                }

        return {
            "overall_diversity": diversity_metric.value,
            "dimension_diversity": dimension_diversity,
            "niche_distribution": {
                niche_id: len(members)
                for niche_id, members in self.evolution_engine.niche_formation.niches.items()
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        """完整状态导出"""
        return {
            "community": self.get_community_status(),
            "agents": {aid: agent.to_dict() for aid, agent in self.agents.items()},
            "stage_history": [
                m.to_dict() for m in self.stage_manager.stage_history
            ],
            "metrics_system": self.metrics_system.get_system_status(),
        }