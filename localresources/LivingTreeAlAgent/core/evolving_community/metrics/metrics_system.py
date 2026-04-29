"""
度量与引导系统 - Metrics and Guidance System

个体层面度量：
- 思考能力指标
- 交流能力指标
- 进化健康度

群体层面度量：
- 多样性指标
- 协作效率
- 生态健康
"""

import time
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

from ..cognition import PersonalityProfile, CognitiveSpace


class MetricCategory(Enum):
    """度量类别"""
    INDIVIDUAL_THINKING = "individual_thinking"
    INDIVIDUAL_COMMUNICATION = "individual_communication"
    INDIVIDUAL_HEALTH = "individual_health"
    POPULATION_DIVERSITY = "population_diversity"
    POPULATION_COLLABORATION = "population_collaboration"
    POPULATION_ECOLOGY = "population_ecology"


@dataclass
class MetricValue:
    """度量值"""
    name: str
    category: MetricCategory
    value: float
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "value": self.value,
            "timestamp": self.timestamp,
            "details": self.details,
        }


@dataclass
class GuidanceAction:
    """引导动作"""
    action_id: str
    action_type: str
    target: str                      # agent_id 或 "population"
    priority: int                   # 1-5, 1最高
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)


class IndividualMetrics:
    """个体度量"""

    @staticmethod
    def measure_thinking_quality(
        agent_id: str,
        thoughts: List[Dict],
    ) -> MetricValue:
        """测量思考质量"""
        if not thoughts:
            return MetricValue(
                name="thinking_quality",
                category=MetricCategory.INDIVIDUAL_THINKING,
                value=0.0,
            )

        avg_depth = sum(t.get("depth_score", 0) for t in thoughts) / len(thoughts)
        avg_creativity = sum(t.get("creativity_score", 0) for t in thoughts) / len(thoughts)
        avg_logical = sum(t.get("logical_score", 0) for t in thoughts) / len(thoughts)

        # 综合思考质量
        quality = (avg_depth * 0.4 + avg_creativity * 0.3 + avg_logical * 0.3)

        return MetricValue(
            name="thinking_quality",
            category=MetricCategory.INDIVIDUAL_THINKING,
            value=quality,
            details={
                "avg_depth": avg_depth,
                "avg_creativity": avg_creativity,
                "avg_logical": avg_logical,
                "thought_count": len(thoughts),
            }
        )

    @staticmethod
    def measure_communication_ability(
        agent_id: str,
        communications: List[Dict],
    ) -> MetricValue:
        """测量交流能力"""
        if not communications:
            return MetricValue(
                name="communication_ability",
                category=MetricCategory.INDIVIDUAL_COMMUNICATION,
                value=0.0,
            )

        avg_clarity = sum(c.get("clarity_score", 0.5) for c in communications) / len(communications)
        avg_engagement = sum(c.get("engagement_score", 0.5) for c in communications) / len(communications)
        avg_influence = sum(c.get("influence_score", 0.5) for c in communications) / len(communications)

        ability = (avg_clarity * 0.3 + avg_engagement * 0.4 + avg_influence * 0.3)

        return MetricValue(
            name="communication_ability",
            category=MetricCategory.INDIVIDUAL_COMMUNICATION,
            value=ability,
            details={
                "avg_clarity": avg_clarity,
                "avg_engagement": avg_engagement,
                "avg_influence": avg_influence,
                "comm_count": len(communications),
            }
        )

    @staticmethod
    def measure_evolution_health(
        agent_id: str,
        personality: PersonalityProfile,
        cognition: CognitiveSpace,
        historical_scores: List[Dict],
    ) -> MetricValue:
        """测量进化健康度"""
        # 认知结构复杂度
        concept_count = len(cognition.concepts)
        complexity = min(1.0, concept_count / 100)

        # 学习曲线斜率
        learning_rate = 0.0
        if len(historical_scores) >= 2:
            recent = historical_scores[-5:]
            if len(recent) >= 2:
                first_score = recent[0].get("overall", 0.5)
                last_score = recent[-1].get("overall", 0.5)
                learning_rate = (last_score - first_score) / len(recent)

        # 适应变化能力
        adaptation = personality.get_cognitive_style().get("adaptation_level", 0.5)

        health = (complexity * 0.3 + learning_rate * 0.3 + adaptation * 0.4)

        return MetricValue(
            name="evolution_health",
            category=MetricCategory.INDIVIDUAL_HEALTH,
            value=health,
            details={
                "complexity": complexity,
                "learning_rate": learning_rate,
                "adaptation": adaptation,
            }
        )


