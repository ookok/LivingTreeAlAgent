"""
测试向量存储管理器 - 支持 Chroma/Qdrant 一键切换
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from loguru import logger
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)

from client.src.business.fusion_rag import (
    VectorStoreManager,
    get_vector_store,
    switch_to_chroma,
    switch_to_qdrant
)


def test_vector_store_manager():
    """测试向量存储管理器"""
    print("\n" + "=" * 60)
    print("测试向量存储管理器")
    print("1. 基本操作测试")
    print("2. 性能监控测试")
    print("3. 一键切换后端测试")
    print("4. 性能评估测试")
    print("=" * 60)
    
    # 初始化管理器（默认使用 Chroma）
    manager = get_vector_store()
    print(f"✓ 初始化完成，当前后端: {manager.get_stats()['backend']}")
    
    # 测试基本操作
    print("\n--- 1. 基本操作测试 ---")
    
    # 添加文档
    docs = [
        "Python 是一种高级编程语言",
        "机器学习是人工智能的分支",
        "深度学习使用神经网络"
    ]
    metadatas = [
        {"category": "programming"},
        {"category": "ai"},
        {"category": "ai"}
    ]
    
    ids = manager.add_documents(docs, metadatas)
    print(f"✓ 添加文档: {ids}")
    
    # 查询测试
    results = manager.query(["Python 编程"], n_results=2)
    print(f"✓ 查询 'Python 编程' 找到 {len(results['ids'][0])} 条结果")
    
    # 带过滤的查询
    results = manager.query(["学习"], n_results=2, where={"category": "ai"})
    print(f"✓ 查询 '学习' 且 category=ai 找到 {len(results['ids'][0])} 条结果")
    
    # 更新文档
    manager.update_documents([ids[0]], ["Python 是最流行的编程语言"])
    print("✓ 更新文档")
    
    # 删除文档
    manager.delete_documents([ids[1]])
    print("✓ 删除文档")
    
    # 统计
    count = manager.count()
    print(f"✓ 当前文档数: {count}")
    
    # 测试性能监控
    print("\n--- 2. 性能监控测试 ---")
    
    # 执行多次查询以收集性能数据
    for i in range(5):
        manager.query([f"测试查询 {i}"])
    
    report = manager.get_performance_report()
    print(report)
    
    # 测试一键切换
    print("\n--- 3. 一键切换后端测试 ---")
    
    print(f"当前后端: {manager.get_stats()['backend']}")
    
    # 切换到 Qdrant
    success = switch_to_qdrant({"url": "http://localhost:6333"})
    if success:
        print("✓ 成功切换到 Qdrant")
    else:
        print("✗ 切换到 Qdrant 失败（可能未安装 Qdrant）")
    
    # 验证数据是否迁移
    count_after_switch = manager.count()
    print(f"切换后文档数: {count_after_switch}")
    
    # 切换回 Chroma
    success = switch_to_chroma()
    if success:
        print("✓ 成功切换回 Chroma")
    
    print(f"当前后端: {manager.get_stats()['backend']}")
    
    # 测试性能评估
    print("\n--- 4. 性能评估测试 ---")
    
    evaluation = manager.evaluate_performance()
    print(f"当前后端: {evaluation['current_backend']}")
    print(f"文档数量: {evaluation['document_count']}")
    print("建议:")
    for rec in evaluation["recommendations"]:
        print(f"  [{rec['level'].upper()}] {rec['message']}")
    
    print("\n" + "=" * 60)
    print("向量存储管理器测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    test_vector_store_manager()