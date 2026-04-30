"""
智能自适应压缩演示

展示系统如何自动选择最佳压缩策略：
1. 文本特征分析
2. 上下文感知
3. 历史学习
4. 自动决策

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client/src'))

from business.adaptive_compression_engine import (
    get_adaptive_compression_engine,
    CompressionContext,
    smart_compress
)


async def demo_auto_compression():
    """演示自动压缩"""
    print("=" * 70)
    print("🤖 演示1: 智能自适应压缩")
    print("=" * 70)
    
    engine = get_adaptive_compression_engine()
    
    test_cases = [
        ("Hello, how are you?", "简单问候", CompressionContext.CHAT_MESSAGE),
        ("def hello():\n    print('Hello, World!')", "代码片段", CompressionContext.CHAT_MESSAGE),
        ("The quick brown fox jumps over the lazy dog. This is a test sentence.", "普通文本", CompressionContext.CHAT_MESSAGE),
        ("""
        The React component is re-rendering because you're creating a new object 
        reference on each render cycle. Use useMemo to memoize expensive calculations.
        """, "技术解释", CompressionContext.MODEL_RESPONSE),
        ("""
        [2024-01-01 10:00:00] INFO: Server started successfully
        [2024-01-01 10:00:01] DEBUG: Loading configuration
        [2024-01-01 10:00:02] INFO: Database connected
        """, "日志消息", CompressionContext.LOG_MESSAGE),
        ("""
        The investment portfolio shows strong returns. We recommend diversifying 
        assets across different sectors to manage risk and maximize returns.
        """, "金融分析", CompressionContext.API_RESPONSE),
        ("""
        According to the agreement, both parties must comply with all terms and 
        conditions outlined in this contract. Failure to comply may result in 
        legal action.
        """, "法律文档", CompressionContext.P2P_TRANSMISSION),
        ("""
        This is an extremely long text that goes on for many lines and contains 
        a lot of information. It continues for quite some time and includes 
        various details about different topics. The text is designed to test 
        the compression algorithm's ability to handle large amounts of content 
        efficiently.
        """ * 3, "超长文本", CompressionContext.CACHE_STORAGE),
    ]
    
    print(f"{'文本类型':<15} {'原始长度':>10} {'策略':<12} {'压缩率':>8} {'决策理由'}")
    print("-" * 70)
    
    for text, label, context in test_cases:
        text = text.strip()
        result = await engine.compress(text, context=context)
        
        ratio = result.get("ratio", result.get("compression_ratio", 0)) * 100
        strategy = result.get("strategy", "unknown")
        reasoning = result.get("decision_info", {}).get("reasoning", "")
        
        print(f"{label:<15} {len(text):>10} {strategy:<12} {ratio:>7.1f}% {reasoning}")


async def demo_context_awareness():
    """演示上下文感知"""
    print("\n" + "=" * 70)
    print("🎯 演示2: 上下文感知压缩")
    print("=" * 70)
    
    engine = get_adaptive_compression_engine()
    
    text = """
    The microservices architecture requires careful design. We need to implement 
    service discovery, load balancing, and circuit breakers for reliability.
    """.strip()
    
    contexts = list(CompressionContext)
    
    print(f"原始文本: {text[:50]}...")
    print(f"原始长度: {len(text)}")
    print()
    
    print(f"{'上下文':<25} {'策略':<12} {'压缩率':>8} {'置信度':>8}")
    print("-" * 60)
    
    for context in contexts:
        result = await engine.compress(text, context=context)
        
        ratio = result.get("ratio", result.get("compression_ratio", 0)) * 100
        strategy = result.get("strategy", "unknown")
        confidence = result.get("decision_info", {}).get("confidence", 0)
        
        print(f"{context.value:<25} {strategy:<12} {ratio:>7.1f}% {confidence:>7.2f}")


async def demo_history_learning():
    """演示历史学习"""
    print("\n" + "=" * 70)
    print("📚 演示3: 历史学习机制")
    print("=" * 70)
    
    engine = get_adaptive_compression_engine()
    engine.clear_history()
    
    code_snippets = [
        "def hello():\n    print('Hello')",
        "function greet() {\n    return 'Hello';\n}",
        "class MyClass:\n    def __init__(self):\n        pass",
        "const x = 10;\nconst y = 20;\nconsole.log(x + y);",
        "async function fetchData() {\n    const response = await fetch('/api');\n    return response.json();\n}",
    ]
    
    print("处理多个代码片段，观察策略选择变化：")
    print()
    
    for i, snippet in enumerate(code_snippets):
        result = await engine.compress(snippet, CompressionContext.CHAT_MESSAGE)
        strategy = result.get("strategy", "unknown")
        ratio = result.get("ratio", result.get("compression_ratio", 0)) * 100
        
        print(f"代码片段 {i+1}:")
        print(f"  策略: {strategy}")
        print(f"  压缩率: {ratio:.1f}%")
        print(f"  理由: {result.get('decision_info', {}).get('reasoning', '')}")
        print()
    
    stats = engine.get_decision_stats()
    print("决策统计:")
    for strategy, info in stats.items():
        print(f"  {strategy}: 使用 {info['used']} 次, 成功率 {info['success_rate']:.1%}")


async def demo_quick_compress():
    """演示便捷函数"""
    print("\n" + "=" * 70)
    print("⚡ 演示4: 便捷压缩函数")
    print("=" * 70)
    
    texts = [
        ("简单消息", "这是一条简单的消息。"),
        ("代码", "function test() {\n    return true;\n}"),
        ("技术解释", "使用 useMemo 可以避免不必要的重新渲染，提高性能。"),
        ("长文本", "这是一段比较长的文本内容，用于测试自适应压缩引擎的效果。" * 5),
    ]
    
    for label, text in texts:
        result = await smart_compress(text)
        ratio = result.get("ratio", result.get("compression_ratio", 0)) * 100
        
        print(f"【{label}】")
        print(f"  原始长度: {len(text)}")
        print(f"  压缩后长度: {result.get('compressed_length', len(text))}")
        print(f"  压缩率: {ratio:.1f}%")
        print(f"  策略: {result.get('strategy', 'unknown')}")
        print(f"  理由: {result.get('decision_info', {}).get('reasoning', '')}")
        print()


async def main():
    """运行所有演示"""
    await demo_auto_compression()
    await demo_context_awareness()
    await demo_history_learning()
    await demo_quick_compress()
    
    print("\n" + "=" * 70)
    print("🎉 智能自适应压缩演示完成！")
    print("=" * 70)
    print("\n📊 自适应压缩引擎总结：")
    print("""
