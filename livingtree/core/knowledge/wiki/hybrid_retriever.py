"""
LivingTree Knowledge Wiki - EvoRAG 混合优先级检索模块
====================================================

实现基于反馈的检索优化。

从 client/src/business/llm_wiki/hybrid_retriever.py 迁移而来。
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import deque

try:
    import numpy as np
except ImportError:
    np = None

from loguru import logger


@dataclass
class RetrievalResult:
    """检索结果"""
    triplet_id: str
    head: str
    relation: str
    tail: str
    semantic_similarity: float
    contribution_score: float
    hybrid_priority: float
    path_priority: float = 0.0
    metadata: Dict[str, Any] = None


class HybridRetriever:
    """
    混合优先级检索器
    实现 EvoRAG 的混合优先级检索策略
    """

    def __init__(
        self,
        feedback_manager,
        kg_self_evolver,
        top_n_entities: int = 10,
        top_m_paths: int = 10,
        alpha: float = 0.5
    ):
        self.feedback_manager = feedback_manager
        self.kg_evolver = kg_self_evolver
        self.top_n = top_n_entities
        self.top_m = top_m_paths
        self.alpha = alpha

        logger.info(f"[HybridRetriever] 初始化完成, "
                    f"N={top_n_entities}, M={top_m_paths}, α={alpha}")

    def retrieve_by_query(
        self,
        query: str,
        knowledge_graph: Dict[str, Any],
        query_embedding: Optional["np.ndarray"] = None
    ) -> List[RetrievalResult]:
        relevant_entities = self._retrieve_relevant_entities(
            query, knowledge_graph
        )
        logger.info(f"[HybridRetriever] 检索到相关实体: {len(relevant_entities)}")

        subgraph = self._extract_subgraph(
            relevant_entities, knowledge_graph
        )
        logger.info(f"[HybridRetriever] 提取子图大小: {len(subgraph)}")

        sorted_results = self._hybrid_sort(subgraph, knowledge_graph)
        top_results = sorted_results[:self.top_n * 2]

        logger.info(f"[HybridRetriever] 检索完成, 返回结果数: {len(top_results)}")

        return top_results

    def retrieve_paths_by_entity(
        self,
        entity: str,
        knowledge_graph: Dict[str, Any],
        max_hops: int = 3
    ) -> List[List[RetrievalResult]]:
        all_paths = self._bfs_search(entity, knowledge_graph, max_hops)

        path_priorities = []
        for path in all_paths:
            priority = self._compute_path_priority(path)
            path_priorities.append((path, priority))

        path_priorities.sort(key=lambda x: x[1], reverse=True)

        top_paths = []
        for path, priority in path_priorities[:self.top_m]:
            result_path = []
            for tid in path:
                tg_data = knowledge_graph.get(tid)
                if not tg_data:
                    continue

                result = RetrievalResult(
                    triplet_id=tid,
                    head=tg_data.get('head', ''),
                    relation=tg_data.get('relation', ''),
                    tail=tg_data.get('tail', ''),
                    semantic_similarity=self._get_semantic_similarity(tid),
                    contribution_score=self._get_contribution_score(tid),
                    hybrid_priority=self._compute_triplet_priority(tid),
                    path_priority=priority
                )
                result_path.append(result)

            top_paths.append(result_path)

        logger.info(f"[HybridRetriever] 实体 {entity} 检索到 {len(top_paths)} 条路径")

        return top_paths

    def _retrieve_relevant_entities(
        self,
        query: str,
        knowledge_graph: Dict[str, Any]
    ) -> List[str]:
        query_lower = query.lower()
        query_tokens = set(query_lower.split())

        entity_scores = {}

        for tg_id, tg_data in knowledge_graph.items():
            head = tg_data.get('head', '')
            tail = tg_data.get('tail', '')
            relation = tg_data.get('relation', '')

            score = 0.0

            for token in query_tokens:
                if token in head.lower():
                    score += 1.0
                if token in tail.lower():
                    score += 1.0
                if token in relation.lower():
                    score += 0.5

            if score > 0:
                if head not in entity_scores:
                    entity_scores[head] = 0.0
                if tail not in entity_scores:
                    entity_scores[tail] = 0.0

                entity_scores[head] += score
                entity_scores[tail] += score

        sorted_entities = sorted(
            entity_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [e[0] for e in sorted_entities[:self.top_n]]

    def _extract_subgraph(
        self,
        entities: List[str],
        knowledge_graph: Dict[str, Any]
    ) -> Dict[str, Any]:
        subgraph = {}
        visited_entities = set(entities)

        for tg_id, tg_data in knowledge_graph.items():
            head = tg_data.get('head', '')
            tail = tg_data.get('tail', '')

            if head in visited_entities or tail in visited_entities:
                subgraph[tg_id] = tg_data

        return subgraph

    def _hybrid_sort(
        self,
        subgraph: Dict[str, Any],
        knowledge_graph: Dict[str, Any]
    ) -> List[RetrievalResult]:
        results = []

        for tg_id, tg_data in subgraph.items():
            priority = self._compute_triplet_priority(tg_id)

            if self.kg_evolver:
                priority_with_suppression = \
                    self.kg_evolver.get_triplet_priority_with_suppression(tg_id)
                priority = priority_with_suppression

            result = RetrievalResult(
                triplet_id=tg_id,
                head=tg_data.get('head', ''),
                relation=tg_data.get('relation', ''),
                tail=tg_data.get('tail', ''),
                semantic_similarity=self._get_semantic_similarity(tg_id),
                contribution_score=self._get_contribution_score(tg_id),
                hybrid_priority=priority
            )
            results.append(result)

        results.sort(key=lambda x: x.hybrid_priority, reverse=True)

        return results

    def _compute_triplet_priority(self, triplet_id: str) -> float:
        if self.feedback_manager:
            return self.feedback_manager.get_triplet_priority(triplet_id)
        else:
            return 0.5

    def _compute_path_priority(self, path: List[str]) -> float:
        if not path:
            return 0.0

        if np is None:
            return 0.5

        log_sum = 0.0
        for tid in path:
            priority = self._compute_triplet_priority(tid)
            if priority > 0:
                log_sum += np.log(priority)
            else:
                log_sum += np.log(1e-10)

        avg_log = log_sum / len(path)
        priority = np.exp(avg_log)

        return float(priority)

    def _get_semantic_similarity(self, triplet_id: str) -> float:
        if self.feedback_manager:
            if triplet_id in self.feedback_manager.triplet_scores:
                return self.feedback_manager.triplet_scores[triplet_id].semantic_similarity

        return 0.5

    def _get_contribution_score(self, triplet_id: str) -> float:
        if self.feedback_manager:
            if triplet_id in self.feedback_manager.triplet_scores:
                return self.feedback_manager.triplet_scores[triplet_id].contribution_score

        return 0.5

    def _bfs_search(
        self,
        start_entity: str,
        knowledge_graph: Dict[str, Any],
        max_hops: int
    ) -> List[List[str]]:
        all_paths = []
        queue = deque([(start_entity, [])])

        while queue:
            current_entity, path = queue.popleft()

            if len(path) >= max_hops:
                if path:
                    all_paths.append(path)
                continue

            for tg_id, tg_data in knowledge_graph.items():
                if tg_data.get('head') == current_entity:
                    new_path = path + [tg_id]
                    all_paths.append(new_path)

                    next_entity = tg_data.get('tail')
                    queue.append((next_entity, new_path))

        return all_paths

    def update_alpha(self, new_alpha: float) -> None:
        self.alpha = max(0.0, min(1.0, new_alpha))
        logger.info(f"[HybridRetriever] α更新为: {self.alpha:.3f}")

    def get_statistics(self) -> Dict[str, Any]:
        return {
            'top_n_entities': self.top_n,
            'top_m_paths': self.top_m,
            'alpha': self.alpha,
            'total_triplets_tracked': len(self.feedback_manager.triplet_scores) if self.feedback_manager else 0
        }
