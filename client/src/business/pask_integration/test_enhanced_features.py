"""
测试增强版功能：LLM Wiki 集成和流式意图检测
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from loguru import logger
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)

from client.src.business.pask_integration import (
    EnhancedGlobalMemory,
    EnhancedIntentDetector,
    StreamingIntentDetector
)


async def test_enhanced_features():
    """测试增强版功能"""
    print("=" * 60)
    print("测试增强版功能")
    print("1. LLM Wiki 集成")
    print("2. 流式意图检测")
    print("=" * 60)
    
    # 测试 1: EnhancedGlobalMemory
    print("\n[1] 测试增强版全局记忆 (LLM Wiki 集成)")
    enhanced_memory = EnhancedGlobalMemory()
    
    # 添加知识
    enhanced_memory.add_entry(
        content="Python 是一种高级编程语言，广泛应用于数据科学和机器学习领域",
        entry_type="knowledge",
        metadata={"source": "LLM Wiki"}
    )
    enhanced_memory.add_entry(
        content="机器学习是人工智能的一个分支，让计算机从数据中学习",
        entry_type="knowledge",
        metadata={"source": "Wikipedia"}
    )
    
    # 搜索测试
    print("✓ 添加知识条目")
    
    # 搜索（带验证）
    results = enhanced_memory.search_with_verification("Python")
    print(f"✓ 搜索 'Python' 找到 {results['total_found']} 条结果")
    for i, result in enumerate(results["results"][:2]):
        entry = result["entry"]
        print(f"  [{i+1}] 类型: {entry['type']}, 分数: {result['score']:.2f}, 验证置信度: {result['verification']['confidence']:.2f}")
    
    # 统计信息
    stats = enhanced_memory.get_stats()
    print(f"✓ LLM Wiki 集成: {'已启用' if stats['wiki_integration_enabled'] else '未启用'}")
    print(f"✓ 本地条目数: {stats['local_entries']}")
    
    # 测试 2: EnhancedIntentDetector
    print("\n[2] 测试增强版意图检测器")
    detector = EnhancedIntentDetector()
    
    # 检测意图
    messages = [
        "你好，我想学习 Python",
        "有没有好的教程推荐？",
        "这个教程太难了"
    ]
    
    for msg in messages:
        result = detector.detect_intent(msg)
        intent = result["intent"]
        sentiment = result["sentiment"]
        
        print(f"\n✓ 消息: '{msg}'")
        print(f"  意图层次: {intent['level1']} → {intent['level2']} → {intent['level3']}")
        print(f"  置信度: {intent['confidence']:.2f}")
        print(f"  情感: {sentiment['type']} ({sentiment['confidence']:.2f})")
        
        if result["predicted_next_intent"]:
            pred = result["predicted_next_intent"]
            print(f"  预测下一个意图: {pred['level3']}")
    
    # 检测潜在需求
    needs = detector.detect_latent_needs()
    print(f"\n✓ 检测到 {len(needs)} 个潜在需求")
    for need in needs:
        print(f"  - {need['description']} (优先级: {(need['urgency'] + need['importance'])/2:.2f})")
    
    # 测试意图演化
    evolution = detector.get_intent_evolution()
    if evolution and evolution.has_evolved():
        print(f"\n✓ 意图演化路径: {' → '.join(evolution.evolution_path())}")
    
    # 测试 3: StreamingIntentDetector
    print("\n[3] 测试流式意图检测")
    stream_detector = StreamingIntentDetector()
    
    # 模拟流式输入
    chunks = ["你", "好", "，", "我", "想", "学", "习", "编", "程", "。"]
    
    for i, chunk in enumerate(chunks):
        result = await stream_detector.stream_detect(chunk)
        
        if result["complete"]:
            final_intent = result["final_intent"]["intent"]
            print(f"✓ 语句完成！最终意图: {final_intent['level1']} → {final_intent['level2']}")
        else:
            if i % 3 == 0:  # 每3个chunk输出一次状态
                print(f"  部分输入 '{stream_detector.get_buffer()}' → 意图: {result['partial_intent']['intent']} (置信度: {result['partial_intent']['confidence']:.2f})")
    
    # 重置并测试另一个语句
    stream_detector.reset()
    result = await stream_detector.stream_detect("帮我创建一个流程图。")
    print(f"\n✓ 流式检测完成: {'完整' if result['complete'] else '部分'}")
    if result["complete"]:
        print(f"  意图: {result['final_intent']['intent']['level1']} → {result['final_intent']['intent']['level2']}")
    
    print("\n" + "=" * 60)
    print("增强版功能测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_enhanced_features())