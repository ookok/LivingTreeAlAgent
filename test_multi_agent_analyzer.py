# -*- coding: utf-8 -*-
"""
Phase 3 多智能体协同分析器测试
=================================

测试多 Agent 架构:
1. SummaryAgent - 摘要生成
2. EntityAgent - 实体提取
3. RelationAgent - 关系分析
4. InsightAgent - 洞察发现
5. SynthesisAgent - 综合报告
6. MultiAgentCoordinator - 协调器

Author: Hermes Desktop Team
Date: 2026-04-24
"""

import sys
import os

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
import time


class TestMultiAgentAnalyzers(unittest.TestCase):
    """多智能体分析器测试"""

    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        from core.long_context import (
            MultiAgentCoordinator,
            AgentType,
            SummaryAgent,
            EntityAgent,
            RelationAgent,
            InsightAgent,
            SynthesisAgent,
            MessageBus,
        )
        cls.AgentType = AgentType
        cls.SummaryAgent = SummaryAgent
        cls.EntityAgent = EntityAgent
        cls.RelationAgent = RelationAgent
        cls.InsightAgent = InsightAgent
        cls.SynthesisAgent = SynthesisAgent
        cls.MultiAgentCoordinator = MultiAgentCoordinator
        cls.MessageBus = MessageBus

        # 测试文本
        cls.test_text = """
人工智能技术在2024年迎来了爆发式发展。OpenAI发布了GPT-5模型，
该模型在推理能力和多模态理解方面有了显著提升。

在中国，百度公司推出了文心一言4.0版本，在中文理解方面表现优异。
同时，阿里巴巴和腾讯也在大模型领域持续投入。

技术发展带来了一些挑战，包括数据隐私、算法偏见等问题。
专家认为，需要建立更好的监管机制来应对这些挑战。

未来，人工智能将在医疗、教育、金融等领域发挥更大作用。
特别是在医疗领域，AI辅助诊断系统已经开始在实际应用中取得成效。
        """

    def test_01_summary_agent(self):
        """测试摘要 Agent"""
        print("\n" + "="*60)
        print("测试 1: SummaryAgent")
        print("="*60)

        agent = self.SummaryAgent()
        context = {"text": self.test_text, "task": "总结AI发展"}

        result = agent.execute(context)

        # 验证结果
        self.assertIsNotNone(result)
        self.assertIn("summaries", result)

        summaries = result["summaries"]
        print(f"超级摘要: {summaries.get('super', 'N/A')[:50]}...")
        print(f"简短摘要: {summaries.get('brief', 'N/A')[:50]}...")
        print(f"关键点: {summaries.get('key_points', [])}")

        self.assertIn("super", summaries)
        self.assertIn("brief", summaries)
        self.assertIn("key_points", summaries)

        print("[PASS] SummaryAgent 测试通过")

    def test_02_entity_agent(self):
        """测试实体提取 Agent"""
        print("\n" + "="*60)
        print("测试 2: EntityAgent")
        print("="*60)

        agent = self.EntityAgent()
        context = {"text": self.test_text}

        result = agent.execute(context)

        # 验证结果
        self.assertIsNotNone(result)
        self.assertIn("entities", result)

        entities = result["entities"]
        print(f"提取的实体: {entities}")

        for entity_type, entity_list in entities.items():
            print(f"  {entity_type}: {entity_list}")

        self.assertIn("org", entities)
        self.assertIn("tech", entities)

        print(f"总实体数: {result.get('total_count', 0)}")
        print("[PASS] EntityAgent 测试通过")

    def test_03_relation_agent(self):
        """测试关系分析 Agent"""
        print("\n" + "="*60)
        print("测试 3: RelationAgent")
        print("="*60)

        # 先执行 EntityAgent
        entity_agent = self.EntityAgent()
        entity_result = entity_agent.execute({"text": self.test_text})

        # 执行 RelationAgent
        agent = self.RelationAgent()
        context = {
            "text": self.test_text,
            "entity_result": entity_result,
        }

        result = agent.execute(context)

        # 验证结果
        self.assertIsNotNone(result)
        self.assertIn("relations", result)

        relations = result["relations"]
        print(f"发现的关系: {relations}")

        for rel in relations[:3]:
            print(f"  {rel.get('type')}: {rel.get('from')} -> {rel.get('to')}")

        print(f"关系数: {result.get('relation_count', 0)}")
        print("[PASS] RelationAgent 测试通过")

    def test_04_insight_agent(self):
        """测试洞察发现 Agent"""
        print("\n" + "="*60)
        print("测试 4: InsightAgent")
        print("="*60)

        # 先执行其他 Agent
        summary_agent = self.SummaryAgent()
        entity_agent = self.EntityAgent()
        relation_agent = self.RelationAgent()

        summary_result = summary_agent.execute({"text": self.test_text})
        entity_result = entity_agent.execute({"text": self.test_text})
        relation_result = relation_agent.execute({
            "text": self.test_text,
            "entity_result": entity_result,
        })

        # 执行 InsightAgent
        agent = self.InsightAgent()
        context = {
            "text": self.test_text,
            "summary_result": summary_result,
            "entity_result": entity_result,
            "relation_result": relation_result,
        }

        result = agent.execute(context)

        # 验证结果
        self.assertIsNotNone(result)
        self.assertIn("insights", result)

        insights = result["insights"]
        print(f"发现的模式: {insights.get('patterns', [])}")
        print(f"异常检测: {insights.get('anomalies', [])}")
        print(f"趋势分析: {insights.get('trends', [])}")
        print(f"建议: {insights.get('recommendations', [])}")

        self.assertIn("patterns", insights)
        self.assertIn("anomalies", insights)
        self.assertIn("recommendations", insights)

        print("[PASS] InsightAgent 测试通过")

    def test_05_synthesis_agent(self):
        """测试综合报告 Agent"""
        print("\n" + "="*60)
        print("测试 5: SynthesisAgent")
        print("="*60)

        # 先执行其他 Agent
        summary_agent = self.SummaryAgent()
        entity_agent = self.EntityAgent()
        relation_agent = self.RelationAgent()
        insight_agent = self.InsightAgent()

        summary_result = summary_agent.execute({"text": self.test_text})
        entity_result = entity_agent.execute({"text": self.test_text})
        relation_result = relation_agent.execute({
            "text": self.test_text,
            "entity_result": entity_result,
        })
        insight_result = insight_agent.execute({
            "text": self.test_text,
            "summary_result": summary_result,
            "entity_result": entity_result,
            "relation_result": relation_result,
        })

        # 执行 SynthesisAgent
        agent = self.SynthesisAgent()
        context = {
            "task": "分析AI发展趋势",
            "summary_result": summary_result,
            "entity_result": entity_result,
            "relation_result": relation_result,
            "insight_result": insight_result,
        }

        result = agent.execute(context)

        # 验证结果
        self.assertIsNotNone(result)
        self.assertIn("summaries", result)
        self.assertIn("conclusions", result)
        self.assertIn("knowledge_graph", result)

        print(f"执行摘要: {result['summaries'].get('executive', 'N/A')[:80]}...")
        print(f"关键发现: {result.get('key_findings', [])}")
        print(f"结论: {result.get('conclusions', [])}")
        print(f"建议: {result.get('suggestions', [])}")
        print(f"置信度: {result.get('confidence_score', 0):.2f}")

        self.assertIn("conclusions", result)
        self.assertIn("suggestions", result)

        print("[PASS] SynthesisAgent 测试通过")

    def test_06_coordinator(self):
        """测试多智能体协调器"""
        print("\n" + "="*60)
        print("测试 6: MultiAgentCoordinator")
        print("="*60)

        coordinator = self.MultiAgentCoordinator()

        start_time = time.time()
        result = coordinator.analyze(
            text=self.test_text,
            task="分析AI发展趋势",
        )
        elapsed = time.time() - start_time

        # 验证结果
        self.assertIsNotNone(result)
        self.assertIn("agent_results", result)
        self.assertIn("final_report", result)
        self.assertIn("execution_time", result)

        agent_results = result["agent_results"]
        final_report = result["final_report"]

        print(f"执行的 Agent 数: {result.get('total_agents', 0)}")
        print(f"agent_results 数量: {len(agent_results)}")
        print(f"执行时间: {result.get('execution_time', 0):.2f}秒")
        print(f"\n最终报告摘要:")
        summary_text = final_report.get('summary', 'N/A')
        if summary_text and summary_text != 'N/A':
            print(f"  {summary_text[:80]}...")
        else:
            print(f"  {summary_text}")
        print(f"  置信度: {final_report.get('confidence', 0):.2f}")
        print(f"  关键发现: {final_report.get('key_findings', [])}")
        print(f"  建议: {final_report.get('suggestions', [])}")

        # 验证有结果
        self.assertTrue(len(agent_results) > 0 or len(final_report) > 0, "应该有分析结果")

        print("[PASS] MultiAgentCoordinator 测试通过")

    def test_07_coordinator_parallel(self):
        """测试协调器并行执行"""
        print("\n" + "="*60)
        print("测试 7: MultiAgentCoordinator 并行执行")
        print("="*60)

        coordinator = self.MultiAgentCoordinator(max_workers=4)

        results = []
        for agent_name, result, progress in coordinator.analyze_streaming(
            text=self.test_text,
            task="分析AI发展趋势",
        ):
            results.append((agent_name, progress))
            print(f"  [{agent_name}] 完成 {progress:.0%}")

        # 应该执行所有注册的 Agent
        print(f"\n执行了 {len(results)} 个 Agent")

        # 验证顺序 - summary/entity 应该在 relation/insight/synthesis 之前
        agent_names = [r[0] for r in results]
        print(f"执行顺序: {agent_names}")

        # 至少应该有 summary 和 entity
        self.assertTrue("summary" in agent_names or "entity" in agent_names)
        
        # synthesis 应该在后面
        if "synthesis" in agent_names and "summary" in agent_names:
            self.assertLess(
                agent_names.index("summary"), 
                agent_names.index("synthesis"), 
                "Summary 应在 Synthesis 之前完成"
            )

        print("[PASS] 并行执行测试通过")

    def test_08_quick_analyze(self):
        """测试便捷函数"""
        print("\n" + "="*60)
        print("测试 8: 便捷函数")
        print("="*60)

        from core.long_context import quick_analyze, analyze_multi_agent

        # 快速分析
        print("快速分析...")
        result = quick_analyze(self.test_text)
        self.assertIn("final_report", result)
        print(f"  结果: {result['final_report'].get('summary', 'N/A')[:50]}...")

        # 标准分析
        print("标准分析...")
        result = analyze_multi_agent(self.test_text, depth="standard")
        self.assertIn("final_report", result)
        print(f"  执行的Agent数: {result.get('total_agents', 0)}")

        # 深度分析
        print("深度分析...")
        result = analyze_multi_agent(self.test_text, depth="deep")
        self.assertIn("final_report", result)
        print(f"  执行的Agent数: {result.get('total_agents', 0)}")

        # 全面分析
        print("全面分析...")
        result = analyze_multi_agent(self.test_text, depth="comprehensive")
        self.assertIn("final_report", result)
        print(f"  执行的Agent数: {result.get('total_agents', 0)}")

        print("[PASS] 便捷函数测试通过")

    def test_09_message_bus(self):
        """测试消息总线"""
        print("\n" + "="*60)
        print("测试 9: MessageBus")
        print("="*60)

        from core.long_context import MessageBus, AgentMessage, MessageType

        bus = MessageBus()

        received = []

        def callback(msg):
            received.append(msg)

        bus.subscribe("test_agent", callback)

        message = AgentMessage(
            msg_id="test_1",
            msg_type=MessageType.TASK,
            from_agent="sender",
            to_agent="test_agent",
            content={"data": "test"},
        )

        bus.publish(message)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].content["data"], "test")

        print(f"发送消息: {message.msg_id}")
        print(f"接收消息: {received[0].msg_id}")
        print("[PASS] MessageBus 测试通过")

    def test_10_performance(self):
        """性能测试"""
        print("\n" + "="*60)
        print("测试 10: 性能测试")
        print("="*60)

        from core.long_context import MultiAgentCoordinator

        coordinator = MultiAgentCoordinator()

        # 使用较长文本
        long_text = self.test_text * 5

        start_time = time.time()
        result = coordinator.analyze(
            text=long_text,
            task="全面分析",
        )
        elapsed = time.time() - start_time

        print(f"文本长度: {len(long_text)} 字符")
        print(f"执行时间: {elapsed:.2f}秒")
        print(f"Agent 数: {result.get('total_agents', 0)}")
        print(f"置信度: {result['final_report'].get('confidence', 0):.2f}")

        # 验证结果完整性
        self.assertIsNotNone(result["final_report"]["summary"])
        self.assertGreater(result["final_report"]["confidence"], 0)

        print("[PASS] 性能测试通过")


def run_tests():
    """运行测试"""
    print("\n" + "="*60)
    print("Phase 3: 多智能体协同分析器测试")
    print("="*60)

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestMultiAgentAnalyzers)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 统计
    print("\n" + "="*60)
    print("测试统计")
    print("="*60)
    print(f"运行测试: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n[OK] 所有测试通过!")
    else:
        print("\n[FAIL] 有测试失败")
        if result.failures:
            print("\n失败:")
            for test, trace in result.failures:
                print(f"  {test}: {trace}")
        if result.errors:
            print("\n错误:")
            for test, trace in result.errors:
                print(f"  {test}: {trace}")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
