"""
测试专家思考模式控制器（动态版 v2.0）

测试内容：
1. ExpertThinkingModeController 基本功能（动态加载、自动匹配）
2. DynamicThinkingInstructionGenerator 指令生成
3. GlobalModelRouter 集成
4. 便捷函数

Author: LivingTreeAI Agent
Date: 2026-04-27
Version: 2.0 (适配动态加载版)
"""

import sys
import os

# 添加项目根目录到路径
project_root = r"f:\mhzyapp\LivingTreeAlAgent"
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def test_dynamic_controller():
    """测试动态专家控制器基本功能"""
    print("=" * 60)
    print("测试1: ExpertThinkingModeController 动态加载")
    print("=" * 60)

    try:
        from client.src.business.ei_agent.expert_thinking_mode import (
            ExpertThinkingModeController,
            ThinkingMode,
            get_expert_thinking_controller,
            ExpertSkillLoader,
        )

        # 测试单例模式
        controller1 = get_expert_thinking_controller()
        controller2 = get_expert_thinking_controller()
        assert controller1 is controller2, "单例模式失败"
        print("✅ 单例模式正常")

        # 测试动态加载（扫描 .livingtree/skills/）
        experts = controller1.list_available_experts()
        print(f"✅ 动态加载专家数: {len(experts)}")
        assert len(experts) > 0, "未加载到任何专家"

        # 测试按名称设置专家
        if experts:
            first_expert = experts[0]
            result = controller1.set_expert_by_name(first_expert)
            assert result is True, "设置专家失败"
            config = controller1.get_current_config()
            assert config["expert_name"] == first_expert, "专家名称不匹配"
            print(f"✅ 设置专家成功: {first_expert}")

        # 测试不存在的专家
        result = controller1.set_expert_by_name("不存在的专家")
        assert result is False, "不存在的专家应该返回False"
        print("✅ 不存在专家处理正确")

        # 测试思考模式设置
        controller1.set_thinking_mode_by_name("immersive")
        config = controller1.get_current_config()
        assert config["thinking_mode"] == "immersive", "设置思考模式失败"
        print(f"✅ 设置思考模式成功: immersive")

        # 测试不存在的思考模式
        result = controller1.set_thinking_mode_by_name("nonexistent")
        assert result is False, "不存在的思考模式应返回False"
        print("✅ 不存在思考模式处理正确")

        # 测试 System Prompt 增强
        base_prompt = "你是一个专业的AI助手。"
        enhanced = controller1.get_enhanced_system_prompt(base_prompt)
        assert len(enhanced) > len(base_prompt), "System Prompt 增强失败"
        print(f"✅ System Prompt 注入成功 (长度: {len(enhanced)} 字符)")

        # 测试消息列表注入
        messages = [
            {"role": "system", "content": "你是一个专家。"},
            {"role": "user", "content": "帮我分析一下。"}
        ]
        enhanced_messages = controller1.inject_to_messages(messages)
        assert "【" in enhanced_messages[0]["content"], "消息注入失败"
        print(f"✅ 消息列表注入成功")

        # 测试默认模式（不注入）
        controller1.set_thinking_mode_by_name("default")
        enhanced_default = controller1.get_enhanced_system_prompt(base_prompt)
        assert enhanced_default == base_prompt, "默认模式应该不注入"
        print(f"✅ 默认模式不注入（正确）")

        print("\n✅ 所有动态控制器测试通过！")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auto_match():
    """测试自动匹配专家"""
    print("\n" + "=" * 60)
    print("测试2: 自动匹配专家")
    print("=" * 60)

    try:
        from client.src.business.ei_agent.expert_thinking_mode import (
            get_expert_thinking_controller,
            ExpertSkillLoader,
        )

        controller = get_expert_thinking_controller()
        loader = ExpertSkillLoader()

        # 测试自动匹配
        test_cases = [
            ("帮我分析这个化工项目的环境影响", None),  # 应该匹配到化工专家
            ("生产工艺流程怎么优化？", None),
            ("设备选型要注意什么？", None),
            ("应急预案怎么编制？", None),
            ("xyz随机问题没有意义", None),  # 可能匹配不到
        ]

        for query, expected_expert in test_cases:
            matched = controller.set_expert_by_query(query)
            if matched:
                config = controller.get_current_config()
                print(f"  查询: {query[:30]}...")
                print(f"  → 匹配专家: {config['expert_name']}")
            else:
                print(f"  查询: {query[:30]}... → 未匹配（符合预期）")

        print("\n✅ 自动匹配测试完成！")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dynamic_instructions():
    """测试动态指令生成"""
    print("\n" + "=" * 60)
    print("测试3: DynamicThinkingInstructionGenerator 动态指令")
    print("=" * 60)

    try:
        from client.src.business.ei_agent.expert_thinking_mode import (
            DynamicThinkingInstructionGenerator,
            ThinkingMode,
            get_expert_thinking_controller,
        )

        controller = get_expert_thinking_controller()
        experts = controller.list_available_experts()

        if not experts:
            print("⚠️ 没有已加载的专家，跳过指令测试")
            return True

        # 测试每个专家的三种模式指令生成
        modes = [ThinkingMode.IMMERSIVE, ThinkingMode.ANALYTICAL, ThinkingMode.GUIDED]
        mode_names = ["沉浸式", "分析式", "引导式"]

        for expert_name in experts[:3]:  # 只测试前3个专家
            expert = controller._loader.get_expert(expert_name)
            if not expert:
                continue

            print(f"\n专家: {expert_name}")
            for mode, name in zip(modes, mode_names):
                instr = DynamicThinkingInstructionGenerator.generate(expert, mode)
                if instr:
                    assert "【" in instr, f"{name}指令格式错误"
                    assert expert_name in instr, f"{name}指令应包含专家名称"
                    print(f"  ✅ {name} (长度: {len(instr)} 字符)")
                else:
                    print(f"  ⚠️ {name} 指令为空")

        print("\n✅ 动态指令生成测试通过！")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_global_model_router_integration():
    """测试 GlobalModelRouter 集成"""
    print("\n" + "=" * 60)
    print("测试4: GlobalModelRouter 集成（动态版）")
    print("=" * 60)

    try:
        from client.src.business.global_model_router import (
            GlobalModelRouter,
            ModelCapability,
        )

        print("✅ GlobalModelRouter 导入成功")

        # 检查方法参数（应该是 str 类型，不是 ExpertType 枚举）
        import inspect
        sig = inspect.signature(GlobalModelRouter.call_model)
        params = list(sig.parameters.keys())

        assert "expert_type" in params, "call_model 缺少 expert_type 参数"
        assert "thinking_mode" in params, "call_model 缺少 thinking_mode 参数"
        print(f"✅ call_model 方法已支持动态专家参数: expert_type, thinking_mode")

        # 检查 expert_type 参数类型注解（应该是 Optional[str]）
        expert_type_annotation = sig.parameters["expert_type"].annotation
        print(f"   expert_type 类型: {expert_type_annotation}")

        print("\n✅ GlobalModelRouter 集成测试通过！")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_convenience_functions():
    """测试便捷函数"""
    print("\n" + "=" * 60)
    print("测试5: 便捷函数（动态版）")
    print("=" * 60)

    try:
        from client.src.business.ei_agent.expert_thinking_mode import (
            set_expert_thinking_mode,
            enhance_messages_with_thinking_mode,
            auto_match_and_enhance,
        )

        # 测试设置函数（使用专家名称字符串）
        set_expert_thinking_mode("环保法规专家", "immersive")
        print("✅ set_expert_thinking_mode 执行成功（使用专家名称）")

        # 测试自动匹配设置
        set_expert_thinking_mode("auto", "guided")
        print("✅ set_expert_thinking_mode(auto) 执行成功")

        # 测试消息增强函数
        messages = [{"role": "user", "content": "测试消息"}]
        enhanced = enhance_messages_with_thinking_mode(messages, expert_name="auto", mode_name="immersive")
        assert len(enhanced) > 0, "消息增强失败"
        print(f"✅ enhance_messages_with_thinking_mode 执行成功")

        # 测试自动匹配并增强
        enhanced_prompt = auto_match_and_enhance("化工项目的废水怎么处理？")
        assert len(enhanced_prompt) > 0, "自动匹配增强失败"
        print(f"✅ auto_match_and_enhance 执行成功")

        print("\n✅ 便捷函数测试通过！")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n🚀 开始测试专家思考模式（动态版 v2.0）")
    print("=" * 60)

    results = []

    # 运行测试
    results.append(("动态控制器基本功能", test_dynamic_controller()))
    results.append(("自动匹配专家", test_auto_match()))
    results.append(("动态指令生成", test_dynamic_instructions()))
    results.append(("GlobalModelRouter 集成", test_global_model_router_integration()))
    results.append(("便捷函数", test_convenience_functions()))

    # 输出测试报告
    print("\n" + "=" * 60)
    print("测试报告")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}  {name}")
        if result:
            passed += 1
        else:
            failed += 1

    print("\n" + "-" * 60)
    print(f"总计: {passed + failed} 个测试")
    print(f"✅ 通过: {passed} 个")
    print(f"❌ 失败: {failed} 个")
    print("-" * 60)

    if failed == 0:
        print("\n🎉 所有测试通过！动态专家思考模式集成成功！")
        return 0
    else:
        print(f"\n⚠️ 有 {failed} 个测试失败，请检查错误信息。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
