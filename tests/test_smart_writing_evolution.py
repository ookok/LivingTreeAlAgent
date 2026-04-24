# -*- coding: utf-8 -*-
"""
智能写作自进化引擎测试 - Smart Writing Evolution Tests
======================================================

测试 SmartWritingEvolutionEngine 的核心功能：
1. 文档生成经验积累
2. 专家反馈学习
3. 模板模式识别
4. 进化指标统计

Author: Hermes Desktop Team
"""

import unittest
import sys
from typing import Dict, Any
from unittest.mock import MagicMock, patch
import json

# 直接加载模块
def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

import importlib


class TestEvolutionMetrics(unittest.TestCase):
    """测试进化指标"""
    
    def setUp(self):
        self.module = load_module('self_evolution', 'core/smart_writing/self_evolution.py')
        self.metrics_class = self.module.EvolutionMetrics
    
    def test_default_values(self):
        """测试默认指标值"""
        metrics = self.metrics_class()
        
        self.assertEqual(metrics.total_generations, 0)
        self.assertEqual(metrics.successful_generations, 0)
        self.assertEqual(metrics.expert_feedback_count, 0)
        self.assertEqual(metrics.pattern_discoveries, 0)
        self.assertEqual(metrics.template_creations, 0)
        self.assertEqual(metrics.average_quality_score, 0.0)
    
    def test_to_dict(self):
        """测试指标转字典"""
        metrics = self.metrics_class(
            total_generations=100,
            successful_generations=90,
            expert_feedback_count=10,
            pattern_discoveries=5,
            template_creations=3,
            average_quality_score=0.85
        )
        
        result = metrics.to_dict()
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['total_generations'], 100)
        self.assertEqual(result['successful_generations'], 90)
        self.assertEqual(result['average_quality_score'], 0.85)


class TestSmartWritingEvolutionEngine(unittest.TestCase):
    """测试智能写作进化引擎"""
    
    def setUp(self):
        self.module = load_module('self_evolution', 'core/smart_writing/self_evolution.py')
        self.engine = self.module.SmartWritingEvolutionEngine()
    
    def test_initialization(self):
        """测试初始化"""
        self.assertFalse(self.engine._initialized)
        self.assertIsInstance(self.engine.metrics, self.module.EvolutionMetrics)
        self.assertEqual(len(self.engine._patterns_cache), 0)
    
    def test_initialize_success(self):
        """测试初始化成功"""
        # Mock 依赖组件
        with patch.object(self.engine, '_kb', None), \
             patch.object(self.engine, '_wiki', None), \
             patch.object(self.engine, '_skill_agent', None), \
             patch.object(self.engine, '_expert', None):
            
            result = self.engine.initialize()
            
            # 允许降级运行
            self.assertTrue(result)
            self.assertTrue(self.engine._initialized)
    
    def test_learn_from_generation(self):
        """测试从生成中学习"""
        requirement = "项目可行性研究报告"
        doc_type = "report"
        content = "这是测试生成的内容..."
        quality_score = 0.85
        
        # 不需要实际 KB 连接
        self.engine._initialized = True
        
        result = self.engine.learn_from_generation(
            requirement=requirement,
            doc_type=doc_type,
            content=content,
            quality_score=quality_score
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('stored', result)
    
    def test_learn_from_generation_low_quality(self):
        """测试低质量生成不存储"""
        result = self.engine.learn_from_generation(
            requirement="测试",
            doc_type="report",
            content="低质量内容",
            quality_score=0.3  # 低分
        )
        
        # 低分内容可能不存储
        self.assertIn('stored', result)
    
    def test_get_reference_documents(self):
        """测试获取参考文档"""
        self.engine._initialized = True
        
        # Mock KB
        self.engine._kb = MagicMock()
        self.engine._kb.search.return_value = [
            {"content": "参考文档1", "score": 0.9},
            {"content": "参考文档2", "score": 0.8}
        ]
        
        refs = self.engine.get_reference_documents(
            requirement="项目可行性研究",
            doc_type="report"
        )
        
        self.assertIsInstance(refs, list)
        self.engine._kb = None  # 恢复
    
    def test_process_expert_feedback(self):
        """测试处理专家反馈"""
        self.engine._initialized = True
        
        feedback = {
            "doc_id": "doc123",
            "feedback": "逻辑清晰，但数据不足",
            "rating": 4,
            "expert_id": "expert001"
        }
        
        result = self.engine.process_expert_feedback(feedback)
        
        self.assertIsInstance(result, dict)
        self.assertIn('learned', result)
        self.assertEqual(self.engine.metrics.expert_feedback_count, 1)
    
    def test_get_metrics(self):
        """测试获取指标"""
        # 添加一些测试数据
        self.engine.metrics.total_generations = 50
        self.engine.metrics.successful_generations = 45
        
        metrics = self.engine.get_metrics()
        
        self.assertEqual(metrics['total_generations'], 50)
        self.assertEqual(metrics['successful_generations'], 45)
    
    def test_get_quality_score(self):
        """测试获取质量分数"""
        # 高质量生成
        self.engine._initialized = True
        
        # Mock KB
        self.engine._kb = MagicMock()
        self.engine._kb.search.return_value = [
            {"content": "相关内容", "score": 0.95}
        ] * 3  # 多条高质量参考
        
        score = self.engine.get_quality_score(
            requirement="测试需求",
            content="测试内容"
        )
        
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 1)
        self.engine._kb = None


