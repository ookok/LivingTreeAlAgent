"""统一记忆层 - 整合所有记忆相关功能"""

from typing import Optional, Dict, Any, List
import asyncio
from enum import Enum

class MemoryStoreType(Enum):
    SHARED = "shared"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    SPECIALIZED = "specialized"

class MemoryRetrieverType(Enum):
    DEFAULT = "default"
    SEMANTIC = "semantic"
    KNOWLEDGE_GRAPH = "knowledge_graph"

class UnifiedMemoryLayer:
    """统一记忆层"""
    
    def __init__(self):
        self._retrievers: Dict[str, Any] = {}
        self._stores: Dict[str, Any] = {}
        self._initialized = False
    
    async def initialize(self):
        """初始化记忆层"""
        if self._initialized:
            return
        
        from .intelligent_memory_retriever import IntelligentMemoryRetriever
        from .shared_memory_system import SharedMemorySystem
        
        self._retrievers[MemoryRetrieverType.DEFAULT.value] = IntelligentMemoryRetriever()
        self._stores[MemoryStoreType.SHARED.value] = SharedMemorySystem()
        
        await asyncio.gather(
            self._retrievers[MemoryRetrieverType.DEFAULT.value].initialize(),
            self._stores[MemoryStoreType.SHARED.value].initialize()
        )
        
        self._initialized = True
    
    async def retrieve(self, query: str, retriever_type: MemoryRetrieverType = MemoryRetrieverType.DEFAULT, **kwargs) -> List[Dict[str, Any]]:
        """统一检索接口"""
        if not self._initialized:
            await self.initialize()
        
        retriever = self._retrievers.get(retriever_type.value)
        if not retriever:
            raise ValueError(f"Unknown retriever type: {retriever_type}")
        
        return await retriever.retrieve(query, **kwargs)
    
    async def store(self, content: str, store_type: MemoryStoreType = MemoryStoreType.SHARED, **kwargs) -> bool:
        """统一存储接口"""
        if not self._initialized:
            await self.initialize()
        
        store = self._stores.get(store_type.value)
        if not store:
            raise ValueError(f"Unknown store type: {store_type}")
        
        return await store.store(content, **kwargs)
    
    async def delete(self, content_id: str, store_type: MemoryStoreType = MemoryStoreType.SHARED) -> bool:
        """统一删除接口"""
        if not self._initialized:
            await self.initialize()
        
        store = self._stores.get(store_type.value)
        if not store:
            raise ValueError(f"Unknown store type: {store_type}")
        
        return await store.delete(content_id)
    
    async def update(self, content_id: str, content: str, store_type: MemoryStoreType = MemoryStoreType.SHARED) -> bool:
        """统一更新接口"""
        if not self._initialized:
            await self.initialize()
        
        store = self._stores.get(store_type.value)
        if not store:
            raise ValueError(f"Unknown store type: {store_type}")
        
        return await store.update(content_id, content)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "initialized": self._initialized,
            "retrievers": list(self._retrievers.keys()),
            "stores": list(self._stores.keys()),
        }
        return stats

# 全局单例
_memory_layer_instance = None

def get_unified_memory_layer() -> UnifiedMemoryLayer:
    """获取统一记忆层实例"""
    global _memory_layer_instance
    if _memory_layer_instance is None:
        _memory_layer_instance = UnifiedMemoryLayer()
    return _memory_layer_instance