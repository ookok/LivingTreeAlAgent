#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Intent Code Generator 测试
"""

import sys
sys.path.insert(0, r'f:\mhzyapp\LivingTreeAlAgent')

from core.ide.code_generator import IntentCodeGenerator

def test_basic_generation():
    """测试基础生成功能"""
    generator = IntentCodeGenerator()
    
    test_cases = [
        ("写一个计算斐波那契的函数", "python"),
        ("帮我写一个用户登录接口", "python"),
        ("创建一个用户管理类", "python"),
        ("写一个登录函数的测试用例", "python"),
    ]
    
    print("=" * 70)
    print(" Intent Code Generator 测试")
    print("=" * 70)
    
    passed = 0
    total = len(test_cases)
    
    for i, (intent, lang) in enumerate(test_cases, 1):
        print(f"\n[Test {i}/{total}] {intent}")
        print("-" * 50)
        
        result = generator.generate(intent, language=lang)
        
        if result.success:
            generated = result.generated
            print(f"  [PASS] Language: {generated.language}")
            print(f"  [PASS] Template: {generated.template_type.value}")
            print(f"  [PASS] Confidence: {generated.confidence:.0%}")
            print(f"  [PASS] File: {generated.file_path}")
            
            # 显示代码片段
            lines = generated.code.split('\n')[:10]
            print(f"\n  代码预览:")
            for line in lines:
                print(f"    {line}")
            if len(generated.code.split('\n')) > 10:
                print("    ...")
            
            passed += 1
        else:
            print(f"  [FAIL] {result.error}")
    
    print("\n" + "=" * 70)
    print(f" 测试结果: {passed}/{total} 通过")
    print("=" * 70)
    
    return passed == total

if __name__ == "__main__":
    success = test_basic_generation()
    sys.exit(0 if success else 1)
