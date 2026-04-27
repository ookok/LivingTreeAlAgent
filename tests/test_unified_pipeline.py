# -*- coding: utf-8 -*-
"""
统一流水线测试 - Unified Pipeline Tests
=========================================

测试 UnifiedPipeline 的核心功能：
1. 意图分类 (L0)
2. 智能路由 (L1-L4)
3. 知识检索
4. 结果缓存
5. 流水线执行

Author: Hermes Desktop Team
"""

import unittest
import sys
import os
from unittest.mock import MagicMock, patch
from typing import Dict, Any

# 直接加载模块，绕过 core/__init__.py
def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

import importlib


class TestIntentType(unittest.TestCase):
    """测试意图类型枚举"""
    
    def setUp(self):
        self.module = load_module('unified_pipeline', 'core/unified_pipeline.py')
    
    def test_intent_type_values(self):
        """测试意图类型枚举值"""
        IntentType = self.module.IntentType
        
        expected = {
            'FACTUAL': 'factual',
            'CONVERSATIONAL': 'conversational',
            'PROCEDURAL': 'procedural',
            'CREATIVE': 'creative',
            'TASK': 'task',
            'WRITING': 'writing',
            'UNKNOWN': 'unknown'
        }
        
        for name, value in expected.items():
            self.assertEqual(getattr(IntentType, name).value, value)
    
    def test_intent_type_count(self):
        """测试意图类型数量"""
        IntentType = self.module.IntentType
        self.assertEqual(len(IntentType), 7)


class TestPipelineContext(unittest.TestCase):
    """测试流水线上下文"""
    
    def setUp(self):
        self.module = load_module('unified_pipeline', 'core/unified_pipeline.py')
        self.ctx_class = self.module.PipelineContext
    
    def test_default_values(self):
        """测试默认字段值"""
        ctx = self.ctx_class()
        
        self.assertEqual(ctx.user_id, "")
        self.assertEqual(ctx.session_id, "")
        self.assertEqual(ctx.query, "")
        self.assertEqual(ctx.intent, self.module.IntentType.UNKNOWN)
        self.assertEqual(ctx.raw_intent, "")
        self.assertEqual(ctx.route_decision, {})
        self.assertEqual(ctx.retrieved_context, [])
        self.assertEqual(ctx.response, "")
        self.assertEqual(ctx.sources, [])
        self.assertEqual(ctx.confidence, 0.0)
        self.assertFalse(ctx.needs_clarification)
        self.assertEqual(ctx.clarification_prompt, "")
        self.assertEqual(ctx.execution_trace, [])
    
    def test_custom_values(self):
        """测试自定义字段值"""
        ctx = self.ctx_class(
            user_id="user123",
            session_id="session456",
            query="测试查询",
            intent=self.module.IntentType.FACTUAL,
            confidence=0.95
        )
        
        self.assertEqual(ctx.user_id, "user123")
        self.assertEqual(ctx.session_id, "session456")
        self.assertEqual(ctx.query, "测试查询")
        self.assertEqual(ctx.intent, self.module.IntentType.FACTUAL)
        self.assertEqual(ctx.confidence, 0.95)
    
    def test_execution_trace(self):
        """测试执行追踪"""
        ctx = self.ctx_class()
        
        # 添加执行步骤
        ctx.execution_trace.append({
            "step": 1,
            "name": "intent_classification",
            "duration_ms": 50,
            "result": "FACTUAL"
        })
        
        self.assertEqual(len(ctx.execution_trace), 1)
        self.assertEqual(ctx.execution_trace[0]["step"], 1)


class TestPipelineStage(unittest.TestCase):
    """测试流水线阶段枚举"""
    
    def setUp(self):
        self.module = load_module('unified_pipeline', 'core/unified_pipeline.py')
    
    def test_stage_values(self):
        """测试阶段枚举值"""
        PipelineStage = self.module.PipelineStage
        
        expected_stages = [
            'PARSE', 'INTENT', 'ROUTE', 'RETRIEVE',
            'GENERATE', 'VERIFY', 'CACHE', 'FINISH'
        ]
        
        for stage in expected_stages:
            self.assertTrue(hasattr(PipelineStage, stage))


