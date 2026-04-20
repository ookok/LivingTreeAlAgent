#!/usr/bin/env python3
"""
知识库增强 - 向量数据库集成
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
_root = Path(__file__).parent
sys.path.insert(0, str(_root))


class VectorDatabaseAdapter:
    """向量数据库适配器"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or str(_root / "data" / "vector_db")
        os.makedirs(self.db_path, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化向量数据库"""
        try:
            import chromadb
            self.client = chromadb.PersistentClient(path=self.db_path)
            self.collection = self.client.get_or_create_collection(
                name="knowledge_base",
                metadata={"hnsw:space": "cosine"}
            )
            print(f"[VectorDB] 初始化成功: {self.db_path}")
        except ImportError:
            print("[VectorDB] chromadb 未安装，使用内存存储")
            self.client = None
            self.collection = None
            self._memory_store = {}
    
    def add_document(self, text, metadata=None):
        """添加文档到向量数据库"""
        if not text:
            return False
        
        try:
            if self.collection:
                import hashlib
                doc_id = hashlib.md5(text.encode()).hexdigest()
                self.collection.add(
                    documents=[text],
                    metadatas=[metadata or {}],
                    ids=[doc_id]
                )
                return True
            else:
                # 内存存储
                import hashlib
                doc_id = hashlib.md5(text.encode()).hexdigest()
                self._memory_store[doc_id] = (text, metadata)
                return True
        except Exception as e:
            print(f"[VectorDB] 添加文档失败: {e}")
            return False
    
    def search(self, query, top_k=3):
        """向量搜索"""
        if not query:
            return []
        
        try:
            if self.collection:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=top_k
                )
                return [
                    {
                        "content": doc,
                        "score": results["distances"][0][i],
                        "metadata": results["metadatas"][0][i]
                    }
                    for i, doc in enumerate(results["documents"][0])
                ]
            else:
                # 简单的文本匹配
                results = []
                for doc_id, (text, metadata) in self._memory_store.items():
                    score = self._calculate_similarity(query, text)
                    if score > 0.3:
                        results.append({
                            "content": text,
                            "score": score,
                            "metadata": metadata
                        })
                results.sort(key=lambda x: x["score"], reverse=True)
                return results[:top_k]
        except Exception as e:
            print(f"[VectorDB] 搜索失败: {e}")
            return []
    
    def _calculate_similarity(self, query, text):
        """简单的文本相似度计算"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, query, text).ratio()
    
    def get_stats(self):
        """获取统计信息"""
        if self.collection:
            try:
                count = self.collection.count()
                return {"count": count, "type": "chromadb"}
            except Exception:
                pass
        return {"count": len(self._memory_store), "type": "memory"}


class KnowledgeBaseEnhancer:
    """知识库增强器"""
    
    def __init__(self):
        self.vector_db = VectorDatabaseAdapter()
        self._init_sample_data()
    
    def _init_sample_data(self):
        """初始化示例数据"""
        sample_knowledge = [
            "Python 是一种高级编程语言，由 Guido van Rossum 创造于 1991 年",
            "Python 支持多种编程范式，包括面向对象、函数式和过程式编程",
            "Python 有丰富的标准库，适用于数据分析、人工智能等领域",
            "Python 是一种解释型语言，不需要编译就可以运行",
            "Python 在人工智能和机器学习领域广泛应用"
        ]
        
        for i, knowledge in enumerate(sample_knowledge):
            self.vector_db.add_document(
                knowledge,
                metadata={"category": "programming", "language": "python", "id": i+1}
            )
        
        print(f"[KnowledgeBase] 初始化 {len(sample_knowledge)} 条示例知识")
    
    def add_knowledge(self, text, metadata=None):
        """添加知识"""
        return self.vector_db.add_document(text, metadata)
    
    def search_knowledge(self, query, top_k=3):
        """搜索知识"""
        return self.vector_db.search(query, top_k)
    
    def get_stats(self):
        """获取统计信息"""
        return self.vector_db.get_stats()


def test_knowledge_base():
    """测试知识库"""
    print("=== 测试知识库增强 ===")
    
    enhancer = KnowledgeBaseEnhancer()
    
    print("\n1. 测试知识库统计")
    stats = enhancer.get_stats()
    print(f"  知识库类型: {stats['type']}")
    print(f"  知识数量: {stats['count']}")
    
    print("\n2. 测试知识搜索")
    queries = ["Python 是什么", "Python 应用领域", "Python 特点"]
    
    for query in queries:
        results = enhancer.search_knowledge(query)
        print(f"\n  查询: {query}")
        for i, result in enumerate(results, 1):
            print(f"    {i}. {result['content']} (相似度: {result['score']:.3f})")
    
    print("\n3. 测试添加知识")
    new_knowledge = "Python 3.10 版本引入了结构模式匹配功能"
    success = enhancer.add_knowledge(
        new_knowledge,
        metadata={"category": "programming", "language": "python", "version": "3.10"}
    )
    print(f"  添加知识: {'成功' if success else '失败'}")
    
    print("\n4. 测试更新后的搜索")
    results = enhancer.search_knowledge("Python 3.10")
    print("  查询: Python 3.10")
    for i, result in enumerate(results, 1):
        print(f"    {i}. {result['content']} (相似度: {result['score']:.3f})")
    
    print("\n知识库增强测试完成！")


if __name__ == "__main__":
    test_knowledge_base()