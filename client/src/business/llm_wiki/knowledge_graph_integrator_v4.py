"""
LLM Wiki 模块 - KnowledgeGraph 集成器（Phase 4: EvoRAG集成版）

================================================

Phase 4 (EvoRAG集成):
1. ✅ 反馈驱动反向传播
2. ✅ 知识图谱自进化（关系融合、抑制）
3. ✅ 混合优先级检索
4. ✅ 动态恢复机制

作者: LivingTreeAI Team
日期: 2026-04-29
版本: 4.0.0 (EvoRAG集成版)
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

# 导入 Phase 1-3 的集成器
from .knowledge_graph_integrator_v3 import (
    LLMWikiKnowledgeGraphIntegratorV3,
    WikiNodeMapping
)

# 导入 EvoRAG 组件
from .feedback_manager import FeedbackManager, FeedbackRecord
from .kg_self_evolver import KnowledgeGraphSelfEvolver
from .hybrid_retriever import HybridRetriever, RetrievalResult


@dataclass
class EvoRAGConfig:
    """EvoRAG配置"""
    enable_feedback: bool = True
    enable_self_evolution: bool = True
    enable_hybrid_retrieval: bool = True

    # 反馈管理器参数
    feedback_db_path: str = "client/data/llm_wiki/feedback_db.json"
    learning_rate: float = 0.5
    alpha: float = 0.5

    # 自进化器参数
    max_hops: int = 3
    min_path_score: float = 0.6

    # 混合检索参数
    top_n_entities: int = 10
    top_m_paths: int = 10


class LLMWikiKnowledgeGraphIntegratorV4:
    """
    LLM Wiki → KnowledgeGraph 集成器（Phase 4: EvoRAG集成版）

    在Phase 3基础上集成EvoRAG的三大核心特性：
    1. 反馈驱动反向传播
    2. 知识图谱自进化
    3. 混合优先级检索
    """

    def __init__(
        self,
        domain: str = "llm_wiki",
        enable_cache: bool = True,
        evorag_config: Optional[EvoRAGConfig] = None
    ):
        """
        初始化集成器

        Args:
            domain: 知识图谱域名
            enable_cache: 是否启用缓存
            evorag_config: EvoRAG配置（为None则使用默认配置）
        """
        # Phase 3 集成器（基础功能）
        self.v3_integrator = LLMWikiKnowledgeGraphIntegratorV3(
            domain=domain,
            enable_cache=enable_cache
        )

        # EvoRAG配置
        self.evorag_config = evorag_config or EvoRAGConfig()

        # EvoRAG组件
        self.feedback_manager: Optional[FeedbackManager] = None
        self.kg_evolver: Optional[KnowledgeGraphSelfEvolver] = None
        self.hybrid_retriever: Optional[HybridRetriever] = None

        # 初始化EvoRAG组件
        if self.evorag_config.enable_feedback:
            self._init_evorag_components()

        # 知识图谱数据（用于EvoRAG）
        self._kg_data: Dict[str, Any] = {}  # {triplet_id: {head, relation, tail}}

        # 推理路径记录 {query: paths}
        self._reasoning_paths: Dict[str, List[List[str]]] = {}

        # 统计信息
        self._evorag_stats: Dict[str, Any] = {
            'feedback_count': 0,
            'evolution_count': 0,
            'retrieval_count': 0,
            'kg_evolution_enabled': self.evorag_config.enable_self_evolution
        }

        logger.info(f"[V4] LLMWikiKnowledgeGraphIntegratorV4 初始化完成, "
                    f"EvoRAG启用: {self.evorag_config.enable_feedback}")

    def _init_evorag_components(self) -> None:
        """初始化EvoRAG组件"""
        # 1. 反馈管理器
        self.feedback_manager = FeedbackManager(
            feedback_db_path=self.evorag_config.feedback_db_path,
            learning_rate=self.evorag_config.learning_rate,
            alpha=self.evorag_config.alpha
        )

        # 2. 知识图谱自进化器
        if self.evorag_config.enable_self_evolution:
            self.kg_evolver = KnowledgeGraphSelfEvolver(
                feedback_manager=self.feedback_manager,
                max_hops=self.evorag_config.max_hops,
                min_path_score=self.evorag_config.min_path_score
            )

        # 3. 混合检索器
        if self.evorag_config.enable_hybrid_retrieval:
            self.hybrid_retriever = HybridRetriever(
                feedback_manager=self.feedback_manager,
                kg_self_evolver=self.kg_evolver,
                top_n_entities=self.evorag_config.top_n_entities,
                top_m_paths=self.evorag_config.top_m_paths,
                alpha=self.evorag_config.alpha
            )

        logger.info("[V4] EvoRAG组件初始化完成")

    def integrate_chunks(
        self,
        chunks: List[Any],
        batch_size: int = 50
    ) -> Any:
        """
        集成文档块到知识图谱（重写以添加EvoRAG支持）

        Args:
            chunks: DocumentChunk列表
            batch_size: 批量处理大小

        Returns:
            KnowledgeGraph实例
        """
        logger.info(f"[V4] 开始集成 {len(chunks)} 个文档块（EvoRAG模式）")

        # 调用V3集成器
        graph = self.v3_integrator.integrate_chunks(chunks, batch_size)

        # 构建KG数据（用于EvoRAG）
        self._build_kg_data()

        logger.info(f"[V4] 集成完成, KG数据大小: {len(self._kg_data)}")

        return graph

    def _build_kg_data(self) -> None:
        """构建KG数据（从KnowledgeGraph提取三元组）"""
        self._kg_data.clear()

        # 从KnowledgeGraph提取三元组
        # 这里假设KnowledgeGraph有nodes和relations
        graph = self.v3_integrator.graph

        # 构建 {node_id: title} 映射
        node_titles = {}
        for node_id, node in graph.nodes.items():
            node_titles[node_id] = node.title

        # 构建三元组
        for rel in graph.relations:
            triplet_id = f"triplet_{rel.relation_id}"

            head_title = node_titles.get(rel.source_id, rel.source_id)
            tail_title = node_titles.get(rel.target_id, rel.target_id)

            self._kg_data[triplet_id] = {
                'head': head_title,
                'relation': rel.relation_type,
                'tail': tail_title,
                'source_id': rel.source_id,
                'target_id': rel.target_id
            }

        logger.debug(f"[V4] 构建KG数据完成, 三元组数: {len(self._kg_data)}")

    def add_feedback(
        self,
        query: str,
        response: str,
        paths: List[List[str]],
        feedback_score: float,
        feedback_type: str = "human"
    ) -> str:
        """
        添加反馈（EvoRAG核心接口）

        Args:
            query: 用户查询
            response: 生成的响应
            paths: 推理路径（三元组ID列表）
            feedback_score: 反馈分数 (1-5)
            feedback_type: 反馈类型

        Returns:
            反馈记录ID
        """
        if not self.feedback_manager:
            raise RuntimeError("反馈管理器未初始化，请在配置中启用EvoRAG")

        # 添加反馈
        record_id = self.feedback_manager.add_feedback(
            query=query,
            response=response,
            paths=paths,
            feedback_score=feedback_score,
            feedback_type=feedback_type
        )

        # 更新统计
        self._evorag_stats['feedback_count'] += 1

        # 触发KG进化（如果启用）
        if self.evorag_config.enable_self_evolution and self.kg_evolver:
            # 定期触发进化（每5次反馈）
            if self._evorag_stats['feedback_count'] % 5 == 0:
                self.evolve_knowledge_graph()

        logger.info(f"[V4] 添加反馈成功, "
                    f"记录ID: {record_id}, "
                    f"查询: {query[:50]}...")

        return record_id

    def evolve_knowledge_graph(self) -> Dict[str, Any]:
        """
        执行知识图谱进化（EvoRAG核心接口）

        Returns:
            进化后的知识图谱数据
        """
        if not self.kg_evolver:
            raise RuntimeError("KG自进化器未初始化")

        logger.info("[V4] 开始KG进化...")

        # 执行进化
        evolved_kg = self.kg_evolver.evolve_knowledge_graph(self._kg_data)

        # 更新KG数据
        self._kg_data = evolved_kg

        # 更新统计
        self._evorag_stats['evolution_count'] += 1

        # 获取统计
        evolver_stats = self.kg_evolver.get_statistics()

        logger.info(f"[V4] KG进化完成, "
                    f"新增捷径边: {evolver_stats['shortcut_edges_count']}, "
                    f"抑制三元组: {evolver_stats['suppressed_triplets_count']}")

        return evolved_kg

    def hybrid_retrieve(
        self,
        query: str,
        top_k: int = 10
    ) -> List[RetrievalResult]:
        """
        混合优先级检索（EvoRAG核心接口）

        Args:
            query: 用户查询
            top_k: 返回结果数

        Returns:
            检索结果列表
        """
        if not self.hybrid_retriever:
            raise RuntimeError("混合检索器未初始化")

        logger.info(f"[V4] 开始混合检索, 查询: {query[:50]}...")

        # 执行检索
        results = self.hybrid_retriever.retrieve_by_query(
            query=query,
            knowledge_graph=self._kg_data
        )

        # 限制返回数量
        top_results = results[:top_k]

        # 更新统计
        self._evorag_stats['retrieval_count'] += 1

        logger.info(f"[V4] 混合检索完成, "
                    f"返回结果数: {len(top_results)}")

        return top_results

    def retrieve_paths(
        self,
        entity: str,
        max_hops: int = 3
    ) -> List[List[RetrievalResult]]:
        """
        检索从实体出发的路径

        Args:
            entity: 起始实体
            max_hops: 最大跳数

        Returns:
            路径列表
        """
        if not self.hybrid_retriever:
            raise RuntimeError("混合检索器未初始化")

        return self.hybrid_retriever.retrieve_paths_by_entity(
            entity=entity,
            knowledge_graph=self._kg_data,
            max_hops=max_hops
        )

    def reason_over_graph_evorag(
        self,
        query: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        基于EvoRAG的图谱推理

        Args:
            query: 用户查询
            top_k: 返回Top-K推理路径

        Returns:
            推理结果
        """
        logger.info(f"[V4] 开始EvoRAG图谱推理, 查询: {query[:50]}...")

        # 步骤1: 混合检索
        retrieval_results = self.hybrid_retrieve(query, top_k=top_k * 2)

        # 步骤2: 构建推理路径
        reasoning_paths = []

        for i, result in enumerate(retrieval_results[:top_k]):
            path = [result]  # 单跳路径
            reasoning_paths.append(path)

            # 记录路径（用于反馈）
            path_ids = [result.triplet_id]
            if query not in self._reasoning_paths:
                self._reasoning_paths[query] = []
            self._reasoning_paths[query].append(path_ids)

        # 步骤3: 生成推理答案（简化版）
        answer = self._generate_answer(query, reasoning_paths)

        # 步骤4: 构建结果
        result = {
            'query': query,
            'answer': answer,
            'reasoning_paths': [
                [r.triplet_id for r in path]
                for path in reasoning_paths
            ],
            'retrieval_results': [
                {
                    'triplet_id': r.triplet_id,
                    'head': r.head,
                    'relation': r.relation,
                    'tail': r.tail,
                    'hybrid_priority': r.hybrid_priority,
                    'semantic_similarity': r.semantic_similarity,
                    'contribution_score': r.contribution_score
                }
                for r in retrieval_results[:top_k]
            ],
            'timestamp': datetime.now().isoformat()
        }

        logger.info(f"[V4] EvoRAG图谱推理完成, "
                    f"路径数: {len(reasoning_paths)}")

        return result

    def _generate_answer(
        self,
        query: str,
        reasoning_paths: List[List[RetrievalResult]]
    ) -> str:
        """
        生成推理答案（简化版）

        Args:
            query: 查询
            reasoning_paths: 推理路径

        Returns:
            答案文本
        """
        # 简化版：基于检索结果生成答案
        answer_parts = [f"基于知识图谱的查询结果（EvoRAG优化）:"]

        for i, path in enumerate(reasoning_paths, 1):
            path_desc = " → ".join([
                f"({r.head} -[{r.relation}]-> {r.tail})"
                for r in path
            ])
            answer_parts.append(f"路径{i}: {path_desc}")

        return "\n".join(answer_parts)

    def get_evorag_statistics(self) -> Dict[str, Any]:
        """获取EvoRAG统计信息"""
        stats = self._evorag_stats.copy()

        # 添加各组件统计
        if self.feedback_manager:
            fm_stats = self.feedback_manager.get_statistics()
            stats['feedback_manager'] = fm_stats

        if self.kg_evolver:
            evolver_stats = self.kg_evolver.get_statistics()
            stats['kg_evolver'] = evolver_stats

        if self.hybrid_retriever:
            retriever_stats = self.hybrid_retriever.get_statistics()
            stats['hybrid_retriever'] = retriever_stats

        return stats

    def update_evorag_config(self, **kwargs) -> None:
        """
        更新EvoRAG配置

        Args:
            **kwargs: 配置参数
        """
        for key, value in kwargs.items():
            if hasattr(self.evorag_config, key):
                setattr(self.evorag_config, key, value)
                logger.info(f"[V4] 更新EvoRAG配置: {key} = {value}")

        # 重新初始化组件（如果必要）
        if 'alpha' in kwargs and self.hybrid_retriever:
            self.hybrid_retriever.update_alpha(kwargs['alpha'])

    # ==================== 代理方法（委托给V3） ====================

    @property
    def graph(self):
        """获取知识图谱"""
        return self.v3_integrator.graph

    @property
    def node_mappings(self):
        """获取节点映射"""
        return self.v3_integrator.node_mappings

    def find_path(self, start: str, end: str) -> List[str]:
        """查找路径（委托给V3）"""
        return self.v3_integrator.find_path(start, end)

    def extract_subgraph(self, center: str, max_depth: int = 2) -> Dict:
        """提取子图（委托给V3）"""
        return self.v3_integrator.extract_subgraph(center, max_depth)

    def query_related_concepts(self, node: str, max_depth: int = 2) -> List[str]:
        """查询相关概念（委托给V3）"""
        return self.v3_integrator.query_related_concepts(node, max_depth)

    def reason_over_graph(self, query: str) -> Dict[str, Any]:
        """图谱推理（委托给V3）"""
        return self.v3_integrator.reason_over_graph(query)


