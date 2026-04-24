#!/usr/bin/env python3
"""
专家蒸馏模块测试

测试所有组件的功能：数据生成、模板库、路由、调用器、流水线。
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "core"))

from core.expert_distillation import (
    DistillationDataGenerator,
    ExpertTemplateLibrary,
    ExpertRouter,
    L4EnhancedCaller,
    ExpertDistillationPipeline,
)
from core.expert_distillation.router import QueryDomain, ComplexityLevel, RouteStrategy
from core.expert_distillation.data_generator import QATriple


def test_data_generator():
    """测试数据生成器"""
    print("\n" + "="*60)
    print("测试: DistillationDataGenerator")
    print("="*60)

    generator = DistillationDataGenerator()

    # 测试生成单条数据
    qa_list = generator.generate_from_seed(
        seed_question="什么是市盈率(PE)？如何用它评估股票？",
        domain="金融"
    )

    print(f"\n生成了 {len(qa_list)} 条数据")
    if qa_list:
        qa = qa_list[0]
        print(f"问题: {qa.question}")
        print(f"领域: {qa.domain}")
        print(f"关键词: {qa.keywords}")

    # 测试批量生成
    print("\n测试批量生成...")
    # batch = generator.generate_dataset("金融", topics=["股票", "债券"], samples_per_topic=4)
    # print(f"批量生成: {len(batch)} 条")

    print("\n统计:", generator.get_stats())
    return True


def test_template_library():
    """测试专家模板库"""
    print("\n" + "="*60)
    print("测试: ExpertTemplateLibrary")
    print("="*60)

    library = ExpertTemplateLibrary()

    # 测试获取专家
    analyst = library.get_expert_profile("金融", "分析师")
    print(f"\n获取金融分析师: {analyst.role if analyst else 'None'}")
    if analyst:
        print(f"特质: {analyst.traits}")

    # 测试模板匹配
    template = library.get_template("分析股票走势", domain="金融")
    print(f"\n匹配模板: {template.name if template else 'None'}")
    if template:
        print(f"推理步骤: {[s.description for s in template.reasoning_steps]}")

    # 测试提示注入
    enhanced = library.inject_expert_context("帮我分析贵州茅台的估值", "金融")
    print(f"\n增强提示长度: {len(enhanced)} 字符")
    print(f"前200字符:\n{enhanced[:200]}...")

    print("\n统计:", library.get_stats())
    return True


def test_router():
    """测试专家路由"""
    print("\n" + "="*60)
    print("测试: ExpertRouter")
    print("="*60)

    router = ExpertRouter()

    # 注册专家模型
    router.register_expert(QueryDomain.FINANCE, "fin_1.5b", "/models/fin_1.5b.gguf", priority=1)
    router.register_expert(QueryDomain.FINANCE, "fin_3b", "/models/fin_3b.gguf", priority=2)

    # 测试路由决策
    test_queries = [
        ("什么是市盈率？", QueryDomain.FINANCE),
        ("分析一下贵州茅台的估值是否合理", QueryDomain.FINANCE),
        ("帮我写一个Python函数", QueryDomain.CODE),
        ("这个合同有什么风险条款需要注意？", QueryDomain.LAW),
    ]

    print("\n路由测试:")
    for query, domain in test_queries:
        decision = router.decide(query, domain)
        print(f"\n查询: {query[:30]}...")
        print(f"  领域: {decision.primary_domain.value}")
        print(f"  复杂度: {decision.complexity.name}")
        print(f"  策略: {decision.strategy.value}")
        print(f"  专家模型: {decision.expert_model or '无'}")
        print(f"  理由: {decision.reasoning}")

    return True


def test_l4_caller():
    """测试 L4 增强调用器"""
    print("\n" + "="*60)
    print("测试: L4EnhancedCaller")
    print("="*60)

    caller = L4EnhancedCaller()

    # 测试调用
    result = caller.call("解释一下什么是股票的市盈率", domain="金融")

    print(f"\n响应:")
    print(result.response[:300] + "..." if len(result.response) > 300 else result.response)
    print(f"\n领域: {result.domain}")
    print(f"延迟: {result.latency_ms:.2f}ms")
    print(f"专家提示: {result.expert_hint[:100] if result.expert_hint else '无'}...")

    print("\n统计:", caller.get_stats())
    return True


def test_pipeline():
    """测试完整流水线"""
    print("\n" + "="*60)
    print("测试: ExpertDistillationPipeline")
    print("="*60)

    pipeline = ExpertDistillationPipeline()

    # 注册专家模型
    pipeline.register_expert_model("金融", "fin_expert", "/models/fin_expert.gguf")

    # 测试聊天
    print("\n测试聊天接口:")
    result = pipeline.chat("股票涨停是什么意思？", domain="金融")
    print(f"响应: {result.response[:200]}...")

    # 测试蒸馏数据生成
    print("\n测试蒸馏数据生成（模拟）:")
    qa_list = pipeline.generate_distillation_data("金融", topics=["股票"], samples_per_topic=2)
    print(f"生成了 {len(qa_list)} 条蒸馏数据")

    # 保存数据
    if qa_list:
        path = pipeline.save_distillation_data(qa_list, format="llama_factory")
        print(f"已保存到: {path}")

    print("\n完整统计:")
    stats = pipeline.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    return True


def test_hybrid_mode():
    """测试混合模式"""
    print("\n" + "="*60)
    print("测试: 混合模式")
    print("="*60)

    pipeline = ExpertDistillationPipeline()
    pipeline.register_expert_model("金融", "fin_1.5b", "/models/fin_1.5b.gguf")

    # 不同复杂度的查询
    queries = [
        ("什么是PE？",),
        ("分析茅台估值",),
        ("深入分析这只股票的投资价值，包括基本面、技术面等",),
    ]

    for query, in queries:
        result = pipeline.chat_with_expert(query, "金融")
        print(f"\n查询: {query[:40]}...")
        print(f"  策略: {result['strategy']}")
        if 'routing' in result:
            r = result['routing']
            print(f"  复杂度: {r.complexity.name}")
            print(f"  专家: {r.expert_model or '无'}")

    return True


def main():
    print("="*60)
    print("专家蒸馏模块测试套件")
    print("="*60)

    tests = [
        ("数据生成器", test_data_generator),
        ("专家模板库", test_template_library),
        ("专家路由", test_router),
        ("L4调用器", test_l4_caller),
        ("完整流水线", test_pipeline),
        ("混合模式", test_hybrid_mode),
    ]

    results = []
    for name, test_fn in tests:
        try:
            success = test_fn()
            results.append((name, success))
        except Exception as e:
            print(f"\n[X] 测试失败: {name}")
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # 汇总
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"通过: {passed}/{total}")

    for name, success in results:
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {name}")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
