"""
嵌入向量生成模块
Embedding Generation Module

用于为记忆项生成语义嵌入向量，支持语义搜索
"""

import json
import math
from typing import List, Optional


class EmbeddingGenerator:
    """嵌入向量生成器"""

    def __init__(self, dimension: int = 128):
        self.dimension = dimension

    def generate_embedding(self, text: str) -> List[float]:
        """
        生成文本的嵌入向量
        使用简单的哈希算法生成固定维度的向量
        实际应用中应使用真实的嵌入模型
        """
        if not text:
            return [0.0] * self.dimension

        # 简单的基于哈希的嵌入生成
        # 实际应用中应使用如 Sentence-BERT 等模型
        embedding = [0.0] * self.dimension
        text = text.lower().strip()

        # 基于字符和词的哈希值生成向量
        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1

        # 填充向量
        for i, (char, count) in enumerate(char_counts.items()):
            if i >= self.dimension:
                break
            # 使用字符的 ASCII 值和出现次数生成向量值
            embedding[i] = (ord(char) * count) % 1.0

        # 归一化向量
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成嵌入向量
        """
        return [self.generate_embedding(text) for text in texts]


class SemanticSearcher:
    """语义搜索器"""

    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.embedding_generator = EmbeddingGenerator()

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """
        语义搜索
        返回搜索结果
        """
        # 生成查询的嵌入向量
        query_embedding = self.embedding_generator.generate_embedding(query)

        # 搜索相似的记忆项
        similar_items = self.vector_store.search_similar(query_embedding, top_k)

        # 构建搜索结果
        results = []
        for item_id, similarity in similar_items:
            results.append({
                "item_id": item_id,
                "similarity": similarity
            })

        return results

    def hybrid_search(self, query: str, top_k: int = 5) -> List[dict]:
        """
        混合搜索（关键词 + 语义）
        """
        # 这里可以结合关键词搜索和语义搜索
        # 简单实现：只返回语义搜索结果
        return self.search(query, top_k)


class EnhancedVectorStore:
    """增强的向量存储"""

    def __init__(self, store_path):
        from .core import VectorStore
        self.vector_store = VectorStore(store_path)
        self.embedding_generator = EmbeddingGenerator()

    def add_item(self, item_id: str, text: str):
        """
        添加项目到向量存储
        """
        # 生成嵌入向量
        embedding = self.embedding_generator.generate_embedding(text)
        # 保存到向量存储
        self.vector_store.add_embedding(item_id, embedding)

    def add_items(self, items: List[dict]):
        """
        批量添加项目到向量存储
        items: [{'id': str, 'text': str}]
        """
        for item in items:
            self.add_item(item['id'], item['text'])

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """
        搜索相似项目
        """
        # 生成查询的嵌入向量
        query_embedding = self.embedding_generator.generate_embedding(query)
        # 搜索相似项目
        similar_items = self.vector_store.search_similar(query_embedding, top_k)
        # 构建结果
        results = []
        for item_id, similarity in similar_items:
            results.append({
                "item_id": item_id,
                "similarity": similarity
            })
        return results

    def get_embedding(self, item_id: str) -> Optional[List[float]]:
        """
        获取项目的嵌入向量
        """
        return self.vector_store.get_embedding(item_id)

    def clear(self):
        """
        清空向量存储
        """
        # 简单实现：删除存储文件
        import os
        import shutil
        store_path = self.vector_store.store_path
        if store_path.exists():
            shutil.rmtree(store_path)
            store_path.mkdir(parents=True, exist_ok=True)
        self.vector_store._embeddings = {}
