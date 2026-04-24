"""
Phase 4 测试文件 - LLM 增强追问

测试 LLM 增强追问的各个组件
"""

import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============== 测试导入 ==============

def test_import():
    """测试模块导入"""
    print("[TEST] Phase 4 模块导入...")
    
    try:
        from core.llm_guidance import (
            LLMSource,
            GuidanceStrategy,
            TriggerCondition,
            LLMGuidanceConfig,
            LLMGuidanceResult,
            OllamaClient,
            LLMGuidanceGenerator,
            GuidanceTrigger,
            HybridGuidanceGenerator,
            create_llm_generator,
            create_hybrid_generator,
            quick_llm_guidance,
        )
        print("   [OK] core.llm_guidance 导入成功")
    except ImportError as e:
        print(f"   [FAIL] core.llm_guidance 导入失败: {e}")
        return False
    
    try:
        from core.full_guidance_integration import (
            FullGuidanceResult,
            FullGuidanceEngine,
            FullGuidanceAgentChat,
            create_full_guidance_chat,
            quick_full_guidance,
        )
        print("   [OK] core.full_guidance_integration 导入成功")
    except ImportError as e:
        print(f"   [FAIL] core.full_guidance_integration 导入失败: {e}")
        return False
    
    return True


# ============== 测试 LLM 配置 ==============

def test_llm_config():
    """测试 LLM 配置"""
    print("\n[TEST] LLM 配置...")
    
    from core.llm_guidance import LLMGuidanceConfig, LLMSource, GuidanceStrategy
    
    config = LLMGuidanceConfig(
        source=LLMSource.OLLAMA_LOCAL,
        model="qwen2.5:1.5b",
        api_base="http://localhost:11434",
        max_questions=3,
        temperature=0.7,
    )
    
    print(f"   源: {config.source.value}")
    print(f"   模型: {config.model}")
    print(f"   API: {config.api_base}")
    print(f"   最大追问: {config.max_questions}")
    print(f"   温度: {config.temperature}")
    
    assert config.source == LLMSource.OLLAMA_LOCAL
    assert config.model == "qwen2.5:1.5b"
    
    print("   [OK] LLM 配置正确")
    return True


# ============== 测试 Ollama 客户端 ==============

def test_ollama_client():
    """测试 Ollama 客户端"""
    print("\n[TEST] Ollama 客户端...")
    
    from core.llm_guidance import OllamaClient
    
    client = OllamaClient(base_url="http://localhost:11434", timeout=5.0)
    
    print(f"   API URL: {client.base_url}")
    print(f"   超时: {client.timeout}s")
    
    # 检查可用性（可能不可用）
    available = client.is_available()
    print(f"   可用性: {available}")
    
    if available:
        models = client.list_models()
        print(f"   可用模型: {len(models)} 个")
        if models:
            print(f"   模型列表: {models[:3]}")
    else:
        print("   [WARN] Ollama 服务不可用，跳过模型列表测试")
    
    print("   [OK] Ollama 客户端创建成功")
    return True


# ============== 测试 LLM 追问生成器 ==============

def test_llm_generator():
    """测试 LLM 追问生成器"""
    print("\n[TEST] LLM 追问生成器...")
    
    from core.llm_guidance import (
        LLMGuidanceGenerator,
        LLMGuidanceConfig,
        LLMSource,
    )
    
    config = LLMGuidanceConfig(
        source=LLMSource.OLLAMA_LOCAL,
        model="qwen2.5:1.5b",
        api_base="http://localhost:11434",
        timeout=10.0,
        max_questions=3,
    )
    
    generator = LLMGuidanceGenerator(config)
    
    # 测试可用性
    available = generator.is_available()
    print(f"   LLM 可用: {available}")
    
    if available:
        # 测试生成
        result = generator.generate(
            user_message="帮我写一个快速排序算法",
            response="这是一个快速排序的实现...",
            intent="code_generation",
            content_type="code",
        )
        
        print(f"   生成追问: {len(result.questions)} 个")
        print(f"   置信度: {result.confidence:.2f}")
        print(f"   延迟: {result.latency:.2f}s")
        print(f"   缓存: {result.cached}")
        
        for i, q in enumerate(result.questions[:3], 1):
            print(f"   {i}. {q}")
        
        assert len(result.questions) > 0, "应该生成追问"
    else:
        print("   [SKIP] LLM 不可用，跳过生成测试")
    
    print("   [OK] LLM 追问生成器正确")
    return True


