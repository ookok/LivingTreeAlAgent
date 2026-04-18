"""
个性化人格参数 - Personality Parameters

定义AI个体的多维人格特质，影响思考方式和行为模式。

人格维度：
- 逻辑性 vs 创造性
- 保守性 vs 冒险性
- 深度 vs 广度
- 速度 vs 准确性
- 同理心 vs 攻击性
"""

import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class PersonalityDimension(Enum):
    """人格维度枚举"""
    # 思考风格
    LOGICAL = "logical"                    # 逻辑性 0-1
    CREATIVE = "creative"                 # 创造性 0-1
    DEPTH = "depth"                       # 深度 0-1
    BREADTH = "breadth"                   # 广度 0-1

    # 行为倾向
    CONSERVATIVE = "conservative"         # 保守性 0-1
    ADVENTUROUS = "adventurous"           # 冒险性 0-1
    CAUTIOUS = "cautious"                # 谨慎性 0-1
    BOLD = "bold"                         # 大胆性 0-1

    # 社交风格
    EMPATHETIC = "empathetic"             # 同理心 0-1
    ANALYTICAL = "analytical"            # 分析性 0-1
    COOPERATIVE = "cooperative"          # 合作性 0-1
    COMPETITIVE = "competitive"          # 竞争性 0-1

    # 表达风格
    CONCISE = "concise"                   # 简洁性 0-1
    VERBOSE = "verbose"                   # 详尽性 0-1
    HUMOROUS = "humorous"                # 幽默感 0-1
    SERIOUS = "serious"                  # 严肃性 0-1