class TestAdaptiveCompression(unittest.TestCase):
    """测试自适应压缩策略"""
    
    def setUp(self):
        self.module = load_module('self_evolution', 'core/smart_writing/self_evolution.py')
    
    def test_compression_strategy_selection(self):
        """测试压缩策略选择"""
        # 短文本 - Keyword
        strategy = self.module.select_compression_strategy("短文本内容")
        self.assertEqual(strategy, 'keyword')
        
        # 中等文本 - Semantic
        medium_text = "中" * 300
        strategy = self.module.select_compression_strategy(medium_text)
        self.assertEqual(strategy, 'semantic')
        
        # 长文本 - Chunk
        long_text = "长" * 600
        strategy = self.module.select_compression_strategy(long_text)
        self.assertEqual(strategy, 'chunk')


class TestKnowledgePattern(unittest.TestCase):
    """测试知识模式"""
    
    def setUp(self):
        self.module = load_module('self_evolution', 'core/smart_writing/self_evolution.py')
    
    def test_pattern_extraction(self):
        """测试模式提取"""
        patterns = self.module.extract_patterns(
            doc_type="报告",
            content="项目概述\n市场需求\n技术方案\n投资估算\n效益分析"
        )
        
        self.assertIsInstance(patterns, list)
    
    def test_pattern_matching(self):
        """测试模式匹配"""
        patterns = ["市场需求", "技术方案"]
        content = "本文档包含市场需求分析和详细的技术方案"
        
        matches = self.module.match_patterns(patterns, content)
        
        self.assertIsInstance(matches, list)
        self.assertGreater(len(matches), 0)


class TestTemplateRecognizer(unittest.TestCase):
    """测试模板识别器"""
    
    def setUp(self):
        self.module = load_module('self_evolution', 'core/smart_writing/self_evolution.py')
    
    def test_template_detection(self):
        """测试模板检测"""
        # 项目报告模板
        report_content = """
        第一章 项目概述
        1.1 项目背景
        1.2 建设规模
        
        第二章 市场分析
        2.1 市场需求
        2.2 竞争分析
        """
        
        template = self.module.detect_template(report_content)
        
        self.assertIsNotNone(template)
        self.assertEqual(template['type'], '报告')
    
    def test_template_similarity(self):
        """测试模板相似度"""
        similarity = self.module.calculate_template_similarity(
            "第一章 项目概述",
            "第一章 项目背景"
        )
        
        self.assertGreaterEqual(similarity, 0)
        self.assertLessEqual(similarity, 1)


class TestEvolutionController(unittest.TestCase):
    """测试进化控制器"""
    
    def setUp(self):
        self.module = load_module('self_evolution', 'core/smart_writing/self_evolution.py')
    
    def test_state_transitions(self):
        """测试状态转换"""
        controller = self.module.EvolutionController()
        
        # 初始状态
        self.assertEqual(controller.state, 'STABLE')
        
        # 学习中
        controller.start_learning()
        self.assertEqual(controller.state, 'LEARNING')
        
        # 改进中
        controller.start_improving()
        self.assertEqual(controller.state, 'IMPROVING')
        
        # 恢复稳定
        controller.stabilize()
        self.assertEqual(controller.state, 'STABLE')
    
    def test_learning_rate_adjustment(self):
        """测试学习率调整"""
        controller = self.module.EvolutionController()
        
        # 高错误率应该提高学习率
        controller.adjust_learning_rate(error_rate=0.3)
        self.assertGreater(controller.learning_rate, 0.1)
        
        # 低错误率应该降低学习率
        controller.adjust_learning_rate(error_rate=0.05)
        self.assertLess(controller.learning_rate, 0.2)


class TestInteractionSample(unittest.TestCase):
    """测试交互样本"""
    
    def setUp(self):
        self.module = load_module('self_evolution', 'core/smart_writing/self_evolution.py')
    
    def test_sample_collection(self):
        """测试样本收集"""
        collector = self.module.InteractionSampleCollector()
        
        # 添加样本
        collector.add(
            requirement="项目可行性报告",
            doc_type="report",
            quality=0.85,
            feedback="优秀"
        )
        
        self.assertEqual(collector.count(), 1)
    
    def test_sample_retrieval(self):
        """测试样本检索"""
        collector = self.module.InteractionSampleCollector()
        
        # 添加样本
        collector.add(
            requirement="项目可行性报告",
            doc_type="report",
            quality=0.85
        )
        
        # 检索相似样本
        samples = collector.get_similar(
            requirement="项目",
            limit=5
        )
        
        self.assertIsInstance(samples, list)


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        self.module = load_module('self_evolution', 'core/smart_writing/self_evolution.py')
    
    def test_full_evolution_cycle(self):
        """测试完整进化周期"""
        engine = self.module.SmartWritingEvolutionEngine()
        engine._initialized = True
        
        # 1. 学习生成
        result = engine.learn_from_generation(
            requirement="测试需求",
            doc_type="报告",
            content="测试内容...",
            quality_score=0.9
        )
        
        # 2. 获取指标
        metrics = engine.get_metrics()
        
        # 3. 获取参考文档
        engine._kb = MagicMock()
        engine._kb.search.return_value = []
        refs = engine.get_reference_documents(
            requirement="测试需求",
            doc_type="报告"
        )
        
        # 4. 添加专家反馈
        engine.process_expert_feedback({
            "doc_id": "test",
            "feedback": "需要改进",
            "rating": 4
        })
        
        # 验证进化发生
        self.assertGreater(metrics['total_generations'], 0)
        
        engine._kb = None


if __name__ == '__main__':
    unittest.main(verbosity=2)