class PopulationMetrics:
    """群体度量"""

    @staticmethod
    def measure_diversity(
        personalities: Dict[str, PersonalityProfile],
    ) -> MetricValue:
        """测量多样性"""
        if len(personalities) < 2:
            return MetricValue(
                name="cognitive_diversity",
                category=MetricCategory.POPULATION_DIVERSITY,
                value=0.0,
            )

        # 计算人格距离矩阵
        distances = []
        agent_ids = list(personalities.keys())

        for i, id1 in enumerate(agent_ids):
            for id2 in agent_ids[i+1:]:
                dist = personalities[id1].calculate_cognitive_distance(personalities[id2])
                distances.append(dist)

        # 平均认知距离
        avg_distance = sum(distances) / len(distances) if distances else 0

        # 认知空间覆盖率
        all_concepts = set()
        total_concepts = 0

        # 生态位分化度
        niche_count = len(set(p["niche_id"] for p in personalities.values()))

        diversity = avg_distance * 0.5 + min(1.0, niche_count / 10) * 0.5

        return MetricValue(
            name="cognitive_diversity",
            category=MetricCategory.POPULATION_DIVERSITY,
            value=diversity,
            details={
                "avg_cognitive_distance": avg_distance,
                "niche_count": niche_count,
                "population_size": len(personalities),
            }
        )

    @staticmethod
    def measure_collaboration_efficiency(
        interactions: List[Dict],
    ) -> MetricValue:
        """测量协作效率"""
        if not interactions:
            return MetricValue(
                name="collaboration_efficiency",
                category=MetricCategory.POPULATION_COLLABORATION,
                value=0.0,
            )

        # 信息传播速度
        propagation_times = []
        for interaction in interactions:
            if "sent_at" in interaction and "received_at" in interaction:
                propagation_times.append(
                    interaction["received_at"] - interaction["sent_at"]
                )

        avg_propagation = sum(propagation_times) / len(propagation_times) if propagation_times else 0
        propagation_score = max(0, 1.0 - avg_propagation / 3600)  # 标准化到1小时

        # 知识整合度
        knowledge_integration = min(1.0, len(interactions) / 100)

        # 冲突解决效率
        conflict_resolutions = sum(1 for i in interactions if i.get("resolved", False))
        conflict_score = conflict_resolutions / len(interactions) if interactions else 0

        efficiency = (
            propagation_score * 0.4 +
            knowledge_integration * 0.3 +
            conflict_score * 0.3
        )

        return MetricValue(
            name="collaboration_efficiency",
            category=MetricCategory.POPULATION_COLLABORATION,
            value=efficiency,
            details={
                "propagation_score": propagation_score,
                "knowledge_integration": knowledge_integration,
                "conflict_score": conflict_score,
                "interaction_count": len(interactions),
            }
        )

    @staticmethod
    def measure_ecology_health(
        population_metrics: Dict[str, Any],
    ) -> MetricValue:
        """测量生态健康"""
        # 种群稳定性
        stability = population_metrics.get("stability_score", 0.5)

        # 可持续进化
        evolution_rate = population_metrics.get("evolution_rate", 0.0)
        sustainability = min(1.0, evolution_rate / 0.5)

        # 抗扰动能力
        resilience = population_metrics.get("resilience_score", 0.5)

        # 资源利用效率
        resource_efficiency = population_metrics.get("resource_efficiency", 0.5)

        health = (
            stability * 0.25 +
            sustainability * 0.25 +
            resilience * 0.25 +
            resource_efficiency * 0.25
        )

        return MetricValue(
            name="ecology_health",
            category=MetricCategory.POPULATION_ECOLOGY,
            value=health,
            details={
                "stability": stability,
                "sustainability": sustainability,
                "resilience": resilience,
                "resource_efficiency": resource_efficiency,
            }
        )


