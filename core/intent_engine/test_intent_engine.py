"""
IntentEngine 测试文件
"""

import pytest
from intent_engine import (
    IntentParser, 
    IntentClassifier, 
    IntentExecutor,
    IntentCache,
    IntentType,
    IntentPriority,
    IntentComplexity
)


class TestIntentParser:
    """意图解析器测试"""
    
    def setup_method(self):
        self.parser = IntentParser()
        
    def test_code_generation_intent(self):
        """测试代码生成意图"""
        intent = self.parser.parse("帮我写一个用户登录函数")
        assert intent.intent_type == IntentType.CODE_GENERATION
        assert intent.confidence > 0
        
    def test_bug_fix_intent(self):
        """测试Bug修复意图"""
        intent = self.parser.parse("修复这个错误: index out of range")
        assert intent.intent_type == IntentType.BUG_FIX
        assert 'error_message' in intent.parameters
        
    def test_entity_extraction(self):
        """测试实体提取"""
        intent = self.parser.parse("打开 core/agent.py 文件")
        assert 'file_paths' in intent.entities
        assert 'core/agent.py' in intent.entities['file_paths']
        
    def test_constraint_extraction(self):
        """测试约束条件提取"""
        intent = self.parser.parse("快速执行这个操作")
        assert 'performance:high' in intent.constraints


class TestIntentClassifier:
    """意图分类器测试"""
    
    def setup_method(self):
        self.parser = IntentParser()
        self.classifier = IntentClassifier()
        
    def test_priority_assessment(self):
        """测试优先级评估"""
        intent = self.parser.parse("紧急修复这个bug")
        category = self.classifier.classify(intent)
        assert category.priority == IntentPriority.P0_CRITICAL
        
    def test_complexity_assessment(self):
        """测试复杂度评估"""
        intent = self.parser.parse("写一个完整的用户系统")
        category = self.classifier.classify(intent)
        assert category.complexity in [
            IntentComplexity.MODERATE,
            IntentComplexity.COMPLEX,
            IntentComplexity.VERY_COMPLEX
        ]
        
    def test_token_estimation(self):
        """测试Token预估"""
        intent = self.parser.parse("生成一个简单的hello world")
        category = self.classifier.classify(intent)
        assert category.estimated_tokens > 0


class TestIntentCache:
    """意图缓存测试"""
    
    def setup_method(self):
        self.cache = IntentCache(max_size=10, default_ttl=60)
        
    def test_cache_set_get(self):
        """测试缓存存取"""
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"
        
    def test_cache_miss(self):
        """测试缓存未命中"""
        result = self.cache.get("nonexistent")
        assert result is None
        
    def test_cache_lru_eviction(self):
        """测试LRU淘汰"""
        cache = IntentCache(max_size=3)
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.set("k3", "v3")
        cache.set("k4", "v4")  # 应该淘汰k1
        
        assert cache.get("k1") is None
        assert cache.get("k4") == "v4"
        
    def test_cache_stats(self):
        """测试缓存统计"""
        self.cache.set("k1", "v1")
        self.cache.get("k1")
        self.cache.get("k2")  # miss
        
        stats = self.cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        
    def test_cache_key_generation(self):
        """测试缓存键生成"""
        key1 = IntentCache.generate_key("test intent")
        key2 = IntentCache.generate_key("test intent")
        key3 = IntentCache.generate_key("different intent")
        
        assert key1 == key2
        assert key1 != key3


class TestIntentIntegration:
    """集成测试"""
    
    def setup_method(self):
        self.parser = IntentParser()
        self.classifier = IntentClassifier()
        self.executor = IntentExecutor()
        
    def test_full_intent_flow(self):
        """测试完整意图流程"""
        # 1. 解析
        intent = self.parser.parse("生成一个Python函数")
        assert intent.raw_text == "生成一个Python函数"
        
        # 2. 分类
        category = self.classifier.classify(intent)
        assert category.category == "code_generation"
        
        # 3. 验证结果结构
        assert hasattr(category, 'priority')
        assert hasattr(category, 'complexity')
        assert hasattr(category, 'estimated_tokens')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
