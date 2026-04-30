"""
Chroma 向量数据库适配器

提供：
1. 简单配置启动（单文件模式）
2. 文档添加/查询/更新/删除
3. 混合检索（向量 + 元数据过滤）
4. 与现有 fusion_rag 架构集成

策略：先用 Chroma 快速落地，后期可迁移到 Qdrant

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import os
import uuid
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger


class ChromaAdapter:
    """Chroma 向量数据库适配器"""
    
    _instance = None
    
    def __new__(cls, persist_directory: str = "./data/chroma"):
        if cls._instance is None:
            cls._instance = super(ChromaAdapter, cls).__new__(cls)
            cls._instance._initialized = False
            cls._instance._persist_directory = persist_directory
        return cls._instance
    
    def initialize(self):
        """初始化 Chroma 客户端"""
        if self._initialized:
            return
        
        try:
            import chromadb
            from chromadb.config import Settings
            
            # 确保目录存在
            os.makedirs(self._persist_directory, exist_ok=True)
            
            # 创建客户端（单文件模式）
            self._client = chromadb.Client(
                Settings(
                    persist_directory=self._persist_directory,
                    anonymized_telemetry=False
                )
            )
            
            # 获取或创建默认集合
            self._collection = self._client.get_or_create_collection(
                name="fusion_rag_knowledge_base",
                metadata={"description": "FusionRAG 知识库"}
            )
            
            self._initialized = True
            logger.info(f"Chroma 适配器初始化完成，存储目录: {self._persist_directory}")
            
        except ImportError:
            logger.warning("Chroma 未安装，使用内存模拟模式")
            self._use_fallback = True
            self._fallback_documents = {}
            self._fallback_embeddings = {}
            self._initialized = True
        
        except Exception as e:
            logger.error(f"Chroma 初始化失败: {e}")
            raise
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        添加文档到向量数据库
        
        Args:
            documents: 文档内容列表
            metadatas: 元数据列表
            ids: 文档 ID 列表（可选，自动生成）
        
        Returns:
            添加的文档 ID 列表
        """
        if not self._initialized:
            self.initialize()
        
        if self._use_fallback:
            return self._fallback_add(documents, metadatas, ids)
        
        # 生成 ID（如果未提供）
        if ids is None:
            ids = [f"doc_{uuid.uuid4().hex[:8]}" for _ in documents]
        
        # 添加到集合
        self._collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        # 持久化
        self._client.persist()
        
        logger.debug(f"添加了 {len(documents)} 条文档")
        return ids
    
    def query(
        self,
        query_texts: List[str],
        n_results: int = 10,
        where: Optional[Dict] = None,
        where_document: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        查询向量数据库
        
        Args:
            query_texts: 查询文本列表
            n_results: 返回数量
            where: 元数据过滤条件
            where_document: 文档内容过滤条件
        
        Returns:
            查询结果
        """
        if not self._initialized:
            self.initialize()
        
        if self._use_fallback:
            return self._fallback_query(query_texts, n_results, where)
        
        results = self._collection.query(
            query_texts=query_texts,
            n_results=n_results,
            where=where,
            where_document=where_document
        )
        
        logger.debug(f"查询返回 {len(results['ids'][0])} 条结果")
        return results
    
    def get_documents(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        获取文档
        
        Args:
            ids: 文档 ID 列表
            where: 元数据过滤条件
        
        Returns:
            文档数据
        """
        if not self._initialized:
            self.initialize()
        
        if self._use_fallback:
            return self._fallback_get(ids, where)
        
        return self._collection.get(
            ids=ids,
            where=where
        )
    
    def update_documents(
        self,
        ids: List[str],
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict]] = None
    ):
        """
        更新文档
        
        Args:
            ids: 文档 ID 列表
            documents: 新文档内容列表
            metadatas: 新元数据列表
        """
        if not self._initialized:
            self.initialize()
        
        if self._use_fallback:
            return self._fallback_update(ids, documents, metadatas)
        
        self._collection.update(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        
        self._client.persist()
        logger.debug(f"更新了 {len(ids)} 条文档")
    
    def delete_documents(self, ids: List[str]):
        """
        删除文档
        
        Args:
            ids: 文档 ID 列表
        """
        if not self._initialized:
            self.initialize()
        
        if self._use_fallback:
            return self._fallback_delete(ids)
        
        self._collection.delete(ids=ids)
        self._client.persist()
        logger.debug(f"删除了 {len(ids)} 条文档")
    
    def count(self) -> int:
        """获取文档数量"""
        if not self._initialized:
            self.initialize()
        
        if self._use_fallback:
            return len(self._fallback_documents)
        
        return self._collection.count()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._initialized:
            self.initialize()
        
        if self._use_fallback:
            return {
                "count": len(self._fallback_documents),
                "persisted": False,
                "storage_type": "memory_fallback"
            }
        
        return {
            "count": self._collection.count(),
            "persisted": True,
            "storage_type": "chroma",
            "directory": self._persist_directory
        }
    
    # ========== 降级实现 ==========
    
    def _fallback_add(self, documents, metadatas, ids):
        """内存降级模式 - 添加文档"""
        if ids is None:
            ids = [f"doc_{uuid.uuid4().hex[:8]}" for _ in documents]
        
        for i, doc_id in enumerate(ids):
            self._fallback_documents[doc_id] = {
                "content": documents[i],
                "metadata": metadatas[i] if metadatas else {}
            }
        
        return ids
    
    def _fallback_query(self, query_texts, n_results, where):
        """内存降级模式 - 查询"""
        results = []
        
        for query in query_texts:
            query_lower = query.lower()
            matched = []
            
            for doc_id, data in self._fallback_documents.items():
                # 简单匹配
                if query_lower in data["content"].lower():
                    # 应用过滤
                    if where:
                        match = True
                        for key, value in where.items():
                            if data["metadata"].get(key) != value:
                                match = False
                                break
                        if not match:
                            continue
                    
                    matched.append({
                        "id": doc_id,
                        "content": data["content"],
                        "metadata": data["metadata"],
                        "distance": 0.5  # 模拟距离
                    })
            
            # 简单排序
            matched.sort(key=lambda x: x["distance"])
            results.append(matched[:n_results])
        
        return {
            "ids": [[r["id"] for r in res] for res in results],
            "documents": [[r["content"] for r in res] for res in results],
            "metadatas": [[r["metadata"] for r in res] for res in results],
            "distances": [[r["distance"] for r in res] for res in results]
        }
    
    def _fallback_get(self, ids, where):
        """内存降级模式 - 获取文档"""
        if ids:
            docs = []
            for doc_id in ids:
                if doc_id in self._fallback_documents:
                    docs.append(self._fallback_documents[doc_id])
            return docs
        else:
            return list(self._fallback_documents.values())
    
    def _fallback_update(self, ids, documents, metadatas):
        """内存降级模式 - 更新文档"""
        for i, doc_id in enumerate(ids):
            if doc_id in self._fallback_documents:
                if documents:
                    self._fallback_documents[doc_id]["content"] = documents[i]
                if metadatas:
                    self._fallback_documents[doc_id]["metadata"] = metadatas[i]
    
    def _fallback_delete(self, ids):
        """内存降级模式 - 删除文档"""
        for doc_id in ids:
            if doc_id in self._fallback_documents:
                del self._fallback_documents[doc_id]
    
    @classmethod
    def get_instance(cls) -> "ChromaAdapter":
        """获取实例"""
        instance = cls()
        if not instance._initialized:
            instance.initialize()
        return instance


# 快捷函数
def get_chroma() -> ChromaAdapter:
    """获取 Chroma 适配器实例"""
    return ChromaAdapter.get_instance()