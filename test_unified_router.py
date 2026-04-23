"""
测试统一路由器 - 复用 L0-L4 组件
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from core.fusion_rag.intent_classifier import QueryIntentClassifier
from core.fusion_rag.intelligent_router import IntelligentRouter
from core.search.result_fusion import ResultFusion
from core.fusion_rag.l4_aware_router import L4AwareRouter


def test_components():
    print("=" * 60)
    print("KnowledgeRouter 集成测试 (复用 L0-L4 组件)")
    print("=" * 60)
    
    queries = [
        "什么是微服务架构",
        "帮我分析 AI 技术趋势",
        "对比一下 Ollama 和 vLLM",
        "Ollama 怎么安装",
    ]
    
    # 复用 L0 组件
    classifier = QueryIntentClassifier()
    
    # 复用 L1-L2 组件
    router = IntelligentRouter()
    
    # 复用 L4 组件
    l4_router = L4AwareRouter(base_router=router, intent_classifier=classifier)
    
    # 复用结果融合
    fusion = ResultFusion()
    
    for q in queries:
        print(f"\n>>> {q}")
        
        # 1. L0: 意图分类
        intent = classifier.classify(q)
        print(f"  [L0] Intent: {intent['primary']} (confidence: {intent['confidence']:.2f})")
        
        # 2. 推荐层级
        layers = classifier.get_recommended_layers(intent)
        print(f"  [L0] Layers: {layers}")
        
        # 3. L1-L2: 路由决策
        route_result = router.route(q, intent, "balanced")
        print(f"  [L1-L2] Strategy: {route_result.get('strategy_description', 'N/A')}")
        print(f"  [L1-L2] Enabled: {route_result.get('enabled_layers', [])}")
        print(f"  [L1-L2] LLM needed: {route_result.get('needs_llm', False)}")
        
        # 4. L4: 完整路由决策
        l4_result = l4_router.route_with_l4_decision(q, [], "balanced", intent)
        print(f"  [L4] Needs L4: {l4_result.get('needs_l4', False)}")
        print(f"  [L4] L4 Decision: {l4_result.get('l4_decision', 'N/A')}")
        print(f"  [L4] L4 Model: {l4_result.get('l4_model', 'N/A')}")
        
        print()
    
    print("=" * 60)
    print("L0-L4 组件调用链验证成功!")
    print("=" * 60)
    
    # 打印组件统计
    print("\n组件统计:")
    print(f"  Intent stats: {classifier.get_stats()}")
    print(f"  Router stats: {router.get_stats()}")
    print(f"  L4 stats: {l4_router.get_stats()}")


if __name__ == "__main__":
    test_components()