核心功能：
1. 多维度特征分析 - 自动提取文本特征
2. 上下文感知 - 根据使用场景选择策略
3. 历史学习 - 基于历史数据优化决策
4. 自动模式 - 无需手动配置

决策流程：
┌─────────────────────────────────────────────┐
│  1. 提取文本特征                           │
│     - 长度、代码密度、技术术语比例          │
├─────────────────────────────────────────────┤
│  2. 识别内容类型和领域                      │
│     - 代码/技术/医疗/金融/法律              │
├─────────────────────────────────────────────┤
│  3. 分析使用上下文                          │
│     - 聊天/模型响应/日志/P2P/缓存/API       │
├─────────────────────────────────────────────┤
│  4. 查询历史数据                            │
│     - 相似文本的成功策略                    │
├─────────────────────────────────────────────┤
│  5. 应用决策规则                            │
│     - 返回最优策略                          │
└─────────────────────────────────────────────┘

使用方式：
    from business.adaptive_compression_engine import smart_compress
    
    # 最简单的方式 - 自动选择策略
    result = await smart_compress(text)
    
    # 指定上下文
    result = await smart_compress(text, context="model_response")
    
    # 使用引擎进行更精细的控制
    from business.adaptive_compression_engine import (
        get_adaptive_compression_engine,
        CompressionContext
    )
    
    engine = get_adaptive_compression_engine()
    result = await engine.compress(text, context=CompressionContext.MODEL_RESPONSE)

输出结果包含：
- compressed_text: 压缩后的文本
- ratio: 压缩率
- strategy: 使用的策略
- decision_info: 决策详情（置信度、理由、特征）
    """)


if __name__ == "__main__":
    asyncio.run(main())
