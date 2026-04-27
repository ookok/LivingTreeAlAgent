"""
RYS (Repeat Yourself) 层重复推理引擎 测试
==========================================

测试内容：
1. RYSBlock / RYSConfig 数据结构
2. 执行序列生成
3. 层分区估算
4. 预设配置
5. 配置验证
6. GlobalModelRouter 集成（参数检查）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_rys_block():
    print("测试1: RYSBlock 数据结构")
    print("-" * 60)

    from client.src.business.rys_engine import RYSBlock

    block = RYSBlock(21, 22)
    assert block.start == 21
    assert block.end == 22
    assert block.repeat_count == 1
    assert block.to_tuple() == (21, 22)
    print(f"  ✅ RYSBlock(21,22): repeat_count={block.repeat_count}")

    # 批量重复
    block2 = RYSBlock(5, 8)
    assert block2.repeat_count == 3
    print(f"  ✅ RYSBlock(5,8): repeat_count={block2.repeat_count}")

    # 边界检查
    try:
        RYSBlock(5, 5)
        assert False, "应该抛出异常"
    except ValueError:
        print(f"  ✅ 边界检查: start >= end 正确拒绝")

    try:
        RYSBlock(22, 21)
        assert False, "应该抛出异常"
    except ValueError:
        print(f"  ✅ 边界检查: start > end 正确拒绝")


def test_rys_config():
    print("\n测试2: RYSConfig 配置")
    print("-" * 60)

    from client.src.business.rys_engine import RYSConfig, RYSBlock

    # 基线配置
    baseline = RYSConfig()
    assert baseline.is_baseline
    assert baseline.total_extra_layers == 0
    print(f"  ✅ 基线配置: is_baseline={baseline.is_baseline}")

    # 单层重复
    config = RYSConfig(blocks=[RYSBlock(21, 22)], num_layers=36)
    assert not config.is_baseline
    assert config.total_extra_layers == 1
    print(f"  ✅ 单层重复: blocks={config.blocks}, extra={config.total_extra_layers}")

    # 双层重复
    config2 = RYSConfig(blocks=[RYSBlock(12, 13), RYSBlock(24, 25)], num_layers=36)
    assert config2.total_extra_layers == 2
    print(f"  ✅ 双层重复: blocks={config2.blocks}, extra={config2.total_extra_layers}")

    # 序列化/反序列化
    d = config2.to_dict()
    restored = RYSConfig.from_dict(d)
    assert restored.total_extra_layers == config2.total_extra_layers
    print(f"  ✅ 序列化/反序列化: to_dict → from_dict 正确")

    # 去重
    config3 = RYSConfig(blocks=[RYSBlock(21, 22), RYSBlock(21, 22)], num_layers=36)
    assert config3.total_extra_layers == 1
    print(f"  ✅ 去重: 重复块正确合并")


def test_execution_sequence():
    print("\n测试3: 执行序列生成")
    print("-" * 60)

    from client.src.business.rys_engine import RYSConfig, RYSBlock

    # 基线（无重复）
    config = RYSConfig(num_layers=10)
    seq = config.get_execution_sequence(10)
    assert seq == list(range(10))
    print(f"  ✅ 基线序列: len={len(seq)}")

    # 单层重复（第5层）
    config = RYSConfig(blocks=[RYSBlock(5, 6)], num_layers=10)
    seq = config.get_execution_sequence(10)
    assert seq[5] == 5  # 第一次经过第5层
    assert seq[6] == 5  # 第二次经过第5层（重复）
    assert len(seq) == 11  # 额外1层
    print(f"  ✅ 单层重复(5,6): {seq}, len={len(seq)}")

    # 多层重复（第3-5层）
    config = RYSConfig(blocks=[RYSBlock(3, 5)], num_layers=10)
    seq = config.get_execution_sequence(10)
    assert seq[3:5] == [3, 4]  # 第一次
    assert seq[5:7] == [3, 4]  # 第二次（重复）
    assert len(seq) == 12  # 额外2层
    print(f"  ✅ 多层重复(3,5): {seq}, len={len(seq)}")

    # 双块重复
    config = RYSConfig(blocks=[RYSBlock(2, 3), RYSBlock(7, 8)], num_layers=10)
    seq = config.get_execution_sequence(10)
    assert len(seq) == 12  # 额外2层
    print(f"  ✅ 双块重复: len={len(seq)}")


def test_layer_zones():
    print("\n测试4: 层分区估算")
    print("-" * 60)

    from client.src.business.rys_engine import estimate_layer_zones, LayerZone

    # Qwen3-4B: 36 层
    zones = estimate_layer_zones(36)
    assert zones.total == 36
    assert zones.encode_end == 6  # ~17%
    assert zones.decode_start == 27  # ~75%
    assert zones.reason_start == 6
    assert zones.reason_end == 27
    assert len(zones.reason_layers) == 21  # 推理区21层
    print(f"  ✅ 36层分区: encode=0-{zones.encode_end-1}, reason={zones.reason_start}-{zones.reason_end-1}, decode={zones.decode_start}-35")

    # Qwen3.5-9B: 40 层
    zones40 = estimate_layer_zones(40)
    assert zones40.total == 40
    print(f"  ✅ 40层分区: encode=0-{zones40.encode_end-1}, reason={zones40.reason_start}-{zones40.reason_end-1}, decode={zones40.decode_start}-39")

    # 安全检查
    assert zones.is_safe_to_repeat(10)  # 推理区
    assert not zones.is_safe_to_repeat(2)  # 编码区
    assert not zones.is_safe_to_repeat(30)  # 解码区
    print(f"  ✅ 安全检查: 10层安全={zones.is_safe_to_repeat(10)}, 2层安全={zones.is_safe_to_repeat(2)}, 30层安全={zones.is_safe_to_repeat(30)}")


def test_presets():
    print("\n测试5: 预设配置")
    print("-" * 60)

    from client.src.business.rys_engine import RYSPreset

    presets = {
        "Qwen3-4B 最优": RYSPreset.for_qwen3_4b(),
        "Qwen3.5-4B 推荐": RYSPreset.for_qwen3_5_4b(),
        "情绪推理": RYSPreset.for_emotion(),
        "数学推理": RYSPreset.for_math(),
        "综合优化": RYSPreset.for_comprehensive(),
    }

    for name, config in presets.items():
        assert not config.is_baseline
        assert config.total_extra_layers >= 1
        print(f"  ✅ {name}: blocks={config.blocks}, extra={config.total_extra_layers}")


def test_suggest_config():
    print("\n测试6: 智能推荐")
    print("-" * 60)

    from client.src.business.rys_engine import RYSEngine, RYSConfig

    engine = RYSEngine()

    # 各任务类型推荐
    for task_type in ["general", "emotion", "math", "reasoning", "chat"]:
        config = engine.suggest_config("qwen3.5:4b", task_type)
        assert not config.is_baseline or task_type == "general"
        if not config.is_baseline:
            assert config.total_extra_layers >= 1
        print(f"  ✅ {task_type}: blocks={config.blocks}, extra={config.total_extra_layers}")


def test_validate_config():
    print("\n测试7: 配置验证")
    print("-" * 60)

    from client.src.business.rys_engine import RYSEngine, RYSConfig, RYSBlock

    engine = RYSEngine()

    # 安全配置
    safe, reason = engine.validate_config(
        RYSConfig(blocks=[RYSBlock(21, 22)], num_layers=36),
        "qwen3.5:4b",
    )
    assert safe
    print(f"  ✅ 安全配置: {reason}")

    # 碰到编码层
    unsafe, reason = engine.validate_config(
        RYSConfig(blocks=[RYSBlock(2, 3)], num_layers=36),
        "qwen3.5:4b",
    )
    assert not unsafe  # 注意：编码层边界可能不同
    print(f"  ✅ 编码层检测: safe={unsafe}, reason={reason}")

    # 重复过多
    unsafe, reason = engine.validate_config(
        RYSConfig(blocks=[RYSBlock(10, 20)], num_layers=36),
        "qwen3.5:4b",
    )
    assert not unsafe
    print(f"  ✅ 过多重复检测: safe={unsafe}, reason={reason}")


def test_model_analysis():
    print("\n测试8: 模型分析报告")
    print("-" * 60)

    from client.src.business.rys_engine import RYSEngine

    engine = RYSEngine()

    # 已知模型（使用缓存）
    report = engine.print_model_analysis("qwen3.5:4b")
    assert "36" in report
    assert "编码层" in report
    assert "推理层" in report
    assert "解码层" in report
    print(report)

    # 未知模型
    report2 = engine.print_model_analysis("unknown-model")
    assert "无法获取" in report2
    print(f"\n  ✅ 未知模型: {report2.strip()[:50]}...")


def test_scan_configs():
    print("\n测试9: 全量扫描配置生成")
    print("-" * 60)

    from client.src.business.rys_engine import RYSEngine

    engine = RYSEngine()
    configs = engine.generate_full_scan_configs(36)
    # 36层模型，推理区 ~21 层
    assert len(configs) == 21
    print(f"  ✅ 36层模型扫描配置数: {len(configs)} (覆盖推理区 6-26)")


def test_global_model_router_integration():
    print("\n测试10: GlobalModelRouter 集成")
    print("-" * 60)

    import inspect
    from client.src.business.global_model_router import GlobalModelRouter, call_model_sync

    # 检查 call_model 方法签名
    sig = inspect.signature(GlobalModelRouter.call_model)
    params = list(sig.parameters.keys())
    assert "rys_config" in params
    print(f"  ✅ call_model 支持 rys_config 参数: 位置={params.index('rys_config')}")

    # 检查 call_model_sync 函数签名
    sig2 = inspect.signature(call_model_sync)
    params2 = list(sig2.parameters.keys())
    assert "rys_config" in params2
    print(f"  ✅ call_model_sync 支持 rys_config 参数: 位置={params2.index('rys_config')}")

    # 检查 rys_config 类型
    param = sig.parameters["rys_config"]
    print(f"  ✅ 参数类型: default={param.default}, annotation={param.annotation}")


# ── 运行所有测试 ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("RYS 层重复推理引擎 测试")
    print("=" * 60)

    tests = [
        test_rys_block,
        test_rys_config,
        test_execution_sequence,
        test_layer_zones,
        test_presets,
        test_suggest_config,
        test_validate_config,
        test_model_analysis,
        test_scan_configs,
        test_global_model_router_integration,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ❌ {test.__name__} 失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"测试报告")
    print("=" * 60)
    print(f"  ✅ 通过: {passed}")
    print(f"  ❌ 失败: {failed}")
    print(f"  📊 总计: {len(tests)}")
    print("=" * 60)

    if failed == 0:
        print("🎉 所有测试通过！")
    else:
        print(f"⚠️ 有 {failed} 个测试失败")
        sys.exit(1)
