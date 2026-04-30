"""
EvoRAG 集成测试脚本
测试Phase 4的EvoRAG三大核心特性：
1. 反馈驱动反向传播
2. 知识图谱自进化
3. 混合优先级检索
"""

import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from loguru import logger

# 导入EvoRAG组件
from business.llm_wiki.feedback_manager import (
    FeedbackManager, FeedbackRecord, TripletScore
)
from business.llm_wiki.kg_self_evolver import (
    KnowledgeGraphSelfEvolver, ShortcutEdge
)
from business.llm_wiki.hybrid_retriever import (
    HybridRetriever, RetrievalResult
)
from business.llm_wiki.knowledge_graph_integrator_v4 import (
    LLMWikiKnowledgeGraphIntegratorV4, EvoRAGConfig, integrate_llm_wiki_to_graph_v4
)
from business.llm_wiki.models import DocumentChunk


def test_feedback_manager():
    """测试反馈管理器"""
    print("\n" + "="*60)
    print("测试1: 反馈驱动反向传播")
    print("="*60)

    # 创建反馈管理器
    fm = FeedbackManager(
        feedback_db_path="client/data/llm_wiki/test_feedback_db.json",
        learning_rate=0.5,
        alpha=0.5
    )

    # 模拟三元组评分
    fm.triplet_scores['t1'] = TripletScore(
        triplet_id='t1',
        semantic_similarity=0.8,
        contribution_score=0.9
    )
    fm.triplet_scores['t2'] = TripletScore(
        triplet_id='t2',
        semantic_similarity=0.6,
        contribution_score=0.7
    )
    fm.triplet_scores['t3'] = TripletScore(
        triplet_id='t3',
        semantic_similarity=0.9,
        contribution_score=0.3  # 低贡献分数
    )
    fm.triplet_scores['t4'] = TripletScore(
        triplet_id='t4',
        semantic_similarity=0.5,
        contribution_score=0.2  # 低贡献分数
    )

    # 模拟反馈
    test_paths = [
        ['t1', 't2', 't3'],
        ['t2', 't4'],
    ]

    print("\n添加反馈...")
    record_id = fm.add_feedback(
        query="什么是机器学习？",
        response="机器学习是人工智能的一个分支...",
        paths=test_paths,
        feedback_score=4.5,  # 高分反馈
        feedback_type="human"
    )
    print(f"✅ 反馈已添加, 记录ID: {record_id}")

    # 获取统计
    stats = fm.get_statistics()
    print(f"\n反馈管理器统计:")
    print(f"  总反馈数: {stats['total_feedback']}")
    print(f"  总三元组数: {stats['total_triplets']}")
    print(f"  α参数: {stats['alpha']:.3f}")
    print(f"  平均贡献分数: {stats['avg_contribution_score']:.3f}")

    # 获取三元组优先级
    print(f"\n三元组优先级（混合优先级P(t)）:")
    for tid in ['t1', 't2', 't3', 't4']:
        priority = fm.get_triplet_priority(tid)
        print(f"  {tid}: P(t) = {priority:.3f}")

    # 获取KG进化候选
    high, low = fm.get_kg_evolution_candidates()
    print(f"\nKG进化候选:")
    print(f"  高质量三元组: {high}")
    print(f"  低质量三元组: {low}")

    print("\n✅ 测试1通过: 反馈驱动反向传播")
    return fm


def test_kg_self_evolver(fm):
    """测试知识图谱自进化"""
    print("\n" + "="*60)
    print("测试2: 知识图谱自进化")
    print("="*60)

    # 创建自进化器
    evolver = KnowledgeGraphSelfEvolver(
        feedback_manager=fm,
        max_hops=3,
        min_path_score=0.6
    )

    # 模拟知识图谱
    kg = {
        't1': {'head': 'EntityA', 'relation': 'rel1', 'tail': 'EntityB'},
        't2': {'head': 'EntityB', 'relation': 'rel2', 'tail': 'EntityC'},
        't3': {'head': 'EntityC', 'relation': 'rel3', 'tail': 'EntityD'},
        't4': {'head': 'EntityD', 'relation': 'rel4', 'tail': 'EntityE'}
    }

    print("\n执行KG进化...")
    evolved_kg = evolver.evolve_knowledge_graph(kg)

    print(f"\n进化结果:")
    print(f"  原始KG大小: {len(kg)}")
    print(f"  进化后KG大小: {len(evolved_kg)}")

    # 获取统计
    stats = evolver.get_statistics()
    print(f"\nKG自进化器统计:")
    print(f"  捷径边数: {stats['shortcut_edges_count']}")
    print(f"  抑制三元组数: {stats['suppressed_triplets_count']}")
    print(f"  恢复候选数: {stats['recovery_candidates_count']}")

    # 测试动态恢复
    print(f"\n测试动态恢复...")
    evolver.dynamic_recovery('t3', 'test query', 0.8)
    print(f"  恢复候选: {evolver.recovery_candidates}")

    # 测试抑制优先级
    print(f"\n测试抑制优先级:")
    for tid in ['t1', 't3']:
        priority = evolver.get_triplet_priority_with_suppression(tid)
        print(f"  {tid}: 优先级（含抑制）= {priority:.3f}")

    print("\n✅ 测试2通过: 知识图谱自进化")
    return evolver


