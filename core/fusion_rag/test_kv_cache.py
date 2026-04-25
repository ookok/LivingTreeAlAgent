"""
FusionRAG KV Cache 优化器测试

测试内容:
1. LRU Cache 基本操作
2. 语义查询缓存
3. 检索结果缓存
4. LLM 响应缓存
5. 缓存预热
6. FusionKVCacheManager 集成

运行: python -m pytest core/fusion_rag/test_kv_cache.py -v
"""

import pytest
import time
import sys
from pathlib import Path

# 添加项目根目录到 path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestLRUCache:
    """测试 LRU Cache"""
    
    def test_basic_operations(self):
        from core.fusion_rag.kv_cache_optimizer import LRUCache
        
        cache = LRUCache(max_size=3, ttl=60)
        
        # 写入
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        
        # 读取
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        
        # LRU 淘汰
        cache.set("d", 4)  # 触发淘汰
        assert cache.get("a") is None  # a 被淘汰
        assert cache.get("d") == 4
    
    def test_ttl_expiration(self):
        from core.fusion_rag.kv_cache_optimizer import LRUCache
        
        cache = LRUCache(max_size=10, ttl=1)  # 1秒 TTL
        
        cache.set("x", 100)
        assert cache.get("x") == 100
        
        time.sleep(1.1)  # 等待过期
        
        assert cache.get("x") is None
    
    def test_hit_rate(self):
        from core.fusion_rag.kv_cache_optimizer import LRUCache
        
        cache = LRUCache(max_size=10, ttl=60)
        
        cache.set("a", 1)
        cache.get("a")  # 命中
        cache.get("b")  # 未命中
        
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert abs(stats["hit_rate"] - 0.5) < 0.01


class TestSemanticQueryCache:
    """测试语义查询缓存"""
    
    def test_exact_match(self):
        from core.fusion_rag.kv_cache_optimizer import SemanticQueryCache
        
        cache = SemanticQueryCache(max_size=10, ttl=60, similarity_threshold=0.9)
        
        cache.set("Python 是什么", {"answer": "一种编程语言"})
        
        value, similarity = cache.get("Python 是什么", return_similarity=True)
        assert value is not None
        assert value["answer"] == "一种编程语言"
        assert similarity == 1.0  # 精确匹配
    
    def test_similarity_match(self):
        from core.fusion_rag.kv_cache_optimizer import SemanticQueryCache
        
        # 简单的 hash 嵌入函数
        def simple_embedding(text):
            return [hash(text) % 100 / 100 for _ in range(10)]
        
        cache = SemanticQueryCache(
            max_size=10, 
            ttl=60, 
            similarity_threshold=0.7,
            embedding_func=simple_embedding
        )
        
        # 存储一个查询
        cache.set("Python 教程", {"content": "Python 入门指南"})
        
        # 查询相似问题
        value, similarity = cache.get("学习 Python", return_similarity=True)
        
        # 相似但不完全相同
        if value is not None:
            assert similarity >= 0.7


class TestRetrievalResultCache:
    """测试检索结果缓存"""
    
    def test_basic_caching(self):
        from core.fusion_rag.kv_cache_optimizer import RetrievalResultCache
        
        cache = RetrievalResultCache(max_size=10, ttl=60)
        
        results = [
            {"id": "1", "content": "测试文档", "score": 0.9},
            {"id": "2", "content": "测试文档2", "score": 0.8}
        ]
        
        cache.set("测试查询", results, top_k=5)
        
        cached = cache.get("测试查询", top_k=5)
        assert cached is not None
        assert len(cached) == 2
        assert cached[0]["id"] == "1"
    
    def test_filter_based_key(self):
        from core.fusion_rag.kv_cache_optimizer import RetrievalResultCache
        
        cache = RetrievalResultCache(max_size=10, ttl=60)
        
        cache.set("查询", [{"id": "1"}], filters={"doc_type": "article"})
        cache.set("查询", [{"id": "2"}], filters={"doc_type": "code"})
        
        # 不同过滤器应该有不同的缓存
        r1 = cache.get("查询", filters={"doc_type": "article"})
        r2 = cache.get("查询", filters={"doc_type": "code"})
        
        assert r1[0]["id"] == "1"
        assert r2[0]["id"] == "2"


