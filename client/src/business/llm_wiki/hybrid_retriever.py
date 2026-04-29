"""
EvoRAG混合优先级检索模块
实现基于反馈的检索优化
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
import numpy as np
from collections import deque


@dataclass
class RetrievalResult:
    """检索结果"""
    triplet_id: str
    head: str
    relation: str
    tail: str
    semantic_similarity: float       # Sr(t)
    contribution_score: float         # Sc(t)
    hybrid_priority: float            # P(t) = (1-α)·Sr + α·Sc
    path_priority: float = 0.0       # P(L) - 如果是路径检索
    metadata: Dict[str, Any] = None


class HybridRetriever:
    """
    混合优先级检索器
    实现EvoRAG的混合优先级检索策略
    """

    def __init__(
        self,
        feedback_manager,
        kg_self_evolver,
        top_n_entities: int = 10,
        top_m_paths: int = 10,
        alpha: float = 0.5
    ):
        """
        初始化混合检索器

        Args:
            feedback_manager: 反馈管理器
            kg_self_evolver: KG自进化器
            top_n_entities: 检索实体数N
            top_m_paths: 每实体检索路径数M
            alpha: 权衡参数
        """
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
        query_embedding: Optional[np.ndarray] = None
    ) -> List[RetrievalResult]:
        """
        基于查询检索（简化版）

        完整流程：
        1. 编码查询为嵌入向量
        2. 检索Top-N相关实体
        3. 提取子图
        4. 混合排序
        5. 返回Top-M路径

        Args:
            query: 用户查询
            knowledge_graph: 知识图谱
            query_embedding: 查询嵌入向量（可选）

        Returns:
            检索结果列表
        """
        # 步骤1: 实体检索（简化版 - 基于关键词匹配）
        relevant_entities = self._retrieve_relevant_entities(
            query, knowledge_graph
        )
        logger.info(f"[HybridRetriever] 检索到相关实体: {len(relevant_entities)}")

        # 步骤2: 子图提取
        subgraph = self._extract_subgraph(
            relevant_entities, knowledge_graph
        )
        logger.info(f"[HybridRetriever] 提取子图大小: {len(subgraph)}")

        # 步骤3: 混合排序
        sorted_results = self._hybrid_sort(subgraph, knowledge_graph)

        # 步骤4: 返回Top结果
        top_results = sorted_results[:self.top_n * 2]  # 返回2N个结果

        logger.info(f"[HybridRetriever] 检索完成, 返回结果数: {len(top_results)}")

        return top_results

    def retrieve_paths_by_entity(
        self,
        entity: str,
        knowledge_graph: Dict[str, Any],
        max_hops: int = 3
    ) -> List[List[RetrievalResult]]:
        """
        检索从实体出发的路径（混合优先级）

        Args:
            entity: 起始实体
            knowledge_graph: 知识图谱
            max_hops: 最大跳数

        Returns:
            路径列表（每个路径是RetrievalResult列表）
        """
        # BFS搜索所有路径
        all_paths = self._bfs_search(entity, knowledge_graph, max_hops)

        # 计算每条路径的优先级
        path_priorities = []
        for path in all_paths:
            priority = self._compute_path_priority(path)
            path_priorities.append((path, priority))

        # 按优先级排序
        path_priorities.sort(key=lambda x: x[1], reverse=True)

        # 返回Top-M路径
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
        """
        检索相关实体（简化版）

        真实场景应使用嵌入向量相似度
        这里使用关键词匹配

        Args:
            query: 查询
            knowledge_graph: 知识图谱

        Returns:
            相关实体列表
        """
        query_lower = query.lower()
        query_tokens = set(query_lower.split())

        entity_scores = {}

        for tg_id, tg_data in knowledge_graph.items():
            head = tg_data.get('head', '')
            tail = tg_data.get('tail', '')
            relation = tg_data.get('relation', '')

            # 计算匹配分数
            score = 0.0

            for token in query_tokens:
                if token in head.lower():
                    score += 1.0
                if token in tail.lower():
                    score += 1.0
                if token in relation.lower():
                    score += 0.5

            if score > 0:
                # 添加到实体分数
                if head not in entity_scores:
                    entity_scores[head] = 0.0
                if tail not in entity_scores:
                    entity_scores[tail] = 0.0

                entity_scores[head] += score
                entity_scores[tail] += score

        # 排序并返回Top-N
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
        """
        提取子图（k-hop邻居）

        Args:
            entities: 中心实体列表
            knowledge_graph: 知识图谱

        Returns:
            子图 {triplet_id: tg_data}
        """
        subgraph = {}
        visited_entities = set(entities)

        # 提取1-hop邻居
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
        """
        混合排序（公式2）

        P(t) = (1-α)·Sr(t) + α·Sc(t)

        Args:
            subgraph: 子图
            knowledge_graph: 完整知识图谱

        Returns:
            排序后的检索结果
        """
        results = []

        for tg_id, tg_data in subgraph.items():
            # 计算混合优先级
            priority = self._compute_triplet_priority(tg_id)

            # 考虑抑制
            if self.kg_evolver:
                priority_with_suppression = self.kg_evolver.get_triplet_priority_with_suppression(tg_id)
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

        # 按混合优先级排序
        results.sort(key=lambda x: x.hybrid_priority, reverse=True)

        return results

    def _compute_triplet_priority(self, triplet_id: str) -> float:
        """
        计算三元组混合优先级（公式2）

        P(t) = (1-α)·Sr(t) + α·Sc(t)

        Args:
            triplet_id: 三元组ID

        Returns:
            混合优先级 [0, 1]
        """
        if self.feedback_manager:
            return self.feedback_manager.get_triplet_priority(triplet_id)
        else:
            # 默认优先级
            return 0.5

    def _compute_path_priority(self, path: List[str]) -> float:
        """
        计算路径优先级（公式3）

        P(Li) = exp((1/|Li|)·Σ(t∈Li) log P(t))
                  / Σ(Lj∈L) exp((1/|Lj|)·Σ(t∈Lj) log P(t))

        简化版：只计算分子部分

        Args:
            path: 三元组ID路径

        Returns:
            路径优先级
        """
        if not path:
            return 0.0

        log_sum = 0.0
        for tid in path:
            priority = self._compute_triplet_priority(tid)
            if priority > 0:
                log_sum += np.log(priority)
            else:
                log_sum += np.log(1e-10)

        avg_log = log_sum / len(path)
        priority = np.exp(avg_log)

        return priority

    def _get_semantic_similarity(self, triplet_id: str) -> float:
        """获取语义相似度Sr(t)"""
        if self.feedback_manager:
            if triplet_id in self.feedback_manager.triplet_scores:
                return self.feedback_manager.triplet_scores[triplet_id].semantic_similarity

        return 0.5

    def _get_contribution_score(self, triplet_id: str) -> float:
        """获取贡献分数Sc(t)"""
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
        """
        BFS搜索从起始实体出发的所有路径

        Args:
            start_entity: 起始实体
            knowledge_graph: 知识图谱
            max_hops: 最大跳数

        Returns:
            路径列表
        """
        all_paths = []
        queue = deque([(start_entity, []),])  # (当前实体, 路径)

        while queue:
            current_entity, path = queue.popleft()

            if len(path) >= max_hops:
                if path:  # 只添加非空路径
                    all_paths.append(path)
                continue

            # 查找以current_entity为head的三元组
            for tg_id, tg_data in knowledge_graph.items():
                if tg_data.get('head') == current_entity:
                    new_path = path + [tg_id]
                    all_paths.append(new_path)

                    # 继续搜索
                    next_entity = tg_data.get('tail')
                    queue.append((next_entity, new_path))

        return all_paths

    def update_alpha(self, new_alpha: float) -> None:
        """更新权衡参数α"""
        self.alpha = max(0.0, min(1.0, new_alpha))
        logger.info(f"[HybridRetriever] α更新为: {self.alpha:.3f}")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'top_n_entities': self.top_n,
            'top_m_paths': self.top_m,
            'alpha': self.alpha,
            'total_triplets_tracked': len(self.feedback_manager.triplet_scores) if self.feedback_manager else 0
        }


if __name__ == "__main__":
    # 测试混合检索器
    from client.src.business.llm_wiki.feedback_manager import FeedbackManager, TripletScore
    from client.src.business.llm_wiki.kg_self_evolver import KnowledgeGraphSelfEvolver

    # 创建组件
    fm = FeedbackManager()
    evolver = KnowledgeGraphSelfEvolver(fm)

    # 模拟三元组评分
    fm.triplet_scores['t1'] = TripletScore(triplet_id='t1', contribution_score=0.9, semantic_similarity=0.8)
    fm.triplet_scores['t2'] = TripletScore(triplet_id='t2', contribution_score=0.7, semantic_similarity=0.6)
    fm.triplet_scores['t3'] = TripletScore(triplet_id='t3', contribution_score=0.3, semantic_similarity=0.9)
    fm.triplet_scores['t4'] = TripletScore(triplet_id='t4', contribution_score=0.5, semantic_similarity=0.5)

    # 创建检索器
    retriever = HybridRetriever(fm, evolver, top_n_entities=5, top_m_paths=3)

    # 模拟知识图谱
    kg = {
        't1': {'head': 'EntityA', 'relation': 'rel1', 'tail': 'EntityB'},
        't2': {'head': 'EntityB', 'relation': 'rel2', 'tail': 'EntityC'},
        't3': {'head': 'EntityC', 'relation': 'rel3', 'tail': 'EntityD'},
        't4': {'head': 'EntityD', 'relation': 'rel4', 'tail': 'EntityE'}
    }

    # 测试检索
    results = retriever.retrieve_by_query("EntityA EntityC", kg)

    print(f"检索结果数: {len(results)}")
    for r in results[:3]:
        print(f"  三元组: {r.triplet_id}, 优先级: {r.hybrid_priority:.3f}")

    # 测试路径检索
    paths = retriever.retrieve_paths_by_entity("EntityA", kg, max_hops=2)
    print(f"\n路径检索结果数: {len(paths)}")
    for i, path in enumerate(paths[:2]):
        print(f"  路径 {i+1}: {[r.triplet_id for r in path]}")

    # 获取统计
    stats = retriever.get_statistics()
    print(f"\n统计信息: {stats}")
