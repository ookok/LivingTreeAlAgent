"""
Epigenetic Learning - 表观遗传学习模块
实现拉马克主义（Lamarckian）和鲍德温效应（Baldwinian）

Author: LivingTreeAI Team
Version: 2.0.0
"""

from typing import Callable, Optional, List, Tuple
import numpy as np
import random
from dataclasses import dataclass, field


class LamarckianLearner:
    """
    拉马克主义学习器

    核心思想：个体在一生中通过学习获得的性状，
    可以直接写入基因，传递给后代。

    实现方式：
    1. 对每个个体执行局部搜索（如梯度下降、随机游走、爬山法）
    2. 将学习得到的改进直接覆盖到个体基因
    3. 后代继承改进后的基因
    """

    def __init__(
        self,
        learning_rate: float = 0.3,
        n_steps: int = 10,
        step_size: float = 0.1,
        method: str = "local_hill_climb",
    ):
        """
        Args:
            learning_rate: 拉马克比率（配置中的 lamarckian_rate）
            n_steps: 每个个体的局部搜索步数
            step_size: 每次搜索的步长
            method: 学习方法
                - "local_hill_climb": 局部爬山（默认）
                - "random_walk": 随机游走
                - "gaussian_perturbation": 高斯扰动
        """
        self.learning_rate = learning_rate
        self.n_steps = n_steps
        self.step_size = step_size
        self.method = method

    def apply(
        self,
        individuals: List["Individual"],
        fitness_func: Callable[[np.ndarray], float],
        gene_min: float = -10.0,
        gene_max: float = 10.0,
    ) -> List["Individual"]:
        """
        对种群应用拉马克学习

        对每个个体：
        1. 以 learning_rate 的概率触发学习
        2. 通过学习改进基因
        3. 直接修改个体的 genes（性状获得 → 基因写入）

        Returns:
            学习后的种群（原地修改，同时返回引用）
        """
        for ind in individuals:
            if random.random() >= self.learning_rate:
                continue  # 跳过此个体

            original_genes = ind.genes.copy()
            improved_genes = self._learn(original_genes, fitness_func, gene_min, gene_max)
            ind.genes = improved_genes
            # 拉马克主义：学习成果直接写入基因
            ind.learned_adjustments = improved_genes - original_genes
            ind.mutations.append({
                "type": "lamarckian_learning",
                "applied": True,
                "inherited": True,
            })

        return individuals

    def _learn(
        self,
        genes: np.ndarray,
        fitness_func: Callable[[np.ndarray], float],
        gene_min: float,
        gene_max: float,
    ) -> np.ndarray:
        """执行局部学习，返回改进后的基因"""
        best_genes = genes.copy()
        best_fitness = fitness_func(genes)

        if self.method == "local_hill_climb":
            return self._hill_climb(best_genes, best_fitness, fitness_func, gene_min, gene_max)
        elif self.method == "random_walk":
            return self._random_walk(best_genes, fitness_func, gene_min, gene_max)
        elif self.method == "gaussian_perturbation":
            return self._gaussian_perturbation(best_genes, fitness_func, gene_min, gene_max)
        else:
            return best_genes

    def _hill_climb(
        self,
        genes: np.ndarray,
        fitness: float,
        fitness_func: Callable[[np.ndarray], float],
        gene_min: float,
        gene_max: float,
    ) -> np.ndarray:
        """局部爬山法：沿梯度方向（近似）搜索"""
        current = genes.copy()
        current_fitness = fitness

        for _ in range(self.n_steps):
            # 随机选择一个维度进行扰动
            dim = random.randint(0, len(current) - 1)
            delta = self.step_size * random.choice([-1, 1])

            candidate = current.copy()
            candidate[dim] += delta
            candidate[dim] = np.clip(candidate[dim], gene_min, gene_max)

            candidate_fitness = fitness_func(candidate)
            if candidate_fitness > current_fitness:
                current = candidate
                current_fitness = candidate_fitness

        return current

    def _random_walk(
        self,
        genes: np.ndarray,
        fitness_func: Callable[[np.ndarray], float],
        gene_min: float,
        gene_max: float,
    ) -> np.ndarray:
        """随机游走：接受一定概率的劣化移动（模拟退火思想）"""
        current = genes.copy()
        current_fitness = fitness_func(genes)
        temperature = self.step_size * 10  # 初始温度

        for step in range(self.n_steps):
            candidate = current + np.random.normal(0, self.step_size, size=len(current))
            candidate = np.clip(candidate, gene_min, gene_max)

            candidate_fitness = fitness_func(candidate)
            delta = candidate_fitness - current_fitness

            # Metropolis 接受准则
            if delta > 0 or random.random() < np.exp(delta / max(temperature, 1e-8)):
                current = candidate
                current_fitness = candidate_fitness

            temperature *= 0.95  # 降温

        return current

    def _gaussian_perturbation(
        self,
        genes: np.ndarray,
        fitness_func: Callable[[np.ndarray], float],
        gene_min: float,
        gene_max: float,
    ) -> np.ndarray:
        """高斯扰动：生成多个候选，选最优"""
        best = genes.copy()
        best_fitness = fitness_func(genes)

        for _ in range(self.n_steps):
            candidate = genes + np.random.normal(0, self.step_size, size=len(genes))
            candidate = np.clip(candidate, gene_min, gene_max)
            candidate_fitness = fitness_func(candidate)

            if candidate_fitness > best_fitness:
                best = candidate
                best_fitness = candidate_fitness

        return best


