"""
智能IDE系统集成测试
验证现有组件和新功能的集成效果
"""

import asyncio
import os
import tempfile

from client.src.business.smart_ide_integration import create_smart_ide_system


async def test_basic_functionality():
    """测试基本功能"""
    print("=== 测试基本功能 ===")
    
    ide_system = create_smart_ide_system()
    
    # 测试系统状态
    status = ide_system.get_system_status()
    print(f"系统状态: {status.keys()}")
    
    # 测试代码补全
    code = "def hello():\n    print('Hello '); return"
    completions = await ide_system.get_code_completion(code, len(code), "python")
    print(f"代码补全建议数量: {len(completions)}")
    
    # 测试错误诊断
    error_message = "NameError: name 'x' is not defined"
    diagnosis = await ide_system.diagnose_error(error_message, "print(x)", "python")
    print(f"错误诊断结果数量: {len(diagnosis)}")
    
    # 测试性能分析
    performance = await ide_system.get_performance_suggestions("for i in range(1000):\n    list.append(i)", "python")
    print(f"性能优化建议数量: {len(performance)}")
    
    # 测试文档生成
    doc = await ide_system.generate_documentation("def add(a, b):\n    return a + b", "python")
    print(f"文档生成: {doc[:100]}...")
    
    # 测试测试生成
    tests = await ide_system.generate_tests("def add(a, b):\n    return a + b", "python")
    print(f"测试用例数量: {len(tests)}")
    
    return True


async def test_natural_language_processing():
    """测试自然语言处理"""
    print("\n=== 测试自然语言处理 ===")
    
    ide_system = create_smart_ide_system()
    
    # 测试简单代码生成
    result = await ide_system.process_natural_language(
        "创建一个Python函数，计算斐波那契数列",
        {"language": "python"}
    )
    print(f"自然语言处理结果: {'成功' if result['success'] else '失败'}")
    if result['success']:
        print(f"生成结果数量: {len(result['results'])}")
    
    # 测试推理可视化
    if 'reasoning_tree' in result:
        visualization = ide_system.visualize_reasoning(result['reasoning_tree'])
        if visualization:
            print("推理过程可视化生成成功")
    
    return result['success']


async def test_git_integration():
    """测试Git集成"""
    print("\n=== 测试Git集成 ===")
    
    ide_system = create_smart_ide_system()
    
    # 测试提交信息生成
    commit_message = await ide_system.generate_commit_message()
    if commit_message:
        print(f"生成的提交信息: {commit_message[:100]}...")
    else:
        print("未检测到Git仓库或变更")
    
    return True


async def test_personalized_learning():
    """测试个性化学习"""
    print("\n=== 测试个性化学习 ===")
    
    ide_system = create_smart_ide_system()
    
    # 测试学习推荐
    recommendations = ide_system.get_recommendations("user")
    print(f"学习推荐数量: {len(recommendations)}")
    for rec in recommendations[:3]:
        print(f"  - {rec['title']} ({rec['difficulty']})")
    
    return True


async def test_integration():
    """集成测试"""
    print("=" * 60)
    print("智能IDE系统集成测试")
    print("=" * 60)
    
    tests = [
        test_basic_functionality,
        test_natural_language_processing,
        test_git_integration,
        test_personalized_learning
    ]
    
    all_passed = True
    
    for test in tests:
        try:
            success = await test()
            if not success:
                all_passed = False
                print(f"测试 {test.__name__} 失败")
            else:
                print(f"测试 {test.__name__} 通过")
        except Exception as e:
            all_passed = False
            print(f"测试 {test.__name__} 异常: {e}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("所有测试通过！智能IDE系统集成成功")
    else:
        print("部分测试失败，需要进一步调试")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    asyncio.run(test_integration())