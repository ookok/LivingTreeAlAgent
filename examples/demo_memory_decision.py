"""
智能记忆与决策支持系统演示
Demonstration of Intelligent Memory and Decision Support Systems
"""

import asyncio
import json
from datetime import datetime

# 导入模块
from core.intelligent_memory import (
    IntelligentMemorySystem,
    MemoryValue,
    get_memory_system
)
from core.decision_engine import (
    DecisionSupportEngine,
    UserProfile,
    get_decision_engine
)


def demo_intelligent_memory():
    """演示智能记忆系统"""
    print("\n" + "=" * 60)
    print("🧠 智能记忆系统演示")
    print("=" * 60)

    # 创建实例
    memory = IntelligentMemorySystem()

    # 1. 记录一些交互
    print("\n📝 记录交互...")

    # 高价值交互
    qa_id1 = memory.record_interaction(
        question="Hermes Desktop 使用什么技术栈？",
        answer="Hermes Desktop 基于 PyQt6 开发，集成了 GPT4All 和 NousHermes 模型，支持从魔搭社区获取 GGUF 模型。核心技术栈包括：PyQt6、SQLite、Ollama API、ModelScope SDK。",
        metadata={"tags": ["技术", "架构"]}
    )
    print(f"  记录高价值问答: {qa_id1}")

    # 低价值交互（会被过滤）
    qa_id2 = memory.record_interaction(
        question="你好",
        answer="你好！有什么可以帮你的吗？",
        metadata={"tags": ["寒暄"]}
    )
    print(f"  记录低价值问答: {qa_id2}")

    # 另一个高价值交互
    qa_id3 = memory.record_interaction(
        question="如何配置 Ollama 连接？",
        answer="在 config.yaml 中配置 ollama 的 host 和 port，默认是 http://localhost:11434。也可以通过环境变量 OLLAMA_HOST 来设置。",
        metadata={"tags": ["配置", "Ollama"]}
    )
    print(f"  记录配置问答: {qa_id3}")

    # 2. 检索上下文
    print("\n🔍 检索上下文...")
    context = memory.retrieve_context("Ollama 配置问题", max_fewshot=2)

    print(f"  查询关键词: {context['query_keywords']}")
    print(f"  Few-Shot 示例数: {len(context['fewshot_examples'])}")
    for i, ex in enumerate(context['fewshot_examples'], 1):
        print(f"    {i}. Q: {ex['question'][:30]}...")
        print(f"       A: {ex['answer'][:50]}...")

    print(f"  事实锚点数: {len(context['fact_anchors'])}")

    # 3. 构建增强提示词
    print("\n💡 构建增强提示词...")
    original_prompt = "请解释 Ollama 的配置方法"
    enhanced = memory.build_enhanced_prompt(original_prompt, "Ollama 配置")
    print(f"  原始提示: {original_prompt}")
    print(f"  增强后长度: {len(enhanced)} 字符")

    # 4. 质量反馈
    print("\n⭐ 质量反馈...")
    if qa_id1:
        memory.update_quality_feedback(qa_id1, is_helpful=True)
        print(f"  标记问答 {qa_id1} 为有帮助")

    # 5. 用户偏好
    print("\n👤 用户偏好...")
    memory.set_preference("response_style", "简洁", category="formatting")
    memory.set_preference("language", "中文", category="general")
    print(f"  设置偏好: response_style=简洁, language=中文")
    print(f"  读取偏好: {memory.get_preference('response_style')}")

    # 6. 统计信息
    print("\n📊 统计信息...")
    stats = memory.get_stats()
    print(f"  问答对数: {stats['qa_pairs']}")
    print(f"  实体数: {stats['entities']}")
    print(f"  关系数: {stats['relations']}")
    print(f"  事实数: {stats['facts']}")

    # 7. 导出知识
    print("\n📤 导出知识...")
    exported = memory.export_knowledge(format="markdown")
    print(f"  导出格式: Markdown")
    print(f"  导出长度: {len(exported)} 字符")