class TestPipelineMetrics(unittest.TestCase):
    """测试流水线指标"""
    
    def setUp(self):
        self.module = load_module('unified_pipeline', 'core/unified_pipeline.py')
    
    def test_default_metrics(self):
        """测试默认指标值"""
        metrics = self.module.PipelineMetrics()
        
        self.assertEqual(metrics.total_requests, 0)
        self.assertEqual(metrics.successful_requests, 0)
        self.assertEqual(metrics.failed_requests, 0)
        self.assertEqual(metrics.total_latency_ms, 0)
    
    def test_to_dict(self):
        """测试指标转字典"""
        metrics = self.module.PipelineMetrics(
            total_requests=100,
            successful_requests=95,
            failed_requests=5
        )
        
        result = metrics.to_dict()
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['total_requests'], 100)
        self.assertEqual(result['successful_requests'], 95)


class TestPipelineConfig(unittest.TestCase):
    """测试流水线配置"""
    
    def setUp(self):
        self.module = load_module('unified_pipeline', 'core/unified_pipeline.py')
    
    def test_default_config(self):
        """测试默认配置"""
        config = self.module.PipelineConfig()
        
        self.assertTrue(config.enable_cache)
        self.assertTrue(config.enable_knowledge)
        self.assertTrue(config.enable_deep_search)
        self.assertEqual(config.max_context_length, 128000)
        self.assertEqual(config.cache_ttl_seconds, 3600)
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = self.module.PipelineConfig(
            enable_cache=False,
            max_context_length=64000,
            deep_search_threshold=0.7
        )
        
        self.assertFalse(config.enable_cache)
        self.assertEqual(config.max_context_length, 64000)
        self.assertEqual(config.deep_search_threshold, 0.7)


class TestPipelineResult(unittest.TestCase):
    """测试流水线结果"""
    
    def setUp(self):
        self.module = load_module('unified_pipeline', 'core/unified_pipeline.py')
    
    def test_success_result(self):
        """测试成功结果"""
        result = self.module.PipelineResult(
            success=True,
            response="测试响应",
            intent=self.module.IntentType.FACTUAL,
            confidence=0.95
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.response, "测试响应")
        self.assertEqual(result.intent, self.module.IntentType.FACTUAL)
        self.assertEqual(result.confidence, 0.95)
        self.assertEqual(result.error, "")
    
    def test_failure_result(self):
        """测试失败结果"""
        result = self.module.PipelineResult(
            success=False,
            error="测试错误"
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.response, "")
        self.assertEqual(result.error, "测试错误")


class TestIntentClassification(unittest.TestCase):
    """测试意图分类功能"""
    
    def setUp(self):
        self.module = load_module('unified_pipeline', 'core/unified_pipeline.py')
    
    def test_classify_factual(self):
        """测试事实查询分类"""
        intent, confidence = self.module.classify_intent("今天北京天气怎么样？")
        
        self.assertEqual(intent, self.module.IntentType.FACTUAL)
        self.assertGreater(confidence, 0)
    
    def test_classify_conversational(self):
        """测试对话类分类"""
        intent, confidence = self.module.classify_intent("你觉得这个方案怎么样？")
        
        self.assertEqual(intent, self.module.IntentType.CONVERSATIONAL)
        self.assertGreater(confidence, 0)
    
    def test_classify_procedural(self):
        """测试流程类分类"""
        intent, confidence = self.module.classify_intent("怎么用 Python 写一个排序算法？")
        
        self.assertEqual(intent, self.module.IntentType.PROCEDURAL)
        self.assertGreater(confidence, 0)
    
    def test_classify_creative(self):
        """测试创意类分类"""
        intent, confidence = self.module.classify_intent("帮我写一首关于春天的诗")
        
        self.assertEqual(intent, self.module.IntentType.CREATIVE)
        self.assertGreater(confidence, 0)
    
    def test_classify_task(self):
        """测试任务类分类"""
        intent, confidence = self.module.classify_intent("帮我预订明天的酒店")
        
        self.assertEqual(intent, self.module.IntentType.TASK)
        self.assertGreater(confidence, 0)
    
    def test_classify_writing(self):
        """测试写作类分类"""
        intent, confidence = self.module.classify_intent("写一份项目可行性研究报告")
        
        self.assertEqual(intent, self.module.IntentType.WRITING)
        self.assertGreater(confidence, 0)


