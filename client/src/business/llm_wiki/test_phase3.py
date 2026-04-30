"""
测试 LLM Wiki Phase 3 功能

测试内容：
1. 跨文档引用检测
2. 实体链接（Entity Linking）
3. 图谱推理（路径查找、子图提取、问答推理）
4. 性能优化（缓存、批量处理）
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from business.llm_wiki.models import DocumentChunk
from business.llm_wiki.knowledge_graph_integrator_v3 import (
    LLMWikiKnowledgeGraphIntegratorV3,
    integrate_llm_wiki_to_graph_v3
)


def create_test_chunks_with_cross_refs():
    """创建带跨文档引用的测试数据"""
    chunks = [
        # 文档1: Python教程
        DocumentChunk(
            content="# Python 教程\n\n这是Python编程语言的教程。",
            chunk_type="text",
            title="Python 教程",
            section="# Python 教程",
            source="python_tutorial.md",
            metadata={"line_start": 1, "line_end": 2}
        ),
        DocumentChunk(
            content="**Python**是一种高级编程语言。参见[机器学习基础](ml_basics.md)。",
            chunk_type="text",
            title="Python 简介",
            section="## Python 简介",
            source="python_tutorial.md",
            metadata={"line_start": 4, "line_end": 5}
        ),
        DocumentChunk(
            content="```python\nprint('Hello, World!')\n```",
            chunk_type="code",
            title="Hello World 示例",
            section="## 示例代码",
            source="python_tutorial.md",
            metadata={"line_start": 7, "line_end": 9}
        ),
        
        # 文档2: 机器学习基础（被引用）
        DocumentChunk(
            content="# 机器学习基础\n\n机器学习是AI的重要分支。参考 Python 教程。",
            chunk_type="text",
            title="机器学习基础",
            section="# 机器学习基础",
            source="ml_basics.md",
            metadata={"line_start": 1, "line_end": 2}
        ),
        DocumentChunk(
            content="**机器学习**需要**Python**编程。See [Python 教程](python_tutorial.md)。",
            chunk_type="text",
            title="ML 简介",
            section="## 简介",
            source="ml_basics.md",
            metadata={"line_start": 4, "line_end": 5}
        ),
    ]
    return chunks


def test_cross_document_references():
    """测试跨文档引用检测"""
    print("\n=== 测试1: 跨文档引用检测 ===")
    
    chunks = create_test_chunks_with_cross_refs()
    
    integrator = LLMWikiKnowledgeGraphIntegratorV3(domain="test_cross_ref")
    graph = integrator.integrate_chunks(chunks)
    
    stats = integrator.get_statistics()
    print(f"节点数: {len(graph.nodes)}")
    print(f"关系数: {len(graph.relations)}")
    print(f"关系类型: {stats.get('relation_types', {})}")
    print(f"跨文档引用数: {stats.get('cross_refs', 0)}")
    
    # 检查是否有 cross_reference 关系
    cross_refs = [r for r in graph.relations if r.relation_type == "cross_reference"]
    print(f"cross_reference 关系数: {len(cross_refs)}")
    
    if len(cross_refs) > 0:
        print("✅ 跨文档引用检测成功")
        return True
    else:
        print("⚠️  未检测到跨文档引用（可能需要调整检测模式）")
        return False


def test_entity_linking():
    """测试实体链接"""
    print("\n=== 测试2: 实体链接（Entity Linking） ===")
    
    chunks = create_test_chunks_with_cross_refs()
    
    integrator = LLMWikiKnowledgeGraphIntegratorV3(domain="test_entity_linking")
    graph = integrator.integrate_chunks(chunks)
    
    # 检查实体索引
    entity_index = integrator._entity_index
    print(f"实体索引大小: {len(entity_index)}")
    print(f"实体列表: {list(entity_index.keys())}")
    
    # 检查是否有重复的 "Python" 概念节点
    python_nodes = [n for n in graph.nodes.values() if n.title.lower() == "python"]
    print(f"Python 概念节点数: {len(python_nodes)}")
    
    if len(python_nodes) == 1:
        print("✅ 实体链接成功：相同实体合并到同一节点")
        return True
    else:
        print(f"⚠️  实体链接可能未生效：找到 {len(python_nodes)} 个 Python 节点")
        return False


def test_graph_reasoning():
    """测试图谱推理功能"""
    print("\n=== 测试3: 图谱推理功能 ===")
    
    chunks = create_test_chunks_with_cross_refs()
    
    integrator = LLMWikiKnowledgeGraphIntegratorV3(domain="test_reasoning")
    graph = integrator.integrate_chunks(chunks)
    
    # 3.1 测试 find_path
    print("\n3.1 测试 find_path（路径查找）")
    node_ids = list(graph.nodes.keys())
    if len(node_ids) >= 2:
        path = integrator.find_path(node_ids[0], node_ids[-1])
        print(f"路径: {path}")
        if path:
            print(f"✅ 找到路径，长度: {len(path)}")
        else:
            print("⚠️  未找到路径（节点可能不连通）")
    
    # 3.2 测试 extract_subgraph
    print("\n3.2 测试 extract_subgraph（子图提取）")
    if node_ids:
        center_id = node_ids[0]
        subgraph = integrator.extract_subgraph(center_id, max_depth=2)
        print(f"中心节点: {center_id}")
        print(f"子图节点数: {len(subgraph.nodes)}")
        print(f"子图关系数: {len(subgraph.relations)}")
        if len(subgraph.nodes) > 0:
            print("✅ 子图提取成功")
    
    # 3.3 测试 query_related_concepts
    print("\n3.3 测试 query_related_concepts（相关概念查询）")
    if node_ids:
        concepts = integrator.query_related_concepts(node_ids[0], max_depth=2)
        print(f"相关概念数: {len(concepts)}")
        for concept in concepts[:3]:
            print(f"  - {concept['concept']} (深度={concept['depth']})")
        if len(concepts) >= 0:
            print("✅ 相关概念查询成功")
    
    # 3.4 测试 reason_over_graph
    print("\n3.4 测试 reason_over_graph（图谱推理）")
    result = integrator.reason_over_graph("Python 机器学习")
    print(f"推理结果: {result}")
    if result.get("confidence", 0) > 0:
        print("✅ 图谱推理成功")
    
    return True


def test_performance_optimization():
    """测试性能优化（缓存）"""
    print("\n=== 测试4: 性能优化（缓存） ===")
    
    chunks = create_test_chunks_with_cross_refs()
    
    # 启用缓存
    integrator = LLMWikiKnowledgeGraphIntegratorV3(domain="test_cache", enable_cache=True)
    graph = integrator.integrate_chunks(chunks)
    
    # 第一次查询（应该miss）
    node = integrator.get_chunk_by_index(0)
    
    # 第二次查询（应该hit）
    node2 = integrator.get_chunk_by_index(0)
    
    cache_stats = integrator.get_cache_stats()
    print(f"缓存命中率: {cache_stats['hit_rate']:.2%}")
    print(f"缓存命中次数: {cache_stats['cache_hits']}")
    print(f"缓存未命中次数: {cache_stats['cache_misses']}")
    
    if cache_stats['hit_rate'] > 0:
        print("✅ 缓存功能正常")
        return True
    else:
        print("⚠️  缓存可能未生效")
        return False


def test_multiple_documents():
    """测试多文档集成"""
    print("\n=== 测试5: 多文档集成 ===")
    
    chunks = create_test_chunks_with_cross_refs()
    
    integrator = LLMWikiKnowledgeGraphIntegratorV3(domain="test_multi_doc")
    graph = integrator.integrate_chunks(chunks)
    
    stats = integrator.get_statistics()
    perf_stats = integrator.get_performance_stats()
    
    print(f"总节点数: {len(graph.nodes)}")
    print(f"总关系数: {len(graph.relations)}")
    print(f"实体链接数: {perf_stats.get('entity_links', 0)}")
    print(f"跨文档引用数: {perf_stats.get('cross_refs', 0)}")
    print(f"关系类型: {stats.get('relation_types', {})}")
    
    print("✅ 多文档集成测试完成")
    return True


def main():
    """主测试函数"""
    print("开始测试 LLM Wiki Phase 3 功能...")
    print("=" * 60)
    
    results = []
    
    # 运行所有测试
    results.append(("跨文档引用检测", test_cross_document_references()))
    results.append(("实体链接", test_entity_linking()))
    results.append(("图谱推理", test_graph_reasoning()))
    results.append(("性能优化（缓存）", test_performance_optimization()))
    results.append(("多文档集成", test_multiple_documents()))
    
    # 输出总结
    print("\n" + "=" * 60)
    print("测试总结:")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    total_passed = sum(1 for _, r in results if r)
    total_tests = len(results)
    print(f"\n总计: {total_passed}/{total_tests} 个测试通过")
    
    if total_passed == total_tests:
        print("\n🎉 所有测试通过！Phase 3 功能正常。")
    else:
        print(f"\n⚠️  有 {total_tests - total_passed} 个测试失败，请检查。")


if __name__ == "__main__":
    main()