def demo_decision_support():
    """演示决策支持系统"""
    print("\n" + "=" * 60)
    print("📊 决策支持系统演示")
    print("=" * 60)

    # 创建实例
    engine = get_decision_engine()

    # 1. 设置用户画像
    print("\n👤 设置用户画像...")
    profile = UserProfile(
        risk_tolerance=0.6,
        investment_experience="intermediate",
        capital_size="medium",
        investment_horizon="medium",
        preferred_sectors=["科技", "新能源"],
        has_stop_loss_experience=True
    )
    engine.save_user_profile("demo_user", profile)
    print(f"  风险承受能力: {profile.risk_tolerance}")
    print(f"  投资经验: {profile.investment_experience}")
    print(f"  资金规模: {profile.capital_size}")
    print(f"  投资周期: {profile.investment_horizon}")

    # 2. 生成分析
    print("\n📈 生成决策支持报告...")

    current_data = {
        "price": 150.0,
        "volume": 1000000,
        "market_cap": "1000亿"
    }

    indicators = {
        "trend": "up",
        "momentum": "strong",
        "volatility": 0.15,
        "support": 145.0,
        "resistance": 165.0,
        "rsi": 65,
        "macd": "golden_cross"
    }

    news = [
        "公司发布季度财报，营收增长20%",
        "获得重要技术专利",
        "行业景气度持续上升"
    ]

    report = engine.generate_analysis(
        symbol="EXAMPLE",
        current_price=150.0,
        current_data=current_data,
        indicators=indicators,
        news=news,
        news_sentiment=0.7,  # 偏利好
        user_profile=profile
    )

    # 3. 显示情景分析
    print("\n📊 情景概率分析:")
    for scenario in report.scenarios:
        emoji = {
            "optimistic": "🟢",
            "neutral": "🟡",
            "pessimistic": "🔴"
        }.get(scenario.type, "⚪")

        print(f"\n  {emoji} {scenario.type.upper()} ({scenario.probability:.0%})")
        print(f"     价格区间: {scenario.price_target_low:.2f} - {scenario.price_target_high:.2f}")
        print(f"     时间框架: {scenario.timeframe_days}天")
        print(f"     触发条件: {', '.join(scenario.trigger_conditions[:2])}")
        print(f"     确认信号: {', '.join(scenario.confirmation_signals[:2])}")

    # 4. 显示策略建议
    print("\n\n🎯 个性化策略建议:")
    for strategy in report.strategies:
        print(f"\n  【{strategy.name}】({strategy.type})")
        print(f"     仓位: {strategy.position_ratio:.0%}")
        print(f"     入场: {strategy.entry_price_low:.2f} - {strategy.entry_price_high:.2f}")
        print(f"     止损: {strategy.stop_loss:.2f}")
        print(f"     止盈: {strategy.take_profit:.2f}")
        print(f"     预期收益: {strategy.expected_return:.1%}")
        print(f"     最大回撤: {strategy.max_drawdown:.1%}")
        print(f"     适合: {strategy.suitable_for}")

    # 5. 显示风险收益矩阵
    print("\n\n📉 风险收益矩阵:")
    print(f"  {'策略':<20} {'预期收益':>10} {'最大回撤':>10} {'夏普比率':>10} {'风险':>6}")
    print(f"  {'-'*60}")
    for metric in report.risk_matrix:
        print(
            f"  {metric.strategy_name:<18} "
            f"{metric.expected_return:>10} "
            f"{metric.max_drawdown:>10} "
            f"{metric.sharpe_ratio:>10} "
            f"{metric.risk_level:>6}"
        )

    # 6. 推荐策略
    print(f"\n\n✅ 推荐策略: {report.recommended_strategy}")

    # 7. 保存决策记录
    print("\n💾 保存决策记录...")
    decision_id = engine.save_decision(
        user_id="demo_user",
        symbol="EXAMPLE",
        report=report,
        selected_strategy=report.recommended_strategy
    )
    print(f"  决策ID: {decision_id}")

    # 8. 获取决策历史
    print("\n📜 决策历史...")
    history = engine.get_decision_history("demo_user", limit=5)
    print(f"  历史记录数: {len(history)}")

    # 9. 决策框架
    print("\n\n📋 决策框架:")
    framework = report.decision_framework
    print(f"  标题: {framework.get('title', '')}")
    for step in framework.get("steps", []):
        print(f"    步骤{step['step']}: {step['title']} - {step['content'][:30]}...")

    # 10. 格式化的完整报告
    print("\n\n" + "=" * 60)
    print("📄 完整报告 (文本格式)")
    print("=" * 60)
    print(engine.format_report_text(report))


def demo_integration():
    """演示集成场景"""
    print("\n" + "=" * 60)
    print("🔗 集成场景演示")
    print("=" * 60)

    memory = get_memory_system()
    engine = get_decision_engine()

    # 场景：用户询问投资建议
    print("\n🎬 场景: 用户询问投资建议")

    user_question = "我应该如何配置我的投资组合？"

    # 1. 先从记忆系统获取用户偏好和历史
    print(f"\n  问题: {user_question}")

    response_style = memory.get_preference("response_style", "详细")
    investment_profile = memory.get_preference("investment_profile", "")

    print(f"  用户偏好-回复风格: {response_style}")
    if investment_profile:
        print(f"  历史投资画像: {investment_profile}")

    # 2. 从记忆系统获取上下文
    context = memory.retrieve_context(user_question)
    print(f"  检索到 Few-Shot 示例: {len(context['fewshot_examples'])}")

    # 3. 根据上下文构建回复
    print("\n  💬 生成回复...")

    if context['fewshot_examples']:
        print("  [系统] 找到相似的历史问答，可以作为参考")
        for ex in context['fewshot_examples'][:2]:
            print(f"    - {ex['question'][:40]}...")

    if context['fact_anchors']:
        print("  [系统] 找到相关事实:")
        for fact in context['fact_anchors'][:3]:
            print(f"    - {fact['subject']} {fact['predicate']} {fact['object']}")

    # 4. 如果涉及投资决策，启动决策引擎
    print("\n  📊 启动决策支持...")

    user_profile = engine.get_user_profile("current_user")
    if user_profile.risk_tolerance == 0.5 and not user_profile.investment_experience:
        # 设置默认值
        user_profile = UserProfile(
            risk_tolerance=0.5,
            investment_experience="beginner",
            capital_size="medium",
            investment_horizon="medium"
        )

    report = engine.generate_analysis(
        symbol="组合配置",
        current_price=1.0,
        current_data={},
        indicators={"trend": "neutral", "volatility": 0.1},
        news=["市场整体平稳"],
        news_sentiment=0.0,
        user_profile=user_profile
    )

    print(f"  生成 {len(report.scenarios)} 种情景")
    print(f"  推荐策略: {report.recommended_strategy}")

    # 5. 保存交互
    answer = f"基于您的风险承受能力({user_profile.risk_tolerance:.0%})和投资经验({user_profile.investment_experience})，推荐{report.recommended_strategy}策略..."
    memory.record_interaction(
        question=user_question,
        answer=answer,
        metadata={"type": "investment_advice", "profile_used": str(user_profile.risk_tolerance)}
    )
    print("\n  ✅ 交互已保存到记忆系统")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🚀 智能记忆与决策支持系统演示")
    print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 演示智能记忆系统
    demo_intelligent_memory()

    # 演示决策支持系统
    demo_decision_support()

    # 演示集成场景
    demo_integration()

    print("\n" + "=" * 60)
    print("✅ 演示完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
