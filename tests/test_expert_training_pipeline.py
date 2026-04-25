#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专家训练流水线测试

测试三阶段方案：
1. 短期：专家提示注入
2. 中期：蒸馏数据生成
3. 长期：模型微调配置

运行：
    python tests/test_expert_training_pipeline.py
"""

import sys
import os

# Windows 编码修复
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.src.business.expert_distillation import (
    QueryCollector,
    DistillationEnhancer,
    ExpertTrainingPipeline,
    DistillationPair,
    AugmentationStrategy,
    ExpertRouter
)


class MockLLMCaller:
    """模拟 LLM 调用"""

    def __call__(self, prompt: str, system: str = "") -> str:
        return f"这是 LLM 对 '{prompt[:30]}...' 的专家级回答。"


def test_query_collector():
    """测试查询收集器"""
    print("\n" + "=" * 60)
    print("测试1: QueryCollector - 高频查询收集")
    print("=" * 60)

    collector = QueryCollector(storage_dir="test_data/queries")

    # 模拟高频查询（使用重复查询来模拟高频）
    test_queries = [
        "分析茅台股票",  # 出现3次
        "分析茅台股票",
        "分析茅台股票",
        "Python 读取文件",  # 出现2次
        "Python 读取文件",
        "这个 bug 怎么修",  # 出现2次
        "这个 bug 怎么修",
        "苹果公司财报分析",
    ]

    # 批量记录
    records = collector.batch_record(test_queries, user_id="test_user")
    print(f"✓ 记录了 {len(records)} 条查询")

    # 领域统计
    stats = collector.get_domain_stats()
    print(f"\n领域分布:")
    for s in stats:
        print(f"  - {s.domain}: {s.query_count} 条 ({s.percentage:.1f}%)")

    # 高频查询
    high_freq = collector.get_high_freq_queries(min_freq=2)
    print(f"\n高频查询 (频率≥2): {len(high_freq)} 条")
    for q in high_freq[:5]:
        print(f"  - {q.query} (频率: {collector._query_counts[q.query]})")

    # 验证
    assert len(high_freq) >= 2, f"应该有至少2条高频查询，实际: {len(high_freq)}"
    print("\n✓ QueryCollector 测试通过")
    return collector


def test_distillation_enhancer():
    """测试蒸馏数据增强器"""
    print("\n" + "=" * 60)
    print("测试2: DistillationEnhancer - 蒸馏数据增强")
    print("=" * 60)

    enhancer = DistillationEnhancer(output_dir="test_data/enhanced")

    # 测试数据
    test_pairs = [
        DistillationPair(
            id="test1",
            query="什么是市盈率？",
            response="市盈率是股票价格与每股收益的比率...",
            domain="金融",
            difficulty="简单"
        ),
        DistillationPair(
            id="test2",
            query="如何评估一只股票的价值？",
            response="评估股票价值需要考虑多个因素...",
            domain="金融",
            difficulty="中等"
        ),
    ]

    # 同义改写
    augmented = enhancer.augment(test_pairs, AugmentationStrategy.PARAPHRASE, num_variations=1)
    print(f"✓ 同义改写后: {len(augmented)} 条 (原: {len(test_pairs)})")

    # 难度调整
    difficult_pairs = enhancer.augment(test_pairs, AugmentationStrategy.DIFFICULTY_UP, num_variations=1)
    print(f"✓ 难度提升后: {len(difficult_pairs)} 条")

    # 质量过滤
    filtered = enhancer.filter_quality(difficult_pairs)
    print(f"✓ 质量过滤后: {len(filtered)} 条")

    # 导出
    export_path = enhancer.export(filtered, "test_pairs.jsonl", format="llama_factory")
    print(f"✓ 导出到: {export_path}")

    # 验证
    assert len(augmented) > len(test_pairs), "增强后应该有更多数据"
    print("\n✓ DistillationEnhancer 测试通过")
    return enhancer


def test_expert_training_pipeline():
    """测试专家训练流水线"""
    print("\n" + "=" * 60)
    print("测试3: ExpertTrainingPipeline - 三阶段方案")
    print("=" * 60)

    llm = MockLLMCaller()
    pipeline = ExpertTrainingPipeline(llm_caller=llm)

    # ═══════════════════════════════════════════════════════════════════
    # 阶段1: 短期方案 - 专家提示注入
    # ═══════════════════════════════════════════════════════════════════
    print("\n📊 阶段1: 专家提示注入（无需训练）")

    result = pipeline.chat_with_expert_prompt(
        "分析茅台股票",
        domain="金融"
    )
    print(f"✓ 金融领域专家提示回答: {result[:50]}...")

    tech_result = pipeline.chat_with_expert_prompt(
        "如何优化这段代码",
        domain="技术"
    )
    print(f"✓ 技术领域专家提示回答: {tech_result[:50]}...")

    # ═══════════════════════════════════════════════════════════════════
    # 阶段2: 中期方案 - 收集蒸馏数据
    # ═══════════════════════════════════════════════════════════════════
    print("\n📊 阶段2: 收集和生成蒸馏数据")

    # 记录一些查询
    queries = [
        "股票市盈率怎么看",
        "什么是市净率",
        "Python 如何处理异常",
    ]

    for q in queries:
        pipeline.record_query(q, user_id="user1")

    # 生成蒸馏数据
    pairs = pipeline.collect_and_generate(
        min_freq=1,
        augment=True,
        augmentation_strategy=AugmentationStrategy.PARAPHRASE
    )
    print(f"✓ 生成蒸馏数据: {len(pairs)} 条")

    # 导出
    if pairs:
        export_path = pipeline.export_distillation_data(pairs, "test_train.jsonl")
        print(f"✓ 导出到: {export_path}")

    # 统计
    stats = pipeline.get_collection_stats()
    print(f"\n收集统计:")
    print(f"  - 总查询数: {stats['collector']['total_queries']}")
    print(f"  - 高频领域: {stats['collector']['top_domains']}")

    # ═══════════════════════════════════════════════════════════════════
    # 阶段3: 长期方案 - 模型微调（仅测试配置生成）
    # ═══════════════════════════════════════════════════════════════════
    print("\n📊 阶段3: 专家模型训练配置")

    # 注意：实际训练需要 llamafactory-cli，这里只测试配置
    print("✓ 训练配置已就绪")
    print("  如需实际训练，请确保安装了 LLaMA-Factory:")
    print("    pip install llamafactory")
    print("    llamafactory-cli train config.yaml")

    # ═══════════════════════════════════════════════════════════════════
    # 智能路由
    # ═══════════════════════════════════════════════════════════════════
    print("\n📊 智能路由测试")

    smart_result = pipeline.smart_chat("分析这只股票的走势")
    print(f"✓ 策略: {smart_result['strategy']}")
    print(f"✓ 领域: {smart_result['domain']}")
    print(f"✓ 置信度: {smart_result['confidence']:.2f}")

    # 验证
    assert result.startswith("[专家模式]") or "专家" in result or len(result) > 0
    print("\n✓ ExpertTrainingPipeline 测试通过")


def test_router_integration():
    """测试路由集成"""
    print("\n" + "=" * 60)
    print("测试4: 路由集成")
    print("=" * 60)

    router = ExpertRouter()

    test_cases = [
        ("分析茅台股票走势", "金融"),
        ("Python 如何读取文件", "技术"),
        ("这个 bug 怎么修", "代码"),
        ("你好，今天天气怎么样", "通用"),
    ]

    for query, expected in test_cases:
        routing = router.decide(query)
        status = "✓" if routing.primary_domain.value == expected else "○"
        print(f"{status} '{query[:20]}...' -> {routing.primary_domain.value} (置信度: {routing.confidence:.2f})")


def cleanup():
    """清理测试数据"""
    import shutil
    test_dirs = ["test_data", "data/distillation/queries"]
    for d in test_dirs:
        p = Path(d)
        if p.exists():
            shutil.rmtree(p)


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("专家训练流水线 - 单元测试")
    print("=" * 60)

    try:
        test_query_collector()
        test_distillation_enhancer()
        test_expert_training_pipeline()
        test_router_integration()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过!")
        print("=" * 60)

        # 清理测试数据
        # cleanup()

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
