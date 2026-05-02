"""
LivingTree Knowledge Wiki - EvoRAG 知识图谱自进化模块
====================================================

实现关系融合和关系抑制。

从 client/src/business/llm_wiki/kg_self_evolver.py 迁移而来。
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

try:
    import numpy as np
except ImportError:
    np = None

from loguru import logger

from .feedback_manager import FeedbackManager, TripletScore


@dataclass
class ShortcutEdge:
    """捷径边（关系融合产物）"""
    head: str
    relation: str
    tail: str
    avg_score: float
    source_path: List[str]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    usage_count: int = 0


class KnowledgeGraphSelfEvolver:
    """
    知识图谱自进化器
    实现 EvoRAG 的关系中心 KG 进化策略
    """

    def __init__(
        self,
        feedback_manager: FeedbackManager,
        max_hops: int = 3,
        min_path_score: float = 0.6
    ):
        self.feedback_manager = feedback_manager
        self.max_hops = max_hops
        self.min_path_score = min_path_score

        self.shortcut_edges: List[ShortcutEdge] = []
        self.suppressed_triplets: Set[str] = set()
        self.recovery_candidates: Dict[str, int] = {}

        logger.info(f"[KnowledgeGraphSelfEvolver] 初始化完成, "
                    f"最大跳数: {max_hops}, "
                    f"最小路径分数: {min_path_score}")

    def evolve_knowledge_graph(
        self,
        knowledge_graph: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info("[KnowledgeGraphSelfEvolver] 开始KG进化...")

        scores = [s.contribution_score
                  for s in self.feedback_manager.triplet_scores.values()]
        if not scores:
            logger.warning("[KnowledgeGraphSelfEvolver] 无三元组评分, 跳过进化")
            return knowledge_graph

        if np is None:
            mean_score = sum(scores) / len(scores)
            variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
            std_score = variance ** 0.5
        else:
            mean_score = float(np.mean(scores))
            std_score = float(np.std(scores))

        tau_high = mean_score + std_score
        tau_low = mean_score - std_score

        logger.info(f"[KnowledgeGraphSelfEvolver] 阈值计算, "
                    f"均值: {mean_score:.3f}, "
                    f"标准差: {std_score:.3f}, "
                    f"τhigh: {tau_high:.3f}, "
                    f"τlow: {tau_low:.3f}")

        t_start_set = [
            tid for tid, ts in self.feedback_manager.triplet_scores.items()
            if ts.contribution_score >= tau_high
        ]

        logger.info(f"[KnowledgeGraphSelfEvolver] 高贡献起始三元组: {len(t_start_set)}")

        shortcuts = []
        for t_start_id in t_start_set:
            if t_start_id not in knowledge_graph:
                continue

            path_shortcuts = self._find_shortcut_paths(
                t_start_id=t_start_id,
                knowledge_graph=knowledge_graph,
                tau_high=tau_high
            )
            shortcuts.extend(path_shortcuts)

        evolved_kg = knowledge_graph.copy()
        for shortcut in shortcuts:
            edge_exists = False
            for tg_id, tg_data in evolved_kg.items():
                if (tg_data.get('head') == shortcut.head and
                    tg_data.get('tail') == shortcut.tail):
                    edge_exists = True
                    break

            if not edge_exists:
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
                self.shortcut_edges.append(shortcut)

        self._update_suppressed_triplets(tau_low, knowledge_graph)

        logger.info(f"[KnowledgeGraphSelfEvolver] KG进化完成, "
                    f"新增捷径边: {len(self.shortcut_edges)}, "
                    f"抑制三元组: {len(self.suppressed_triplets)}")

        return evolved_kg

    def _find_shortcut_paths(
        self,
        t_start_id: str,
        knowledge_graph: Dict[str, Any],
        tau_high: float
    ) -> List[ShortcutEdge]:
        shortcuts = []

        t_start = knowledge_graph.get(t_start_id)
        if not t_start:
            return shortcuts

        frontier = [(t_start_id, [t_start_id])]

        for hop in range(self.max_hops):
            next_frontier = []

            for curr_tid, path in frontier:
                curr_triplet = knowledge_graph.get(curr_tid)
                if not curr_triplet:
                    continue

                neighbors = self._get_neighbor_triplets(
                    curr_triplet, knowledge_graph
                )

                neighbors.sort(
                    key=lambda x: self.feedback_manager.triplet_scores.get(
                        x[0], TripletScore(triplet_id=x[0])
                    ).contribution_score,
                    reverse=True
                )

                for nbr_tid, nbr_triplet in neighbors:
                    path_score = self._compute_path_avg_score(path + [nbr_tid])

                    if path_score < tau_high:
                        break

                    head = knowledge_graph[t_start_id]['head']
                    tail = nbr_triplet['tail']

                    if self._edge_exists(head, tail, knowledge_graph):
                        shortcut = ShortcutEdge(
                            head=head,
                            relation=self._recommend_relation(path + [nbr_tid]),
                            tail=tail,
                            avg_score=path_score,
                            source_path=path + [nbr_tid]
                        )
                        shortcuts.append(shortcut)

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
        neighbors = []
        tail_entity = triplet.get('tail')

        for tid, tdata in knowledge_graph.items():
            if tdata.get('head') == tail_entity:
                neighbors.append((tid, tdata))

        return neighbors

    def _compute_path_avg_score(self, path: List[str]) -> float:
        scores = []
        for tid in path:
            if tid in self.feedback_manager.triplet_scores:
                scores.append(
                    self.feedback_manager.triplet_scores[tid].contribution_score
                )

        if not scores:
            return 0.0

        if np is None:
            return sum(scores) / len(scores)
        return float(np.mean(scores))

    def _edge_exists(self, head: str, tail: str, knowledge_graph: Dict[str, Any]) -> bool:
        for tg_data in knowledge_graph.values():
            if tg_data.get('head') == head and tg_data.get('tail') == tail:
                return True
        return False

    def _recommend_relation(self, path: List[str]) -> str:
        return f"path_via_{len(path)}_triplets"

    def _update_suppressed_triplets(
        self,
        tau_low: float,
        knowledge_graph: Dict[str, Any]
    ) -> None:
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
        base_priority = self.feedback_manager.get_triplet_priority(triplet_id)

        if triplet_id in self.suppressed_triplets:
            return base_priority * 0.3
        elif triplet_id in self.recovery_candidates:
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
        if triplet_id not in self.suppressed_triplets:
            return

        if semantic_similarity > 0.7:
            if triplet_id not in self.recovery_candidates:
                self.recovery_candidates[triplet_id] = 0

            self.recovery_candidates[triplet_id] += 1

            logger.debug(f"[KnowledgeGraphSelfEvolver] 动态恢复候选, "
                         f"三元组: {triplet_id}, "
                         f"恢复分数: {self.recovery_candidates[triplet_id]}")

            if self.recovery_candidates[triplet_id] >= 5:
                self.suppressed_triplets.remove(triplet_id)
                logger.info(f"[KnowledgeGraphSelfEvolver] 三元组恢复, "
                            f"三元组: {triplet_id}")

    def get_shortcut_edges(self) -> List[ShortcutEdge]:
        return self.shortcut_edges

    def get_suppressed_triplets(self) -> Set[str]:
        return self.suppressed_triplets

    def get_statistics(self) -> Dict[str, Any]:
        return {
            'shortcut_edges_count': len(self.shortcut_edges),
            'suppressed_triplets_count': len(self.suppressed_triplets),
            'recovery_candidates_count': len(self.recovery_candidates),
            'max_hops': self.max_hops,
            'min_path_score': self.min_path_score
        }
