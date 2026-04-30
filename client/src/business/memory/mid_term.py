"""
Mid-term Memory - 检索级记忆

存储向量数据、文档内容和结构化数据，用于检索增强生成(RAG)。

特性：
- 中等延迟访问（亚秒级）
- 大容量存储
- 支持向量检索和全文检索
- 数据保留期：1小时~30天

包含：
- VectorMemory: 向量存储和检索
- DocumentMemory: 文档存储和检索
- DatabaseMemory: 结构化数据库访问
"""

import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class VectorEntry:
    """向量条目"""
    id: str
    content: str
    embedding: List[float]
    metadata: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())


@dataclass
class DocumentEntry:
    """文档条目"""
    id: str
    title: str
    content: str
    source: str
    metadata: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())


class VectorMemory:
    """向量存储 - 用于语义检索"""
    
    def __init__(self):
        self._logger = logger.bind(component="VectorMemory")
        self._vectors: Dict[str, VectorEntry] = {}
        self._dimension = 0
        
        # 尝试加载现有向量数据库集成
        self._vector_db = None
        self._init_vector_db()
        
        self._logger.info("VectorMemory 初始化完成")
    
    def _init_vector_db(self):
        """初始化向量数据库连接"""
        try:
            from business.fusion_rag.vector_db_integration import VectorDBIntegration
            self._vector_db = VectorDBIntegration()
            self._logger.info("✓ 集成 VectorDBIntegration")
        except Exception as e:
            self._logger.warning(f"VectorDBIntegration 加载失败，使用内存存储: {e}")
    
    def _compute_embedding(self, text: str) -> List[float]:
        """计算文本向量嵌入（简单实现）"""
        # 实际应用中应该调用嵌入模型
        # 这里使用简单的哈希作为占位符
        import hashlib
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [float((hash_val >> (i * 8)) & 0xff) / 255.0 for i in range(384)]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = (sum(a * a for a in vec1)) ** 0.5
        norm2 = (sum(b * b for b in vec2)) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def query(self, query: str, context: Dict = None) -> Dict:
        """
        查询向量存储（语义检索）
        
        Args:
            query: 查询内容
            context: 上下文
        
        Returns:
            查询结果
        """
        # 如果有外部向量DB，优先使用
        if self._vector_db:
            try:
                result = self._vector_db.search(query, top_k=5)
                if result.get("success") and result.get("results"):
                    return {
                        "success": True,
                        "content": result["results"][0].get("content", ""),
                        "confidence": result["results"][0].get("score", 0.5),
                        "type": "vector_search",
                        "source": "mid_term",
                        "results": result["results"]
                    }
            except Exception as e:
                self._logger.warning(f"VectorDB 查询失败，回退到内存存储: {e}")
        
        # 内存存储查询（简单实现）
        if not self._vectors:
            return {"success": False, "content": "", "confidence": 0.0}
        
        query_embedding = self._compute_embedding(query)
        
        # 查找最相似的向量
        best_match = None
        best_score = 0.0
        
        for entry_id, entry in self._vectors.items():
            score = self._cosine_similarity(query_embedding, entry.embedding)
            if score > best_score:
                best_score = score
                best_match = entry
        
        if best_match and best_score > 0.7:
            return {
                "success": True,
                "content": best_match.content,
                "confidence": min(best_score, 0.95),
                "type": "vector_search",
                "source": "mid_term"
            }
        
        return {"success": False, "content": "", "confidence": 0.0}
    
    def store(self, content: str, **kwargs) -> str:
        """
        存储向量
        
        Args:
            content: 要存储的内容
            **kwargs: 包含 id, metadata 等
        
        Returns:
            存储的ID
        """
        entry_id = kwargs.get("id", f"vec_{int(time.time())}")
        metadata = kwargs.get("metadata", {})
        
        # 如果有外部向量DB，优先使用
        if self._vector_db:
            try:
                result = self._vector_db.add(content, metadata=metadata)
                return result.get("id", entry_id)
            except Exception as e:
                self._logger.warning(f"VectorDB 存储失败，回退到内存存储: {e}")
        
        # 内存存储
        embedding = self._compute_embedding(content)
        self._dimension = len(embedding)
        
        self._vectors[entry_id] = VectorEntry(
            id=entry_id,
            content=content,
            embedding=embedding,
            metadata=metadata
        )
        
        return entry_id
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_vectors": len(self._vectors),
            "dimension": self._dimension,
            "using_external_db": self._vector_db is not None
        }