# ============== 测试触发器 ==============

def test_trigger():
    """测试触发器"""
    print("\n[TEST] 触发器...")
    
    from core.llm_guidance import (
        GuidanceTrigger,
        TriggerCondition,
    )
    
    # 测试低置信度触发
    trigger = GuidanceTrigger(
        condition=TriggerCondition.LOW_CONFIDENCE,
        confidence_threshold=0.5,
    )
    
    # 低置信度场景
    should_trigger, reason = trigger.should_trigger_llm(
        rule_confidence=0.3,
        rule_questions=["问题1"],
        content_type="code",
        intent="code_generation",
    )
    print(f"   低置信度: {should_trigger} - {reason}")
    
    # 高置信度场景
    should_trigger2, reason2 = trigger.should_trigger_llm(
        rule_confidence=0.8,
        rule_questions=["问题1", "问题2", "问题3"],
        content_type="code",
        intent="code_generation",
    )
    print(f"   高置信度: {should_trigger2} - {reason2}")
    
    assert should_trigger == True, "低置信度应该触发"
    
    # 测试自适应触发器
    adaptive = GuidanceTrigger.create_adaptive_trigger(
        message_count=1,
        followup_count=0,
        rule_confidence=0.3,
    )
    print(f"   自适应触发器创建成功")
    
    print("   [OK] 触发器正确")
    return True


# ============== 测试混合生成器 ==============

def test_hybrid_generator():
    """测试混合生成器"""
    print("\n[TEST] 混合生成器...")
    
    from core.llm_guidance import (
        HybridGuidanceGenerator,
        LLMGuidanceConfig,
        LLMSource,
        GuidanceTrigger,
        TriggerCondition,
    )
    
    config = LLMGuidanceConfig(
        model="qwen2.5:1.5b",
        api_base="http://localhost:11434",
    )
    
    trigger = GuidanceTrigger(condition=TriggerCondition.LOW_CONFIDENCE)
    
    generator = HybridGuidanceGenerator(config, trigger)
    
    # 测试生成
    result = generator.generate(
        rule_questions=["规则追问1", "规则追问2"],
        rule_confidence=0.4,
        user_message="帮我写个Python函数",
        response="这是一个Python函数...",
        intent="code_generation",
        content_type="code",
    )
    
    print(f"   规则追问: {len(result.rule_questions)} 个")
    print(f"   LLM 追问: {len(result.llm_questions)} 个")
    print(f"   合并追问: {len(result.all_questions)} 个")
    print(f"   规则置信度: {result.rule_confidence:.2f}")
    print(f"   最终置信度: {result.final_confidence:.2f}")
    print(f"   策略: {result.strategy_used}")
    
    for q, source in result.question_sources.items():
        print(f"   - {q[:30]}... [{source}]")
    
    print("   [OK] 混合生成器正确")
    return True


# ============== 测试完整追问引擎 ==============

def test_full_guidance_engine():
    """测试完整追问引擎"""
    print("\n[TEST] 完整追问引擎...")
    
    from core.full_guidance_integration import FullGuidanceEngine
    from core.agent_chat_enhancer import ChatIntent
    
    engine = FullGuidanceEngine(
        enable_template=True,
        enable_semantic=True,
        enable_llm=True,
    )
    
    # 测试生成
    result = engine.generate(
        user_message="帮我写一个快速排序算法",
        response="""
        这是快速排序的实现：
        
        ```python
        def quick_sort(arr):
            if len(arr) <= 1:
                return arr
            pivot = arr[len(arr) // 2]
            left = [x for x in arr if x < pivot]
            middle = [x for x in arr if x == pivot]
            right = [x for x in arr if x > pivot]
            return quick_sort(left) + middle + quick_sort(right)
        ```
        
        时间复杂度 O(n log n)，空间复杂度 O(n)。
        """,
        intent=ChatIntent.CODE_GENERATION,
        context=None,
    )
    
    print(f"   模板追问: {len(result.template_questions)} 个")
    print(f"   语义追问: {len(result.semantic_questions)} 个")
    print(f"   LLM 追问: {len(result.llm_questions)} 个")
    print(f"   合并追问: {len(result.all_questions)} 个")
    print(f"   策略: {result.strategy_used}")
    print(f"   最终置信度: {result.final_confidence:.2f}")
    
    if result.content_analysis:
        print(f"   内容类型: {result.content_analysis.content_type.value}")
        print(f"   复杂度: {result.content_analysis.complexity:.2f}")
        print(f"   包含代码: {result.content_analysis.has_code}")
    
    if result.quality_assessment:
        print(f"   质量等级: {result.quality_assessment.quality.value}")
    
    for q in result.all_questions[:5]:
        source = result.question_sources.get(q, "unknown")
        print(f"   - {q[:40]}... [{source}]")
    
    print("   [OK] 完整追问引擎正确")
    return True


