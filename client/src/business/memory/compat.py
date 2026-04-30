"""
兼容性层 - 为旧代码提供迁移接口

这个模块提供了与旧API兼容的接口，允许逐步迁移到新的统一记忆层。

旧API映射：
- business.knowledge_base → business.memory.compat.KnowledgeBase
- business.fusion_rag → business.memory.compat.FusionRAG
- business.error_memory → business.memory.compat.ErrorMemory (已直接集成)

使用方式：
```python
# 旧代码（将逐步淘汰）
from business.memory.compat import KnowledgeBase
kb = KnowledgeBase()
result = kb.search("查询")

# 新代码（推荐）
from business.memory import query_memory
result = query_memory("查询")
```
"""

import warnings
from typing import Dict, Any, Optional, List


class KnowledgeBase:
    """兼容性包装器 - 模拟旧 KnowledgeBase API"""
    
    def __init__(self):
        warnings.warn(
            "business.memory.compat.KnowledgeBase 已废弃，请使用 business.memory.query_memory()",
            DeprecationWarning,
            stacklevel=2
        )
        from . import get_memory_router
        self._router = get_memory_router()
    
    def search(self, query: str, **kwargs) -> Dict:
        """模拟旧搜索接口"""
        result = self._router.query(query)
        return {
            "success": result.get("success", False),
            "documents": [{
                "content": result.get("content", ""),
                "score": result.get("confidence", 0.0)
            }] if result.get("success") else [],
            "confidence": result.get("confidence", 0.0)
        }
    
    def add_document(self, content: str, **kwargs) -> Dict:
        """模拟旧添加文档接口"""
        from . import store_memory
        doc_id = store_memory(content, memory_type="mid_term", **kwargs)
        return {"success": True, "id": doc_id}
    
    def get_statistics(self) -> Dict:
        """模拟旧统计接口"""
        return {"total_documents": 0, "total_queries": 0}


class FusionRAG:
    """兼容性包装器 - 模拟旧 FusionRAG API"""
    
    def __init__(self):
        warnings.warn(
            "business.memory.compat.FusionRAG 已废弃，请使用 business.memory.query_memory()",
            DeprecationWarning,
            stacklevel=2
        )
        from . import get_memory_router
        self._router = get_memory_router()
    
    def query(self, query: str, **kwargs) -> Dict:
        """模拟旧查询接口"""
        result = self._router.query(query, kwargs)
        return {
            "success": result.get("success", False),
            "answer": result.get("content", ""),
            "sources": result.get("results", []),
            "confidence": result.get("confidence", 0.0)
        }
    
    def add_to_index(self, content: str, **kwargs) -> str:
        """模拟旧添加索引接口"""
        from . import store_memory
        return store_memory(content, memory_type="mid_term", **kwargs)


class VectorDBIntegration:
    """兼容性包装器 - 模拟旧 VectorDBIntegration API"""
    
    def __init__(self):
        warnings.warn(
            "business.memory.compat.VectorDBIntegration 已废弃，请使用 business.memory.get_vector_memory()",
            DeprecationWarning,
            stacklevel=2
        )
        from .mid_term import get_vector_memory
        self._vector_memory = get_vector_memory()
    
    def search(self, query: str, **kwargs) -> Dict:
        """模拟旧搜索接口"""
        result = self._vector_memory.query(query)
        return {
            "success": result.get("success", False),
            "results": [{
                "content": result.get("content", ""),
                "score": result.get("confidence", 0.0)
            }] if result.get("success") else []
        }
    
    def add(self, content: str, **kwargs) -> Dict:
        """模拟旧添加接口"""
        doc_id = self._vector_memory.store(content, **kwargs)
        return {"success": True, "id": doc_id}


# 便捷函数（模拟旧API）
def search_knowledge(query: str, **kwargs) -> Dict:
    """便捷搜索函数"""
    warnings.warn(
        "business.memory.compat.search_knowledge 已废弃，请使用 business.memory.query_memory()",
        DeprecationWarning,
        stacklevel=2
    )
    from . import query_memory
    return query_memory(query, kwargs)


def add_knowledge(content: str, **kwargs) -> str:
    """便捷添加函数"""
    warnings.warn(
        "business.memory.compat.add_knowledge 已废弃，请使用 business.memory.store_memory()",
        DeprecationWarning,
        stacklevel=2
    )
    from . import store_memory
    return store_memory(content, **kwargs)


__all__ = [
    "KnowledgeBase",
    "FusionRAG",
    "VectorDBIntegration",
    "search_knowledge",
    "add_knowledge"
]