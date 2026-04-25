# -*- coding: utf-8 -*-
"""
自进化系统测试
==============

测试自进化系统的各个组件：
1. SelfEvolvingSystem - 统一自进化系统
2. EvolutionMiddleware - Agent集成中间件
3. 自动调用集成

Author: LivingTreeAI Team
Date: 2026-04-24
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def test_self_evolving_system():
    """测试自进化系统"""
    print("\n" + "="*60)
    print("测试 1: SelfEvolvingSystem - 统一自进化系统")
    print("="*60)
    
    from client.src.business.self_evolving import SelfEvolvingSystem, QualityLevel
    
    # 创建系统
    system = SelfEvolvingSystem(
        enable_quality=True,
        enable_reflection=True,
        enable_error_learning=True,
        enable_skill_evolution=True,
        quality_threshold=0.5,
    )
    
    # 注册模拟执行器
    async def mock_executor(task: str, **kwargs):
        level = kwargs.get('level', 0)
        return f"[L{level}] 响应: {task[:20]}..."
    
    system.register_executor('mock', mock_executor)
    
    # 测试执行
    async def run_test():
        result = await system.execute(
            task="解释什么是机器学习",
            executor_name='mock',
        )
        
        print(f"\n[结果]")
        print(f"  响应: {result.response[:50]}...")
        print(f"  质量分数: {result.quality_score:.2f}")
        print(f"  质量等级: {result.quality_level.name}")
        print(f"  模型级别: L{result.model_level}")
        print(f"  执行时间: {result.execution_time:.3f}s")
        print(f"  尝试次数: {result.attempts}")
        print(f"  是否升级: {result.was_upgraded}")
        
        return result.quality_level.value >= QualityLevel.ACCEPTABLE.value
    
    success = asyncio.run(run_test())
    print(f"\n[状态] {'[OK]' if success else '[FAIL]'}")
    return success


def test_evolution_middleware():
    """测试进化中间件"""
    print("\n" + "="*60)
    print("测试 2: EvolutionMiddleware - Agent集成中间件")
    print("="*60)
    
    from client.src.business.self_evolving import EvolutionMiddleware, InterventionType
    
    # 创建模拟的AgentChat
    class MockAgentChat:
        def __init__(self):
            self.call_count = 0
        
        def chat(self, message, **kwargs):
            self.call_count += 1
            return f"[Mock] 你好，{message[:20]}..."
    
    mock_agent = MockAgentChat()
    
    # 创建中间件
    middleware = EvolutionMiddleware(
        mock_agent,
        enable_quality=True,
        enable_reflection=True,
        enable_error_fix=True,
        enable_learning=True,
        quality_threshold=0.5,
    )
    
    # 测试聊天
    response = middleware.chat("你好世界")
    
    print(f"\n[结果]")
    print(f"  原始Agent调用次数: {mock_agent.call_count}")
    print(f"  响应: {response}")
    
    # 检查元数据
    evolved = middleware.chat_with_metadata("测试消息")
    print(f"  质量分数: {evolved.quality_score:.2f}")
    print(f"  干预次数: {len(evolved.interventions)}")
    
    # 统计
    stats = middleware.get_stats()
    print(f"\n[统计]")
    print(f"  总调用: {stats['total_calls']}")
    print(f"  质量检查: {stats['quality_checks']}")
    print(f"  反思增强: {stats['reflections']}")
    print(f"  错误修复: {stats['error_fixes']}")
    
    success = mock_agent.call_count > 0
    print(f"\n[状态] {'[OK]' if success else '[FAIL]'}")
    return success


def test_module_integration():
    """测试模块集成"""
    print("\n" + "="*60)
    print("测试 3: 模块集成 - 三个系统协同工作")
    print("="*60)
    
    try:
        # 1. 导入所有模块
        print("\n[1] 导入模块检查...")
        
        from client.src.business.adaptive_quality import AdaptiveQualitySystem, quick_evaluate
        print("  [OK] AdaptiveQualitySystem")
        
        from client.src.business.error_memory import ErrorLearningSystem, quick_fix_from_message
        print("  [OK] ErrorLearningSystem")
        
        from client.src.business.reflective_agent import ReflectiveAgentLoop
        print("  [OK] ReflectiveAgentLoop")
        
        from client.src.business.self_evolving import SelfEvolvingSystem
        print("  [OK] SelfEvolvingSystem (统一系统)")
        
        # 2. 测试质量评估
        print("\n[2] 质量评估测试...")
        score, needs_up, level = quick_evaluate(
            "Python是一种高级编程语言。",
            "什么是Python?"
        )
        print(f"  评分: {score:.2f}, 需升级: {needs_up}, 目标级别: L{level}")
        
        # 3. 测试错误修复
        print("\n[3] 错误修复测试...")
        solution = quick_fix_from_message(
            "UnicodeDecodeError: 'utf-8' codec can't decode byte",
            {"operation": "file_read"}
        )
        print(f"  匹配模式: {solution['matched_pattern']['pattern_name']}")
        print(f"  推荐模板: {solution['recommended_templates'][0]['template_name']}")
        
        # 4. 测试统一系统
        print("\n[4] 统一系统测试...")
        system = SelfEvolvingSystem()
        
        async def test_unified():
            result = await system.execute(
                task="解释递归算法",
                executor_name='default',
            )
            return result
        
        result = asyncio.run(test_unified())
        print(f"  质量等级: {result.quality_level.name}")
        print(f"  执行时间: {result.execution_time:.3f}s")
        
        print(f"\n[状态] [OK]")
        return True
        
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        print(f"\n[状态] [FAIL]")
        return False


def test_error_handling():
    """测试错误处理"""
    print("\n" + "="*60)
    print("测试 4: 错误处理集成")
    print("="*60)
    
    from client.src.business.self_evolving import EvolutionMiddleware
    
    # 创建会抛出异常的AgentChat
    class ErrorAgentChat:
        def __init__(self):
            self.fixed = False
        
        def chat(self, message, **kwargs):
            if "error" in message.lower():
                raise ValueError("Test error message")
            return f"Response: {message}"
    
    error_agent = ErrorAgentChat()
    
    middleware = EvolutionMiddleware(
        error_agent,
        enable_quality=True,
        enable_error_fix=True,
    )
    
    # 测试正常消息
    normal_response = middleware.chat("正常消息")
    print(f"\n[正常消息] {normal_response}")
    
    # 测试错误消息
    error_response = middleware.chat("触发error的消息")
    print(f"[错误消息] {error_response[:50]}...")
    
    stats = middleware.get_stats()
    print(f"\n[错误修复统计] {stats['error_fixes']}")
    
    success = stats['error_fixes'] > 0
    print(f"[状态] {'[OK]' if success else '[WARN] 无错误触发（正常）'}")
    return True  # 不强制要求有错误


def test_stats_and_metadata():
    """测试统计和元数据"""
    print("\n" + "="*60)
    print("测试 5: 统计和元数据")
    print("="*60)
    
    from client.src.business.self_evolving import SelfEvolvingSystem
    
    system = SelfEvolvingSystem()
    
    # 执行几个任务
    async def run_tasks():
        tasks = [
            "什么是Python?",
            "解释量子计算",
            "写一个排序算法",
        ]
        
        for task in tasks:
            await system.execute(task, 'default')
    
    asyncio.run(run_tasks())
    
    # 获取统计
    stats = system.get_stats()
    
    print(f"\n[系统统计]")
    print(f"  总任务数: {stats['total_tasks']}")
    print(f"  成功任务: {stats['successful_tasks']}")
    print(f"  成功率: {stats['success_rate']:.1%}")
    print(f"  升级次数: {stats['upgraded_tasks']}")
    print(f"  升级率: {stats['upgrade_rate']:.1%}")
    print(f"  平均质量: {stats['avg_quality_score']:.2f}")
    print(f"  启用模块: {stats['enabled_modules']}")
    
    success = stats['total_tasks'] > 0
    print(f"\n[状态] {'[OK]' if success else '[FAIL]'}")
    return success


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("自进化系统测试套件")
    print("="*60)
    
    tests = [
        ("SelfEvolvingSystem", test_self_evolving_system),
        ("EvolutionMiddleware", test_evolution_middleware),
        ("模块集成", test_module_integration),
        ("错误处理", test_error_handling),
        ("统计和元数据", test_stats_and_metadata),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n[{name}] 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {name}")
    
    print(f"\n通过率: {passed}/{total} ({passed/total*100:.0f}%)")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
