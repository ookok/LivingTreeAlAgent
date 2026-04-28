#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试深度搜索功能，将结果写入文件以避免输出被截断
"""

import asyncio
import time
import os
from core.smolllm2.l0_integration import smart_execute, preview_route


async def test_depth_search():
    """测试深度搜索"""
    # 输出文件路径
    output_file = "depth_search_final.txt"
    
    # 清空输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("开始测试深度搜索功能\n")
        f.write("=" * 60 + "\n")
    
    # 测试查询
    queries = [
        "五一南京有哪些地方值得玩",
        "南京溧水养猪场环评报告",
        "北京海淀区科技园区规划"
    ]
    
    for i, query in enumerate(queries):
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"\n第 {i+1} 次测试:\n")
            f.write(f"查询: {query}\n")
        
        # 测试 L0 路由
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write("分析意图和路由...\n")
        try:
            decision = await preview_route(query)
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"L0 路由决策: {decision.route.value}\n")
                f.write(f"意图: {decision.intent.value}\n")
                f.write(f"原因: {decision.reason}\n")
                f.write(f"置信度: {decision.confidence:.2f}\n")
                f.write(f"延迟: {decision.latency_ms:.2f}ms\n")
                f.write(f"模型: {decision.model_used}\n")
                f.write(f"是否备用: {decision.fallback}\n")
        except Exception as e:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"L0 路由测试失败: {e}\n")
                import traceback
                traceback.print_exc()
        
        # 测试智能执行
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write("执行深度搜索...\n")
        start_time = time.time()
        try:
            result = await smart_execute(query)
            latency = (time.time() - start_time) * 1000
            
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write("执行结果:\n")
                f.write(f"内容长度: {len(result.get('content', ''))} 字符\n")
                f.write(f"内容: {result.get('content', '')}\n")
                f.write(f"延迟: {latency:.2f}ms\n")
                
                if "cache_hit" in result and result["cache_hit"]:
                    f.write("缓存命中\n")
                elif "escalate_to_human" in result and result["escalate_to_human"]:
                    f.write("转人工\n")
                
                if "l0_decision" in result:
                    l0_decision = result["l0_decision"]
                    f.write(f"L0 决策: {l0_decision['route']}, 意图: {l0_decision['intent']}\n")
                    f.write(f"原因: {l0_decision['reason']}\n")
        except Exception as e:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"智能执行失败: {e}\n")
                import traceback
                traceback.print_exc()
        
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write("\n" + "=" * 60 + "\n")
    
    # 完成测试
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("测试完成\n")
    
    # 打印完成信息
    print(f"测试完成，结果已写入 {output_file}")
    print(f"文件路径: {os.path.abspath(output_file)}")


if __name__ == "__main__":
    asyncio.run(test_depth_search())
