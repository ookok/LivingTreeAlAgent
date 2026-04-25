#!/usr/bin/env python3
"""
测试搜索流程
"""

import asyncio
import traceback
from client.src.business.agent import HermesAgent

async def test_search_flow():
    """测试搜索流程"""
    print("=== 测试搜索流程 ===")
    
    try:
        # 创建Agent实例
        print("创建HermesAgent实例...")
        agent = HermesAgent("test_session")
        print("Agent实例创建成功")
        
        # 测试查询
        test_query = "海安地区养猪场环评报告"
        print(f"\n测试查询: {test_query}")
        
        # 1. 测试知识库搜索
        print("\n1. 测试知识库搜索...")
        try:
            kb_results = agent._search_knowledge_base(test_query)
            print(f"知识库搜索结果: {len(kb_results)} 条")
            for i, result in enumerate(kb_results[:3], 1):
                content = result.get("content", "").strip()
                if content:
                    print(f"  {i}. {content[:100]}...")
        except Exception as e:
            print(f"知识库搜索出错: {e}")
            traceback.print_exc()
        
        # 2. 测试深度搜索
        print("\n2. 测试深度搜索...")
        try:
            deep_results = await agent._deep_search(test_query)
            print(f"深度搜索结果: {len(deep_results)} 条")
            for i, result in enumerate(deep_results[:3], 1):
                content = result.get("content", "").strip()
                if content:
                    print(f"  {i}. {content[:100]}...")
        except Exception as e:
            print(f"深度搜索出错: {e}")
            traceback.print_exc()
        
        # 3. 测试模型路由
        print("\n3. 测试模型路由...")
        try:
            model_name = agent._route_model(test_query)
            print(f"选择的模型: {model_name}")
        except Exception as e:
            print(f"模型路由出错: {e}")
            traceback.print_exc()
        
        # 4. 测试完整流程
        print("\n4. 测试完整流程...")
        try:
            chunks = agent.send_message(test_query)
            print("开始生成回答...")
            for chunk in chunks:
                if chunk.content:
                    print(chunk.content, end="", flush=True)
                if chunk.done:
                    print()
                if chunk.error:
                    print(f"错误: {chunk.error}")
        except Exception as e:
            print(f"完整流程出错: {e}")
            traceback.print_exc()
        
        print("\n=== 测试完成 ===")
    except Exception as e:
        print(f"测试过程出错: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_search_flow())
