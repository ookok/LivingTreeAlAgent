"""
简化的专家训练系统测试脚本
只测试不需要LLM的核心功能
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_industry_classification():
    """测试行业分类功能（不需要LLM）"""
    print("\n=== 测试1: 行业分类 ===")
    
    try:
        from client.src.business.expert_training.industry_classification import (
            get_industry_classifier,
            INDUSTRY_CATEGORIES,
            OCCUPATION_CATEGORIES
        )
        
        # 测试分类器初始化
        classifier = get_industry_classifier()
        print("[OK] 行业分类器初始化成功")
        
        # 测试分类功能
        test_cases = [
            ("环评专家", "我是环境影响评价专家，专注于建设项目环评"),
            ("软件工程师", "我擅长Python、Java编程，熟悉软件开发流程"),
            ("财务分析师", "我精通财务报表分析、投资估值、风险管理"),
        ]
        
        for name, desc in test_cases:
            result = classifier.classify_expert(desc, name)
            industry_name = result.get('industry_name', '未知')
            match_type = result.get('match_type', 'unknown')
            print(f"  - {name}: {industry_name} (匹配类型: {match_type})")
        
        # 测试获取行业树
        tree = classifier.get_industry_tree()
        category_count = len(tree.get('categories', {}))
        print(f"[OK] 行业分类树获取成功，共 {category_count} 个门类")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_notification_system():
    """测试通知系统功能（不需要LLM）"""
    print("\n=== 测试2: 通知系统 ===")
    
    try:
        from client.src.business.expert_training.notification_system import (
            get_notification_system,
            notify_expert_created
        )
        
        # 测试通知系统初始化
        notification_system = get_notification_system()
        print("[OK] 通知系统初始化成功")
        
        # 测试通知发送
        test_notification = {
            "type": "test_notification",
            "message": "这是一条测试通知",
            "timestamp": "2026-04-27T15:00:00"
        }
        
        result = notification_system.send_notification(test_notification)
        if result:
            print("[OK] 通知发送成功")
        else:
            print("[FAIL] 通知发送失败")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tools():
    """测试工具函数（不需要LLM）"""
    print("\n=== 测试3: 工具函数 ===")
    
    try:
        from client.src.business.expert_training.tools import (
            get_expert_industry,
            get_industry_tree
        )
        
        # 测试获取专家行业
        industry = get_expert_industry("数据分析专家", "数据分析专家")
        industry_name = industry.get('industry_name', '未知')
        print(f"[OK] 获取专家行业成功: {industry_name}")
        
        # 测试获取行业树
        tree = get_industry_tree()
        print("[OK] 获取行业树成功")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_system_integration():
    """测试系统集成（不需要LLM）"""
    print("\n=== 测试4: 系统集成 ===")
    
    try:
        from client.src.business.expert_training import (
            get_expert_training_system,
            __version__
        )
        
        # 测试系统初始化
        system = get_expert_training_system()
        print(f"[OK] 专家训练系统初始化成功 (版本: {__version__})")
        
        # 测试获取系统状态
        status = system.get_system_status()
        expert_count = status.get('expert_count', 0)
        industry_count = status.get('industry_count', 0)
        print(f"[OK] 系统状态获取成功:")
        print(f"  - 专家数量: {expert_count}")
        print(f"  - 行业数量: {industry_count}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("专家训练系统简化测试（不需要LLM）")
    print("=" * 60)
    
    results = []
    
    # 运行所有测试
    results.append(("行业分类", test_industry_classification()))
    results.append(("通知系统", test_notification_system()))
    results.append(("工具函数", test_tools()))
    results.append(("系统集成", test_system_integration()))
    
    # 打印测试总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} - {name}")
        
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("\n[ALL PASSED] 所有测试通过！专家训练系统核心功能正常。")
    else:
        print(f"\n[WARN] 有 {failed} 个测试失败，请检查错误信息。")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
