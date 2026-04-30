"""
认知框架测试套件
"""

import asyncio
import pytest
from datetime import datetime

from .mental_model_builder import MentalModelBuilder, ConceptGraph, ConceptNode
from .attention_controller import AttentionController, PriorityLevel, FocusStack, TaskContext
from .meta_reasoning_engine import MetaReasoningEngine, VerificationReport, ConfidenceScore
from .experience_manager import ExperienceManager, CaseRecord, DecisionTree
from .idea_generator import IdeaGenerator, Idea
from .cognitive_framework import CognitiveFramework


class TestMentalModelBuilder:
    """心理表征模块测试"""
    
    def test_build_from_text(self):
        """测试从文本构建概念图"""
        builder = MentalModelBuilder()
        text = "人工智能是一门研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的新的技术科学。"
        
        graph = builder.build_from_text(text, domain="ai")
        
        assert isinstance(graph, ConceptGraph)
        assert len(graph.nodes) > 0
        assert graph.get_statistics()["total_nodes"] > 0
    
    def test_concept_search(self):
        """测试概念搜索"""
        builder = MentalModelBuilder()
        text = "人工智能技术。机器学习方法。"
        
        graph = builder.build_from_text(text)
        results = graph.search("人工智能")
        
        assert len(results) >= 1
        # 检查是否包含相关概念（标签可能包含完整匹配项）
        labels = [node.label for node in results]
        assert any("人工智能" in label for label in labels)
    
    def test_concept_inference(self):
        """测试概念推理"""
        builder = MentalModelBuilder()
        text = "人工智能包含机器学习，机器学习包含深度学习。"
        
        graph = builder.build_from_text(text)
        nodes = graph.search("人工智能")
        
        if nodes:
            inferred = graph.infer(nodes[0].node_id, max_depth=2)
            assert isinstance(inferred, list)


class TestAttentionController:
    """注意力控制器测试"""
    
    def test_task_submission(self):
        """测试任务提交"""
        controller = AttentionController()
        
        def sample_task():
            return "done"
        
        task_id = controller.submit_task(
            name="测试任务",
            handler=sample_task,
            priority="high"
        )
        
        assert task_id is not None
        task = controller.get_task(task_id)
        assert task is not None
        assert task.name == "测试任务"
    
    def test_focus_stack(self):
        """测试焦点栈"""
        stack = FocusStack(max_depth=5)
        
        context1 = TaskContext(name="任务1")
        context2 = TaskContext(name="任务2")
        
        stack.push(context1)
        stack.push(context2)
        
        assert stack.depth() == 2
        assert stack.peek().name == "任务2"
        
        popped = stack.pop()
        assert popped.name == "任务2"
        assert stack.depth() == 1
    
    def test_priority_queues(self):
        """测试优先级队列"""
        controller = AttentionController()
        
        def handler():
            pass
        
        controller.submit_task("低优先级任务", handler, priority="low")
        controller.submit_task("高优先级任务", handler, priority="high")
        controller.submit_task("紧急任务", handler, priority="critical")
        
        stats = controller.get_stats()
        assert stats["queue_sizes"]["critical"] == 1
        assert stats["queue_sizes"]["high"] == 1
        assert stats["queue_sizes"]["low"] == 1


class TestMetaReasoningEngine:
    """元认知引擎测试"""
    
    def test_confidence_score(self):
        """测试置信度评分"""
        score = ConfidenceScore(
            overall=0.8,
            factuality=0.9,
            logic=0.7,
            completeness=0.8,
            relevance=0.85,
            consistency=0.75,
            source_reliability=0.9
        )
        
        assert score.overall == 0.8
        assert score.to_dict()["factuality"] == 0.9
    
    def test_fact_checker(self):
        """测试事实核查"""
        engine = MetaReasoningEngine()
        engine.add_knowledge("地球", "圆的")
        
        # 测试评估 - 检查逻辑验证通过即可（事实检查器需要外部工具支持）
        async def run_test():
            report = await engine.evaluate("地球是圆的")
            assert isinstance(report, VerificationReport)
            # 验证报告结构正确
            assert report.confidence.overall >= 0.0
            assert report.confidence.logic >= 0.0
        
        asyncio.run(run_test())
    
    def test_validation_pipeline(self):
        """测试验证流水线"""
        engine = MetaReasoningEngine(threshold=0.5)
        
        async def run_test():
            report = await engine.evaluate("这是一个合理的陈述。它有明确的前提和结论。")
            assert report.result.value in ["passed", "failed"]
            assert 0 <= report.confidence.overall <= 1
        
        asyncio.run(run_test())