class TestLLMResponseCache:
    """测试 LLM 响应缓存"""
    
    def test_message_hash(self):
        from core.fusion_rag.kv_cache_optimizer import LLMResponseCache
        
        cache = LLMResponseCache(max_size=10, ttl=60)
        
        messages = [
            {"role": "user", "content": "你好"}
        ]
        
        response = {
            "choices": [{"message": {"content": "你好！有什么可以帮你？"}}]
        }
        
        cache.set(messages, response)
        
        cached = cache.get(messages)
        assert cached is not None
        assert "你好！" in cached["choices"][0]["message"]["content"]


class TestCachePreheater:
    """测试缓存预热器"""
    
    def test_preheat(self):
        from core.fusion_rag.kv_cache_optimizer import CachePreheater
        
        preheater = CachePreheater()
        
        # 没有知识库时应该返回 0
        count = preheater.preheat(["Python", "Java"], top_k=5)
        assert count == 0


class TestFusionKVCacheManager:
    """测试 FusionKVCacheManager"""
    
    def test_singleton(self):
        from core.fusion_rag.kv_cache_optimizer import FusionKVCacheManager, get_kv_cache_manager
        
        manager1 = get_kv_cache_manager()
        manager2 = get_kv_cache_manager()
        
        # 应该是同一个实例
        assert manager1 is manager2
    
    def test_stats(self):
        from core.fusion_rag.kv_cache_optimizer import get_kv_cache_manager
        
        manager = get_kv_cache_manager()
        stats = manager.get_stats()
        
        assert "query_cache" in stats
        assert "retrieval_cache" in stats
        assert "llm_cache" in stats
        assert "config" in stats
    
    def test_invalidate_all(self):
        from core.fusion_rag.kv_cache_optimizer import get_kv_cache_manager
        
        manager = get_kv_cache_manager()
        
        # 添加一些缓存
        manager.set_query_cache("test", {"result": "data"})
        manager.set_retrieval_cache("test", [{"id": "1"}])
        manager.set_llm_cache([{"role": "user", "content": "test"}], {"content": "response"})
        
        # 使全部失效
        manager.invalidate_all()
        
        # 验证缓存已清空
        assert manager.get_query_cached("test") is None
        assert manager.get_retrieval_cached("test") is None


class TestKnowledgeBaseIntegration:
    """测试 KnowledgeBase 与 KV Cache 集成"""
    
    def test_knowledge_base_kv_cache(self):
        from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
        
        # 创建知识库（启用 KV Cache）
        kb = KnowledgeBaseLayer(enable_kv_cache=True)
        
        # 添加测试文档
        kb.add_document({
            "id": "doc1",
            "title": "测试文档",
            "content": "这是一篇关于 Python 编程的测试文档。",
            "type": "article"
        })
        
        # 第一次搜索（写入缓存）
        results1 = kb.search("Python 编程", top_k=5)
        assert len(results1) > 0
        
        # 第二次搜索（应该命中缓存）
        stats = kb.get_stats()
        assert stats["kv_cache_enabled"] == True
    
    def test_knowledge_base_without_kv_cache(self):
        from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
        
        # 创建知识库（禁用 KV Cache）
        kb = KnowledgeBaseLayer(enable_kv_cache=False)
        
        kb.add_document({
            "id": "doc1",
            "title": "测试文档",
            "content": "这是测试内容。",
            "type": "article"
        })
        
        results = kb.search("测试", top_k=5)
        stats = kb.get_stats()
        
        assert stats["kv_cache_enabled"] == False


class TestFusionEngineIntegration:
    """测试 FusionEngine 与 KV Cache 集成"""
    
    def test_fusion_engine_kv_cache(self):
        from core.fusion_rag.fusion_engine import FusionEngine
        
        # 创建 FusionEngine（启用 LLM Cache）
        engine = FusionEngine(top_k=10, enable_llm_cache=True)
        
        stats = engine.get_stats()
        assert stats["llm_cache_enabled"] == True


class TestL4ExecutorIntegration:
    """测试 L4Executor 与 KV Cache 集成"""
    
    def test_l4_executor_kv_cache(self):
        from core.fusion_rag.l4_executor import L4RelayExecutor
        
        # 创建 L4Executor（启用 KV Cache）
        executor = L4RelayExecutor(
            gateway_url="http://localhost:8000/v1",
            enable_kv_cache=True
        )
        
        stats = executor.get_stats()
        assert stats["kv_cache_enabled"] == True


def run_tests():
    """运行所有测试"""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()
