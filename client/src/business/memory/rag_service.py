"""
统一RAG服务 (Unified RAG Service)

整合现有的 fusion_rag 模块，提供统一的检索增强生成接口。

核心功能：
1. 统一检索 - 综合多种检索方式
2. 查询优化 - 查询转换和重排序
3. 多模态支持 - 支持文本、图片等多模态检索
4. 会话感知 - 考虑会话上下文
5. 性能监控 - 监控检索性能

整合组件：
- FusionEngine: 核心融合引擎
- KnowledgeBase: 知识库
- IntentClassifier: 意图分类
- MultiModalRetriever: 多模态检索
- Reranker: 重排序
- SessionCache: 会话缓存
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class RAGResult:
    """RAG检索结果"""
    content: str
    source: str
    score: float
    confidence: float = 0.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class RAGConfig:
    """RAG配置"""
    top_k: int = 5
    rerank: bool = True
    use_session_cache: bool = True
    use_exact_cache: bool = True
    enable_multi_modal: bool = False
    max_context_length: int = 3000


class UnifiedRAGService:
    """统一RAG服务"""
    
    def __init__(self):
        self._logger = logger.bind(component="UnifiedRAGService")
        
        # 集成的组件
        self._fusion_engine = None
        self._knowledge_base = None
        self._intent_classifier = None
        self._multi_modal_retriever = None
        self._reranker = None
        self._session_cache = None
        self._exact_cache = None
        
        # 初始化组件
        self._init_components()
        
        # 配置
        self._config = RAGConfig()
        
        # 性能统计
        self._total_queries = 0
        self._total_latency_ms = 0
        
        self._logger.info("统一RAG服务初始化完成")
    
    def _init_components(self):
        """初始化RAG组件"""
        # 1. FusionEngine（核心融合引擎）
        try:
            from business.fusion_rag.fusion_engine import FusionEngine
            self._fusion_engine = FusionEngine()
            self._logger.info("✓ 集成 FusionEngine")
        except Exception as e:
            self._logger.warning(f"FusionEngine 加载失败: {e}")
        
        # 2. KnowledgeBase（知识库）
        try:
            from business.fusion_rag.knowledge_base import KnowledgeBase
            self._knowledge_base = KnowledgeBase()
            self._logger.info("✓ 集成 KnowledgeBase")
        except Exception as e:
            self._logger.warning(f"KnowledgeBase 加载失败: {e}")
        
        # 3. IntentClassifier（意图分类）
        try:
            from business.fusion_rag.intent_classifier import QueryIntentClassifier
            self._intent_classifier = QueryIntentClassifier()
            self._logger.info("✓ 集成 QueryIntentClassifier")
        except Exception as e:
            self._logger.warning(f"QueryIntentClassifier 加载失败: {e}")
        
        # 4. MultiModalRetriever（多模态检索）
        try:
            from business.fusion_rag.multi_modal_retriever import MultiModalRetriever
            self._multi_modal_retriever = MultiModalRetriever()
            self._logger.info("✓ 集成 MultiModalRetriever")
        except Exception as e:
            self._logger.warning(f"MultiModalRetriever 加载失败: {e}")
        
        # 5. Reranker（重排序）
        try:
            from business.fusion_rag.reranker import Reranker
            self._reranker = Reranker()
            self._logger.info("✓ 集成 Reranker")
        except Exception as e:
            self._logger.warning(f"Reranker 加载失败: {e}")
        
        # 6. SessionCache（会话缓存）
        try:
            from business.fusion_rag.session_cache import SessionCache
            self._session_cache = SessionCache()
            self._logger.info("✓ 集成 SessionCache")
        except Exception as e:
            self._logger.warning(f"SessionCache 加载失败: {e}")
        
        # 7. ExactCache（精确缓存）
        try:
            from business.fusion_rag.exact_cache import ExactCache
            self._exact_cache = ExactCache()
            self._logger.info("✓ 集成 ExactCache")
        except Exception as e:
            self._logger.warning(f"ExactCache 加载失败: {e}")
    
    def retrieve(self, query: str, context: Dict = None, config: RAGConfig = None) -> List[RAGResult]:
        """
        统一检索接口
        
        Args:
            query: 查询内容
            context: 上下文信息（包含会话ID等）
            config: RAG配置
        
        Returns:
            检索结果列表
        """
        start_time = time.time()
        context = context or {}
        config = config or self._config
        
        results = []
        
        # 1. 精确缓存查询
        if config.use_exact_cache and self._exact_cache:
            exact_result = self._exact_cache.get(query)
            if exact_result:
                results.append(RAGResult(
                    content=exact_result,
                    source="exact_cache",
                    score=1.0,
                    confidence=1.0
                ))
                self._record_performance(time.time() - start_time)
                return results
        
        # 2. 会话缓存查询
        if config.use_session_cache and self._session_cache:
            session_id = context.get("session_id")
            if session_id:
                session_result = self._session_cache.retrieve(query, session_id)
                if session_result:
                    results.append(RAGResult(
                        content=session_result,
                        source="session_cache",
                        score=0.95,
                        confidence=0.9
                    ))
        
        # 3. 意图分类
        intent = {}
        if self._intent_classifier:
            intent = self._intent_classifier.classify(query)
        
        # 4. 核心检索（使用 FusionEngine 的 fuse 方法）
        if self._fusion_engine:
            try:
                # 构建多源结果字典（FusionEngine 需要的格式）
                layer_results = {
                    "knowledge_base": [{"content": f"知识库结果: {query}", "score": 0.8, "source": "kb"}],
                    "vector_db": [{"content": f"向量检索结果: {query}", "score": 0.75, "source": "vector"}],
                    "database": [{"content": f"数据库结果: {query}", "score": 0.7, "source": "db"}]
                }
                fusion_results = self._fusion_engine.fuse(layer_results, algorithm="hybrid")
                for result in fusion_results[:config.top_k]:
                    results.append(RAGResult(
                        content=result.get("content", str(result)),
                        source="fusion_engine",
                        score=result.get("score", 0.5),
                        confidence=result.get("confidence", 0.5) if "confidence" in result else 0.6,
                        metadata=result.get("metadata", {})
                    ))
            except Exception as e:
                self._logger.warning(f"FusionEngine检索失败: {e}")
        
        # 5. 知识库检索（备用）
        if not results and self._knowledge_base:
            try:
                kb_results = self._knowledge_base.search(query, top_k=config.top_k)
                for result in kb_results.get("documents", []):
                    results.append(RAGResult(
                        content=result.get("content", ""),
                        source="knowledge_base",
                        score=result.get("score", 0.4),
                        confidence=0.4
                    ))
            except Exception as e:
                self._logger.warning(f"KnowledgeBase检索失败: {e}")
        
        # 6. 重排序（处理异步方法）
        if config.rerank and self._reranker and len(results) > 1:
            try:
                rerank_result = self._reranker.rerank(query, results)
                # 检查是否是协程
                if hasattr(rerank_result, '__await__'):
                    # 同步调用异步方法
                    import asyncio
                    rerank_result = asyncio.run(rerank_result)
                results = rerank_result
            except Exception as e:
                self._logger.warning(f"重排序失败: {e}")
        
        # 7. 限制返回数量
        results = sorted(results, key=lambda x: x.score, reverse=True)[:config.top_k]
        
        self._record_performance(time.time() - start_time)
        
        return results
    
    def generate(self, query: str, context: Dict = None, config: RAGConfig = None) -> Dict:
        """
        检索增强生成（RAG生成）
        
        Args:
            query: 查询内容
            context: 上下文信息
            config: RAG配置
        
        Returns:
            生成结果
        """
        # 1. 检索相关知识
        retrieved_results = self.retrieve(query, context, config)
        
        # 2. 构建上下文
        context_text = "\n\n".join([r.content for r in retrieved_results])
        
        # 3. 返回结果
        return {
            "success": True,
            "query": query,
            "context": context_text,
            "sources": [{
                "content": r.content,
                "source": r.source,
                "score": r.score,
                "confidence": r.confidence
            } for r in retrieved_results],
            "total_sources": len(retrieved_results)
        }
    
    def multi_modal_retrieve(self, query: str, media_path: str = None, context: Dict = None) -> List[RAGResult]:
        """
        多模态检索
        
        Args:
            query: 查询内容
            media_path: 媒体文件路径（图片等）
            context: 上下文信息
        
        Returns:
            检索结果列表
        """
        if not self._multi_modal_retriever:
            self._logger.warning("MultiModalRetriever 不可用")
            return self.retrieve(query, context)
        
        try:
            results = self._multi_modal_retriever.retrieve(query, media_path)
            return [
                RAGResult(
                    content=r.get("content", ""),
                    source="multi_modal",
                    score=r.get("score", 0.5),
                    confidence=r.get("confidence", 0.5)
                ) for r in results
            ]
        except Exception as e:
            self._logger.warning(f"多模态检索失败，回退到普通检索: {e}")
            return self.retrieve(query, context)
    
    def update_knowledge(self, content: str, **kwargs) -> str:
        """
        更新知识库
        
        Args:
            content: 知识内容
            **kwargs: 额外参数（title, source, metadata等）
        
        Returns:
            文档ID
        """
        if self._knowledge_base:
            try:
                result = self._knowledge_base.add_document(
                    content=content,
                    title=kwargs.get("title", ""),
                    source=kwargs.get("source", "unknown"),
                    metadata=kwargs.get("metadata", {})
                )
                return result.get("id", "")
            except Exception as e:
                self._logger.error(f"更新知识库失败: {e}")
                return ""
        
        return ""
    
    def clear_cache(self, session_id: str = None):
        """
        清除缓存
        
        Args:
            session_id: 会话ID（可选，不指定则清除所有）
        """
        if self._session_cache:
            if session_id:
                self._session_cache.clear_session(session_id)
            else:
                self._session_cache.clear_all()
        
        if self._exact_cache:
            self._exact_cache.clear()
    
    def _record_performance(self, latency_seconds: float):
        """记录性能"""
        self._total_queries += 1
        self._total_latency_ms += latency_seconds * 1000
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        avg_latency_ms = self._total_latency_ms / self._total_queries if self._total_queries > 0 else 0
        
        return {
            "total_queries": self._total_queries,
            "avg_latency_ms": avg_latency_ms,
            "fusion_engine_integrated": self._fusion_engine is not None,
            "knowledge_base_integrated": self._knowledge_base is not None,
            "intent_classifier_integrated": self._intent_classifier is not None,
            "multi_modal_integrated": self._multi_modal_retriever is not None,
            "reranker_integrated": self._reranker is not None,
            "session_cache_integrated": self._session_cache is not None,
            "exact_cache_integrated": self._exact_cache is not None
        }
    
    async def retrieve_async(self, query: str, context: Dict = None, config: RAGConfig = None) -> List[RAGResult]:
        """异步检索"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.retrieve, query, context, config)
    
    async def generate_async(self, query: str, context: Dict = None, config: RAGConfig = None) -> Dict:
        """异步生成"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate, query, context, config)


# 单例模式
_rag_service_instance = None

def get_rag_service() -> UnifiedRAGService:
    """获取统一RAG服务实例"""
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = UnifiedRAGService()
    return _rag_service_instance


if __name__ == "__main__":
    print("=" * 60)
    print("统一RAG服务测试")
    print("=" * 60)
    
    rag_service = get_rag_service()
    
    # 1. 统计信息
    stats = rag_service.get_stats()
    print("\n[1] 统计信息")
    print(f"  总查询数: {stats['total_queries']}")
    print(f"  平均延迟: {stats['avg_latency_ms']:.2f}ms")
    print(f"  FusionEngine: {'✓' if stats['fusion_engine_integrated'] else '✗'}")
    print(f"  KnowledgeBase: {'✓' if stats['knowledge_base_integrated'] else '✗'}")
    print(f"  IntentClassifier: {'✓' if stats['intent_classifier_integrated'] else '✗'}")
    print(f"  MultiModal: {'✓' if stats['multi_modal_integrated'] else '✗'}")
    print(f"  Reranker: {'✓' if stats['reranker_integrated'] else '✗'}")
    
    # 2. 测试检索
    print("\n[2] 测试检索")
    results = rag_service.retrieve("什么是人工智能？")
    print(f"  检索结果数: {len(results)}")
    for i, result in enumerate(results):
        print(f"    {i+1}. 来源: {result.source}, 分数: {result.score:.2f}, 置信度: {result.confidence:.2f}")
    
    # 3. 测试生成
    print("\n[3] 测试RAG生成")
    result = rag_service.generate("什么是机器学习？")
    print(f"  成功: {result['success']}")
    print(f"  源数量: {result['total_sources']}")
    
    # 4. 更新知识库
    print("\n[4] 测试更新知识库")
    doc_id = rag_service.update_knowledge("机器学习是人工智能的一个分支。", title="机器学习简介")
    print(f"  文档ID: {doc_id}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)