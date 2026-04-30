"""
压缩集成演示文件（独立版）

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
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'client/src'))

from business.tools.caveman_tool import get_caveman_tool, CompressionLevel


async def demo_text_compression():
    """演示文本压缩功能"""
    print("=" * 60)
    print("📝 演示1: 文本压缩")
    print("=" * 60)
    
    caveman = get_caveman_tool()
    
    sample_text = """
The reason your React component is re-rendering is likely because you're creating a 
new object reference on each render cycle. When you pass an inline object as a prop, 
React's shallow comparison sees it as a different object every time, which triggers 
a re-render. I'd recommend using useMemo to memoize the object.
    """.strip()
    
    print(f"原始文本长度: {len(sample_text)}")
    print(f"原始文本:\n{sample_text}\n")
    
    levels = ["lite", "full", "ultra", "wenyan"]
    
    for level in levels:
        result = await caveman.execute(sample_text, level=level)
        ratio = result["compression_ratio"] * 100
        print(f"【{level.upper()}】压缩后长度: {result['compressed_length']} ({ratio:.1f}%)")
        print(f"压缩后:\n{result['compressed_text']}\n")


async def demo_compression_strategies():
    """演示不同内容类型的自适应压缩"""
    print("=" * 60)
    print("🤖 演示2: 自适应压缩策略")
    print("=" * 60)
    
    caveman = get_caveman_tool()
    
    test_cases = [
        ("def hello():\n    print('Hello')", "代码"),
        ('{"name": "test", "value": 123}', "JSON"),
        ("# 标题\n\n这是一段Markdown文本", "Markdown"),
        ("2024-01-01 INFO: Server started", "日志"),
        ("用户问了一个关于React性能的问题，需要详细解释", "普通文本"),
        ("好的，我来帮你解决这个问题。", "简短回复"),
    ]
    
    for text, label in test_cases:
        length = len(text)
        
        if length < 50:
            level = "lite"
        elif "def" in text or "code" in text.lower():
            level = "lite"
        elif "{" in text and "}" in text:
            level = "full"
        elif length > 100:
            level = "ultra"
        else:
            level = "full"
        
        result = await caveman.execute(text, level=level)
        print(f"【{label}】长度: {length}, 策略: {level}, 压缩率: {result['compression_ratio'] * 100:.1f}%")


async def demo_chat_context_compression():
    """演示对话上下文压缩"""
    print("=" * 60)
    print("💬 演示3: 对话上下文压缩")
    print("=" * 60)
    
    caveman = get_caveman_tool()
    
    messages = [
        {"role": "user", "content": "你好，我有一个React性能问题需要帮助"},
        {"role": "assistant", "content": "好的，请描述一下你的问题"},
        {"role": "user", "content": "我的组件频繁重新渲染，导致页面卡顿"},
        {"role": "assistant", "content": "这通常是由于状态变化或props变化引起的。让我分析一下可能的原因：\n1. 状态不必要的更新\n2. 父组件重新渲染\n3. 函数引用变化"},
        {"role": "user", "content": "我检查了这些，但问题仍然存在"},
        {"role": "assistant", "content": "你是否使用了useMemo或useCallback来优化？这些Hook可以帮助减少不必要的重新渲染。让我给你一个例子：\n```javascript\nconst memoizedValue = useMemo(() => computeExpensiveValue(a, b), [a, b]);\n```"},
    ]
    
    original_total = sum(len(msg["content"]) for msg in messages)
    print(f"原始总长度: {original_total} 字符")
    
    compressed_messages = []
    compressed_total = 0
    
    for i, msg in enumerate(messages):
        if i < len(messages) - 2:
            result = await caveman.execute(msg["content"], level="full")
            compressed_content = result["compressed_text"]
            compressed_total += len(compressed_content)
            compressed_messages.append({**msg, "content": compressed_content})
        else:
            compressed_total += len(msg["content"])
            compressed_messages.append(msg)
    
    print(f"压缩后总长度: {compressed_total} 字符")
    print(f"整体压缩率: {(1 - compressed_total / original_total) * 100:.1f}%")
    print(f"保留最近 {len(messages) - (len(messages) - 2)} 条消息完整")


async def demo_p2p_transmission():
    """演示P2P传输压缩"""
    print("=" * 60)
    print("🔄 演示4: P2P传输压缩")
    print("=" * 60)
    
    caveman = get_caveman_tool()
    
    message = {
        "type": "chat",
        "from": "node_abc123",
        "to": "node_xyz789",
        "content": "这是一条需要在P2P网络中传输的消息，包含了大量的文本内容用于测试压缩效果。",
        "timestamp": 1714435200.0
    }
    
    original_json = json.dumps(message)
    original_size = len(original_json)
    
    result = await caveman.execute(message["content"], level="full")
    compressed_msg = {**message, "content": result["compressed_text"]}
    compressed_json = json.dumps(compressed_msg)
    compressed_size = len(compressed_json)
    
    print(f"原始消息大小: {original_size} 字节")
    print(f"压缩后消息大小: {compressed_size} 字节")
    print(f"传输节省: {(1 - compressed_size / original_size) * 100:.1f}%")


async def main():
    """运行所有演示"""
    await demo_text_compression()
    await demo_compression_strategies()
    await demo_chat_context_compression()
    await demo_p2p_transmission()
    
    print("=" * 60)
    print("🎉 所有演示完成！")
    print("=" * 60)
    print("\n📊 压缩工具创新设计总结：")
    print("""
1. 语义感知压缩 - 根据内容类型智能选择压缩级别
2. 分层压缩策略 - 关键消息保留，次要消息压缩
3. 自适应压缩 - 根据文本特征自动调整
4. 多级别支持 - Lite/Full/Ultra/Wenyan四级压缩
5. 纯Python实现 - 无外部CLI依赖

应用场景：
- LLM响应压缩（节省token成本）
- P2P消息传输（减少带宽占用）
- 对话上下文管理（控制上下文窗口）
- 日志存储优化（减少存储占用）
    """)


if __name__ == "__main__":
    asyncio.run(main())