# ==================== 便捷函数 ====================

def integrate_llm_wiki_to_graph_v4(
    chunks: List[Any],
    domain: str = "llm_wiki",
    enable_cache: bool = True,
    enable_evorag: bool = True
) -> LLMWikiKnowledgeGraphIntegratorV4:
    """
    便捷函数：集成LLM Wiki到KnowledgeGraph（V4 - EvoRAG版）

    Args:
        chunks: DocumentChunk列表
        domain: 域名
        enable_cache: 是否启用缓存
        enable_evorag: 是否启用EvoRAG

    Returns:
        V4集成器实例
    """
    config = EvoRAGConfig(enable_feedback=enable_evorag)

    integrator = LLMWikiKnowledgeGraphIntegratorV4(
        domain=domain,
        enable_cache=enable_cache,
        evorag_config=config
    )

    integrator.integrate_chunks(chunks)

    logger.info(f"[V4] LLM Wiki已集成到KnowledgeGraph（EvoRAG模式）, "
                f"节点数: {len(integrator.graph.nodes)}, "
                f"关系数: {len(integrator.graph.relations)}")

    return integrator


if __name__ == "__main__":
    # 测试V4集成器
    from client.src.business.llm_wiki.models import DocumentChunk

    # 创建测试数据
    test_chunks = [
        DocumentChunk(
            content="# 标题1\n\n这是第一段内容。\n\n## 子标题\n\n这是子标题内容。",
            title="标题1",
            section="标题1",
            chunk_type="text",
            source="test_doc.md",
            metadata={"title": "标题1"}
        ),
        DocumentChunk(
            content="```python\nprint('Hello World')\n```",
            title="标题1",
            section="标题1",
            chunk_type="code",
            source="test_doc.md",
            metadata={"title": "标题1"}
        )
    ]

    # 创建V4集成器
    integrator = integrate_llm_wiki_to_graph_v4(
        chunks=test_chunks,
        enable_evorag=True
    )

    print(f"集成完成:")
    print(f"  节点数: {len(integrator.graph.nodes)}")
    print(f"  关系数: {len(integrator.graph.relations)}")

    # 测试混合检索
    results = integrator.hybrid_retrieve("标题1", top_k=5)
    print(f"\n混合检索结果数: {len(results)}")
    for r in results[:3]:
        print(f"  三元组: {r.triplet_id}, 优先级: {r.hybrid_priority:.3f}")

    # 测试添加反馈
    if results:
        paths = [[r.triplet_id for r in results[:2]]]
        record_id = integrator.add_feedback(
            query="测试查询",
            response="测试响应",
            paths=paths,
            feedback_score=4.0,
            feedback_type="human"
        )
        print(f"\n添加反馈成功, 记录ID: {record_id}")

    # 获取统计
    stats = integrator.get_evorag_statistics()
    print(f"\nEvoRAG统计信息:")
    print(f"  反馈次数: {stats['feedback_count']}")
    print(f"  检索次数: {stats['retrieval_count']}")
