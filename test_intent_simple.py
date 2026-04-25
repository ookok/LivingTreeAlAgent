#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
意图引擎测试 - 验证能正确解析用户指令
"""

import sys
import os

# 直接导入，不经过 core/__init__.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'core'))

# 导入意图引擎核心
from intent_engine_core import IntentEngine, IntentType


def test_intent_parsing():
    """测试意图解析"""
    print("=" * 60)
    print("意图引擎测试")
    print("=" * 60)
    
    engine = IntentEngine()
    
    # 测试用例
    test_cases = [
        # 代码生成
        ("帮我写一个用户登录函数", IntentType.CODE_GENERATION),
        ("生成一个Python的快速排序算法", IntentType.CODE_GENERATION),
        ("写一个FastAPI的用户接口", IntentType.CODE_GENERATION),
        
        # Bug修复
        ("修复这个bug: index out of range", IntentType.BUG_FIX),
        ("帮我修一下空指针错误", IntentType.BUG_FIX),
        ("这个报错怎么解决", IntentType.BUG_FIX),
        
        # 代码审查
        ("帮我审查这段代码", IntentType.CODE_REVIEW),
        ("检查一下这个函数", IntentType.CODE_REVIEW),
        
        # 重构
        ("重构这段代码", IntentType.REFACTORING),
        ("优化一下这个类", IntentType.REFACTORING),
        
        # 查询
        ("查找所有用户相关的函数", IntentType.QUERY),
        ("搜索这个文件中的内容", IntentType.QUERY),
        
        # 执行
        ("运行这个脚本", IntentType.EXECUTION),
        ("执行pytest测试", IntentType.EXECUTION),
        
        # 解释
        ("解释这段代码", IntentType.EXPLANATION),
        ("什么是装饰器", IntentType.EXPLANATION),
        
        # 删除
        ("删除这个文件", IntentType.DELETION),
        
        # 创建
        ("新建一个Python项目", IntentType.CREATION),
    ]
    
    print("\n测试结果:")
    print("-" * 60)
    
    passed = 0
    failed = 0
    
    for query, expected_type in test_cases:
        intent = engine.parse(query)
        
        # 检查结果
        is_correct = intent.intent_type == expected_type
        status = "[PASS]" if is_correct else "[FAIL]"
        
        if is_correct:
            passed += 1
        else:
            failed += 1
        
        # 打印结果
        print(f"\n{status}: {query}")
        print(f"  期望: {expected_type.value}")
        print(f"  实际: {intent.intent_type.value}")
        print(f"  技术栈: {', '.join(intent.tech_stack) if intent.tech_stack else '无'}")
        print(f"  置信度: {intent.confidence:.2f}")
    
    print("\n" + "=" * 60)
    print(f"测试总结: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


def demo_usage():
    """演示用法"""
    print("\n" + "=" * 60)
    print("使用演示")
    print("=" * 60)
    
    engine = IntentEngine()
    
    # 演示1: 简单查询
    print("\n[演示1] 简单代码生成")
    intent = engine.parse("帮我写一个用户登录函数，用Python")
    print(f"输入: {intent.raw_input}")
    print(f"输出: {intent}")
    
    # 演示2: 带技术栈
    print("\n[演示2] 带技术栈")
    intent = engine.parse("生成一个FastAPI的REST接口")
    print(f"输入: {intent.raw_input}")
    print(f"输出: {intent}")
    
    # 演示3: Bug修复
    print("\n[演示3] Bug修复")
    intent = engine.parse("修复空指针异常")
    print(f"输入: {intent.raw_input}")
    print(f"输出: {intent}")
    
    # 演示4: 批量处理
    print("\n[演示4] 批量处理")
    queries = [
        "写一个排序算法",
        "修复这个错误",
        "检查代码质量"
    ]
    intents = engine.parse_batch(queries)
    for i, intent in enumerate(intents, 1):
        print(f"  {i}. {intent.intent_type.value}: {intent.target[:30]}")


if __name__ == '__main__':
    print("\n>> LivingTreeAI Intent Engine Test")
    print()
    
    # 运行测试
    success = test_intent_parsing()
    
    # 演示用法
    demo_usage()
    
    # 返回结果
    print("\n" + "=" * 60)
    if success:
        print("[OK] All tests passed! Intent engine works.")
    else:
        print("[WARN] Some tests failed. Please check the parsing logic.")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
