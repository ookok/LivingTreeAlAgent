"""测试统一记忆层优化功能"""
import sys
sys.path.insert(0, 'client/src')

import asyncio
from business.memory import get_memory_router, query_memory

print("=" * 60)
print("统一记忆层优化功能测试")
print("=" * 60)

router = get_memory_router()

# 1. 测试增强版意图分类
print("\n[1] 测试增强版意图分类")
test_queries = [
    "如何修复代码中的错误？",
    "帮我写一个 Python 函数",
    "解释一下量子计算的原理",
    "查找用户手册文档",
    "系统如何进行自我进化？",
    "不要帮我写代码"
]

for query in test_queries:
    intent = router._analyze_intent(query)
    print(f'"{query}"')
    print(f'  -> 意图: {intent["type"]}, 置信度: {intent["confidence"]:.2f}')
    if intent.get("candidates"):
        print(f'  -> 候选: {intent["candidates"]}')

# 2. 测试性能监控
print("\n[2] 测试性能监控")
# 执行多次查询来生成统计数据
for i in range(3):
    result = router.query(f"测试查询 {i}")

stats = router.get_stats()
print(f'总查询数: {stats["total_queries"]}')
print(f'\n各记忆类型性能统计:')
for mem_type, metrics in stats["detailed_performance"].items():
    print(f'  {mem_type}:')
    print(f'    - 查询数: {metrics["total_queries"]}')
    print(f'    - 命中率: {metrics["hit_rate"]:.2%}')
    print(f'    - 平均延迟: {metrics["avg_latency_ms"]:.2f}ms')

# 3. 测试异步查询
print("\n[3] 测试异步查询")
async def test_async_queries():
    print("  执行异步查询...")
    
    # 并行执行多个查询
    queries = ["什么是人工智能？", "什么是机器学习？", "什么是深度学习？"]
    tasks = [router.query_async(q) for q in queries]
    
    results = await asyncio.gather(*tasks)
    
    for q, r in zip(queries, results):
        print(f'  "{q}" -> 来源: {r["memory_source"]}, 置信度: {r["confidence"]:.2f}')

asyncio.run(test_async_queries())

# 4. 测试路由策略
print("\n[4] 测试路由策略")
test_cases = [
    ("如何修复网络错误？", {"is_error_recovery": True}),
    ("系统如何进化？", {"is_evolution": True}),
    ("你好！", {"session_id": "test_session"}),
    ("查找文档", {})
]

for query, context in test_cases:
    routes = router.route(query, context)
    print(f'"{query}" -> 路由: {routes}')

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)