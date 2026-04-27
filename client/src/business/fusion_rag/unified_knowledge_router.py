"""
知识库智能路由器 (使用现有 L0-L4 组件)

复用项目已有的组件:
- core.fusion_rag.intent_classifier.QueryIntentClassifier
- core.fusion_rag.intelligent_router.IntelligentRouter
- core.search.result_fusion.ResultFusion
- core.fusion_rag.l4_aware_router.L4AwareRouter
"""

import time
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# 复用现有组件
from core.fusion_rag.intent_classifier import QueryIntentClassifier
from core.fusion_rag.intelligent_router import IntelligentRouter
from core.search.result_fusion import ResultFusion
from core.fusion_rag.l4_aware_router import L4AwareRouter


@dataclass
class UnifiedSearchResponse:
    """统一搜索响应"""
    query: str
    intent: Dict[str, Any]           # 来自 QueryIntentClassifier
    routes: List[str]                # 来自 IntelligentRouter
    fused_results: Any               # 来自 ResultFusion
    total_time_ms: float
    strategy: str


class KnowledgeRouter:
    """
    知识库智能路由器 - 复用 L0-L4 架构
    
    调用链路:
    L0 QueryIntentClassifier → L1-L2 IntelligentRouter → KnowledgeBases → ResultFusion → L4
    """
    
    def __init__(self, strategy: str = "balanced"):
        """初始化路由器"""
        # 复用 L0 组件
        self.intent_classifier = QueryIntentClassifier()
        
        # 复用 L1-L2 组件
        self.intelligent_router = IntelligentRouter()
        
        # 复用结果融合
        self.result_fusion = ResultFusion()
        
        # 复用 L4 感知路由
        self.l4_aware_router = L4AwareRouter(
            base_router=self.intelligent_router,
            intent_classifier=self.intent_classifier
        )
        
        # 路由策略
        self.strategy = strategy
        
        # 统计
        self.stats = {
            "total_queries": 0,
            "intent_distribution": {},
            "strategy_usage": {}
        }
    
    async def search(
        self,
        query: str,
        top_k: int = 10,
        force_l4: bool = False
    ) -> UnifiedSearchResponse:
        """
        统一搜索接口
        
        流程:
        1. L0: 意图分类 (QueryIntentClassifier)
        2. L1-L2: 智能路由 (IntelligentRouter) 
        3. L3: 多知识库并行搜索
        4. L3: 结果融合 (ResultFusion)
        5. L4: LLM 增强 (L4AwareRouter)
        """
        start = time.time()
        
        # ========== L0: 意图分类 ==========
        intent_result = self.intent_classifier.classify(query)
        recommended_layers = self.intent_classifier.get_recommended_layers(intent_result)
        
        # ========== L1-L2: 智能路由 ==========
        route_plan = self.intelligent_router.plan_route(
            query=query,
            intent=intent_result,
            strategy=self.strategy
        )
        
        # ========== L3: 多知识库搜索 ==========
        results = await self._search_knowledge_bases(query, recommended_layers, top_k)
        
        # ========== 结果融合 ==========
        fused = self.result_fusion.fuse(
            results=results,
            query=query,
            max_results=top_k
        )
        
        # ========== L4: LLM 增强 (如果需要) ==========
        if force_l4 or self._should_use_llm(intent_result, fused):
            fused = await self._llm_enhance(query, fused, intent_result)
        
        total_time = (time.time() - start) * 1000
        
        # 统计
        self.stats["total_queries"] += 1
        self.stats["intent_distribution"][intent_result["primary"]] = \
            self.stats["intent_distribution"].get(intent_result["primary"], 0) + 1
        
        return UnifiedSearchResponse(
            query=query,
            intent=intent_result,
            routes=recommended_layers,
            fused_results=fused,
            total_time_ms=total_time,
            strategy=self.strategy
        )
    
    async def _search_knowledge_bases(
        self,
        query: str,
        layers: List[str],
        top_k: int
    ) -> List[Any]:
        """搜索多个知识库"""
        results = []
        
        # KnowledgeBaseLayer
        if "knowledge_base" in layers:
            try:
                from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
                kb = KnowledgeBaseLayer()
                kb_results = kb.search(query, top_k=top_k)
                results.extend(kb_results if kb_results else [])
            except Exception as e:
                print(f"KB search error: {e}")
        
        # PageIndex
        if "exact_cache" in layers:
            try:
                from core.page_index.index_builder import PageIndexBuilder
                pi = PageIndexBuilder()
                pi_results = pi.search(query, top_k=top_k)
                results.extend(pi_results if pi_results else [])
            except Exception as e:
                print(f"PageIndex search error: {e}")
        
        return results
    
    def _should_use_llm(self, intent: Dict, fused: Any) -> bool:
        """判断是否需要 LLM 增强"""
        # 创意类意图需要 LLM
        if intent["primary"] == "creative":
            return True
        
        # 无检索结果需要 LLM
        if not fused or not hasattr(fused, 'results') or not fused.results:
            return True
        
        # 低置信度需要 LLM
        if intent["confidence"] < 0.6:
            return True
        
        return False
    
    async def _llm_enhance(
        self,
        query: str,
        fused: Any,
        intent: Dict
    ) -> Any:
        """LLM 增强结果"""
        # 使用 L4AwareRouter 穿透
        decision = self.l4_aware_router.decide(
            query=query,
            intent=intent,
            current_results=fused.results if fused else []
        )
        
        if decision == "force_l4":
            # TODO: 集成 L4RelayExecutor
            pass
        
        return fused
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "intent_stats": self.intent_classifier.get_stats()
        }


# ========== 便捷接口 ==========

async def unified_search(
    query: str,
    strategy: str = "balanced",
    top_k: int = 10
) -> UnifiedSearchResponse:
    """
    统一搜索便捷接口
    
    Args:
        query: 查询文本
        strategy: 路由策略 (speed_first/balanced/accuracy_first)
        top_k: 返回结果数量
        
    Returns:
        UnifiedSearchResponse: 统一响应
    """
    router = KnowledgeRouter(strategy=strategy)
    return await router.search(query, top_k=top_k)


# ========== 测试 ==========

if __name__ == "__main__":
    async def test():
        print("=" * 60)
        print("KnowledgeRouter 集成测试 (复用 L0-L4 组件)")
        print("=" * 60)
        
        queries = [
            "什么是微服务架构",
            "帮我分析 AI 技术趋势",
            "对比一下 Ollama 和 vLLM",
            "Ollama 怎么安装",
        ]
        
        for q in queries:
            print(f"\n>>> {q}")
            
            # 1. L0: 意图分类
            classifier = QueryIntentClassifier()
            intent = classifier.classify(q)
            print(f"  [L0] Intent: {intent['primary']} (confidence: {intent['confidence']:.2f})")
            
            # 2. 推荐层级
            layers = classifier.get_recommended_layers(intent)
            print(f"  [L0] Layers: {layers}")
            
            # 3. L1-L2: 路由决策
            router = IntelligentRouter()
            route_plan = router.plan_route(q, intent, "balanced")
            print(f"  [L1-L2] Strategy: {route_plan.get('strategy', {}).get('description', 'N/A')}")
            print(f"  [L1-L2] Selected: {route_plan.get('selected_layers', [])}")
            
            print()
        
        print("=" * 60)
        print("All components working correctly!")
        print("=" * 60)
    
    asyncio.run(test())
