"""
进化引擎 - Evolution Engine

核心机制：
1. 多维适应度评价
2. 差异化选择压力
3. 知识重组与变异
4. 生态位分化

目标：不是优化单一目标，而是分化生态位
"""

import random
import time
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from collections import defaultdict

from ..cognition import PersonalityProfile, CognitiveSpace, ThinkingEngine


@dataclass
class FitnessScore:
    """适应度评分"""
    agent_id: str
    timestamp: float = field(default_factory=time.time)

    # 多维适应度
    thinking_quality: float = 0.0      # 思考质量
    communication_ability: float = 0.0 # 交流能力
    niche_adaptation: float = 0.0      # 生态位适应
    cooperation_score: float = 0.0     # 合作能力
    innovation_score: float = 0.0      # 创新能力

    # 综合评分
    overall_fitness: float = 0.0

    # 历史记录
    historical_scores: List[Dict] = field(default_factory=list)

    def calculate_overall(self, weights: Optional[Dict[str, float]] = None) -> float:
        """计算综合评分"""
        if weights is None:
            weights = {
                "thinking_quality": 0.3,
                "communication_ability": 0.25,
                "niche_adaptation": 0.2,
                "cooperation_score": 0.15,
                "innovation_score": 0.1,
            }

        self.overall_fitness = sum(
            getattr(self, metric) * weight
            for metric, weight in weights.items()
        )
        return self.overall_fitness

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "thinking_quality": self.thinking_quality,
            "communication_ability": self.communication_ability,
            "niche_adaptation": self.niche_adaptation,
            "cooperation_score": self.cooperation_score,
            "innovation_score": self.innovation_score,
            "overall_fitness": self.overall_fitness,
        }


@dataclass
class EvolutionEvent:
    """进化事件"""
    event_id: str
    event_type: str                    # SELECTION/MUTATION/CROSSOVER/SPECIATION
    timestamp: float = field(default_factory=time.time)
    participants: List[str] = field(default_factory=list)  # 涉及的个体ID
    result: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


class SelectionPressure:
    """
    选择压力

    定义多维选择压力：
    1. 思考质量压力
    2. 交流能力压力
    3. 生态位适应压力
    """

    def __init__(self, config: Optional[Dict[str, float]] = None):
        # 基础选择压力强度
        self.base_pressure = config or {
            "thinking_quality": 0.5,
            "communication_ability": 0.5,
            "niche_adaptation": 0.5,
            "cooperation": 0.5,
            "innovation": 0.5,
        }

        # 选择强度
        self.selection_intensity: float = 0.7  # 0-1，越高越严格

    def evaluate(
        self,
        fitness_scores: List[FitnessScore],
        stage: str,
    ) -> List[Tuple[str, float]]:
        """
        评估选择压力

        Args:
            fitness_scores: 个体适应度列表
            stage: 当前阶段

        Returns:
            [(agent_id, survival_probability), ...]
        """
        if not fitness_scores:
            return []

        # 阶段调整
        pressure_multiplier = self._get_stage_multiplier(stage)

        # 计算生存概率
        survival_probs = []
        for score in fitness_scores:
            # 多维压力加权
            effective_fitness = (
                score.thinking_quality * self.base_pressure["thinking_quality"] +
                score.communication_ability * self.base_pressure["communication_ability"] +
                score.niche_adaptation * self.base_pressure["niche_adaptation"] +
                score.cooperation_score * self.base_pressure["cooperation"] +
                score.innovation_score * self.base_pressure["innovation"]
            ) / sum(self.base_pressure.values())

            # 应用选择强度
            survival_prob = effective_fitness * self.selection_intensity * pressure_multiplier
            survival_prob = max(0.1, min(0.95, survival_prob))

            survival_probs.append((score.agent_id, survival_prob))

        return survival_probs

    def _get_stage_multiplier(self, stage: str) -> float:
        """获取阶段调整因子"""
        multipliers = {
            "garden": 1.2,   # 花园阶段：较高压力，人工控制
            "forest": 1.0,  # 森林阶段：标准压力
            "rainforest": 0.7,  # 雨林阶段：较低压力，自然选择
        }
        return multipliers.get(stage, 1.0)

    def set_pressure(self, dimension: str, value: float):
        """调整特定维度的选择压力"""
        if dimension in self.base_pressure:
            self.base_pressure[dimension] = max(0.0, min(1.0, value))


