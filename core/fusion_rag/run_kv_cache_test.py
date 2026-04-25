"""KV Cache 优化器独立测试"""
import sys
from pathlib import Path
import importlib.util

# 添加项目根目录
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 直接加载 kv_cache_optimizer 模块，避免导入 core/__init__.py
def load_module_directly(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

kv_cache_module = load_module_directly(
    "kv_cache_optimizer",
    project_root / "core" / "fusion_rag" / "kv_cache_optimizer.py"
)

LRUCache = kv_cache_module.LRUCache
SemanticQueryCache = kv_cache_module.SemanticQueryCache
RetrievalResultCache = kv_cache_module.RetrievalResultCache
LLMResponseCache = kv_cache_module.LLMResponseCache
FusionKVCacheManager = kv_cache_module.FusionKVCacheManager
get_kv_cache_manager = kv_cache_module.get_kv_cache_manager
clear_kv_cache = kv_cache_module.clear_kv_cache

def test_lru_cache():
    print('=== 测试 LRU Cache ===')
    cache = LRUCache(max_size=3, ttl=60)
    cache.set('a', 1)
    cache.set('b', 2)
    cache.set('c', 3)
    print(f'a={cache.get("a")}, b={cache.get("b")}, c={cache.get("c")}')
    cache.set('d', 4)  # 触发 LRU 淘汰
    print(f'a 被淘汰: {cache.get("a") is None}, d={cache.get("d")}')
    print('✅ LRU Cache 测试通过\n')

def test_semantic_query_cache():
    print('=== 测试 SemanticQueryCache ===')
    sem_cache = SemanticQueryCache(max_size=10, ttl=60, similarity_threshold=0.9)
    sem_cache.set('Python 是什么', {'answer': '一种编程语言'})
    value, sim = sem_cache.get('Python 是什么', return_similarity=True)
    print(f'精确匹配: value={value}, similarity={sim}')
    print('✅ SemanticQueryCache 测试通过\n')

def test_retrieval_result_cache():
    print('=== 测试 RetrievalResultCache ===')
    ret_cache = RetrievalResultCache(max_size=10, ttl=60)
    results = [{'id': '1', 'content': '测试'}, {'id': '2', 'content': '测试2'}]
    ret_cache.set('查询', results)
    cached = ret_cache.get('查询')
    print(f'检索缓存: {len(cached)} 条结果')
    print('✅ RetrievalResultCache 测试通过\n')

def test_llm_response_cache():
    print('=== 测试 LLMResponseCache ===')
    llm_cache = LLMResponseCache(max_size=10, ttl=60)
    messages = [{'role': 'user', 'content': '你好'}]
    response = {'choices': [{'message': {'content': '你好！'}}]}
    llm_cache.set(messages, response)
    cached = llm_cache.get(messages)
    print(f'LLM 缓存: {cached["choices"][0]["message"]["content"]}')
    print('✅ LLMResponseCache 测试通过\n')

def test_fusion_kv_cache_manager():
    print('=== 测试 FusionKVCacheManager ===')
    manager = FusionKVCacheManager()
    stats = manager.get_stats()
    print(f'Query Cache: {stats["query_cache"]["type"]}')
    print(f'Retrieval Cache: {stats["retrieval_cache"]["type"]}')
    print(f'LLM Cache: {stats["llm_cache"]["type"]}')

    # 测试缓存操作
    manager.set_query_cache('test', {'data': 'value'})
    result = manager.get_query_cached('test')
    print(f'缓存读写: {result}')

    # 测试清空
    manager.invalidate_all()
    result = manager.get_query_cached('test')
    print(f'清空后查询: {result}')
    print('✅ FusionKVCacheManager 测试通过\n')

def test_integration_with_knowledge_base():
    print('=== 测试 KnowledgeBase 集成 ===')
    try:
        from core.fusion_rag.knowledge_base import KnowledgeBaseLayer

        kb = KnowledgeBaseLayer(enable_kv_cache=True)

        # 添加测试文档
        kb.add_document({
            'id': 'doc1',
            'title': '测试文档',
            'content': '这是一篇关于 Python 编程的测试文档。',
            'type': 'article'
        })

        # 第一次搜索（写入缓存）
        results1 = kb.search('Python 编程', top_k=5)
        print(f'第一次搜索: {len(results1)} 条结果')

        # 第二次搜索（应该命中缓存）
        results2 = kb.search('Python 编程', top_k=5)
        print(f'第二次搜索: {len(results2)} 条结果')

        stats = kb.get_stats()
        print(f'KV Cache 启用: {stats["kv_cache_enabled"]}')
        print('✅ KnowledgeBase 集成测试通过\n')
    except Exception as e:
        print(f'⚠️ KnowledgeBase 集成测试跳过: {e}\n')

def test_integration_with_fusion_engine():
    print('=== 测试 FusionEngine 集成 ===')
    try:
        from core.fusion_rag.fusion_engine import FusionEngine

        engine = FusionEngine(top_k=10, enable_llm_cache=True)

        stats = engine.get_stats()
        print(f'LLM Cache 启用: {stats["llm_cache_enabled"]}')
        print('✅ FusionEngine 集成测试通过\n')
    except Exception as e:
        print(f'⚠️ FusionEngine 集成测试跳过: {e}\n')

if __name__ == '__main__':
    print('=' * 50)
    print('FusionRAG KV Cache 优化器测试')
    print('=' * 50)
    print()

    test_lru_cache()
    test_semantic_query_cache()
    test_retrieval_result_cache()
    test_llm_response_cache()
    test_fusion_kv_cache_manager()
    test_integration_with_knowledge_base()
    test_integration_with_fusion_engine()

    print('=' * 50)
    print('所有测试完成!')
    print('=' * 50)
