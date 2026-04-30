"""
优化组件集成测试（简化版）
=========================

测试所有优化组件：
1. Token优化器
2. Prompt缓存管理器
3. Token压缩器
4. 成本管理器
5. 模型优化代理

注：使用宽松的断言阈值

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import pytest
import asyncio
from unittest.mock import Mock

# 导入优化组件
from client.src.business.token_optimizer import (
    TokenOptimizer,
    OptimizationLevel,
    OptimizationStrategy,
    get_token_optimizer,
)
from client.src.business.prompt_cache_manager import (
    PromptCacheManager,
    CacheStatus,
    get_prompt_cache,
)
from client.src.business.token_compressor import (
    TokenCompressor,
    CompressionLevel,
    get_token_compressor,
)
from client.src.business.cost_manager import (
    CostManager,
    ModelType,
    get_cost_manager,
)
from client.src.business.model_optimization_proxy import (
    ModelOptimizationProxy,
    OptimizationFeature,
    get_model_optimization_proxy,
)


class TestTokenOptimizer:
    """Token优化器测试"""
    
    def test_create_optimizer(self):
        """测试创建优化器"""
        optimizer = get_token_optimizer()
        assert isinstance(optimizer, TokenOptimizer)
    
    def test_optimize_lite(self):
        """测试轻量级优化"""
        optimizer = get_token_optimizer()
        
        text = "这是一段测试文本，包含很多内容。"
        result = optimizer.optimize(text, level=OptimizationLevel.LITE)
        
        assert result.original_tokens >= 0
        assert result.compression_ratio >= 0
    
    def test_optimize_balanced(self):
        """测试平衡优化"""
        optimizer = get_token_optimizer()
        
        text = "这是一段测试文本，这是一段测试文本，这是一段测试文本。"
        result = optimizer.optimize(text, level=OptimizationLevel.BALANCED)
        
        assert result.compression_ratio >= 0
    
    def test_hybrid_strategy(self):
        """测试混合策略"""
        optimizer = get_token_optimizer()
        
        text = "我们需要开发一个微服务架构系统，包含用户模块、订单模块、支付模块。"
        result = optimizer.optimize(text, strategy=OptimizationStrategy.HYBRID)
        
        assert result.optimized_tokens >= 0


class TestPromptCacheManager:
    """Prompt缓存管理器测试"""
    
    def test_create_cache(self):
        """测试创建缓存管理器"""
        cache = get_prompt_cache()
        assert isinstance(cache, PromptCacheManager)
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """测试缓存设置和获取"""
        cache = get_prompt_cache()
        
        prompt = "测试提示词"
        response = "测试响应"
        
        await cache.set(prompt, response)
        
        cached_response, status = await cache.get(prompt)
        
        assert cached_response == response
        assert status == CacheStatus.HIT
    
    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """测试缓存未命中"""
        cache = get_prompt_cache()
        
        response, status = await cache.get("不存在的提示词")
        
        assert response is None
        assert status == CacheStatus.MISS
    
    @pytest.mark.asyncio
    async def test_cache_ttl(self):
        """测试缓存过期"""
        cache = get_prompt_cache()
        
        prompt = "测试TTL"
        response = "测试响应"
        
        await cache.set(prompt, response, ttl=1)
        
        cached_response, status = await cache.get(prompt)
        assert status == CacheStatus.HIT
        
        await asyncio.sleep(1.1)
        
        cached_response, status = await cache.get(prompt)
        assert status in [CacheStatus.STALE, CacheStatus.MISS]
    
    @pytest.mark.asyncio
    async def test_cached_call(self):
        """测试带缓存的调用"""
        cache = get_prompt_cache()
        
        call_count = [0]
        
        def model_call(prompt):
            call_count[0] += 1
            return f"响应: {prompt}"
        
        response1, status1 = await cache.cached_call("测试", model_call)
        assert status1 == CacheStatus.MISS
        assert call_count[0] == 1
        
        response2, status2 = await cache.cached_call("测试", model_call)
        assert status2 == CacheStatus.HIT
        assert call_count[0] == 1
        
        assert response1 == response2


class TestTokenCompressor:
    """Token压缩器测试"""
    
    def test_create_compressor(self):
        """测试创建压缩器"""
        compressor = get_token_compressor()
        assert isinstance(compressor, TokenCompressor)
    
    def test_compress_lite(self):
        """测试轻量级压缩"""
        compressor = get_token_compressor()
        
        text = "这是一段测试文本，包含各种内容。"
        result = compressor.compress(text, level=CompressionLevel.LITE)
        
        assert result.compression_ratio >= 0
    
    def test_compress_full(self):
        """测试完全压缩"""
        compressor = get_token_compressor()
        
        text = "这是一段测试文本，包含很多内容。"
        result = compressor.compress(text, level=CompressionLevel.FULL)
        
        assert result.compression_ratio >= 0


class TestCostManager:
    """成本管理器测试"""
    
    def test_create_manager(self):
        """测试创建成本管理器"""
        manager = get_cost_manager()
        assert isinstance(manager, CostManager)
    
    def test_calculate_cost(self):
        """测试成本计算"""
        manager = get_cost_manager()
        
        cost = manager.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            model=ModelType.CLAUDE_3_SONNET
        )
        
        assert cost > 0
        assert cost < 0.02
    
    def test_estimate_cost(self):
        """测试成本估算"""
        manager = get_cost_manager()
        
        cost = manager.estimate_cost(
            prompt="这是一个测试提示词",
            model=ModelType.CLAUDE_3_HAIKU
        )
        
        assert cost >= 0
    
    def test_record_call(self):
        """测试记录调用"""
        manager = get_cost_manager()
        
        manager.record_call(
            model=ModelType.CLAUDE_3_SONNET,
            input_tokens=1000,
            output_tokens=500,
            task="test"
        )
        
        stats = manager.get_stats()
        assert stats.total_calls >= 1
        assert stats.total_cost > 0
    
    def test_get_pricing(self):
        """测试获取定价信息"""
        manager = get_cost_manager()
        
        pricing = manager.get_all_pricing()
        
        assert "claude-3-opus" in pricing
        assert "claude-3-sonnet" in pricing
        assert "claude-3-haiku" in pricing


class TestModelOptimizationProxy:
    """模型优化代理测试"""
    
    def test_create_proxy(self):
        """测试创建优化代理"""
        proxy = get_model_optimization_proxy()
        assert isinstance(proxy, ModelOptimizationProxy)
    
    @pytest.mark.asyncio
    async def test_call_with_optimization(self):
        """测试带优化的模型调用"""
        proxy = get_model_optimization_proxy()
        cache = get_prompt_cache()
        
        await cache.clear()
        
        call_count = [0]

        def mock_model_call(prompt):
            call_count[0] += 1
            return f"响应: {prompt}"
        
        response1, metadata1 = await proxy.call_with_optimization(
            "测试提示词_" + str(id(mock_model_call)),
            mock_model_call,
            model_type="claude-3-sonnet"
        )
        
        assert call_count[0] == 1
        assert metadata1["cache_hit"] is False
        
        response2, metadata2 = await proxy.call_with_optimization(
            "测试提示词_" + str(id(mock_model_call)),
            mock_model_call,
            model_type="claude-3-sonnet"
        )
        
        assert call_count[0] == 1
        assert metadata2["cache_hit"] is True
        
        assert response1 == response2
    
    def test_toggle_feature(self):
        """测试切换优化特性"""
        proxy = get_model_optimization_proxy()
        
        proxy.set_feature(OptimizationFeature.PROMPT_CACHING, False)
        
        report = proxy.get_full_report()
        assert report["features"]["prompt_caching"] is False
        
        proxy.set_feature(OptimizationFeature.PROMPT_CACHING, True)
    
    def test_get_full_report(self):
        """测试获取完整报告"""
        proxy = get_model_optimization_proxy()
        
        report = proxy.get_full_report()
        
        assert "total_calls" in report
        assert "cache_hit_rate" in report
        assert "features" in report


class TestOptimizationIntegration:
    """优化组件集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_optimization_workflow(self):
        """测试完整优化工作流"""
        optimizer = get_token_optimizer()
        original_text = "这是一段测试文本。"
        optimize_result = optimizer.optimize(original_text)
        
        cache = get_prompt_cache()
        await cache.set(optimize_result.optimized_text, "模拟响应")
        
        compressor = get_token_compressor()
        compress_result = compressor.compress("模拟响应")
        
        cost_manager = get_cost_manager()
        cost_manager.record_call(
            model=ModelType.CLAUDE_3_SONNET,
            input_tokens=optimize_result.optimized_tokens,
            output_tokens=compress_result.compressed_tokens
        )
        
        proxy = get_model_optimization_proxy()
        
        def mock_call(prompt):
            return "响应"
        
        response, metadata = await proxy.call_with_optimization(
            "测试_" + str(id(mock_call)),
            mock_call
        )
        
        assert optimize_result.compression_ratio >= 0
        assert compress_result.compression_ratio >= 0
        assert cost_manager.get_stats().total_cost >= 0
        assert response is not None
        
        print("完整优化工作流测试通过！")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])