@dataclass
class PersonalityProfile:
    """
    个性化人格配置

    每个AI拥有独特的人格配置，决定其思考和交流方式。
    配置通过基因式编码，可以进行进化和变异。
    """

    # 基础标识
    profile_id: str
    name: str
    created_at: float = field(default_factory=time.time)

    # 核心人格维度 (0.0 - 1.0)
    dimensions: Dict[str, float] = field(default_factory=dict)

    # 专业领域权重
    expertise_domains: Dict[str, float] = field(default_factory=dict)

    # 兴趣标签
    interest_tags: List[str] = field(default_factory=list)

    # 元信息
    generation: int = 0                  # 进化代数
    parent_id: Optional[str] = None      # 父代ID

    def __post_init__(self):
        """初始化时设置默认维度"""
        if not self.dimensions:
            self.dimensions = self._random_init_dimensions()

    def _random_init_dimensions(self) -> Dict[str, float]:
        """随机初始化人格维度"""
        return {dim.value: random.random() for dim in PersonalityDimension}

    def get_dimension(self, dimension: PersonalityDimension) -> float:
        """获取维度值"""
        return self.dimensions.get(dimension.value, 0.5)

    def set_dimension(self, dimension: PersonalityDimension, value: float):
        """设置维度值"""
        self.dimensions[dimension.value] = max(0.0, min(1.0, value))

    def get_cognitive_style(self) -> Dict[str, Any]:
        """获取认知风格摘要"""
        return {
            "thinking_style": self._classify_thinking_style(),
            "social_style": self._classify_social_style(),
            "expression_style": self._classify_expression_style(),
            "primary_domains": self._get_top_domains(3),
            "adaptation_level": self._calculate_adaptation_level(),
        }

    def _classify_thinking_style(self) -> str:
        """分类思考风格"""
        logical = self.get_dimension(PersonalityDimension.LOGICAL)
        creative = self.get_dimension(PersonalityDimension.CREATIVE)
        depth = self.get_dimension(PersonalityDimension.DEPTH)

        if logical > 0.7 and depth > 0.7:
            return "deep_analytical"
        elif creative > 0.7:
            return "divergent_creative"
        elif logical > 0.6:
            return "balanced_reasoning"
        else:
            return "intuitive_synthetic"

    def _classify_social_style(self) -> str:
        """分类社交风格"""
        empathetic = self.get_dimension(PersonalityDimension.EMPATHETIC)
        cooperative = self.get_dimension(PersonalityDimension.COOPERATIVE)
        competitive = self.get_dimension(PersonalityDimension.COMPETITIVE)

        if empathetic > 0.7 and cooperative > 0.7:
            return "nurturing_collaborator"
        elif cooperative > 0.7:
            return "team_player"
        elif competitive > 0.7:
            return "healthy_competitor"
        else:
            return "independent_thinker"

    def _classify_expression_style(self) -> str:
        """分类表达风格"""
        concise = self.get_dimension(PersonalityDimension.CONCISE)
        humorous = self.get_dimension(PersonalityDimension.HUMOROUS)
        serious = self.get_dimension(PersonalityDimension.SERIOUS)

        if concise > 0.7:
            return "precise_and_punchy"
        elif humorous > 0.7:
            return "witty_and_engaging"
        elif serious > 0.7:
            return "scholarly_and_thorough"
        else:
            return "warm_and_accessible"

    def _get_top_domains(self, n: int) -> List[str]:
        """获取Top N专业领域"""
        sorted_domains = sorted(
            self.expertise_domains.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [d[0] for d in sorted_domains[:n]]

    def _calculate_adaptation_level(self) -> float:
        """计算适应度水平"""
        values = list(self.dimensions.values())
        if not values:
            return 0.5
        avg = sum(values) / len(values)
        variance = sum((v - avg) ** 2 for v in values) / len(values)
        balance_score = 1.0 - min(1.0, variance ** 0.5)
        avg_expertise = sum(self.expertise_domains.values()) / len(self.expertise_domains) if self.expertise_domains else 0.5
        return balance_score * 0.4 + avg_expertise * 0.6

    def to_gene_sequence(self) -> str:
        """将人格转换为基因序列"""
        dim_genes = "".join([
            format(int(v * 31), '05b')
            for v in self.dimensions.values()
        ])
        domain_genes = ""
        sorted_domains = sorted(self.expertise_domains.items(), key=lambda x: x[1], reverse=True)
        for domain, weight in sorted_domains[:8]:
            domain_genes += format(int(weight * 31), '05b')
        return dim_genes + domain_genes

    @classmethod
    def from_gene_sequence(cls, gene_seq: str, name: str, profile_id: str) -> 'PersonalityProfile':
        """从基因序列创建人格配置"""
        dimensions = {}
        dim_names = [d.value for d in PersonalityDimension]
        for i, dim_name in enumerate(dim_names):
            start = i * 5
            end = start + 5
            if end <= len(gene_seq):
                value = int(gene_seq[start:end], 2) / 31.0
                dimensions[dim_name] = value

        expertise_domains = {}
        domain_start = len(dim_names) * 5
        domain_names = ["philosophy", "science", "technology", "arts", "literature",
                       "psychology", "economics", "politics"]
        for i, dname in enumerate(domain_names):
            start = domain_start + i * 5
            end = start + 5
            if end <= len(gene_seq):
                expertise_domains[dname] = int(gene_seq[start:end], 2) / 31.0

        return cls(
            profile_id=profile_id,
            name=name,
            dimensions=dimensions,
            expertise_domains=expertise_domains,
        )

    def crossover(self, other: 'PersonalityProfile') -> 'PersonalityProfile':
        """与另一个配置进行交叉"""
        gene1 = self.to_gene_sequence()
        gene2 = other.to_gene_sequence()
        crossover_point = random.randint(1, min(len(gene1), len(gene2)) - 1)
        child_gene = gene1[:crossover_point] + gene2[crossover_point:]
        child = PersonalityProfile.from_gene_sequence(
            child_gene,
            name=f"{self.name}_x_{other.name}",
            profile_id=f"child_{random.randint(1000, 9999)}"
        )
        child.generation = max(self.generation, other.generation) + 1
        child.parent_id = self.profile_id
        return child

    def mutate(self, mutation_rate: float = 0.1) -> 'PersonalityProfile':
        """变异"""
        new_dimensions = self.dimensions.copy()
        for dim in PersonalityDimension:
            if random.random() < mutation_rate:
                current = new_dimensions.get(dim.value, 0.5)
                mutation = random.gauss(0, 0.1)
                new_dimensions[dim.value] = max(0.0, min(1.0, current + mutation))

        new_domains = self.expertise_domains.copy()
        for domain in new_domains:
            if random.random() < mutation_rate:
                mutation = random.gauss(0, 0.1)
                new_domains[domain] = max(0.0, min(1.0, new_domains[domain] + mutation))

        return PersonalityProfile(
            profile_id=f"mut_{random.randint(1000, 9999)}",
            name=f"{self.name}_mut",
            dimensions=new_dimensions,
            expertise_domains=new_domains,
            generation=self.generation + 1,
            parent_id=self.profile_id,
        )

    def calculate_cognitive_distance(self, other: 'PersonalityProfile') -> float:
        """计算与另一个体的认知距离"""
        all_dims = set(self.dimensions.keys()) | set(other.dimensions.keys())
        dim_distance = 0.0
        for dim in all_dims:
            v1 = self.dimensions.get(dim, 0.5)
            v2 = other.dimensions.get(dim, 0.5)
            dim_distance += (v1 - v2) ** 2
        dim_distance = (dim_distance / len(all_dims)) ** 0.5 if all_dims else 0

        all_domains = set(self.expertise_domains.keys()) | set(other.expertise_domains.keys())
        domain_overlap = 0.0
        if all_domains:
            for domain in all_domains:
                v1 = self.expertise_domains.get(domain, 0)
                v2 = other.expertise_domains.get(domain, 0)
                domain_overlap += abs(v1 - v2)
            domain_overlap /= len(all_domains)

        return 0.7 * dim_distance + 0.3 * domain_overlap

    def calculate_communication_probability(self, other: 'PersonalityProfile') -> float:
        """计算与另一个体交流的概率"""
        cognitive_distance = self.calculate_cognitive_distance(other)
        if cognitive_distance < 0.2:
            similarity_weight = 0.8
        elif cognitive_distance > 0.6:
            similarity_weight = 0.3
        else:
            similarity_weight = 1.0
        optimal_distance = 0.35
        distance_factor = 1.0 - abs(cognitive_distance - optimal_distance)
        base_prob = 0.3
        return base_prob * similarity_weight * distance_factor

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "created_at": self.created_at,
            "dimensions": self.dimensions,
            "expertise_domains": self.expertise_domains,
            "interest_tags": self.interest_tags,
            "generation": self.generation,
            "parent_id": self.parent_id,
            "cognitive_style": self.get_cognitive_style(),
        }

    def __str__(self) -> str:
        top_domains = self._get_top_domains(2)
        return f"Personality({self.name}, gen={self.generation}, domains={top_domains})"


