"""
测试增强记忆系统
Test Enhanced Memory System
"""

import time
from core.enhanced_memory import get_enhanced_memory_system


def test_enhanced_memory_system():
    """测试增强记忆系统"""
    print("=== 测试增强记忆系统 ===")

    # 1. 初始化系统
    print("\n1. 初始化增强记忆系统...")
    memory_system = get_enhanced_memory_system()
    print("✓ 增强记忆系统初始化成功")

    # 2. 获取初始统计信息
    stats = memory_system.get_stats()
    print(f"\n2. 初始统计信息:")
    print(f"   记忆项数量: {stats.get('memory_items', 0)}")
    print(f"   会话数量: {stats.get('sessions', 0)}")

    # 3. 开始新会话
    print("\n3. 开始新会话...")
    session_id = memory_system.start_session({
        "user": "测试用户",
        "purpose": "测试增强记忆系统"
    })
    print(f"✓ 会话开始成功，会话ID: {session_id}")

    # 4. 添加记忆
    print("\n4. 添加记忆...")
    test_memories = [
        ("Python是一种广泛使用的高级编程语言，由Guido van Rossum创建。", ["编程", "Python"]),
        ("JavaScript是一种用于Web开发的脚本语言，常用于前端开发。", ["编程", "JavaScript"]),
        ("机器学习是人工智能的一个分支，专注于开发能够从数据中学习的算法。", ["AI", "机器学习"]),
        ("深度学习是机器学习的一个子集，使用多层神经网络来模拟人脑的学习过程。", ["AI", "深度学习"]),
        ("数据结构是计算机中组织和存储数据的方式，如数组、链表、树等。", ["编程", "数据结构"])
    ]

    memory_ids = []
    for content, tags in test_memories:
        memory_id = memory_system.add_memory(content, tags)
        memory_ids.append(memory_id)
        print(f"  添加记忆成功，ID: {memory_id}")

    # 5. 搜索记忆
    print("\n5. 搜索记忆...")
    search_queries = ["Python", "AI", "数据结构"]
    for query in search_queries:
        results = memory_system.search_memory(query, limit=3)
        print(f"  搜索 '{query}' 结果 ({len(results)} 项):")
        for i, item in enumerate(results, 1):
            print(f"    {i}. {item.summary[:50]}...")

    # 6. 检索上下文
    print("\n6. 检索上下文...")
    context = memory_system.retrieve_context("机器学习", max_tokens=500)
    print(f"  检索上下文成功")
    print(f"  摘要数量: {len(context.get('summaries', []))}")
    print(f"  详细项目数量: {len(context.get('detailed_items', []))}")
    print(f"  使用令牌数: {context.get('tokens_used', 0)}")
    print(f"  优化统计: {context.get('optimization_stats', {})}")

    # 7. 结束会话
    print("\n7. 结束会话...")
    memory_system.end_session("测试会话完成，添加了5条记忆")
    print("✓ 会话结束成功")

    # 8. 测试跨会话持久化
    print("\n8. 测试跨会话持久化...")
    # 重新获取系统实例
    new_memory_system = get_enhanced_memory_system()
    # 搜索之前添加的记忆
    results = new_memory_system.search_memory("Python")
    print(f"  跨会话搜索结果: {len(results)} 项")
    if results:
        print(f"  找到记忆: {results[0].summary[:50]}...")

    # 9. 获取最新统计信息
    print("\n9. 最终统计信息:")
    final_stats = new_memory_system.get_stats()
    print(f"   记忆项数量: {final_stats.get('memory_items', 0)}")
    print(f"   会话数量: {final_stats.get('sessions', 0)}")

    # 10. 测试语义搜索
    print("\n10. 测试语义搜索...")
    semantic_results = new_memory_system.search_memory("编程语言", use_semantic=True)
    print(f"  语义搜索结果 ({len(semantic_results)} 项):")
    for i, item in enumerate(semantic_results, 1):
        print(f"    {i}. {item.summary[:50]}...")

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_enhanced_memory_system()
