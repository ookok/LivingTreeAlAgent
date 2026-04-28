#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试深度搜索功能，将结果写入文件以避免输出被截断
"""

import asyncio
import time
import os
from core.smolllm2.l0_integration import smart_execute, preview_route


async def test_depth_search(output_file):
    """测试深度搜索"""
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("=== 测试深度搜索 ===\n\n")
    
    # 测试查询
    query = "五一南京有哪些地方值得玩"
    
    # 测试 L0 路由
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("测试 L0 路由:\n")
    try:
        decision = await preview_route(query)
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"L0 路由决策: {decision.route.value}, 意图: {decision.intent.value}\n")
            f.write(f"原因: {decision.reason}, 置信度: {decision.confidence:.2f}\n")
    except Exception as e:
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"❌ L0 路由测试失败: {e}\n")
            import traceback
            traceback.print_exc()
    
    # 连续测试5次，检查输出截断问题
    for i in range(5):
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"\n第 {i+1} 次测试:\n")
            f.write(f"查询: {query}\n")
        
        start_time = time.time()
        try:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write("开始执行 smart_execute...\n")
            # 直接调用 L4 执行器，绕过 L0 路由
            from core.fusion_rag.l4_executor import L4RelayExecutor
            executor = L4RelayExecutor()
            messages = [{"role": "user", "content": query}]
            result = await executor.execute(messages)
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write("smart_execute 执行完成\n")
            latency = (time.time() - start_time) * 1000
            
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write("智能执行结果:\n")
                f.write(f"内容长度: {len(result.get('content', ''))} 字符\n")
                f.write(f"内容: {result.get('content', '')}\n")
                f.write(f"延迟: {latency:.2f}ms\n")
        except Exception as e:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"❌ 智能执行失败: {e}\n")
                import traceback
                traceback.print_exc()
        
        # 等待 2 秒避免请求过于频繁
        time.sleep(2)


async def main():
    """主测试函数"""
    # 输出文件路径
    output_file = "depth_search_results.txt"
    
    # 清空输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("🚀 开始测试深度搜索功能\n")
        f.write("=" * 60 + "\n")
    
    # 测试深度搜索
    await test_depth_search(output_file)
    
    # 完成测试
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("\n" + "=" * 60 + "\n")
        f.write("📋 测试完成\n")
    
    # 打印完成信息
    print(f"测试完成，结果已写入 {output_file}")
    print(f"文件路径: {os.path.abspath(output_file)}")


if __name__ == "__main__":
    asyncio.run(main())