class PersonalityFactory:
    """人格工厂"""

    @staticmethod
    def create_balanced(name: str, profile_id: str) -> PersonalityProfile:
        dimensions = {dim.value: 0.5 for dim in PersonalityDimension}
        return PersonalityProfile(
            profile_id=profile_id, name=name, dimensions=dimensions,
            expertise_domains={"philosophy": 0.6, "science": 0.6, "technology": 0.6, "arts": 0.6},
        )

    @staticmethod
    def create_logical_analyzer(name: str, profile_id: str) -> PersonalityProfile:
        dimensions = {
            PersonalityDimension.LOGICAL.value: 0.9, PersonalityDimension.DEPTH.value: 0.8,
            PersonalityDimension.CAUTIOUS.value: 0.7, PersonalityDimension.ANALYTICAL.value: 0.9,
            PersonalityDimension.CONCISE.value: 0.7, PersonalityDimension.SERIOUS.value: 0.8,
            PersonalityDimension.CREATIVE.value: 0.3, PersonalityDimension.ADVENTUROUS.value: 0.2,
        }
        return PersonalityProfile(
            profile_id=profile_id, name=name, dimensions=dimensions,
            expertise_domains={"science": 0.9, "technology": 0.8, "philosophy": 0.7, "economics": 0.6},
        )

    @staticmethod
    def create_creative_explorer(name: str, profile_id: str) -> PersonalityProfile:
        dimensions = {
            PersonalityDimension.CREATIVE.value: 0.9, PersonalityDimension.ADVENTUROUS.value: 0.9,
            PersonalityDimension.BREADTH.value: 0.8, PersonalityDimension.BOLD.value: 0.8,
            PersonalityDimension.HUMOROUS.value: 0.7,
            PersonalityDimension.CONSERVATIVE.value: 0.2, PersonalityDimension.CAUTIOUS.value: 0.3,
            PersonalityDimension.LOGICAL.value: 0.4,
        }
        return PersonalityProfile(
            profile_id=profile_id, name=name, dimensions=dimensions,
            expertise_domains={"arts": 0.9, "literature": 0.8, "psychology": 0.7, "philosophy": 0.8},
        )

    @staticmethod
    def create_empathetic_communicator(name: str, profile_id: str) -> PersonalityProfile:
        dimensions = {
            PersonalityDimension.EMPATHETIC.value: 0.9, PersonalityDimension.COOPERATIVE.value: 0.9,
            PersonalityDimension.HUMOROUS.value: 0.7, PersonalityDimension.VERBOSE.value: 0.7,
            PersonalityDimension.SERIOUS.value: 0.2,
            PersonalityDimension.COMPETITIVE.value: 0.2, PersonalityDimension.ANALYTICAL.value: 0.4,
        }
        return PersonalityProfile(
            profile_id=profile_id, name=name, dimensions=dimensions,
            expertise_domains={"psychology": 0.9, "literature": 0.8, "philosophy": 0.7, "arts": 0.6},
        )

    @staticmethod
    def create_random(name: str, profile_id: str) -> PersonalityProfile:
        dimensions = {dim.value: random.random() for dim in PersonalityDimension}
        all_domains = ["philosophy", "science", "technology", "arts", "literature",
                       "psychology", "economics", "politics", "history", "biology"]
        n_domains = random.randint(3, 6)
        expertise = {d: random.random() for d in random.sample(all_domains, n_domains)}
        return PersonalityProfile(
            profile_id=profile_id, name=name, dimensions=dimensions,
            expertise_domains=expertise, interest_tags=random.sample(all_domains, 3),
        )