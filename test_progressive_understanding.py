# -*- coding: utf-8 -*-
"""
Phase 4: 渐进式理解测试
========================

测试渐进式理解器的核心功能：
1. 会话管理
2. 进度追踪
3. 知识积累
4. 渐进式理解流程
5. 便捷函数
"""

import unittest
import time
from typing import List, Dict, Any

# 测试目标导入
try:
    import sys
    sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent')
    
    from client.src.business.long_context.progressive_understanding_impl import (
        ProgressiveUnderstanding,
        UnderstandingConfig,
        UnderstandingDepth,
        ComprehensionPhase,
        ComprehensionState,
        KnowledgeAccumulator,
        KnowledgeItem,
        ProgressTracker,
        SessionManager,
        UnderstandingContext,
        create_progressive_understander,
        quick_understand,
    )
    IMPORTS_OK = True
except ImportError as e:
    IMPORTS_OK = False
    print(f"导入失败: {e}")


class TestProgressiveUnderstanding(unittest.TestCase):
    """渐进式理解测试"""
    
    @classmethod
    def setUpClass(cls):
        """测试准备"""
        cls.test_text = """
        人工智能（AI）是计算机科学的一个分支，致力于开发能够执行通常需要人类智能的任务的系统。
        
        主要研究方向包括：
        1. 机器学习 - 让计算机从数据中学习
        2. 深度学习 - 使用神经网络进行复杂模式识别
        3. 自然语言处理 - 理解和生成人类语言
        4. 计算机视觉 - 理解和分析图像视频
        
        机器学习又分为监督学习、无监督学习和强化学习三大类。
        
        深度学习是机器学习的一个分支，使用多层神经网络来学习数据的层次化表示。
        典型的应用包括图像识别、语音识别和自然语言处理。
        """
        
        cls.test_task = "分析AI的主要研究方向和技术分类"
    
    def test_01_progress_tracker(self):
        """测试进度追踪器"""
        print("\n" + "="*60)
        print("测试 1: ProgressTracker 进度追踪器")
        print("="*60)
        
        tracker = ProgressTracker(total_phases=3, max_iterations=3)
        
        # 模拟进度更新
        tracker.update_phase("compression", 0.5, "压缩进行中")
        tracker.update_phase("chunking", 0.3, "分块进行中")
        tracker.update_iteration(1, 0.5)
        
        progress = tracker.get_progress_snapshot()
        
        print(f"  总进度: {progress.overall_progress:.0%}")
        print(f"  压缩进度: {progress.compression_progress:.0%}")
        print(f"  分块进度: {progress.chunking_progress:.0%}")
        print(f"  分析进度: {progress.analysis_progress:.0%}")
        print(f"  当前步骤: {progress.current_step}")
        print(f"  洞察: {progress.insights}")
        
        self.assertGreater(progress.overall_progress, 0)
        self.assertEqual(progress.current_iteration, 1)
        
        print("[PASS] ProgressTracker 测试通过")
    
    def test_02_knowledge_accumulator(self):
        """测试知识积累器"""
        print("\n" + "="*60)
        print("测试 2: KnowledgeAccumulator 知识积累器")
        print("="*60)
        
        accumulator = KnowledgeAccumulator(max_items=20)
        
        # 添加知识
        item1 = accumulator.add(
            content="机器学习是AI的核心技术",
            category="concept",
            confidence=0.9
        )
        
        item2 = accumulator.add(
            content="深度学习使用神经网络",
            category="concept",
            confidence=0.85,
            tags={"深度学习", "神经网络"}
        )
        
        item3 = accumulator.add(
            content="深度学习是机器学习的分支",
            category="relationship",
            confidence=0.8
        )
        
        print(f"  添加的知识条目: {len(accumulator.items)}")
        
        # 测试相似合并
        item4 = accumulator.add(
            content="机器学习是AI的核心技术之一",
            category="concept",
            confidence=0.95
        )
        
        # 验证相似合并
        stats = accumulator.get_statistics()
        print(f"  统计: {stats}")
        
        # 知识图谱
        graph = accumulator.get_knowledge_graph()
        print(f"  知识图谱: {graph}")
        
        # 验证
        self.assertLessEqual(len(accumulator.items), 20)
        self.assertIn("concept", stats["by_category"])
        
        print("[PASS] KnowledgeAccumulator 测试通过")
    
    def test_03_session_manager(self):
        """测试会话管理器"""
        print("\n" + "="*60)
        print("测试 3: SessionManager 会话管理器")
        print("="*60)
        
        manager = SessionManager(max_sessions=10, ttl_seconds=60)
        
        # 创建会话
        config = UnderstandingConfig()
        session1 = manager.create_session(config)
        
        print(f"  创建会话: {session1.session_id}")
        self.assertIsNotNone(session1.session_id)
        
        # 获取会话
        retrieved = manager.get_session(session1.session_id)
        self.assertEqual(retrieved.session_id, session1.session_id)
        
        # 创建多个会话
        for i in range(3):
            session = manager.create_session(config)
            print(f"  创建会话 {i+1}: {session.session_id}")
        
        # 活跃会话
        active = manager.get_active_sessions()
        print(f"  活跃会话数: {len(active)}")
        
        # 关闭会话
        manager.close_session(session1.session_id)
        active = manager.get_active_sessions()
        print(f"  关闭后活跃会话数: {len(active)}")
        
        self.assertEqual(len(active), 3)
        
        print("[PASS] SessionManager 测试通过")
    
    def test_04_understanding_context(self):
        """测试理解上下文"""
        print("\n" + "="*60)
        print("测试 4: UnderstandingContext 理解上下文")
        print("="*60)
        
        context = UnderstandingContext(session_id="test-001")
        
        # 添加知识
        item = KnowledgeItem(
            id="k1",
            content="测试知识",
            category="concept",
            confidence=0.9
        )
        context.add_knowledge(item)
        
        # 合并发现
        new_findings = ["发现1", "发现2", "发现3"]
        added = context.merge_findings(new_findings)
        print(f"  首次合并新增: {added} 条")
        
        added = context.merge_findings(["发现2", "发现4"])
        print(f"  第二次合并新增: {added} 条")
        
        # 按类别获取
        concepts = context.get_knowledge_by_category("concept")
        print(f"  概念类别: {len(concepts)} 条")
        
        # 添加文本历史
        context.text_history.append("测试文本1")
        context.text_history.append("测试文本2")
        print(f"  文本历史: {len(context.text_history)} 条")
        
        self.assertEqual(len(context.knowledge_base), 1)
        self.assertEqual(len(context.converged_findings), 4)
        
        print("[PASS] UnderstandingContext 测试通过")
    
    def test_05_progressive_understander_basic(self):
        """测试渐进式理解器基础功能"""
        print("\n" + "="*60)
        print("测试 5: ProgressiveUnderstanding 基础功能")
        print("="*60)
        
        # 创建理解器
        config = UnderstandingConfig(
            depth=UnderstandingDepth.QUICK,
            use_compression=True,
            use_layered=False,
            use_multi_agent=False,
            max_iterations=1
        )
        
        understander = ProgressiveUnderstanding(config)
        
        # 执行理解
        result = understander.understand(
            text=self.test_text,
            task=self.test_task
        )
        
        print(f"  会话ID: {result.session_id}")
        print(f"  执行时间: {result.execution_time:.3f}s")
        print(f"  总进度: {result.progress.overall_progress:.0%}")
        print(f"  理解结果: {result.primary_understanding[:50] if result.primary_understanding else 'N/A'}...")
        print(f"  关键洞察: {len(result.key_insights)} 条")
        print(f"  置信度: {result.confidence:.2f}")
        
        # 验证
        self.assertIsNotNone(result.session_id)
        self.assertGreater(result.execution_time, 0)
        
        print("[PASS] ProgressiveUnderstanding 基础功能测试通过")
    
    def test_06_progressive_understander_full(self):
        """测试渐进式理解器完整功能"""
        print("\n" + "="*60)
        print("测试 6: ProgressiveUnderstanding 完整功能")
        print("="*60)
        
        # 完整配置
        config = UnderstandingConfig(
            depth=UnderstandingDepth.STANDARD,
            use_compression=True,
            use_layered=True,
            use_multi_agent=True,
            max_iterations=2,
            convergence_threshold=0.8
        )
        
        understander = ProgressiveUnderstanding(config)
        
        # 首次理解
        result1 = understander.understand(
            text=self.test_text,
            task=self.test_task
        )
        
        print(f"  [第一轮]")
        print(f"    会话ID: {result1.session_id}")
        print(f"    执行时间: {result1.execution_time:.3f}s")
        print(f"    理解: {result1.primary_understanding[:50] if result1.primary_understanding else 'N/A'}...")
        print(f"    洞察数: {len(result1.key_insights)}")
        print(f"    新知识: {len(result1.new_knowledge)} 条")
        print(f"    收敛度: {result1.convergence_score:.2f}")
        
        # 第二轮理解（使用同一会话）
        follow_up_text = """
        除了上述方向，AI还有以下重要应用：
        - 自动驾驶
        - 医疗诊断
        - 金融风控
        - 智能客服
        """
        
        result2 = understander.understand(
            text=follow_up_text,
            task="AI有哪些重要应用场景",
            session_id=result1.session_id,
            previous_findings=result1.key_insights
        )
        
        print(f"  [第二轮]")
        print(f"    执行时间: {result2.execution_time:.3f}s")
        print(f"    洞察数: {len(result2.key_insights)}")
        print(f"    新知识: {len(result2.new_knowledge)} 条")
        print(f"    收敛度: {result2.convergence_score:.2f}")
        print(f"    已收敛: {result2.converged}")
        
        # 会话状态
        status = understander.get_session_status(result1.session_id)
        if status:
            print(f"  [会话状态]")
            print(f"    进度: {status['progress']:.0%}")
            print(f"    知识数: {status['knowledge_count']}")
            print(f"    发现数: {status['findings_count']}")
        
        # 验证
        self.assertIsNotNone(result2.session_id)
        self.assertEqual(result2.session_id, result1.session_id)
        
        # 清理
        understander.close_session(result1.session_id)
        
        print("[PASS] ProgressiveUnderstanding 完整功能测试通过")
    
    def test_07_depth_variants(self):
        """测试不同深度级别"""
        print("\n" + "="*60)
        print("测试 7: 不同深度级别")
        print("="*60)
        
        for depth in [UnderstandingDepth.QUICK, UnderstandingDepth.STANDARD]:
            config = UnderstandingConfig(
                depth=depth,
                use_compression=True,
                use_layered=False,
                use_multi_agent=False
            )
            
            understander = ProgressiveUnderstanding(config)
            result = understander.understand(self.test_text, self.test_task)
            
            print(f"  {depth.value}: {result.execution_time:.3f}s, {result.progress.overall_progress:.0%}")
            
            understander.close_session(result.session_id)
        
        print("[PASS] 不同深度级别测试通过")
    
    def test_08_convenience_functions(self):
        """测试便捷函数"""
        print("\n" + "="*60)
        print("测试 8: 便捷函数")
        print("="*60)
        
        # 创建理解器
        understander = create_progressive_understander(
            depth="standard",
            use_compression=True,
            use_layered=True,
            use_multi_agent=False
        )
        
        print(f"  理解器创建成功")
        
        # 快速理解
        result = quick_understand(
            text=self.test_text,
            task=self.test_task,
            depth="standard"
        )
        
        print(f"  session_id: {result['session_id']}")
        print(f"  理解: {result['understanding'][:50] if result['understanding'] else 'N/A'}...")
        print(f"  洞察数: {len(result['insights'])}")
        print(f"  置信度: {result['confidence']:.2f}")
        print(f"  执行时间: {result['execution_time']:.3f}s")
        
        self.assertIn("session_id", result)
        self.assertIn("understanding", result)
        
        print("[PASS] 便捷函数测试通过")
    
    def test_09_knowledge_graph(self):
        """测试知识图谱"""
        print("\n" + "="*60)
        print("测试 9: 知识图谱")
        print("="*60)
        
        understander = ProgressiveUnderstanding()
        
        # 执行理解
        result = understander.understand(self.test_text, self.test_task)
        
        # 获取知识图谱
        graph = understander.get_knowledge_graph(result.session_id)
        print(f"  知识图谱: {graph}")
        
        # 全局知识图谱
        global_graph = understander.get_knowledge_graph()
        print(f"  全局图谱: {global_graph}")
        
        print("[PASS] 知识图谱测试通过")
    
    def test_10_performance(self):
        """性能测试"""
        print("\n" + "="*60)
        print("测试 10: 性能测试")
        print("="*60)
        
        config = UnderstandingConfig(
            depth=UnderstandingDepth.QUICK,
            use_compression=True,
            use_layered=False,
            use_multi_agent=False
        )
        
        understander = ProgressiveUnderstanding(config)
        
        start = time.time()
        
        # 多次执行
        for i in range(5):
            result = understander.understand(self.test_text, f"任务{i}")
            understander.close_session(result.session_id)
        
        elapsed = time.time() - start
        avg_time = elapsed / 5
        
        print(f"  总时间: {elapsed:.3f}s")
        print(f"  平均时间: {avg_time:.3f}s")
        print(f"  QPS: {5/elapsed:.1f}")
        
        # 验证性能
        self.assertLess(avg_time, 2.0, "平均时间应小于2秒")
        
        print("[PASS] 性能测试通过")


def run_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print(" Phase 4: 渐进式理解测试套件")
    print("="*70)
    
    if not IMPORTS_OK:
        print("\n[SKIP] 导入失败，跳过测试")
        return False
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestProgressiveUnderstanding)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 总结
    print("\n" + "="*70)
    print(" 测试总结")
    print("="*70)
    
    if result.wasSuccessful():
        print(f"\n[OK] 所有测试通过! ({result.testsRun} 个测试)")
    else:
        print(f"\n[FAIL] 有 {len(result.failures) + len(result.errors)} 个测试失败")
        
        if result.failures:
            print("\n失败:")
            for test, trace in result.failures:
                print(f"  {test}")
        
        if result.errors:
            print("\n错误:")
            for test, trace in result.errors:
                print(f"  {test}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