class BaldwinianLeaner:
    """
    鲍德温效应学习器

    核心思想：个体在一生中可以学习，
    学习能力影响适应度（生存优势），
    但学习成果不直接写入基因。
    经过多代进化，原本需要学习的能力逐渐"固化"到基因中。

    实现方式：
    1. 对每个个体执行局部搜索，得到"学习后适应度"
    2. 用"学习后适应度"替代原始适应度（影响选择）
    3. 基因本身不修改（学习成果不遗传）
    4. 多代后：能快速学习优质解的个体有优势 → 优质解的基因逐渐占据主导
    """

    def __init__(
        self,
        learning_rate: float = 0.2,
        n_steps: int = 10,
        step_size: float = 0.1,
        method: str = "local_search",
    ):
        """
        Args:
            learning_rate: 鲍德温比率（配置中的 baldwin_rate）
            n_steps: 每个个体的学习步数
            step_size: 学习步长
            method: 学习方法
                - "local_search": 局部搜索（默认）
                - "random_walk": 随机游走
        """
        self.learning_rate = learning_rate
        self.n_steps = n_steps
        self.step_size = step_size
        self.method = method

    def compute_baldwin_fitness(
        self,
        individuals: List["Individual"],
        fitness_func: Callable[[np.ndarray], float],
        gene_min: float = -10.0,
        gene_max: float = 10.0,
    ) -> List[float]:
        """
        计算鲍德温适应度（学习后的适应度）

        对每个个体：
        1. 以 learning_rate 的概率触发学习
        2. 学习得到的适应度 > 原始适应度 → 使用学习适应度
        3. 基因不变，只影响选择压力

        Returns:
            鲍德温适应度列表（用于选择，不改变原始 fitness）
        """
        baldwin_fitnesses = []

        for ind in individuals:
            original_fitness = fitness_func(ind.genes)

            if random.random() >= self.learning_rate:
                # 不触发学习，使用原始适应度
                baldwin_fitnesses.append(original_fitness)
                continue

            # 执行学习，得到学习后的最优基因和适应度
            learned_genes = self._learn(ind.genes, fitness_func, gene_min, gene_max)
            learned_fitness = fitness_func(learned_genes)

            # 鲍德温效应：用学习后的适应度（但基因不修改）
            baldwin_fitnesses.append(learned_fitness)

            # 记录学习调整量（用于分析，不遗传）
            ind.learned_adjustments = learned_genes - ind.genes
            ind.mutations.append({
                "type": "baldwinian_learning",
                "original_fitness": original_fitness,
                "learned_fitness": learned_fitness,
                "inherited": False,  # 关键：不遗传
            })

        return baldwin_fitnesses

    def _learn(
        self,
        genes: np.ndarray,
        fitness_func: Callable[[np.ndarray], float],
        gene_min: float,
        gene_max: float,
    ) -> np.ndarray:
        """执行局部学习，返回学习到的最优基因"""
        best = genes.copy()
        best_fitness = fitness_func(genes)

        current = genes.copy()
        current_fitness = best_fitness

        for _ in range(self.n_steps):
            # 随机扰动
            candidate = current + np.random.normal(0, self.step_size, size=len(current))
            candidate = np.clip(candidate, gene_min, gene_max)
            candidate_fitness = fitness_func(candidate)

            # 只接受改进（纯贪心，也可用模拟退火）
            if candidate_fitness > current_fitness:
                current = candidate
                current_fitness = candidate_fitness

            if current_fitness > best_fitness:
                best = current.copy()
                best_fitness = current_fitness

        return best


class EpigeneticEngine:
    """
    表观遗传引擎 — 统一入口

    整合拉马克主义和鲍德温效应，
    在进化引擎的主循环中统一调用。
    """

    def __init__(
        self,
        lamarckian_rate: float = 0.3,
        baldwin_rate: float = 0.2,
        enabled: bool = True,
    ):
        self.enabled = enabled
        self.lamarckian_learner = LamarckianLearner(
            learning_rate=lamarckian_rate,
        )
        self.baldwinian_learner = BaldwinianLeaner(
            learning_rate=baldwin_rate,
        )

    def apply_epigenetic_learning(
        self,
        individuals: List["Individual"],
        fitness_func: Callable[[np.ndarray], float],
        gene_min: float = -10.0,
        gene_max: float = 10.0,
    ) -> Tuple[List["Individual"], Optional[List[float]]]:
        """
        应用表观遗传学习

        返回：
            (可能修改后的个体列表, 鲍德温适应度或 None)

        逻辑：
        - 如果 enabled=False：不做任何事，返回 (原列表, None)
        - 拉马克：直接修改个体基因 → 返回 (修改后列表, None)
        - 鲍德温：不修改基因，返回 (原列表, 鲍德温适应度列表)
        - 两者都启用：先拉马克（改基因），再鲍德温（影响选择适应度）
        """
        if not self.enabled:
            return individuals, None

        baldwin_fitnesses = None

        # 1. 拉马克学习（修改基因）
        if self.lamarckian_learner.learning_rate > 0:
            self.lamarckian_learner.apply(
                individuals, fitness_func, gene_min, gene_max
            )

        # 2. 鲍德温学习（只影响适应度，不修改基因）
        if self.baldwinian_learner.learning_rate > 0:
            baldwin_fitnesses = self.baldwinian_learner.compute_baldwin_fitness(
                individuals, fitness_func, gene_min, gene_max
            )

        return individuals, baldwin_fitnesses

    def update_rates(self, lamarckian_rate: float, baldwin_rate: float):
        """动态更新学习率（可在进化过程中自适应调整）"""
        self.lamarckian_learner.learning_rate = lamarckian_rate
        self.baldwinian_learner.learning_rate = baldwin_rate
        if lamarckian_rate > 0 or baldwin_rate > 0:
            self.enabled = True
        else:
            self.enabled = False
