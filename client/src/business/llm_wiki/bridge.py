"""
Wiki-RAG Bridge

FusionRAG 与 LLM Wiki 之间的桥接模块，实现双向数据流动，集成DeepOnto本体推理。

作者: LivingTreeAI Team
日期: 2026-05-01
版本: 1.1.0
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    from deeponto.reasoner import DLReasoner
    from deeponto.embedding import OntologyEmbedding
    HAS_DEEPONTO = True
except ImportError:
    HAS_DEEPONTO = False


@dataclass
class WikiRAGResult:
    """Wiki-RAG 查询结果"""
    content: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    wiki_pages: List[Dict[str, Any]] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0


class WikiRAGBridge:
    """
    Wiki-RAG 桥接器
    
    核心功能：
    - 通过 FusionRAG 查询 Wiki 知识
    - 使用 FusionRAG 增强 Wiki 页面内容
    - 双向数据同步
    - 统一搜索体验
    - 本体推理增强（DeepOnto集成）
    """
    
    def __init__(self):
        """初始化桥接器"""
        self._fusion_rag = None
        self._wiki_core = None
        self._entity_recognizer = None
        self._ontology_reasoner = None
        self._entity_embedding_service = None
        
        self._init_dependencies()
        logger.info("WikiRAGBridge v1.1.0 初始化完成")
    
    def _init_dependencies(self):
        """初始化依赖模块"""
        try:
            from ..fusion_rag import get_fusion_rag_engine
            from .wiki_core import WikiCore
            from ..entity_management import get_entity_recognizer
            from ..deeponto_integration import get_ontology_reasoner, get_entity_embedding_service
            
            self._fusion_rag = get_fusion_rag_engine()
            self._wiki_core = WikiCore()
            self._entity_recognizer = get_entity_recognizer()
            
            self._ontology_reasoner = get_ontology_reasoner()
            self._ontology_reasoner.initialize()
            
            self._entity_embedding_service = get_entity_embedding_service()
            self._entity_embedding_service.initialize()
            
            logger.info("依赖模块加载成功（含DeepOnto集成）")
        except ImportError as e:
            logger.warning(f"依赖模块加载失败: {e}")
    
    async def query_wiki(self, query: str, include_rag: bool = True) -> WikiRAGResult:
        """
        通过 FusionRAG 查询 Wiki 知识
        
        Args:
            query: 查询文本
            include_rag: 是否包含 RAG 检索
            
        Returns:
            WikiRAGResult 查询结果
        """
        result = WikiRAGResult(content="", confidence=0.0)
        
        # 1. 在 Wiki 中搜索
        wiki_pages = []
        if self._wiki_core:
            pages = self._wiki_core.search_pages(query)
            wiki_pages = [{
                "id": page.id,
                "title": page.title,
                "summary": page.summary,
                "content": page.content[:200] + "..." if len(page.content) > 200 else page.content,
                "updated_at": page.updated_at,
            } for page in pages]
            result.wiki_pages = wiki_pages
        
        # 2. 使用 FusionRAG 检索（如果启用）
        rag_content = ""
        rag_sources = []
        if include_rag and self._fusion_rag:
            rag_result = await self._fusion_rag.query(query)
            rag_content = rag_result.content
            rag_sources = rag_result.sources
            result.confidence = rag_result.confidence
        
        # 3. 合并结果
        if wiki_pages:
            wiki_content = "\n\n".join(f"## {page['title']}\n\n{page['content']}" for page in wiki_pages)
        else:
            wiki_content = ""
        
        if rag_content:
            result.content = f"{wiki_content}\n\n---\n\n## 补充知识\n\n{rag_content}" if wiki_content else rag_content
        else:
            result.content = wiki_content
        
        result.sources = rag_sources
        
        # 4. 提取实体
        if self._entity_recognizer:
            entities = self._entity_recognizer.recognize(query)
            result.entities = [{
                "text": e.text,
                "type": e.entity_type.value,
                "confidence": e.confidence,
            } for e in entities.entities]
        
        return result
    
    async def enrich_page(self, page_id: str) -> Dict[str, Any]:
        """
        使用 FusionRAG 增强页面内容
        
        Args:
            page_id: 页面ID
            
        Returns:
            Dict 增强结果
        """
        if not self._wiki_core or not self._fusion_rag:
            return {"success": False, "message": "依赖模块不可用"}
        
        page = self._wiki_core.get_page(page_id)
        if not page:
            return {"success": False, "message": "页面不存在"}
        
        # 使用 FusionRAG 查询相关知识
        rag_result = await self._fusion_rag.query(page.title)
        
        # 提取页面中的实体
        entities = []
        if self._entity_recognizer:
            result = self._entity_recognizer.recognize(page.content)
            entities = [{
                "text": e.text,
                "type": e.entity_type.value,
                "confidence": e.confidence,
            } for e in result.entities]
        
        # 生成增强内容
        enhanced_content = self._generate_enhanced_content(page.content, rag_result.content)
        
        return {
            "success": True,
            "page_id": page_id,
            "original_content": page.content,
            "enhanced_content": enhanced_content,
            "related_knowledge": rag_result.content,
            "sources": rag_result.sources,
            "entities": entities,
        }
    
    def _generate_enhanced_content(self, original: str, additional: str) -> str:
        """
        生成增强内容
        
        Args:
            original: 原始内容
            additional: 附加知识
            
        Returns:
            str 增强后的内容
        """
        if not additional:
            return original
        
        # 在页面末尾添加相关知识
        enhanced = f"{original}\n\n---\n\n## 相关知识\n\n{additional}"
        return enhanced
    
    async def sync_wiki_to_rag(self, page_id: str) -> bool:
        """
        将 Wiki 页面同步到 RAG
        
        Args:
            page_id: 页面ID
            
        Returns:
            bool 是否成功
        """
        if not self._wiki_core or not self._fusion_rag:
            return False
        
        page = self._wiki_core.get_page(page_id)
        if not page:
            return False
        
        # 摄入页面内容到 FusionRAG
        result = await self._fusion_rag.ingest(
            data=page.content,
            data_type="markdown",
            metadata={
                "page_id": page.id,
                "page_title": page.title,
                "author": page.author,
                "updated_at": page.updated_at,
                "tags": page.tags,
            },
        )
        
        return result.get("success", False)
    
    async def sync_all_wiki_to_rag(self) -> Dict[str, Any]:
        """
        将所有 Wiki 页面同步到 RAG
        
        Returns:
            Dict 同步结果
        """
        if not self._wiki_core:
            return {"success": False, "message": "Wiki Core 不可用"}
        
        pages = self._wiki_core.get_all_pages()
        success_count = 0
        failed_count = 0
        
        for page in pages:
            try:
                result = await self.sync_wiki_to_rag(page.id)
                if result:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"同步页面失败 {page.id}: {e}")
                failed_count += 1
        
        return {
            "success": True,
            "total_pages": len(pages),
            "success_count": success_count,
            "failed_count": failed_count,
        }
    
    async def get_link_suggestions(self, page_id: str) -> List[Dict[str, Any]]:
        """
        获取页面的链接建议
        
        Args:
            page_id: 页面ID
            
        Returns:
            List 链接建议列表
        """
        if not self._wiki_core or not self._fusion_rag:
            return []
        
        page = self._wiki_core.get_page(page_id)
        if not page:
            return []
        
        # 提取页面中的实体
        entities = []
        if self._entity_recognizer:
            result = self._entity_recognizer.recognize(page.content)
            entities = [e.text for e in result.entities if e.entity_type.value not in ["date", "number", "email", "phone", "url"]]
        
        suggestions = []
        for entity in entities:
            # 检查是否已有链接
            if f"[[{entity}]]" in page.content:
                continue
            
            # 检查是否有对应的 Wiki 页面
            existing_page = self._wiki_core.get_page_by_title(entity)
            if existing_page:
                suggestions.append({
                    "entity": entity,
                    "action": "link",
                    "target_page_id": existing_page.id,
                    "target_page_title": existing_page.title,
                    "reason": f"「{entity}」已有对应的Wiki页面",
                    "confidence": 0.8,
                })
            else:
                suggestions.append({
                    "entity": entity,
                    "action": "create",
                    "suggested_title": entity,
                    "reason": f"建议为「{entity}」创建Wiki页面",
                    "confidence": 0.6,
                })
        
        return suggestions
    
    async def search_unified(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        统一搜索（同时搜索 Wiki 和 RAG）
        
        Args:
            query: 查询文本
            limit: 返回数量
            
        Returns:
            List 搜索结果列表
        """
        results = []
        
        # 搜索 Wiki
        if self._wiki_core:
            wiki_pages = self._wiki_core.search_pages(query)
            for page in wiki_pages[:limit//2]:
                results.append({
                    "type": "wiki",
                    "id": page.id,
                    "title": page.title,
                    "summary": page.summary,
                    "updated_at": page.updated_at,
                    "score": 0.8,
                })
        
        # 搜索 RAG
        if self._fusion_rag:
            rag_results = await self._fusion_rag.search_similar(query, limit//2)
            for result in rag_results:
                results.append({
                    "type": "rag",
                    "id": result.get("metadata", {}).get("document_id", ""),
                    "title": result.get("metadata", {}).get("title", ""),
                    "summary": result.get("content", "")[:100],
                    "score": result.get("score", 0.0),
                })
        
        # 排序并限制数量
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]


# 全局桥接器实例
_bridge_instance = None

def get_wiki_rag_bridge() -> WikiRAGBridge:
    """获取全局 Wiki-RAG 桥接器实例"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = WikiRAGBridge()
    return _bridge_instance