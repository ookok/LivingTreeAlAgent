"""
RAGIntegrator - RAG 系统集成器

将 PASK 混合记忆系统与现有的 FusionRAG 集成。
"""

from typing import Dict, Any, Optional, List
from loguru import logger

from ..memory_model import HybridMemory
from business.fusion_rag import (
    FusionEngine,
    ExactCacheLayer,
    SessionCacheLayer
)


class RAGIntegrator:
    """RAG 系统集成器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RAGIntegrator, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self):
        """初始化集成器"""
        if self._initialized:
            return
        
        self._logger = logger.bind(component="RAGIntegrator")
        self._fusion_engine = None  # 延迟加载
        self._exact_cache = ExactCacheLayer()
        self._session_cache = SessionCacheLayer()
        
        self._initialized = True
        self._logger.info("RAGIntegrator 初始化完成")
    
    def _get_fusion_engine(self):
        """延迟加载 FusionEngine"""
        if self._fusion_engine is None:
            from business.fusion_rag.fusion_engine import FusionEngine
            self._fusion_engine = FusionEngine()
        return self._fusion_engine
    
    async def augment_query(self, query: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        使用 FusionRAG 增强查询
        
        Args:
            query: 用户查询
            context: 上下文
            
        Returns:
            增强后的查询和检索结果
        """
        try:
            fusion_engine = self._get_fusion_engine()
            
            # 使用 FusionRAG 进行检索增强
            result = await fusion_engine.query(
                query=query,
                context=context,
                enable_reranking=True,
                top_k=5
            )
            
            return {
                "query": query,
                "enhanced_query": result.get("enhanced_query", query),
                "results": result.get("results", []),
                "context": result.get("context", "")
            }
            
        except Exception as e:
            self._logger.error(f"查询增强失败: {e}")
            return {
                "query": query,
                "enhanced_query": query,
                "results": [],
                "context": ""
            }
    
    def update_cache(self, query: str, response: str, session_id: str = "default"):
        """更新缓存"""
        # 更新精确缓存
        self._exact_cache.set(query, response)
        
        # 更新会话缓存（使用 add_exchange）
        self._session_cache.add_exchange(session_id, query, response)
        
        self._logger.debug(f"已更新缓存: {query[:30]}...")
    
    def get_cached_response(self, query: str) -> Optional[str]:
        """获取缓存的响应"""
        # 先查精确缓存
        cached = self._exact_cache.get(query)
        if cached:
            return cached
        
        # 再查会话缓存
        results = self._session_cache.search(query)
        if results:
            return results[0].get("response")
        
        return None
    
    def sync_knowledge_to_rag(self, memory: HybridMemory):
        """将 PASK 记忆同步到 RAG"""
        try:
            # 获取全局知识
            knowledge_entries = memory.global_memory._entries
            
            for entry in knowledge_entries:
                if entry.type == "knowledge":
                    # 添加到 FusionRAG 知识库
                    self._fusion_engine.add_document(
                        content=entry.content,
                        metadata=entry.metadata
                    )
            
            self._logger.debug(f"已同步 {len(knowledge_entries)} 条知识到 RAG")
            
        except Exception as e:
            self._logger.warning(f"同步知识到 RAG 失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "exact_cache_size": len(self._exact_cache.memory_cache),
            "session_cache_size": len(self._session_cache.sessions),
            "fusion_engine_status": "active" if self._fusion_engine else "not_loaded"
        }
    
    @classmethod
    def get_instance(cls) -> "RAGIntegrator":
        """获取实例"""
        instance = cls()
        if not instance._initialized:
            instance.initialize()
        return instance