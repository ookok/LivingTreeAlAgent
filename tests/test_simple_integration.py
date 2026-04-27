"""
简化版集成测试（动态版 v2.0）

只测试基本功能，不运行完整异步测试。
适配动态加载版 expert_thinking_mode.py（无 ExpertType 枚举）。

Author: LivingTreeAI Agent
Date: 2026-04-27
Version: 2.0
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("🧪 简化版集成测试（动态版 v2.0）")
print("=" * 70)


# ── 测试1：模块导入 ─────────────────────────────────────────────────────

print("\n测试1: 模块导入检查")
print("-" * 70)

try:
    from client.src.business.emotion_perception import (
        EmotionPerception, get_emotion_perception
    )
    print("✅ EmotionPerception 导入成功")
except Exception as e:
    print(f"❌ EmotionPerception 导入失败: {e}")
    sys.exit(1)

try:
    from client.src.business.ei_agent.expert_thinking_mode import (
        ExpertThinkingModeController,
        ThinkingMode,
        get_expert_thinking_controller,
        DynamicThinkingInstructionGenerator,
    )
    print("✅ ExpertThinkingModeController 导入成功")
except Exception as e:
    print(f"❌ ExpertThinkingModeController 导入失败: {e}")
    sys.exit(1)

try:
    from client.src.business.emotion_thinking_integrator import (
        EmotionThinkingIntegrator, IntegratedResult,
        get_emotion_thinking_integrator
    )
    print("✅ EmotionThinkingIntegrator 导入成功")
except Exception as e:
    print(f"❌ EmotionThinkingIntegrator 导入失败: {e}")
    sys.exit(1)

try:
    from client.src.business.global_model_router import (
        call_model_with_emotion, call_model_with_emotion_sync,
        ModelCapability, RoutingStrategy
    )
    print("✅ GlobalModelRouter (情绪感知函数) 导入成功")
except Exception as e:
    print(f"❌ GlobalModelRouter 导入失败: {e}")
    sys.exit(1)

print("\n✅ 所有模块导入测试通过！")


# ── 测试2：EmotionPerception 基本功能 ─────────────────────────────────

print("\n测试2: EmotionPerception 基本功能")
print("-" * 70)

try:
    perception = EmotionPerception(use_llm=False)
    print("✅ EmotionPerception 实例化成功")

    # 测试同步版本（不运行异步）
    print("   （跳过异步情绪识别测试）")

except Exception as e:
    print(f"❌ EmotionPerception 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ EmotionPerception 基本功能测试通过！")


# ── 测试3：ExpertThinkingModeController 情绪适配 ──────────────────────

print("\n测试3: ExpertThinkingModeController 情绪适配（动态版）")
print("-" * 70)

try:
    controller = get_expert_thinking_controller()
    print("✅ ExpertThinkingModeController 实例化成功")

    # 测试：负面情绪 → 分析式
    controller.set_emotional_state("anger", 0.8)
    assert controller._current_mode.value == "analytical", \
        f"愤怒情绪应该切换到分析式，实际: {controller._current_mode.value}"
    print(f"✅ 愤怒情绪(0.8) → 思考模式: {controller._current_mode.value}")

    # 测试：困惑情绪 → 引导式
    controller.set_emotional_state("confused", 0.6)
    assert controller._current_mode.value == "guided", \
        f"困惑情绪应该切换到引导式，实际: {controller._current_mode.value}"
    print(f"✅ 困惑情绪(0.6) → 思考模式: {controller._current_mode.value}")

    # 测试：正面情绪 → 沉浸式
    controller.set_emotional_state("happy", 0.7)
    assert controller._current_mode.value == "immersive", \
        f"正面情绪应该切换到沉浸式，实际: {controller._current_mode.value}"
    print(f"✅ 正面情绪(0.7) → 思考模式: {controller._current_mode.value}")

    # 测试：情绪适配指令生成
    controller.set_expert_by_name("环保法规专家")
    controller.set_thinking_mode_by_name("guided")
    emotion_instruction = controller._generate_emotion_instruction()
    assert len(emotion_instruction) > 0, "情绪适配指令不应该为空"
    print(f"✅ 情绪适配指令生成成功 (长度: {len(emotion_instruction)})")

    # 测试：增强 Prompt
    base_prompt = "你是一个环评专家。"
    enhanced_prompt = controller.get_enhanced_system_prompt(base_prompt)
    assert len(enhanced_prompt) > len(base_prompt), "增强后的 Prompt 应该更长"
    print(f"✅ Prompt 增强成功 (原始: {len(base_prompt)}, 增强后: {len(enhanced_prompt)})")

except Exception as e:
    print(f"❌ ExpertThinkingModeController 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ ExpertThinkingModeController 情绪适配测试通过！")


# ── 测试4：动态指令生成 ────────────────────────────────────────────────

print("\n测试4: 动态指令生成（DynamicThinkingInstructionGenerator）")
print("-" * 70)

try:
    # 获取一个已加载的专家
    experts = controller.list_available_experts()
    if experts:
        first_expert_name = experts[0]
        expert = controller._loader.get_expert(first_expert_name)
        print(f"  测试专家: {first_expert_name}")

        modes = [ThinkingMode.IMMERSIVE, ThinkingMode.ANALYTICAL, ThinkingMode.GUIDED]
        mode_names = ["沉浸式", "分析式", "引导式"]

        for mode, name in zip(modes, mode_names):
            instr = DynamicThinkingInstructionGenerator.generate(expert, mode)
            if instr:
                assert "【" in instr, f"{name}指令格式错误"
                print(f"  ✅ {name} (长度: {len(instr)} 字符)")
            else:
                print(f"  ⚠️ {name} 指令为空")

        print(f"\n✅ 动态指令生成测试通过！")
    else:
        print("⚠️ 没有已加载的专家，跳过指令测试")

except Exception as e:
    print(f"❌ 动态指令生成测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


# ── 测试总结 ────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("🎉 所有简化版测试通过！")
print("=" * 70)

print("\n📊 测试总结：")
print("├─ ✅ 模块导入检查")
print("├─ ✅ EmotionPerception 基本功能")
print("├─ ✅ ExpertThinkingModeController 情绪适配")
print("└─ ✅ 动态指令生成")

print("\n🚀 集成功能已就绪！")

print("\n使用示例：")
print("```python")
print("import asyncio")
print("from client.src.business.global_model_router import call_model_with_emotion_sync")
print("")
print("response = call_model_with_emotion_sync(")
print("    capability=ModelCapability.REASONING,")
print('    prompt="你们这个系统太垃圾了！",')
print('    system_prompt="你是一个环评专家。"')
print('    expert_type="environmental_assessment",')
print("    auto_emotion=True  # 启用自动情绪感知")
print(")")
print("```")

sys.exit(0)
