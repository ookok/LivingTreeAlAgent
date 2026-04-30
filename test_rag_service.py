"""测试统一RAG服务"""
import sys
sys.path.insert(0, 'client/src')

from business.memory import get_rag_service

print("=" * 60)
print("统一RAG服务测试")
print("=" * 60)

rag_service = get_rag_service()

# 1. 统计信息
stats = rag_service.get_stats()
print("\n[1] 统计信息")
print(f"  总查询数: {stats['total_queries']}")
print(f"  平均延迟: {stats['avg_latency_ms']:.2f}ms")
print(f"  FusionEngine: {'✓' if stats['fusion_engine_integrated'] else '✗'}")
print(f"  KnowledgeBase: {'✓' if stats['knowledge_base_integrated'] else '✗'}")
print(f"  IntentClassifier: {'✓' if stats['intent_classifier_integrated'] else '✗'}")
print(f"  MultiModal: {'✓' if stats['multi_modal_integrated'] else '✗'}")
print(f"  Reranker: {'✓' if stats['reranker_integrated'] else '✗'}")
print(f"  SessionCache: {'✓' if stats['session_cache_integrated'] else '✗'}")
print(f"  ExactCache: {'✓' if stats['exact_cache_integrated'] else '✗'}")

# 2. 测试检索
print("\n[2] 测试检索")
results = rag_service.retrieve("什么是人工智能？")
print(f"  检索结果数: {len(results)}")
for i, result in enumerate(results):
    print(f"    {i+1}. 来源: {result.source}, 分数: {result.score:.2f}, 置信度: {result.confidence:.2f}")

# 3. 测试RAG生成
print("\n[3] 测试RAG生成")
result = rag_service.generate("什么是机器学习？")
print(f"  成功: {result['success']}")
print(f"  源数量: {result['total_sources']}")

# 4. 更新知识库
print("\n[4] 测试更新知识库")
doc_id = rag_service.update_knowledge("机器学习是人工智能的一个分支。", title="机器学习简介")
print(f"  文档ID: {doc_id}")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)