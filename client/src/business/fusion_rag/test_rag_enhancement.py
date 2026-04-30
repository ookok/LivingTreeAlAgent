"""
测试 RAG 增强功能：PageIndex 和 Chroma 集成
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from loguru import logger
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)

from client.src.business.fusion_rag import PageIndex, ChromaAdapter, get_chroma


def test_page_index():
    """测试 PageIndex 无向量检索"""
    print("\n" + "=" * 60)
    print("[1] 测试 PageIndex 无向量检索")
    print("=" * 60)
    
    page_index = PageIndex()
    
    # 添加测试文档
    test_docs = [
        {
            "doc_id": "doc1",
            "content": """Python 是一种高级编程语言。
它广泛应用于数据科学、机器学习和 Web 开发。
Python 的语法简洁，易于学习。""",
            "metadata": {"category": "programming", "language": "python"}
        },
        {
            "doc_id": "doc2",
            "content": """机器学习是人工智能的一个分支。
它让计算机从数据中学习模式。
监督学习和无监督学习是两种主要类型。""",
            "metadata": {"category": "ai", "language": "english"}
        },
        {
            "doc_id": "doc3",
            "content": """深度学习是机器学习的一个子领域。
它使用神经网络来模拟人脑。
深度学习在图像识别和自然语言处理中表现出色。""",
            "metadata": {"category": "ai", "language": "chinese"}
        }
    ]
    
    for doc in test_docs:
        page_index.add_document(doc["doc_id"], doc["content"], doc["metadata"])
        print(f"✓ 添加文档: {doc['doc_id']}")
    
    # 测试搜索
    print("\n--- 搜索测试 ---")
    
    # 普通搜索
    results = page_index.search("Python 机器学习", top_k=3)
    print(f"搜索 'Python 机器学习' 找到 {len(results)} 条结果")
    for i, res in enumerate(results):
        print(f"  [{i+1}] {res['doc_id']} (分数: {res['score']:.2f})")
    
    # 带过滤的搜索
    results = page_index.search("学习", filters={"category": "ai"}, top_k=2)
    print(f"\n搜索 '学习' 且 category=ai 找到 {len(results)} 条结果")
    for i, res in enumerate(results):
        print(f"  [{i+1}] {res['doc_id']}")
    
    # 邻近搜索
    results = page_index.search_with_proximity("神经网络 机器学习", top_k=2)
    print(f"\n邻近搜索 '神经网络 机器学习' 找到 {len(results)} 条结果")
    for i, res in enumerate(results):
        print(f"  [{i+1}] {res['doc_id']} (邻近分数: {res['score']:.2f})")
    
    # 统计信息
    stats = page_index.get_stats()
    print(f"\n统计信息: {stats}")
    
    # 更新文档
    page_index.update_document("doc1", "Python 是最好的编程语言！", {"category": "programming"})
    print("✓ 更新文档: doc1")
    
    # 删除文档
    page_index.delete_document("doc2")
    print("✓ 删除文档: doc2")
    
    stats = page_index.get_stats()
    print(f"删除后统计: {stats}")
    
    print("\n✓ PageIndex 测试完成")


def test_chroma_adapter():
    """测试 Chroma 适配器"""
    print("\n" + "=" * 60)
    print("[2] 测试 Chroma 向量数据库适配器")
    print("=" * 60)
    
    chroma = get_chroma()
    
    # 添加测试文档
    documents = [
        "Python 是一种高级编程语言，广泛应用于数据科学",
        "机器学习是人工智能的一个分支，让计算机从数据中学习",
        "深度学习使用神经网络，在图像识别中表现出色"
    ]
    metadatas = [
        {"category": "programming", "source": "wiki"},
        {"category": "ai", "source": "wiki"},
        {"category": "ai", "source": "research"}
    ]
    
    ids = chroma.add_documents(documents, metadatas)
    print(f"✓ 添加了 {len(ids)} 条文档: {ids}")
    
    # 查询测试
    results = chroma.query(["Python 数据科学"], n_results=2)
    print(f"\n查询 'Python 数据科学' 找到 {len(results['ids'][0])} 条结果")
    for i, (doc_id, content) in enumerate(zip(results["ids"][0], results["documents"][0])):
        print(f"  [{i+1}] {doc_id}: {content[:30]}...")
    
    # 带过滤的查询
    results = chroma.query(["学习"], n_results=2, where={"category": "ai"})
    print(f"\n查询 '学习' 且 category=ai 找到 {len(results['ids'][0])} 条结果")
    
    # 统计信息
    stats = chroma.get_stats()
    print(f"\n统计信息: {stats}")
    
    # 测试更新
    chroma.update_documents([ids[0]], ["Python 是一种流行的编程语言"])
    print("✓ 更新文档")
    
    # 测试删除
    chroma.delete_documents([ids[1]])
    print("✓ 删除文档")
    
    # 最终统计
    count = chroma.count()
    print(f"\n剩余文档数: {count}")
    
    print("\n✓ Chroma 适配器测试完成")


def main():
    """主测试函数"""
    print("=" * 60)
    print("RAG 增强功能测试")
    print("1. PageIndex 无向量检索")
    print("2. Chroma 向量数据库适配器")
    print("=" * 60)
    
    test_page_index()
    test_chroma_adapter()
    
    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()