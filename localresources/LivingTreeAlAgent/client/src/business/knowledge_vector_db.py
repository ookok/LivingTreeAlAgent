#!/usr/bin/env python3
"""
知识库增强 - 向量数据库集成
支持 Chroma/FAISS，提供语义搜索能力
"""

import hashlib
import math
import os
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class VectorStoreType(Enum):
    """向量存储类型"""
    CHROMA = "chroma"
    FAISS = "faiss"
    MEMORY = "memory"


class EmbeddingModel(Enum):
    """嵌入模型"""
    SENTENCE_BERT = "sentence_bert"
    TF_IDF = "tfidf"
    BM25 = "bm25"
    RANDOM = "random"


@dataclass
class Document:
    """文档单元"""
    doc_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    relevance_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "access_count": self.access_count,
        }


class SimpleEmbedding:
    """简单嵌入函数（无需外部依赖）"""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, text: str) -> List[float]:
        """生成伪嵌入向量"""
        import hashlib
        hash_val = hashlib.md5(text.encode()).digest()
        vec = []
        for i in range(self.dim):
            byte_val = hash_val[i % len(hash_val)]
            vec.append((byte_val / 255.0) * 2 - 1 + (i % 10) * 0.01)
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec]

    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class VectorDatabase:
    """
    向量数据库

    支持:
    1. Chroma (持久化)
    2. FAISS (高性能)
    3. 内存存储 (测试用)
    """

    def __init__(
        self,
        db_type: str = "memory",
        db_path: str = None,
        embedding_dim: int = 384,
    ):
        self.db_type = VectorStoreType(db_type) if isinstance(db_type, str) else db_type
        self.db_path = db_path or "./data/vector_db"
        self.embedding_dim = embedding_dim

        self._documents: Dict[str, Document] = {}
        self._embedding_func = SimpleEmbedding(dim=embedding_dim)
        self._next_id = 1

        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        if self.db_type == VectorStoreType.CHROMA:
            self._init_chroma()
        elif self.db_type == VectorStoreType.FAISS:
            self._init_faiss()
        elif self.db_type == VectorStoreType.MEMORY:
            pass
        else:
            raise ValueError(f"Unsupported db_type: {self.db_type}")

    def _init_chroma(self):
        """初始化 Chroma"""
        try:
            import chromadb
            os.makedirs(self.db_path, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=self.db_path)
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name="knowledge_base",
                metadata={"hnsw:space": "cosine"}
            )
        except ImportError:
            print("[VectorDB] chromadb 未安装，降级到内存存储")
            self.db_type = VectorStoreType.MEMORY

    def _init_faiss(self):
        """初始化 FAISS"""
        try:
            import faiss
            self._faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        except ImportError:
            print("[VectorDB] faiss 未安装，降级到内存存储")
            self.db_type = VectorStoreType.MEMORY

    def set_embedding_func(self, func: Callable[[str], List[float]]):
        """设置自定义嵌入函数"""
        self._embedding_func = func

    def add(
        self,
        content: str,
        metadata: Dict[str, Any] = None,
        doc_id: str = None,
    ) -> str:
        """添加文档"""
        if doc_id is None:
            doc_id = f"doc_{self._next_id:08d}"
            self._next_id += 1

        embedding = self._embedding_func.embed(content)

        document = Document(
            doc_id=doc_id,
            content=content,
            metadata=metadata or {},
            embedding=embedding,
        )

        self._documents[doc_id] = document

        if self.db_type == VectorStoreType.CHROMA:
            self._chroma_collection.add(
                documents=[content],
                metadatas=[metadata or {}],
                ids=[doc_id]
            )
        elif self.db_type == VectorStoreType.FAISS:
            import numpy as np
            self._faiss_index.add(np.array([embedding], dtype=np.float32))

        return doc_id

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Dict[str, Any] = None,
    ) -> List[Tuple[Document, float]]:
        """
        语义搜索

        Args:
            query: 查询文本
            top_k: 返回数量
            filters: 元数据过滤器

        Returns:
            文档列表及相似度分数
        """
        query_embedding = self._embedding_func.embed(query)
        results = []

        if self.db_type == VectorStoreType.CHROMA:
            chroma_results = self._chroma_collection.query(
                query_texts=[query],
                n_results=top_k * 2 if filters else top_k,
                where=filters,
            )
            for i, doc_id in enumerate(chroma_results["ids"][0]):
                if doc_id in self._documents:
                    doc = self._documents[doc_id]
                    score = 1 - chroma_results["distances"][0][i]
                    results.append((doc, score))

        elif self.db_type == VectorStoreType.FAISS:
            import numpy as np
            D, I = self._faiss_index.search(
                np.array([query_embedding], dtype=np.float32),
                min(top_k * 2, len(self._documents))
            )
            for i, idx in enumerate(I[0]):
                if idx < len(self._documents):
                    doc = list(self._documents.values())[idx]
                    score = float(D[0][i])
                    results.append((doc, score))

        else:
            for doc in self._documents.values():
                if filters:
                    if not all(doc.metadata.get(k) == v for k, v in filters.items()):
                        continue

                if doc.embedding:
                    score = self._embedding_func.cosine_similarity(
                        query_embedding, doc.embedding
                    )
                    if score > 0.3:
                        results.append((doc, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def get(self, doc_id: str) -> Optional[Document]:
        """获取文档"""
        doc = self._documents.get(doc_id)
        if doc:
            doc.access_count += 1
        return doc

    def update(
        self,
        doc_id: str,
        content: str = None,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """更新文档"""
        doc = self._documents.get(doc_id)
        if not doc:
            return False

        if content is not None:
            doc.content = content
            doc.embedding = self._embedding_func.embed(content)

        if metadata is not None:
            doc.metadata.update(metadata)

        doc.updated_at = datetime.now()
        return True

    def delete(self, doc_id: str) -> bool:
        """删除文档"""
        if doc_id in self._documents:
            del self._documents[doc_id]
            return True
        return False

    def count(self) -> int:
        """获取文档数量"""
        return len(self._documents)

    def clear(self):
        """清空所有文档"""
        self._documents.clear()
        if self.db_type == VectorStoreType.CHROMA:
            try:
                self._chroma_client.delete_collection("knowledge_base")
                self._chroma_collection = self._chroma_client.get_or_create_collection(
                    name="knowledge_base"
                )
            except Exception:
                pass

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_documents": len(self._documents),
            "db_type": self.db_type.value,
            "embedding_dim": self.embedding_dim,
        }


class KnowledgeBaseVectorStore:
    """知识库向量存储"""

    def __init__(self, db_path: str = None):
        self._db = VectorDatabase(
            db_type="memory",
            db_path=db_path,
        )
        self._init_sample_data()

    def _init_sample_data(self):
        """初始化示例数据"""
        sample_knowledge = [
            {
                "content": "Python 是一种高级编程语言，由 Guido van Rossum 创造于 1991 年",
                "metadata": {"category": "programming", "language": "python"}
            },
            {
                "content": "Python 支持多种编程范式，包括面向对象、函数式和过程式编程",
                "metadata": {"category": "programming", "language": "python"}
            },
            {
                "content": "Python 有丰富的标准库，适用于数据分析、人工智能等领域",
                "metadata": {"category": "programming", "language": "python"}
            },
            {
                "content": "深度学习是机器学习的一个分支，使用多层神经网络",
                "metadata": {"category": "ai", "topic": "deep_learning"}
            },
            {
                "content": "自然语言处理 (NLP) 是人工智能的一个分支，处理文本数据",
                "metadata": {"category": "ai", "topic": "nlp"}
            },
        ]

        for item in sample_knowledge:
            self._db.add(
                content=item["content"],
                metadata=item["metadata"],
            )

        print(f"[KnowledgeBase] 已初始化 {len(sample_knowledge)} 条知识")

    def add_knowledge(
        self,
        content: str,
        category: str = None,
        topic: str = None,
        **metadata
    ) -> str:
        """添加知识"""
        meta = metadata.copy()
        if category:
            meta["category"] = category
        if topic:
            meta["topic"] = topic

        return self._db.add(content=content, metadata=meta)

    def search_knowledge(
        self,
        query: str,
        top_k: int = 5,
        category: str = None,
    ) -> List[Dict[str, Any]]:
        """搜索知识"""
        filters = {"category": category} if category else None
        results = self._db.search(query=query, top_k=top_k, filters=filters)

        return [
            {
                "content": doc.content,
                "score": score,
                "metadata": doc.metadata,
                "doc_id": doc.doc_id,
            }
            for doc, score in results
        ]

    def update_knowledge(
        self,
        doc_id: str,
        content: str = None,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """更新知识"""
        return self._db.update(doc_id=doc_id, content=content, metadata=metadata)

    def delete_knowledge(self, doc_id: str) -> bool:
        """删除知识"""
        return self._db.delete(doc_id=doc_id)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return self._db.get_stats()


def test_vector_database():
    """测试向量数据库"""
    print("=== 测试向量数据库 ===")

    db = VectorDatabase(db_type="memory")

    print("\n1. 测试添加文档")
    doc_ids = []
    for i in range(5):
        doc_id = db.add(
            content=f"这是第 {i+1} 个测试文档，内容关于 Python 编程",
            metadata={"category": "programming", "index": i}
        )
        doc_ids.append(doc_id)
        print(f"  添加文档: {doc_id}")

    print("\n2. 测试搜索")
    results = db.search("Python 编程", top_k=3)
    print(f"  找到 {len(results)} 个结果:")
    for doc, score in results:
        print(f"    - {doc.content[:40]}... (分数: {score:.3f})")

    print("\n3. 测试统计")
    stats = db.get_stats()
    print(f"  统计: {stats}")

    print("\n向量数据库测试完成！")


def test_knowledge_base():
    """测试知识库"""
    print("\n=== 测试知识库向量存储 ===")

    kb = KnowledgeBaseVectorStore()

    print("\n1. 测试知识库统计")
    stats = kb.get_stats()
    print(f"  统计: {stats}")

    print("\n2. 测试知识搜索")
    queries = ["Python", "深度学习", "编程语言"]

    for query in queries:
        results = kb.search_knowledge(query)
        print(f"\n  查询: {query}")
        print(f"  找到 {len(results)} 条知识:")
        for r in results[:3]:
            print(f"    - {r['content'][:50]}... (分数: {r['score']:.3f})")

    print("\n3. 测试添加知识")
    new_id = kb.add_knowledge(
        content="机器学习是人工智能的一个分支，通过数据训练模型",
        category="ai",
        topic="machine_learning"
    )
    print(f"  添加知识: {new_id}")

    print("\n4. 测试更新知识")
    success = kb.update_knowledge(new_id, content="更新后的机器学习知识")
    print(f"  更新成功: {success}")

    print("\n5. 测试知识库搜索（新添加的知识）")
    results = kb.search_knowledge("机器学习")
    print(f"  找到 {len(results)} 条知识:")
    for r in results[:3]:
        print(f"    - {r['content'][:50]}... (分数: {r['score']:.3f})")

    print("\n知识库向量存储测试完成！")


if __name__ == "__main__":
    test_vector_database()
    test_knowledge_base()