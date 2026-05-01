"""
DeepOnto Integration Test Suite
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ontology_reasoner():
    """测试本体推理器"""
    logger.info("=== 测试本体推理器 ===")
    from .ontology_reasoner import get_ontology_reasoner
    
    reasoner = get_ontology_reasoner()
    reasoner.initialize()
    
    # 测试一致性检查
    is_consistent = reasoner.check_consistency()
    logger.info(f"本体一致性: {is_consistent}")
    
    # 测试类层次结构
    hierarchy = reasoner.get_class_hierarchy()
    logger.info(f"类层次结构: {hierarchy}")
    
    # 测试实例分类
    types = reasoner.classify_instance("Person")
    logger.info(f"实体类型分类: {types}")
    
    # 测试关系推断
    relations = reasoner.infer_relations("Person", "Organization")
    logger.info(f"推断关系: {relations}")
    
    # 测试推理
    result = reasoner.reason({"query": "What is a Person?"})
    logger.info(f"推理结果: consistent={result.is_consistent}")
    logger.info(f"推断公理: {result.inferred_axioms}")
    
    logger.info("本体推理器测试完成\n")

async def test_entity_embedding():
    """测试实体嵌入服务"""
    logger.info("=== 测试实体嵌入服务 ===")
    from .entity_embedding import get_entity_embedding_service
    
    service = get_entity_embedding_service()
    service.initialize()
    
    # 测试编码实体
    result = service.encode_entity("人工智能")
    logger.info(f"实体嵌入维度: {len(result.embedding)}")
    
    # 测试相似性计算
    similarity = service.calculate_similarity("人工智能", "机器学习")
    logger.info(f"语义相似度: {similarity}")
    
    # 测试相似实体查找
    candidates = ["人工智能", "机器学习", "深度学习", "Python"]
    matches = service.find_similar_entities("AI", candidates, top_k=3)
    logger.info(f"相似实体匹配: {[(m.entity_id, m.score) for m in matches]}")
    
    # 测试实体解析
    context = {"candidates": ["机器学习", "深度学习"]}
    resolved = service.resolve_entity("ML", context)
    logger.info(f"实体解析结果: {resolved.entity_id} (置信度: {resolved.score})")
    
    # 测试实体聚类
    entities = ["人工智能", "机器学习", "深度学习", "Python", "PyTorch", "TensorFlow"]
    clusters = service.cluster_entities(entities, num_clusters=2)
    logger.info(f"实体聚类结果: {clusters}")
    
    logger.info("实体嵌入服务测试完成\n")

async def test_ontology_alignment():
    """测试本体对齐服务"""
    logger.info("=== 测试本体对齐服务 ===")
    from .ontology_alignment import get_alignment_service
    
    service = get_alignment_service()
    service.initialize()
    
    # 测试实体匹配
    target_entities = ["Human", "Company", "Location"]
    mappings = service.match_entities("Person", target_entities)
    logger.info(f"实体对齐映射: {[(m.source_entity, m.target_entity, m.confidence) for m in mappings]}")
    
    # 测试对齐评估
    test_mappings = [
        {"source_entity": "Person", "target_entity": "Human", "confidence": 0.95, "relation_type": "equivalent"},
        {"source_entity": "Organization", "target_entity": "Company", "confidence": 0.88, "relation_type": "subclass"}
    ]
    gold_standard = [("Person", "Human"), ("Organization", "Company")]
    result = service.evaluate_alignment(test_mappings, gold_standard)
    logger.info(f"对齐评估: precision={result.precision}, recall={result.recall}, f1={result.f1_score}")
    
    # 测试本体合并
    ontologies = [
        {"classes": ["Person", "Organization"]},
        {"classes": ["Human", "Company"]}
    ]
    merged = service.merge_ontologies(ontologies)
    logger.info(f"本体合并结果: {merged}")
    
    logger.info("本体对齐服务测试完成\n")

async def test_ontology_completion():
    """测试本体补全服务"""
    logger.info("=== 测试本体补全服务 ===")
    from .ontology_completion import get_completion_service
    
    service = get_completion_service()
    service.initialize()
    
    # 测试实体补全
    result = service.complete_entity("NewEntity", {"context": "test"})
    logger.info(f"实体补全结果: {result.added_axioms}")
    
    # 测试缺失公理预测
    ontology = {"classes": ["Person", "Human"]}
    axioms = service.predict_missing_axioms(ontology, max_axioms=3)
    logger.info(f"预测缺失公理: {axioms}")
    
    # 测试属性建议
    props = service.suggest_properties("Person")
    logger.info(f"属性建议: {props}")
    
    # 测试定义优化
    refined = service.refine_definition("Person", "A human being")
    logger.info(f"优化定义: {refined}")
    
    logger.info("本体补全服务测试完成\n")

async def test_smart_module_scheduler():
    """测试智能模块调度器"""
    logger.info("=== 测试智能模块调度器 ===")
    from .smart_module_scheduler import get_smart_module_scheduler, ModuleType
    
    scheduler = get_smart_module_scheduler()
    scheduler.initialize()
    
    # 测试查询分析
    query_context = scheduler.analyze_query("What is machine learning?")
    logger.info(f"查询分析结果:")
    logger.info(f"  查询: {query_context.query}")
    logger.info(f"  实体: {query_context.entities}")
    logger.info(f"  意图: {query_context.intent}")
    logger.info(f"  置信度: {query_context.confidence}")
    
    # 测试模块选择
    selected = scheduler.select_modules(query_context)
    logger.info(f"选择的模块: {[m.value for m in selected]}")
    
    # 注册测试模块
    def test_handler(context):
        return {"result": "test_result", "context": context.query}
    
    scheduler.register_module(ModuleType.FUSION_RAG, test_handler)
    
    # 测试执行查询
    results = await scheduler.execute_query("What is AI?")
    logger.info(f"执行结果: {len(results)} 个模块响应")
    
    logger.info("智能模块调度器测试完成\n")

async def test_fusion_rag_integration():
    """测试FusionRAG集成"""
    logger.info("=== 测试FusionRAG集成 ===")
    from ..fusion_rag.engine import get_fusion_rag_engine
    
    engine = get_fusion_rag_engine()
    
    # 测试本体推理查询
    result = await engine.ontological_query("What is a Person?")
    logger.info(f"本体推理查询结果: {result.content[:100]}...")
    logger.info(f"置信度: {result.confidence}")
    
    # 测试语义搜索
    results = await engine.semantic_search("machine learning", top_k=3)
    logger.info(f"语义搜索结果: {len(results)} 个匹配")
    
    stats = engine.get_stats()
    logger.info(f"引擎状态: {stats}")
    
    logger.info("FusionRAG集成测试完成\n")

async def test_knowledge_graph_integration():
    """测试知识图谱集成"""
    logger.info("=== 测试知识图谱集成 ===")
    from ..fusion_rag.knowledge_graph import get_dynamic_knowledge_graph
    
    kg = get_dynamic_knowledge_graph()
    
    # 添加测试实体
    await kg.add_entity({
        "id": "TestPerson",
        "name": "Test Person",
        "type": "person",
        "description": "A test person"
    })
    
    # 测试本体分类
    types = await kg.classify_entity("TestPerson")
    logger.info(f"实体分类结果: {types}")
    
    # 测试本体关系推断
    relations = await kg.infer_ontological_relations("TestPerson")
    logger.info(f"本体关系推断: {len(relations)} 个关系")
    
    # 测试一致性验证
    consistency = await kg.validate_knowledge_consistency()
    logger.info(f"知识一致性: {consistency}")
    
    # 获取类层次结构
    hierarchy = kg.get_class_hierarchy()
    logger.info(f"类层次结构: {hierarchy}")
    
    logger.info("知识图谱集成测试完成\n")

async def test_entity_management_integration():
    """测试实体管理集成"""
    logger.info("=== 测试实体管理集成 ===")
    from ..entity_management.entity_resolution import get_entity_resolver
    from ..entity_management.models import Entity, EntityType
    
    resolver = get_entity_resolver()
    
    # 创建测试实体
    entity = Entity(
        id="test_entity",
        text="AI",
        entity_type=EntityType.TECH_TERM,
        start=0,
        end=2
    )
    
    # 测试标准解析
    resolved = resolver.resolve(entity, context="machine learning")
    logger.info(f"标准解析结果: {resolved.canonical_name} (置信度: {resolved.confidence})")
    
    # 测试基于嵌入的解析
    resolved_emb = resolver.resolve_with_embedding(entity, context="artificial intelligence")
    logger.info(f"嵌入解析结果: {resolved_emb.canonical_name} (置信度: {resolved_emb.confidence})")
    
    # 测试实体聚类
    entities = [
        Entity(id="1", text="人工智能", entity_type=EntityType.TECH_TERM, start=0, end=4),
        Entity(id="2", text="机器学习", entity_type=EntityType.TECH_TERM, start=0, end=4),
        Entity(id="3", text="Python", entity_type=EntityType.TECH_TERM, start=0, end=6),
        Entity(id="4", text="PyTorch", entity_type=EntityType.TECH_TERM, start=0, end=7),
    ]
    clusters = resolver.cluster_entities(entities, num_clusters=2)
    logger.info(f"实体聚类结果: {len(clusters)} 个聚类")
    
    logger.info("实体管理集成测试完成\n")

async def main():
    """运行所有测试"""
    logger.info("=" * 60)
    logger.info("DeepOnto 集成测试套件")
    logger.info("=" * 60 + "\n")
    
    try:
        await test_ontology_reasoner()
        await test_entity_embedding()
        await test_ontology_alignment()
        await test_ontology_completion()
        await test_smart_module_scheduler()
        await test_fusion_rag_integration()
        await test_knowledge_graph_integration()
        await test_entity_management_integration()
        
        logger.info("=" * 60)
        logger.info("🎉 所有测试通过！")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())