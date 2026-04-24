"""
SeamlessEnhancer Tests
无缝自动增强层测试
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_trigger_decider():
    """Test 1: 触发决策器"""
    print("\n" + "="*50)
    print("Test 1: Trigger Decider")
    print("="*50)
    
    from trigger_decider import TriggerDecider, EnhancementType
    
    decider = TriggerDecider()
    
    # 测试简单任务
    simple = decider.analyze("帮我查天气")
    print(f"  Simple query: '{simple.raw_query}'")
    print(f"    Complexity: {simple.complexity:.1f}")
    print(f"    Enhancements: {[e.value for e in simple.enabled_enhancements]}")
    
    # 测试复杂任务
    complex_task = decider.analyze(
        "帮我设计一个微服务架构系统，包括用户模块、订单模块、支付模块，需要考虑高并发、容错、可扩展性"
    )
    print(f"\n  Complex query: '{complex_task.raw_query[:30]}...'")
    print(f"    Complexity: {complex_task.complexity:.1f}")
    print(f"    Risk: {complex_task.risk_level:.1f}")
    print(f"    Domains: {complex_task.domains}")
    print(f"    Enhancements: {[e.value for e in complex_task.enabled_enhancements]}")
    
    # 测试多领域任务
    multi_domain = decider.analyze("帮我写一个Python爬虫来抓取网页数据并存入数据库")
    print(f"\n  Multi-domain: '{multi_domain.raw_query[:20]}...'")
    print(f"    Domains: {multi_domain.domains}")
    print(f"    Multi-domain required: {multi_domain.requires_multi_domain}")
    print(f"    Enhancements: {[e.value for e in multi_domain.enabled_enhancements]}")
    
    print("  [PASS]")
    return True


async def test_seamless_enhancer():
    """Test 2: 无缝增强器"""
    print("\n" + "="*50)
    print("Test 2: Seamless Enhancer")
    print("="*50)
    
    from seamless_enhancer import SeamlessEnhancer
    
    # 创建增强器
    async def mock_handler(query):
        await asyncio.sleep(0.01)
        return f"处理完成: {query[:30]}..."
    
    enhancer = SeamlessEnhancer(
        base_handler=mock_handler,
        config={"max_retries": 1}
    )
    
    # 测试对话
    queries = [
        "你好",
        "帮我写一个排序算法",
        "设计一个高并发的订单系统架构"
    ]
    
    for query in queries:
        result = await enhancer.chat(query)
        stats = enhancer.get_stats()
        print(f"\n  Query: '{query[:30]}...'")
        print(f"    Result: {result[:50]}...")
        print(f"    Stats: total={stats['total_requests']}, success_rate={stats['success_rate']:.1%}")


async def test_enhanced_integration():
    """Test 3: 增强集成"""
    print("\n" + "="*50)
    print("Test 3: Enhanced Integration")
    print("="*50)
    
    from enhanced_integration import create_enhanced_agent
    
    agent = create_enhanced_agent()
    
    # 第一次对话 - 会创建技能
    print("\n  First interaction:")
    result1 = await agent.chat("帮我写一个Python函数来计算斐波那契数列")
    print(f"    Query: 计算斐波那契数列")
    print(f"    Result: {result1[:50]}...")
    
    # 第二次对话 - 应该匹配技能
    print("\n  Second interaction (should match skill):")
    result2 = await agent.chat("斐波那契数列")
    print(f"    Query: 斐波那契数列")
    print(f"    Result: {result2[:50]}...")
    
    # 检查技能库
    skills = agent.get_skills_summary()
    print(f"\n  Skills summary:")
    print(f"    Total skills: {skills['total_skills']}")
    print(f"    Total uses: {skills['total_uses']}")
    
    # 检查教训库
    lessons = agent.get_lessons_summary()
    print(f"\n  Lessons summary:")
    print(f"    Total lessons: {lessons['total_lessons']}")
    
    print("  [PASS]")
    return True


async def test_automation_flow():
    """Test 4: 自动化流程"""
    print("\n" + "="*50)
    print("Test 4: Automation Flow (Progressive + Reflective)")
    print("="*50)
    
    from enhanced_integration import create_enhanced_agent
    
    agent = create_enhanced_agent({
        "auto_learn": True,
        "auto_reflect": True
    })
    
    # 模拟用户无感知的多轮对话
    queries = [
        ("你好", "问候"),
        ("帮我写一个快速排序", "代码生成"),
        ("优化一下排序性能", "优化任务"),
        ("设计一个缓存系统", "系统设计")
    ]
    
    print("\n  Simulating user interactions:")
    for query, desc in queries:
        result = await agent.chat(query)
        print(f"\n    [{desc}] {query}")
        print(f"      -> {result[:40]}...")
    
    # 最终统计
    stats = agent.get_integration_stats()
    print("\n  Final Stats:")
    print(f"    Skills created: {stats['skills']['total_skills']}")
    print(f"    Total skill uses: {stats['skills']['total_uses']}")
    print(f"    Lessons learned: {stats['lessons']['total_lessons']}")
    print(f"    Agent success rate: {stats['enhancer']['success_rate']:.1%}")
    
    print("  [PASS]")
    return True


async def test_quick_chat():
    """Test 5: 快速聊天"""
    print("\n" + "="*50)
    print("Test 5: Quick Chat API")
    print("="*50)
    
    from enhanced_integration import quick_chat
    
    result = await quick_chat("帮我写一个hello world程序")
    print(f"  Query: 帮我写一个hello world程序")
    print(f"  Result: {result}")
    
    print("  [PASS]")
    return True


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("[SEAMLESS ENHANCER TEST SUITE]")
    print("User-unaware Progressive + Reflective Learning")
    print("="*60)
    
    results = []
    
    tests = [
        ("Trigger Decider", test_trigger_decider),
        ("Seamless Enhancer", test_seamless_enhancer),
        ("Enhanced Integration", test_enhanced_integration),
        ("Automation Flow", test_automation_flow),
        ("Quick Chat API", test_quick_chat)
    ]
    
    for name, test_func in tests:
        try:
            await test_func()
            results.append((name, True))
            print(f"\n  [PASS] {name}")
        except Exception as e:
            print(f"\n  [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("[TEST SUMMARY]")
    print("="*60)
    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    for name, success in results:
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {name}")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