class GuidanceSystem:
    """
    引导系统

    根据阶段自适应调整引导策略：
    - 前期：主动引导
    - 中期：环境塑造
    - 后期：自主进化
    """

    def __init__(self, stage: str = "garden"):
        self.stage = stage
        self.guidance_history: List[GuidanceAction] = []

    def generate_guidance(
        self,
        individual_metrics: Optional[Dict[str, MetricValue]] = None,
        population_metrics: Optional[Dict[str, MetricValue]] = None,
    ) -> List[GuidanceAction]:
        """生成引导动作"""
        actions = []

        if self.stage == "garden":
            actions = self._garden_guidance(individual_metrics, population_metrics)
        elif self.stage == "forest":
            actions = self._forest_guidance(individual_metrics, population_metrics)
        else:
            actions = self._rainforest_guidance(individual_metrics, population_metrics)

        self.guidance_history.extend(actions)
        return actions

    def _garden_guidance(
        self,
        individual_metrics: Optional[Dict[str, MetricValue]],
        population_metrics: Optional[Dict[str, MetricValue]],
    ) -> List[GuidanceAction]:
        """花园阶段引导"""
        actions = []

        # 设置明确的进化目标
        actions.append(GuidanceAction(
            action_id=f"guide_{int(time.time())}_1",
            action_type="SET_EVOLUTION_GOAL",
            target="population",
            priority=1,
            description="设置明确的进化目标：培养深度思考能力",
            parameters={"focus": "thinking_depth", "target": 0.7}
        ))

        # 人工选择优秀个体
        if individual_metrics:
            sorted_agents = sorted(
                [(aid, m.get("thinking_quality", MetricValue("", MetricCategory.INDIVIDUAL_THINKING, 0)).value)
                 for aid, m in individual_metrics.items()],
                key=lambda x: x[1],
                reverse=True
            )

            if sorted_agents:
                top_agent = sorted_agents[0][0]
                actions.append(GuidanceAction(
                    action_id=f"guide_{int(time.time())}_2",
                    action_type="PROMOTE_AGENT",
                    target=top_agent,
                    priority=2,
                    description=f"选择 {top_agent} 作为优秀个体鼓励",
                    parameters={"reward_type": "cognition_boost"}
                ))

        return actions

    def _forest_guidance(
        self,
        individual_metrics: Optional[Dict[str, MetricValue]],
        population_metrics: Optional[Dict[str, MetricValue]],
    ) -> List[GuidanceAction]:
        """森林阶段引导"""
        actions = []

        # 设计选择压力环境
        actions.append(GuidanceAction(
            action_id=f"guide_{int(time.time())}_1",
            action_type="ADJUST_SELECTION_PRESSURE",
            target="population",
            priority=1,
            description="调整选择压力，鼓励创新",
            parameters={"innovation_pressure": 0.7, "cooperation_pressure": 0.5}
        ))

        # 创建合作机会
        actions.append(GuidanceAction(
            action_id=f"guide_{int(time.time())}_2",
            action_type="CREATE_COLLABORATION",
            target="population",
            priority=2,
            description="创建跨领域合作任务",
            parameters={"task_type": "cross_domain_analysis"}
        ))

        return actions

    def _rainforest_guidance(
        self,
        individual_metrics: Optional[Dict[str, MetricValue]],
        population_metrics: Optional[Dict[str, MetricValue]],
    ) -> List[GuidanceAction]:
        """雨林阶段引导"""
        actions = []

        # 移除中心化干预
        actions.append(GuidanceAction(
            action_id=f"guide_{int(time.time())}_1",
            action_type="REDUCE_CENTRAL_CONTROL",
            target="population",
            priority=1,
            description="减少中心化控制，让自然选择主导",
            parameters={"control_level": 0.2}
        ))

        # 保护少数思考
        if population_metrics:
            diversity = population_metrics.get("cognitive_diversity", MetricValue("", MetricCategory.POPULATION_DIVERSITY, 0.5))
            if diversity.value < 0.3:
                actions.append(GuidanceAction(
                    action_id=f"guide_{int(time.time())}_2",
                    action_type="PROTECT_MINORITY",
                    target="population",
                    priority=2,
                    description="保护少数派思考，维护多样性",
                    parameters={"protection_level": 0.8}
                ))

        return actions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "guidance_count": len(self.guidance_history),
            "recent_guidance": [
                {"action_type": g.action_type, "target": g.target}
                for g in self.guidance_history[-5:]
            ]
        }


class MetricsSystem:
    """
    度量系统核心

    整合所有度量功能
    """

    def __init__(self, stage: str = "garden"):
        self.stage = stage
        self.individual_metrics = IndividualMetrics()
        self.population_metrics = PopulationMetrics()
        self.guidance_system = GuidanceSystem(stage)

        self.metric_history: List[MetricValue] = []

    def measure_individual(
        self,
        agent_id: str,
        personality: PersonalityProfile,
        cognition: CognitiveSpace,
        thoughts: List[Dict],
        communications: List[Dict],
        historical_scores: List[Dict],
    ) -> Dict[str, MetricValue]:
        """测量个体"""
        metrics = {}

        metrics["thinking_quality"] = self.individual_metrics.measure_thinking_quality(
            agent_id, thoughts
        )
        metrics["communication_ability"] = self.individual_metrics.measure_communication_ability(
            agent_id, communications
        )
        metrics["evolution_health"] = self.individual_metrics.measure_evolution_health(
            agent_id, personality, cognition, historical_scores
        )

        self.metric_history.extend(metrics.values())
        return metrics

    def measure_population(
        self,
        personalities: Dict[str, PersonalityProfile],
        interactions: List[Dict],
        population_metrics: Dict[str, Any],
    ) -> Dict[str, MetricValue]:
        """测量群体"""
        metrics = {}

        metrics["cognitive_diversity"] = self.population_metrics.measure_diversity(
            personalities
        )
        metrics["collaboration_efficiency"] = self.population_metrics.measure_collaboration_efficiency(
            interactions
        )
        metrics["ecology_health"] = self.population_metrics.measure_ecology_health(
            population_metrics
        )

        self.metric_history.extend(metrics.values())
        return metrics

    def generate_guidance(
        self,
        individual_metrics: Optional[Dict[str, Dict[str, MetricValue]]] = None,
        population_metrics: Optional[Dict[str, MetricValue]] = None,
    ) -> List[GuidanceAction]:
        """生成引导"""
        return self.guidance_system.generate_guidance(individual_metrics, population_metrics)

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "stage": self.stage,
            "total_metrics": len(self.metric_history),
            "guidance_system": self.guidance_system.to_dict(),
        }