"""
压缩集成演示文件

展示创新的多层级信息传递优化方案：
1. 传输层压缩 - P2P网络传输优化
2. 模型响应压缩 - LLM输出自动压缩
3. 上下文压缩 - 对话历史智能压缩
4. 智能压缩策略 - 基于内容类型自适应

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import asyncio
import json
from typing import Dict, Any

from business.compression_integration import (
    get_compression_integration, 
    CompressionStrategy, 
    compress_response,
    compress_p2p
)
from business.intelligent_context_compressor import (
    get_context_compressor,
    ContextMessage
)
from business.compression_router import (
    get_compression_router,
    with_compression,
    compress_llm_response
)


async def demo_text_compression():
    """演示文本压缩功能"""
    print("=" * 60)
    print("📝 演示1: 文本压缩")
    print("=" * 60)
    
    compression = get_compression_integration()
    
    sample_text = """
The reason your React component is re-rendering is likely because you're creating a 
new object reference on each render cycle. When you pass an inline object as a prop, 
React's shallow comparison sees it as a different object every time, which triggers 
a re-render. I'd recommend using useMemo to memoize the object.
    """.strip()
    
    print(f"原始文本长度: {len(sample_text)}")
    print(f"原始文本:\n{sample_text}\n")
    
    strategies = [CompressionStrategy.LITE, CompressionStrategy.FULL, CompressionStrategy.ULTRA]
    
    for strategy in strategies:
        result = await compression.compress_text(sample_text, strategy=strategy)
        ratio = result["compression_ratio"] * 100
        print(f"【{strategy.value.upper()}】压缩后长度: {result['compressed_length']} ({ratio:.1f}%)")
        print(f"压缩后:\n{result['compressed_text']}\n")


async def demo_p2p_compression():
    """演示P2P消息压缩"""
    print("=" * 60)
    print("🔄 演示2: P2P消息压缩")
    print("=" * 60)
    
    compression = get_compression_integration()
    
    message = {
        "type": "chat",
        "from": "node_abc123",
        "to": "node_xyz789",
        "content": "这是一条需要在P2P网络中传输的消息，包含了大量的文本内容用于测试压缩效果。",
        "timestamp": 1714435200.0
    }
    
    print(f"原始消息大小: {len(json.dumps(message))} 字节")
    
    wrapped = await compression.wrap_p2p_message(message, "chat")
    print(f"压缩后大小: {len(wrapped)} 字节")
    print(f"压缩率: {(1 - len(wrapped) / len(json.dumps(message))) * 100:.1f}%\n")
    
    unwrapped, meta = await compression.unwrap_p2p_message(wrapped)
    print(f"解包后内容类型: {meta.get('content_type')}")
    print(f"压缩策略: {meta.get('strategy')}")


async def demo_context_compression():
    """演示智能上下文压缩"""
    print("=" * 60)
    print("💬 演示3: 智能上下文压缩")
    print("=" * 60)
    
    compressor = get_context_compressor()
    
    messages = [
        {"role": "user", "content": "你好，我有一个React性能问题需要帮助"},
        {"role": "assistant", "content": "好的，请描述一下你的问题"},
        {"role": "user", "content": "我的组件频繁重新渲染，导致页面卡顿"},
        {"role": "assistant", "content": "这通常是由于状态变化或props变化引起的。让我分析一下可能的原因：\n1. 状态不必要的更新\n2. 父组件重新渲染\n3. 函数引用变化"},
        {"role": "user", "content": "我检查了这些，但问题仍然存在"},
        {"role": "assistant", "content": "你是否使用了useMemo或useCallback来优化？这些Hook可以帮助减少不必要的重新渲染。让我给你一个例子：\n```javascript\nconst memoizedValue = useMemo(() => computeExpensiveValue(a, b), [a, b]);\n```"},
        {"role": "user", "content": "谢谢你的建议，我试试看"},
        {"role": "assistant", "content": "不客气！如果还有问题随时可以问我。"},
    ]
    
    for i, msg in enumerate(messages):
        await compressor.add_message({**msg, "id": f"msg_{i}"})
    
    stats = compressor.get_statistics()
    print(f"消息总数: {stats['total_messages']}")
    print(f"压缩消息数: {stats['compressed_messages']}")
    print(f"原始大小: {stats['original_size']} 字符")
    print(f"压缩后大小: {stats['compressed_size']} 字符")
    print(f"压缩率: {stats['compression_ratio'] * 100:.1f}%")
    print(f"Token数: {stats['token_count']}")
    print(f"重要性分布: {stats['importance_distribution']}")
    print(f"关键点: {stats['key_points_count']} 个")


async def demo_decorator_pattern():
    """演示装饰器模式"""
    print("=" * 60)
    print("🎀 演示4: 装饰器模式")
    print("=" * 60)
    
    @compress_response
    async def generate_response(prompt: str) -> str:
        return f"这是对 '{prompt}' 的详细回答，包含了大量的解释性文字和示例代码。"
    
    result = await generate_response("什么是压缩")
    print(f"响应类型: {type(result)}")
    print(f"响应内容: {result[:50]}...")
    
    @compress_p2p
    async def send_p2p_message(node_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "sent", "node": node_id, "message": message}
    
    msg = {"content": "测试消息", "type": "chat"}
    sent = await send_p2p_message("node_123", msg)
    print(f"发送消息: {sent}")


async def demo_compression_router():
    """演示压缩路由中间件"""
    print("=" * 60)
    print("🚀 演示5: 压缩路由中间件")
    print("=" * 60)
    
    router = get_compression_router()
    
    mock_response = {
        "content": "这是一个模拟的LLM响应，包含了详细的技术解释和代码示例。" * 5,
        "model": "test-model",
        "usage": {"prompt_tokens": 100, "completion_tokens": 200}
    }
    
    compressed = await compress_llm_response(mock_response, capability="writing")
    print(f"原始长度: {len(mock_response['content'])}")
    print(f"压缩后长度: {len(compressed['content'])}")
    print(f"压缩信息: {compressed.get('compression')}")


async def demo_adaptive_strategy():
    """演示自适应压缩策略"""
    print("=" * 60)
    print("🤖 演示6: 自适应压缩策略")
    print("=" * 60)
    
    compression = get_compression_integration()
    
    test_cases = [
        ("def hello():\n    print('Hello')", "代码"),
        ('{"name": "test", "value": 123}', "JSON"),
        ("# 标题\n\n这是一段Markdown文本", "Markdown"),
        ("2024-01-01 INFO: Server started", "日志"),
        ("用户问了一个关于React性能的问题，需要详细解释", "普通文本"),
    ]
    
    for text, label in test_cases:
        strategy = compression._select_strategy(text)
        result = await compression.compress_text(text, strategy=strategy)
        print(f"【{label}】策略: {strategy.value}, 压缩率: {result['compression_ratio'] * 100:.1f}%")


async def main():
    """运行所有演示"""
    await demo_text_compression()
    await demo_p2p_compression()
    await demo_context_compression()
    await demo_decorator_pattern()
    await demo_compression_router()
    await demo_adaptive_strategy()
    
    print("=" * 60)
    print("🎉 所有演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
