# -*- coding: utf-8 -*-
"""
AI 意图引擎测试 - 使用真实 AI 服务
"""

import sys
import os

# 添加 core 路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'core'))

from ai_intent_engine import AIIntentEngine, IntentType


def test_ai_intent():
    """测试 AI 意图解析"""
    print("=" * 60)
    print("AI Intent Engine Test")
    print("Server: http://www.mogoo.com.cn:8899/v1")
    print("=" * 60)
    
    # 创建引擎
    engine = AIIntentEngine(
        base_url="http://www.mogoo.com.cn:8899/v1",
        model="qwen3.5:4b"  # 使用 qwen3.5:4b 模型
    )
    
    # 测试用例
    test_cases = [
        # 代码生成
        "帮我写一个用户登录函数",
        "生成一个Python的快速排序算法",
        "写一个FastAPI的用户接口",
        
        # Bug修复
        "修复这个bug: index out of range",
        "帮我修一下空指针错误",
        
        # 重构
        "重构这段代码",
        "优化一下这个类的性能",
        
        # 查询
        "查找所有用户相关的函数",
        "搜索这个文件中的内容",
        
        # 执行
        "运行这个脚本",
        "执行pytest测试",
        
        # 解释
        "解释这段代码",
        "什么是装饰器",
        
        # 复杂场景
        "帮我用Python写一个连接MySQL的函数，要有异常处理",
        "这段代码报错了，帮我看看是什么问题",
    ]
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    for i, query in enumerate(test_cases, 1):
        print(f"\n[{i}] {query}")
        print("-" * 40)
        
        try:
            intent = engine.parse(query)
            
            print(f"  Intent Type: {intent.intent_type.value}")
            print(f"  Action: {intent.action or 'N/A'}")
            print(f"  Target: {intent.target or 'N/A'}")
            print(f"  Tech Stack: {', '.join(intent.tech_stack) if intent.tech_stack else 'None'}")
            print(f"  Confidence: {intent.confidence:.2f}")
            
            if intent.reasoning:
                print(f"  Reasoning: {intent.reasoning[:100]}...")
                
        except Exception as e:
            print(f"  ERROR: {e}")


def test_single_query():
    """测试单个查询"""
    print("\n" + "=" * 60)
    print("Single Query Test")
    print("=" * 60)
    
    engine = AIIntentEngine(
        base_url="http://www.mogoo.com.cn:8899/v1",
        model="deepseek-r1:14b"
    )
    
    while True:
        print("\n" + "-" * 40)
        query = input("Enter your query (or 'q' to quit): ").strip()
        
        if query.lower() == 'q':
            break
        
        if not query:
            continue
        
        print("\nParsing...")
        try:
            intent = engine.parse(query)
            
            print(f"\n  Intent Type: {intent.intent_type.value}")
            print(f"  Action: {intent.action or 'N/A'}")
            print(f"  Target: {intent.target or 'N/A'}")
            print(f"  Tech Stack: {', '.join(intent.tech_stack) if intent.tech_stack else 'None'}")
            print(f"  Constraints: {', '.join(intent.constraints) if intent.constraints else 'None'}")
            print(f"  Confidence: {intent.confidence:.2f}")
            
            if intent.reasoning:
                print(f"\n  Reasoning:\n  {intent.reasoning}")
                
        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == '__main__':
    print("\n>> AI Intent Engine Test")
    print(">> Using: http://www.mogoo.com.cn:8899/v1")
    print()
    
    # 批量测试
    test_ai_intent()
    
    # 单个查询测试
    # test_single_query()
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
