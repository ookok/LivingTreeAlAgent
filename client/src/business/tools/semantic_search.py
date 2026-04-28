"""
SemanticSearch - 语义搜索模块

为 ToolRegistry 添加向量检索能力，提升工具发现的准确性。

功能：
1. 工具描述向量化
2. 查询向量化
3. 向量相似度匹配
4. 支持多种嵌入模型
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger
import numpy as np


@dataclass
class VectorStore:
    """向量存储"""
    tool_name: str
    embedding: np.ndarray
    metadata: Dict[str, Any]


class SemanticSearchEngine:
    """
    语义搜索引擎
    
    使用向量检索提升工具发现的准确性。
    
    支持的嵌入模型：
    - OpenAI Embeddings
    - Sentence Transformers
    - Local models
    """
    
    def __init__(self):
        self._logger = logger.bind(component="SemanticSearchEngine")
        self._vector_store: List[VectorStore] = []
        self._embedding_model = None
        self._init_embedding_model()
    
    def _init_embedding_model(self):
        """初始化嵌入模型"""
        try:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            self._logger.info("使用 Sentence Transformers 嵌入模型")
        except ImportError:
            self._logger.warning("Sentence Transformers 未安装，使用简单的关键词匹配")
    
    def add_tool(self, tool_name: str, description: str, metadata: Dict[str, Any] = None):
        """
        添加工具到向量存储
        
        Args:
            tool_name: 工具名称
            description: 工具描述
            metadata: 元数据
        """
        if self._embedding_model:
            embedding = self._embedding_model.encode(description)
            self._vector_store.append(VectorStore(
                tool_name=tool_name,
                embedding=embedding,
                metadata=metadata or {}
            ))
            self._logger.debug(f"工具 {tool_name} 已添加到向量存储")
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        语义搜索工具
        
        Args:
            query: 搜索查询词
            top_k: 返回前 k 个结果
            
        Returns:
            工具列表（按相似度排序）
        """
        if not self._vector_store:
            return []
        
        if self._embedding_model:
            return self._vector_search(query, top_k)
        else:
            return self._keyword_search(query, top_k)
    
    def _vector_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """向量搜索"""
        query_embedding = self._embedding_model.encode(query)
        
        # 计算相似度
        results = []
        for store in self._vector_store:
            similarity = self._cosine_similarity(query_embedding, store.embedding)
            results.append({
                "tool_name": store.tool_name,
                "similarity": similarity,
                "metadata": store.metadata
            })
        
        # 按相似度排序
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
        return results[:top_k]
    
    def _keyword_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """关键词搜索（降级方案）"""
        results = []
        query_lower = query.lower()
        
        for store in self._vector_store:
            score = 0
            description = store.metadata.get("description", "")
            
            # 匹配工具名称
            if query_lower in store.tool_name.lower():
                score += 3
            
            # 匹配描述
            if query_lower in description.lower():
                score += 2
            
            # 匹配参数
            params = store.metadata.get("parameters", {})
            for param_name in params.keys():
                if query_lower in param_name.lower():
                    score += 1
            
            if score > 0:
                results.append({
                    "tool_name": store.tool_name,
                    "similarity": score / 6,  # 归一化
                    "metadata": store.metadata
                })
        
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def clear(self):
        """清空向量存储"""
        self._vector_store = []
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_tools": len(self._vector_store),
            "embedding_model": "Sentence Transformers" if self._embedding_model else "Keyword Matching"
        }