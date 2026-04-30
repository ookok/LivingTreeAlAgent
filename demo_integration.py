"""
压缩工具深度集成演示

展示增强后的压缩工具如何与系统深度集成：
1. 基础压缩策略（Lite/Full/Ultra/Wenyan）
2. 高级压缩策略（领域自适应/知识蒸馏/增量压缩/混合）
3. P2P消息压缩
4. 上下文压缩
5. 完整的压缩流程

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client/src'))

from business.compression_integration import (
    get_compression_integration,
    CompressionStrategy
)


async def demo_basic_strategies():
    """演示基础压缩策略"""
    print("=" * 70)
    print("📝 演示1: 基础压缩策略")
    print("=" * 70)
    
    compression = get_compression_integration()
    
    sample_text = """
The reason your React component is re-rendering is likely because you're creating a 
new object reference on each render cycle. When you pass an inline object as a prop, 
React's shallow comparison sees it as a different object every time, which triggers 
a re-render. I'd recommend using useMemo to memoize the object.
    """.strip()
    
    print(f"原始文本长度: {len(sample_text)}")
    print(f"原始文本:\n{sample_text}\n")
    
    strategies = [
        CompressionStrategy.LITE,
        CompressionStrategy.FULL,
        CompressionStrategy.ULTRA,
        CompressionStrategy.WENYAN,
    ]
    
    for strategy in strategies:
        result = await compression.compress_text(sample_text, strategy=strategy)
        ratio = result.get("ratio", result.get("compression_ratio", 0)) * 100
        print(f"【{strategy.value.upper()}】压缩率: {ratio:.1f}%")
        print(f"  长度: {result['original_length']} → {result['compressed_length']}")
        print(f"  压缩后: {result['compressed_text'][:80]}...\n")


async def demo_advanced_strategies():
    """演示高级压缩策略"""
    print("=" * 70)
    print("🚀 演示2: 高级压缩策略")
    print("=" * 70)
    
    compression = get_compression_integration()
    
    test_cases = [
        ("""
        The patient was admitted to the ICU with severe symptoms. 
        The doctor prescribed medication and ordered lab tests.
        """, "医疗文本"),
        
        ("""
        The investment portfolio shows strong returns. 
        We recommend diversifying assets to manage risk.
        """, "金融文本"),
        
        ("""
        According to the agreement, both parties must comply with all terms.
        The contract includes confidentiality clauses.
        """, "法律文本"),
    ]
    
    for text, label in test_cases:
        text = text.strip()
        print(f"【{label}】原始长度: {len(text)}")
        
        strategies = [
            CompressionStrategy.DOMAIN,
            CompressionStrategy.KNOWLEDGE,
            CompressionStrategy.HYBRID,
        ]
        
        for strategy in strategies:
            result = await compression.compress_text(text, strategy=strategy)
            ratio = result.get("ratio", result.get("compression_ratio", 0)) * 100
            print(f"  {strategy.value}: {ratio:.1f}% ({result['compressed_length']}字符)")
        
        print()


async def demo_incremental_compression():
    """演示增量压缩"""
    print("=" * 70)
    print("📈 演示3: 增量压缩")
    print("=" * 70)
    
    compression = get_compression_integration()
    
    version1 = """
    项目进度报告
    ============
    
    已完成:
    - 用户登录模块
    - 数据存储模块
    
    进行中:
    - API接口开发
    """
    
    version2 = """
    项目进度报告
    ============
    
    已完成:
    - 用户登录模块
    - 数据存储模块
    - API接口开发 ✅
    
    进行中:
    - 前端界面开发
    - 测试用例编写
    
    下阶段计划:
    - 性能优化
    """
    
    print(f"版本1长度: {len(version1.strip())}")
    print(f"版本2长度: {len(version2.strip())}")
    
    result = await compression.compress_text(version2.strip(), strategy=CompressionStrategy.INCREMENTAL)
    ratio = result.get("ratio", result.get("compression_ratio", 0))
    print(f"\n增量压缩率: {ratio * 100:.1f}%")
    print(f"压缩后长度: {result['compressed_length']}")
    print(f"\n新增内容:")
    print(result["compressed_text"])


async def demo_p2p_integration():
    """演示P2P消息压缩集成"""
    print("=" * 70)
    print("🔄 演示4: P2P消息压缩集成")
    print("=" * 70)
    
    compression = get_compression_integration()
    
    message = {
        "type": "chat",
        "from": "node_abc123",
        "to": "node_xyz789",
        "content": "这是一条需要在P2P网络中传输的技术消息，包含了大量的专业术语和技术细节用于测试压缩效果。",
        "timestamp": 1714435200.0,
        "priority": "high"
    }
    
    original_size = len(str(message))
    print(f"原始消息大小: {original_size} 字节")
    
    compressed = await compression.compress_message(message)
    compressed_size = len(str(compressed))
    print(f"压缩后消息大小: {compressed_size} 字节")
    print(f"压缩率: {(1 - compressed_size / original_size) * 100:.1f}%")
    
    if "compression" in compressed:
        print(f"\n压缩信息:")
        print(f"  类型: {compressed['compression']['type']}")
        print(f"  级别: {compressed['compression']['level']}")
        print(f"  文本压缩率: {compressed['compression']['ratio'] * 100:.1f}%")


async def demo_context_compression():
    """演示上下文压缩"""
    print("=" * 70)
    print("💬 演示5: 对话上下文压缩")
    print("=" * 70)
    
    compression = get_compression_integration()
    
    messages = [
        {"role": "user", "content": "你好，我有一个React性能问题需要帮助"},
        {"role": "assistant", "content": "好的，请描述一下你的问题"},
        {"role": "user", "content": "我的组件频繁重新渲染，导致页面卡顿"},
        {"role": "assistant", "content": "这通常是由于状态变化或props变化引起的。让我分析一下可能的原因：\n1. 状态不必要的更新\n2. 父组件重新渲染\n3. 函数引用变化"},
        {"role": "user", "content": "我检查了这些，但问题仍然存在"},
        {"role": "assistant", "content": "你是否使用了useMemo或useCallback来优化？这些Hook可以帮助减少不必要的重新渲染。"},
        {"role": "user", "content": "我试试这些方法"},
        {"role": "assistant", "content": "很好！如果还有问题随时可以问我。"},
    ]
    
    original_tokens = sum(len(msg["content"]) // 4 for msg in messages)
    print(f"原始token数: {original_tokens}")
    
    compressed = await compression.compress_context(messages, max_tokens=200)
    compressed_tokens = sum(len(msg.get("content", "")) // 4 for msg in compressed)
    
    print(f"压缩后token数: {compressed_tokens}")
    print(f"压缩率: {(1 - compressed_tokens / original_tokens) * 100:.1f}%")
    print(f"保留消息数: {len(compressed)}")


async def demo_all_strategies_summary():
    """演示所有策略对比"""
    print("=" * 70)
    print("⚡ 演示6: 所有压缩策略对比")
    print("=" * 70)
    
    compression = get_compression_integration()
    
    text = """
    To optimize the React application's performance, you should use useMemo 
    to memoize expensive calculations and useCallback to prevent unnecessary 
    re-renders. The key is to identify which values change frequently and 
    which remain stable across render cycles.
    """.strip()
    
    print(f"原始文本长度: {len(text)}")
    print()
    
    strategies = list(CompressionStrategy)
    
    results = []
    for strategy in strategies:
        result = await compression.compress_text(text, strategy=strategy)
        ratio = result.get("ratio", result.get("compression_ratio", 0)) * 100
        results.append({
            "strategy": strategy.value,
            "ratio": ratio,
            "length": result["compressed_length"]
        })
    
    results.sort(key=lambda x: -x["ratio"])
    
    print(f"{'策略':<20} {'压缩率':>10} {'压缩后长度':>15}")
    print("-" * 50)
    for r in results:
        print(f"{r['strategy']:<20} {r['ratio']:>9.1f}% {r['length']:>15d}")


async def main():
    """运行所有演示"""
    await demo_basic_strategies()
    await demo_advanced_strategies()
    await demo_incremental_compression()
    await demo_p2p_integration()
    await demo_context_compression()
    await demo_all_strategies_summary()
    
    print("\n" + "=" * 70)
    print("🎉 深度集成演示完成！")
    print("=" * 70)
    print("\n📊 压缩工具集成总结：")
    print("""
