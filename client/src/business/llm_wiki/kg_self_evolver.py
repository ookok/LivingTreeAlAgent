"""
EvoRAG知识图谱自进化模块
实现关系融合和关系抑制
"""
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
from collections import deque

from loguru import logger
from client.src.business.llm_wiki.feedback_manager import FeedbackManager, TripletScore


@dataclass
class ShortcutEdge:
    """捷径边（关系融合产物）"""
    head: str                           # 头实体
    relation: str                        # 关系标签（由LLM推荐）
    tail: str                            # 尾实体
    avg_score: float                     # 平均路径分数
    source_path: List[str]               # 来源路径（三元组ID列表）
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    usage_count: int = 0                # 使用次数


class KnowledgeGraphSelfEvolver:
    """
    知识图谱自进化器
    实现EvoRAG的关系中心KG进化策略
    """

    def __init__(
        self,
        feedback_manager: FeedbackManager,
        max_hops: int = 3,
        min_path_score: float = 0.6
    ):
        """
        初始化自进化器

        Args:
            feedback_manager: 反馈管理器（用于获取三元组评分）
            max_hops: 最大跳数
            min_path_score: 最小路径分数阈值
        """
        self.feedback_manager = feedback_manager
        self.max_hops = max_hops
        self.min_path_score = min_path_score

        # 捷径边集合
        self.shortcut_edges: List[ShortcutEdge] = []

        # 抑制三元组集合（软降级）
        self.suppressed_triplets: Set[str] = set()

        # 恢复候选（动态恢复机制）
        self.recovery_candidates: Dict[str, int] = {}  # {triplet_id: recovery_score}

        logger.info(f"[KnowledgeGraphSelfEvolver] 初始化完成, "
                    f"最大跳数: {max_hops}, "
                    f"最小路径分数: {min_path_score}")

    def evolve_knowledge_graph(
        self,
        knowledge_graph: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行KG进化（Algorithm 1: Feedback-driven KG Evolution）

        Args:
            knowledge_graph: 知识图谱数据结构
                            {triplet_id: {head, relation, tail, ...}}

        Returns:
            进化后的知识图谱
        """
        logger.info("[KnowledgeGraphSelfEvolver] 开始KG进化...")

        # 步骤1: 计算阈值
        scores = [s.contribution_score
                  for s in self.feedback_manager.triplet_scores.values()]
        if not scores:
            logger.warning("[KnowledgeGraphSelfEvolver] 无三元组评分, 跳过进化")
            return knowledge_graph

        mean_score = np.mean(scores)
        std_score = np.std(scores)
        tau_high = mean_score + std_score
        tau_low = mean_score - std_score

        logger.info(f"[KnowledgeGraphSelfEvolver] 阈值计算, "
                    f"均值: {mean_score:.3f}, "
                    f"标准差: {std_score:.3f}, "
                    f"τhigh: {tau_high:.3f}, "
                    f"τlow: {tau_low:.3f}")

        # 步骤2: 识别起始三元组（高贡献）
        t_start_set = [
            tid for tid, ts in self.feedback_manager.triplet_scores.items()
            if ts.contribution_score >= tau_high
        ]

        logger.info(f"[KnowledgeGraphSelfEvolver] 高贡献起始三元组: {len(t_start_set)}")

        # 步骤3: 并行处理每个起始三元组（这里简化为顺序处理）
        shortcuts = []
        for t_start_id in t_start_set:
            if t_start_id not in knowledge_graph:
                continue

            # BFS搜索高质量路径
            path_shortcuts = self._find_shortcut_paths(
                t_start_id=t_start_id,
                knowledge_graph=knowledge_graph,
                tau_high=tau_high
            )
            shortcuts.extend(path_shortcuts)

        # 步骤4: 添加捷径边到KG
        evolved_kg = knowledge_graph.copy()
        for shortcut in shortcuts:
            # 检查是否已存在相同边
            edge_exists = False
            for tg_id, tg_data in evolved_kg.items():
                if (tg_data.get('head') == shortcut.head and
                    tg_data.get('tail') == shortcut.tail):
                    edge_exists = True
                    break

            if not edge_exists:
                # 添加捷径边
                shortcut_id = f"shortcut_{len(evolved_kg)}"
                evolved_kg[shortcut_id] = {
                    'head': shortcut.head,
                    'relation': shortcut.relation,
                    'tail': shortcut.tail,
                    'type': 'shortcut',
                    'avg_score': shortcut.avg_score,
                    'source_path': shortcut.source_path,
                    'created_at': shortcut.created_at
                }
                shortcuts.append(shortcut)

        # 步骤5: 更新抑制集合
        self._update_suppressed_triplets(tau_low, knowledge_graph)

        logger.info(f"[KnowledgeGraphSelfEvolver] KG进化完成, "
                    f"新增捷径边: {len(shortcuts)}, "
                    f"抑制三元组: {len(self.suppressed_triplets)}")

        return evolved_kg

    def _find_shortcut_paths(
        self,
        t_start_id: str,
        knowledge_graph: Dict[str, Any],
        tau_high: float
    ) -> List[ShortcutEdge]:
        """
        查找可融合的路径（创建捷径边）

        Args:
            t_start_id: 起始三元组ID
            knowledge_graph: 知识图谱
            tau_high: 高质量阈值

        Returns:
            捷径边列表
        """
        shortcuts = []

        # 获取起始三元组
        t_start = knowledge_graph.get(t_start_id)
        if not t_start:
            return shortcuts

        # BFS搜索
        frontier = [(t_start_id, [t_start_id])]  # (当前三元组, 路径)

        for hop in range(self.max_hops):
            next_frontier = []

            for curr_tid, path in frontier:
                curr_triplet = knowledge_graph.get(curr_tid)
                if not curr_triplet:
                    continue

                # 获取邻居三元组
                neighbors = self._get_neighbor_triplets(
                    curr_triplet, knowledge_graph
                )

                # 按贡献分数排序（降序）
                neighbors.sort(
                    key=lambda x: self.feedback_manager.triplet_scores.get(
                        x[0], TripletScore(triplet_id=x[0])
                    ).contribution_score,
                    reverse=True
                )

                for nbr_tid, nbr_triplet in neighbors:
                    # 检查路径分数
                    path_score = self._compute_path_avg_score(path + [nbr_tid])

                    if path_score < tau_high:
                        # 低于阈值，终止该路径
                        break

                    # 检查是否已存在直接边
                    head = knowledge_graph[t_start_id]['head']
                    tail = nbr_triplet['tail']

                    if self._edge_exists(head, tail, knowledge_graph):
                        # 已存在边，创建捷径边
                        shortcut = ShortcutEdge(
                            head=head,
                            relation=self._recommend_relation(path + [nbr_tid]),
                            tail=tail,
                            avg_score=path_score,
                            source_path=path + [nbr_tid]
                        )
                        shortcuts.append(shortcut)

                    # 继续搜索
                    next_frontier.append((nbr_tid, path + [nbr_tid]))

            frontier = next_frontier

            if not frontier:
                break

        return shortcuts

    def _get_neighbor_triplets(
        self,
        triplet: Dict[str, Any],
        knowledge_graph: Dict[str, Any]
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        获取邻居三元组

        Args:
            triplet: 当前三元组
            knowledge_graph: 知识图谱

        Returns:
            [(triplet_id, triplet_data), ...]
        """
        neighbors = []
        tail_entity = triplet.get('tail')

        for tid, tdata in knowledge_graph.items():
            if tdata.get('head') == tail_entity:
                neighbors.append((tid, tdata))

        return neighbors

    def _compute_path_avg_score(self, path: List[str]) -> float:
        """
        计算路径平均分数

        Args:
            path: 三元组ID路径

        Returns:
            平均分数
        """
        scores = []
        for tid in path:
            if tid in self.feedback_manager.triplet_scores:
                scores.append(
                    self.feedback_manager.triplet_scores[tid].contribution_score
                )

        if not scores:
            return 0.0

        return np.mean(scores)

    def _edge_exists(self, head: str, tail: str, knowledge_graph: Dict[str, Any]) -> bool:
        """
        检查边是否已存在

        Args:
            head: 头实体
            tail: 尾实体
            knowledge_graph: 知识图谱

        Returns:
            是否存在
        """
        for tg_data in knowledge_graph.values():
            if tg_data.get('head') == head and tg_data.get('tail') == tail:
                return True
        return False

    def _recommend_relation(self, path: List[str]) -> str:
        """
        推荐关系标签（简化版）

        原文使用LLM根据路径语义推荐
        这里使用简化逻辑：合并路径上的所有关系

        Args:
            path: 三元组ID路径

        Returns:
            推荐的关系标签
        """
        # 简化版：使用 "path_relation" 格式
        return f"path_via_{len(path)}_triplets"

    def _update_suppressed_triplets(
        self,
        tau_low: float,
        knowledge_graph: Dict[str, Any]
    ) -> None:
        """
        更新抑制三元组集合

        Args:
            tau_low: 低质量阈值
            knowledge_graph: 知识图谱
        """
        self.suppressed_triplets.clear()

        for tid, ts in self.feedback_manager.triplet_scores.items():
            if ts.contribution_score < tau_low:
                self.suppressed_triplets.add(tid)

        logger.debug(f"[KnowledgeGraphSelfEvolver] 更新抑制集合, "
                     f"低质量三元组: {len(self.suppressed_triplets)}")

    def get_triplet_priority_with_suppression(
        self,
        triplet_id: str
    ) -> float:
        """
        获取考虑抑制的优先级

        EvoRAG的软降级策略：
        - 抑制的三元组优先级降低
        - 但保留动态恢复的可能性

        Args:
            triplet_id: 三元组ID

        Returns:
            优先级 [0, 1]
        """
        base_priority = self.feedback_manager.get_triplet_priority(triplet_id)

        if triplet_id in self.suppressed_triplets:
            # 软降级：降低优先级但不完全移除
            return base_priority * 0.3
        elif triplet_id in self.recovery_candidates:
            # 恢复候选：逐步提升优先级
            recovery_score = self.recovery_candidates[triplet_id]
            return base_priority * (0.5 + 0.5 * min(recovery_score / 10.0, 1.0))
        else:
            return base_priority

    def dynamic_recovery(
        self,
        triplet_id: str,
        query: str,
        semantic_similarity: float
    ) -> None:
        """
        动态恢复机制

        如果被抑制的三元组对某个查询具有高语义相关性，
        则将其加入恢复候选

        Args:
            triplet_id: 三元组ID
            query: 用户查询
            semantic_similarity: 语义相似度
        """
        if triplet_id not in self.suppressed_triplets:
            return

        # 如果语义相似度高，加入恢复候选
        if semantic_similarity > 0.7:
            if triplet_id not in self.recovery_candidates:
                self.recovery_candidates[triplet_id] = 0

            self.recovery_candidates[triplet_id] += 1

            logger.debug(f"[KnowledgeGraphSelfEvolver] 动态恢复候选, "
                         f"三元组: {triplet_id}, "
                         f"恢复分数: {self.recovery_candidates[triplet_id]}")

            # 如果恢复分数足够高，从抑制集合中移除
            if self.recovery_candidates[triplet_id] >= 5:
                self.suppressed_triplets.remove(triplet_id)
                logger.info(f"[KnowledgeGraphSelfEvolver] 三元组恢复, "
                            f"三元组: {triplet_id}")

    def get_shortcut_edges(self) -> List[ShortcutEdge]:
        """获取所有捷径边"""
        return self.shortcut_edges

    def get_suppressed_triplets(self) -> Set[str]:
        """获取所有被抑制的三元组"""
        return self.suppressed_triplets

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'shortcut_edges_count': len(self.shortcut_edges),
            'suppressed_triplets_count': len(self.suppressed_triplets),
            'recovery_candidates_count': len(self.recovery_candidates),
            'max_hops': self.max_hops,
            'min_path_score': self.min_path_score
        }


