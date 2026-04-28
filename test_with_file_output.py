#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本，将结果写入文件以避免输出被截断
"""

import asyncio
import time
import os
from core.smolllm2.l0_integration import smart_execute, preview_route


async def test_deep_search(output_file):
    """测试深度搜索"""
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("=== 测试深度搜索 ===\n\n")
    
    # 测试查询
    query = "五一南京周边哪些地方适合玩"
    
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
    
    # 测试智能执行
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("\n测试智能执行:\n")
        f.write("开始执行 smart_execute...\n")
    start_time = time.time()
    try:
        result = await smart_execute(query)
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write("smart_execute 执行完成\n")
        latency = (time.time() - start_time) * 1000
        
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write("智能执行结果:\n")
            f.write(f"内容长度: {len(result['content'])} 字符\n")
            f.write(f"内容: {result['content']}\n")
            f.write(f"延迟: {latency:.2f}ms\n")
            
            if "cache_hit" in result and result["cache_hit"]:
                f.write("✅ 缓存命中\n")
            elif "escalate_to_human" in result and result["escalate_to_human"]:
                f.write("⚠️  转人工\n")
            
            if "l0_decision" in result:
                l0_decision = result["l0_decision"]
                f.write(f"L0 决策: {l0_decision['route']}, 意图: {l0_decision['intent']}\n")
                f.write(f"原因: {l0_decision['reason']}\n")
    except Exception as e:
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"❌ 智能执行失败: {e}\n")
            import traceback
            traceback.print_exc()


async def test_long_context(output_file):
    """测试超长上下文处理"""
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("\n=== 测试超长上下文处理 ===\n\n")
    
    # 创建1000字的超长上下文
    long_context = "a" * 1000
    query = f"请分析以下内容: {long_context}"
    
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write(f"超长上下文长度: {len(long_context)} 字符\n")
    
    # 测试 L0 路由
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("\n测试 L0 路由:\n")
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
    
    # 测试智能执行
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("\n测试智能执行:\n")
        f.write("开始执行 smart_execute...\n")
    start_time = time.time()
    try:
        result = await smart_execute(query)
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write("smart_execute 执行完成\n")
        latency = (time.time() - start_time) * 1000
        
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write("智能执行结果:\n")
            f.write(f"内容长度: {len(result['content'])} 字符\n")
            f.write(f"内容: {result['content'][:500]}...\n")  # 只显示前500个字符
            f.write(f"延迟: {latency:.2f}ms\n")
            
            if "cache_hit" in result and result["cache_hit"]:
                f.write("✅ 缓存命中\n")
            elif "escalate_to_human" in result and result["escalate_to_human"]:
                f.write("⚠️  转人工\n")
            
            if "l0_decision" in result:
                l0_decision = result["l0_decision"]
                f.write(f"L0 决策: {l0_decision['route']}, 意图: {l0_decision['intent']}\n")
                f.write(f"原因: {l0_decision['reason']}\n")
    except Exception as e:
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"❌ 智能执行失败: {e}\n")
            import traceback
            traceback.print_exc()


async def main():
    """主测试函数"""
    # 输出文件路径
    output_file = "test_results.txt"
    
    # 清空输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("🚀 开始综合测试\n")
        f.write("=" * 60 + "\n")
    
    # 测试深度搜索
    await test_deep_search(output_file)
    
    # 测试超长上下文处理
    await test_long_context(output_file)
    
    # 完成测试
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("\n" + "=" * 60 + "\n")
        f.write("📋 测试完成\n")
    
    # 打印完成信息
    print(f"测试完成，结果已写入 {output_file}")
    print(f"文件路径: {os.path.abspath(output_file)}")


if __name__ == "__main__":
    asyncio.run(main())