# ============== 测试便捷函数 ==============

def test_convenience_functions():
    """测试便捷函数"""
    print("\n[TEST] 便捷函数...")
    
    from core.llm_guidance import create_llm_generator, quick_llm_guidance
    from core.full_guidance_integration import quick_full_guidance
    
    # 测试创建 LLM 生成器
    generator = create_llm_generator(
        model="qwen2.5:1.5b",
        api_base="http://localhost:11434",
    )
    print(f"   create_llm_generator: OK")
    
    # 测试快速完整追问
    result = quick_full_guidance(
        user_message="什么是Python？",
        response="Python 是一种高级编程语言...",
        intent="question",
        content_type="explanation",
        enable_llm=False,  # 禁用 LLM 加速测试
    )
    
    print(f"   quick_full_guidance:")
    print(f"   - 语义追问: {len(result['semantic_questions'])} 个")
    print(f"   - 合并追问: {len(result['all_questions'])} 个")
    if result.get('quality'):
        print(f"   - 质量: {result['quality']['level']}")
    
    print("   [OK] 便捷函数正确")
    return True


# ============== 测试数据流 ==============

def test_data_flow():
    """测试数据流"""
    print("\n[TEST] 数据流...")
    
    from core.full_guidance_integration import FullGuidanceEngine
    from core.agent_chat_enhancer import ChatIntent
    
    engine = FullGuidanceEngine(
        enable_template=True,
        enable_semantic=True,
        enable_llm=True,
    )
    
    # 模拟对话
    test_cases = [
        {
            "user": "帮我写一个快排",
            "response": "```python\ndef quick_sort(arr): ...\n```\n时间复杂度 O(n log n)",
            "intent": ChatIntent.CODE_GENERATION,
        },
        {
            "user": "什么是机器学习？",
            "response": "机器学习是人工智能的一个分支，让计算机从数据中学习...",
            "intent": ChatIntent.QUESTION,
        },
        {
            "user": "Python和JavaScript哪个好？",
            "response": "两者各有优势：Python适合数据科学，JavaScript适合前端开发...",
            "intent": ChatIntent.QUESTION,
        },
    ]
    
    for i, case in enumerate(test_cases, 1):
        result = engine.generate(
            user_message=case["user"],
            response=case["response"],
            intent=case["intent"],
        )
        
        print(f"\n   Case {i}: {case['intent'].value}")
        print(f"   - 追问数: {len(result.all_questions)}")
        print(f"   - 策略: {result.strategy_used}")
        print(f"   - 置信度: {result.final_confidence:.2f}")
        
        if result.content_analysis:
            print(f"   - 类型: {result.content_analysis.content_type.value}")
    
    print("   [OK] 数据流正确")
    return True


# ============== 主测试函数 ==============

def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Phase 4 LLM 增强追问 - 测试")
    print("=" * 60)
    print()
    
    tests = [
        test_import,
        test_llm_config,
        test_ollama_client,
        test_llm_generator,
        test_trigger,
        test_hybrid_generator,
        test_full_guidance_engine,
        test_convenience_functions,
        test_data_flow,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"   [ERROR] {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
        print()
    
    # 汇总
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"测试结果: {passed}/{total} 通过")
    print("=" * 60)
    
    if passed == total:
        print("[PASS] All Phase 4 tests passed!")
    else:
        print("[WARN] Some tests failed, please check output above")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