class MutationOperator:
    """变异算子"""

    def __init__(self, base_rate: float = 0.1):
        self.base_rate = base_rate

    def mutate_personality(
        self,
        personality: PersonalityProfile,
        pressure_dimension: Optional[str] = None,
    ) -> PersonalityProfile:
        """
        对人格进行变异

        Args:
            personality: 原始人格
            pressure_dimension: 选择压力维度，影响变异方向

        Returns:
            变异后的人格
        """
        # 根据选择压力调整变异率
        if pressure_dimension == "innovation":
            mutation_rate = self.base_rate * 1.5  # 创新压力大，增加变异
        elif pressure_dimension == "thinking_quality":
            mutation_rate = self.base_rate * 0.8  # 思考质量压力大，降低变异
        else:
            mutation_rate = self.base_rate

        return personality.mutate(mutation_rate=mutation_rate)

    def mutate_cognition(
        self,
        cognition: CognitiveSpace,
        novelty_factor: float = 0.2,
    ) -> CognitiveSpace:
        """
        对认知空间进行变异

        添加新的概念或强化现有连接
        """
        # 添加随机新概念
        if random.random() < novelty_factor:
            new_concept_id = f"novel_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
            categories = ["domain", "skill", "topic"]
            cognition.add_concept(
                concept_id=new_concept_id,
                label=f"新概念_{new_concept_id}",
                category=random.choice(categories),
                expertise_level=0.3,
                weight=0.4,
            )

        # 强化随机连接
        for node in cognition.concepts.values():
            if node.connections and random.random() < novelty_factor:
                for conn_id in node.connections:
                    node.connections[conn_id] = min(1.0, node.connections[conn_id] + 0.1)

        return cognition


class CrossoverOperator:
    """交叉算子"""

    def __init__(self, crossover_rate: float = 0.3):
        self.crossover_rate = crossover_rate

    def crossover(
        self,
        parent1: PersonalityProfile,
        parent2: PersonalityProfile,
    ) -> Tuple[PersonalityProfile, PersonalityProfile]:
        """
        交叉两个人格配置

        Returns:
            (child1, child2) 或 (child1, None) 单亲繁殖
        """
        if random.random() > self.crossover_rate:
            # 不进行交叉，复制父母
            return parent1.mutate(), parent2.mutate()

        # 基因交叉
        child1 = parent1.crossover(parent2)
        child2 = parent2.crossover(parent1)

        return child1, child2


class NicheFormation:
    """
    生态位形成

    负责：
    1. 检测生态位重叠
    2. 促进生态位分化
    3. 维持多样性
    """

    def __init__(self, min_niche_distance: float = 0.3):
        self.min_niche_distance = min_niche_distance
        self.niches: Dict[str, List[str]] = defaultdict(list)  # niche_id -> [agent_ids]
        self.agent_niches: Dict[str, str] = {}  # agent_id -> niche_id

    def assign_niche(
        self,
        agent_id: str,
        personality: PersonalityProfile,
    ) -> str:
        """
        为个体分配生态位

        如果存在相似生态位，则加入
        否则创建新生态位
        """
        # 查找相似生态位
        for niche_id, members in self.niches.items():
            if members:
                # 简化的生态位相似度判断
                if random.random() < 0.7:
                    self.niches[niche_id].append(agent_id)
                    self.agent_niches[agent_id] = niche_id
                    return niche_id

        # 创建新生态位
        new_niche_id = f"niche_{len(self.niches)}"
        self.niches[new_niche_id].append(agent_id)
        self.agent_niches[agent_id] = new_niche_id
        return new_niche_id

    def calculate_niche_overlap(self) -> float:
        """计算生态位重叠度"""
        if len(self.niches) <= 1:
            return 0.0

        total_overlap = 0.0
        for niche1_id, members1 in self.niches.items():
            for niche2_id, members2 in self.niches.items():
                if niche1_id != niche2_id:
                    overlap = len(set(members1) & set(members2)) / max(len(members1), len(members2), 1)
                    total_overlap += overlap

        avg_overlap = total_overlap / max(len(self.niches) * (len(self.niches) - 1), 1)
        return avg_overlap

    def apply_diversification_pressure(self, fitness_scores: Dict[str, FitnessScore]):
        """
        应用多样化选择压力

        对处于拥挤生态位的个体施加额外压力
        """
        penalties = {}

        for niche_id, members in self.niches.items():
            if len(members) > 5:  # 生态位过于拥挤
                # 对适应度最低的个体施加惩罚
                member_fitness = [(mid, fitness_scores.get(mid, FitnessScore(mid)).overall_fitness)
                                for mid in members]
                member_fitness.sort(key=lambda x: x[1])

                for i, (mid, _) in enumerate(member_fitness[:2]):  # 最差的2个
                    penalties[mid] = 0.1 * (i + 1)  # 递减惩罚

        return penalties