if __name__ == "__main__":
    # 测试KG自进化器
    from client.src.business.llm_wiki.feedback_manager import FeedbackManager

    # 创建反馈管理器
    fm = FeedbackManager()

    # 模拟一些三元组评分
    fm.triplet_scores['t1'] = TripletScore(triplet_id='t1', contribution_score=0.9)
    fm.triplet_scores['t2'] = TripletScore(triplet_id='t2', contribution_score=0.8)
    fm.triplet_scores['t3'] = TripletScore(triplet_id='t3', contribution_score=0.3)
    fm.triplet_scores['t4'] = TripletScore(triplet_id='t4', contribution_score=0.2)

    # 创建自进化器
    evolver = KnowledgeGraphSelfEvolver(fm, max_hops=2)

    # 模拟知识图谱
    kg = {
        't1': {'head': 'EntityA', 'relation': 'rel1', 'tail': 'EntityB'},
        't2': {'head': 'EntityB', 'relation': 'rel2', 'tail': 'EntityC'},
        't3': {'head': 'EntityC', 'relation': 'rel3', 'tail': 'EntityD'},
        't4': {'head': 'EntityD', 'relation': 'rel4', 'tail': 'EntityE'}
    }

    # 执行进化
    evolved_kg = evolver.evolve_knowledge_graph(kg)

    print(f"原始KG大小: {len(kg)}")
    print(f"进化后KG大小: {len(evolved_kg)}")
    print(f"统计信息: {evolver.get_statistics()}")

    # 测试动态恢复
    evolver.dynamic_recovery('t3', 'test query', 0.8)
    print(f"恢复候选: {evolver.recovery_candidates}")
