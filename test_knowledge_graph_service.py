"""测试统一知识图谱服务"""
import sys
sys.path.insert(0, 'client/src')

from business.memory import get_knowledge_graph_service

print("=" * 60)
print("统一知识图谱服务测试")
print("=" * 60)

kg_service = get_knowledge_graph_service()

# 1. 统计信息
print("\n[1] 统计信息")
stats = kg_service.get_stats()
print(f"  节点数: {stats['total_nodes']}")
print(f"  关系数: {stats['total_relations']}")
print(f"  LLM Wiki集成: {'✓ 是' if stats['llm_wiki_integrated'] else '✗ 否'}")
print(f"  KnowledgeGraphManager集成: {'✓ 是' if stats['knowledge_graph_manager_integrated'] else '✗ 否'}")

# 2. 添加知识节点
print("\n[2] 添加知识节点")
ai_id = kg_service.add_node("人工智能", domain="计算机科学", year=1956)
ml_id = kg_service.add_node("机器学习", domain="人工智能")
dl_id = kg_service.add_node("深度学习", domain="机器学习")
print(f"  添加节点: AI={ai_id}, ML={ml_id}, DL={dl_id}")

# 3. 添加关系
print("\n[3] 添加关系")
kg_service.add_relation(ai_id, ml_id, "包含")
kg_service.add_relation(ml_id, dl_id, "包含")
print(f"  添加关系: AI -包含-> ML -包含-> DL")

# 4. 测试检索
print("\n[4] 混合检索测试")
results = kg_service.hybrid_retrieve("人工智能")
print(f"  检索结果 ({len(results)}):")
for i, result in enumerate(results):
    print(f"    {i+1}. {result.entity} (分数: {result.score:.2f}, 置信度: {result.confidence:.2f})")

# 5. 测试推理
print("\n[5] 图谱推理测试")
reason_result = kg_service.reason_over_graph("人工智能包含哪些领域")
print(f"  推理成功: {reason_result.get('success', False)}")

# 6. 测试知识融合
print("\n[6] 知识融合测试")
fusion_result = kg_service.knowledge_fusion(["人工智能", "机器学习", "深度学习"])
print(f"  融合来源: {fusion_result['sources']}")
print(f"  融合概念数: {len(fusion_result['merged_concepts'])}")
print(f"  融合摘要: {fusion_result['summary']}")

# 7. 测试图查询
print("\n[7] 图查询测试")
graph_result = kg_service.graph_query("all")
print(f"  节点数: {len(graph_result.get('nodes', []))}")
print(f"  关系数: {len(graph_result.get('relations', []))}")

# 8. 更新统计
print("\n[8] 更新后的统计信息")
stats = kg_service.get_stats()
print(f"  节点数: {stats['total_nodes']}")
print(f"  关系数: {stats['total_relations']}")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)