class EvolutionEngine:
    """
    进化引擎核心

    整合所有进化机制：
    1. 适应度评估
    2. 选择
    3. 变异
    4. 交叉
    5. 生态位形成
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.config = config or {}
        self.selection_pressure = SelectionPressure(
            self.config.get("selection_pressure")
        )
        self.mutation_op = MutationOperator(
            self.config.get("mutation_rate", 0.1)
        )
        self.crossover_op = CrossoverOperator(
            self.config.get("crossover_rate", 0.3)
        )
        self.niche_formation = NicheFormation()

        # 进化事件记录
        self.evolution_history: List[EvolutionEvent] = []

        # 当前种群
        self.population: Dict[str, Dict[str, Any]] = {}

    def register_agent(
        self,
        agent_id: str,
        personality: PersonalityProfile,
        cognition: CognitiveSpace,
        thinking_engine: ThinkingEngine,
    ):
        """注册个体"""
        self.population[agent_id] = {
            "personality": personality,
            "cognition": cognition,
            "thinking_engine": thinking_engine,
            "fitness": FitnessScore(agent_id),
            "registered_at": time.time(),
            "niche_id": self.niche_formation.assign_niche(agent_id, personality),
        }

    def evaluate_fitness(
        self,
        agent_id: str,
        evaluation_data: Dict[str, Any],
    ) -> FitnessScore:
        """
        评估个体适应度

        Args:
            agent_id: 个体ID
            evaluation_data: 评估数据，包含：
                - recent_thoughts: 近期思考
                - communications: 交流记录
                - cooperation_events: 合作事件
        """
        if agent_id not in self.population:
            return FitnessScore(agent_id=agent_id)

        agent = self.population[agent_id]
        score = FitnessScore(agent_id=agent_id)

        # 评估思考质量
        recent_thoughts = evaluation_data.get("recent_thoughts", [])
        if recent_thoughts:
            score.thinking_quality = sum(
                t.get("depth_score", 0) + t.get("creativity_score", 0) + t.get("logical_score", 0)
                for t in recent_thoughts
            ) / (len(recent_thoughts) * 3)

        # 评估交流能力
        communications = evaluation_data.get("communications", [])
        if communications:
            score.communication_ability = sum(
                c.get("clarity_score", 0.5) * c.get("engagement_score", 0.5)
                for c in communications
            ) / len(communications)

        # 生态位适应（基于所在生态位）
        niche_id = agent["niche_id"]
        niche_members = self.niche_formation.niches.get(niche_id, [])
        score.niche_adaptation = 1.0 / max(len(niche_members), 1)

        # 合作能力
        cooperation_events = evaluation_data.get("cooperation_events", [])
        score.cooperation_score = min(1.0, len(cooperation_events) / 10)

        # 创新能力（基于新概念数量）
        cognition = agent["cognition"]
        novelty_count = sum(
            1 for c in cognition.concepts.values()
            if "novel" in c.concept_id
        )
        score.innovation_score = min(1.0, novelty_count / 5)

        # 计算综合评分
        score.calculate_overall()

        # 更新个体
        agent["fitness"] = score

        return score

    def evolve_generation(
        self,
        stage: str,
        generation_size: int,
    ) -> List[EvolutionEvent]:
        """
        进化一代

        执行完整的进化循环：
        1. 评估适应度
        2. 应用选择压力
        3. 执行变异和交叉
        4. 更新生态位

        Returns:
            进化事件列表
        """
        events = []

        # 1. 选择
        fitness_scores = [agent["fitness"] for agent in self.population.values()]
        survival_probs = self.selection_pressure.evaluate(fitness_scores, stage)

        # 记录选择事件
        selected = [(aid, prob) for aid, prob in survival_probs if random.random() < prob]
        events.append(EvolutionEvent(
            event_id=f"sel_{int(time.time())}",
            event_type="SELECTION",
            participants=[aid for aid, _ in selected],
            result={"selected_count": len(selected)},
            description=f"选择了 {len(selected)} 个个体"
        ))

        # 2. 多样化压力
        penalties = self.niche_formation.apply_diversification_pressure(
            {aid: self.population[aid]["fitness"] for aid in self.population}
        )

        # 3. 变异和交叉
        new_generation = {}
        selected_ids = [aid for aid, _ in selected]

        # 复制优秀个体
        for agent_id in selected_ids:
            if agent_id in self.population:
                new_generation[agent_id] = self.population[agent_id].copy()

        # 交叉产生新个体
        if len(selected_ids) >= 2:
            parent1_id, parent2_id = random.sample(selected_ids, 2)
            parent1 = self.population[parent1_id]["personality"]
            parent2 = self.population[parent2_id]["personality"]

            child1, child2 = self.crossover_op.crossover(parent1, parent2)

            # 创建新个体
            for child in [child1, child2]:
                if child:
                    child_id = f"agent_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
                    mutated_personality = self.mutation_op.mutate_personality(
                        child,
                        pressure_dimension="innovation" if random.random() < 0.3 else None
                    )

                    # 更新认知空间
                    cognition = self.population[parent1_id]["cognition"]
                    mutated_cognition = self.mutation_op.mutate_cognition(cognition)

                    new_generation[child_id] = {
                        "personality": mutated_personality,
                        "cognition": mutated_cognition,
                        "thinking_engine": self.population[parent1_id]["thinking_engine"],
                        "fitness": FitnessScore(child_id),
                        "registered_at": time.time(),
                        "niche_id": self.niche_formation.assign_niche(child_id, mutated_personality),
                    }

                    events.append(EvolutionEvent(
                        event_id=f"birth_{child_id}",
                        event_type="CROSSOVER",
                        participants=[parent1_id, parent2_id, child_id],
                        result={"child_id": child_id},
                        description=f"从 {parent1_id} 和 {parent2_id} 交叉产生 {child_id}"
                    ))

        # 4. 限制种群大小
        if len(new_generation) > generation_size:
            # 保留适应度最高的
            sorted_agents = sorted(
                new_generation.items(),
                key=lambda x: x[1]["fitness"].overall_fitness,
                reverse=True
            )
            new_generation = dict(sorted_agents[:generation_size])

        # 5. 更新种群
        self.population = new_generation

        # 6. 更新生态位
        self.niche_formation = NicheFormation()
        for agent_id, agent in self.population.items():
            agent["niche_id"] = self.niche_formation.assign_niche(
                agent_id, agent["personality"]
            )

        self.evolution_history.extend(events)
        return events

    def get_evolution_statistics(self) -> Dict[str, Any]:
        """获取进化统计"""
        if not self.population:
            return {"population_size": 0}

        fitness_scores = [a["fitness"].overall_fitness for a in self.population.values()]

        return {
            "population_size": len(self.population),
            "avg_fitness": sum(fitness_scores) / len(fitness_scores) if fitness_scores else 0,
            "max_fitness": max(fitness_scores) if fitness_scores else 0,
            "min_fitness": min(fitness_scores) if fitness_scores else 0,
            "niche_count": len(self.niche_formation.niches),
            "niche_overlap": self.niche_formation.calculate_niche_overlap(),
            "evolution_events": len(self.evolution_history),
        }