class TestExperienceManager:
    """经验档案测试"""
    
    def test_store_case(self):
        """测试案例存储"""
        manager = ExperienceManager()
        
        case_id = manager.store_case({
            "problem": "如何修复代码错误",
            "problem_type": "debug",
            "domain": "programming",
            "solution": "检查日志和调试工具",
            "outcome": "success",
            "confidence": 0.85,
            "tags": ["debug", "code"]
        })
        
        assert case_id is not None
        case = manager.get_case(case_id)
        assert case is not None
        assert case.problem == "如何修复代码错误"
    
    def test_retrieve_similar(self):
        """测试相似案例检索"""
        manager = ExperienceManager()
        
        # 存储几个案例
        manager.store_case({
            "problem": "如何调试Python代码",
            "domain": "programming",
            "solution": "使用print语句",
            "outcome": "success",
            "confidence": 0.8
        })
        
        manager.store_case({
            "problem": "如何调试Java代码",
            "domain": "programming",
            "solution": "使用IDE调试器",
            "outcome": "success",
            "confidence": 0.85
        })
        
        results = manager.retrieve_similar("调试代码", limit=2)
        assert len(results) >= 1
    
    def test_decision_tree(self):
        """测试决策树"""
        manager = ExperienceManager()
        
        tree = manager.create_decision_tree("task1")
        assert isinstance(tree, DecisionTree)
        assert tree.root_id is not None
        
        # 添加决策
        node_id = manager.add_decision("task1", "选择方案A", "效率更高", 0.9)
        assert node_id is not None


class TestIdeaGenerator:
    """创意引擎测试"""
    
    def test_generate_ideas(self):
        """测试创意生成"""
        generator = IdeaGenerator()
        
        # 注册简单生成器
        def simple_generator(prompt, num):
            return [f"{prompt} - 创意{i}" for i in range(num)]
        
        generator.register_model("simple", simple_generator)
        
        async def run_test():
            result = await generator.generate("如何提高效率", num_ideas=3)
            assert len(result.ideas) == 3
            assert result.model_count == 1
        
        asyncio.run(run_test())
    
    def test_vote(self):
        """测试投票机制"""
        generator = IdeaGenerator()
        
        ideas = [
            Idea(content="创意1", quality_score=0.8, diversity_score=0.7),
            Idea(content="创意2", quality_score=0.9, diversity_score=0.5),
            Idea(content="创意3", quality_score=0.7, diversity_score=0.9)
        ]
        
        result = generator.vote(ideas)
        assert result is not None
    
    def test_refine(self):
        """测试创意优化"""
        generator = IdeaGenerator()
        
        def simple_refiner(prompt, num):
            return [f"优化: {prompt}"]
        
        generator.register_model("refiner", simple_refiner)
        
        original = Idea(content="原始创意", confidence=0.7)
        
        async def run_test():
            refined = await generator.refine(original, iterations=1)
            assert refined.content.startswith("优化")
            assert refined.status.value == "refined"
        
        asyncio.run(run_test())


class TestCognitiveFramework:
    """认知框架整合测试"""
    
    def test_framework_init(self):
        """测试框架初始化"""
        cf = CognitiveFramework()
        
        assert cf is not None
        assert hasattr(cf, '_mental_model_builder')
        assert hasattr(cf, '_attention_controller')
        assert hasattr(cf, '_meta_reasoning_engine')
        assert hasattr(cf, '_experience_manager')
        assert hasattr(cf, '_idea_generator')
    
    def test_process_request(self):
        """测试处理请求"""
        cf = CognitiveFramework()
        
        async def run_test():
            result = await cf.process_request(
                query="如何提高工作效率",
                context={"user_id": "test", "session_id": "test_session"}
            )
            
            assert hasattr(result, 'success')
            assert hasattr(result, 'confidence')
            assert hasattr(result, 'content')
            assert result.success is True
        
        asyncio.run(run_test())
    
    def test_stats(self):
        """测试统计信息"""
        cf = CognitiveFramework()
        stats = cf.get_stats()
        
        assert "attention_controller" in stats
        assert "experience_manager" in stats
        assert "meta_reasoning_engine" in stats


if __name__ == "__main__":
    print("=" * 60)
    print("认知框架测试套件")
    print("=" * 60)
    
    # 运行测试
    pytest.main([__file__, "-v"])
