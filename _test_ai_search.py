"""
测试 AISearchTool 搜索吉奥环朋
"""
import asyncio
import sys
sys.path.insert(0, 'd:/mhzyapp/LivingTreeAlAgent')

from core.search_tool import AISearchTool, IntentClassifier, QueryOptimizer

async def test_ai_search():
    print("=" * 60)
    print("测试 AISearchTool 搜索 吉奥环朋")
    print("=" * 60)
    
    # 创建搜索工具（使用免费引擎）
    search_tool = AISearchTool()
    
    print(f"\n可用引擎: {search_tool.get_available_engines()}")
    
    # 测试意图分类
    query = "吉奥环朋"
    intent = IntentClassifier.classify(query)
    print(f"\n意图分类: {intent.value}")
    
    # 多查询扩展
    queries = IntentClassifier.generate_multi_queries(query, intent)
    print(f"多查询扩展: {queries}")
    
    # 执行搜索
    print(f"\n开始搜索: {query}")
    print("-" * 60)
    
    response = await search_tool.search(
        query,
        intent=intent,
        num_results=10,
        use_cache=False,
        multi_query=True
    )
    
    print(f"\n搜索结果统计:")
    print(f"  - 查询: {response.query}")
    print(f"  - 意图: {response.intent.value}")
    print(f"  - 结果数: {len(response.results)}")
    print(f"  - 使用引擎: {response.engine_used}")
    print(f"  - 来源: {response.sources[:3] if response.sources else '无'}")
    
    print(f"\n搜索结果详情:")
    print("-" * 60)
    
    for i, result in enumerate(response.results[:10], 1):
        print(f"\n【{i}】{result.title}")
        print(f"    URL: {result.url}")
        print(f"    来源: {result.source}")
        print(f"    日期: {result.date or '未知'}")
        print(f"    摘要: {result.snippet[:150]}...")
        print(f"    相关性: {result.relevance_score:.2f}")
        if result.file_type:
            print(f"    文件类型: {result.file_type}")
    
    return response

if __name__ == "__main__":
    result = asyncio.run(test_ai_search())
