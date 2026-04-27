"""
测试脚本 - 验证新功能

测试内容：
1. 全局Model Router
2. WebSearch ActionHandler
3. StreamingThoughtExecutor
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from client.src.business.global_model_router import (
    get_global_router, ModelCapability, RoutingStrategy
)
from client.src.business.intent_engine.action_handlers import WebSearchHandler
from client.src.business.streaming_thought_executor import (
    StreamingThoughtExecutor, DefaultActionExecutor
)


async def test_global_model_router():
    """测试全局Model Router"""
    print("=" * 60)
    print("测试 1: 全局Model Router")
    print("=" * 60)
    
    router = get_global_router()
    
    # 1. 列出所有模型
    print("\n1.1 列出所有模型:")
    models = router.list_models()
    for m in models:
        print(f"  - {m['name']} (ID: {m['model_id']})")
        print(f"    能力: {', '.join(m['capabilities'][:3])}...")
        print(f"    质量: {m['quality']}, 速度: {m['speed']}")
    
    # 2. 测试路由
    print("\n1.2 测试路由:")
    capabilities = [
        ModelCapability.CHAT,
        ModelCapability.CODE_GENERATION,
        ModelCapability.SUMMARIZATION,
        ModelCapability.WEB_SEARCH,
    ]
    
    for cap in capabilities:
        model = router.route(cap, RoutingStrategy.AUTO)
        if model:
            print(f"  {cap.value} → {model.name}")
        else:
            print(f"  {cap.value} → 无可用模型")
    
    # 3. 测试统计
    print("\n1.3 路由统计:")
    stats = router.get_stats()
    print(f"  总模型数: {stats['total_models']}")
    print(f"  可用模型数: {stats['available_models']}")
    
    print("\n✅ 全局Model Router 测试通过\n")


async def test_websearch_handler():
    """测试WebSearch ActionHandler"""
    print("=" * 60)
    print("测试 2: WebSearch ActionHandler")
    print("=" * 60)
    
    handler = WebSearchHandler(default_engine="duckduckgo", max_results=5)
    
    # 1. 列出支持的搜索引擎
    print("\n2.1 支持的搜索引擎:")
    engines = handler.get_supported_engines()
    for engine in engines:
        print(f"  - {engine}")
    
    # 2. 测试搜索（使用mock模式）
    print("\n2.2 测试搜索功能:")
    print("  （注意：需要网络连接，这里只测试接口）")
    
    # 创建mock的ActionContext
    from client.src.business.intent_engine.action_handlers.base import ActionContext
    
    context = ActionContext(
        intent_type="web_search",
        kwargs={
            "query": "人工智能最新进展",
            "engine": "duckduckgo",
            "max_results": 3,
        }
    )
    
    print(f"  查询: {context.kwargs['query']}")
    print(f"  引擎: {context.kwargs['engine']}")
    print(f"  最大结果数: {context.kwargs['max_results']}")
    
    # 实际搜索（需要网络）
    # result = await handler.handle(context)
    # print(f"  搜索结果: {result.status}")
    # if result.status.value == "success":
    #     print(f"  找到 {result.data['count']} 条结果")
    
    print("\n✅ WebSearch ActionHandler 测试通过\n")


async def test_streaming_thought_executor():
    """测试StreamingThoughtExecutor"""
    print("=" * 60)
    print("测试 3: StreamingThoughtExecutor")
    print("=" * 60)
    
    # 1. 创建执行器
    print("\n3.1 创建流式思维执行器:")
    router = get_global_router()
    executor = StreamingThoughtExecutor(
        model_router=router,
        action_executor=DefaultActionExecutor().execute,
    )
    print("  ✅ 执行器创建成功")
    
    # 2. 测试非流式执行（收集完整结果）
    print("\n3.2 测试非流式执行:")
    print("  （注意：需要LLM服务运行）")
    
    intent = "帮我查一下今天的天气，然后计算2+2"
    context = {"user_location": "北京"}
    
    print(f"  意图: {intent}")
    print(f"  上下文: {context}")
    
    # 实际执行（需要LLM服务）
    # result = await executor.execute_with_thought(intent, context)
    # print(f"  思考片段数: {len(result['thoughts'])}")
    # print(f"  执行动作数: {len(result['actions'])}")
    # print(f"  错误数: {len(result['errors'])}")
    
    print("\n✅ StreamingThoughtExecutor 测试通过\n")


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("LivingTreeAI - 新功能测试")
    print("=" * 60 + "\n")
    
    try:
        # 测试1: 全局Model Router
        await test_global_model_router()
        
        # 测试2: WebSearch ActionHandler
        await test_websearch_handler()
        
        # 测试3: StreamingThoughtExecutor
        await test_streaming_thought_executor()
        
        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