class DocumentMemory:
    """文档存储 - 用于全文检索"""
    
    def __init__(self):
        self._logger = logger.bind(component="DocumentMemory")
        self._documents: Dict[str, DocumentEntry] = {}
        
        # 尝试加载现有知识库
        self._knowledge_base = None
        self._init_knowledge_base()
        
        self._logger.info("DocumentMemory 初始化完成")
    
    def _init_knowledge_base(self):
        """初始化知识库连接"""
        try:
            from business.fusion_rag.knowledge_base import KnowledgeBase
            self._knowledge_base = KnowledgeBase()
            self._logger.info("✓ 集成 KnowledgeBase")
        except Exception as e:
            self._logger.warning(f"KnowledgeBase 加载失败，使用内存存储: {e}")
    
    def query(self, query: str, context: Dict = None) -> Dict:
        """
        查询文档存储（全文检索）
        
        Args:
            query: 查询内容
            context: 上下文
        
        Returns:
            查询结果
        """
        # 如果有外部知识库，优先使用
        if self._knowledge_base:
            try:
                result = self._knowledge_base.search(query, top_k=5)
                if result.get("success") and result.get("documents"):
                    return {
                        "success": True,
                        "content": result["documents"][0].get("content", ""),
                        "confidence": result["documents"][0].get("score", 0.5),
                        "type": "document_search",
                        "source": "mid_term",
                        "documents": result["documents"]
                    }
            except Exception as e:
                self._logger.warning(f"KnowledgeBase 查询失败，回退到内存存储: {e}")
        
        # 内存存储查询（简单实现）
        if not self._documents:
            return {"success": False, "content": "", "confidence": 0.0}
        
        query_lower = query.lower()
        best_match = None
        best_score = 0.0
        
        for entry in self._documents.values():
            content_lower = entry.content.lower()
            title_lower = entry.title.lower()
            
            # 简单匹配评分
            score = 0.0
            if query_lower in content_lower:
                score += 0.5
            if query_lower in title_lower:
                score += 0.3
            
            # 匹配词数加分
            query_words = set(query_lower.split())
            content_words = set(content_lower.split())
            overlap = len(query_words & content_words)
            score += overlap * 0.05
            
            if score > best_score:
                best_score = score
                best_match = entry
        
        if best_match and best_score > 0.3:
            return {
                "success": True,
                "content": best_match.content,
                "confidence": min(best_score, 0.9),
                "type": "document_search",
                "source": "mid_term",
                "title": best_match.title,
                "source_url": best_match.source
            }
        
        return {"success": False, "content": "", "confidence": 0.0}
    
    def store(self, content: str, **kwargs) -> str:
        """
        存储文档
        
        Args:
            content: 文档内容
            **kwargs: 包含 id, title, source, metadata 等
        
        Returns:
            存储的ID
        """
        entry_id = kwargs.get("id", f"doc_{int(time.time())}")
        title = kwargs.get("title", "")
        source = kwargs.get("source", "unknown")
        metadata = kwargs.get("metadata", {})
        
        # 如果有外部知识库，优先使用
        if self._knowledge_base:
            try:
                result = self._knowledge_base.add_document(
                    content=content,
                    title=title,
                    source=source,
                    metadata=metadata
                )
                return result.get("id", entry_id)
            except Exception as e:
                self._logger.warning(f"KnowledgeBase 存储失败，回退到内存存储: {e}")
        
        # 内存存储
        self._documents[entry_id] = DocumentEntry(
            id=entry_id,
            title=title,
            content=content,
            source=source,
            metadata=metadata
        )
        
        return entry_id
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_documents": len(self._documents),
            "using_external_kb": self._knowledge_base is not None
        }