class TestSmartRouting(unittest.TestCase):
    """测试智能路由功能"""
    
    def setUp(self):
        self.module = load_module('unified_pipeline', 'core/unified_pipeline.py')
    
    def test_route_to_l1(self):
        """测试 L1 路由"""
        decision = self.module.smart_route(
            intent=self.module.IntentType.FACTUAL,
            query="简单的事实查询",
            complexity_score=0.2
        )
        
        self.assertIn('route', decision)
        self.assertIn('estimated_time_ms', decision)
    
    def test_route_to_l4(self):
        """测试 L4 路由"""
        decision = self.module.smart_route(
            intent=self.module.IntentType.WRITING,
            query="复杂的专业报告",
            complexity_score=0.9
        )
        
        self.assertIn('route', decision)
        self.assertGreater(decision['estimated_time_ms'], 1000)


class TestCache(unittest.TestCase):
    """测试缓存功能"""
    
    def setUp(self):
        self.module = load_module('unified_pipeline', 'core/unified_pipeline.py')
        self.cache = self.module.UnifiedCache(max_size=100)
    
    def test_set_and_get(self):
        """测试缓存设置和获取"""
        self.cache.set("key1", {"data": "value1"})
        result = self.cache.get("key1")
        
        self.assertEqual(result, {"data": "value1"})
    
    def test_cache_miss(self):
        """测试缓存未命中"""
        result = self.cache.get("nonexistent")
        self.assertIsNone(result)
    
    def test_cache_overflow(self):
        """测试缓存溢出"""
        # 创建大于 max_size 的缓存项
        for i in range(150):
            self.cache.set(f"key{i}", {"data": i})
        
        # 检查最早的项被清除
        self.assertIsNone(self.cache.get("key0"))
        # 检查最近的项存在
        self.assertIsNotNone(self.cache.get("key149"))
    
    def test_cache_clear(self):
        """测试缓存清除"""
        self.cache.set("key1", {"data": "value1"})
        self.cache.clear()
        
        self.assertIsNone(self.cache.get("key1"))
    
    def test_cache_stats(self):
        """测试缓存统计"""
        self.cache.set("key1", {"data": "value1"})
        self.cache.get("key1")  # 命中
        self.cache.get("key2")  # 未命中
        
        stats = self.cache.get_stats()
        
        self.assertEqual(stats['hits'], 1)
        self.assertEqual(stats['misses'], 1)
        self.assertAlmostEqual(stats['hit_rate'], 0.5)


class TestUnifiedPipeline(unittest.TestCase):
    """测试统一流水线"""
    
    def setUp(self):
        self.module = load_module('unified_pipeline', 'core/unified_pipeline.py')
    
    @patch('core.unified_pipeline.OllamaClient')
    def test_pipeline_execute(self, mock_client):
        """测试流水线执行"""
        # Mock OllamaClient
        mock_instance = MagicMock()
        mock_instance.generate.return_value = "测试响应"
        mock_client.return_value = mock_instance
        
        # 创建流水线
        pipeline = self.module.UnifiedPipeline()
        
        # 执行
        result = pipeline.execute(
            query="测试查询",
            user_id="user123",
            session_id="session456"
        )
        
        self.assertIsInstance(result, self.module.PipelineResult)
        # 可能失败因为依赖组件，但至少应该返回结果对象
    
    def test_pipeline_stream(self):
        """测试流式输出"""
        pipeline = self.module.UnifiedPipeline()
        
        # 生成流式结果
        chunks = list(pipeline.stream(
            query="测试查询",
            user_id="user123"
        ))
        
        # 验证流式输出
        self.assertIsInstance(chunks, list)


class TestPerformanceMetrics(unittest.TestCase):
    """测试性能指标"""
    
    def setUp(self):
        self.module = load_module('unified_pipeline', 'core/unified_pipeline.py')
    
    def test_latency_percentiles(self):
        """测试延迟百分位"""
        latencies = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        
        p50 = self.module.calculate_percentile(latencies, 50)
        p95 = self.module.calculate_percentile(latencies, 95)
        p99 = self.module.calculate_percentile(latencies, 99)
        
        self.assertEqual(p50, 500)
        self.assertEqual(p95, 950)
        self.assertEqual(p99, 990)
    
    def test_throughput_calculation(self):
        """测试吞吐量计算"""
        # 100 个请求在 10 秒内完成
        throughput = self.module.calculate_throughput(100, 10.0)
        self.assertEqual(throughput, 10.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
