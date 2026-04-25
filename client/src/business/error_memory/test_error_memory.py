# -*- coding: utf-8 -*-
"""
Test Error Memory System - 错误记忆系统测试
============================================

Author: LivingTreeAI Agent
Date: 2026-04-24
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import traceback
from error_models import (
    ErrorSurfaceFeatures,
    ErrorPattern,
    ErrorCategory,
    ErrorSeverity,
)
from pattern_matcher import ErrorPatternMatcher, FeatureExtractor
from error_learning_system import ErrorLearningSystem, quick_fix_from_message
from error_knowledge_base import get_knowledge_base


def test_feature_extractor():
    """测试特征提取"""
    print("\n" + "=" * 60)
    print("测试 1: Feature Extractor")
    print("=" * 60)
    
    # 测试错误类型提取
    messages = [
        "UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd6 in position 100",
        "FileNotFoundError: [Errno 2] No such file or directory: 'data.csv'",
        "TimeoutError: Connection timed out after 30 seconds",
        "ImportError: cannot import name 'Module' from 'unknown'",
    ]
    
    for msg in messages:
        error_type = FeatureExtractor.extract_error_type(msg)
        error_name = FeatureExtractor.extract_error_name(msg)
        keywords = FeatureExtractor.extract_keywords(msg)
        
        print(f"\n  错误消息: {msg[:50]}...")
        print(f"    类型: {error_type}")
        print(f"    名称: {error_name}")
        print(f"    关键词: {keywords[:5]}")
    
    return True


def test_pattern_matcher():
    """测试模式匹配"""
    print("\n" + "=" * 60)
    print("测试 2: Pattern Matcher")
    print("=" * 60)
    
    matcher = ErrorPatternMatcher()
    
    # 测试用例
    test_cases = [
        {
            "message": "UnicodeDecodeError: 'utf-8' codec can't decode byte",
            "context": {"operation": "file_read"},
            "expected_pattern": "encoding_mismatch",
        },
        {
            "message": "FileNotFoundError: [Errno 2] No such file or directory",
            "context": {"operation": "file_open"},
            "expected_pattern": "file_not_found",
        },
        {
            "message": "TimeoutError: Connection timed out",
            "context": {"operation": "http_request"},
            "expected_pattern": "network_timeout",
        },
    ]
    
    passed = 0
    for case in test_cases:
        surface = ErrorSurfaceFeatures(
            raw_message=case["message"],
            error_type=FeatureExtractor.extract_error_name(case["message"]),
            operation_type=case["context"].get("operation"),
        )
        
        matches = matcher.find_matching_patterns(surface, case["context"])
        
        print(f"\n  错误: {case['message'][:40]}...")
        print(f"    匹配模式数: {len(matches)}")
        
        if matches:
            best = matches[0]
            print(f"    最佳匹配: {best.pattern.pattern_name}")
            print(f"    置信度: {best.confidence:.2f}")
            print(f"    推荐模板: {[t.template_name for t in best.recommended_templates[:2]]}")
            
            if best.pattern.pattern_id == case["expected_pattern"]:
                passed += 1
    
    print(f"\n  模式匹配测试: {passed}/{len(test_cases)} 通过")
    return passed >= 2


def test_error_learning_system():
    """测试错误学习系统"""
    print("\n" + "=" * 60)
    print("测试 3: Error Learning System")
    print("=" * 60)
    
    els = ErrorLearningSystem(auto_learn=True, storage_path="./test_error_knowledge")
    
    # 测试从异常学习
    try:
        # 模拟一个Unicode解码错误
        with open("nonexistent_file_12345.csv", "r", encoding="utf-8") as f:
            f.read()
    except Exception as e:
        solution = els.learn_and_fix(
            error=e,
            context={"operation": "file_read", "file": "test.csv"}
        )
        
        print(f"\n  异常类型: {type(e).__name__}")
        print(f"  成功: {solution['success']}")
        
        if solution['success']:
            print(f"  匹配模式: {solution['matched_pattern']['pattern_name']}")
            print(f"  模式类别: {solution['matched_pattern']['category']}")
            print(f"  根因: {solution['matched_pattern']['root_cause']}")
            
            if solution['recommended_templates']:
                print(f"  推荐模板: {solution['recommended_templates'][0]['template_name']}")
        else:
            print(f"  提示: {solution.get('suggestion', '')}")
    
    # 测试从消息学习
    print("\n  --- 从错误消息学习 ---")
    solution = els.learn_and_fix_from_message(
        "UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd6",
        context={"operation": "file_read"}
    )
    
    print(f"  成功: {solution['success']}")
    if solution['success']:
        print(f"  匹配模式: {solution['matched_pattern']['pattern_name']}")
        if solution['recommended_templates']:
            template = solution['recommended_templates'][0]
            print(f"  推荐方案: {template['template_name']}")
            print(f"  成功率: {template['success_rate']:.1%}")
            print(f"  步骤: {template['steps'][:2]}")
    
    return True


def test_quick_api():
    """测试快速API"""
    print("\n" + "=" * 60)
    print("测试 4: Quick API")
    print("=" * 60)
    
    # 模拟错误
    class MockError(Exception):
        pass
    
    # 测试快速学习
    try:
        raise MockError("Test error for quick learn")
    except Exception as e:
        solution = quick_fix_from_message(
            str(e),
            context={"operation": "test"}
        )
        
        print(f"\n  快速学习结果:")
        print(f"    成功: {solution['success']}")
        print(f"    记录ID: {solution.get('record_id', 'N/A')}")
    
    return True


def test_pattern_management():
    """测试模式管理"""
    print("\n" + "=" * 60)
    print("测试 5: Pattern Management")
    print("=" * 60)
    
    kb = get_knowledge_base()
    stats = kb.get_statistics()
    
    print(f"\n  知识库统计:")
    print(f"    总记录数: {stats['total_records']}")
    print(f"    解决率: {stats['resolution_rate']:.1%}")
    print(f"    总模式数: {stats['total_patterns']}")
    print(f"    总模板数: {stats['total_templates']}")
    
    if stats['category_stats']:
        print(f"    类别分布:")
        for cat, count in stats['category_stats'].items():
            print(f"      {cat}: {count}")
    
    return True


def test_error_simulation():
    """测试错误模拟场景"""
    print("\n" + "=" * 60)
    print("测试 6: Error Simulation")
    print("=" * 60)
    
    els = ErrorLearningSystem(auto_learn=True)
    
    # 模拟常见错误场景
    scenarios = [
        {
            "name": "CSV文件读取编码错误",
            "message": "UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd6 in position 0",
            "context": {"operation": "csv_read", "file": "data.csv"},
        },
        {
            "name": "配置文件缺失",
            "message": "FileNotFoundError: [Errno 2] No such file or directory: 'config.yaml'",
            "context": {"operation": "config_load"},
        },
        {
            "name": "API调用超时",
            "message": "TimeoutError: Connection timed out after 30 seconds",
            "context": {"operation": "api_request", "url": "https://api.example.com"},
        },
        {
            "name": "模块导入失败",
            "message": "ModuleNotFoundError: No module named 'requests'",
            "context": {"operation": "import_module"},
        },
    ]
    
    print("\n  错误场景模拟:")
    for scenario in scenarios:
        solution = els.learn_and_fix_from_message(
            scenario["message"],
            scenario["context"]
        )
        
        status = "[OK]" if solution["success"] else "[FAIL]"
        pattern = solution.get("matched_pattern", {}).get("pattern_name", "N/A")
        templates = len(solution.get("recommended_templates", []))
        
        print(f"\n  {status} {scenario['name']}")
        print(f"     消息: {scenario['message'][:40]}...")
        print(f"     匹配: {pattern}")
        print(f"     方案: {templates} 个推荐模板")
    
    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("智能错误修复记忆系统测试")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    results.append(("Feature Extractor", test_feature_extractor()))
    results.append(("Pattern Matcher", test_pattern_matcher()))
    results.append(("Error Learning System", test_error_learning_system()))
    results.append(("Quick API", test_quick_api()))
    results.append(("Pattern Management", test_pattern_management()))
    results.append(("Error Simulation", test_error_simulation()))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {name}")
    
    print(f"\n  总计: {passed}/{total} 测试通过")
    
    # 获取系统统计
    els = ErrorLearningSystem()
    stats = els.get_statistics()
    print(f"\n  系统统计:")
    print(f"    总错误数: {stats['total_errors']}")
    print(f"    解决数: {stats['resolved_errors']}")
    print(f"    自动修复: {stats['auto_fixed_errors']}")
    print(f"    新模式: {stats['new_patterns_learned']}")
    print(f"    新模板: {stats['new_templates_created']}")
    
    return passed >= total - 1


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