压缩策略矩阵：
┌─────────────────┬─────────────────┬─────────────────┐
│   策略类型      │   压缩率范围    │   适用场景      │
├─────────────────┼─────────────────┼─────────────────┤
│ Lite            │  0-10%         │ 代码/短文本     │
│ Full            │ 20-40%         │ 通用文本        │
│ Ultra           │ 35-50%         │ 长文本/日志     │
│ Wenyan          │ 30-45%         │ 趣味模式        │
│ Domain          │ 10-20%         │ 专业领域        │
│ Knowledge       │ 10-30%         │ 报告/总结       │
│ Incremental     │ 40-70%         │ 版本控制        │
│ Hybrid          │ 20-45%         │ 默认推荐        │
└─────────────────┴─────────────────┴─────────────────┘

系统集成点：
1. 模型响应压缩 → GlobalModelRouter
2. P2P消息压缩 → P2P网络层
3. 上下文压缩 → 对话管理器
4. 日志压缩 → 日志系统
5. 缓存压缩 → 缓存层

使用方式：
    from business.compression_integration import get_compression_integration
    
    compression = get_compression_integration()
    
    # 基础压缩
    result = await compression.compress_text(text, strategy=CompressionStrategy.FULL)
    
    # 高级压缩
    result = await compression.compress_text(text, strategy=CompressionStrategy.HYBRID)
    
    # P2P消息压缩
    compressed_msg = await compression.compress_message(message)
    
    # 上下文压缩
    compressed_ctx = await compression.compress_context(messages)
    """)


if __name__ == "__main__":
    asyncio.run(main())