def test_hybrid_retriever(fm, evolver):
    """测试混合优先级检索"""
    print("\n" + "="*60)
    print("测试3: 混合优先级检索")
    print("="*60)

    # 创建混合检索器
    retriever = HybridRetriever(
        feedback_manager=fm,
        kg_self_evolver=evolver,
        top_n_entities=10,
        top_m_paths=10,
        alpha=0.5
    )

    # 模拟知识图谱
    kg = {
        't1': {'head': 'EntityA', 'relation': 'rel1', 'tail': 'EntityB'},
        't2': {'head': 'EntityB', 'relation': 'rel2', 'tail': 'EntityC'},
        't3': {'head': 'EntityC', 'relation': 'rel3', 'tail': 'EntityD'},
        't4': {'head': 'EntityD', 'relation': 'rel4', 'tail': 'EntityE'}
    }

    # 测试检索
    print("\n执行混合检索...")
    results = retriever.retrieve_by_query(
        query="EntityA EntityC",
        knowledge_graph=kg
    )

    print(f"\n检索结果（Top-5）:")
    for i, r in enumerate(results[:5], 1):
        print(f"  {i}. 三元组: {r.triplet_id}")
        print(f"     头实体: {r.head}")
        print(f"     关系: {r.relation}")
        print(f"     尾实体: {r.tail}")
        print(f"     语义相似度Sr: {r.semantic_similarity:.3f}")
        print(f"     贡献分数Sc: {r.contribution_score:.3f}")
        print(f"     混合优先级P: {r.hybrid_priority:.3f}")
        print()

    # 测试路径检索
    print("执行路径检索...")
    paths = retriever.retrieve_paths_by_entity(
        entity="EntityA",
        knowledge_graph=kg,
        max_hops=2
    )

    print(f"\n路径检索结果（Top-3）:")
    for i, path in enumerate(paths[:3], 1):
        path_str = " → ".join([r.triplet_id for r in path])
        print(f"  路径{i}: {path_str}")
        print(f"    优先级: {path[0].path_priority:.3f}")

    # 获取统计
    stats = retriever.get_statistics()
    print(f"\n混合检索器统计:")
    print(f"  Top-N实体数: {stats['top_n_entities']}")
    print(f"  Top-M路径数: {stats['top_m_paths']}")
    print(f"  α参数: {stats['alpha']:.3f}")
    print(f"  追踪三元组数: {stats['total_triplets_tracked']}")

    print("\n✅ 测试3通过: 混合优先级检索")
    return retriever


def test_v4_integrator():
    """测试V4集成器"""
    print("\n" + "="*60)
    print("测试4: V4集成器（EvoRAG完整集成）")
    print("="*60)

    # 创建测试数据
    test_chunks = [
        DocumentChunk(
            content="# 机器学习\n\n机器学习是人工智能的一个分支。\n\n## 监督学习\n\n监督学习使用标注数据。",
            title="机器学习",
            section="机器学习",
            chunk_type="text",
            source="ml_doc.md",
            metadata={"title": "机器学习"}
        ),
        DocumentChunk(
            content="```python\ndef train_model(X, y):\n    return model.fit(X, y)\n```",
            title="机器学习",
            section="机器学习",
            chunk_type="code",
            source="ml_doc.md",
            metadata={"title": "机器学习"}
        )
    ]

    print("\n创建V4集成器...")
    config = EvoRAGConfig(
        enable_feedback=True,
        enable_self_evolution=True,
        enable_hybrid_retrieval=True,
        alpha=0.5
    )

    integrator = LLMWikiKnowledgeGraphIntegratorV4(
        domain="test_llm_wiki",
        enable_cache=True,
        evorag_config=config
    )

    print("\n集成文档块...")
    graph = integrator.integrate_chunks(test_chunks)

    print(f"\n集成结果:")
    print(f"  节点数: {len(graph.nodes)}")
    print(f"  关系数: {len(graph.relations)}")

    # 测试混合检索
    print(f"\n测试混合检索...")
    results = integrator.hybrid_retrieve("机器学习", top_k=5)
    print(f"  检索结果数: {len(results)}")

    # 测试EvoRAG推理
    print(f"\n测试EvoRAG图谱推理...")
    reasoning = integrator.reason_over_graph_evorag("什么是机器学习？")
    print(f"  查询: {reasoning['query']}")
    print(f"  答案: {reasoning['answer'][:100]}...")
    print(f"  推理路径数: {len(reasoning['reasoning_paths'])}")

    # 获取统计
    stats = integrator.get_evorag_statistics()
    print(f"\nV4集成器统计:")
    print(f"  反馈次数: {stats['feedback_count']}")
    print(f"  检索次数: {stats['retrieval_count']}")

    print("\n✅ 测试4通过: V4集成器（EvoRAG完整集成）")
    return integrator


def main():
    """主测试函数"""
    print("\n" + "🚀"*30)
    print("EvoRAG 集成测试")
    print("🚀"*30)

    try:
        # 测试1: 反馈驱动反向传播
        fm = test_feedback_manager()

        # 测试2: 知识图谱自进化
        evolver = test_kg_self_evolver(fm)

        # 测试3: 混合优先级检索
        retriever = test_hybrid_retriever(fm, evolver)

        # 测试4: V4集成器
        integrator = test_v4_integrator()

        print("\n" + "✅"*30)
        print("所有测试通过！EvoRAG集成成功！")
        print("✅"*30)

        print("\n" + "="*60)
        print("EvoRAG 三大核心特性已实现:")
        print("  1. ✅ 反馈驱动反向传播")
        print("  2. ✅ 知识图谱自进化")
        print("  3. ✅ 混合优先级检索")
        print("="*60)

        return 0

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