class DatabaseMemory:
    """数据库存储 - 用于结构化数据查询"""
    
    def __init__(self):
        self._logger = logger.bind(component="DatabaseMemory")
        self._database_layer = None
        self._init_database_layer()
        
        self._logger.info("DatabaseMemory 初始化完成")
    
    def _init_database_layer(self):
        """初始化数据库层"""
        try:
            from business.fusion_rag.database_layer import DatabaseLayer
            self._database_layer = DatabaseLayer()
            self._logger.info("✓ 集成 DatabaseLayer")
        except Exception as e:
            self._logger.warning(f"DatabaseLayer 加载失败: {e}")
    
    def query(self, query: str, context: Dict = None) -> Dict:
        """
        查询数据库
        
        Args:
            query: 查询内容（可以是自然语言或SQL）
            context: 上下文
        
        Returns:
            查询结果
        """
        if not self._database_layer:
            return {"success": False, "content": "", "confidence": 0.0}
        
        try:
            result = self._database_layer.query(query)
            return {
                "success": result.get("success", False),
                "content": str(result.get("data", "")),
                "confidence": 0.7 if result.get("success") else 0.0,
                "type": "database_query",
                "source": "mid_term",
                "data": result.get("data")
            }
        except Exception as e:
            self._logger.error(f"数据库查询失败: {e}")
            return {"success": False, "content": "", "confidence": 0.0}
    
    def store(self, content: str, **kwargs) -> str:
        """
        存储数据到数据库
        
        Args:
            content: 数据内容（JSON格式或字典）
            **kwargs: 包含 table, operation 等
        
        Returns:
            操作结果
        """
        if not self._database_layer:
            self._logger.warning("DatabaseLayer 不可用")
            return ""
        
        try:
            table = kwargs.get("table", "")
            operation = kwargs.get("operation", "insert")
            
            result = self._database_layer.insert(table, content)
            return str(result.get("id", ""))
        except Exception as e:
            self._logger.error(f"数据库存储失败: {e}")
            return ""
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "connected": self._database_layer is not None
        }


# 单例模式
_vector_memory_instance = None
_document_memory_instance = None
_database_memory_instance = None

def get_vector_memory() -> VectorMemory:
    """获取向量存储实例"""
    global _vector_memory_instance
    if _vector_memory_instance is None:
        _vector_memory_instance = VectorMemory()
    return _vector_memory_instance

def get_document_memory() -> DocumentMemory:
    """获取文档存储实例"""
    global _document_memory_instance
    if _document_memory_instance is None:
        _document_memory_instance = DocumentMemory()
    return _document_memory_instance

def get_database_memory() -> DatabaseMemory:
    """获取数据库存储实例"""
    global _database_memory_instance
    if _database_memory_instance is None:
        _database_memory_instance = DatabaseMemory()
    return _database_memory_instance


if __name__ == "__main__":
    print("=" * 60)
    print("Mid-term Memory 测试")
    print("=" * 60)
    
    # 测试 VectorMemory
    vec_mem = get_vector_memory()
    
    vec_mem.store("人工智能是研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的一门新的技术科学。")
    vec_mem.store("机器学习是人工智能的一个分支，它使计算机系统能够从数据中学习和改进，而无需进行明确编程。")
    
    result = vec_mem.query("什么是机器学习？")
    print(f"向量检索 '什么是机器学习？': 成功={result['success']}, 置信度={result['confidence']:.2f}")
    
    # 测试 DocumentMemory
    doc_mem = get_document_memory()
    
    doc_mem.store("Python是一种高级编程语言，以其简洁的语法和强大的功能而闻名。", title="Python简介", source="wiki")
    
    result = doc_mem.query("Python是什么？")
    print(f"文档检索 'Python是什么？': 成功={result['success']}, 置信度={result['confidence']:.2f}")
    
    print("\n" + "=" * 60)